# v8.3 record (2026-11-15)

Two researchers ran 21:58–23:00Z on the v8.2 split, which v8.3 keeps unchanged. Dev runs to Nov 6, there are 61 origins from Jul 1 to Oct 29, and the gate is Sep 1 – Oct 29. No holdout was left, because the v8.1 holdout weeks were already scored, so every number here is dev-only evidence. pacsci1 started from its v8.2 near-miss b776439 (870891d plus "a run that stopped is a new level") and pacsci2 from its near-miss e258c4a (c9804cc plus "a sibling trigger only from rare movers").

Result: the pick is cfeab06 (pacsci2). Its gate is .2318 against 870891d's .2058 (+.026), its full dev is .2247 against .2004 (+.024), and 99.5% of series resamples favour it on the gate. July–August is .1730 against v7's .1221. It passes G1–G3 against v7, and the order check left all 4008 cells unchanged. Eight keeps cleared the rule against 870891d; cfeab06 has the highest gate. pacsci1's best was 93f54d7 (gate +.0217, full dev +.0195, resamples 1.00). The challenger CSV for origin 11-06 is on branch research/v83-challenger, with the pick's code as loop/research/forecaster_agent_v83.py.

These gains come from weeks that every start point and gpuloop had already seen. November is the real test.

- PREREG.md: the pick rule, written and committed before the round started.
- pick.out and scores.jsonl: the pick run, with candidates re-scored on dev (gate, Jul-Aug, full dev, lines, guard failures) and the step-3 test against 870891d.
- orderck.jsonl: the order check (shuffled origins, and a fresh process per origin) for cfeab06 and for 13bba5c, the provisional pick before cfeab06 was kept.
- results-a/b.tsv and LEARNED-a/b.md: each researcher's experiment log and notes. pacsci2's 89a8ee3 (gate .2323) was logged as a discard, so it was not a candidate.
- notebook-v83.tsv and LESSONS-v83.md: the round's rows from the shared notebook, and its new lessons.
- harness-v83.patch: the harness change from main to research/v82, which v8.3 used unchanged (dates, scope, manifest coverage). The branch itself is not pushed.

*Data left out on purpose:* the v8.2/v8.3 harness rebuilds harness/dev_series.npz to run to Nov 6. That file holds the Oct 16 – Nov 6 prices, so it is not in this repo, and neither are the researcher branches that carry it. To rerun, build it from the full series with harness/build_dev.py after applying the patch.
