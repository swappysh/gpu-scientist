"""Post-mortem guards (v8.1, director meta round 5 'healing', PREREG-v81.md). Read-only.

b06b208 carried a one-off price jump forward as a run and lost on new data. These checks
are stricter additions to the keep rule (candidate vs its parent, the current best) and to
the final pick (model vs v7). They read per-cell dev rows from core.evaluate_dev:
[series_id, origin, h, truth, last, [q10, q50, q90], loss, flat_loss].

  G1 big median bets must pay: keep: on cells where the candidate's median is more than BIG
     (log) from the parent's, the candidate's loss must not exceed the parent's.
     pick: on cells where the median is more than BIG from the last price, skill vs flat >= 0.
  G2 the newest week must not drop: on the last 7 days of dev origins (Oct 1-7), skill may not
     fall more than TOL below the reference (keep: parent; pick: v7).
  G3 no single line pays for the rest: no line's loss may rise by more than TOL of the total
     flat loss (all dev cells) vs the reference (keep: parent; pick: v7).

Healing rounds (heal.py) add checks in healed/round_N.py. Each is check(cand, ref) -> (ok, why),
run in both forms after G1-G3. A check that crashes counts as a reject.
"""

from __future__ import annotations

import importlib.util
import math
from collections import defaultdict
from pathlib import Path

BIG = 0.04  # G1: about two typical moves (mean |move| 0.02-0.03)
TOL = 0.005  # G2, G3: same size as the locked Jul-Sep tolerance
NEWEST_DAYS = 7


def _index(rows: list) -> dict:
    return {(r[0], r[1], r[2]): r for r in rows}


def _skill(c: dict, keys: list) -> float:
    b = sum(c[k][7] for k in keys)
    return 1 - sum(c[k][6] for k in keys) / b if b > 0 else 0.0


def g1_keep(cand: dict, parent: dict) -> tuple[bool, str]:
    ks = [k for k in cand if k in parent and abs(math.log(cand[k][5][1] / parent[k][5][1])) > BIG]
    lc, lp = sum(cand[k][6] for k in ks), sum(parent[k][6] for k in ks)
    return lc <= lp, f"G1 big median shifts vs the parent: loss {lc:.3f} vs {lp:.3f} on {len(ks)} cells"


def g1_pick(model: dict) -> tuple[bool, str]:
    ks = [k for k in model if abs(math.log(model[k][5][1] / model[k][4])) > BIG]
    s = _skill(model, ks) if ks else 0.0
    return s >= 0, f"G1 big median bets: skill {s:+.4f} on {len(ks)} cells (needs >= 0)"


def g2(cand: dict, ref: dict) -> tuple[bool, str]:
    last = max(k[1] for k in cand)
    ks = [k for k in cand if k[1] > last - NEWEST_DAYS and k in ref]
    d = _skill(cand, ks) - _skill(ref, ks)
    return d >= -TOL, f"G2 newest week: skill {d:+.4f} vs reference on {len(ks)} cells (needs >= -{TOL})"


def g3(cand: dict, ref: dict) -> tuple[bool, str]:
    tot = sum(r[7] for r in cand.values())
    d = defaultdict(float)
    for k in cand:
        if k in ref:
            d[k[0]] += cand[k][6] - ref[k][6]
    worst = max(d, key=d.get)
    return d[worst] / tot <= TOL, f"G3 worst line {worst}: loss up {d[worst] / tot:.4f} of flat (needs <= {TOL})"


def _healed() -> list:
    fns = []
    for f in sorted(Path(__file__).with_name("healed").glob("round_*.py")):
        spec = importlib.util.spec_from_file_location(f"healed_{f.stem}", f)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        fns += [getattr(m, n) for n in m.ADOPTED]
    return fns


HEALED = _healed()


def _run_healed(cand: dict, ref: dict) -> list[str]:
    out = []
    for fn in HEALED:
        try:
            ok, why = fn(cand, ref)
        except Exception as exc:  # noqa: BLE001
            ok, why = False, f"{fn.__name__} crashed: {type(exc).__name__}"
        if not ok:
            out.append(f"{fn.__module__.removeprefix('healed_')} {fn.__name__}: {why}")
    return out


def keep_check(cand_rows: list, parent_rows: list) -> list[str]:
    """Reasons a keep fails the guards (empty list = passes)."""
    c, p = _index(cand_rows), _index(parent_rows)
    return [why for ok, why in (g1_keep(c, p), g2(c, p), g3(c, p)) if not ok] + _run_healed(c, p)


def pick_check(model_rows: list, v7_rows: list) -> list[str]:
    """Reasons a final pick fails the guards (empty list = passes)."""
    m, v = _index(model_rows), _index(v7_rows)
    return [why for ok, why in (g1_pick(m), g2(m, v), g3(m, v)) if not ok] + _run_healed(m, v)
