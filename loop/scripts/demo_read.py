"""One agent reads what another wrote, on past.dev, live.

    ./demo_read.sh              # fresh scope: evaluator writes, proposer and critic read
    ./demo_read.sh scored37-d   # read a finished loop run's ledger as the proposer

Needs PAST_API_KEY. Writes two facts per fresh run (a few credits).
"""
import sys
import time

from pacific_hack import ledger
from pacific_hack.data import HELDOUT_END, TRAIN_END
from pacific_hack.memory import HOLDOUT_AUDIENCE, PastDevMemory


def show(entries, indent="    "):
    if not entries:
        print(indent + "(nothing)")
    for e in entries:
        private = f", audience {e['audience']}" if e.get("audience") else ""
        print(f"{indent}written by {e['agent']}, dated {e['market_date']}{private}")
        print(f"{indent}  {ledger.render_entry_text(e).removeprefix('Experiment ledger entry. ')}")


def read_run(scope):
    proposer = PastDevMemory(scope=scope).bound("proposer")
    entries = [e for e in proposer.entries(as_of=TRAIN_END) if e["agent"] != "proposer"]
    print(f"proposer ({proposer.identity}) reads run {scope} as of {TRAIN_END}:")
    print(f"  {len(entries)} facts written by other agents")
    show(entries[:8])


def fresh():
    scope = time.strftime("demo-%Y%m%dT%H%M%S", time.gmtime())
    evaluator = PastDevMemory(scope=scope).bound("evaluator")
    public = ledger.make_entry(
        "decision", "kept", "evaluator", market_date=TRAIN_END, idea_id="idea-demo",
        change={"param": "half_life_days", "value": 14.0},
        scores={"skill_train": 0.120, "d_train": 0.024},
        reason="passed the Jul-Sep and September gates",
    )
    private = ledger.make_entry(
        "result", "kept", "evaluator", market_date=HELDOUT_END, idea_id="idea-demo",
        change={"param": "half_life_days", "value": 14.0},
        scores={"skill_heldout": 0.131, "d_heldout": 0.009},
        reason="October numbers for the critic only",
        audience=HOLDOUT_AUDIENCE,
    )
    print(f"scope {scope}\n")
    print(f"1. evaluator ({evaluator.identity}) writes two facts:")
    show([public, private])
    evaluator.append(public, wait=True)
    evaluator.append(private, wait=True)
    time.sleep(2)  # recall settles a moment after ingestion completes

    proposer = evaluator.bound("proposer")
    print(f"\n2. proposer ({proposer.identity}) reads as of {TRAIN_END}:")
    show(proposer.entries(as_of=TRAIN_END))

    critic = evaluator.bound("critic")
    print(f"\n3. critic ({critic.identity}) reads as of {HELDOUT_END}:")
    show(critic.entries(as_of=HELDOUT_END))

    # The same read without the client-side filter: what past.dev itself returns.
    page = proposer._call("POST", "/recall", {
        "query": "experiment ledger decision result kept",
        "identity": proposer.identity, "level": "medium",
    })
    leaked = [
        s["metadata"]["entry"]["id"] for r in page.get("results", []) for s in r.get("sources", [])
        if (s.get("metadata") or {}).get("entry", {}).get("id") == private["id"]
    ]
    print(f"\n4. raw past.dev recall as {proposer.identity}, no client filter: "
          f"the October fact came back {len(leaked)} times")


if __name__ == "__main__":
    read_run(sys.argv[1]) if len(sys.argv) > 1 else fresh()
