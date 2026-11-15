"""Live check of the read boundary on past.dev itself. Needs PAST_API_KEY;
skipped otherwise. Writes two facts under a fresh scope, then recalls as
each agent straight from the server, with no client-side filter."""

import os
import time
import uuid

import pytest

from pacific_hack import ledger
from pacific_hack.data import HELDOUT_END, TRAIN_END
from pacific_hack.memory import HOLDOUT_AUDIENCE, PastDevMemory

pytestmark = pytest.mark.skipif(not os.environ.get("PAST_API_KEY"), reason="needs PAST_API_KEY")


def server_ids(mem: PastDevMemory, query: str, as_of: str | None = None) -> set[str]:
    body = {"query": query, "identity": mem.identity, "level": "medium"}
    if as_of:
        body["queryTimestamp"] = as_of + "T00:00:00Z"
    page = mem._call("POST", "/recall", body)
    ids = set()
    for result in page.get("results", []):
        for src in result.get("sources", []):
            entry = (src.get("metadata") or {}).get("entry")
            if isinstance(entry, dict) and entry.get("scope") == mem.scope:
                ids.add(entry["id"])
    return ids


def test_server_enforces_audience_and_market_date():
    evaluator = PastDevMemory(scope=f"livetest-{uuid.uuid4().hex[:8]}").bound("evaluator")
    public = ledger.make_entry("decision", "kept", "evaluator", market_date=TRAIN_END,
                               scores={"d_train": 0.01}, reason="live boundary test, public")
    private = ledger.make_entry("result", "kept", "evaluator", market_date=HELDOUT_END,
                                scores={"skill_heldout": 0.13}, reason="live boundary test, private",
                                audience=HOLDOUT_AUDIENCE)
    evaluator.append(public, wait=True)
    evaluator.append(private, wait=True)
    time.sleep(2)  # recall settles a moment after ingestion completes

    query = "live boundary test kept result decision"
    critic = evaluator.bound("critic")
    assert server_ids(critic, query) >= {public["id"], private["id"]}
    for name in ("proposer", "evaluator"):
        seen = server_ids(evaluator.bound(name), query)
        assert public["id"] in seen, name
        assert private["id"] not in seen, name

    # Point-in-time: as of the end of Jul-Sep, the October-dated fact is not
    # eligible, even for the critic.
    assert private["id"] not in server_ids(critic, query, as_of=TRAIN_END)
    assert public["id"] in server_ids(critic, query, as_of=TRAIN_END)
