# v8.1 record (2026-11-15)

Three researchers ran 18:36–20:00Z on the v8.1 split (dev to Oct 15, guards G1–G3). Pick 870891d; holdout says no switch. v7 stays.

- PREREG.md: plan, keep and switch rules, the pick (filled before the holdout).
- HOLDOUT.md: the one holdout run (skill, coverage, 95% interval, 77% share above 0, lines better).
- scores.jsonl: the 16 pick candidates re-scored on dev (gate, Jul-Aug, full dev, lines, guard failures).
- orderck_v81.jsonl: order check on Modal for 19a5148, v7, 870891d, c9804cc (all pass).
- results-a/b/c.tsv, LEARNED-a/b/c.md: per-researcher experiment logs and notes (pacsci1/2/3).
- notebook.tsv, LESSONS.md, meta.tsv: shared notebook, lessons (v8 and v8.1, incl. the b06b208 post-mortem), director rounds.
- The pick's code is on branch research/v81-pick.
