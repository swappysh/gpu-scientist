# Demo script, Round 1 (about 3.5 minutes)

Spoken text is plain. Lines in [brackets] are what to show. Times are cumulative.

## 0:00 The question

[Title: GPU price scientist]

GPU rental prices move in steps. On most days, tomorrow's price is today's price. So "the price stays flat" is a hard forecast to beat.

We asked two things. Can a team of agents improve a price forecaster on its own, one change at a time, without peeking at the month it is judged on? And what will an H100 or an A100 be worth in two or three years?

## 0:30 How the loop works

[docs/loop.png]

The forecaster's middle guess is the last price. The real work is the band around it: how likely a seller is to reprice, and by how much.

Three agents share one lab notebook, which is a past.dev memory. A proposer suggests one change to the forecaster. An evaluator backtests it on Modal and keeps it only if September improves. A critic re-tests every kept change on reshuffled series and kills the ones that don't hold.

Every fact in the notebook carries a date and a list of who may read it. The proposer reads only facts as of September 30. October scores are hidden from it. October is scored once, at the end.

## 1:15 What the loop tried and kept

[TODO: round chart from gpuloop, loop/results/loop_rounds.png]

TODO: one sentence per round, from loop_rounds.json: what was tried, what was kept, what was killed.

In a sweep of 38 settings on July to September, one idea mattered most: borrowing repricing behavior from all 725 series in the pack. Doubling the band width cut September skill by two thirds.

## 1:50 Results, honestly

[Table from docs/FINDINGS.md]

The clear win is calibration. In October, which no decision saw, our band held the true price 76% of the time. The target is 80%. The starting forecaster managed 62%.

The skill gain is small, and it is not significant. We score +0.134 against +0.122. The 95% interval on that difference runs from slightly below zero to +0.04.

One thing we learned: a trend setting helps a lot on AWS spot, and does not help on posted rental prices. We think that is because AWS moves its spot price in small steps, while rental sellers jump rarely.

## 2:30 Resale in one line

[docs/resale.md, the view table]

On AWS spot, a six-year-old A100 rents for more than it did at age two. Rent holds up, so we forecast rent first. Our view: an H100 sells for about $4,700 in November 2028, 14% of its launch price, with a range of 8 to 22%.

## 2:50 One agent reads another agent's memory

[TODO: live command from gpuloop]

Here the proposer starts a new round. It asks the notebook what was tried. It gets back the evaluator's verdicts and the critic's refutations, all dated before September 30. It skips ideas that already failed. The October scores never come back.

## 3:20 Caveats

One month of held-out data on 37 series is small. The skill gain could be noise; the calibration gain is large. The resale view rests on two used-price prints. Everything rebuilds with one command from the public data pack.

Thank you.
