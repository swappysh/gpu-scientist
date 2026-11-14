"""Synthetic H100 daily median price series with step dynamics.

GPU rental medians move in steps (a few distinct values over months), so the
generator holds a flat level, jumps occasionally, then adds small measurement
jitter. `train` covers "Jul-Sep" and `heldout` covers "October" by length, so
jinx's real harness can swap in the same split by replacing this function.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

TRAIN_DAYS = 92   # ~Jul 1 - Sep 30
HELDOUT_DAYS = 31  # ~Oct 1 - Oct 31
START_DATE = date(2026, 7, 1)


def date_of(day_index: int) -> str:
    """Market date (YYYY-MM-DD) of the i-th day of the series."""
    return (START_DATE + timedelta(days=day_index)).isoformat()


TRAIN_END = date_of(TRAIN_DAYS - 1)  # 2026-09-30: last day the proposer may know
HELDOUT_END = date_of(TRAIN_DAYS + HELDOUT_DAYS - 1)  # 2026-10-31


def make_series(
    seed: int = 7,
    n_days: int = TRAIN_DAYS + HELDOUT_DAYS,
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


def split(prices: list[float]) -> tuple[list[float], list[float]]:
    """(train Jul-Sep, heldout October)."""
    return prices[:TRAIN_DAYS], prices[TRAIN_DAYS:]
