# Replay: the new loop over Oct 1 - Nov 4, frozen v8 and v8.1 commits

Run 2026-11-15. No new researcher calls. One real director call for healing ($0.89). Rule: WALKFORWARD.md, written before these numbers.

## Answer
The new loop would not have shipped v8. In the first week (Oct 1-7), v8's pick b06b208 tied v7 (+0.007, 95% interval -0.021 to +0.044), so v7 stayed. In the second week (Oct 8-14), b06b208 lost clearly (-0.137, interval -0.317 to -0.001), and healing started on its own. So the first week held v8 back, and the second week caught it as a loss.

## Setup
- 72 frozen forecasters: v7 (18c491e, the incumbent), 57 v8 keeps (they compete from the Sep 30 cutoff) and 14 v8.1 keeps (from Oct 15).
- Five rounds, cutoffs Sep 30, Oct 7, 14, 21 and 28. Each round picks on dev up to its cutoff and is scored once on the next 7 target days. Round 1 uses v8's pick rule (no guards). Rounds 2-5 use v8.1's rule.
- One forecaster run on the full pack (to Nov 6) gives every round's cells. That is leak-free because each origin sees only rows up to that origin (a test checks it).

## Rounds (pick vs v7 on the week; skill difference, 95% interval)
1. Cutoff Sep 30, week Oct 1-7: b06b208 (v8's pick), +0.007 [-0.021, +0.044]. Tie, v7 stays.
2. Cutoff Oct 7, week Oct 8-14: b06b208, -0.137 [-0.317, -0.001]. Lose, heal starts.
3. Cutoff Oct 14, week Oct 15-21: 19a5148, -0.002 [-0.060, +0.058]. Lose (any negative difference counts), heal starts.
4. Cutoff Oct 21, week Oct 22-28: 870891d (v8.1's pick), +0.008 [-0.044, +0.055]. Tie, v7 stays.
5. Cutoff Oct 28, week Oct 29-Nov 4: 4fda766, +0.124 [+0.004, +0.226]. Win, 4fda766 becomes the incumbent.

## Healing on round 2 (dry run)
- The director saw only dev up to Oct 7 and the week's numbers. It found that b06b208 pushes the median along each line's recent move: it carries 0.33 of the past week's move, against 0.07 or less for every earlier step.
- It wrote two checks. One rejects a pick that carries more than 0.15 of the past move. The other rejects a pick that loses more than 2% if the last week's moves reverse.
- Both checks passed the trial: each rejects the pick, passes v7, and rejects none of the 14 earlier steps.
- The dry run would restart the researchers from 19a5148 and v7, with dev extended through Oct 14.

## Did healing help later rounds?
Not on these weeks. Rounds 3-5 were rerun with the two checks in the pick rule. They changed the picks in rounds 3 and 4 (to 1bd0783 and c9804cc), but not the verdicts: lose (-0.010), tie (+0.006), then the same win in round 5.

## Limits
- Weeks are small: about 37 lines. The round 3 "lose" is noise (-0.002), and a loss that small still costs a director call.
- Weeks from Oct 16 overlap v8.1's spent holdout. The v8.1 researchers never saw them, but we knew v8.1's holdout result when we wrote this rule.
- The replay ran with frozen commits, so it can't show what restarted researchers would have found.
- Bug found and fixed by this dry run: in walk-forward mode, healing extended dev to the end of the pack (Nov 6), which would have shown later weeks to the restarted researchers. Now it extends dev only through the lost week.
