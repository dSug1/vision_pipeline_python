"""Golden vectors for `Resources/owner_remap.py` (T3 narrow remap).

Written BEFORE the wiring, per the binding rule -- and specifically to pin the
cases the 4.1 migration got wrong, so this attempt cannot repeat them:

  * §3.1 the fallback that fired exactly when the id was missing;
  * §3.5 a returning hand inheriting the previous hand's claim;
  * -1 (no identity) never matching a real track.

Run:  .venv/Scripts/python.exe analysis/verify_owner_remap.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import owner_remap as OR  # noqa: E402

FAILS = []


def check(name, got, want):
    ok = (got == want)
    if not ok:
        FAILS.append("%s: got %r, want %r" % (name, got, want))
    print("  [%s] %-64s %r" % ("PASS" if ok else "FAIL", name, got))


def main():
    print("Golden vectors -- T3 narrow remap")
    print()

    print("1. slot_of_track")
    check("finds the slot holding a track", OR.slot_of_track({"Left": 7, "Right": 8}, 7), "Left")
    check("finds it after a swap", OR.slot_of_track({"Left": 8, "Right": 7}, 7), "Right")
    check("absent track -> None", OR.slot_of_track({"Left": 8, "Right": 9}, 7), None)
    check("empty mapping -> None", OR.slot_of_track({}, 7), None)
    # -1 is DR-1's "no identity this frame". Two unidentified hands must NOT look
    # like the same hand -- that is how a cube would follow the wrong hand.
    check("-1 never matches (no identity)", OR.slot_of_track({"Left": -1, "Right": -1}, -1), None)
    check("None track -> None", OR.slot_of_track({"Left": 7}, None), None)
    check("a real id is not matched by a -1 slot",
          OR.slot_of_track({"Left": -1, "Right": 7}, 7), "Right")

    print()
    print("2. remap_owner -- THE DEFECT: the cube must follow the HAND")
    # The recorded steal: t7 owns via slot Right, then t7 and t8 swap slots.
    check("track stays put -> owner unchanged",
          OR.remap_owner("Right", 7, {"Left": 8, "Right": 7}), "Right")
    check("** tracks SWAP -> owner follows the track to its new slot",
          OR.remap_owner("Right", 7, {"Left": 7, "Right": 8}), "Left")
    check("...so the cube does NOT stay with the slot the other hand took",
          OR.remap_owner("Right", 7, {"Left": 7, "Right": 8}) != "Right", True)

    print()
    print("3. the cases 4.1 got wrong -- these must NOT change behaviour")
    # §3.1: the fallback fired exactly when the id was missing, and that is when
    # release needed to find the cube. Here, absence must be a NO-OP.
    check("holding track ABSENT -> owner unchanged (coast/release owns this)",
          OR.remap_owner("Right", 7, {"Left": 8, "Right": 9}), "Right")
    check("no tracks at all -> owner unchanged",
          OR.remap_owner("Right", 7, {}), "Right")
    check("both slots unidentified (-1) -> owner unchanged",
          OR.remap_owner("Right", 7, {"Left": -1, "Right": -1}), "Right")
    check("unowned cube stays unowned", OR.remap_owner(None, 7, {"Left": 7}), None)
    check("owned but no holder recorded -> unchanged (never guess)",
          OR.remap_owner("Right", None, {"Left": 7, "Right": 8}), "Right")
    # §3.5: a NEW track must not inherit a claim. A different id simply does not
    # match, so the cube stays where it was rather than following the newcomer.
    check("a DIFFERENT track in the slot does not capture the cube",
          OR.remap_owner("Right", 7, {"Left": 99, "Right": 42}), "Right")

    print()
    print("4. remap_all -- batch form both tools call")
    owners = {"large": "Right", "small": "Left", "tiny": None}
    holders = {"large": 7, "small": 8}
    ids = {"Left": 7, "Right": 8}
    check("batch remaps each independently",
          OR.remap_all(owners, holders, ids),
          {"large": "Left", "small": "Right", "tiny": None})
    check("batch keeps every cube key", sorted(OR.remap_all(owners, holders, ids)),
          ["large", "small", "tiny"])

    print()
    print("5. the A/B switch must restore pre-remap behaviour exactly")
    saved = OR.OWNER_FOLLOWS_TRACK
    try:
        OR.OWNER_FOLLOWS_TRACK = False
        check("flag off -> owner never moves",
              OR.remap_owner("Right", 7, {"Left": 7, "Right": 8}), "Right")
        check("flag off -> batch is identity",
              OR.remap_all(owners, holders, ids), owners)
    finally:
        OR.OWNER_FOLLOWS_TRACK = saved
    check("flag restored", OR.OWNER_FOLLOWS_TRACK, saved)

    print()
    print("6. IDEMPOTENCE -- applying it twice must change nothing further")
    once = OR.remap_owner("Right", 7, {"Left": 7, "Right": 8})
    twice = OR.remap_owner(once, 7, {"Left": 7, "Right": 8})
    check("remap is idempotent", twice, once)

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
