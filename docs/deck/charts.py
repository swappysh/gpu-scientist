"""xkcd charts for the jury deck. Every number is copied from a repo file named next to it.

    VIRGIL_TTF=<Virgil.ttf> uv run --no-project --with matplotlib python docs/deck/charts.py

VIRGIL_TTF is optional: Excalidraw's Virgil font as TTF, so charts and diagrams share one hand.

Writes PNGs to docs/deck/img/. steps.png comes from the earlier deck script (docs/slides/charts.py, in git history before this deck replaced it); the diagram from docs/*.excalidraw.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, patheffects

OUT = Path(__file__).with_name("img")
OUT.mkdir(exist_ok=True)
# Poster palette: warm ink, one tomato red, off-white. Same four colours as the deck.
INK, RED, GREY, LIGHT = "#1C1410", "#D8000F", "#8A7F78", "#F5F2EF"
GREEN = INK  # no second accent: "good" is plain ink
plt.xkcd(scale=1.0, length=100, randomness=2)
PAPER = "#FFFFFF"
plt.rcParams["path.effects"] = [patheffects.withStroke(linewidth=4, foreground=PAPER)]
if os.environ.get("VIRGIL_TTF"):
    font_manager.fontManager.addfont(os.environ["VIRGIL_TTF"])
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=os.environ["VIRGIL_TTF"]).get_name()
plt.rcParams.update({"font.size": 21, "axes.titlesize": 22, "axes.facecolor": "none", "figure.facecolor": "none",
                     "savefig.transparent": True})


def save(fig, name):
    fig.savefig(OUT / name, dpi=130, bbox_inches="tight")
    plt.close(fig)


def v7_vs_starter():
    # docs/FINDINGS.md, table "37 scored series" (source loop/results/backtest.json, key "scored")
    months = ["Jul-Sep", "September\n(gate)", "October\n(held out)"]
    starter, v7 = [0.096, 0.127, 0.122], [0.157, 0.185, 0.149]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = range(len(months))
    ax.bar([i - 0.19 for i in x], starter, 0.36, color=LIGHT, ec=INK, label="starter")
    ax.bar([i + 0.19 for i in x], v7, 0.36, color=RED, ec=INK, label="v7 (our loop)")
    for i, (s, v) in enumerate(zip(starter, v7)):
        ax.text(i - 0.19, s + 0.006, f"+{s:.3f}", ha="center", fontsize=21)
        ax.text(i + 0.19, v + 0.006, f"+{v:.3f}", ha="center", fontsize=20, color=RED)
    ax.text(2.0, 0.195, "the month\nthat counts", ha="center", fontsize=19, color=RED)
    ax.set_xticks(list(x))
    ax.set_xticklabels(months)
    ax.set_ylim(0, 0.24)
    ax.set_yticks([])
    ax.set_ylabel("skill vs. 'price stays flat'")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper left", frameon=False)
    save(fig, "v7_vs_starter.png")


def october_loss():
    # loop/research/v8-record/PREREG.md (pick b06b208: Jul-Aug +0.1554, Sept +0.3332; v7 guard +0.1221);
    # docs/FINDINGS.md v8 section (v7 Sept +0.185, October +0.069 vs +0.149, gap -0.080, 95% -0.130 to -0.023)
    months = ["July-Aug", "September", "October\n(opened once)"]
    v7, pick = [0.122, 0.185, 0.149], [0.155, 0.333, 0.069]
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.plot(range(3), v7, "-o", color=INK, lw=3, ms=10, label="v7, submitted")
    ax.plot(range(3), pick, "-o", color=RED, lw=3, ms=10, label="v8 pick")
    ax.text(0.03, 0.163, "+0.155", color=RED, fontsize=19)
    ax.text(1.03, 0.333, "+0.333", color=RED, fontsize=19)
    ax.text(2.08, 0.062, "+0.069", color=RED, fontsize=19)
    ax.text(2.08, 0.150, "+0.149", color=INK, fontsize=19)
    ax.annotate("", xy=(1.9, 0.072), xytext=(1.9, 0.146), arrowprops=dict(arrowstyle="<->", color=RED, lw=2))
    ax.text(1.18, 0.02, "lost by 0.080\n95% range: 0.023 to 0.130", color=RED, fontsize=19)
    ax.axvspan(1.5, 2.5, color=LIGHT, lw=0)
    ax.set_xticks(range(3))
    ax.set_xticklabels(months)
    ax.set_xlim(-0.3, 2.5)
    ax.set_ylim(0, 0.37)
    ax.set_yticks([])
    ax.set_ylabel("skill")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper left", frameon=False)
    save(fig, "october_loss.png")


def heal_replay():
    # loop/research/heal/round_6-dry/trial.json: each check rejects the pick (b06b208), passes the incumbent (v7)
    # and rejects none of the 14 earlier keeps (chain_steps 14, chain_rejects empty)
    checks = ["a median leaves\nv7's own band", "one line gets\nmuch worse", "the last 15 days\nget worse"]
    cols = ["v8 pick", "v7", "14 earlier\nkeeps"]
    marks = [("no", "yes", "yes")] * 3
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    for r, row in enumerate(marks):
        y = 2 - r
        ax.text(-0.55, y, checks[r], ha="right", va="center", fontsize=21)
        for c, m in enumerate(row):
            color = RED if m == "no" else GREEN
            ax.text(c, y, "REJECT" if m == "no" else "pass", ha="center", va="center", fontsize=24 if m == "no" else 21,
                    color=color, fontweight="bold")
    for c, name in enumerate(cols):
        ax.text(c, 2.85, name, ha="center", va="center", fontsize=21)
    ax.plot([-2.5, 2.5], [2.45, 2.45], color=INK, lw=1.5)
    ax.text(0, -0.85, "new checks the loop wrote for itself after the loss", ha="center", fontsize=19, color=GREY)
    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(-1.1, 3.2)
    ax.axis("off")
    save(fig, "heal_replay.png")


def v81_vs_v8():
    # v8: docs/FINDINGS.md (-0.080, 95% -0.130 to -0.023). v8.1: holdout run once on 2026-11-15,
    # pick 870891d +0.1233 vs v7 +0.1092, gap +0.014, 95% -0.027 to +0.053 (loop/research/v81-record/HOLDOUT.md)
    # Different test windows: say so on each row so no one reads them as one test.
    rows = [("v8 pick\nOct 1-30", -0.080, -0.130, -0.023, RED), ("v8.1 pick (healed)\nOct 16-30", 0.014, -0.027, 0.053, INK)]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for i, (name, mid, lo, hi, color) in enumerate(rows):
        y = 1 - i
        ax.plot([lo, hi], [y, y], color=color, lw=4)
        ax.plot([lo, lo], [y - 0.08, y + 0.08], color=color, lw=3)
        ax.plot([hi, hi], [y - 0.08, y + 0.08], color=color, lw=3)
        ax.plot(mid, y, "o", color=color, ms=14)
        ax.text(-0.205, y, name, ha="right", va="center", fontsize=21)
        ax.text(mid + 0.01, y + 0.2, f"{mid:+.3f}", ha="center", fontsize=21, color=color)
    ax.axvline(0, color=GREY, lw=2, ls="--")
    ax.text(0, 1.55, "same as v7", ha="center", color=GREY, fontsize=19)
    ax.text(-0.19, -0.62, "<- worse than v7", color=RED, fontsize=19)
    ax.text(0.012, -0.62, "better than v7 ->", color=GREEN, fontsize=19)
    ax.set_xlim(-0.2, 0.1)
    ax.set_ylim(-0.75, 1.7)
    ax.axis("off")
    save(fig, "v81_vs_v8.png")


def v8_hits():
    # Share of v8 tries kept per director round, as in the earlier deck script docs/slides/charts.py (in git history; v8_hits there
    # reads the researcher logs). Copied counts; the assert ties them to README's 57 kept of 144.
    labels = ["before the\nfirst round", "after\nround 1", "after\nround 2", "after\nround 3", "after\nround 4"]
    k, n = [28, 15, 7, 5, 2], [92, 25, 11, 9, 7]
    assert sum(k) == 57 and sum(n) == 144
    rate = [a / b for a, b in zip(k, n)]
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.bar(range(5), rate, 0.6, color=[LIGHT] + [RED] * 4, ec=INK)
    for i, (a, b) in enumerate(zip(k, n)):
        ax.text(i, rate[i] + 0.025, f"{a} of {b}", ha="center", fontsize=21, color=INK)
    ax.set_xticks(range(5))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 0.78)
    ax.set_yticks([])
    ax.set_ylabel("share of tries kept")
    ax.spines[["top", "right", "left"]].set_visible(False)
    save(fig, "v8_hits.png")


if __name__ == "__main__":
    v7_vs_starter()
    october_loss()
    heal_replay()
    v81_vs_v8()
    v8_hits()
