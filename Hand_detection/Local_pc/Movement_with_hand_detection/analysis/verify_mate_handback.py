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

print()
print("=" * 78)
print("⛔⛔ ONLY THE FOLLOWER IS RE-SEATED — the DRIVER must not RATCHET")
print("=" * 78)

# ⭐⭐ CAUGHT BY A LIVE SESSION'S OWN LOG, 2026-08-28. The re-seat above fixed the
# CHILD's 0.180 m jump, and was applied one object too wide: the DRIVER's depth was
# always its own, so re-anchoring it bakes the current offset in as a new zero and
# resets the ratio to 1.0 — and doing that on EVERY break ACCUMULATES.
#
#     [z] mated  large z=0.589 ... anchor=0.557
#     [z] broke  large z=0.591 ... anchor=0.557
#     [z] mated  large z=0.647 ... anchor=0.662
#     [z] broke  large z=0.670 ... anchor=0.662
#     [z] mated  large z=0.766 ... anchor=0.670
#     [z] broke  large z=0.774 ... anchor=0.670     <- 0.85 m is the far wall
#
# The parent climbed 0.589 -> 0.774 m WHILE HELD THROUGHOUT, ending 76 mm from the
# ceiling where pushing clamps and pulling back needs a large hand movement. Owner:
# *"at the end of the recording, I could not move the cube on the left on the z
# axis."*
#
# ⚠ This drives the REAL loop over repeated cycles and measures the drift. An
# earlier draft of this very block asserted `True` for each case — a check that
# could not fail, which is the exact fault this file's header warns about.
# ⚠⚠ THE HAND MUST MOVE IN Z DURING EACH CYCLE, or there is no offset for a
# ratchet to bake in and the check cannot fail. A first draft held the hand at a
# constant scale and passed against the ratcheting code — a second fake test in
# the same investigation.
# ⭐ THE PROPERTY: the hand returns to the SAME apparent size at the end of every
# cycle, so a correct build returns the object to the SAME depth. A ratchet
# carries the offset forward and the depth climbs.
L._hand_track_ids["Left"] = 3
L._hand_track_ids["Right"] = 7
st = L.CubeState(window_size=FRAME)
small, large = st.cubes["small"], st.cubes["large"]
_t = [0.0]


def _tick(hl, hr):
    L.update_hands(st, {"Left": hl, "Right": hr}, now_ms=_t[0],
                   rotation=L.PRODUCTION_ROTATION)
    _t[0] += 42.0


def _h(cx, cy, scale=1.0):
    px = [(cx + scale * (6.0 * (i % 7) - 18.0), cy + scale * (5.0 * (i // 7) - 10.0))
          for i in range(21)]
    wl = [(0.01 * (i % 7) - 0.03, 0.01 * (i // 7) - 0.01, 0.002 * (i % 5))
          for i in range(21)]
    return {"pixel_landmarks": px, "world_landmarks": wl,
            "thumb_outward": False, "hand_depth": (HAND_AT_M, True)}


lx, ly = OA.center_px_of(large)
OA.place_center(small, (lx + 80.0, ly), FRAME)
for _ in range(8):
    _tick(None, None)
sx, sy = OA.center_px_of(small)
_cycles, _zs = 0, []
for _c in range(4):
    for _ in range(14):                       # both grab; the mate forms
        _tick(_h(lx, ly), _h(sx, sy))
    # ⛔⛔ PUSH IN Z **AND STAY PUSHED THROUGH THE BREAK**. A first draft came back
    # to scale 1.0 before pulling apart, so the object was at its anchor when the
    # mate dropped and there was nothing for a ratchet to bake in — the check
    # passed against the ratcheting code. In the live session the breaks happened
    # at z = 0.591 / 0.670 / 0.774, i.e. DISPLACED, which is what accumulates.
    for _s in (1.10, 1.20, 1.30):
        for _ in range(3):
            _tick(_h(lx, ly, _s), _h(sx, sy))
    for _i in range(1, 60):                   # pull apart, still pushed out
        _tick(_h(lx - _i * 3.0, ly, 1.30), _h(sx + _i * 3.0, sy))
        if not st.assembly.links:
            _cycles += 1
            break
    for _ in range(4):                        # hand back at its ORIGINAL size
        _tick(_h(lx, ly, 1.0), None)
    _zs.append(large.depth_m)
    OA.place_center(large, (lx, ly), FRAME)
    OA.place_center(small, (sx, sy), FRAME)
    for _ in range(10):
        _tick(None, None)

check("⚠ the fixture actually reached the state it tests (4 mate/break cycles)",
      _cycles == 4, "%d cycles" % _cycles)
if _cycles == 4:
    _drift = abs(_zs[-1] - _zs[0])
    check("⛔⛔ the DRIVER's depth does not RATCHET across repeated breaks",
          _drift < 0.03,
          "%.3f m drift, hand back to its own size each time (%s)"
          % (_drift, " -> ".join("%.3f" % z for z in _zs)))
    check("...and it never gets pressed against a play-volume wall",
          all(0.32 < z < 0.83 for z in _zs),
          "%.3f .. %.3f m" % (min(_zs), max(_zs)))

print("=" * 78)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — a mate hands an object back without moving it.")
