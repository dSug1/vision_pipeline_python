# Part One — gesture/pattern recognition design & matrix

> **⚠ Gesture set changed again (2026-08-01): read `GESTURE_PIPELINE_SPEC.md`
> §13 first.** After §6-§8's rule-based pinch attempt was abandoned
> (2026-07-30, see the original banner text preserved below) and a
> subsequently *trained* pinch classifier was built, fixed repeatedly, and
> finally live-validated (`GESTURE_PIPELINE_SPEC.md` §12, through §12.7),
> **Stage 4 live testing found pinch still missed too many real
> grabs/releases (worse off `front`) and had a perceptible input lag** —
> a real, live-observed UX problem, not just an offline metric. **Pinch is
> now archived** (code/corpus/weights kept, not deleted — reusable if
> revisited later). **New primary gesture set (§13 of the pipeline spec
> has the full design + state-of-the-art check): proximity-based object
> snapping (replaces pinch-triggered grab), open-palm rotation, closed-fist
> release.** The matrix in §3 below has been updated accordingly — rows
> 2-4 (trigger/grab/release) now describe the new gestures; rows 1, 5, 7
> (scaffolding, translation, rotation) mostly reuse their prior design,
> just with the new trigger signal swapped in; row 6 (depth-proxy
> scale/color) is dropped for now, not carried forward automatically.
> §2's core architecture decisions (sticky grab, shared-registry
> arbitration, image-space translation, depth-proxy-not-raw-`z`,
> quaternion rotation) are **unchanged and still apply** — only the
> *trigger* gestures changed, not the manipulation architecture around
> them.
>
> **Update (2026-08-01, later conversation): open-palm/closed-fist
> detection (row 2) is now PARKED**, not being pursued for the moment —
> so "open-palm rotation, closed-fist release" above is historical intent,
> not the current plan. Rotation is permanently ungated; release now
> relies on tracking-loss plus a new hand-open-quick-release gesture
> (§3 row 4, `GESTURE_PIPELINE_SPEC.md` §14.2) instead of `Closed_Fist`.
>
> **Original 2026-07-30 banner, preserved for context**: §6–§8 below
> document a **rule-based (hand-tuned threshold) pinch classifier that was
> built, tested, and then abandoned** — it worked for the hand orientation
> it was calibrated on, but a state-of-the-art literature check plus
> reproducible live/recorded evidence showed it could not be fixed without
> either endless heuristic patching (rejected — not backed by literature,
> doesn't generalize) or a fundamentally different approach. That
> different approach — labeled recording, a *trained* classifier instead
> of hand-picked thresholds, and a live debug tool, run identically for
> every future gesture — is specified in `GESTURE_PIPELINE_SPEC.md`
> (still the active methodology spec for any gesture that ends up needing
> custom training). Every file the rule-based attempt produced
> (`GestureRules.py`, `AnalyzeRecordings.py`,
> `ValidateWindowedClassifier.py`, `LiveGestureDebug.py`,
> `debug_gestures.bat`) and every old recording have been deleted — §6–§8
> are kept below **only** as the evidence trail for why, not as a
> description of current code.

Implements §7 of `Specification.md`: Pipeline A gesture recognition, developed
on PC against the existing Python MediaPipe pipeline. This file is the living
design reference for Part One's gesture vocabulary — **the matrix in §3 below
is meant to be enriched** as new gestures/objects are added; keep it in sync
with the classifier code as it's built (see `GESTURE_PIPELINE_SPEC.md` for how).

## 1. Scope decided so far

**Concrete first build**: two hands, two cubes (existing blue cube + a new
red cube), pinch-to-grab manipulation. This is a live, visually-tuned PC
prototype — not the offline-JSON-only R&D originally sketched in
Specification.md §2/§7 — because grab thresholds, rotation feel, and the
depth-proxy mapping all need to be tuned by eye against a live webcam feed,
the same way Part Zero-bis's coordinate mapping needed live verification
(see `PART_ZERO_BIS.md`). It's built as a direct extension of Part Zero's
`CubeWindow.py`, **in place, in the same `Hand_detection/Local_pc/` folder**
— not a new sibling folder and not a separate offline module. This matches
how Part Zero itself was built (modifying the pre-existing cursor-control
pipeline in place, with `PART_ZERO.md` documenting the delta rather than a
frozen copy being kept). `Part_Zero_local_pc/` and `Part_Zero_Bis_Web/` were
renamed to `Local_pc/` and `Web/` accordingly once Part One started —
history is in git, not in a parallel folder. See Specification.md §7.5 for
the pointer back to this file.

**Sequencing vs. the browser port**: built PC-only, first, in full — no
parallel JS implementation. See Specification.md §2 for why (avoids
maintaining tuned thresholds in two languages at once); portability is kept
cheap via pure-function `features.py`/`rules.py` and an engine-agnostic
`gesture_config.json` (§7.4), not by building both sides simultaneously.

**Gesture classification is data-driven and camera-pose-invariant, not
eyeballed.** Revised after step 1: rather than hand-picking a pixel-distance
threshold and tuning it live by eye, gestures are classified from
`world_landmarks` (metric, hand-relative 3D — not image-space pixels or
normalized `[0,1]` coordinates), built from **recorded, labeled sessions**
via the pipeline in `GESTURE_PIPELINE_SPEC.md` (labeled recording →
literature benchmark → **trained classifier** → live debug tool — not
hand-picked thresholds; §6–§8 below tried the hand-picked-threshold version
first and document why it didn't hold up). Two reasons this still holds
regardless of classifier method: (1) a flat pixel threshold breaks the
moment camera resolution or hand-to-camera distance changes, and doesn't
survive the planned future move to a glasses-mounted, outward-facing camera
(§12 of `Specification.md`) — only hand-relative 3D geometry does; (2)
empirical calibration against real recorded data beats a guessed constant,
regardless of whether that calibration is a hand-picked threshold or a
trained model's weights. This does **not** apply to cube *translation*
(positioning the cube on screen) — that stays image-space/pixel-based,
since placing something on screen inherently needs a frame-relative
signal; only gesture *classification* moved to `world_landmarks`.

## 2. Core architecture decisions

- **Two hands, independent pose classification.** Each hand's pinch state,
  translation, rotation, and depth proxy are computed purely from that
  hand's own landmarks — no gesture in the current matrix needs both hands'
  data fused together.
- **One cross-hand exception: grab arbitration.** Either hand can grab either
  cube (no fixed left→blue/right→red pairing), so a cube can only ever be
  held by one hand at a time. This needs a small shared registry both hands'
  grab logic can see: `{cube: holding_hand | None}`. Rule: on a pinch
  rising-edge, look at all **unowned** cubes within grab radius of the pinch
  point, claim the nearest one; skip cubes already owned by the other hand.
  This is the one piece of "combined" cross-hand logic the architecture
  needs — everything else stays per-hand.
- **Sticky grab.** Once acquired, a cube stays grabbed regardless of how far
  the pinch point drifts from it — only releasing un-pinches it (or losing
  hand tracking, see below). The initial proximity check only gates
  *acquisition*, not continued holding.
- **Release conditions**: un-pinch (thumb-index distance exceeds a release
  threshold, with hysteresis vs. the grab threshold to avoid boundary
  jitter), **or** loss of hand tracking — ⭐ **the latter now only after a
  150 ms coast, and with a 3-frame resync blend on reacquisition** (queue
  D1/D2/D3, shipped 2026-08-21; `GAME_RULES.md` rule 2 is the behavioural
  statement of record). Either way: cube freezes in place at
  its last known position, ownership is cleared, state → idle. Re-acquiring
  always requires a fresh pinch rising-edge near the cube — tracking
  resuming mid-pinch does **not** auto-regrab.
- **Release is decomposed from pinch as its own onset/apex/offset concern,
  not assumed symmetric with it** — confirmed against literature
  (`GESTURE_PIPELINE_SPEC.md` §3.3.1, added 2026-07-30): production XR SDKs
  (Ultraleap, Meta Quest) detect pinch and release as two events read off
  one continuous confidence signal via hysteresis, which is what the
  release-conditions bullet above already did — but prehension-kinematics
  literature shows release/opening genuinely behaves differently from
  pinch/closing (measurably different movement timing, not just a
  time-reversed mirror), so the event layer tunes onset and offset detection
  as two independent parameter sets. And since grabbing an object is
  usually done near `front` but releasing it can happen at any orientation
  if the point of the grab was to rotate the object, release detection is
  recorded and validated across the full 6-orientation grid, not just the
  orientation pinch itself is normally performed at. See
  `GESTURE_PIPELINE_SPEC.md` §5 for the resulting recording taxonomy.
- **Rotation — quaternion-based, gimbal-lock-safe.** Track hand orientation
  as a quaternion built from an orthonormal frame (Gram-Schmidt on
  `wrist→index_MCP` and `wrist→pinky_MCP` from `world_landmarks`), and slerp
  the cube's quaternion toward it each frame. **Never decompose into
  separate roll/pitch/yaw Euler angles at any point** — gimbal lock is a
  property of that decomposition, not of the underlying rotation itself.
  Smooth the whole quaternion uniformly (single slerp factor); don't smooth
  per-axis, since that would silently reintroduce the same problem through
  the back door.
  - Rotation about the axis **orthogonal to the camera plane** (the
    depth/Z axis — twisting the wrist while facing the camera) is easy to
    detect: it shows up as a clean 2D rotation in the landmarks' `x,y`
    image-space positions.
  - Rotation about axes **in the camera plane** (tilting the hand toward/
    away from the camera — pitch/yaw) is harder: it shows up mostly as
    changes in `world_landmarks`' `z` component and foreshortened landmark
    spacing, and MediaPipe's `z` is the least reliable of the three
    coordinates monocularly. Expect this to be noisier; verify empirically
    once built (same discipline as `PART_ZERO_BIS.md`'s `NOTES.md`) rather
    than assuming a fix in advance.
- **Depth proxy — apparent hand size, not raw MediaPipe `z`.** Use the
  hand's apparent span in normalized/pixel image coordinates (e.g.
  wrist↔middle-MCP distance) relative to a calibration baseline captured at
  grab time: `ratio = current_span / baseline_span`. Drives cube **scale**
  and **color gradient** only (bigger + darker = closer, smaller + lighter =
  farther) — **no Z-axis translation** for now (explicitly deferred).
  Active only while grabbed, bundled with translate/rotate as an effect of
  the grabbed state (not a hover preview).

## 3. Gesture / signal matrix

Build order = difficulty order (easiest first); each step mostly reuses the
previous step's code. **Enrich this table when adding new gestures/objects**
— add a row, keep the Order column meaningful (insert at the difficulty tier
it actually belongs to), and cross-check §7.4's engine-agnostic
`gesture_config.json` rule whenever a new row is added.

| Order | Signal / Gesture | Hand(s) | Input | Detection logic | Effect | Status |
|---|---|---|---|---|---|---|
| 1 | Scaffolding | both, independent | full 21-landmark list per hand | n/a — plumbing only | red cube added to scene; both hands' landmarks flow through (not just left); no ownership/grab logic yet | **Built and live-verified** — code in `Local_pc/Movement_with_hand_detection/`; confirmed via `debug_snap.bat`'s combined video+landmarks+cube view (2026-08-01) |
| 2 | Open-palm / closed-fist detection | each hand independently | `world_landmarks` (or a geometric heuristic on landmarks — see status) | MediaPipe's built-in `Open_Palm`/`Closed_Fist` classes **tried and reverted** (live-tested unreliable across hand positions — `GESTURE_PIPELINE_SPEC.md` §13.5); next candidate a geometric heuristic on finger-curl angles, else a **trained classifier** per `GESTURE_PIPELINE_SPEC.md`'s pipeline | Previously: `Open_Palm` gates rotation (row 7); `Closed_Fist` triggers release (row 4) — **neither dependency still applies, see status** | **PARKED — not intended to be used for the moment (2026-08-01, direct request).** Was blocked on finding a working detection approach; now deprioritized rather than actively pursued. Both rows that once depended on it have moved on without it: rotation (row 7) stays permanently ungated by design, not just pending this row; release (row 4) now uses the hand-open-quick gesture (§14.2) instead of `Closed_Fist`. `gesture_recognizer.task` still kept on disk for a possible future `Thumb_Up` use, unrelated to this row. Revisit only if explicitly requested again |
| 3 | Snap acquisition + arbitration | each hand vs. shared registry | hand position (palm-center, §13.3) vs. cube positions | pure proximity trigger — nearest **unowned** cube within grab radius of hand position → claim in shared registry, blocked by the thumb-outward rule (§13.6) | idle/hover → snapped | **Proximity trigger + thumb-outward restriction built and live-verified (2026-08-01)** — `Resources/HandsTriggeredActions.py`; the closed-fist-blocks-snap refinement (§13.4) is now **PARKED along with row 2** (was "pending row 2," row 2 itself is now parked, not just blocked). A same-frame release/re-snap ordering bug (cube instantly "jumping" to the other hand when one hand lost tracking near it) was found live and fixed — release now always resolves before that frame's snap pass, see the module's `on_hands_frame` docstring. Full rules list: `Claude/GAME_RULES.md` |
| 4 | Release (un-snap) | each hand | quick full hand-open (§14.2 — geometric signal, no row 2 dependency), or tracking loss | rapid full finger-extension while the wrist stays stable, on a hand holding a snapped cube (§14.2, **not yet built**) **or** hand tracking lost (built) | snapped → idle; cube frozen in place; ownership cleared; requires fresh proximity-snap to reacquire | **Tracking-loss release built and live-verified (2026-08-01).** Closed-fist-triggered release is now **PARKED** (it depended on row 2, which is parked — see above). Hand-open-quick-release (§14.2) is now the **sole active plan** for a deliberate release trigger — not yet built, queued **second** in build order (§14.1 pivot fix → §14.2 release trigger → §14.3 Z-translation) |
| 5 | Translation | each hand, while snapped | at grab: object position vs. ~9 phalange-adjacent landmarks (5 fingertips + 4 non-thumb MCPs); each frame after: those SAME landmarks' current 2D positions | distance-weighted combination — weights = normalized inverse-distance from the object at grab, FROZEN thereafter; `object_position(t) = Σ(frozen_weight_i × landmark_i_position(t)) + grab_residual_offset` (residual added once for exact no-pop continuity) | cube follows a live-tracked, grab-time-weighted point instead of one fixed anchor | **REDESIGNED, IMPLEMENTED IN `LiveSnapDebug.py`, REPLAY-VERIFIED (2026-08-01, later conversation)** — no longer today's zero-offset mechanism. Recorder + analysis tooling built, 7 real hold intervals tested — no-pop exact (0.0000px), jitter comparable to today, translation now measurably scales with real rotation (~2x under high vs. low rotation). Implemented, then **verified by replaying a real recording's landmarks through the actual modified `update_hands`**: grab frame stayed at the cube's own resting position (zero pop) vs. the old recorded data's ~76px pop at the same frame. **Known, deliberately deferred limitation**: the computed point swings toward the palm under YAW specifically (confirmed empirically, correlation −0.25 across intervals) — pitch/roll are fine. Root cause: purely-2D weighting can't distinguish yaw-driven foreshortening from real repositioning; likely shares root cause with row 9's Z-axis-at-grab problem. Decision: implement as-is, revisit yaw together with a proposed future startup Z-axis calibration step. **CONFIRMED WORKING LIVE (2026-08-01)** — user tested against a real camera via `debug_snap.bat`: "it's working." **Ported to production** (`HandsTriggeredActions.py`/`CubeWindow.py`, same day) — verified via line-by-line parity review against the live-verified debug-tool version (can't safely replay-test production directly, it opens a real pygame window on import). **"Object Jump Correction" — ROOT-CAUSED, NOT YET FIXED (TODO for a future improvements round)**: the earlier "spurious jump" report recurred, was made reproducible via a record-and-confirm-per-take workflow, and root-caused from real data — a whole-hand landmark-cluster teleport (MediaPipe briefly mixing up which physical hand is "Right" for a few frames, high confidence throughout, self-corrects a few frames later), NOT frame-edge extrapolation or per-landmark noise. A first fix attempt (exclude out-of-bounds candidates) was built and verified AGAINST REAL DATA to NOT help, and was discarded rather than shipped. A real fix needs a filter design comparable in complexity to rotation's own (which took two iterations to get right) — deferred, not attempted blind. Full account + reusable recorded data: `GESTURE_PIPELINE_SPEC.md` §14.1.4. First in the confirmed build order, translation itself is DONE |
| 6 | Depth proxy → scale + color | each hand, while snapped | apparent hand span (image coords) vs. calibration baseline | `ratio = current_span / baseline_span` | cube scale ∝ ratio; color lerps light↔dark by ratio | **Dropped for now (2026-08-01)** — not part of the new gesture set as directed; not carried forward automatically, revisit only if explicitly wanted again. **Note (2026-08-01, later conversation): row 9 (Z-axis translation) reuses this row's hand-span-ratio metric** — the signal is shared, the scale/color effect itself is not; this row stays dropped as its own feature |
| 7 | Rotation (quaternion) | each hand, while snapped, **UNGATED** (confirmed 2026-08-01 — not gated on `Open_Palm`; now permanent, since row 2 is parked, not just temporarily absent) | `world_landmarks`: wrist(0), index_MCP(5), middle_MCP(9), pinky_MCP(17) | orthonormal frame → quaternion → predictive/reliability-weighted filter → relative delta-from-grab → slerp | cube orientation follows hand orientation | **Ported to production and CONFIRMED WORKING LIVE (2026-08-01)** — wire protocol extended (`hands_world` packet, §4's gap closed), `HandsTriggeredActions.py`/`CubeWindow.py` match the debug-tool-verified design, tested end-to-end against a real camera. Rendering upgraded same day to real mesh-generic 3D objects (row 8 below) once rotation was confirmed. Known open TODOs: rotation quality still poor with the back of the hand facing the camera (reduced, not eliminated, `GESTURE_PIPELINE_SPEC.md` §13.7). **Filter audit (2026-08-01, later conversation)**: the predictive/reliability-weighted filter was reviewed for removal (direct request to strip filters that don't earn their keep) and KEPT — its improvement is measured and substantial (eliminates all >30°/>60° jumps in tested data), not marginal. New TODO: re-test whether it's redundant once future improvements (Object Jump Correction, Z-axis/depth calibration) land — `GESTURE_PIPELINE_SPEC.md` §13.7.1. **object translation coupling during pure hand rotation — reframed (2026-08-01, later conversation): row 5's zero-offset translation logic was the actual defect, not this row.** Corrected model does NOT reuse this row's rotation math — it's a separate, purely 2D distance-weighted live-landmark mechanism (row 5's own status cell has detail): `GESTURE_PIPELINE_SPEC.md` §14.1 |
| 8 | 3D object rendering | n/a (visual only) | orientation quaternion (row 7) | mesh-generic: rotate vertices → perspective-project (fixed camera distance) → backface-cull → depth-sort → draw each face's own color | replaces the flat-square placeholder with a real rotating 3D shape; cube is a placeholder for a future imported object | **Built and confirmed working live (2026-08-01)** — `CubeWindow.py`'s `_draw_object_3d` (mirrored in `LiveSnapDebug.py`), fully generic over any `Mesh`/`MeshFace` (verified by swapping in a non-cube mesh at runtime with zero code changes). A live-found morphing bug (unsafe per-vertex scale formula) was found and fixed the same day. Two placeholder objects: **large** (yellow/violet/turquoise, 2x size) and **small** (green/red/blue) — grab radius now scales per-object size. Full account: `GESTURE_PIPELINE_SPEC.md` §13.7-§13.8. Real 3D-file import (OBJ/glTF) not yet built — scoped remaining gap noted in §13.8 |
| 9 | Z-axis (camera-view-axis) translation | each hand, while snapped | apparent hand span (image coords, wrist↔middle-MCP) vs. calibration baseline — same metric as the dropped row 6, **not** raw `world_landmarks` `z` | `ratio = current_span / baseline_span`, mapped absolutely/continuously (like row 5, not a grab-time delta like row 7); snap itself becomes a 3D proximity check (hand must be close on X, Y, **and** Z-derived depth to a cube, not just X/Y) | cube's Z position follows hand depth; grab radius/arbitration (row 3) extended to 3D | **Proposed and design-confirmed 2026-08-01 (new conversation), NOT YET BUILT.** Queued **third** in build order — after the §14.1 pivot fix and §14.2 release trigger below. Order reconfirmed unchanged (2026-08-01, later conversation) when row 2 was parked and rows 4/6 updated. **Related finding (2026-08-01, same later conversation): row 5's yaw/palm-sinking bug likely shares this row's root cause** (depth ambiguity a purely-2D or purely-hand-span signal can't resolve) — proposed direction, not yet designed: a startup Z-axis calibration step, to address both together when this row is picked up. Full design + open unknowns: `GESTURE_PIPELINE_SPEC.md` §14.3 |

**Rows 2-4 replaced (2026-08-01)**: pinch's onset/offset event pair (the
original rows 2/4, decomposed per the 2026-07-30 note below) is replaced
by a proximity trigger (snap) and a `Closed_Fist` trigger (release) —
full rationale and state-of-the-art check in `GESTURE_PIPELINE_SPEC.md`
§13. The original pinch/release decomposition note is preserved below for
historical context, since the same "onset and offset are independently-
tuned, not assumed symmetric" discipline likely still applies to whichever
release mechanism ends up needing an event layer.

**Row 2 parked, row 4's release trigger changed (2026-08-01, later
conversation)**: open-palm/closed-fist detection (row 2) is parked, not
being pursued for the moment — so the `Closed_Fist`-triggered release
described in the paragraph above is no longer the active plan. Release
now relies on tracking-loss (built) and the hand-open-quick-release
gesture (§14.2, not yet built) as its sole deliberate trigger. See row 2
and row 4's own status cells above for detail.

**Original row 2 (pinch/onset) and row 4 (release/offset) note
(2026-07-30, historical)**: these were the same episodic gesture's two
event boundaries, not independent gestures — decomposed and cross-checked
against literature in `GESTURE_PIPELINE_SPEC.md` §3.3.1, which also drove
the 6-orientation recording grid in that document's §5 (`front`/
`palm_away`/`palm_up`/`palm_down`/`palm_in`/`palm_out`) replacing the
earlier 3-orientation version. See §2's release-conditions bullet above
for the design consequence (still applies to the new release trigger).

## 3.1 Merged build queue — THE single TODO list (2026-08-02)

**This is the only build queue. It supersedes every other ordered TODO
list in the project**, including `PERCEPTION_LAYER_SPEC.md` §5's
module→TODO mapping and the three-item queue previously carried in
`HANDOFF_SNAP_ROTATE_RELEASE.md` §3. Those now point here. Do not
maintain a second list anywhere.

Created when `PERCEPTION_LAYER_SPEC.md` was integrated into the pipeline
(2026-08-02, direct request: *"the list of TODO can be merged into one for
the pipeline"*). It merges (a) the perception-layer modules M0–M10 and
(b) the pipeline's own pre-existing TODOs, which were previously tracked
separately and in some cases duplicated each other without knowing it.

**Owner decisions on integration (2026-08-02)**: build the perception
layer in **Python** under `Local_pc/` (the spec's `gestureConfig.js`
target does not exist — see the spec's §0.1/A1), keeping the spec
language-neutral for the later web/mobile port; run **Phases 0–2, then
reassess** before committing to Phase 3+; **do not** replace §14.1's
shipped translation mechanism with the spec's M8a until an A/B measures
them (A7).

**Governing rule (spec A10, binding):** every module must show a measured
improvement on the M0 metrics via replay A/B on identical recorded input,
or be **reverted**. A null result is recorded, not shipped hopefully.

**Where the evidence lives (added 2026-08-03):** every non-obvious number in this
queue's status cells was produced by a script in
**`Local_pc/Movement_with_hand_detection/analysis/`** — see that folder's
`README.md`, which maps each claim to its script. Run them from the parent
directory (`.venv/Scripts/python.exe analysis/<name>.py`). This matters because
several statuses below are *negative* results used to kill or re-point items
(2.3 deprioritised, T1/T2 re-pointed, 1.4 declared unreachable): **a negative
result that cannot be re-run is an assertion, not a finding.** The README also
lists the four measurement bugs caught mid-session — start any audit there.

**⚠ THOSE NEGATIVE RESULTS WERE THEMSELVES AUDITED (2026-08-03) — read
`PERCEPTION_LAYER_SPEC.md` §0.15 before acting on any status cell below.**
Outcome in one line: **the five 2.3 nulls and the M2 premise-kill are GENUINE
and re-confirmed on corrected streams; two claims were artifacts** — the jump
tail was inflated ~25% by identity contamination (82% → ~77% at high
observability, conclusion unchanged), and **"the motion model is weak" is
RETRACTED** (it was a closed-loop cascade statistic; the real one-frame error is
a 4.2–4.5° median), which **unblocks item 3.1**. New harnesses:
`analysis/audit_jump_provenance.py`, `analysis/audit_m2_proportions.py`.
**Binding for all future harnesses: build streams via `build_v2()` (DR-1 replay
+ duplicate-label + frame-continuity guards); never key a stream on the raw
MediaPipe label again.** A state-of-the-art literature audit ran at the same
time; **its adopted items S1–S12 are now folded into the rows below** (rationale
and sources stay in the spec's §10 addendum). **This table remains the only list
to follow — no S-item lives outside it.**

---

### ⭐ YOU ARE HERE (2026-08-04, end of day) — PHASE 1 IS CLOSED. All of 1.5/1.6/1.7 parked.

**Read `PERCEPTION_LAYER_SPEC.md` §0.18 before doing anything in Phase 1.**

Three items were built, measured and parked the same day. They are **one finding,
measured three ways**: the orientation frame is `wrist / index-MCP / middle-MCP /
pinky-MCP`, and when MediaPipe's palm reconstruction collapses (Google #5156,
back of hand) all four are wrong *together*. So filtering can't fix it (§0.13.2),
re-weighting can't (A5), constraining bone lengths can't (the frame doesn't use
them), and gating can't without destroying legitimate fast input (§0.17).

**T1 and T2 are reclassified from open bugs to a known single-camera sensor
limit.** Do not open a fifth attempt without a second camera.

⚠ **Binding rule added, and it cost the most to learn**: 1.6 initially PASSED its
A/B and had to be reversed — the metric counted removing the owner's *real fast
movements* as success. **Any module that rejects or suppresses data must CLASSIFY
what it removed, not merely count it.**

✅ **What survives**: `hand_skeleton.palm_width_world()` is the per-session scale
reference M9 needs (dead item 1.4 was supposed to supply it). It needs no
skeleton fit. **This unblocks 4.1 → 4.2 (Z-axis translation).**

**⭐ DIRECTION SET 2026-08-04 (owner): the BLOCK REPRESENTATION, Phase B below.**
The hand is 6 blocks for grab/rotate/translate — palm transform + 5 finger arcs
— and the corpus already measured both halves (palm rigid to 2.76 mm; PIP↔DIP
co-flexion 0.0% negative over 29k frames, so a finger is ONE DOF). Design:
`GESTURE_PIPELINE_SPEC.md` **§16**. This supersedes "what's next" below.

| order | item | why |
|---|---|---|
| **1** | **B1** `hand_blocks.py` derived view | costs nothing if it loses — a pure function over existing landmarks, no pipeline change |
| **2** | **B2** measure palm-transform predictability | position prediction error has NEVER been measured; this decides whether B3 is worth building, as the 1.5→1.6 gate did |
| **3** | **B3** palm predictor → **B4** the 3.3 three-arm A/B → **B5** grab from arcs | |
| — | 4.1/4.2 Z-axis | owner: later, not now. ⚠ read §14.3.1 first (multi-anchor; a yaw take must be recorded) |
| — | 4.3 M10.7 grace | **DEFERRED by owner** — no new layers of rules for now |
| — | U2 3D import | **POSTPONED by owner** — blocked on the platform choice, not on effort |

⚠ **3.4 ("brain-mimicking" endpoint/intent prediction, S12) is NOT available
yet** — it is blocked on 4.3 (M10) and on the §14.2 aperture gesture. The
*unblocked* prediction item is **3.1** (M7 render-latency prediction), which still
depends on **0.3** (end-to-end latency measurement, needs a 240 fps phone).

---

### Superseded: YOU ARE HERE (2026-08-04) — 1.5 is BUILT; next is 1.6

**Item 1.5 (M3a anatomical constraints) is built and measured** —
`Resources/hand_anatomy.py`, with `analysis/m3a_violations.py` and
`analysis/m3a_diagnose.py`. **0.00% false positives on 1446 control hand-frames**;
fires on 5–59% of frames in the poses MediaPipe is documented to fail.
Full account: spec **§0.16**. It is **not yet consumed by anything** — A10's
ship-or-revert test bites when **1.6** gates on it, so 1.6 is next.

**Item 0.5 (offline oracle) is DROPPED, not deferred** — two independent
blockers, one of them permanent. See its row below and the two new items N13/N14.

**Do not re-derive the constraint thresholds from the corpus.** They are clinical
goniometry norms on purpose (spec §0.16); fitting them to MediaPipe's own output
is precisely the circularity 0.5 existed to remove and no longer can.

| order | item | why it is next |
|---|---|---|
| **1** | **1.7** impose a skeleton via constrained IK (+S7) | **replaces dead 1.4**; supplies the pose-consistent skeleton and M9's scale reference. ⚠ **NOT with real MANO** — see N13 |
| **2** | **T1 / T2 retest** | the first honest re-test after attacking landmark quality at source |
| **3** | **R** reassess (owner decision point) | then Phase 3 (3.1 M7, now unblocked) or Phase 4 features |

**⚠ One owner decision is now outstanding, raised by 1.6's result (spec §0.17):
item 1.5 has no demonstrated consumer.** It was built to feed 1.6's gate; 1.6
measured that it should not be wired in, because M3a covers the *orientation*
failure class and M4 the *position* class and the two do not compose. 1.5 is not
disproven — its orientation signal is strong (92% coverage, 33.8× lift) — but
under A10 unconsumed code is a revert candidate. **Decide whether to keep it
pending an orientation-side consumer, or revert it.** Do not let it drift.

---

### Superseded: YOU ARE HERE (2026-08-03) — the M6 hand-off

**If you were working on M6 (item 2.3): STOP there — it is deprioritised, and
the audit CONFIRMED that verdict on corrected data.** Five attempts, all null;
the shipped `HandOrientationFilter` beat every one of them again on
identity-corrected streams. M6 cannot reach ~77% of the large orientation jumps
because those occur in *well-observed* frames — they are bad landmarks, not bad
pose filtering.

**Follow this order from here. Everything is in the table below.**

| order | item | why it is next |
|---|---|---|
| **1** | **1.5** M3a anatomical constraints (+S6) | the strongest published lever on the T1/T2 depth errors — measured as *halving* depth error; no longer blocked (1.4 is dead) |
| **2** | **1.6** M4 consistency gate (+S5) | rescoped: gates on consistency cues, not M2's dead residual. Anti-cascade rules are binding |
| **3** | **1.7** impose a skeleton via constrained IK (+S7) | **replaces dead 1.4**; supplies the pose-consistent skeleton, clean joint angles and M9's scale reference |
| **4** | **T1 / T2 retest** | the first honest re-test of back-of-hand + pitch crossing after attacking landmark quality at source |
| **5** | **R** reassess (owner decision point) | then Phase 3 (3.1 M7, now unblocked) or Phase 4 features |

Optional and parallelisable at any time: **0.4** (predictor eval harness, S1) and
**0.5** (offline oracle, S8). Neither blocks anything.

---

### S1–S12 index — where each literature item was placed

| S | item | queue row |
|---|---|---|
| S1 | predictor evaluation harness: side-effect metrics + mandatory baselines | **0.4** (new) |
| S2 | M7 prediction with amended parameters (1-frame horizon, filtered derivative, speed gate, damping, post-filter, DES) | **3.1** |
| S3 | predicted-for-rendering vs unpredicted-for-gestures split | **3.1** |
| S4 | One Euro on the FORM channel, Google's own tunings | **3.1** |
| S5 | consistency-gated frame rejection (M4's revised core) | **1.6** |
| S6 | anatomical validity from published constraint sets | **1.5** |
| S7 | impose a skeleton (constrained IK / MANO-lite) instead of measuring one | **1.7** (new) |
| S8 | offline oracle (HaMeR/WiLoR) over the recorded corpus | **0.5** (new) |
| S9 | causal SmoothNet-class temporal refinement | **5.4** (new) |
| S10 | freeze the depth ratio inside the DR-2 edge-on band | **4.1** |
| S11 | multi-hypothesis / uncertainty-aware prediction (Waymo transfer) | **5.5** (new) |
| S12 | minimum-jerk endpoint / intent prediction | **3.4** |

| # | Item | Kind | Status | Depends on | Notes |
|---|---|---|---|---|---|
| **PHASE 0 — instrumentation** ||||||
| 0.2 | M0 baseline metrics on current pipeline | perception | **DONE 2026-08-02** | — | `AnalyzePerceptionBaseline.py`, 7 existing recordings, no new capture. **Bone CV 10.0% vs <3% target; palm rigidity 2.76 mm already at target; DR-2 validated (41.5× flip concentration, 0 flips above edge-on 0.60).** Results: `PERCEPTION_LAYER_SPEC.md` §0.2 |
| 0.1 | M0 recorder/replay/metrics harness | perception | **partly done — frame capture + stop-reason landed 2026-08-04** | — | Generalise `RecordTranslationPivotDebug.py` / `AnalyzeTranslationPivot.py` / `AnalyzePerceptionBaseline.py`; add `tCapture`, optional frame capture. ✅ **`--save-frames` BUILT 2026-08-04** (`RecordPerceptionSequence.py`): saves the **MIRRORED, PRE-OVERLAY** frame MediaPipe actually ran on — feeding an oracle an un-flipped frame inverts chirality and voids the comparison — buffered in RAM and encoded **after** the take, because encoding inside the loop costs ms against a ~41 ms budget and a sub-20-fps take is non-comparable to the corpus (N10). Landmarks are written to disk BEFORE the frames, so a frame-write failure can never cost an operator's take. **⚠ Compile-checked but NOT yet exercised on a live take.** ✅ **`stop_reason` + `completed_full_duration` BUILT 2026-08-04**, after two takes in a row ended early (21.5 s then 3.2 s of a requested 30 s) with no way to tell a closed preview window from a camera read failure; an early take otherwise looks perfectly valid in analysis, just shorter |
| 0.2b | Record the §7.2 scripted sequences | perception | **7 takes DONE 2026-08-02 (§7.2 is 10 rows, not 9)** | — | `RecordPerceptionSequence.py` (raw capture, no gesture logic) + `AnalyzePerceptionSequences.py`. **Done (verified on disk 2026-08-02):** static_hold, non_crossing, pitch_sweep_slow, pitch_sweep_fast, two_hand_crossing, two_hand_overlap, two_hand_near_miss. **Results corrected §0.2 — see §0.3.** *(This line previously read "4 of 9" — stale: it was not updated when §0.4's three two-hand takes were recorded, and the count also disagreed with §7.2's actual 10 rows.)* **`palm_back` recorded then DELETED 2026-08-02** — both takes (the counted one and an aborted one) discarded on owner instruction because they ran at 15–16 fps in poor light: *"I don't want the lack of light to pollute our analysis."* Their numeric result is **indicative only, data gone** (§0.7). **REPLACED by four speed-decoupled takes** — `palm_back_s1_very_slow` / `s2_slow` / `s3_medium` / `s4_fast`, built into the recorder with **prescribed** cycle counts (10/15/20/30 → 20/30/40/60 expected sign changes), **PITCH axis** stated explicitly, and a `<20 fps` warning at save time (§0.7.1). **SUBSTANTIALLY DONE 2026-08-03 (daylight) — 14 new sessions.** (a) four `palm_back_s*` speed takes + four `known_*` fixture clips, all 24–25 fps, 100% detection → §0.8 (N3 closed) and §0.9 (item 1.1 done); (b) two **single-hand** `palm_back_s2_slow` takes (right + left, 16 cycles each) for N11 isolation and clean single-hand pitch data — **analysis not yet run**; (c) **`occlusion` split into three explicit one-handed takes** (`_exit_reenter`, `_behind_object`, `_finger_over_finger`) after the original single prompt proved unactionable — it bundled three different mechanisms and never said how many hands. They separate cleanly at **63% / 61% / 100%** detection = total loss / occluded-but-present / never-lost; (d) `depth_sweep` (727 frames) for M9; (e) `free_manipulation` regression net, 3 × 1-min unscripted chunks. **Remaining: fiducial grabs (needs 5 physical markers, serves Phase 3 item 3.3) and direction reversals (= item 0.3, needs a 240 fps phone for the actual latency figure). Neither blocks Phase 1–2.** ⚠ The `free_manipulation` chunks ran at **19.3–20.7 fps** as daylight faded and are KEPT deliberately (a regression net benefits from a wider frame interval) but are **not valid for cross-corpus metric A/B** — caveat recorded in each `meta.json`. Note `non_crossing` is an extra take serving M0's chirality-flip metric, not a §7.2 row |
| 0.3 | §6.2 end-to-end latency measurement | perception | queued | — | Manual, needs a 240 fps phone; instrument socket IPC separately (extra stage vs. the spec's table) |
| 0.4 | **NEW — S1: predictor evaluation harness (side-effect metrics + mandatory baselines)** | perception | **NEW 2026-08-03, optional, parallelisable** | — | **Spec §10.4/S1.** Prerequisite for judging 3.1 honestly, and cheap. Two halves: (a) adopt **Nancel et al.'s perceptual side-effect metrics** — lateness/undershoot, over-anticipation/overshoot, wrong orientation, jitter, jumps, spring — instead of raw next-frame RMSE, which hides exactly the artifacts users notice; (b) **make every predictor beat a zero-velocity and a constant-velocity baseline at every horizon**, reported per horizon. That discipline is why the AV and human-motion literatures caught their own overclaims (a constant-velocity model beat published LSTMs; a zero-velocity baseline beat published human-motion models). ✅ Seed already exists: the 1/2/3-frame horizon table in spec §0.15, produced by `analysis/audit_jump_provenance.py`. ⚠ Build streams with `build_v2()`, per the binding rule above |
| 0.5 | ~~S8: offline oracle over the recorded corpus~~ | perception | **DROPPED 2026-08-04 — two independent blockers, one permanent** | — | ⭐ **Do not restart this without reading both reasons.** **(a) LICENSING, decisive.** HaMeR and WiLoR both depend on **MANO**, licensed for non-commercial scientific research only (commercial licensing is separate, via Meshcapade). This project is intended for **commercial release**, so MANO is out — even for offline tooling that never ships, because "used a non-commercial model to tune a commercial product" is an ambiguity not worth carrying, for an item the queue itself marks optional and blocking nothing. Owner decision 2026-08-04. **(b) THE CORPUS HAS NO PIXELS.** Verified exhaustively: the entire capture root is **390 `.json` + 25 `.jsonl`, 334 MB, and zero image or video bytes**; no recorder ever wrote frames. An image-based oracle cannot be run over the existing sessions **at any budget** — this row's own wording ("across the 24 recorded sessions") was never achievable. New item **N13** carries the licensing constraint forward; **N14** carries the no-pixels fact. **Commercially-clean substitutes if an external reference is ever needed**: ArUco/ChArUco fiducials (BSD, `opencv-contrib-python` already installed, gives REAL ground truth rather than pseudo) or RTMPose-Hand (Apache-2.0, but 2D only, so it cannot bound the depth errors behind T1/T2). Prior note follows. **Spec §10.4/S8.** Run a heavyweight offline model (**HaMeR** or **WiLoR** — GPU or slow CPU, offline is fine) across the 24 recorded sessions to produce pseudo-ground-truth. Standard evaluation trick in this literature, and it solves a real problem here: **1.5/1.6's gates currently have nothing to be tuned against except MediaPipe judging itself.** Also quantifies MediaPipe's error per pose class, which is the honest way to bound what T1/T2 can ever achieve on this sensor. Not on the critical path — start it whenever there is idle machine time |
| **PHASE 1 — kill the singularities** ||||||
| 1.1 | **M5d `K` fixture test** | perception | **DONE 2026-08-03 — all 13 checks pass, exit 0** | 0.1 | **§0.9.** `VerifyChiralityFixture.py`, 4 clips, **788/788 on every check**. The two defects found on first run were **in the test, not the pipeline**, and both are fixed: (a) the drift guard dumped ASTs *with* identifier names, so `landmarks` vs `pixel_landmarks` read as drift — now canonicalised, **and re-validated against 5 mutants (incl. the §13.6.1 inversion) to prove it still fails on real drift**; (b) the label expectation was backwards. **KEY FINDING — the label is the MIRRORED/apparent hand, NOT the physical hand: a physical RIGHT hand carries the label `"Left"`.** Established by measurement (the `"Right"` label sits on the image-LEFT hand 100% of the time across static_hold/non_crossing/palm_back_s1 = 1991 frames), not by flipping the expectation until green. Both pipeline paths converge on this by different routes — do not "simplify" either. Original note follows. `VerifyChiralityFixture.py`. Imports **production's real `_is_thumb_outward`** (headless via `SDL_VIDEODRIVER=dummy`, working around the `CubeWindow()` import side effect — §7.3) rather than reimplementing the convention; a test with its own copy would have passed while production was inverted on 2026-08-01. **RESULT: the sign convention is CORRECT — 788/788 frames across both hands and both facings, and the negative control inverts 100%, proving the test can detect the regression.** Four ground-truth clips recorded at 24–25 fps, 100% detection. **Two defects are in the TEST, not the pipeline, and it is not a valid guard until both are fixed:** (a) the drift guard compares ASTs *including identifier names*, so production's `landmarks` vs the debug copy's `pixel_landmarks` reads as drift — a false positive; (b) the label-convention check expects the recorded handedness to equal the physical hand presented, and it fails 0/788 on all four clips — the recorded label is consistently the *mirror* of the physical hand. **Which convention is correct has NOT been established from data yet** (the diagnostic was deferred for camera time); do not "fix" it by flipping the expectation until it is |
| 1.2 | M5a `edgeOnMeasure` (recover `\|s\|`) | perception | **DONE 2026-08-03** | — | **§0.10.** New shared module `Resources/palm_geometry.py` (pure stdlib, no side effects), **imported by BOTH** `HandsTriggeredActions.py` and `LiveSnapDebug.py` — so this also **retires the hand-synced duplicate `_is_thumb_outward`**, the exact duplication behind §13.6.1. Same treatment as the identity tracker (N6). Exposes `signed_palm_area`, `edge_on_measure`, `is_thumb_outward`, `is_edge_on`, `EDGE_ON_THRESHOLD=0.15`. **Verified: `edge_on_measure` matches `AnalyzePerceptionSequences.edge_on()` to 5.55e-16 across 22,345 hand-frames / 24 sessions** — required because every recorded threshold is expressed in the analyser's scale, so a different normalisation would silently invalidate 0.15. Fixture test still **15/15, exit 0** (production sign behaviour unchanged, 788/788). 1.54% of the corpus sits below the gate, matching §0.3's predicted shape. **Not yet consumed by any gesture rule — DR-2 (2.2) is what will gate on it.** **LIVE-CONFIRMED 2026-08-03** — operator verdict *"everything working"*; thumb rule checked in both orientations on both hands, plus grab/translate/rotate/release. 18 DR-1 events all benign (9 locks, 9 track-ends), **0 switches / 0 duplicate repairs / 0 errors**. A regression test by design: the change is behaviour-preserving, so "nothing changed" was the pass condition |
| 1.3 | M6a verify no Euler in estimation path | perception | **already satisfied** | — | Tick and move on — quaternions since day one, §2 forbids Euler |
| 1.4 | M2 bone-length calibration | perception | **DEAD — verdict AUDITED AND UPHELD 2026-08-03; replaced by NEW item 1.7** | — | ⭐ **Audit (spec §0.15/§10.2).** The kill was measured against **absolute** lengths while §2f defines the target as *proportions + a per-session scale constant* — so it was re-measured on the correct quantity (`audit_m2_proportions.py`): palm-normalised **proportions** give median IQR 6.5–8.7%, still **0/21 bones inside 2%**, with cross-session disagreement up to **32–40%** (worst on the back-of-hand takes). **The premise-kill STANDS.** External corroboration: `worldLandmarks` are a **GHUM average-hand fit with a documented 1.3–1.5 cm mean 3D error** and an assumed focal length — a pose-consistent personal skeleton was never in this signal — plus Google's open issue **#5156** for world landmarks collapsing on the back of the hand. **→ Do not retry M2. Build 1.7 instead (impose a skeleton rather than measure one).** Prior note follows | ⭐ **§0.14.** `Resources/hand_model.py` built (numpy-free, median-based, low-motion-gated, persistent). **Measured on still frames pooled across all 24 sessions with full pose diversity, exactly as §2f prescribes: NOT ONE BONE converges.** Per-bone IQR/median — Left palm **10.49%**, Right palm **6.28%**, fingertips 11.4%, worst 22.2% — against a **<2%** freeze gate; **0/5 palm and 0/5 fingertip bones inside target**. Half-vs-half disagreement 4.02% / 24.33%. **Does NOT contradict §0.2's 2.76 mm palm rigidity — that is a rigid-body fit WITHIN a pose; this is bone length ACROSS poses.** Conclusion: **`worldLandmarks` do not encode a pose-consistent skeleton**, so M2's "20 fixed lengths are the strongest prior available" does not hold here. **Do not tune the gate to make it pass.** ⚠ **Downstream: N2 CONFIRMED and my fix FAILED** (pose-normalised residual moved moving/still only 2.05×→1.99×; the pose effect is not common-mode) — N2 needs a new idea; **1.6 (M4) loses its intended per-landmark error signal**; **4.1 (M9) and T4 are at risk**. Three options in §0.14, none chosen — owner call. ⚠ `_try_freeze` can freeze prematurely (fires at MIN_SAMPLES, not full window) — fix before any use | Hard prerequisite for Z-axis control. **§0.3 corrects the rationale**: held still, bone CV is already 0.9–1.1% (inside target) — the 10% figure is motion/rotation-induced, not a sensor floor. So calibration is EASY (gate on low motion), but **the bone residual is a weaker M4 error signal than assumed — it reports "the hand is rotating", not "landmark 8 is bad", and must be pose-normalised** |
| 1.5 | M3a hard anatomical constraints | perception | **DONE 2026-08-04 — built and measured; 0.00% false positives on the control** | ~~1.4~~ (M2 is dead; no longer blocked) | ⭐ **Spec §0.16.** `Resources/hand_anatomy.py` (stdlib-only, numpy-free, no side effects, shared by production and the debug tool per the N6 precedent) + `analysis/m3a_violations.py` + `analysis/m3a_diagnose.py`. **Result: 0/1446 control hand-frames violate (`static_hold`), while the failure poses fire at 5–59%** — pitch/edge-on crossing 33–59%, back-of-hand 5.1%, finger self-occlusion 5.6%. ⚠ **The FIRST version was wrong and the control caught it (93.7% false positives).** Two real errors, both diagnosed from measured distributions rather than fixed by loosening thresholds: **(a)** requiring all three joints of a finger to co-flex is anatomically false — the MCP extends while the IPs flex, measured at **31.1% negative on valid hands**, so the unidirectional prior belongs to the **PIP↔DIP pair only** (0.0% negative, min +0.41); **(b)** the hinge plane from metacarpal×proximal is ill-conditioned (MCP bend median only ~14°, so near-parallel vectors) — rebuilt from **proximal×middle**, median 25.5°→11.5°. ⚠ **Thresholds are CLINICAL GONIOMETRY NORMS, not corpus-fitted** — Spurr et al. publishes no table, its limits are fitted from RHD/GANerated/STB/FreiHAND, and Hand-BMC-pytorch (MIT **code**, but it ships no values) generates them from those research-licensed datasets. Fitting them to MediaPipe's own output would also be the exact circularity 0.5 was meant to remove. Do not re-derive them. ⚠ **NOT yet consumed by anything — A10's ship-or-revert test applies when 1.6 gates on it.** Prior note follows. **Spec §10.4/S6.** Unidirectional-flexion prior breaks bas-relief ambiguity. ⭐ **Literature (Spurr et al., ECCV 2020) measures biomechanical constraints — joint limits, unidirectional flexion, planar articulation — as HALVING depth error on FreiHAND** (vs 15% without), the strongest published lever on exactly the depth-error family behind T1/T2. A reusable constraint set exists (`MengHao666/Hand-BMC-pytorch`). Deliverables: (a) the per-frame validity bit that feeds 1.6's gate, (b) M5's bas-relief disambiguation term. **With 1.4 dead, build this BEFORE any T1/T2 retest** |
| 1.6 | M4 precision weighting + χ² gating | perception | **BUILT 2026-08-04 — A10 PASSES on both metrics; 2 of 4 cues measured out** | 1.5 (**DONE, but NOT used — see below**) | ⭐ **Spec §0.17.** `Resources/frame_gate.py` + `analysis/m4_cue_distributions.py` + `analysis/m4_gate_ab.py`. **Result: 54% of >1.0 and >2.0 palm-width position excursions removed, at a 0.40% rejection rate and a tracking cost of 0.00004 palm widths (p99 exactly 0)** — invisible when the measurement deserves belief. Two cues shipped (position innovation vs the LAST ACCEPTED frame, palm-width collapse), rejections capped at 2 consecutive frames. ⭐ **Two cues were built, measured and REMOVED**: bone-length deviation (changed the outcome by ONE excursion while causing 58% of all rejections; alone it is *worse than nothing*, −1%) and **M3a tightening**. ⚠⚠ **ITEM 1.5 IS NOT CONSUMED BY THIS ITEM.** Using M3a's validity bit to tighten the gate made the result slightly WORSE (35 vs 33) at double the rejections, because **80.8% of the largest position innovations occur on anatomically VALID frames** — a teleport moves every landmark coherently, so the hand stays anatomically perfect while sitting in the wrong place. M3a covers the ORIENTATION class, M4 the POSITION class; **they do not compose** (the converse of A5). **So 1.5 currently has no demonstrated consumer and is a revert candidate under A10 unless an orientation-side consumer is built — owner decision.** ⚠ The 2-frame cap is load-bearing, not a formality: loosening it to 4 frames costs **170× worse tracking** for one extra excursion — the §0.13.3 cascade, measured directly on position. ⚠ **Not wired into production, no live confirmation. T3 is improved, NOT closed** (the survivors are multi-frame teleports that outlast the cap by design), and `translation_pivot_jump_test4` has not yet been replayed through it (different schema). Prior note follows. ⭐ **Spec §0.16, "does the validity bit predict the jumps".** Measured before starting: M3a violation at either endpoint of a transition gives **lift 33.8× and 92.0% coverage on >60° jumps** — so 1.5 survives A10 and 1.6 has a real cue. ⚠ **But it is an EXCULPATOR, not an accuser, and 1.6 must be built that way.** P(jump \| anatomically ok) = **0.22%** (a 99.78% "this frame is fine" signal), while only **7.5%** of flagged frames actually jump and the bit flags **25% of the whole corpus**. Rejecting every violating frame would discard a quarter of the stream to catch 2% of it and would violate S5's anti-cascade cap outright. **Build M3a as a cheap FIRST-STAGE PASS clearing ~75% of frames, then run the expensive consistency cues (velocity/acceleration plausibility, palm-pixel-width collapse, last-accepted comparison) only on the flagged quarter.** ⚠ Co-occurrence, not forecasting — do not reuse it as a predictor. Prior note follows. **Spec §10.4/S5.** Hard prerequisite for unsnap. **Verify against `jump_test4`**. ⚠ 1.4's death removed M4's intended per-landmark signal. Replacement, per literature: gate on **consistency cues** — bone-length deviation as a *gross* outlier flag only (~6–10%, the precision the sensor actually supports, NOT M2's dead 2%), velocity/acceleration plausibility, palm-pixel-width collapse, anatomical validity from 1.5. Per-frame confidence scores are documented as poorly calibrated for exactly these well-conditioned-pose failures. ⚠ **Binding rules learned from §0.13.3's χ² failure**: compare against the **last accepted** measurement, **cap consecutive rejections at 1–2 frames** (the cascade is what manufactured the gate's own failure), and evaluate **POSITION first** — the χ² null condemned orientation gating only |
| 1.7 | **M2b: impose a skeleton instead of measuring one** | perception | **BUILT AND PARKED 2026-08-04 — cannot affect orientation BY CONSTRUCTION** | 1.5, 1.6 (both parked) | ⭐ **Spec §0.18.** `Resources/hand_skeleton.py` + `analysis/m2b_skeleton_ab.py`. The fit works — phalange bone CV → **exactly 0.000**, consistent by construction, which is what 1.4 could never reach. **But orientation jumps are 1413/586 → 1413/586, a 0.0% change, and that is structural rather than a bug: the orientation frame is wrist/index-MCP/middle-MCP/pinky-MCP — four PALM landmarks, no finger bones.** Pinning the palm (correct, since §0.2 measured it rigid to 2.76 mm) means the frame cannot move; *not* pinning it overwrites the most reliable data on the hand with a population-average prior for a noise-level change at 3× the distortion (0.73 vs 0.23 palm widths). **Do not retry with better proportions or more iterations.** ⚠ Built **without MANO** per N13 — population-average proportions scaled by observed palm width, no research-licensed data anywhere. ✅ **One deliverable survives and is genuinely useful: `palm_width_world()` is the per-session scale reference item 4.1 (M9) needs** — the thing dead 1.4 was supposed to supply — and it needs no skeleton fit at all. **That unblocks 4.1 → 4.2.** Prior note follows. ⭐ **Spec §10.4/S7.** The literature's answer to "worldLandmarks are not length-consistent" is not better averaging — it is **fitting a fixed-bone-length kinematic model per frame, so lengths are consistent by construction** (MANO's whole purpose; documented precedents fit to 2D keypoints with bone-length preservation, warm-started, a few LM iterations per frame). Delivers everything 1.4 was supposed to: a pose-consistent skeleton, clean joint angles for M3, a better-conditioned orientation source, and **the per-session scale reference 4.1 (M9) needs** — from a mechanism that structurally cannot have 1.4's failure mode. Population-average proportions suffice to start. **T1/T2 retest after this, not after 1.4** |
| **PHASE 2 — temporal identity** ||||||
| 2.1 | M5c DR-1 chirality lock | perception | **DONE — delivered early as N5, LIVE-CONFIRMED 2026-08-02** | 1.1 | Built ahead of Phase 2 because Object Jump Correction needed it. Live-tested against a camera 2026-08-02 (spec §0.6): operator verdict "it's working", 16 tracker events, 0 errors, and both the glitch-rejection and switch branches fired correctly. Remaining: drive `_ASSUMED_FPS` from measured timing instead of the hard-coded 24.0 (N7); reconcile with M4's quality gates |
| 2.2 | M5e DR-2 edge-on band | perception | **BUILT + LIVE-TESTED 2026-08-03 (regression clean); latency now MEASURED** | 1.2, 2.1 | **Live test: no regressions** ("it does not seem anything regressed"), 0 errors over two runs. **Freeze latency measured over 144 episodes: median 96 ms, p90 163 ms, but p99 1.8 s / max 3.5 s** in sustained sideways-on poses — the tail was not anticipated and is now recorded in `GAME_RULES.md` rule 3. ⚠ **My test-3 design was faulty**: I asked the operator to perceive whether the game had registered a turn-over, but production surfaces no indicator for it — unverifiable by a human, so it was measured from recordings instead. A max-freeze cap was considered and deliberately NOT added (the spec's answer is `orientationValid` suppression once a consumer exists; a cap would be heuristic pile-up). Build detail follows. **§0.11.** `PalmFacingTracker` in `palm_geometry.py`, per hand, **shared by production and the debug tool**. Freezes the palm/back sign while `edge_on_measure < 0.15`; resumes only above 0.24 for ~100 ms (ms, not frames — finding N1); `reset()` on tracking loss. **Closes a real rule-3 defect**: rule 3 disarms its snap exception on a SINGLE thumb-inward reading, and the raw sign chatters at up to 765 flips/1k frames near edge-on — so one spurious flip silently revoked the exception (release showing the back of the hand, pass through edge-on, re-grab refused for no visible reason). **A/B over 24 sessions: 2 of 10 ground-truth streams improved, 0 worsened, 0 activity on both chirality controls, fixture test still 15/15.** Effect is **modest** (8 of 10 unchanged) — passes A10 on no-regression + measured gain, not magnitude. ⚠ **PARTIAL vs. spec**: M5e's carry-the-sign-through-by-integrating-M6-angular-velocity is absent because M6 is 2.3 — a genuine crossing registers ~100 ms LATE, never wrong. ⚠ **Changes game behaviour, so "nothing changed" is NOT its pass condition.** Original note follows. **Validated and its threshold SETTLED 2026-08-02** (§0.2 + §0.3): `non_crossing` gave **0 flips in 723 frames** with edge-on never below 0.353, so the 0.15 band is never entered in normal use — but 4.6–8.0% of normal frames fall below 0.60, so **raising the threshold toward 0.60 is contraindicated**. Keep 0.15. Reconcile with rule 3's armed-exception state machine |
| 2.3 | M6b–e quaternion UKF, anisotropic covariance | perception | **DEPRIORITISED — 5 attempts all null; verdict AUDITED AND CONFIRMED 2026-08-03 on corrected streams** | 2.1 | ⭐ **Audit (spec §0.15).** Every A/B behind this row built streams on the **raw MediaPipe label with no duplicate-label or frame-continuity guard**, on a corpus deliberately full of label flips and duplicates — i.e. they replayed a pre-DR-1 pipeline that production no longer runs. Re-run on DR-1 identity-corrected streams: **the shipped filter still wins (>60 jumps 442 vs no-filter 572, tracking 1.34°), the best-tail UKF still costs 22° of tracking, the gated variant still does nothing (0.000° tracking, tail untouched), and observability-as-blend-signal still loses.** **All five nulls, the SVD-frame rejection and the Kalman-family discard are CONFIRMED — do not revisit on artifact grounds.** ⚠ Two numbers here are nonetheless wrong: the raw tail was inflated ~25% by contamination (>60: 730 → 572) and **"82% of jumps at observability ≥ 0.60" is really ~77%** — conclusion unchanged, numbers superseded. ⚠ The row's own conclusion *"the motion model is weak"* is **RETRACTED** (see 3.1). Prior note follows | ⭐ **§0.13.2 — the decisive measurement: the tail is NOT an observability problem.** Bucketing RAW >60° jumps by observability: low-observability frames are ~17× more dangerous *per frame* (319/1k vs 19/1k), **but 82% of all large jumps occur at observability ≥ 0.60**, because that is 97.7% of frames. **M6c can only reach 18% of the problem.** This explains all five failures as one cause: attempts 1–4 keyed damping to observability so had to damp *everywhere* to catch the 82% (→ 3–17× worse tracking); attempt 5 gated to act only in the band, so tracked perfectly (0.000°) and left the tail untouched. **A 6th anisotropy attempt is NOT warranted.** At 24 fps a >60° change in 41 ms implies >1460°/s — at/beyond the human wrist limit — so these are **bad landmarks, not real motion**. → **Redirect to 1.4 (M2) and 1.6 (M4): M4's χ² gate is designed to reject exactly this implausible-excursion case.** ⚠ **T1/T2 were queued behind 2.3 assuming better pose filtering would fix them; that assumption is now MEASURED FALSE for 82% of failures — re-test them after 1.4/1.6, not 2.3.** `orientation_filter.py` stays **parked and unwired** (built, correct, loses ungated; substrate only). Prior detail follows. **§0.13.1: the propagated-covariance filter WAS built** (`Resources/orientation_filter.py`, full error-state multiplicative KF on SO(3), numpy-free, P grows by Q while coasting and shrinks only when trusted — the exact growing/snapping-back mechanism the fixed-P attempt lacked). **54 configs swept; the trade is absolute** — best tail (>60: 589→**1**, max 180°→63°) costs 17× worse tracking; best tracking (3.56°) erases the tail benefit. ⭐ **WHY: the shipped filter is not a continuous filter but a SWITCH** — passthrough (`fused==raw`, zero lag) when well-conditioned, hard damp when degenerate. That **bimodality matches the failure mode** (rare + severe), while a Kalman filter pays graded lag every frame for protection needed occasionally. **This reframes A6: the filter's crudeness IS the fit.** Untried ideas recorded in §0.13.1 so attempt 5 is not a repeat: (a) gate the KF to passthrough above an observability threshold, using covariance only inside the bad band; (b) full 3×3 P with the frame-rotation term; (c) fix it at source via M2/M4 instead of filtering. ⚠ `orientation_filter.py` is **built but NOT wired to production** — under A10 a null-result module is removed; kept pending owner decision. Prior detail follows. **§0.12 + §0.13.** (a) **M6b SVD frame REJECTED** — 2.1× more >30° jumps than the shipped Gram-Schmidt frame, and worse on controls the shipped frame handles cleanly. (b) **`observability` as a drop-in for `conditioning_norm` REJECTED** — 1473/663 vs shipped 1386/611; wider dynamic range ≠ better signal. (c) **M6c anisotropic covariance NOT DEMONSTRATED** — three parameterisations, none beats the shipped filter on *both* jump-tail and tracking fidelity; every tail improvement cost 3–10× worse tracking. ⚠ **Key methodological finding: jump counts REWARD an over-damped filter.** Attempt 1 scored >60° 589→0 while sitting **37° from a trustworthy measurement**. Any future attempt MUST also report `angle(fused, raw)` on frames with `observability > 0.6`. ⚠ **M6c is not disproven — the fixed-P approximation of it is.** A real UKF propagates covariance (P grows while coasting, gain rises on recovery); that was NOT built. **A fair retry must propagate P — do not re-run the fixed-gain version.** ✅ `palm_observability()` IS built: numpy-free closed form (web-port ready), verified to 1.6e-11 vs numpy over 22,345 frames. ✅ Shipped filter re-validated a 3rd time; **A6's "delete `HandOrientationFilter`" obligation NOT met — it stays.** Prior detail follows. **§0.12.** Measured M6b's SVD frame against the shipped Gram-Schmidt frame before changing production, per the §13.7 lesson that frame changes silently invert yaw/roll. **Result: the SVD frame is a REGRESSION — 3233 vs 1533 >30° per-frame jumps (2.1× worse), and it introduces jumps in controls the shipped frame handles cleanly (`non_crossing` 1→175, `depth_sweep` 0→64, `two_hand_near_miss` 0→57).** Likely cause: singular-vector sign/axis swap when S₂≈S₃ — right-handedness was enforced, temporal continuity was not. Chirality was NEVER violated (0 left-handed frames either way), so this is a stability failure, not an inversion. **Null result recorded per A10, not retried blindly.** **`observability = 1 − S₃/S₂` is BUILT (numpy-free closed form, verified to 1.6e-11 vs numpy over 22,345 frames) but NOT adopted as the filter's conditioning signal.** An initial read — based on its far wider dynamic range (0.046–0.908 vs `conditioning_norm`'s 0.058–0.092) — said it should replace `conditioning_norm`. **Tested, that was WRONG:** driving the shipped filter with it gives >30/>60 jumps of **1473/663 vs the shipped 1386/611** (no filter at all: 1533/730), at every threshold pair swept. Reason: `conditioning_norm` measures conditioning of *the frame actually in use*, observability measures conditioning of the **rejected** palm-plane fit. **Lesson recorded: wider dynamic range is not evidence of a better signal.** `observability` is retained for **M6c**, where it shapes a per-axis covariance rather than a scalar blend weight — a different use this null result does not condemn. **A6's "one metric" question is NOT yet settled**; it becomes real only when M6c ships. **Remaining: 6c anisotropic covariance, 6d motion model, 6e `orientationSigma`, and DELETING `HandOrientationFilter`** (still a deliverable). Note: singular values need numpy, which `HandsTriggeredActions.py` does not currently import |
| **— REASSESS (owner decision point) —** ||||||
| R | Re-measure all M0 metrics; re-test Object Jump Correction; decide whether Phase 3 precedes feature work | — | gate | 2.3 | |
| **PIPELINE TODOs — expected to close in Phases 1–2** ||||||
| T1 | Back-of-hand rotation quality | pipeline | open, 4 attempts | **1.5, 1.6, 1.7** (was 1.4/1.6, was 2.3) | ⚠ **Dependency CHANGED AGAIN 2026-08-03 (§0.15/§10).** 1.4 is dead, so "re-test after 1.4/1.6" is not buildable as written — re-test after **1.5 (anatomical constraints), 1.6 (consistency gate) and 1.7 (imposed skeleton)**, which are the three mechanisms that attack landmark quality at source. ⭐ **External corroboration for this exact failure**: Google has an **open issue (#5156) that palm/MCP world landmarks COLLAPSE when the back of the hand faces the camera** — T1 is a documented sensor failure mode, not only a filtering problem, and §0.15's worst cross-session offenders were the `known_*_back` takes. Prior note follows. §13.7. ⚠ **Dependency CHANGED 2026-08-03 (§0.13.2).** Was "M6c's anisotropic covariance is the untried mechanism" — M6c has now been tried **five times and cannot reach 82% of the large jumps**, which occur in *well-observed* frames. Re-test after **1.4 (M2) / 1.6 (M4)**, which attack landmark quality at source; M4's χ² gate targets exactly the implausible single-frame excursion this turns out to be ⭐⭐ **NEW, BINDING (2026-08-17, §16.17): STOP LOOKING FOR A ROTATION-ESTIMATOR FIX.** Two structurally unrelated estimators — the shipped Gram-Schmidt frame and a Horn least-squares fit over 5 points — reproduce the SAME ~60° jumps to within 1° on the SAME live frames (62.38 vs 61.83, 57.73 vs 57.58, 49.71 vs 48.53). **A jump both estimators reproduce is already in the landmarks.** This row is therefore the LANDMARK layer's (1.5 / 1.6 / 1.7, and 5.4's causal SmoothNet) and no further estimator work will touch it. |
| T2 | Pitch-plane crossing | pipeline | partly fixed | 2.2 (done), **1.5, 1.6, 1.7** (was 1.4/1.6, was 2.3) | ⚠ **Dependency re-pointed with T1 (2026-08-03)** — 1.4 is dead. ⭐ **The literature says the edge-on configuration is genuinely ill-posed for one RGB camera** (HandFlow, VMV 2022: the pose posterior is multimodal there; Meta uses multi-camera rigs for precisely this) — so DR-2's freeze-and-suppress plus motion carry-through is the *correct class* of answer and no per-frame cure should be expected. Prior note follows. §13.7. M6a satisfied; **DR-2 (2.2) shipped and closes the sign-flip half**. ⚠ **The rotation-quality half is NOT M6c's to fix** (§0.13.2) — redirected to 1.4/1.6 with the rest of the tail ⭐⭐ **NEW, BINDING (2026-08-17, §16.17): STOP LOOKING FOR A ROTATION-ESTIMATOR FIX.** Two structurally unrelated estimators — the shipped Gram-Schmidt frame and a Horn least-squares fit over 5 points — reproduce the SAME ~60° jumps to within 1° on the SAME live frames (62.38 vs 61.83, 57.73 vs 57.58, 49.71 vs 48.53). **A jump both estimators reproduce is already in the landmarks.** This row is therefore the LANDMARK layer's (1.5 / 1.6 / 1.7, and 5.4's causal SmoothNet) and no further estimator work will touch it. |
| T3 | **Object Jump Correction** | pipeline | ✅ **BUILT 2026-08-21 (owner: "build it") — the cube now follows the HAND, not the LABEL. ⚠ Awaiting a live look; partial by design** | 2.1 (+ N5 now) | ⭐ **Built: `Resources/hand_ownership.py`** (stdlib-only, numpy-free, no imports at all), wired into `HandsTriggeredActions.py` **and** `LiveSnapDebug.py`. When a hand holding a cube vanishes and the SAME hand reappears in the other handedness slot, ownership follows it instead of the cube dropping. ⭐ **No protocol change** — DR-1 runs server-side, so a relabel arrives as "owner slot empties, other slot fills"; the client recognises it by POSITION, which is DR-1's own criterion, from data already on the wire. Same scoping call as D1 (spec §2.2). ⭐ **The threshold is MEASURED, not chosen** (`analysis/t3_relabel_threshold.py`): candidate displacement is **median 0.11 palm widths, 86% inside 0.5, only 3 of 57 between 0.5 and 1.0** — a hand that "moved" 0.11 palm widths between consecutive frames *is* the same hand, and that tight cluster is itself the evidence for the relabel reading. **0.5 pw sits at the knee of the cluster, deliberately not where it would catch the most events**: past the cluster you stop repairing relabels and start handing cubes to hands that are somewhere else. ⚠⚠ **THE GUARD IS WHAT MAKES THIS SAFE AND IT BLOCKS MORE THAN IT ALLOWS**: no transfer if the other slot already held a tracked hand, because that is two real hands and moving a cube between them is **N8 cube-stealing arriving through a new door**. It blocks 84 of 141 candidates. ⭐ **Effect: 49 of 236 vanish-while-held moments now keep their cube** (the remaining 8 candidates fall outside the threshold; 95 are true dropouts and belong to D2). ⚠ **State migration is the subtle part**: the orientation filter and Horn reference MOVE with the cube (both computed from world landmarks alone, so they describe the physical hand — and moving them is what prevents an orientation pop, since `grab_hand_orientation` was captured against that same stream); DR-2's `PalmFacingTracker` does NOT (it is chirality-sensitive, so its frozen sign is in the old label's convention — carrying it across would be a §13.6.1 inversion). ⚠⚠ **SCOPE, so this is not mistaken for a full close: the two-hand SWAP is NOT fixed** (both hands present, labels exchanged — the owner slot never empties, so nothing fires and the cube silently follows the wrong physical hand). That is spec §0.4's duplicate-label case and it stays open. Verified: `analysis/verify_hand_ownership.py` + `verify_d1_wiring.py` §5. Prior status follows. ⛔⛔ **RE-OPENED 2026-08-21 BY MEASUREMENT — DR-1 REDUCED IT, DID NOT CLOSE IT** | ⭐⭐ **THE MEASUREMENT THIS ROW WAS WAITING FOR ARRIVED FROM PHASE D, AND IT IS NOT THE ANSWER ANYONE EXPECTED.** `analysis/d2_bridge_ab.py` classified every spurious cube release across 36 takes and 40,307 held frames: **205 of them, of which only 83 are true dropouts.** **113 are the owner's own hand reappearing under the OTHER handedness label** (99 `IDENTITY/RELABEL` + 14 `MIXED/RELABEL` — a hand carrying the other label within 2 palm widths of where the owner hand just was, i.e. the same physical hand, relabelled), and 9 are a genuinely different hand. ⚠ **These recordings were made with DR-1 RUNNING.** So the 2026-08-02 live test was not wrong — the symptom did not occur while the operator provoked it — but "did not occur in one session" was never the same as closed, and the row's own status line said so. ⭐ **AND THE ROOT CAUSE IS NOT DR-1's ACCURACY, IT IS THE KEYING**: cube ownership is keyed by the handedness LABEL (`cube_owned_by("Right")`), so any relabel — a DR-1 error *or* a DR-1 correction — silently orphans a held cube. Spec §0.4 identified the mechanism; what is new is that it is **the single largest cause of spurious releases, larger than dropouts.** ⭐ **Proposed fix, NOT built, owner's call: key ownership on the DR-1 TRACK rather than the label.** That is a design change to `CubeWindow`'s ownership primitives, not another filter — and it would remove a defect class rather than damp it. ⚠ **Do NOT "fix" this by widening D2's bridge window.** Bridging papers over relabels cleanly (pop/save 0.00 at 150 ms, because the hand is in the same place) and that is exactly what makes it a trap: a heuristic that hides an unfixed root cause, against the standing keep-the-rule-set-small preference. Prior status follows. **FIXED by DR-1, live-confirmed 2026-08-02 — but NOT yet closed by measurement.** **Live test passed** (spec §0.6): the symptom did not occur while the operator actively tried to provoke it. **The M0 regression metric is still unmeasured** — "2 jumps → 0" needs a fresh recording replayed through `AnalyzePerceptionBaseline.py`, which a live test does not produce. Per A10, measurement is what closes this, so it stays open. Root-cause account follows. **Not two-hand confusion** — a matched near-miss control produced 0 events despite 28.6% occlusion in the overlap take. Actual cause: **MediaPipe's handedness LABEL is unstable under rotation** — flips on a single hand (18 events in `pitch_sweep_fast`, at score 0.663 vs 0.95–0.99 baseline) and **duplicate labels** (both hands labelled the same: 4/9/12 frames). Ownership is keyed by handedness, and `extract_hand_by_type` returns the first match or nothing → wrong hand claims the cube, other hand reads as not-detected → tracking-loss drop. **DR-1 is now the primary fix; M4's χ² gate demoted to belt-and-braces.** Regression metric: 2 jumps in the old baseline → 0 |
| T4 | Yaw / palm-sinking in translation | pipeline | deferred | 1.4, 1.2, 4.1 | §14.1.1. **Newly mapped** (A8): M9's foreshortening correction is the concrete fix its "startup calibration" note gestured at |
| **PHASE B — THE BLOCK REPRESENTATION (owner direction, 2026-08-04). ⭐ THE ACTIVE PHASE.** ||||||
| B1 | **`hand_blocks.py` — the derived view** | perception | **DONE — status corrected 2026-08-17** (it had read "NEXT" while B2/B4/B8, all of which depend on it, were already closed). `Resources/hand_blocks.py` is built, stdlib-only, and is imported by `palm_anchor`, `palm_rotation`, `frame_gate` and every B4 harness | — | ⭐ **`GESTURE_PIPELINE_SPEC.md` §16.** Pure function `landmarks → {palm transform (2D pos, quaternion, scale), 5 arc deployment scalars}`. **A DERIVED VIEW ONLY**: no pipeline change, no wire-protocol change, nothing in production touched, so it costs nothing if it loses. Stdlib / numpy-free / no side effects / golden vectors before the port (U3 discipline). ⚠ **Thumb stays RAW landmarks** (saddle joint; an arc does not describe opposition). ⚠ **Scope is grab/rotate/translate ONLY** — future gestures may need raw landmarks, which stay available |
| B2 | **Block separability** | perception | **DONE 2026-08-04 — anchor claim HOLDS, outlier claim NOT supported** | B1 | ⭐ The position analogue of §0.15's orientation table, which does not exist yet (*"position prediction error is still unmeasured"*). Per **S1, mandatory**: report error at 1/2/3-frame horizons and **beat a zero-velocity AND a constant-velocity baseline at every horizon** — the discipline that caught published predictors losing to trivial baselines. **This measurement decides whether B3 is worth building at all**, exactly as the 1.5→1.6 gate did |
| B3 | **Palm-transform predictor** | perception | queued | B2 | **Spec §10.4/S2.** Build with the amended parameters, not M7 as written: **(a) filter the derivative BEFORE extrapolating** — never a raw two-sample ω/v, which is where TurboTouch's 2–3× gain came from; (b) speed-gated with a dead-band (prediction OFF below ~0.03 rad/s); (c) damped extrapolation λ≈0.3–0.5; (d) post-filter the predicted signal; (e) **LaViola double-exponential smoothing**, published ≈Kalman accuracy at ~1/135 the cost. ⚠ **ONE frame (~40 ms), never two** — §0.15 measured median 4.2–4.5° at one frame vs 7.3–8.0° at two. ⚠ Report **Nancel's perceptual side-effect metrics** (lateness, overshoot, jitter, jumps, spring), never RMSE |
| B4 | **Anchor + rotation A/B (blocks)** | decision | ✅ **CLOSED 2026-08-17 by the live six-arm session — §14.1 KEEPS, arm B REJECTED, `Horn(PALM_LANDMARKS)` SHIPPED to production and live-confirmed** | B1 | ⭐ **Results: §16.17.** ⛔⛔ **§16.14's headline is RETRACTED and the retraction is the important part: `SINK` is `corr(‖cube−o‖/s, edge_on)` while `Arm2D` DEFINES position as `o + s·(Rx·ex+Ry·ey)`, so `‖cube−o‖/s ≡ ‖R‖ ≡` frozen at grab — measured sd **0.0000** within a grab. Arm B could not have scored anything but 0. That is handoff trap #4 landing on this row's PRIMARY criterion**, and any future anchor metric must compare against a quantity the anchor does not define. ⛔ Arm B also LOSES the one criterion still able to discriminate: still-hand step worse on all 4 takes (yaw 5.18→**12.72**, back 5.66→**11.27**), free-play position max 49.60→**261.68 px** — because `s`/`ex` ride TWO landmarks while §14.1 averages nine. ⚠ Arm B's rotational behaviour was nonetheless the honest one (palm-frame bearing range **0.0°** vs §14.1's **358.8°**); if an anchor is revisited, keep that and pair it with `hand_skeleton.palm_width_world()`. ✅ **HORN: `PALM_AND_TIPS` REJECTED** (p95 9.85→27.79 in play — finger motion fitted as rotation; the 'fingers still' protocol HID it), **`PALM_LANDMARKS` shipped on DESIGN grounds, not measured benefit** (balanced blind 4–2, p=0.34; p95 3–3). ⭐⭐ **Both estimators emit the SAME ~60° jumps to within 1° → those jumps are in the LANDMARKS and no rotation estimator can fix them (see T1/T2).** Harnesses: `analysis/b4_orbit_and_sink_audit.py`, `b4_six_arm_verdict.py` |
| B5 | **Grab signal from arcs, + intent prediction** | feature | queued | B1, B4 | The arcs are a natural grab/release substrate (open vs closed is one scalar per finger). ⚠ **S3 BINDING: predicted state must NEVER reach the gesture state machine** — predicted blocks for rendering/attachment, UNPREDICTED blocks for grab/release. Apple ships exactly this split. This is also where **S12 endpoint/intent prediction** belongs (pre-arm the snap, choose the target), not render-latency hiding |
| B6 | **Two-channel outlier test (the T3 hypothesis)** | perception | **research — hypothesis, NOT evidence** | B1, B2 | ⭐ §16. A teleport is MediaPipe reporting a DIFFERENT hand (§14.1.4), so it should show a large palm displacement **with a DISCONTINUOUS arc-vector jump**, while genuine fast motion shows large displacement with **continuous arcs**. That two-channel signature is what item 1.6 lacked — it rejected **4 real fast movements per teleport caught at every threshold** because single-channel position innovation cannot tell them apart (§0.17). ⚠⚠ **Must be proven the way 1.6 was disproven: CLASSIFY what is rejected, never merely count it.** Do not ship on the strength of the idea |
| B7 | **Confirmation gate (selective fixed-lag smoother)** | perception | ⛔ **PARK CONFIRMED UNDER A BLIND TEST 2026-08-17 — do not revive without new evidence** | B1 | ⭐ **Results: §16.7 (corpus), §16.9 (live), §16.9.1 (the park), §16.17 (the blind test).** The owner twice chose a B7 window when he could see the labels (windows 2 and 6, calling it *'quite predictable'*), which looked like grounds to un-park it. **Blind, balanced, 6 rounds (`blindgate_r1..r6`): no-gate 4, B7 2, p = 0.34 — NO SIGNAL. The labelled preferences were priming artifacts.** ⚠ B7 is nonetheless REAL: it has the lower worst-case orientation step in 4 of 6 rounds (59.05°→**30.20°** at best) while p95 is unchanged-to-worse (its ~83 ms lag). **Measurable, invisible — exactly the 2026-08-04 reasoning, now confirmed by a method that could have overturned it.** ⭐ Contrast with the rotation decision, which is consistent rather than contradictory: `horn-palm` REPLACES an estimator (no layer, no latency, free), B7 ADDS a layer with 83 ms of hold, against the standing keep-the-rule-set-small preference |
| B8 | **Optimise the quadratic (weights / window / order)** | perception | **DONE 2026-08-04 — ⚠ S1 FAILS: every fit loses to "hold the last value"** | B1 | ⭐ **Result: §16.8.** 15 configurations, open loop, stratified by hand speed. **(a) ORDER 2 IS WRONG** — the acceleration term differentiates noise twice; error at h=6 is 34.2 floors vs order 1's 12.9. **(b) exp weighting, half-life 2 frames, is best.** **(c) ⚠⚠ NO config beats the zero-velocity baseline at every horizon**, and orientation's log-map model loses to holding the last quaternion at every horizon. The fit wins ONLY on a moving hand at h=1–2 — exactly where a gate coasts, and nowhere else. ⭐ **And B8 is NOT the separate lever the brief assumed**: order+weighting cut B7's reversal FLAG ratio 7.03× → **3.84×** and jitter max 1.3244 → **0.5816**. The brief's "leaves the ratio intact" was measured for `ACCEL_UNCERTAINTY` only. `fit_channel(order=, weighting=, half_life=)` shipped; ⚠ defaults deliberately unchanged so pre-B8 numbers stay reproducible. |
| **PHASE 3 — latency and grab** ||||||
| 3.1 | M7 dual-pathway + forward prediction | perception | **UNBLOCKED 2026-08-03 — the "premise at risk" warning was an ARTIFACT and is retracted; first task DONE** | 0.3, ~~2.3~~ | ⭐ **Spec §0.15 + §10.4/S1–S4.** The "60% of one-frame predictions disagree by >25°" figure was a **closed-loop cascade statistic**, not a prediction error (one rejected frame books up to 8 rejections while the filter coasts). Measured open-loop on identity-corrected streams, the constant-angular-velocity model has **median error 4.2–4.5° at 1 frame, 7.3–8.0° at 2, 10.8–11.8° at 3**, exceeding 25° on only 6.4–11.4% at one frame. **Verdict: fit to extrapolate ONE frame (~40 ms), not two** — which matches the published envelope independently (Azuma <80 ms; Meta's 20–40 ms operating range; TurboTouch usable to 32–48 ms; artifacts clearly perceived at 75 ms). **Build with the S2 amendments, not M7 steps 2–5 as written**: (a) filter the derivative BEFORE extrapolating — never extrapolate a raw two-sample ω (this is where TurboTouch's 2–3× gain came from, and the parked filter's `omega` is exactly such a raw difference); (b) speed-gated horizon with a dead-band (prediction OFF below ~0.03 rad/s — shipped Oculus design); (c) damped extrapolation, shorter horizon for orientation than position; (d) post-filter the predicted signal; (e) prefer **LaViola double-exponential smoothing** over a Kalman predictor (published ≈equal accuracy at ~1/135 the cost). ⚠ **S3, binding: predicted state must NEVER reach a gesture state machine** — Apple ships exactly this split (predicted stream for rendering/attachment, unpredicted for gesture detection). ⚠ **S1: report Nancel's perceptual side-effect metrics and beat zero-velocity + constant-velocity baselines at every horizon**, not RMSE. FORM channel starts from Google's own production One Euro tunings (spec §10.2.3). Position-prediction error is still unmeasured — measure it here. Prior note follows | Retires `ROTATION_SLERP_FACTOR` into the FORM channel. ⚠ **§0.13.3: the constant-angular-velocity motion model M7 extrapolates with is measurably WEAK** — a one-frame prediction disagrees with the measurement by >25° on **60% of frames**, against a mean frame-to-frame motion of 9.9°. M7 extrapolates that model up to ~80 ms ≈ 2 frames, and its headline claim ("net perceived latency can go to zero") assumes a predictor this data does not support. **FIRST TASK for 3.1: measure the model's prediction error at 1/2/3 frames and decide whether it is fit to extrapolate with.** If not, M7's FORM/MOTION channel split may still be worthwhile on its own — the split does not require prediction. ✅ The motion model, `omega` as a public state and `predict_forward()` already exist in the parked `orientation_filter.py`; 3.1's old dependency on 2.3 was for exactly that and is now satisfied without it |
| 3.2 | M8b RTS retrospective smoothing | perception | queued | 2.3 | **Additive** to §14.1 — not blocked by the M8a deferral |
| 3.3 | **M8a A/B vs. §14.1** | decision | queued | 2.3, 4.1 | A7. Measure grab-placement **accuracy**, not just jitter. Do not touch §14.1 before this |
| 3.4 | M8c predictive grasp onset | perception | **blocked** | 4.3 | Today's snap is proximity-based; aperture enters the design only with §14.2. ⭐ **Spec §10.4/S12 — this is where the "brain-mimicking prediction" idea actually belongs.** Minimum-jerk models predict *where a ballistic reach ends*, not the next frame (published: ~0.8 cm at 100 ms for ballistic VR reaches; endpoint prediction needs ~50% of the movement observed). That is an **intent** signal — pre-arm the snap, choose the target object — and it is the published form of M8c's anticipatory-grip analogue. Do **not** try to use it for render-latency hiding; that is 3.1's job and has a ~40 ms ceiling |
| **PHASE D — DROPOUT MITIGATION. ✅ D0–D3 SHIPPED AND OWNER-ACCEPTED LIVE 2026-08-21. D4 is an open owner DECISION, not a build.** ⚠ Phase D also RE-OPENED **T3**, which is now the larger defect — see that row before starting 4.1. ||||||
| D0 | **Dropout census — does MediaPipe actually drop out, and what does it cost?** | measurement | ✅ **DONE 2026-08-21** | — | ⭐ `analysis/d0_dropout_census.py`, run before building anything, because the source document orders the whole build on a falsifiable premise. ⛔⛔ **THE PREMISE IS FALSE HERE: pitch-crossing + back-of-hand takes — 7 purpose-built takes, 3 sessions, 2 frame rates, 11,524 in-take frames — contain ZERO dropped frames (0.000%).** MediaPipe does not fail to detect in that band on this hardware. ⚠ **The document also has the failure TYPE backwards**: it argues this is *"not a landmark-accuracy problem ... it's an upstream detection failure"*, but pitch crossing here produces **no missing landmarks and plenty of bad ones** — §16.17's ~60° jumps that BOTH estimators reproduce to within 1°. Bridging cannot touch that; it is T1/T2's (1.5/1.6/1.7, 5.4). ⭐ **BUT THE REMEDY IS STILL JUSTIFIED ON DIFFERENT, MEASURED EVIDENCE**: dropouts are real at **1.36%**, clustered in FREE PLAY (hand leaving frame, fast motion), and because `_is_detected` is False on ONE placeholder frame and `update_hands` releases immediately, they cause **98 spurious cube releases over 40,307 held frames** — one per ~24 s of holding. Median gap **89 ms**; bridging to 150 ms saves 66%, 300 ms 82%, 1 s 98%. **Build it before 4.1 — the document's ordering is right and its stated reason is not** ⚠⚠ **SUPERSEDED IN PART BY D2's CLASSIFICATION (2026-08-21) — read that before quoting the 98.** This census counted frames where **no hand at all** was present, but production's `_is_detected` is **per hand**, so it also fires when the owner's hand is found under the other label. Counted that way there are **205** spurious releases, not 98 — and only **83** are true dropouts. **113 are relabels, which is T3, not Phase D**, and that row has been re-opened on the strength of it. The 98 is not wrong, it is the answer to a narrower question than the one that mattered |
| D1 | **`HandState` — land the tracking fields on the EXISTING contract** | perception | ✅ **DONE 2026-08-21 — built, verified, wired, and it changes NO behaviour by construction** | D0 | ⭐ **Built: `Resources/hand_state.py`** (stdlib-only, numpy-free, clock-free — `now_ms` is injected so it stays deterministic), wired into `Resources/HandsTriggeredActions.py` **and** `LiveSnapDebug.py` together, per the §13.6.1 duplication rule. ⭐⭐ **`BRIDGE_WINDOW_MS` ships at 0.0, which makes `BRIDGING` unreachable and D1 provably free**: the release decision and the filter/DR-2 resets now read a tracking STATE instead of the raw detection bit, on exactly the frames that bit was False. **D2 is then one constant plus the coasting pose, not a re-plumbing.** ⚠ The resets are gated on `SUSTAINED_LOST`, NOT on "this frame missed" — wiping the orientation filter, the Horn reference and DR-2's frozen sign on the first missed frame would discard precisely what a bridge must coast on, and D2 would resume from a cold start (a pop instead of the drop it replaced). A no-op today, load-bearing the moment the window opens. ✅ **Also landed: DR-2's `orientation_valid`**, computed since 2.2 and discarded ever since, is now recorded as `quality.orientationValid` — still read by no rule, which stays a separate decision. **Verification: `analysis/verify_hand_state.py`** (37 vectors, U3 golden-vector discipline, dependency-free so a port must reproduce it — §2 asserts the zero-window invariant and §4 asserts the ms-not-frames rule at 14 and 24 fps) **+ `analysis/verify_d1_wiring.py`** (production drives release on exactly the pre-D1 frames, AND the tracker is proven load-bearing rather than wired-in-and-ignored). All 7 pre-existing verify suites re-run clean. ⚠ **Not live-tested — and it should not need to be, since behaviour is unchanged; the live test belongs to D2.** Design notes follow. ⚠⚠ **NOT a new schema. `PERCEPTION_LAYER_SPEC.md` §2 already defines `HandState` v2** and it was spec-only (never implemented), so the two-schema clash was resolved on paper 2026-08-21 — see the new **§2.1**, which is the single schema of record. ⭐ **v2 already covers the source document's §2 and beats it twice**: `positionConfidence`→`palm.covTrace` (real uncertainty, not a time-decay ramp), `orientationConfidence`→`palm.orientationSigma` (**per-axis anisotropic** — one scalar would discard the very asymmetry §16.17 measured), `framesSinceGoodDetection`→`quality.framesSinceMeasurement` (already present). **`trackingState` was the ONLY genuinely new field and is now added to v2's `quality` block.** ⭐ **SCOPE (owner decision 2026-08-21): a CLIENT-SIDE SUBSET, not the wire protocol** — see §2.2. Dropouts surface client-side (the server already sends 21 zero landmarks via `remap_keypoints`'s `expected_count` fallback; `_is_detected` reads them), so `trackingState` + the miss-counter are computed on the client from EXISTING wire data. **No second protocol exists, so v2's "do not run both protocols in parallel" rule is not engaged** — taken literally it would have put a socket migration in front of D0's measured 98 drops. ⚠ **The full v2 wire migration is still required and is a SEPARATE decision, naturally paired with 4.1/M9**, which is what makes v2's metric fields mean anything; until then do not serialise the struct. ⚠ A third `HandState` (an unrelated gesture-history buffer in `LiveGestureDebug.py`) was renamed `GestureHistory` to free the identifier. Stdlib-only, numpy-free, golden vectors before the port (U3) |
| D2 | **HOLD-and-decay bridging + confidence-scaled follow** | perception | ✅✅ **SHIPPED 2026-08-21 — built at 150 ms, measured on replay, then ACCEPTED LIVE BY THE OWNER against the three-arm rig** | D1 (**DONE**) | ⭐ **The live decision, and how it was taken.** The owner ran OFF / ON / BLEND side by side off one camera and chose **BLEND** — *"3 · BLEND is definitely better"* — and **explicitly waived the blind test.** ⚠⚠ **RECORD THAT WAIVER AS A DELIBERATE OWNER CALL, NOT AN OVERSIGHT**, because this project's own rule (§16.17) is that a *preference* between arms needs the balanced `--blind-series`: an unbalanced sighted comparison once manufactured a convincing 5–1 that collapsed to 4–2, p = 0.34. The rule was stated before the session and the owner overrode it knowingly. ⭐ **And the two cases are not alike, which is why the override is reasonable rather than a lapse**: B7/horn-palm were *invisible* effects hunting for a preference, so priming could supply one. Here the arms differ in whether the cube is still in your hand — a discrete, unmistakable event, seen simultaneously rather than in sequence, with per-arm counters on screen. ⚠ Nonetheless: **no p-value attaches to this, and none should be claimed.** Prior status follows. **BUILT 2026-08-21 at 150 ms — measured on replay, AWAITING THE OWNER'S LIVE LOOK (A7)** | ⭐ **Result: `analysis/d2_bridge_ab.py`, which classifies every held-cube dropout instead of counting the ones removed.** Window **150 ms**, derived from the measured median true-dropout gap of **128 ms** (2–3 frames at 14–24 fps), never copied from the source document's 30–60 fps constants. **Of 83 true dropouts: 39 SAVED, 19 POP, 25 LATE_RELEASE.** Going to 300 ms buys 9 saves for 2 pops, barely moves the ratio (0.49 → 0.44) and **triples the worst added hang** — and the hang, not the ratio, is the ceiling, because a long window IS D4/M10.7's grace period, which is GATED. ⚠⚠ **The POP class is the whole reason this row is not "done, ship it": a bridge with no blend TRADES a drop for a jump** (resume displacement median 0.64, p90 1.87, max 2.47 palm widths) — which is why **D3 was brought forward and ships with it**. ⭐ **The code change is small because D1 made it small**: the coast is `BRIDGE_WINDOW_MS`, the "hold" is free (the per-hand pass already skips, and `set_target_position` is instantaneous, so a skipped frame IS a frozen cube), and the resets were already gated on `SUSTAINED_LOST`. ⭐ **One real addition: `omega` is ZEROED on the resume frame** — an angular velocity measured before the gap must not be replayed across a gap the filter never observed (B8: hold beats extrapolate at every horizon). ⛔ **"Confidence-scaled follow" needed nothing built**: position has no follow to scale (it is set exactly each frame), and orientation's is `_reliability_alpha`, which already ships. Adding a second mechanism would be the rule-stacking the owner has asked against. Verified by `analysis/verify_d1_wiring.py` §2/§4 (both arms, incl. a 0 ms control that still reproduces pre-D2 behaviour exactly). ⚠ **AWAITING THE LIVE LOOK. `debug_snap.bat` (or `LiveSnapDebug.py --arms 3`) now shows all THREE arms side by side** — OFF (pre-D2 control) / ON (bridge, no blend) / BLEND (shipped) — each with its own cubes, trackers and counters, **all driven by ONE camera frame, ONE detection and ONE identity resolution**, so a visible difference between panels has exactly one cause (B4's one-variable discipline). `analysis/verify_three_arm_bridge.py` proves the panels really are three arms before anyone is asked to judge them, because a multi-arm tool that shares state shows three identical panels and reads as "no difference". ⚠ **The session tests nothing unless dropouts are PROVOKED** — grab a cube, move fast, sweep out past the frame edge and back; if the `brid` counter stays 0, nothing was exercised. ⚠ **Sighted test: "did anything regress", NOT a preference verdict** (§16.17's balanced `--blind-series` rule). Design follows. ⚠ **Start from what D1 already gives you**: `hand_state.BRIDGE_WINDOW_MS` (raise it — from D0's measured distribution, not the source document's constants), the state machine, the reset gating, and `reacquired_after_ms` for D3. What D1 deliberately did NOT build is the coasting POSE — freezing the last good landmarks/transform and decaying confidence — and the follow-strength ramp. ⚠⚠ **The A/B must CLASSIFY every bridged frame, never count drops removed**: a bridge that holds a cube through a genuine hand-leaves-frame is a FALSE HOLD, and "98 → N" cannot see it. Item 1.6 passed on exactly that kind of count and had to be reversed. Re-run `analysis/d0_dropout_census.py` so before/after come off one harness. ⚠ Raise the window in **both** `HandsTriggeredActions.py` and `LiveSnapDebug.py` or the debug tool stops mirroring the game. Design follows. ⭐ **The row that fixes the 98 drops.** ⚠⚠ **NOT the source document's §3.2, which extrapolates: B8 measured EVERY velocity fit losing to "hold the last value" at every horizon, and orientation's model losing to holding the last quaternion at every horizon.** So: freeze the last good pose, decay confidence over the gap, and let follow-strength carry the cube to a stop (§3.7's shape, which `_reliability_alpha` already half-implements). Simpler than the document AND the version this project's own measurements support. ⚠ **Derive the constants from the measured 89 ms median, never copy the document's**: it assumes 30–60 fps, this pipeline runs **14–24 fps**, so its 150 ms is 2–3 frames here, not 5–9. ⛔ **Do NOT build the document's §3.4 resync validation gate — DR-1 (2.1) already does multi-frame confirmation, glitch rejection and velocity plausibility.** Wire to it |
| D3 | **Resync blend on reacquisition** | perception | ✅✅ **SHIPPED 2026-08-21 — brought forward to ship WITH D2, and it is the arm the owner chose** | D2 | ⭐ **The live comparison separated D2 from D2+D3 and the blend is what won**: the owner picked BLEND over ON, i.e. the difference the blend makes was visible, not just measurable. That is the strongest evidence this row has and it is worth more than the replay numbers below. Prior status follows. **BUILT 2026-08-21 — BROUGHT FORWARD to ship WITH D2, on D2's own evidence** | ⭐ **Why it moved**: D2 measured that bridging without a blend does not remove a defect, it **trades a drop for a jump** — 19 of 58 bridged dropouts move the cube more than a palm width on the resume frame, and that jump is the §14.1.4 teleport this project has spent real effort on. Shipping D2 alone would have been a regression dressed as a fix. ⭐ **Result, REPLAYED over the hand's real post-gap trajectory, not modelled** (the tempting shortcut — "a 3-frame blend divides the step by 3" — is false, because the hand keeps moving during the blend): worst single-frame cube step over the resume, **median 0.62 → 0.38, p90 1.95 → 0.87, max 2.47 → 1.49 palm widths**, with **3 of 47 resumes made worse**. Those 3 are reported and not hidden — a smoother that helps on average and hurts on some cases is exactly how 1.6 passed. **Position only**: orientation already converges through `ROTATION_SLERP_FACTOR`'s slerp and needs no second mechanism. `RESYNC_BLEND_FRAMES = 3`, `t = 1/frames_left` so the last step lands exactly on the measurement with no residual offset. ⚠ **A bug worth remembering, caught by its own test**: the blend was armed on every resume but is only consumed while a cube is held, so an empty hand kept it armed and blended the NEXT grab — one that never bridged. Now armed only for a hand that is actually holding. ⚠ Confidence ramp-up is NOT built (nothing consumes confidence yet); that lands with the v2 wire migration. Design follows. The source document's §3.5, and **the one mechanism in it that is genuinely absent today** — nothing blends when a track is reacquired, so recovery is a hard cut. Blend position (lerp) and orientation (slerp) over 2–3 frames and ramp both confidences back up. ⚠ Measure it against the A10 rule like everything else: it must show a measured improvement on the M0 metrics or be reverted |
| D4 | **Grace period before release — ⚠ THIS IS M10.7 UNDER A NEW NAME** | decision | ⛔⛔ **DECLINED BY THE OWNER 2026-08-21, AFTER seeing D2/D3 live. NOT deferred again — answered.** Recorded for a later potential improvement only | D2, D3 | ⭐ **The owner's words, after running the three-arm rig: _"I do not see the need: the behaviour and results are already good at this stage, and in line with what I want to ship. Just record it for later potential improvement."_** ⚠⚠ **DO NOT RE-PROPOSE THIS.** The reopening condition (*"revisit only if immediate-drop becomes a felt problem in live play"*) was met, measured at **205 spurious releases**, put in front of the owner with a working comparison, and the answer was still no — because D2/D3's 150 ms sensor coast made the residual stop being felt. That is a **stronger** close than the 2026-08-04 deferral was: it is a decision taken with the numbers and the live behaviour both available, not a postponement. The standing preference (*"I don't want to overbuild with layers of rules"*) is therefore reaffirmed, not merely still pending. ⭐ **What would legitimately reopen it**: a hand genuinely lost for LONGER than the sensor gap becoming a felt problem in real play — the case the coast structurally cannot cover. Nothing short of that. Prior gating note follows | The source document's §3.8 (auto-release timeout + UI signal). ⚠⚠ **It is queue item 4.3's M10.7, which the owner DEFERRED on 2026-08-04** with a standing preference — *"I don't want to overbuild with layers of rules"* — and an explicit instruction: **do not re-propose it as a side effect of another item.** Adopting the source document wholesale would do exactly that. ⭐ **Its stated reopening condition — *"revisit only if immediate-drop becomes a felt problem in live play"* — IS now met, with a number for the first time: 98 spurious drops (D0).** Owner's call: **measure D2/D3 first**, see how many of the 98 bridging alone removes, and decide whether the remainder justifies changing `GAME_RULES.md` rule 2. ⛔ **Tier 2 (Kalman) and Tier 3 (past+future smoothing) are STRUCK from the source document, not deferred**: Tier 2 is queue **2.3** (5 null attempts, audited and re-confirmed), Tier 3 is **B7** (parked twice, blind-confirmed at chance 2026-08-17, §16.17). ⭐ **The source document is NOT filed in `Claude/` and will not be — owner decision 2026-08-21: its content is DISTILLED into the documents that own each part of it**, and those are the versions of record. Its schema → `PERCEPTION_LAYER_SPEC.md` §2.1 (with a field-by-field mapping table, so nothing is lost); its build tiers → this Phase D block, tier by tier, with the four that are already-rejected work struck and named; its premise → the **D0** row and `analysis/d0_dropout_census.py`, which is the measurement that refuted it. ⚠ It is still NAMED in those places, as provenance for a claim recorded here — that is a citation, not a pointer to a file anyone can open. **Do not treat an unresolvable reference to it as a missing dependency, and do not reconstruct it.** |
| **PHASE 4 — unlock the features** ||||||
| 4.1 | M9 metric depth | perception | **UNBLOCKED 2026-08-04 — the scale reference exists. ⚠ Read `GESTURE_PIPELINE_SPEC.md` §14.3.1 BEFORE building: the anchor must be MULTI-anchor, and a yaw take must be recorded first** | ~~1.7~~ — **satisfied**: `hand_skeleton.palm_width_world()` supplies the per-session scale reference without needing 1.7's fit (spec §0.18) | ⚠ **NO LONGER NEXT — PHASE D (dropout mitigation) RUNS FIRST, owner direction 2026-08-21.** Reason is measured, not stylistic: a single missing frame releases a held cube today, which cost **98 spurious drops** across the corpus (D0), and 4.1 leads to 4.2 (Z-axis) whose own grab handling would be built on top of that defect. ⭐ Still the recommended build AFTER Phase D. The one Phase 1 deliverable that survived, on the one quantity this sensor measures well (palm width, near pose-invariant, §10.1). Leads directly to 4.2. Prior note follows. Refines §14.3's ratio design: never a single bone; foreshortening-corrected. ⚠ **Dependency moved to 1.7** — 1.4 cannot supply the scale reference; the imposed skeleton can. ⭐ **Literature confirms the ratio form is the right call**: absolute camera-space hand position from monocular RGB is only ~3.5 cm at SOTA (ScaleHP 2026), while a scale *ratio* needs only temporal consistency of one anchor; **palm width is the documented anchor of choice** (near pose-invariant, unlike finger spans). ⚠ **S10, missing from both M9 and §14.3: the palm-width anchor COLLAPSES edge-on, so the depth ratio must FREEZE inside the DR-2 band** (reuse `PalmFacingTracker`'s pattern) or Z-control inherits the pitch-crossing failure |
| 4.2 | **Z-axis translation (§14.3)** | feature | designed, not built | 4.1 | Open: what happens to 3D snap gating when `depthValid` is false — undecided |
| 4.3 | M10 commitment dynamics | perception | **M10.7 DEFERRED BY OWNER 2026-08-04 — do not build** | ~~1.6~~ (parked) | **M10.7 changes `GAME_RULES.md` rule 2** (immediate drop → 400 ms grace) and would close N8. **Owner decision taken: leave it undecided for now** — *"I don't want to overbuild with layers of rules for the moment."* ⚠ Treat that as a **standing preference on RULES**, the counterpart of the no-heuristic-pile-up rule on filters: the rule set stays small and legible, and a rule whose job is to patch another rule's consequences is what is being avoided. **Do not re-propose it as a side effect of another item**; revisit only if immediate-drop becomes a felt problem in live play, and then ask explicitly. The rest of M10 also loses its 1.6 dependency (parked) and would need re-deriving before it could start |
| 4.4 | **Hand-open release trigger (§14.2)** | feature | designed, not built | 4.3 | The sole active release plan since closed-fist was parked |
| **PHASE 5 — optional** ||||||
| 5.1 | M3b synergy subspace | perception | optional | 1.5 | May make parked row 2 viable again — **do not un-park without asking** |
| 5.2 | M3 IK (26-DOF) | perception | optional | 5.1 | Subsumes 3a/3b, costs more |
| 5.3 | Trajectory gesture classification | perception | optional | 5.1 | |
| 5.4 | **NEW — causal SmoothNet-class temporal refinement** | perception | **optional, NEW 2026-08-03** | 1.5, 1.6, 1.7 | **Spec §10.4/S9.** If the consistency gate + anatomical constraints + imposed skeleton leave a residual glitch tail, the documented next step is a **tiny per-joint temporal MLP** (SmoothNet): plug-and-play across estimators, and its published analysis targets exactly this failure shape — "highly unbalanced" errors, most frames fine, failures as large deviations over short runs. ⚠ Verify the causal-mode accuracy drop and window latency before committing. Only after 1.5/1.6/1.7 are measured |
| 5.5 | **NEW — multi-hypothesis / uncertainty-aware prediction (Waymo transfer, minimal form)** | perception | **research, NEW 2026-08-03** | 3.1 | **Spec §10.4/S11.** What transfers from MultiPath++/MotionLM is the *principle* — predict distributions not points, keep discrete hypotheses where the future branches — **not** the models (their scale, 3–8 s horizons, lane-graph context and GPU cost are all inapplicable at 40 ms on CPU, and at short horizons their own literature shows physics baselines win). Minimal forms: (a) prediction emits a variance growing with horizon and recent residual, used as the render blend weight; (b) **3-mode reversal blending {continue, decelerate, reverse}** weighted by acceleration-sign consistency — targets the overshoot-on-reversal failure directly; (c) research option: carry the mirror (bas-relief) pose hypothesis through the DR-2 band and let motion continuity select on exit. **Only if 3.1's measured side-effect metrics justify more machinery** |
| **NEW — surfaced by the 0.2/0.2b measurements** ||||||
| N1 | Re-express all frame-count parameters in ms | perception | queued | — | §0.3: pipeline runs at **~24 fps, not 30** (older recorders synthesised a 33 ms cadence, hiding this). M5e's 3-frame dwell, M10's 3/4-frame dwells and M4's 8-frame coast are all ~38% longer in wall-clock than intended |
| N2 | Pose-normalise the bone residual before M4 consumes it | perception | queued | 1.4 | §0.3: the raw residual tracks hand rotation, not per-landmark quality; used directly it would down-weight every landmark whenever the hand moves |
| N3 | Counted-crossing sequence → **speed-threshold sweep** | perception | **CLOSED 2026-08-03** | — | **§0.8.** Four daylight takes at 24.1–24.5 fps, counted ground truth. **The totals were lying**: delta stays −4..+9 at every speed, but the *physically-implausible* flip fraction rises **6% → 58%** as cycle time falls 4.44 s → 0.96 s. Missed genuine crossings and spurious flips **cancel in the total**. §0.7 called this unresolvable without a rotation timeline — it is resolvable from the edge-on plausibility test alone. **Knee at ~1.3 s/cycle.** Honest limit: the fast take reached only 0.96 s/cycle, not the prescribed 0.5, so breakdown is bracketed, not bounded. Prior status follows. §0.7 + §0.7.1. **The recorded take was DELETED** (15.77 fps, poor light) — its numbers are indicative only and the data is gone. **Superseded by four speed-decoupled takes** with prescribed cycle counts and explicit PITCH axis, which locate the *threshold* at which crossings start being missed rather than yielding one blended count. **Indicative prior result (unsupported, do not cite as measurement)**: 29 cycles = 58 expected sign changes, detected **52 (Left) / 50 (Right) — UNDER-detection, not an excess**, which **reverses** the prior working suspicion of a large spurious population. **⚠ Unit trap, recorded because it caused a wrong reading once**: the operator counts palm→back→palm as ONE crossing; the analyser counts sign inversions. Compare against `expected_sign_changes` (58), never `counted_crossing_cycles` (29). **Still open**: totals cannot rule out a compensating mix of missed genuine crossings plus spurious flips — that needs per-flip matching against the rotation timeline. **Also confounded by N10**: this take ran at 15.77 fps, so the 63.4 ms interval makes genuine band-traversing crossings easier. **Re-record in better light before concluding.** Original note: §0.3 flagged the slow-sweep flips at edge-on 0.58–0.73 as suspicious, not diagnosed |
| N4 | External capture drive is unreliable | infra | **open** | — | E: dropped out ~4× in 15 min on 2026-08-02 (reads and writes both, WinError 21). Recorder now preflights and refuses rather than losing a completed take; analyser retries. Check cable/port and USB power-management, or switch to `--local` capture |
| **N5** | **DR-1 track-level hand identity (hysteresis)** | perception | **DONE — built, replay-verified AND LIVE-CONFIRMED 2026-08-02** | — | **Live test passed (spec §0.6)**: operator verdict "it's working" while deliberately rotating hands back-to-camera and crossing them; 16 tracker events, 0 errors/tracebacks; the transient-glitch branch held a 3-frame mismatch and the swap branch switched on a full 12 — the exact separation replay predicted. Original build account follows. §0.4/§0.5. A first stateless duplicate-resolver was built and **removed the same day** — score-based choice was a coin flip on 36% of frames and blind to 28 label flips. Replaced by `_HandIdentityTracker` in `hands_visualizer.py`: associate by **position** not label; lock after a vote; brief mismatch → hold, **long + confident mismatch → switch**; re-decide freely when a track ends. **A 'never switch' variant was tried and disproved** — position association swaps identities at a crossing, giving 528 overrides in runs of up to 225 frames. Replay result: duplicates **25 → 0**, longest wrong-hold **225 → 10 frames**, and **0 overrides/switches in all three control sequences**. This IS queue item 2.1 delivered early. **`SWITCH_MS` (12 frames/~500 ms) is TUNABLE — latency vs. false-glitch; re-derive if camera/fps/lighting change (spec §0.5)** |
| **N6** | **DR-1 parity: debug tool now shares the perception code** | infra | **RESOLVED 2026-08-02** | — | Was: `LiveSnapDebug.py` bypassed `hands_visualizer.py`, so DR-1 was production-only. Fixed the architecturally correct way per owner instruction ("I do not want to have a debug tool which is not in tune with the production"): the tracker was **extracted to `Resources/hand_identity.py`** — standalone, pure stdlib, no cv2/mediapipe/window side effects — and is now **imported by both**, not copied. `LiveSnapDebug.py`'s own latent duplicate bug (it keyed hands by handedness in a dict, silently overwriting one of a duplicate pair — the same defect that hid Object Jump Correction in the old recorder) was fixed in the same change. **Verified: production and debug produce byte-identical identity output across all 7 recorded sessions**, and exactly one tracker definition exists in the codebase |
| N7 | Drive `ASSUMED_FPS` from measured frame timing | perception | **DONE 2026-08-04 (DR-1). ⚠ `palm_geometry` still to do** | 0.1 | ⭐ **Built**: `FrameRateEstimator` in `hand_identity.py` — median of a 45-frame (~2 s) interval window, fed by a **caller-supplied** timestamp, never by reading the clock internally (a replay harness runs faster than real time, so an internally-sampled rate would look right in production and be meaningless in replay — the exact debug/production divergence class N6 exists to end). All four DR-1 dwells became per-instance properties re-derived each frame. `update(observations, now_ms=None)` — **omitting the timestamp preserves the old behaviour exactly**, so nothing broke while callers were wired. Production (`hands_visualizer.py`) and the debug tool (`LiveSnapDebug.py`) both now pass `time.perf_counter()`. **A/B (`analysis/n7_measured_fps_ab.py`): 20 of 21 sessions within 1 fps of 24 produce IDENTICAL assignments — a no-op where the old assumption held, which is the pass condition — while sessions at 19–21 fps now use a 10–11 frame switch dwell instead of 12, correcting a +14–24% overshoot.** ⚠ The 45-frame window was chosen against data: a 15-frame window tracked per-second jitter (reporting 15.7 fps in a session averaging 20.7) and made the dwell swing 8↔12 within one recording. ⭐ **`palm_geometry`'s half was then EXAMINED AND DELIBERATELY NOT APPLIED (2026-08-04)** — built, measured, reverted. **The time-based dwell froze DR-2 for +47.4% more frames (595 → 877)**, lengthening exactly the staleness window `GAME_RULES.md` rule 3 documents, for no correctness gain. Root of the misjudgement, worth carrying: `exit_run >= 2` exits on the SECOND consecutive above-threshold frame — **one frame interval, ~42 ms at 24 fps, not the ~83 ms "2 frames" suggests** — so a 100 ms time-based dwell needs FOUR frames and roughly doubles the freeze. ⭐ **The general rule this establishes: a "resume after N consecutive confirmations" DEBOUNCE belongs in frames; N1's re-express-in-ms applies to dwells representing real elapsed TIME (DR-1's voting windows) and not to debounces.** So `_ASSUMED_FPS` in `palm_geometry` is **not** the defect N7 fixed, and this item is CLOSED rather than half-done. Evidence, with the rejected variant kept in the harness rather than as dead code in the module: `analysis/n7_dr2_dwell_ab.py`. Prior note follows | **§0.7: frame rate is environment-dependent, not a fixed ~24** (15.1/15.77 fps measured at 22:18 vs 24.09–24.14 earlier the same evening). `SWITCH_FRAMES = round(500 × 24/1000) = 12`, so at 15.77 fps the dwell is **~761 ms instead of 500** — a 52% overshoot in the one parameter §0.5 flagged as most worth getting right. Original note follows. Hard-coded 24.0 in **`Resources/hand_identity.py`** (moved there from `hands_visualizer.py` when the tracker was extracted — N6); all DR-1 dwell constants derive from it, so a different camera silently changes every threshold. Should come from `HandState.tCapture` |
| N8 | **Cube can be stolen by occluding the holding hand** | gameplay | **recorded only — not being fixed now** | 4.3 | Observed 2026-08-02. Hand A holds a cube; hand B moves in front of it; A's tracking is lost, rule 2 releases the cube, and B — which is right where A was, so inside the grab radius — snaps it a frame or two later. **Mechanism inferred from the rules, not instrumented.** §13.5's same-frame ordering fix only blocks re-snap on the SAME tick, not the next. Expected to resolve as a side effect of refining snap control: **M10.7's grace period would hold the cube through the occlusion, leaving nothing to steal**. Recorded so it isn't rediscovered as a new bug |
| N9 | **DR-1's duplicate-repair fallback fires in normal live use** | perception | **observed 2026-08-02, NOT diagnosed — deliberately not tuned** | 0.2b | Spec §0.6. §0.5 reported duplicates eliminated **structurally**, and the end-of-function invariant was described as a fuzz-found edge case reachable only when a detection jumps past `MAX_ASSOC_PALM_RATIO = 3.0` with both track slots full. It fired **3× in one short live session**. **No duplicate was emitted — the invariant did its job, which is why the live test passed** — but the frequency is new information the 7 recorded sessions did not predict. Two candidate causes, undiagnosed: the association limit is too tight for live crossing speed (it was derived from recorded motion of 0.6–1.4 palm widths), or a dropped detection frame (§0.3: 2.9% lost under fast motion) leaves a stale track position. **Do not tune the ratio on this evidence** — per A10 that is a measurement question, and the cost of leaving it is currently zero. Quantify from the 0.2b sequences |
| N10 | **Camera frame rate is environment-dependent (lighting)** | infra/perception | **open — leading hypothesis, not diagnosed** | — | §0.7. Same recorder/camera/machine/resolution measured **24.09–24.14 fps at 19:13–20:51 and 15.1/15.77 fps at 22:18–22:19**. Leading hypothesis: webcam auto-exposure lengthening frame duration in dimmer light — **untested**. Consequences hold regardless of cause: (a) N7 becomes correctness — no single measured constant is valid; (b) recordings are only comparable to each other if fps is comparable, so **`meta.json`'s `measured_fps` must be checked before any cross-session A/B** under A10; (c) the DR-1 live test (§0.6) ran at an unmeasured frame rate. Cheapest probe: record the same sequence in bright vs. dim light and compare `measured_fps` |
| N11 | **Left/Right asymmetry in sign-cue reliability** | perception | **NOT REPRODUCED — direction REVERSED on clean single-hand takes (2026-08-03)** | — | **Tested and the claim did not survive.** Two matched single-hand `palm_back_s2_slow` takes (16 cycles each, no duplicate-label contamination): **Right 25% implausible, Left 41%** — the opposite of the two-hand result (Left 7%, Right 23%). **So the original asymmetry was most likely a TWO-HAND artifact, not a property of the chirality correction.** Do not act on the original hypothesis. ⚠ The retest has its own confound — the left take ran at 21.12 fps vs the right's 24.11, and a longer frame interval mechanically inflates implausible flips — so this **disproves the direction without establishing the reverse**. Settling it properly needs matched-fps single-hand takes. Clean side-result: **both hands hit 32/32 exactly on total flips** while carrying 25–41% impossible ones, reinforcing §0.8's headline. Original observation follows. §0.8 Finding 3. The Right hand's implausible-flip fraction exceeds the Left's at **every** speed in the sweep (24 vs 6, 23 vs 7, 41 vs 15, 58 vs 50 %), consistently across four independent takes — systematic, not noise. **Candidate hypothesis only**: the handedness-dependent chirality correction is the one non-handedness-symmetric step in the pipeline, and §13.6.1's inversion bug lived exactly there. Do not act on this without measuring; a clean test is to re-run the sweep one hand at a time |
| N12 | **Held cube jumps as the hand crosses the horizontal (pitch) plane** | pipeline | **observed live 2026-08-03, NOT fixed — third symptom of a known weakness** | 3.3 | **Operator report during the DR-2 live test**: *"when the hand crosses the horizontal plane, the cube jumps slightly because the landmarks of the fingers become confused and the cube likely aligns quickly with the position of the confused fingers, before restoring to the correct position when the hand has crossed."* **NOT caused by DR-2** — DR-2 only changes the palm/back sign, which gates snapping, and never touches a held cube's position. Pre-existing. **This is the THIRD independent symptom of the same root weakness**, alongside T4 (yaw/palm-sinking) and Object Jump Correction: §14.1's translation anchors on **5 fingertips + 4 MCPs**, and fingertips are measurably the worst landmarks on the hand — bone-length CV 13–32% distally vs a **palm already rigid to 2.76 mm** (§0.2 finding 1). Spec M8a predicted exactly this (*"Fingertips determine whether a grab occurred; they must not determine where"*, anti-pattern #6). A7 deferred M8a to an A/B rather than adopting it — **this observation materially strengthens the case for running that A/B (item 3.3), and gives it a third concrete failure to measure against.** Do not modify §14.1 before the A/B, per A7 |
| N13 | **Commercial release forbids non-commercial-licensed dependencies** | governance | **BINDING — owner decision 2026-08-04** | — | ⭐ **Check the licence BEFORE proposing any model or package, and state it in the proposal.** Apache-2.0 / BSD / MIT are fine; "research use only", "non-commercial", CC-BY-NC are not. The game is intended for commercial release, so this applies to **offline tooling too**, not only shipped runtime code. **This killed item 0.5** (MANO, and therefore HaMeR and WiLoR). ⚠ **It also constrains item 1.7, which the spec calls "MANO-lite" — do NOT build it with actual MANO.** 1.7 needs a skeleton with *fixed bone proportions*; published anthropometric proportions are free and sufficient (§2f itself says population-average proportions suffice to start). ⚠ Note the trap 0.5 walked into: a permissive licence on the **code** does not cover **data** it generates from research datasets — Hand-BMC-pytorch is MIT but derives its constraint values from RHD/GANerated/STB/FreiHAND |
| N14 | **The recorded corpus contains NO image data** | infra | **established by exhaustive scan 2026-08-04** | — | The whole capture root is **390 `.json` + 25 `.jsonl`, 334 MB, zero image/video bytes of any extension**; `imwrite`/`VideoWriter` appear nowhere in the codebase. Covers all four subfolders, including the richly-annotated `Unsuccessful_grip` / `Pencil_style_grip` pinch corpora and `Position_during_rotation` — **those annotate LANDMARKS, not images.** Consequence: **no image-based model can ever be run over the existing sessions retroactively**, so any such proposal must price in re-recording and operator camera time up front. `--save-frames` now exists (item 0.1) for takes recorded from 2026-08-04 onward |
| N15 | **`2026-08-02_191353_static_hold` has no `raw_landmarks.jsonl`** | infra | **observed 2026-08-04, not investigated** | — | The corpus is **29 session directories but only 28 usable**. The original `static_hold` take is an empty stub — it silently contributes nothing to any pooled metric, including §0.2's baseline. Not diagnosed; noted so a future "why is n smaller than expected" is not re-investigated from scratch. The 2026-08-04 `static_hold` retake supersedes it in practice |
| N16 | **Two 2026-08-04 takes contained an unrequested second hand** | infra | **found and metadata CORRECTED 2026-08-04** | — | `known_right_back` and `occlusion_finger_over_finger` were requested and recorded as `--hand right`, but a second, nearly motionless hand was in view throughout (two hands in essentially every frame, palm-x separated ~200 px and stable to within 3–15 px, **0 duplicate-label frames**). So the hands are genuinely distinct and correctly labelled — §0.8-finding-4 contamination did **not** occur and the takes remain usable — but `hands_used` has been corrected to `both` and per-hand analysis must separate them. **Effect on numbers: the bystander scores 0.00% in every take, so pooled rates are DILUTED** — `known_right_back`'s real figure is 5.12% for the hand under test, not the pooled 2.56%. ⚠ These two are therefore **not** a matched single-hand pair with the same day's `known_left_back`, so they do not settle N11. **Lesson: check the frame for a resting hand before starting a single-hand take** |
| N17 | **`RecordTranslationPivotDebug.py` SYNTHESISES its timestamps** | infra | **found 2026-08-04, not fixed** | — | ⚠ Every pivot take reports **30.33–30.45 fps** — suspiciously constant, and 1000/30.38 = **33 ms**, the exact synthetic cadence §0.3/N1 records older recorders using. **The real rate is ~24 fps**: a 40 s take produced 967 frames (24.2 fps real) which the fake cadence compresses to an apparent 31.9 s, and `jump_test4` claims 11.8 s for a 15 s recording. **Per-frame geometry is unaffected (B4's anchor A/B is safe), but ANY velocity-in-real-time analysis on pivot takes is wrong by ~25%** — including anything that reuses B3′'s windowed derivatives on this corpus. Fix: adopt `RecordPerceptionSequence.py`'s real monotonic `tCapture`. ⚠ **It also has no `--note` option**, so operator annotations have nowhere to live in the recording; the 2026-08-04 takes use `.notes.json` sidecars as a workaround. Add `--note` at the same time |
| N18 | **2026-08-04 daylight corpus additions** | infra | **recorded** | — | Perception (all full duration): `two_hand_overlap` 777 fr/25.96 fps, `two_hand_near_miss` 794/26.51, `yaw_sweep_constant_depth` 741/24.76, `known_right_back` 751/25.09. Pivot (cube held 100% of frames): `n12_pitch_crossing` 967 fr/11 cycles, `t4_yaw_hold` 953 fr/12 cycles. **⭐ N16 CLOSED** — `known_right_back` is genuinely single-hand, restoring the matched pair N11 needs. **⭐ The YAW axis is in the corpus for the first time** (9 cycles, operator confirmed the hand passed through to show the back, so `expected_sign_changes` = 18 is valid) — every prior rotation take is PITCH by design, which is why §14.3.1's palm-width-collapses-under-yaw claim could only be inferred. ⚠ Both two-hand takes **deliberately add rotation** vs the 2026-08-02 originals, because §0.4 established the identity mixup is caused by label instability under ROTATION, not occlusion — a harder test, so 0 jumps would be stronger evidence for T3, not weaker. Control separates cleanly: near-miss 0 one-hand frames, overlap 145 (18.7% occlusion) |
| **UNSCHEDULED / NOT QUEUED** ||||||
| U1 | Open-palm / closed-fist detection (row 2) | feature | **PARKED** | — | Priority decision, not only technical. 5.1 would help; still requires owner sign-off |
| U2 | Real 3D-file import (OBJ/glTF) | feature | **POSTPONED 2026-08-04 (owner) — blocked on a PLATFORM decision, not on effort** | — | §13.8; not blocking anything. ⚠ **Do not build this against the pygame renderer.** Owner reasoning: the import path depends on the eventual rendering platform (native WebGL, Three.js, or something else), so building it now would mean writing a loader for a renderer the product will not ship on. The current `_draw_object_3d` is a deliberate placeholder and is already **mesh-generic** (verified live by swapping in a non-cube mesh with zero code changes), so nothing is lost by waiting — the remaining work is a file parser, and which parser depends entirely on the target. **Revisit once the platform is chosen** (see U3), not before. Current focus is hand-detection quality, not rendering |
| U3 | Web/mobile port | platform | deferred | — | `HandState` v2 is the contract it reimplements against. ⭐ **Port-readiness discipline established 2026-08-04**: a module designated for the port gets **golden vectors BEFORE the port exists**, not after — see `analysis/verify_frame_rate_estimator.py` (and `verify_observability.py`, the precedent). **This is not ceremony: the very first run caught a real bug.** Python's `round()` is banker's rounding (half-to-even), JavaScript's `Math.round` is half-up, and the DR-1 dwells land exactly on `.5` at odd frame rates (500 ms × 13 fps = 6.5 frames) — Python gave 6, a JS port would have given 7, and nothing in normal testing would have surfaced it. Fixed in shared code via `hand_identity._round_half_up()`. **Reasoning about cross-language equivalence is not evidence.** Port units so far: `palm_observability`, `FrameRateEstimator` (47 dependency-free lines) |
| U4 | `PART_ONE.md` §7.4 dangling reference | docs | open | — | §3 cites §7.4 for `gesture_config.json`; that section does not exist |

## 4. Known wire-protocol gap (live pipeline, not recording)

The existing socket protocol (`VisionPipeline.py` → `Client.py` →
`PythonApp_Main.py`) currently sends only 2D pixel-space landmarks (21
points × 2 hands × `(x_px, y_px)` = 84 floats per `"hands"` packet) — no `z`,
no `world_landmarks`. Translation (step 5) only needs 2D image-space data,
so that part of the protocol doesn't need to change. But since §1's revision,
**gesture classification needs `world_landmarks`**, which the live socket
protocol doesn't carry yet — originally this gap was only flagged for step 7
(rotation), it now also blocks wiring the tuned pinch classifier (step 2/3)
into the live pipeline.

This does **not** block recording or analysis, though: `RecordSession.py`
(§7) captures `world_landmarks` directly from the in-process MediaPipe
`HandLandmarker` result, bypassing the socket entirely — recording and
offline analysis can proceed with today's protocol unchanged. The wire
extension is only needed at the point where the *tuned* classifier gets
wired into `HandsTriggeredActions.py` for live use. Extend `VisionPipeline.py`
/ `Server.py` to send `world_landmarks` then, not before.

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

## 6. Pinch classifier design basis (state-of-the-art check, 2026-07-30)

*(§6–§8: historical record of the abandoned rule-based approach — see the
banner at the top of this file. Kept for the evidence trail, not as a
description of current code.)*

Researched before building, since a naive single-distance threshold is not
what production implementations actually use. Findings, and how they shape
the design:

- **Distance alone false-positives on a fist.** Common practice (e.g.
  MediaPipe-based tutorials, GRLib) checks `distance(thumb_tip, index_tip)`
  **and** confirms the other three fingertips are *not* also curled in
  (middle/ring/pinky tips below their MCP joints) — otherwise a closed fist
  reads as a pinch too, since thumb and index end up close together there
  as well. Folded into row #2's detection logic above as a required
  conjunct, not an optional refinement.
- **Ratio-normalize by a hand-size reference**, not a raw distance — this
  is the single biggest accuracy lever per Specification.md §6, and it's
  also what makes the classifier resolution/distance-independent, which is
  the whole point of moving off pixels (§1).
- **A learned classifier (small MLP / SVM / XGBoost on landmark-derived
  features, or MediaPipe's own embedding+classification-head architecture)
  is the state-of-the-art direction for larger gesture vocabularies**, and
  several papers report strong results this way. Not adopted now —
  Specification.md §7.1 already recommends starting rule-based and only
  reaching for a learned model if rules prove insufficient, and nothing
  here contradicts that. But recording full labeled landmark data (§7),
  not just derived ratios, means today's sessions could train a small
  classifier later with **no recapture needed** if rules turn out
  insufficient — free optionality, not a plan change.
- **DTW/HMM/sliding-window+LSTM are for genuinely dynamic gestures**
  (swipe, twist trajectories), not a static pose like pinch. Confirms
  rather than changes the matrix's existing plan (row #7's dynamic
  gestures already deferred, sliding-window only if static rules prove
  insufficient — Specification.md §7.1).
- **4–6 landmarks is enough** per several papers — matches row #2 above
  (thumb tip, index tip, wrist, middle MCP, plus the three other
  fingers' MCP/PIP/tip for the uncurl check — nowhere near all 21 points).
- **Curl is a joint angle, not a wrist-relative distance ratio** — refined
  after an XR-SDK literature check (Meta Horizon OS, Unity XR Hands):
  production hand-tracking curl features use the angle at the PIP joint
  (`angle(MCP→PIP, PIP→tip)`, small = straight, large = curled), not a
  `distance(wrist, tip) / distance(wrist, MCP)` ratio. `GestureRules.py`
  implements both (`finger_curl_angle_deg`, `finger_extension_ratio`) so
  the analysis script could compare them empirically rather than assuming
  which is better — see §7's result.
- **Otsu's method (Otsu, 1979)** — a standard automatic-thresholding
  algorithm from image binarization, generalized here to any 1D bimodal
  distribution — is the principled way to split `pinch_x3`'s frames into a
  pinching/released cluster without per-frame labels, rather than an
  ad-hoc "biggest gap" heuristic. Used in `AnalyzeRecordings.py` (§7).

### 6.1 Derived result (2026-07-30, `AnalyzeRecordings.py` against 2× `pinch_x3` + `fist` + `open_hand`)

- **`pinch_ratio` threshold = 0.371`** (Otsu split of `pinch_x3`'s own
  distribution — the value is the boundary between a 56-frame low/pinching
  cluster and a 184-frame high/released cluster).
- **`pinch_angle_deg` was tested but not adopted** as a required condition:
  its own Otsu split produced a much larger, misaligned cluster (143 of 240
  frames — implausibly high for a signal meant to isolate brief pinch
  moments) versus `pinch_ratio`'s 56, indicating it responds to more than
  just the pinch action (likely overall hand orientation during the
  cycle). `pinch_angle_deg()` is still computed and available in
  `GestureRules.py` for future re-evaluation, just not required by
  `is_pinching()`.
- **Other-fingers-uncurled gate: curl angle, percentile-based, not a clean
  min/max split.** Even restricted to the 56 frames `pinch_ratio` confirms
  as genuinely mid-pinch, the *worst* (most-curled) of middle/ring/pinky
  sometimes reached fist-like curl values — a per-finger breakdown showed
  this wasn't one specific finger misbehaving, all three showed some tail
  overlap with `fist`. Read as either brief transition frames near the
  ratio decision boundary, or genuine finger coupling (thumb+index closing
  measurably drags the other fingers somewhat — documented in hand
  biomechanics literature, not unique to this data). Chasing a zero-overlap
  split on 2 recordings would be overfitting, not rigor — so the threshold
  is the **90th percentile of confirmed-pinch `curl_worst_deg`, = 112.965°**
  (accepts the top 10% of true-pinch frames failing the gate, in exchange
  for a threshold that generalizes past this one session).
- **Measured result**: `pinch_ratio < 0.371 AND curl_worst_deg < 112.965°`
  together produce **0/117 false positives on the recorded `fist`
  session** (actually measured, not assumed from the two gates
  separately).
- **Gap found, not yet closed: 9.2% (11/120) false positives on
  `open_hand`.** `open_hand` wasn't part of the threshold derivation (only
  `fist` was used as the adversarial stress test, per §6's original
  reasoning) — running the finalized `is_pinching()` back over all four
  recordings as a sanity check surfaced this. Likely a *relaxed* open hand
  occasionally lets thumb and index drift closer than a deliberately
  splayed one. Not fixed yet — see §7's open items.

## 7. Recording & analysis workflow

**Tool**: `Local_pc/Python_Server_MediaPipe_vision_pipeline/RecordSession.py`,
run via `Local_pc/Movement_with_hand_detection/record.bat <label>
[duration_seconds]` (reuses that folder's `.venv` — run `launch.bat` at
least once first if it doesn't exist yet). Standalone: opens the webcam
directly, runs MediaPipe `HandLandmarker` in `VIDEO` mode. **Recording is
timed, not keypress-stopped** — a 3s on-screen countdown gives time to get
hands in frame, then capture runs for `duration_seconds` (default 4s) and
stops automatically. No keypress needed once it starts, since both hands
are busy performing the gesture, not at the keyboard — closing the preview
window is still available as an early abort if needed. Every captured frame
— both hands' `handedness`, normalized `landmarks`, and `world_landmarks`
(Specification.md §6 schema) — is saved to
`Local_pc/Python_Server_MediaPipe_vision_pipeline/recordings/<label>_<timestamp>.json`.
No cube window, no socket — independent of the live pipeline (§4).
`recordings/` is gitignored (raw capture data, not source).

**Session convention**: one label per whole session (§1's revision from an
earlier held-pose-only plan) — cyclic gestures like pinch are recorded as
the gesture repeated ~3 times within one session (neutral → pinch → release,
×3), so the transition dynamics show up multiple times per file, not just a
single static hold. Static baselines (open hand, fist) are a single held
session, no repetition needed.

**Sessions recorded so far**: 2× `pinch_x3` (60 frames each), 1× `fist`
(60 frames), 1× `open_hand` (60 frames) — all with both hands detected
throughout. `near_pinch` (fingers close but not touching, a deliberate
boundary stress test per the original recording-set plan) not recorded yet.

**Analysis**: built — `Local_pc/Movement_with_hand_detection/AnalyzeRecordings.py`.
Loads every session from `recordings/`, computes `pinch_ratio`,
`pinch_angle_deg`, per-finger curl angles, and per-finger extension ratios
per hand-frame (via `Resources/GestureRules.py`), prints full distributions
per label, runs the Otsu split described in §6.1, cross-checks against
`fist`/`open_hand`, and prints recommended thresholds with the actual
measured false-positive counts (not estimates). Re-run it
(`.venv\Scripts\python.exe AnalyzeRecordings.py`) any time more sessions are
added — thresholds should be re-derived, not hand-adjusted.

**Open items surfaced by this pass** (not yet resolved):
- **`open_hand` false-positive root cause found (2026-07-30 debug pass)**:
  all 11 false positives are on the **left hand only**, in three brief
  ~66–99ms bursts (frames 17-20, 31-33, 45-48 — roughly evenly spaced,
  not random scatter). Curl values throughout stay comfortably in the
  extended range (72–82°, nowhere near the 112.965° threshold) — the curl
  gate is working correctly; it's specifically the thumb-index ratio that
  periodically narrows (down to 0.212) on an otherwise genuinely open,
  relaxed left hand. Likely natural resting-hand thumb drift, not a
  tracking artifact (the rhythmic spacing argues against random jitter)
  and not a fist-confusion case.
  - **Debounce alone won't cleanly fix this**: checked contiguous
    `is_pinching()`-true run lengths in the `pinch_x3` recordings —
    genuine pinch holds run only 3–5 frames (~100–165ms), i.e. *the same
    order of duration* as the false-positive blips. A simple "require N
    consecutive frames" filter would either still catch the blips (if N is
    small enough to keep genuine fast pinches) or reject real pinches (if
    N is large enough to exclude the blips) — the current data doesn't
    support a clean duration cutoff either.
  - **Practical mitigation that already exists**: grab acquisition (matrix
    row #3) is proximity-gated, not pinch-alone-gated — a relaxed hand
    that isn't near any cube can't spuriously grab one no matter how the
    raw pinch signal flickers. This softens the real-world impact
    considerably; don't over-fit the threshold chasing this artifact from
    one small recording before row #3 exists to actually test against.
  - **If still a problem once row #3 is live-tested**: record pinch
    sessions with slower, more deliberate holds (longer `--duration`,
    fewer cycles) so genuine pinches are unambiguously longer than
    incidental drift, making a duration debounce viable; and/or record a
    second `open_hand` baseline with fingers explicitly fanned apart to
    see if that removes the drift (would confirm it's a relaxed-hand
    posture effect, not inherent to this classifier).
- `near_pinch` session still not recorded — would sharpen exactly where the
  0.371 ratio boundary should sit, rather than relying on `pinch_x3`'s own
  release-phase frames as the only "not pinching" reference for that
  threshold.
- Only one person's hand in this data (2 sessions worth of `pinch_x3`) —
  thresholds are a starting point for live tuning against `is_pinching()`,
  not a final calibration.

### 7.1 Live debug tool (§8 step 4)

**Tool**: `Local_pc/Movement_with_hand_detection/LiveGestureDebug.py`, run
via `debug_gestures.bat` in the same folder (or `--duration <seconds>` for
a bounded, non-interactive run). Standalone — no socket, no cube window —
opens the webcam directly and overlays each detected hand's gesture status
on a preview window (`PINCH *` when active), logging to the console on
each detection's rising edge rather than every frame. `GESTURES` is a
`{display_name: classifier_function}` dict — adding a future gesture here
is a one-line addition, the loop itself doesn't change.

**Integration bug found and fixed while building this (2026-07-30)**:
`GestureRules.py`'s functions were only ever exercised against
JSON-loaded landmark dicts (`{"x", "y", "z"}`, the shape
`RecordSession.py` writes) via `AnalyzeRecordings.py` — never against
MediaPipe's native live result objects, which expose `.x`/`.y`/`.z` as
attributes, not dict keys. First live run crashed on this
(`TypeError: 'Landmark' object is not subscriptable`). Fixed at the call
site (`_to_dict_landmarks()` converts before calling any classifier) rather
than making `GestureRules.py` polymorphic over two landmark shapes — keeps
the classifier functions' data contract single and simple. **Lesson for
future gestures**: a classifier that's only been tested against recorded
JSON hasn't been tested against the live data path at all — step 4 isn't
optional polish, it catches integration bugs step 3 structurally cannot.

**First live smoke test (bounded 12s run)**: 8 `PINCH` detections logged on
the right hand, no crash, clean shutdown. Not yet a full interactive
session — that's next, checking both hands and specifically trying to
reproduce the `open_hand` left-hand flicker (§7's open items) live.

### 7.2 Interactive live testing found a bigger gap: rotation (2026-07-30)

Live testing (§7.1) surfaced what the recorded-data analysis couldn't:
static single-frame geometry is fundamentally ambiguous under hand
rotation, and doesn't generalize across hand orientation at all.

**Observed live**: (1) pinch detection works well with hands in
roughly the same position/orientation as the recordings; (2) rotating the
hand triggers pinch detection randomly; (3) palm-up (not represented in any
recording) doesn't detect pinches at all.

**Quantified**: ran `is_pinching()` (the static classifier) against a new
`rotating_hand` baseline (hand moving/rotating, no pinching, recorded via
`RecordSession.py --label rotating_hand --duration 6`) — **38.5% false
positives overall, 62.2% on one hand**. Confirms this isn't a minor edge
case.

**Why, per a literature check**: a pinch is inherently a *transition*, not
a fixed pose — a static geometric snapshot can't distinguish "thumb and
index happen to be close right now" (which many rotated, non-pinching hand
configurations produce incidentally) from "thumb and index are closing
together" (the actual pinch action). A robust VR-controller pinch-detection
paper (AtaTouch) uses closing *velocity* — not just distance — as a core
signal, plus a ~100ms temporal-persistence check to reject transient noise.

**Redesign — `PinchTracker` / `is_pinching_from_window` in
`GestureRules.py`**: a windowed detector requiring both the static gates
(ratio + curl, unchanged) **and** a recent closing motion (`pinch_ratio`
decreased by at least `DEFAULT_VELOCITY_THRESHOLD` = -0.05 over a
`PINCH_WINDOW_FRAMES` = 5-frame / ~165ms window). This is the one place
state enters the module — `PinchTracker` is a thin rolling-buffer wrapper
around the pure `is_pinching_from_window` function (Specification.md §7.1
already anticipated dynamic gestures needing a sliding window; pinch just
needed it sooner than planned). `is_pinching()` (the static-only version)
is kept as a building block and for static-geometry analysis, with its
limitation documented in its own docstring — **not used for live
detection anymore**.

**Validated against all 5 recorded sessions, in temporal per-hand order**
(`ValidateWindowedClassifier.py` — unlike `AnalyzeRecordings.py`'s pooled
analysis, this preserves frame adjacency, which a velocity feature needs):

| Session | Hand | Static | Windowed |
|---|---|---|---|
| `rotating_hand` | Right | 62.2% | **22.2%** |
| `rotating_hand` | Left | 14.6% | 10.1% |
| `open_hand` | Left | 18.3% | **18.3% (unchanged)** |
| `pinch_x3` (×2, true positives) | both | 16.7–25.0% | 13.3–20.0% (some loss) |

**Real progress, not a full fix — and the reason why matters more than the
numbers.** Inspected the `open_hand` left-hand blip directly: `pinch_ratio`
drops from 0.546 → 0.212 → back to 0.543 within ~6 frames (~200ms) — a
genuine, complete closing-and-reopening motion, not static noise. It has
the velocity signature of a real pinch **because it structurally is one** —
an unintentional but real fast hand motion. Velocity alone can't
distinguish it from a genuine pinch because the reference `pinch_x3`
recordings are themselves very fast: 3 cycles in 4 seconds means real pinch
holds only last 3–5 frames (§6.1's contiguous-run-length finding) — right
in the same range as this incidental blip. **The two classes overlap in
timing because the training data doesn't have a clean timing signature to
key off of, not because the velocity approach is wrong.**

**Next step (not yet done)**: re-record `pinch_x3` (or a new, explicitly
slower variant) with deliberate, sustained holds — e.g. ~300–500ms per
hold, not a rapid ×3-in-4-seconds cadence — so genuine pinches have an
unambiguous duration to detect against. Re-deriving `DEFAULT_VELOCITY_THRESHOLD`
and `PINCH_WINDOW_FRAMES` against fast-cadence data would be overfitting
to a dataset that structurally can't support the separation; the recording
protocol needs to change, not just the threshold.

## 8. General gesture classifier development workflow (apply to every future gesture)

Established while building pinch (§6–§7 are the worked example) — this is
now the standard procedure for adding **any** new gesture to §3's matrix,
not pinch-specific process notes. Four steps, always in this order:

1. **Record several automatic sessions**: the target gesture itself (cyclic
   gestures as repeated cycles per session, e.g. ×3, static poses as one
   held session — §7's convention), **plus several baseline/negative
   sessions** covering poses that could plausibly be confused with the
   target gesture. Which baselines to record is decided by step 2, not
   guessed — `fist` was recorded for pinch because the literature flagged
   it as the specific confusable pose, not because it seemed like a
   reasonable default. Use `RecordSession.py` (§7): timed/auto-stop, no
   keypress needed since both hands are busy performing the gesture.
   **Camera-in-front for now.** The same recording set gets repeated later
   with a forward/outward-facing camera once the project moves toward the
   glasses use case (Specification.md §12) — camera orientation is a
   variable to eventually test empirically, not assumed to transfer
   unchanged from the front-facing data. **Also record a baseline of the
   hand moving/rotating through varied orientations without performing the
   gesture** (§7.2's `rotating_hand` finding) — a static single-frame
   classifier is ambiguous under rotation almost by construction, and this
   is the cheapest single session to catch it early rather than live.
   **Cadence matters if the classifier will use velocity/timing at all**
   (§7.2): recording a cyclic gesture too fast (e.g. 3 reps in 4 seconds)
   makes genuine holds barely longer than incidental micro-movements,
   destroying exactly the timing signal a velocity feature needs — record
   deliberate, sustained reps unless the real target gesture is
   itself meant to be that fast.
2. **Benchmark the classifier strategy against state-of-the-art literature
   *before* computing anything.** As done for pinch (§6): what
   features/thresholds/algorithms do existing implementations and papers
   use for this gesture or a close analog? This is what surfaces the right
   feature set (e.g. §6's curl-angle vs. distance-ratio finding) and the
   specific confusable poses step 1 needs baselines for — the fist
   false-positive risk was *found* this way, not guessed after the fact.
   Don't skip straight to recording without it.
3. **Compute the classifier from the recorded data.** Derive thresholds
   empirically — Otsu's method for unlabeled bimodal cyclic-gesture data
   (§6.1), percentile-based margins where a clean min/max split doesn't
   exist, cross-validated against the negative baselines with *actually
   measured* false-positive counts, not assumed ones. `AnalyzeRecordings.py`
   (§7) is the reference implementation for pinch; extend it (or add a
   parallel analysis script) for each new gesture using the same method,
   not a different ad-hoc one each time.
4. **Live debug tool.** Run the camera live and display "gesture X
   detected" in real time (`LiveGestureDebug.py`) before wiring the
   classifier into the actual grab/release pipeline (matrix row #3+). This
   is the step that catches what a small recorded dataset can't — e.g. the
   `open_hand` false-positive gap (§6.1) was only found by running the
   finalized classifier back over the recordings as a sanity check; a live
   tool makes that kind of check immediate and visual instead of a
   one-off script run.

Don't skip a step because a gesture "seems simple" — pinch looked simple
too. Step 4 in particular is what catches what steps 1–3 miss on a small
dataset; treat thresholds from steps 1–3 as a starting point for step 4's
live tuning, not a final answer.
