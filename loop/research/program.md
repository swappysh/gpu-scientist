# Research program: GPU price forecasts (v8)

ANGLE: (set per researcher, see the line below this header in your branch)

You are a researcher. Your job is to make `research/forecaster_agent.py` forecast GPU
rental prices better, one tested idea at a time, until 10:00 AM Pacific. Then you write
what you learned.

## The task

For each scored price series (37 lines, e.g. one provider's H100 on-demand price) and each
forecast origin, give the 10%, 50% and 90% quantiles of the price 1, 3 and 7 days later.
Score = pinball loss over those three quantiles, as a skill against "price stays where it
is": skill = 1 - your loss / flat loss, pooled over the 37 series. Higher is better.
All 725 series (scored or not) are in the history, so you can borrow from other lines.

## What moves GPU prices (what we know so far)

- Most lines are flat most days and then jump: a provider re-prices in one step. The flat
  forecast is hard to beat because most days nothing happens.
- Changes cluster: a line that changed recently tends to change again; some lines re-price
  often, some almost never.
- Providers follow each other: when one cuts an H100 price, others often follow within days.
- Generation launches (new GPU types) push older types down.
- Spot and marketplace lines are noisy; on-demand list prices are step-like.
- The seed (v7) uses recency-weighted past h-day changes, pooled with the same instrument
  class, a small AR(1) momentum term and a small drift. Sept skill +0.1853, Jul-Sep +0.1573.

## The rules

1. Edit only `research/forecaster_agent.py`. Everything in `research/harness/` and this file
   is fixed, read-only and hash-checked; the scorer refuses to run if they change.
2. `forecast(history, catalog_row, origin, h)` sees only rows dated on or before the origin
   (see the docstring at the top of the file). It may not open files, use the network or
   start processes; the harness blocks these at run time. Import every module at the top of
   the file. numpy and scikit-learn are installed. No new packages.
3. No hardcoded dates, day numbers or series ids. Use `history.origin` and the catalog.
4. A held-out month exists. You will never see it, and it is scored once, at the end, on the
   final version only. An idea that only fits September will fail there. Prefer ideas that
   say something true about the market.
5. Never print or write any key or token. Don't read files outside this worktree.
6. Writing (commits, lessons, the final note) is short and plain: short sentences, numbers
   with what they mean, no jargon.

## One experiment

```
cd loop
.venv/bin/python research/harness/notebook.py          # 1. read everyone's rows first
# 2. edit research/forecaster_agent.py
.venv/bin/python research/harness/run.py "<family>: <one-line hypothesis>"
.venv/bin/python research/harness/run.py --lesson <commit> "<what this taught you>"
```

- Step 1: the notebook lists every researcher's tries (yours and the two others').
  Skip an idea someone already tried, unless you have a real reason it would go
  differently this time; say that reason in the hypothesis.
- The hypothesis starts with a short family name (`steps:`, `band:`, `pool:`, `momentum:`,
  ...), then one line about the market or the forecast, e.g.
  `steps: lines that changed in the last 7 days are 3x more likely to change again`.
- run.py commits your edit, backtests Jul 1 - Sep 23 (about 15 s) and decides:
  - *keep*: September skill gains at least 0.003, Jul-Sep falls at most 0.005, and the
    gain holds on at least 60% of 200 resamples of the series. After 3 discards in a row
    in one family, that family is exhausted and needs 0.006.
  - *keep-simpler*: about the same score (within 0.003, losing at most 0.001) with at
    least 10% fewer code lines.
  - otherwise *discard*: the commit is reset and the file goes back to the best version.
  - a crash or a leak-review failure is logged and reset too.
- Every result, crashes included, goes in `research/results.tsv` and the shared notebook.
  The lesson is the most useful thing you write: what this result says about the market or
  the method, in one line, so the others don't repeat it.

## How to work

- Small, testable changes. One idea per experiment, so the result means something.
- Simpler is better. A gain of 0.003 that adds 40 lines of tuning is worth less than a
  gain of 0.003 from a real feature. Removing code that doesn't help is a good result.
- Don't grid-search constants. Tuning one number in small steps is overfitting the gate.
- Look at the data inside the forecaster only. To explore, write a short throwaway script
  that imports `harness.core`, loads the dev history (`core.load()`, which stops at Sep 30)
  and prints what you want to know. Keep exploration scripts out of git.
- Keep going. Don't stop to ask; nobody is watching live. When an idea fails, write the
  lesson and try the next one. Aim for 20+ experiments.

## At 10:00 AM Pacific (`TZ=America/Los_Angeles date`)

Stop experimenting. Write `research/LEARNED.md` (under 40 lines): what worked and by how
much, what didn't and why you think so, what you'd try next. Base it on results.tsv.
Commit it with `git commit -m "<agent>: what I learned" -- research/LEARNED.md`, then stop.
