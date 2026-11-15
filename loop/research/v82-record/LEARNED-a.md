# pacsci1, v8.2: what I learned (start 870891d, angle: the busy weeks Oct 8-29)

Baseline 870891d: gate +0.2058, full dev +0.2004. On Oct 8-29 origins alone: +0.1747.

Where it loses to flat on Oct 8-29 (per line and horizon, as a share of total flat loss):
- fastgpu B300 rate card h7 (0.005): a -13% drop on Oct 23 after a month of rises. No model saw it coming. The band was wide upward, but the low end sat right at the last price.
- fastgpu B300 spot h7 (0.0035): the price crept up daily until Oct 17, then held. The model kept moving the median up for two more weeks.
- Smaller: the gpurentalprices H100 ask h3, and a never-moving A100_40GB rate card whose q90 jumped to +53% when a sibling moved.

Tried (no keeps):
- b776439 (discarded): a line whose moves add up keeps its median carry only if it moved in the last 2 days. Oct 8-29 +0.0045, gate +0.0019, full +0.0017, 82% of resamples. It's true and robust, but under the 0.003 bar. The market fact: a run that stopped is a new level, not a trend.
- Not run: ending the summed band too for such lines. Worse than changing only the median (Oct 8-29 -0.003). After a run, the band should stay wide.
- Not run: no sibling trigger for lines with no re-price in 60 days. Neutral (-0.0001).
- Not run: the line's move rate over the last 14 days instead of all history. Worse (-0.005): early October was busier, so the drift grew.

Next:
- Pair the run-stop rule with another small, true fix and test the two as one change. On its own it is just under the bar.
- B300 rate card: after a run of rises, a step back down is plausible. Look at whether the q10 of a just-risen rate card should open up to the pre-run level (the take-back mass, but for runs, not single steps).
