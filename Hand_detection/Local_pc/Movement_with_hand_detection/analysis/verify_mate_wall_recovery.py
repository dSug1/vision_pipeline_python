"""GOLDEN VECTORS: at un-snap an object is anchored on its HAND, even from a wall.

Queue `AS8`; design of record
`Claude/30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md` §8ter.

THE OWNER'S ARGUMENT, AND IT IS THE RIGHT ONE (2026-08-28)
----------------------------------------------------------
    "The hand can grab the cube (even if it is mated) only if it is close to the
    cube ... At un-snap, the position should be the position of the hand which
    grabbed the cube, not whatever stale previous position it was before snap."

`A1` already decided this for a normal grab: capture the whole gap as an offset and
WALK it to zero, so the object migrates to its hand's depth instead of teleporting.
An un-snap is a fresh grab and must behave the same way.

TWO EARLIER VERSIONS BROKE EXACTLY THIS, BOTH INTRODUCED BY THE FIX ABOVE IT
---------------------------------------------------------------------------
  * falling back to `grab_hand_depth_m = None` when the grip depth was missing left
    the anchor at the MATE's depth forever -- no migration at all;
  * a "do not re-seat at a wall" guard, which refused the one thing that RECOVERS
    from a wall. Built and reverted the same day.

WHY ITS OWN FILE
----------------
The per-hand trackers are MODULE level, so scenarios sharing a process leak state
into each other: this check failed inside `verify_mate_handback.py` purely because
earlier scenarios there had left the hand's chirality unconfirmed, and it passes
from a clean import. ⭐ The guard caught it rather than letting it report a number
it had not earned -- which is the rule this whole row was written under.

    .venv/Scripts/python.exe analysis/verify_mate_wall_recovery.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import LiveSnapDebug as L                                      # noqa: E402
from Resources import object_assembly as OA                    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # pragma: no cover
    pass

FRAME = (640, 480)
HAND_AT_M = 0.50
WALL_M = 0.850

_fails = []


def check(name, cond, detail=""):
    print("  [%s] %-58s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        _fails.append(name)


def hand(cx, cy, depth=HAND_AT_M):
    px = [(cx + 6.0 * (i % 7) - 18.0, cy + 5.0 * (i // 7) - 10.0) for i in range(21)]
    wl = [(0.01 * (i % 7) - 0.03, 0.01 * (i // 7) - 0.01, 0.002 * (i % 5))
          for i in range(21)]
    return {"pixel_landmarks": px, "world_landmarks": wl,
            "thumb_outward": False, "hand_depth": (depth, True)}


print("=" * 78)
print("AT UN-SNAP THE OBJECT IS ANCHORED ON ITS HAND — EVEN FROM A WALL")
print("=" * 78)

L._hand_track_ids["Left"] = -1
L._hand_track_ids["Right"] = 7
st = L.CubeState(window_size=FRAME)
cube = st.cubes["small"]
cx, cy = OA.center_px_of(cube)
t = 0.0
for _ in range(40):
    L.update_hands(st, {"Left": None, "Right": hand(cx, cy)}, now_ms=t,
                   rotation=L.PRODUCTION_ROTATION)
    t += 42.0

check("⚠ the fixture actually reached the state it tests (object grabbed)",
      cube.owner is not None, str(cube.owner))

if cube.owner is not None:
    OA.place_center(cube, (cx + 150.0, cy + 60.0), FRAME)   # ...and off to one side
    cube.depth_m = WALL_M                 # the mate parked it against the far wall
    cube.rebaseline_depth = True
    L.update_hands(st, {"Left": None, "Right": hand(cx, cy)}, now_ms=t,
                   rotation=L.PRODUCTION_ROTATION)
    t += 42.0
    check("the anchor is the HAND's depth, not the mate's",
          cube.grab_hand_depth_m is not None
          and abs(cube.grab_hand_depth_m - HAND_AT_M) < 0.05,
          "anchor %.3f vs hand %.2f" % (cube.grab_hand_depth_m or -1, HAND_AT_M))
    check("...and the whole gap is captured as an offset to be walked off",
          cube.grab_depth_offset_m is not None and cube.grab_depth_offset_m > 0.2,
          "offset %+.3f m" % (cube.grab_depth_offset_m or 0.0))
    check("⛔ it does NOT teleport on the changeover frame",
          abs(cube.depth_m - WALL_M) < 0.01, "%.3f m" % cube.depth_m)

    # ⚠ A1's fade is spent in HAND MOVEMENT, not in time: a still hand closes no
    # gap at all, by design ("never faster than the hand").
    for i in range(60):
        L.update_hands(st, {"Left": None, "Right": hand(cx + (i % 14) * 6.0, cy)},
                       now_ms=t, rotation=L.PRODUCTION_ROTATION)
        t += 42.0
    check("⭐⭐ once the hand MOVES, it walks off the wall back to the hand",
          cube.depth_m < 0.80, "%.3f -> %.3f m" % (WALL_M, cube.depth_m))
    # ⭐⭐⭐ AND THE IN-PLANE HALF — the owner's "slerp to the fingertip
    # barycentre". An earlier version re-seated only the DEPTH, so the object kept
    # whatever offset the mate had given it and never came to the hand.
    _g = st.last_grip_px.get("Right")
    _c = OA.center_px_of(cube)
    _gap = ((_c[0] - _g[0]) ** 2 + (_c[1] - _g[1]) ** 2) ** 0.5 if _g else -1.0
    check("⭐⭐ ...and it converges on the FINGERTIP BARYCENTRE in plane too",
          0 <= _gap < 25.0, "%.0f px from the grip point" % _gap)
    check("...and the offset fully retires, so it settles rather than creeping",
          cube.grab_depth_offset_m is not None
          and abs(cube.grab_depth_offset_m) < 0.005,
          "offset %+.4f m" % (cube.grab_depth_offset_m or 0.0))

print("=" * 78)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — an un-snap anchors on the hand and recovers from a wall.")
