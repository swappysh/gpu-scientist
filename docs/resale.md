# H100 and A100 in 2028 and 2029: rent and resale value

An H100 that cost $33,600 at launch will rent for about $3/hr and sell for about $4,700 in November 2028. That is 14% of its launch price; our range is 8% to 22%. An A100 will rent for about $1.50/hr and sell for about $1,400.

Rent is the anchor, and old GPUs keep earning. On AWS spot, a six-year-old A100 rented for more in October 2026 than it did at age two. A used GPU sells for a fraction of a year's rent, and that fraction shrinks as the chip ages. So we forecast rent first, then turn rent into a resale value.

All figures are USD per GPU. Rents are posted on-demand prices from neocloud rate cards (Lambda, Nebius, Verda and similar) unless we say otherwise. The pack's data ends on 2026-11-06.

## The view

| | Nov 2028 low / mid / high | Nov 2029 low / mid / high |
|---|---|---|
| H100 SXM rent, $/hr | 2.11 / 2.95 / 3.99 | 1.54 / 2.95 / 3.99 |
| H100 SXM resale | $2,800 / $4,700 / $7,400 | $1,500 / $3,500 / $5,600 |
| H100 SXM resale, % of launch | 8% / 14% / 22% | 5% / 10% / 17% |
| A100 80GB rent, $/hr | 1.18 / 1.54 / 2.24 | 0.86 / 1.54 / 2.24 |
| A100 80GB resale | $1,000 / $1,400 / $2,200 | $560 / $1,070 / $1,660 |
| A100 80GB resale, % of launch | 7% / 9% / 15% | 4% / 7% / 11% |

The A100 percentages use the A100 40GB launch price of $15,000, because the pack has no launch price for the 80GB card. The 80GB card launched later and almost certainly cost more, so these A100 percentages run high.

For a lease: a lessor who buys a used H100 today at $12,000 and sells it at our mid value in November 2028 loses about $0.60 per GPU-hour at 70% use. Power, hosting and margin come on top. The same sum for an A100 bought at $5,050 is about $0.30.

## Why rent holds up

Three things in the pack set the rent paths.

**Old chips have kept their rent.** AWS spot for the A100 40GB was $1.69/hr in October 2022 and $2.09/hr in October 2026, about 6% a year up. It fell 26% over the first three of those years and then jumped in 2026. The H100 had the rougher ride: AWS spot fell from $8.79 to $2.71 between October 2023 and October 2025, then rose 36% to $3.68.

**2026 was a shortage year.** Every neocloud rate card that we can follow from January to November 2026 went up. The median rise was 42% for the H100 and 65% for the A100. Most of it came in March to May. Hyperscaler list prices did not move. Our mid case assumes this surge unwinds: rents fall back to the January 2026 level of the same venues ($2.95 for the H100, $1.54 for the A100) and stay there.

**A chip one year older rents for about 27% less.** Across V100, A100, H100 and B200 in November 2026, rent falls 27% for each extra year since launch. Our low case applies that slope to today's rent every year. Our high case holds today's rent flat, as A100 spot did over four years.

Newer chips are cheaper per unit of work. Measured by the pack's capability ladder (A100 = 1, H100 = 2.46, B200 = 7.91), an A100 costs $2.24/hr per unit and a B200 $1.04. That 2.2x gap is the pressure that pulls old rents down.

## From rent to resale

A used GPU sells for a fraction of one year's rent at full use. We call that fraction M. We read M from two used-price prints:

- H100 SXM sold for $10,000 to $14,000 over the 12 months to August 2026, while it rented for a median $3.44/hr. So M = 0.33 to 0.46, at about 3.4 years old.
- A100 80GB SXM sold for $4,700 to $5,400, while it rented for $2.50/hr. So M = 0.21 to 0.25, at about 5.3 years old.

M falls about 25% for each year of age between those two points. We extend that line to 2028 and 2029. Two points are thin evidence, and the whole resale column rests on this line. If buyers stop paying for remaining life faster than this, the low case is the better guide.

Resale value = M × rent × 8,760 hours. Low uses the low rent path with the low end of M; high uses the high rent with the high end of M.

A check on the H100 mid case for November 2028: M is 0.39 at age 3.4 and falls to 0.18 by age 6.1. So the resale value is 0.18 × $2.95 × 8,760 = $4,650, which the table rounds to $4,700.

## Where we differ from the published bands

American Compute publishes forward residual bands for the H100. For 2028 they give 5% to 7% of price new (conservative) and 7% to 14% (moderate). For 2029 they give 2% to 3% and 3% to 6%.

Our mid case sits at the top of their moderate band in 2028, and well above it in 2029. Their own used prices are the reason we stay higher. A 5-year-old A100 80GB sells for about a third of the A100 40GB launch price today. Their bands say a 6-year-old H100 will hold one seventh or less. The H100 launched at a shortage price, so a lower share is plausible. A drop that steep would also need H100 rent to fall well below our low path.

Their conservative band suits a lender who wants a margin of safety. On our evidence, it assumes a rent collapse that the pack has not shown for any chip yet.

## Assumptions

- Rent paths start from the November 2026 median of 25 H100 SXM venues ($3.99) and 24 A100 80GB venues ($2.24).
- The January 2026 levels come from 3 H100 and 2 A100 venues that span the whole year. That is a small base for the mid case.
- M depends on chip age and nothing else. Both chips follow the same age line.
- Used prices are broker midpoints. Forced sales would clear lower.
- No currency, tax, power or hosting effects.

## What would change the view

- **Blackwell and Rubin supply.** Fast B200 and B300 ramps pull rents down hardest on the A100, which already costs 2.2x a B200 per unit of work. That moves us toward the low case.
- **The 2026 surge.** If rents stay at November 2026 levels into 2027, the high case is the better guide. If they fall below January 2026 levels, M will fall too, and both effects compound.
- **A floor from power.** An A100 draws 400 W and an H100 700 W. Once rent nears power and hosting cost, operators retire chips and resale goes toward scrap.
- **A new used-price print.** One more dated print for an H100 or A100 would test the M line directly.

## Sources

Pack data (gpu-price-pack v0.1.1-handover), cited with the pack's ATTRIBUTION.md wording:
- AWS spot: "AWS Spot Price History", Eric Pauley (University of Wisconsin-Madison), Zenodo, https://doi.org/10.5281/zenodo.14198917 (version 2026-10: https://doi.org/10.5281/zenodo.23853281), CC BY 4.0.
- Rate cards: Hubbard, A. (2026). GPU Price Tracker dataset. https://github.com/alex-hubbard/gpu_price_tracker (CC BY 4.0). GPU rental price data by gpurentalprices.com (https://gpurentalprices.com), licensed under CC BY 4.0. Data: FastGPU GPU cloud pricing dataset (https://fastgpu.co/dataset), CC BY 4.0.
- Launch prices and release dates: Epoch AI, 'Data on machine learning hardware'. Published online at epoch.ai. Retrieved from 'https://epoch.ai/data/machine-learning-hardware' [online resource]. These are analyst estimates; the H100 has no official MSRP.
- Capability ladder: built from MLCommons MLPerf® Inference results (Apache License 2.0), as described in the pack's capability/BUILD_capability.md.

Outside the pack (public, free, dated before 6 November 2026; both pages are listed in the pack's resale_pointers.csv):
- American Compute, GPU Prices, October 2026, https://www.amcompute.com/gpu-prices (accessed 2026-11-14). Used H100 SXM and A100 80GB SXM prices, 12 months to August 2026.
- American Compute, GPU residual value report, June 2026, https://www.amcompute.com/gpu-resale-index/residual-value (accessed 2026-11-15). H100 residual bands.

## Reproduce

```
python -I analysis/spot_history.py PACK_DIR results/resale
python -I analysis/rental_trend_2026.py PACK_DIR results/resale
python -I analysis/residual.py PACK_DIR results/resale
```

Each runs in under 10 seconds. The view table comes from results/resale/residual_scenarios.csv, and its inputs from residual_inputs.csv.
