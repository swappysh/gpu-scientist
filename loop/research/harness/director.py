"""Outer loop (director, gpuloop only): measure the research process, log a meta round.

    research/harness/director.py <worktree> [<worktree> ...]                  # print the scoreboard
    research/harness/director.py <worktree> ... --log ROUND "<what changed and why>"

Reads every researcher's results.tsv. Per agent and in total: experiments,
keeps, keep rate, best September gain over the baseline, experiments and
gain per hour, all since the start and since the last meta round. --log
appends one row to research/meta.tsv (and the shared copy). It changes how
the swarm searches, never how it is judged: the harness, scorer, split and
keep rule are not touched here.
"""

from __future__ import annotations

import argparse
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from run import HEADER, RESEARCH, SHARED, clean

META = RESEARCH / "meta.tsv"
META_HEADER = ["round", "time_utc", "program_sha", "experiments", "keeps", "keep_rate",
               "best_sept_gain", "experiments_per_hour", "gain_per_hour", "per_agent", "changed"]
TRIES = ("keep", "keep-simpler", "discard", "crash", "leak")


def rows(worktree: Path) -> list[dict]:
    f = worktree / "loop/research/results.tsv"
    if not f.exists():
        return []
    return [dict(zip(HEADER, ln.split("\t"))) for ln in f.read_text().splitlines()[1:] if ln.strip()]


def commit_time(worktree: Path, commit: str) -> float | None:
    import subprocess

    r = subprocess.run(["git", "-C", str(worktree), "show", "-s", "--format=%ct", commit],
                       capture_output=True, text=True)
    return float(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def last_round() -> tuple[int, float]:
    if not META.exists():
        return 0, 0.0
    lines = META.read_text().splitlines()[1:]
    if not lines:
        return 0, 0.0
    last = dict(zip(META_HEADER, lines[-1].split("\t")))
    return int(last["round"]), datetime.fromisoformat(last["time_utc"]).timestamp()


def stats(worktrees: list[Path], since: float) -> dict:
    out, now = {}, time.time()
    for wt in worktrees:
        rs = rows(wt)
        base = next((r for r in rs if r["status"] in ("baseline", "fork")), None)
        start = commit_time(wt, base["commit"]) if base else None
        for r in rs:
            agent = r["agent"]
            a = out.setdefault(agent, {"n": 0, "k": 0, "n_new": 0, "k_new": 0, "best": 0.0,
                                       "start": start or now, "fams": {}})
            if r["status"] not in TRIES:
                continue
            t = commit_time(wt, r["commit"]) or now
            keep = r["status"].startswith("keep")
            a["n"] += 1
            a["k"] += keep
            if t >= since:
                a["n_new"] += 1
                a["k_new"] += keep
            fam = r["hypothesis"].split(":", 1)[0].strip().lower()
            f = a["fams"].setdefault(fam, [0, 0])
            f[0] += 1
            f[1] += keep
            if keep and base and r["sept"]:
                a["best"] = max(a["best"], float(r["sept"]) - float(base["sept"]))
    for a in out.values():
        hours = max((now - a["start"]) / 3600, 1e-6)
        a["rate"] = a["k"] / a["n"] if a["n"] else 0.0
        a["per_hour"], a["gain_per_hour"] = a["n"] / hours, a["best"] / hours
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("worktrees", nargs="+", type=Path)
    ap.add_argument("--log", nargs=2, metavar=("ROUND", "CHANGED"))
    a = ap.parse_args()
    rnd, since = last_round()
    st = stats(a.worktrees, since)
    for agent, s in sorted(st.items()):
        fams = ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(s["fams"].items()))
        print(f"{agent}: {s['n']} tries, {s['k']} keeps ({s['rate']:.0%}); since round {rnd}: "
              f"{s['n_new']} tries, {s['k_new']} keeps; best sept gain {s['best']:+.4f}; "
              f"{s['per_hour']:.1f} tries/h | families: {fams}")
    n, k = sum(s["n"] for s in st.values()), sum(s["k"] for s in st.values())
    best = max((s["best"] for s in st.values()), default=0.0)
    hours = max((time.time() - min((s["start"] for s in st.values()), default=time.time())) / 3600, 1e-6)
    print(f"total: {n} tries, {k} keeps ({k / n if n else 0:.0%}), best sept gain {best:+.4f}")
    if not a.log:
        return
    progs = b"".join((wt / "loop/research/program.md").read_bytes() for wt in a.worktrees)
    row = {"round": a.log[0], "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "program_sha": hashlib.sha256(progs).hexdigest()[:12], "experiments": n, "keeps": k,
           "keep_rate": f"{k / n if n else 0:.2f}", "best_sept_gain": f"{best:+.4f}",
           "experiments_per_hour": f"{n / hours:.1f}", "gain_per_hour": f"{best / hours:+.4f}",
           "per_agent": "; ".join(f"{g} {s['k']}/{s['n']} {s['best']:+.4f}" for g, s in sorted(st.items())),
           "changed": a.log[1]}
    for f in (META, SHARED.parent / "meta.tsv"):
        if not f.parent.exists():
            continue
        new = not f.exists()
        with open(f, "a") as fh:
            if new:
                fh.write("\t".join(META_HEADER) + "\n")
            fh.write("\t".join(clean(str(row[c])) for c in META_HEADER) + "\n")
    print("logged meta round", a.log[0])


if __name__ == "__main__":
    main()
