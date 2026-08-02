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
  jitter), **or** loss of hand tracking. Either way: cube freezes in place at
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

| # | Item | Kind | Status | Depends on | Notes |
|---|---|---|---|---|---|
| **PHASE 0 — instrumentation** ||||||
| 0.2 | M0 baseline metrics on current pipeline | perception | **DONE 2026-08-02** | — | `AnalyzePerceptionBaseline.py`, 7 existing recordings, no new capture. **Bone CV 10.0% vs <3% target; palm rigidity 2.76 mm already at target; DR-2 validated (41.5× flip concentration, 0 flips above edge-on 0.60).** Results: `PERCEPTION_LAYER_SPEC.md` §0.2 |
| 0.1 | M0 recorder/replay/metrics harness | perception | **NEXT** | — | Generalise `RecordTranslationPivotDebug.py` / `AnalyzeTranslationPivot.py` / `AnalyzePerceptionBaseline.py`; add `tCapture`, optional frame capture |
| 0.2b | Record the §7.2 scripted sequences | perception | **7 takes DONE 2026-08-02 (§7.2 is 10 rows, not 9)** | — | `RecordPerceptionSequence.py` (raw capture, no gesture logic) + `AnalyzePerceptionSequences.py`. **Done (verified on disk 2026-08-02):** static_hold, non_crossing, pitch_sweep_slow, pitch_sweep_fast, two_hand_crossing, two_hand_overlap, two_hand_near_miss. **Results corrected §0.2 — see §0.3.** *(This line previously read "4 of 9" — stale: it was not updated when §0.4's three two-hand takes were recorded, and the count also disagreed with §7.2's actual 10 rows.)* **`palm_back` recorded then DELETED 2026-08-02** — both takes (the counted one and an aborted one) discarded on owner instruction because they ran at 15–16 fps in poor light: *"I don't want the lack of light to pollute our analysis."* Their numeric result is **indicative only, data gone** (§0.7). **REPLACED by four speed-decoupled takes** — `palm_back_s1_very_slow` / `s2_slow` / `s3_medium` / `s4_fast`, built into the recorder with **prescribed** cycle counts (10/15/20/30 → 20/30/40/60 expected sign changes), **PITCH axis** stated explicitly, and a `<20 fps` warning at save time (§0.7.1). **Remaining: the four `palm_back_s*` takes, `occlusion`, `depth_sweep`, fiducial grabs, direction reversals (= item 0.3), free manipulation.** Note `non_crossing` is an extra take serving M0's chirality-flip metric, not a §7.2 row |
| 0.3 | §6.2 end-to-end latency measurement | perception | queued | — | Manual, needs a 240 fps phone; instrument socket IPC separately (extra stage vs. the spec's table) |
| **PHASE 1 — kill the singularities** ||||||
| 1.1 | **M5d `K` fixture test** | perception | **queued — do first** | 0.1 | Hours, not days. Guards the exact production-only inversion bug shipped 2026-08-01 (§13.6.1). Recordings already exist |
| 1.2 | M5a `edgeOnMeasure` (recover `\|s\|`) | perception | queued | — | Signed area itself is **already built** (`_is_thumb_outward`); only the magnitude is being discarded |
| 1.3 | M6a verify no Euler in estimation path | perception | **already satisfied** | — | Tick and move on — quaternions since day one, §2 forbids Euler |
| 1.4 | M2 bone-length calibration | perception | queued | — | Hard prerequisite for Z-axis control. **§0.3 corrects the rationale**: held still, bone CV is already 0.9–1.1% (inside target) — the 10% figure is motion/rotation-induced, not a sensor floor. So calibration is EASY (gate on low motion), but **the bone residual is a weaker M4 error signal than assumed — it reports "the hand is rotating", not "landmark 8 is bad", and must be pose-normalised** |
| 1.5 | M3a hard anatomical constraints | perception | queued | 1.4 | Unidirectional-flexion prior breaks bas-relief ambiguity |
| 1.6 | M4 precision weighting + χ² gating | perception | queued | 1.4 | Hard prerequisite for unsnap. **Verify against `jump_test4`** |
| **PHASE 2 — temporal identity** ||||||
| 2.1 | M5c DR-1 chirality lock | perception | **DONE — delivered early as N5, LIVE-CONFIRMED 2026-08-02** | 1.1 | Built ahead of Phase 2 because Object Jump Correction needed it. Live-tested against a camera 2026-08-02 (spec §0.6): operator verdict "it's working", 16 tracker events, 0 errors, and both the glitch-rejection and switch branches fired correctly. Remaining: drive `_ASSUMED_FPS` from measured timing instead of the hard-coded 24.0 (N7); reconcile with M4's quality gates |
| 2.2 | M5e DR-2 edge-on band | perception | queued | 1.2, 2.1 | **Validated and its threshold SETTLED 2026-08-02** (§0.2 + §0.3): `non_crossing` gave **0 flips in 723 frames** with edge-on never below 0.353, so the 0.15 band is never entered in normal use — but 4.6–8.0% of normal frames fall below 0.60, so **raising the threshold toward 0.60 is contraindicated**. Keep 0.15. Reconcile with rule 3's armed-exception state machine |
| 2.3 | M6b–e quaternion UKF, anisotropic covariance | perception | queued | 2.1 | **Deleting `HandOrientationFilter` is a deliverable** (A6). Re-verify chirality if the frame construction changes |
| **— REASSESS (owner decision point) —** ||||||
| R | Re-measure all M0 metrics; re-test Object Jump Correction; decide whether Phase 3 precedes feature work | — | gate | 2.3 | |
| **PIPELINE TODOs — expected to close in Phases 1–2** ||||||
| T1 | Back-of-hand rotation quality | pipeline | open, 4 attempts | 2.1, 2.3 | §13.7. Was "likely a monocular floor"; M6c's anisotropic covariance is the untried mechanism |
| T2 | Pitch-plane crossing | pipeline | partly fixed | 2.2, 2.3 | §13.7. M6a already satisfied; M6c + DR-2 are the remainder |
| T3 | **Object Jump Correction** | pipeline | **FIXED by DR-1, live-confirmed 2026-08-02 — but NOT yet closed by measurement** | 2.1 (+ N5 now) | **Live test passed** (spec §0.6): the symptom did not occur while the operator actively tried to provoke it. **The M0 regression metric is still unmeasured** — "2 jumps → 0" needs a fresh recording replayed through `AnalyzePerceptionBaseline.py`, which a live test does not produce. Per A10, measurement is what closes this, so it stays open. Root-cause account follows. **Not two-hand confusion** — a matched near-miss control produced 0 events despite 28.6% occlusion in the overlap take. Actual cause: **MediaPipe's handedness LABEL is unstable under rotation** — flips on a single hand (18 events in `pitch_sweep_fast`, at score 0.663 vs 0.95–0.99 baseline) and **duplicate labels** (both hands labelled the same: 4/9/12 frames). Ownership is keyed by handedness, and `extract_hand_by_type` returns the first match or nothing → wrong hand claims the cube, other hand reads as not-detected → tracking-loss drop. **DR-1 is now the primary fix; M4's χ² gate demoted to belt-and-braces.** Regression metric: 2 jumps in the old baseline → 0 |
| T4 | Yaw / palm-sinking in translation | pipeline | deferred | 1.4, 1.2, 4.1 | §14.1.1. **Newly mapped** (A8): M9's foreshortening correction is the concrete fix its "startup calibration" note gestured at |
| **PHASE 3 — latency and grab** ||||||
| 3.1 | M7 dual-pathway + forward prediction | perception | queued | 0.3, 2.3 | Retires `ROTATION_SLERP_FACTOR` into the FORM channel |
| 3.2 | M8b RTS retrospective smoothing | perception | queued | 2.3 | **Additive** to §14.1 — not blocked by the M8a deferral |
| 3.3 | **M8a A/B vs. §14.1** | decision | queued | 2.3, 4.1 | A7. Measure grab-placement **accuracy**, not just jitter. Do not touch §14.1 before this |
| 3.4 | M8c predictive grasp onset | perception | **blocked** | 4.3 | Today's snap is proximity-based; aperture enters the design only with §14.2 |
| **PHASE 4 — unlock the features** ||||||
| 4.1 | M9 metric depth | perception | queued | 1.4 | Refines §14.3's ratio design: never a single bone; foreshortening-corrected |
| 4.2 | **Z-axis translation (§14.3)** | feature | designed, not built | 4.1 | Open: what happens to 3D snap gating when `depthValid` is false — undecided |
| 4.3 | M10 commitment dynamics | perception | queued | 1.6 | **M10.7 changes `GAME_RULES.md` rule 2** (immediate drop → 400 ms grace) — raise with owner first |
| 4.4 | **Hand-open release trigger (§14.2)** | feature | designed, not built | 4.3 | The sole active release plan since closed-fist was parked |
| **PHASE 5 — optional** ||||||
| 5.1 | M3b synergy subspace | perception | optional | 1.5 | May make parked row 2 viable again — **do not un-park without asking** |
| 5.2 | M3 IK (26-DOF) | perception | optional | 5.1 | Subsumes 3a/3b, costs more |
| 5.3 | Trajectory gesture classification | perception | optional | 5.1 | |
| **NEW — surfaced by the 0.2/0.2b measurements** ||||||
| N1 | Re-express all frame-count parameters in ms | perception | queued | — | §0.3: pipeline runs at **~24 fps, not 30** (older recorders synthesised a 33 ms cadence, hiding this). M5e's 3-frame dwell, M10's 3/4-frame dwells and M4's 8-frame coast are all ~38% longer in wall-clock than intended |
| N2 | Pose-normalise the bone residual before M4 consumes it | perception | queued | 1.4 | §0.3: the raw residual tracks hand rotation, not per-landmark quality; used directly it would down-weight every landmark whenever the hand moves |
| N3 | Counted-crossing sequence → **speed-threshold sweep** | perception | **REDESIGNED, data discarded, re-record in daylight (2026-08-02)** | — | §0.7 + §0.7.1. **The recorded take was DELETED** (15.77 fps, poor light) — its numbers are indicative only and the data is gone. **Superseded by four speed-decoupled takes** with prescribed cycle counts and explicit PITCH axis, which locate the *threshold* at which crossings start being missed rather than yielding one blended count. **Indicative prior result (unsupported, do not cite as measurement)**: 29 cycles = 58 expected sign changes, detected **52 (Left) / 50 (Right) — UNDER-detection, not an excess**, which **reverses** the prior working suspicion of a large spurious population. **⚠ Unit trap, recorded because it caused a wrong reading once**: the operator counts palm→back→palm as ONE crossing; the analyser counts sign inversions. Compare against `expected_sign_changes` (58), never `counted_crossing_cycles` (29). **Still open**: totals cannot rule out a compensating mix of missed genuine crossings plus spurious flips — that needs per-flip matching against the rotation timeline. **Also confounded by N10**: this take ran at 15.77 fps, so the 63.4 ms interval makes genuine band-traversing crossings easier. **Re-record in better light before concluding.** Original note: §0.3 flagged the slow-sweep flips at edge-on 0.58–0.73 as suspicious, not diagnosed |
| N4 | External capture drive is unreliable | infra | **open** | — | E: dropped out ~4× in 15 min on 2026-08-02 (reads and writes both, WinError 21). Recorder now preflights and refuses rather than losing a completed take; analyser retries. Check cable/port and USB power-management, or switch to `--local` capture |
| **N5** | **DR-1 track-level hand identity (hysteresis)** | perception | **DONE — built, replay-verified AND LIVE-CONFIRMED 2026-08-02** | — | **Live test passed (spec §0.6)**: operator verdict "it's working" while deliberately rotating hands back-to-camera and crossing them; 16 tracker events, 0 errors/tracebacks; the transient-glitch branch held a 3-frame mismatch and the swap branch switched on a full 12 — the exact separation replay predicted. Original build account follows. §0.4/§0.5. A first stateless duplicate-resolver was built and **removed the same day** — score-based choice was a coin flip on 36% of frames and blind to 28 label flips. Replaced by `_HandIdentityTracker` in `hands_visualizer.py`: associate by **position** not label; lock after a vote; brief mismatch → hold, **long + confident mismatch → switch**; re-decide freely when a track ends. **A 'never switch' variant was tried and disproved** — position association swaps identities at a crossing, giving 528 overrides in runs of up to 225 frames. Replay result: duplicates **25 → 0**, longest wrong-hold **225 → 10 frames**, and **0 overrides/switches in all three control sequences**. This IS queue item 2.1 delivered early. **`SWITCH_MS` (12 frames/~500 ms) is TUNABLE — latency vs. false-glitch; re-derive if camera/fps/lighting change (spec §0.5)** |
| **N6** | **DR-1 parity: debug tool now shares the perception code** | infra | **RESOLVED 2026-08-02** | — | Was: `LiveSnapDebug.py` bypassed `hands_visualizer.py`, so DR-1 was production-only. Fixed the architecturally correct way per owner instruction ("I do not want to have a debug tool which is not in tune with the production"): the tracker was **extracted to `Resources/hand_identity.py`** — standalone, pure stdlib, no cv2/mediapipe/window side effects — and is now **imported by both**, not copied. `LiveSnapDebug.py`'s own latent duplicate bug (it keyed hands by handedness in a dict, silently overwriting one of a duplicate pair — the same defect that hid Object Jump Correction in the old recorder) was fixed in the same change. **Verified: production and debug produce byte-identical identity output across all 7 recorded sessions**, and exactly one tracker definition exists in the codebase |
| N7 | Drive `ASSUMED_FPS` from measured frame timing | perception | **PROMOTED — correctness, not tidiness (2026-08-02)** | 0.1 | **§0.7: frame rate is environment-dependent, not a fixed ~24** (15.1/15.77 fps measured at 22:18 vs 24.09–24.14 earlier the same evening). `SWITCH_FRAMES = round(500 × 24/1000) = 12`, so at 15.77 fps the dwell is **~761 ms instead of 500** — a 52% overshoot in the one parameter §0.5 flagged as most worth getting right. Original note follows. Hard-coded 24.0 in **`Resources/hand_identity.py`** (moved there from `hands_visualizer.py` when the tracker was extracted — N6); all DR-1 dwell constants derive from it, so a different camera silently changes every threshold. Should come from `HandState.tCapture` |
| N8 | **Cube can be stolen by occluding the holding hand** | gameplay | **recorded only — not being fixed now** | 4.3 | Observed 2026-08-02. Hand A holds a cube; hand B moves in front of it; A's tracking is lost, rule 2 releases the cube, and B — which is right where A was, so inside the grab radius — snaps it a frame or two later. **Mechanism inferred from the rules, not instrumented.** §13.5's same-frame ordering fix only blocks re-snap on the SAME tick, not the next. Expected to resolve as a side effect of refining snap control: **M10.7's grace period would hold the cube through the occlusion, leaving nothing to steal**. Recorded so it isn't rediscovered as a new bug |
| N9 | **DR-1's duplicate-repair fallback fires in normal live use** | perception | **observed 2026-08-02, NOT diagnosed — deliberately not tuned** | 0.2b | Spec §0.6. §0.5 reported duplicates eliminated **structurally**, and the end-of-function invariant was described as a fuzz-found edge case reachable only when a detection jumps past `MAX_ASSOC_PALM_RATIO = 3.0` with both track slots full. It fired **3× in one short live session**. **No duplicate was emitted — the invariant did its job, which is why the live test passed** — but the frequency is new information the 7 recorded sessions did not predict. Two candidate causes, undiagnosed: the association limit is too tight for live crossing speed (it was derived from recorded motion of 0.6–1.4 palm widths), or a dropped detection frame (§0.3: 2.9% lost under fast motion) leaves a stale track position. **Do not tune the ratio on this evidence** — per A10 that is a measurement question, and the cost of leaving it is currently zero. Quantify from the 0.2b sequences |
| N10 | **Camera frame rate is environment-dependent (lighting)** | infra/perception | **open — leading hypothesis, not diagnosed** | — | §0.7. Same recorder/camera/machine/resolution measured **24.09–24.14 fps at 19:13–20:51 and 15.1/15.77 fps at 22:18–22:19**. Leading hypothesis: webcam auto-exposure lengthening frame duration in dimmer light — **untested**. Consequences hold regardless of cause: (a) N7 becomes correctness — no single measured constant is valid; (b) recordings are only comparable to each other if fps is comparable, so **`meta.json`'s `measured_fps` must be checked before any cross-session A/B** under A10; (c) the DR-1 live test (§0.6) ran at an unmeasured frame rate. Cheapest probe: record the same sequence in bright vs. dim light and compare `measured_fps` |
| **UNSCHEDULED / NOT QUEUED** ||||||
| U1 | Open-palm / closed-fist detection (row 2) | feature | **PARKED** | — | Priority decision, not only technical. 5.1 would help; still requires owner sign-off |
| U2 | Real 3D-file import (OBJ/glTF) | feature | not started | — | §13.8; not blocking anything |
| U3 | Web/mobile port | platform | deferred | — | `HandState` v2 is the contract it reimplements against |
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
