"""Forecast CSV from a research forecaster (forecaster_agent.py) at one origin, every series.

    uv run python research/challenger.py research/forecaster_agent_v81.py data/series_scored.npz 2026-11-06 challenger_v81_2026-11-06.csv "v8.1 pick 870891d"

Same worker as the research harness (core.forecasts: the forecaster sees only rows dated on
or before the origin), with every series in the build forecast, not just the scored ones, so
the rows match submission_2026-11-06.csv. The catalog keeps the build's real scored flags, and
the scored series' forecasts must equal a plain harness run (checked below). Same schema as pacific_hack.submit. Checks the
output before writing: finite, > 0, q10 <= q50 <= q90 (core._check), one row per series
with history and horizon.
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.harness import core  # noqa: E402

TEAM_ID = "gpu-scientist"


@dataclass
class AllSeries(core.World):
    """Asks for every series, but the forecaster still sees the real scored flags."""
    flags: list[bool] | None = None

    @property
    def catalog(self) -> dict[str, dict]:
        return {s: core.catalog_row(s, g, f) for s, g, f in zip(self.sids, self.groups, self.flags)}


if __name__ == "__main__":
    agent, npz, origin_iso, out, label = sys.argv[1:6]
    world = core.load(npz)
    o = core.day(origin_iso)
    every = AllSeries(world.sids, world.groups, world.days, world.vals, [True] * len(world.sids), world.scored)
    fc = core.forecasts(agent, every, [o])
    plain = core.forecasts(agent, world, [o])
    assert all(fc[k] == q for k, q in plain.items()), "scored series differ from the plain harness run"
    have = core.cut(world, o)
    assert set(fc) == {(s, o, h) for s in have for h in core.HORIZONS}, "missing or extra cells"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series_id", "origin_date", "horizon_days", "q10", "q50", "q90", "target_date", "team_id", "method_note"])
        for s in world.sids:  # build order, like pacific_hack.submit
            for h in core.HORIZONS:
                if (s, o, h) in fc:
                    q10, q50, q90 = fc[(s, o, h)]
                    w.writerow([s, origin_iso, h, f"{q10:.10g}", f"{q50:.10g}", f"{q90:.10g}", core.iso(o + h), TEAM_ID, label])
    print(f"wrote {out}: {len(fc)} rows, {len(have)} series, origin {origin_iso}")
