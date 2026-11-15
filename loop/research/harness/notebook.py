"""Read the shared notebook: LESSONS.md, then every researcher's rows (local copy + past.dev scope research-v8).

    cd loop && .venv/bin/python research/harness/notebook.py [--past]

Prints the shared rows (all agents) so you can skip ideas already tried.
--past also recalls the same facts from past.dev (slower; the local copy is the full list).
"""
import sys

from run import HEADER, LESSONS, SCOPE, SHARED  # noqa: E402

if LESSONS.exists():
    print("== LESSONS.md ==\n" + LESSONS.read_text() + "== tries ==")
rows = {}
if SHARED.exists():
    for ln in SHARED.read_text().splitlines()[1:]:
        r = dict(zip(HEADER, ln.split("\t")))
        rows[(r["agent"], r["commit"])] = r  # a later lesson row replaces the first one
for r in rows.values():
    print("\t".join(r.get(k, "") for k in HEADER))
if "--past" in sys.argv:
    from pacific_hack.memory import PastDevMemory

    for e in PastDevMemory(scope=SCOPE).bound("reader").entries():
        print(f"[past.dev] {e.get('agent')} {e.get('idea_id')} {e.get('status')} {e.get('scores')} {e.get('reason')}")
