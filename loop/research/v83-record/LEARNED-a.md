# pacsci1, v8.3: what I learned (start b776439, angle: a run stops, new level)

Start b776439: gate +0.2077, full dev +0.2021. Best now 93f54d7: gate +0.2275 (+0.0198), full +0.2199 (+0.0178), Jul-Aug +0.1645 (above v7's +0.1221). It beats 870891d (gate +0.2058) by +0.022.

What worked: runs get taken back, so price that in.
- 8f6986b (keep, +0.0119 gate): a rate card in a run of same-way moves gets extra forecast weight halfway back to its pre-run price. That weight is the market's recent share of runs that gave back at least half within h days. Before this, 23% of fresh up-runs at h7 ended below q10, and q10 sat only 0.8% under the last price. Oct 23-29 +0.041.
- d92c086 (keep, +0.0036): a lone step counts as a run of one. A step's old price is often older than the 14-day old-levels window.
- 93f54d7 (keep, +0.0043, 85% of resamples): a run that settled more than 60 days ago is the level, so it gets no take-back weight. Gains on every window; old runs had also diluted the market rate.
- Gain of d92c086 by two-week block: Oct 7-20 +0.025, Oct 21-29 +0.041, Sep 9-22 -0.002 (the creep weeks). It pays when runs reverse and costs a little when prices creep. That is a good bet for November.
- Robust to the landing point: weight at the full pre-run price still gives +0.012 over the start (halfway gives +0.0155).

What failed, and why I think so:
- "A fresh run goes one more step" is the mirror idea. As learned weight it fell -0.042 on the gate: the share is 0.70-0.78 in Oct (daily creepers) and it drags the median. As band only, it fell -0.007. Runs end. Price in a take-back, never a continuation.
- A line's own take-back record shrunk to the market's: -0.004. Take-backs are a market rate, not a line habit.
- Separate take-back rates for lines that just moved vs lines that held, plus pacsci2's rare-mover sibling trigger (c323174): Jul-Aug +0.012, gate +0.0007, but it held on only 49% of resamples. Discarded. The trigger alone on 93f54d7: gate +0.0002, Jul-Aug +0.007.
- Take-back on spot lines too (on top of d92c086): gate +0.0002, Jul-Aug -0.008. Keep it to rate cards.
- Dropping the old-levels weight (-0.0026) or the source pace factor (-0.0046): both still pay.

Next: watch whether November runs reverse like late October did. If prices creep all month, expect about -0.002 from the take-back.
