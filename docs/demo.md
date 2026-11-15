# Demo script, Round 1 (about 3.75 minutes)

Spoken text is plain. Lines in [brackets] are what to show. Times are cumulative.

## 0:00 The question

[Title: GPU price scientist]

On AWS spot, a six-year-old A100 rents for more than it did at age two.

GPU rental prices move in steps. On most days, tomorrow's price is today's price. So "the price stays flat" is a hard forecast to beat.

We asked two things. Can a team of agents improve a price forecaster on its own, one change at a time, without peeking at the month it is judged on? And what will an H100 or an A100 be worth in two or three years?

## 0:30 How the loop works

[docs/loop.png]

The forecaster's middle guess is the last price. The real work is the band around it: how likely a seller is to reprice, and by how much.

Three agents share one lab notebook, which is a past.dev memory. A proposer suggests one change to the forecaster. An evaluator backtests it on Modal and keeps it only if September improves. A critic re-tests every kept change on reshuffled series and kills the ones that don't hold.

Each fact in the notebook has a date. The proposer sees only facts dated September 30 or earlier, and the server enforces that cut. October numbers sit in a part of the notebook only the critic can read. October is scored once, at the end.

## 1:10 How we built it

[docs/evolution.png]

We built this in one afternoon, in eight versions. Two mistakes taught us the most. A trend model won big on AWS spot, which Sunday does not score. And at first the loop kept or killed changes using October, the month it is judged on. We fixed both before the final tuning.

## 1:30 What the loop tried and kept

[loop/results/loop_rounds.png]

This is the last live run: eight rounds, three ideas each. The loop kept 7 of 24. Almost all the September gain came from two of them: weighting recent repricing more, and borrowing repricing behavior from other series. Momentum weights, band changes and window changes were killed every time.

The run's final settings score +0.149 on October, against +0.122 for the start. That gap is not yet tested. We kept the submission we picked before this run, because switching now would mean choosing on October.

## 2:00 Results, honestly

[Table from docs/FINDINGS.md]

The clear win is calibration. In October, which no decision saw, on the 37 series Sunday scores, our band held the true price 76% of the time. The target is 80%. The starting forecaster managed 62%.

The skill gain is small, and it is not significant. We score +0.134 against +0.122. The 95% interval on that difference runs from slightly below zero to +0.04.

One thing we learned: a trend setting helps a lot on AWS spot, and does not help on posted rental prices. We think that is because AWS moves its spot price in small steps, while rental sellers jump rarely.

## 2:40 Resale in one line

[docs/resale.md, the view table]

Remember the six-year-old A100. Rent holds up, so we forecast rent first. Our view: an H100 sells for about $4,700 in November 2028, 14% of its launch price, with a range of 8 to 22%.

## 3:00 One agent reads another agent's memory

[Terminal: `cd loop && ./demo_read.sh`. Needs PAST_API_KEY. `./demo_read.sh <scope>` replays a finished run instead.]

Here the evaluator writes a verdict into the notebook. The proposer reads it back, with the earlier verdicts and the critic's refutations, all dated September 30 or earlier. The last lines are the raw server response to the proposer. It holds no October numbers. The critic reads the same notebook and does see them. In the last full run the agents wrote 110 facts, 32 of them critic-only, and the proposer got none of the 32.

## 3:30 Caveats

One month of held-out data on 37 series is small. The skill gain could be noise; the calibration gain is large. The memory boundary keeps honest code away from October; all three agents share one key, so it would not stop an agent that lies about who it is. The resale view rests on two used-price prints. Everything rebuilds with one command from the public data pack.

Thank you.
