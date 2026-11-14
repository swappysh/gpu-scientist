"""Jul-Sep sweep on the 37 scored series. Never touches October origins.

Pooling sees every series in the build (as in submit.py); only the scored
series count. fit = origins Jul 1 - Aug 24, val = Sep 1 - 23, train = both.

    uv run python scripts/sweep37.py data/series_scored.npz < scripts/sweep_julsep_37.jsonl
"""
import json
import sys

from pacific_hack import pack
from pacific_hack.data import ORIGIN_STEP, day
from pacific_hack.forecaster import Changes, ForecasterConfig, score

world = pack.load(sys.argv[1])
ids = pack.scored_ids(sys.argv[1])
sub = [s for s in world if s.sid in ids]
ch = Changes(world)
fit = list(range(day("2026-07-01"), day("2026-08-31") - 7 + 1, ORIGIN_STEP))
val = list(range(day("2026-09-01"), day("2026-09-30") - 7 + 1, ORIGIN_STEP))
train = fit + val

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    cfg = ForecasterConfig(**json.loads(line))
    a = score(cfg, sub, fit, changes=ch)
    b = score(cfg, sub, val, changes=ch)
    t = score(cfg, sub, train, changes=ch)
    print(f"{line:72s} fit {a['skill']:+.3f} val {b['skill']:+.3f} train {t['skill']:+.3f} "
          f"cov {t['coverage']:.2f} cells {t['cells']}", flush=True)
