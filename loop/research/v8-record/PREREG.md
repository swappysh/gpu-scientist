# v8 final pick: pre-registration

Written 2026-11-15T12:07Z (4:07 AM PT) by gpuloop, agreed with iterate. October has not been opened on any v8 model. The authoritative copy is ~/swappybot/lanes/pac-v8/PREREG.md, committed in the swappybot repo (the commit time is the timestamp). /tmp/pac-v8-shared/PREREG.md is a read copy for the researchers.

## Why
September (the keep gate) and July-August disagree. The cross-source changes raise September but lower July-August below the seed. The keep rule's Jul-Sep guard can't see this, because September is 54% of the Jul-Sep cells. The keep rule stays locked; this rule only picks the final among kept models.

## Provenance and limits
- Found by gpuloop (the agent running the harness) re-running July-August by hand. Neither the automated keep rule nor the director caught it. The rule was approved by iterate (an agent); the owner was not involved.
- October was already inspected for v1-v7, so it is not a fresh test for the project as a whole. The only clean test is November.

## Rule
1. Candidates: every commit on research/v8-a, -b and -c that the harness logged as keep or keep-simpler, plus any merge gpuloop builds at 9 AM PT. Each is re-scored by gpuloop with the locked harness and scorer on dev_series.npz.
2. July-August = dev origins before 2026-09-01, scored with core.score. September = the gate origins, as in results.tsv.
3. Guard: July-August skill ≥ +0.1221 (the seed, 18c491e, the v7 loop pick).
4. Pick: the highest September skill among candidates that pass the guard. If two are within 0.001 on September, take the one with fewer lines in forecaster_agent.py.
5. Comparison model: the highest September skill among all candidates, guard ignored.
6. Validity (added 2026-11-15 ~15:55Z at iterate's ask, before the pick; a check, not a ranking change): before its hash is written below, the pick must give the same forecasts when the dev origins are scored in shuffled order (one process, seed 0) and when each origin is scored in its own fresh process, compared with the harness's ascending order, every cell within 1e-9; a crash in either run is a fail (/tmp/gpl-lag/orderck_modal.py, run on Modal so each fresh-process origin gets its own container; same comparison as /tmp/gpl-lag/orderck.py). A model that fails is not eligible; take the next model that passes the guard and this check. Reason: a model that carries state across origins can behave differently on October, where score_heldout starts cold. The same check is run on the comparison model and reported.

## Order at 9-10 AM PT
1. 9 AM: score the candidates, then write the picked hash, the comparison hash, and their Jul-Aug / Sept / 1-day-lag numbers below. All of this happens before anything opens October.
2. 10 AM freeze: score_heldout.py once on the pick (with the luck check vs v7), and once on the comparison model.
3. Only the pick can become a submission, and only with the owner's yes and an October luck check vs v7 that excludes 0. The comparison model is reported only, to show whether the guard was right either way.

## Pick (filled in at 9 AM PT, before October; then this file is made read-only with chmod a-w)
- Filled 2026-11-15T17:01Z (9:01 AM PT), cutoff 17:00Z. October not opened on any v8 model. Candidates: 57 keep/keep-simpler commits on research/v8-a/-b/-c logged by 17:00Z; no merges built (rule 1 allows, not requires; pacsci1 had already tried b06b208 plus its ideas, 9f94897, discarded). The 20 early keeps not re-scored on Jul-Aug all have September at most +0.2846 in results.tsv, so none can be the pick or the comparison.
- order check (rule 6), pick: b06b208 PASS (Modal, 16:20Z; 43 dev origins, 2010 cells; shuffled: 0 cells changed, max diff 0; fresh process per origin: 0 cells changed, max diff 1.8e-15). Control 0eaf581 (module-level ISSUED list) FAILS: its shuffled run crashes.
- order check (rule 6), comparison: same model as the pick, same result.
- pick: b06b208 (pacsci2, research/v8-b; 331 lines). July-August +0.1554 (guard +0.1221: passes), September +0.3332. With other-source rows 1 day late: September +0.3295. Next below it that passes: 19a5148, +0.1574 / +0.3281 (not within 0.001).
- comparison: b06b208 (highest September of all candidates, guard ignored; the same model as the pick, so the October check is one run reported as both).
- Timing change (owner via iterate, 16:50Z, "why wait"): October is scored right after this file is locked, not at 10 AM PT. The 9:00 AM PT cutoff and everything above are unchanged.
- Correction 17:03Z, still before October: the candidate count first read 39 (a guess, not counted); counted from the three results.tsv it is 57. Nothing else changed.
