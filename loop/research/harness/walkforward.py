"""Walk-forward check (rolling origin): each round's pick is scored once on the next unseen week.

Run by the outer loop only; it opens the full build, which the researchers never see.
The rule is research/WALKFORWARD.md. In short, round k has dev cutoff C:

  dev   = grid origins whose targets (origin + 1, 3, 7) are all on or before C
  week  = every grid cell whose target day is C+1 .. C+7
  pick  = PREREG-v81's pick rule on dev (Jul-Aug >= incumbent, G1-G3 vs incumbent, best gate)
  score = pick minus incumbent skill on the week, with a 95% series bootstrap
  win   = diff > 0 and the interval excludes 0: the pick becomes the incumbent
  lose  = heal.lost(diff, lo, hi): healing is triggered
  then C += 7 and the week joins dev

One forecaster run over every grid origin gives the cells for all rounds: a forecast at
origin o sees only rows on or before o (core.cut), and origins run in ascending order, so a
dev cell is the same number whether the run stops at C or goes on to the pack's end.

    .venv/bin/python research/harness/walkforward.py round --full F --cutoff C --incumbent I CAND...
    .venv/bin/python research/harness/walkforward.py replay PLAN.json [--out DIR]

A lost week starts heal.py on its own, with dev cells cut at the round's cutoff, so the
director never sees the week. --heal-dry (today's default) stops heal before it adopts checks
or restarts researchers. Candidate names must be commits when healing is on.

A candidate is NAME=FILE.py, or NAME=FILE.py@SEEN (the last day its researcher saw; it
competes only from cutoffs on or after SEEN). The scorer, cut, grid and keep numbers are core's.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import core, guards  # noqa: E402
from harness.heal import lost  # noqa: E402

RESEARCH = Path(__file__).resolve().parents[1]
LEDGER = RESEARCH / "walkforward.tsv"
WEEK = 7
TIE = 0.001  # pick rule: gate skills this close count as equal; fewer lines wins
DRAWS = 10_000
HEADER = ["round", "cutoff", "week", "pick", "incumbent", "pick_gate", "pick_julaug", "pick_week",
          "incumbent_week", "diff", "lo", "hi", "verdict", "action"]


def grid(world: core.World) -> list[int]:
    """The harness's origins (every 2 days from Jul 1) up to the day before the pack's last row."""
    end = max(int(d.max()) for d in world.days if len(d))
    return list(range(core.day(core.TRAIN_START), end, core.ORIGIN_STEP))


def all_cells(agent_file: str, world: core.World) -> list:
    """Per-cell rows for every grid origin with a known target: one locked-worker run."""
    origins = grid(world)
    return core.cells(world, core.forecasts(agent_file, world, origins), origins)


def cached_cells(agent_file: str, world: core.World, cache: Path | None) -> list:
    """all_cells, kept per forecaster sha256 and full-build sha256."""
    if cache is None:
        return all_cells(agent_file, world)
    key = hashlib.sha256(Path(agent_file).read_bytes() + repr(world.sids).encode()
                         + b"".join(d.tobytes() + v.tobytes() for d, v in zip(world.days, world.vals))).hexdigest()[:16]
    f = cache / f"{Path(agent_file).stem}-{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    rows = all_cells(agent_file, world)
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows))
    return rows


def dev(rows: list, cutoff: int) -> list:
    return [r for r in rows if r[1] + max(core.HORIZONS) <= cutoff]


def week(rows: list, cutoff: int) -> list:
    return [r for r in rows if cutoff < r[1] + r[2] <= cutoff + WEEK]


def skill(rows: list) -> float:
    b = sum(r[7] for r in rows)
    return 1 - sum(r[6] for r in rows) / b if b > 0 else 0.0


def gate_julaug(rows: list) -> tuple[float, float]:
    val = core.day(core.VAL_START)
    return skill([r for r in rows if r[1] >= val]), skill([r for r in rows if r[1] < val])


def per_series(rows: list) -> dict:
    out: dict = {}
    for r in rows:
        a = out.setdefault(r[0], [0.0, 0.0])
        a[0] += r[6]
        a[1] += r[7]
    return out


def diff_ci(pick_rows: list, inc_rows: list, draws: int = DRAWS, seed: int = 0) -> tuple[float, float, float, float]:
    """Pick minus incumbent skill, and its series bootstrap (as score_heldout.py): diff, lo, hi, share > 0."""
    a, b = per_series(pick_rows), per_series(inc_rows)
    ids = sorted(set(a) & set(b))
    pa = np.array([a[i] for i in ids])
    pb = np.array([b[i] for i in ids])
    idx = np.random.default_rng(seed).integers(0, len(ids), size=(draws, len(ids)))
    d = (pb[:, 0][idx].sum(1) - pa[:, 0][idx].sum(1)) / pb[:, 1][idx].sum(1)
    lo, hi = np.quantile(d, [0.025, 0.975])
    return skill(pick_rows) - skill(inc_rows), float(lo), float(hi), float((d > 0).mean())


def verdict(diff: float, lo: float, hi: float) -> str:
    if lost(diff, lo, hi):
        return "lose"
    return "win" if diff > 0 and lo > 0 else "tie"


def pick(cands: dict, incumbent: str, cutoff: int, use_guards: bool = True) -> tuple[str, list]:
    """PREREG-v81's pick rule on dev cells only. cands: name -> {"rows", "lines"}. Returns (pick, table)."""
    inc = dev(cands[incumbent]["rows"], cutoff)
    _, bar = gate_julaug(inc)
    table = []
    for name, c in cands.items():
        rows = dev(c["rows"], cutoff)
        g, j = gate_julaug(rows)
        why = [] if j >= bar else [f"Jul-Aug {j:+.4f} < incumbent {bar:+.4f}"]
        if use_guards and name != incumbent:
            why += guards.pick_check(rows, inc)
        table.append({"name": name, "gate": g, "julaug": j, "lines": c["lines"], "eligible": not why, "why": why})
    ok = [t for t in table if t["eligible"] or t["name"] == incumbent]
    top = max(t["gate"] for t in ok)
    best = min((t for t in ok if t["gate"] >= top - TIE), key=lambda t: (t["lines"], -t["gate"]))
    return best["name"], table


def scored_weeks() -> set[str]:
    if not LEDGER.exists():
        return set()
    return {ln.split("\t")[2] for ln in LEDGER.read_text().splitlines()[1:] if ln.strip()}


def log_row(row: dict, ledger: Path) -> None:
    new = not ledger.exists()
    with open(ledger, "a") as f:
        if new:
            f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(str(row[k]) for k in HEADER) + "\n")


def one_round(k: int, cutoff: int, cands: dict, incumbent: str, use_guards: bool = True) -> tuple[dict, list]:
    """Pick on dev to `cutoff`, then score pick vs incumbent once on the week after it."""
    p, table = pick(cands, incumbent, cutoff, use_guards)
    g, j = next((t["gate"], t["julaug"]) for t in table if t["name"] == p)
    wp, wi = week(cands[p]["rows"], cutoff), week(cands[incumbent]["rows"], cutoff)
    if p == incumbent:
        d, lo, hi, v, act = 0.0, 0.0, 0.0, "none", "pick is the incumbent: nothing to test"
    else:
        d, lo, hi, _ = diff_ci(wp, wi)
        v = verdict(d, lo, hi)
        act = {"win": f"{p} becomes the incumbent", "tie": f"{incumbent} stays",
               "lose": f"{incumbent} stays; heal triggered on {p}"}[v]
    row = {"round": k, "cutoff": core.iso(cutoff), "week": f"{core.iso(cutoff + 1)}..{core.iso(cutoff + WEEK)}",
           "pick": p, "incumbent": incumbent, "pick_gate": f"{g:+.4f}", "pick_julaug": f"{j:+.4f}",
           "pick_week": f"{skill(wp):+.4f}", "incumbent_week": f"{skill(wi):+.4f}", "diff": f"{d:+.4f}",
           "lo": f"{lo:+.4f}", "hi": f"{hi:+.4f}", "verdict": v, "action": act}
    return row, table


def heal_round(row: dict, cutoff: int, cands: dict, full: str, cells_dir: Path, rnd: int,
               dry: bool = True, fake_director: str | None = None) -> int:
    """The week was lost: run heal.py on it, with every chain step's dev cells cut at the cutoff."""
    from harness import heal
    pick, inc = row["pick"], row["incumbent"]
    steps = heal.chain(inc, pick)
    cells_dir.mkdir(parents=True, exist_ok=True)
    world = None
    for c in {inc} | {x for st in steps for x in st[:2]}:
        if c in cands:
            rows = cands[c]["rows"]
        else:  # a chain step that was not a candidate (a discard's parent, a fork)
            world = world or core.load(full)
            f = cells_dir / f"{c}.py"
            f.write_text(heal.forecaster(c))
            rows = cached_cells(str(f), world, cells_dir / "all")
        (cells_dir / f"dev_cells_{c}.json").write_text(json.dumps(dev(rows, cutoff)))
    cmd = [sys.executable, str(Path(heal.__file__)), "--pick", pick, "--incumbent", inc,
           "--diff", row["diff"], "--lo", row["lo"], "--hi", row["hi"], "--round", str(rnd),
           "--cutoff", core.iso(cutoff), "--full-npz", full, "--cells-cache", str(cells_dir)]
    cmd += ["--dry-run"] if dry else []
    cmd += ["--fake-director", fake_director] if fake_director else []
    print("  heal: " + " ".join(cmd[1:]), flush=True)
    return subprocess.run(cmd).returncode


def parse_cand(spec: str) -> tuple[str, str, int | None]:
    name, rest = spec.split("=", 1)
    path, _, seen = rest.partition("@")
    return name, path, core.day(seen) if seen else None


def load_cands(specs: list[str], world: core.World, cache: Path | None) -> dict:
    from harness.run import code_lines
    out = {}
    for s in specs:
        name, path, seen = parse_cand(s)
        t0 = time.time()
        rows = cached_cells(path, world, cache)
        out[name] = {"rows": rows, "lines": code_lines(Path(path).read_text()), "seen": seen}
        print(f"  cells {name}: {len(rows)} ({time.time() - t0:.0f} s)", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("round", help="one live round: pick on dev, score the next week once")
    r.add_argument("--full", required=True, help="private full build (.npz)")
    r.add_argument("--cutoff", required=True, help="last dev day, YYYY-MM-DD")
    r.add_argument("--incumbent", required=True, help="NAME=FILE.py")
    r.add_argument("cands", nargs="+", help="NAME=FILE.py[@SEEN]")
    r.add_argument("--cache", type=Path)
    r.add_argument("--no-guards", action="store_true", help="v8's pick rule (Jul-Aug bar only)")
    r.add_argument("--heal-round", type=int, help="healing round number if the week is lost")
    r.add_argument("--heal-live", action="store_true", help="let heal adopt checks and restart (default: dry run)")
    p = sub.add_parser("replay", help="dry replay over frozen forecasters; no researcher, no model call")
    p.add_argument("plan", type=Path)
    p.add_argument("--out", type=Path, help="folder for the replay ledger (default: next to the plan)")
    a = ap.parse_args()

    if a.cmd == "round":
        world = core.load(a.full)
        cutoff = core.day(a.cutoff)
        wk = f"{core.iso(cutoff + 1)}..{core.iso(cutoff + WEEK)}"
        if wk in scored_weeks():
            sys.exit(f"week {wk} was already scored once: it is dev now, pick the next cutoff")
        if cutoff + WEEK > max(int(d.max()) for d in world.days if len(d)):
            sys.exit(f"week {wk} is not complete in the full build yet")
        cands = load_cands([a.incumbent, *a.cands], world, a.cache)
        inc = parse_cand(a.incumbent)[0]
        cands = {n: c for n, c in cands.items() if c["seen"] is None or c["seen"] <= cutoff}
        k = len(scored_weeks()) + 1
        row, _ = one_round(k, cutoff, cands, inc, not a.no_guards)
        log_row(row, LEDGER)
        print("\t".join(f"{h}={row[h]}" for h in HEADER))
        if row["verdict"] == "lose":
            from harness.director import last_round
            rnd = a.heal_round or last_round()[0] + 1
            sys.exit(heal_round(row, cutoff, cands, a.full, (a.cache or RESEARCH / "state") / f"heal-{rnd}",
                                rnd, dry=not a.heal_live))
        return

    plan = json.loads(a.plan.read_text())
    out = a.out or a.plan.parent
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "walkforward-replay.tsv"
    ledger.unlink(missing_ok=True)
    world = core.load(plan["full"])
    specs = [f"{c['name']}={c['file']}" + (f"@{c['seen']}" if c.get("seen") else "") for c in plan["candidates"]]
    allc = load_cands(specs, world, Path(plan["cache"]) if plan.get("cache") else None)
    inc = plan["incumbent"]
    picks = {}
    for k, c in enumerate(plan["cutoffs"], 1):
        cutoff = core.day(c)
        cands = {n: x for n, x in allc.items() if n == inc or x["seen"] is None or x["seen"] <= cutoff}
        rule = plan.get("rules", {}).get(c, plan.get("rule", "v81"))
        row, table = one_round(k, cutoff, cands, inc, rule != "v8")
        log_row(row, ledger)
        picks[c] = table
        print(f"round {k} cutoff {row['cutoff']} week {row['week']} rule {rule}: pick {row['pick']} "
              f"(gate {row['pick_gate']}) vs {inc}: week {row['pick_week']} vs {row['incumbent_week']}, "
              f"diff {row['diff']} [{row['lo']}, {row['hi']}] -> {row['verdict']}: {row['action']}", flush=True)
        if row["verdict"] == "win":
            inc = row["pick"]
        h = plan.get("heal")
        if row["verdict"] == "lose" and h:
            rnd = h.get("first_round", 100) + k
            fake = h.get("fake_director") if k not in h.get("real_director_rounds", []) else None
            rc = heal_round(row, cutoff, cands, plan["full"], out / f"heal-{rnd}", rnd, True, fake)
            print(f"  heal round {rnd} exit {rc}", flush=True)
    (out / "walkforward-replay-picks.json").write_text(json.dumps(picks, indent=1))


if __name__ == "__main__":
    main()
