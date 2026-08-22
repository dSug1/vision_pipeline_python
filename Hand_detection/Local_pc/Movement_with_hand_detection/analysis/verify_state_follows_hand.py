"""Rule 3's snap permission must follow the HAND, not the handedness slot.

THE MEASURED DEFECT THIS LOCKS OUT
-----------------------------------
`GAME_RULES.md` rule 3: a hand cannot snap while thumb-outward (back of hand to
camera) UNLESS it was already thumb-outward when that object was last un-snapped.

4.1 moved cube OWNERSHIP onto the DR-1 track id but left rule 3's state --
`_last_known_thumb_outward`, `_thumb_outward_snap_allowed`, and DR-2's
`_palm_facing_trackers` -- keyed by SLOT. So when two hands cross and the labels
swap, the incoming hand INHERITS the other hand's armed permission.

Owner, live: "one hand show palm and the other show back, the back occludes the
palm: the cube drops but it seems in some cases the back hand can grab the
dropped cube (which should be prohibited if I recall the rules)". Measured on
`2026-08-22_163014_optionA_frozen_cube_check`: **4 snaps by a thumb-outward hand
that rule 3 forbids.**

⚠ This exercises PRODUCTION's own module state, not a copy of the rule.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_state_follows_hand.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Resources import HandsTriggeredActions as HTA  # noqa: E402

FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:66s} got {got!r}")
    if not ok:
        FAILURES.append(name)


def main():
    # ⚠ This file tests the 4.1 IDENTITY MIGRATION, which is REVERTED
    # (HandsTriggeredActions.TRACK_OWNERSHIP = False, owner instruction
    # 2026-08-22 -- see Claude/POSTMORTEM_4_1_IDENTITY_MIGRATION.md).
    # SKIP rather than FAIL: a suite that is permanently red stops being read,
    # and these checks are still correct for the day the flag goes back on.
    if not getattr(HTA, "TRACK_OWNERSHIP", False):
        print("=" * 78)
        print("SKIPPED -- TRACK_OWNERSHIP is False (4.1 identity migration reverted).")
        print("Set it True to re-enable the feature and these checks.")
        print("=" * 78)
        return 0


    print("=" * 82)
    print("Rule 3's snap permission follows the HAND, not the slot")
    print("=" * 82)

    HTA._track_registry.reset()
    HTA._bound_bundles.clear()

    print("\n--- setup: hand A (track 3) in Left, hand B (track 8) in Right ---")
    HTA.on_hand_tracks_frame(3, 8)
    HTA._bind_track_state(0.0)
    # A earns the exception: it was thumb-outward when it released something
    HTA._last_known_thumb_outward["Left"] = True
    HTA._thumb_outward_snap_allowed["Left"] = True
    HTA._last_known_thumb_outward["Right"] = False
    HTA._thumb_outward_snap_allowed["Right"] = False
    HTA._writeback_track_state(0.0)
    check("track 3 is armed", HTA._track_registry.state(3).thumb_outward_snap_allowed, True)
    check("track 8 is NOT armed", HTA._track_registry.state(8).thumb_outward_snap_allowed, False)

    print("\n--- !! THE DEFECT: the labels swap (hands cross) ---")
    HTA.on_hand_tracks_frame(8, 3)          # track 8 now in Left, track 3 in Right
    HTA._bind_track_state(40.0)
    check("!! the Left SLOT is now NOT armed (track 8 moved in)",
          HTA._thumb_outward_snap_allowed["Left"], False)
    check("!! the Right SLOT is now armed (track 3 moved in)",
          HTA._thumb_outward_snap_allowed["Right"], True)
    print("      -> the permission travelled with the HAND. Before this fix the")
    print("         slots kept their values and hand B inherited A's permission.")

    print("\n--- the palm/back reading travels too (DR-2 state) ---")
    check("track 3's reading followed it to Right",
          HTA._last_known_thumb_outward["Right"], True)
    check("track 8's reading followed it to Left",
          HTA._last_known_thumb_outward["Left"], False)

    print("\n--- DR-2's tracker OBJECT follows the hand, not the slot ---")
    t3 = HTA._track_registry.state(3).palm_facing
    check("the Right slot now holds track 3's own PalmFacingTracker",
          HTA._palm_facing_trackers["Right"] is t3, True)

    print("\n--- a brand-new hand starts unarmed (no inheritance) ---")
    HTA.on_hand_tracks_frame(99, 3)
    HTA._bind_track_state(80.0)
    check("!! track 99 is NOT armed", HTA._thumb_outward_snap_allowed["Left"], False)

    print("\n--- no track ids -> the dicts are left alone (legacy behaviour) ---")
    print("      every pre-4.1 harness relies on this")
    HTA.on_hand_tracks_frame(-1, -1)
    HTA._thumb_outward_snap_allowed["Left"] = True
    HTA._bind_track_state(2000.0)           # past the slot-memory window
    check("an injected value survives when there is no identity",
          HTA._thumb_outward_snap_allowed["Left"], True)

    print("")
    print("--- !! 6. A HAND THAT LEAVES AND RETURNS IS A *NEW* TRACK ---")
    print("      Owner, live: 'the hand exited as palm and came back as back and")
    print("      still could grab the cube. Then all the cubes frozed.'")
    print("      A new track must inherit NOTHING from the slot it appears in --")
    print("      not the snap permission, and not the tracker OBJECT (two tracks")
    print("      sharing one HandStateTracker is what froze every cube).")
    HTA._track_registry.reset(); HTA._bound_bundles.clear()
    HTA.on_hand_tracks_frame(20, -1)
    HTA._bind_track_state(0.0)
    HTA._thumb_outward_snap_allowed["Left"] = True
    HTA._last_known_thumb_outward["Left"] = True
    HTA._writeback_track_state(0.0)
    old = HTA._track_registry.state(20)

    HTA.on_hand_tracks_frame(21, -1)
    HTA._bind_track_state(40.0)
    new = HTA._track_registry.state(21)
    check("!! the returning hand is NOT armed", HTA._thumb_outward_snap_allowed["Left"], False)
    check("!! its palm/back reading is fresh", HTA._last_known_thumb_outward["Left"], False)
    check("!! it does NOT alias the old HandStateTracker", new.tracking is old.tracking, False)
    check("...nor the PalmFacingTracker", new.palm_facing is old.palm_facing, False)
    check("...nor the orientation filter",
          new.orientation_filter is old.orientation_filter, False)

    print("")
    print("--- 7. CONFIG is still carried, so a tuned coast is not silently lost ---")
    from Resources import hand_state as _HS
    HTA._track_registry.reset(); HTA._bound_bundles.clear()
    HTA._hand_state_trackers["Left"] = _HS.HandStateTracker(bridge_window_ms=999.0)
    HTA.on_hand_tracks_frame(30, -1)
    HTA._bind_track_state(0.0)
    check("a new track inherits the configured bridge window",
          HTA._track_registry.state(30).tracking.bridge_window_ms, 999.0)


    print("\n" + "=" * 82)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): " + ", ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED -- rule 3's state follows the hand.")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    sys.exit(main())
