"""Guard: DR-1 must SURVIVE a partly-out-of-frame hand (2026-08-22).

THE DEFECT THIS LOCKS OUT
--------------------------
`hands_visualizer.py` used `_normalized_to_pixel_coordinates`, which returns None
for ANY landmark outside [0,1] — i.e. a hand partially out of frame. One None in a
PALM landmark (0, 5, 9, 13, 17) makes `palm_centroid` return None, which fails the
`all(o[0] is not None ...)` guard, which **skips DR-1 entirely for that frame**.
Consequences, both measured on the first recorded production run
(`2026-08-22_154426_production_4_1`, 5114 frames):

1. ⛔ **The stranded cube.** No hand gets a `trackId`, so the wire carries -1 for
   BOTH slots while landmarks keep flowing. A cube held by a track id then matched
   no live key, while its slot still held a DETECTED hand, so release never fired:
   *"indicated as grabbed but did not move, and the free hand could not grab it
   again"* — 40-frame (~1.6 s) runs, repeatedly. **A hand near the frame EDGE was
   enough to trigger it.**
2. ⛔ **A landmark teleporting to the origin.** `remap_keypoints` converts a None
   to (0, 0) through its TypeError fallback, so an out-of-frame landmark reached
   the client at the TOP-LEFT CORNER — corrupting `_weighted_position`'s
   translation average, not just identity.

⭐ Production now uses plain multiplication (`lm.x * width`), exactly as
`LiveSnapDebug.py` always has — which is why the debug tool never showed either
defect. **This was a production/debug divergence of the same class as §13.6.1 and
the mirror bug.**

⚠ This test deliberately checks the PROPERTY (identity survives an off-screen palm
landmark), not the implementation, so it still guards if the conversion is
rewritten. Dependency-free; no camera, no recordings.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_offscreen_identity.py
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "hand_identity_srv",
    os.path.join(_HERE, "..", "..", "Python_Server_MediaPipe_vision_pipeline",
                 "Resources", "hand_identity.py"))
H = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(H)

WIDTH, HEIGHT = 640, 480
FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:62s} got {got!r}")
    if not ok:
        FAILURES.append(name)


def to_pixels(norm):
    """What production sends NOW: plain multiplication, out-of-frame allowed."""
    return [(x * WIDTH, y * HEIGHT) for x, y in norm]


def to_pixels_old(norm):
    """What it sent BEFORE: None whenever the landmark leaves [0,1]."""
    return [((x * WIDTH, y * HEIGHT) if (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0)
             else (None, None)) for x, y in norm]


def hand_with(index, pos):
    h = [(0.5, 0.5)] * 21
    h[index] = pos
    return h


def main():
    print("=" * 78)
    print("DR-1 must survive a partly-out-of-frame hand")
    print("=" * 78)
    print(f"  palm landmarks feeding palm_centroid: {H.PALM_LANDMARKS}\n")

    print("--- 1. a PALM landmark just off the left edge ---")
    h = hand_with(17, (-0.04, 0.5))          # pinky MCP outside the frame
    check("OLD conversion loses the centroid (this WAS the bug)",
          H.palm_centroid(to_pixels_old(h)), None)
    check("NEW conversion still yields a centroid",
          H.palm_centroid(to_pixels(h)) is not None, True)
    check("NEW conversion still yields a palm width",
          H.palm_width(to_pixels(h)) is not None, True)

    print("\n--- 2. every edge, and both axes ---")
    for idx in H.PALM_LANDMARKS:
        for label, pos in (("left", (-0.1, 0.5)), ("right", (1.1, 0.5)),
                           ("top", (0.5, -0.1)), ("bottom", (0.5, 1.1))):
            h = hand_with(idx, pos)
            ok = H.palm_centroid(to_pixels(h)) is not None
            if not ok:
                check(f"landmark {idx} off the {label} edge", ok, True)
    check("all palm landmarks x all four edges keep identity alive", True, True)

    print("\n--- 3. !! DR-1 actually assigns a track id in that state ---")
    print("      (the property that matters -- a centroid nobody uses is no fix)")
    tracker = H.HandIdentityTracker(log=lambda *a: None)
    h = hand_with(0, (-0.08, 0.5))           # WRIST off-frame
    px = to_pixels(h)
    labels = tracker.update([(H.palm_centroid(px), "Left", 0.97, H.palm_width(px))],
                            now_ms=0.0)
    ids = tracker.last_track_ids
    check("a label is assigned", labels[0] in ("Left", "Right"), True)
    check("a STABLE TRACK ID is published (not -1)", ids[0] >= 0, True)

    print("\n--- 4. a fully absent hand must STILL be rejected ---")
    print("      (the fix must not make garbage look like a hand)")
    check("a short landmark list yields no centroid",
          H.palm_centroid([(0.0, 0.0)] * 5), None)
    check("an explicitly None palm point yields no centroid",
          H.palm_centroid([(None, None)] * 21), None)

    print("\n" + "=" * 78)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): " + ", ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED -- identity survives the frame edge.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
