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
   - **Proposed change, NOT yet decided (2026-08-02)**: the perception
     spec's M10.7 argues for a **~400 ms grace period** before dropping —
     "losing tracking is not the same as letting go." That would change
     this rule's behaviour, so it is a **game-design decision for the
     owner**, not something to introduce as a side effect of building
     M10. Note it also interacts with the same-frame release/re-snap
     ordering fix (a cube held in limbo must be excluded from other
     hands' snap passes meanwhile). `PERCEPTION_LAYER_SPEC.md` M10.
   - **KNOWN ISSUE (observed 2026-08-02, recorded only — not being fixed
     now): a hand can steal another hand's cube by occluding it.** If
     hand A is holding a cube and hand B moves in front of it, hand A's
     tracking is lost, this rule releases the cube, and hand B — which is
     by definition right where hand A was, hence within grab radius —
     snaps it on a following frame. **Mechanism is inferred from the
     rules, not instrumented**: the existing same-frame ordering fix
     (§13.5) only prevents re-snapping on the *same* tick, not the next
     one. Expected to be resolved as a side effect of refining snap
     control — in particular M10.7's grace period would keep the cube
     held through the occlusion, leaving nothing to steal. Recorded so it
     is not rediscovered as a new bug. Merged queue item N8.

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
   - **Bug found and FIXED (2026-08-01, later conversation): this rule was
     silently INVERTED in production only** (debug tool was always
     correct) — root cause was a mirrored-vs-unmirrored handedness label
     mismatch in the server's wire protocol (`hands_visualizer.py`), not
     the rule's own formula, which was identical in both files. Fixed at
     the source (`_mirror_handedness()`). Live-confirmed 2026-08-02. Full
     account: `GESTURE_PIPELINE_SPEC.md` §13.6.1.
   - **Two changes queued (2026-08-02, perception spec)**: (a) a **`K`
     fixture test** locking this rule's sign convention permanently, so
     the inversion above cannot regress silently — queued first in the
     merged build queue; (b) **DR-2**: this rule depends on `palmFacing`,
     so it must be **suppressed while the palm is edge-on to the camera**,
     where the sign is genuinely unobservable and chatters on noise. Its
     existing armed-exception state machine should be reconciled with
     DR-2's freeze rather than duplicating it. `PERCEPTION_LAYER_SPEC.md`
     M5d/M5e.

4. **Rotation while snapped.** While a hand holds a cube, the cube's
   orientation follows the hand's rotation — but RELATIVE to how the hand
   was oriented at the moment of the grab, not absolute: grabbing a cube
   never makes it pop/snap to match whatever twist the hand happens to be
   at, it only starts rotating from there as the hand keeps turning.
   Active for any snapped hand regardless of pose (not gated on
   open-palm — that detector is parked, not just missing yet, see "Not yet
   built" below).
   - Ported to production (`Resources/HandsTriggeredActions.py`/
     `Resources/CubeWindow.py`, wire protocol extended) and **confirmed
     working live against a real camera** 2026-08-01. Full account:
     `GESTURE_PIPELINE_SPEC.md` §13.7.
   - **Known issue (TODO, separate from below), REFRAMED 2026-08-01 (later
     conversation), mechanism resolved in a follow-up discussion: the
     object currently translates when the hand rotates.** Root cause
     corrected — this is NOT about the tracked hand-position anchor
     (§13.3) not being precisely at the true rotational pivot; it's that
     translation (rule 1/row 5) has **no grab-time offset at all** — the
     cube is forced to sit exactly on one tracked anchor every single
     frame. Chosen fix: **distance-weighted live landmark tracking** — at
     grab, freeze a weighted set of ~9 phalange-adjacent landmarks
     (fingertips + MCPs), weighted by proximity to the object; each frame,
     recompute the weighted position from those same landmarks' real
     tracked motion (no rotation math reused, stays purely 2D/pixel-based)
     — literally "in relation to the phalanges," decided by direct
     follow-up question. Literature-grounded (human grasp biomechanics —
     grip point depends on object size, not one fixed landmark; the
     broader "offset captured at grab, held fixed" principle used by
     Unity's XR Interaction Toolkit and Meta's Horizon OS hand-grab SDKs).
     **Once fixed, some translation during pure rotation is expected and
     correct** (an object held off-center from the wrist genuinely swings
     when the wrist twists) — this is no longer "the cube shouldn't
     translate at all." Full design + citations: `GESTURE_PIPELINE_SPEC.md`
     §14.1 (rewritten). Not yet started — first in the confirmed build
     order.
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
   - **Filter audit (2026-08-01, later conversation): KEPT, but flagged
     for future re-test.** Confirmed this filter's improvement is real and
     substantial (eliminates all >30°/>60° jumps in tested data), not
     marginal, so removing it now would be a regression. **TODO**: once
     future improvements land (Object Jump Correction, Z-axis translation/
     depth calibration), re-test whether this filter has become redundant
     — don't keep it out of inertia if a later fix resolves the underlying
     depth-ambiguity problem at its source. `GESTURE_PIPELINE_SPEC.md`
     §13.7.1.

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

6. **Translation follows a grab-relative, distance-weighted point, not a
   fixed single anchor.** While a hand holds a cube, the cube's position
   is a weighted combination of ~9 phalange-adjacent landmarks (5
   fingertips + 4 knuckles), weighted by how close each one was to the
   cube at the moment of grab and FROZEN from then on — so the cube keeps
   its own position at grab (no pop/snap onto the hand) and only moves as
   those same landmarks actually move afterward. Replaces the earlier
   design where the cube was forced to sit exactly on one fixed
   hand-center point every frame, which caused a visible pop at grab and
   incorrect coupling when the hand only rotated in place.
   - `Resources/HandsTriggeredActions.py` (`_compute_grab_weights`/
     `_weighted_position`, production) — `LiveSnapDebug.py` (identical
     functions, debug tool). Redesigned, live-verified, and ported to
     production 2026-08-01 — full account: `GESTURE_PIPELINE_SPEC.md`
     §14.1/§14.1.1/§14.1.3.
   - **Known issue (TODO): swings toward the palm specifically when the
     hand turns sideways (yaw), not pitch/roll.** A purely-2D signal can't
     distinguish yaw-driven foreshortening from real repositioning —
     likely shares root cause with the not-yet-built Z-axis translation
     gesture. Deliberately deferred; proposed direction is a future
     startup Z-axis calibration step. `GESTURE_PIPELINE_SPEC.md` §14.1.1.
     **Fix path identified 2026-08-02**: the perception spec's M9
     (foreshortening-corrected depth, using M5a's edge-on measure as the
     `|cos θ|` term) is that "startup calibration" idea made concrete.
     Queued as item T4 in the merged build queue.
   - **Known issue (TODO, named "Object Jump Correction" for reference) —
     ROOT-CAUSED, NOT YET FIXED: the cube can jump to a completely
     different on-screen location and back.** No longer "spurious" —
     made reproducible via a record-and-confirm-per-take workflow and
     root-caused from real data: for a few frames, MediaPipe briefly mixes
     up hand identity, reporting a DIFFERENT physical hand's position
     under the SAME handedness label (all 9 candidate landmarks move
     together coherently, high confidence throughout, self-corrects a few
     frames later) — NOT frame-edge extrapolation, NOT per-landmark noise.
     A first fix attempt (exclude out-of-bounds candidates) was built and
     verified against real data to NOT help, and was discarded rather than
     shipped anyway. A real fix needs a filter design comparable in
     complexity to rule 4's own rotation filter (which took two iterations
     to get right) — explicitly deferred to a future round of
     improvements, not attempted blind. Full account + reusable recorded
     data: `GESTURE_PIPELINE_SPEC.md` §14.1.4.
     **Fix path identified 2026-08-02**: the perception spec maps this to
     **DR-1** (make handedness a track-level property established once,
     rather than a per-frame decision — which is the structural cause) plus
     **M4's χ² gate** (reject the implausible single-frame excursion and
     coast on the model). Queued as item T3 in the merged build queue;
     expected to close in Phases 1–2 rather than needing its own filter.

## Not yet built

- **Open-palm/closed-fist detection: PARKED (2026-08-01, later
  conversation)**, not intended to be pursued for the moment — was
  blocked on finding a working fist-detection approach (MediaPipe's
  built-in classifier was tried and reverted, see
  `GESTURE_PIPELINE_SPEC.md` §13.5), now deprioritized rather than
  actively worked on. Its two former dependents no longer need it:
  rotation stays permanently ungated (rule 4), and release no longer plans
  to use closed-fist at all — see the next item.
- **Release trigger — quick full hand-open, now the sole active plan
  (design confirmed 2026-08-01, not yet built)**: unsnap by quickly fully
  opening the hand (fingers extending outward fast while the wrist stays
  stable) — specifically designed to be distinguishable from Z-axis
  translation below (moving the whole hand toward/away from the camera,
  where fingers AND wrist would scale together instead). The closed-fist
  release plan is superseded by this, not coexisting with it, since
  closed-fist detection is parked above. Proposed recording-based
  discrimination plan: `GESTURE_PIPELINE_SPEC.md` §14.2. **Re-sequenced
  2026-08-02**: now gated behind its hard prerequisites — M4 (occlusion
  detection: without it, a partially-hidden hand drops its object) and
  M10 (commitment dynamics) — because building it first means building it
  twice. Merged queue item 4.4.
- Open-palm rotation gating — **not planned**: rotation stays permanently
  ungated now that open-palm/closed-fist detection is parked (rule 4).
- **Z-axis (camera-view-axis) translation, design confirmed 2026-08-01, not
  yet built**: moving a snapped hand closer to/farther from the camera
  would move the cube along the same axis. Driven by apparent hand-span
  ratio (not raw MediaPipe `z`), mapped absolutely/continuously like
  today's X/Y translation. Snap itself would become a 3D proximity check
  (hand must be close to the cube on X, Y, **and** this new Z axis, not
  just X/Y as today). **Re-sequenced 2026-08-02**: gated behind M2
  (calibrated skeleton) and M9 (metric depth) — no calibrated skeleton
  means no usable depth. Merged queue item 4.2. **Related (2026-08-01):
  shares root cause with the translation fix's yaw/palm-sinking
  limitation above** — M9's foreshortening correction addresses both.
  **Still undecided**: what the 3D snap check does when `depthValid` is
  false — fall back to 2D proximity, or refuse to snap. Full design:
  `GESTURE_PIPELINE_SPEC.md` §14.3.

**Build order — see `PART_ONE.md` §3.1.** As of 2026-08-02 the project has
**one merged build queue** covering both the gesture features above and
the newly-integrated perception-layer modules
(`Claude/PERCEPTION_LAYER_SPEC.md`). The previous ordering recorded here
(translation-pivot fix → release trigger → Z-axis) is superseded:
perception Phases 0–2 now come first, and the two remaining features are
gated behind their prerequisites. Open-palm/closed-fist detection stays
parked and unqueued.

## Status

Current build target: Local_pc desktop prototype (`PART_ONE.md` §1). Web
port planned later, after the Local_pc build is done — with `HandState` v2
(`PERCEPTION_LAYER_SPEC.md` §2) as the contract that port reimplements
against.
