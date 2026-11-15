# pacsci2: what I learned

Head b06b208: Sept +.3332, Jul-Aug +.1554 (seed .1853 / .122). Every keep from 43fa54e on passes the Jul-Aug guard except 69f3ead, b186d4e and f865cde (.120-.121).

## What worked (Sept / Jul-Aug after the keep)
- State: right after a move (2 days), draw the pool only from lines that had also just moved (16c9717), and let the line use its own after-move windows (57281f6, .309/.132). Moves cluster: 62% vs 3% of days.
- Weekday: a line whose move rate differs by weekday (chi-square) learns from windows on the target weekday (43fa54e, .231/.127), plus pacsci1's weekday move-mass factor (1859cd5, .284/.125).
- Horizon: a line whose h-day spread is at least h times its 1-day spread gets summed 1-day draws (69f3ead, +.035 Sept but Jul-Aug .120). It held only together with the reversion ports.
- Reversion ports from pacsci1: class pull to the 14-day median (f865cde), noise redraw for daily re-quoters (2969d01, .299/.127), pull only on moved mass (1bd0783).
- Market = class + pricing for the pool and the pull-back (99db9d9, .319/.148): the biggest Jul-Aug gain (+.016).
- Step quantiles (no interpolation between a held price and a move) and a summed re-quoter keeping its median (799b5c4, .323/.147).
- Old levels (pacsci1 0cba333): prices quoted in the last 14 days get the market's share of moves that land on one (19a5148, .328/.157). Marketplace gained in both halves.
- Runs at their pace since the first move (pacsci1 c3bc47d; b06b208, .333/.155). Runs failed on 799b5c4 (+.0028) and passed once old levels were under them.

## What didn't (diag numbers, Sept / Jul-Aug)
- Anything that widens or narrows bands by class: Sept and Jul-Aug want opposite scales almost everywhere. Sept moved more in every class.
- Rare-mover state (a daily re-quoter is never "just changed"): Jul-Aug .155 to .168, rate card -.13 to +.01, but Sept only +.001 to +.002. The best Jul-Aug idea I had; it failed only the Sept gate.
- Variance-ratio scaling of summed bands, 7-day sibling windows, market activity factor: within ±.002.
- Busy-line residual band (pacsci3), even outside marketplace: rate card Sept .237 to .214.
- pacsci3's move calibration on step lines: .325/.161. The plain-pool prediction doesn't match my state- and weekday-dependent band.
- Summing all lines (.307/.111), no summing (.283/.153); quiet lines pooling only quiet windows (.310/.129); runs from a single move (.285/.036: lone spot steps are taken back).
- Per-line old-level rate (.329/.156): the market rate times the line's move share is better.
- Shorter-horizon fallback for a new line with no pool (pacsci1's idea, ec8bb8d): Jul-Aug .155 to .181 with Sept exactly equal (only the H100 marketplace ask, flat at h3/h7 in its first weeks). Discarded only because the gate needs a Sept gain.
- PIT-learned step-line quantile levels (pacsci3's move calibration), rebuilt per origin (70 MB): widen-only .258 Sept, widen-only bounded at .05/.95 .301, both ways .297 (head .333). The PITs come from the raw sample, but the final band adds the run shift, drifted median and noise redraw.
- My first PIT version cached a cut history per past origin and hit 2.7 GB; workers are now capped at 1.5 GB.

## What to try next
- Rate-card q10 at h7 loses to flat in both halves: one recent step fills a step line's own recent windows (recency weighting of a single event). Count a past move once per line, not once per overlapping window.
- Rare-mover state again on top of whatever comes next: it is free Jul-Aug.
- Add the shorter-horizon fallback together with any Sept gain: it is +.026 Jul-Aug for free.
- PIT calibration only if the PITs come from the full forecast (all steps after the sample), not the raw sample.
