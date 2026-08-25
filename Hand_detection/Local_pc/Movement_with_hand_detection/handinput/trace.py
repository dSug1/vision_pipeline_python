"""Write live action events to a file -- `HANDINPUT_TRACE=1`.

⭐ WHY THIS IS PART OF THE PACKAGE AND NOT OF EITHER TOOL. Both tools need it, so
by N6 it is imported rather than copied. And it is the only way to get conformance
traces off REAL hands: `conformance/generate_traces.py` scripts the state machine
deterministically, but it cannot produce measured orientations, real coast timings
or the ragged frame intervals a webcam actually delivers.

    set HANDINPUT_TRACE=1                 turn it on (either tool)
    set HANDINPUT_TRACE_TAG=<name>        file-name suffix

⚠⚠ AN ENVIRONMENT VARIABLE, NOT A CLI FLAG, for the same reason `VISION_RECORD`
is one: production is launched `PythonApp_Main -> Launcher -> Client`, so a flag
would need plumbing through three processes while an env var is inherited free.

⚠ ONE LINE PER EVENT, FLUSHED PERIODICALLY, NEVER BUFFERED TO EXIT. Production has
no clean shutdown path -- these sessions end with the window's X button -- and a
buffered trace would be lost exactly when it was most wanted.

⚠ OFF COSTS NOTHING: with the variable unset, `sink()` returns None and the tools
never build a context.
"""
import atexit
import json
import os
from datetime import datetime

# ⭐ Traces prefer the capture drive, matching where every other artifact of a
# session goes, but they must never BLOCK a run: an unreachable E: falls back to
# a local folder and says so. A trace is a dev artifact, not a recording.
_PREFERRED_ROOT = r"E:\Python\Recordings for vision_pipeline\handinput_traces"
_LOCAL_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "handinput_traces")

_state = {"fh": None, "n": 0, "path": None}


def enabled():
    return os.environ.get("HANDINPUT_TRACE") == "1"


def _open():
    tag = os.environ.get("HANDINPUT_TRACE_TAG", "trace")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    for root in (_PREFERRED_ROOT, _LOCAL_ROOT):
        try:
            os.makedirs(root, exist_ok=True)
            path = os.path.join(root, "%s_%s.jsonl" % (stamp, tag))
            fh = open(path, "w", encoding="utf-8")
        except OSError:
            continue
        _state.update(fh=fh, path=path, n=0)
        print("[handinput] TRACING -> %s" % path)
        atexit.register(close)
        return True
    print("[handinput] cannot open a trace file; continuing WITHOUT tracing")
    os.environ["HANDINPUT_TRACE"] = "0"
    return False


def sink(source=""):
    """The callable to assign to `HandInput.trace_sink`, or None when off."""
    if not enabled():
        return None
    if _state["fh"] is None and not _open():
        return None
    header = {"_meta": {"source": source, "schema": 1}}
    _state["fh"].write(json.dumps(header) + "\n")

    def _write(ctx):
        fh = _state["fh"]
        if fh is None:
            return
        fh.write(json.dumps(ctx.as_dict()) + "\n")
        _state["n"] += 1
        if _state["n"] % 200 == 0:
            fh.flush()

    return _write


def close():
    if _state["fh"] is None:
        return
    try:
        _state["fh"].close()
        print("[handinput] wrote %d events to %s" % (_state["n"], _state["path"]))
    except Exception:
        pass
    finally:
        _state["fh"] = None
