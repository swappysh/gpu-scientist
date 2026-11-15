# pacsci1: what I learned (v8-a, how prices move)

Skill vs flat, Jul-Aug / Sept (split.py). Seed .122 / .185. Guard: Jul-Aug >= .1221.

## What worked (keeps, in order)
- Per-line weekday move schedules (a45eb89): .132 / .217.
- Runs go on (56c14d1): Sept .292, but Jul-Aug fell to .111, under the guard, along with the cross-source keeps before it.
- Same-pricing pool (1565c54): spot, on-demand, community and serverless are separate markets. .141 / .300; this alone brought Jul-Aug back over the guard.
- Fresh steps taken back (104055f): .144 / .304.
- Sibling moves scaled by own/sibling move share (fda7247): .146 / .307.
- Old levels times daily move share (0cba333): .173 / .310. The biggest Jul-Aug gain; the unscaled version failed (Sept +.0029).
- Run pace from the run's first move (c3bc47d): .174 / .314.
- Sibling scale from the line's first step (5c3c8bf): .1747 / .3191. My best; it passes the guard.

## What didn't
- Hazard by age since the last change: discarded twice (Jul-Aug .118).
- Ports from the others onto 5c3c8bf: pacsci2 step quantiles .171/.317, pacsci3 move calibration .173/.317, after-move windows .176/.321 (+.002, under the gate).
- Moving q50 with step-back/levels/events: Jul-Aug up to .19, Sept flat or down.
- Activity and size scales, symmetric state conditioning, summed 1-day draws, monotone moved share across horizons (.170/.318): all down.
- Ports onto pacsci2 b06b208 (.155/.333): GPU waves .154/.336 (discarded: steps family needs +.006), scaled sibling pool .160/.335 (unscaled .143/.321: the scale is what makes it work), follow .154/.333, nested bands .168/.332, step-back .163/.331.

## Jul-Aug-only lifts the Sept gate can't keep
- Young-line fallback to the shorter horizon (the marketplace line, alone in its class from Aug 4): .205 / .319.
- Nesting the h3 band into h7: .185 / .321. Step-back and levels moving q50: .194 / .313.

## What I found
- Lines that have moved a lot still miss at h7. Sept rate cards move in 57-67% of h7 windows, but 20-27% fall above q90; gpurentalprices H100 SXM is 83% above, L4 50% below. The misses run one way per line (the Sept climbs), so symmetric widening doesn't help, and trend following is Sept-only.
- Forecasts don't depend on scoring order (the cache is per origin; 0.0 max diff over 7,392 shuffled cells).
- Bug in 5c3c8bf: a line with no own h-day pairs whose siblings all moved gets 0 weight everywhere and returns NaN. Seen only on an unscored line (fastgpu L4 card, Sept 11, h7), but a scored line younger than h days would crash the harness. Fix: own_mass = w.sum() if w.sum() > 0 else 1.0.

## Next
- Waves plus the scaled sibling pool on b06b208, tested as two separate steps (+.003 and +.001 Sept, sibling pool +.005 Jul-Aug). Both together, split.py only: .159 / .337.
- A way to keep Jul-Aug-only gains: the young-line fallback is a real +.03 on Jul-Aug.
- Rate-card h7 misses on b06b208 lean up whatever the last 7 days did: after an up week, 43% above vs 14% below in Aug (35/15 Sept); after a down week, 11/33 Aug (15/33 Sept, mostly above). Look for an up-skew, not trend following (Aug n is small).
