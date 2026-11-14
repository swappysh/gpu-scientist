"""The backtest seam the agent loop calls.

    backtest_batch(configs, runner="local", seed=7) -> list[dict]

Each result is {"skill_train", "skill_heldout"} (optionally "steps": forecast
dates walked, used for the steps-per-hour metric). The loop never calls
`backtest` directly, so jinx's real harness replaces this module's
`backtest_seed` (one config + one data seed -> one result) and keeps the rest:
`run_local` maps it in-process, `modal_app.run_batch` maps the same function
on Modal containers (`.starmap`, one call per job).

World: the Pacific pack build (`pack.py`), or step-shaped fake series when
PACIFIC_DATA=synthetic (offline tests). Skill is scored on the build's
headline (scored) series; the rest only feed pooling. `seed` < 1000 scores
every scored series; seed >= 1000 (the critic's alternate worlds) scores a
bootstrap resample of them, so a kept change must hold up on other mixes.
"""

from __future__ import annotations

import os
import random
from contextlib import contextmanager

from . import pack
from .data import Series, synthetic_world
from .forecaster import ForecasterConfig, backtest

RUNNERS = ("local", "modal")
DATA_ENV = "PACIFIC_DATA"  # "pack" (default) or "synthetic"
BOOTSTRAP_FROM = 1000


def world(seed: int) -> tuple[list[Series], list[Series]]:
    """(pool, scored): pooling sees `pool`, skill is scored on `scored`."""
    if os.environ.get(DATA_ENV, "pack") == "synthetic":
        series, ids = synthetic_world(seed=7), None
    else:
        series, ids = pack.load(), pack.scored_ids()
    scored = [s for s in series if s.sid in ids] if ids else series
    if seed >= BOOTSTRAP_FROM:
        rng = random.Random(seed)
        scored = [scored[rng.randrange(len(scored))] for _ in scored]
        if not ids:  # older builds: the resample is the whole world, as before
            series = scored
    return series, scored


def backtest_seed(config: dict, seed: int) -> dict:
    """One job: score one config on world `seed`. Runs locally or on Modal."""
    pool, scored = world(seed)
    return backtest(ForecasterConfig(**config), pool, score_on=scored)


def run_local(jobs: list[tuple[dict, int]]) -> list[dict]:
    return [backtest_seed(config, seed) for config, seed in jobs]


def backtest_batch(
    configs: list[ForecasterConfig], runner: str = "local", seed: int = 7
) -> list[dict]:
    """Backtest every config; results are in the same order as `configs`."""
    jobs = [(c.to_dict(), seed) for c in configs]
    if runner == "local":
        return run_local(jobs)
    if runner == "modal":
        from . import modal_app  # imported lazily: local runs never touch Modal

        return modal_app.run_batch(jobs)
    raise ValueError(f"unknown runner {runner!r} (use one of {RUNNERS})")


@contextmanager
def session(runner: str):
    """Hold the runner open for a whole loop (Modal app start-up is paid once)."""
    if runner == "modal":
        from . import modal_app

        with modal_app.session():
            yield
    else:
        yield
