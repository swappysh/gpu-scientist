#!/bin/sh
# One command: pack -> series -> held-out backtest -> Nov 6 submission.
#   ./reproduce.sh <unzipped gpu-price-pack-v0.1.1-handover dir>
set -eu
PACK=${1:?usage: ./reproduce.sh <pack dir>}
cd "$(dirname "$0")"
uv run --group pack python -m pacific_hack.pack --pack "$PACK"
uv run --group pack python -m pacific_hack.pack --pack "$PACK" --tier all --out data/series_all.npz
uv run python -c "
import json
from pacific_hack import pack
from pacific_hack.forecaster import ForecasterConfig, backtest
for name, c in [('starter', ForecasterConfig()), ('best', ForecasterConfig(**json.load(open('best_config.json'))))]:
    r = backtest(c, pack.load())
    print(f\"{name:8s} skill train {r['skill_train']:+.4f} heldout {r['skill_heldout']:+.4f} coverage heldout {r['coverage_heldout']:.2f}\")
"
uv run python -m pacific_hack.submit --config best_config.json --series data/series_all.npz \
    --origin 2026-11-06 --out submission_2026-11-06.csv
