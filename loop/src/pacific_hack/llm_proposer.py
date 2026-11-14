"""LLM candidate generator behind `Proposer.propose_batch`.

The model sees only: the current config, the field schema, and the public
ledger history (proposal/decision entries with no `audience`, and only their
Jul-Sep numbers). Holdout numbers are never put in the prompt: the memory read
boundary already hides them from the proposer, and `public_history` allow-lists
fields as a second guard.

`llm_candidates` raises on any failure (no key, API error, bad JSON); the
caller falls back to the rule-based proposer.

Field schema: a list of {"name", "type": "int"|"float"|"str", and either
"min"/"max" or "choices"}. `schema_from_config` builds one for
`ForecasterConfig`; pass your own for the real step-model config fields.
"""

from __future__ import annotations

import json
import os

DEFAULT_MODEL = "gpt-5-mini"
MODEL_ENV = "PROPOSER_MODEL"

FieldSpec = dict

# Allowed range per ForecasterConfig field.
FORECASTER_RANGES: dict[str, tuple[float, float]] = {
    "window_days": (0, 120),
    "half_life_days": (0.0, 90.0),
    "band_scale": (0.5, 3.0),
    "drift_weight": (0.0, 1.0),
    "pool_weight": (0.0, 2.0),
    "min_samples": (2, 60),
}


def schema_from_config(config) -> list[FieldSpec]:
    """Field schema for ForecasterConfig (ranges in FORECASTER_RANGES)."""
    schema = []
    for name, (lo, hi) in FORECASTER_RANGES.items():
        kind = "int" if isinstance(getattr(config, name), int) else "float"
        schema.append({"name": name, "type": kind, "min": lo, "max": hi})
    return schema


def validate_value(spec: FieldSpec, value) -> bool:
    if "choices" in spec:
        return value in spec["choices"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return spec["type"] == "str" and isinstance(value, str)
    if spec["type"] == "int" and value != int(value):
        return False
    return spec["min"] <= value <= spec["max"]


def validate_candidates(
    raw: list, schema: list[FieldSpec], current: dict, tried: set[tuple]
) -> list[dict]:
    """Keep valid, new candidates; one per param (they are applied together).

    Dropped: unknown fields, out-of-range/wrong-type values, no-ops (value equals
    the current one), repeats of (param, value) already in the ledger, and a
    second change to a param already used in this batch.
    """
    specs = {s["name"]: s for s in schema}
    out, used = [], set()
    for c in raw:
        if not isinstance(c, dict):
            continue
        param, value, hypothesis = c.get("param"), c.get("value"), c.get("hypothesis")
        spec = specs.get(param)
        if spec is None or not validate_value(spec, value):
            continue
        if spec["type"] == "int":
            value = int(value)
        elif spec["type"] == "float":
            value = float(value)
        if value == current.get(param) or (param, value) in tried or param in used:
            continue
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            continue
        used.add(param)
        out.append({"param": param, "value": value, "hypothesis": hypothesis.strip()})
    return out


def public_history(entries: list[dict]) -> list[dict]:
    """Latest public verdict per idea: change, status, reason, Jul-Sep numbers only."""
    latest: dict[str, dict] = {}
    for e in entries:
        if e.get("audience") or e.get("kind") not in ("proposal", "decision"):
            continue
        if e.get("idea_id") and e.get("change"):
            latest[e["idea_id"]] = e
    history = []
    for idea_id, e in latest.items():
        scores = e.get("scores") or {}
        history.append(
            {
                "idea_id": idea_id,
                "param": e["change"]["param"],
                "value": e["change"]["value"],
                "status": e["status"],
                "reason": e.get("reason", ""),
                **{k: scores[k] for k in ("skill_train", "d_train") if k in scores},
            }
        )
    return history


def response_schema(schema: list[FieldSpec], k: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "maxItems": k,
                "items": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "enum": [s["name"] for s in schema]},
                        "value": {"anyOf": [{"type": "number"}, {"type": "string"}]},
                        "hypothesis": {"type": "string"},
                    },
                    "required": ["param", "value", "hypothesis"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }


def build_messages(current: dict, schema: list[FieldSpec], history: list[dict], k: int) -> list[dict]:
    system = (
        "You tune a GPU-price forecaster one config field at a time. Propose "
        f"up to {k} candidate changes. Each changes exactly ONE field to a value "
        "inside its allowed range/choices, touches a different field than the "
        "other candidates, comes with a one-line hypothesis, and must not repeat "
        "an idea already in the history. Learn from kept/corroborated vs "
        "killed/refuted ideas and their reasons."
    )
    user = json.dumps(
        {"current_config": current, "field_schema": schema, "history": history},
        sort_keys=True,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def make_client():
    """OpenAI client; the SDK reads OPENAI_API_KEY itself and raises if it is missing."""
    from openai import OpenAI

    return OpenAI(timeout=60, max_retries=1)


def llm_candidates(
    current: dict,
    schema: list[FieldSpec],
    entries: list[dict],
    k: int,
    client=None,
    model: str | None = None,
) -> list[dict]:
    """Ask the model for up to `k` {"param", "value", "hypothesis"} changes (validated)."""
    history = public_history(entries)
    tried = {(h["param"], h["value"]) for h in history}
    client = client or make_client()
    response = client.chat.completions.create(
        model=model or os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        messages=build_messages(current, schema, history, k),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "config_candidates",
                "strict": True,
                "schema": response_schema(schema, k),
            },
        },
    )
    raw = json.loads(response.choices[0].message.content)["candidates"]
    return validate_candidates(raw, schema, current, tried)[:k]
