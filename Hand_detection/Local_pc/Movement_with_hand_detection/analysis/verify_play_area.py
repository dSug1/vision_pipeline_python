"""Golden vectors for U9's PLAY AREA -- `palm_geometry.clamp_to_play_area`.

The rule: every object is confined to the display window inset by
`EDGE_MARGIN_PX`, so it can never be pushed to the edge of the display.

⛔⛔ TWO HAND-SIDE TRIGGERS WERE BUILT BEFORE THIS AND BOTH WERE REVERTED. They
released the object when the HAND CENTRE crossed the margin. Kept here as the
reason the vectors below test a CLAMP and not a trigger:

  1. an ADAPTIVE margin (half the CURRENT palm width) -- the measured width
     collapsed 45% in one frame (50.9 -> 28.2 px), the margin collapsed with it,
     and the object was re-grabbed and carried out of frame. **A threshold must
     not be computed from a quantity that is noisy in the regime the threshold
     governs.**
  2. a CUBE-DRIVEN check -- it found the hand by the object's owner SLOT, so a
     relabel that emptied that slot made the check silently skip: it fired on the
     first approach to an edge and never again.

⭐⭐ And even correct, a trigger could not do the job. Translation is
GRAB-RELATIVE, so an object keeps its own offset from the hand and every
grab-push-drop cycle walks it further out. A trigger decides WHEN TO LET GO; only
a clamp decides WHERE THE OBJECT MAY BE. **A trigger cannot enforce an invariant.**

⭐⭐ 4.2 EXTENDED IT INTO A WORLD-SPACE VOLUME (owner decision, 2026-08-23).
The display is the camera's FRUSTUM, so once depth is driven the margin and the
object's extent both project differently at different depths: the clamp moves
into world coordinates and the on-screen boundary MOVES with depth. Section 2
below asserts that, and asserts the thing that keeps it honest -- the world rule
and the pixel rule it replaces MEET at 0.40 m, the depth the pixel rule was
derived at (42.5 mm x 554 px / 0.40 m = 58.9 px ~ EDGE_MARGIN_PX = 60).

Run:  .venv/Scripts/python.exe analysis/verify_play_area.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import palm_geometry as PG  # noqa: E402

FAILS = []
FRAME = (640, 480)
M = PG.EDGE_MARGIN_PX


def check(name, got, want):
    ok = (got == want)
    if not ok:
        FAILS.append("%s: got %r, want %r" % (name, got, want))
    print("  [%s] %-64s %r" % ("PASS" if ok else "FAIL", name, got))


def main():
    print("Golden vectors -- U9 play area (inset %.0f px)" % M)
    print()

    print("1. ** THE PLAY AREA -- the cube may never reach the display edge **")
    # Owner, 2026-08-23: *"I can still push step by step the cube to the edge of
    # the display window ... I want the cube to be constrained in a smaller window
    # within a display window."* The hand-side margin above is a TRIGGER (when to
    # let go); this is the INVARIANT (where the cube may be). A hand rule alone
    # cannot enforce it -- translation is grab-relative, so the cube keeps its own
    # offset from the hand and creeps outward on every grab-push-drop cycle.
    FR2 = (640, 480)
    for size, label in ((80, "large"), (40, "small")):
        lo = M
        hi_x, hi_y = 640 - M - size, 480 - M - size
        check("%s cube pushed far off the LEFT/TOP stops at the play edge" % label,
              PG.clamp_to_play_area(-500.0, -500.0, size, FR2), (lo, lo))
        check("%s cube pushed far off the RIGHT/BOTTOM stops at the play edge" % label,
              PG.clamp_to_play_area(5000.0, 5000.0, size, FR2), (hi_x, hi_y))
        check("%s cube well inside is untouched" % label,
              PG.clamp_to_play_area(300.0, 200.0, size, FR2), (300.0, 200.0))
        # the whole cube, not just its corner, stays inside the play area
        x, y = PG.clamp_to_play_area(5000.0, 5000.0, size, FR2)
        check("...and the %s cube's FAR corner is inside too" % label,
              (x + size <= 640 - M) and (y + size <= 480 - M), True)

    check("idempotent -- clamping twice changes nothing",
          PG.clamp_to_play_area(*PG.clamp_to_play_area(5000.0, 5000.0, 80, FR2),
                                size=80, frame_size=FR2),
          PG.clamp_to_play_area(5000.0, 5000.0, 80, FR2))
    check("unconfigured frame size -> position unchanged, never crippled",
          PG.clamp_to_play_area(12.0, 34.0, 80, None), (12.0, 34.0))
    # A play area narrower than the cube would invert the clamp and pin the cube
    # to a nonsense corner; centring is the least-surprising fallback.
    check("degenerate play area -> centred rather than inverted",
          PG.clamp_to_play_area(-999.0, -999.0, 200, (200, 200)), (0.0, 0.0))

    print()
    print("2. ** 4.2 -- THE PLAY AREA IS A WORLD-SPACE VOLUME, FRUSTUM-AWARE **")
    # Owner decision, 2026-08-23. The display shows the camera's field of view --
    # a frustum, not a box -- so an object's projected extent grows as it comes
    # near and shrinks as it recedes, and so does the world margin's projection.
    # The 2D rule above is the special case at the reference depth.
    F = PG.focal_px(FR2)
    check("focal length at 60 deg on a 640-wide frame", round(F, 1), 554.3)

    # ⭐⭐ THE LOAD-BEARING CHECK: the world rule and the pixel rule it replaces
    # must MEET at the depth the pixel rule was derived at. 42.5 mm at 0.40 m is
    # 58.9 px; EDGE_MARGIN_PX is 60. If these ever drift apart, one of them has
    # been changed without the other and U9's derivation no longer holds.
    margin_at_ref = F * PG.PLAY_AREA_MARGIN_M / PG.U9_DERIVATION_DEPTH_M
    check("42.5 mm at U9's 0.40 m projects to ~EDGE_MARGIN_PX",
          abs(margin_at_ref - PG.EDGE_MARGIN_PX) < 1.5, True)
    # ⚠ And the object's RESTING depth is NOT that derivation depth. It is the
    # operator's measured median working distance (analysis/m9_working_distance.py,
    # 0.497 m over 86109 trusted frames); 0.40 m is only where U9 happened to
    # derive a pixel count. Conflating the two put an object 10 cm nearer than
    # the hand and made it unreachable in 29% of frames.
    check("the resting depth is the MEASURED median, not U9's derivation depth",
          PG.REFERENCE_DEPTH_M != PG.U9_DERIVATION_DEPTH_M, True)
    check("...and it is the measured median, rounded", PG.REFERENCE_DEPTH_M, 0.50)

    print()
    print("  2a. an object at the reference depth is its nominal size")
    for size in (80, 40):
        check("size %d unchanged at the resting depth" % size,
              PG.projected_size_px(size, PG.REFERENCE_DEPTH_M), float(size))
    check("HALF the depth -> TWICE the projected extent",
          PG.projected_size_px(40, 0.30, reference_depth_m=0.60), 80.0)
    check("...and the object's REAL size never changed -- only its projection",
          PG.projected_size_px(40, 0.80), 40.0 * PG.REFERENCE_DEPTH_M / 0.80)
    # ⚠ At the DEFAULT reference depth 0.20 m is outside the play volume, so the
    # projection is taken at the near wall instead -- deliberate, and the reason
    # the check above passes its own reference explicitly. An object may not be
    # brought nearer than PLAY_DEPTH_MIN_M however hard the hand pushes.
    check("...and a depth outside the volume projects at the wall, not beyond",
          PG.projected_size_px(40, 0.05), PG.projected_size_px(40, PG.PLAY_DEPTH_MIN_M))

    print()
    print("  2b. the boundary MOVES with depth -- inward as the object recedes")
    # ⭐ This is the intended consequence of the owner's decision, asserted so
    # nobody 'fixes' it later: pushed hard right, a NEARER object stops further
    # right (its margin projects wider but so does it) and a FAR object stops
    # further left in world terms. What must hold at every depth is the
    # INVARIANT: the whole object, at its projected extent, stays inside the
    # play area computed at its own depth.
    for depth in (PG.PLAY_DEPTH_MIN_M, 0.40, PG.REFERENCE_DEPTH_M, 0.70,
                  PG.PLAY_DEPTH_MAX_M):
        for size, label in ((80, "large"), (40, "small")):
            cx, cy = PG.clamp_to_play_volume(9000.0, 9000.0, depth, size, FR2)
            proj = PG.projected_size_px(size, depth)
            m = F * PG.PLAY_AREA_MARGIN_M / depth
            right, bottom = cx + proj / 2.0, cy + proj / 2.0
            check("%s at %.2f m: far corner inside the play area" % (label, depth),
                  (right <= 640 - m + 1e-6) and (bottom <= 480 - m + 1e-6), True)
            cx, cy = PG.clamp_to_play_volume(-9000.0, -9000.0, depth, size, FR2)
            check("%s at %.2f m: near corner inside the play area" % (label, depth),
                  (cx - proj / 2.0 >= m - 1e-6) and (cy - proj / 2.0 >= m - 1e-6), True)

    print()
    print("  2c. the world form equals the reduced pixel form")
    # `clamp_to_play_volume` is written in world coordinates on purpose -- it is
    # the owner's rule as stated. But it must agree with the algebra: under a
    # pinhole camera both the margin and the extent scale as 1/Z, so the whole
    # thing reduces to the 2D clamp with a depth-dependent margin and size. If
    # these disagree, the world implementation has a bug the eye would not catch.
    for depth in (0.32, 0.40, 0.75):
        for size in (80, 40):
            proj = PG.projected_size_px(size, depth)
            m = F * PG.PLAY_AREA_MARGIN_M / depth
            for want_x, want_y in ((9000.0, -9000.0), (-9000.0, 9000.0), (317.0, 201.0)):
                gx, gy = PG.clamp_to_play_volume(want_x, want_y, depth, size, FR2)
                ex, ey = PG.clamp_to_play_area(want_x - proj / 2.0, want_y - proj / 2.0,
                                               proj, FR2, margin_px=m)
                check("size %d at %.2f m from (%.0f,%.0f)" % (size, depth, want_x, want_y),
                      (round(gx - proj / 2.0, 6), round(gy - proj / 2.0, 6)),
                      (round(ex, 6), round(ey, 6)))

    print()
    print("  2d. degradations never cripple the clamp")
    check("no depth -> the depth-free 2D rule, unchanged",
          PG.clamp_to_play_volume(9000.0, 9000.0, None, 80, FR2),
          (640 - M - 80 + 40.0, 480 - M - 80 + 40.0))
    check("no frame size -> position unchanged",
          PG.clamp_to_play_volume(12.0, 34.0, 0.40, 80, None), (12.0, 34.0))
    # An object nearer than the volume allows would otherwise render huge and
    # walk out of frame; the depth clamp is what stops that.
    check("depth below the volume is clamped up", PG.clamp_depth(0.05), PG.PLAY_DEPTH_MIN_M)
    # ⭐⭐ THE WALLS MUST BE REACHABLE, or an object can be parked where it can
    # never be picked up again -- release freezes it in Z and a re-grab needs the
    # hand within GRAB_Z_TOLERANCE_M of it. Measured p1/p99 of the operator's own
    # working distance (analysis/m9_working_distance.py) are 0.309/0.837.
    check("the near wall is inside the measured p1 hand depth",
          PG.PLAY_DEPTH_MIN_M <= 0.309 + 0.001, True)
    check("the far wall is inside the measured p99 hand depth",
          PG.PLAY_DEPTH_MAX_M >= 0.837 - 0.001, True)
    check("depth above the volume is clamped down", PG.clamp_depth(9.0), PG.PLAY_DEPTH_MAX_M)
    # Degenerate: at the near wall the large object and its margin together
    # exceed a 200 px window entirely -> centre it rather than invert the clamp.
    dx, dy = PG.clamp_to_play_volume(-999.0, -999.0, PG.PLAY_DEPTH_MIN_M, 200, (200, 200))
    check("degenerate volume -> centred rather than inverted", (dx, dy), (100.0, 100.0))

    print()
    print()
    if FAILS:
        print("=" * 72)
        print("FAILED (%d):" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        print("=" * 72)
        return 1
    print("=" * 72)
    print("ALL GOLDEN VECTORS PASS")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
