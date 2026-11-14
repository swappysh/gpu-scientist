"""The Pacific data pack as a backtest world.

    uv run --group pack python -m pacific_hack.pack --pack <gpu-price-pack dir>

builds the series with the pack's own `starter/build_series.py` (catalog as of
2026-10-24, the starter demo's cutoff) and saves the headline series to one
small .npz. The loop, locally or on Modal, reads only that file.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np

from .data import Series, day

CATALOG_AS_OF = "2026-10-24"
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "series.npz"
PATH_ENV = "PACIFIC_SERIES"


def path() -> Path:
    return Path(os.environ.get(PATH_ENV) or DEFAULT_PATH)


@lru_cache(maxsize=1)
def load(npz: str | None = None) -> list[Series]:
    p = Path(npz) if npz else path()
    if not p.exists():
        raise FileNotFoundError(f"{p} missing; build it with python -m pacific_hack.pack --pack <dir>")
    z = np.load(p, allow_pickle=False)
    world = []
    for i, (sid, group) in enumerate(zip(z["sids"], z["groups"])):
        lo, hi = z["offsets"][i], z["offsets"][i + 1]
        world.append(Series(str(sid), str(group), z["days"][lo:hi], z["vals"][lo:hi]))
    return world


def build(pack_dir: str, out: str, tier: str = "headline") -> int:
    starter = Path(pack_dir) / "starter" / "build_series.py"
    with tempfile.TemporaryDirectory() as tmp:
        series_csv, catalog_csv = f"{tmp}/series_daily.csv", f"{tmp}/series_catalog.csv"
        subprocess.run(
            [sys.executable, "-I", "-B", str(starter), "--pack", pack_dir, "--out", series_csv,
             "--catalog", catalog_csv, "--as-of", CATALOG_AS_OF, "--report", f"{tmp}/report.json"],
            check=True,
        )
        with open(catalog_csv, newline="") as f:
            keep = {r["series_id"]: r["instrument_class"] for r in csv.DictReader(f) if r["tier"] == tier}
        rows: dict[str, list[tuple[int, float]]] = {sid: [] for sid in keep}
        with open(series_csv, newline="") as f:
            for r in csv.DictReader(f):
                if r["series_id"] in rows and r["value"] not in ("", "nan"):
                    rows[r["series_id"]].append((day(r["date"][:10]), float(r["value"])))
    sids = sorted(rows)
    days, vals, offsets = [], [], [0]
    for sid in sids:
        pts = sorted(dict(rows[sid]).items())
        days += [d for d, _ in pts]
        vals += [v for _, v in pts]
        offsets.append(len(days))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out, sids=np.array(sids), groups=np.array([keep[s] for s in sids]),
        days=np.array(days, dtype=np.int64), vals=np.array(vals, dtype=np.float64),
        offsets=np.array(offsets, dtype=np.int64),
    )
    return len(sids)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", required=True, help="unzipped gpu-price-pack-v0.1.1-handover directory")
    ap.add_argument("--out", default=str(DEFAULT_PATH))
    ap.add_argument("--tier", default="headline")
    args = ap.parse_args()
    n = build(args.pack, args.out, args.tier)
    print(f"wrote {args.out}: {n} {args.tier} series (catalog as of {CATALOG_AS_OF})")


if __name__ == "__main__":
    main()
