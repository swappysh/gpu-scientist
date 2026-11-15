# pacsci1, v8.1: what I learned (angle: the new regime)

Start 19a5148: gate +0.2168, Jul-Sep +0.2048, Jul-Aug +0.1574, Oct 1-7 +0.1571.

## What 19a5148 gets wrong on Oct 1-7
- Bands are too narrow: 70% coverage (aim 80%); 16% land above q90, 14% below q10.
- Most of the loss is the Oct 1-3 market-wide jump (B300 +14%, A100_40GB +54%).
  Nothing in the history predicts it.
- The jump then enters bands: A100_40GB at Oct 5 had q90 3.07 at h=7 with the last
  price at 1.99, so the band re-applied the +54% step.

## Best: 870891d (KEEP), a big step is a new level + pace that fades
- New level: an on-demand line's most recent step in the last 14 days that is over 4x
  the median of its other steps is taken out of the windows that span it, in its own
  changes and in the class pool its siblings use.
- Pace: moved windows weigh more (only up, at most 2x) when this source's market moved
  more often in the last 7 days than in the 21 before.
- Gate +.2315, Jul-Sep +.2173, Jul-Aug +.1615 (split.py), Oct 1-7 +.1833, resamples .98.
- Unused dev origins Oct 8-14 (455 cells): .2661, vs .2116 for 19a5148.
- The run took 408 s (others 60 s): the per-step loop is slow; the limit is 900 s.

## How I got there (gate)
- 7100b8c: pace against the 28 days before: .2236, but Oct 8-14 .2026. Once busy is
  normal, a 28-day base keeps widening bands. A 21-day base fades.
- Netting only the very last step, only in the line's own windows: .2264 (discard).
  In the pool too: .2267 (4add042). The latest big step even with small re-quotes after
  it: .2315. Most of the gain is lines that re-quoted after the Oct 1-3 jump.
- Pace per line or per class over all sources: loses Jul-Aug. Cap 1.5: -0.002.
- Netting every last step loses Sep (small steps creep on); spot lines lose (big steps
  repeat there). Thresholds 3x/5x, base 10 or a 10-day recent window: no better.

## Lost (pre-screens on 7100b8c, gate change)
- Shorter memory when busier: Oct 1-7 -0.015. Pace without the cap: -0.001.
- Pull-back fitted apart for just-moved vs settled quotes: -0.0013; per source: -0.003.
- No median carry for lines whose moves add up: Sep -0.006.
- Removing old levels, weekday rates or summed 1-day draws: -0.002 to -0.011 each.

## Next
- Score candidates on Oct 8-14 before picking. Pick 870891d. Speed up its step loop.
