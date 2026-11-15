"""How posted GPU rental prices moved from January to November 2026, per venue.

A venue is one (source, provider, GPU model, instrument class, pricing tier). Pooled
medians move with the mix of providers sampled, so this script never pools first: it
takes each venue's daily median USD per GPU-hour (across regions and SKUs), compares the
venue's own start window with its own end window, and only then takes medians of those
per-venue changes. Start window: the venue's first 14 days with data, all before
2026-03-01. End window: its last 14 days, all after 2026-10-15 (data cutoff 2026-11-06).

It also writes the end-window level per venue (the cross-section of chips) and each
venue's mean level from January to August 2026 (to match used-price prints).

Usage: python -I analysis/rental_trend_2026.py PACK_DIR OUT_DIR
Writes OUT_DIR/rental_venue_change_2026.csv, OUT_DIR/rental_change_summary_2026.csv and
OUT_DIR/rental_levels_nov2026.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

FAMILY = {
    "V100": "V100", "V100S": "V100",
    "A100 40GB": "A100", "A100 80GB": "A100", "A100 SXM 80GB": "A100", "A100 PCIe 80GB": "A100",
    "A100 (memory unspecified)": "A100",
    "H100 SXM 80GB": "H100", "H100 80GB": "H100", "H100 PCIe 80GB": "H100", "H100 NVL": "H100",
    "H200": "H200", "H200 NVL": "H200", "B200": "B200",
}
SOURCES = ["afhubbard", "gpurentalprices", "fastgpu_daily", "tanod"]
COLS = ["provider", "gpu_model", "instrument_class", "pricing_tier", "usd_per_gpu_hour"]
KEY = ["source_id", "provider", "gpu_model", "instrument_class", "pricing_tier"]


def load(pack):
    parts = []
    for src in SOURCES:
        for f in sorted(Path(pack, "rental_observations", f"source_id={src}").glob("dt=*/part.parquet")):
            t = pq.read_table(f, columns=COLS).to_pandas()
            t = t[t.gpu_model.isin(FAMILY.keys()) & (t.usd_per_gpu_hour > 0)]
            if t.empty:
                continue
            t["dt"] = pd.Timestamp(f.parent.name[3:])
            t["source_id"] = src
            parts.append(t.groupby(KEY + ["dt"]).usd_per_gpu_hour.median().reset_index())
    return pd.concat(parts)


def main(pack, out):
    daily = load(pack)
    rows = []
    for k, g in daily.groupby(KEY):
        g = g.sort_values("dt")
        start, end = g.head(14), g.tail(14)
        if len(g) < 28:
            continue
        lvl = {"level_end": end.usd_per_gpu_hour.median(), "end_from": end.dt.min(), "end_to": end.dt.max()}
        ok = start.dt.max() < pd.Timestamp("2026-03-01") and end.dt.min() > pd.Timestamp("2026-10-15")
        r = dict(zip(KEY, k), family=FAMILY[k[2]], n_days=len(g), **lvl,
                 level_start=start.usd_per_gpu_hour.median(), start_from=start.dt.min(), panel=ok)
        r["years"] = (r["end_to"] - r["start_from"]).days / 365.25
        r["change"] = r["level_end"] / r["level_start"] - 1
        r["annual_change"] = (r["level_end"] / r["level_start"]) ** (1 / r["years"]) - 1
        r["n_level_changes"] = int((g.usd_per_gpu_hour.diff().abs() > 1e-9).sum())
        # Mean level Jan 12 to Aug 31, the part of the 12 months to August 2026 the pack covers.
        r["mean_jan_aug"] = g[g.dt <= pd.Timestamp("2026-08-31")].usd_per_gpu_hour.mean()
        rows.append(r)
    v = pd.DataFrame(rows)
    Path(out).mkdir(parents=True, exist_ok=True)
    v.to_csv(Path(out, "rental_venue_change_2026.csv"), index=False, float_format="%.4f")

    p = v[v.panel]
    summ = (p.groupby(["family", "instrument_class"])
            .agg(n_venues=("change", "size"), median_change=("change", "median"),
                 p25_change=("change", lambda s: s.quantile(.25)),
                 p75_change=("change", lambda s: s.quantile(.75)),
                 share_down=("change", lambda s: (s < -0.005).mean()),
                 share_up=("change", lambda s: (s > 0.005).mean()))
            .reset_index())
    fam = (p.groupby("family")
           .agg(n_venues=("change", "size"), median_change=("change", "median"),
                p25_change=("change", lambda s: s.quantile(.25)),
                p75_change=("change", lambda s: s.quantile(.75)),
                share_down=("change", lambda s: (s < -0.005).mean()),
                share_up=("change", lambda s: (s > 0.005).mean()))
           .reset_index().assign(instrument_class="all"))
    summ = pd.concat([summ, fam])
    summ.to_csv(Path(out, "rental_change_summary_2026.csv"), index=False, float_format="%.4f")

    # Nov 2026 levels: every venue with an end window after 2026-10-15, rental classes only.
    lv = v[v.end_from > pd.Timestamp("2026-10-15")]
    levels = (lv.groupby(["family", "gpu_model", "instrument_class", "pricing_tier"])
              .agg(n_venues=("level_end", "size"), median=("level_end", "median"),
                   p25=("level_end", lambda s: s.quantile(.25)), p75=("level_end", lambda s: s.quantile(.75)))
              .reset_index())
    levels.to_csv(Path(out, "rental_levels_nov2026.csv"), index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(summ.round(3).to_string())
    print(levels[levels.pricing_tier.isin(["on_demand", "spot"])].round(3).to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
