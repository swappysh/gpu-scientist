"""Score the final config of a --trace log that stopped before its last step.

The loop writes the trace after every round; if it dies later (a network
outage while writing to past.dev), the rounds are kept but "final" is
missing. This scores the last round's config once, with the same harness
and world, and fills "final" in, marked as scored here.

    PACIFIC_SERIES=data/series_scored.npz uv run python scripts/finish_trace.py results/loop_rounds.json
"""
import json
import sys

from pacific_hack import harness
from pacific_hack.forecaster import ForecasterConfig

path = sys.argv[1]
t = json.loads(open(path).read())
if t.get("final"):
    sys.exit(f"{path} already has a final block")
last = t["rounds"][-1]
(final,) = harness.run_local([(last["config"], 7)])
(base,) = harness.run_local([(ForecasterConfig().to_dict(), 7)])
t["final"] = {
    "config": last["config"],
    "skill_train": final["skill_train"],
    "skill_val": final["skill_val"],
    "skill_heldout": final["skill_heldout"],
    "coverage_train": final["coverage_train"],
    "coverage_heldout": final["coverage_heldout"],
    "baseline_skill_heldout": base["skill_heldout"],
    "scored_by": f"scripts/finish_trace.py after round {last['round']} (the loop stopped on a network error)",
}
open(path, "w").write(json.dumps(t, indent=2) + "\n")
print(json.dumps(t["final"], indent=2))
