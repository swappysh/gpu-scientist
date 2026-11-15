"""Self-healing round (outer loop, gpuloop only): after the holdout, react to a lost pick in code.

    .venv/bin/python research/harness/heal.py --pick P --incumbent I --diff D --lo L --hi H [--parent Q]
        [--cells-cache DIR] [--round N] [--dry-run] [--full-npz F] [--fake-director DIR]

Input: the pick, the incumbent and the holdout result (pick minus incumbent skill, 95% interval).
If the pick did not lose (diff >= 0 and the interval does not sit below 0), it logs
"no heal needed" and stops. If it lost, it runs the round a human started by hand for v8.1:

  a. packet: the failure signal only (who lost, by how much), per-cell DEV rows for the
     incumbent, the pick and the pick's parent, every chain step's forecaster and commit
     message, and price-move rates by period. Nothing from the holdout but those 3 numbers.
  b. director: a fresh Claude session in a bwrap sandbox that sees only the packet. It writes
     a post-mortem (one LESSONS.md line) and proposes checks in checks.py.
  c. trial: each check runs in code (sandbox, no network). It must reject the pick against
     the incumbent, pass the incumbent against itself, and reject at most half of the chain's
     earlier keep steps. Checks that fail, crash or reject too much are dropped and logged.
  d. adopt: passing checks go to harness/healed/round_N.py, which guards.py loads into the
     keep rule and the pick rule. Checks only add rejections, so the locked keep rule never
     loosens. Then: one meta.tsv row "healing round N, trigger = holdout fail", dev extended to
     the last holdout target, and the researchers restarted from the pick's parent and the
     incumbent. --dry-run stops before d's writes and prints what it would do.

The scorer, split functions and keep-rule numbers are not touched. Extending dev changes
only the date constants in core.py, as the v8 -> v8.1 round did by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
REPO = RESEARCH.parents[1]
REL_AGENT = "loop/research/forecaster_agent.py"
HEAL_DIR = RESEARCH / "heal"
HEALED = HERE / "healed"
MODEL = "claude-opus-5-5"  # the researchers' and director's model
BUDGET_USD = 2.5  # one director session; the lane's cap is $3
MAX_CHAIN_REJECT = 0.5  # a check that rejects most past keeps would freeze research, not guard it
# RESEARCHER_SANDBOX: script that starts one researcher, called as `<script> <name> <worktree>`;
# unset means heal.py prints the launch commands instead of running them
SANDBOX = os.environ.get("RESEARCHER_SANDBOX")
TMUX_SESSION = os.environ.get("RESEARCHER_TMUX", "research")
RESEARCHERS = ("pacsci1", "pacsci2", "pacsci3")


def log(rnd_dir: Path | None, msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S', time.gmtime())}Z {msg}"
    print(line, flush=True)
    for d in (rnd_dir, HEAL_DIR):
        if d is not None:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "heal.log", "a") as f:
                f.write(line + "\n")


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def lost(diff: float, lo: float, hi: float) -> bool:
    """The pick lost if it scored below the incumbent, or the whole interval sits below 0."""
    return diff < 0 or hi < 0


# ---- a. packet -------------------------------------------------------------------------------

def chain(incumbent: str, pick: str) -> list[tuple[str, str, str]]:
    """(commit, parent, message) from the incumbent to the pick, oldest first, first-parent line."""
    out = git("log", "--reverse", "--first-parent", "--format=%h%x09%p%x09%s", f"{incumbent}..{pick}")
    steps = []
    for ln in out.splitlines():
        c, parents, msg = ln.split("\t", 2)
        steps.append((c, parents.split()[0], msg))
    return steps


def forecaster(commit: str) -> str:
    return git("show", f"{commit}:{REL_AGENT}")


def dev_cells(commit: str, text: str, cache: Path | None) -> list:
    """Per-cell dev rows for one forecaster: from the cache if gpuloop already scored it, else scored here."""
    if cache:
        for name in (f"dev_cells_{commit}.json", f"{commit}.json", f"out/dev_cells_{commit}.json"):
            f = cache / name
            if f.exists():
                d = json.loads(f.read_text())
                return d["rows"] if isinstance(d, dict) else d
    sys.path.insert(0, str(RESEARCH))
    from harness import core
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(text)
    try:
        return core.evaluate_dev(fh.name)["cells"]
    finally:
        os.unlink(fh.name)


def move_rates() -> str:
    """Share of days a scored line's price moved, mean move size, ups/downs, by source and period (dev rows only)."""
    from collections import defaultdict

    import numpy as np
    sys.path.insert(0, str(RESEARCH))
    from harness import core
    w = core.load()
    end = core.day(core.TRAIN_END)
    periods = {"before gate": (core.day(core.TRAIN_START), core.day(core.VAL_START) - 1),
               "gate, all but the last 15 days": (core.day(core.VAL_START), end - 15),
               "last 15 dev days": (end - 14, end)}
    agg = defaultdict(lambda: defaultdict(lambda: np.zeros(5)))
    for sid, d, v, sc in zip(w.sids, w.days, w.vals, w.scored):
        if not sc:
            continue
        for p, (a, b) in periods.items():
            idx = np.nonzero((d >= a) & (d <= b))[0]
            idx = idx[idx > 0]
            if len(idx) == 0:
                continue
            r = np.log(v[idx] / v[idx - 1])
            row = np.array([1, len(idx), (np.abs(r) > 1e-9).sum(), np.abs(r).sum(), (r > 1e-9).sum()])
            for key in (sid.split(".")[0], "all"):
                agg[key][p] += row
    out = [f"dev rows {core.TRAIN_START}..{core.TRAIN_END}; periods: " +
           "; ".join(f"{p} = {core.iso(a)}..{core.iso(b)}" for p, (a, b) in periods.items()),
           "source  period  lines  days  move_share  mean_abs_move  up/down"]
    for key in sorted(agg):
        for p in periods:
            n, rows_, mv, absr, up = agg[key][p]
            if rows_:
                out.append(f"{key}\t{p}\t{int(n)}\t{int(rows_)}\t{mv / rows_:.3f}\t{absr / max(mv, 1):.4f}\t{int(up)}/{int(mv - up)}")
    return "\n".join(out) + "\n"


def build_packet(packet: Path, a, steps, cache: Path | None, rnd_dir: Path) -> dict[str, list]:
    packet.mkdir(parents=True, exist_ok=True)
    (packet / "forecasters").mkdir(exist_ok=True)
    (packet / "cells").mkdir(exist_ok=True)
    (packet / "out").mkdir(exist_ok=True)  # mount point for the director's writable out dir
    (packet / "FAILURE.md").write_text(
        f"The pick {a.pick} lost to the incumbent {a.incumbent} on held-out data it never saw:\n"
        f"skill difference (pick minus incumbent) {a.diff:+.3f}, 95% interval [{a.lo:+.3f}, {a.hi:+.3f}].\n"
        f"The pick's parent (the step before it) is {a.parent}.\n"
        "That is all you get from the holdout. Everything else in this folder is dev data.\n")
    (packet / "chain.txt").write_text("".join(f"{c}\tparent {p}\t{m}\n" for c, p, m in steps))
    commits = [a.incumbent] + [c for c, _, _ in steps]
    cells = {}
    for c in commits:
        text = forecaster(c)
        (packet / "forecasters" / f"{c}.py").write_text(text)
        t0 = time.time()
        cells[c] = dev_cells(c, text, cache)
        (packet / "cells" / f"{c}.json").write_text(json.dumps(cells[c]))
        log(rnd_dir, f"packet: dev cells {c} ({len(cells[c])} cells, {time.time() - t0:.0f} s)")
    (packet / "moves.txt").write_text(move_rates())
    (packet / "README.md").write_text(
        "cells/<commit>.json: one row per scored dev cell: [series_id, origin (date ordinal), h, truth, "
        "last price at origin, [q10, q50, q90], pinball loss, flat (last-value) loss]. "
        "Skill on a set of cells = 1 - sum(loss) / sum(flat loss).\n"
        f"Key models: incumbent {a.incumbent}, pick {a.pick}, pick's parent {a.parent}. "
        "cells/ also holds every chain step.\n"
        "chain.txt: each step from the incumbent to the pick, its parent and its commit message.\n"
        "forecasters/<commit>.py: each step's forecaster.\n"
        "moves.txt: how often prices moved, by source and period.\n")
    return cells


# ---- b. director -----------------------------------------------------------------------------

PROMPT = """You are the director of an AI research swarm that forecasts GPU rental prices. A fresh session: you see only the files in this folder.

What happened: read FAILURE.md. The researchers' best model (the pick) passed every dev check, then lost to the old model (the incumbent) on held-out data. Your job is a post-mortem and new checks that would have stopped it, from dev data only. Read README.md, then chain.txt, the forecasters (diff the pick against its parent first) and the dev cells. Use python3 (numpy is installed) to find where the pick's loss rose: which cells, lines, horizons and origin weeks, and the mechanism in the code that caused it.

Write three files in ./out/:
1. out/postmortem.md: a short post-mortem in plain words (what changed, where it hurt with 2-4 numbers, the mechanism, why the dev keep rule passed it, what to do differently).
2. out/lesson.txt: ONE line for the shared LESSONS.md that the researchers read before each experiment.
3. out/checks.py: 1 to 4 new checks. Each is a top-level function named check_<name>(cand, ref) -> (ok: bool, why: str).
   - cand and ref are dicts keyed (series_id, origin, h) whose values are the cell rows from cells/*.json (row[5] is [q10, q50, q90], row[6] the loss, row[7] the flat loss).
   - The same function is used two ways: as a keep check (cand = a new experiment, ref = the current best) and as a pick check (cand = the final model, ref = the incumbent). ok=False rejects cand.
   - Checks can only reject more; they are added on top of a locked keep rule you cannot change.
   - Tie each check to the mechanism you found. Choose each threshold for a stated reason before you test it, and say the reason in the function's docstring.
   - Standard library and numpy only. No file or network access inside the checks.
   - At the end of the file set ADOPTED = [the check functions' names, as strings].
   Test them yourself on the cells: each must reject the pick against the incumbent and pass the incumbent against itself, and should pass most earlier chain steps (each step vs its parent). A test harness will rerun these tests in code and drop any check that fails them.

Write only inside ./out/. Keep it brief; finish when the three files exist."""


def sandbox_args(packet: Path, out: Path, state: Path, net: bool) -> list[str]:
    """bwrap: empty home and /tmp; only the packet (read-only), the out dir and this python come back in."""
    H = str(Path.home())
    venv = Path(sys.prefix)
    a = ["bwrap", "--dev-bind", "/", "/", "--unshare-pid", "--proc", "/proc", "--die-with-parent",
         "--tmpfs", "/tmp", "--tmpfs", "/var/tmp", "--tmpfs", H,
         "--ro-bind", f"{H}/.local", f"{H}/.local",
         "--ro-bind", str(venv), str(venv),
         "--ro-bind", str(packet), "/tmp/heal",
         "--bind", str(out), "/tmp/heal/out",
         "--unsetenv", "OPENAI_API_KEY", "--unsetenv", "MODAL_PROFILE", "--unsetenv", "PAST_API_KEY",
         "--unsetenv", "TMUX", "--unsetenv", "TMUX_PANE",
         "--setenv", "PATH", f"{venv}/bin:{H}/.local/bin:/usr/local/bin:/usr/bin:/bin",
         "--chdir", "/tmp/heal"]
    if net:
        a += ["--ro-bind", f"{H}/.claude/settings.json", f"{H}/.claude/settings.json",
              "--bind", f"{H}/.claude/.credentials.json", f"{H}/.claude/.credentials.json",
              "--bind", str(state / "projects"), f"{H}/.claude/projects",
              "--bind", str(state / "claude.json"), f"{H}/.claude.json"]
    else:
        a += ["--unshare-net"]
    return a


def run_director(packet: Path, out: Path, rnd_dir: Path, fake: Path | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    if fake:  # tests: copy a prepared out dir instead of calling the model
        for f in fake.iterdir():
            if f.is_file():
                shutil.copy(f, out / f.name)
        log(rnd_dir, f"director: fake ({fake})")
        return {"cost_usd": 0.0}
    state = Path(tempfile.mkdtemp(prefix="heal-claude-"))
    (state / "projects").mkdir()
    shutil.copy(Path.home() / ".claude.json", state / "claude.json")
    cmd = sandbox_args(packet, out, state, net=True) + [
        "claude", "-p", PROMPT, "--model", MODEL, "--dangerously-skip-permissions",
        "--max-budget-usd", str(BUDGET_USD), "--output-format", "json"]
    log(rnd_dir, f"director: fresh {MODEL} session in a sandbox with only the packet (budget ${BUDGET_USD})")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    shutil.rmtree(state, ignore_errors=True)
    (rnd_dir / "director.stderr").write_text(r.stderr[-4000:])
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        res = {"result": r.stdout[-2000:]}
    (rnd_dir / "director.result.txt").write_text(str(res.get("result", ""))[:4000])
    cost = float(res.get("total_cost_usd", res.get("cost_usd", 0.0)) or 0.0)
    log(rnd_dir, f"director: done in {time.time() - t0:.0f} s, exit {r.returncode}, cost ${cost:.2f}")
    return {"cost_usd": cost}


# ---- c. trial --------------------------------------------------------------------------------

def trial(checks_file: Path, cells_dir: Path, pick: str, incumbent: str, parent: str, steps: list) -> list[dict]:
    """Run each proposed check on the dev cells. Called inside the no-network sandbox (--trial)."""
    import importlib.util

    def load(c):
        return {(r[0], r[1], r[2]): r for r in json.loads((cells_dir / f"{c}.json").read_text())}

    spec = importlib.util.spec_from_file_location("proposed_checks", checks_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    names = list(getattr(mod, "ADOPTED", [])) or sorted(n for n in dir(mod) if n.startswith("check_"))
    P, I, Q = load(pick), load(incumbent), load(parent)
    earlier = [(c, p) for c, p, _ in steps if c != pick]
    models = {c: load(c) for c, _ in earlier} | {p: load(p) for _, p in earlier}
    res = []
    for n in names:
        fn = getattr(mod, n, None)
        row = {"check": n, "doc": (getattr(fn, "__doc__", "") or "").strip().split("\n")[0]}
        try:
            ok_pick, why_pick = fn(P, I)
            ok_inc, why_inc = fn(I, I)
            ok_keep, why_keep = fn(P, Q)
            ok_par, _ = fn(Q, I)
            rej = [c for c, p in earlier if not fn(models[c], models[p])[0]]
        except Exception as exc:  # noqa: BLE001
            row.update(passed=False, reason=f"crashed: {type(exc).__name__}: {exc}"[:300])
            res.append(row)
            continue
        share = len(rej) / len(earlier) if earlier else 0.0
        row.update(rejects_pick=not ok_pick, why_pick=str(why_pick), passes_incumbent=bool(ok_inc),
                   rejects_pick_as_keep=not ok_keep, why_keep=str(why_keep), passes_parent_as_pick=bool(ok_par),
                   chain_rejects=rej, chain_steps=len(earlier))
        fails = []
        if ok_pick:
            fails.append("does not reject the pick vs the incumbent")
        if not ok_inc:
            fails.append(f"rejects the incumbent vs itself ({why_inc})")
        if share > MAX_CHAIN_REJECT:
            fails.append(f"rejects {len(rej)} of {len(earlier)} earlier chain keeps")
        row.update(passed=not fails, reason="; ".join(fails) or "ok")
        res.append(row)
    return res


def run_trial(packet: Path, out: Path, a, steps, rnd_dir: Path, sandbox: bool) -> list[dict]:
    args = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--trial", str(out / "checks.py"),
            str(packet / "cells"), a.pick, a.incumbent, a.parent, str(packet / "chain.txt")]
    if sandbox:
        args = sandbox_args(packet, out, Path("/nonexistent"), net=False) + \
            ["--ro-bind", str(HERE), str(HERE)] + \
            [args[0], "-I", "-B", str(Path(__file__).resolve()), "--trial", "/tmp/heal/out/checks.py",
             "/tmp/heal/cells", a.pick, a.incumbent, a.parent, "/tmp/heal/chain.txt"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=900)
    if r.returncode:
        log(rnd_dir, f"trial: checks.py failed to load: {r.stderr.strip()[-300:]}")
        return []
    return json.loads(r.stdout)


# ---- d. adopt --------------------------------------------------------------------------------

def adopted_file(rnd: int, checks_text: str, names: list[str], a) -> str:
    head = (f'"""Healing round {rnd} (heal.py, {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ}): checks a fresh director proposed after\n'
            f"pick {a.pick} lost to incumbent {a.incumbent} on the holdout ({a.diff:+.3f}, 95% [{a.lo:+.3f}, {a.hi:+.3f}]).\n"
            f"Adopted after the trial (each rejects the pick, passes the incumbent): {', '.join(names)}. Read-only.\n"
            '"""\n\n')
    body = re.sub(r"(?m)^ADOPTED\s*=.*$", "", checks_text).rstrip()
    return head + body + f"\n\nADOPTED = {names!r}\n"


def extend_dev_plan(full_npz: str | None) -> tuple[str, list[str]]:
    """New dev end = the last holdout target. Only the date constants in core.py move."""
    sys.path.insert(0, str(RESEARCH))
    from harness import core
    new_end = core.PACK_END
    nxt = core.iso(core.day(new_end) + 1)
    cmds = [f"core.py: TRAIN_END {core.TRAIN_END} -> {new_end}; HELDOUT_START {core.HELDOUT_START} -> {nxt} "
            f"(HELDOUT_END, PACK_END wait for new data)",
            f"build_dev.py {full_npz or '<private full build>'} {core.DEV_NPZ}"]
    return new_end, cmds


def extend_dev(full_npz: str, rnd_dir: Path) -> None:
    sys.path.insert(0, str(RESEARCH))
    from harness import core
    f = HERE / "core.py"
    src = f.read_text()
    old = f'TRAIN_START, TRAIN_END, VAL_START = "{core.TRAIN_START}", "{core.TRAIN_END}", "{core.VAL_START}"'
    new = f'TRAIN_START, TRAIN_END, VAL_START = "{core.TRAIN_START}", "{core.PACK_END}", "{core.VAL_START}"'
    old2 = f'HELDOUT_START, HELDOUT_END, PACK_END = "{core.HELDOUT_START}"'
    new2 = f'HELDOUT_START, HELDOUT_END, PACK_END = "{core.iso(core.day(core.PACK_END) + 1)}"'
    if src.count(old) != 1 or src.count(old2) != 1:
        sys.exit("core.py date constants not in the expected form: extend dev by hand")
    f.write_text(src.replace(old, new).replace(old2, new2))
    subprocess.run([sys.executable, str(HERE / "build_dev.py"), full_npz, str(core.DEV_NPZ)], cwd=HERE, check=True)
    log(rnd_dir, f"adopt: dev extended to {core.PACK_END}")


def restart_plan(rnd: int, a) -> list[tuple[str, str, str, str]]:
    """(researcher, start commit, branch, worktree): two from the pick's parent, one from the incumbent (as v8.1)."""
    starts = (a.parent, a.parent, a.incumbent)
    return [(who, c, f"research/heal{rnd}-{'abc'[i]}", str(REPO.parent / f"{REPO.name}-heal{rnd}-{'abc'[i]}"))
            for i, (who, c) in enumerate(zip(RESEARCHERS, starts))]


def launch_cmd(who: str, wt: str) -> list[str]:
    return ["tmux", "new-window", "-d", "-t", f"{TMUX_SESSION}:", "-n", who, str(SANDBOX or "$RESEARCHER_SANDBOX"), who, wt]


def restart(plan, rnd_dir: Path) -> None:
    for who, c, br, wt in plan:
        if subprocess.run(["tmux", "list-windows", "-t", TMUX_SESSION, "-F", "#W"], capture_output=True,
                          text=True).stdout.split().count(who):
            log(rnd_dir, f"restart: window {who} still exists; not started (close it, then rerun with --restart-only)")
            continue
        git("worktree", "add", wt, "-b", br, "HEAD")
        subprocess.run(["git", "-C", wt, "checkout", c, "--", REL_AGENT], check=True)
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"heal round start point: {c} forecaster", "--", REL_AGENT])
        if not SANDBOX:
            log(rnd_dir, f"restart: {who} ready on {br} from {c} in {wt}; RESEARCHER_SANDBOX unset, start it with: "
                         + " ".join(launch_cmd(who, wt)))
            continue
        subprocess.run(launch_cmd(who, wt), check=True)
        log(rnd_dir, f"restart: {who} on {br} from {c} in {wt}")


def meta_row(rnd: int, changed: str) -> dict:
    from director import META_HEADER
    row = dict.fromkeys(META_HEADER, "-")
    row.update(round=str(rnd), time_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), changed=changed)
    return row


def write_meta(row: dict) -> None:
    from director import META, META_HEADER
    from run import SHARED, clean
    for f in (META, SHARED.parent / "meta.tsv"):
        if not f.parent.exists():
            continue
        new = not f.exists()
        with open(f, "a") as fh:
            if new:
                fh.write("\t".join(META_HEADER) + "\n")
            fh.write("\t".join(clean(str(row[c])) for c in META_HEADER) + "\n")


def rebuild_manifest() -> None:
    """Rehash every file the manifest lists, plus the healed checks (the run is over; researchers restart on these)."""
    import hashlib
    from run import MANIFESTS
    MANIFEST = MANIFESTS[0]
    if not MANIFEST.exists():
        return
    names = [ln.split(None, 1)[1].strip() for ln in MANIFEST.read_text().splitlines() if ln.strip()]
    names += [str(f.relative_to(HERE)) for f in sorted(HEALED.glob("round_*.py")) if str(f.relative_to(HERE)) not in names]
    MANIFEST.chmod(0o644)
    MANIFEST.write_text("".join(f"{hashlib.sha256((HERE / n).read_bytes()).hexdigest()}  {n}\n" for n in names))
    MANIFEST.chmod(0o444)


def commit_harness(rnd: int, msg: str) -> None:
    """The restart branches from HEAD, so the adopted checks and the dev extension go into a commit first."""
    paths = [str(p.relative_to(REPO)) for p in (HEALED, HERE / "core.py", HERE / "dev_series.npz") if p.exists()]
    git("add", "--", *paths)
    git("commit", "-q", "-m", f"heal round {rnd}: {msg}"[:200], "--", *paths)


# ---- main ------------------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--trial":
        checks, cells, pick, inc, par, chain_txt = sys.argv[2:8]
        steps = [tuple(ln.split("\t")[0:1] + [ln.split("\t")[1].replace("parent ", ""), ""])
                 for ln in Path(chain_txt).read_text().splitlines() if ln]
        print(json.dumps(trial(Path(checks), Path(cells), pick, inc, par, steps)))
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", required=True)
    ap.add_argument("--incumbent", required=True)
    ap.add_argument("--parent", help="the pick's parent (default: pick~1)")
    ap.add_argument("--diff", type=float, required=True, help="holdout skill, pick minus incumbent")
    ap.add_argument("--lo", type=float, required=True)
    ap.add_argument("--hi", type=float, required=True)
    ap.add_argument("--round", type=int, help="healing round number (default: last meta round + 1)")
    ap.add_argument("--cells-cache", type=Path, help="dir with dev_cells_<commit>.json already scored")
    ap.add_argument("--full-npz", help="private full build, to extend dev (real runs only)")
    ap.add_argument("--dry-run", action="store_true", help="stop before step d's writes; print them")
    ap.add_argument("--fake-director", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--no-sandbox", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    a.pick = git("rev-parse", "--short", a.pick).strip()
    a.incumbent = git("rev-parse", "--short", a.incumbent).strip()
    a.parent = git("rev-parse", "--short", a.parent or f"{a.pick}~1").strip()

    if not lost(a.diff, a.lo, a.hi):
        log(None, f"no heal needed: pick {a.pick} vs incumbent {a.incumbent} {a.diff:+.4f} [{a.lo:+.4f}, {a.hi:+.4f}]")
        return
    sys.path.insert(0, str(HERE))
    from director import last_round
    rnd = a.round or last_round()[0] + 1
    rnd_dir = HEAL_DIR / f"round_{rnd}{'-dry' if a.dry_run else ''}"
    if rnd_dir.exists():
        sys.exit(f"{rnd_dir} exists: one healing round per number")
    rnd_dir.mkdir(parents=True)
    log(rnd_dir, f"healing round {rnd}, trigger = holdout fail: pick {a.pick} lost to {a.incumbent} "
                 f"{a.diff:+.4f} [{a.lo:+.4f}, {a.hi:+.4f}]{' (dry run)' if a.dry_run else ''}")

    steps = chain(a.incumbent, a.pick)
    if not steps or steps[-1][0] != a.pick:
        sys.exit(f"{a.pick} is not on a first-parent line from {a.incumbent}")
    packet, out = rnd_dir / "packet", rnd_dir / "out"
    build_packet(packet, a, steps, a.cells_cache, rnd_dir)
    log(rnd_dir, f"packet: {len(steps)} chain steps, files {sorted(p.name for p in packet.iterdir())}")

    cost = run_director(packet, out, rnd_dir, a.fake_director)["cost_usd"]
    if not (out / "checks.py").exists():
        log(rnd_dir, "director wrote no checks.py: round stops, nothing adopted")
        return
    lesson = (out / "lesson.txt").read_text().strip().splitlines()[0] if (out / "lesson.txt").exists() else ""
    log(rnd_dir, f"post-mortem lesson: {lesson}")

    res = run_trial(packet, out, a, steps, rnd_dir, sandbox=not a.no_sandbox)
    (rnd_dir / "trial.json").write_text(json.dumps(res, indent=1))
    for r in res:
        extra = "" if "crashed" in r["reason"] else (
            f" | pick: {r['why_pick']} | keep vs parent: {'reject' if r['rejects_pick_as_keep'] else 'pass'}"
            f" | parent as pick: {'pass' if r['passes_parent_as_pick'] else 'reject'}"
            f" | chain rejects {len(r['chain_rejects'])}/{r['chain_steps']} {' '.join(r['chain_rejects'])}")
        log(rnd_dir, f"trial {r['check']}: {'PASS' if r['passed'] else 'DROP'} ({r['reason']}){extra}")
    names = [r["check"] for r in res if r["passed"]]
    log(rnd_dir, f"trial: {len(names)} of {len(res)} checks pass: {', '.join(names) or 'none'}")

    changed = (f"healing round {rnd}, trigger = holdout fail ({a.pick} vs {a.incumbent} {a.diff:+.3f}); "
               f"adopted {', '.join(names) or 'no checks'}; restart from {a.parent} and {a.incumbent}")
    target = HEALED / f"round_{rnd}.py"
    plan = restart_plan(rnd, a)
    new_end, dev_cmds = extend_dev_plan(a.full_npz)
    if a.dry_run:
        log(rnd_dir, f"dry run: would write {target.relative_to(REPO)} with {names}, commit it and rehash the manifest")
        log(rnd_dir, f"dry run: would append to LESSONS.md: {lesson}")
        log(rnd_dir, f"dry run: would log meta.tsv row: {changed}")
        for c in dev_cmds:
            log(rnd_dir, f"dry run: would extend dev: {c}")
        for who, c, br, wt in plan:
            log(rnd_dir, f"dry run: would launch {who}: git worktree add {wt} -b {br}; start point {c}; "
                         + " ".join(launch_cmd(who, wt)))
        if names:
            (rnd_dir / f"round_{rnd}.py").write_text(adopted_file(rnd, (out / "checks.py").read_text(), names, a))
        log(rnd_dir, f"dry run done; director cost ${cost:.2f}")
        return
    if not names:
        log(rnd_dir, "no check passed the trial: nothing adopted; researchers not restarted")
        write_meta(meta_row(rnd, changed))
        return
    HEALED.mkdir(exist_ok=True)
    target.write_text(adopted_file(rnd, (out / "checks.py").read_text(), names, a))
    from run import note
    if lesson:
        note("director", f"healing round {rnd}: {lesson}")
    write_meta(meta_row(rnd, changed))
    if a.full_npz:
        extend_dev(a.full_npz, rnd_dir)
    else:
        log(rnd_dir, "adopt: no --full-npz given, dev not extended")
    commit_harness(rnd, changed)
    rebuild_manifest()
    log(rnd_dir, f"adopt: committed {git('rev-parse', '--short', 'HEAD').strip()}, manifest rehashed")
    restart(plan, rnd_dir)
    log(rnd_dir, f"healing round {rnd} done; director cost ${cost:.2f}")


if __name__ == "__main__":
    main()
