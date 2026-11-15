# Post-mortem: pick b06b208 lost to incumbent 18c491e on holdout (-0.080 skill)

**What changed.** b06b208 (parent 19a5148) added "runs": if a line made 2 or more moves one way in the last 7 days and none back, it gets
`run = run_rate * run_pace`. Here `run_pace` = (log move since the run started) * h / (days since the first move). That run is added to
the median, and the band is stretched to reach it (`q10 = min(q10, run)`, `q90 = max(q90, run)`). In effect this draws a straight line
through a recent jump and extends it h days. Nothing caps the result. A 2-day run at h=7 is extended 3.5x.

**Where it hurt.** On dev overall the pick looks fine (skill 0.171 vs incumbent 0.152). Underneath:
- The gain is in September only: skill 0.315 vs parent 0.309 on cells whose target falls in September. On cells whose target is in the last
  15 dev days (October), skill fell from 0.163 (parent) to 0.094, below the incumbent's 0.146. It fell at every horizon (h=3: 0.111 to 0.027).
  The losses are in the origin weeks of Sep 28 and Oct 5.
- Two lines cause most of it: fastgpu B200 on-demand and gpurentalprices A100_40GB on-demand together add +1.52 loss against the incumbent.
  That outweighs the pick's whole net gain over the incumbent on dev (-0.98). Example: B200 on 2026-10-03, h=7, last price 7.52. The pick's
  median and q90 are both 11.30 (+50%). The parent's q90 was 8.20. The truth was 7.42. A100_40GB was flat at 1.99, and the pick's h=7
  median was 3.26 (+64%).
- In October the market moved more often (move share 0.45 vs 0.27) and mostly up (201 up / 45 down). Many short runs formed there and
  were extended 3-7x, but prices then held or reverted.

**Why the keep rule passed it.** The keep window rewarded September, when runs did continue. Nothing in the rule looks at (a) medians
moved outside the reference's own 80% band, (b) damage concentrated in one line, or (c) the latest dev days. Each step also only had to
beat its parent, so the pick check against the incumbent saw 0.171 > 0.152 and stopped there. Against the parent the pick was already
worse on dev overall (0.171 vs 0.205).

**What to do differently.** Cap any trend extrapolation, for example at the largest h-day move seen on that line, and don't scale it
linearly with h. Use the new checks in out/checks.py:
- loss on cells whose median falls outside the reference band must not rise by more than 1% of flat loss;
- no single line may cost more than 1% of flat loss;
- skill in the last 15 dev days must not drop by more than 0.02.

All three reject b06b208 against both the incumbent and the parent, and pass all 15 earlier steps.
