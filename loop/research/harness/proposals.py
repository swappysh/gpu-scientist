"""Self-growing search (outer loop, gpuloop only): the director proposes, researchers pick, the loop tallies.

    research/harness/proposals.py propose ROUND --results R.tsv [R.tsv ...] [--lessons L] [--walkforward W] [--fake DIR]
    research/harness/proposals.py track --results R.tsv [R.tsv ...]
    research/harness/proposals.py program [--into program.md]   # the open list, at the end of the strategy section

The director reads the experiment rows, LESSONS.md and the walk-forward ledger and writes a
short list of new inputs or model families to try, each with a reason and a test. It writes
words, never code that runs: researchers still change forecaster_agent.py one idea at a time
and the locked keep rule judges every try. A researcher who works on proposal P7 puts "[P7]"
in the hypothesis; `track` counts each proposal's tries, keeps and best gate gain from
results.tsv, and marks it open, taken, kept or dropped (3 tries and no keep, as run.py's
exhausted rule). The scorer, split, keep rule and guards are not touched here.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
LEDGER = RESEARCH / "proposals.tsv"
COLS = ["id", "round", "kind", "proposal", "why", "test", "status", "tries", "keeps", "best_gain", "commits"]
KINDS = ("input", "family")
MAX_NEW = 6
DROP_AFTER = 3  # tries with no keep, as run.py's EXHAUSTED_AFTER
BUDGET_USD = 1.0
TAG = re.compile(r"\[P(\d+)\]")
LOCKED = re.compile(r"\b(scorer|pinball|keep rule|keep-rule|data split|train/val split|guards?|G[123])\b", re.I)
MARK = "### Director's proposals"

PROMPT = """You are the director of an AI research swarm that forecasts GPU rental prices (10/50/90% quantiles, 1, 3 and 7 days ahead, scored by pinball loss against "price stays flat"). A fresh session: you see only the files in this folder.

Read README.md, then results.tsv (every experiment: hypothesis, gate skill, status, lesson), LESSONS.md and, if present, walkforward.tsv (how each round's pick did on the next unseen week) and proposals.tsv (earlier proposals and how they fared).

Write out/proposals.tsv: a tab-separated file with header kind, proposal, why, test and 3 to 6 rows.
- kind is "input" (a new thing to compute from price history or the catalog: e.g. days since a sibling line moved) or "family" (a new model shape: e.g. a mixture of "no move" and "one step").
- proposal: one plain sentence a researcher can build in one experiment, from rows dated on or before the origin only.
- why: the evidence in these files, with the commit or the number.
- test: what result would keep it and what would drop it.
Prefer ideas no row has tried. Skip anything a lesson says is dead. Never propose a change to the scorer, the split, the keep rule or the checks: they are locked. Words only: write no code for the forecaster.
Write only out/proposals.tsv. Keep it brief."""


def read_tsv(f: Path) -> list[dict]:
    if not f.exists():
        return []
    return list(csv.DictReader(io.StringIO(f.read_text()), delimiter="\t"))


def write_ledger(rows: list[dict], f: Path = LEDGER) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, COLS, delimiter="\t", lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    f.write_text(buf.getvalue())


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def parse_director(text: str, start: int, rnd: int) -> tuple[list[dict], list[str]]:
    """The director's rows, numbered from `start`. Bad rows are dropped with a reason."""
    out, bad = [], []
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        kind = clean(r.get("kind", "")).lower()
        p = clean(r.get("proposal", ""))
        if kind not in KINDS or not p:
            bad.append(f"dropped row (kind {kind!r}, proposal {p[:40]!r}): needs kind input|family and a proposal")
            continue
        if LOCKED.search(p):
            bad.append(f"dropped row {p[:60]!r}: names a locked part")
            continue
        if len(out) == MAX_NEW:
            bad.append(f"dropped row {p[:60]!r}: over {MAX_NEW} proposals")
            continue
        out.append({"id": f"P{start + len(out)}", "round": rnd, "kind": kind, "proposal": p,
                    "why": clean(r.get("why", "")), "test": clean(r.get("test", "")), "status": "open",
                    "tries": 0, "keeps": 0, "best_gain": "", "commits": ""})
    return out, bad


def tally(ledger: list[dict], results: list[dict]) -> list[dict]:
    """Count tries and keeps per proposal from results.tsv rows tagged [P<n>]; set each status."""
    by = {p["id"]: dict(p, tries=0, keeps=0, best_gain="", commits="") for p in ledger}
    for r in results:
        st = r.get("status", "")
        if st not in ("keep", "keep-simpler", "discard", "crash", "leak"):
            continue
        for n in TAG.findall(r.get("hypothesis", "")):
            p = by.get(f"P{n}")
            if p is None:
                continue
            p["tries"] += 1
            p["commits"] = " ".join(x for x in (p["commits"], r["commit"]) if x)
            if st.startswith("keep"):
                p["keeps"] += 1
                g = re.search(r"sept ([+-]\d\.\d+) vs best", r.get("lesson", ""))
                if g and (p["best_gain"] == "" or float(g.group(1)) > float(p["best_gain"])):
                    p["best_gain"] = g.group(1)
    for p in by.values():
        p["status"] = ("kept" if p["keeps"] else "dropped" if p["tries"] >= DROP_AFTER
                       else "taken" if p["tries"] else "open")
    return list(by.values())


def program_text(ledger: list[dict]) -> str:
    """The open and taken proposals, for the strategy part of program.md."""
    live = [p for p in ledger if p["status"] in ("open", "taken")]
    if not live:
        return ""
    lines = [MARK + " (tag your hypothesis with the id, e.g. \"[P3] family: ...\")"]
    lines += [f"- {p['id']} ({p['kind']}, {p['status']}, {p['tries']} tries): {p['proposal']} "
              f"Why: {p['why']} Test: {p['test']}" for p in live]
    return "\n".join(lines) + "\n"


def into_program(program: Path, text: str) -> None:
    """Replace the proposals block at the end of program.md's strategy section (the last section)."""
    s = program.read_text()
    if MARK in s:
        s = s[:s.index(MARK)].rstrip("\n") + "\n"
    program.write_text(s + ("\n" + text if text else ""))


def run_director(packet: Path, out: Path, fake: Path | None) -> float:
    """One fresh director session in heal.py's sandbox, with only the packet. Returns the cost."""
    out.mkdir(parents=True, exist_ok=True)
    if fake:
        shutil.copy(fake / "proposals.tsv", out / "proposals.tsv")
        return 0.0
    sys.path.insert(0, str(HERE))
    import heal
    state = Path(tempfile.mkdtemp(prefix="grow-claude-"))
    (state / "projects").mkdir()
    shutil.copy(Path.home() / ".claude.json", state / "claude.json")
    (packet / "out").mkdir(exist_ok=True)
    cmd = heal.sandbox_args(packet, out, state, net=True) + [
        "claude", "-p", PROMPT, "--model", heal.MODEL, "--dangerously-skip-permissions",
        "--max-budget-usd", str(BUDGET_USD), "--output-format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    shutil.rmtree(state, ignore_errors=True)
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        res = {}
    return float(res.get("total_cost_usd", 0.0) or 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("round", type=int)
    p.add_argument("--results", type=Path, nargs="+", required=True)
    p.add_argument("--lessons", type=Path)
    p.add_argument("--walkforward", type=Path)
    p.add_argument("--fake", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--ledger", type=Path, default=LEDGER)
    t = sub.add_parser("track")
    t.add_argument("--results", type=Path, nargs="+", required=True)
    t.add_argument("--ledger", type=Path, default=LEDGER)
    g = sub.add_parser("program")
    g.add_argument("--ledger", type=Path, default=LEDGER)
    g.add_argument("--into", type=Path, help="program.md to update in place")
    a = ap.parse_args()
    ledger = read_tsv(a.ledger)

    if a.cmd == "program":
        if a.into:
            into_program(a.into, program_text(ledger))
        else:
            print(program_text(ledger), end="")
        return
    results = [r for f in a.results for r in read_tsv(f)]
    if a.cmd == "track":
        ledger = tally(ledger, results)
        write_ledger(ledger, a.ledger)
        for x in ledger:
            print(f"{x['id']} {x['status']:8} tries {x['tries']} keeps {x['keeps']} best {x['best_gain'] or '-'}: {x['proposal']}")
        return

    packet = Path(tempfile.mkdtemp(prefix="grow-packet-"))
    out = a.ledger.parent / "proposals" / f"round_{a.round}"
    buf = io.StringIO()
    w = csv.DictWriter(buf, ["agent", "commit", "hypothesis", "sept", "julsep", "status", "lesson"],
                       delimiter="\t", lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(results)
    (packet / "results.tsv").write_text(buf.getvalue())
    for src, name in ((a.lessons, "LESSONS.md"), (a.walkforward, "walkforward.tsv"), (a.ledger, "proposals.tsv")):
        if src and src.exists():
            shutil.copy(src, packet / name)
    (packet / "README.md").write_text(
        "results.tsv: one row per experiment (sept = gate skill, julsep = all dev origins).\n"
        "LESSONS.md: one line per notable keep or failure, oldest first.\n"
        "walkforward.tsv: each round's pick vs the incumbent on the next unseen week.\n"
        "proposals.tsv: earlier proposals with tries, keeps and status.\n")
    t0 = time.time()
    cost = run_director(packet, out, a.fake)
    shutil.rmtree(packet, ignore_errors=True)
    f = out / "proposals.tsv"
    if not f.exists():
        sys.exit("director wrote no proposals.tsv: nothing added")
    start = 1 + max((int(x["id"][1:]) for x in ledger), default=0)
    new, bad = parse_director(f.read_text(), start, a.round)
    for b in bad:
        print(b)
    write_ledger(ledger + new, a.ledger)
    (out / "log.txt").write_text(f"round {a.round}: {len(new)} proposals added, {len(bad)} dropped, "
                                 f"{time.time() - t0:.0f} s, cost ${cost:.2f}\n" + "\n".join(bad) + "\n")
    for x in new:
        print(f"{x['id']} {x['kind']}: {x['proposal']}")
    print(f"added {len(new)}, cost ${cost:.2f}")


if __name__ == "__main__":
    main()
