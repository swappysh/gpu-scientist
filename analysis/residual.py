"""Rent and residual-value scenarios for the H100 SXM and A100 80GB, Nov 2028 and Nov 2029.

Rent: neocloud_rate_card, on demand, USD per GPU-hour, venue medians (never spliced with
other instrument classes). Three paths from the Nov 2026 level:
  low  = today's level decays at the cross-section age slope (how much less a chip one
         year older rents for today, fitted on V100, A100, H100, B200);
  mid  = back to the early-2026 level of the same venues, then flat;
  high = today's level held flat (what A100 spot did from age 2 to age 6).

Residual: used price = M x annual rent at 100% use, where M depends on chip age. M is
calibrated on two used prints (American Compute, GPU Prices, October 2026, 12 months to
August 2026; outside the pack, cited by pointer in resale_pointers.csv) against each
chip's mean rent over Jan 12 to Aug 31 2026. Two points give a log-linear M(age); low and
high use the low and high ends of the used-price range. A lease floor column gives
the value lost per GPU-hour for a chip bought at the used midpoint today. Residual % is over the launch
price in hardware_fundamentals (A100 80GB has none there, so the A100 40GB price stands in).

Usage: python -I analysis/residual.py PACK_DIR RESULTS_DIR
Reads RESULTS_DIR/rental_levels_nov2026.csv and rental_venue_change_2026.csv (from
rental_trend_2026.py). Writes RESULTS_DIR/residual_scenarios.csv and residual_inputs.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HOURS = 8760
CAL_DATE = pd.Timestamp("2026-03-01")  # middle of the 12 months to August 2026
NOW = pd.Timestamp("2026-11-06")       # pack data cutoff
HORIZONS = [pd.Timestamp("2028-11-06"), pd.Timestamp("2029-11-06")]

# American Compute, GPU Prices, October 2026, https://www.amcompute.com/gpu-prices
# (used per-GPU resale, 12 months to August 2026; accessed 2026-11-14).
USED = {"H100": (10_000, 14_000), "A100": (4_700, 5_400)}
# American Compute, GPU residual value report, June 2026,
# https://www.amcompute.com/gpu-resale-index/residual-value (% of price new; accessed 2026-11-15).
AMC_BANDS = {("H100", 2028): ("5-7%", "7-14%"), ("H100", 2029): ("2-3%", "3-6%")}

CHIPS = {  # family: (gpu_models in the rental data, accelerator in hardware_fundamentals)
    "H100": (["H100 SXM 80GB"], "NVIDIA H100 SXM5 80GB"),
    "A100": (["A100 SXM 80GB", "A100 80GB"], "NVIDIA A100 SXM4 80 GB"),
}
AGE_LADDER = {  # one model per generation for the age slope
    "V100": "NVIDIA V100", "A100 80GB": "NVIDIA A100 SXM4 80 GB",
    "H100 SXM 80GB": "NVIDIA H100 SXM5 80GB", "B200": "NVIDIA B200",
}


def years(a, b):
    return (b - a).days / 365.25


def main(pack, res):
    hw = pd.read_csv(Path(pack, "hardware_fundamentals", "hardware_fundamentals.csv"),
                     parse_dates=["release_date"]).set_index("accelerator")
    lv = pd.read_csv(Path(res, "rental_levels_nov2026.csv"))
    vc = pd.read_csv(Path(res, "rental_venue_change_2026.csv"), parse_dates=["start_from", "end_from"])
    od = lambda d: d[(d.instrument_class == "neocloud_rate_card") & (d.pricing_tier == "on_demand")]
    lv, vc = od(lv), od(vc)

    # Age slope: log Nov 2026 rent on release date across generations.
    lad = lv[lv.gpu_model.isin(AGE_LADDER)].set_index("gpu_model")["median"]
    age = np.array([years(hw.loc[AGE_LADDER[m], "release_date"], NOW) for m in lad.index])
    slope = np.polyfit(age, np.log(lad.values), 1)[0]
    decay = np.exp(slope) - 1  # change in rent per extra year of age

    rows, inputs = [], []
    for fam, (models, acc) in CHIPS.items():
        rel = hw.loc[acc, "release_date"]
        launch = hw.loc[acc, "release_price_usd"]
        if np.isnan(launch):
            launch = hw.loc["NVIDIA A100 SXM4 40 GB", "release_price_usd"]
        v = vc[vc.gpu_model.isin(models)]
        now = v[v.end_from > pd.Timestamp("2026-10-15")].level_end.median()
        early = v[v.panel].level_start.median()
        trail = v[v.start_from < pd.Timestamp("2026-02-01")].mean_jan_aug.median()
        m_lo, m_hi = (u / (trail * HOURS) for u in USED[fam])
        inputs.append({"family": fam, "release_date": rel.date(), "launch_price": launch,
                       "rent_nov2026": now, "rent_early2026": early, "rent_jan_aug_2026": trail,
                       "used_lo": USED[fam][0], "used_hi": USED[fam][1], "M_lo": m_lo, "M_hi": m_hi,
                       "age_at_cal": years(rel, CAL_DATE),
                       "n_venues_now": int((v.end_from > pd.Timestamp("2026-10-15")).sum()),
                       "n_venues_panel": int(v.panel.sum()), "age_slope_decay": decay})
    inp = pd.DataFrame(inputs).set_index("family")

    # M(age): log-linear through the two chips' midpoints, same slope for lo and hi.
    a = inp.age_at_cal.values
    m_mid = np.sqrt(inp.M_lo * inp.M_hi).values
    m_slope = (np.log(m_mid[1]) - np.log(m_mid[0])) / (a[1] - a[0])
    inp["M_age_slope"] = m_slope

    for fam, r in inp.iterrows():
        for h in HORIZONS:
            t, age_h = years(NOW, h), years(pd.Timestamp(r.release_date), h)
            shift = np.exp(m_slope * (age_h - r.age_at_cal))
            rent = {"low": r.rent_nov2026 * (1 + decay) ** t, "mid": r.rent_early2026, "high": r.rent_nov2026}
            mult = {"low": r.M_lo * shift, "mid": np.sqrt(r.M_lo * r.M_hi) * shift, "high": r.M_hi * shift}
            for case in ["low", "mid", "high"]:
                value = mult[case] * rent[case] * HOURS
                rows.append({"family": fam, "date": h.date(), "age_years": round(age_h, 1), "case": case,
                             "rent_usd_hr": rent[case], "M": mult[case], "residual_usd": value,
                             "residual_pct_launch": value / r.launch_price,
                             # Lease floor: value lost per GPU-hour if bought at the used midpoint
                             # today and sold at this residual, at 70% use (no power, opex or margin).
                             "depr_usd_hr_70pct": (np.mean(USED[fam]) - value) / (t * HOURS * 0.7),
                             "amc_conservative": AMC_BANDS.get((fam, h.year), ("", ""))[0],
                             "amc_moderate": AMC_BANDS.get((fam, h.year), ("", ""))[1]})
    out = pd.DataFrame(rows)
    inp.to_csv(Path(res, "residual_inputs.csv"), float_format="%.4f")
    out.to_csv(Path(res, "residual_scenarios.csv"), index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(inp.round(3).T.to_string())
    print(out.round(3).to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
