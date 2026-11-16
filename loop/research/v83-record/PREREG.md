# v8.3 pick: pre-registration

Written 2026-11-15 21:57Z (1:57 PM PT) by gpuloop, before the researchers started, after the owner's yes via iterate. It uses the same split and pick rule as v8.2. The rule was committed in gpuloop's lane repo before launch; this is a copy with internal paths removed.

## Split (harness: research/v82 1a970d5, not pushed; the code change is in harness-v83.patch, the same as v8.2's)
- Dev = all rows to Nov 6, the end of the pack. Dev origins = Jul 1 – Oct 29, every 2 days (61), so every target is on or before Nov 6.
- Gate (column "sept") = origins Sep 1 – Oct 29.
- *There is no holdout.* The v8.1 holdout weeks (origins Oct 16–30) were scored once for v8.1 and are now in dev. No unseen week remains. Any v8.2 result is dev-only evidence; November is the real test.

## Round
- Researchers: pacsci1 starts from its v8.2 near-miss b776439, which is 870891d plus "a run that stopped is a new level" (gate +0.0019 on 870891d). Its branch is research/v83-a. pacsci2 starts from its v8.2 near-miss e258c4a, which is c9804cc plus "a sibling trigger only from rare movers" (+0.0022 on c9804cc). Its branch is research/v83-b.
- Each researcher's baseline row is its near-miss. The keep rule compares against that row, so a stack of the near-miss and a new idea must clear +0.003 over the near-miss. The pick rule (below) compares against 870891d.
- Two researchers, because of memory (1.3 GB free at start).
- Keep rule unchanged from v8.1: the locked gate rule plus G1–G3 against the current best. The harness hash manifest is locked read-only outside the researchers' sandbox.
- The researchers stop at 23:00Z (3:00 PM PT), 60 minutes after the start.

## Pick at 23:00Z (3:00 PM PT)
1. Candidates: every commit on research/v83-a and -b logged as keep or keep-simpler, with a commit time on or before 23:00Z. Also 870891d, c9804cc and the two near-misses b776439 and e258c4a. gpuloop re-scores each one with the v8.2 harness, which is unchanged for v8.3.
2. A candidate is eligible only if all of these hold:
   - (a) Its July–August skill is at least +0.1221 (v7's score).
   - (b) It passes G1–G3 in pick form against v7, the same checks as v8.1.
   - (c) It passes the order check on Modal: shuffled order and a fresh process per origin, with every cell within 1e-9. This runs only for the would-be pick. If it fails, the next eligible candidate is checked.
3. To replace 870891d, a candidate must beat it on all three of these:
   - gate skill at least +0.003 higher;
   - full dev (Jul 1 – Oct 29) at most 0.005 lower;
   - at least 60% of 200 series resamples favour it on the gate.
4. Pick = the eligible candidate with the highest gate skill that passes step 3. If two are within 0.001 of each other, take the one with fewer lines. If no candidate passes step 3, the pick stays 870891d. Then the v8.1 challenger on main stays and no challenger branch is pushed.
5. If the pick changes, gpuloop rebuilds the challenger CSV for origin 2026-11-06 with research/challenger.py. The label is "v8.3, dev-only evidence (holdout weeks already used)". The CSV is validated the same way as v8.1 (same rows, keys, order and header as the submission, positive and ordered quantiles, byte-identical on rebuild). It is pushed as research/v83-challenger, and iterate is told.
6. The v7 submission files are not touched.

## Caveats
- gpuloop and both start points have already seen every week in dev, including Oct 16–30. A gain here is a fit to known weeks until November says otherwise.
- v8.2 tried one change per researcher and kept none. Each near-miss gained on every window its researcher measured, but each was under the bar alone.
- The record is pushed as research/v83-record, with no npz and no internal paths.
