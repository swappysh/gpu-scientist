# pacsci2, v8.1: what I learned (angle: simplify 19a5148)

Start 8ccbf1d (= 19a5148): gate +.2168, Jul-Sep +.2048, Jul-Aug +.1574, Oct 1-7 +.1571.
Best c9804cc: gate +.2274, Jul-Sep +.2147, Jul-Aug +.1649, Oct 1-7 +.1801. 192 code lines (start 210).

## What worked
- dde369c keep: dropped a line's own after-move windows and the share x pull-back
  median term. Gate +.0039, Jul-Aug +.0077, Oct 1-7 +.0136. After a jump, the
  just-moved class pool says more than the line's own few post-move windows.
- 5aa136a keep-simpler: dropped the source weekday profile prior and the fixed 0.03
  median drift. Same gate (.2207), 21 fewer code lines. The median now stays at the
  last price unless the line's moves add up.
- c9804cc keep: for lines whose moves add up, the band is the wider of the summed
  1-day draws and the line's direct h-day changes (both tails). Gate +.0066,
  Oct 1-7 +.0101, Jul-Aug flat; 4 rate cards gain, no line loses. On busy October
  rate cards (fastgpu h3/h7) the summed band was narrower than the real h-day moves.
  Upper tail only: gate +.005, Oct +.003.

## Which parts carry the gain (removing each one on the start point, Jul-Aug/gate/Oct 1-7)
- Just-moved pool: .179/.184/.146. The biggest part on the gate (-.033).
- Class pull-back to the 14-day median: .151/.202/.156 (gate -.015).
- Sibling trigger: .164/.206/.151 (gate -.011). It costs Jul-Aug but pays later.
- Persistent sums: .165/.210/.168. A September part before the union band; after
  it, removing them costs the gate .012 and gains Oct 1-7 nothing.
- Noise redraw .161/.212/.155; old levels .147/.215/.157; pricing split .140/.214/.158.
- Dead: own after-move windows, share x pull median term, source weekday profile,
  fixed 0.03 drift. Same-weekday windows are worth about .001.

## What didn't work and why I think so
- Gating persistence (recent 60 days only, or a move-count floor): no gain. The
  problem was the band width, not which lines count as persistent.
- One pooled set of 1-day draws instead of per-weekday draws: gate -.0024.
- Weekday factor on every line, no chi-square test: gate -.005, Oct -.009 (noise).
- Same-weekday band floored at the all-weekday band: Jul-Aug -.005 (quiet days are narrow).

## What I'd try next
- Union floor on the just-moved pool band: neutral (gate -.0007); that pool is wide enough.
- Sibling trigger's Jul-Aug cost is one line (gpr L40S), set off by a busy afhubbard
  sibling (moves 23% of days). Try ignoring siblings that re-price that often.
