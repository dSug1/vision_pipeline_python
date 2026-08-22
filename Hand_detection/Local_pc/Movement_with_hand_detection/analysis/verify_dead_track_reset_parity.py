"""N6 guard: production and the debug tool must reset the SAME state on a dead track.

WHY THIS EXISTS
----------------
Owner, live 2026-08-22: *"when the palm exits and comes back with back, the back
hand still grabs the cube for a short while before the cube ungrabs: this does not
happen in production."*

Cause: on `SUSTAINED_LOST` production reset FOUR things and the debug tool reset
THREE -- it never called `PalmFacingTracker.reset()`. DR-2 FREEZES the palm/back
sign while edge-on, so without the reset the sign frozen before a hand left
survived its death. A hand returning back-of-hand is briefly edge-on with nothing
measurable, so it was judged with the OLD hand's "palm" reading, `thumb_outward`
came back False, and rule 3's gate let it snap.

⚠ A ONE-LINE divergence, invisible to every unit test, live-visible in seconds.
That is the third divergence of this class in one session (§13.6.1, the mirror,
this) -- which is the argument for **U6**, collapsing the two pipelines.

WHAT IT CHECKS, AND WHY IT IS A SOURCE COMPARISON
--------------------------------------------------
Both tools' dead-track branches are read from SOURCE and the reset TARGETS
compared. It cannot be satisfied by a copy of the rule living in the test -- the
same reasoning `VerifyChiralityFixture.py` is built on.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_dead_track_reset_parity.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []

# What each tool must clear when a track is properly gone. Matched loosely on the
# state's NAME so either tool's spelling (module dict vs per-arm field) counts.
REQUIRED = ("hand_orientation_filters", "hand_rotation_states",
            "palm_facing_trackers", "resync_blend_left")


def dead_track_block(path, marker):
    src = io.open(os.path.join(ROOT, path), encoding="utf-8").read()
    i = src.index(marker)
    j = src.index("continue", i)
    return src[i:j]


def main():
    print("=" * 78)
    print("N6 PARITY: the dead-track (SUSTAINED_LOST) reset must match")
    print("=" * 78)
    try:
        prod = dead_track_block(
            "Resources/HandsTriggeredActions.py",
            "if tracking.tracking_state == hand_state.SUSTAINED_LOST:")
        dbg = dead_track_block(
            "LiveSnapDebug.py",
            "tracking_state == hand_state.SUSTAINED_LOST:")
    except ValueError as e:
        print(f"  [FAIL] could not locate a dead-track block: {e}")
        return 1

    print(f"\n  {'state cleared on a dead track':38s} {'production':>12s} {'debug':>8s}")
    print("  " + "-" * 62)
    for name in REQUIRED:
        in_p = re.search(re.escape(name), prod) is not None
        in_d = re.search(re.escape(name), dbg) is not None
        ok = in_p and in_d
        print(f"  {name:38s} {str(in_p):>12s} {str(in_d):>8s}   {'ok' if ok else '<-- MISMATCH'}")
        if not ok:
            FAILURES.append(name)

    print("\n  ! palm_facing_trackers is the one that was missing from the debug")
    print("    tool and produced the owner's forbidden back-of-hand grab.")

    print("\n" + "=" * 78)
    if FAILURES:
        print(f"{len(FAILURES)} MISMATCH(ES): " + ", ".join(FAILURES))
        print("Both tools must clear the same state, or one will carry a dead")
        print("hand's history into the next hand.")
        return 1
    print("PARITY OK -- both tools clear the same state on a dead track.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
