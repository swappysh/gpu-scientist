"""Walk-forward check (research/harness/walkforward.py) on tiny fake cases: no real data."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from harness import core, walkforward as wf  # noqa: E402

D0 = core.day("2026-07-01")


def row(sid, o, h, loss, flat=1.0, q50=1.0, last=1.0):
    return [sid, o, h, 1.0, last, [q50 * 0.9, q50, q50 * 1.1], loss, flat]


def test_dev_and_week_split_by_target():
    c = D0 + 60
    rows = [row("s", o, h, 0.5) for o in range(D0, c + 14, 2) for h in core.HORIZONS]
    dv, wk = wf.dev(rows, c), wf.week(rows, c)
    assert dv and wk
    assert max(r[1] + r[2] for r in dv) <= c  # no dev target after the cutoff
    assert all(c < r[1] + r[2] <= c + 7 for r in wk)  # the week is the 7 target days after it
    assert {r[1] + r[2] for r in wk} <= set(range(c + 1, c + 8))
    nxt = wf.dev(rows, c + 7)  # next round: the week's prices are dev now
    assert any(r[1] + r[2] > c for r in nxt)


def test_verdict():
    assert wf.verdict(-0.01, -0.05, 0.03) == "lose"  # any loss triggers healing
    assert wf.verdict(0.02, 0.005, 0.04) == "win"
    assert wf.verdict(0.02, -0.01, 0.05) == "tie"


def test_pick_rule_and_round():
    """b has the best gate but fails the Jul-Aug bar; a wins on dev and loses the week."""
    c = core.day(core.VAL_START) + 30
    def model(jul, sep, wk):
        out = []
        for o in range(D0, c + 7, 2):
            for h in core.HORIZONS:
                t = o + h
                loss = wk if t > c else (jul if o < core.day(core.VAL_START) else sep)
                out += [row(s, o, h, loss) for s in ("x", "y", "z")]
        return out
    cands = {"inc": {"rows": model(0.8, 0.8, 0.8), "lines": 100},
             "a": {"rows": model(0.8, 0.7, 0.95), "lines": 120},
             "b": {"rows": model(0.9, 0.5, 0.5), "lines": 90}}
    p, table = wf.pick(cands, "inc", c, use_guards=False)
    assert p == "a"
    assert not next(t for t in table if t["name"] == "b")["eligible"]
    r, _ = wf.one_round(1, c, cands, "inc", use_guards=False)
    assert r["pick"] == "a" and r["verdict"] == "lose" and "heal triggered" in r["action"]


def test_tie_goes_to_fewer_lines():
    c = core.day(core.VAL_START) + 20
    rows = [row("s", o, 1, 0.5) for o in range(D0, c, 2)]
    cands = {"inc": {"rows": [r[:6] + [0.9, 1.0] for r in rows], "lines": 50},
             "big": {"rows": rows, "lines": 300}, "small": {"rows": [r[:6] + [0.5004, 1.0] for r in rows], "lines": 200}}
    assert wf.pick(cands, "inc", c, use_guards=False)[0] == "small"


AGENT = '''
SEEN = []
def forecast(history, catalog_row, origin, h):
    """Stateful on purpose: remembers every origin it was called at."""
    SEEN.append(origin)
    d, v = history.series[catalog_row["series_id"]]
    m = float(v[-3:].mean()) * (1 + 0.001 * len(set(SEEN)))
    return (m * 0.95, m, m * 1.05)
'''


def test_one_run_matches_a_run_cut_at_the_cutoff(tmp_path):
    """Dev cells from the full run equal those from a world that ends at the cutoff: nothing leaks back."""
    rng = np.random.default_rng(1)
    days = np.arange(D0, D0 + 120)
    vals = [np.exp(np.cumsum(rng.normal(0, 0.02, len(days)))) + 1 for _ in range(2)]
    full = core.World(sids=["a.c.g.p.s", "b.c.g.p.s"], groups=["c", "c"], days=[days, days], vals=vals, scored=[True, True])
    c = D0 + 80
    cut = core.World(sids=full.sids, groups=full.groups, days=[d[d <= c] for d in full.days],
                     vals=[v[full.days[i] <= c] for i, v in enumerate(full.vals)], scored=full.scored)
    f = tmp_path / "agent.py"
    f.write_text(AGENT)
    a = wf.dev(wf.all_cells(str(f), full), c)
    b = wf.dev(wf.all_cells(str(f), cut), c)
    assert a and a == b
    assert not wf.week(wf.all_cells(str(f), cut), c)  # the cut world holds no week cells at all


def test_a_week_is_scored_once(tmp_path, monkeypatch):
    monkeypatch.setattr(wf, "LEDGER", tmp_path / "walkforward.tsv")
    r = dict.fromkeys(wf.HEADER, "")
    r["week"] = "2026-10-01..2026-10-07"
    wf.log_row(r, wf.LEDGER)
    assert "2026-10-01..2026-10-07" in wf.scored_weeks()


def test_a_lost_week_starts_heal_with_dev_cells_only(tmp_path, monkeypatch):
    """heal.py gets the week's numbers and dev cells cut at the cutoff: no cell with a later target."""
    from harness import heal
    c = core.day(core.VAL_START) + 20
    rows = [row("s", o, h, 0.5) for o in range(D0, c + 7, 2) for h in core.HORIZONS]
    cands = {"i0": {"rows": rows}, "p1": {"rows": rows}, "k2": {"rows": rows}}
    monkeypatch.setattr(heal, "chain", lambda inc, pick: [("p1", "i0", "parent step"), ("k2", "p1", "pick step")])
    calls = []
    monkeypatch.setattr(wf.subprocess, "run", lambda cmd: calls.append(cmd) or type("R", (), {"returncode": 0})())
    r = {"pick": "k2", "incumbent": "i0", "diff": "-0.0200", "lo": "-0.0500", "hi": "+0.0100"}
    assert wf.heal_round(r, c, cands, "full.npz", tmp_path / "cells", 101) == 0
    cmd = calls[0]
    assert cmd[cmd.index("--cutoff") + 1] == core.iso(c) and "--dry-run" in cmd and cmd[cmd.index("--diff") + 1] == "-0.0200"
    for name in ("i0", "p1", "k2"):
        cut = json.loads((tmp_path / "cells" / f"dev_cells_{name}.json").read_text())
        assert cut and max(x[1] + x[2] for x in cut) <= c
