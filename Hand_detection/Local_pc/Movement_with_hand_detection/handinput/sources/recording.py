"""Replay a recorded session as `HandFrame`s.

⭐ THE RECORDER ALREADY WRITES ALMOST THE WHOLE OBSERVATION, which is not luck:
`recorder_schema` 2 added *"the cue production actually used"* and 3 added depth,
both for the same reason this package exists -- so a later reader gets what RAN
instead of recomputing it. So a replay here is a genuine re-run of the input
layer, not a simulation of one.

⚠⚠ WHAT A RECORDING DOES **NOT** CARRY, stated so nobody reads a replay as more
than it is:

  * **the palm ORIENTATION quaternion.** Only the cube's orientation is recorded,
    and that is the SLERPED result, not the hand's reading -- so `palm_pose`
    replays with `orientation=None` and `rotation_delta` never goes live.
    ⛔ Do not "fix" that by re-running Horn here: that is the recomputation this
    project has been bitten by, and it would silently become the reference for a
    conformance trace. ⭐ The live trace (`HANDINPUT_TRACE=1`) is where rotation
    events come from.
  * **the tracking STATE.** `hand_state` is client-side and not serialised.
    It is reconstructed below by running a real `HandStateTracker` over the
    recorded presence and timestamps -- the same module the tools run, fed the
    same inputs, so this is a re-run rather than an imitation.
  * **`snap_allowed` before schema 2**, and everything about hands on takes with
    no `recorder_schema` at all. Those rows are yielded with the fields absent.
"""
import json
import os

from ..contract import HandFrame
from . import live

try:                                         # in-repo layout
    from Resources import hand_state as _HS
    from Resources import palm_geometry as _PG
except ImportError:                          # standalone export, or Resources on sys.path
    import hand_state as _HS
    import palm_geometry as _PG

SLOTS = ("Left", "Right")


def read_meta(session_dir):
    path = os.path.join(session_dir, "meta.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def frames(session_dir, limit=None):
    """Yield `HandFrame`s from a session directory.

    ⚠ One `HandStateTracker` per SLOT, created once and advanced every frame --
    including frames where the hand is absent, which is what produces BRIDGING
    and SUSTAINED_LOST. Advancing it only on present frames would report a hand
    as continuously tracked across a dropout and quietly delete D2 from the
    replay.
    """
    path = os.path.join(session_dir, "raw_landmarks.jsonl")
    trackers = {s: _HS.HandStateTracker() for s in SLOTS}
    n = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            t = float(row.get("tCapture", 0.0))
            by_slot = {h.get("handedness"): h for h in row.get("hands", [])}
            obs = []
            for slot in SLOTS:
                h = by_slot.get(slot)
                trackers[slot].update(h is not None, t)
                if h is not None:
                    trackers[slot].set_orientation_valid(h.get("orientation_valid", False))
                lm = h.get("landmarks") if h else None
                obs.append(live.observe(
                    slot=slot,
                    tracking=trackers[slot],
                    present=h is not None,
                    track_id=(h or {}).get("trackId", -1),
                    position_px=_PG.palm_center_px(lm) if lm else None,
                    depth_m=(h or {}).get("hand_depth_m"),
                    depth_valid=(h or {}).get("depth_valid", False),
                    orientation=None,                      # not recorded -- see the header
                    thumb_outward=(h or {}).get("thumb_outward", False),
                    snap_allowed=(h or {}).get("snap_allowed", False),
                    edge_on=None,
                    landmarks_px=lm,
                    world_landmarks=(h or {}).get("world_landmarks"),
                ))
                if h is not None:
                    # `chirality_confirmed` is a recorded FACT on schema >= 2, and
                    # there is no tracker object here to read it off, so it is
                    # written straight onto the observation.
                    obs[-1].chirality_confirmed = bool(h.get("chirality_confirmed", False))
                    obs[-1].orientation_valid = bool(h.get("orientation_valid", False))
            yield HandFrame(time_ms=t, hands=obs)
            n += 1
            if limit is not None and n >= limit:
                return
