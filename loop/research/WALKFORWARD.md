# Walk-forward rule (rolling origin): one unseen week per round

Written 2026-11-15 ~21:10Z, before any walk-forward number was computed. Code: `harness/walkforward.py`. Test: `loop/tests/test_walkforward.py`.

## Why
v8 and v8.1 each had one holdout. It was spent once, and now no unseen data is left. The loop could climb for hours with no fresh check. This rule gives every round its own unseen week. The pick is scored once on that week, and then the week joins dev.

## The rule
Round k has a cutoff C_k, the last day of dev.

1. *Dev.* The researchers get the full build cut at C_k: every series, rows dated on or before C_k. Dev cells are the harness's: origins every 2 days from Jul 1 whose targets (origin + 1, 3, 7) all fall on or before C_k. The gate is the dev origins from Sep 1.
2. *The week.* Week k is the 7 target days C_k+1 to C_k+7. Its cells are every grid origin and horizon whose target day falls in the week. A forecast at origin o still sees only rows on or before o, so no forecast sees its own target. No researcher and no director sees any price dated after C_k during round k.
3. *Pick on dev.* At the end of the round, the pick rule runs on dev only (PREREG-v81, unchanged): Jul-Aug skill at least the incumbent's, G1-G3 in pick form against the incumbent, then the highest gate skill. Ties within 0.001 go to fewer code lines.
4. *Score once.* The outer loop scores the pick and the incumbent on week k, once: skill difference and a 95% series bootstrap (10,000 draws, seed 0), as in score_heldout.py.
5. *Verdict.* Same switch rule as v8.1.
   - *win*: the difference is above 0 and the interval excludes 0. The pick becomes the incumbent.
   - *lose*: the difference is below 0, or the whole interval sits below 0 (heal.py's `lost`). This triggers healing (step 2 of the lane).
   - *tie*: anything else. The incumbent stays.
6. *Roll.* C_{k+1} = C_k + 7. Week k's prices join dev. A week is scored exactly once, as week k, and never again as unseen.
7. *Log.* One row per round in `walkforward.tsv`: round, cutoff, week, pick, incumbent, the pick's gate and Jul-Aug skill, week skill of both, difference, interval, verdict, action.

## Locked
The scorer (core.score, core.cells, the pinball loss), the per-origin cut, the grid and horizons, and the keep-rule numbers stay as they are. walkforward.py imports them and changes none. The full build lives outside the researchers' sandbox; only the outer loop opens it.

## Known limits
- One week is small: about 37 lines and 400 cells. A real gain of +0.01 will often show as a tie. Lose triggers on any negative difference, so healing will fire on some noise. Healing only adds checks that must reject the loser and pass the incumbent, so a false trigger costs a director call and can't loosen the rule.
- The prices from Nov 7 on do not exist yet. The live loop can only start new rounds as new weeks arrive.
- In a replay over frozen commits, a commit counts as a candidate only from a cutoff after the last day its researcher saw (v8: Sep 30, v8.1: Oct 15). Weeks before that would not be unseen for it.
