# pacsci2, v8.3: what I learned
Start e258c4a (gate +.1964, full +.1934). Best cfeab06: gate +.2318, full +.2247, Jul-Aug +.1730, Oct 23-29 +.2491
(870891d: +.2058 / +.2004 / +.1615 / +.1597). 5 keeps, 8 discards, 1 crash. Gains below are on the gate, over the previous keep.
- a6d6190 +.0148: 870891d's big-step netting stacked on my weekly-sibling trigger. They fix different lines, so the gains add.
- 3a44de9 +.0053, 1533115 +.0040: after rises on a rate card, open q10 toward the pre-rise price by h/7. A rate card is lower
  7 days after a rise 23% of the time (Sep 9%, Oct 31%). Neocloud spot rises are almost never taken back (1-3%).
- 13bba5c +.0033: falls are undone too (q90 toward the pre-fall price), plus pacsci1's "no median carry once a run stopped".
  Alone +.0030 and +.0003. Resamples .96. This is the broadest keep and the safer November pick.
- cfeab06 +.0080: q10 toward the 14-day low on every rate card, even after mixed steps. Only 2 lines carry it
  (fastgpu B200 +.0084, H200 +.0044) and 5 lines lose, so trust it less.
Failed: a run that starts after the latest big step (-.0029; a big rise can still be taken back); switching the take-back off
when the market's recent take-back rate is under 10% (-.0015); also opening the near tail, "the run goes on" (-.0057; wider
q90 costs on flat cells); q90 toward the 14-day high (gate +.0085 but G2 failed, Oct 23-29 -.0076: the late-Oct falls held). Dropping the rise
q10 rule given the 14-day low: -.0006 (they overlap). No q10 below last on neocloud spot after rises: +.0001 (already there).
Ablation: without my v8.2 weekly-sibling filter cfeab06 loses gate -.0011, full -.0018. It still pays.
Process: scoring scripts need `if __name__ == "__main__"` (this was v8.2's crash). np.unique opens files in the worker.
Next: check the rate-card take-back in November. If rises hold there, the q10 opening costs. Score cfeab06 without B200/H200.
