"""Modal runner for the backtest batch (thin on purpose; swap freely).

The remote function only calls `harness.backtest_seed`, so replacing that
function (jinx's real harness) changes what runs on Modal with no edit here.
`run_batch` fans one job per (config, seed) out with `.starmap`.

Credentials: the Modal SDK reads its own token (`modal token set`, or
MODAL_TOKEN_ID / MODAL_TOKEN_SECRET in the environment). Nothing here reads
or prints them. Run the loop with `--runner modal`.
"""

from __future__ import annotations

from contextlib import contextmanager

import modal

app = modal.App("pacific-hack-backtest")
image = modal.Image.debian_slim(python_version="3.12").add_local_python_source("pacific_hack")


@app.function(image=image, timeout=600)
def backtest_remote(config: dict, seed: int) -> dict:
    from pacific_hack.harness import backtest_seed

    return backtest_seed(config, seed)


@contextmanager
def session():
    with modal.enable_output(), app.run():
        yield


def run_batch(jobs: list[tuple[dict, int]]) -> list[dict]:
    """Run jobs on Modal in parallel; must be called inside `session()`."""
    return list(backtest_remote.starmap(jobs))
