"""Static dashboard for one loop run, built from its --trace JSON.

    uv run python -m pacific_hack.dashboard results/loop_rounds.json results/dashboard.html

The loop rewrites it after every round, next to the trace. One HTML file,
inline SVG, no scripts, no server.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

FATE = {"kept": "#1a7f37", "killed": "#888", "refuted": "#cf222e", "corroborated": "#1a7f37"}


def _chart(rounds: list[dict], final: dict | None) -> str:
    w, h, pad = 640, 240, 40
    xs = [r["round"] for r in rounds]
    series = [("Jul–Sep", "skill_train", "#0969da"), ("September (the gate)", "skill_val", "#bf8700")]
    ys = [r[k] for r in rounds for _, k, _ in series]
    if final:
        ys += [final["skill_heldout"], final["baseline_skill_heldout"]]
    lo, hi = min(ys) - 0.01, max(ys) + 0.01
    n = max(max(xs), 1) + (1 if final else 0)

    def px(x):
        return pad + (w - 2 * pad) * x / n

    def py(y):
        return h - pad + (2 * pad - h) * (y - lo) / (hi - lo)

    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px">']
    for t in range(5):
        y = lo + (hi - lo) * t / 4
        out.append(f'<line x1="{pad}" x2="{w - pad}" y1="{py(y):.1f}" y2="{py(y):.1f}" stroke="#eee"/>')
        out.append(f'<text x="{pad - 4}" y="{py(y) + 4:.1f}" font-size="10" text-anchor="end">{y:+.3f}</text>')
    for x in xs:
        out.append(f'<text x="{px(x):.1f}" y="{h - pad + 14}" font-size="10" text-anchor="middle">{x}</text>')
    out.append(f'<text x="{w / 2}" y="{h - 6}" font-size="11" text-anchor="middle">round</text>')
    for i, (label, key, colour) in enumerate(series):
        pts = " ".join(f"{px(r['round']):.1f},{py(r[key]):.1f}" for r in rounds)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2"/>')
        for r in rounds:
            out.append(f'<circle cx="{px(r["round"]):.1f}" cy="{py(r[key]):.1f}" r="3" fill="{colour}"/>')
        out.append(f'<text x="{pad + 6}" y="{14 + 14 * i}" font-size="11" fill="{colour}">{label}</text>')
    if final:
        x = px(n)
        for label, key, colour in (("October, loop's pick", "skill_heldout", "#cf222e"),
                                   ("October, starter", "baseline_skill_heldout", "#888")):
            y = py(final[key])
            out.append(f'<text x="{x:.1f}" y="{y + 5:.1f}" font-size="16" text-anchor="middle" fill="{colour}">★</text>')
            out.append(f'<text x="{x - 10:.1f}" y="{y + 4:.1f}" font-size="10" text-anchor="end" fill="{colour}">'
                       f'{label} {final[key]:+.3f}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _ideas(rounds: list[dict]) -> str:
    rows = []
    for r in rounds:
        for i in r["ideas"]:
            critic = i.get("critic", "")
            rows.append(
                f"<tr><td>{r['round']}</td><td>{i['idea_id']}</td><td><code>{i['param']}={i['value']}</code></td>"
                f'<td style="color:{FATE[i["status"]]}">{i["status"]}</td>'
                f'<td style="color:{FATE.get(critic, "#000")}">{critic or "–"}</td><td>{i["d_train"]:+.4f}</td></tr>'
            )
    head = "<tr><th>round</th><th>idea</th><th>change</th><th>evaluator</th><th>critic</th><th>Δ Jul–Sep</th></tr>"
    return f"<table>{head}{''.join(rows)}</table>" if rows else "<p>No ideas yet.</p>"


def _memory(log: list[dict]) -> str:
    if not log:
        return "<p>No memory log in this trace (runs before 2026-11-15 did not record one).</p>"
    writes: dict[tuple, int] = {}
    reads: dict[tuple, int] = {}
    for a in log:
        if a["op"] == "write":
            writes[(a["agent"], a["layer"])] = writes.get((a["agent"], a["layer"]), 0) + 1
        else:
            for author, n in a["authors"].items():
                reads[(a["agent"], author)] = reads.get((a["agent"], author), 0) + n
    wrows = "".join(f"<tr><td>{a}</td><td>{l}</td><td>{n}</td></tr>" for (a, l), n in sorted(writes.items()))
    rrows = "".join(
        f"<tr><td>{r}</td><td>{w}</td><td>{n}</td><td>{'another agent' if r != w else 'itself'}</td></tr>"
        for (r, w), n in sorted(reads.items())
    )
    lines = []
    for a in log:
        if a["op"] == "write":
            what = f"{a['kind']}/{a['status']}" + (f" {a['idea_id']}" if a.get("idea_id") else "")
            lines.append(f"<tr><td>{a['at'][11:19]}</td><td>{a['agent']}</td><td>write</td><td>{a['layer']}</td><td>{what}</td></tr>")
        else:
            whose = ", ".join(f"{n} by {w}" for w, n in sorted(a["authors"].items())) or "nothing"
            layers = ", ".join(sorted(a["layers"])) or "–"
            lines.append(f"<tr><td>{a['at'][11:19]}</td><td>{a['agent']}</td><td>read as of {a['as_of'] or 'now'}</td>"
                         f"<td>{layers}</td><td>{a['facts']} facts: {whose}</td></tr>")
    return (
        "<h3>Writes</h3><table><tr><th>agent</th><th>layer</th><th>facts</th></tr>" + wrows + "</table>"
        "<h3>Reads: whose data each agent read</h3>"
        "<table><tr><th>reader</th><th>author</th><th>facts read</th><th></th></tr>" + rrows + "</table>"
        f"<details><summary>Every read and write ({len(log)})</summary><table>"
        "<tr><th>UTC</th><th>agent</th><th>op</th><th>layer</th><th>what</th></tr>" + "".join(lines) + "</table></details>"
    )


def render(trace: dict) -> str:
    rounds, final = trace["rounds"], trace.get("final")
    ideas = [i for r in rounds for i in r["ideas"]]
    kept = sum(i["status"] == "kept" for i in ideas)
    refuted = sum(i.get("critic") == "refuted" for i in ideas)
    state = "finished" if final else f"running, round {rounds[-1]['round']} done"
    summary = (f"{len(rounds) - 1} rounds, {len(ideas)} ideas: {kept} kept, {len(ideas) - kept} killed, "
               f"{refuted} refuted by the critic. Jul–Sep skill {rounds[0]['skill_train']:+.3f} → {rounds[-1]['skill_train']:+.3f}.")
    if final:
        summary += (f" October, scored once at the end: {final['skill_heldout']:+.3f} vs the starter's "
                    f"{final['baseline_skill_heldout']:+.3f}.")
        if "coverage_heldout" in final:
            summary += f" The 10–90 band held the October truth {final['coverage_heldout']:.0%} of the time."
    setup = (f"proposer {trace['proposer']}, memory {trace['memory']}"
             + (f" (scope {trace['scope']})" if trace.get("scope") else "") + f", runner {trace['runner']}")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pacific loop</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px;color:#1f2328;background:#fff}}
table{{border-collapse:collapse;margin:8px 0 16px;font-size:13px}} td,th{{padding:3px 10px;border-bottom:1px solid #eee;text-align:left}}
code{{font-size:12px}} .muted{{color:#666}} details{{margin-bottom:24px}}
</style></head><body>
<h1>Pacific loop</h1>
<p class="muted">{html.escape(setup)}. {state}. Updated {html.escape(trace.get('updated', ''))} UTC.</p>
<p>{summary}</p>
<h2>Skill per round</h2>
<p class="muted">Ideas are kept on September skill (the gate) and Jul–Sep. October is scored once, after the last round.</p>
{_chart(rounds, final)}
<h2>Ideas</h2>
{_ideas(rounds)}
<h2>Memory</h2>
<p class="muted">The ledger the three agents share. Layers: <b>public</b> (every agent reads) and <b>holdout-scores</b> (October numbers, critic only). Reads are point-in-time: the proposer reads as of 2026-09-30.</p>
{_memory(trace.get('memory_log', []))}
</body></html>
"""


def write(trace_path: str | Path, out_path: str | Path) -> None:
    trace = json.loads(Path(trace_path).read_text())
    Path(out_path).write_text(render(trace))


if __name__ == "__main__":
    write(sys.argv[1], sys.argv[2])
