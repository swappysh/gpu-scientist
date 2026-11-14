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


def fate(idea: dict) -> str:
    return "refuted" if idea.get("critic") == "refuted" else idea["status"]


def short(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def main(src: str, out: str) -> None:
    t = json.loads(open(src).read())
    rounds = t["rounds"]
    x = [r["round"] for r in rounds]
    fig, (top, bot) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.25]})

    top.plot(x, [r["skill_train"] for r in rounds], "-o", color="tab:blue", label="Jul-Sep skill")
    top.plot(x, [r["skill_val"] for r in rounds], "-s", color="tab:orange",
             label="September skill (the keep/kill gate)")
    f = t["final"]
    end = x[-1] + 0.6
    top.plot([end], [f["skill_heldout"]], "*", ms=14, color="black",
             label=f"October, scored once: {f['skill_heldout']:+.3f}")
    top.plot([end], [f["baseline_skill_heldout"]], "*", ms=12, color="lightgrey", mec="grey",
             label=f"starter on October: {f['baseline_skill_heldout']:+.3f}")
    top.set_ylabel("skill vs flat last value")
    top.legend(fontsize=8, loc="lower right")
    top.grid(alpha=0.3)
    top.set_title(f"Agent loop on the 37 scored series ({t['proposer']} proposer, "
                  f"{t['memory'].replace('Memory', '')} memory, {t['runner']} runner)")

    seen = set()
    for r in rounds:
        for j, idea in enumerate(r["ideas"]):
            k = fate(idea)
            m, c, lab = STYLE[k]
            y = idea["d_train"]
            bot.scatter([r["round"]], [y], marker=m, color=c, s=60, zorder=3,
                        label=None if k in seen else lab)
            seen.add(k)
            bot.annotate(f"{idea['param']}={short(idea['value'])}", (r["round"], y),
                         xytext=(6, -3 + 8 * (j - 1)), textcoords="offset points", fontsize=7, color=c)
    bot.axhline(0, color="black", lw=0.8)
    bot.set_ylabel("idea's change in Jul-Sep skill")
    bot.set_xlabel("round (0 = starter)")
    bot.legend(fontsize=8, loc="upper right")
    bot.grid(alpha=0.3)
    bot.set_xticks(x)
    bot.set_xlim(-0.4, end + 0.6)

    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
