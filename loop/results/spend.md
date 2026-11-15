# Spend

Everything on this page cost under $0.10.

- *Modal:* $0.0097 billed to the `pacific-hack-backtest` app across three runs, as of 2026-11-15 00:50 UTC (`modal billing report --start 2026-11-13`). The report lags by a few hours, so the last loop run (00:06–00:44 UTC) is not in it yet. That run had the same shape as the one before it, so it should add about $0.005. Each job is one config backtested on one CPU container.
- *OpenAI:* the LLM proposer made about 10 calls to `gpt-5-mini` across the two loop runs, a few thousand tokens each. This is an estimate from the call count, not a bill.
- *past.dev:* paid from the hackathon's free credits. Each run writes tens of facts and reads them back a few times per round.

Throughput, from the loop's own notes: a Modal batch of 6 configs ran at about 100,000 forecast-date steps per hour once the containers were warm, and about 7,500 per hour on a cold start.
