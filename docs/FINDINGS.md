# Findings

TODO (owner): one-sentence headline, written after Sunday's score.

## Question

Can a team of agents, changing a forecaster one setting at a time, beat the last posted price on GPU rental series 1, 3 and 7 days ahead, without ever seeing the month it is judged on?

Posted rental prices move in steps. On most days tomorrow's price equals today's, so the last price is a hard baseline to beat. Any gain has to come from the band around it: how likely a seller is to reprice, and by how much.

## Method

The forecaster's middle quantile is the last posted price. Its 0.1 and 0.9 quantiles come from how often and how far each kind of seller has repriced before. The starting configuration uses each series' own history only.

Three agents improve it through one shared memory on past.dev:

- a proposer reads past decisions and suggests one-setting changes;
- an evaluator backtests each batch in parallel on Modal and keeps a change only if it raises September skill without lowering July to September skill;
- a critic re-scores kept changes on resampled series mixes and rolls back the ones that don't hold.

October scores sit behind a read boundary. Only the critic can see them, and no decision uses them.

The final configuration differs from the start in three settings. It weights recent repricing more (14-day half-life). It borrows repricing behavior from all 725 series in the pack at half weight. And it widens the band by 20%. Configs: loop/submit_config.json. Rebuild: loop/reproduce.sh.

## Evaluation

The evaluation never looks ahead. Development uses origins from July to September 2026, the gate is September alone, and October is scored once at the end. The metric is the challenge's: pinball loss at the 0.1, 0.5 and 0.9 quantiles over each (series, origin, horizon) cell. Skill is 1 minus loss over the last-value loss, so 0 means no better than the last price.

The scored set is the 37 posted rental series that Sunday's truth file covers. AWS spot series are reported separately and are not scored on Sunday, because their November data arrives on 1 December.

## Results

On October, which no decision saw, the final configuration scores +0.134 skill on the 37 series. The starting configuration scores +0.122. Its interval coverage is 0.76 against a target of 0.8; the start's is 0.62.

| 37 scored series | Jul-Sep | September (gate) | October (held out) | Coverage, October |
|---|---|---|---|---|
| Starting config | +0.096 | +0.127 | +0.122 | 0.62 |
| Final config | +0.144 | +0.172 | +0.134 | 0.76 |

October has 1,522 cells; Jul-Sep has 2,010. Source: loop/results/backtest.json, key "scored".

The October gain is not significant. Resampling the 37 series 10,000 times puts the difference at +0.0125, with a 95% interval from −0.0097 to +0.0412. The model has the lower loss on 22 of the 37 series. Source: loop/results/bootstrap_october_37.txt, script loop/scripts/bootstrap_october37.py.

TODO (Sunday): skill on the frozen truth for 7, 9 and 13 November, pooled, mean, median and geometric mean, with coverage.

## What the loop learned across rounds

TODO (gpuloop): the round-by-round log and chart, from loop/results/loop_rounds.json and loop_rounds.png. For each round: what was proposed, kept, killed and refuted, and the September skill after it.

The sweep that picked the final settings tried 38 configurations on July to September (loop/results/sweep_julsep_37.txt). Two lessons from it:

- Borrowing repricing behavior from other series helped most. Half weight raised September skill from +0.127 to +0.162 on its own.
- Wider bands cost skill quickly. Scaling the band by 2 cut September skill to +0.041.

## AWS spot: trend works there and fails on posted prices

A trend setting wins on AWS spot and loses on posted prices. On 80 AWS spot series in October, a configuration that follows recent price momentum scores +0.36 skill against the starting configuration's +0.26. On the 37 posted rental series, the same trend model scores +0.101 against +0.122.

Our reading, which we have not tested directly: AWS spot is an administered price that AWS moves in frequent small steps, so a move tends to continue. Posted rate cards change rarely and in jumps, and a trend there mostly adds noise. The spot result is not scored on Sunday.

Sources: loop/results/backtest.json, key "aws_trend"; loop/results/october_37_three_models.txt, script loop/scripts/october37.py.

## Negative results

- Most of the September edge did not survive to October. The final configuration led the start by 0.045 in September and by 0.012 in October, a gap within noise. Choosing among 38 configurations on September made September look better than it was.
- Momentum hurts on posted prices. Adding it at 0.5 cut September skill from +0.127 to +0.034.
- A drift term added nothing (+0.125 against +0.127 in September).
- TODO (gpuloop): any LLM-proposer rounds that kept nothing.

## Rent and resale in 2028 and 2029

We expect an H100 to rent for about $3/hr and sell for about $4,700 in November 2028, 14% of its launch price (range 8% to 22%). The argument, ranges, sources and scripts are in docs/resale.md.

## Limits

- One month of October origins on 37 series is a small held-out set, and the October gain over the start is small.
- Most posted series have short histories: the pack's rental panels start in January 2026 or later, and many start in August.
- The resale view rests on two used-price prints and a handful of rate cards that span all of 2026.
- TODO (gpuloop): past.dev memory runs verified against the live API, or not.
