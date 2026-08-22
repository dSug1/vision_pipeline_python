"""⭐ D1's ONLY BEHAVIOURAL CLAIM: production does exactly what it did before.

`analysis/verify_hand_state.py` proves the state machine is correct in isolation
and is deliberately dependency-free, because it is the artifact a web/mobile port
must reproduce (U3). THIS script proves the other half -- that the state machine
was WIRED into `HandsTriggeredActions` without moving the release point -- and it
needs pygame and the production module, so it is kept separate rather than
polluting the golden vectors with a runtime dependency the port cannot satisfy.

WHAT IT CHECKS: a cube is released on exactly the frames `_is_detected` is False,
which is the pre-D1 rule, at the shipped 0 ms bridge window. And that this stops
being true the moment the window opens -- otherwise the test would still pass on
a build where the tracker had been wired in but was ignored, which is precisely
the silent failure worth catching.

⚠ Runs pygame headless (`SDL_VIDEODRIVER=dummy`): importing
`Resources.HandsTriggeredActions` constructs a `CubeWindow`, which opens a real
window otherwise.

    .venv/Scripts/python.exe analysis/verify_d1_wiring.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import HandsTriggeredActions as HTA  # noqa: E402
from Resources import hand_state as HS  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


# A plausible open right hand in mirrored webcam pixels. The exact pose does not
# matter -- nothing here asserts on geometry -- only that it is DETECTED, i.e.
# the index tip is not (0, 0). The miss frame is what the server actually sends
# on a dropout: 21 zero points (`remap_keypoints`'s expected_count fallback).
HAND = [(320.0 + 6.0 * i, 240.0 + 4.0 * i) for i in range(21)]
MISS = [(0.0, 0.0)] * 21
# Same hand parked in the corner, out of every cube's grab radius, for the checks
# that need a DETECTED hand holding nothing.
FAR_HAND = [(8.0 + 2.0 * i, 8.0 + 1.5 * i) for i in range(21)]


def run(pattern, window_ms=None, dt_ms=42.0):
    """Feed `pattern` (True = detected) to production one frame at a time with a
    cube already held, and return the frame index at which it was released, or
    None. Timestamps are injected, so this does not depend on how fast the test
    machine runs."""
    for h in HTA.TRACKED_HANDS:
        HTA._hand_state_trackers[h] = HS.HandStateTracker(
            bridge_window_ms=HS.BRIDGE_WINDOW_MS if window_ms is None else window_ms)
        HTA._palm_facing_trackers[h].reset()
    for name in list(HTA.cube_window.cubes):
        HTA.cube_window.release_cube(name)
    # Grab the cube by hand rather than through `_try_snap`: the snap path also
    # depends on proximity and on DR-2's chirality reading, and neither is what
    # this script is about. The grab STATE is initialised exactly as production's
    # snap block does, so the translation update below it behaves normally.
    HTA.cube_window.snap_cube("large", "Right")
    cube = HTA.cube_window.cubes["large"]
    at_grab = HTA.cube_window.cube_center("large")
    cube.grab_landmark_weights = HTA._compute_grab_weights(at_grab, HAND)
    weighted = HTA._weighted_position(cube.grab_landmark_weights, HAND)
    cube.grab_residual_offset = (at_grab[0] - weighted[0], at_grab[1] - weighted[1])

    released_at = None
    for i, detected in enumerate(pattern):
        HTA.on_hands_frame(MISS, HAND if detected else MISS, now_ms=i * dt_ms)
        if released_at is None and HTA.cube_window.cube_owned_by("Right") is None:
            released_at = i
    return released_at


print("=" * 78)
print("D1/D2/D3 WIRING in production -- both arms of the live A/B")
print("=" * 78)

print("\n1. THE CONTROL ARM -- a 0 ms window still reproduces the pre-D2 rule")
# This is what the live A/B compares against, so it has to keep working long
# after nobody remembers what production did before D2.
check("continuous tracking never releases", run([True] * 20, window_ms=0.0) is None)
check("a single missed frame at index 5 releases at 5",
      run([True] * 5 + [False] + [True] * 5, window_ms=0.0) == 5)
check("a miss on the very first frame releases at 0",
      run([False] + [True] * 5, window_ms=0.0) == 0)
check("a long gap releases at its FIRST frame, not its last",
      run([True] * 3 + [False] * 8 + [True] * 3, window_ms=0.0) == 3)

print("\n2. ⭐ THE SHIPPED BUILD -- D2's window is live and load-bearing")
check("the shipped constant is D2's measured 150.0 ms", HS.BRIDGE_WINDOW_MS == 150.0,
      repr(HS.BRIDGE_WINDOW_MS))
# 42 ms per frame, so 150 ms covers 3 missed frames and no more.
check("a 1-frame gap no longer releases the cube",
      run([True] * 5 + [False] + [True] * 5) is None)
check("a 3-frame gap no longer releases the cube",
      run([True] * 5 + [False] * 3 + [True] * 5) is None)
# Last measurement at frame 2 (t = 84 ms); the misses at 126/168/210 ms are
# 42/84/126 ms stale so they bridge, and frame 6 at 168 ms stale does not.
# Three bridged frames at 42 ms each -- the same count `verify_hand_state.py` §4
# derives for 24 fps, which is the cross-check that these two agree.
check("an 8-frame gap still releases, once the coast is exhausted",
      run([True] * 3 + [False] * 8 + [True] * 3) == 6,
      str(run([True] * 3 + [False] * 8 + [True] * 3)))
print("     ⚠ These are `d2_bridge_ab.py`'s SAVED and LATE_RELEASE classes shown")
print("       working in production code. WHETHER the trade is worth making is")
print("       that script's question, and finally the owner's -- not this one's.")

print("\n3. THE COASTING STATE SURVIVES A BRIDGE (what D2 coasts on)")
run([True] * 5)
before = HTA._hand_orientation_filters["Right"]
HTA.on_hands_frame(MISS, MISS, now_ms=5 * 42.0)
check("orientation filter is NOT wiped on a bridged frame",
      HTA._hand_orientation_filters["Right"] is before)
HTA.on_hands_frame(MISS, MISS, now_ms=400.0)          # past the window
check("and IS wiped once the track is SUSTAINED_LOST",
      HTA._hand_orientation_filters["Right"] is not before)

print("\n4. ⭐ D2's RESUME RULE and D3's BLEND")
# Rotate omega away from identity, bridge, and confirm the resume zeroes it: an
# angular velocity measured before the gap must not be replayed across a gap the
# filter never saw (B8 -- hold beats extrapolate, at every horizon).
run([True] * 5)
HTA._hand_orientation_filters["Right"].omega = (0.9, 0.1, 0.2, 0.3)
HTA.on_hands_frame(MISS, MISS, now_ms=5 * 42.0)                 # bridged
check("omega survives the bridged frame itself",
      HTA._hand_orientation_filters["Right"].omega != HTA.IDENTITY_QUATERNION)
HTA.on_hands_frame(MISS, HAND, now_ms=6 * 42.0)                 # resume
check("⭐ and is zeroed on the RESUME frame -- no extrapolation across the gap",
      HTA._hand_orientation_filters["Right"].omega == HTA.IDENTITY_QUATERNION)
check("  the resume also arms D3's blend",
      HTA._resync_blend_left["Right"] == HTA.RESYNC_BLEND_FRAMES - 1,
      str(HTA._resync_blend_left["Right"]))
for k in range(HTA.RESYNC_BLEND_FRAMES):
    HTA.on_hands_frame(MISS, HAND, now_ms=(7 + k) * 42.0)
check("  and it runs down to 0 over the following frames",
      HTA._resync_blend_left["Right"] == 0, str(HTA._resync_blend_left["Right"]))
# A track that dies must not leave a blend armed for the next grab.
run([True] * 5)
HTA._resync_blend_left["Right"] = 3
HTA.on_hands_frame(MISS, MISS, now_ms=5000.0)                   # SUSTAINED_LOST
check("a dead track clears any pending blend",
      HTA._resync_blend_left["Right"] == 0)

# ⚠ The bug this catches was real: the blend was armed on every resume, but is
# only consumed while a cube is held, so an empty hand kept it armed and the
# NEXT grab -- which never bridged at all -- got blended.
for h in HTA.TRACKED_HANDS:
    HTA._hand_state_trackers[h] = HS.HandStateTracker()
    HTA._resync_blend_left[h] = 0
for name in list(HTA.cube_window.cubes):
    HTA.cube_window.release_cube(name)
# ⚠ FAR_HAND, not HAND: the cubes start centred and `HAND` lands close enough to
# snap one, which quietly made the first version of this check test the opposite
# of what it says. Keep this hand in the corner, out of every grab radius.
HTA.on_hands_frame(MISS, FAR_HAND, now_ms=0.0)
HTA.on_hands_frame(MISS, MISS, now_ms=42.0)                     # bridged, no cube
HTA.on_hands_frame(MISS, FAR_HAND, now_ms=84.0)                 # resume, no cube
check("  (the far hand really is holding nothing)",
      HTA.cube_window.cube_owned_by("Right") is None)
check("⭐ an EMPTY hand's resume does not arm the blend for a later grab",
      HTA._resync_blend_left["Right"] == 0, str(HTA._resync_blend_left["Right"]))


print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
