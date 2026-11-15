# v8.2 pick: pre-registration

Written 2026-11-15 21:12Z (1:12 PM PT) by gpuloop, before the researchers started, after the owner's go via iterate. The rule was committed in gpuloop's lane repo before launch; this is a copy with internal paths removed.

## Split (harness: research/v82 1a970d5, not pushed; the code change is in harness-v82.patch)
- Dev = all rows to Nov 6, the end of the pack. Dev origins = Jul 1 – Oct 29, every 2 days (61), so every target is on or before Nov 6.
- Gate (column "sept") = origins Sep 1 – Oct 29.
- *There is no holdout.* The v8.1 holdout weeks (origins Oct 16–30) were scored once for v8.1 and are now in dev. No unseen week remains. Any v8.2 result is dev-only evidence; November is the real test.

## Round
- Researchers: pacsci1 starts from 870891d (the v8.1 pick), branch research/v82-a. pacsci2 starts from c9804cc (the v8.1 runner-up), branch research/v82-b. Two, not three, because of memory (1.9 GB free at start).
- Keep rule unchanged from v8.1: the locked gate rule plus G1–G3 against the current best. The harness hash manifest is locked read-only outside the researchers' sandbox.
- The researchers stop at 21:35Z (1:35 PM PT).

## Pick at 21:35Z (1:35 PM PT)
1. Candidates: every commit on research/v82-a and -b logged as keep or keep-simpler, with a commit time on or before 21:35Z. Also the incumbent 870891d and c9804cc. gpuloop re-scores each one with the v8.2 harness.
2. A candidate is eligible only if all of these hold:
   - (a) Its July–August skill is at least +0.1221 (v7's score).
   - (b) It passes G1–G3 in pick form against v7, the same checks as v8.1.
   - (c) It passes the order check on Modal: shuffled order and a fresh process per origin, with every cell within 1e-9. This runs only for the would-be pick. If it fails, the next eligible candidate is checked.
3. To replace 870891d, a candidate must beat it on all three of these:
   - gate skill at least +0.003 higher;
   - full dev (Jul 1 – Oct 29) at most 0.005 lower;
   - at least 60% of 200 series resamples favour it on the gate.
4. Pick = the eligible candidate with the highest gate skill that passes step 3. If two are within 0.001 of each other, take the one with fewer lines. If no candidate passes step 3, the pick stays 870891d. Then the v8.1 challenger on main stays and no research/v82-challenger is pushed.
5. If the pick changes, gpuloop rebuilds the challenger CSV for origin 2026-11-06 with research/challenger.py. The label is "v8.2, dev-only evidence (holdout weeks already used)". The CSV is validated the same way as v8.1 (same rows, keys, order and header as the submission, positive and ordered quantiles, byte-identical on rebuild). It is pushed as research/v82-challenger by 21:45Z (1:45 PM PT).
6. The v7 submission files are not touched.

## Caveats
- gpuloop and both start points have already seen every week in dev, including Oct 16–30. A gain here is a fit to known weeks until November says otherwise.
- The round is about 25 minutes long, so expect few experiments, and possibly no change.
