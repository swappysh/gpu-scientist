"""October, once, on the 37 scored series, for the three configs fixed on Jul-Sep.

    uv run python scripts/october37.py data/series_scored.npz
"""
import sys

from pacific_hack import pack
from pacific_hack.data import heldout_origins
from pacific_hack.forecaster import Changes, ForecasterConfig, score

world = pack.load(sys.argv[1])
ids = pack.scored_ids(sys.argv[1])
sub = [s for s in world if s.sid in ids]
ch = Changes(world)
for label, cfg in [
    ("starter", ForecasterConfig()),
    ("trend (aws pick)", ForecasterConfig(half_life_days=7.0, momentum=0.65, momentum_fit=1.0, band_scale=0.8, pool_weight=0.25)),
    ("pick37 (band 1.2)", ForecasterConfig(pool_weight=0.5, half_life_days=14.0, band_scale=1.2)),
]:
    r = score(cfg, sub, heldout_origins(), changes=ch)
    print(f"october sunday37 {label:18s} skill {r['skill']:+.4f} cov {r['coverage']:.2f} cells {r['cells']}", flush=True)
