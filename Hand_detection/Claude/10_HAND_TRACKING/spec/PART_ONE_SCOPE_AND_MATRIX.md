<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 62-222
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PART_ONE.md lines 1141-1157
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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

<!-- VERBATIM-END -->
