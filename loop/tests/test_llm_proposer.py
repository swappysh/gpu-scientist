"""LLM proposer tests: mocked OpenAI client, no network, no keys."""

import json
from types import SimpleNamespace

import pytest

from pacific_hack import ledger
from pacific_hack.agents import Evaluator, Proposer
from pacific_hack.data import HELDOUT_END, TRAIN_END
from pacific_hack.forecaster import ForecasterConfig
from pacific_hack.llm_proposer import (
    DEFAULT_MODEL,
    llm_candidates,
    public_history,
    schema_from_config,
)
from pacific_hack.memory import HOLDOUT_AUDIENCE, JsonlMemory
from pacific_hack.run import run


class FakeClient:
    """Mimics client.chat.completions.create(...) and records every call."""

    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def cand(param, value, hypothesis="a one-line hypothesis"):
    return {"param": param, "value": value, "hypothesis": hypothesis}


@pytest.fixture
def memory(tmp_path):
    return JsonlMemory(str(tmp_path / "ledger.jsonl"))


def proposer(memory, client, **kw):
    return Proposer(memory.bound("proposer"), mode="llm", llm_client=client, **kw)


def test_valid_llm_output_becomes_proposals(memory):
    client = FakeClient({"candidates": [
        cand("window_days", 21, "a shorter window tracks regime changes"),
        cand("band_scale", 1.5, "wider bands"),
    ]})
    out = proposer(memory, client).propose_batch(ForecasterConfig(), k=3)
    assert [(p["change"]["param"], p["change"]["value"]) for p in out] == [
        ("window_days", 21), ("band_scale", 1.5)]
    assert out[0]["reason"] == "a shorter window tracks regime changes"
    assert out[0]["previous"] == {"param": "window_days", "value": 0}
    assert out[0]["kind"] == "proposal" and out[0]["fact_id"] == f"hyp-{out[0]['idea_id']}"
    assert len(memory.entries()) == 2  # written to the shared ledger
    call = client.calls[0]
    assert call["model"] == DEFAULT_MODEL
    assert call["response_format"]["json_schema"]["strict"] is True


def test_model_comes_from_env(memory, monkeypatch):
    monkeypatch.setenv("PROPOSER_MODEL", "my-model")
    client = FakeClient({"candidates": [cand("band_scale", 1.5)]})
    proposer(memory, client).propose_batch(ForecasterConfig())
    assert client.calls[0]["model"] == "my-model"


def test_invalid_and_duplicate_candidates_are_dropped(memory):
    cfg = ForecasterConfig()
    # An earlier idea already tried window_days=28 (killed).
    memory.append(ledger.make_entry(
        "decision", "killed", "evaluator", TRAIN_END, idea_id="idea-001",
        change={"param": "window_days", "value": 28}, previous={"param": "window_days", "value": 0},
        scores={"skill_train": 0.1, "d_train": -0.01}, reason="failed the gate",
        fact_id="hyp-idea-001"))
    client = FakeClient({"candidates": [
        cand("window_days", 28),              # already tried
        cand("bogus_field", 1),               # unknown field
        cand("half_life_days", 150.0),        # out of range
        cand("window_days", 10.5),            # int field, fractional value
        cand("band_scale", "wide"),           # wrong type
        cand("pool_weight", 0.0),             # no-op (equals current)
        cand("drift_weight", 0.5, "  "),      # empty hypothesis
        cand("drift_weight", 0.25),           # valid
        cand("drift_weight", 0.5),            # second change to the same param
        cand("half_life_days", 14.0),         # valid
    ]})
    out = proposer(memory, client).propose_batch(cfg, k=5)
    assert [(p["change"]["param"], p["change"]["value"]) for p in out] == [
        ("drift_weight", 0.25), ("half_life_days", 14.0)]
    assert out[0]["idea_id"] == "idea-002"  # continues the ledger numbering


def test_choices_schema_is_enforced():
    schema = [{"name": "model", "type": "str", "choices": ["a", "b"]}]
    client = FakeClient({"candidates": [cand("model", "c"), cand("model", "b")]})
    out = llm_candidates({"model": "a"}, schema, [], 3, client=client)
    assert [c["value"] for c in out] == ["b"]


def test_holdout_numbers_never_reach_the_prompt(memory):
    secret = 0.987654
    memory.append(ledger.make_entry(
        "decision", "kept", "evaluator", TRAIN_END, idea_id="idea-001",
        change={"param": "window_days", "value": 28}, previous={"param": "window_days", "value": 0},
        scores={"skill_train": 0.25, "d_train": 0.01}, reason="passed the Jul-Sep and held-out gates",
        fact_id="hyp-idea-001"))
    memory.append(ledger.make_entry(
        "result", "kept", "evaluator", HELDOUT_END, idea_id="idea-001",
        change={"param": "window_days", "value": 28},
        scores={"skill_heldout": secret, "d_heldout": secret}, audience=HOLDOUT_AUDIENCE))
    client = FakeClient({"candidates": [cand("band_scale", 1.5)]})
    proposer(memory, client).propose_batch(ForecasterConfig())
    prompt = json.dumps(client.calls[0]["messages"])
    assert "0.25" in prompt and "passed the Jul-Sep" in prompt  # public history is there
    assert str(secret) not in prompt and "d_heldout" not in prompt and "skill_heldout" not in prompt


def test_public_history_guards_against_audience_entries_even_if_memory_leaks():
    leaked = ledger.make_entry(
        "decision", "kept", "evaluator", TRAIN_END, idea_id="idea-009",
        change={"param": "band_scale", "value": 3.0}, scores={"skill_heldout": 0.55},
        audience=HOLDOUT_AUDIENCE)
    public = ledger.make_entry(
        "decision", "kept", "evaluator", TRAIN_END, idea_id="idea-001",
        change={"param": "band_scale", "value": 2.0},
        scores={"skill_train": 0.2, "d_train": 0.01, "skill_heldout": 0.77}, reason="ok")
    history = public_history([leaked, public])
    assert [h["idea_id"] for h in history] == ["idea-001"]
    assert "skill_heldout" not in history[0] and "0.77" not in json.dumps(history)


@pytest.mark.parametrize("client", [
    FakeClient(error=RuntimeError("boom sk-secret")),
    FakeClient("not json"),
    FakeClient({"candidates": [cand("bogus", 1)]}),
    FakeClient({"candidates": []}),
], ids=["api-error", "bad-json", "nothing-valid", "empty"])
def test_fallback_to_rule_proposer(memory, client, capsys):
    out = proposer(memory, client).propose_batch(ForecasterConfig(), k=3)
    assert out and all("param history score" in p["reason"] for p in out)  # rule-based reasons
    assert "sk-secret" not in capsys.readouterr().err  # exception text is never printed


def test_fallback_when_key_is_missing(memory, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = Proposer(memory.bound("proposer"), mode="llm").propose_batch(ForecasterConfig(), k=2)
    assert out and all("param history score" in p["reason"] for p in out)


def test_full_loop_with_llm_mode_and_no_key(memory, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    run(memory, rounds=1, seed=7, proposer_mode="llm", verbose=False)
    # proposals are superseded by the evaluator's decisions (same fact_id)
    assert any(e["kind"] == "decision" and e["idea_id"] for e in memory.entries())


def test_custom_field_schema_is_used(memory):
    schema = [{"name": "window_days", "type": "int", "min": 5, "max": 20}]
    client = FakeClient({"candidates": [cand("window_days", 40), cand("window_days", 18)]})
    out = proposer(memory, client, field_schema=schema).propose_batch(ForecasterConfig())
    assert [p["change"]["value"] for p in out] == [18]
    assert json.loads(client.calls[0]["messages"][1]["content"])["field_schema"] == schema


def test_default_schema_covers_every_config_field():
    names = {s["name"] for s in schema_from_config(ForecasterConfig())}
    assert names == set(ForecasterConfig().to_dict())
