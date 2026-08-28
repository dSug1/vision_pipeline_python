"""GOLDEN VECTORS: a mate handing an object BACK to its hand must be continuous in z.

Queue `AS8`; design of record
`Claude/30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md` §8ter.

THE DEFECT THIS LOCKS OUT (live, 2026-08-28)
--------------------------------------------
While an object is a mate FOLLOWER the mate owns its depth, and the grab baseline
it captured earlier goes STALE. The moment the mate lets go, the hand's ratio drive
resumes from that stale anchor and the object TELEPORTS -- measured **0.180 m**.

    Owner: "when the child snap break, verify what the z position of the cube
    becomes. It looks like it does not match with the z position of the hand that
    grabbed it when it was a child."

WHY THIS IS ITS OWN FILE
------------------------
It must run in a CLEAN PROCESS. The first attempt appended it to
`verify_debug_update_hands.py`, whose `main()` leaves the module-level
`_hand_track_ids` mutated -- and with a stale id the hand drives nothing, so the
control arm reported 0.000 m of jump and read as a PASS of a check that had not
run. Shared state between fixtures, caught only because the number disagreed with
a standalone probe.

⚠ It drives `update_hands`, i.e. the REAL pixel-span -> ratio -> anchor ->
`depth_from_ratio` chain. A probe that sets `depth_m` directly cannot see this
defect at all, and several did exactly that before it was found.

    .venv/Scripts/python.exe analysis/verify_mate_handback.py
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
CARRIED_TO_M = 0.680          # where the mate had taken the object
HAND_AT_M = 0.50              # where its hand has been the whole time

_fails = []


def check(name, cond, detail=""):
    print("  [%s] %-56s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        _fails.append(name)


def hand(cx, cy, depth=HAND_AT_M):
    px = [(cx + 6.0 * (i % 7) - 18.0, cy + 5.0 * (i // 7) - 10.0) for i in range(21)]
    wl = [(0.01 * (i % 7) - 0.03, 0.01 * (i // 7) - 0.01, 0.002 * (i % 5))
          for i in range(21)]
    return {"pixel_landmarks": px, "world_landmarks": wl,
            "thumb_outward": False, "hand_depth": (depth, True)}


def trial(reseat):
    """Grab an object, pretend the mate carried it to `CARRIED_TO_M`, then hand it
    back. Returns its depth one frame later."""
    L._hand_track_ids["Left"] = -1
    L._hand_track_ids["Right"] = 7
    st = L.CubeState(window_size=FRAME)
    cube = st.cubes["small"]
    cx, cy = OA.center_px_of(cube)
    t = 0.0
    for _ in range(10):
        L.update_hands(st, {"Left": None, "Right": hand(cx, cy)}, now_ms=t,
                       rotation=L.PRODUCTION_ROTATION)
        t += 42.0
    if cube.owner is None:                    # the fixture must reach the state
        return None, cube
    cube.depth_m = CARRIED_TO_M               # the mate carried it here
    cube.rebaseline_depth = reseat
    L.update_hands(st, {"Left": None, "Right": hand(cx, cy)}, now_ms=t,
                   rotation=L.PRODUCTION_ROTATION)
    return cube.depth_m, cube


print("=" * 78)
print("A MATE HANDING AN OBJECT BACK MUST BE CONTINUOUS IN Z")
print("=" * 78)

without, c1 = trial(False)
with_, c2 = trial(True)

check("⚠ the fixture actually reached the state it tests (object grabbed)",
      without is not None and with_ is not None,
      "grabbed" if without is not None else "NOT GRABBED — the check below is void")

if without is not None and with_ is not None:
    check("⛔ WITHOUT the re-seat the object TELEPORTS — the defect",
          abs(without - CARRIED_TO_M) > 0.05,
          "%.3f -> %.3f, jump %.3f m" % (CARRIED_TO_M, without,
                                         abs(without - CARRIED_TO_M)))
    check("⭐ WITH the re-seat the hand-over is continuous",
          abs(with_ - CARRIED_TO_M) < 0.01,
          "%.3f -> %.3f, jump %.3f m" % (CARRIED_TO_M, with_,
                                         abs(with_ - CARRIED_TO_M)))
    check("...the flag is CONSUMED, so it re-seats once and not every frame",
          c2.rebaseline_depth is False)
    check("...and the baseline now matches the object's own depth",
          c2.grab_depth_m is not None
          and abs(c2.grab_depth_m - CARRIED_TO_M) < 0.01,
          "anchor %.3f" % (c2.grab_depth_m or -1))

print("=" * 78)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — a mate hands an object back without moving it.")
