# v8.2 record (2026-11-15)

Two researchers ran 21:13–21:35Z on the v8.2 split. Dev runs to Nov 6, there are 61 origins from Jul 1 to Oct 29, and the gate is Sep 1 – Oct 29. No holdout was left, because the v8.1 holdout weeks were already scored, so every number here is dev-only evidence. pacsci1 started from 870891d (the v8.1 pick) and pacsci2 from c9804cc (the runner-up).

Result: each researcher tried one change, and both were discarded for gaining less than +0.003 on the gate. Under the pre-set rule, nothing beat 870891d, so the v8.1 challenger on main stays and there is no v8.2 challenger.

- PREREG.md: the pick rule, written and committed before the round started.
- pick.out and scores.jsonl: the pick run, with candidates re-scored on dev (gate, Jul-Aug, full dev, lines, guard failures) and the step-3 test against 870891d.
- results-a/b.tsv and LEARNED-a/b.md: each researcher's experiment log and notes.
- notebook-v82.tsv and LESSONS-v82.md: the round's rows from the shared notebook, and its new lessons.
- harness-v82.patch: the harness change from main to research/v82 (dates, scope, manifest coverage). The branch itself is not pushed.

*Data left out on purpose:* research/v82 also rebuilds harness/dev_series.npz to run to Nov 6. That file holds the Oct 16 – Nov 6 prices, so it is not in this repo. To rerun, build it from the full series with harness/build_dev.py after applying the patch.
