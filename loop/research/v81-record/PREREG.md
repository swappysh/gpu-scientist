# v8.1 pick and holdout: pre-registration

Written 2026-11-15 18:04Z (10:04 AM PT) by gpuloop, on the plan the owner approved via iterate (9:52 AM PT). The researchers have not yet seen any v8.1 dev data (rows after Sep 30). The authoritative copy was committed in gpuloop's lane repo (commit 7d3ac454 holds the filled Pick section); the commit time is the timestamp. The researchers had a read-only copy. Everything above the Pick section is fixed by this commit; the Pick section is filled in at 20:00Z, and then this copy is made read-only too.

## Why
The v8 pick, b06b208, lost to v7 on October (−0.080, 95% [−0.130, −0.023]). v8.1 extends dev to Oct 15, adds post-mortem guards, and restarts the researchers from 19a5148 (the step before b06b208) and from v7. One holdout run at the end decides whether anything beats v7.

## Split (harness: research/v81 814dee7)
- Dev = rows to Oct 15. Dev origins = Jul 1 – Oct 7, every 2 days (50), so every target is on or before Oct 15.
- Gate (column "sept" in results.tsv) = origins Sep 1 – Oct 7.
- Holdout = origins Oct 16, 18, … 30 (8), targets to Nov 6, from the private full build. Scored once, by gpuloop, at ~20:00Z.
- The plan said "gate = Sep 1 – Oct 15". gpuloop ended dev origins at Oct 7 so no target passes Oct 15.

## Keep rule
- The locked v8 rule stays unchanged: gate gain ≥ +0.003, Jul-Sep drop ≤ 0.005, ≥ 60% of resamples favour the change, and the simpler-change rule.
- Added (harness/guards.py): a keep or keep-simpler must also pass G1–G3 against the current best, on per-cell dev rows.
  - G1, big median bets must pay: on cells where the candidate's median is more than 0.04 (log) from the parent's, the candidate's loss must not exceed the parent's.
  - G2, the newest week must not drop: on origins Oct 1–7, skill may not fall more than 0.005 below the parent's.
  - G3, no single line pays for the rest: no line's loss may rise by more than 0.005 of the total flat loss.

## Pick at 20:00Z (12:00 PM PT)
1. Candidates:
   - every commit on research/v81-a, -b and -c logged as keep or keep-simpler by 20:00Z;
   - plus the start points, v7 (18c491e) and 19a5148.
   gpuloop re-scores each one with the locked v8.1 harness.
2. Eligible only if all of these hold:
   - (a) July-August skill (origins before Sep 1) ≥ +0.1221. That is v7's score on this dev file, the same bar as v8.
   - (b) G1–G3 in pick form, against v7:
     - G1: on cells where the median is more than 0.04 from the last price, skill vs flat ≥ 0;
     - G2: Oct 1–7 origins no more than 0.005 below v7;
     - G3: no line's loss up more than 0.005 of the total flat loss vs v7.
   - (c) The order check from v8 PREREG rule 6, run on Modal: shuffled order and a fresh process per origin, every cell within 1e-9.
3. Pick = the highest gate skill among eligible candidates. If two are within 0.001, take the one with fewer lines. If the pick is v7, nothing changes.
4. Holdout: `score_heldout.py <full build> <pick> <v7>` from the v8.1 harness, once. It gives skill, coverage, a series bootstrap of the difference (10,000 draws), and the number of lines better.
5. The pick hash and its numbers are written below and committed before the holdout runs.

## Switch rule
v8.1 replaces v7 only if both hold:
- the pick beats v7 on the holdout and the 95% interval of the difference excludes 0;
- the owner says yes.

No submission file (submit_config.json, the forecasts CSV) is touched before both hold.

## Who proposed what
- Plan (new split, guards, restart from 19a5148 and v7, switch rule): the owner, via iterate (9:52 AM PT). A healing round before the restart: the owner, via iterate (9:42 AM PT).
- Guards G1–G3: the director, meta round 5 "healing", a fresh agent. It saw only:
  - the failure signal above;
  - per-cell dev results (origins to Oct 7) for v7, 19a5148 and b06b208;
  - the 16 chain forecasters and their commit messages;
  - move rates for Jul-Aug, Sept and Oct 1–15.

  It did not see any Oct 16–31 data. Correction (18:10Z, before the researchers restart): it did see gpuloop's guard (1) as code, because core.cap_over was in the harness it was allowed to read. Its post-mortem says that cap would not have fired, and it proposed G1 instead. It did not see gpuloop's guards (2) and (3). Its settings: G1 0.04, "about two typical moves", chosen before testing. G2 and G3 use 0.005, the size of the locked Jul-Sep tolerance. Tests on dev:
  - each guard rejects b06b208 as a keep (vs 19a5148) and as a pick, and passes v7 and 19a5148 as picks;
  - of the 15 chain keep steps, G1 rejects 1, G2 rejects 3 (69f3ead −0.008, 57281f6 −0.010, b06b208) and G3 rejects 1;
  - gpuloop re-ran the table with the harness copy and got the same numbers.
- gpuloop's guards, written before the director round and kept as a reference only, not adopted. Their settings were chosen from September tests, and the gate now includes Oct 1–7 cells, so the damage would show there:
  - (1) reject a keep if any gate cell's |log(q50/last)| exceeds the line's largest past h-day move + 0.01;
  - (2) at the pick, no line may give more than 40% of the gain;
  - (3) the pick must beat each simpler ancestor by ≥ +0.005.
- Overlap between the two sets:
  - the director's G1 targets the same mechanism as gpuloop's (1), big median shifts, but checks whether the bets paid off. It also found why (1) is weak: the jump itself sets the line's "largest past move";
  - G3 is a single-line check like (2), but on loss, not gain;
  - G2 is new;
  - (3) has no counterpart.
- The Jul-Aug guard comes from v8 PREREG (iterate yes 12:07Z).

## Caveats (read before trusting the holdout)
- *gpuloop has already seen October, including the holdout weeks.* For the diagnosis (17:27Z, report-only), gpuloop scored all 16 chain models from v7 to b06b208 on full October (origins Oct 1–31). It looked at per-line and per-cell results, including the fastgpu B200 cells at origins Oct 17–21. So these were chosen after that look, and the holdout is only weak evidence:
  - running a healing round on b06b208;
  - restarting from 19a5148;
  - extending dev to Oct 15.
  November (the judging period) is the real test.
- Full-October skill is already known for both start points: v7 +0.149, 19a5148 +0.148. If the pick is 19a5148 or close to it, the holdout tells us little that is new.
- The director never saw October 16–31. But the inputs it got were chosen by gpuloop, who had: the failure signal, b06b208 as the model to explain, and the Oct 1–15 move rate.
- On the v8.1 dev data the locked gate alone already rejects b06b208 (−0.04 vs 19a5148). The guards are for the next regime change, not this one.
- The holdout is small (8 origins, 37 lines), so the luck check will be wide. A real gain may not show as significant.
- Researchers see the post-mortem in LESSONS.md (dev numbers only) and the Oct 1–15 move rate (0.27 in Sept → 0.45). They never see Oct 16–31 or any full-October number.

## Pick (filled in at 20:00Z, before the holdout; then this file is made read-only)
Written 2026-11-15 20:35Z by gpuloop, before the holdout runs.
- Candidates: 14 keeps on research/v81-a/-b/-c committed by 20:00Z (none late), plus v7 and 19a5148. All 16 were re-scored with the locked v8.1 harness (scores in scores.jsonl). All 16 pass the Jul-Aug bar and G1-G3 in pick form against v7.
- *Pick: 870891d* (pacsci1, research/v81-a, committed 19:43Z, 340 lines; forecaster sha256 01b182f73abfc335…).
  - Gate +0.2315. Jul-Aug +0.1615. Full dev +0.2173. 98% of resamples favour it.
  - For comparison, v7 scores gate +0.1600 and Jul-Aug +0.1221; 19a5148 scores gate +0.2168.
  - Its changes on 19a5148: source pace (7100b8c), then 4add042, then "the latest big step is the new level" (870891d).
- Runner-up: c9804cc (pacsci2), gate +0.2274, Jul-Aug +0.1649, 268 lines. It is more than 0.001 below, so the tie rule does not apply.
- Order check on Modal: 870891d passes. Shuffled and fresh runs change 0 of 2787 cells (max diff 1.8e-15). c9804cc, 19a5148 and v7 also pass.
- Holdout next: `score_heldout.py series_full.npz fa_870891d.py fa_v7.py`, once.

This record copy differs from the committed original only in that local file paths were removed.
