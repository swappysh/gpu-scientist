"""Healing round 6 (heal.py, 2026-11-15 18:46Z): checks a fresh director proposed after
pick b06b208 lost to incumbent 18c491e on the holdout (-0.080, 95% [-0.130, -0.023]).
Adopted after the trial (each rejects the pick, passes the incumbent): check_median_outside_ref_band, check_single_line_damage, check_recent_window. Read-only.
"""

"""Checks against the b06b208 failure: run-pace extrapolation (pace since the run's first move x h)
pushed medians far outside the reference band on a few lines, and the damage landed in the
latest dev days, which the keep rule did not weigh. Rows: [sid, origin, h, truth, last, [q10,q50,q90], loss, flat]."""
from collections import defaultdict


def _common(cand, ref):
    keys = [k for k in cand if k in ref]
    flat = sum(ref[k][7] for k in keys)
    return keys, flat


def check_median_outside_ref_band(cand, ref):
    """Cells where cand's median leaves ref's own [q10, q90] must not raise loss, in sum, by more
    than 1% of ref's total flat loss (= one skill point). Reason: a median outside the ref's 80% band
    is a strong claim (the run extrapolation did exactly this); a step usually claims 0.002-0.005
    skill in total, so relocated medians costing a full point are not noise we should accept."""
    keys, flat = _common(cand, ref)
    if not flat:
        return True, "no flat loss"
    out = [k for k in keys if not (ref[k][5][0] - 1e-9 <= cand[k][5][1] <= ref[k][5][2] + 1e-9)]
    d = sum(cand[k][6] - ref[k][6] for k in out) / flat
    return d <= 0.01, f"{len(out)} medians outside ref band, loss change {d:+.4f} of flat (max +0.01)"


def check_single_line_damage(cand, ref):
    """No single series may raise loss by more than 1% of ref's total flat loss. Reason: a
    multiplicative extrapolation fails on one or two lines at a time (B200, A100_40GB here); one
    line costing a full skill point exceeds any single step's whole claimed gain, so the average
    gain elsewhere is not allowed to buy it."""
    keys, flat = _common(cand, ref)
    if not flat:
        return True, "no flat loss"
    d = defaultdict(float)
    for k in keys:
        d[k[0]] += cand[k][6] - ref[k][6]
    sid, worst = max(d.items(), key=lambda x: x[1]) if d else ("-", 0.0)
    return worst / flat <= 0.01, f"worst line {sid} loss change {worst / flat:+.4f} of flat (max +0.01)"


def check_recent_window(cand, ref):
    """Skill on cells whose target day (origin + h) is in the last 15 dev days must not fall more than
    0.02 below ref's. Reason: those days are nearest the holdout and in a different regime (move share
    0.45 vs 0.27, mostly up) that the keep window does not cover; two skill points is about twice the
    largest gain a single step claims, so a bigger drop there is a trade of recent for older skill."""
    keys, _ = _common(cand, ref)
    if not keys:
        return True, "no cells"
    end = max(k[1] + k[2] for k in keys)
    late = [k for k in keys if k[1] + k[2] > end - 15]
    flat = sum(ref[k][7] for k in late)
    if not flat:
        return True, "no flat loss in recent window"
    sc = 1 - sum(cand[k][6] for k in late) / flat
    sr = 1 - sum(ref[k][6] for k in late) / flat
    return sc >= sr - 0.02, f"last-15-day skill {sc:.3f} vs ref {sr:.3f} (max drop 0.02)"

ADOPTED = ['check_median_outside_ref_band', 'check_single_line_damage', 'check_recent_window']
