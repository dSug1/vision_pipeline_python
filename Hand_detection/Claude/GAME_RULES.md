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

4. **Rotation while snapped.** While a hand holds a cube, the cube's
   orientation follows the hand's rotation — but RELATIVE to how the hand
   was oriented at the moment of the grab, not absolute: grabbing a cube
   never makes it pop/snap to match whatever twist the hand happens to be
   at, it only starts rotating from there as the hand keeps turning.
   Active for any snapped hand regardless of pose (not gated on
   open-palm — that detector doesn't exist yet, see "Not yet built"
   below).
   - Ported to production (`Resources/HandsTriggeredActions.py`/
     `Resources/CubeWindow.py`, wire protocol extended) and **confirmed
     working live against a real camera** 2026-08-01. Full account:
     `GESTURE_PIPELINE_SPEC.md` §13.7.
   - **Known issue (TODO, separate from below): the object currently
     translates somewhat when the hand only rotates in place** (it
     shouldn't). The tracked hand-position anchor (§13.3, wrist + 4 MCP
     centroid) isn't exactly at the hand's true rotational pivot, so pure
     wrist rotation still traces a small arc in image space. Candidate
     fixes and a recording-based verification plan: `GESTURE_PIPELINE_SPEC.md`
     §14.1. Not yet started.
   - **Known issue (TODO): rotation quality is still poor with the back
     of the hand facing the camera.** A pitch-crossing collinearity
     problem (rotation glitching when the hand rotates through edge-on,
     back-of-hand facing the camera) was found and substantially — but not
     completely — fixed 2026-08-01: large per-frame jumps are now much
     less frequent in that pose, but still occur occasionally. Three
     alternative landmark choices (thumb-based, PCA/centroid-averaged)
     were tested against recorded data and all failed to improve it
     further — the remaining noise looks like a genuine, shared
     (not per-landmark) monocular depth-estimation limit at that viewing
     angle, not a fixable landmark-selection problem. A temporal/predictive
     (Kalman-style) filter was then implemented and live-tested — a real
     but INSUFFICIENT improvement ("slightly better but not yet solving the
     issue"), kept in place since it's a net improvement, but **the TODO
     remains OPEN**: four attempts total (three geometric, one temporal)
     have each helped without fully resolving it, increasingly looking like
     a genuine floor of a single-monocular-camera setup rather than a
     software fix away. See `GESTURE_PIPELINE_SPEC.md`
     §13.7's last section before investigating further.

5. **Cubes are real rotating 3D shapes, not flat squares — and the cube
   itself is just a placeholder for future imported 3D objects.** Each
   cube has 6 colored faces in 3 opposite-pair color families, one side of
   each pair a darker shade of the other. The **large** cube (yellow /
   violet / turquoise) is exactly 2x the size of the **small** cube
   (green / red / blue) in every dimension — snap radius scales with each
   cube's own size accordingly (`PART_ONE.md` §5's long-open "grab radius
   scaled to object size" item, resolved by this). The rendering pipeline
   itself is generic over ANY 3D mesh (verified live by swapping in a
   completely different shape with zero code changes) — a real imported
   3D object later is a matter of building a different mesh, not
   rewriting any drawing/rotation code.
   - `Resources/CubeWindow.py` (`_draw_object_3d`, backface-culled +
     painter's-algorithm depth-sorted, mesh-generic), built 2026-08-01
     once rotation was confirmed working end-to-end. A live-found morphing
     bug (cube corners could flip to the wrong side at certain rotations)
     was found and fixed the same day — full account and the
     mesh-generalization design: `GESTURE_PIPELINE_SPEC.md` §13.7-§13.8.

## Not yet built

- Release via closed fist (original plan; blocked on finding a working
  fist-detection approach — MediaPipe's built-in classifier was tried and
  reverted, see `GESTURE_PIPELINE_SPEC.md` §13.5).
- **New candidate release trigger, proposed 2026-08-01, not yet built**:
  unsnap by quickly fully opening the hand (fingers extending outward
  fast while the wrist stays stable) — specifically designed to be
  distinguishable from a future depth/Z-axis-translation gesture (moving
  the whole hand toward/away from the camera, where fingers AND wrist
  would scale together instead). Proposed recording-based discrimination
  plan: `GESTURE_PIPELINE_SPEC.md` §14.2. Not yet confirmed whether this
  replaces or complements the closed-fist plan above.
- Open-palm rotation gating (rotation is currently ungated — see rule 4).
- Object translation shouldn't couple to pure hand rotation — see rule 4's
  TODO and `GESTURE_PIPELINE_SPEC.md` §14.1.

## Status

Current build target: Local_pc desktop prototype (`PART_ONE.md` §1). Web
port planned later, after the Local_pc build is done.
