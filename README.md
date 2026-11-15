# gpu-scientist

An AI scientist that forecasts GPU rental prices for the Pacific track at the SF AI Research Hackathon (14–15 Nov 2026). Three agents share an experiment ledger on past.dev and run their backtests on Modal.

![the loop](docs/loop.png)

## Idea
Posted GPU rental prices move in steps, so on most days tomorrow's price equals today's. The middle forecast is the last price. The low and high come from how often each kind of seller reprices, and by how much. A team of agents improves the forecaster one change at a time. A change counts only if it wins on September origins; October is scored once, at the end.

## Results
The submission uses the agent loop's pick. On the 37 series that are scored, its October skill is +0.149 vs +0.122 for the starter: a gain of +0.027, 95% interval +0.008 to +0.055. It also beats our earlier hand pick (+0.134) by +0.015 (+0.004 to +0.027). Its 10–90 band holds the truth 71% of the time, against 62% for the starter and a target of 80%. We picked it after seeing October, so that October number is optimistic. Details, the agent loop's rounds and what lives in past.dev are in [`loop/README.md`](loop/README.md).

Rebuild the results and the submission in one command:

```bash
cd loop && uv sync --group pack && ./reproduce.sh <unzipped gpu-price-pack-v0.1.1-handover dir>
```

## Data
Pacific gpu-price-pack v0.1.1-handover (CC BY 4.0, data cutoff 6 Nov 2026). Not committed here; see `data/README.md` for how to fetch and verify it.
