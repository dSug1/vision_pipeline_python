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

Run:  .venv/Scripts/python.exe analysis/verify_edge_margin.py
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
