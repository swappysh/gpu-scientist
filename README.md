# gpu-scientist

An AI scientist that forecasts GPU rental prices (Pacific track, SF AI Research Hackathon, 14–15 Nov 2026), with a shared agent memory on past.dev.

Status: work in progress during the event.

## Idea
Posted GPU rental prices move in steps, so on most days tomorrow's price equals today's. The middle forecast is the last price; the low and high come from how often each kind of seller reprices, and by how much. A team of agents improves the forecaster one change at a time. A change counts only if it wins on September origins; October is scored once, at the end.

## Data
Pacific gpu-price-pack v0.1.1-handover (CC BY 4.0, data cutoff 6 Nov 2026). Not committed here; see `data/README.md` for how to fetch and verify it.
