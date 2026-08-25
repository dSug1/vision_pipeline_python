"""Generate `traces/*.json` -- END-TO-END action traces.

    .venv/Scripts/python.exe handinput/conformance/generate_traces.py

⭐⭐ THIS IS THE ARTIFACT THAT MAKES THE INPUT SYSTEM PORTABLE, and it is worth
more than the per-function vectors. The vectors pin arithmetic; a trace pins
BEHAVIOUR OVER TIME -- when `started` fires versus `performed`, that a button does
not re-fire while held, that a 150 ms coast does NOT cancel `tracked` but DOES
cancel `palm_pose`, that a lost track silently drops a rotation reference. Those
are the rules a port gets wrong, and none of them are visible in a single frame.

A trace is: a scripted list of observations (+ optional API commands), and the
exact event list they must produce. Replay it in any language, compare the lists.

⚠ THE SCRIPT IS SYNTHETIC AND ITS ROLE IS SPECIFICATION, NOT REALISM. It walks the
state machine through the transitions that matter, including ones a real session
would only reach by luck. ⭐ For traces off REAL hands, run either tool with
`HANDINPUT_TRACE=1` -- those are the same format and are the only place
`rotation_delta` sees measured orientations.
"""
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from handinput import HandInput                                   # noqa: E402
from handinput.contract import HandFrame, HandObservation         # noqa: E402

TRACES = os.path.join(_HERE, "traces")

try:
    from Resources import hand_state as HS                        # noqa: E402
except ImportError:
    import hand_state as HS                                       # noqa: E402


def _yaw_quat(deg):
    a = math.radians(deg) / 2.0
    return [round(math.cos(a), 12), 0.0, round(math.sin(a), 12), 0.0]


# ── the script ──────────────────────────────────────────────────────────────
# Each row: dt_ms, then per-slot facts. A slot that is absent this frame is
# simply not listed. `cmds` are calls a HOST would make on the API.
#
# ⚠ `tracking_state` is NOT scripted -- it is produced by running the real
# `HandStateTracker` over the presence column, so the trace cannot drift from
# the module that owns the coast.
SCRIPT = [
    {"dt": 0.0,  "hands": {}},
    {"dt": 40.0, "hands": {}},
    # hand enters: chirality still PROVISIONAL (U8), so no grab_ready
    {"dt": 40.0, "hands": {"Left": dict(pos=(300.0, 240.0), depth=(0.50, True),
                                        quat=_yaw_quat(0.0), confirmed=False)}},
    {"dt": 40.0, "hands": {"Left": dict(pos=(302.0, 241.0), depth=(0.50, True),
                                        quat=_yaw_quat(0.0), confirmed=False)}},
    # chirality confirms -> grab_ready starts
    {"dt": 40.0, "hands": {"Left": dict(pos=(305.0, 242.0), depth=(0.50, True),
                                        quat=_yaw_quat(2.0), confirmed=True)}},
    # still ready: a BUTTON must NOT re-fire while held
    {"dt": 40.0, "hands": {"Left": dict(pos=(308.0, 243.0), depth=(0.50, True),
                                        quat=_yaw_quat(4.0), confirmed=True)}},
    # back of hand, exception NOT armed -> rule 3 refuses -> grab_ready canceled
    {"dt": 40.0, "hands": {"Left": dict(pos=(310.0, 244.0), depth=(0.50, True),
                                        quat=_yaw_quat(6.0), confirmed=True,
                                        thumb_outward=True)}},
    # exception ARMED (released while thumb-outward) -> ready again
    {"dt": 40.0, "hands": {"Left": dict(pos=(312.0, 245.0), depth=(0.50, True),
                                        quat=_yaw_quat(8.0), confirmed=True,
                                        thumb_outward=True, snap_allowed=True)}},
    # depth FROZEN (4.2 DECISION 1) -> refuse, even though everything else is fine
    {"dt": 40.0, "hands": {"Left": dict(pos=(314.0, 246.0), depth=(0.50, False),
                                        quat=_yaw_quat(10.0), confirmed=True)}},
    # a host grabs something: freeze the rotation reference
    {"dt": 40.0, "cmds": [("set_rotation_reference", "Left")],
     "hands": {"Left": dict(pos=(316.0, 247.0), depth=(0.50, True),
                            quat=_yaw_quat(12.0), confirmed=True)}},
    {"dt": 40.0, "hands": {"Left": dict(pos=(318.0, 248.0), depth=(0.51, True),
                                        quat=_yaw_quat(25.0), confirmed=True)}},
    {"dt": 40.0, "hands": {"Left": dict(pos=(320.0, 249.0), depth=(0.52, True),
                                        quat=_yaw_quat(40.0), confirmed=True)}},
    # ⭐ DROPOUT INSIDE THE COAST: `tracked` must stay live, the POSE must not
    {"dt": 40.0, "hands": {}},
    {"dt": 40.0, "hands": {}},
    # a second hand appears while the first is coasting
    {"dt": 40.0, "hands": {"Right": dict(pos=(120.0, 300.0), depth=(0.45, True),
                                         quat=_yaw_quat(0.0), confirmed=True)}},
    # ⭐ COAST EXHAUSTED -> `tracked` cancels, and the rotation reference is dropped
    {"dt": 120.0, "hands": {"Right": dict(pos=(124.0, 302.0), depth=(0.45, True),
                                          quat=_yaw_quat(3.0), confirmed=True)}},
    # the left hand returns: everything re-STARTS, and rotation_delta stays dark
    # because its reference died with the track
    {"dt": 40.0, "hands": {"Left": dict(pos=(400.0, 200.0), depth=(0.60, True),
                                        quat=_yaw_quat(90.0), confirmed=True),
                           "Right": dict(pos=(126.0, 303.0), depth=(0.45, True),
                                         quat=_yaw_quat(5.0), confirmed=True)}},
    {"dt": 40.0, "hands": {"Left": dict(pos=(402.0, 201.0), depth=(0.60, True),
                                        quat=_yaw_quat(92.0), confirmed=True),
                           "Right": dict(pos=(128.0, 304.0), depth=(0.45, True),
                                         quat=_yaw_quat(6.0), confirmed=True)}},
]

SLOTS = ("Left", "Right")


def build():
    hi = HandInput()
    events = []
    hi.trace_sink = lambda ctx: events.append(ctx.as_dict())
    trackers = {s: HS.HandStateTracker() for s in SLOTS}
    rows, now = [], 0.0

    for step in SCRIPT:
        now += step["dt"]
        for name, hand in step.get("cmds", ()):
            getattr(hi, name)(hand)
        obs_list, row_hands = [], {}
        for slot in SLOTS:
            spec = step["hands"].get(slot)
            trackers[slot].update(spec is not None, now)
            if spec is not None:
                trackers[slot].set_orientation_valid(True)
            obs = HandObservation(
                slot=slot,
                present=spec is not None,
                tracking_state=trackers[slot].tracking_state,
                track_id={"Left": 1, "Right": 2}[slot] if spec is not None else -1,
                frames_since_measurement=trackers[slot].frames_since_measurement,
                reacquired_after_ms=trackers[slot].reacquired_after_ms,
                position_px=tuple(spec["pos"]) if spec else None,
                depth_m=spec["depth"][0] if spec else None,
                depth_valid=bool(spec["depth"][1]) if spec else False,
                orientation=tuple(spec["quat"]) if spec else None,
                thumb_outward=bool(spec.get("thumb_outward", False)) if spec else False,
                chirality_confirmed=bool(spec.get("confirmed", False)) if spec else False,
                orientation_valid=spec is not None,
                edge_on=0.62 if spec else None,
                snap_allowed=bool(spec.get("snap_allowed", False)) if spec else False,
            )
            obs_list.append(obs)
            if spec is not None:
                row_hands[slot] = spec
        before = len(events)
        hi.update(HandFrame(time_ms=now, hands=obs_list))
        rows.append({
            "tCapture": now,
            "cmds": [list(c) for c in step.get("cmds", ())],
            "hands": {s: {"position_px": list(v["pos"]),
                          "depth_m": v["depth"][0], "depth_valid": bool(v["depth"][1]),
                          "orientation": list(v["quat"]),
                          "thumb_outward": bool(v.get("thumb_outward", False)),
                          "chirality_confirmed": bool(v.get("confirmed", False)),
                          "snap_allowed": bool(v.get("snap_allowed", False))}
                      for s, v in row_hands.items()},
            "events": len(events) - before,
        })
    return rows, events


def main():
    rows, events = build()
    os.makedirs(TRACES, exist_ok=True)
    path = os.path.join(TRACES, "scripted_lifecycle.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({
            "trace": "scripted_lifecycle",
            "note": "Enter -> provisional chirality -> ready -> rule 3 refusal -> "
                    "armed exception -> frozen depth -> rotation reference -> "
                    "coast -> sustained loss -> re-entry. Presence drives a REAL "
                    "HandStateTracker, so BRIDGE_WINDOW_MS is not duplicated here.",
            "input": rows,
            "expected_events": events,
        }, fh, indent=1)
    print("handinput conformance -- %d frames, %d events -> %s"
          % (len(rows), len(events), path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
