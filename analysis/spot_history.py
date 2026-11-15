"""Monthly AWS spot price per GPU-hour for the A100, H100 and neighbour families, May 2022 to Oct 2026.

Instrument: hyperscaler_spot (AWS EC2 spot, an administered price). Contract per family:
one instance type, Linux/UNIX, every availability zone that quotes it, USD per GPU-hour
(instance price / GPU count). The archive is a stream of change events; this script
samples the price in force at 12:00 UTC each day per (instance type, AZ), takes the
median across AZs, then the median of those daily values per month. Months 2026-03 to
2026-06 are missing from the archive and stay missing (no interpolation).

Usage: python -I analysis/spot_history.py PACK_DIR OUT_DIR
Writes OUT_DIR/spot_monthly.csv and OUT_DIR/spot_yearly_change.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

INSTANCES = {
    "p3.16xlarge": "V100 16GB",
    "p4d.24xlarge": "A100 40GB",
    "p4de.24xlarge": "A100 80GB",
    "p5.48xlarge": "H100 80GB",
    "p5en.48xlarge": "H200",
    "p6-b200.48xlarge": "B200",
}
COLS = ["az_global_id", "instance_type", "product_description", "ts_utc", "usd_per_gpu_hour"]


def month_daily(path, carry):
    """Daily 12:00 UTC price per (instance, az) for one monthly file.

    carry holds the last price per key from the previous month, used only when the
    previous month exists (the archive also clamps a carried-in row to the month start).
    """
    t = pq.read_table(path, columns=COLS,
                      filters=[("instance_type", "in", list(INSTANCES)),
                               ("product_description", "=", "Linux/UNIX")]).to_pandas()
    if t.empty:
        return pd.DataFrame(), carry
    t = t.sort_values("ts_utc")
    month = pd.Timestamp(t.ts_utc.min()).to_period("M")
    days = pd.date_range(month.start_time, month.end_time.normalize(), freq="D") + pd.Timedelta(hours=12)
    out = []
    for (inst, az), g in t.groupby(["instance_type", "az_global_id"]):
        ts = g.ts_utc.values
        px = g.usd_per_gpu_hour.values
        idx = np.searchsorted(ts, days.values, side="right") - 1
        prev = carry.get((inst, az), np.nan)
        vals = np.where(idx >= 0, px[np.clip(idx, 0, None)], prev)
        carry[(inst, az)] = px[-1]
        out.append(pd.DataFrame({"day": days.normalize(), "instance_type": inst, "az": az, "price": vals}))
    return pd.concat(out), carry


def main(pack, out):
    files = sorted(Path(pack, "aws_spot_ticks").glob("aws_spot_ticks_*.parquet"))
    carry, daily, last_month = {}, [], None
    for f in files:
        m = pd.Period(f.stem.split("_")[-1], "M")
        if last_month is not None and m != last_month + 1:
            carry = {}  # archive hole: never carry a price across it
        d, carry = month_daily(f, carry)
        if not d.empty:
            daily.append(d)
        last_month = m
    d = pd.concat(daily).dropna(subset=["price"])
    per_day = d.groupby(["instance_type", "day"]).price.agg(["median", "size"]).reset_index()
    per_day["month"] = per_day.day.dt.to_period("M").astype(str)
    monthly = (per_day.groupby(["instance_type", "month"])
               .agg(usd_per_gpu_hour=("median", "median"), n_az_median=("size", "median"),
                    n_days=("day", "size")).reset_index())
    monthly["gpu"] = monthly.instance_type.map(INSTANCES)
    monthly = monthly[["gpu", "instance_type", "month", "usd_per_gpu_hour", "n_az_median", "n_days"]]
    Path(out).mkdir(parents=True, exist_ok=True)
    monthly.to_csv(Path(out, "spot_monthly.csv"), index=False, float_format="%.4f")

    # Year-on-year change, same calendar month (Oct to Oct; Feb used where Oct is missing).
    rows = []
    piv = monthly.pivot(index="month", columns="gpu", values="usd_per_gpu_hour")
    for gpu in piv.columns:
        s = piv[gpu].dropna()
        for a, b in [("2022-10", "2023-10"), ("2023-10", "2024-10"), ("2024-10", "2025-10"),
                     ("2025-10", "2026-10"), ("2022-10", "2026-10"), ("2023-10", "2026-10")]:
            if a in s.index and b in s.index:
                yrs = (pd.Period(b, "M") - pd.Period(a, "M")).n / 12
                r = s[b] / s[a]
                rows.append({"gpu": gpu, "from": a, "to": b, "price_from": s[a], "price_to": s[b],
                             "ratio": r, "annual_change": r ** (1 / yrs) - 1})
    pd.DataFrame(rows).to_csv(Path(out, "spot_yearly_change.csv"), index=False, float_format="%.4f")
    print(piv.round(3).to_string())
    print(pd.DataFrame(rows).round(3).to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
