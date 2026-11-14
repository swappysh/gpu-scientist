"""Tests for the shared-memory loop. No network, no keys."""

import json

import pytest

from pacific_hack import harness, ledger
from pacific_hack.agents import Critic, hypothesis_fact_id
from pacific_hack.data import HELDOUT_END, TRAIN_END, synthetic_world
from pacific_hack.forecaster import ForecasterConfig, backtest
from pacific_hack.memory import HOLDOUT_AUDIENCE, JsonlMemory, PastDevMemory
from pacific_hack.run import run

HOLDOUT_KEYS = ("skill_heldout", "d_heldout", "skill_val", "d_val", "alt_val")


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
        change={"param": "window_days", "value": 45},
        previous={"param": "window_days", "value": 0},
        fact_id=fid,
    )
    memory.append(ledger.make_entry("proposal", "proposed", "proposer", market_date=TRAIN_END, **kw))
    memory.append(ledger.make_entry("decision", "kept", "evaluator", market_date=TRAIN_END, **kw))
    # Force the critic to refute: every alternate world shows a September loss.
    monkeypatch.setattr(
        "pacific_hack.agents.backtest_batch",
        lambda configs, runner, seed: [
            {"skill_train": 0, "skill_val": 0.5, "skill_heldout": 0.5, "steps": 1},
            {"skill_train": 0, "skill_val": 0.1, "skill_heldout": 0.9, "steps": 1},
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
    configs = [ForecasterConfig(), ForecasterConfig(window_days=45)]
    got = harness.backtest_batch(configs, runner="local", seed=7)
    assert got == [backtest(c, synthetic_world(seed=7)) for c in configs]


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


def test_momentum_extends_the_last_daily_change():
    import numpy as np

    from pacific_hack.data import Series, day
    from pacific_hack.forecaster import Changes, forecast

    days = np.arange(day("2026-07-01"), day("2026-07-01") + 60)
    vals = 2.0 * np.exp(0.01 * np.arange(60))  # steady +1% a day
    s = Series("up", "g", days, vals)
    origin, ch = int(days[-1]), Changes([s])
    flat = forecast(ForecasterConfig(), s, ch, origin, 3)
    mom = forecast(ForecasterConfig(momentum=0.5), s, ch, origin, 3)
    shift = 0.01 * (0.5 + 0.25 + 0.125)
    assert mom[1] == pytest.approx(flat[1] * np.exp(shift))
    assert ForecasterConfig().momentum == 0.0  # default keeps starter parity


def test_october_never_decides_keep_or_kill(memory, monkeypatch):
    from pacific_hack.agents import Evaluator, Proposer

    # The candidate wins October by a mile but loses September: it must be killed.
    monkeypatch.setattr(
        "pacific_hack.agents.backtest_batch",
        lambda configs, runner, seed: [
            {"skill_train": 0.2, "skill_val": 0.2, "skill_heldout": 0.1, "steps": 1},
            {"skill_train": 0.2, "skill_val": 0.19, "skill_heldout": 0.9, "steps": 1},
        ],
    )
    proposals = Proposer(memory.bound("proposer")).propose_batch(ForecasterConfig(), k=1)
    (decision,) = Evaluator(memory.bound("evaluator")).evaluate_batch(proposals, ForecasterConfig())
    assert decision["status"] == "killed"


def test_critic_toggles_one_param_on_the_current_config(memory, monkeypatch):
    seen = []
    monkeypatch.setattr(
        "pacific_hack.agents.backtest_batch",
        lambda configs, runner, seed: seen.append(configs)
        or [{"skill_train": 0, "skill_val": 0.1, "skill_heldout": 0, "steps": 1}] * 2,
    )
    kw = dict(idea_id="idea-001", change={"param": "band_scale", "value": 0.8},
              previous={"param": "band_scale", "value": 1.0}, fact_id=hypothesis_fact_id("idea-001"))
    memory.append(ledger.make_entry("decision", "kept", "evaluator", market_date=TRAIN_END, **kw))
    current = ForecasterConfig(half_life_days=7.0, band_scale=0.8)
    Critic(memory.bound("critic"), n_alt_seeds=1).review_pending(current)
    before, after = seen[0]
    assert before == ForecasterConfig(half_life_days=7.0, band_scale=1.0)
    assert after == current
