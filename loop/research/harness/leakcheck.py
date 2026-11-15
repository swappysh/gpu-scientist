"""Leak review of forecaster_agent.py before it is scored. Read-only.

Flags code that could see past the origin or outside the history it is given:
file/network/process access, frame or garbage-collector tricks, hardcoded
dates or day ordinals, and hardcoded scored-series ids. The worker also
blocks file, network and process access at run time; this catches it early
and names the line.
"""

from __future__ import annotations

import re

BANNED = [
    (r"\bopen\s*\(", "opens a file"),
    (r"\b(np|numpy)\s*\.\s*(load|fromfile|loadtxt|genfromtxt|memmap)\b", "reads a data file"),
    (r"\bread_(csv|parquet|json|table)\b", "reads a data file"),
    (r"^\s*(import|from)\s+(os|sys|pathlib|io|subprocess|socket|urllib|requests|http|shutil|glob|"
     r"inspect|gc|ctypes|importlib|builtins|pickle|marshal|multiprocessing|threading|signal|tempfile|"
     r"pacific_hack|harness)\b", "imports a module that reaches outside the history"),
    (r"__import__|\beval\s*\(|\bexec\s*\(|\bcompile\s*\(|\bglobals\s*\(|\bvars\s*\(", "dynamic code or scope access"),
    (r"_getframe|f_back|f_locals|f_globals|__globals__|__builtins__|__subclasses__|tb_frame", "frame or interpreter tricks"),
    (r"['\"]20\d\d-\d\d", "hardcoded date (use history.origin and the rows you are given)"),
    (r"\b7[34]\d{4}\b", "hardcoded day ordinal (use history.origin)"),
]


def check(text: str, scored_ids: set[str] | None = None) -> list[str]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        for pat, why in BANNED:
            if re.search(pat, code):
                out.append(f"line {i}: {why}")
    if scored_ids is None:
        from .core import DEV_NPZ, load

        w = load(DEV_NPZ)
        scored_ids = {s for s, sc in zip(w.sids, w.scored) if sc}
    for sid in scored_ids:
        if sid in text:
            out.append(f"hardcoded series id {sid}")
    return out
