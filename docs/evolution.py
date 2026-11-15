"""Timeline of how the forecasting framework changed on Sat Nov 14 (PT), from the commits on main.

Usage: uv run --no-project --with matplotlib python -I docs/evolution.py [OUT_PNG]
Writes OUT_PNG (default docs/evolution.png).
"""
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.xkcd(scale=1, length=100, randomness=2)
fig, ax = plt.subplots(figsize=(13, 6))
steps = [
 ("1:09 PM", "v0  skeleton", "3 agents share one memory:\nproposer -> evaluator -> critic\n(fake prices, rule proposer)"),
 ("1:25 PM", "v1  LLM proposer", "gpt-5-mini suggests changes,\nrules as fallback"),
 ("3:10 PM", "v2  real data", "backtest on the pack,\nscored like the starter;\nModal: 7.5k -> 101k steps/h"),
 ("3:37 PM", "v3  trend model", "+0.36 on AWS spot...\nbut Sunday doesn't\nscore AWS spot"),
 ("3:49 PM", "v4  leak fixed", "keep/kill on September,\nnot October; critic re-tests\nthe current config"),
 ("4:43 PM", "v5  right target", "tune on the 37 scored series;\nranges hold 76% of prices\n(starter 62%)"),
 ("4:54 PM", "v6  honest + traced", "bootstrap: score gain may be\nluck; every round logged\n(ideas, kept, killed)"),
 ("now", "v7  in progress", "8-round run on Modal,\nread-permission test,\ndemo of one agent\nreading another's notes"),
]
xs = range(len(steps))
ax.plot([0, len(steps)-1.5], [0, 0], color="k", lw=2.5)
ax.plot([len(steps)-1.5, len(steps)-1], [0, 0], color="k", lw=2.5, ls="--")
for i, (t, name, what) in enumerate(steps):
    up = i % 2 == 0
    y = 1 if up else -1
    col = "tab:red" if i in (3,) else ("tab:green" if i in (4, 5, 6) else ("grey" if i == 7 else "k"))
    ax.plot([i], [0], "o", ms=11, color=col)
    ax.plot([i, i], [0, y*0.35], color=col, lw=1.5)
    ax.text(i, y*0.42, name, ha="center", va="bottom" if up else "top", fontsize=12, color=col, weight="bold")
    ax.text(i, y*0.42 + (0.17 if up else -0.17), what, ha="center", va="bottom" if up else "top", fontsize=8.5)
    ax.text(i, -0.12 if up else 0.12, t, ha="center", va="top" if up else "bottom", fontsize=9, color="grey")
ax.text(3, -1.45, "oops: a big win\non the wrong series", ha="center", va="top", fontsize=10, color="tab:red")
ax.set_xlim(-0.7, len(steps)-0.3); ax.set_ylim(-1.85, 1.25)
ax.axis("off")
ax.set_title("HOW OUR FORECASTING FRAMEWORK EVOLVED (SAT NOV 14, PT)", fontsize=15)
fig.text(0.99, 0.01, "commits on gpu-scientist main: 96bc708 ... 52ff939", ha="right", fontsize=7, color="grey")
fig.tight_layout(); fig.savefig(sys.argv[1] if len(sys.argv) > 1 else "docs/evolution.png", dpi=150)
