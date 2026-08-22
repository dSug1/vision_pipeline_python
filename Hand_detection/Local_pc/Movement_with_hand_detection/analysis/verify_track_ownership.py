"""Verifies queue 4.1 / T3: cube ownership survives a handedness RELABEL.

THE DEFECT THIS PROVES IS GONE
-------------------------------
Ownership used to key on MediaPipe's handedness LABEL, which is not an identity.
When the label flipped -- whether DR-1 erred OR corrected itself -- the held cube
was orphaned. Measured at **113 of 205 spurious releases**
(`analysis/d2_bridge_ab.py`), larger than true dropouts (83).

⛔ A client-side repair was built, live-tested and REVERTED (`git show d4972b5`):
it inferred "same hand" from POSITION, and two hands in the same place are
indistinguishable by position -- which is what OCCLUSION is. Live, it handed a
held cube to the operator's other physical hand.

⭐ The fix is to carry the identity the server already computes. This file is the
regression guard for that.

WHAT IS ACTUALLY EXERCISED
---------------------------
Not a mock: `CubeWindow.snap_cube`/`cube_owned_by` are production's own, and the
owner key comes from production's own `_owner_key`. A test carrying its own copy
of the keying rule would pass while the game was broken -- the same reasoning
`VerifyChiralityFixture.py` is built on.

⚠ Needs pygame (CubeWindow imports it) but opens no window and no camera.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_track_ownership.py
Exit code 0 = all pass.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import HandsTriggeredActions as HTA   # noqa: E402
from Resources.CubeWindow import (Cube, _make_cube_mesh, FACE_COLOR_YELLOW,  # noqa: E402
                                  FACE_COLOR_VIOLET, FACE_COLOR_GREEN)

FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:60s} got {got!r}")
    if not ok:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


class FakeWindow:
    """Minimal stand-in holding real `Cube` objects, exercising the real
    ownership comparison. Only the three ownership primitives are needed."""

    def __init__(self):
        mesh = _make_cube_mesh(FACE_COLOR_YELLOW, FACE_COLOR_VIOLET, FACE_COLOR_GREEN)
        self.cubes = {"large": Cube(mesh=mesh, size=120)}

    def cube_owned_by(self, owner_key):
        for name, cube in self.cubes.items():
            if cube.owner == owner_key:
                return name
        return None

    def snap_cube(self, name, owner_key):
        self.cubes[name].owner = owner_key


def main():
    print("=" * 78)
    print("Queue 4.1 / T3 -- ownership keys on the STABLE TRACK ID")
    print("=" * 78)

    win = FakeWindow()

    print("\n--- 1. the owner key prefers the track id ---")
    HTA.on_hand_tracks_frame(7, 9)
    check("Left  -> track id 7", HTA._owner_key("Left"), 7)
    check("Right -> track id 9", HTA._owner_key("Right"), 9)

    print("\n--- 2. !! fallback to the label when no id backs the hand ---")
    print("      (older server, or DR-1 could not resolve identity this frame)")
    HTA.on_hand_tracks_frame(-1, -1)
    check("Left  falls back to the label", HTA._owner_key("Left"), "Left")
    check("Right falls back to the label", HTA._owner_key("Right"), "Right")

    print("\n--- 3. THE DEFECT: a relabel must NOT orphan a held cube ---")
    HTA.on_hand_tracks_frame(7, 9)                 # hand A = track 7, labelled Left
    win.snap_cube("large", HTA._owner_key("Left"))
    check("cube is held by the hand in the Left slot",
          win.cube_owned_by(HTA._owner_key("Left")), "large")

    # The SAME physical hand now arrives under the OTHER label -- exactly the
    # 113/205 case. Its track id is unchanged, because identity did not change.
    HTA.on_hand_tracks_frame(-1, 7)                # track 7 is now in the Right slot
    check("after the relabel the cube is NOT orphaned",
          win.cube_owned_by(HTA._owner_key("Right")), "large")
    check("and the empty Left slot owns nothing",
          win.cube_owned_by(HTA._owner_key("Left")), None)

    print("\n--- 4. a genuinely DIFFERENT hand must not inherit the cube ---")
    print("      (this is what the reverted position-based fix got wrong)")
    HTA.on_hand_tracks_frame(42, 7)                # track 42 is a different hand
    check("the other hand (track 42) owns nothing",
          win.cube_owned_by(HTA._owner_key("Left")), None)
    check("track 7 still holds it", win.cube_owned_by(HTA._owner_key("Right")), "large")

    print("\n--- 5. !! id 0 is a VALID track, not 'absent' ---")
    print("      (a truthiness test instead of >= 0 would break the first hand)")
    HTA.on_hand_tracks_frame(0, -1)
    check("track id 0 is used, not treated as missing", HTA._owner_key("Left"), 0)

    print("")
    print("--- 6. !! THE STRANDED-CUBE REGRESSION (owner-found live, 2026-08-22) ---")
    print("      'the cube was indicated as grabbed but did not move at all and")
    print("       the free hand could not grab it again.'")
    print("      Cause: release read cube_owned_by(_owner_key(hand)). When a track")
    print("      ENDS the key degrades to the LABEL, the int-keyed cube is never")
    print("      found, and it stays owned by a dead id -- drawn as grabbed, driven")
    print("      by nothing, excluded from unowned_cube_names() forever.")

    win2 = FakeWindow()
    HTA.on_hand_tracks_frame(5, -1)
    win2.snap_cube("large", HTA._owner_key("Left"))
    check("cube held by track 5", win2.cubes["large"].owner, 5)

    HTA.on_hand_tracks_frame(-1, -1)                 # the track ends
    check("the OLD release lookup finds nothing (this WAS the bug)",
          win2.cube_owned_by(HTA._owner_key("Left")), None)
    check("...while the cube is still owned -> it would strand",
          win2.cubes["large"].owner is not None, True)

    # The FIX: a remembered governing hand keeps release reachable.
    HTA.cube_window = win2
    HTA._owner_hand_of_cube.clear()
    HTA.on_hand_tracks_frame(5, -1)
    HTA._refresh_cube_owner_hands()
    check("governing hand recorded while the track is visible",
          HTA._owner_hand_of_cube.get("large"), "Left")

    HTA.on_hand_tracks_frame(-1, -1)                 # track vanishes
    HTA._refresh_cube_owner_hands()
    check("!! governing hand KEPT when the track vanishes (D2 coast needs it)",
          HTA._owner_hand_of_cube.get("large"), "Left")

    HTA.on_hand_tracks_frame(-1, 5)                  # same track, other slot
    HTA._refresh_cube_owner_hands()
    check("governing hand FOLLOWS the track across a relabel",
          HTA._owner_hand_of_cube.get("large"), "Right")


    print("\n" + "=" * 78)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED -- a relabel no longer orphans a held cube.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
