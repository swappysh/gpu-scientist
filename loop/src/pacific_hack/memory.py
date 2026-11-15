"""Shared memory for the agent loop.

All three agents talk to one `Memory` ledger:

    bound(identity)         -> a view of the same memory for one agent
    append(entry)           -> write one ledger entry (append-only facts)
    entries(as_of=None)     -> read back entries, optionally point-in-time
    search(query, k, as_of) -> small recall used by the critic/proposer

Two invariants the hackathon memory judges care about:

* No peeking: every entry carries `market_date` (the date the fact
  describes). Readers pass `as_of=` their forecast date, so facts about
  later prices cannot leak into an earlier read. Local backend filters;
  past.dev backend sends `queryTimestamp` on recall and stores the market
  date as the data point's `timestamp` (event time).
* Read boundary: entries may name `audience` (e.g. HOLDOUT_AUDIENCE for
  October holdout scores). Only identities in that audience read them, so
  the proposer sees kept/killed decisions, never holdout numbers.

Write volume stays small on purpose (tens of facts/day): past.dev ingests
sends sequentially. When a fact is revised (e.g. a hypothesis refuted by
the critic) the new entry reuses `fact_id`, so past.dev supersedes the old
claim (`artifact.supersededAt`) instead of piling up duplicates.

Backends:

* `JsonlMemory`   — append-only JSONL + flock; works offline now.
* `PastDevMemory` — past.dev Memory API (https://past.dev/docs/memory-api).
                    Needs env var `PAST_API_KEY` (a `past_sk_` project key).
                    Base URL https://api.past.dev/api/v1.

past.dev mapping: each ledger entry is one data point. `content` is an
English sentence (extraction produces useful memories); the full structured
entry is duplicated under `metadata.entry` so readers can reconstruct the
exact record from recall `sources[].metadata`. Entries without `audience`
are project-visible; each agent reads via its own `identity`
("pacific-proposer" etc.), satisfying the challenge: several agents write,
several read, and readers consume facts written by other agents.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Protocol

from . import ledger

PAST_API_BASE = os.environ.get("PAST_API_BASE", "https://api.past.dev/api/v1")
RETRIES = 10  # backoff 1, 2, 4, 8, 16, then 30 s: about 3 minutes before a network error surfaces
PAST_API_KEY_ENV = "PAST_API_KEY"

# The audience holding October holdout scores; only the critic reads it.
HOLDOUT_AUDIENCE = "holdout-scores"
AUDIENCES: dict[str, set[str]] = {HOLDOUT_AUDIENCE: {"critic"}}


# Every read and write this process makes through either backend, in order.
# The loop's trace and dashboard show it as the memory evidence.
ACCESS_LOG: list[dict] = []


def _log_write(entry: dict) -> None:
    ACCESS_LOG.append({
        "op": "write", "at": ledger.utcnow(), "agent": entry["agent"],
        "layer": entry.get("audience") or "public", "kind": entry["kind"],
        "status": entry["status"], "idea_id": entry.get("idea_id"),
    })


def _log_read(reader: str | None, as_of: str | None, entries: list[dict], query: str | None = None) -> None:
    authors: dict[str, int] = {}
    layers: dict[str, int] = {}
    for e in entries:
        authors[e["agent"]] = authors.get(e["agent"], 0) + 1
        layer = e.get("audience") or "public"
        layers[layer] = layers.get(layer, 0) + 1
    ACCESS_LOG.append({
        "op": "read", "at": ledger.utcnow(), "agent": reader or "loop", "as_of": as_of,
        "query": query, "facts": len(entries), "authors": authors, "layers": layers,
    })


def _visible(entry: dict, reader: str | None) -> bool:
    audience = entry.get("audience")
    if not audience:
        return True
    return reader in AUDIENCES.get(audience, set())


def _in_time(entry: dict, as_of: str | None) -> bool:
    if as_of is None:
        return True
    return (entry.get("market_date") or "") <= as_of


class Memory(Protocol):
    def bound(self, agent_name: str) -> "Memory": ...
    def append(self, entry: dict) -> None: ...
    def entries(self, as_of: str | None = None) -> list[dict]: ...
    def search(self, query: str, k: int = 10, as_of: str | None = None) -> list[dict]: ...


class JsonlMemory:
    """Local append-only JSONL ledger. The default, no-key backend."""

    def __init__(self, path: str, reader: str | None = None):
        self.path = path
        self.reader = reader
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        open(path, "a").close()

    def bound(self, agent_name: str) -> "JsonlMemory":
        return JsonlMemory(self.path, reader=agent_name)

    def append(self, entry: dict) -> None:
        import fcntl

        with open(self.path, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(ledger.entry_to_json(entry) + "\n")
            fcntl.flock(fh, fcntl.LOCK_UN)
        _log_write(entry)

    def _entries(self, as_of: str | None) -> list[dict]:
        with open(self.path) as fh:
            raw = [ledger.entry_from_json(line) for line in fh if line.strip()]
        visible = [e for e in raw if _visible(e, self.reader) and _in_time(e, as_of)]
        return ledger.latest_per_fact(visible)

    def entries(self, as_of: str | None = None) -> list[dict]:
        out = self._entries(as_of)
        _log_read(self.reader, as_of, out)
        return out

    def search(self, query: str, k: int = 10, as_of: str | None = None) -> list[dict]:
        terms = {t.lower() for t in query.split() if len(t) > 2}
        scored = []
        for e in self._entries(as_of):
            text = ledger.entry_to_json(e).lower()
            score = sum(text.count(t) for t in terms)
            if score:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = [e for _, e in scored[:k]]
        _log_read(self.reader, as_of, out, query)
        return out


class PastDevError(RuntimeError):
    pass


class PastDevMemory:
    """past.dev backend. Real HTTP, stdlib only; fails loudly without a key.

    TODO(kiss): once a project key exists (console https://app.past.dev ->
    API keys; hackathon code SFAIHACK500 buys 500k credits), export
    PAST_API_KEY and run `--memory past`. Verify on a small -n run first:
    ingestion is async and recall only sees completed sends.
    """

    def __init__(
        self,
        api_key: str | None = None,
        identity: str = "pacific-reader",
        _pending: list[str] | None = None,
        scope: str | None = None,
        reader: str | None = None,
    ):
        self.api_key = api_key or os.environ.get(PAST_API_KEY_ENV)
        if not self.api_key:
            raise PastDevError(
                f"no past.dev key: set {PAST_API_KEY_ENV} (past_sk_... project key "
                "from https://app.past.dev -> API keys). Hackathon: code SFAIHACK500 "
                "with 500,000 credits selected."
            )
        self.identity = identity
        # The agent name behind the identity ("critic"). Recall results are
        # filtered by audience and market date here too, so a private or
        # later fact never reaches an agent even if the server returned it.
        self.reader = reader
        # One project holds every run. A scope (e.g. "scored37") tags this
        # run's facts and filters reads to them, so ideas judged on another
        # series world don't count as history here.
        self.scope = scope
        self._pending_ingestions = _pending if _pending is not None else []
        self._ensured_audiences: set[str] = set()

    def bound(self, agent_name: str) -> "PastDevMemory":
        """A view of the same memory that recalls as this agent's identity,
        e.g. "pacific-critic", so reads are attributed per agent."""
        return PastDevMemory(
            api_key=self.api_key,
            identity=f"pacific-{agent_name}",
            _pending=self._pending_ingestions,
            scope=self.scope,
            reader=agent_name,
        )

    # -- HTTP plumbing ------------------------------------------------------

    def _call(self, method: str, path: str, body: dict | list | None = None) -> dict:
        req = urllib.request.Request(
            PAST_API_BASE + path,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(body).encode() if body is not None else None,
        )
        # Network blips (DNS, resets, 5xx, 429) are retried with backoff. A
        # re-sent ingest is safe: the data point id is fixed, so past.dev
        # supersedes the copy.
        for attempt in range(RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read()
                return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                if (exc.code >= 500 or exc.code == 429) and attempt < RETRIES:
                    time.sleep(min(2 ** attempt, 30))
                    continue
                detail = exc.read().decode(errors="replace")[:400]
                raise PastDevError(f"{method} {path} -> {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == RETRIES:
                    raise
                time.sleep(min(2 ** attempt, 30))

    def _wait(self, ingestion_id: str, timeout: float = 60.0) -> None:
        """Poll GET /ingest/{id} until completed/failed (polls are free)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self._call("GET", f"/ingest/{ingestion_id}")
            if status.get("status") == "completed":
                return
            if status.get("status") == "failed":
                raise PastDevError(f"ingest {ingestion_id} failed: {status.get('failure')}")
            time.sleep(2)

    def _ensure_audience(self, slug: str) -> None:
        """Create the audience once, with its member identities."""
        if slug in self._ensured_audiences:
            return
        members = AUDIENCES.get(slug)
        if members is None:
            raise PastDevError(f"audience {slug!r} has no member list in AUDIENCES")
        self._call(
            "PUT",
            f"/audiences/{slug}",
            {
                "kind": "fixed",
                "name": slug,
                "identities": [f"pacific-{m}" for m in members],
            },
        )
        self._ensured_audiences.add(slug)

    # -- Memory interface ---------------------------------------------------

    def append(self, entry: dict, wait: bool = False) -> None:
        # One data point per ledger entry. The data point `id` is the entry's
        # fact_id when present: a later entry with the same fact_id replaces
        # this data point, and its claims get supersededAt (that's how a
        # critic refutation supersedes a hypothesis instead of coexisting).
        if audience := entry.get("audience"):
            self._ensure_audience(audience)
        if self.scope:
            entry = {**entry, "scope": self.scope}
        key = entry.get("fact_id") or entry["id"]
        market_date = entry.get("market_date") or entry["timestamp"]
        if "T" not in market_date:
            market_date += "T00:00:00Z"
        body = {
            "id": f"ledger:{self.scope}:{key}" if self.scope else f"ledger:{key}",
            "content": (f"Run {self.scope}. " if self.scope else "") + ledger.render_entry_text(entry),
            "label": f"pacific-hack {entry['kind']}",
            "timestamp": market_date,  # event time = the date the fact describes
            "metadata": {"entry": entry, "kind": entry["kind"], "agent": entry["agent"]},
        }
        if audience:
            body["audience"] = audience
        receipt = self._call("POST", "/ingest", body)
        _log_write(entry)
        if ingestion_id := receipt.get("ingestionId"):
            if wait:
                self._wait(ingestion_id)
            else:
                self._pending_ingestions.append(ingestion_id)

    def drain(self) -> None:
        """Wait for queued ingestions to complete (called before reads).
        past.dev processes a project's sends sequentially and recall only
        sees completed sends, so a read right after writes can lag."""
        while self._pending_ingestions:
            self._wait(self._pending_ingestions.pop())
        time.sleep(0.5)  # recall settles a moment after completion

    def _recall(self, query: str, as_of: str | None = None, level: str = "medium") -> list[dict]:
        # Recall ranks over the whole project and cannot filter by run, so the
        # scope leads both the content and the query to rank this run first.
        if self.scope:
            query = f"Run {self.scope}. {query}"
        body: dict = {"query": query, "identity": self.identity, "level": level, "limit": 200}
        if as_of is not None:
            # Point-in-time read: only facts true/known as of this market date.
            body["queryTimestamp"] = as_of if "T" in as_of else as_of + "T00:00:00Z"
        page = self._call("POST", "/recall", body)
        out = []
        for result in page.get("results", []):
            # Prefer the exact stored record from metadata; fall back to a
            # synthetic entry wrapping the returned document content.
            entry = None
            for src in result.get("sources", []):
                meta = src.get("metadata") or {}
                if isinstance(meta.get("entry"), dict):
                    entry = meta["entry"]
                    break
            out.append(
                entry
                or {
                    "id": f"recall:{result.get('id')}",
                    "kind": "note",
                    "status": "proposed",
                    "agent": "pastdev",
                    "idea_id": None,
                    "change": None,
                    "previous": None,
                    "scores": None,
                    "reason": result.get("content", ""),
                    "timestamp": result.get("occurredAt", ledger.utcnow()),
                    "market_date": result.get("occurredAt", ledger.utcnow())[:10],
                    "audience": None,
                    "fact_id": None,
                }
            )
        return [e for e in out if _visible(e, self.reader) and _in_time(e, as_of)]

    def entries(self, as_of: str | None = None) -> list[dict]:
        """All ledger entries visible to this identity. past.dev has no
        'list everything' route, so we recall with a few broad queries and
        dedupe by entry id."""
        self.drain()
        seen: dict[str, dict] = {}
        for q in (
            "experiment ledger hypothesis forecaster config change",
            "backtest result kept killed skill",
            "critic verdict refuted corroborated",
            "throughput steps per hour runner",
        ):
            for e in self._recall(q, as_of=as_of):
                if e.get("scope") == self.scope:
                    seen.setdefault(e["id"], e)
        ordered = sorted(seen.values(), key=lambda e: (e["timestamp"], e["id"]))
        out = ledger.latest_per_fact(ordered)
        _log_read(self.reader, as_of, out)
        return out

    def search(self, query: str, k: int = 10, as_of: str | None = None) -> list[dict]:
        self.drain()
        out = [e for e in self._recall(query, as_of=as_of) if e.get("scope") == self.scope][:k]
        _log_read(self.reader, as_of, out, query)
        return out


def make_memory(kind: str, path: str | None = None, scope: str | None = None) -> Memory:
    if kind == "jsonl":
        return JsonlMemory(path or "ledger.jsonl")  # a fresh file is its own scope
    if kind == "past":
        return PastDevMemory(scope=scope)
    raise ValueError(f"unknown memory backend {kind!r} (use 'jsonl' or 'past')")
