# pacsci2, v8.2: what I learned
Start point c9804cc (v8.1 runner-up, 192 lines). On this dev: gate +0.1943, full dev +0.1907, Jul-Aug +0.1649.
One experiment ran in this round. No keep, so c9804cc stays my best.
What I tried:
- e258c4a, discard. The sibling trigger fires only for siblings that move at most once a week.
  Gate +0.1964 (+0.0022), full dev +0.1934 (+0.0027), Jul-Aug +0.1714 (+0.0065), 99% of resamples gain.
  It missed the 0.003 bar, but it did not lose on any window I measured.
  Why I think it is true: a sibling that re-prices on 23% of days (afhubbard L40S rate card) gives no news
  about its followers. Rare movers do. The Jul-Aug gain is the gpr L40S line found in my v8.1 diagnostic.
What went wrong in the process:
- I lost about 8 minutes. My wait loop used `pgrep -f "run.py --baseline"`, which matched its own
  command line and never ended. Also, my own scoring script crashed ("worker closed the pipe")
  while split.py worked on the same file. I did not find out why.
What I would try next:
- Stack e258c4a with another small, true gain. Best candidate: 870891d's latest-big-step netting
  (an on-demand step over 4x the line's other steps is a new level). It gained on unused Oct 8-14 origins.
- Check e258c4a on the newest week (Oct 23-29) alone before building on it. I did not get that number.
- Ablations from v8.1 still stand: every part of c9804cc paid. Same-weekday windows paid least (+.0012),
  so they are the next thing to drop if a simpler model is wanted.
