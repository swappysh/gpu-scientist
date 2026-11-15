# pacsci3: what I learned (angle: learn from the model's own past errors)

Jul-Aug / Sept skill (split.py; seed .122 / .185). Pick candidate **cfe3fb0 .151 / .278** (then 5b8925f .159 / .274); both order-free (0 cells differ shuffled or fresh-process).

## What worked (all held Jul-Aug above the seed)
- Busy lines (they change on most days, e.g. the H100 ask): reversion to the 14-day median plus a band of past residuals (9eb04c0, 3a46398 .155 / .218).
  The fit is pooled over the class's busy lines; one line's 60 days are too noisy (1398a10 .156 / .232).
- Move calibration: scale a step line's move chance by realized / predicted moves at its past origins with known outcomes.
  Two-way (7f6b84e .168 / .236); weekday-matched origins for h<7 (bd7e2e9 .164 / .244, 2cd12a6 .173 / .248);
  pooled over the source's scored lines in the class (b611e6d .172 / .252); h=7 grow-only because its windows overlap.
- Learned quantile levels: move q10/q90 to where the PITs of past step forecasts (per source+class+h) put them.
  Order-dependent 46e6885 .170 / .270; with a class-wide fallback for a new source (fastgpu), 0eaf581 .170 / .275.
  Two guards were essential: spread a no-move outcome over its atom (midpoint PITs: Jul-Aug .144, Jul-Sep −.005),
  and widen only (two-way levels narrowed hyperscaler bands). The gain is mostly rate-card h7 (upper tail exceeded 33%).
- PREREG rule 6: 46e6885 and 0eaf581 kept a module-level list of issued forecasts, so they are NOT eligible.
  5b8925f rebuilds each past origin's step forecast from the rows up to that origin and memoises only its 5 PITs (pure).
  That costs Jul-Aug .011 (.170 → .159), all afhubbard hyperscaler h7, because levels now learn from June's rebuilt forecasts.
  A cold October run starts the same way, so .159 is the honest number.
  Memoising whole past distributions (55k samples each) hit the 1.5 GB cap. Weekday-matched PITs for h<7 (cfe3fb0): Sept +.005, Jul-Aug −.008.
  After 9:00: match only h=1 (h3 spans several update days): .160 / .279, at least as good as both, order-free. With class+pricing: .174 / .282, Jul-Sep .234 (2/3 of its Jul-Aug gain is the H100 ask): the next base.
## What didn't
- Cross-line borrowing (sibling pool, follow, partner and gap, waves): Sept up to .239, but Jul-Aug .113-.118, below the seed: abandoned.
- Calibration variants, Sept vs about .25: recency-weighted .249, class-pooled .244, h7 two-way .245, no h7 calibration .242,
  just-moved .243, pooled move size .240. Per-line PIT levels .261 (vs .275): pool them.
- Busy lines: weekday residuals .238, own residual bias .231, learned levels on residual bands .268 (vs .270).
- Learning the q50 level too (unshrunk median): .2455 / Jul-Aug .168. Keep the 0.03-shrunk median.
- Trend-carry median .173; chained daily rate .251 (Jul-Aug .137); soft online weighting .125; class activity .239.
- Level groups split by pricing are identical. Non-overlapping PIT windows .262 / .156. On cfe3fb0 (Sept / Jul-Aug):
  recency-weighted PITs .251 / .156, adding unscored lines' PITs .187 / .152, a (source, h) fallback .268 / .156.
- The class+pricing step pool on 5b8925f (36ee30c) scores .173 / .277, lifting both halves (Jul-Sep +.008); discarded only by the exhausted-family bar (.006).
- Young busy line, one-day changes × √h (ea84783): Jul-Aug +.016 (.187) but Sept +0, so the keep rule discards it; on 5b8925f .157 / .275 (levels cover it).

## What to try next
- Nest q90 across horizons (h3 >= h1, h7 >= h3), after 9:00 on cfe3fb0: .160 / .279, but its Jul-Aug gain is mostly one line
  (the young H100 ask, h7; afhubbard h7 gets worse). With class+pricing: .170 / .282. Class+pricing alone: Sept gain broad (rate-card h7, 232 cells).
  Busy fits by class+pricing on top: .186 / .277; they change only the young H100 ask (12-14 cells per h): noise.
  That one line (Aug 6-10, a 56-62% fall) swings Jul-Aug by ~.01 and carries most Jul-Aug gains here: check it first.
- Remaining Sept loss: rate-card h7 upper tail exceeded 17-28% (the Sept climb), hyperscaler busy lower tail 14-20% at every h.
- Put the learned levels on top of pacsci1/2's same-pricing pool and old levels; both held in both halves.
