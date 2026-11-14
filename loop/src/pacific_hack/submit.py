"""Write a forecast CSV in the starter's schema (starter/FORECAST_SCHEMA.md).

    uv run python -m pacific_hack.submit --config best_config.json --origin 2026-11-06 --out submission.csv

One row per (series, horizon) at one origin. The model sees only data on or
before the origin. Series with no history get no row (the scorer fills the
last-value baseline for them).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from . import pack
from .data import HORIZONS, Series, day, iso
from .forecaster import Changes, ForecasterConfig, forecast

TEAM_ID = "gpu-scientist"


def rows(config: ForecasterConfig, world, origin: int, horizons=HORIZONS) -> list[dict]:
    # Changes ending after the origin are invisible to forecast(), so passing
    # the full series leaks nothing; truncate anyway to make that obvious.
    world = [Series(s.sid, s.group, s.days[s.days <= origin], s.vals[s.days <= origin]) for s in world]
    changes = Changes(world)
    out = []
    for s in world:
        for h in horizons:
            f = forecast(config, s, changes, origin, h)
            if f is None:
                continue
            q10, q50, q90 = f
            out.append({
                "series_id": s.sid,
                "origin_date": iso(origin),
                "horizon_days": h,
                "q10": f"{q10:.10g}",
                "q50": f"{q50:.10g}",
                "q90": f"{q90:.10g}",
                "target_date": iso(origin + h),
                "team_id": TEAM_ID,
                "method_note": "step model: " + json.dumps(config.to_dict(), sort_keys=True),
            })
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="JSON file with ForecasterConfig fields (default: starter parity)")
    ap.add_argument("--origin", default="2026-11-06")
    ap.add_argument("--series", help="series .npz (default: the pack build, $PACIFIC_SERIES)")
    ap.add_argument("--out", default="submission.csv")
    args = ap.parse_args(argv)
    config = ForecasterConfig(**json.loads(Path(args.config).read_text())) if args.config else ForecasterConfig()
    out = rows(config, pack.load(args.series), day(args.origin))
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    n = len({r["series_id"] for r in out})
    print(f"wrote {args.out}: {len(out)} rows, {n} series, origin {args.origin}")


if __name__ == "__main__":
    main()
