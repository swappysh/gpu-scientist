"""Chart a --trace log: skill per round (top) and every idea's fate (bottom).

    uv run --with matplotlib python scripts/plot_rounds.py results/loop_rounds.json results/loop_rounds.png
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

STYLE = {  # final status -> (marker, colour, label)
    "kept": ("o", "tab:green", "kept (wins on September)"),
    "killed": ("x", "grey", "killed"),
    "refuted": ("v", "tab:red", "kept, then refuted by the critic"),
}


MEMORY = {"PastDevMemory": "past.dev", "JsonlMemory": "local JSONL"}
NAMES = {"llm": "LLM", "rule": "rule-based", "modal": "Modal"}


def fate(idea: dict) -> str:
    return "refuted" if idea.get("critic") == "refuted" else idea["status"]


def short(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def main(src: str, out: str) -> None:
    t = json.loads(open(src).read())
    rounds = t["rounds"]
    x = [r["round"] for r in rounds]
    fig, (top, bot) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [1.3, 1]})

    top.plot(x, [r["skill_train"] for r in rounds], "-o", color="tab:blue", label="Jul-Sep skill")
    top.plot(x, [r["skill_val"] for r in rounds], "-s", color="tab:orange",
             label="September skill (the keep/kill gate)")
    f = t["final"]  # None while a run is still going (or crashed)
    end = x[-1] + 0.6
    if f:
        top.plot([end], [f["skill_heldout"]], "*", ms=14, color="black",
                 label=f"October, scored once: {f['skill_heldout']:+.3f}")
        top.plot([end], [f["baseline_skill_heldout"]], "*", ms=12, color="lightgrey", mec="grey",
                 label=f"starter on October: {f['baseline_skill_heldout']:+.3f}")
    top.set_ylabel("skill vs flat last value")
    top.legend(fontsize=8, loc="lower right")
    top.grid(alpha=0.3)
    top.set_title(f"Agent loop on the 37 scored series ({NAMES.get(t['proposer'], t['proposer'])} proposer, "
                  f"{MEMORY.get(t['memory'], t['memory'])} memory, {NAMES.get(t['runner'], t['runner'])} runner)")

    seen = set()
    for r in rounds:
        ideas = sorted(r["ideas"], key=lambda i: -i["d_train"])
        for j, idea in enumerate(ideas):
            k = fate(idea)
            m, c, lab = STYLE[k]
            bot.scatter([r["round"] - 0.35], [-j], marker=m, color=c, s=50, zorder=3,
                        label=None if k in seen else lab)
            seen.add(k)
            bot.text(r["round"] - 0.25, -j, f"{idea['param']}={short(idea['value'])}\n{idea['d_train']:+.3f}",
                     fontsize=7, color=c, va="center")
    depth = max((len(r["ideas"]) for r in rounds), default=1)
    bot.set_ylim(-depth + 0.4, 0.8)
    bot.set_yticks([])
    bot.set_ylabel("ideas each round\n(change in Jul-Sep skill)")
    bot.set_xlabel("round (0 = starter)")
    bot.legend(fontsize=8, loc="upper left", ncol=3, frameon=False)
    bot.set_xticks(x)
    bot.set_xlim(-0.5, end + 0.6)
    for xi in x:
        bot.axvline(xi - 0.45, color="lightgrey", lw=0.6)

    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
