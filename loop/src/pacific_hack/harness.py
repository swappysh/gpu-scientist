"""The backtest seam the agent loop calls.

    backtest_batch(configs, runner="local", seed=7) -> list[dict]

Each result is {"skill_train", "skill_heldout"} (optionally "steps": forecast
dates walked, used for the steps-per-hour metric). The loop never calls
`backtest` directly, so jinx's real harness replaces this module's
`backtest_seed` (one config + one data seed -> one result) and keeps the rest:
`run_local` maps it in-process, `modal_app.run_batch` maps the same function
on Modal containers (`.starmap`, one call per job).

`seed` selects the synthetic world today; with the real harness it can
select a dataset / forecast-date window instead.
"""

from __future__ import annotations

from contextlib import contextmanager

from .data import make_series, split
from .forecaster import ForecasterConfig, backtest

RUNNERS = ("local", "modal")


def backtest_seed(config: dict, seed: int) -> dict:
    """One job: score one config on the synthetic world `seed`. Runs locally or on Modal."""
    train, heldout = split(make_series(seed=seed))
    return backtest(ForecasterConfig(**config), train, heldout)


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
