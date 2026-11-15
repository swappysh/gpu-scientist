"""Run the self-improving forecaster loop.

    python -m pacific_hack.run [--memory jsonl|past] [--runner local|modal]
                               [--ledger ledger.jsonl] [-n 3] [--batch 3] [--seed 7]
                               [--proposer rule|llm] [--trace results/loop_rounds.json]

Each round: the proposer reads the shared ledger and writes a batch of
`proposal` facts; the evaluator backtests the whole batch in one harness call
(`--runner modal` fans it out on Modal) and writes kept/killed; the critic
re-checks kept ideas on fresh worlds and writes refuted/corroborated. Refuted
ideas roll the config back.

--trace writes, per round, the loop's config with its Jul-Sep and September
skill and every idea's verdict (for the round-by-round chart). The agents
never read it; October appears once, for the final config.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import dashboard, harness, ledger
from .agents import Critic, Evaluator, Proposer
from .data import HELDOUT_END, TRAIN_END
from .forecaster import ForecasterConfig
from .memory import ACCESS_LOG, HOLDOUT_AUDIENCE, Memory, make_memory


def run(
    memory: Memory,
    rounds: int,
    seed: int,
    batch: int = 3,
    runner: str = "local",
    verbose: bool = True,
    proposer_mode: str = "rule",
    trace: str | None = None,
) -> ForecasterConfig:
    ACCESS_LOG.clear()  # this run's reads and writes only
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
        rounds_log = [_round_entry(0, config, base, [])]

        for r in range(rounds):
            proposals = proposer.propose_batch(config, k=batch)
            if not proposals:
                if verbose:
                    print("proposer: mutation space exhausted")
                break
            ideas = []
            for decision in evaluator.evaluate_batch(proposals, config):
                c = decision["change"]
                ideas.append({"idea_id": decision["idea_id"], "param": c["param"], "value": c["value"],
                              "status": decision["status"], "d_train": decision["scores"]["d_train"]})
                if decision["status"] == "kept":
                    config = config.updated(c["param"], c["value"])
                if verbose:
                    print(f"[round {r + 1}] {decision['idea_id']}: {c['param']}={c['value']} -> {decision['status']}")

            for verdict in critic.review_pending(config):
                if verbose:
                    print(f"    critic: {verdict['idea_id']} {verdict['status']}")
                for idea in ideas:
                    if idea["idea_id"] == verdict["idea_id"]:
                        idea["critic"] = verdict["status"]
                if verdict["status"] == "refuted":
                    prev = verdict["previous"]
                    config = config.updated(prev["param"], prev["value"])
            if trace:
                (cur,) = harness.backtest_batch([config], runner=runner, seed=seed)
                rounds_log.append(_round_entry(r + 1, config, cur, ideas))
                _write_trace(trace, proposer_mode, memory, runner, rounds_log)  # a crash keeps the rounds so far

        (final,) = harness.backtest_batch([config], runner=runner, seed=seed)
        if trace:
            _write_trace(trace, proposer_mode, memory, runner, rounds_log,
                         final={"config": config.to_dict(), "skill_train": final["skill_train"],
                                "skill_val": final["skill_val"], "skill_heldout": final["skill_heldout"],
                                "coverage_train": final["coverage_train"],
                                "coverage_heldout": final["coverage_heldout"],
                                "baseline_skill_heldout": base["skill_heldout"]})

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


def _write_trace(path: str, proposer_mode: str, memory: Memory, runner: str, rounds_log: list[dict],
                 final: dict | None = None) -> None:
    """Write the trace and, next to it, the dashboard (dashboard.html)."""
    out = {"proposer": proposer_mode, "memory": type(memory).__name__, "scope": getattr(memory, "scope", None),
           "runner": runner, "updated": ledger.utcnow()[:19].replace("T", " "),
           "rounds": rounds_log, "final": final, "memory_log": ACCESS_LOG}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")
    dashboard.write(path, Path(path).with_name("dashboard.html"))


def _round_entry(r: int, config: ForecasterConfig, res: dict, ideas: list[dict]) -> dict:
    """Jul-Sep and September skill only: October stays out of the per-round log."""
    return {"round": r, "config": config.to_dict(), "skill_train": res["skill_train"],
            "skill_val": res["skill_val"], "ideas": ideas}


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--memory", choices=["jsonl", "past"], default="jsonl")
    p.add_argument("--runner", choices=list(harness.RUNNERS), default="local")
    p.add_argument("--ledger", default="ledger.jsonl", help="path for the jsonl backend")
    p.add_argument("-n", "--rounds", type=int, default=3)
    p.add_argument("--batch", type=int, default=3, help="candidates per round")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--proposer", choices=["rule", "llm"], default="rule", help="llm needs OPENAI_API_KEY; falls back to rule")
    p.add_argument("--trace", help="write the round-by-round log (JSON) here")
    p.add_argument("--scope", help="past.dev: tag this run's facts and read only them (e.g. scored37)")
    args = p.parse_args(argv)
    memory = make_memory(args.memory, args.ledger, scope=args.scope)
    run(memory, args.rounds, args.seed, batch=args.batch, runner=args.runner, proposer_mode=args.proposer,
        trace=args.trace)


if __name__ == "__main__":
    main()
