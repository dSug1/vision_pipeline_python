"""Drives the DEBUG tool's `update_hands` through the transitions that crashed it.

THE CRASH THIS LOCKS OUT (live, 2026-08-22)
--------------------------------------------
    TypeError: 'NoneType' object is not subscriptable
    thumb_outward = data["thumb_outward"]

Cause: finishing 4.1's migration rebinds `hand_state_trackers` to whichever TRACK
is in a slot. That bind was placed AFTER the trackers were updated, so the track's
own tracker was swapped in only after this frame's detection had been applied to
the PREVIOUS one -- leaving a stale `TRACKING` state on a slot whose `data` was
None. The window closed on the operator mid-session.

⚠ Sixteen unit suites passed while this crashed on the first real frame sequence,
because none of them drove `update_hands` with track ids published AND a hand
disappearing. That combination is the whole point of this file.

Needs cv2/mediapipe on the import path (no camera is opened, no window shown).

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_debug_update_hands.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import LiveSnapDebug as L  # noqa: E402

FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:62s} got {got!r}")
    if not ok:
        FAILURES.append(name)


def hand_at(cx, cy):
    p = [(cx, cy)] * 21
    p[0] = (cx, cy + 40); p[5] = (cx - 30, cy - 20); p[9] = (cx, cy - 30)
    p[13] = (cx + 15, cy - 25); p[17] = (cx + 30, cy - 15)
    return {"pixel_landmarks": p, "world_landmarks": [(0.0, 0.0, 0.0)] * 21,
            "thumb_outward": False}


def main():
    print("=" * 78)
    print("DEBUG TOOL: update_hands survives hands appearing and vanishing")
    print("=" * 78)

    arm = L._make_arm("blend", 640, 480)
    cx, cy = arm.cube_center("large")
    t = 0.0

    print("\n--- 1. a hand appears WITH a track id, on the cube ---")
    L._hand_track_ids["Left"] = -1
    L._hand_track_ids["Right"] = 7
    try:
        for _ in range(8):
            L.update_hands(arm, {"Left": None, "Right": hand_at(cx, cy)}, now_ms=t)
            t += 40.0
        check("no exception while tracking", True, True)
    except Exception as e:
        check(f"no exception while tracking ({type(e).__name__}: {e})", False, True)
        return 1

    print("\n--- 2. !! THE CRASH: the hand VANISHES while its id lingers ---")
    print("      data is None while the rebound tracker may still read TRACKING")
    try:
        for _ in range(12):
            L.update_hands(arm, {"Left": None, "Right": None}, now_ms=t)
            t += 40.0
        check("no exception when the hand vanishes", True, True)
    except Exception as e:
        check(f"no exception when the hand vanishes ({type(e).__name__}: {e})", False, True)
        return 1

    print("\n--- 3. the id disappears too, then the hand returns ---")
    try:
        L._hand_track_ids["Right"] = -1
        for _ in range(10):
            L.update_hands(arm, {"Left": None, "Right": None}, now_ms=t)
            t += 40.0
        L._hand_track_ids["Right"] = 9            # a NEW hand
        for _ in range(6):
            L.update_hands(arm, {"Left": None, "Right": hand_at(cx, cy)}, now_ms=t)
            t += 40.0
        check("no exception across id loss and a new hand", True, True)
    except Exception as e:
        check(f"no exception across id loss ({type(e).__name__}: {e})", False, True)
        return 1

    print("\n--- 4. !! a RELABEL mid-hold must not crash either ---")
    try:
        L._hand_track_ids["Left"], L._hand_track_ids["Right"] = 9, -1   # slot swap
        for _ in range(6):
            L.update_hands(arm, {"Left": hand_at(cx, cy), "Right": None}, now_ms=t)
            t += 40.0
        check("no exception across a relabel", True, True)
    except Exception as e:
        check(f"no exception across a relabel ({type(e).__name__}: {e})", False, True)
        return 1

    print("\n--- 5. and the cube did not end up frozen-but-owned ---")
    owner = arm.cubes["large"].owner
    live = {v for v in L._hand_track_ids.values() if v >= 0}
    frozen = isinstance(owner, int) and owner not in live
    check("cube is either unowned or owned by a LIVE track", frozen, False)

    print("\n" + "=" * 78)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): " + ", ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
