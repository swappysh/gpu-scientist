"""The three agents sharing one memory ledger.

- Proposer:  reads the ledger as of the forecast date, proposes a BATCH of
             one-parameter changes (rule-based; an LLM can replace
             `propose_batch` if it still writes `proposal` entries).
- Evaluator: backtests the batch through `harness.backtest_batch` (local or
             Modal), keeps a change only if it also improves held-out October
             skill. Holdout numbers go to a private entry; the public
             `decision` entry carries only kept/killed and Jul-Sep numbers.
- Critic:    the only reader of the holdout audience. Re-scores kept ideas on
             fresh synthetic worlds and writes refuted/corroborated. The
             public verdict reuses the hypothesis `fact_id`, so a refuted
             hypothesis is superseded (past.dev `supersededAt`).

Every batch also writes a `note` with runner, steps and steps-per-hour.
"""

from __future__ import annotations

import random
import sys
import time

from . import ledger
from .data import HELDOUT_END, TRAIN_END
from .forecaster import ForecasterConfig
from .harness import backtest_batch
from .llm_proposer import llm_candidates, schema_from_config
from .memory import HOLDOUT_AUDIENCE, Memory

# One change at a time: (param, value) pairs the proposer walks through.
MUTATIONS: list[tuple[str, object]] = [
    ("window_days", 90),
    ("window_days", 45),
    ("half_life_days", 30.0),
    ("half_life_days", 14.0),
    ("half_life_days", 7.0),
    ("band_scale", 0.8),
    ("band_scale", 1.25),
    ("drift_weight", 0.5),
    ("drift_weight", 1.0),
    ("pool_weight", 0.5),
    ("pool_weight", 1.0),
    ("min_samples", 10),
    ("min_samples", 40),
    ("momentum", 0.5),
    ("momentum", 0.65),
    ("momentum_fit", 0.5),
]

GOOD = ("kept", "corroborated")
BAD = ("killed", "refuted")


def hypothesis_fact_id(idea_id: str) -> str:
    return f"hyp-{idea_id}"


def run_batch_logged(
    memory: Memory,
    agent: str,
    configs: list[ForecasterConfig],
    runner: str,
    seed: int,
) -> list[dict]:
    """Call the harness seam and log runner + steps-per-hour to the ledger."""
    start = time.perf_counter()
    results = backtest_batch(configs, runner=runner, seed=seed)
    seconds = max(time.perf_counter() - start, 1e-9)
    steps = sum(r.get("steps", 1) for r in results)
    memory.append(
        ledger.make_entry(
            "note",
            "proposed",
            agent,
            market_date=TRAIN_END,
            scores={
                "runner": runner,
                "configs": len(configs),
                "steps": steps,
                "seconds": round(seconds, 3),
                "steps_per_hour": round(steps / seconds * 3600),
            },
            reason=f"{agent} backtest batch on the {runner} runner",
        )
    )
    return results


def _ideas(entries: list[dict]) -> dict[str, dict]:
    """Latest public entry per idea (proposal -> decision -> verdict decision)."""
    ideas: dict[str, dict] = {}
    for e in entries:
        if e.get("idea_id") and e.get("kind") in ("proposal", "decision"):
            ideas[e["idea_id"]] = e
    return ideas


class Proposer:
    name = "proposer"

    def __init__(
        self,
        memory: Memory,
        seed: int = 0,
        as_of: str = TRAIN_END,
        mode: str = "rule",
        field_schema: list[dict] | None = None,
        llm_client=None,
    ):
        if mode not in ("rule", "llm"):
            raise ValueError(f"unknown proposer mode {mode!r}")
        self.memory = memory
        self.rng = random.Random(seed)
        self.as_of = as_of  # forecast date: the proposer cannot read later facts
        self.mode = mode
        self.field_schema = field_schema  # default: schema_from_config(current)
        # Ideas this proposer wrote in this process: idea_id -> (param, value).
        # past.dev recall can miss a fact, so ids keep counting from here and
        # an idea we wrote counts as tried even when recall drops it.
        self.issued: dict[str, tuple] = {}
        self.llm_client = llm_client

    def propose_batch(self, current: ForecasterConfig, k: int = 3) -> list[dict]:
        """Write up to `k` proposals touching distinct params; [] when exhausted.

        In `llm` mode the model proposes; the rule-based proposer takes over if
        the key is missing, the call fails, or no valid candidate comes back.
        """
        entries = self.memory.entries(as_of=self.as_of)
        seen = set(_ideas(entries))
        missed = sorted(set(self.issued) - seen)
        print(f"proposer: ledger shows {len(seen)} of {len(self.issued)} ideas written so far"
              + (f" (missing {', '.join(missed)})" if missed else ""), file=sys.stderr)
        if self.mode == "llm":
            proposals = self._propose_llm(current, k, entries)
            if proposals:
                return proposals
        return self._propose_rule(current, k, entries)

    def _next_idea_id(self, entries: list[dict]) -> str:
        known = list(_ideas(entries)) + list(self.issued)
        n = max((int(i.rsplit("-", 1)[1]) for i in known if i.rsplit("-", 1)[-1].isdigit()), default=0)
        return f"idea-{n + 1:03d}"

    def _propose_llm(self, current: ForecasterConfig, k: int, entries: list[dict]) -> list[dict]:
        try:
            candidates = llm_candidates(
                current.to_dict(),
                self.field_schema or schema_from_config(current),
                entries,
                k,
                client=self.llm_client,
            )
        except Exception as exc:  # any failure -> rule-based fallback; never print the message (may echo a key)
            print(f"proposer: LLM unavailable ({type(exc).__name__}), using rules", file=sys.stderr)
            return []
        proposals = []
        for c in candidates:
            if (c["param"], c["value"]) in self.issued.values():
                continue
            idea_id = self._next_idea_id(entries)
            entry = ledger.make_entry(
                "proposal",
                "proposed",
                self.name,
                market_date=self.as_of,
                idea_id=idea_id,
                change={"param": c["param"], "value": c["value"]},
                previous={"param": c["param"], "value": getattr(current, c["param"])},
                reason=c["hypothesis"],
                fact_id=hypothesis_fact_id(idea_id),
            )
            self.memory.append(entry)
            self.issued[idea_id] = (entry["change"]["param"], entry["change"]["value"])
            proposals.append(entry)
        return proposals

    def _propose_rule(self, current: ForecasterConfig, k: int, entries: list[dict]) -> list[dict]:
        ideas = _ideas(entries)
        tried = {
            (i["change"]["param"], i["change"]["value"]) for i in ideas.values() if i.get("change")
        } | set(self.issued.values())
        # Learn from the ledger: params with kept/corroborated history rank
        # first, params with killed/refuted history rank last.
        param_score: dict[str, int] = {}
        for i in ideas.values():
            if i.get("change"):
                delta = 1 if i["status"] in GOOD else -1 if i["status"] in BAD else 0
                param_score[i["change"]["param"]] = param_score.get(i["change"]["param"], 0) + delta
        candidates = [
            m for m in MUTATIONS if m not in tried and getattr(current, m[0]) != m[1]
        ]
        self.rng.shuffle(candidates)
        candidates.sort(key=lambda m: -param_score.get(m[0], 0))

        proposals, used_params = [], set()
        for param, value in candidates:
            if param in used_params:
                continue
            used_params.add(param)
            idea_id = self._next_idea_id(entries)
            entry = ledger.make_entry(
                "proposal",
                "proposed",
                self.name,
                market_date=self.as_of,
                idea_id=idea_id,
                change={"param": param, "value": value},
                previous={"param": param, "value": getattr(current, param)},
                reason=f"param history score {param_score.get(param, 0):+d} from {len(ideas)} past idea(s)",
                fact_id=hypothesis_fact_id(idea_id),
            )
            self.memory.append(entry)
            self.issued[idea_id] = (entry["change"]["param"], entry["change"]["value"])
            proposals.append(entry)
            if len(proposals) == k:
                break
        return proposals


class Evaluator:
    name = "evaluator"

    def __init__(self, memory: Memory, runner: str = "local", seed: int = 7):
        self.memory = memory
        self.runner = runner
        self.seed = seed

    def evaluate_batch(self, proposals: list[dict], current: ForecasterConfig) -> list[dict]:
        """Backtest the whole batch in one harness call; returns public decisions.

        Keep rule: September skill (the dev gate slice) must strictly improve
        AND Jul-Sep skill must not regress. October never decides anything; it
        is logged privately and reported once at the end of a run. Each idea
        is scored against the pre-batch config.
        """
        if not proposals:
            return []
        candidates = [
            current.updated(p["change"]["param"], p["change"]["value"]) for p in proposals
        ]
        results = run_batch_logged(
            self.memory, self.name, [current, *candidates], self.runner, self.seed
        )
        base, cand_results = results[0], results[1:]
        decisions = []
        for proposal, cand in zip(proposals, cand_results):
            d_train = cand["skill_train"] - base["skill_train"]
            d_held = cand["skill_heldout"] - base["skill_heldout"]
            d_val = cand["skill_val"] - base["skill_val"]
            keep = d_val > 0 and d_train >= -0.005
            status = "kept" if keep else "killed"
            common = dict(
                agent=self.name,
                idea_id=proposal["idea_id"],
                change=proposal["change"],
                previous=proposal["previous"],
            )
            # Private: holdout numbers, readable by the critic only.
            self.memory.append(_private_result(status, cand, d_train, d_val, d_held, common))
            # Public: status + Jul-Sep numbers only. Reuses the hypothesis
            # fact_id, so it supersedes the `proposed` fact.
            decision = ledger.make_entry(
                "decision",
                status,
                market_date=TRAIN_END,
                scores={"skill_train": cand["skill_train"], "d_train": d_train},
                reason=(
                    "passed the Jul-Sep and September gates"
                    if keep
                    else "failed the Jul-Sep or September gate"
                ),
                fact_id=hypothesis_fact_id(proposal["idea_id"]),
                **common,
            )
            self.memory.append(decision)
            decisions.append(decision)
        return decisions


def _private_result(status: str, cand: dict, d_train: float, d_val: float, d_held: float, common: dict) -> dict:
    return ledger.make_entry(
        "result",
        status,
        market_date=HELDOUT_END,
        scores={
            "skill_train": cand["skill_train"],
            "skill_val": cand["skill_val"],
            "skill_heldout": cand["skill_heldout"],
            "d_train": d_train,
            "d_val": d_val,
            "d_heldout": d_held,
        },
        reason=f"delta train {d_train:+.4f}, September {d_val:+.4f}, heldout {d_held:+.4f}",
        audience=HOLDOUT_AUDIENCE,
        **common,
    )


class Critic:
    name = "critic"
    REFUTE_MARGIN = -0.02  # September delta worse than this on a fresh world => refute

    def __init__(self, memory: Memory, runner: str = "local", n_alt_seeds: int = 2):
        self.memory = memory
        self.runner = runner
        self.n_alt_seeds = n_alt_seeds

    def review_pending(self, current: ForecasterConfig | None = None) -> list[dict]:
        """Re-check every kept-but-unreviewed idea against `current` (the loop's
        config after the batch); returns the public verdict decisions."""
        current = current or ForecasterConfig()
        entries = self.memory.entries(as_of=HELDOUT_END)
        originals = {
            e["idea_id"]: e for e in entries if e["kind"] == "result" and e.get("idea_id")
        }
        verdicts = []
        for idea_id, idea in _ideas(entries).items():
            if idea["kind"] == "decision" and idea["status"] == "kept":
                verdicts.append(self._judge(idea, originals.get(idea_id), current))
        return verdicts

    def _judge(self, idea: dict, original: dict | None, current: ForecasterConfig) -> dict:
        change, previous = idea["change"], idea["previous"]
        # Toggle only this idea's param; every other kept change stays in place.
        before = current.updated(previous["param"], previous["value"])
        after = current.updated(change["param"], change["value"])
        deltas = []
        for alt in range(self.n_alt_seeds):
            base, cand = run_batch_logged(
                self.memory, self.name, [before, after], self.runner, seed=10_000 + alt
            )
            deltas.append(cand["skill_val"] - base["skill_val"])
        refuted = min(deltas) < self.REFUTE_MARGIN
        status = "refuted" if refuted else "corroborated"
        common = dict(
            agent=self.name, idea_id=idea["idea_id"], change=change, previous=previous
        )
        # Private evidence: alternate-world September deltas next to the evaluator's.
        self.memory.append(
            ledger.make_entry(
                "verdict",
                status,
                market_date=HELDOUT_END,
                scores={
                    "alt_val_deltas": deltas,
                    "original_d_val": (original or {}).get("scores", {}).get("d_val"),
                },
                reason=(
                    f"September delta on {len(deltas)} alternate world(s): "
                    + ", ".join(f"{d:+.4f}" for d in deltas)
                    + ("; does not generalize" if refuted else "; generalizes")
                ),
                audience=HOLDOUT_AUDIENCE,
                **common,
            )
        )
        # Public replacement fact: supersedes the kept hypothesis (same fact_id).
        decision = ledger.make_entry(
            "decision",
            status,
            market_date=TRAIN_END,
            reason=(
                "critic refuted: change does not generalize to fresh worlds"
                if refuted
                else "critic corroborated: change generalizes to fresh worlds"
            ),
            fact_id=hypothesis_fact_id(idea["idea_id"]),
            **common,
        )
        self.memory.append(decision)
        return decision
