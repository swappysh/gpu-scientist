"""Run the self-improving forecaster loop.

    python -m pacific_hack.run [--memory jsonl|past] [--runner local|modal]
                               [--ledger ledger.jsonl] [-n 3] [--batch 3] [--seed 7]
                               [--proposer rule|llm]

Each round: the proposer reads the shared ledger and writes a batch of
`proposal` facts; the evaluator backtests the whole batch in one harness call
(`--runner modal` fans it out on Modal) and writes kept/killed; the critic
re-checks kept ideas on fresh worlds and writes refuted/corroborated. Refuted
ideas roll the config back.
"""

from __future__ import annotations

import argparse
import json

from . import harness, ledger
from .agents import Critic, Evaluator, Proposer
from .data import HELDOUT_END, TRAIN_END
from .forecaster import ForecasterConfig
from .memory import HOLDOUT_AUDIENCE, Memory, make_memory


def run(
    memory: Memory,
    rounds: int,
    seed: int,
    batch: int = 3,
    runner: str = "local",
    verbose: bool = True,
    proposer_mode: str = "rule",
) -> ForecasterConfig:
    # One bound view per agent: reads are attributed (past.dev identity) and
    # filtered (holdout audience) per agent.
    proposer = Proposer(memory.bound("proposer"), seed=seed + 1, mode=proposer_mode)
    evaluator = Evaluator(memory.bound("evaluator"), runner=runner, seed=seed)
    critic = Critic(memory.bound("critic"), runner=runner)

    with harness.session(runner):
        config = ForecasterConfig()
        (base,) = harness.backtest_batch([config], runner=runner, seed=seed)
        # Public note: Jul-Sep only. The October number is private to the critic.
        memory.append(
            ledger.make_entry(
                "note",
                "proposed",
                "loop",
                market_date=TRAIN_END,
                scores={"skill_train": base["skill_train"]},
                reason=f"baseline config {json.dumps(config.to_dict())}",
            )
        )
        memory.append(
            ledger.make_entry(
                "result",
                "proposed",
                "loop",
                market_date=HELDOUT_END,
                scores={"skill_heldout": base["skill_heldout"]},
                reason="baseline held-out score",
                audience=HOLDOUT_AUDIENCE,
            )
        )
        if verbose:
            print(f"baseline  skill_train={base['skill_train']:+.4f} skill_heldout={base['skill_heldout']:+.4f}")

        for r in range(rounds):
            proposals = proposer.propose_batch(config, k=batch)
            if not proposals:
                if verbose:
                    print("proposer: mutation space exhausted")
                break
            for decision in evaluator.evaluate_batch(proposals, config):
                c = decision["change"]
                if decision["status"] == "kept":
                    config = config.updated(c["param"], c["value"])
                if verbose:
                    print(f"[round {r + 1}] {decision['idea_id']}: {c['param']}={c['value']} -> {decision['status']}")

            for verdict in critic.review_pending(config):
                if verbose:
                    print(f"    critic: {verdict['idea_id']} {verdict['status']}")
                if verdict["status"] == "refuted":
                    prev = verdict["previous"]
                    config = config.updated(prev["param"], prev["value"])

        (final,) = harness.backtest_batch([config], runner=runner, seed=seed)

    if verbose:
        print(f"final     config={json.dumps(config.to_dict())}")
        print(f"final     skill_train={final['skill_train']:+.4f} skill_heldout={final['skill_heldout']:+.4f}")
        counts: dict[str, int] = {}
        for e in memory.bound("critic").entries():
            if e["kind"] in ("proposal", "decision"):
                counts[e["status"]] = counts.get(e["status"], 0) + 1
        print(f"ideas     {counts}")
        for e in memory.bound("critic").entries():
            if e["kind"] == "note" and e["agent"] != "loop":
                s = e["scores"]
                print(f"throughput {e['agent']}: {s['runner']} {s['steps']} steps in {s['seconds']}s = {s['steps_per_hour']:,} steps/hour")
    return config


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--memory", choices=["jsonl", "past"], default="jsonl")
    p.add_argument("--runner", choices=list(harness.RUNNERS), default="local")
    p.add_argument("--ledger", default="ledger.jsonl", help="path for the jsonl backend")
    p.add_argument("-n", "--rounds", type=int, default=3)
    p.add_argument("--batch", type=int, default=3, help="candidates per round")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--proposer", choices=["rule", "llm"], default="rule", help="llm needs OPENAI_API_KEY; falls back to rule")
    args = p.parse_args(argv)
    memory = make_memory(args.memory, args.ledger)
    run(memory, args.rounds, args.seed, batch=args.batch, runner=args.runner, proposer_mode=args.proposer)


if __name__ == "__main__":
    main()
