# v8.1 holdout result

Run once, 2026-11-15 ~20:45Z, by gpuloop, after the Pick section of PREREG.md was committed (lane repo commit 7d3ac454, 20:35Z). Command: `score_heldout.py <full build> fa_870891d.py fa_v7.py` from the v8.1 harness (research/v81 814dee7).

Holdout = origins Oct 16, 18, … 30 (8 origins), targets to Nov 6, 37 scored lines, 836 cells. Not part of dev; no researcher or the director saw it.

| | holdout skill | 80% band coverage |
|---|---|---|
| pick 870891d | +0.1233 | 0.68 |
| v7 (18c491e) | +0.1092 | 0.72 |

- Difference (pick − v7): +0.0141, 95% interval [−0.0266, +0.0527] (series bootstrap, 10,000 draws).
- Share of draws above 0: 0.768 (77%).
- Lines with lower holdout loss under the pick: 18 of 37.

## Verdict under the switch rule
The interval includes 0, so v8.1 does not replace v7. No submission file changed.

## Read with care
- gpuloop saw full October, including these weeks, before choosing the v8.1 setup (PREREG.md, Caveats). The holdout is weak evidence either way.
- The pick's band coverage is 0.04 below v7's.
- v8's pick (b06b208) lost on the same kind of holdout (−0.080, 95% [−0.130, −0.023]); v8.1's guards removed that loss but did not show a gain.
