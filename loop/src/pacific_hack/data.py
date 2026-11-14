"""Series the backtest walks over, real or synthetic, plus the date split.

A world is a list of `Series` (daily days + values, gaps allowed). The real
world is the Pacific pack's headline series (`pack.py`); the synthetic world
is step-shaped fake prices for offline tests. Both go through the same model
and scorer, so tests exercise the real code path.

Split (no peeking): dev origins forecast targets on or before TRAIN_END, so
the proposer's numbers never touch October. Held-out origins are in October;
their 7-day targets end on the pack's last day, 2026-11-06.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

HORIZONS = (1, 3, 7)
TRAIN_START = "2026-07-01"
TRAIN_END = "2026-09-30"  # last date any dev number may use: the proposer's as-of date
VAL_START = "2026-09-01"  # dev origins from here on form the keep/kill gate slice
HELDOUT_START = "2026-10-01"
HELDOUT_END = "2026-10-31"
PACK_END = "2026-11-06"  # last day in the pack (data cutoff)
ORIGIN_STEP = 2  # days between forecast origins


def day(iso: str) -> int:
    return date.fromisoformat(iso).toordinal()


def iso(d: int) -> str:
    return date.fromordinal(int(d)).isoformat()


def date_of(day_index: int, start: str = TRAIN_START) -> str:
    """Market date (YYYY-MM-DD) `day_index` days after `start`."""
    return (date.fromisoformat(start) + timedelta(days=day_index)).isoformat()


def dev_origins() -> list[int]:
    """Jul 1 .. Sep 23: every target (origin + up to 7 days) is on or before Sep 30."""
    last = day(TRAIN_END) - max(HORIZONS)
    return list(range(day(TRAIN_START), last + 1, ORIGIN_STEP))


def val_origins() -> list[int]:
    """Sep 1 .. Sep 23: the last stretch of dev origins, the evaluator's and critic's gate."""
    return [o for o in dev_origins() if o >= day(VAL_START)]


def heldout_origins() -> list[int]:
    """Oct 1 .. Oct 30: targets run to Nov 6, the last day in the pack."""
    last = min(day(HELDOUT_END), day(PACK_END) - max(HORIZONS))
    return list(range(day(HELDOUT_START), last + 1, ORIGIN_STEP))


@dataclass
class Series:
    sid: str
    group: str  # instrument class; the model may pool changes within a group
    days: np.ndarray  # int64 ordinals, sorted, unique
    vals: np.ndarray  # float64 USD per GPU-hour


def make_series(
    seed: int = 7,
    n_days: int = 300,
    start: float = 2.40,
    jump_prob: float = 0.06,
    jump_sigma: float = 0.20,
    jitter_sigma: float = 0.015,
    floor: float = 1.20,
) -> list[float]:
    """Step-shaped daily series: flat regimes + rare jumps + tiny jitter."""
    rng = random.Random(seed)
    level, prices = start, []
    for _ in range(n_days):
        if rng.random() < jump_prob:
            level = max(floor, level + rng.gauss(0, jump_sigma))
        prices.append(round(level + rng.gauss(0, jitter_sigma), 4))
    return prices


def synthetic_world(seed: int = 7, n_series: int = 6) -> list[Series]:
    """Fake step-shaped series covering Jan 12 .. Nov 6 2026, two groups."""
    first, last = day("2026-01-12"), day(PACK_END)
    days = np.arange(first, last + 1, dtype=np.int64)
    world = []
    for i in range(n_series):
        vals = np.array(make_series(seed=seed * 100 + i, n_days=len(days)), dtype=np.float64)
        world.append(Series(f"synthetic.{i}", f"g{i % 2}", days, vals))
    return world
