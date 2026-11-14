"""Tests for the shared-memory loop. No network, no keys."""

import json

import pytest

from pacific_hack import harness, ledger
from pacific_hack.agents import Critic, hypothesis_fact_id
from pacific_hack.data import HELDOUT_END, TRAIN_END, make_series, split
from pacific_hack.forecaster import ForecasterConfig, backtest
from pacific_hack.memory import HOLDOUT_AUDIENCE, JsonlMemory, PastDevMemory
from pacific_hack.run import run

HOLDOUT_KEYS = ("skill_heldout", "d_heldout", "alt_heldout")


@pytest.fixture
def memory(tmp_path):
    return JsonlMemory(str(tmp_path / "ledger.jsonl"))


def fact(date, **kw):
    return ledger.make_entry("note", "proposed", "test", market_date=date, **kw)


def record_calls(monkeypatch, mem):
    calls = []
    monkeypatch.setattr(
        mem, "_call", lambda method, path, body=None: calls.append((method, path, body)) or {}
    )
    return calls


# 1. No peeking at the future ------------------------------------------------


def test_earlier_read_does_not_return_future_fact(memory):
    memory.append(fact("2026-09-15", reason="step to 2.10"))
    memory.append(fact("2026-10-15", reason="future step to 2.60"))
    reader = memory.bound("proposer")
    assert [e["reason"] for e in reader.entries(as_of="2026-09-30")] == ["step to 2.10"]
    assert [e["reason"] for e in reader.search("step future", as_of="2026-09-30")] == ["step to 2.10"]
    assert len(reader.entries(as_of="2026-10-31")) == 2


def test_past_backend_sends_query_timestamp_and_event_time(monkeypatch):
    mem = PastDevMemory(api_key="test-key").bound("proposer")
    calls = record_calls(monkeypatch, mem)
    mem.entries(as_of="2026-09-30")
    recalls = [b for m, p, b in calls if p == "/recall"]
    assert recalls and all(b["queryTimestamp"] == "2026-09-30T00:00:00Z" for b in recalls)
    assert all(b["identity"] == "pacific-proposer" for b in recalls)

    mem.append(fact("2026-09-15"))
    ingest = [b for m, p, b in calls if p == "/ingest"][0]
    assert ingest["timestamp"] == "2026-09-15T00:00:00Z"
    assert "audience" not in ingest


# 2. Read boundary -----------------------------------------------------------


def test_holdout_audience_readable_only_by_critic(memory):
    memory.append(fact(HELDOUT_END, scores={"skill_heldout": 0.31}, audience=HOLDOUT_AUDIENCE))
    assert memory.bound("critic").entries(as_of=HELDOUT_END)
    for reader in ("proposer", "evaluator"):
        assert memory.bound(reader).entries(as_of=HELDOUT_END) == []
    assert memory.entries(as_of=HELDOUT_END) == []  # unbound reader


def test_past_backend_creates_critic_only_audience(monkeypatch):
    mem = PastDevMemory(api_key="test-key")
    calls = record_calls(monkeypatch, mem)
    mem.append(fact(HELDOUT_END, audience=HOLDOUT_AUDIENCE))
    put = [(p, b) for m, p, b in calls if m == "PUT"][0]
    assert put[0] == f"/audiences/{HOLDOUT_AUDIENCE}"
    assert put[1] == {"kind": "fixed", "name": HOLDOUT_AUDIENCE, "identities": ["pacific-critic"]}
    ingest = [b for m, p, b in calls if p == "/ingest"][0]
    assert ingest["audience"] == HOLDOUT_AUDIENCE


def test_proposer_never_sees_holdout_numbers_in_full_loop(memory):
    run(memory, rounds=4, seed=7, verbose=False)
    for reader in ("proposer", "evaluator"):
        visible = json.dumps(memory.bound(reader).entries(as_of="2999-01-01"))
        assert not any(k in visible for k in HOLDOUT_KEYS), reader
    assert any(k in json.dumps(memory.bound("critic").entries()) for k in HOLDOUT_KEYS)


# 3. Small writes + supersession ---------------------------------------------


def test_refuted_hypothesis_is_superseded_not_duplicated(memory, monkeypatch):
    fid = hypothesis_fact_id("idea-001")
    kw = dict(
        idea_id="idea-001",
        change={"param": "lookback_days", "value": 7},
        previous={"param": "lookback_days", "value": 14},
        fact_id=fid,
    )
    memory.append(ledger.make_entry("proposal", "proposed", "proposer", market_date=TRAIN_END, **kw))
    memory.append(ledger.make_entry("decision", "kept", "evaluator", market_date=TRAIN_END, **kw))
    # Force the critic to refute: every alternate world shows a heldout loss.
    monkeypatch.setattr(
        "pacific_hack.agents.backtest_batch",
        lambda configs, runner, seed: [
            {"skill_train": 0, "skill_heldout": 0.5, "steps": 1},
            {"skill_train": 0, "skill_heldout": 0.1, "steps": 1},
        ],
    )
    (verdict,) = Critic(memory.bound("critic")).review_pending()
    assert verdict["status"] == "refuted" and verdict["fact_id"] == fid

    live = [e for e in memory.bound("proposer").entries(as_of=TRAIN_END) if e["fact_id"] == fid]
    assert [e["status"] for e in live] == ["refuted"]  # one live fact, now refuted
    raw = [json.loads(line) for line in open(memory.path)]
    assert [e["status"] for e in raw if e["fact_id"] == fid] == ["proposed", "kept", "refuted"]


def test_past_backend_reuses_data_point_id_for_supersession(monkeypatch):
    mem = PastDevMemory(api_key="test-key")
    calls = record_calls(monkeypatch, mem)
    for status in ("proposed", "refuted"):
        mem.append(
            ledger.make_entry(
                "decision", status, "critic", market_date=TRAIN_END, fact_id="hyp-idea-001"
            )
        )
    ids = [b["id"] for m, p, b in calls if p == "/ingest"]
    assert ids == ["ledger:hyp-idea-001", "ledger:hyp-idea-001"]


def test_loop_writes_tens_of_facts_not_rows(memory):
    run(memory, rounds=4, seed=7, verbose=False)
    assert len(open(memory.path).readlines()) < 100


# Runner seam + steps/hour ---------------------------------------------------


def test_backtest_batch_matches_backtest_and_keeps_order():
    configs = [ForecasterConfig(), ForecasterConfig(lookback_days=7)]
    got = harness.backtest_batch(configs, runner="local", seed=7)
    train, heldout = split(make_series(seed=7))
    assert got == [backtest(c, train, heldout) for c in configs]


def test_modal_runner_dispatches_to_modal_app(monkeypatch):
    from pacific_hack import modal_app

    seen = {}

    def fake_run_batch(jobs):
        seen["jobs"] = jobs
        return [{"skill_train": 0.0, "skill_heldout": 0.0}] * len(jobs)

    monkeypatch.setattr(modal_app, "run_batch", fake_run_batch)
    harness.backtest_batch([ForecasterConfig()], runner="modal", seed=3)
    assert seen["jobs"] == [(ForecasterConfig().to_dict(), 3)]


def test_throughput_note_records_runner_and_steps_per_hour(memory):
    run(memory, rounds=1, seed=7, verbose=False)
    notes = [
        e for e in memory.bound("critic").entries() if e["kind"] == "note" and e["agent"] == "evaluator"
    ]
    assert notes
    s = notes[0]["scores"]
    assert s["runner"] == "local" and s["steps"] > 0 and s["steps_per_hour"] > 0


def test_loop_keeps_and_kills(memory):
    run(memory, rounds=4, seed=7, verbose=False)
    statuses = {e["status"] for e in memory.bound("critic").entries() if e["kind"] == "decision"}
    assert "killed" in statuses and statuses & {"kept", "corroborated"}
