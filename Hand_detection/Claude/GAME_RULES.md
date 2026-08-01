# Game Rules

Living inventory of the game's interaction rules, in plain language, as
they're confirmed and built. This file lists *what* the rules are; for
*why* (design rationale, state-of-the-art checks, build status) see
`GESTURE_PIPELINE_SPEC.md` §13 and `PART_ONE.md` §3. Add a new rule here
every time one is confirmed and implemented — keep entries short and in
plain language, not implementation detail (link to the code instead).

## Object snapping & manipulation

1. **Snap on proximity.** A hand snaps to an object when the hand's
   position gets close enough to that object (within its grab radius).
   Either hand can snap either object; each hand holds at most one object
   at a time.
   - `Resources/HandsTriggeredActions.py` (`_try_snap`/`on_hands_frame`,
     production) — `LiveSnapDebug.py` (`_try_snap`/`update_hands`, debug
     tool).

2. **Un-snap on tracking loss.** If a hand holding an object goes out of
   the camera's view (tracking lost), the object un-snaps and freezes in
   place at its last position.
   - Same files as rule 1, tracking-loss release branch.

3. **Thumb-outward snap restriction.** A hand cannot snap an object while
   oriented with the thumb outward (i.e. the camera is facing the back of
   the hand) — *unless* the hand was already oriented with the thumb
   outward at the moment the object it's now trying to snap was last
   un-snapped, and the hand has not presented with the thumb inward since
   that un-snap. In practice: releasing an object while thumb-outward lets
   you immediately re-grab it in that same orientation without first
   turning your palm back to the camera; any other approach while
   thumb-outward is blocked.
   - Same files as rule 1: `_is_thumb_outward()` plus the
     `last_known_thumb_outward`/`thumb_outward_snap_allowed` per-hand state
     pair. Orientation sign convention calibrated live 2026-08-01 (see
     `GESTURE_PIPELINE_SPEC.md` §13.6).

## Not yet built

- Rotation while snapped (planned: gated on the hand being open-palm).
- Release via closed fist (planned; blocked on finding a working
  fist-detection approach — MediaPipe's built-in classifier was tried and
  reverted, see `GESTURE_PIPELINE_SPEC.md` §13.5).

## Status

Current build target: Local_pc desktop prototype (`PART_ONE.md` §1). Web
port planned later, after the Local_pc build is done.
