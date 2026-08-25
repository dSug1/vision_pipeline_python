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

2. **Un-snap on tracking loss — after a 150 ms coast.** If a hand holding an
   object goes out of the camera's view (tracking lost), the object un-snaps
   and freezes in place at its last position. **Since 2026-08-21 the release
   waits out a 150 ms coast first**: while the hand is missing but the coast
   has not expired the object stays held and frozen where it is, and if the
   hand comes back the object walks back to it over 3 frames instead of
   jumping. Only when the coast expires does the object un-snap.
   - Same files as rule 1, tracking-loss release branch, plus
     `Resources/hand_state.py` (`BRIDGE_WINDOW_MS`, `RESYNC_BLEND_FRAMES`).
     Queue **D1/D2/D3**; owner accepted it live 2026-08-21.
   - **⚠⚠ THIS IS NOT M10.7's GRACE PERIOD, and the difference is worth
     stating precisely because the two are easy to confuse — they have the
     same shape at different scales.** The coast is a **sensor** rule: for
     150 ms there was no measurement, so there was no evidence to act on,
     and the number is the measured median detection gap (128 ms) rather
     than a judgement about the player. M10.7's grace period below is a
     **game** rule: it holds the object through a loss the sensor reported
     correctly, on the argument that *"losing tracking is not the same as
     letting go"*, and it comes with a UI signal. **M10.7 remains deferred
     and undecided** — see the next bullet, which is unchanged.
   - ✅ **FIXED 2026-08-22 (queue T3): a handedness RELABEL no longer drops the
     object.** Ownership was keyed to MediaPipe's Left/Right label, which is not
     stable, so when the label moved the object was orphaned — **113 of 205
     spurious releases, the single largest cause**, larger than dropouts. A held
     object's owner now follows its tracked hand across a relabel
     (`Resources/owner_remap.py`). Measured on a recorded take: the spurious
     drop-and-regrab disappears, and it took a **single hand moving between
     labels with no second hand present** to trigger it.
     - ⭐ **It also closed a route nobody had named**: when the two hands swapped
       labels, a held object passed to the *other physical hand* with **no
       un-snap and no snap at all** — so rule 3 was never consulted. That was the
       one way a back-of-hand hand could take an object legitimately held by the
       other, and it is why ordinary back-of-hand grabs were correctly blocked
       while that one was not.
     - ⚠ An earlier client-side repair was built, live-tested on 2026-08-21 and
       **reverted on 2026-08-22**: it identified "the same hand" by POSITION,
       which cannot separate two hands in the same place, and it handed a held
       object to the operator's other hand. ⛔ **Do not re-attempt that approach.**
       The shipped fix uses the tracked identity instead, and deliberately leaves
       ownership expressed as a hand SLOT so nothing else changed.
   - ⭐ **OBJECTS ARE CONFINED TO A PLAY AREA, ADDED 2026-08-23 (U9).** Every
     object is constrained to the display window inset by a fixed margin (60 px,
     which is half a hand width at 40 cm — the closest the operator works). It
     cannot be pushed to the edge of the display, however many times it is
     nudged. The margin is the same for every object and needs no per-object
     setup: the bounds are derived from the object's own size.
     - ⛔ **This replaced two attempts to do it by DROPPING the object when the
       hand neared the edge, both reverted.** They could not work: an object
       keeps whatever offset it had from the hand when it was grabbed, so it can
       sit much closer to the edge than the hand does, and each grab-push-drop
       cycle walks it further out. Deciding *when to let go* can never decide
       *where the object may be*. Do not re-propose a hand-side trigger for this.
     - ✅ **(a) IS DONE — the play area became a WORLD VOLUME on 2026-08-23
       (queue 4.2), and it is now **rule 10** above.** The margin never changed:
       it was always a real-world distance (half a hand breadth, ~42.5 mm), and
       60 px was only how that looks at 40 cm.
       ⚠ **(b) is still open (queue U2):** for an imported 3D object the margin
       must be applied against a bounding-sphere radius, not a single size, or
       the boundary will move as the object rotates.

   - ⭐ **Side effect on N8 (cube-stealing, below): partially closed for
     free.** An occlusion shorter than 150 ms no longer releases the cube,
     so there is nothing for the occluding hand to steal. Occlusions longer
     than that still steal. Not measured live — recorded as an expected
     consequence of the mechanism, not as a fix.
   - **Proposed change — DEFERRED BY THE OWNER, 2026-08-04. Do not build it,
     and do not re-propose it as a side effect of some other item.** The
     perception spec's M10.7 argues for a **~400 ms grace period** before
     dropping — "losing tracking is not the same as letting go" — and it
     would also close N8 (cube-stealing). The owner has deliberately left
     it undecided: *"I don't want to overbuild with layers of rules for the
     moment."*
     - **This is a standing design preference, not a one-off deferral.**
       The rule set is meant to stay small and legible; a rule that exists
       to patch the consequences of another rule is exactly what is being
       avoided. Weigh any new *rule* proposal against that first, the same
       way filter proposals are weighed against the no-heuristic-pile-up
       rule.
     - Revisit only if the immediate-drop behaviour becomes a felt problem
       in live play, and raise it as an explicit question rather than
       bundling it into a module. ⭐ **THAT CONDITION IS NOW MET AND THE
       QUESTION IS OPEN (2026-08-21, queue D4).** Immediate-drop was
       measured, not merely felt: **205 spurious releases across the
       corpus.** The 150 ms coast above removes a share of the 83 that were
       true detection dropouts. **What it does NOT address is a hand that is
       genuinely lost for longer than the sensor gap** — which is what M10.7
       is actually about. So the owner's question is now answerable with
       numbers rather than impressions, and it is still the owner's. Note it also interacts with the same-frame release/re-snap
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

3. ~~**Thumb-outward snap restriction.**~~ ⛔⛔ **REMOVED 2026-08-25** (owner,
   queue `F1`). **An object may now be grabbed at any palm facing, including with
   the back of the hand to the camera, and including on re-entry into the frame
   window.** Owner: *"condition that cube cannot be grabbed if back of the hand is
   shown to the camera is removed."*
   - **What it used to say**: a hand could not snap while thumb-outward *unless*
     it was already thumb-outward when the object was last un-snapped and had not
     shown thumb-inward since. Kept here because rules 1, `U8` and `T3` below all
     refer to it, and because the un-snap/re-grab behaviour it describes is what
     several recorded takes were made to exercise.
   - ⭐ **Why it went, and it was not for convenience.** It read
     `_is_thumb_outward()`, which applies a **handedness-dependent** correction and
     therefore **inverts on a wrong label** — and the label was wrong **10.8%** of
     the time until `U7` replaced it with geometry. Rotation quality with the back
     of the hand showing also measures **better**, not worse, on both control takes
     (16.8° vs 23.5°, and 11.8° vs 24.5°).
   - **Measured effect of the removal**, from the six takes whose recordings carry
     the rule's own fields (3432 hand-frames): the rule was refusing on **15.7%**
     of hand-frames, and on **8.3%** the hand held nothing, so a grab was genuinely
     blocked. Those 8.3% are now allowed.
   - ⚠ **This re-opens `N8`** (an object stolen by occluding the holding hand) —
     rule 3 had been suppressing part of it incidentally. The real fix is the grab
     trigger, `B5` + `4.4`. ⛔ Do not reintroduce a facing gate.
   - **State**: `thumb_outward_snap_allowed` is **deleted** from both tools,
     `handinput` and the recorder schema. `last_known_thumb_outward` **survives as
     an observation only** — it is on the debug HUD and is published as
     `palm_facing`; it gates nothing.
   - ⭐ **BEHAVIOUR ADDED 2026-08-22 (U8), owner-accepted live — A HAND THAT HAS
     JUST ENTERED THE FRAME CANNOT SNAP AT ALL for 200 ms.**
     Not a bug and not the edge-on latency below: the palm/back cue is computed
     from the THUMB's offset from the palm plane, so while a hand is still
     entering — the thumb being the last part to appear — that cue is not merely
     noisy but **undefined**, and MediaPipe supplies a plausible hallucinated
     thumb. Measured: a back-of-hand hand read as PALM and took a cube this rule
     forbade. The game now **refuses to snap while the chirality is provisional**
     rather than guess, which is the same choice rule 1's edge-on freeze makes.
     ⚠ **`U8` is KEPT, but note its first reason expired with rule 3 above.** It
     stands now on the OTHER thing chirality drives — the rotation sign and DR-2 —
     so snapping on a provisional chirality still hands the object a wrong frame.
     Worth re-measuring on its own; not silently dropped in a change that was not
     about it.
     ⚠ **Felt cost**: a grab by a just-entered hand is delayed by up to 200 ms
     (lowered from 400 ms after the owner found that too long) — *delayed*, never refused; the hand is still
     there when the gate opens. ⭐ The window is a DURATION, so the delay
     feels the same whether the rig is running 15 fps or 30 — which is the
     point: a frame count would have felt twice as long in dim light.
     See queue item **U8** and `analysis/u8_entry_settling.py`.
   - ⭐ **RELATED, 2026-08-22 (T3):** a held object no longer changes hands when
     the tracker relabels the two hands. Previously ownership followed the
     handedness *label*, so when the labels swapped the object silently passed to
     the other physical hand **without any un-snap or snap — so this rule was
     never consulted**. That was the one way a back-of-hand hand could take an
     object legitimately held by the other. `Resources/owner_remap.py`.
   - **⚠ KNOWN LATENCY, INTRODUCED 2026-08-03 — TO BE REMOVED BY QUEUE ITEM
     2.3.** Turning the hand palm↔back is registered *late*: the game keeps
     using the previous palm/back reading until the hand is clearly out of
     the edge-on zone, then catches up. It is never *wrong*, only delayed.
     - **Measured over 144 freeze episodes across the whole recording
       corpus** (not estimated): **median 96 ms, p90 163 ms — but p99
       1.8 s and max 3.5 s.** The long tail is not a defect in the
       mechanism: it occurs when the hand is held **sustained sideways-on**
       to the camera (worst in the two-hand near-miss/overlap takes), where
       the cue is genuinely unreadable for that whole period. The typical
       case really is about a tenth of a second, and a live test on
       2026-08-03 could not perceive it at all.
     - **The consequence to be aware of**: in a sustained sideways pose this
       rule can act on a palm/back reading up to ~3.5 s stale. Nothing has
       been observed to break because of it, and it is preferable to acting
       on a coin-flip, but it is a real window and is recorded rather than
       hidden.
     - **Why it exists.** Passing through edge-on, the palm/back cue is
       genuinely unreadable — measured at up to 765 sign flips per 1000
       frames, which no real hand motion can produce. DR-2 (queue item 2.2)
       therefore freezes the reading through that zone instead of acting on
       noise. Without it, a single spurious flip silently revoked this
       rule's own exception, so a legitimate re-grab was refused with no
       visible cause.
     - **Why it is temporary.** The design (spec M5e) also calls for
       *carrying the sign through* the zone by integrating the hand's
       angular velocity, so a genuine turn registers immediately on exit.
       That needs the orientation estimator in **queue item 2.3**, which is
       not built. **When 2.3 lands, this latency should be removed, not
       kept** — it is the cost of a missing component, not a design choice.
     - Full account: `PERCEPTION_LAYER_SPEC.md` §0.11.
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

7. **No snapping while depth is frozen.** ✅✅ **BUILT AND CONFIRMED LIVE 2026-08-23** (queue 4.2, BOTH tools — owner, debug: *"yes. this is working properly"*; production: *"this is working fine"*). When an object's depth
   cannot be measured — the hand is edge-on, so the depth reading is being *held*
   rather than measured — a hand cannot pick anything up.
   - **Why refuse rather than guess.** A frozen depth is a remembered value, not
     an observation, and 4.2 makes the grab check three-dimensional. Deciding
     whether a hand is close enough to an object using a number the sensor is not
     currently supplying is exactly the kind of confident-but-wrong answer that
     rule 3 spent this project's worst debugging on. It is the same choice the
     game already makes when the palm/back reading is untrustworthy (rule 1's
     edge-on freeze) and when a just-entered hand's chirality has not settled.
   - ⚠ **Flagged as tunable for game feel** (owner's framing). If refusing turns
     out to be too strict in play, the fallback to try is degrading to the flat
     2D grab radius while frozen, rather than refusing outright. ⛔ Do not change
     it on impression — measure how often the freeze actually coincides with a
     grab attempt first. Queue **4.2**; §14.3.2 had left this open and it is now
     closed. ⭐ **The measurement now exists**: the edge-on band covers **1.6%**
     of hand-frames over the whole corpus (`analysis/m9_working_distance.py`) —
     and that is a *ceiling*, since it counts every edge-on frame rather than
     those where a hand was also within grab radius of a free object. Production
     records `depth_valid` per hand, so narrowing it is a query against an
     existing session, not a new one. ⭐ **And it held up live: 2.0% in the first
     production take, nothing reported un-grabbable.**
   - ⭐⭐ **OWNER, 2026-08-23: KEEP AS IS, AND FILE IT FOR RECALL WHEN PLAYABILITY
     WORK STARTS.** Not a live concern. It is recorded as a **known dial**, so if
     the game ever feels reluctant to pick things up, this is one of the first two
     places to look — the other being `GRAB_Z_TOLERANCE_M`, and both are covered
     by queue **U12** (a start-of-game calibration step). ⛔ Do not touch either
     before then.

8. **An object moves toward and away from the camera with the hand that holds
   it.** ✅✅ **BUILT AND CONFIRMED LIVE 2026-08-23** (queue 4.2, BOTH tools — owner, debug: *"yes. this is working properly"*; production: *"this is working fine"*). Moving a
   holding hand nearer brings the object nearer; moving it away pushes the object
   away. The object grows and shrinks on screen accordingly, because it is nearer
   or further — **its real size never changes.**
   - **The grab frame is continuous in Z**, exactly as it already is in X/Y and
     in orientation: an object keeps its own depth at the instant of grab and
     moves only by how much the hand's apparent size changes afterwards. Picking
     something up never teleports it toward the hand.
   - **The object cannot be pushed out of reach.** It is confined to a depth
     range measured from where the operator's hands actually go (0.30–0.85 m,
     the p1–p99 of 86 109 recorded hand-frames). An object parked at either wall
     is still at a depth the hand demonstrably reaches, so it can always be
     picked up again.
   - **While the hand is edge-on the object's depth HOLDS** rather than guessing —
     the same suppression rule 1 already applies to the palm/back reading.
   - `GESTURE_PIPELINE_SPEC.md` §14.3 (design) and §14.3.5 (what was built).

9. **An object can only be picked up by a hand that is beside it — in all three
   dimensions.** ✅✅ **BUILT AND CONFIRMED LIVE 2026-08-23** (queue 4.2, BOTH tools — owner, debug: *"yes. this is working properly"*; production: *"this is working fine"*).
   Reaching *past* an object, or stopping *short* of it, no longer grabs it just
   because the hand crosses it on screen. ⚠ The two tolerances are deliberately
   different sizes: sideways it is the same reach that always applied, but along
   the camera axis it is much more forgiving, because the game can only estimate
   how far away a hand is by assuming a typical hand size — a player with unusual
   hands would otherwise be unable to pick anything up at all.

10. **The play area is a volume, not a rectangle.** ✅✅ **BUILT AND CONFIRMED LIVE 2026-08-23** (queue 4.2, BOTH tools — owner, debug: *"yes. this is working properly"*; production: *"this is working fine"*). Rule "an object may never reach the display
    edge" (U9) still holds, but the boundary is now a real distance in the world —
    half a hand's breadth — rather than a fixed number of pixels. ⭐ **So the
    on-screen boundary MOVES as an object changes depth**: it draws inward as the
    object recedes and outward as it approaches. That is the rule being correct,
    not a glitch — the margin exists to leave room for a hand, and a hand looks
    smaller when it is further away.

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
  twice. Merged queue item 4.4. ⚠⚠ **AND ITS CONFOUND IS NO LONGER
  HYPOTHETICAL (2026-08-23).** This design distinguishes "release" from "moving
  toward the camera" by arguing that a release scales the FINGERS while
  Z-translation scales fingers AND wrist together. Z-translation is now BUILT,
  and it does not use fingers at all — it reads the four RIGID PALM SPANS, and
  deliberately excludes every MCP→TIP length precisely because those change with
  GRIP. ⭐ That is good news for the discrimination (the two signals touch
  different landmarks), but the reasoning must be **re-verified against the real
  implementation** rather than carried over: check §14.2's planned recordings
  against `palm_depth`'s actual ratio, not against the imagined confound.
- Open-palm rotation gating — **not planned**: rotation stays permanently
  ungated now that open-palm/closed-fist detection is parked (rule 4).
- ✅ **Z-axis (camera-view-axis) translation — BUILT AND CONFIRMED LIVE IN BOTH
  TOOLS 2026-08-23. Moved OUT of this section; it is now rules 8, 9 and 10
  above.** The two questions this entry carried are both answered: the 3D snap
  check **refuses** when depth is frozen (rule 7), and no calibration step is
  needed (the ratio cancels the unknown hand size exactly). ⚠ The M2 gate this
  entry named turned out not to apply — M2 is dead, and the depth estimator
  never needed a calibrated skeleton, only the rigid palm quad. Full account:
  `GESTURE_PIPELINE_SPEC.md` §14.3 (design) and §14.3.5 (what was built).
  ⚠ **The yaw/palm-sinking limitation above is NOT closed by this** — 4.2 drives
  the object's depth, it does not correct the translation anchor's yaw swing.
  That is still T4.

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
