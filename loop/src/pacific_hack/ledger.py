"""Shared experiment ledger entries.

Every agent (proposer, evaluator, critic) reads and writes these entries
through the `Memory` interface. The same schema is stored as a JSON line
locally and as one past.dev data point (full entry under `metadata.entry`)
so both backends carry identical information.

Kinds:
  proposal  public   a hypothesis: one config change
  decision  public   kept / killed / refuted / corroborated, no holdout numbers
  result    private  holdout (October) scores, readable only by HOLDOUT_AUDIENCE
  verdict   private  critic's evidence (alternate-world deltas), same audience
  note      public   baseline and throughput metrics (steps per hour, runner)

`market_date` is the market date a fact describes (YYYY-MM-DD). Readers pass
`as_of=` their forecast date so later facts cannot leak. `fact_id` is optional:
an entry that reuses an earlier entry's `fact_id` supersedes it.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

KINDS = ("proposal", "decision", "result", "verdict", "note")
STATUSES = ("proposed", "kept", "killed", "refuted", "corroborated")

_run_id = uuid.uuid4().hex[:6]  # keeps ids unique across runs sharing one ledger
_counter = 0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_entry(
    kind: str,
    status: str,
    agent: str,
    market_date: str,
    idea_id: str | None = None,
    change: dict | None = None,
    previous: dict | None = None,
    scores: dict | None = None,
    reason: str = "",
    audience: str | None = None,
    fact_id: str | None = None,
) -> dict:
    """Build one ledger entry. `change` = {"param": name, "value": x} (one change per idea)."""
    global _counter
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    _counter += 1
    return {
        "id": f"{kind}-{_run_id}-{_counter:04d}",
        "kind": kind,
        "status": status,
        "agent": agent,
        "idea_id": idea_id,
        "change": change,
        "previous": previous,
        "scores": scores,
        "reason": reason,
        "timestamp": utcnow(),
        "market_date": market_date,
        "audience": audience,
        "fact_id": fact_id,
    }


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    return str(value)


def render_entry_text(entry: dict) -> str:
    """Human-readable statement of the entry, used as past.dev `content`."""
    bits = [
        f"[{entry['kind']}/{entry['status']}]",
        f"agent={entry['agent']}",
        f"market_date={entry['market_date']}",
    ]
    if entry.get("idea_id"):
        bits.append(f"idea={entry['idea_id']}")
    if entry.get("change"):
        bits.append(f"set {entry['change']['param']}={entry['change']['value']}")
    if entry.get("scores"):
        bits.append(" ".join(f"{k}={_fmt(v)}" for k, v in entry["scores"].items()))
    if entry.get("reason"):
        bits.append(f"reason: {entry['reason']}")
    return "Experiment ledger entry. " + " | ".join(bits)


def entry_to_json(entry: dict) -> str:
    return json.dumps(entry, sort_keys=True)


def entry_from_json(line: str) -> dict:
    return json.loads(line)


def latest_per_fact(entries: list[dict]) -> list[dict]:
    """Keep only the newest revision of each `fact_id` (entries without one stay).

    Mirrors past.dev supersession: a later data point with the same id replaces
    the earlier one. The JSONL file itself keeps every revision as an audit trail.
    """
    latest: dict[str, dict] = {}
    for e in entries:
        key = e.get("fact_id") or e["id"]
        latest.pop(key, None)
        latest[key] = e
    return list(latest.values())
