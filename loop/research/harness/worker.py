"""Worker process: runs the researcher's forecast() on per-origin history only.

It imports forecaster_agent.py, then blocks file, network and process access
for the rest of its life (a Python audit hook cannot be removed). After that
the only data it ever holds is what the harness sends: series cut at each
origin. Import every module you need at the top of forecaster_agent.py; a
lazy import inside forecast() opens a file and is refused.
"""

from __future__ import annotations

import importlib.util
import sys
import traceback

BLOCKED = ("open", "os.listdir", "os.scandir", "os.system", "os.exec", "os.posix_spawn", "os.spawn",
           "os.fork", "os.forkpty", "subprocess.Popen", "socket.", "ctypes.", "urllib.", "shutil.",
           "os.chdir", "glob.glob", "sys._getframe", "sys._current_frames", "gc.get_objects",
           "gc.get_referrers", "gc.get_referents", "object.__getattr__")


def _hook(event, args):
    if event.startswith(BLOCKED):
        if event == "object.__getattr__" and args and args[1] not in ("f_back", "f_locals", "f_globals"):
            return
        raise PermissionError(f"forecaster_agent may not use {event} (only the history it is given)")


def main(conn, agent_file: str) -> None:
    try:
        spec = importlib.util.spec_from_file_location("forecaster_agent", agent_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = mod.forecast
        from .core import History  # noqa: F401  (loaded before the lock)
    except BaseException:  # noqa: BLE001
        conn.send(("error", "import failed:\n" + traceback.format_exc()[-1500:]))
        return
    sys.addaudithook(_hook)
    conn.send(("ready",))
    while True:
        msg = conn.recv()
        if msg[0] == "stop":
            return
        _, origin, series, catalog, reqs = msg
        hist = History(origin=origin, series=series, catalog=catalog)
        try:
            out = [tuple(fn(hist, catalog[s], origin, h)) for s, h in reqs]
        except BaseException:  # noqa: BLE001
            conn.send(("error", f"forecast raised at origin {hist.origin_date}:\n" + traceback.format_exc()[-1500:]))
            return
        conn.send(("ok", out))
