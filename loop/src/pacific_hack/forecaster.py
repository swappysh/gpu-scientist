"""Forecaster config + fake backtest harness.

`ForecasterConfig` is the single mutable object the agent loop tunes:
one change at a time, proposed -> backtested -> kept/killed.

`backtest(config, train, heldout)` returns {"skill_train", "skill_heldout"}
where skill = 1 - MAE(model) / MAE(flat baseline), matching the track's
"price stays flat" reference. A real harness (jinx) can replace `backtest`
as long as it keeps this signature and score convention.
"""

from __future__ import annotations

from dataclasses import dataclass, replace, asdict
from statistics import median

HORIZONS = (1, 3, 7)


@dataclass(frozen=True)
class ForecasterConfig:
    # Median of the last `lookback_days` prices is the level estimate.
    lookback_days: int = 14
    # Shrink the level toward the whole-history median (0 = none, 1 = full).
    shrink_to_history: float = 0.0
    # Additive $/hr drift applied per horizon day.
    drift_per_day: float = 0.0
    # p10/p90 half-width = spread_k * recent MAD + spread_floor (bands only;
    # the step-median trick keeps them narrow until a jump).
    spread_k: float = 6.0
    spread_floor: float = 0.05

    def updated(self, param: str, value) -> "ForecasterConfig":
        return replace(self, **{param: value})

    def to_dict(self) -> dict:
        return asdict(self)


def _median(xs):
    return median(xs) if xs else 0.0


def predict_p50(config: ForecasterConfig, history: list[float], horizon: int) -> float:
    recent = history[-config.lookback_days :] or history
    level = _median(recent)
    hist_med = _median(history)
    level = level + config.shrink_to_history * (hist_med - level)
    return level + config.drift_per_day * horizon


def predict_bands(config: ForecasterConfig, history: list[float], horizon: int):
    p50 = predict_p50(config, history, horizon)
    recent = history[-config.lookback_days :] or history
    med = _median(recent)
    mad = _median([abs(x - med) for x in recent])
    half = config.spread_k * mad + config.spread_floor
    half *= 1 + 0.25 * (horizon - 1)  # wider for longer horizons
    return p50 - half, p50, p50 + half


def _mae(preds, actuals) -> float:
    return sum(abs(p - a) for p, a in zip(preds, actuals)) / max(len(actuals), 1)


def _score(config: ForecasterConfig, prices: list[float], warmup: int = 30) -> tuple[float, int]:
    """Walk-forward p50 skill vs the flat baseline; returns (skill, forecast dates used)."""
    model_err, flat_err, n = 0.0, 0.0, 0
    for t in range(warmup, len(prices)):
        hist = prices[:t]
        for h in HORIZONS:
            if t + h > len(prices):
                continue
            actual = prices[t + h - 1]
            model_err += abs(predict_p50(config, hist, h) - actual)
            flat_err += abs(hist[-1] - actual)
            n += 1
    steps = len(prices) - warmup
    if n == 0 or flat_err == 0:
        return 0.0, steps
    return 1.0 - model_err / flat_err, steps


def backtest(config: ForecasterConfig, train: list[float], heldout: list[float]) -> dict:
    """Returns {"skill_train", "skill_heldout", "steps"}.

    steps = forecast dates walked (the unit of the steps-per-hour metric).

    skill_train:   walk-forward over the Jul-Sep tail.
    skill_heldout: walk-forward over October, forecasting from history that
                   includes train (as the real competition will).
    """
    skill_train, steps_train = _score(config, train)
    skill_heldout, steps_heldout = _score(config, train + heldout, warmup=len(train))
    return {
        "skill_train": skill_train,
        "skill_heldout": skill_heldout,
        "steps": steps_train + steps_heldout,
    }
