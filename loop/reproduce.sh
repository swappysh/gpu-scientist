#!/bin/sh
# One command: pack -> series -> backtest -> Nov 6 submission.
#   ./reproduce.sh <unzipped gpu-price-pack-v0.1.1-handover dir>
set -eu
PACK=${1:?usage: ./reproduce.sh <pack dir>}
cd "$(dirname "$0")"
# 10-24 headline set (the loop's AWS spot world) and every series with the
# 11-06 headline flag (the 37 scored series; the rest feed pooling).
uv run --group pack python -m pacific_hack.pack --pack "$PACK"
uv run --group pack python -m pacific_hack.pack --pack "$PACK" --tier all --as-of 2026-11-06 \
    --out data/series_scored.npz
uv run python -m pacific_hack.evaluate --config submit_config.json \
    --scored data/series_scored.npz --headline data/series.npz --out results/backtest.json
uv run python -m pacific_hack.submit --config submit_config.json --series data/series_scored.npz \
    --origin 2026-11-06 --out submission_2026-11-06.csv
