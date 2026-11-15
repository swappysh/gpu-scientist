"""October, scored once at the freeze, by gpuloop only. Read-only.

    .venv/bin/python research/harness/score_heldout.py <full npz> <final forecaster.py> <v7 forecaster.py>

The full build (with October and the first days of November) lives outside
the researchers' sandbox. Same worker and scorer as the dev runs. Prints
October skill and coverage for both files and a series bootstrap of the
difference (the luck check vs v7).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import core  # noqa: E402

if __name__ == "__main__":
    full, final, v7 = sys.argv[1:4]
    world = core.load(full)
    origins = core.heldout_origins()
    res = {}
    for name, f in (("final", final), ("v7", v7)):
        s = core.score(world, core.forecasts(f, world, origins), origins)
        res[name] = s
        print(f"{name}: october skill {s['skill']:+.4f} coverage {s['coverage']:.2f} cells {s['cells']}")
    ids = sorted(res["final"]["per_series"])
    a = np.array([res["final"]["per_series"][i] for i in ids])
    b = np.array([res["v7"]["per_series"][i] for i in ids])
    idx = np.random.default_rng(0).integers(0, len(ids), size=(10000, len(ids)))
    diff = (b[:, 0][idx].sum(1) - a[:, 0][idx].sum(1)) / b[:, 1][idx].sum(1)
    lo, hi = np.quantile(diff, [0.025, 0.975])
    print(f"final - v7: {res['final']['skill'] - res['v7']['skill']:+.4f}, 95% interval [{lo:+.4f}, {hi:+.4f}], "
          f"share above 0: {(diff > 0).mean():.3f}, series with lower October loss: {int((a[:, 0] < b[:, 0]).sum())} of {len(ids)}")
