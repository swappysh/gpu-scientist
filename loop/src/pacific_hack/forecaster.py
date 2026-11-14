"""Step-model forecaster config + walk-forward backtest, scored like the starter.

`ForecasterConfig` is the single mutable object the agent loop tunes, one
change at a time: proposed -> backtested -> kept/killed. Defaults reproduce
the starter's `last_value_empirical` baseline exactly: q50 = last value, q10
and q90 = last value scaled by the 0.1 / 0.9 quantiles of the series' past
h-day log changes (pairs of days both on or before the origin).

Score = the track's: cell loss = mean pinball loss over q10/q50/q90 at
origin + h; skill = 1 - sum(loss) / sum(flat last-value loss), pooled over
every cell (the scorer's default headline number).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np

from .data import HORIZONS, Series, dev_origins, heldout_origins

QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class ForecasterConfig:
    # Use only changes ending in the last N days before the origin (0 = all).
    window_days: int = 0
    # Recency weight 0.5 ** (age / half_life) on each past change (0 = equal weights).
    half_life_days: float = 0.0
    # Multiply the q10/q90 log changes (1 = empirical width).
    band_scale: float = 1.0
    # q50 = last * exp(drift_weight * median past change) (0 = last value).
    drift_weight: float = 0.0
    # Mix in changes from the same instrument class, at this share of the own weight.
    pool_weight: float = 0.0
    # Fewer changes than this (own + pooled) -> flat forecast at the last value.
    min_samples: int = 20
    # AR(1) on daily log changes: shift all quantiles by r * (phi + ... + phi^h),
    # r = the last 1-day change (0 = off). Spot prices trend: train lag-1 ac ~ +0.6.
    momentum: float = 0.0
    # Blend phi toward the series' own lag-1 autocorrelation of daily changes
    # (visible history, clipped to [0, 0.95]) at this weight (0 = global phi only).
    momentum_fit: float = 0.0

    def updated(self, param: str, value) -> "ForecasterConfig":
        return replace(self, **{param: value})

    def to_dict(self) -> dict:
        return asdict(self)


class Changes:
    """Every h-day log change per series, indexed by the day the change ends."""

    def __init__(self, world: list[Series]):
        self.by_series: dict[tuple[str, int], tuple[np.ndarray, np.ndarray]] = {}
        groups: dict[tuple[str, int], list[tuple[np.ndarray, np.ndarray]]] = {}
        for s in world:
            for h in HORIZONS:
                end, ch = _pairs(s.days, s.vals, h)
                self.by_series[(s.sid, h)] = (end, ch)
                groups.setdefault((s.group, h), []).append((end, ch))
        self.by_group = {}
        for key, parts in groups.items():
            end = np.concatenate([p[0] for p in parts])
            ch = np.concatenate([p[1] for p in parts])
            order = np.argsort(end, kind="stable")
            self.by_group[key] = (end[order], ch[order])


def _pairs(days: np.ndarray, vals: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray]:
    """(end day, log change) for every pair (t, t + h) where both days exist."""
    if len(days) < 2 or not (vals > 0).all():
        return np.empty(0, np.int64), np.empty(0)
    idx = np.minimum(np.searchsorted(days, days + h), len(days) - 1)
    ok = days[idx] == days + h
    return days[idx[ok]], np.log(vals[idx[ok]] / vals[ok])


def _visible(end: np.ndarray, ch: np.ndarray, origin: int, window: int):
    hi = np.searchsorted(end, origin, side="right")
    lo = np.searchsorted(end, origin - window, side="right") if window > 0 else 0
    return end[lo:hi], ch[lo:hi]


def _weighted_quantiles(x: np.ndarray, w: np.ndarray, qs) -> np.ndarray:
    order = np.argsort(x, kind="stable")
    x, w = x[order], w[order]
    cw = np.cumsum(w)
    mid = (cw - 0.5 * w) / cw[-1]
    return np.interp(qs, mid, x)


def forecast(config: ForecasterConfig, s: Series, changes: Changes, origin: int, h: int):
    """(q10, q50, q90) for one series, origin and horizon, or None with no history."""
    k = int(np.searchsorted(s.days, origin, side="right"))
    if k == 0:
        return None
    last = float(s.vals[k - 1])
    end, ch = _visible(*changes.by_series[(s.sid, h)], origin, config.window_days)
    if config.pool_weight > 0:
        p_end, p_ch = _visible(*changes.by_group[(s.group, h)], origin, config.window_days)
    else:
        p_end, p_ch = end[:0], ch[:0]
    if len(ch) + len(p_ch) < config.min_samples:
        return last, last, last
    if config.half_life_days <= 0 and len(p_ch) == 0:
        q = np.quantile(ch, QUANTILES)  # the starter's estimator, for exact parity
    else:
        def weights(e):
            if config.half_life_days > 0:
                return 0.5 ** ((origin - e) / config.half_life_days)
            return np.ones(len(e))

        w, pw = weights(end), weights(p_end)
        if len(pw) and pw.sum() > 0:
            own_mass = w.sum() if len(w) else 1.0
            pw = pw * (config.pool_weight * own_mass / pw.sum())
        q = _weighted_quantiles(np.concatenate([ch, p_ch]), np.concatenate([w, pw]), QUANTILES)
    if config.momentum > 0 or config.momentum_fit > 0:
        phi = config.momentum
        if config.momentum_fit > 0:
            phi += config.momentum_fit * (_lag1_ac(changes, s, origin) - phi)
        last *= float(np.exp(_momentum(s, k, h, phi)))
    q10 = last * float(np.exp(config.band_scale * q[0]))
    q90 = last * float(np.exp(config.band_scale * q[2]))
    q50 = last * float(np.exp(config.drift_weight * q[1]))
    return min(q10, q50), q50, max(q90, q50)


def _momentum(s: Series, k: int, h: int, phi: float) -> float:
    """Expected h-day log change under AR(1) on daily changes, from the last 1-day change."""
    if k < 2 or s.days[k - 1] - s.days[k - 2] != 1:
        return 0.0
    r = float(np.log(s.vals[k - 1] / s.vals[k - 2]))
    return r * sum(phi ** i for i in range(1, h + 1))


def _lag1_ac(changes: Changes, s: Series, origin: int) -> float:
    end, ch = _visible(*changes.by_series[(s.sid, 1)], origin, 0)
    ok = np.diff(end) == 1
    if ok.sum() < 20:
        return 0.0
    x, y = ch[:-1][ok], ch[1:][ok]
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.clip(np.corrcoef(x, y)[0, 1], 0.0, 0.95))


def _pinball(y: float, f: float, tau: float) -> float:
    d = y - f
    return max(tau * d, (tau - 1.0) * d)


def _cell_loss(y: float, qs) -> float:
    return sum(_pinball(y, f, t) for f, t in zip(qs, QUANTILES)) / 3.0


def score(config: ForecasterConfig, world: list[Series], origins: list[int],
          horizons=HORIZONS, changes: Changes | None = None) -> dict:
    """Pooled pinball skill vs flat last value over every scorable cell."""
    changes = changes or Changes(world)
    loss = base = 0.0
    n = inside = 0
    for s in world:
        truth = dict(zip(s.days.tolist(), s.vals.tolist()))
        for o in origins:
            for h in horizons:
                y = truth.get(o + h)
                if y is None:
                    continue
                f = forecast(config, s, changes, o, h)
                if f is None:
                    continue
                loss += _cell_loss(y, f)
                base += _cell_loss(y, (f_last := _last(s, o),) * 3)
                inside += f[0] <= y <= f[2]
                n += 1
    skill = 1.0 - loss / base if base > 0 else 0.0
    return {"skill": skill, "cells": n, "coverage": inside / n if n else 0.0}


def _last(s: Series, origin: int) -> float:
    return float(s.vals[int(np.searchsorted(s.days, origin, side="right")) - 1])


def backtest(config: ForecasterConfig, world: list[Series]) -> dict:
    """Returns {"skill_train", "skill_heldout", "steps", "coverage_*", "cells_*"}.

    skill_train:   dev origins Jul 1 - Sep 23 (all targets on or before Sep 30).
    skill_heldout: October origins (targets up to Nov 6).
    steps = forecast dates walked (the unit of the steps-per-hour metric).
    """
    changes = Changes(world)
    dev, held = dev_origins(), heldout_origins()
    tr = score(config, world, dev, changes=changes)
    ho = score(config, world, held, changes=changes)
    return {
        "skill_train": tr["skill"],
        "skill_heldout": ho["skill"],
        "steps": len(dev) + len(held),
        "coverage_train": tr["coverage"],
        "coverage_heldout": ho["coverage"],
        "cells_train": tr["cells"],
        "cells_heldout": ho["cells"],
    }
