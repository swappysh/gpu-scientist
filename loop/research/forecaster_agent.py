"""The one file the researcher edits. Seeded with the v7 loop pick.

    forecast(history, catalog_row, origin, h) -> (q10, q50, q90)

history: what is known at the origin (see harness/core.py History):
    history.series[sid] = (days, prices), rows dated <= origin, for every line
    history.catalog[sid] = catalog row (series_id, instrument_class, source, gpu, pricing, stat)
    history.cache = dict for this origin only (reuse work across calls)
catalog_row: the row of the series to forecast. origin: day ordinal.
h: horizon in days (1, 3 or 7). Prices are USD per GPU-hour.

v7 = step-model quantiles of past h-day log changes, recency-weighted
(half-life 14 days), pooled with the same instrument class at 0.7 of the
own weight, q50 drift 0.03 of the median change. (v7's AR(1) momentum is
gone: it added nothing.) After the line or a same-GPU sibling just moved,
the pool is only lines that had just moved too. If a line's moves add up
rather than revert, its h-day band sums h draws of 1-day changes.
The band is centred on the last price pulled back toward its 14-day
median by the share of such gaps the class has undone within h days
(pacsci1), and drawn from past changes net of that pull-back. For a
weekday-bound line, moved windows weigh more when the coming weekdays are
move-prone (pacsci1's per-line weekday rates shrunk to the source's).
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

HALF_LIFE_DAYS = 14.0
DRIFT_WEIGHT = 0.03
POOL_WEIGHT = 0.7
MIN_SAMPLES = 6
RECENT_DAYS = 2  # a line that moved this recently is "just changed": its next moves are bigger
CHI2_6DF_5PCT = 12.59  # move rate differs by weekday at the usual 5% level
QS = (0.1, 0.5, 0.9)
WEEKDAY_PRIOR = 4  # weeks of the source's weekday pattern added to a line's own
LEVEL_DAYS = 14  # a quote is compared with its median over this many past days
LEVEL_LOOKBACK = 60  # days of past pairs used to measure how often moves land on an old price
RUN_DAYS = 7  # two or more moves one way and none back over this many days make a run (pacsci1)
RUN_LOOKBACK = 60  # days of past runs used to measure how often runs go on
UNIFORM = np.random.default_rng(0).random((4000, 7))  # fixed draws for summing 1-day changes


def just_changed(days, vals, at):
    """For each day in `at`: did the line change within RECENT_DAYS before it?"""
    moved = days[1:][vals[1:] != vals[:-1]]
    k = np.searchsorted(moved, at, side="right")
    last = np.where(k > 0, moved[np.maximum(k - 1, 0)] if len(moved) else 0, -10 ** 9)
    return at - last <= RECENT_DAYS


def pairs(days, vals, h):
    """(start rows, end day, log change, just changed at start) for every pair of rows (t, t + h)."""
    if len(days) < 2 or not (vals > 0).all():
        return np.zeros(len(days), bool), np.empty(0, np.int64), np.empty(0), np.empty(0, bool)
    idx = np.minimum(np.searchsorted(days, days + h), len(days) - 1)
    ok = days[idx] == days + h
    return ok, days[idx[ok]], np.log(vals[idx[ok]] / vals[ok]), just_changed(days, vals, days[ok])


def raw_changes(history, sid, h):
    """(end day, h-day log change, just changed at start)."""
    key = ("raw", sid, h)
    if key not in history.cache:
        history.cache[key] = pairs(*history.series[sid], h)
    return history.cache[key][1:]


def own_changes(history, sid, h):
    """Like raw_changes, but net of the pull-back to the median that the class predicts."""
    key = ("own", sid, h)
    if key not in history.cache:
        end, ch, state = raw_changes(history, sid, h)
        ok = history.cache[("raw", sid, h)][0]
        slope = reversion(history, market(history.catalog[sid]), h)
        history.cache[key] = end, np.where(ch != 0, ch - slope * level_gap(history, sid)[ok], 0.0), state
    return history.cache[key]


def market(row):
    """Spot, on-demand, serverless and reserved quotes of a class are different markets (pacsci1)."""
    return row["instrument_class"], row.get("pricing")


def class_changes(history, group, h):
    key = ("class", group, h)
    if key not in history.cache:
        parts = [own_changes(history, s, h) for s in history.series
                 if market(history.catalog[s]) == group]
        end = np.concatenate([p[0] for p in parts])
        ch = np.concatenate([p[1] for p in parts])
        state = np.concatenate([p[2] for p in parts])
        moved = np.concatenate([raw_changes(history, s, h)[1] != 0 for s in history.series
                                if market(history.catalog[s]) == group])
        order = np.argsort(end, kind="stable")
        history.cache[key] = (end[order], ch[order], state[order], moved[order])
    return history.cache[key]


def sibling_moved(history, row, origin):
    """Did the same GPU at the same pricing and class just move at another source? Then this line is about to."""
    key = ("sib", row["instrument_class"], row["gpu"], row["pricing"], row["source"])
    if key not in history.cache:
        history.cache[key] = any(
            just_changed(*history.series[s], np.array([origin]))[0] for s in history.series
            if s != row["series_id"] and len(history.series[s][0]) > 1
            and all(history.catalog[s][f] == row[f] for f in ("instrument_class", "gpu", "pricing")))
    return history.cache[key]


def weekday_bound(history, sid):
    """Does the line re-price on its own weekdays? Chi-square test of its daily move rate across weekdays."""
    key = ("weekday", sid)
    if key not in history.cache:
        end, ch, _ = raw_changes(history, sid, 1)
        moved = np.bincount(end % 7, weights=(ch != 0).astype(float), minlength=7)
        n = np.bincount(end % 7, minlength=7).astype(float)
        p = moved.sum() / max(n.sum(), 1.0)
        exp_m, exp_q = n * p, n * (1 - p)
        ok = (exp_m > 0) & (exp_q > 0)
        chi2 = ((moved - exp_m) ** 2 / np.where(ok, exp_m, 1) + (n - moved - exp_q) ** 2 / np.where(ok, exp_q, 1))[ok].sum()
        history.cache[key] = chi2 > CHI2_6DF_5PCT
    return history.cache[key]


def persistent(history, sid, h):
    """Do the line's h-day changes spread at least h times its 1-day ones (moves add up, no reversion)?"""
    _, c1, _ = raw_changes(history, sid, 1)
    _, ch, _ = raw_changes(history, sid, h)
    return len(ch) > 0 and (ch ** 2).mean() >= h * (c1 ** 2).mean()


def level_gap(history, sid):
    """Log distance of each row's price from its own median over the past LEVEL_DAYS days."""
    key = ("gap", sid)
    if key not in history.cache:
        days, vals = history.series[sid]
        if not len(days):
            history.cache[key] = np.zeros(0)
            return history.cache[key]
        at = days - days[0]  # window i covers grid days at .. at + LEVEL_DAYS, ending at row i
        grid = np.full(at[-1] + 1 + LEVEL_DAYS, np.nan)
        grid[at + LEVEL_DAYS] = np.log(np.maximum(vals, 1e-9))
        win = np.sort(sliding_window_view(grid, LEVEL_DAYS + 1)[at], axis=1)  # NaN sorts last
        c = (~np.isnan(win)).sum(1)
        r = np.arange(len(days))
        med = 0.5 * (win[r, (c - 1) // 2] + win[r, c // 2])
        full = ~np.isnan(grid[at])  # a row exactly LEVEL_DAYS earlier exists
        history.cache[key] = np.where(full, grid[at + LEVEL_DAYS] - med, 0.0)
    return history.cache[key]


def reversion(history, group, h):
    """Class-wide share of a gap from the recent median that is undone within h days (<= 0)."""
    key = ("rev", group, h)
    if key not in history.cache:
        xy = np.zeros(2)
        for s in history.series:
            if market(history.catalog[s]) != group:
                continue
            raw_changes(history, s, h)
            ok, _, y, _ = history.cache[("raw", s, h)]
            x = level_gap(history, s)[ok]
            xy += (x * y).sum(), (x * x).sum()
        history.cache[key] = float(np.clip(xy[0] / xy[1], -1.0, 0.0)) if xy[1] > 0 else 0.0
    return history.cache[key]


def daily_moves(days, vals):
    """Weekday (0 = Monday) and moved flag of every day-to-day step."""
    ok = np.diff(days) == 1
    return (days[1:][ok] - 1) % 7, vals[1:][ok] != vals[:-1][ok]


def weekday_profile(history, catalog_row):
    """Daily move rate by weekday over this source and class, relative to its mean."""
    key = ("wdprof", catalog_row.get("source"), catalog_row["instrument_class"])
    if key not in history.cache:
        hit, n = np.ones(7), np.ones(7)
        for s in history.series:
            c = history.catalog[s]
            if (c.get("source"), c["instrument_class"]) == key[1:]:
                wd, m = daily_moves(*history.series[s])
                np.add.at(n, wd, 1)
                np.add.at(hit, wd, m)
        rate = hit / n
        history.cache[key] = rate / rate.mean()
    return history.cache[key]


def weekday_factor(history, catalog_row, origin, h):
    """How much likelier a move is over the weekdays origin+1..origin+h than over an average h-day window."""
    wd, m = daily_moves(*history.series[catalog_row["series_id"]])
    if not m.any():
        return 1.0
    hit = m.mean() * WEEKDAY_PRIOR * weekday_profile(history, catalog_row)
    n = np.full(7, float(WEEKDAY_PRIOR))
    np.add.at(n, wd, 1)
    np.add.at(hit, wd, m)
    r = np.minimum(hit / n, 0.99)
    chance = [1.0 - np.prod(1.0 - r[(start + np.arange(1, h + 1)) % 7]) for start in range(7)]
    return chance[(origin - 1) % 7] / np.mean(chance)


def old_levels(days, vals, t):
    """Prices other than row t's quoted in the LEVEL_DAYS days before it, with how many days each was quoted."""
    win = vals[(days < days[t]) & (days >= days[t] - LEVEL_DAYS)]
    return np.unique(win[win != vals[t]], return_counts=True)


def level_rate(history, group, h):
    """Share of the market's recent h-day pairs that moved onto a price the line quoted in the LEVEL_DAYS days before (pacsci1)."""
    key = ("level", group, h)
    if key not in history.cache:
        hit = events = 0
        for s, (days, vals) in history.series.items():
            if market(history.catalog[s]) != group:
                continue
            idx = np.minimum(np.searchsorted(days, days + h), len(days) - 1)
            for t in np.flatnonzero((days[idx] == days + h) & (days >= history.origin - LEVEL_LOOKBACK)):
                events += 1
                y = vals[idx[t]]
                hit += y != vals[t] and y in old_levels(days, vals, t)[0]
        history.cache[key] = min(hit / events, 0.9) if events >= 20 else 0.0
    return history.cache[key]


def run_pace(days, vals, origin, h):
    """The run's log move per day since its first move, carried on for h days, or 0 if the line is not in a run (pacsci1)."""
    k = np.searchsorted(days, origin - RUN_DAYS)
    seq = np.log(vals[k:])
    if len(seq) != RUN_DAYS + 1 or days[k] != origin - RUN_DAYS:
        return 0.0
    step = np.sign(np.diff(seq))
    if min((step > 0).sum(), (step < 0).sum()) > 0 or np.abs(step).sum() < 2:
        return 0.0
    span = RUN_DAYS - np.flatnonzero(step)[0]  # days since the day before the run's first move
    return float(seq[-1] - seq[0]) * h / span


def run_rate(history, group, h):
    """Net share (same minus opposite sign) of the market's past runs that went on within h days."""
    key = ("run", group, h)
    if key in history.cache:
        return history.cache[key]
    o, n = history.origin, RUN_LOOKBACK
    grids = []
    for s, (days, vals) in history.series.items():
        if market(history.catalog[s]) == group:
            g = np.full(n + 1, np.nan)
            ok = days >= o - n
            g[days[ok] - (o - n)] = np.log(vals[ok])
            grids.append(g)
    G = np.array(grids)
    d = np.diff(G, axis=1)
    cum = [np.concatenate([np.zeros((len(G), 1)), np.cumsum(x, 1)], 1) for x in (d > 0, d < 0, np.isnan(d))]
    t = np.arange(RUN_DAYS, n + 1 - h)
    up, down, gaps = (c[:, t] - c[:, t - RUN_DAYS] for c in cum)
    sign = np.where((up >= 2) & (down == 0), 1, np.where((down >= 2) & (up == 0), -1, 0)) * (gaps == 0)
    fut = np.sign(G[:, t + h] - G[:, t])
    ev = (sign != 0) & ~np.isnan(fut)
    history.cache[key] = min(max((sign * np.nan_to_num(fut))[ev].sum() / ev.sum(), 0.0), 0.9) if ev.sum() >= 20 else 0.0
    return history.cache[key]


def weighted_quantiles(x, w, qs):
    order = np.argsort(x, kind="stable")
    x, w = x[order], w[order]
    cw = np.cumsum(w)
    return x[np.minimum(np.searchsorted(cw / cw[-1], qs), len(x) - 1)]  # a step: no leak between a held price and a move


def forecast(history, catalog_row, origin, h):
    sid = catalog_row["series_id"]
    last = float(history.series[sid][1][-1])
    pull = reversion(history, market(catalog_row), h) * level_gap(history, sid)[-1]
    x, w = changes(history, catalog_row, origin, h, shift=pull)  # the pull-back comes with a move
    if x is None:
        return (last * float(np.exp(pull)),) * 3
    adds = h > 1 and persistent(history, sid, h)
    if adds:  # sum h draws of the 1-day changes: more and fresher data
        days1 = [changes(history, catalog_row, origin, 1, start=origin + k, shift=pull / h) for k in range(h)]
        if all(x1 is not None for x1, _ in days1):  # day k draws from windows on its own weekday
            x = sum(x1[np.minimum(np.searchsorted(np.cumsum(w1) / w1.sum(), UNIFORM[:, k]), len(x1) - 1)]
                    for k, (x1, w1) in enumerate(days1))
            w = np.ones(len(UNIFORM))
    days, vals = history.series[sid]
    moves = daily_moves(days, vals)[1]
    lv, n = old_levels(days, vals, len(days) - 1)
    r = level_rate(history, market(catalog_row), h) * moves.mean() if len(lv) and len(moves) else 0.0
    if r and (lv > 0).all() and last > 0:  # a line that flicks between prices goes back to one it quoted lately (pacsci1)
        x, w = np.append(x, np.log(lv / last)), np.append(w, w.sum() * r / (1 - r) * n / n.sum())
    q = weighted_quantiles(x, w, QS)
    share = float(moves.mean()) if len(moves) else 0.0  # a line that re-quotes daily has its median pulled too
    drift = DRIFT_WEIGHT + (1 - DRIFT_WEIGHT) * share if adds else DRIFT_WEIGHT  # a daily re-quoter whose moves add up keeps its median change
    u = run_pace(days, vals, origin, h)
    run = run_rate(history, market(catalog_row), h) * u if u else 0.0  # a run tends to go on (pacsci1): its net share of the pace moves the median
    q = last * np.exp([min(q[0], run), drift * q[1] + share * pull + run, max(q[2], run)])
    recent = vals[days > origin - LEVEL_DAYS]
    noise = -reversion(history, market(catalog_row), h) * moves.mean() if len(recent) >= MIN_SAMPLES and len(moves) else 0.0
    if noise > 0:  # a reverting line that re-quotes daily redraws from its recent prices (pacsci1)
        q = (1 - noise) * q + noise * weighted_quantiles(recent, np.ones(len(recent)), QS)
    q10, q50, q90 = (float(v) for v in q)
    return min(q10, q50), q50, max(q90, q50)


def changes(history, catalog_row, origin, h, start=None, shift=0.0):
    """Past h-day log changes of the line and its class pool, with their weights; moves get shift added."""
    sid = catalog_row["series_id"]
    days, vals = history.series[sid]
    end, ch, own_state = own_changes(history, sid, h)
    own_moved = raw_changes(history, sid, h)[1] != 0
    start = origin if start is None else start
    if h < 7 and weekday_bound(history, sid):  # learn from windows that start on the same weekday
        same = (end - h) % 7 == start % 7
        end, ch, own_moved, own_state = end[same], ch[same], own_moved[same], own_state[same]
    p_end, p_ch, p_state, p_moved = class_changes(history, market(catalog_row), h)
    jc = just_changed(days, vals, np.array([origin]))[0]
    if jc or sibling_moved(history, catalog_row, origin):
        p_end, p_ch, p_moved = p_end[p_state], p_ch[p_state], p_moved[p_state]
    if jc and own_state.sum() >= MIN_SAMPLES:  # and the line from its own windows after its past moves
        end, ch, own_moved = end[own_state], ch[own_state], own_moved[own_state]
    if len(ch) + len(p_ch) < MIN_SAMPLES:
        return None, None
    w = 0.5 ** ((origin - end) / HALF_LIFE_DAYS)
    pw = 0.5 ** ((origin - p_end) / HALF_LIFE_DAYS)
    if len(pw) and pw.sum() > 0:
        own_mass = w.sum() if len(w) else 1.0
        pw = pw * (POOL_WEIGHT * own_mass / pw.sum())
    k = weekday_factor(history, catalog_row, start, h) if weekday_bound(history, sid) else 1.0
    w, pw = np.where(own_moved, w * k, w), np.where(p_moved, pw * k, pw)
    return np.concatenate([np.where(own_moved, ch + shift, ch), np.where(p_moved, p_ch + shift, p_ch)]), np.concatenate([w, pw])
