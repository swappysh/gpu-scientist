"""One experiment: check, commit, score on Jul-Sep, keep or revert, log. Read-only.

    cd loop && .venv/bin/python research/harness/run.py "<family>: <one-line hypothesis>"
    cd loop && .venv/bin/python research/harness/run.py --lesson <commit> "<what you learned>"
    cd loop && .venv/bin/python research/harness/run.py --note "<one line for LESSONS.md>"
    cd loop && .venv/bin/python research/harness/run.py --adopt <branch>   (director's fork order)

Steps:
1. The harness files match the locked SHA-256 manifest, and the only edited
   tracked file is research/forecaster_agent.py.
2. Leak review of the file (leakcheck.py). A failure is logged as "leak" and reverted.
3. git commit, then backtest Jul 1 - Sep 23 origins in a locked worker.
4. Keep rule vs the current best (state/best.json):
     keep:   September skill gain >= MIN_GAIN (2x after 3 discards in a row in the
             same family: that family is exhausted), Jul-Sep drop <= MAX_JULSEP_DROP,
             and the gain is positive on >= MIN_SHARE of 200 series resamples.
     simpler: |September gain| < MIN_GAIN, gain >= -SIMPLER_SLACK, Jul-Sep drop <= MAX_JULSEP_DROP,
             and >= 10% fewer code lines than the best.
     else discard (git reset to the best); a crash is logged and reset too.
5. One row in research/results.tsv (and the shared notebook: past.dev scope research-v8).
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from harness import core, leakcheck  # noqa: E402

LOOP = RESEARCH.parent
AGENT_FILE = RESEARCH / "forecaster_agent.py"
REL_AGENT = "loop/research/forecaster_agent.py"
DIRECTOR_FILES = {"loop/research/program.md"}  # the director rewrites the strategy part; never committed here
TSV = RESEARCH / "results.tsv"
STATE = RESEARCH / "state"
BEST = STATE / "best.json"
HEADER = ["commit", "agent", "hypothesis", "sept", "julsep", "resample_share", "status", "lesson"]
# HARNESS_MANIFEST points at a locked copy kept outside the worktree; the repo copy is the fallback
MANIFESTS = [Path(os.environ.get("HARNESS_MANIFEST") or RESEARCH / "harness.sha256")]
# SHARED_DIR is the folder all researchers' worktrees share; one clone falls back to research/shared
SHARED_DIR = Path(os.environ.get("SHARED_DIR") or RESEARCH / "shared")
SHARED_DIR.mkdir(parents=True, exist_ok=True)
SHARED = SHARED_DIR / "notebook.tsv"  # the researchers' rows, read by notebook.py
LESSONS = SHARED.parent / "LESSONS.md"  # shared, append-only memory (research/LESSONS.md links here)
MIN_GAIN = 0.003
MAX_JULSEP_DROP = 0.005
MIN_SHARE = 0.60
SIMPLER_SLACK = 0.001
EXHAUSTED_AFTER = 3
SCOPE = "research-v8"


def sh(*args, check=True, raw=False) -> str:
    r = subprocess.run(args, cwd=LOOP.parent, capture_output=True, text=True)  # repo root: paths below are root-relative
    if check and r.returncode:
        sys.exit(f"{' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout if raw else r.stdout.strip()


def verify_manifest() -> None:
    m = next((p for p in MANIFESTS if p.exists()), None)
    if m is None:
        sys.exit("harness manifest missing: refusing to score")
    for line in m.read_text().splitlines():
        digest, name = line.split(None, 1)
        f = RESEARCH / "harness" / name.strip()
        if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            sys.exit(f"harness file {name.strip()} changed or missing: refusing to score")


def code_lines(text: str) -> int:
    n, in_doc = 0, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(('"""', "'''")):
            if not (len(s) > 3 and s.endswith(s[:3])):
                in_doc = not in_doc
            continue
        if in_doc or not s or s.startswith("#"):
            continue
        n += 1
    return n


def rows() -> list[dict]:
    if not TSV.exists():
        return []
    lines = TSV.read_text().splitlines()
    return [dict(zip(HEADER, ln.split("\t"))) for ln in lines[1:] if ln.strip()]


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def append_row(row: dict) -> None:
    new = not TSV.exists()
    with open(TSV, "a") as f:
        if new:
            f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(clean(str(row[k])) for k in HEADER) + "\n")
    if SHARED.parent.exists():
        with open(SHARED, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            if SHARED.stat().st_size == 0:
                f.write("\t".join(HEADER) + "\n")
            f.write("\t".join(clean(str(row[k])) for k in HEADER) + "\n")


def rewrite_lesson(commit: str, lesson: str) -> dict | None:
    rs, hit = rows(), None
    for r in rs:
        if r["commit"] == commit:
            r["lesson"], hit = lesson + " | " + r["lesson"], r
    if hit is None:
        return None
    TSV.write_text("\t".join(HEADER) + "\n" + "".join(
        "\t".join(clean(r[k]) for k in HEADER) + "\n" for r in rs))
    if SHARED.exists():
        with open(SHARED, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write("\t".join(clean(str(hit[k])) for k in HEADER) + "\n")
    return hit


def note(agent: str, text: str) -> None:
    """One line appended to the shared LESSONS.md, under a lock."""
    LESSONS.parent.mkdir(exist_ok=True)
    head = sh("git", "rev-parse", "--short", "HEAD")
    with open(LESSONS, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(f"- {time.strftime('%H:%M', time.gmtime())}Z {agent} @{head}: {clean(text)}\n")


def post(row: dict) -> None:
    """Same fact to past.dev (shared notebook). Never fails the experiment."""
    try:
        from pacific_hack.memory import PastDevMemory
        mem = PastDevMemory(scope=SCOPE).bound(row["agent"])
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        mem.append({
            "id": f"{row['agent']}-{row['commit']}", "fact_id": f"{row['agent']}-{row['commit']}",
            "kind": "experiment", "status": row["status"], "agent": row["agent"],
            "market_date": core.TRAIN_END, "timestamp": now, "idea_id": row["commit"],
            "change": None, "previous": None, "audience": None,
            "scores": {"sept": row["sept"], "julsep": row["julsep"], "resample_share": row["resample_share"]},
            "reason": f"hypothesis: {row['hypothesis']}. lesson: {row['lesson']}",
        })
    except Exception as exc:  # noqa: BLE001
        STATE.mkdir(exist_ok=True)
        with open(STATE / "pastdev_errors.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {row['commit']}: {core.describe_error(exc)}\n")


def family(hyp: str) -> str:
    return hyp.split(":", 1)[0].strip().lower() if ":" in hyp else "misc"


def exhausted(fam: str) -> bool:
    """3+ decided tries in a row in this family since its last keep (loop v2's rule)."""
    n = 0
    for r in reversed(rows()):
        if family(r["hypothesis"]) != fam:
            continue
        if r["status"].startswith("keep") or r["status"] == "baseline":
            break
        if r["status"] == "discard":
            n += 1
    return n >= EXHAUSTED_AFTER


def score_file(path: str) -> dict:
    return core.evaluate_dev(path)


def load_best() -> dict:
    """The best so far = HEAD's forecaster. Re-scored if the cache doesn't match it."""
    text = AGENT_FILE.read_text() if not sh("git", "status", "--porcelain", "--", REL_AGENT) else \
        sh("git", "show", f"HEAD:{REL_AGENT}", raw=True)
    sha = hashlib.sha256(text.encode()).hexdigest()
    if BEST.exists():
        b = json.loads(BEST.read_text())
        if b.get("sha") == sha:
            return b
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(text)
    r = score_file(f.name)
    os.unlink(f.name)
    b = {"sha": sha, "commit": sh("git", "rev-parse", "--short", "HEAD"), "lines": code_lines(text), **r}
    STATE.mkdir(exist_ok=True)
    BEST.write_text(json.dumps(b))
    return b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hypothesis", nargs="?")
    ap.add_argument("--lesson", nargs=2, metavar=("COMMIT", "TEXT"))
    ap.add_argument("--baseline", action="store_true", help="log HEAD's forecaster as the starting row")
    ap.add_argument("--note", metavar="TEXT", help="add one line to the shared LESSONS.md")
    ap.add_argument("--adopt", metavar="BRANCH", help="fork: continue from another researcher's best")
    a = ap.parse_args()
    agent = os.environ.get("PAC_AGENT", "gpuloop")
    verify_manifest()
    if a.lesson:
        hit = rewrite_lesson(*a.lesson)
        if hit is None:
            sys.exit(f"no row with commit {a.lesson[0]}")
        post(hit)
        print(f"lesson saved for {a.lesson[0]}")
        return
    if a.note:
        note(agent, a.note)
        print("noted in LESSONS.md")
        return
    if a.adopt:
        if sh("git", "status", "--porcelain", "--untracked-files=no", "--", REL_AGENT):
            sys.exit(f"{REL_AGENT} has uncommitted edits: finish or undo them first")
        sh("git", "reset", "-q", "--keep", a.adopt)
    if a.baseline or a.adopt:
        b = load_best()
        hyp = f"fork: adopt {a.adopt}" if a.adopt else "baseline: v7 loop pick"
        row = {"commit": b["commit"], "agent": agent, "hypothesis": hyp,
               "sept": f"{b['sept']:+.4f}", "julsep": f"{b['julsep']:+.4f}", "resample_share": "",
               "status": "fork" if a.adopt else "baseline", "lesson": "starting point"}
        append_row(row)
        post(row)
        print(row)
        return
    hyp = clean(a.hypothesis or "")
    if not hyp:
        sys.exit('give a one-line hypothesis: run.py "<family>: <hypothesis>"')
    dirty = [ln[3:] for ln in sh("git", "status", "--porcelain", "--untracked-files=no", raw=True).splitlines()]
    others = [p for p in dirty if p != REL_AGENT and p not in DIRECTOR_FILES]
    if others:
        sys.exit(f"only {REL_AGENT} may change; also changed: {others}")
    if REL_AGENT not in dirty:
        sys.exit(f"{REL_AGENT} has no change to test")
    best = load_best()
    fam = family(hyp)
    min_gain = MIN_GAIN * (2 if exhausted(fam) else 1)
    text = AGENT_FILE.read_text()
    problems = leakcheck.check(text)
    sh("git", "add", REL_AGENT)
    sh("git", "commit", "-q", "-m", f"{agent}: {hyp}"[:200], "--", REL_AGENT)
    commit = sh("git", "rev-parse", "--short", "HEAD")
    row = {"commit": commit, "agent": agent, "hypothesis": hyp, "sept": "", "julsep": "",
           "resample_share": ""}
    t0 = time.time()
    if problems:
        row.update(status="leak", lesson="leak review: " + "; ".join(problems))
    else:
        try:
            r = score_file(str(AGENT_FILE))
        except Exception as exc:  # noqa: BLE001
            row.update(status="crash", lesson=core.describe_error(exc))
        else:
            gain = r["sept"] - best["sept"]
            jdrop = best["julsep"] - r["julsep"]
            share = core.resample_share(r["sept_per_series"], best["sept_per_series"])
            lines = code_lines(text)
            row.update(sept=f"{r['sept']:+.4f}", julsep=f"{r['julsep']:+.4f}", resample_share=f"{share:.2f}")
            ok_j = jdrop <= MAX_JULSEP_DROP
            if gain >= min_gain and ok_j and share >= MIN_SHARE:
                status = "keep"
            elif abs(gain) < MIN_GAIN and gain >= -SIMPLER_SLACK and ok_j and lines <= 0.9 * best["lines"]:
                status = "keep-simpler"
            else:
                status = "discard"
            why = []
            if gain < min_gain:
                why.append(f"gain below {min_gain:.3f}" + (f" ({fam} exhausted)" if min_gain > MIN_GAIN else ""))
            if not ok_j:
                why.append(f"Jul-Sep fell {jdrop:.4f}")
            if share < MIN_SHARE:
                why.append(f"resamples {share:.2f} < {MIN_SHARE}")
            row.update(status=status, lesson=(
                f"sept {gain:+.4f} vs best {best['sept']:+.4f}; julsep {-jdrop:+.4f}; "
                f"coverage sept {r['coverage_sept']:.2f}; lines {lines} vs {best['lines']}"
                + ("" if status.startswith("keep") else "; " + ", ".join(why) if why else "")))
            if status.startswith("keep"):
                BEST.write_text(json.dumps({"sha": hashlib.sha256(text.encode()).hexdigest(),
                                            "commit": commit, "lines": lines, **r}))
    if not row["status"].startswith("keep"):
        sh("git", "reset", "-q", "--keep", "HEAD~1")
    append_row(row)
    post(row)
    print(f"{row['status'].upper()} {commit} sept {row['sept'] or '-'} julsep {row['julsep'] or '-'} "
          f"resamples {row['resample_share'] or '-'} ({time.time() - t0:.0f} s)\n  {row['lesson']}")
    print("Now add your lesson: research/harness/run.py --lesson " + commit + ' "<one line>"')


if __name__ == "__main__":
    main()
