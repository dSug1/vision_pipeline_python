<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1303-1377
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 5. Open items to resolve empirically, not now

- Pinch classification itself — archived, see the banner at the top of
  this file and `GESTURE_PIPELINE_SPEC.md` §13.
- ~~Exact grab-radius value (likely scaled to cube size)~~ — **resolved
  2026-08-01**: grab radius now scales to each candidate object's own
  `size` (`_try_snap` in both `HandsTriggeredActions.py` and
  `LiveSnapDebug.py`), a natural side effect of the large/small cube
  rework, see `GESTURE_PIPELINE_SPEC.md` §13.8.
- Tie-break rule if both hands' proximity triggers land on the same free
  cube in the same frame (currently unspecified — low-probability edge
  case, revisit only if it's actually hit in practice).
- Exact hand-span metric for the depth proxy (wrist↔middle-MCP vs. a full
  bounding-box diagonal) — moot for now since row 6 is dropped; revisit
  only if depth-proxy scale/color comes back.
- ~~See `GESTURE_PIPELINE_SPEC.md` §13.4 for the new gesture set's own open
  questions (whether `Open_Palm`/`Closed_Fist` need custom training,
  whether snap should be blocked while closed-fist, whether rotation's
  `Open_Palm` gate is the right design).~~ — **Moot (2026-08-01, later
  conversation): row 2 is parked, not being pursued for the moment.**
  Rotation stays permanently ungated by design; snap is not blocked by
  closed-fist since closed-fist detection itself is parked.
- **Reframed (2026-08-01, later conversation), mechanism resolved,
  implemented, and CONFIRMED WORKING LIVE — not yet ported to
  production** — object translates when the hand
  rotates. **Not an anchor-selection problem**: the actual defect is that
  row 5's translation logic has no grab-time offset at all (cube center
  forced to exactly equal one tracked anchor every frame — confirmed by
  reading `HandsTriggeredActions.py`). Fix, chosen mechanism: distance-
  weighted live landmark tracking — freeze a weighted set of ~9
  phalange-adjacent landmarks (fingertips + MCPs) at grab, weighted by
  proximity to the object, then recompute the weighted position live each
  frame from those same landmarks' real tracked motion. Stays purely
  2D/pixel-based, no reuse of row 7's rotation math. Literature-grounded
  (Napier grasp taxonomy — grip point depends on object size, not one
  fixed landmark; Unity XRI's Dynamic Attach / Meta Horizon's GripPoint
  establish the broader "offset captured at grab, held fixed" principle
  this extends). Some translation during pure rotation is now understood
  to be physically CORRECT (an off-center held point swings when the
  wrist twists), not a bug to eliminate. **Verified against 7 real hold
  intervals (2026-08-01)**: no-pop exact, jitter comparable to today,
  translation scales with rotation as expected. **Known deferred
  limitation**: swings toward the palm under yaw specifically (pitch/roll
  fine) — decision made to implement as-is and revisit alongside a future
  Z-axis startup calibration idea (see row 9). Full design + citations +
  verification results: `GESTURE_PIPELINE_SPEC.md` §14.1/§14.1.1
  (rewritten). **First in the confirmed build order.**
- **NEW: "Object Jump Correction" (2026-08-01, same day, later
  conversation) — ROOT-CAUSED, NOT YET FIXED, sequencing not yet
  decided.** Confirmed (via a record-and-confirm-per-take workflow) to be
  a whole-hand landmark-cluster teleport — MediaPipe briefly mixing up
  hand identity under the same handedness label for a few frames, then
  self-correcting — not frame-edge extrapolation (a first fix attempt for
  that was built, verified against real data to NOT help, and discarded).
  Needs a filter design comparable in complexity to rotation's own
  (§13.7, which took two iterations). Explicitly deferred to "a future
  round of improvements" — ask the user where it fits in the build order
  before starting. Full account + reusable recorded data:
  `GESTURE_PIPELINE_SPEC.md` §14.1.4.
- **Confirmed as the sole active release-trigger plan (2026-08-01, later
  conversation)** — a release trigger (unsnap by quickly fully opening the
  hand), designed to be distinguishable from the now-designed Z-translation
  gesture (row 9); proposed 6-recordings-per-hand-position discrimination
  plan: `GESTURE_PIPELINE_SPEC.md` §14.2. The closed-fist release
  alternative is now parked (row 2 is parked), so this no longer needs to
  be weighed against it — it's the one plan going forward. **Second in the
  confirmed build order.**
- **New, design confirmed 2026-08-01 (later conversation), not yet
  started** — Z-axis (camera-view-axis) translation (matrix row 9):
  hand-span-ratio-driven, absolute/continuous mapping, snap gating
  extended to 3D. Queued third, after the pivot fix and release trigger
  above. Open unknowns (exact ratio→Z mapping, how Z-tolerance relates to
  the existing grab radius, hand-size recalibration): `GESTURE_PIPELINE_SPEC.md`
  §14.3.

<!-- VERBATIM-END -->
