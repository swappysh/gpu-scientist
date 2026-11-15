"""Fixed v8.1 research harness: data, per-origin history, scorer. Read-only.

v8.1 (2026-11-15, PREREG-v81.md): dev runs to Oct 15 (gate = origins Sep 1 - Oct 7, all
targets on or before Oct 15); the holdout is origins Oct 16-30, scored once by gpuloop.
A dev run also returns per-cell rows, which the post-mortem guards (guards.py) read.

The researcher edits only research/forecaster_agent.py. Its function

    forecast(history, catalog_row, origin, h) -> (q10, q50, q90)

is called in a separate worker process (worker.py). For each origin the
worker receives copies of every series cut at the origin (rows dated on or
before it) and nothing else, so no forecast can see a later price. Origins
run in ascending order in one fresh process per experiment, so state kept
between calls only ever holds the past.

Score = the track's: cell loss = mean pinball loss over q10/q50/q90 at
origin + h; skill = 1 - sum(loss) / sum(flat last-value loss), pooled over
the scored series. Same definition and numbers as pacific_hack.forecaster.
"""

from __future__ import annotations

import multiprocessing as mp
import time
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEV_NPZ = HERE / "dev_series.npz"  # every series cut at TRAIN_END: no row after Oct 15 exists here
HORIZONS = (1, 3, 7)
QUANTILES = (0.1, 0.5, 0.9)
TRAIN_START, TRAIN_END, VAL_START = "2026-07-01", "2026-10-15", "2026-09-01"
HELDOUT_START, HELDOUT_END, PACK_END = "2026-10-16", "2026-10-31", "2026-11-06"
ORIGIN_STEP = 2
TIME_LIMIT_S = 900  # one experiment's forecasts; past this the run counts as a crash


def day(iso: str) -> int:
    return date.fromisoformat(iso).toordinal()


def iso(d: int) -> str:
    return date.fromordinal(int(d)).isoformat()


def dev_origins() -> list[int]:
    """Jul 1 .. Oct 8, every 2 days: all targets on or before Oct 15."""
    return list(range(day(TRAIN_START), day(TRAIN_END) - max(HORIZONS) + 1, ORIGIN_STEP))


def heldout_origins() -> list[int]:
    last = min(day(HELDOUT_END), day(PACK_END) - max(HORIZONS))
    return list(range(day(HELDOUT_START), last + 1, ORIGIN_STEP))


def catalog_row(sid: str, group: str, scored: bool) -> dict:
    """Static facts about one series, parsed from its id (source.class.gpu.pricing.stat)."""
    parts = sid.split(".")
    row = {"series_id": sid, "instrument_class": group, "scored": scored}
    if len(parts) == 5:
        row.update(source=parts[0], gpu=parts[2], pricing=parts[3], stat=parts[4])
    else:  # e.g. aws_spot.<instance>.<zone>
        row.update(source=parts[0], gpu="", pricing="spot", stat="", detail=".".join(parts[1:]))
    return row


@dataclass
class World:
    sids: list[str]
    groups: list[str]
    days: list[np.ndarray]
    vals: list[np.ndarray]
    scored: list[bool]

    @property
    def catalog(self) -> dict[str, dict]:
        return {s: catalog_row(s, g, sc) for s, g, sc in zip(self.sids, self.groups, self.scored)}


def load(npz: str | Path = DEV_NPZ) -> World:
    z = np.load(npz, allow_pickle=False)
    off = z["offsets"]
    n = len(z["sids"])
    return World(
        sids=[str(s) for s in z["sids"]],
        groups=[str(g) for g in z["groups"]],
        days=[z["days"][off[i]:off[i + 1]].copy() for i in range(n)],
        vals=[z["vals"][off[i]:off[i + 1]].copy() for i in range(n)],
        scored=[bool(x) for x in z["headline"]],
    )


@dataclass
class History:
    """Everything a forecast may see at one origin: rows dated <= origin, as copies.

    history.origin       int day ordinal (datetime.date.toordinal())
    history.origin_date  "YYYY-MM-DD"
    history.series       {series_id: (days int64 ordinals, prices float64 USD/GPU-hour)},
                         sorted by day, gaps allowed; every series with >= 1 row so far
    history.catalog      {series_id: catalog row}, for every series in history.series
    history.cache        a dict that lives for this origin only (share work across calls)
    """
    origin: int
    series: dict
    catalog: dict
    cache: dict = field(default_factory=dict)

    @property
    def origin_date(self) -> str:
        return iso(self.origin)


def cut(world: World, origin: int) -> dict:
    """Copies of every series up to and including `origin` (the only data sent to the worker)."""
    out = {}
    for sid, d, v in zip(world.sids, world.days, world.vals):
        k = int(np.searchsorted(d, origin, side="right"))
        if k:
            out[sid] = (d[:k].copy(), v[:k].copy())
    return out


def _pinball_cell(y: float, qs) -> float:
    tot = 0.0
    for f, t in zip(qs, QUANTILES):
        d = y - f
        tot += max(t * d, (t - 1.0) * d)
    return tot / 3.0


def _check(q, sid, origin, h):
    try:
        q10, q50, q90 = (float(x) for x in q)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{sid} {iso(origin)} h{h}: forecast must return 3 numbers, got {q!r}") from exc
    if not all(np.isfinite([q10, q50, q90])) or min(q10, q50, q90) <= 0:
        raise ValueError(f"{sid} {iso(origin)} h{h}: quantiles must be finite and > 0, got {(q10, q50, q90)}")
    if not q10 <= q50 <= q90:
        raise ValueError(f"{sid} {iso(origin)} h{h}: need q10 <= q50 <= q90, got {(q10, q50, q90)}")
    return q10, q50, q90


class Crash(Exception):
    pass


def forecasts(agent_file: str, world: World, origins: list[int], time_limit: float = TIME_LIMIT_S) -> dict:
    """{(sid, origin, h): (q10, q50, q90)} for the scored series, from a sandboxed worker."""
    from . import worker

    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=worker.main, args=(child, agent_file), daemon=True)
    proc.start()
    child.close()
    catalog = world.catalog
    scored = [s for s, sc in zip(world.sids, world.scored) if sc]
    out: dict = {}
    t0 = time.monotonic()
    try:
        msg = _recv(parent, proc, t0, time_limit)
        if msg[0] != "ready":
            raise Crash(msg[1])
        for o in origins:  # ascending: state kept by the forecaster only ever holds the past
            series = cut(world, o)
            reqs = [(s, h) for s in scored if s in series for h in HORIZONS]
            parent.send(("origin", o, series, {s: catalog[s] for s in series}, reqs))
            msg = _recv(parent, proc, t0, time_limit)
            if msg[0] != "ok":
                raise Crash(msg[1])
            for (s, h), q in zip(reqs, msg[1]):
                out[(s, o, h)] = _check(q, s, o, h)
        parent.send(("stop",))
    finally:
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
    return out


def _recv(conn, proc, t0, limit):
    while not conn.poll(1.0):
        if not proc.is_alive():
            raise Crash(f"worker died (exit code {proc.exitcode}); out of memory or a hard crash")
        if time.monotonic() - t0 > limit:
            proc.kill()
            raise Crash(f"time limit: forecasts took over {limit:.0f} s")
    try:
        return conn.recv()
    except EOFError as exc:
        raise Crash("worker closed the pipe") from exc


def score(world: World, fc: dict, origins: list[int]) -> dict:
    """Per scored series: loss and flat last-value loss summed over its cells, plus coverage."""
    per = {}
    inside = n = 0
    for sid, d, v, sc in zip(world.sids, world.days, world.vals, world.scored):
        if not sc:
            continue
        truth = dict(zip(d.tolist(), v.tolist()))
        loss = base = 0.0
        for o in origins:
            k = int(np.searchsorted(d, o, side="right"))
            if k == 0:
                continue
            last = float(v[k - 1])
            for h in HORIZONS:
                y = truth.get(o + h)
                if y is None or (sid, o, h) not in fc:
                    continue
                q = fc[(sid, o, h)]
                loss += _pinball_cell(y, q)
                base += _pinball_cell(y, (last, last, last))
                inside += q[0] <= y <= q[2]
                n += 1
        per[sid] = (loss, base)
    L = sum(x[0] for x in per.values())
    B = sum(x[1] for x in per.values())
    return {"skill": 1.0 - L / B if B > 0 else 0.0, "cells": n,
            "coverage": inside / n if n else 0.0, "per_series": per}


def cells(world: World, fc: dict, origins: list[int]) -> list[list]:
    """Per scored cell: [series_id, origin, h, truth, last, [q10, q50, q90], loss, flat_loss] (input of guards.py)."""
    rows = []
    for sid, d, v, sc in zip(world.sids, world.days, world.vals, world.scored):
        if not sc:
            continue
        truth = dict(zip(d.tolist(), v.tolist()))
        for o in origins:
            k = int(np.searchsorted(d, o, side="right"))
            if k == 0:
                continue
            last = float(v[k - 1])
            for h in HORIZONS:
                y = truth.get(o + h)
                if y is None or (sid, o, h) not in fc:
                    continue
                q = [float(x) for x in fc[(sid, o, h)]]
                rows.append([sid, o, h, y, last, q, _pinball_cell(y, q), _pinball_cell(y, (last, last, last))])
    return rows


def evaluate_dev(agent_file: str, world: World | None = None) -> dict:
    """Jul 1 - Oct 7 origins (column julsep) and the gate Sep 1 - Oct 7 (column sept) for one forecaster file, plus per-cell rows for the guards."""
    world = world or load(DEV_NPZ)
    assert max(int(d.max()) for d in world.days if len(d)) <= day(TRAIN_END), "dev file holds rows after Oct 15"
    origins = dev_origins()
    fc = forecasts(agent_file, world, origins)
    sept = [o for o in origins if o >= day(VAL_START)]
    js, se = score(world, fc, origins), score(world, fc, sept)
    return {"julsep": js["skill"], "sept": se["skill"], "coverage_julsep": js["coverage"],
            "coverage_sept": se["coverage"], "cells_julsep": js["cells"], "cells_sept": se["cells"],
            "sept_per_series": {k: list(v) for k, v in se["per_series"].items()},
            "cells": cells(world, fc, origins)}


def resample_share(cand: dict, best: dict, draws: int = 200, seed: int = 0) -> float:
    """Share of series resamples (with replacement) where the candidate's pooled skill beats the best's."""
    ids = sorted(cand)
    c = np.array([cand[i] for i in ids])
    b = np.array([best[i] for i in ids])
    idx = np.random.default_rng(seed).integers(0, len(ids), size=(draws, len(ids)))
    base = b[:, 1][idx].sum(1)  # flat loss does not depend on the forecaster
    gain = (b[:, 0][idx].sum(1) - c[:, 0][idx].sum(1)) / base
    return float((gain > 0).mean())


def describe_error(exc: BaseException) -> str:
    return "".join(traceback.format_exception_only(type(exc), exc)).strip()[-400:]
