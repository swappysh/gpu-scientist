# pacsci3: what I learned

A fresh lineage from v7 (a3d3c3d). Pick: 4fda766.
Gate .1600 -> .2125, julsep .1523 -> .2020. Split: Jul-Aug .1606 (floor .1221).
Scratch Oct 1-7 went from .145 to .215.

## What worked (gate gain at keep, resamples)
- Pool by class+pricing, not class (487353c): +.003, 1.00. Spot and on-demand are different markets. Lifted Jul-Aug +.031.
- Drop AR(1) momentum (7bffdb3): +.004, 0.86. Prices have no day-to-day momentum.
- Just-moved pool (194be78): +.018, 1.00. Moves cluster: after a line moves, borrow only changes that started right after a move. Cost Jul-Aug -.014.
- Sibling state (48b2c8f): +.006, 0.98. If the same class+GPU+pricing just moved at another source, use the just-moved band.
- Busy pull-back (5d33567): +.004, 0.81. A line that re-quotes most days drifts back to its 14-day median. Steps hold. The slope is fit by least squares on busy lines of the same class+pricing. Nearly all of it is the H100 marketplace ask.
- Take-back on step lines (d2da6d0): +.004, 0.78. A step from the last 2 days is often undone (fastgpu Oct rate cards). Add mass at the old price, sized by the class's recent take-back share. Oct 1-7 +.027.
- Busy residual band (e0a624a): +.010, 0.94. After the pull-back, the band is the spread of the fit's residuals. About 2/3 is the H100 ask, the rest busy rate cards.
- Step-line q90 nesting (4fda766): +.003, 1.00. Small gains on many lines. Costs Jul-Aug -.008, all on the young H100 ask.

## What didn't (scratch, not run)
- v8 sibling pool, follow mass and follow rate: Jul-Aug and Oct 1-7 both fall on the new split.
- Own just-moved windows: Oct 1-7 -.009. Dropping own windows that hold the fresh step: gate -.008.
- Three since-move states: Jul-Aug -.023. Too few samples per state.
- Weekday factor: gate -.016. There is no weekday pattern at h=3 or h=7.
- Learned PIT levels for the band: gate -.011, Oct 1-7 -.06. Calibration fit on the past does not carry into Oct.
- Source+class pool: gate -.013. Too thin.
- Band-only pull-back (+.001), busy residual median (worse), sibling direction filter (gate +.0015, Oct -.003).
- q10 nesting too: Jul-Aug +.040, but all on the young H100 ask, and gate -.001. That is an artifact, not a market fact.
- Half-life 10: worse on all three periods.
- h=7 q90 from h summed independent 1-day changes: gate -.002, Oct 1-7 -.010, Jul-Aug -.010.
  Days are not independent. It stacks steps that a step line rarely makes.
- One-step mixture (chance of a step in h days x size): gate +.0005 pooled, -.003 own-only. Scaling q90 by recent class move size: Oct 1-7 -.015. Flooring q90 at a sibling's 7-day rise: gate -.0075.

## Lessons
- np.quantile, np.median and Generator.choice open files inside the worker. Use sort and index.
- Check every v8 idea on Jul-Aug and Oct 1-7 per line. Several v8 gains sit on one young line, the H100 ask.
- What holds: spot and on-demand are separate markets, moves cluster, providers follow each other, busy quotes revert, and fresh steps get undone.

## Next
- Rate-card h=7 outcomes land above q90 33-34% of the time in Sep/Oct (target 10%). The upper tail of step lines is the largest gap left. 119 of 381 such cells miss, but by little: median +3%, against a q90 only ~1% above last. Widening every step line costs as much on the flat cells. Next: find which lines creep up (e.g. median-of-providers lines).
- The H100 ask drives much of the gate. Test every change with that line removed.
- Fit the busy share and median window per class rather than using fixed 0.5 and 14 days.
