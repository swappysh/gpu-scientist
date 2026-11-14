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
import time

from . import ledger
from .data import HELDOUT_END, TRAIN_END
from .forecaster import ForecasterConfig
from .harness import backtest_batch
from .memory import HOLDOUT_AUDIENCE, Memory

# One change at a time: (param, value) pairs the proposer walks through.
MUTATIONS: list[tuple[str, object]] = [
    ("lookback_days", 28),
    ("shrink_to_history", 0.2),
    ("shrink_to_history", 0.5),
    ("drift_per_day", -0.005),
    ("drift_per_day", 0.005),
    ("lookback_days", 7),
    ("spread_k", 3.0),
    ("spread_k", 10.0),
    ("lookback_days", 60),
    ("shrink_to_history", 0.8),
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

    def __init__(self, memory: Memory, seed: int = 0, as_of: str = TRAIN_END):
        self.memory = memory
        self.rng = random.Random(seed)
        self.as_of = as_of  # forecast date: the proposer cannot read later facts

    def propose_batch(self, current: ForecasterConfig, k: int = 3) -> list[dict]:
        """Write up to `k` proposals touching distinct params; [] when exhausted."""
        entries = self.memory.entries(as_of=self.as_of)
        ideas = _ideas(entries)
        tried = {
            (i["change"]["param"], i["change"]["value"]) for i in ideas.values() if i.get("change")
        }
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
            idea_id = f"idea-{len(ideas) + len(proposals) + 1:03d}"
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

        Keep rule: held-out October skill must strictly improve AND Jul-Sep
        skill must not regress (guards against fitting the holdout). Each idea
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
            keep = d_held > 0 and d_train >= -0.005
            status = "kept" if keep else "killed"
            common = dict(
                agent=self.name,
                idea_id=proposal["idea_id"],
                change=proposal["change"],
                previous=proposal["previous"],
            )
            # Private: holdout numbers, readable by the critic only.
            self.memory.append(_private_result(status, cand, d_train, d_held, common))
            # Public: status + Jul-Sep numbers only. Reuses the hypothesis
            # fact_id, so it supersedes the `proposed` fact.
            decision = ledger.make_entry(
                "decision",
                status,
                market_date=TRAIN_END,
                scores={"skill_train": cand["skill_train"], "d_train": d_train},
                reason=(
                    "passed the Jul-Sep and held-out gates"
                    if keep
                    else "failed the Jul-Sep or held-out gate"
                ),
                fact_id=hypothesis_fact_id(proposal["idea_id"]),
                **common,
            )
            self.memory.append(decision)
            decisions.append(decision)
        return decisions


def _private_result(status: str, cand: dict, d_train: float, d_held: float, common: dict) -> dict:
    return ledger.make_entry(
        "result",
        status,
        market_date=HELDOUT_END,
        scores={
            "skill_train": cand["skill_train"],
            "skill_heldout": cand["skill_heldout"],
            "d_train": d_train,
            "d_heldout": d_held,
        },
        reason=f"delta train {d_train:+.4f}, heldout {d_held:+.4f}",
        audience=HOLDOUT_AUDIENCE,
        **common,
    )


class Critic:
    name = "critic"
    REFUTE_MARGIN = -0.02  # heldout delta worse than this on a fresh world => refute

    def __init__(self, memory: Memory, runner: str = "local", n_alt_seeds: int = 2):
        self.memory = memory
        self.runner = runner
        self.n_alt_seeds = n_alt_seeds

    def review_pending(self) -> list[dict]:
        """Re-check every kept-but-unreviewed idea; returns the public verdict decisions."""
        entries = self.memory.entries(as_of=HELDOUT_END)
        originals = {
            e["idea_id"]: e for e in entries if e["kind"] == "result" and e.get("idea_id")
        }
        verdicts = []
        for idea_id, idea in _ideas(entries).items():
            if idea["kind"] == "decision" and idea["status"] == "kept":
                verdicts.append(self._judge(idea, originals.get(idea_id)))
        return verdicts

    def _judge(self, idea: dict, original: dict | None) -> dict:
        change, previous = idea["change"], idea["previous"]
        before = ForecasterConfig().updated(previous["param"], previous["value"])
        after = before.updated(change["param"], change["value"])
        deltas = []
        for alt in range(self.n_alt_seeds):
            base, cand = run_batch_logged(
                self.memory, self.name, [before, after], self.runner, seed=10_000 + alt
            )
            deltas.append(cand["skill_heldout"] - base["skill_heldout"])
        refuted = min(deltas) < self.REFUTE_MARGIN
        status = "refuted" if refuted else "corroborated"
        common = dict(
            agent=self.name, idea_id=idea["idea_id"], change=change, previous=previous
        )
        # Private evidence: alternate-world deltas next to the evaluator's holdout delta.
        self.memory.append(
            ledger.make_entry(
                "verdict",
                status,
                market_date=HELDOUT_END,
                scores={
                    "alt_heldout_deltas": deltas,
                    "original_d_heldout": (original or {}).get("scores", {}).get("d_heldout"),
                },
                reason=(
                    f"heldout delta on {len(deltas)} alternate world(s): "
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
