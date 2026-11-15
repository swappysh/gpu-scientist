"""xkcd-style charts for the submission slides. Numbers come from loop/results/.

    uv run --no-project --with matplotlib python docs/slides/charts.py <series_daily.csv>

series_daily.csv is the starter's build of the data pack (only the price-steps panel uses it).
Writes PNGs to docs/slides/img/.
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "loop" / "results"
OUT = Path(__file__).with_name("img")
OUT.mkdir(exist_ok=True)
STEPS_SERIES = "gpurentalprices.neocloud_rate_card.A100_40GB.on_demand.median"
plt.xkcd(scale=1.0, length=100, randomness=2)
plt.rcParams.update({"font.size": 13, "axes.titlesize": 17})


def save(fig, name):
    fig.savefig(OUT / name, dpi=110, bbox_inches="tight")
    plt.close(fig)


def box(ax, x, y, w, h, text, fc, size=12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.2", fc=fc, ec="k", lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size)


def arrow(ax, a, b, text=None, color="k", ls="-", off=(0, 0.25)):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=2, color=color, linestyle=ls))
    if text:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], text, ha="center", fontsize=11, color=color)


def steps(series_csv):
    pts = [(date.fromisoformat(r["date"][:10]), float(r["value"])) for r in csv.DictReader(open(series_csv))
           if r["series_id"] == STEPS_SERIES and r["value"] not in ("", "nan")]
    d, v = zip(*sorted(pts))
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.step(d, v, where="post", color="k", lw=2.5)
    jumps = [i for i in range(1, len(v)) if v[i] != v[i - 1]]
    big = max(jumps, key=lambda i: abs(v[i] - v[i - 1]))
    ax.annotate("most days:\nsame as yesterday", xy=(d[len(d) // 5], v[len(d) // 5]),
                xytext=(d[len(d) // 8], max(v) + (max(v) - min(v)) * 0.25), arrowprops=dict(arrowstyle="->"))
    ax.annotate("then a jump", xy=(d[big], v[big]), xytext=(d[min(big + 8, len(d) - 1)], v[big] + (max(v) - min(v)) * 0.35),
                color="tab:red", arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax.set_ylim(min(v) - (max(v) - min(v)) * 0.3, max(v) + (max(v) - min(v)) * 0.6)
    ax.set_ylabel("$ per GPU-hour")
    ax.set_title("A100 40GB, posted on-demand price, 2026")
    ax.spines[["top", "right"]].set_visible(False)
    fig.autofmt_xdate()
    save(fig, "steps.png")


def agents(log):
    writes = [x for x in log if x["op"] == "write"]
    private = sum(1 for x in writes if x["layer"] != "public")
    seen = sum(x.get("layers", {}).get("holdout-scores", 0) for x in log if x["op"] == "read" and x["agent"] == "proposer")
    fig, ax = plt.subplots(figsize=(12, 7)); ax.set_xlim(0, 12); ax.set_ylim(0, 7.2); ax.axis("off")
    box(ax, 0.3, 4.6, 3.3, 1.9, "SUGGESTER\n(an LLM)\n'change one setting,\nhere is why'", "#fff2b3")
    box(ax, 4.35, 4.6, 3.3, 1.9, "TESTER\nre-forecasts every past\nday on Modal; keeps it\nif September improves", "#c9efc9")
    box(ax, 8.4, 4.6, 3.3, 1.9, "CHECKER\nre-scores on shuffled\nmixes of lines;\nundoes what breaks", "#f6c9c9")
    arrow(ax, (3.65, 5.55), (4.3, 5.55))
    arrow(ax, (7.7, 5.55), (8.35, 5.55))
    box(ax, 0.3, 0.4, 7.4, 1.6, "PUBLIC NOTES on past.dev\nideas, keep or kill, July-September scores", "#d6e6fb")
    box(ax, 8.0, 0.4, 3.7, 1.6, "PRIVATE NOTES\nOctober scores\n(checker only)", "#e3d3f5")
    arrow(ax, (1.2, 2.05), (1.2, 4.55), "reads", color="#1f5fbf", ls="--", off=(-0.5, 0))
    arrow(ax, (10.8, 2.05), (10.8, 4.55), "reads", color="#7d3cbf", ls="--", off=(0.5, 0))
    ax.text(6, 3.05, f"they never message each other. they all write in one notebook.\n"
                     f"last run: {len(writes)} notes, {private} of them private. the suggester saw {seen}.",
            ha="center", fontsize=12)
    save(fig, "agents.png")


def modal():
    fig, ax = plt.subplots(figsize=(12, 6.2)); ax.set_xlim(0, 12); ax.set_ylim(0, 6.2); ax.axis("off")
    box(ax, 0.2, 2.4, 2.6, 1.6, "a batch of\nideas", "#fff2b3", 13)
    for k in range(6):
        y = 0.35 + k * 0.95
        box(ax, 4.6, y, 2.4, 0.7, f"container {k + 1}", "#c9efc9", 11)
        arrow(ax, (2.85, 3.2), (4.55, y + 0.35))
        arrow(ax, (7.05, y + 0.35), (8.75, 3.2))
    box(ax, 8.8, 2.4, 3.0, 1.6, "scores go to\nthe notebook", "#d6e6fb", 13)
    ax.text(5.8, 6.05, "each container tests one idea: every July-September day,\n37 lines, 1, 3 and 7 days ahead",
            ha="center", fontsize=12)
    save(fig, "modal.png")


def gain():
    txt = (RES / "bootstrap_october_37.txt").read_text()
    rows = {}
    for who in ("model", "loop"):
        m = re.search(who + r" - starter: ([+-][\d.]+), 95% interval \[([+-][\d.]+), ([+-][\d.]+)\].*?(\d+) of 37", txt)
        rows[who] = [float(m.group(i)) for i in (1, 2, 3)] + [int(m.group(4))]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    labels = {"model": "our hand pick", "loop": "the agents' pick\n(submitted)"}
    for y, who in enumerate(("model", "loop")):
        g, lo, hi, n = rows[who]
        c = "tab:green" if lo > 0 else "tab:red"
        ax.plot([lo, hi], [y, y], color=c, lw=4)
        ax.plot([g], [y], "o", color=c, ms=13)
        verdict = "beats the starter" if lo > 0 else "no clear gain"
        ax.text(hi + 0.002, y, f"{verdict}: {g:+.3f}\n95% range {lo:+.3f} to {hi:+.3f}\nlower loss on {n} of 37 lines",
                va="center", fontsize=12, color=c)
    ax.axvline(0, color="grey", ls="--", lw=1.5)
    ax.text(0.0008, 1.42, "no gain", color="grey", fontsize=11)
    ax.set_yticks([0, 1]); ax.set_yticklabels([labels["model"], labels["loop"]])
    ax.set_ylim(-0.6, 1.6); ax.set_xlim(-0.015, 0.085)
    ax.set_xlabel("October skill gain over the starter (dot) and 95% range from 10,000 resamples")
    ax.spines[["top", "right", "left"]].set_visible(False)
    save(fig, "gain.png")


def rounds(r):
    rs = r["rounds"]
    x = [k["round"] for k in rs]
    sep = [k["skill_val"] for k in rs]
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(x, sep, "o-", lw=2.5, color="k")
    kept = [sum(i["status"] == "kept" for i in k["ideas"]) for k in rs]
    for k, n in zip(x[1:], kept[1:]):
        ax.text(k, 0.112, f"{n}/3", ha="center", fontsize=11, color="grey")
    ax.text(-0.35, 0.112, "kept:", fontsize=11, color="grey")
    win = max(range(1, len(sep)), key=lambda k: sep[k] - sep[k - 1])
    ax.annotate("the one big win:\nborrow from lines\nof the same kind", xy=(win, sep[win]), xytext=(win - 2.3, sep[win] + 0.004),
                color="tab:green", arrowprops=dict(arrowstyle="->", color="tab:green"))
    ax.axvspan(win + 0.5, x[-1] + 0.3, color="tab:red", alpha=0.07)
    ax.text(win + 1.2, 0.165, "the stall: 4 more 'keeps',\neach worth less than 0.001", color="tab:red", fontsize=12)
    ax.set_ylim(0.105, 0.2); ax.set_xlim(-0.5, x[-1] + 0.4)
    ax.set_xticks(x)
    ax.set_xlabel("round of the last run (3 ideas each)")
    ax.set_ylabel("September skill")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "rounds.png")


if __name__ == "__main__":
    lr = json.loads((RES / "loop_rounds.json").read_text())
    if len(sys.argv) > 1:
        steps(sys.argv[1])
    agents(lr["memory_log"])
    modal()
    gain()
    rounds(lr)
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
