# MANIPULATION — §14: translation, depth, the yaw investigation, the lag

> **live · grab-relative translation, Z-axis, 4.2, and the rotation lag fix**
> **SOURCE** · `GESTURE_PIPELINE_SPEC.md` §14–§14.3.6 — extracted verbatim, not edited

⭐ The most-cited spec file. **§14.1** grab-relative translation · **§14.2** the
release trigger · **§14.3** Z-axis · **§14.3.4–§14.3.4.11** the yaw-lean
investigation · **§14.3.5** what 4.2 shipped · **§14.3.6** the lag.
⚠ When two sections conflict, **the later one wins**.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/GESTURE_PIPELINE_SPEC.md lines 3464-5331
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 14. Next build targets, proposed 2026-08-01 (not yet started)

Two build targets the user proposed immediately after confirming the 3D
cube rendering worked, to be picked up in a fresh conversation (see
`Claude/HANDOFF_SNAP_ROTATE_RELEASE.md`, refreshed the same session to
point here). **A third target, Z-axis translation, was added and its
design confirmed in a later conversation (§14.3)** — queued after the
first two, not started.

**⚠ BUILD ORDER SUPERSEDED (2026-08-02) — see `PART_ONE.md` §3.1.**
A perception-layer design spec (`Claude/PERCEPTION_LAYER_SPEC.md`) was
integrated into the pipeline, and all TODOs — this section's §14.1-§14.3,
§14.1.4's Object Jump Correction, §13.7's back-of-hand TODO, and the new
perception modules M0–M10 — were **merged into one ordered queue** at
`PART_ONE.md` §3.1, per direct request. That queue is now the single
authoritative build order. **Do not follow the sequence described below;
it is retained only as the record of what was decided before the merge.**

The material change: **the perception-layer work (Phases 0–2) now precedes
the remaining features.** §14.2 (hand-open release) and §14.3 (Z-axis
translation) are unchanged as designs but are gated behind their hard
prerequisites — M10 and M9/M2 respectively — because building either
first means building it twice. §14.1.4 (Object Jump Correction), which had
no agreed sequence, is now mapped to M4 + M5-DR-1 and is expected to close
in Phases 1–2.

**Historical (2026-08-01)**: §14.1 (pivot fix, DONE — implemented,
live-confirmed, ported to production) → §14.2 (hand-open release) → §14.3
(Z-axis translation), with §14.1.4 unsequenced.

### 14.1 Grab-relative rigid attachment for translation (REDESIGNED, 2026-08-01, later conversation) — supersedes the original anchor-selection framing below

**The original framing (preserved below for context) was wrong, per
direct user correction.** It asked "which single tracked landmark drifts
least during pure rotation," implicitly treating any translation during
rotation as an artifact to be minimized by picking a better point. That
missed the actual root cause.

**Root cause, confirmed by reading the current code**
(`HandsTriggeredActions.py`, `on_hands_frame`, ~line 426): unlike
rotation — which explicitly captures a grab-time baseline pair
(`grab_hand_orientation`/`grab_cube_orientation`) and computes a relative
DELTA each frame — translation has **no grab-time offset at all**:
`cube_window.set_target_position(owned_cube, _top_left_for_center(hand_pos, ...))`
forces the cube's center to exactly equal the mapped anchor position
**every** frame, unconditionally. The object is never allowed to sit
anywhere other than exactly on top of the tracked anchor point, so any
imprecision in that anchor shows up directly as spurious motion, and the
object's actual position at the moment of grab (which can be up to
`GRAB_RADIUS` away from the anchor) is discarded at that instant. No
choice of anchor landmark fixes this — the zero-offset forcing is the
actual defect, not the anchor's precision.

**Corrected model, per direct user request**: real prehension does not
work this way. When a hand grasps an object, the object occupies a
specific position within the volume the hand's fingers/palm close around
at the moment of grasp, and stays fixed relative to that grip as the hand
subsequently moves and rotates — the phalanges don't keep sliding around
the object mid-hold. The correct model captures the object's relationship
to the hand **once, at the moment of grab**, and follows it live
thereafter — the translation counterpart of what rotation already does
for orientation. (Which exact mechanism does that capturing — a single
frozen offset reapplied via a rotation transform, vs. a live-tracked
weighted combination of nearby landmarks — was a genuine open question,
resolved below in "Concrete redesign, chosen mechanism" after direct
follow-up discussion with the user.)

**Literature confirms this over the original anchor-selection framing,
not just the user's intuition**:
- **Grasp biomechanics (Napier, 1956 — the foundational prehension
  taxonomy, still the standard reference today)**: human grasps fall into
  two main patterns, **power grip** (object held against the palm,
  fingers flexed around it, thumb-assisted — larger objects/force) and
  **precision grip** (object pinched between the pads of thumb and
  fingers, palm largely uninvolved — smaller objects/control). Object size
  is a confirmed determinant of which pattern is used, and of exactly
  where on the hand the object sits — a real "grasp point" is not one
  fixed anatomical landmark, it depends on the object
  ([PMC: quantitative taxonomy of human hand grasps](https://pmc.ncbi.nlm.nih.gov/articles/PMC6377750/),
  [OT Mastery: grasp pattern taxonomy](https://www.otmastery.com/resources/types-of-grasp-patterns)).
  Postural studies further show grasp contact points/posture vary
  systematically and continuously with object size relative to hand size,
  not just discretely between the two categories
  ([Springer, J. Mech. Sci. Technol. 2014: postural variation of precision grips by object size](https://link.springer.com/article/10.1007/s12206-014-0309-x)).
- **VR/AR hand-interaction industry practice already implements exactly
  the corrected model, as the standard, not an edge case.** Unity's XR
  Interaction Toolkit: grabbing with **Dynamic Attach** "grab[s] the
  object wherever the hand touches it, which keeps relative position" —
  the relative offset is captured once at the grab instant and held fixed
  through the hold
  ([Unity XR Interaction Toolkit — XR Grab Interactable](https://docs.unity3d.com/Packages/com.unity.xr.interaction.toolkit@3.2/manual/xr-grab-interactable.html)).
  Meta's Horizon OS Hand Grab Interaction SDK defines a `GripPoint` — "an
  offset from the Wrist... used... as anchor for attaching the object"
  ([Meta Horizon OS — Hand Grab Interactions](https://developers.meta.com/horizon/documentation/unity/unity-isdk-hand-grab-interaction/)).
  Both are the same underlying principle — a hand-object relationship
  fixed once at grab, followed thereafter, not a per-frame absolute remap
  of a single tracked point — via a single frozen attach-point offset.
  This project's chosen mechanism (below) goes one step further, given
  finer-grained per-landmark data is already available and free: instead
  of one frozen offset from one point, it's a live-tracked, distance-
  weighted combination of several phalange-adjacent landmarks — directly
  motivated by the Napier finding above that a real grasp point isn't one
  fixed landmark, it depends on the object.

**Important caveat specific to this pipeline, not present in the VR
citations above**: those systems either use real physical controllers, or
(for hand-tracking headsets) treat the tracked hand as *assumed* to
mechanically conform around the object once a grab is recognized. This
pipeline's MediaPipe landmarks are **not** mechanically constrained by any
real object — nothing stops the tracked fingers from continuing to report
their true, unconstrained pose during a "hold." So "the volume enclosed by
the distal phalanges at the moment of grab" cannot be literally measured
from landmark contact here; it has to be **approximated as a fixed offset
captured at the grab instant**, exactly the way Unity's Dynamic Attach
does it ("grab the object wherever the hand touches it" — a geometric
snapshot, not a physical contact simulation). This is a faithful, standard
approximation, not a shortcut unique to this project.

**Concrete redesign, chosen mechanism (resolved 2026-08-01, follow-up
discussion)**: direct user question — "how do you define the offset at
grab? In relation to the phalanges?" — surfaced that the first draft above
(a single frozen offset from the existing wrist+4-MCP anchor, reapplied
via the 3D rotation quaternion each frame) left a real gap unresolved: it
never specified how a 2D pixel-space offset and a 3D `world_landmarks`
rotation delta are supposed to combine — translation has always been kept
deliberately in image-space (§1), while `rotation_delta` lives in the
noisier 3D `world_landmarks` space. Presented as an explicit fork (single
frozen offset + 3D delta / single frozen offset + simple 2D rotation /
distance-weighted live landmarks) — **user chose distance-weighted live
landmarks.**

1. **Candidate landmark set** (phalange-adjacent joints — starting point,
   extend only if verification shows it helps, don't over-scope up
   front): the 5 fingertips (`THUMB_TIP`, `INDEX_TIP`, `MIDDLE_TIP`,
   `RING_TIP`, `PINKY_TIP`) plus the existing 4 non-thumb MCPs already
   used by `_hand_position` (`INDEX_MCP`, `MIDDLE_MCP`, `RING_MCP`,
   `PINKY_MCP`) — 9 candidates. PIP/DIP joints are a natural extension to
   test later if the fingertip+MCP set proves too coarse, not assumed
   necessary up front.
2. **At grab**: for each candidate landmark *i*, compute
   `weight_i = 1 / (distance(object_position_at_grab, landmark_i_position_at_grab) + EPSILON)`,
   then normalize so `Σ weight_i = 1`. **Freeze this weight vector** —
   `grab_landmark_weights` — for the duration of the hold; it is never
   recomputed. This is the literal, computable version of "the phalanges
   are locked once the object is grabbed": the SET of landmarks and their
   relative influence is decided once, from real geometry at that grab
   instant (which landmarks were actually near the object), not
   hardcoded per cube identity.
3. **Exact no-pop continuity**: inverse-distance weighting is an
   approximation, not exact interpolation — it won't land precisely on
   `object_position_at_grab` in general. So also store a small constant
   `grab_residual_offset = object_position_at_grab − Σ(grab_landmark_weights_i
   × landmark_i_position_at_grab)`, added every frame. This guarantees the
   grab frame itself is bit-for-bit continuous (same no-pop discipline as
   rotation's own baseline capture, and the same "grab-time position = the
   object's own position" principle already decided for Z-axis translation,
   §14.3).
4. **Every subsequent frame**:
   `object_position(t) = Σ(grab_landmark_weights_i × landmark_i_position(t)) + grab_residual_offset`
   — same frozen weights, each candidate landmark's CURRENT live tracked
   2D pixel position. **No quaternion, no rotation-delta application, no
   2D/3D space-bridging at all** — translation stays purely 2D/pixel-based
   throughout, consistent with §1's original architecture decision.
   Rotation-coupling falls out naturally and correctly, because real
   fingertip/knuckle landmarks genuinely do swing more than the wrist
   during a wrist twist — no explicit "reapply a rotation" step needed.
5. **Napier's grip-size distinction falls out for free, superseding the
   earlier "pick a different hardcoded anchor per object size" idea**:
   grab the small cube near the fingertips and weights concentrate on TIP
   landmarks (precision-grip-like); grab the large cube more centrally and
   weights spread across MCPs (power-grip-like) — an emergent property of
   the actual grab geometry, not a branch on which cube name was grabbed.
   The size-dependent-single-anchor refinement from the first draft is now
   unnecessary and superseded, not a separate open item anymore.

**Known risk to verify, not assume**: individual fingertip/joint landmarks
are noisier than the existing wrist+4-MCP centroid — that noise-stability
was §13.3's original reason for choosing a multi-point centroid in the
first place. If weights concentrate sharply on one or two landmarks (a
small object grabbed right at the fingertips), the resulting position
signal could be jitterier than today's very stable translation.
Mitigations to test empirically if the data shows they're needed, not
picked blindly up front: a weight-concentration cap (e.g. a larger
`EPSILON` floor under the inverse-distance denominator, or clamping the
max single-landmark weight share), and/or light temporal smoothing on the
final combined position (same category of fix as rotation's own slerp,
applied to position instead).

**Revised verification methodology** (supersedes both the old "measure
which anchor drifts least" plan below AND the first draft's rotation-delta
plan above — this is the concrete mechanism to test): record a hand
grabbing, then rotating in place at a few real positions, for both cube
sizes. Offline, check: (1) the grab frame itself shows exactly zero pop
(sanity-checks the residual-offset math); (2) rotation-coupled translation
now looks proportional to the real swing of the weighted landmark set, not
the erratic behavior row 5 previously showed; (3) whether weights
concentrate too sharply for the small cube specifically, and whether that
shows up as extra jitter vs. the large cube — deciding whether a
concentration cap or smoothing is needed based on what's actually
measured. Build the base weighted-tracking mechanism first, verify against
recorded data, THEN tune concentration/smoothing parameters only if the
data shows they're needed — don't skip straight to implementation-by-feel
for either.

### 14.1.1 Verification results (2026-08-01, same conversation) — no-pop confirmed, jitter comparable, one deferred limitation found

**Tooling built**: `RecordTranslationPivotDebug.py`/`record_translation_pivot_debug.bat`
(imports `LiveSnapDebug.py`'s real, already-live-verified snap/translate
logic, so recorded grab events and cube centers are real ground truth, not
simulated — same lineage as `RecordRotationDebug.py`) and
`AnalyzeTranslationPivot.py` (offline: finds real grab events, freezes
distance-weighted candidate weights, replays the mechanism, checks
no-pop/jitter/rotation-coupling/yaw-foreshortening). Recordings saved to
`E:\Python\Recordings for vision_pipeline\Position_during_rotation`
(direct request — external-drive corpus convention, not the local
one-off-diagnostic pattern `RecordRotationDebug.py` used). Core math
(no-pop residual, pure-translation linearity) synthetically sanity-checked
before ever touching the camera — both exact — same discipline as
rotation's own offline checks.

**7 hold intervals analyzed across 3 valid live recordings** (both cube
sizes, both hands, a few of the first takes discarded because the
small-cube grip wasn't actually closed — quality-controlled by the
operator before analysis, not assumed valid):
- **No-pop: exactly 0.0000px in every interval.** The residual-offset
  construction is correct.
- **Jitter comparable to today's system** (new ≈4.4–4.8px mean per-frame
  movement vs. old ≈4.0–4.7px) — not a regression.
- **Translation now measurably scales with real rotation, not flat/erratic**:
  low-rotation-amount frames average 2.97px jitter, high-rotation-amount
  frames 5.95px (≈2.0x) — consistent across all 7 intervals individually.
  (Today's system shows a similar ≈2.1x ratio too — expected, since both
  draw from overlapping parts of the same tracked hand; this check mainly
  confirms the new mechanism doesn't move erratically independent of
  actual rotation, not that it's dramatically different from today's.)
- **Important caveat on the above**: this recording methodology
  structurally cannot exercise the actual "non-zero grab offset" case the
  whole redesign exists for, because `object_position_at_grab` (the ground
  truth) is itself defined as today's buggy zero-offset cube center. A
  fair old-vs-new comparison needs the mechanism actually wired into
  `LiveSnapDebug.py` and watched live, once a real non-zero offset can
  exist.

**Deferred limitation found (direct live report, verified against the
same 3 recordings — no new recording needed): the computed point swings
toward the palm specifically under YAW** (hand turning left/right,
knuckle row going edge-on to the camera), NOT under pitch/roll (reported
fine). Quantified: knuckle-row width (`INDEX_MCP`↔`PINKY_MCP` pixel
distance) shrank to as little as 38% of its grab-time value in these
recordings; correlation between that foreshortening and a palm-vs-fingertip
bias metric was negative in 6/7 intervals (mean −0.25); bias averaged
+0.48 (leaning palm) at the most-sideways frames vs. +0.29 at the most-frontal
frames (0 = balanced, +1 = fully at palm, on a signed scale). A persistent
baseline lean toward the palm exists even facing the camera (+0.29, not
0) — because the MCP candidates are inherently closer to the
centroid-based ground truth than the fingertip candidates are.

**Why this happens, and why it's structural, not a bug to quick-fix**: yaw
is specifically the rotation that moves fingers toward/away from the
camera (a real depth/Z change), not just sideways in the image. A purely
2D pixel-distance weighting (chosen deliberately, §14's "Concrete redesign"
above, to avoid the noisy 3D `world_landmarks` and to stay consistent with
§1's image-space-translation decision) cannot distinguish "this fingertip
foreshortened toward the palm's 2D silhouette because of yaw" from "this
fingertip actually moved toward the palm" — both look identical to a 2D
distance metric. This is the same class of problem as §14.3's Z-axis
translation design (both need a notion of depth the current signal set
doesn't reliably provide monocularly).

**Decision (direct request): defer the yaw fix, implement the mechanism
as-is.** Roll/pitch behavior is fine; only yaw is affected; the mechanism
is still a strict improvement over today's zero-offset forcing (verified
above) even with this known gap. **New TODO, proposed direction**: "we
will probably need to build a calibration on the Z axis at the beginning
of the game" — a startup calibration step (e.g. establishing a baseline
hand-to-camera depth reference before play begins) is the leading
candidate to eventually resolve both this yaw/palm-sinking issue and
§14.3's Z-axis-at-grab problem together, since they likely share root
cause. Not designed yet — revisit once Z-axis translation (§14.3) is
actually being built, per the confirmed build order.

### 14.1.2 Implementation, live confirmation, and production port (2026-08-01, same conversation)

**Implemented in `LiveSnapDebug.py`**: `Cube` gained `grab_landmark_weights`/
`grab_residual_offset` (mirrors the rotation baseline pair);
`_compute_grab_weights`/`_weighted_position` added; `update_hands` now
captures weights from the cube's own pre-existing position at grab (not
the hand anchor) and tracks live thereafter.

**Verified by replaying a real recording's landmarks through the actual
modified `update_hands` function** (not just the standalone analysis
script, closing the loop on the real code path): at the grab frame, the
cube stayed at its resting position (320.0, 240.0) — zero pop — while the
OLD recorded data at that same frame had already popped to (395.9, 255.3),
a ~76px discontinuous jump the new mechanism eliminates. Confirmed against
real camera data, not just synthetic math.

**Confirmed working live**: user tested the redesigned mechanism against
a real camera via `debug_snap.bat`: "it's working" — same confirmation
pattern as rotation's own live test (§13.7).

**Ported to production** (`HandsTriggeredActions.py`/`CubeWindow.py`,
same day): identical `Cube` fields, verbatim `_compute_grab_weights`/
`_weighted_position` formulas, `on_hands_frame`'s translation logic
mirrored. **Verification method necessarily differs**:
`HandsTriggeredActions.py` opens a real pygame window as an import side
effect (module-level `cube_window = CubeWindow()`), so it can't be safely
replayed through a script the way `LiveSnapDebug.py` was — verified
instead via careful line-by-line parity review against the already
live-verified debug-tool version. One intentional, justified divergence:
translation's grab-weight capture is unconditional (not gated on
`hand_quat_now is not None` the way rotation's baseline is), since
translation only needs 2D `landmarks` (always available every frame), not
the slower-arriving `world_landmarks` — no "missed the grab-frame capture"
fallback needed for it, unlike rotation's.

**Status**: implemented, replay-verified, live-camera-confirmed, and
ported to production with a parity review. **Not yet independently
live-tested in production itself** — recommend a quick live check
(running the actual client/server pipeline, not just `debug_snap.bat`)
before considering this fully closed out, same as rotation's own
production port was ultimately confirmed live.

### 14.1.3 Live production test — mostly confirmed working, one spurious NOT-YET-ROOT-CAUSED glitch found (2026-08-01)

User ran the actual production client/server pipeline (`launch.bat`) and
confirmed the translation-pivot fix generally works. **One glitch
reported**: "in one case, the cube jumped from one hand to another and
came back to the hand" — not reproducible on demand ("it was spurious so
I do not know how to replicate this bug"), and the user couldn't recall
whether the hands were close together/crossing at the time.

**Leading hypothesis, NOT verified (no repro data available)**: the
distance-weighted mechanism has no outlier rejection across its 9
candidate landmarks, unlike rotation's reliability-weighted predictive
filter (§13.7). A single fingertip landmark briefly misread (e.g. from
occlusion when hands pass close to each other, or a fast-motion tracking
glitch) could pull the weighted average toward that bad reading for a
frame or two before self-correcting once tracking recovers — this would
look exactly like a brief jump toward wherever the glitchy landmark
reported, then a snap back. This is exactly the risk already flagged as
deferred-but-unverified when the mechanism was designed ("individual
landmarks are noisier than the existing centroid... mitigations only if
data shows they're needed," §14.1) — a live, spurious report is real
evidence the risk can materialize, even without a controlled reproduction.

**Decision (direct request): document only, no code change.** Per this
project's standing discipline, don't fix without verifying against real
data — and there's no repro to verify against. A conservative mitigation
(max-per-frame-jump clamp, or borrowing rotation's reliability-weighted
approach) was considered and explicitly deferred, not rejected on merit.
**Revisit if**: this recurs, becomes reproducible, or a recorded session
happens to catch it (check candidate-landmark positions frame-by-frame
around any future occurrence for a stray outlier before assuming any
other cause).

**UPDATE (2026-08-01, later same-day conversation): this recurred, was
made reproducible, and root-caused — see §14.1.4, "Object Jump
Correction."** The "no outlier rejection" hypothesis above was directionally
right but incomplete; the actual mechanism is more specific (a whole-hand
identity mix-up, not per-landmark noise) and needs a different fix
approach than a simple outlier-exclusion filter. Read §14.1.4 before
picking this back up — don't restart from the hypothesis above.

---

**Original framing (2026-08-01, superseded above — kept for context, not
current design)**:

**Problem, as reported**: "at the moment, the cube is located somewhere
inside the palm/wrist and therefore it translates when the hand rotates:
I would like the cube not to translate if the hand rotates cleanly." The
current translation target (`_hand_position`, §13.3) is the centroid of
`wrist(0)` + the four non-thumb MCPs (`index_MCP(5)`, `middle_MCP(9)`,
`ring_MCP(13)`, `pinky_MCP(17)`) — chosen originally for stability
(§13.3's own rationale: "more stable than the wrist alone... or any single
MCP"), but stability against LANDMARK NOISE is a different property from
being AT THE TRUE ROTATIONAL PIVOT. When a hand rotates in place (the
user's intent: "just twisting my wrist, not moving my hand"), any tracked
point that isn't exactly at the anatomical rotation center (roughly the
wrist joint / forearm axis) will trace a real, non-zero arc in image space
as a geometric consequence of the rotation itself — this is not
noise/jitter, it would happen even with perfect, noise-free tracking,
because the palm-center centroid is pulled toward the knuckles, offset
from the true pivot.

**Candidate approaches that were proposed** (superseded — kept for
context; candidate 3's "offset along the hand's local axis" idea is the
one thing that foreshadowed the corrected model above, but was framed as
an anchor-position adjustment rather than a grab-relative offset):

1. **User's own suggestion**: "center of gravity in the middle of all
   volume created by the fingers and palm" — i.e. a centroid over a wider
   set of landmarks (potentially all 21, or all MCP+PIP+DIP joints, not
   just wrist+4 MCPs) intended to approximate the geometric center of the
   hand's own enclosed volume when loosely closed around a grabbed object
   — the physical point a real held object's center would occupy.
2. **Wrist-anchored**: use the `wrist(0)` landmark alone (or a point very
   close to it) as the translation target instead of a centroid — the
   wrist joint is anatomically closer to the true rotational pivot for a
   "twist your wrist in place" motion than the palm-center centroid is,
   so it should exhibit LESS translation-from-rotation coupling, at the
   cost of losing the original single-landmark noise-stability §13.3
   flagged (may need to reconsider that tradeoff, or address noise a
   different way, e.g. temporal smoothing on the position signal itself).
3. **Weighted/adjusted centroid**: something between 1 and 2 — e.g. the
   existing wrist+4-MCP centroid, but re-weighted toward the wrist, or
   offset along the hand's own local "into the palm" axis (derivable from
   the same orthonormal frame §13.7 already computes for rotation) toward
   the anatomically-correct pivot rather than the raw landmark centroid.

### 14.1.4 "Object Jump Correction" — root cause found via recorded data, FIX NOT YET DESIGNED (TODO for a future improvements round)

**Name this item "Object Jump Correction" in any future conversation** —
direct request, so it can be referred to by name without re-explaining.
This is the same bug §14.1.3 first reported as "spurious, not
reproducible" — it recurred, was made reproducible, and is now
root-caused with real data. **Read this section fully before attempting
a fix** — the original "no outlier rejection" hypothesis (§14.1.3) was
directionally right but incomplete, and a first fix attempt built on it
(below) was tried, verified against real data, and found NOT to work.

**Investigation process (recorded-data-first discipline, followed
throughout)**:
1. First hypothesis (frame-edge extrapolation): when a hand goes
   partially off the camera frame, MediaPipe still returns 21 landmarks,
   but the off-screen ones become extrapolated/unreliable. Built
   `RecordTranslationPivotDebug.py` recordings (`edge_test1/2/3`,
   `E:\Python\Recordings for vision_pipeline\Position_during_rotation`)
   deliberately moving a hand near/off frame edges while holding a cube.
   **Confirmed real**: out-of-bounds candidate landmarks (pixel x/y
   outside `[0,width]×[0,height]`) correlate with elevated jitter (5.45px
   mean vs 5.24px clean, and visibly compounding drift over sustained
   multi-frame out-of-bounds stretches, e.g. `edge_test1` frames 70-136).
2. **Proposed fix #1, built and verified, REJECTED because it didn't
   help**: exclude out-of-bounds candidates from the weighted average
   each frame, renormalizing the remaining weights (freeze if fewer than
   3 valid candidates remain). Tested against all 3 `edge_test`
   recordings, comparing old vs. fixed mean/max jitter, split by
   clean-frame vs. out-of-bounds-frame. **Result: virtually no
   difference** (clean: 5.24px vs 5.23px; out-of-bounds: 5.45px vs
   5.49px). Investigating the single biggest recorded jump (60px) showed
   ALL 21 landmarks were in-bounds with a 0.98 confidence score at that
   frame — not explained by the out-of-bounds hypothesis at all.
3. **Direct instruction**: don't analyze non-representative data — record
   sessions one at a time, ask the operator after EACH one whether they
   actually observed the reported jump, discard takes that didn't
   reproduce it, keep recording until one does. Three takes
   (`jump_test1/2/3`) did not reproduce it and were deleted. The fourth
   (`jump_test4`, kept) did.

**Root cause, confirmed from `jump_test4`'s actual data (Right hand,
holding the small cube, frames ~100-112)** — NOT frame-edge extrapolation,
NOT per-landmark noise:

| Frame | Wrist x | All 9 candidate landmarks | Detection score |
|---|---|---|---|
| 100-103 | ~120-127 | clustered left side (~x=60-180) | 0.97-0.99 |
| **104** | **608.5** | **ALL 9 jumped together** to the right side (~x=540-650) | 0.985 |
| 105-106 | ~600-603 | stayed consistently at the NEW (wrong) location | 0.99+ |
| 107 | 586.1 | still right side | **0.665** (notably low — a transition frame) |
| 108 | 95.3 | jumped BACK, matching frame 103's location | 0.997 |

Critically: at frame 108, the "Left" hand (undetected for the entire
100-107 window) was briefly detected for exactly one frame, with its
wrist at x=575 — almost exactly where "Right" had just been. **This is
the signature of a hand-identity/handedness-slot mix-up in MediaPipe's
own multi-hand tracking**, not a data-quality problem this pipeline's
code caused: for several frames, whatever MediaPipe internally tracks as
"the Right hand" pointed at a completely different (and differently
located) hand-like detection, with normal-to-high confidence throughout
(no low-confidence signal to gate on, except the one transition frame),
before self-correcting. All 9 weighted-average candidates moved together
coherently — this is why bounds-checking individual landmarks (fix #1)
could never catch it: the teleported landmarks were mostly still WITHIN
the visible frame the whole time, just reporting the wrong hand's
position entirely.

**Why this needs careful filter design, not a quick patch — direct
parallel to this project's own rotation-filter history**: a naive
"reject an implausibly large frame-to-frame jump, compare against the
previous accepted position" filter would face the EXACT two traps
rotation's filter needed two iterations to escape (§13.7's "Attempt 3"
history):
1. If frames 105-106 are compared against the frozen/rejected reference
   from frame 104's correction rather than each other, the gap can look
   even bigger than it is, incorrectly extending the rejection
   (rotation's "self-reinforcing trap" bug).
2. Even comparing raw-to-previous-raw has a subtler problem HERE
   specifically: frames 104-106 are internally CONSISTENT with each
   other (a sustained wrong state, not a single spike) — a filter that
   only checks "does this frame agree with the last raw frame" would
   correctly flag frame 104 (big jump from 103) but then get fooled by
   105 and 106 (small jumps from 104), accepting the wrong state as the
   new normal. Distinguishing "a brief bad spike" from "a real new
   sustained state" is inherently the hard part — rotation's own
   two-bug history is direct evidence this is easy to get subtly wrong
   even with a clear design in mind, not a reason to skip the care, a
   reason to budget for it.

**NOT fixed — explicitly deferred to a future round of improvements**
(direct request). Do not restart the investigation from scratch — the
root cause above is confirmed, not hypothesized. What's still needed:
1. Decide the filter's accept/reject/recovery logic (how many consecutive
   consistent-but-different frames before accepting a new state as real,
   mirroring how tracking-loss-then-reacquire already has its own timeout
   semantics elsewhere in this codebase).
2. Verify the chosen design against `jump_test4` specifically (does it
   suppress the 104-107 excursion) AND against this same recording's
   legitimate fast-motion frames (e.g. frames 57-61, ~40-48px/frame,
   smooth multi-frame progression, NOT a glitch — a filter must not
   suppress genuine fast motion) before considering it done.
3. Decide where the fix lives: likely needs to operate on the OVERALL
   computed translation output (or reuse `_hand_position`, already used
   for grab-radius), not per-candidate-landmark, since the failure mode
   is a coherent whole-hand shift, not individual-landmark corruption.
4. Consider whether MediaPipe's own multi-hand tracking configuration
   (e.g. `num_hands`, tracking confidence thresholds) offers any
   upstream mitigation before building a downstream filter — not yet
   investigated.

**Reusable recorded data for whoever picks this up**: `jump_test4`
(`E:\Python\Recordings for vision_pipeline\Position_during_rotation\translation_pivot_jump_test4_20260802_174438.json`)
has the confirmed real jump (frames ~100-112, Right hand, small cube).
The three `edge_test*` recordings remain useful for the separate,
smaller-magnitude, lower-priority off-frame-extrapolation finding (item 1
above) if that's ever worth revisiting on its own. The record-one-at-a-time
-with-operator-confirmation workflow (`record_translation_pivot_debug.bat`,
delete non-reproducing takes) is itself a reusable pattern for any future
hard-to-reproduce live bug report — don't skip straight to analyzing
whatever was captured first.

### 14.2 Unsnap by quickly fully opening the hand — new candidate release trigger

**Design, as described**: while a hand holds a snapped object, rapidly and
fully opening that hand (fingers extending outward quickly) unsnaps it —
**provided the wrist/hand base does NOT translate much at the same time**.
That qualifier is the whole design: it's there specifically to distinguish
this gesture from a DIFFERENT, NOT YET BUILT future gesture — moving the
hand closer to or farther from the camera to control translation along the
camera's view axis (depth/Z). In that future depth-translation gesture,
the WHOLE hand (fingers AND wrist together) would grow or shrink in the
image as the hand physically approaches or recedes from the camera. In
THIS release gesture, only the fingers extend/spread rapidly while the
wrist's own image position and apparent size stay roughly stable. The
discriminating signal is therefore expected to be something like:
*rate of finger extension (curl-angle or fingertip-to-wrist distance,
changing quickly) while wrist-relative hand scale/position stays
roughly constant* — as opposed to depth-translation's *fingers AND wrist
scale together*.

**Confirmed as the sole active release-trigger plan (2026-08-01, later
conversation)**: the earlier closed-fist release plan (§13.4/§13.5 —
blocked since inception on finding a working fist-detection approach,
MediaPipe's built-in classifier tried and reverted) depended on row 2
(`Open_Palm`/`Closed_Fist` detection), which is now **PARKED**, not being
pursued for the moment. This gesture is therefore no longer weighed as an
alternative to closed-fist release — it's the one release-trigger plan
going forward, second in the confirmed build order (§14.1 → §14.2 →
§14.3). Unlike a static closed-fist POSE classifier, this is
fundamentally a **transient, rate-of-change** gesture (a quick motion, not
a held pose) — closer in spirit to how this project's pinch-release work
(archived, §12) approached onset/offset detection than to a per-frame pose
classifier, and plausibly easier: opening HANDS quickly is a large,
coarse, fast motion (matching this project's own literature-grounded
intuition, §13.5, that fist/open-palm-scale gestures should be
structurally easier than pinch's fine-grained one), and the specific
signal proposed (rate of finger extension vs. wrist stability) is a
purely geometric, landmark-derived quantity — no pretrained classifier
dependency at all, sidestepping the exact class of problem that blocked
closed-fist. **Resolved (2026-08-01, later conversation): this supersedes
the closed-fist plan**, not coexists with it — row 2 is parked, so
closed-fist release has no working detection path to run on regardless.

**Proposed empirical approach, directly requested**: "we can take 6
recordings in each hand position to record the gesture and see which
finger and wrist data we can exploit to discriminate this gesture." Concrete
plan for whoever picks this up:
- Record short sessions (mirroring `RecordRotationDebug.py`'s pattern —
  reuse or closely copy that tool's recording harness) of: (a) the target
  gesture itself (grab an object, then quickly fully open the hand to
  release it) and (b) the confound to rule out (moving the whole hand
  toward/away from the camera without a release intent) — 6 recordings
  each, across a few different real hand positions/distances from the
  camera (per direct request), so whatever signal is found generalizes
  across position, not just one convenient spot.
- Log full landmark data (pixel AND world landmarks, all 21 points, both
  hands) each frame, same schema `RecordRotationDebug.py` already uses.
- Offline, compute candidate discriminating signals per frame across both
  recording sets and compare: rate of change of a "hand openness" metric
  (e.g. mean fingertip-to-wrist distance, or per-finger curl angle from
  `features.py`'s existing finger-curl functions — already built for the
  archived pinch work, potentially directly reusable) vs. rate of change
  of overall hand scale (e.g. wrist-to-middle-MCP span, the same
  depth-proxy metric `PART_ONE.md` §2 already designed for the dropped
  depth-proxy row) — the target gesture should show HIGH finger-openness
  rate-of-change with LOW wrist-scale rate-of-change; the confound gesture
  should show both changing together. Verify this separation holds across
  all 12 recordings before designing a threshold/classifier, not after.

### 14.3 Z-axis (camera-view-axis) translation — new gesture, design confirmed 2026-08-01, NOT YET BUILT

**Not previously specified as its own gesture.** Before this conversation
the only two references to camera-axis depth in this project were: (1)
`PART_ONE.md` §2's "depth proxy" (apparent hand span vs. a grab-time
baseline), which was scoped to drive **scale + color only**, explicitly
**not** Z-axis translation ("no Z-axis translation for now, explicitly
deferred") — and that whole row was later **dropped** entirely during the
snap/rotate/release pivot (§13.3); (2) §14.2 above, which mentions
Z-translation only as a **hypothetical confound** to justify the
hand-open release gesture's wrist-stability qualifier, not as a real
design. This section is the first actual design for it.

**Related finding, added 2026-08-01 (later conversation, during §14.1's
verification pass)**: live-testing the §14.1 translation-pivot fix
surfaced a yaw-specific bug (the computed grasp point swings toward the
palm when the hand turns edge-on to the camera, confirmed empirically —
§14.1.1) that's likely the SAME underlying depth-ambiguity problem this
section exists to solve, not a coincidence. **Proposed direction (direct
request, not yet designed): a startup calibration step** — establishing a
baseline hand-to-camera depth reference before play begins — is the
leading candidate to resolve both this row's own grab-time Z positioning
AND §14.1's yaw/palm-sinking issue together. Revisit when this row is
actually picked up, per the confirmed build order (§14.1 → §14.2 → §14.3).

**Design, confirmed with the user before starting** (four decisions, in
the order asked):

1. **Signal: apparent hand-span ratio**, not raw `world_landmarks` `z`.
   Same metric the dropped depth-proxy row used —
   `wrist↔middle-MCP` image-space distance vs. a baseline captured at grab
   time, `ratio = current_span / baseline_span`. Consistent with this
   project's established, literature-backed finding that MediaPipe's raw
   monocular `z` is the least reliable of the three coordinates (§13.2);
   raw `z` was explicitly rejected as the signal.
2. **Mapping: absolute and continuous, not relative-delta.** Symmetric
   with how X/Y translation already works (row 5: cube position =
   mapped(hand position) every frame) — **not** like rotation's
   grab-time-baseline-delta design (§13.7). The cube's Z position is a
   direct function of the current hand-span ratio each frame; there is no
   "keep the cube's own Z at grab, only move by however much the ratio
   changes afterward" baselining.
3. **Snap gating becomes 3D.** A hand can only snap a cube if it is close
   enough on **all three axes** — X, Y, **and** Z (hand-span-ratio-derived
   depth) — not just image-space X/Y proximity as today. Direct quote:
   "the snap can occur only if the hand position on the camera view axis
   is close enough to the position of the cube on the same axis (same
   logic as X/Y translation: the cube follows exactly the translation of
   the hand, but the hand cannot snap the cube if it is not close enough
   to the cube)." This means the grab-radius/arbitration logic (§13.3, row
   3, currently a 2D image-space proximity check in `_try_snap`) needs to
   become a 3D proximity check once this ships — a real change to existing
   snap logic, not just an additive new axis bolted on afterward.
4. **Scope: Z-translation only.** The old dropped depth-proxy scale/color
   effect (row 6) stays dropped — not revived alongside this. Once
   snapped, only position (now X/Y/Z) is affected, same as today's
   rendering (real size stays fixed per-object, per §13.8).

**Confirmed build order**: this is the **third** of three now-queued
targets — after §14.1 (translation-pivot fix) and §14.2 (hand-open
release trigger). Not started next; do §14.1 first.

### 14.3.1 The scale anchor must be MULTI-ANCHOR, not palm width alone (2026-08-04)

**Owner observation that prompted this**: palm width works as a depth anchor
*"except when the hand rotates around the yaw axis and shows the hand edge to the
camera"*, and other markers may be needed depending on what the hand presents.
**Correct, and measured** (`analysis/m9_depth_anchors.py`).

A depth anchor must be CONSTANT while the hand rotates in place and move only
when distance genuinely changes. Measured CV over the corpus:

| take type | palm **width** (5↔17) | palm **length** (0↔9) | **max(w, l)** |
|---|---|---|---|
| rotation in place (mean) | 0.094 | **0.301** | **0.088** |
| `depth_sweep` (want HIGH) | 0.456 | 0.422 | 0.449 |
| steady hand, face-on | 0.003–0.008 | 0.004–0.012 | 0.003–0.008 |

**Three conclusions, all load-bearing for 4.1/4.2:**

1. **Use the MAXIMUM of the rigid palm-quad spans, normalised to their own
   grab-time baselines — never palm width alone.** It is never worse than width
   in any take, and it stays fully responsive on `depth_sweep` (0.449 vs 0.456).
   Foreshortening only ever *shrinks* an apparent span, so the largest normalised
   span is the one least corrupted, and taking the max automatically selects
   whichever anchor the current hand pose has left intact — which is exactly the
   owner's "depending on what the hand is showing to the camera".

2. **⚠ Use the RIGID palm quad, NOT finger lengths.** The owner's instinct was
   "finger length ratios", and the direction is right but the landmarks must not
   be: any MCP→TIP span changes with GRIP, so it would conflate "the hand closed"
   with "the hand moved away" — catastrophic for a grab gesture, where the hand
   closes at exactly the moment depth must stay stable. The rigid spans are the
   four palm-quad measures: `5↔17` (width), `0↔9` (length), `0↔5` and `0↔17`
   (diagonals). Adding the two diagonals gains a further 0.088 → 0.085.

3. **⚠ THE YAW CASE IS STILL UNTESTED — the corpus contains no yaw take.** Every
   rotation recording is PITCH by deliberate design (`palm_back_*` and
   `pitch_sweep_*`; yaw is a separate open item, T4). That is why *length* scores
   so badly above: pitch foreshortens the wrist→middle-MCP axis while leaving the
   MCP row intact. Under yaw the geometry inverts — width collapses, length
   survives — which is precisely the owner's scenario and precisely what max(w, l)
   is designed to absorb, **but it is inferred from geometry, not measured.**
   **A `yaw_sweep_constant_depth` take is a prerequisite for building 4.2.**

4. **Even the best anchor carries ~9% false depth during rotation.** So the
   multi-anchor rule is necessary but not sufficient: S10's freeze (reuse
   `PalmFacingTracker`'s pattern on `edge_on_measure`) is still required as the
   backstop for when *all* anchors are foreshortened at once — a combined
   yaw+pitch pose — and Z output will likely need rate-limiting on top. Do not
   expect a clean metric depth signal from this sensor; expect a usable
   *relative* one, which is all §14.3's ratio design ever claimed.

### 14.3.2 ⚠ THE YAW AXIS IS NOW MEASURED (2026-08-04) — §14.3.1's reasoning was half wrong

§14.3.1 predicted from geometry that palm **width** collapses under yaw while
palm **length** survives, mirroring pitch. That half was an **inference**, flagged
as such, because the corpus contained no yaw take. It now does
(`yaw_sweep_constant_depth`, 741 frames, 9 cycles, hand passing fully through to
back-of-hand). Measured (`analysis/m9_depth_anchors.py`, CV — lower is better):

| rotation | width | length | max(w,l) | max4 |
|---|---|---|---|---|
| **PITCH** (5 takes) | 0.094 | **0.301** | 0.088 | 0.085 |
| **YAW** (1 take) | 0.128 | **0.125** | **0.080** | **0.056** |

- **Pitch: prediction CONFIRMED.** Length collapses, width survives — a 3.2×
  asymmetry, exactly as the foreshortening argument says.
- **⚠ Yaw: prediction REFUTED.** Width and length degrade **equally** (0.128 vs
  0.125). There is no asymmetry, and no anchor is immune.

**Why, and the answer was already in the corpus**: §0.18 established that at
edge-on **all four palm-frame landmarks collapse together**. Once the palm is
edge-on it does not matter which axis got it there. The orthogonal-foreshortening
argument holds only for pitch, where the hand reaches foreshortening *without*
the palm going edge-on.

**Consequences — the recommendation survives, the rationale changes:**

1. **Multi-anchor is MORE valuable under yaw, not less.** `max(w,l)` beats width
   alone by **37%** there (0.080 vs 0.128) and `max4` by **56%** (0.056), against
   only 6% under pitch. So §14.3.1's rule stands and is strengthened.
2. **⚠ But the mechanism is different, and it matters.** The gain is not "one
   axis is immune" — it is "take whichever anchor is least corrupted *this
   frame*". Since under yaw **both** degrade, **S10's freeze is REQUIRED, not
   optional**: there is no surviving anchor to fall back on inside the band.
   §14.3.1's point 4 already said the freeze is needed as a backstop; this
   promotes it from backstop to prerequisite.
3. n = 1 yaw take. The direction is clear (equal degradation, not asymmetry) but
   the magnitudes should not be quoted as settled.

**Not yet resolved — defer to whoever actually picks this up, don't guess
in advance**:
- The exact mapping function from hand-span ratio to a Z position/depth
  unit (linear? bounded range? what ratio counts as "no Z movement," i.e.
  the resting width around 1.0?).
- How the new Z-proximity check relates to the existing 2D grab-radius
  value — the same radius extended into 3D (e.g. a spherical/ellipsoidal
  check), or a separately-tuned Z tolerance? Needs live tuning either way,
  same discipline as `GRAB_RADIUS`/`ROTATION_SLERP_FACTOR` etc.
  (`HANDOFF_SNAP_ROTATE_RELEASE.md` §4).
- **Interaction with §14.2's still-unbuilt release trigger**: §14.2's
  discrimination design already reasoned about this gesture as a
  *hypothetical* confound (fingers+wrist scaling together vs. release's
  fingers-only). Once this is actually built (not hypothetical), §14.2's
  planned recordings should be re-verified against the REAL Z-translation
  implementation's actual hand-span-ratio signal, not just the imagined
  confound — don't assume the earlier reasoning still holds unchecked.
- Whether the hand-span metric needs recalibration/baseline capture to be
  robust across different real hand sizes/users (same open question the
  dropped depth-proxy row never resolved, `PART_ONE.md` §5).

Per this project's standing discipline (`HANDOFF_SNAP_ROTATE_RELEASE.md`
§4): verify the chosen hand-span-ratio-to-Z mapping against recorded or
live data before committing to specific constants, same as every other
build step in this document.

---

### 14.3.3 ⚠⚠ THE YAW TAKE §14.3.2 RESTS ON IS AXIS-CONTAMINATED (2026-08-22)

**Read this before using §14.3.2's mechanism claim for 4.1.** Measured with
`analysis/t5c_operator_or_estimator.py`, using **2D pixel landmarks only** — it
never touches world z, so it does not share an expression with what it is
auditing (the B4 rule).

A rigid plate foreshortens the dimension PERPENDICULAR to its rotation axis and
leaves the parallel one alone, so which span collapses says which axis the hand
actually turned about. Collapse ratio = p5(span)/p95(span):

| take | palm WIDTH | palm LENGTH | what the operator actually did |
|---|---|---|---|
| `yaw_sweep_constant_depth` | **0.629** | **0.670** | ⚠ **BOTH collapse — a MIXED axis, not a clean yaw** |
| `pitch_sweep_slow` (2026-08-04) | 0.891 | **0.278** | clean pitch ✅ |
| `palm_back_s2_slow` RIGHT | 0.646 | **0.294** | clean pitch ✅ |
| `palm_back_s2_slow` LEFT | 0.710 | **0.468** | clean pitch ✅ |

**What this does and does not overturn:**

1. ⚠ **§14.3.2's MECHANISM claim is not established by this take.** It reads
   "width and length degrade equally under yaw" as proof that *edge-on collapses
   all four palm landmarks at once*. But the operator rotated about a mixed axis,
   which produces equal degradation on its own. The two explanations are
   confounded in this recording and it cannot separate them.
2. ✅ **§14.3.2's RECOMMENDATION stands unchanged**: `max4` won under either
   reading, and S10's freeze is the conservative call either way. **Build 4.1 as
   §14.3.2 prescribes** — this note changes the confidence in *why*, not *what*.
3. ⚠ **§14.3.2 already warned "n = 1 yaw take ... magnitudes should not be quoted
   as settled."** That warning was right and is now stronger: it is n=1 *and*
   contaminated. **Do not quote 0.128/0.125 as yaw anchor CVs.**

⭐ **A CLEAN `yaw_sweep_constant_depth` RETAKE IS THE CHEAPEST FIX** and it settles
two questions at once — this one, and whether the owner-reported cube-rotation
tilt (below) is the estimator's or the hand's.

### 14.3.4 Owner-reported: a yaw hand-rotation turns the cube about a tilted axis (2026-08-22)

**Owner, 2026-08-22**: *"when I rotate my hand on the yaw axis, the cube seems to
rotate on an axis which is not the world z axis"*, with pitch and roll believed
correct but unconfirmed.

**The cube's axis IS the estimator's axis, exactly.** `HandsTriggeredActions.py`
(~L711) computes `delta = hand_quat_now * conj(grab_hand_orientation)` and
left-multiplies it onto the cube. There is **no frame conversion**, and none is
needed: the renderer's frame (`CubeWindow._draw_object_3d` — x right, y down via
pygame, +z away from the viewer) **matches** the landmark frame on all three axes.
So any axis error in the fit transfers to the cube 1:1.

Measured (`analysis/t5_rotation_axis_fidelity.py`, at large rotation where the
axis is well determined):

| hand rotation | expected axis | measured deviation |
|---|---|---|
| **YAW** | vertical | **25.6°** (33.1° pooled) |
| **PITCH** | horizontal | **5.0°** |
| **ROLL** | depth | ⚠ **NEVER MEASURED — no take exists** |

**Two candidate causes were tested and BOTH FAILED:**

1. ❌ **The `invert_x` mirror is NOT the cause.** Analytically a reflection can only
   REVERSE an axis, never tilt one: `M R M⁻¹ = R(−Mn, θ)`. Empirically, negating x
   flips the axis signs and leaves the deviation **bit-identical at 33.1°**.
   ⚠ This also means `remap_world_keypoints`'s "confirm the rotation's sign/axis
   feel live, don't assume this is correct as-is" caveat is **still open** — the
   mirror is exonerated for the TILT, not for the SIGN.
2. ❌ **Constellation degeneracy is NOT the cause** in this take.
   `palm_observability` never leaves **0.85–0.89** across the whole yaw sweep — it
   never approaches the DR-2 band, so the palm never went rank-deficient.
   (It *does* bite the `palm_back` takes at full extension: observability 0.588
   with the axis 84.8° off.)

⛔ **THE CAUSE IS THEREFORE NOT YET IDENTIFIED, AND §14.3.3 IS WHY IT CANNOT BE
FROM EXISTING DATA**: the only yaw take is axis-contaminated, so an unknown part
of that 25.6° is the operator's own pitch rather than estimator error. **A clean
yaw take is required before attributing it.**

⭐ **ONE ACTIONABLE RESULT ALREADY**: the 9-point **palm+tips** constellation beats
production's 5-point palm-only on axis fidelity in **every take measured** —
pitch 8.1°→3.9°, palm_back RIGHT 22.4°→6.4°, LEFT 36.9°→19.0°, yaw 28.3°→24.9°.
⚠ **Do not just switch it on**: production ships palm-only deliberately
(`HandsTriggeredActions.py` L482) because tips scored orientation p95 9.85→27.79
**worse** in free play. Those measure different things — that was JITTER, this is
AXIS — so this is an **A/B to run under A10**, not a change to make.

### ⭐⭐ 14.3.4.1 THE OWNER RE-FRAMED IT, AND TWO CAUSES ARE NOW ELIMINATED BY CONTROL (2026-08-22)

**Owner's requirement, stated precisely**: *"rotation of the hand on the vertical
world axis = equal rotation of the cube in the vertical 2d screen axis"*. Observed:
the cube turns about a **mix of screen x and y**. That matches the measurement —
the fitted axis sits **29.8° off screen-vertical inside the screen plane**.

**1. ❌ NOT the hand's own anatomy** (`analysis/t5e_axis_vs_hand_long_axis.py`).
Turning a palm edge-on is forearm pronation, whose axis is the hand's LONG axis —
so a tilted hand would produce a tilted cube axis *correctly*. Refuted: in the yaw
take the hand's long axis is **+4.7° from screen-vertical** (near-upright) while the
fitted axis is **+23.8°**. The cube is not faithfully following a tilted hand.
⚠ The pitch control reads **+80.9°**, which is *correct* (pitch's axis IS ~90° from
vertical) and is what shows the harness is sane.

**2. ❌ NOT the fitting code — Horn is EXACT.** Synthetic control: a REAL palm
constellation rotated by an exact amount about vertical, fed through production's
estimator, recovers the axis to **0.000°** and the angle to **0.01°** at 10/20/30/
45/60/80°. ⭐ **So `palm_rotation.Horn` is not the defect and must not be
"fixed".** Together with §14.3.4's mirror and degeneracy controls, **every
code-side candidate is now eliminated. The error is in the DATA.**

**⭐ WHAT THE DATA DOES DO, measured on the same synthetic rig with z scaled to 0.6
(a compressed depth estimate — MediaPipe's weakest coordinate, §13.2):**

| applied yaw | recovered angle | axis tilt |
|---|---|---|
| 10° | **7.03°** | 7.5° |
| 30° | **23.87°** | 6.4° |
| 60° | **61.63°** | 3.8° |

⭐⭐ **Depth error UNDER-REPORTS the yaw angle — 10° of hand becomes 7° of cube —
and that alone violates the owner's "equal rotation" requirement**, independently
of any axis question. The tilt it induces is modest and lands on **z**, whereas the
observed real-data tilt is toward **x**; so z-compression explains the *angle*
shortfall but not all of the *axis* mixing.

⚠ **The residue still cannot be attributed from this corpus** (§14.3.3): a
mixed-axis operator rotation tilts the axis toward x exactly as observed, and the
only yaw take has measured pitch contamination. **A clean yaw take remains the
one missing control.**

⭐ **DESIGN CONSEQUENCE, and it converges with 4.1.** The signal a z-free yaw
estimate needs — how far the palm quad has foreshortened — **is the same
measurement 4.1's `max4` anchor already makes**. Building a z-free orientation
decomposition (roll from the in-image knuckle angle, exact; yaw from width
foreshortening; pitch from length foreshortening) reuses 4.1's machinery rather
than duplicating it. ⚠ Its own costs are real and must not be waved past: a cosine
is insensitive near 0°, foreshortening is sign-ambiguous (needs DR-2's palm sign to
disambiguate), and width also shrinks with DISTANCE — which is precisely the
confound 4.1/M9 exists to resolve. **This is an A10 A/B, not a refactor.**

### ⭐⭐ 14.3.4.2 THE CLEAN YAW TAKE IS RECORDED, AND IT SPLITS THE DEFECT IN TWO (2026-08-22)

`2026-08-22_134553_yaw_sweep_constant_depth` — RIGHT hand, 508 frames, 24.79 fps,
a hand in **508/508** frames. ⚠ Ended at 20.5 s of a requested 30 s (preview window
closed early), which still gives ~6 sweeps and is ample. **The recorder's prompt was
corrected FIRST** — "doorknob" (which is ROLL about depth, not yaw) removed, and
"fingers STRAIGHT UP" / "no sideways tilt" added, plus a new `YAW_AXIS_NOTE`.

**✅ IT PASSES THE CLEANLINESS GATE** (`analysis/t5c_operator_or_estimator.py`):

| take | WIDTH collapse | LENGTH collapse | verdict |
|---|---|---|---|
| **2026-08-22 (new)** | **0.219** | 0.751 | ✅ textbook single-axis yaw |
| 2026-08-04 (old) | 0.629 | 0.670 | ❌ mixed axis |

**⭐ RESULT — the owner's requirement is TWO claims and they fail differently**
(`analysis/t5f_equal_rotation.py`; ground truth is z-free, from palm-width
foreshortening, unwrapped past edge-on with the palm-facing sign):

| | old (contaminated) | **new (clean)** |
|---|---|---|
| axis, in-screen tilt from vertical | +21.6° | **+12.3°** |
| axis, 3D off-vertical | 31.2° | **13.0°** |
| angle gain (median) | not interpretable | **1.11** |

1. ⭐ **"EQUAL rotation" is broadly SATISFIED.** Gain by true-yaw band: 0.93 / 0.68 /
   0.86 / 1.11 / 1.13 / 1.10 / 1.11 / 1.11 — **median 1.11**. The cube turns about as
   far as the hand does. ⚠ This **retires the worry raised in §14.3.4.1** that depth
   error would badly under-report the angle: the synthetic used z×0.6, and the real
   z is evidently not that compressed. The residual pattern is a mild *under*-rotation
   between 20–60° and a ~11% *over*-rotation past 60°.
2. ⛔ **THE AXIS IS THE REAL DEFECT, AND IT IS NOW CLEANLY QUANTIFIED AT ~13°.**
   That is what shows on screen as the owner's "mix of x and y".
3. ⭐⭐ **ROUGHLY HALF THE PREVIOUSLY REPORTED FIGURE WAS OPERATOR CONTAMINATION**
   (31.2° → 13.0°). ⚠ **Quote 13.0°, never the old 25.6/27.3/33.1° numbers** — those
   came from the mixed-axis take and §14.3.3 explains why.

⚠ **What is still NOT established**: whether the residual ~13° is entirely estimator
bias or partly residual operator wobble — a freehand "pure" yaw can plausibly carry
~10°. The controls in §14.3.4/§14.3.4.1 rule out the mirror, the frame convention,
constellation degeneracy, the hand's own anatomy, and the Horn fit itself, so the
remaining candidates are **MediaPipe's world-z error** and **residual hand wobble**.

⭐ **A NOTE ON THE Z-FREE MEASUREMENT, learned the hard way here**: `acos(width)`
**FOLDS at edge-on** — past 90° the width comes back up, so 150° reads as 30°. A
first pass produced a nonsense "gain 3.57" from exactly this, and a second produced
"gain 21.5" by freezing the estimator's reference on an already-rotated frame rather
than the most face-on one. **Both traps are inherent to any foreshortening-based
angle design, not to the harness** — so if a z-free yaw estimate is ever built, it
MUST carry a sign cue (DR-2's palm sign works) and a face-on reference.

⚠ **The small-angle noise floor, binding on any future axis measurement**: below
~30° of rotation the axis is barely determined — a *clean* pitch take reads
**44–63° off its own axis** there. Never quote an axis deviation without the
rotation magnitude it was measured at. This is also why `t5d`'s harvested roll
segments (12–20° sweeps) prove nothing.

### ⛔⛔ 14.3.4.3 PRODUCTION AND THE DEBUG TOOL ARE NOT THE SAME PIPELINE (2026-08-22)

**Owner, 2026-08-22**: *"in this debug configuration the vertical axis rotation
looks ok ... it seemed to me the behavior in the production was not the same."*
**Correct, and now measured** (`analysis/t6_mirror_route_ab.py`).

**FIRST, WHAT IS SHARED — audited, so nobody re-hunts these.** Identical in both:
the estimator (`Horn(PALM_LANDMARKS,'ref')`), the delta math
(`delta = q_now * conj(q_grab)`, left-multiplied), `ROTATION_SLERP_FACTOR` 0.35,
and **DR-1** — the server runs `hand_identity` and OVERRIDES MediaPipe's
handedness with the resolved track label (`hands_visualizer.py`), exactly as
`LiveSnapDebug.py` does. Pixel and world landmarks are extracted with the SAME
label key, so they cannot be cross-assigned. **None of these is the difference.**

**⭐ EXACTLY ONE THING DIFFERS — WHERE THE MIRROR IS APPLIED:**

| | detection input | world landmarks |
|---|---|---|
| **debug** (`LiveSnapDebug.py`, and the recorders) | frame `cv2.flip`ped **before** detect | used as-is |
| **production** (`VisionPipeline.py`) | **raw, un-mirrored** | **x-negated after** (`remap_world_keypoints(invert_x=True)`) |

Those are equivalent **only if MediaPipe is mirror-equivariant**
(`W_mirrored_input == diag(-1,1,1) · W_raw_input`). ⚠ **Both files flagged this as
never verified, in nearly the same words** — `remap_world_keypoints`: *"This has
NOT been live-verified yet ... don't assume this is correct as-is"*;
`LiveSnapDebug.py`: *"verify live when that port happens"*.

**⛔ IT IS NOW VERIFIED, AND IT IS FALSE.** Both routes run on the SAME camera
frames through two detectors:

| | world-landmark RMS, debug vs mirrored-production | angle between the two routes' rotations |
|---|---|---|
| **VIDEO mode** (what both systems actually run) | **7.66 mm** p50 (p95 9.54, max 19.8) | **11.83°** p50 (p95 15.9, max 19.5) |
| **IMAGE mode** (stateless control) | **10.07 mm** p50 (p95 16.7) | **20.14°** p50 (p95 25.0) |

1. ⚠ **This is NOT tracking-state drift.** The obvious confound is that two VIDEO
   detectors carry independent temporal state. The stateless IMAGE-mode control
   makes the disagreement **larger, not smaller** — so it is the MODEL, not the
   tracker. **MediaPipe is not mirror-equivariant.**
2. **The magnitude is not noise.** 7.7–10 mm is on the scale of MediaPipe's own
   documented 13–15 mm world-landmark error (§1.4) and **3–4× the palm's own
   2.76 mm rigidity** (§0.2).
3. ⭐⭐ **It explains the owner's report exactly.** The clean-take residual axis
   tilt of **13°** (§14.3.4.2) was measured on *debug-route* recordings — the
   recorders flip before detection. **Production carries that PLUS ~12° of route
   disagreement**, which is why the debug tool "looks ok" and production does not.

**⭐ THE FIX IS TO DELETE THE ASSUMPTION, NOT TO TUNE IT**: make the server
`cv2.flip` the frame **before** detection, exactly as the debug tool does. Then
production *is* the debug route by construction — same input, same output — and no
equivariance is assumed anywhere.

⚠⚠ **It is a COORDINATED change; doing part of it re-creates §13.6.1's silent
handedness inversion.** All four together:
1. `VisionPipeline.py` — flip the frame before `detect_for_video`
2. `remap_keypoints` (pixel) — `invert_x` → **False** (already mirrored)
3. `remap_world_keypoints` — `invert_x` → **False**
4. `hands_visualizer._mirror_handedness` — **remove**; MediaPipe now reports the
   mirrored label natively, so mirroring it again would re-invert chirality

### ✅ 14.3.4.4 THE FIX IS BUILT (2026-08-22) — ⚠ automated checks green, LIVE CONFIRMATION STILL OPEN

**FIVE sites, not four.** §14.3.4.3's plan listed four; a fifth was found while
implementing and would have been a silent regression:

| # | site | change |
|---|---|---|
| 1 | `VisionPipeline.py` | `cv2.flip(frame, 1)` before detection, on **BOTH** `cap.read()` calls |
| 2 | ⚠ **face** `remap_keypoints` | `invert_x` → **False** — **MISSED BY THE ORIGINAL PLAN** |
| 3 | hands pixel `remap_keypoints` ×2 | `invert_x` → **False** |
| 4 | `remap_world_keypoints` ×2 | `invert_x` → **False** |
| 5 | `hands_visualizer._mirror_handedness` | **removed**; the mirrored frame makes MediaPipe's own label already correct |

⚠ **On site 1**: the FIRST `cap.read()` is not only a resolution probe — the loop
consumes that frame before reading the next, so it reaches inference. Flipping
only the loop's read would have left frame 1 un-mirrored.

⚠ **On site 2**: face keypoints carried `invert_x=True` too. Left alone they would
have been mirrored TWICE (once by the frame flip, once by the remap) — the M5d
even/odd-flip trap, latent because the face consumer is still a `pass`.

⭐ **Both utils' DEFAULTS were also flipped to `invert_x=False`** and the
falsified rationale in `remap_world_keypoints`'s docstring replaced with the
measurement, so a future call site cannot silently reinstate the flip.

**Automated results after the change:**
- `VerifyChiralityFixture.py` — **ALL CHECKS PASSED**, 100% on every clip
  (label / production sign / negative control), same as the pre-change baseline
- the 10 golden-vector suites — **10/10 PASS**

⛔⛔ **DO NOT READ THAT AS CONFIRMED.** Those fixtures run on **RECORDINGS**, which
were always made with the frame flipped before detection. They prove the
downstream sign convention is right *for mirrored-label input* — which is what
production now emits — but **they never execute the live server**. §13.6.1 shipped
inverted while passing an end-to-end claim; the only thing that closes this gap is
the owner watching the running pipeline.

⭐ **What to watch, and why DIRECTION matters more than axis**: an axis error is
what prompted this work, but **chirality is the failure mode of this class of
change**. A cube that turns about the right axis *the wrong way* is a sign
inversion — and it is exactly what a recording-based fixture cannot catch.

**Status 2026-08-22: built, automated checks green, both apps launched and run
without error, owner verdict NOT YET GIVEN.** ⚠ Not committed.

⚠ **Side-by-side is impossible on one webcam** — DSHOW is exclusive ACROSS
processes, so production and the debug tool must be compared back-to-back. (Two
`VideoCapture` handles inside ONE process both succeed, which is a misleading
test — it does not predict cross-process behaviour.)

⭐ **Verification is already built**: `analysis/verify_chirality_fixture.py` /
`VerifyChiralityFixture.py` and the `known_left_*`/`known_right_*` takes exist for
exactly this class, and §0.12's Q1 was written to catch it. **Run them before and
after.** ⚠ And note this decides the same question for the **web/mobile port**
(U3), which faces the identical choice.

### ✅ 14.3.4.5 OWNER CONFIRMED THE MIRROR FIX LIVE — and found the label inversion (2026-08-22)

⭐⭐ **§14.3.4.3's fix is LIVE-CONFIRMED.** Owner, after running both apps
back-to-back: *"both sessions are OK now. fix is positive."* **The production
pipeline and the debug tool now behave the same**, which is what §14.3.4.3
predicted and what the recording-based fixtures could not prove.

**Separate defect reported in the same breath**: *"on both the sessions, the label
'left' or 'right' hands are inverted (probably because the camera is taking the
view from the opposite of the hand). It shall be rectified."* **Correct, and
measured against the ground-truth clips:**

| ground truth | internal label |
|---|---|
| physical **RIGHT** hand | `Left` (751/751 frames) |
| physical **LEFT** hand | `Right` (200/200 frames) |

⚠⚠ **THIS IS PRE-EXISTING, NOT A SIDE EFFECT OF THE MIRROR FIX.** Before it,
detection ran on the raw frame and `_mirror_handedness()` flipped the label;
after it, detection runs on the mirrored frame and MediaPipe reports that same
value directly. **Both routes display the same thing** — which is exactly why
`VerifyChiralityFixture.py`, whose ground truth literally reads *"PHYSICAL Right
hand -> expected label 'Left' (mirrored convention)"*, passed unchanged before AND
after.

⛔⛔ **THE INTERNAL LABEL WAS NOT FLIPPED, AND MUST NOT BE.** It is load-bearing in
four places, all calibrated to the current convention:
1. `palm_geometry.is_thumb_outward()`'s handedness-dependent chirality correction
   (`if handedness == "Left": cross = -cross`). **Flipping the label inverts that
   sign — that IS §13.6.1**, the bug that shipped inverted in production and
   survived an "end-to-end confirmed" claim.
2. All **415 recorded sessions** store labels in this convention — flipping live
   would desynchronise every replay harness from the live pipeline.
3. `VerifyChiralityFixture.py` encodes it as ground truth.
4. Cube ownership and DR-1's track slots key on it (queue **T3**).

⭐ **FIXED AS DISPLAY-ONLY**, at the two places a human reads it:
`hands_visualizer.py`'s preview text and `LiveSnapDebug.py`'s per-hand overlay.
The helper is `hand_identity.anatomical_name()`, defined in the module **both**
already import so the two cannot drift (rule N6: imported, never copied). ⚠ Its
docstring forbids feeding the result back into any rule, filter or ownership key.

**Re-verified after the display change**: `VerifyChiralityFixture.py` ALL PASS,
10/10 golden-vector suites PASS — the fixture passing is itself the proof the
internal convention did not move.

⚠ **Not yet eyeballed live** — the label change is cosmetic and low-risk, but it
has not been seen on screen yet.

---

### ⚠ 14.3.4.6 THE CARD-REFERENCE YAW TAKE (2026-08-23) — CLEAN, BUT TOO SHORT TO CONCLUDE

`2026-08-23_202153_yaw_card_axis_check`, debug tool, 586 frames / 34.3 s.
⚠ **Analysed over 5.0–31.3 s only** — the operator asked for the first 5 s and last
3 s to be dropped (*"I was not really on position then"*). Harness:
`analysis/t5g_cube_axis_from_recording.py`.

⭐⭐ **THE METHOD IS NEW AND IT IS THE PART WORTH KEEPING.** The operator held a flat
card clamped at the **BASE of the index and middle fingers** — i.e. on the rigid
palm plate the Horn fit actually uses (landmarks 0, 5, 9, 13, 17) — plane parallel
to the palm, long edge VERTICAL. Under a pure yaw a vertical card stays vertical,
so **wobble becomes visible to the operator in the moment and can be corrected as
it happens**, instead of being discovered in the analysis afterwards.
⚠ **NOT at the fingertips**, which was the first instinct: fingertips contribute
NOTHING to the rotation fit and sit two joints away from the plate, so a finger
flex would rotate the card without rotating the estimate — and be blamed on the
estimator. ⚠ The card is never in the file (recordings hold landmarks, never
pixels — N14); it is an operator-control device, and the cleanliness gate is what
confirms from the data that the control worked.

⭐ **AND IT WORKED.** Pitch contamination, which is sweep-independent, came out
BETTER than the take that currently defines "clean":

| | this take | 2026-08-22 "clean" | 2026-08-04 mixed |
|---|---|---|---|
| palm LENGTH collapse (contamination) | **0.833** | 0.751 | 0.670 |
| palm WIDTH collapse (sweep size) | 0.639 | **0.219** | 0.629 |

⛔ **BUT THE SWEEP WAS TOO SMALL, AND THAT IS WHAT MAKES IT INCONCLUSIVE.** Width
implies only **~50°** of yaw from face-on; the cube reached a maximum of 55.9° and
a median of 39.3°. The 13.0° reference was measured **at large rotation**, and
§14.3.4.2's binding rule is that an axis deviation is meaningless without the
rotation magnitude it was measured at — below ~30° even a *clean pitch* take reads
44–63° off its own axis.

**Axis vs rotation magnitude — the only honest way to read it:**

| rotation band | frames | axis off-vertical (median) |
|---|---|---|
| 30–40° | 63 | 66.8° |
| 40–50° | 37 | 59.2° |
| **50–60°** | **9** | **39.1°** |
| 60–90° | 0 | never reached |

⭐ **Monotonically converging, exactly as the noise floor predicts** — and it never
reached the band where 13.0° was measured. **This take shows no evidence of a NEW
or worse defect; it simply cannot resolve the old one.** ⛔ Do not quote 39° or
66° as the yaw tilt.

⭐ **ONE THING IT DOES REPRODUCE INDEPENDENTLY**: implied hand yaw ~50° against a
cube maximum of 55.9° is a gain of **~1.12**, against the 1.11 median measured on
the 2026-08-22 clean take by a completely different method. "Equal rotation" holds.

✅✅ **AND IT DELIVERED AN UNASKED-FOR RESULT THAT MATTERS MORE — 4.2's DEPTH
ANCHOR IS NOT FOOLED BY ROTATION.** A rotation-only take is the direct test of the
A10 property `palm_depth` was built for (a depth anchor must stay CONSTANT while
the hand merely rotates), and this is the first time it has been measured **live,
with an object actually attached**, from the cube's own recorded depth rather than
a re-derivation:

| rotation | frames | median object depth |
|---|---|---|
| 0–15° | 129 | 0.479 m |
| 15–30° | 214 | 0.483 m |
| 30–45° | 98 | 0.490 m |
| 45–90° | 11 | 0.495 m |

**+16 mm across a 50° rotation.** The total depth span over the take was 90 mm, so
the great majority of that is the operator's hand genuinely moving, not
foreshortening leaking into Z. ⭐ That is the `max4` multi-anchor rule doing
precisely the job §14.3.1/§14.3.2 designed it for.

⚠⚠ **TWO HARNESS BUGS WERE CAUGHT AND FIXED BEFORE ANY NUMBER WAS REPORTED**, both
of them already documented traps:

1. ⛔ The first pass referenced the cube's orientation to the **first held frame**
   of the trimmed window. §14.3.4.2 records exactly this trap ("produced 'gain
   21.5' by freezing the reference on an already-rotated frame rather than the most
   face-on one"). The reference is now the **widest-palm frame** in the window, and
   that alone moved the reported axis from 77° to 65°.
2. ⛔ The cleanliness gate conflated **a SHORT sweep with a DIRTY one**. Width
   collapse is ~cos(sweep) BY CONSTRUCTION, so a clean 50° yaw scores 0.64 and
   looks identical to the contaminated 2026-08-04 take. ⭐ **The two numbers answer
   different questions and must be read separately: LENGTH collapse measures
   contamination and is sweep-independent; WIDTH collapse measures how far the hand
   turned.** The gate now prints both as implied angles.

⭐ **WHAT TO DO NEXT — the retake needs TWO changes, not one:**
- **Turn further**, until the palm is nearly edge-on (~80°), not the ~50° achieved.
- ⭐ **PAUSE about a second at each extreme.** Only **9 frames** of 452 landed in
  the informative 50–60° band because the sweeps moved fastest exactly where the
  measurement is meaningful. The pause, not the sweep count, is what fills that bin.
⚠ Going past edge-on is acceptable for THIS measurement — the axis comes from the
recorded quaternion, which does not fold — but the width-based *sweep* estimate
above does fold past 90°, so read it as a floor once the palm passes edge-on.

### ✅✅ 14.3.4.7 THE YAW QUESTION IS ANSWERED (2026-08-23) — the tilt is real, and the one candidate fix is REJECTED

`2026-08-23_203307_yaw_card_axis_check_b` — the retake with the two corrections
§14.3.4.6 asked for (turn further, **and pause at each extreme**). It worked:
**77° sweep** (width collapse 0.229, matching the 2026-08-22 clean take's 0.219),
contamination 0.798 (better than that take's 0.751), **536 frames above the noise
floor and 185 in the 60–90° band** against take 1's nine. ⭐ **The PAUSE was the
fix, not the extra sweeps** — the hand moves fastest exactly where the measurement
is meaningful.

**Axis by rotation band, from the cube's own recorded quaternion:**
36.7° (30–40) → 29.8° (40–50) → 18.0° (50–60) → **17.2° (60–90, n=185)** —
converged and stable.

#### ⛔ THE CARD DID NOT REDUCE THE TILT. IT READ HIGHER.

The card was introduced to remove **operator wobble** as a candidate by control.
It did control the sweep — contamination genuinely improved — but the measured
tilt went **UP**, not down: ~17–19° with the card versus **12.6–13.0°** on the
card-free clean take. Two readings, and both point the same way for the decision:
(a) the residual is not wobble, so removing wobble cannot help it; or (b) gripping
a card perturbs the hand or its landmarks and adds error of its own.
⭐ **Either way the card-free take remains the better measurement of the defect,
and 13° stands as the number.** ⚠ The card method is still worth keeping for
what it was good at — it produced the cleanest contamination score ever measured
— but it must not be used for the axis magnitude itself.

#### ⛔⛔ THE 9-POINT CONSTELLATION A/B IS CLOSED: REJECTED UNDER A10

Open since 2026-08-22 on the strength of "palm+tips beats palm-only on axis
fidelity in every take measured". ⚠ **Those numbers came from the CONTAMINATED
2026-08-04 take.** Re-run on the clean card-free take, with jitter measured on a
real production handling take, one variable, same frames
(`analysis/t5h_constellation_ab.py`):

| | axis @ 60–90° (clean yaw) | jitter p95 (production handling) |
|---|---|---|
| **palm, 5 pt — SHIPS** | **12.6°** | **25.41°** |
| palm+tips, 9 pt | 11.2° | 30.34° |

**+1.4° of axis accuracy for +4.9° of p95 jitter.** ⛔ **Do not switch the
constellation.** It reproduces the DIRECTION of the original jitter finding
(tips worse) while the axis benefit is a fraction of what the contaminated take
advertised. A10: a null-or-negative result is recorded, not shipped hopefully.

⭐ **The harness validates itself on the way**: `t5h` reads **12.6°** for the
shipped constellation on the take `t5f` measured at **13.0°** — two different
implementations, two different routes to the ground truth, same answer.

#### ⭐ WHAT TO DO ABOUT THE YAW TILT: ACCEPT ~13° FOR NOW

Every code-side cause is eliminated (§14.3.4/§14.3.4.1: mirror, frame convention,
constellation degeneracy, hand anatomy, the Horn fit itself — exact to 0.000° on
synthetic input). Operator wobble is now argued against by control. The remaining
candidate is **MediaPipe's world-z error**, i.e. the DATA, and the only lever that
would move it is a **z-free rotation decomposition** (roll from the in-image
knuckle angle, yaw from width foreshortening, pitch from length foreshortening).
⚠ That is a substantial build, it shares its measurement with 4.1's anchor, and
it carries real costs — cosine-insensitive near 0°, sign-ambiguous (needs DR-2's
palm sign), and width also shrinks with DISTANCE, which is the very confound
4.1/M9 exists to resolve. **Not worth it ahead of 4.4+B5.**

⚠ **ROLL IS STILL NEVER MEASURED.** No scripted take exists and harvesting it from
free play fails (those takes are ~85% two-handed). **Do not claim rotation is
correct in all three axes** — two are measured, one is unknown.

### ⭐⭐ 14.3.4.8 THE OWNER'S ACTUAL QUESTION, ANSWERED — and a NEW LEVER on the tilt (2026-08-23)

⚠ **§14.3.4.7's "accept ~13°" recommendation is SUPERSEDED by this section.** It
was made in the units the analysis happened to use, and those units understated
what the defect looks like on screen.

#### 1. Does the cube rotate purely about the vertical axis? **NO — it LEANS as it turns.**

Owner, 2026-08-23: *"did the cube purely rotate around the vertical axis? ... this
is key for me, as the cube has to represent the physical world correctly."*
⛔ The honest answer, measured on the clean card-free take by rotating the cube's
own UP vector and asking how far it leaves vertical:

| hand turned | cube tipped out of upright (median / p90) |
|---|---|
| 0–20° | 6.8° / 10.7° |
| 20–40° | 12.3° / 16.1° |
| 40–60° | 21.9° / 25.4° |
| **60–90°** | **26.8° / 32.2°** |

⭐ **State it this way from now on, not as "13° of axis deviation".** A 13° axis
tilt sounds minor; *"the object leans up to 27° as you turn it"* is what the owner
sees, and it is the same fact. **The rotation AMOUNT is right (gain 1.13, matching
§14.3.4.2's 1.11 by an independent route); the UPRIGHTNESS is not.**

#### 2. ⭐ THE LEAN IS A SYSTEMATIC BIAS, NOT NOISE, AND IT LIVES IN THE SCREEN PLANE

Owner's observation, and it is the right one: *"the +12.3° is close to the +13°.
Check if this is a pure coincidence."* **It is not a coincidence — it is a
decomposition.** Measured over 388 frames above 40°:

| | |
|---|---|
| axis components, median abs | x **0.212**, y 0.974, z **0.064** |
| tilt measured IN the screen plane (x vs y) | **12.31°** |
| tilt measured in full 3D (includes z) | **12.98°** |
| share of the tilt that is in-plane | **95%** |

The two numbers agree because **the axis error has almost no depth component**: it
is a SIDEWAYS LEAN of the rotation axis as seen on screen, exactly the *"mix of
screen x and y"* the owner reported in §14.3.4.1. ⚠ And it is **100% consistent in
direction** (every one of 388 frames leans the same way, IQR 9.3–17.2°) — a
systematic bias, which is the class of error that CAN have a correction.

⚠ **This qualifies §14.3.4.1's reasoning.** That section argued depth error's
induced tilt "lands on z, while the observed tilt is toward x", and used it to
separate the two. The observed tilt is indeed ~all x — but item 3 shows z-trust
nonetheless drives it, so that argument does not exclude depth as the cause.

#### 3. ⭐⭐ NEW: THE TILT SCALES WITH HOW MUCH THE FIT TRUSTS MEDIAPIPE'S WORLD Z

Re-fitting the SHIPPED constellation with world z multiplied by a constant `k`
(everything else identical), on the clean card-free take:

| z-scale `k` | axis tilt @>40° | cube tip-out @60–90° | gain (fitted/true) |
|---|---|---|---|
| 0.00 | **2.0°** | **3.9°** | 1.34 |
| 0.20 | 2.1° | 3.9° | 1.27 |
| 0.40 | **3.7°** | **6.6°** | 1.20 |
| 0.60 | 7.0° | 12.6° | 1.16 |
| 0.85 | 11.1° | 19.6° | 1.13 |
| **1.00 — SHIPS** | **13.0°** | **23.4°** | **1.13** |

⭐ **Monotonic, and large.** Down-weighting z to 0.4 would cut the visible lean
from **23.4° to 6.6°**, at the cost of the cube over-rotating by 20% instead of
13%. That is the first lever ever found that moves this defect.

⛔⛔ **DO NOT SHIP IT ON THIS EVIDENCE.** It is ONE take, ONE operator, ONE axis.
Before it could be considered it needs, under A10: **(a)** the PITCH takes — z is
what makes pitch observable at all, so `k` may well destroy it; **(b)** jitter in
real handling, since down-weighting a coordinate can amplify noise; **(c)** the
ROLL axis, which has still never been recorded at all; **(d)** a principled
statement of what `k` IS — today it is a global fudge factor, and the honest
version is anisotropic weighting of a coordinate already known to be the least
reliable (§13.2), not a magic number.
⚠ And it interacts with 4.2: `palm_depth` deliberately uses **pixel** spans and
never world z, so it is unaffected — verify that, do not assume it.

#### ⚠ TWO MEASUREMENT TRAPS HIT AGAIN IN THIS SESSION, BOTH ALREADY DOCUMENTED

1. **The `acos` FOLD.** A first pass at the gain column read **2.41–3.02** where
   the true value is ~1.13, because width foreshortening folds past edge-on
   (a 140° pose reads as 40°). §14.3.4.2 records the identical failure producing
   "3.57". Fixed by unwrapping with DR-2's palm-facing sign — after which the
   harness reproduces the documented 1.11 as **1.13**.
2. **The card perturbs the hand, and the operator identified the mechanism**:
   *"I had to tilt the hand and arm to keep the card straight up."* That is why
   the card take reads 17–19° against the card-free 12.6–13.0°. ⭐ **The card
   method controls the SWEEP well — best contamination score ever measured — but
   it must never be used for the tilt magnitude.**

### ⛔⛔ 14.3.4.9 THE z-SCALE LEAD IS DEAD (2026-08-23) — it moves the error from yaw to pitch

§14.3.4.8 found that the yaw axis tilt scales with how much the Horn fit trusts
MediaPipe's world z, and flagged the obvious way it could die: **z is what makes
PITCH observable at all.** Under pitch the knuckle row barely moves in the image
and the hand rotates INTO the screen, so a fit that ignores depth has almost
nothing left to measure. Tested (`analysis/t5i_zscale_sweep.py`):

| `k` (world z x k) | YAW axis | PITCH axis *(validated take)* | PITCH axis *(2nd take)* |
|---|---|---|---|
| **1.00 — SHIPS** | 14.5° | **5.5°** | 30.0° |
| 0.60 | 7.9° | 5.3° | 33.7° |
| 0.40 | **4.3°** | **10.6°** | 38.0° |
| 0.20 | 1.9° | 19.3° | 45.6° |
| 0.00 | 0.6° | 22.5° | 60.4° |

⛔ **REJECTED.** At the k that makes yaw good (0.4), pitch roughly DOUBLES on the
take where pitch is currently excellent. There is no k that improves both. **This
is not a fix, it is a redistribution** — exactly the failure this test was written
to catch, and the reason it was written before proposing anything.

⭐⭐ **BUT THE DIAGNOSIS IS NOW ESTABLISHED, NOT MERELY SUSPECTED.** Scaling world z
moves the yaw tilt smoothly from 14.5° to 0.6°, which demonstrates the tilt is
**caused by MediaPipe's world-z error**. §14.3.4/§14.3.4.1 had eliminated every
code-side cause and pointed at the data; this is the positive evidence for it.

⚠ **AND IT CLOSES THE 'JUST WEIGHT z LESS' FAMILY**, not only this one constant. A
weighting that helps yaw necessarily hurts pitch, because the two axes need
opposite things from the same coordinate. ⛔ Anisotropic covariance was already
tried and failed five times (queue 2.3, audited and confirmed genuine) — this is
the same wall from a different side. **The only remaining candidate is the z-free
rotation decomposition** (roll from the in-image knuckle angle, yaw from width
foreshortening, pitch from length foreshortening), which does not weight z at all
because it never uses it.

#### ⚠⚠ A THIRD MEASUREMENT TRAP, AND IT NEARLY PRODUCED A FALSE ALARM

The first pitch run reported **45–55°** where §14.3.4 documents **5.0°**, which
looked like pitch being catastrophically broken. It was the harness. **Two
harnesses were measuring different quantities under the same name:**

* `t5_rotation_axis_fidelity.py` **AVERAGES the per-frame axes first**, then reports
  how far that MEAN axis sits from the expected one — pure BIAS. That is where
  "pitch 5.0°" comes from.
* `t5i` was reporting the **MEDIAN PER-FRAME deviation**, which also carries
  frame-to-frame SCATTER.

Both are legitimate and they are not the same number. `t5i` now prints **both**,
and at k=1.0 its MEAN-axis column reads **5.5°** against the documented 5.0° —
which is what says the harness is sound.
⭐ **THE RULE: two numbers measuring "the axis error" are not comparable unless
they aggregate the same way. Print the aggregation, not just the value.**
⚠ An earlier pass also assumed pitch's expected axis was a fixed screen-horizontal;
it is the **knuckle row**, which is only horizontal when the hand is held upright.

### ✅✅ 14.3.4.10 ROLL IS MEASURED AT LAST (2026-08-23) — and it CONFIRMS the depth diagnosis

`2026-08-23_211528_roll_card_axis_check_b` (first 4 s dropped, operator).
**The roll axis had never been recorded in this project.** Harness:
`analysis/t5j_roll_axis.py`.

⭐⭐ **ROLL IS THE CONTROL EVERY OTHER MEASUREMENT NEEDED.** It is rotation about
the CAMERA axis, so it happens entirely in the image plane and **its ground truth
needs no depth at all** — just the in-image angle of the knuckle row. So it
separates "the fit/conventions are wrong" from "the depth data is wrong", which
yaw and pitch cannot do on their own.

| axis | mean-axis error | gain (fitted/true) | needs depth? |
|---|---|---|---|
| **ROLL** | **6.7°** | **1.02** | ⭐ **NO** |
| YAW | 14.5° | 1.13 | yes |
| PITCH *(validated take)* | 5.5° | 0.74 | yes |

⭐ **Roll's gain is 1.02 — essentially exact.** The two axes that depend on depth
are wrong in OPPOSITE directions (yaw over-rotates 13%, pitch under-rotates 26%)
while the axis that does not depend on depth is right.

⛔ **That is independent confirmation of §14.3.4.9's conclusion by a completely
different route.** The Horn fit, the quaternion maths, the frame conventions and
the renderer are all SOUND — roll exercises every one of them and comes out
right. **The defect is MediaPipe's world-z.** Two independent lines of evidence
now say so: scaling z slides the yaw tilt 14.5°→0.6°, and the one axis that
never touches z is accurate.

⭐ **THE OPERATOR AID THAT MADE THE TAKE POSSIBLE, worth reusing.** The first
attempt was discarded by the owner — *"I have to stay exactly perpendicular to the
axis of the camera and this is difficult"*. ⭐ `edge_on_measure` is **INVARIANT
under pure roll** (an in-plane rotation turns both palm vectors together, changing
neither their lengths nor the angle between them) and drops only when yaw or pitch
leaks in. It was added to the debug HUD as a live `sq` readout, and the operator
held it steady at **0.65–0.71** across the whole take. Cleanliness: width collapse
**0.904**, length **0.891** — both high, which is exactly what a pure roll should
produce, since nothing foreshortens.
⚠ Absolute squareness was 0.68, not 1.0 — the palm was somewhat turned. That does
not matter here: **purity (steadiness) is what the measurement needs, not
squareness**, and steadiness is what the aid delivers.

### ⭐⭐ 14.3.4.11 THE FIX FOR THE YAW LEAN: SOLVE ORIENTATION FROM 2D, NOT FROM PREDICTED DEPTH (design, 2026-08-23)

Owner, 2026-08-23: *"this is a show-stopper for me as I can't tolerate a cube which
rotates differently than what it should to reflect the physical world."*

**The evidence now points at ONE intervention, and the literature independently
prescribes the same one.**

#### The evidence, in one table

| axis | mean-axis error | gain | uses MediaPipe's world z? |
|---|---|---|---|
| **ROLL** | **6.7°** | **1.02** | ⭐ **NO** — pure image plane |
| YAW | 14.5° | 1.13 (over) | yes |
| PITCH | 5.5° | 0.74 (under) | yes |

⭐ **The axis that never touches depth is the accurate one, and the two that do are
wrong in OPPOSITE directions.** Add §14.3.4.9's finding — scaling world z slides the
yaw tilt smoothly 14.5° → 0.6° — and the conclusion is not in doubt: **MediaPipe's
2D landmarks are good; its predicted depth is what breaks the rotation.**

#### The prescription: PnP against a canonical palm, not Horn against predicted 3D

Today `palm_rotation.Horn` fits **3D↔3D**: the canonical palm constellation against
MediaPipe's `world_landmarks`, z and all. **Replace it with a 2D↔3D fit** — solve
the pose that best PROJECTS a canonical 3D palm onto the observed 2D pixel
landmarks. The predicted depth is then never consumed at all.

⭐ **This is what the current literature does.** Monocular hand methods recover
GLOBAL orientation by aligning a 3D model to 2D keypoints under a camera model
rather than trusting regressed root-relative depth — *Monocular 3D Hand Pose
Estimation with Implicit Camera Alignment* (arXiv 2506.11133) does exactly this
with a PnP formulation on MediaPipe 2D keypoints, and *EPro-PnP* (arXiv 2303.12787)
is the general end-to-end form. The depth ambiguity that makes regressed z
unreliable for orientation is the stated motivation in both.

#### ⭐⭐ FOUR REASONS THIS FITS THIS PROJECT UNUSUALLY WELL

1. ⛔ **NO MANO, SO NO LICENCE PROBLEM (N13).** The papers use MANO; **we do not
   need it.** The fit needs only the RIGID 5-POINT PALM — wrist + four MCPs — and
   its anthropometric dimensions are **already in the codebase**
   (`palm_depth.NOMINAL_SPAN_M`, added for 4.2). That is the entire model.
2. ⭐ **THE PLANAR AMBIGUITY IS ALREADY SOLVED HERE.** A near-planar target has a
   well-known two-fold pose ambiguity — a mirror flip about the line of sight.
   IPPE (Collins & Bartoli, IJCV 2014; `cv::SOLVEPNP_IPPE`) is built for planar
   targets and **returns BOTH solutions with their reprojection errors**. ⭐ And
   the disambiguator already exists and is live: **U7's geometric chirality**
   (`palm_geometry.signed_palm_volume`), which is exactly a palm-front/palm-back
   decision. ⚠ This is also the "bas-relief / mirror hypothesis" S11(c) parked as
   research — it arrives here as a solved sub-problem rather than a new one.
3. ⭐ **THE CAMERA MODEL ALREADY EXISTS.** `palm_geometry.focal_px` and its
   documented 60°-FOV assumption shipped with 4.2.
4. ⭐⭐ **AND FOR THE FIRST TIME THE MEASUREMENT RIG IS COMPLETE.** `t5i` scores
   yaw AND pitch (mean-axis, per-frame median, and gain); `t5j` scores roll against
   a depth-free ground truth. **All three axes, on recorded takes, one variable.**
   A replacement estimator can be A/B'd against the shipped Horn on identical
   frames — which is the only reason this is now a buildable item rather than a
   hope.

#### ⚠ THE COSTS, STATED BEFORE ANYONE STARTS

* ⛔ **THE PORT CONTRACT.** `palm_rotation` is stdlib-only and numpy-free BY
  CONTRACT so it can be transliterated to JS/Swift/Kotlin (U3). `cv2.solvePnP`
  would break that. IPPE's core is compact (a homography plus a local analytic
  solve) and is implementable in stdlib — **budget that, or the port debt is real.**
  ⛔ Do not quietly import cv2 into the client estimator layer.
* ⚠ **PnP NEEDS INTRINSICS, AND OURS ARE ASSUMED.** Focal-length error mostly
  corrupts the OUT-OF-PLANE component — i.e. exactly yaw and pitch, the thing
  being fixed. ⭐ **This is the first hard technical reason for queue U12** (the
  start-of-game calibration step), which until now was only about grab reach.
* ⚠ **NOT A RERUN OF 2.3.** The five null attempts there re-weighted the FUSION of
  a bad signal. This replaces the INPUT. Different intervention, and the
  distinction should be stated in any write-up so the history is not misread.
* ⚠ **A10 APPLIES IN FULL**: it must beat Horn on all three axes AND not regress
  jitter in real handling (the trap that killed the 9-point constellation), or it
  is recorded and not shipped.

#### ⭐ SEQUENCING

The owner calls this a show-stopper, so it outranks the "not worth it ahead of
4.4+B5" line in §14.3.4.7 — **that judgement is withdrawn.** ⚠ But note 4.4+B5
does not depend on it and vice versa: rotation fidelity and grab/release are
independent subsystems.

### ✅ 14.3.5 4.2 IS BUILT (2026-08-23) — Z-axis translation, a 3D snap gate, and the play area as a world volume

✅✅ **CONFIRMED LIVE IN BOTH TOOLS, back to back, 2026-08-23** — owner, debug:
***"yes. this is working properly"***; owner, production: ***"this is working
fine"***. ⭐ Production matters separately here because §13.6.1's inversion was
**production-only** while the debug tool looked fine, and `parity_replay` cannot
cover it: it replays recorded landmarks and never exercises production's own
capture, mirror and socket path. Everything below is also golden-vectored (23
suites), parity-clean and measured against the corpus.

**LIVE ACCEPTANCE, BOTH TOOLS, RECORDED SO THE CLAIM IS CHECKABLE:**

| | debug `193716_4_2_zaxis_debug_first_look` | production `194406_4_2_zaxis_production_check` |
|---|---|---|
| owner | *"yes. this is working properly"* | *"this is working fine"* |
| coverage | 2274 object-frames | 771 frames, 963 hand-frames, 1542 object-frames, 46 s |
| Z actually exercised | — | large **0.316–0.850 m** (346 distinct), small 0.346–0.850 |
| snaps under the 3D gate | — | **10**, both hands, 778 held object-frames |
| S10 freeze fired | — | **2.0%** of hand-frames |
| play-area invariant | **0 violations** | **0 violations** |

⭐⭐ **TWO INDEPENDENT CONFIRMATIONS FELL OUT OF THAT TAKE, NEITHER OF THEM ASKED FOR:**

1. **The measured constant reproduced itself live.** The hand depth in this
   session runs p5 0.349 / **median 0.502** / p95 0.707 m — against the corpus
   median of **0.497 m** that `REFERENCE_DEPTH_M = 0.50` was derived from. A
   constant measured over 65 old sessions predicted this new one to 5 mm.
2. **DECISION 1's cost landed where it was predicted.** The freeze fired on 2.0%
   of hand-frames against the corpus-wide ceiling of 1.6% — same order, and
   nothing was reported as un-grabbable.

⚠⚠ **AND THE HARNESS CRIED WOLF ONCE MORE — the fifth time this pattern has
appeared, and again the instrument was the suspect.**
`verify_play_volume_from_recording.py` reported **361 violations** on the take the
owner had just watched work. Worst magnitude: **0.0115 px.** ⭐ The cause is that
the harness compared RECORDED values, which the recorder rounds (`position` and
`projected_size` to 2 dp, `depth_m` to 4), against an UNROUNDED boundary — and
an object pinned exactly on that boundary, which is the correct outcome, rounds a
hundredth of a pixel outside. ⭐ **THE GENERAL RULE, now written into the harness:
compare at the precision the INPUT carries, not at the precision the arithmetic
can produce.** Tighten it by recording more digits, never by asserting below what
was recorded.


**What shipped, in one table:**

| | where | flag / constant |
|---|---|---|
| **Z translation** — a held object's depth follows the hand's grab-referenced span ratio | `HandsTriggeredActions.on_hands_frame` / `LiveSnapDebug.update_hands`, driving `Cube.depth_m` from `palm_depth.DepthRatioTracker` | `Z_TRANSLATION` |
| **3D snap gate** — a hand may only claim an object it is close to on X, Y **and** Z | `_try_snap` in both tools; axial term from the new `palm_depth.HandDepthTracker` | `GRAB_Z_TOLERANCE_M = 0.15` |
| **DECISION 1** — no snapping while depth is frozen | `can_snap` in both tools | `SNAP_REQUIRES_VALID_DEPTH` |
| **DECISION 2** — the play area is a world-space volume, frustum-aware | `palm_geometry.clamp_to_play_volume`, from both tools' `set_target_center` | `PLAY_AREA_MARGIN_M = 0.0425` |
| **projection** — an object's on-screen extent is its real size AT ITS DEPTH | `palm_geometry.projected_size_px`, used by the centre, the clamp, the grab radius and both renderers | `REFERENCE_DEPTH_M` |
| **recorders** — `depth_m` + `projected_size` per object, `hand_depth_m` + `depth_valid` per hand | both recorders | `recorder_schema: 3` |

#### ⭐⭐ The four things §14.3/§14.3.2 left open, and what they resolved to

1. **"The exact mapping from span ratio to a Z position."**
   `cube.depth_m = cube.grab_depth_m / ratio`, clamped to the play volume.
   ⚠ **§14.3 decision 2 ("absolute and continuous, not relative-delta") and
   §14.1's no-pop rule LOOK contradictory here, and the resolution is the ratio's
   own baseline.** `ratio` is `d/d0` with `d0` captured AT THE GRAB, so this is a
   direct, memoryless function of this frame's measurement — nothing integrates,
   nothing drifts, and every re-grab re-normalises. That satisfies decision 2.
   And because the ratio is 1.0 on the grab frame by construction, the object's
   depth is unchanged at that instant — the same no-pop guarantee §14.1 gives
   X/Y, obtained the same way. ⛔ Reading decision 2 as *"snap the object to the
   hand's depth on grab"* would put a Z teleport into the one gesture this
   project has spent the most effort removing.
   Multiplicative rather than additive is **forced, not chosen**: the hand's own
   depth is knowable only up to an unknown scale, so a ratio is the only quantity
   the sensor supplies.

2. **"The same radius extended into 3D, or a separately-tuned Z tolerance?"**
   **An ellipsoid, and the asymmetry is the point.** Lateral stays the projected
   grab radius (X/Y feel unchanged, and it now scales correctly with depth);
   axial gets its own, much looser `GRAB_Z_TOLERANCE_M = 0.15 m`.
   ⛔ **A sphere would have shipped an un-grabbable object.** The axial term
   compares against a depth scaled by NOMINAL anatomy, so a user 20% off the
   median reads ~80 mm away from where they are, *constantly*; the small object's
   spherical tolerance would have been 43 mm. The failure would have looked like
   a broken build, not a mis-sized constant.

3. **"What does the check do when `depthValid` is false?"** — closed by the owner
   as DECISION 1: **refuse**. Measured cost **ceiling 1.6%** of hand-frames
   (`analysis/m9_working_distance.py`), and that is a ceiling, not the cost: it
   counts every edge-on frame, not those where a hand was also within grab radius
   of a free object. `depth_valid` is now recorded per hand so narrowing it is a
   query against a session rather than a new session.

4. **"Does the span metric need recalibration across users?"** — **no calibration
   step, confirmed** (4.1's finding stands): the ratio cancels scale exactly. ⚠
   But 4.2 needed a second, *absolute* estimator the ratio form cannot provide —
   the snap gate asks about a hand that has not grabbed anything, so there is no
   baseline. `palm_depth.HandDepthTracker` substitutes anthropometric medians for
   the missing baseline and **therefore carries a per-user scale bias**. That bias
   is constant, not noise, which is what makes it usable for a tolerance decision
   and useless for anything else. ⛔ It gates snapping and nothing else; feeding
   it into the Z mapping would re-import the error the ratio design deletes.

#### ⚠⚠ THE CONSTANT THAT WAS ABOUT TO BE WRONG, AND HOW IT WAS CAUGHT

An object's resting depth was first set to **0.40 m**, because U9 derived its
60 px margin there and U9's row says *"40 cm IS the closest the operator actually
works"*. ⭐ **That sentence is about the CLOSEST APPROACH — it reads the corpus's
p99 palm width.** The TYPICAL distance is 10 cm further, and the typical distance
is what an object must sit at to be reachable.

Measured with the shipped estimator over **86 109 trusted hand-frames across 65
sessions** (`analysis/m9_working_distance.py`):

| p1 | p5 | p25 | **MEDIAN** | p75 | p95 | p99 |
|---|---|---|---|---|---|---|
| 0.309 | 0.372 | 0.443 | **0.497** | 0.558 | 0.668 | 0.837 |

Against 4.2's own axial gate: an object at 0.40 m is reachable on **70.9%** of
trusted frames; at the measured median, **91.2%**. ⛔ **A quarter of all frames
unable to pick anything up would have read as a broken build.**
`REFERENCE_DEPTH_M = 0.50`. U9's derivation depth survives as
`U9_DERIVATION_DEPTH_M`, used only by the golden vector that asserts the world
margin and the pixel margin still meet there.

⭐ **The reusable form of this: a constant borrowed from another row's derivation
inherits that row's QUESTION, not just its number.** U9 was asking "how big is a
hand near the edge"; 4.2 was asking "where does the hand live". Same corpus,
different statistic.

#### The play volume's walls decide something non-obvious

`PLAY_DEPTH_MIN_M = 0.30`, `PLAY_DEPTH_MAX_M = 0.85` — the measured p1..p99 of
the operator's own working distance. ⚠ **It is the WALLS, not the tolerance, that
bound re-grabbability**: release freezes an object in all three axes, and a
re-grab needs the hand within `GRAB_Z_TOLERANCE_M` of it, so a wall beyond the
operator's reach would let an object be parked where it can never be picked up
again. Cross-checked against the independent reach measurement
(`m9_depth_envelope.py`: ratio 0.53–1.89, i.e. 0.26–0.94 m from a 0.50 m rest) —
both walls sit inside the arm's envelope with margin.

#### ⚠ What "the object gets bigger" is and is not

An object's PROJECTION scales with depth; its real size never changes. That is
what §14.3 decision 4's *"real size stays fixed per-object"* means under a
perspective camera, and it is **not** the dropped depth-proxy scale/colour row —
that one scaled the real object as a depth *readout*. Without the projection,
Z-translation would be literally invisible on screen.

Consequence, and it is load-bearing: **`cube.size` is now the extent at the
resting depth only.** The centre, the clamp, the grab radius and both renderers
read `projected_size_px`. `_top_left_for_center` was DELETED from both tools for
exactly this reason — it converted with the nominal size, and a stale copy is how
an object's centre would silently drift as it moved in Z.

#### Evidence

| claim | harness |
|---|---|
| the world volume, the depth-free fallback, the walls, and the agreement with U9's 60 px | `analysis/verify_play_area.py` (golden vectors) |
| the absolute estimator: 1/Z law, span selection, S10 hold + hysteresis, non-median hand reachable | `analysis/verify_palm_depth.py` §§10–14 |
| the invariant read STRAIGHT from a recording, schema-aware | `analysis/verify_play_volume_from_recording.py` |
| working distance, reachability, DECISION 1's cost ceiling | `analysis/m9_working_distance.py` |
| production and the debug tool still agree frame by frame | `analysis/parity_replay.py` — **no divergence**, 509 frames |
| the two recorders write the same fields | `analysis/verify_recorder_parity.py` |

⚠ The recording-based invariant check reproduces the previously hand-quoted
result exactly (`schema2_production_check`: 1018 cube-frames, 0 outside, closest
approach 0.0 px), which is what says the harness reads real files correctly
rather than merely agreeing with itself.

### 14.3.6 ✅ THE ROTATION LAG — one constant, a dead filter above it, and the retune (2026-08-24)

> **Owner:** *"there is a slerp introduced somewhere during the development of our
> grab and rotate: I don't recall if it was extrapolation and waiting several ms or
> during the work on steal or a gate we have introduced to avoid jitter. I need to
> find where we introduced this slerp during development, because as it is now, the
> cube is lagging the hand and this feels very uncomfortable."*

⭐ **ALL THREE GUESSES WERE WRONG, and they are recorded so they are not re-searched.**
It is not the coast, not extrapolation, not a jitter gate. `git log -S` puts it in
**`b0035a4` (2026-08-01, "building the rotation")** at 0.25, raised to **0.35** in
`b003cfe` the same day — it has been there since rotation first existed.

#### The chain, and where the time actually goes

1. the camera delivers a frame — **64.0 ms** apart in poor light, **48.0 ms** in good;
2. MediaPipe → landmarks;
3. **Horn** fits the palm against the frozen grab reference → `target_quat`.
   **This step has no history and no filter: it is instantaneous.**
4. `cube.orientation = _quat_slerp(cube.orientation, target_quat, 0.35)`.

**Step 4 is the whole of it.** Measured end-to-end at **128 ms** by shift-aligning
the shipped cube against an UNSMOOTHED replay of the same take — not inferred from
the constant, measured against a control.

#### ⛔⛔ TWO INDEPENDENT DEFECTS ON ONE LINE

**(a) THE UNITS.** A fixed per-FRAME factor is a settling time of `1/−ln(1−f)` =
**2.32 FRAMES**, so the feel is whatever the camera is doing:

| frame interval | settling |
|---|---|
| 48.0 ms (good light) | **111 ms** |
| 64.0 ms (poor light) | **149 ms** |

**The same code feels 34% laggier in a darker room.** ⭐⭐ **And the frame rate was
proved CAMERA-bound, not compute-bound, by a test that costs nothing: the inter-frame
gap is IDENTICAL with and without a hand in frame (64.1 vs 64.0 ms).** MediaPipe's
landmark pass and the entire gesture path only run when a hand is present, so if
computation were the limit those two numbers would differ. The exact, quantised
values (64.0 / 48.0) are the signature of a DSHOW webcam stepping its interval under
**auto-exposure**. ⚠ On a phone, where frame rates vary far more, this is first-order.

**(b) THE MAGNITUDE, and the reason is dated.** 0.35 was tuned on 2026-08-01 against
the **Gram-Schmidt** frame — p50 1.59, p95 21.91, **max 144.19°** of single-frame
excursion. Horn shipped 2026-08-17 at p95 11.71, max 25.07 (§16.13). **The smoothing
was never revisited after the signal it smooths improved that much.** Measured, every
arm replaying identical input:

| smoothing | lag | cube step p95 |
|---|---|---|
| per-frame 0.25 | 192 ms | 10.20° |
| **per-frame 0.35 — what shipped** | **128 ms** | **11.29°** |
| τ 149 ms (== the old feel, new unit) | 128 ms | 11.44° |
| τ 80 ms | 64 ms | 12.76° |
| τ 40 ms | 0 ms | 13.93° |
| **τ 20 ms — SHIPPED** | **0 ms** | **14.64°** |
| τ 0 (none at all) | 0 ms | 15.17° |

**All 128 ms of lag bought a 26% jitter reduction.** ⚠ "step p95" includes genuine
hand motion, so it overstates jitter in absolute terms; it is a fair RELATIVE
comparison because every arm replays one take, and it must not be quoted as an
absolute jitter figure.

#### ⭐ THE FIX, AND WHAT IT GUARANTEES

`factor = 1 − exp(−dt / τ)` with **τ = 20 ms**. Settling is then constant in real
time — verified **20.0 ms at 48, 64 and 16.7 ms/frame**, a 4× frame-rate range.

⚠ **`dt` IS CLAMPED AT 200 ms.** After a dropout, a coast or a stalled frame `now_ms`
can jump by hundreds of ms, and an unclamped dt drives the factor to 1.0 — the cube
teleports onto the hand on the first frame back, undoing D3's resync blend, a defect
the owner has already accepted a fix for.

⚠ **STAMP THE CLOCK ONCE PER FRAME, NEVER PER HAND.** Stamping inside the per-hand
loop gives the second hand a dt of zero, a blend factor of zero, and a cube that
never moves.

⭐ **N6 — τ LIVES IN EXACTLY ONE PLACE**, `hand_state.py`, beside `BRIDGE_WINDOW_MS`.
`LiveSnapDebug` cannot import `HandsTriggeredActions` (that module opens a pygame
window at import time), so production could not be the source, and a duplicated
TUNING constant is precisely how the two tools drift.

#### ⭐⭐ THE PREDICTIVE ORIENTATION FILTER WAS DEAD, AND THAT IS MEASURED

§13.7's predictive/reliability-weighted filter still ran every frame, but Horn
**replaced its output whenever it succeeded** — so its value survived only on frames
where Horn FAILED:

    Horn returned None on 0 of 9091 hand-frames, across four recordings.

**It reached the cube on none of them.** Removed from BOTH tools on 2026-08-24 and
archived whole, with its rationale and this measurement, in
`Resources/_archived_predictive_orientation_filter.py`.
⭐ **Consequence worth carrying: the slerp onto the cube is now the ONLY smoothing in
the rotation path**, which is what makes its time constant the entire felt lag.
⚠ `_reliability_alpha` was KEPT — it is a conditioning measure, not part of that
filter, and it still drives the operator-facing `reliability` readout.
⚠ Also removed as orphaned: `_make_continuous` (only the filter used it) and
production's dead private `_edge_on_measure` (a second copy of
`palm_geometry.edge_on_measure`). ⭐ `_is_thumb_outward` and
`configure_source_resolution` LOOKED dead to an AST scan and were **kept** —
`guard_sensitivity.py` inspects the first by name and `PythonApp_Main.py` calls the
second. **An in-file usage scan is not a repo-wide one.**

#### ⚠⚠ TWO GUARDS CAUGHT THE REMOVAL, WHICH IS WHAT THEY EXIST FOR

`verify_d1_wiring` and `verify_dead_track_reset_parity` both asserted on the deleted
state. They were **repointed at state that still exists**, not deleted.
⛔⛔ **AND THE FIRST REPOINT WAS WRONG IN THE MOST DANGEROUS WAY**: `verify_d1_wiring`
was aimed at Horn's frozen reference, and **passed vacuously** — that harness feeds
pixel landmarks only, so no `hands_world` packet arrives, Horn never freezes, and the
assertion was `None is None`. A green check measuring nothing is the exact failure
this repository keeps paying for. It now watches DR-2's `frozen` sign, which the
harness genuinely exercises.

#### ⚠ METHOD NOTE — how the removal itself went wrong, three times

The T6d strip-out was done by cutting text REGIONS, and three launches failed in a
row on pieces the cuts took with them: a CLI flag, a rig builder, and a module global
that `main()` assigned and thereby made function-local. **`import` and `py_compile`
pass on all three.** Static checks for undefined names in `main()` and for module
globals shadowed by assignment were added afterwards and catch all three classes.
⭐ **For a removal this wide, delete by symbol and re-verify by running, not by
region and re-verify by compiling.**

<!-- VERBATIM-END -->
