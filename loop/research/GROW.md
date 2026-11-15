# The outer loop: pick, test on a fresh week, heal, grow

Written 2026-11-15. The researchers' inner loop (program.md, run.py) is unchanged. This is the order the outer loop runs each round. Each step is a script in `harness/`.

1. *Pick and test* (`walkforward.py round`). Pick on dev by the PREREG-v81 rule, then score the pick once on the next unseen week (rule: WALKFORWARD.md). A win makes the pick the incumbent.
2. *Heal* (`heal.py`, started by step 1). A lost week starts healing with no human: a post-mortem, new checks that only make the pick rule stricter, and a restart. Checks that fail their tests are dropped.
3. *Grow* (`proposals.py`).
   - `propose ROUND` gives the director the experiment rows, LESSONS.md, the walk-forward ledger and earlier proposals. The director writes 3 to 6 new inputs or model families as plain sentences, each with its evidence and a test. These are words, not code. Rows that name a locked part are dropped.
   - `program --into program.md` puts the open proposals at the end of the strategy section. A researcher who builds one tags the hypothesis "[P7] ...".
   - `track` counts each proposal's tries and keeps from results.tsv. A proposal is open, taken, kept, or dropped after 3 tries with no keep. The ledger is `proposals.tsv`.
4. *Roll.* The week joins dev and the next round starts.

## Locked
The scorer, the data split, the grid, the keep-rule numbers and the pick rule do not change. Healing may only add checks. Proposals change what researchers try, never how a try is judged.
