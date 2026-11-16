"""Self-healing round (research/harness/heal.py) on a tiny fake case: no model call, no real data."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "harness"))
import heal  # noqa: E402

# One line, two origins, h=1. Rows: [series_id, origin, h, truth, last, [q10, q50, q90], loss, flat_loss].
INC = [["s", 1, 1, 1.0, 1.0, [0.9, 1.0, 1.1], 0.03, 0.0], ["s", 3, 1, 1.0, 1.0, [0.9, 1.0, 1.1], 0.03, 0.0]]
PICK = [["s", 1, 1, 1.0, 1.0, [1.2, 1.4, 1.6], 0.40, 0.0], ["s", 3, 1, 1.0, 1.0, [0.9, 1.0, 1.1], 0.03, 0.0]]

CHECKS = '''
import math

def check_big_bets(cand, ref):
    """Reject a model whose median sits more than 0.2 (log) from the last price on any cell."""
    n = sum(abs(math.log(r[5][1] / r[4])) > 0.2 for r in cand.values())
    return n == 0, f"{n} big median bets"

def check_useless(cand, ref):
    """Passes everything, so it would not have stopped the pick: the trial must drop it."""
    return True, "always passes"

def check_crash(cand, ref):
    """Crashes: dropped."""
    return 1 / 0

ADOPTED = ["check_big_bets", "check_useless", "check_crash"]
'''


@pytest.fixture
def case(tmp_path, monkeypatch):
    """Incumbent i0 -> parent p1 -> pick k2, with cells and a fake director's out dir."""
    cells = tmp_path / "cache"
    cells.mkdir()
    for c, rows in (("i0", INC), ("p1", INC), ("k2", PICK)):
        (cells / f"{c}.json").write_text(json.dumps(rows))
    fake = tmp_path / "director"
    fake.mkdir()
    (fake / "checks.py").write_text(CHECKS)
    (fake / "lesson.txt").write_text("A median far from the last price must pay for itself.\n")
    monkeypatch.setattr(heal, "HEAL_DIR", tmp_path / "heal")
    monkeypatch.setattr(heal, "git", lambda *a: a[-1].split("~")[0] + "\n" if a[0] == "rev-parse" else "")
    monkeypatch.setattr(heal, "chain", lambda inc, pick: [("p1", "i0", "parent step"), ("k2", "p1", "pick step")])
    monkeypatch.setattr(heal, "forecaster", lambda c: f"# forecaster {c}\n")
    monkeypatch.setattr(heal, "move_rates", lambda *a: "fake move rates\n")
    return tmp_path, cells, fake


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["heal.py", *args])
    heal.main()


def test_lost_rule():
    assert heal.lost(-0.08, -0.13, -0.02)
    assert heal.lost(-0.01, -0.05, 0.03)  # lower point estimate is enough
    assert not heal.lost(0.02, -0.01, 0.05)


def test_winning_pick_does_not_heal(case, monkeypatch, capsys):
    tmp, cells, fake = case
    run(monkeypatch, "--pick", "k2", "--incumbent", "i0", "--parent", "p1", "--diff", "0.02", "--lo", "-0.01", "--hi", "0.05",
        "--cells-cache", str(cells), "--fake-director", str(fake), "--round", "1", "--dry-run")
    assert "no heal needed" in capsys.readouterr().out
    assert not (tmp / "heal" / "round_1-dry").exists()


def test_losing_pick_heals_and_drops_bad_checks(case, monkeypatch, capsys):
    tmp, cells, fake = case
    run(monkeypatch, "--pick", "k2", "--incumbent", "i0", "--parent", "p1", "--diff", "-0.08", "--lo", "-0.13", "--hi", "-0.02",
        "--cells-cache", str(cells), "--fake-director", str(fake), "--round", "1", "--dry-run", "--no-sandbox")
    out = capsys.readouterr().out
    rnd = tmp / "heal" / "round_1-dry"
    assert "trigger = holdout fail" in out
    res = {r["check"]: r for r in json.loads((rnd / "trial.json").read_text())}
    assert res["check_big_bets"]["passed"]
    assert not res["check_useless"]["passed"] and "does not reject the pick" in res["check_useless"]["reason"]
    assert not res["check_crash"]["passed"] and "crashed" in res["check_crash"]["reason"]
    adopted = (rnd / "round_1.py").read_text()
    assert "ADOPTED = ['check_big_bets']" in adopted
    assert "would launch pacsci3" in out and "start point i0" in out
    assert json.loads((rnd / "packet" / "cells" / "k2.json").read_text()) == PICK
    assert "-0.080" in (rnd / "packet" / "FAILURE.md").read_text()


def test_real_round_adopts_and_restarts(case, monkeypatch, capsys):
    """Without --dry-run: the passing check lands in healed/, a meta row and a lesson are written, researchers restart."""
    import run as run_mod
    tmp, cells, fake = case
    calls = {}
    monkeypatch.setattr(heal, "HEALED", tmp / "healed")
    monkeypatch.setattr(heal, "commit_harness", lambda rnd, msg: calls.setdefault("commit", msg))
    monkeypatch.setattr(heal, "rebuild_manifest", lambda: calls.setdefault("manifest", True))
    monkeypatch.setattr(heal, "restart", lambda plan, d: calls.setdefault("restart", plan))
    monkeypatch.setattr(heal, "write_meta", lambda row: calls.setdefault("meta", row))
    monkeypatch.setattr(run_mod, "note", lambda who, text: calls.setdefault("note", text))
    run(monkeypatch, "--pick", "k2", "--incumbent", "i0", "--parent", "p1", "--diff", "-0.08", "--lo", "-0.13",
        "--hi", "-0.02", "--cells-cache", str(cells), "--fake-director", str(fake), "--round", "2", "--no-sandbox")
    f = tmp / "healed" / "round_2.py"
    ns = {}
    exec(f.read_text(), ns)
    assert ns["ADOPTED"] == ["check_big_bets"]
    assert not ns["check_big_bets"]({k: r for k, r in enumerate(PICK)}, {})[0]
    assert "trigger = holdout fail" in calls["meta"]["changed"] and calls["meta"]["round"] == "2"
    assert "must pay for itself" in calls["note"]
    assert [(w, c) for w, c, _, _ in calls["restart"]] == [("pacsci1", "p1"), ("pacsci2", "p1"), ("pacsci3", "i0")]
    assert calls["manifest"] and "check_big_bets" in calls["commit"]
