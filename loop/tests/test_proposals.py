"""Self-growing proposals (research/harness/proposals.py) on fake files: no model call."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from harness import proposals as pr  # noqa: E402

SCRIPT = Path(pr.__file__)
DIRECTOR = ("kind\tproposal\twhy\ttest\n"
            "input\tDays since a sibling line last moved.\tlines move together (abc1234)\tkeep if gate +0.003\n"
            "family\tMix no move with one step.\tmost days are flat\tdrop if Jul-Aug falls\n"
            "model\tSomething odd.\tx\ty\n"
            "family\tLoosen the keep rule to 0.001.\tx\ty\n")


def test_parse_drops_bad_and_locked_rows():
    new, bad = pr.parse_director(DIRECTOR, 4, 2)
    assert [p["id"] for p in new] == ["P4", "P5"] and new[1]["kind"] == "family"
    assert len(bad) == 2 and any("locked" in b for b in bad)


def test_tally_counts_tries_and_keeps():
    new, _ = pr.parse_director(DIRECTOR, 1, 1)
    res = [{"commit": "c1", "hypothesis": "[P1] input: sibling days", "status": "discard", "lesson": ""},
           {"commit": "c2", "hypothesis": "[P1] input: sibling days, v2", "status": "keep",
            "lesson": "sept +0.3400 vs best +0.3300"},
           {"commit": "c3", "hypothesis": "[P2] family: mix", "status": "discard", "lesson": ""},
           {"commit": "c4", "hypothesis": "[P2] again", "status": "crash", "lesson": ""},
           {"commit": "c5", "hypothesis": "[P2] third", "status": "discard", "lesson": ""},
           {"commit": "c6", "hypothesis": "[P9] unknown id", "status": "keep", "lesson": ""}]
    t = {p["id"]: p for p in pr.tally(new, res)}
    assert t["P1"]["status"] == "kept" and t["P1"]["tries"] == 2 and t["P1"]["best_gain"] == "+0.3400"
    assert t["P1"]["commits"] == "c1 c2"
    assert t["P2"]["status"] == "dropped" and t["P2"]["keeps"] == 0
    assert "P1" not in pr.program_text(list(t.values()))  # kept and dropped leave the open list


def test_propose_and_track_end_to_end(tmp_path):
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / "proposals.tsv").write_text(DIRECTOR)
    results = tmp_path / "results.tsv"
    results.write_text("agent\tcommit\thypothesis\tsept\tjulsep\tstatus\tlesson\n"
                       "a\tc1\tbaseline\t0.3\t0.2\tkeep\t\n")
    ledger = tmp_path / "proposals.tsv"
    py = sys.executable
    subprocess.run([py, SCRIPT, "propose", "1", "--results", results, "--fake", fake, "--ledger", ledger], check=True)
    assert len(pr.read_tsv(ledger)) == 2
    assert (tmp_path / "proposals" / "round_1" / "log.txt").exists()
    with results.open("a") as f:
        f.write("a\tc2\t[P2] family: mix\t0.31\t0.2\tkeep\tsept +0.3100 vs best +0.3000\n")
    subprocess.run([py, SCRIPT, "track", "--results", results, "--ledger", ledger], check=True)
    assert {p["id"]: p["status"] for p in pr.read_tsv(ledger)} == {"P1": "open", "P2": "kept"}
    out = subprocess.run([py, SCRIPT, "program", "--ledger", ledger], capture_output=True, text=True, check=True).stdout
    assert "P1 (input, open" in out and "P2" not in out
    subprocess.run([py, SCRIPT, "propose", "2", "--results", results, "--fake", fake, "--ledger", ledger], check=True)
    assert [p["id"] for p in pr.read_tsv(ledger)][-2:] == ["P3", "P4"]  # ids keep counting up


def test_program_block_is_replaced_not_stacked(tmp_path):
    prog = tmp_path / "program.md"
    prog.write_text("fixed part\n## Strategy (rewritten by the director; the rest of this file is fixed)\nfork now\n")
    new, _ = pr.parse_director(DIRECTOR, 1, 1)
    pr.into_program(prog, pr.program_text(new))
    pr.into_program(prog, pr.program_text(new[:1]))
    s = prog.read_text()
    assert s.count(pr.MARK) == 1 and "fork now" in s and "P1" in s and "P2" not in s
    pr.into_program(prog, "")
    assert pr.MARK not in prog.read_text() and prog.read_text().endswith("fork now\n")


def test_ordinary_words_are_not_locked():
    ok = "kind\tproposal\twhy\ttest\ninput\tSplit lines by GPU class and check the sibling's last move.\tx\ty\n"
    assert len(pr.parse_director(ok, 1, 1)[0]) == 1
