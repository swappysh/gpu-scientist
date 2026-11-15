"""Replay a loop run's kept changes in order and score each one alone.

    uv run python scripts/keeps37.py results/loop_rounds.json

Prints, per keep, the change in Jul-Sep and September skill against the
config just before it (local runner, scored set). No October.
"""
import json
import sys

from pacific_hack.forecaster import ForecasterConfig
from pacific_hack.harness import backtest_batch

trace = json.load(open(sys.argv[1]))
keeps = [(r["round"], i) for r in trace["rounds"] for i in r["ideas"] if i["status"] == "kept"]
configs = [ForecasterConfig()]
for _, i in keeps:
    configs.append(configs[-1].updated(i["param"], i["value"]))
res = backtest_batch(configs)
print(f"# {sys.argv[1]}: each kept change scored against the config before it")
for (rnd, i), prev, cur in zip(keeps, res, res[1:]):
    print(f"round {rnd} {i['idea_id']} {i['param']}={i['value']}: "
          f"Jul-Sep {cur['skill_train'] - prev['skill_train']:+.4f}, September {cur['skill_val'] - prev['skill_val']:+.4f}")
print(f"end: Jul-Sep {res[-1]['skill_train']:+.4f}, September {res[-1]['skill_val']:+.4f}")
