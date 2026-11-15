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
own weight, AR(1) momentum on the last daily change (phi fitted per series
at weight 0.2), q50 drift 0.03 of the median change.
"""

import numpy as np

HALF_LIFE_DAYS = 14.0
DRIFT_WEIGHT = 0.03
POOL_WEIGHT = 0.7
MIN_SAMPLES = 6
MOMENTUM_FIT = 0.2
QS = (0.1, 0.5, 0.9)


def pairs(days, vals, h):
    """(end day, log change) for every pair of rows (t, t + h)."""
    if len(days) < 2 or not (vals > 0).all():
        return np.empty(0, np.int64), np.empty(0)
    idx = np.minimum(np.searchsorted(days, days + h), len(days) - 1)
    ok = days[idx] == days + h
    return days[idx[ok]], np.log(vals[idx[ok]] / vals[ok])


def own_changes(history, sid, h):
    key = ("own", sid, h)
    if key not in history.cache:
        history.cache[key] = pairs(*history.series[sid], h)
    return history.cache[key]


def class_changes(history, group, h):
    key = ("class", group, h)
    if key not in history.cache:
        parts = [own_changes(history, s, h) for s in history.series
                 if history.catalog[s]["instrument_class"] == group]
        end = np.concatenate([p[0] for p in parts])
        ch = np.concatenate([p[1] for p in parts])
        order = np.argsort(end, kind="stable")
        history.cache[key] = (end[order], ch[order])
    return history.cache[key]


def weighted_quantiles(x, w, qs):
    order = np.argsort(x, kind="stable")
    x, w = x[order], w[order]
    cw = np.cumsum(w)
    mid = (cw - 0.5 * w) / cw[-1]
    return np.interp(qs, mid, x)


def lag1_ac(history, sid):
    end, ch = own_changes(history, sid, 1)
    ok = np.diff(end) == 1
    if ok.sum() < 20:
        return 0.0
    x, y = ch[:-1][ok], ch[1:][ok]
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.clip(np.corrcoef(x, y)[0, 1], 0.0, 0.95))


def momentum(days, vals, h, phi):
    """Expected h-day log change under AR(1) on daily changes, from the last 1-day change."""
    if len(days) < 2 or days[-1] - days[-2] != 1:
        return 0.0
    r = float(np.log(vals[-1] / vals[-2]))
    return r * sum(phi ** i for i in range(1, h + 1))


def forecast(history, catalog_row, origin, h):
    sid = catalog_row["series_id"]
    days, vals = history.series[sid]
    last = float(vals[-1])
    end, ch = own_changes(history, sid, h)
    p_end, p_ch = class_changes(history, catalog_row["instrument_class"], h)
    if len(ch) + len(p_ch) < MIN_SAMPLES:
        return last, last, last
    w = 0.5 ** ((origin - end) / HALF_LIFE_DAYS)
    pw = 0.5 ** ((origin - p_end) / HALF_LIFE_DAYS)
    if len(pw) and pw.sum() > 0:
        own_mass = w.sum() if len(w) else 1.0
        pw = pw * (POOL_WEIGHT * own_mass / pw.sum())
    q = weighted_quantiles(np.concatenate([ch, p_ch]), np.concatenate([w, pw]), QS)
    phi = MOMENTUM_FIT * lag1_ac(history, sid)
    last *= float(np.exp(momentum(days, vals, h, phi)))
    q10 = last * float(np.exp(q[0]))
    q90 = last * float(np.exp(q[2]))
    q50 = last * float(np.exp(DRIFT_WEIGHT * q[1]))
    return min(q10, q50), q50, max(q90, q50)
