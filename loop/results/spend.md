# Spend

Everything on this page cost under $0.10.

- *Modal:* $0.0097 billed to the `pacific-hack-backtest` app across three runs, as of 2026-11-15 02:30 UTC (`modal billing report --start 2026-11-13`). The report lags by a few hours, so three later runs are not in it yet: `scored37-c` (died before round 1), `scored37-d` (stopped in round 2) and the 8-round `scored37-e` (01:14–02:12 UTC). Each is the same shape as the billed runs, at about $0.005 per 6 rounds, so the total should stay under $0.03. Each job is one config backtested on one CPU container.
- *OpenAI:* the LLM proposer makes one `gpt-5-mini` call per round, a few thousand tokens each: about 25 calls across all loop runs. This is an estimate from the call count, not a bill.
- *past.dev:* paid from the hackathon's free credits. Each run writes tens of facts and reads them back a few times per round.

Throughput, from the loop's own notes: a Modal batch of 6 configs ran at about 100,000 forecast-date steps per hour once the containers were warm, and about 7,500 per hour on a cold start.
