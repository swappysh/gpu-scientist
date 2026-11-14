"""Backtest the submitted configs against the starter and write results/backtest.json.

    uv run python -m pacific_hack.evaluate --config submit_config.json \
        --scored data/series_scored.npz --headline data/series.npz

Two separate questions:
  scored:    the 37 series the 11-06 catalog marks headline (what Sunday
             scores), pooled over every series in the build. The config was
             picked on Jul-Sep; October is reported once.
  aws_trend: the AWS spot series of the 10-24 headline set. A finding, not
             a scored entry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import pack
from .forecaster import ForecasterConfig, backtest
from .submit import load_configs

KEYS = ("skill_train", "skill_val", "skill_heldout", "coverage_train", "coverage_heldout",
        "cells_train", "cells_heldout")


def compare(cfg: ForecasterConfig, pool, scored) -> dict:
    out = {}
    for name, c in [("starter", ForecasterConfig()), ("model", cfg)]:
        r = backtest(c, pool, score_on=scored)
        out[name] = {"config": c.to_dict(), **{k: r[k] for k in KEYS}}
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="submit_config.json")
    ap.add_argument("--scored", default="data/series_scored.npz")
    ap.add_argument("--headline", default="data/series.npz")
    ap.add_argument("--out", default="results/backtest.json")
    args = ap.parse_args(argv)
    configs = load_configs(json.loads(Path(args.config).read_text()))

    world = pack.load(args.scored)
    ids = pack.scored_ids(args.scored)
    scored = [s for s in world if s.sid in ids]
    headline = pack.load(args.headline)
    aws = [s for s in headline if s.sid.startswith("aws_spot.")]
    results = {
        "scored": {"series": len(scored), **compare(configs["default"], world, scored)},
        "aws_trend": {"series": len(aws), **compare(configs["aws_spot."], headline, aws)},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2) + "\n")
    for part, r in results.items():
        for name in ("starter", "model"):
            x = r[name]
            print(f"{part:9s} n={r['series']:3d} {name:7s} skill train {x['skill_train']:+.4f} "
                  f"sep {x['skill_val']:+.4f} october {x['skill_heldout']:+.4f} "
                  f"coverage train {x['coverage_train']:.2f} october {x['coverage_heldout']:.2f}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
