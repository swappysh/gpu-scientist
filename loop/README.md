# pacific-hack

Self-improving GPU-price forecaster loop (Track 2, Pacific) on shared memory
(past.dev challenge) with parallel backtests (Modal prize). Prototype: the
backtest is fake (synthetic step-shaped prices) so the loop runs end to end;
jinx's real harness plugs in at one seam.

## Run

```bash
uv sync
uv run python -m pacific_hack.run                       # local JSONL memory, local runner
uv run python -m pacific_hack.run --runner modal        # same loop, backtests on Modal
PAST_API_KEY=... uv run python -m pacific_hack.run --memory past -n 2   # past.dev memory
uv run python -c "import sys,pytest; sys.exit(pytest.main(['-q','tests']))"   # tests, offline
```

Flags: `-n` rounds (default 3), `--batch` candidates per round (3), `--seed`,
`--ledger` (JSONL path), `--memory jsonl|past`, `--runner local|modal`,
`--proposer rule|llm` (default `rule`).

## The loop

Each round, three agents work through one shared `Memory` (`memory.py`):

1. **Proposer** reads the ledger as of the forecast date (2026-09-30) and writes a
   batch of one-parameter hypotheses. It skips ideas already tried and ranks params
   by their kept/killed history, so it learns from what the other agents wrote.
2. **Evaluator** backtests the whole batch in one `harness.backtest_batch` call
   (the Modal fan-out) and keeps a change only if it improves September skill
   (the last dev slice) without regressing Jul-Sep. October never decides
   anything; a run reports it once, at the end. Writes kept/killed.
3. **Critic** re-scores kept ideas on resampled series mixes, toggling only that
   idea's param on the current config, and writes refuted/corroborated from the
   September delta. Refuted ideas roll the config back.

Everything (tried / kept / killed / refuted, and why) is a ledger entry
(`ledger.py`). Entries per run stay in the tens, not raw price rows.

## LLM proposer (`--proposer llm`)

`llm_proposer.py` sits behind `Proposer.propose_batch`. It sends OpenAI
(Chat Completions, strict JSON schema output) the current config, a field schema
and the public ledger history (kept/killed/refuted/corroborated, reasons, Jul-Sep
numbers only; holdout entries are hidden by the read boundary and also filtered
out of the prompt). It returns up to `--batch` single-field changes, each with a
one-line hypothesis, written as `proposal` entries. Every candidate is validated
against the schema; unknown fields, out-of-range values, no-ops, ideas already in
the ledger and a second change to the same param are dropped. If the key is
missing, the call fails or nothing valid comes back, the rule-based proposer runs.

Env: `OPENAI_API_KEY` (read by the `openai` SDK), `PROPOSER_MODEL` (default `gpt-5-mini`).
Real config fields: pass `Proposer(..., field_schema=[{"name": ..., "type": "int"|"float"|"str",
"min": .., "max": ..} or {"name": ..., "type": "str", "choices": [...]}])`; the default
is `schema_from_config(ForecasterConfig())`.

## How past.dev sits in the loop

past.dev Memory API, base `https://api.past.dev/api/v1`, `Authorization: Bearer $PAST_API_KEY`
(`past_sk_` project key; hackathon credits: sign up at past.dev, pick 500,000 credits,
code `SFAIHACK500`, then create a key). Docs: https://past.dev/docs/memory-api/overview,
`/quickstart`, `/concepts`, `/sending-data`, `/authentication`, `/api-reference`.
`PastDevMemory` uses stdlib HTTP only and fails loudly without a key. **Not yet
verified against the live API** (no key was used building this); the first
`--memory past -n 1` run is the check.

| Need | How it maps |
| --- | --- |
| Write a fact | `POST /ingest`, one data point per ledger entry. `content` is an English sentence, full entry in `metadata.entry`. Ingestion is async; `GET /ingest/{id}` is polled before reads (`drain`). |
| No peeking at the future | `timestamp` = the entry's `market_date`; reads send `queryTimestamp` = the agent's forecast date, so later facts are not eligible. The JSONL backend filters `market_date <= as_of`. |
| Read boundary | October holdout scores are written with `audience: "holdout-scores"`, a `fixed` audience (`PUT /audiences/holdout-scores`) listing only `pacific-critic`. Proposer/evaluator read as `pacific-proposer` / `pacific-evaluator`, so they get kept/killed decisions and Jul-Sep numbers, never holdout numbers. |
| Revise a fact | A hypothesis is data point `ledger:hyp-<idea>`. The evaluator and then the critic re-send the same id (kept, then refuted), so past.dev supersedes it (`artifact.supersededAt` on recall). JSONL keeps the newest revision per `fact_id` on read and every revision in the file. |
| Several writers/readers | proposer, evaluator, critic and the loop all write; each reads under its own identity and uses facts written by the others. |

Memory vs other techniques: the ledger facts (hypotheses, decisions, verdicts,
metrics) live in past.dev; the config being tuned and the price series stay in
code/data files; no RAG. `PastDevMemory.entries()` has no list-all route to use,
so it runs a few broad recalls and dedupes by id; recall is semantic and capped
by `level` (`medium` = 16k tokens), so for long runs prefer targeted `search`.

## How Modal sits in the loop

The evaluator's batch (current config + every candidate) and the critic's
alternate-world checks go through `harness.backtest_batch(configs, runner, seed)`.
With `--runner modal`, `modal_app.run_batch` maps `backtest_remote.starmap(jobs)`
over Modal containers, one job per (config, seed). The Modal SDK reads its own
token (`modal token set` or `MODAL_TOKEN_ID/SECRET`); the code never touches
credentials. Each batch also writes a `note` to the ledger with
`runner`, `steps`, `seconds`, `steps_per_hour`, so running once with `--runner local`
and once with `--runner modal` against the same ledger gives the comparison.
A "step" = one forecast date walked for one config. `harness.session` keeps one
Modal app open for the whole loop. Not yet run on Modal (no token here).
With the fake backtest (milliseconds) local will win; the point of Modal is the
real harness (~20 dates x ~100 series per config).

## Plugging in the real harness

Replace `harness.backtest_seed(config: dict, seed: int) -> dict`. Return
`{"skill_train", "skill_val", "skill_heldout"}` (skill = 1 - model error / flat-baseline error;
add `"steps"` = forecast dates walked for the steps/hour metric). Both runners map
that one function, so Modal picks up the change with no edit to `modal_app.py`.
If the harness needs a different unit of work (one Modal call per forecast date),
change `run_local` / `modal_app.run_batch`; `backtest_batch(configs, runner, seed)`
and the agents stay as they are. Also swap `data.py` dates (`TRAIN_END`,
`HELDOUT_END`) for the real split, and `forecaster.ForecasterConfig` for the real
config; `Proposer`'s `MUTATIONS` list (or an LLM in `propose_batch`) generates changes.

## Known simplifications

- Each idea in a batch is scored against the pre-batch config; kept changes then
  apply together (distinct params per batch, so interactions are small but real).
- The default proposer is rule-based; the LLM proposer is opt-in (`--proposer llm`).
