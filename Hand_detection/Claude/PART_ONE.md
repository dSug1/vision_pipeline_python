# Part One — gesture/pattern recognition design & matrix

> ⭐ **§3.1 IS THE SINGLE BUILD QUEUE FOR THE WHOLE PROJECT.** If you are here to
> find out what to build next, go to §3.1's "YOU ARE HERE" block. For the map of
> everything else — architecture, what was rejected, which file answers what —
> read `README.md` first.

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

### ⭐⭐⭐ YOU ARE HERE (2026-08-25, LATEST) — **INPUT SYSTEM BUILT (`IS1`–`IS3`) + A ROBUSTNESS/SECURITY AUDIT SHIPPED (`SEC1`). THE NEXT BUILD IS STILL `F1`.**

⭐⭐ **THE AUDIT'S HEADLINE IS THE CLEAN HALF, and it is the compliance evidence,
not a formality**: **no network egress anywhere in the pipeline** (not one HTTP
call — *"nothing leaves the device"* is verifiable **by absence**), no `eval` /
`exec` / `pickle` / `shell=True` / `yaml.load`, both `subprocess.Popen` calls in
list form, models loaded by absolute path, and the socket already on loopback.
Full account: `GESTURE_PIPELINE_SPEC.md` **§18**. Suite:
**`analysis/verify_hardening.py`, 51 checks**.

**Seven fixes shipped, each mirrored into BOTH tools where both have the code:**
off-loopback now **refused** unless `--allow-remote` is passed deliberately (S1);
session tags **sanitised** so a name cannot escape the capture root, in one shared
module (S2); the `meta` resolution **clamped** and every wire value **type-checked**
before it reaches arithmetic (S3); the receive buffer **capped** and decoded per
packet rather than per chunk (R1/R2); ⭐ **a single failed camera read no longer
ends the session in either tool** (R3 — it used to cost a whole `--record` take);
a clear message when the port is already held by a stray (R4); and the
permanently-red `verify_planar_pnp.py` fixed — **all 26 suites now pass, for the
first time** (R5).

⛔ **Four things were found and deliberately NOT fixed**, each with a queue row so
it is a decision rather than an omission: **`SEC3`** the face detector runs every
frame and nothing consumes it (a switch was added, the default was not flipped —
turning it off is visible, so it is the owner's call); **`SEC4`** the debug
recorder buffers the whole session in RAM while production streams; **`SEC5`**
both tools feed MediaPipe a fake 33 ms clock; **`SEC2`** only two direct
dependencies are pinned and the transitive tree floats.

⚠ `parity_replay` reports **NO DIVERGENCE** after the mirrored edits — which is
what says the two tools did not drift apart while being corrected.

---

### ⚠ Superseded: YOU ARE HERE (2026-08-25) — **THE INPUT SYSTEM IS BUILT (`IS1`/`IS2`/`IS3`). THE NEXT BUILD IS STILL `F1`: THE CUBE'S TRANSFORM FROM THE FINGERTIPS.**

> **Owner, 2026-08-24:** *"I want to be able to later ship independently this hand
> detection system as an input system (for my game, or for any other purpose such as
> a filter on Snapchat for example) ... mimicking the input system of Unity."*
> And: *"No need for TypeScript for the moment, no need for C# for the moment."*

⭐⭐ **WHAT LANDED, AND WHY IT COULD LAND WITHOUT RISK.**
`Local_pc/Movement_with_hand_detection/handinput/` — five **actions**, Unity's five
**phases**, `+=` **callbacks with a context**, a **polling** API, and `HandState` v2
as the wire contract. ⚠⚠ **IT OBSERVES AND DRIVES NOTHING**: every value it
publishes was produced by the gesture logic that already ran that frame, so no cube
is snapped, moved or released by it and the change **cannot** alter behaviour.
Package: `handinput/README.md`. Record: `GESTURE_PIPELINE_SPEC.md` **§17**.

| evidence | result |
|---|---|
| new suite `analysis/verify_handinput.py` | **95 checks pass** |
| the 24 existing `verify_*` suites | pass |
| `parity_replay` on `2026-08-24_220415_prod_tau20` | **NO DIVERGENCE**, 454 frames |
| a real recording replayed through the input system | 454 frames → **785 events** |
| `export_package.py` → run standalone, no repo on the path | **works**; 9 modules, 4 416 lines |

⛔⛔ **NOT CLOSED: THE OWNER'S LIVE LOOK IN BOTH TOOLS.** Deferred by the owner to
the evening of 2026-08-25 (*"I will run the debug and production this evening"*).
⚠ **Automated green is necessary and not sufficient** — §13.6.1 shipped inverted
while passing an "end-to-end confirmed" claim. **Until that take happens, treat
`IS1`–`IS3` as BUILT, not SHIPPED.** What to look for: the debug HUD's green
`handinput …` line (per hand: the `tracked` phase, `RDY` when `grab_ready` is
performing, `ROT` when a rotation reference is frozen), and that everything else
behaves exactly as it did last night.

⚠ One pre-existing failure found while running everything, and it is **not** from
this work: `analysis/verify_planar_pnp.py` prints `ALL GOLDEN VECTORS PASS` and
then dies on a **console encoding error** writing a `⚠` character (cp1252). It
fails identically with the change reverted. Left alone deliberately — fixing an
unrelated file inside this change would have muddied the parity evidence.

⭐⭐⭐ **THE NEXT BUILD IS UNCHANGED: `F1`.** The input system is orthogonal to it —
it publishes what the pipeline produces, so a better transform underneath simply
makes the same actions better. Read `F1`'s row, and its one trap (a rigid-body fit
over palm+tips is A10-dead twice).

---

### ⚠ Superseded: YOU ARE HERE (2026-08-24) — **T6 IS CLOSED, THE LAG IS FIXED AND SHIPPED, AND THE NEXT BUILD IS `F1`: THE CUBE'S TRANSFORM FROM THE FINGERTIPS.**

> **Owner, after four live T6d sessions and a lag hunt:**
> 1. *"the anisotropic fit bring very minor improvement and I don't want to ship it."*
> 2. *"the grab and rotations with the anchor to the palm and limited knuckles arc as
>    it is currently designed is too coarse: it does not render subtle movements of
>    the fingertips ... I want to keep it, but as an indication (for orientation, for
>    sign, for chirality, etc.) in support to the fingertips."*
> 3. *"there is a slerp introduced somewhere ... the cube is lagging the hand and
>    this feels very uncomfortable."*
> 4. **NEXT BUILD, to be specified in its own conversation:** *"control the transform
>    (Vector3 position and rotation quaternion) of the cube from the fingertips."*

⛔⛔ **1. THE WHOLE T6 LINE IS CLOSED — REJECTED, NOT PAUSED.** Five arms were built
and all five failed A10 or the owner's feel test: planar PnP, the 6-point thumb
model, the world-z gate, the trustworthy-halves rebuild, and T6d's anisotropic 2×2.
⭐ **NOTHING HAD TO BE REVERTED, and that is the process win worth keeping**: every
arm lived in `palm_rotation.estimators()` and the debug tool behind a toggle that was
**measured byte-identical to shipped Horn** (975/975 and 1084/1084 replayed frames),
so production never ran a line of it. **A rejected experiment cost one flag flip, not
a revert.** ⭐ The DIAGNOSIS stays on the record and is still the best account of the
defect (`HANDOFF_T6_ORIENTATION_FROM_2D.md` §2.0–§2.0.16): MediaPipe reports a
physically face-on palm as **24.9° tilted**, its world x,y are faithful, only z is
fabricated, and it gets the tilt BEARING right while the MAGNITUDE is wrong.
⚠ **It is SUPERSEDED, not merely rejected** — decision 2 changes what the estimator
is being asked to do.

✅✅ **2. THE LAG IS FIXED AND SHIPPED TO PRODUCTION.** Full account: **§14.3.6**.
In one line: **one constant, found by measurement, and the filter above it was dead.**

| what | before | after |
|---|---|---|
| rotation smoothing | fixed **0.35 per FRAME** | **τ = 20 ms**, `1 − exp(−dt/τ)` |
| settling at 48 ms/frame | 111 ms | **20 ms** |
| settling at 64 ms/frame | 149 ms | **20 ms** |
| predictive orientation filter | ran every frame | **removed** (dead: Horn replaced it on **9091/9091** frames) |

⭐⭐⭐ **3. THE NEXT BUILD IS `F1` — THE CUBE'S TRANSFORM (POSITION *AND* ROTATION)
FROM THE FINGERTIPS.** To be specified by the owner in its own conversation. Read
`F1`'s row before starting; the one thing that must not be re-tried is a rigid-body
fit over palm+tips, which is A10-dead twice over for a reason that is now the whole
point of the new design.

---

### ⚠ Superseded: YOU ARE HERE (2026-08-24) — **T6d IS BUILT. THE NEXT STEP IS A LIVE SESSION, NOT CODE.**

> **Owner:** *"The immediate next build will be a debug run which implements this
> anisotropic fit, so I can feel the behaviour during run time. In this debug run,
> add sliders to modify the anisotropic fit parameters, so I can modify them during
> runtime and feel the resulting changes in behaviour."*

✅ **BUILT 2026-08-24.** `debug_snap.bat` now opens a second window with the four
sliders and the toggle; `t` toggles the rebuild, `0/1/2` load identity / the fitted
yaw / the fitted pitch parameters. ⭐ **The toggle starts OFF and OFF is MEASURED to
be the shipped estimator** — byte-identical cube orientations on 975/975 replayed
frames, 953/975 differing once it is on, so `t` is a true one-variable A/B.
⭐⭐ **RUN IT WITH `--record`.** The session is not only a feel test: it is the
measurement the corpus lacks. Every frame now stores its own `ratio`, `ψ`, gain and
applied tilt **and the parameters in force**, and `meta.json` logs every slider move
with its frame — so the take can be cut into per-setting segments. **What is needed
from it is TIME SPENT AT INTERMEDIATE ψ** (turn *and* tip together, slowly): the yaw
takes sit at ψ≈0/180 and the pitch takes at ψ≈90, which is precisely why `b` and `c`
are unconstrained today.
⚠ Changing a parameter while a cube is HELD gives the cube a one-off offset (the grab
reference was frozen under the old values) — the HUD says so; release and re-grab.

⭐⭐ **READ `HANDOFF_T6_ORIENTATION_FROM_2D.md` — its top block is how to run it, and
§2.0.17 records what was built and the four decisions inside it** (including one that
would silently break a port: ψ must come from the principal-axis closed form, since
the textbook eigenvector row collapses to noise at exactly pure yaw and pure pitch).
Then §2.0.16 for the fit, §2.0.9/§2.0.12 for why it is shaped that way.

**WHERE T6 ACTUALLY GOT TO.** Four estimator replacements were built and all four
were A10-rejected (planar PnP, PnP+thumb, the z gate, the normal rebuild) — but the
rejections mapped the problem precisely, and the fifth approach works:

| finding | number |
|---|---|
| ⭐⭐ **ROOT CAUSE**: MediaPipe reports a physically FACE-ON palm as tilted | **24.9° median**, 61 sessions, 3131 pixel-verified frames |
| ⭐ its world **x,y are FAITHFUL**; only z is fabricated | 1.1° vs the pixels' 1.2° |
| ⭐ it gets the tilt **BEARING right** — only the MAGNITUDE is wrong | 10.6° median vs 45° for chance |
| ⭐⭐ the bias is a **repeatable function of pose WITHIN a recording** | between/within ratio **5.17** |
| ⛔ but its map is **per-session** and does not transfer | shape disagreement 13.4° vs 14–22° amplitude |
| ⭐⭐⭐ **yaw-like and pitch-like tilt need DIFFERENT gains** | **1.15** vs **1.55** |

⭐⭐⭐ **THE ANISOTROPIC 2×2 FIT IS THE RESULT THAT SURVIVED.** Because yaw compresses
the palm's WIDTH and pitch its LENGTH — perpendicular directions — a gain that depends
on the compression direction ψ can treat them oppositely where no scalar can:
`g(ψ) = a + b·cos2ψ + c·sin2ψ`, which IS a symmetric 2×2 evaluated on that direction.
Fitted per recording against camera-independent objectives: **PITCH drift 76.4° →
23.6°** and scatter 44.4° → 21.2°; **YAW scatter 9.5° → 7.4°**, gain 0.82 → 0.95.
⛔ **Open**: each take exercises only its own ψ, so `b`/`c` are unconstrained — which
is exactly what the slider run is for.

⚠ **Production is UNTOUCHED throughout.** Everything lives in `estimators()`; both
golden-vector suites pass.

---

### ⚠ Superseded: YOU ARE HERE (2026-08-23) — **NEXT BUILD IS T6, AND THE OWNER WANTS IT BEFORE ANYTHING ELSE.**

> **Owner:** *"I want to implement the fix before anything else is built."*
> And on the defect: *"this is a show-stopper for me as I can't tolerate a cube
> which rotates differently than what it should to reflect the physical world."*

⭐⭐ **READ `HANDOFF_T6_ORIENTATION_FROM_2D.md` — it is a COMPLETE brief written so a
fresh session can start implementing immediately.** Then T6's row below, then
`GESTURE_PIPELINE_SPEC.md` §14.3.4.7 → §14.3.4.11.

**THE DEFECT**: when the hand turns like a page, the object does not turn purely
about the vertical — **it LEANS, up to ~27° at a 60–90° turn**. ⚠ Always state it
that way, never as "13° of axis deviation": same fact, but the degrees-of-axis
framing is why an earlier pass wrongly recommended accepting it.

**THE CAUSE IS PROVEN BY TWO INDEPENDENT ROUTES** — scaling MediaPipe's world z
slides the yaw tilt 14.5°→0.6°, and **ROLL, the one axis needing no depth,
measures gain 1.02** while yaw (1.13) and pitch (0.74) err in OPPOSITE directions.
Horn, the quaternion maths, the frame conventions and the renderer are all
exonerated. **The 2D landmarks are good; the predicted depth breaks rotation.**

**THE FIX (T6)**: replace `palm_rotation.Horn`'s 3D↔3D fit with a **2D↔3D planar
PnP** — fit the pose that best PROJECTS a canonical palm onto the PIXEL landmarks.
⭐ The integration point already exists: `freeze(px, world)` / `delta(state, px,
world)` already receive pixels and ignore them, so T6 is a **sibling class behind
the same interface**, swapped at two call sites. ⛔ **No MANO needed** (N13 safe).
⭐ The planar mirror ambiguity is already solved here by U7's chirality.

⭐⭐ **AND THE MEASUREMENT RIG IS FINALLY COMPLETE** — `t5i` (yaw+pitch),
`t5j` (roll, depth-free), `t5h` (jitter). All three axes, recorded takes, one
variable. Baselines to beat are tabulated in the handoff §5.

⚠ **4.2 is DONE and owner-confirmed live in both tools** — see the superseded
block below for it. Nothing about T6 depends on it, or it on T6.

---

### ✅ Superseded: YOU ARE HERE (2026-08-23) — **4.2 IS BUILT AND OWNER-CONFIRMED LIVE.**

> Owner, debug tool: ***"yes. this is working properly"***
> Owner, production: ***"this is working fine"***

**Read this block, then 4.2's row, then `GESTURE_PIPELINE_SPEC.md` §14.3.5.**

| | |
|---|---|
| **state** | Z-axis translation, the 3D snap gate and the world-space play volume are BUILT in BOTH tools and **CONFIRMED LIVE in the debug tool** |
| **automated** | 23 golden-vector suites PASS · `parity_replay` NO DIVERGENCE (509 frames) · `VerifyChiralityFixture` ALL PASS · the play-area invariant reads clean straight from every recording that carries cube rows |
| ✅ **live** | **BOTH TOOLS, back to back, 2026-08-23** — debug *"yes. this is working properly"*, production *"this is working fine"*. Both takes recorded at `recorder_schema: 3`, the first sessions ever written at it |

| what shipped | where | flag / constant |
|---|---|---|
| **Z translation** — a held object's depth follows the hand's grab-referenced span ratio | both tools, driving `Cube.depth_m` from `palm_depth.DepthRatioTracker` | `Z_TRANSLATION` |
| **3D snap gate** — close on X, Y **and** Z | `_try_snap` in both tools, axial term from the new `palm_depth.HandDepthTracker` | `GRAB_Z_TOLERANCE_M = 0.15` |
| **DECISION 1** — no snapping while depth is frozen | `can_snap` in both tools | `SNAP_REQUIRES_VALID_DEPTH` |
| **DECISION 2** — the play area is a world-space VOLUME, frustum-aware | `palm_geometry.clamp_to_play_volume`, from both `set_target_center`s | `PLAY_AREA_MARGIN_M = 0.0425` |
| **projection** — on-screen extent = real size AT ITS DEPTH | `palm_geometry.projected_size_px` | `REFERENCE_DEPTH_M = 0.50` |
| **recorders** | `depth_m` + `projected_size` per object, `hand_depth_m` + `depth_valid` per hand | `recorder_schema: 3` |

⭐⭐ **THE ONE THING WORTH READING IF YOU READ NOTHING ELSE — a constant that was
about to be wrong, and the shape of the mistake.** An object's resting depth was
first set to **0.40 m**, on the strength of U9's own row: *"40 cm IS the closest
the operator actually works"*. **That sentence reads the corpus's p99 palm width
— it is about the CLOSEST APPROACH.** The typical distance is 10 cm further, and
the typical distance is what an object must sit at to be reachable. Measured over
**86 109 trusted hand-frames across 65 sessions**
(`analysis/m9_working_distance.py`): median **0.497 m**, p1–p99 0.309–0.837.
Against 4.2's own axial gate, an object at 0.40 m is reachable on **70.9%** of
frames; at the measured median, **91.2%**. ⛔ **A quarter of all frames unable to
pick anything up would have read as a broken build, not a mis-sized constant.**

⭐ **The reusable form: a constant borrowed from another row's derivation inherits
that row's QUESTION, not just its number.** U9 asked "how big is a hand near the
edge"; 4.2 asked "where does the hand live". Same corpus, different statistic.

**Three more decisions that are recorded rather than obvious** — full reasoning in
spec §14.3.5:

1. ⛔ **The 3D gate is an ELLIPSOID, not a sphere, and a sphere would have shipped
   an un-grabbable object.** The axial term compares against a depth scaled by
   NOMINAL anatomy, so a user 20% off the median reads ~80 mm away from where they
   are, *constantly*; the small object's spherical tolerance would have been 43 mm.
2. ⭐ **§14.3's "absolute, not relative-delta" and §14.1's no-pop rule only LOOK
   contradictory.** `cube.depth_m = grab_depth_m / ratio`, and the ratio's own
   `d0` is captured at the grab — so it is memoryless (decision 2 satisfied) AND
   exactly 1.0 on the grab frame (no pop). Reading decision 2 as "snap the object
   to the hand's depth" would have put a Z teleport into the gesture this project
   has worked hardest to remove.
3. ⚠ **It is the play volume's WALLS, not the tolerance, that bound
   re-grabbability.** Release freezes an object in all three axes, so a wall beyond
   the operator's reach would let one be parked where it can never be picked up.
   The walls are therefore the measured p1–p99 of the hand's own working distance.

⚠ **`cube.size` is now the extent at the RESTING DEPTH only.** The centre, the
clamp, the grab radius and both renderers read `projected_size_px`.
`_top_left_for_center` was DELETED from both tools — it converted with the
nominal size, and a stale copy is how an object's centre would silently drift as
it moved in Z.

⭐ **DECISION 1's cost has a number from day one**, which is what the owner asked
for before it is ever re-tuned: the edge-on band covers **1.6%** of hand-frames
corpus-wide — and that is a *ceiling*, counting every edge-on frame rather than
those where a hand was also within grab radius of a free object.


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

⛔ **Still open and unchanged by this build**: U7's declared-ground-truth
acceptance take (see the block below) and T4's yaw/palm-sink — 4.2 drives an
object's depth, it does not correct the translation anchor's yaw swing.

---

### ✅ Superseded: YOU ARE HERE (2026-08-23) — **FIVE FIXES SHIPPED AND LIVE-CONFIRMED. NEXT BUILD IS 4.2.**

> Owner, at the end of the session: ***"the build now is good."***

**Start here, then read the rows for U7 / U8 / U9 / T3. Nothing is committed —
the working tree holds all of it.**

| what shipped | where | flag / constant |
|---|---|---|
| **U7** — chirality from GEOMETRY, not the 10.8%-wrong handedness label | `palm_geometry.signed_palm_volume` / `geometric_chirality` / `ChiralityResolver`, wired into `PalmFacingTracker.update()` | `GEOMETRIC_CHIRALITY` |
| **T3** — a held object's owner SLOT follows its TRACK across a relabel | `Resources/owner_remap.py`, called by both tools | `OWNER_FOLLOWS_TRACK` |
| **U8** — rule 3 may not act on a PROVISIONAL chirality | `ChiralityResolver.confirmed`, gating `can_snap` in both tools | `CHIRALITY_CONFIRM_MS = 200` |
| **U9** — an object may never reach the display edge | `palm_geometry.clamp_to_play_area`, from both `set_target_position`s | `EDGE_MARGIN_PX = 60` |
| **recorders** — both log the cue AND cube position/size, sampled at the same point in the frame | `_record_flush` (production), the debug recorder | `recorder_schema: 2` |

✅ **ALL FIVE ARE LIVE-CONFIRMED IN BOTH TOOLS (2026-08-23 evening).** Owner:
*"Production is OK as well."* The recorder rework is verified end to end on
`2026-08-23_173029_schema2_production_check` (509 frames, 21.4 fps): schema 2
present, all eight hand fields and all four cube fields written, and — the point
of the whole change — **the play-area invariant was read STRAIGHT FROM THE
RECORDING, with no replay and no re-derivation: 0 of 1018 cube-frames outside,
closest approach 0.0 px slack** (the large cube at x=500, exactly the computed
boundary).

⛔⛔ **STILL OPEN, AND NOT WHAT ITS FILENAME SUGGESTS — U7's ACCEPTANCE TAKE.** An
attempt was made (`2026-08-23_172804_u7_acceptance_known_right`) and the operator
then reported that **BOTH hands were used**, so the declared `known_hand` was
FALSE. ⭐ **The declaration is RETRACTED in that session's `meta.json`**: the field
is renamed `known_hand_RETRACTED` and `ground_truth_valid: false` added, so no
harness can read it as ground truth (`u7_geometric_chirality.py` looks for
`known_hand`). ⚠⚠ **Trusting a wrong declared label is exactly the circularity
that hid the handedness defect through seven patches — do not resurrect that
field.** The take is still useful as an ordinary session and as the first debug
take carrying schema 2. ⭐ **U7's behaviour was observed correct live** (exit
palm / re-enter back / re-grab refused) — real evidence, but NOT the specified
acceptance test. **U7 acceptance remains OPEN** and needs a take where ONE
physical hand is used throughout.

**NEXT BUILD: 4.2 — Z-axis translation**, driving cube Z from 4.1's depth ratio
(`Resources/palm_depth.py`, A10-passed, wired to nothing). ⚠ It must also make
snap gating **3D** — `_try_snap`'s grab radius becomes a 3D check, a real change
to existing logic. ⚠⚠ **AND IT MUST REVISIT U9's PLAY-AREA CLAMP**, which is a 2D
rule: the display is the camera's FIELD OF VIEW (a frustum), so an object's
projected extent changes with depth, and `clamp_to_play_area`'s `size` term stops
being a constant — a NEAR object could otherwise overflow the play area. See 4.2's
row for the design question that comes with it, and pair the change with **U2**. ⚠ Read `GESTURE_PIPELINE_SPEC.md` §14.3 **and then §14.3.2,
which corrects it**, plus **S10** (the depth ratio must FREEZE inside the DR-2
band). ⭐ No calibration step is needed — the envelope is 3.59x and `d0` is
per-grab.

---

**⚠⚠ THE METHOD LESSONS OF THIS SESSION. They cost four reverted builds, and every
one is about an INSTRUMENT, not about the pipeline.**

1. ⛔⛔ **FOUR TIMES A HARNESS REPORTED CLEAN ON A TAKE THE OWNER HAD JUST WATCHED
   FAIL.** Each time the instrument was wrong, not the owner:
   - counted a SLOT change as a hand change (label-as-identity — the very
     confusion under diagnosis);
   - recomputed the palm/back cue with a slot-keyed tracker while production ran
     track-aware;
   - looked the hand up by the cube's owner SLOT, so a relabel made it skip;
   - paired `hands[i]` with `cubes[i]` when production sampled cubes a frame
     earlier — **11 phantom violations**.
   ⭐ **When the owner's eyes and the instrument disagree, the instrument is the
   suspect.**
2. ⭐ **RECORD WHAT RAN; DO NOT RE-DERIVE IT.** A recomputation is a second
   implementation that can silently disagree with the real one. Production now
   records `thumb_outward`, `chirality_confirmed`, `snap_allowed`, and cube
   `position`/`size`. `analysis/verify_recorder_parity.py` keeps the two
   recorders honest by SOURCE.
3. ⚠ **`parity_replay.py` reported a divergence THREE times and every time it was
   THE HARNESS**, feeding an input to one side only. A comparator must be
   symmetric in its INPUTS, not just its logic.
4. ⭐⭐ **A TRIGGER CANNOT ENFORCE AN INVARIANT** (U9). Two hand-side triggers were
   built and reverted before the positional clamp; see U9's row.
5. ⭐ **A threshold must not be computed from a quantity that is noisy in the
   regime the threshold governs** (U9's adaptive margin, 45% width jitter).
6. ⚠ **The count alone was not the guard it looked like** (U8): the dispute
   condition catches the recorded failure at every window from 400 ms down to
   100 ms; the window is a backstop.

---

### Superseded: YOU ARE HERE (2026-08-22, END OF SESSION) — **THREE FIXES SHIPPED AND OWNER-ACCEPTED LIVE.**

> Owner, after the production run: ***"fix is working. I believe this is good to ship."***

**Read this block, then the U7/U8/T3 rows. The next build is 4.2 (Z-axis translation).**

| what shipped | where | flag |
|---|---|---|
| **U7** — chirality from GEOMETRY, not the 10.8%-wrong handedness label | `palm_geometry.signed_palm_volume/geometric_chirality/ChiralityResolver`, wired into `PalmFacingTracker.update()` | `GEOMETRIC_CHIRALITY` |
| **T3 narrow remap** — a held cube's owner SLOT follows its TRACK across a relabel | `Resources/owner_remap.py`, called by both tools | `OWNER_FOLLOWS_TRACK` |
| **U8** — rule 3 may not act on a PROVISIONAL chirality | `ChiralityResolver.confirmed`, gating `can_snap` in both tools | `CHIRALITY_CONFIRM_MS = 200` |
| **production records the CUE** — `thumb_outward`, `chirality_confirmed`, `orientation_valid`, `snap_allowed` | `HandsTriggeredActions._record_flush()` | `VISION_RECORD=1` |
| **U9** — an object may never reach the display edge (play area = window inset 60 px) | `palm_geometry.clamp_to_play_area`, from both tools' `set_target_position` | `EDGE_MARGIN_PX = 60` |

**⭐ THREE DISTINCT DEFECTS, and they were only separable by recording them.**
All three presented as *"a back-of-hand hand takes the cube"*:

1. **Steal by RELABEL** (`n8_back_steal_b`, f478) — DR-1 swaps two tracks between
   slots; ownership is a slot NAME, so the cube changes PHYSICAL HAND with **no
   release, no snap and rule 3 never consulted**. Fixed by the remap.
2. **Back-grab by INHERITED STATE** (`t3_remap_debug_test`, f1050) — a track moving
   into a slot inherited the previous occupant's `PalmFacingTracker`, so its
   back-of-hand read as PALM for 2 frames. **Post-mortem §3.4, still live.** Fixed
   by resetting the tracker when the track in a slot changes.
3. **Back-grab by PROVISIONAL CHIRALITY** (`t3_remap_production_test`, f664) — a
   newly entered hand's chirality measured wrong for 5 frames. Fixed by U8.

⚠⚠ **THE METHOD LESSON, and it cost two wrong builds tonight:**

- ⛔ **Twice a harness reported CLEAN on a take the owner had just watched the
  defect in.** Both times the instrument was wrong, not the owner. The first
  treated a slot change as a hand change (label-as-identity — the very confusion
  under diagnosis); the second recomputed the cue with a slot-keyed tracker while
  production ran track-aware. ⭐ **When the owner's eyes and the instrument
  disagree, the instrument is the suspect.**
- ⭐ **This is why production now RECORDS the cue instead of re-deriving it.** A
  recomputation is a second implementation that can silently disagree with the
  real one. It did, immediately.
- ⚠ `parity_replay.py` reported a divergence **three times** this session and
  **every time it was the harness**, feeding an input to one side only. A
  comparator must be symmetric in its INPUTS, not just its logic.

**LIVE ACCEPTANCE (both tools, recorded so the claim is checkable):**

| | debug `202023_u8_gate_debug_test` | production `202329_u8_gate_production_test` |
|---|---|---|
| coverage | 1420 fr, 487 two-hand, 1328 held, 506 back | 928 fr, 258 two-hand, 721 held, 275 back |
| silent handovers | **0** | **0** |
| back-of-hand steals | **0** | **0** |
| back-of-hand snaps | 2 — **both legal** (rule 3's armed exception) | 1 — **legal**, `snap_allowed=True` recorded |

⭐ The production row is the first read from **recorded** cue fields rather than a
recomputation, and it settled the one back-snap immediately: the hand was
thumb-outward when tracking was lost, which ARMS rule 3's documented exception.

---

### Superseded: YOU ARE HERE (2026-08-22, LATEST) — **U7 IS BUILT. IT NEEDS ONE LIVE KNOWN-HAND TAKE.**

**The next action is not a build — it is a 30-second recording only the owner can make.**

| | |
|---|---|
| **status** | ✅ Built, all offline guards green. ⛔ **NOT accepted** — acceptance is a LIVE known-hand take, which needs the owner and the camera |
| ⭐ **run this** | `LiveSnapDebug.py --known-hand right` (then `left`): exit palm, re-enter **back-of-hand**, try to grab. Rule 3 must **refuse**. Then `analysis/u7_geometric_chirality.py` on the new session |
| **what changed** | `Resources/palm_geometry.py`: `signed_palm_volume`, `geometric_chirality`, `ChiralityResolver`, wired into `PalmFacingTracker.update()` — the **one** place the label enters the palm/back cue in either tool, so both are fixed by one edit (N6) |
| **A/B switch** | `palm_geometry.GEOMETRIC_CHIRALITY = False` restores pre-U7 behaviour exactly. No `world_landmarks` → falls back to the label, i.e. today's behaviour; never worse |
| ⭐ **measured effect** | at the 5 recorded snaps, rule 3's input changes on **exactly 1 — frame 122, the documented failing snap** — and the four sound snaps are untouched. Verified through the REAL tracker, not a reimplementation (STEP 9) |
| **green** | 19 verify suites; `VerifyChiralityFixture.py`; new golden vectors `analysis/verify_geometric_chirality.py`; `guard_sensitivity.py`; `parity_replay.py` **zero divergence on 5534 frames** across two sessions |
| ⚠⚠ **read this before believing the green** | the 4.1 post-mortem's decisive fact was that its final session **measured CLEAN and the owner still saw bugs**. Everything above is offline. It is evidence the change does what was intended, **not** evidence the defect is gone in play |

**⭐ TWO FINDINGS THIS BUILD PRODUCED THAT WERE NOT IN THE PLAN:**

1. **The conditioning gate earns nothing, and was NOT shipped.** Sweeping the
   thumb-plane-thickness threshold 0→7 mm changed the error count not at all
   between 0 and 5 mm, and made it **worse** at 3–5 mm (0 residual errors → 3),
   because suppressing observations stalls the debounce and lets a bad value
   persist. **Under A10 a null result is recorded, not shipped hopefully** —
   `palm_plane_thickness()` stays exposed as a diagnostic only. **The 3-frame
   debounce does all the work**, and it is free because *a hand cannot change
   chirality*: within a track the value is constant.
   ⚠ **Honest caveat**: debounce=3 was chosen against **5 residual errors in one
   session**. Small sample. Re-validate on the live take before treating it as settled.
2. ⛔ **`analysis/guard_sensitivity.py` had been DEAD since 2026-08-03.** It
   AST-compared `HandsTriggeredActions._is_thumb_outward`'s body against an inlined
   reference — but queue item **1.2 moved that logic into `palm_geometry.py` the
   same month**, leaving a one-line delegation. From that day the guard **could not
   pass**: it printed "GUARD IS BROKEN" on every run for 19 days, about **itself**.
   ⭐ **A guard that cannot pass is worse than no guard** — its failure carries no
   information and everyone learns to ignore it. Repointed at the functions that
   actually hold the logic, plus new U7 mutants and an N6 delegation check.

⚠ The DR-2 A/B harnesses (`dr2_ab.py`, `dr2_latency.py`, `n7_dr2_dwell_ab.py`)
are **deliberately left on the two-argument call**, so their recorded historical
numbers stay reproducible. That is a choice, not an oversight.

---

### Superseded: YOU ARE HERE (2026-08-22, LATE) — **U7 STEP 0 IS DONE. THE REMEDY IS MEASURED VIABLE. BUILD IT.**

**Read this block, then U7's row, then `Claude/HANDEDNESS_LABEL_DEFECT.md` §5
(whose mechanism was corrected by this measurement).**

| | |
|---|---|
| **next build** | ⭐ **U7 — replace the MediaPipe handedness label as the CHIRALITY source with a geometric one.** Not 4.2 |
| **why not 4.2** | 4.2's central change rewrites `_try_snap`'s grab radius into a **3D check** — i.e. it rebuilds snap gating, the exact rule U7 corrupts. Building it first means re-deriving snap logic on top of a gate known to be **10.8% wrong**, and every live test of 4.2 would be read through that error |
| ⭐ **the measurement** | `analysis/u7_geometric_chirality.py`, scored against the operator's **DECLARATION** (never `is_thumb_outward(px, label)` — that circularity is the whole B4 lesson). 7 sessions, 2555 single-hand frames |
| ⛔ **§5's mechanism was WRONG** | the doc proposed "use the 3D palm normal instead of the 2D cross product". **3D alone does not remove the chirality dependence** — the 2D signed area already IS that normal's z-component, and a left hand showing its palm is the mirror image of a right hand showing its back. **The THUMB is what separates them**, because it leaves the palm plane: `V = det[index_MCP−wrist, pinky_MCP−wrist, thumb_CMC−wrist]` is rotation-invariant and flips sign only under reflection |
| ⭐ **result** | corpus **99.8%** vs the label's 98.8%; on the one discriminating take **98.3% vs 89.4%** — 31 errors → 5, **84% fewer**. ⚠ **Quote the second row, not the first**: six of seven takes are steady holds where MediaPipe is already 100% |
| ⭐⭐ **it fixes the SNAP** | of the 5 snaps in that take, rule 3's input changes on **exactly 1 — frame 122, the documented failing snap** — from "palm, allowed" to "back, forbidden". **The four sound snaps are untouched.** That two-sided result is the deliverable, not the accuracy number |
| ⚠ **build notes** | give the new cue its **own conditioning gate** (thumb distance from the palm plane: median 8.8 mm, p10 7.9 mm, min 0.9 mm) exactly as the 2D sign has `edge_on_measure`; residual errors form runs of [2,1,1,1], so **3 of 4 are isolated frames a 2-frame debounce absorbs** |
| ⛔ **the honest gap** | the four declared-**facing** takes are all takes where MediaPipe never errs, so **they cannot demonstrate the facing fix**. **Acceptance stays a known-hand LIVE take** (`LiveSnapDebug.py --known-hand left|right`), never a replay that trusts the recorded label. Re-run `VerifyChiralityFixture.py` and `analysis/parity_replay.py` around the change |
| ⭐ **then** | 4.2 (Z-axis), then U5 — ⚠ **U5 and N8 want sequencing together**, since a longer hold widens N8's steal window by construction |

⚠ **One coverage note worth keeping**: `2026-08-04_054109_known_right_back` is
**excluded** — all 723 frames detect TWO hands on a declared one-hand take, so its
ground truth is ambiguous. The harness names it rather than averaging it in.

---

### Superseded: YOU ARE HERE (2026-08-22, END OF SESSION) — read this, then U7, then the two post-mortems.

**Two documents carry the whole story. Read them before touching ownership,
per-hand state, or anything chirality-sensitive:**
- `Claude/HANDEDNESS_LABEL_DEFECT.md` — ⛔ **the root cause of the defect that
  survived seven patches**: the handedness label is wrong **10.8%** of the time
  and every chirality-sensitive rule inverts on it. Queue item **U7**.
- `Claude/POSTMORTEM_4_1_IDENTITY_MIGRATION.md` — why 4.1's identity migration
  was built, patched five times, and reverted.

| | |
|---|---|
| **state of the pipeline** | ✅ **Both tools behave**, on the reverted baseline. Production and debug were live-checked and measure clean (production 18 snaps / 18 releases, freeze signature 3 frames) |
| **reverted** | 4.1's identity migration — one flag, `TRACK_OWNERSHIP = False` (mirrored in `LiveSnapDebug.py`). **Nothing deleted**; set it True to restore |
| ⭐ **KEPT from 4.1, all independently good** | `palm_depth.py` (depth estimator, A10-passed, **now with the owner's edge-on fallback** — 100% availability, false depth unchanged); the **DR-1 frame-edge fix**; **production recording** (`VISION_RECORD=1`); the `hand_tracks` wire packet (sent, unused) |
| **next build** | **4.2 (Z-axis translation)** — it does not depend on any of the above. ⚠ But **U7 is the deepest open defect**, and it makes rule 3 unreliable today |
| ⚠ **still open** | **U7** (label 10.8% wrong), **U5** (occlusion coast), **N8** (cube stealing), and **T3 is ACTIVE again** — with ownership back on the handedness label, a relabel orphans a held cube: in play, a cube **drops** for no visible reason while crossing hands or rotating through edge-on, and the operator re-grabs |
| ⭐⭐ **T3 and U7 are ONE root cause** | the handedness label is unreliable (**10.8% wrong**) and the pipeline uses it as **both** identity (T3 — who owns the cube) **and** chirality truth (U7 — which way the palm faces). **Fix the label, or remove the dependency on it, and both go; patch either symptom alone and neither does.** That is the single highest-value target on the board |
| ✅ **U6 DECIDED** | owner, 2026-08-22: ***"we will keep two: production and debug"***. The collapse proposal is CLOSED. ⚠ The obligation that replaces it: **divergence must be caught mechanically** — run `analysis/parity_replay.py` whenever either tool's gesture logic changes, and whenever "it does not happen in production" is said. That sentence meant a real divergence 3 times and sampling once this session |

**⚠⚠ THE METHOD LESSON, which cost most of this session:**

1. ⛔ **Reach for GROUND TRUTH the first time a chirality-sensitive claim is
   questioned, not the seventh.** Seven analyses reported "zero violations"
   because each compared the pipeline's belief against a formula fed **the same
   wrong label**. `LiveSnapDebug --known-hand left|right` now stores the operator's
   declaration in `meta.json`; the corpus's `known_left_*`/`known_right_*`
   sequences existed for exactly this.
2. ⚠ **Check session COVERAGE before reading any result.** Three sessions produced
   green numbers from ~0 cubes held or 0 two-hand frames.
3. ⚠ **Instrumentation reported success while behaviour regressed, twice** (a
   recorder key collision; a harness that skipped the session recorded to test the
   fix). **A green instrument you cannot trust is a reason to stop, not continue.**
4. ⭐ **When the owner says "it does not happen in production", build the
   comparator** (`analysis/parity_replay.py`) rather than hunting divergences by
   eye. It found three real ones this session — and then proved the fourth claim
   was sampling, not a divergence.

---

### Superseded: YOU ARE HERE (2026-08-22, end of day) — **4.1's IDENTITY MIGRATION IS REVERTED.**

**Read `Claude/POSTMORTEM_4_1_IDENTITY_MIGRATION.md` before touching ownership or
per-hand state. It is the whole story with measurements.**

| | |
|---|---|
| **reverted** | cube ownership keyed on the DR-1 track id, AND per-hand state following the track. Owner instruction after 5 live sessions: *"it is still full of bugs. Revert."* |
| **how** | one flag — `HandsTriggeredActions.TRACK_OWNERSHIP = False`, mirrored in `LiveSnapDebug.py`. **Nothing was deleted.** Ownership and per-hand state key on the handedness SLOT again, exactly as before 4.1 |
| **cost** | **T3 returns**: a held cube is orphaned when the label flips, 113 of 205 spurious releases. ⭐ That is a DROP the operator re-grabs; the migration traded it for FREEZES and rule violations, which are worse |
| ⭐ **KEPT, independent and good** | `palm_depth.py` (4.1's depth estimator — A10-passed, drives nothing), the **DR-1 frame-edge fix**, **production recording** (`VISION_RECORD=1`), the `hand_tracks` wire packet (sent, unused), and every harness |
| ⚠ **the decisive fact** | the final session measured **CLEAN** — 0 rule-3 violations across 21 relabels, 43 snaps, 1255 two-hand frames, no frozen cube — **and the owner still saw bugs.** The instruments were not capturing what breaks, so further patching could not be trusted |
| ⚠ **before retrying** | fix **U6** first (one pipeline) — 3 of the 5 defects were production/debug divergences. Then migrate ALL per-hand state at once, never seed a new track from a slot, and write the system-level property test BEFORE the first live session |

**Next build is still 4.2 (Z-axis translation)** — it does not depend on the
migration. ⚠ But **U5** (occlusion coast) and **N8** (cube stealing) are still
open, and T3 is back.

---

### Superseded: YOU ARE HERE (2026-08-22, end of day) — **4.1 IS BUILT. NEXT BUILD IS 4.2 (Z-axis translation).**

**Read this block, then 4.2's row, then `GESTURE_PIPELINE_SPEC.md` §14.3 and
§14.3.2. You should not need anything else to start.**

| | |
|---|---|
| **next build** | **4.2 — Z-axis translation (§14.3)**, driving cube Z from 4.1's depth ratio |
| ⭐ **4.1 is DONE, both halves** | the depth **estimator** (`Resources/palm_depth.py`, A10-passed) **and** the `HandState` v2 **wire migration** carrying `trackId` (ownership now keys on identity, not the handedness label) |
| ⚠ what 4.2 must add | §14.3's **3D snap gating** — `_try_snap`'s grab radius becomes a 3D check. That is a real change to existing snap logic, not an additive axis |
| ⚠ undecided, deliberately | what happens to snap gating when `depthValid` is False (the S10 freeze). §14.3.2 leaves this to whoever builds it |
| ⭐ no calibration step needed | measured: an ordinary push/pull spans **3.59x**, and `d0` is captured **per grab**, so every grab self-normalises. See spec §14.3.4.6 / `analysis/m9_depth_envelope.py` |

⛔⛔ **TWO DEFECTS FOUND ON THE FIRST RECORDED PRODUCTION RUN (2026-08-22) — READ
BEFORE 4.2.** Session `2026-08-22_154426_production_4_1` (5114 frames, 205 s).

**(1) THE STRAND IS STILL PRESENT IN PRODUCTION, WITH A SECOND ROOT CAUSE.**
Owner: *"the small cube was dropped but my free hand could not catch it again."*
Measured: cubes owned by an absent track for runs of **40 frames (~1.6 s)**,
repeatedly. ⚠ **NOT "the track ended"** — the hands were still DETECTED, their
**track ids went to -1** while landmarks kept arriving:

```
f1997  hands=[('Left', 3), ('Right', 2)]  owner=3
f1999  hands=[('Left',-1), ('Right',-1)]  owner=3   <- stranded
```

⭐ **Root cause, server-side**: `_normalized_to_pixel_coordinates` returns None for
any landmark outside [0,1] — a hand **partially out of frame**. One None makes
`palm_centroid` None, which fails `all(o[0] is not None ...)`, which **skips DR-1
entirely for that frame**, so NO hand gets a `trackId` and the wire carries -1 for
both slots. **Moving a hand near the frame edge is enough.** The cube is then owned
by an int matching no live key, while its governing slot still holds a DETECTED
hand — so `holds_track` is True and release never fires.

✅⭐ **ROOT-FIXED 2026-08-22 (owner: "fix it")**: `hands_visualizer.py` now builds
pixel landmarks by **plain multiplication** (`lm.x * width`), exactly as
`LiveSnapDebug.py` always has — so out-of-frame coordinates go negative instead of
becoming None, `palm_centroid` survives, DR-1 keeps running and `trackId` keeps
being published. ⭐ **This was a production/debug DIVERGENCE of the same class as
§13.6.1 and the mirror bug** — the debug tool never had either defect because it
never used the None-ing converter. ⭐ It also fixes a **second, separate** defect:
`remap_keypoints` turned a None into **(0, 0)**, so an out-of-frame landmark
reached the client at the TOP-LEFT CORNER, corrupting `_weighted_position`'s
translation average as well as identity. Guard:
`analysis/verify_offscreen_identity.py` (every palm landmark x all four edges,
plus "DR-1 really publishes an id in that state" and "garbage is still rejected").
⚠ The client-side safety net (`OWNER_ABSENT_RELEASE_MS = 700`) is KEPT as
defence-in-depth — a cube must never strand for any future reason.

**(2) ⭐⭐ D4 IS REOPENED BY MEASUREMENT — the recorded condition is now met.**
Owner: *"when the hands quickly pass in front of each other and one occludes the
other ... the cube grabbed by the occluded hand is ungrabbed and then grabbed
again ... which causes a jump."* Measured on the same take — gaps where one hand
vanishes **while the other is present** (i.e. crossing/occlusion):

| | |
|---|---|
| events | 60 |
| median gap | **402 ms** |
| p90 / max | 2130 ms / 3778 ms |
| **longer than D2's 150 ms coast** | **42 of 60 = 70%** |

⭐ D2's coast is **2.7x too short** for hand crossing, so the cube is released on
70% of them and re-snaps on reappearance — the jump the owner describes.
⚠ **D4 was DECLINED 2026-08-21** (*"I do not see the need"*), and the recorded
reopening condition was **"only a hand lost LONGER than the sensor gap"**. That
condition is now measured. **This is a legitimate reopening, not a re-proposal.**

⭐ **PARKED AS QUEUE ITEM U5 (owner decision 2026-08-22)** — *"mark the issue as an
improvement for later re-opening"*. **U5's row carries the observation, the
recording reference, the measurement and the explanation**, so the topic can be
reopened cold. ⚠⚠ **The remedy is a LONGER HOLD, not extrapolation**: the owner's
framing said "extrapolation", but **B8 already measured every fit LOSING to "hold
the last value"**. Owner's stated approach: extend D2's window and **pick it by a
RECORDING TEST**, not by feel. ⚠ Cost to price: a longer hold widens the window for
**N8** and for holding a cube the operator really released.

**⭐ WHAT 4.1 SHIPPED (2026-08-22)**

- **`Resources/palm_depth.py`** — `DepthRatioTracker`: `max4` over the rigid palm
  quad vs a grab-time baseline, S10 freeze inside the edge-on band, rate limit,
  clamp. **A10 PASSED**: responsive **3.68x** on `depth_sweep`; on rotation-in-place
  its OWN error is **1.30x worst case** vs a naive width-only **8.04x**.
  ⚠ **Quote the drift-floor-corrected number** — 1.40x of the clean yaw take's
  1.82x is the operator's arm genuinely moving. 24 golden vectors.
  ⛔ **It is wired to NOTHING yet — that is 4.2.**
- **The `trackId` wire migration** — `hand_tracks` packet, `_owner_key()`,
  ownership keyed on the stable DR-1 id. Live A/B over three sessions: label
  keying orphaned a held cube **794 / 377 / 15** frames, track keying **0** every
  time (session 2 had **24** relabels). `PERCEPTION_LAYER_SPEC.md` §2.2.1–§2.2.3.
- **Production and the debug tool are now the SAME pipeline** — the mirror fix
  (spec §14.3.4.3/§14.3.4.4), owner-confirmed live.
- **Production can now RECORD** (`VISION_RECORD=1`), same JSONL schema as the
  debug tool, so every `analysis/` harness reads a production take unchanged.

⚠⚠ **TWO BUGS I INTRODUCED AND THE OWNER FOUND LIVE — read before touching
ownership.** (1) **The stranded cube**: release read
`cube_owned_by(_owner_key(hand))`, which degrades to the LABEL once a track ends,
so an int-keyed cube was never found and stayed owned by a dead id — drawn as
grabbed, driven by nothing, un-regrabbable. **The fallback fired exactly when the
id was missing, which is exactly when release needed it.** Fixed by driving
release from the CUBES, governed by whichever slot the owning TRACK is in now.
(2) The hand **LABEL displayed inverted** — pre-existing, fixed DISPLAY-ONLY;
⛔ **never flip the internal label**, four things are calibrated to it.

⚠ **Still open on 4.1**: the **~13° yaw axis tilt** is real and unattributed
(spec §14.3.4.2) — the mirror, the frame convention, degeneracy, hand anatomy and
the Horn fit are all eliminated; MediaPipe's world-z error and residual operator
wobble remain. **ROLL has never been recorded.**

---

### Superseded: YOU ARE HERE (2026-08-22, morning) — PHASE D IS CLOSED. **NEXT BUILD IS 4.1 (M9 metric depth).**

**Read this section, then 4.1's row, then `GESTURE_PIPELINE_SPEC.md` §14.3.1. You should not need anything else to start.**

| | |
|---|---|
| **next build** | **4.1 — M9 metric depth**, leading to 4.2 (Z-axis translation) |
| ✅ **NOT blocked** (corrected 2026-08-22) | The yaw take **was recorded on 2026-08-04** — `2026-08-04_164647_yaw_sweep_constant_depth`, 741 frames, verified present on disk — and **§14.3.2 already analysed it** (`max4` CV 0.056 under yaw). The earlier "⛔ blocked on the owner: a YAW take must be recorded first" line was §14.3.1's wording carried forward past §14.3.2, which superseded it the same day. See row N18. ⚠ **§14.3.2 also REFUTED §14.3.1's prediction**: under yaw, width and length degrade *equally* (0.128 vs 0.125) — no anchor is immune — which **promotes S10's freeze from backstop to prerequisite**. |
| ⚠ read before building | §14.3.1 **and then §14.3.2, which corrects it** (multi-anchor), **S10** (the palm-width anchor COLLAPSES edge-on, so the depth ratio must FREEZE inside the DR-2 band — reuse `PalmFacingTracker`'s pattern — or Z-control inherits the pitch-crossing failure) |
| ⭐ the scale reference already exists | `hand_skeleton.palm_width_world()` (spec §0.18). 1.7's fit is NOT needed. |
| ⭐ do it **with** 4.1 | **the `HandState` v2 wire migration**, which is what makes v2's metric fields mean anything — and it now has a second, measured customer: **carry a `trackId` and key cube ownership on it** (see T3 below, and spec §2.2's 2026-08-22 addendum) |

⚠⚠ **NEW, 2026-08-22 — READ BEFORE 4.1 USES §14.3.2.** The owner reported that a
YAW hand rotation turns the cube about a tilted axis. **Measured and confirmed**
(`analysis/t5*`): yaw is **25.6° off vertical** at large rotation vs pitch's
**5.0°**. Two suspects were tested and **both cleared** — the `invert_x` mirror
(a reflection can only reverse an axis, never tilt one: `M R M⁻¹ = R(−Mn,θ)`;
empirically the tilt is bit-identical) and constellation degeneracy
(`palm_observability` never leaves 0.85–0.89). ⛔ **The cause is NOT yet
identified, and it cannot be from existing data**: the corpus's only yaw take is
**axis-contaminated** — the operator mixed pitch in (2D-pixel control,
`t5c`), so part of that 25.6° is the hand, not the estimator. **A clean yaw
retake settles both this AND §14.3.2's mechanism claim, which rests on the same
take** (spec §14.3.3/§14.3.4). §14.3.2's *recommendation* — `max4` + S10 freeze —
**is unaffected; build 4.1 as prescribed.** ⭐ One actionable result already:
**palm+tips beats palm-only on axis fidelity in every take** (pitch 8.1°→3.9°),
but production ships palm-only for measured JITTER reasons — that is an **A/B
under A10**, not a switch to flip. ⚠ **ROLL has never been recorded** and stays
unmeasured.

**What just shipped (2026-08-21/22), all owner-accepted live:**

- **D0–D3 — dropout mitigation.** A **150 ms tracking-loss coast** plus a **3-frame resync blend**, in production and the debug tool. Owner ran a three-arm rig (off / bridge / bridge+blend) and chose BLEND. `GAME_RULES.md` rule 2 is the behavioural statement of record.
- **D4 (M10.7 grace period) — DECLINED**, not deferred: *"I do not see the need."* Do not re-propose it.
- **T3 — defect confirmed and quantified (113 of 205 releases), client-side remedy BUILT, LIVE-TESTED AND REVERTED.** Re-pointed at the v2 track id. ⚠ **Do not rebuild it at the client layer** — see its row.

⚠ **Two open items that are NOT next, recorded so they are not rediscovered:** the
**two-hand swap** (both hands present, labels exchanged, cube silently follows the
wrong hand — spec §0.4) and **N8 cube-stealing by occlusion**, which the owner saw
live on 2026-08-21 and wants handled with **B5**'s grab/release mechanism rather
than patched now.

---

### Superseded: YOU ARE HERE (2026-08-04, end of day) — PHASE 1 IS CLOSED. All of 1.5/1.6/1.7 parked.

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
| T1 | Back-of-hand rotation quality | pipeline | open — ⭐⭐ **AND A NEW LEVER WAS FOUND ON THE YAW TILT (2026-08-23, spec §14.3.4.8): the tilt SCALES WITH HOW MUCH THE FIT TRUSTS MEDIAPIPE'S WORLD Z.** Re-fitting the shipped constellation with world z x `k`: k=1.0 (ships) gives 13.0° axis / **23.4° visible lean**; k=0.4 gives 3.7° / **6.6°**, at the cost of over-rotating 20% instead of 13%. First thing ever found that moves this defect. ⛔⛔ **TESTED AND REJECTED THE SAME DAY (spec §14.3.4.9)**: at the k that makes yaw good (0.4), PITCH roughly DOUBLES on the take where pitch is currently excellent (5.5°→10.6°). **No k improves both — it is a redistribution, not a fix**, and it closes the whole 'just weight z less' family, because yaw and pitch need OPPOSITE things from the same coordinate (cf. queue 2.3, anisotropic covariance, 5 attempts all null). ⭐⭐ **The DIAGNOSIS is now established rather than suspected**: scaling z moves the yaw tilt smoothly 14.5°→0.6°, so the tilt IS caused by MediaPipe's world-z error. ⭐ **The only remaining candidate is the z-FREE decomposition**, which never uses z at all. ⚠ **State the defect as "the object LEANS up to 27° as you turn it", not "13° of axis deviation"** — same fact, and only the first one describes what the owner sees. ⭐ The lean is 100% consistent in direction and **95% in the SCREEN PLANE** (axis components x 0.212 / y 0.974 / z 0.064), which is why the in-plane 12.3° and the 3D 13.0° agree — a decomposition, not a coincidence. — ⛔ **the 9-POINT CONSTELLATION CANDIDATE IS CLOSED (2026-08-23, A10 REJECT)**: measured on a CLEAN card-free yaw take with jitter from a real production take, palm+tips buys **+1.4° of axis** (12.6→11.2) and costs **+4.9° of p95 jitter** (25.41→30.34). The "beats palm-only in every take" claim came from the CONTAMINATED 2026-08-04 take. `analysis/t5h_constellation_ab.py`; spec §14.3.4.7 | **1.5, 1.6, 1.7** (was 1.4/1.6, was 2.3) | ⚠ **Dependency CHANGED AGAIN 2026-08-03 (§0.15/§10).** 1.4 is dead, so "re-test after 1.4/1.6" is not buildable as written — re-test after **1.5 (anatomical constraints), 1.6 (consistency gate) and 1.7 (imposed skeleton)**, which are the three mechanisms that attack landmark quality at source. ⭐ **External corroboration for this exact failure**: Google has an **open issue (#5156) that palm/MCP world landmarks COLLAPSE when the back of the hand faces the camera** — T1 is a documented sensor failure mode, not only a filtering problem, and §0.15's worst cross-session offenders were the `known_*_back` takes. Prior note follows. §13.7. ⚠ **Dependency CHANGED 2026-08-03 (§0.13.2).** Was "M6c's anisotropic covariance is the untried mechanism" — M6c has now been tried **five times and cannot reach 82% of the large jumps**, which occur in *well-observed* frames. Re-test after **1.4 (M2) / 1.6 (M4)**, which attack landmark quality at source; M4's χ² gate targets exactly the implausible single-frame excursion this turns out to be ⭐⭐ **NEW, BINDING (2026-08-17, §16.17): STOP LOOKING FOR A ROTATION-ESTIMATOR FIX.** Two structurally unrelated estimators — the shipped Gram-Schmidt frame and a Horn least-squares fit over 5 points — reproduce the SAME ~60° jumps to within 1° on the SAME live frames (62.38 vs 61.83, 57.73 vs 57.58, 49.71 vs 48.53). **A jump both estimators reproduce is already in the landmarks.** This row is therefore the LANDMARK layer's (1.5 / 1.6 / 1.7, and 5.4's causal SmoothNet) and no further estimator work will touch it. |
| T2 | Pitch-plane crossing | pipeline | partly fixed | 2.2 (done), **1.5, 1.6, 1.7** (was 1.4/1.6, was 2.3) | ⚠ **Dependency re-pointed with T1 (2026-08-03)** — 1.4 is dead. ⭐ **The literature says the edge-on configuration is genuinely ill-posed for one RGB camera** (HandFlow, VMV 2022: the pose posterior is multimodal there; Meta uses multi-camera rigs for precisely this) — so DR-2's freeze-and-suppress plus motion carry-through is the *correct class* of answer and no per-frame cure should be expected. Prior note follows. §13.7. M6a satisfied; **DR-2 (2.2) shipped and closes the sign-flip half**. ⚠ **The rotation-quality half is NOT M6c's to fix** (§0.13.2) — redirected to 1.4/1.6 with the rest of the tail ⭐⭐ **NEW, BINDING (2026-08-17, §16.17): STOP LOOKING FOR A ROTATION-ESTIMATOR FIX.** Two structurally unrelated estimators — the shipped Gram-Schmidt frame and a Horn least-squares fit over 5 points — reproduce the SAME ~60° jumps to within 1° on the SAME live frames (62.38 vs 61.83, 57.73 vs 57.58, 49.71 vs 48.53). **A jump both estimators reproduce is already in the landmarks.** This row is therefore the LANDMARK layer's (1.5 / 1.6 / 1.7, and 5.4's causal SmoothNet) and no further estimator work will touch it. |
| T3 | **Object Jump Correction** | pipeline | ✅✅ **FIXED 2026-08-22 BY THE NARROW REMAP, owner-accepted live.** `Resources/owner_remap.py`: a held cube's owner SLOT follows its DR-1 TRACK when the two hands swap slots. ⭐ **NOT 4.1's migration, and the difference is the whole point**: ownership REMAINS a slot name, so every consumer (release, drive, `unowned_cube_names`, the renderer) is untouched and nothing else moves off the slot — there is no seam, which is what the post-mortem blames for the revert. One int per held cube is the only new state. Flag `OWNER_FOLLOWS_TRACK`. ⭐ **MEASURED A/B on the deliberately recorded steal** (`analysis/t3_remap_ab.py` on `2026-08-22_184440_n8_back_steal_b`): silent handovers **2 → 0**, remap fired 6 times on 9 relabels in the live take, and the ONLY other change is **one FEWER release** — the spurious relabel-drop at f206, where a single hand moved slot with no second hand present. ⚠ **The acceptance criterion had to be corrected**: its first version demanded an identical release count, which would have BLOCKED the fix — removing spurious releases is T3's entire purpose (113 of 205). ⛔ **This also revealed the SILENT HANDOVER**, which no earlier T3 work had named: the cube changes physical hand with **no release, no snap and rule 3 never consulted**, so it bypasses the gate entirely. That is why ordinary back-of-hand grabs were correctly blocked while this one was not. Prior status follows. **ACTIVE AGAIN 2026-08-22 — 4.1's track-id ownership was REVERTED, so ownership keys on the handedness LABEL once more and a relabel orphans a held cube.** In play this is a cube DROPPING for no visible reason while crossing hands or rotating through edge-on; the operator simply re-grabs. ⭐⭐ **T3 AND U7 ARE THE SAME ROOT CAUSE**: the handedness label is unreliable (measured **10.8% wrong**, U7) and the pipeline uses it as if it were BOTH identity (T3: who owns the cube) AND chirality truth (U7: which way the palm faces). **Fixing the label — or removing the dependency on it — fixes both; patching either symptom alone will not.** ⚠ The v2 track-id remedy was built and reverted (see `POSTMORTEM_4_1_IDENTITY_MIGRATION.md`); prior status follows. **DEFECT CONFIRMED AND QUANTIFIED; THE CLIENT-SIDE FIX WAS BUILT, LIVE-TESTED AND REVERTED 2026-08-22. Re-pointed at the v2 wire protocol (with 4.1/M9).** | 2.1 (+ N5 now) | ⭐⭐ **THE DEFECT IS REAL AND IS THE LARGEST OF ITS KIND**: of 205 spurious cube releases, **113 are the owner's own hand reappearing under the other handedness label**, against 83 true dropouts (`analysis/d2_bridge_ab.py`). Ownership is keyed to that label, so a relabel orphans a held cube — whether DR-1 errs *or* corrects itself. **That finding stands and is not affected by the revert.** ⛔ **What was reverted is the client-side REMEDY.** `Resources/hand_ownership.py` transferred ownership when a hand reappeared in the other slot within 0.5 palm widths. It worked — 5 transfers in a one-minute live session, 49 of 236 corpus events — **and it was wrong, structurally rather than by mis-tuning: it recognised "the same hand" by POSITION, and two hands in the same place are indistinguishable by position, which is exactly what OCCLUSION is.** Live it handed a held cube to the operator's **other physical hand**. ⭐ **The post-mortem measurement is the decisive one** (`analysis/t3_relabel_threshold.py`, GUARD VARIANTS): **38 of the 49 saves occur with a second hand seen inside the preceding second** — nearly the entire benefit sits in the regime the mechanism cannot judge — and the unambiguously safe remainder is **11 of 236 (4.7%)**. ⚠ **Owner's live verdict decided it**: the T3-on and T3-off arms *"felt much the same"*, i.e. **the benefit was imperceptible while the failure mode was plainly visible.** By the B7 precedent (parked for being measurable-but-invisible, and B7 had **no** failure mode) this is a strictly weaker case. ⭐⭐ **RE-POINTED, NOT ABANDONED: `HandState` v2 carries a TRACK identity, so ownership keys on the track and the question disappears.** That migration is scheduled with **4.1/M9** (spec §2.2) — do it there, in three lines and correctly, instead of reconstructing a track id from positions on the client. ⚠ **Do NOT rebuild a position-based transfer at the client layer.** `analysis/t3_relabel_threshold.py` is kept and re-runnable; the module and its golden vectors are deleted. Prior status follows. ⭐ **Built: `Resources/hand_ownership.py`** (stdlib-only, numpy-free, no imports at all), wired into `HandsTriggeredActions.py` **and** `LiveSnapDebug.py`. When a hand holding a cube vanishes and the SAME hand reappears in the other handedness slot, ownership follows it instead of the cube dropping. ⭐ **No protocol change** — DR-1 runs server-side, so a relabel arrives as "owner slot empties, other slot fills"; the client recognises it by POSITION, which is DR-1's own criterion, from data already on the wire. Same scoping call as D1 (spec §2.2). ⭐ **The threshold is MEASURED, not chosen** (`analysis/t3_relabel_threshold.py`): candidate displacement is **median 0.11 palm widths, 86% inside 0.5, only 3 of 57 between 0.5 and 1.0** — a hand that "moved" 0.11 palm widths between consecutive frames *is* the same hand, and that tight cluster is itself the evidence for the relabel reading. **0.5 pw sits at the knee of the cluster, deliberately not where it would catch the most events**: past the cluster you stop repairing relabels and start handing cubes to hands that are somewhere else. ⚠⚠ **THE GUARD IS WHAT MAKES THIS SAFE AND IT BLOCKS MORE THAN IT ALLOWS**: no transfer if the other slot already held a tracked hand, because that is two real hands and moving a cube between them is **N8 cube-stealing arriving through a new door**. It blocks 84 of 141 candidates. ⭐ **Effect: 49 of 236 vanish-while-held moments now keep their cube** (the remaining 8 candidates fall outside the threshold; 95 are true dropouts and belong to D2). ⚠ **State migration is the subtle part**: the orientation filter and Horn reference MOVE with the cube (both computed from world landmarks alone, so they describe the physical hand — and moving them is what prevents an orientation pop, since `grab_hand_orientation` was captured against that same stream); DR-2's `PalmFacingTracker` does NOT (it is chirality-sensitive, so its frozen sign is in the old label's convention — carrying it across would be a §13.6.1 inversion). ⚠⚠ **SCOPE, so this is not mistaken for a full close: the two-hand SWAP is NOT fixed** (both hands present, labels exchanged — the owner slot never empties, so nothing fires and the cube silently follows the wrong physical hand). That is spec §0.4's duplicate-label case and it stays open. Verified: `analysis/verify_hand_ownership.py` + `verify_d1_wiring.py` §5. Prior status follows. ⛔⛔ **RE-OPENED 2026-08-21 BY MEASUREMENT — DR-1 REDUCED IT, DID NOT CLOSE IT** | ⭐⭐ **THE MEASUREMENT THIS ROW WAS WAITING FOR ARRIVED FROM PHASE D, AND IT IS NOT THE ANSWER ANYONE EXPECTED.** `analysis/d2_bridge_ab.py` classified every spurious cube release across 36 takes and 40,307 held frames: **205 of them, of which only 83 are true dropouts.** **113 are the owner's own hand reappearing under the OTHER handedness label** (99 `IDENTITY/RELABEL` + 14 `MIXED/RELABEL` — a hand carrying the other label within 2 palm widths of where the owner hand just was, i.e. the same physical hand, relabelled), and 9 are a genuinely different hand. ⚠ **These recordings were made with DR-1 RUNNING.** So the 2026-08-02 live test was not wrong — the symptom did not occur while the operator provoked it — but "did not occur in one session" was never the same as closed, and the row's own status line said so. ⭐ **AND THE ROOT CAUSE IS NOT DR-1's ACCURACY, IT IS THE KEYING**: cube ownership is keyed by the handedness LABEL (`cube_owned_by("Right")`), so any relabel — a DR-1 error *or* a DR-1 correction — silently orphans a held cube. Spec §0.4 identified the mechanism; what is new is that it is **the single largest cause of spurious releases, larger than dropouts.** ⭐ **Proposed fix, NOT built, owner's call: key ownership on the DR-1 TRACK rather than the label.** That is a design change to `CubeWindow`'s ownership primitives, not another filter — and it would remove a defect class rather than damp it. ⚠ **Do NOT "fix" this by widening D2's bridge window.** Bridging papers over relabels cleanly (pop/save 0.00 at 150 ms, because the hand is in the same place) and that is exactly what makes it a trap: a heuristic that hides an unfixed root cause, against the standing keep-the-rule-set-small preference. Prior status follows. **FIXED by DR-1, live-confirmed 2026-08-02 — but NOT yet closed by measurement.** **Live test passed** (spec §0.6): the symptom did not occur while the operator actively tried to provoke it. **The M0 regression metric is still unmeasured** — "2 jumps → 0" needs a fresh recording replayed through `AnalyzePerceptionBaseline.py`, which a live test does not produce. Per A10, measurement is what closes this, so it stays open. Root-cause account follows. **Not two-hand confusion** — a matched near-miss control produced 0 events despite 28.6% occlusion in the overlap take. Actual cause: **MediaPipe's handedness LABEL is unstable under rotation** — flips on a single hand (18 events in `pitch_sweep_fast`, at score 0.663 vs 0.95–0.99 baseline) and **duplicate labels** (both hands labelled the same: 4/9/12 frames). Ownership is keyed by handedness, and `extract_hand_by_type` returns the first match or nothing → wrong hand claims the cube, other hand reads as not-detected → tracking-loss drop. **DR-1 is now the primary fix; M4's χ² gate demoted to belt-and-braces.** Regression metric: 2 jumps in the old baseline → 0 |
| T4 | Yaw / palm-sinking in translation | pipeline | deferred | 1.4, 1.2, 4.1 | §14.1.1. **Newly mapped** (A8): M9's foreshortening correction is the concrete fix its "startup calibration" note gestured at |
| **T6d** | ⛔ **THE ANISOTROPIC 2×2 FIT — live, with sliders** | perception | ⛔⛔ **BUILT, LIVE-TESTED OVER FOUR SESSIONS, AND REJECTED BY THE OWNER 2026-08-24** (*"the anisotropic fit bring very minor improvement and I don't want to ship it"*). ⭐ **Nothing to revert — production never ran it.** Removed from `LiveSnapDebug.py` entirely (sliders, HUD, presets, A/B rig, recorder fields); the estimator survives in `palm_rotation.py` only because `analysis/t5i_zscale_sweep.py` and `t5j_roll_axis.py` drive it. ⭐ **The measured reason it was invisible: the two panels' cube orientations differ by a median of just 4.83° (p90 17.4), FLAT across every palm-tilt band.** Original status: How to run it: the top block of `HANDOFF_T6_ORIENTATION_FROM_2D.md`; what was built and the four decisions inside it: **§2.0.17**; the fit and its numbers: §2.0.16 | T6 (built) | **WHY IT EXISTS**: four estimator REPLACEMENTS were built and A10-rejected, but they mapped the problem exactly — **Horn's flaw is BIAS (it eats a fabricated z) and every per-frame replacement's flaw is VARIANCE**. The survivor is a CORRECTION that keeps Horn's five-point averaging and fixes only the tilt. ⭐⭐ **The correction must be ANISOTROPIC and that is the whole insight**: yaw compresses the palm's WIDTH, pitch its LENGTH — perpendicular directions — so a gain depending on the compression direction ψ can treat them oppositely, which no scalar can. `g(ψ) = a + b·cos2ψ + c·sin2ψ` **is a symmetric 2×2 evaluated on that direction**. Measured need: **1.15 for yaw-like ψ, 1.55 for pitch-like** — genuinely different, which is why every scalar attempt failed and why the docs' "no k improves both" conclusion was right about scalars and wrong about the general case. **RESULTS, fitted per recording against camera-independent objectives (SCATTER = spread about the take's own mean axis; DRIFT = mean axis at a low turn vs a high turn — ⭐ the owner's complaint as a number, since the lean grows with the turn)**: PITCH **drift 76.4° → 23.6°**, scatter 44.4° → 21.2°, gain 0.65 → 1.24; YAW scatter 9.5° → 7.4°, gain 0.82 → 0.95. ⛔⛔ **THE OPEN GAP, AND THE SLIDER RUN IS ITS ANSWER**: a yaw sweep exercises only ψ≈0 and a pitch sweep only ψ≈90°, so `b` and `c` are **fitted but UNCONSTRAINED** — the pitch fit puts gain 0.15 at a ψ its recording never visits. **Live hand exploration covers the intermediate ψ no recording does**, so ⭐ **RECORD the slider session with its parameter values in `meta.json`** — that take becomes the diagonal-ψ data needed to fit the 2×2 as ONE object. ⚠ Jitter deferred by the owner, and note it has only ever been measured RAW, bypassing the shipped `orientation_filter`. ⚠ Roll is not a target (owner) — guard only against the palm-facing degeneracy and division by zero. ✅ **AS BUILT**: `AnisoParams` + `rebuild_terms` + `RebuiltNormalHorn(params=...)` in `palm_rotation.py`, sliders/HUD/recorder in `LiveSnapDebug.py`, **production untouched**; 23 golden suites pass, `parity_replay` clean, and the toggle-OFF path is **measured byte-identical to shipped Horn over 975 frames**. ⭐⭐ **ψ IS NOW VALIDATED ON REAL DATA, not argued**: from the pixels alone the yaw take piles up at ψ≈0/180 (61%) and the pitch take at ψ≈90 (85%), exactly as the model-frame definition predicts, and ψ is invariant under in-plane roll on synthetic input. ⛔ **Nothing here has been through A10** — the run is a feel test plus a capture; the accept/reject numbers come from the recording it produces. |
| **T6** | ⭐⭐ **ORIENTATION FROM 2D (planar PnP) instead of from MediaPipe's predicted depth** | perception | ⛔⛔ **BUILT AND A10-REJECTED 2026-08-24 — the code ships in `estimators()` only, the two call sites are UNCHANGED, production untouched.** Yaw, the show-stopper, gets **WORSE** (median/frame **13.0° → 29.8°**); pitch **GAIN is fixed** (0.74 → **0.99**). ⚠⚠ **FOUR EXPLANATIONS TESTED AND ALL REFUTED — do not re-run them**: the near-edge-on planar degeneracy (PnP loses in EVERY rotation band, not just at 90°), twin-branch flips (**12 in 508 frames**, and flip-frame error 27.9° ≈ held-frame error 29.9°), model shape (session measures 1.228 vs the model's 1.280; forcing the session shape gives 29.3° → 27.5°), and the assumed FOV (swept 30–120°, best **16.3° at 100°**, still worse than Horn's 13.0°). ⭐⭐ **THE FINDING WORTH CARRYING IS AN AMENDMENT TO THE PREMISE**: T6 rested on *"the 2D landmarks are good; the predicted depth breaks the rotation"* — but the first half was an **INFERENCE from roll being accurate, and roll was measured with HORN OVER WORLD LANDMARKS, so it never tested 2D alone.** T6 is the **first direct test of a 2D-only pose and it is worse.** ⛔ The planar model is NOT the culprit: reprojection RMS is **2.1–2.6 px median** on every take, i.e. the palm's own documented 2.76 mm rigidity (~3.1 px at 0.5 m) — the model fits, and the residual is simply at the scale that corrupts the out-of-plane component, very likely **systematically** (the palm flexes with pose) rather than randomly. ⭐ **STEP 7's OWED NUMBER WAS PRODUCED ANYWAY**: FOV sensitivity is **~2–4° of axis error per 10° of FOV error** (60°→29.8°, 70°→20.0°, 80°→18.2°) — see **U12**, and note it is the **U3 port risk** in one figure. ⭐ Two instrument defects were caught by measurement rather than reasoning and are the reusable part: `BACK_TO_CAMERA_NZ_POSITIVE` derived as True measured **False** (81.2%/18.8%, 9403 frames) — §13.6.1's exact shape, caught this time; and `verify_palm_rotation.py`'s fixture **was not a hand** (orthographic `px`, THUMB_CMC at the origin, an invented palm shape), never exercised because every prior estimator ignored `px`. Prior status follows. **DESIGNED 2026-08-23 — OWNER CALLS THE DEFECT A SHOW-STOPPER** | 4.2 | **THE DEFECT**: the object does not turn purely about the vertical — it **LEANS up to ~27°** at a 60–90° hand turn. ⭐⭐ **CAUSE ESTABLISHED BY TWO INDEPENDENT ROUTES**: scaling world z slides the yaw tilt 14.5°→0.6° (§14.3.4.9), and **ROLL — the one axis that needs NO depth — measures gain 1.02 with the smallest axis error (6.7°), while yaw (1.13, over) and pitch (0.74, under) are wrong in OPPOSITE directions** (§14.3.4.10). MediaPipe's 2D is good; its predicted depth is what breaks rotation. **THE FIX**: replace `palm_rotation.Horn`'s 3D↔3D fit with a **2D↔3D fit** — solve the pose that best PROJECTS a canonical palm onto the observed PIXEL landmarks, so predicted z is never consumed. Literature prescribes the same (arXiv 2506.11133 *Implicit Camera Alignment* does exactly this on MediaPipe 2D keypoints; EPro-PnP arXiv 2303.12787 is the general form). ⭐ **FOUR REASONS IT FITS HERE**: (1) ⛔ **no MANO, so no licence problem (N13)** — it needs only the rigid 5-point palm and its anthropometry is ALREADY in `palm_depth.NOMINAL_SPAN_M`; (2) the planar two-fold ambiguity is **already solved** — IPPE returns both poses with reprojection errors and **U7's `signed_palm_volume` is the disambiguator**; (3) the camera model shipped with 4.2 (`palm_geometry.focal_px`); (4) ⭐⭐ **the measurement rig is finally COMPLETE** — `t5i` scores yaw+pitch (mean, median, gain), `t5j` scores roll depth-free, so a replacement is A/B-able against Horn on identical frames. ⚠⚠ **COSTS, before anyone starts**: ⛔ **the PORT CONTRACT** — `palm_rotation` is stdlib-only/numpy-free so it can be transliterated (U3); **cv2.solvePnP would break it**, so budget a stdlib IPPE (homography + local analytic solve); ⚠ **PnP needs INTRINSICS and ours are ASSUMED (60° FOV)** — focal error corrupts the OUT-OF-PLANE component, i.e. exactly yaw/pitch, which is **the first hard technical reason for U12**; ⚠ **NOT a rerun of 2.3** (those five nulls re-weighted the FUSION of a bad signal; this replaces the INPUT); ⚠ **A10 in full** — must beat Horn on all three axes AND not regress jitter in real handling, the trap that killed the 9-point constellation. ⚠ Independent of 4.4+B5 in both directions. Full design: `GESTURE_PIPELINE_SPEC.md` §14.3.4.11 |
| **L1** | ✅ **ROTATION SMOOTHING — a TIME CONSTANT, not a per-frame factor** | responsiveness | ✅✅ **SHIPPED TO PRODUCTION 2026-08-24, owner-settled live at τ = 20 ms.** Full account: **§14.3.6** | — | **THE COMPLAINT** (owner): *"the cube is lagging the hand and this feels very uncomfortable."* ⭐ **FOUND BY MEASUREMENT, NOT BY READING**: end-to-end lag measured at **128 ms** by shift-aligning the cube against an UNSMOOTHED replay of the same take. ⭐ **ONE SOURCE**: `cube.orientation = slerp(cube.orientation, target, 0.35)`, introduced in `b0035a4` (2026-08-01, *"building the rotation"*) at 0.25 and raised to 0.35 in `b003cfe` the same day — **the original rotation build, not the steal work, not extrapolation, not a jitter gate** (the owner's three guesses; recorded so they are not re-searched). ⛔⛔ **TWO INDEPENDENT DEFECTS ON THAT ONE LINE. (a) UNITS**: a fixed per-FRAME factor is a settling time of 2.32 FRAMES, so the feel is whatever the camera does — measured **111 ms at 48.0 ms/frame** and **149 ms at 64.0 ms/frame**, i.e. **34% laggier in a darker room**, because the webcam drops its rate under auto-exposure. ⭐⭐ **The frame interval was proved camera-bound, not compute-bound: the gap is IDENTICAL with and without a hand in frame (64.1 vs 64.0 ms)**, and MediaPipe plus the whole gesture path only run when a hand is present. **(b) MAGNITUDE**: 0.35 was tuned against the GRAM-SCHMIDT estimator (p95 21.91°, **max 144.19°**); Horn shipped 2026-08-17 at p95 11.71°, max 25.07°, and **the smoothing was never revisited after the signal it smooths got that much cleaner**. Measured trade, identical input to every arm: per-frame 0.35 → 128 ms lag / step p95 11.29°; τ 149 ms → 128 ms / 11.44° (the old feel, in the new unit); τ 80 → 64 ms / 12.76°; τ 40 → 0 ms / 13.93°; **τ 20 → 0 ms / 14.64° (SHIPPED)**; τ 0 → 0 ms / 15.17°. **All 128 ms bought a 26% jitter reduction.** ⚠ "step p95" includes genuine hand motion so it overstates jitter absolutely; it is a fair RELATIVE comparison because every arm replays one take. ⭐ **THE FIX**: `factor = 1 − exp(−dt/τ)`, τ in ms, so settling is constant in real time — verified **20.0 ms at 48, 64 AND 16.7 ms/frame**, a 4× frame-rate range. ⚠ `dt` clamped at 200 ms so a dropout cannot drive the factor to 1.0 and teleport the cube, which would undo D3's resync blend. ⭐ **N6**: τ lives ONCE, in `hand_state.py` beside `BRIDGE_WINDOW_MS` — `LiveSnapDebug` cannot import `HandsTriggeredActions` (pygame window at import), so production could not be the source and a duplicated tuning constant is exactly how the two drift. ⭐ **HOW IT WAS TUNED**: a live slider in the debug tool plus a two-panel rig (`--slerp-ab`) running the same Horn with only the smoothing differing; the owner swept 0→149 and back and settled on 20 twice. |
| **F1** | ⭐⭐⭐ **THE CUBE'S TRANSFORM — POSITION *AND* ROTATION — FROM THE FINGERTIPS** | perception + gesture | ⭐⭐ **NEXT BUILD, owner-requested 2026-08-24. TO BE SPECIFIED BY THE OWNER IN ITS OWN CONVERSATION** — this row records the decision and the one trap, not the design | L1 (lag must be gone first, and it is) | **THE ASK** (owner): *"the grab and rotations with the anchor to the palm and limited knuckles arc as it is currently designed is too coarse: it does not render subtle movements of the fingertips which in real physical world rotate subtely the object. If I want to mimick grabbing and rotating small objects, I need to use fingertips to be able to rotate them subtely to align them for assembly. The palm + limited knuckles arcs is too coarse. I want to keep it, but as an indication (for orientation, for sign, for chirality, etc.) in support to the fingertips which we will build now."* Then, on scope: *"control the transform (Vector3 position and rotation quaternion) of the cube from the fingertips."* ⭐ **SO IT IS THE WHOLE TRANSFORM, not just rotation** — position and orientation both come from the fingertips, with the palm demoted to a SUPPORT role (reference frame, sign, chirality). Target use is **assembly-style alignment of small objects**. ⛔⛔ **THE ONE TRAP, AND IT IS ALREADY IN THE REJECTED LIST — READ IT AS SUPPORT, NOT AS A BLOCKER.** B4 rejected `PALM_AND_TIPS`, and the 9-point constellation was A10-rejected again on 2026-08-23, because the tips were added to a **RIGID-BODY (Horn) fit**, where finger motion is fitted as whole-object rotation — p95 9.85° → 27.79° in real play. ⭐⭐ **That is the SAME physical fact the owner is now asking to exploit, seen from the other side**: the tips MOVE relative to the palm, and that motion is the signal. ⛔ **So the new design must NOT be a rigid fit over palm+tips** — that arm is measured and dead. The tips have to enter as a **DEFORMATION relative to the palm frame**, or as contact points on the object, not as extra rigid points in one constellation. ⚠ **Two design questions the owner has not yet answered** (do not guess them): whether the object should follow the tips like a real grasped object (contact-point model) or take a bounded fine-TRIM on top of the palm's coarse rotation; and whether the drivers are thumb+index only (precision pinch) or every tip judged in contact. ⚠ **A changing driver SET can itself inject rotation** — a finger joining or leaving mid-hold moves the fit. ⭐ **Related and probably ONE project**: 4.4 (release trigger) and B5 (grab from finger arcs) are already recorded as the same mechanism from the other end, and N8 (stealing) rides on it. ⚠ The wire already carries world landmarks (`hands_world`), so nothing protocol-side blocks this. |
| **T7** | ⭐⭐ **WORLD-REFERENCED ROTATION — correct for a TILTED CAMERA, so a hand turn about the WORLD axis is what the cube reproduces** | perception | **DESIGNED 2026-08-24, OWNER-REQUESTED. ⛔ A NEW REQUIREMENT, NOT A RESTATEMENT OF T6, and the two must not be conflated. ⭐ SHIPS WITH U12, not after T6 — see the sourcing decision below** | T6, **U12** | **THE ASK** (owner): *"the user's camera may be tilted in pitch (especially if user uses mobile phone camera) and we need a correction so that rotation of hand in world axis is reproduced by the cube."* ⛔⛔ **FIRST, THE THING THAT WOULD OTHERWISE BE MIS-CONCLUDED: A TILTED CAMERA IS *NOT* THE CAUSE OF THE CURRENT ~27° LEAN, AND THIS WAS MEASURED, NOT ASSUMED.** The confound is real and sharp — `t5i` scores YAW against the *assumed* vertical (0,1,0) while `world_landmarks` are **camera-aligned**, so a mounting tilt would be scored as estimator error; and note the asymmetry that makes it suspicious, that the PITCH take's expected axis is *measured from the image* (the knuckle row) and therefore ABSORBS any tilt, which by itself predicts "yaw axis bad, pitch axis good" — exactly what is measured (14.5° vs 5.5°). ⭐⭐ **THE k-SWEEP SETTLES IT AT ZERO EXTRA COST, because a FIXED camera tilt is a rigid rotation of the whole scene and scaling world z CANNOT rotate an axis lying in the IMAGE PLANE.** Decomposing the fitted yaw axis against k: the x-component (in-image ⇒ camera ROLL) runs **0.241 → -0.011** and the z-component (out-of-plane ⇒ camera PITCH) **0.072 → 0.000** as k → 0. **Both collapse, so both are depth-induced and T6 owns them.** ⭐ It also BOUNDS this rig: implied camera pitch **≤ 4.2°** at k=1.00, and that is an upper bound still contaminated by the depth error. `analysis/` harness: the k-vs-axis-components decomposition (scratch, re-derivable from `t5i`). ⭐⭐ **BUT IT BECOMES FIRST-ORDER ON MOBILE, WHICH IS WHY THE ROW EXISTS.** A phone propped on a desk is routinely pitched **20–40°**. The lean a camera tilt θ produces at a hand turn φ is `acos(cos φ + cos²θ·(1−cos φ))` → **2θ at φ=180°**; at θ=20°, φ=90° that is **27.9°** — i.e. **a 20° phone tilt reproduces the entire show-stopper on its own**, with a perfect T6 underneath. ⭐⭐ **THE FIX IS ONE CONJUGATION, AND IT IS CHEAP**: `ΔR_world = C · ΔR_cam · C⁻¹`, with `C` the camera→world rotation, applied to the quaternion before rendering. Stdlib, numpy-free, portable by transliteration — it belongs in the estimator layer beside `palm_rotation`. ⭐⭐ **AND ONLY TWO DOF MATTER, WHICH GRAVITY SUPPLIES EXACTLY**: camera YAW leaves gravity unchanged in camera coordinates and is irrelevant (the fit is grab-referenced anyway); camera PITCH and ROLL are precisely what a gravity vector measures. So `C` reduces to "where is down, in camera coordinates", default `(0, 1, 0)` = level = today's behaviour. ⭐⭐ **WHERE `C` COMES FROM — OWNER DECISION 2026-08-24, AND IT IS A SEQUENCING DECISION AS MUCH AS A TECHNICAL ONE**: *"i don't want to introduce a different behavior between desktop and mobile for the moment, therefore i do not want to use gyroscope to detect gravity on mobile: keep that as a second order fallback improvement. I would prefer we later work on an initial calibration sequence at the beginning of the game which calibrates the game including camera tilt."* ⭐ **SO `C` COMES FROM U12'S CALIBRATION SEQUENCE, ON EVERY PLATFORM IDENTICALLY**, and `C` **defaults to identity (level camera) = today's behaviour** until it does. ⭐⭐ **AND THIS IS THE ARCHITECTURALLY BETTER CALL, not merely a preference**: an IMU is a **platform-conditional input into the estimator layer**, which is precisely the divergence the port contract and N6 exist to prevent — one code path, one `C`, sourced the same way everywhere, stays transliterable. ⛔ **THEREFORE T7 IS RE-SEQUENCED TO SHIP WITH U12, NOT AFTER T6.** With `C` = identity T7 is a **no-op**, so building it earlier is dead code with nothing to live-verify; the DESIGN is settled here and the two rows are built together. ⚠⚠ **THE IMU IS A RECORDED SECOND-ORDER FALLBACK, AND ITS TRIGGER IS SPECIFIC RATHER THAN "later": a calibration sequence assumes THE CAMERA DOES NOT MOVE AFTER CALIBRATION.** That holds for a webcam on a monitor and is **false for a hand-held phone** — an IMU is the only source that tracks a camera moving DURING play, and without one the game degrades silently after the user picks the device up. ⭐ **So revisit the IMU when, and only when, play on a moving hand-held device is actually on the table** — `DeviceOrientationEvent`/`Accelerometer` on web (⚠ iOS needs `requestPermission()` behind a user gesture), `CMMotionManager`/`SensorManager` native. ⚠ A third option exists and is NOT recommended: a head-upright proxy from a face model — it adds a model and a licence check (N13) to save a calibration screen that is being built anyway. ⚠⚠ **A PLAYABILITY TENSION TO DECIDE BEFORE SHIPPING, NOT DISCOVER AFTER**: with a strongly tilted camera the corrected cube turns about SCREEN-vertical while the hand *visibly* turns about a tilted axis on screen, so cube and hand visibly disagree. The owner's requirement is world-referenced and has now been stated three times consistently (*"reflect the physical world"*, *"rotation of the hand on the vertical world axis = equal rotation of the cube in the vertical 2d screen axis"*, and the ask above) — **so build it world-referenced**, but ⚠ **a live look on a deliberately tilted camera is what closes it**, per §13.6.1. ⚠⚠ **AND A CORPUS CAVEAT THAT LANDS TODAY (owner, 2026-08-24): THE CAMERA WAS MOVED BETWEEN RECORDINGS** — *"I am not using a fixed camera but I move my camera to capture the recordings."* Consequences, in order of how much they bite: **(a)** an A/B on the **SAME take is still sound** — both arms carry the identical offset — **so T6's acceptance protocol is unaffected**; **(b)** ⛔ **cross-take ABSOLUTE axis numbers are not comparable**, each carrying its own unknown offset, which is a live candidate for the otherwise-unexplained 3× gap between the two pitch takes (see `HANDOFF_T6_ORIENTATION_FROM_2D.md` §8); **(c)** ⛔ **it cannot be recovered retroactively** — gravity leaves no signature in hand landmarks and the corpus holds **no image data** — so **record the camera tilt in `meta.json` from now on**, which is the cheapest possible fix and only works going forward. |
| **PHASE B — THE BLOCK REPRESENTATION (owner direction, 2026-08-04). ⭐ THE ACTIVE PHASE.** ||||||
| B1 | **`hand_blocks.py` — the derived view** | perception | **DONE — status corrected 2026-08-17** (it had read "NEXT" while B2/B4/B8, all of which depend on it, were already closed). `Resources/hand_blocks.py` is built, stdlib-only, and is imported by `palm_anchor`, `palm_rotation`, `frame_gate` and every B4 harness | — | ⭐ **`GESTURE_PIPELINE_SPEC.md` §16.** Pure function `landmarks → {palm transform (2D pos, quaternion, scale), 5 arc deployment scalars}`. **A DERIVED VIEW ONLY**: no pipeline change, no wire-protocol change, nothing in production touched, so it costs nothing if it loses. Stdlib / numpy-free / no side effects / golden vectors before the port (U3 discipline). ⚠ **Thumb stays RAW landmarks** (saddle joint; an arc does not describe opposition). ⚠ **Scope is grab/rotate/translate ONLY** — future gestures may need raw landmarks, which stay available |
| B2 | **Block separability** | perception | **DONE 2026-08-04 — anchor claim HOLDS, outlier claim NOT supported** | B1 | ⭐ The position analogue of §0.15's orientation table, which does not exist yet (*"position prediction error is still unmeasured"*). Per **S1, mandatory**: report error at 1/2/3-frame horizons and **beat a zero-velocity AND a constant-velocity baseline at every horizon** — the discipline that caught published predictors losing to trivial baselines. **This measurement decides whether B3 is worth building at all**, exactly as the 1.5→1.6 gate did |
| B3 | **Palm-transform predictor** | perception | queued | B2 | **Spec §10.4/S2.** Build with the amended parameters, not M7 as written: **(a) filter the derivative BEFORE extrapolating** — never a raw two-sample ω/v, which is where TurboTouch's 2–3× gain came from; (b) speed-gated with a dead-band (prediction OFF below ~0.03 rad/s); (c) damped extrapolation λ≈0.3–0.5; (d) post-filter the predicted signal; (e) **LaViola double-exponential smoothing**, published ≈Kalman accuracy at ~1/135 the cost. ⚠ **ONE frame (~40 ms), never two** — §0.15 measured median 4.2–4.5° at one frame vs 7.3–8.0° at two. ⚠ Report **Nancel's perceptual side-effect metrics** (lateness, overshoot, jitter, jumps, spring), never RMSE |
| B4 | **Anchor + rotation A/B (blocks)** | decision | ✅ **CLOSED 2026-08-17 by the live six-arm session — §14.1 KEEPS, arm B REJECTED, `Horn(PALM_LANDMARKS)` SHIPPED to production and live-confirmed** | B1 | ⭐ **Results: §16.17.** ⛔⛔ **§16.14's headline is RETRACTED and the retraction is the important part: `SINK` is `corr(‖cube−o‖/s, edge_on)` while `Arm2D` DEFINES position as `o + s·(Rx·ex+Ry·ey)`, so `‖cube−o‖/s ≡ ‖R‖ ≡` frozen at grab — measured sd **0.0000** within a grab. Arm B could not have scored anything but 0. That is handoff trap #4 landing on this row's PRIMARY criterion**, and any future anchor metric must compare against a quantity the anchor does not define. ⛔ Arm B also LOSES the one criterion still able to discriminate: still-hand step worse on all 4 takes (yaw 5.18→**12.72**, back 5.66→**11.27**), free-play position max 49.60→**261.68 px** — because `s`/`ex` ride TWO landmarks while §14.1 averages nine. ⚠ Arm B's rotational behaviour was nonetheless the honest one (palm-frame bearing range **0.0°** vs §14.1's **358.8°**); if an anchor is revisited, keep that and pair it with `hand_skeleton.palm_width_world()`. ✅ **HORN: `PALM_AND_TIPS` REJECTED** (p95 9.85→27.79 in play — finger motion fitted as rotation; the 'fingers still' protocol HID it), **`PALM_LANDMARKS` shipped on DESIGN grounds, not measured benefit** (balanced blind 4–2, p=0.34; p95 3–3). ⭐⭐ **Both estimators emit the SAME ~60° jumps to within 1° → those jumps are in the LANDMARKS and no rotation estimator can fix them (see T1/T2).** Harnesses: `analysis/b4_orbit_and_sink_audit.py`, `b4_six_arm_verdict.py` |
| B5 | **Grab signal from arcs, + intent prediction** — ⭐ **ONE PROJECT WITH 4.4** | feature | queued | B1, B4 | ⭐⭐ **OWNER DECISION 2026-08-23: 4.4 AND B5 ARE ONE PROJECT, NOT TWO QUEUE ITEMS** — *"treat this as one project with 4.4"*. They are the same mechanism seen from both ends (grab and let go) and they read the SAME signal: how open or closed each finger is. Building them separately means building the finger measurement twice, and it is what the owner already said about N8 — *"a matter to be corrected once we better build the mechanism for grab-ungrab"*. ⚠ Whichever row is picked up first, read BOTH rows before starting. N8 rides on the same project. The arcs are a natural grab/release substrate (open vs closed is one scalar per finger). ⚠ **S3 BINDING: predicted state must NEVER reach the gesture state machine** — predicted blocks for rendering/attachment, UNPREDICTED blocks for grab/release. Apple ships exactly this split. This is also where **S12 endpoint/intent prediction** belongs (pre-arm the snap, choose the target), not render-latency hiding |
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
| 4.1 | M9 metric depth | perception | ⭐ **ESTIMATOR HALF BUILT + A10 PASSED 2026-08-22** — `Resources/palm_depth.py` (`DepthRatioTracker`): max4 over the rigid palm quad vs a grab-time baseline, S10 freeze in the edge-on band, rate limit + clamp. Measured (`analysis/m9_depth_envelope.py`): responsive **3.68x** on `depth_sweep`; on rotation-in-place the estimator's own error is **1.30x worst case** against a naive width-only **8.04x** — a **4.4x** reduction in false depth. ⚠ **Quote the drift-floor-corrected number, not the raw span**: 1.40x of the clean yaw take's 1.82x is the operator's arm really moving. 24 golden vectors in `analysis/verify_palm_depth.py`. ⭐ **No calibration step is needed** — the envelope is 3.59x and `d0` is per-grab (see the row's note and spec §14.3.4.6). ⛔ **STILL TO DO for 4.1: the `HandState` v2 WIRE MIGRATION carrying `trackId`**, and wiring the ratio into the cube (that is 4.2). Prior note follows. **UNBLOCKED 2026-08-04 — the scale reference exists. ⚠ Read `GESTURE_PIPELINE_SPEC.md` §14.3.1 BEFORE building: the anchor must be MULTI-anchor, and a yaw take must be recorded first** | ~~1.7~~ — **satisfied**: `hand_skeleton.palm_width_world()` supplies the per-session scale reference without needing 1.7's fit (spec §0.18) | ⚠ **NO LONGER NEXT — PHASE D (dropout mitigation) RUNS FIRST, owner direction 2026-08-21.** Reason is measured, not stylistic: a single missing frame releases a held cube today, which cost **98 spurious drops** across the corpus (D0), and 4.1 leads to 4.2 (Z-axis) whose own grab handling would be built on top of that defect. ⭐ Still the recommended build AFTER Phase D. The one Phase 1 deliverable that survived, on the one quantity this sensor measures well (palm width, near pose-invariant, §10.1). Leads directly to 4.2. Prior note follows. Refines §14.3's ratio design: never a single bone; foreshortening-corrected. ⚠ **Dependency moved to 1.7** — 1.4 cannot supply the scale reference; the imposed skeleton can. ⭐ **Literature confirms the ratio form is the right call**: absolute camera-space hand position from monocular RGB is only ~3.5 cm at SOTA (ScaleHP 2026), while a scale *ratio* needs only temporal consistency of one anchor; **palm width is the documented anchor of choice** (near pose-invariant, unlike finger spans). ⚠ **S10, missing from both M9 and §14.3: the palm-width anchor COLLAPSES edge-on, so the depth ratio must FREEZE inside the DR-2 band** (reuse `PalmFacingTracker`'s pattern) or Z-control inherits the pitch-crossing failure |
| 4.2 | **Z-axis translation (§14.3)** | feature | ✅✅ **BUILT AND OWNER-CONFIRMED LIVE IN BOTH TOOLS 2026-08-23** (debug: *"yes. this is working properly"*; production: *"this is working fine"*). 23 golden-vector suites pass, `parity_replay` reports NO DIVERGENCE, and the production take proves Z was actually exercised — objects swept **0.316–0.850 m**, 10 snaps under the 3D gate, 0 play-area violations. ⭐ The take also re-derived the constant: its hand depth medians **0.502 m** against the 0.497 m corpus median `REFERENCE_DEPTH_M` came from. Full account: `GESTURE_PIPELINE_SPEC.md` §14.3.5; behaviour: `GAME_RULES.md` rules 7–10. ⭐⭐ **THE CONSTANT THAT WAS ABOUT TO BE WRONG:** an object's resting depth was first set to 0.40 m on the strength of U9's *"40 cm IS the closest the operator actually works"* — but **that sentence reads the corpus's p99 palm width, i.e. the CLOSEST APPROACH.** Measured over 86 109 trusted hand-frames across 65 sessions (`analysis/m9_working_distance.py`): median **0.497 m**, p1–p99 0.309–0.837. Against 4.2's own axial gate an object at 0.40 m is reachable on **70.9%** of frames, at the median **91.2%** — ⛔ a quarter of frames unable to pick anything up would have read as a BROKEN BUILD, not a mis-sized constant. `REFERENCE_DEPTH_M = 0.50`; U9's derivation depth survives as `U9_DERIVATION_DEPTH_M`, used only by the vector asserting the world margin and the pixel margin still meet there. ⭐ **Reusable: a constant borrowed from another row's derivation inherits that row's QUESTION, not just its number.** ⛔ **THE 3D GATE IS AN ELLIPSOID, NOT A SPHERE** — lateral stays the projected grab radius (X/Y feel untouched), axial gets its own `GRAB_Z_TOLERANCE_M = 0.15 m`. A sphere would have given the small object a 43 mm axial tolerance while the hand depth is scaled by NOMINAL anatomy, so a user 20% off the median reads ~80 mm away CONSTANTLY — un-grabbable, and it would have looked like a broken build. ⭐ **§14.3's "absolute, not relative-delta" and §14.1's no-pop rule only LOOK contradictory**: `cube.depth_m = grab_depth_m / ratio`, and the ratio's `d0` is captured AT THE GRAB — memoryless (decision 2 satisfied) and exactly 1.0 on the grab frame (no pop). ⚠ **It is the play volume's WALLS, not the tolerance, that bound re-grabbability**: release freezes an object in all three axes, so the walls are the measured p1–p99 of the hand's own working distance (0.30–0.85 m), cross-checked against `m9_depth_envelope.py`'s independent 0.26–0.94 m reach. ⚠ **`cube.size` is now the extent at the RESTING DEPTH only** — the centre, the clamp, the grab radius and both renderers read `projected_size_px`; `_top_left_for_center` was DELETED from both tools because it converted with the nominal size. ⭐ New harnesses: `analysis/m9_working_distance.py`, `analysis/verify_play_volume_from_recording.py`, `verify_palm_depth.py` §§10–14, `verify_play_area.py` §2. Recorders at `recorder_schema: 3`. | 4.1 | ✅ **DECISION 1, OWNER 2026-08-23 — NO SNAPPING WHILE DEPTH IS FROZEN.** When `depthValid` is false (the S10 edge-on freeze) a snap is REFUSED. §14.3.2 left this open; it is now closed. ⭐ **Same philosophy as DR-2 and U8: suppress rather than guess** — a frozen depth is a held value, not a measurement, and 3D snap gating built on one would be deciding proximity from a number the sensor is not currently supplying. ⚠ **FLAGGED AS REVISITABLE FOR GAME USABILITY** (owner's words): if refusing feels too strict in play, the fallback to try is degrading to the 2D radius while frozen rather than refusing outright. **Do not change it without a live take** — measure how often the freeze coincides with a grab attempt first. ✅ **DECISION 2, OWNER 2026-08-23 — THE PLAY AREA IS A WORLD-SPACE VOLUME, FRUSTUM-AWARE**, not a screen-space rectangle. See the U9 row for what that means for `clamp_to_play_area`. ⚠⚠ **ALSO REVISIT U9's PLAY-AREA CLAMP HERE (owner, 2026-08-23) — it is a 2D rule and Z breaks its assumption.** The display shows the camera's FIELD OF VIEW, a frustum rather than a box, so an object's PROJECTED extent shrinks as it moves away and grows as it comes near. `clamp_to_play_area(x, y, size, frame_size)` takes `size` as a constant today only because nothing drives Z. Once this ships, **`size` must become the extent AS PROJECTED at the object's current depth** — otherwise a distant object is held needlessly far from the edge and, the dangerous direction, **a NEAR object's real footprint exceeds the margin and can still overflow the play area**. ✅ **ANSWERED (owner, 2026-08-23): a WORLD-SPACE VOLUME, accounting for the camera frustum.** So the clamp moves into world coordinates: at the object's depth, take the frustum's lateral extent, inset it by the world margin, and clamp the object's world position inside that — then project. The on-screen boundary therefore MOVES with depth (inward as the object recedes), which is correct and expected, not a regression. ⚠ Do it in the SAME pass as **U2**'s bounding-radius change — both replace the `size` term, and doing them separately means touching this code twice. |
| 4.3 | M10 commitment dynamics | perception | **M10.7 DEFERRED BY OWNER 2026-08-04 — do not build** | ~~1.6~~ (parked) | **M10.7 changes `GAME_RULES.md` rule 2** (immediate drop → 400 ms grace) and would close N8. **Owner decision taken: leave it undecided for now** — *"I don't want to overbuild with layers of rules for the moment."* ⚠ Treat that as a **standing preference on RULES**, the counterpart of the no-heuristic-pile-up rule on filters: the rule set stays small and legible, and a rule whose job is to patch another rule's consequences is what is being avoided. **Do not re-propose it as a side effect of another item**; revisit only if immediate-drop becomes a felt problem in live play, and then ask explicitly. The rest of M10 also loses its 1.6 dependency (parked) and would need re-deriving before it could start |
| 4.4 | **Hand-open release trigger (§14.2)** — ⭐ **ONE PROJECT WITH B5** | feature | designed, not built | 4.3 | The sole active release plan since closed-fist was parked. ⭐⭐ **OWNER DECISION 2026-08-23: 4.4 AND B5 ARE ONE PROJECT, NOT TWO QUEUE ITEMS** — *"treat this as one project with 4.4"*. They are the same mechanism seen from both ends (grab and let go) and they read the SAME signal: how open or closed each finger is. Building them separately means building the finger measurement twice, and it is what the owner already said about N8 — *"a matter to be corrected once we better build the mechanism for grab-ungrab"*. ⚠ Whichever row is picked up first, read BOTH rows before starting. N8 rides on the same project. ⚠⚠ **AND ITS DISCRIMINATION ARGUMENT MUST BE RE-VERIFIED, NOT INHERITED (owner, 2026-08-23: capture it here, resolve it when 4.4 is built).** §14.2 distinguishes "release" from "moving toward the camera" by arguing a release scales the FINGERS while Z-translation scales fingers AND wrist together. That was written against a HYPOTHETICAL Z-translation. The real one (4.2) reads only the four RIGID PALM SPANS and deliberately excludes every MCP→TIP length, because those change with GRIP. ⭐ So the two gestures touch DIFFERENT landmarks, which should make them easier to separate than feared — but check it against `palm_depth`'s actual ratio on real takes, do not carry the old reasoning over. |
| **PHASE 5 — optional** ||||||
| 5.1 | M3b synergy subspace | perception | **optional — future menu (owner, 2026-08-23)** | 1.5 | ⭐ **OWNER DECISION 2026-08-23: the whole 5.x block is OPTIONAL — a MENU FOR FUTURE POTENTIAL IMPROVEMENT, IF REQUIRED.** Nothing here is scheduled and nothing is waiting on it. Its value is that when a hard problem does appear, the options are already researched and priced. ⛔ Do not pick one up speculatively; each is explicitly gated behind a MEASUREMENT that has not yet demanded it. May make parked row 2 viable again — **do not un-park without asking** |
| 5.2 | M3 IK (26-DOF) | perception | **optional — future menu (owner, 2026-08-23)** | 5.1 | Subsumes 3a/3b, costs more. See 5.1 for the standing decision on the whole 5.x block |
| 5.3 | Trajectory gesture classification | perception | **optional — future menu (owner, 2026-08-23)** | 5.1 | See 5.1 for the standing decision on the whole 5.x block |
| 5.4 | **NEW — causal SmoothNet-class temporal refinement** | perception | **optional — future menu (owner, 2026-08-23)** | 1.5, 1.6, 1.7 | **Spec §10.4/S9.** If the consistency gate + anatomical constraints + imposed skeleton leave a residual glitch tail, the documented next step is a **tiny per-joint temporal MLP** (SmoothNet): plug-and-play across estimators, and its published analysis targets exactly this failure shape — "highly unbalanced" errors, most frames fine, failures as large deviations over short runs. ⚠ Verify the causal-mode accuracy drop and window latency before committing. Only after 1.5/1.6/1.7 are measured |
| 5.5 | **NEW — multi-hypothesis / uncertainty-aware prediction (Waymo transfer, minimal form)** | perception | **optional/research — future menu (owner, 2026-08-23)** | 3.1 | **Spec §10.4/S11.** What transfers from MultiPath++/MotionLM is the *principle* — predict distributions not points, keep discrete hypotheses where the future branches — **not** the models (their scale, 3–8 s horizons, lane-graph context and GPU cost are all inapplicable at 40 ms on CPU, and at short horizons their own literature shows physics baselines win). Minimal forms: (a) prediction emits a variance growing with horizon and recent residual, used as the render blend weight; (b) **3-mode reversal blending {continue, decelerate, reverse}** weighted by acceleration-sign consistency — targets the overshoot-on-reversal failure directly; (c) research option: carry the mirror (bas-relief) pose hypothesis through the DR-2 band and let motion continuity select on exit. **Only if 3.1's measured side-effect metrics justify more machinery** |
| **NEW — surfaced by the 0.2/0.2b measurements** ||||||
| N1 | Re-express all frame-count parameters in ms | perception | queued | — | §0.3: pipeline runs at **~24 fps, not 30** (older recorders synthesised a 33 ms cadence, hiding this). M5e's 3-frame dwell, M10's 3/4-frame dwells and M4's 8-frame coast are all ~38% longer in wall-clock than intended |
| N2 | Pose-normalise the bone residual before M4 consumes it | perception | queued | 1.4 | §0.3: the raw residual tracks hand rotation, not per-landmark quality; used directly it would down-weight every landmark whenever the hand moves |
| N3 | Counted-crossing sequence → **speed-threshold sweep** | perception | **CLOSED 2026-08-03** | — | **§0.8.** Four daylight takes at 24.1–24.5 fps, counted ground truth. **The totals were lying**: delta stays −4..+9 at every speed, but the *physically-implausible* flip fraction rises **6% → 58%** as cycle time falls 4.44 s → 0.96 s. Missed genuine crossings and spurious flips **cancel in the total**. §0.7 called this unresolvable without a rotation timeline — it is resolvable from the edge-on plausibility test alone. **Knee at ~1.3 s/cycle.** Honest limit: the fast take reached only 0.96 s/cycle, not the prescribed 0.5, so breakdown is bracketed, not bounded. Prior status follows. §0.7 + §0.7.1. **The recorded take was DELETED** (15.77 fps, poor light) — its numbers are indicative only and the data is gone. **Superseded by four speed-decoupled takes** with prescribed cycle counts and explicit PITCH axis, which locate the *threshold* at which crossings start being missed rather than yielding one blended count. **Indicative prior result (unsupported, do not cite as measurement)**: 29 cycles = 58 expected sign changes, detected **52 (Left) / 50 (Right) — UNDER-detection, not an excess**, which **reverses** the prior working suspicion of a large spurious population. **⚠ Unit trap, recorded because it caused a wrong reading once**: the operator counts palm→back→palm as ONE crossing; the analyser counts sign inversions. Compare against `expected_sign_changes` (58), never `counted_crossing_cycles` (29). **Still open**: totals cannot rule out a compensating mix of missed genuine crossings plus spurious flips — that needs per-flip matching against the rotation timeline. **Also confounded by N10**: this take ran at 15.77 fps, so the 63.4 ms interval makes genuine band-traversing crossings easier. **Re-record in better light before concluding.** Original note: §0.3 flagged the slow-sweep flips at edge-on 0.58–0.73 as suspicious, not diagnosed |
| N4 | External capture drive is unreliable | infra | **open** | — | E: dropped out ~4× in 15 min on 2026-08-02 (reads and writes both, WinError 21). Recorder now preflights and refuses rather than losing a completed take; analyser retries. Check cable/port and USB power-management, or switch to `--local` capture |
| **N5** | **DR-1 track-level hand identity (hysteresis)** | perception | **DONE — built, replay-verified AND LIVE-CONFIRMED 2026-08-02** | — | **Live test passed (spec §0.6)**: operator verdict "it's working" while deliberately rotating hands back-to-camera and crossing them; 16 tracker events, 0 errors/tracebacks; the transient-glitch branch held a 3-frame mismatch and the swap branch switched on a full 12 — the exact separation replay predicted. Original build account follows. §0.4/§0.5. A first stateless duplicate-resolver was built and **removed the same day** — score-based choice was a coin flip on 36% of frames and blind to 28 label flips. Replaced by `_HandIdentityTracker` in `hands_visualizer.py`: associate by **position** not label; lock after a vote; brief mismatch → hold, **long + confident mismatch → switch**; re-decide freely when a track ends. **A 'never switch' variant was tried and disproved** — position association swaps identities at a crossing, giving 528 overrides in runs of up to 225 frames. Replay result: duplicates **25 → 0**, longest wrong-hold **225 → 10 frames**, and **0 overrides/switches in all three control sequences**. This IS queue item 2.1 delivered early. **`SWITCH_MS` (12 frames/~500 ms) is TUNABLE — latency vs. false-glitch; re-derive if camera/fps/lighting change (spec §0.5)** |
| **N6** | **DR-1 parity: debug tool now shares the perception code** | infra | **RESOLVED 2026-08-02** | — | Was: `LiveSnapDebug.py` bypassed `hands_visualizer.py`, so DR-1 was production-only. Fixed the architecturally correct way per owner instruction ("I do not want to have a debug tool which is not in tune with the production"): the tracker was **extracted to `Resources/hand_identity.py`** — standalone, pure stdlib, no cv2/mediapipe/window side effects — and is now **imported by both**, not copied. `LiveSnapDebug.py`'s own latent duplicate bug (it keyed hands by handedness in a dict, silently overwriting one of a duplicate pair — the same defect that hid Object Jump Correction in the old recorder) was fixed in the same change. **Verified: production and debug produce byte-identical identity output across all 7 recorded sessions**, and exactly one tracker definition exists in the codebase |
| N7 | Drive `ASSUMED_FPS` from measured frame timing | perception | **DONE 2026-08-04 (DR-1). ⚠ `palm_geometry` still to do** | 0.1 | ⭐ **Built**: `FrameRateEstimator` in `hand_identity.py` — median of a 45-frame (~2 s) interval window, fed by a **caller-supplied** timestamp, never by reading the clock internally (a replay harness runs faster than real time, so an internally-sampled rate would look right in production and be meaningless in replay — the exact debug/production divergence class N6 exists to end). All four DR-1 dwells became per-instance properties re-derived each frame. `update(observations, now_ms=None)` — **omitting the timestamp preserves the old behaviour exactly**, so nothing broke while callers were wired. Production (`hands_visualizer.py`) and the debug tool (`LiveSnapDebug.py`) both now pass `time.perf_counter()`. **A/B (`analysis/n7_measured_fps_ab.py`): 20 of 21 sessions within 1 fps of 24 produce IDENTICAL assignments — a no-op where the old assumption held, which is the pass condition — while sessions at 19–21 fps now use a 10–11 frame switch dwell instead of 12, correcting a +14–24% overshoot.** ⚠ The 45-frame window was chosen against data: a 15-frame window tracked per-second jitter (reporting 15.7 fps in a session averaging 20.7) and made the dwell swing 8↔12 within one recording. ⭐ **`palm_geometry`'s half was then EXAMINED AND DELIBERATELY NOT APPLIED (2026-08-04)** — built, measured, reverted. **The time-based dwell froze DR-2 for +47.4% more frames (595 → 877)**, lengthening exactly the staleness window `GAME_RULES.md` rule 3 documents, for no correctness gain. Root of the misjudgement, worth carrying: `exit_run >= 2` exits on the SECOND consecutive above-threshold frame — **one frame interval, ~42 ms at 24 fps, not the ~83 ms "2 frames" suggests** — so a 100 ms time-based dwell needs FOUR frames and roughly doubles the freeze. ⭐ **The general rule this establishes: a "resume after N consecutive confirmations" DEBOUNCE belongs in frames; N1's re-express-in-ms applies to dwells representing real elapsed TIME (DR-1's voting windows) and not to debounces.** So `_ASSUMED_FPS` in `palm_geometry` is **not** the defect N7 fixed, and this item is CLOSED rather than half-done. Evidence, with the rejected variant kept in the harness rather than as dead code in the module: `analysis/n7_dr2_dwell_ab.py`. Prior note follows | **§0.7: frame rate is environment-dependent, not a fixed ~24** (15.1/15.77 fps measured at 22:18 vs 24.09–24.14 earlier the same evening). `SWITCH_FRAMES = round(500 × 24/1000) = 12`, so at 15.77 fps the dwell is **~761 ms instead of 500** — a 52% overshoot in the one parameter §0.5 flagged as most worth getting right. Original note follows. Hard-coded 24.0 in **`Resources/hand_identity.py`** (moved there from `hands_visualizer.py` when the tracker was extracted — N6); all DR-1 dwell constants derive from it, so a different camera silently changes every threshold. Should come from `HandState.tCapture` |
| N8 | **Cube can be stolen by occluding the holding hand** | gameplay | **recorded only — ⭐ now OBSERVED LIVE (2026-08-21), owner routes it to B5** | ~~4.3~~ → **B5** | ⭐ **No longer inferred.** The owner saw it repeatedly in the live D2/D3 session: *"the other jumps of cubes were caused when the second hand occludes the hand holding the cube: in such case, the cube jumps to the other hand."* ⭐ **Owner direction: fix it with the grab/release mechanism (B5), not with a patch here** — *"a matter to be corrected once we better build the mechanism for grab-ungrab"*. Today's snap is pure proximity, which is why anything near a released cube takes it. ⚠ **A share of what was seen may have been T3's reverted transfer rather than this release-then-snap path; the two produce the same symptom and were not instrumented apart. Instrument them separately when B5 is built — do not assume.** Prior note follows. Observed 2026-08-02. Hand A holds a cube; hand B moves in front of it; A's tracking is lost, rule 2 releases the cube, and B — which is right where A was, so inside the grab radius — snaps it a frame or two later. **Mechanism inferred from the rules, not instrumented.** §13.5's same-frame ordering fix only blocks re-snap on the SAME tick, not the next. Expected to resolve as a side effect of refining snap control: **M10.7's grace period would hold the cube through the occlusion, leaving nothing to steal**. Recorded so it isn't rediscovered as a new bug |
| N9 | **DR-1's duplicate-repair fallback fires in normal live use** | perception | **observed 2026-08-02, NOT diagnosed — deliberately not tuned** | 0.2b | Spec §0.6. §0.5 reported duplicates eliminated **structurally**, and the end-of-function invariant was described as a fuzz-found edge case reachable only when a detection jumps past `MAX_ASSOC_PALM_RATIO = 3.0` with both track slots full. It fired **3× in one short live session**. **No duplicate was emitted — the invariant did its job, which is why the live test passed** — but the frequency is new information the 7 recorded sessions did not predict. Two candidate causes, undiagnosed: the association limit is too tight for live crossing speed (it was derived from recorded motion of 0.6–1.4 palm widths), or a dropped detection frame (§0.3: 2.9% lost under fast motion) leaves a stale track position. **Do not tune the ratio on this evidence** — per A10 that is a measurement question, and the cost of leaving it is currently zero. Quantify from the 0.2b sequences |
| N10 | **Camera frame rate is environment-dependent (lighting)** | infra/perception | **open — leading hypothesis, not diagnosed** | — | §0.7. Same recorder/camera/machine/resolution measured **24.09–24.14 fps at 19:13–20:51 and 15.1/15.77 fps at 22:18–22:19**. Leading hypothesis: webcam auto-exposure lengthening frame duration in dimmer light — **untested**. Consequences hold regardless of cause: (a) N7 becomes correctness — no single measured constant is valid; (b) recordings are only comparable to each other if fps is comparable, so **`meta.json`'s `measured_fps` must be checked before any cross-session A/B** under A10; (c) the DR-1 live test (§0.6) ran at an unmeasured frame rate. Cheapest probe: record the same sequence in bright vs. dim light and compare `measured_fps` |
| N11 | **Left/Right asymmetry in sign-cue reliability** | perception | **NOT REPRODUCED — direction REVERSED on clean single-hand takes (2026-08-03)** | — | **Tested and the claim did not survive.** Two matched single-hand `palm_back_s2_slow` takes (16 cycles each, no duplicate-label contamination): **Right 25% implausible, Left 41%** — the opposite of the two-hand result (Left 7%, Right 23%). **So the original asymmetry was most likely a TWO-HAND artifact, not a property of the chirality correction.** Do not act on the original hypothesis. ⚠ The retest has its own confound — the left take ran at 21.12 fps vs the right's 24.11, and a longer frame interval mechanically inflates implausible flips — so this **disproves the direction without establishing the reverse**. Settling it properly needs matched-fps single-hand takes. Clean side-result: **both hands hit 32/32 exactly on total flips** while carrying 25–41% impossible ones, reinforcing §0.8's headline. Original observation follows. §0.8 Finding 3. The Right hand's implausible-flip fraction exceeds the Left's at **every** speed in the sweep (24 vs 6, 23 vs 7, 41 vs 15, 58 vs 50 %), consistently across four independent takes — systematic, not noise. **Candidate hypothesis only**: the handedness-dependent chirality correction is the one non-handedness-symmetric step in the pipeline, and §13.6.1's inversion bug lived exactly there. Do not act on this without measuring; a clean test is to re-run the sweep one hand at a time |
| N12 | **Held cube jumps as the hand crosses the horizontal (pitch) plane** | pipeline | **observed live 2026-08-03, NOT fixed — third symptom of a known weakness** | 3.3 | **Operator report during the DR-2 live test**: *"when the hand crosses the horizontal plane, the cube jumps slightly because the landmarks of the fingers become confused and the cube likely aligns quickly with the position of the confused fingers, before restoring to the correct position when the hand has crossed."* **NOT caused by DR-2** — DR-2 only changes the palm/back sign, which gates snapping, and never touches a held cube's position. Pre-existing. **This is the THIRD independent symptom of the same root weakness**, alongside T4 (yaw/palm-sinking) and Object Jump Correction: §14.1's translation anchors on **5 fingertips + 4 MCPs**, and fingertips are measurably the worst landmarks on the hand — bone-length CV 13–32% distally vs a **palm already rigid to 2.76 mm** (§0.2 finding 1). Spec M8a predicted exactly this (*"Fingertips determine whether a grab occurred; they must not determine where"*, anti-pattern #6). A7 deferred M8a to an A/B rather than adopting it — **this observation materially strengthens the case for running that A/B (item 3.3), and gives it a third concrete failure to measure against.** Do not modify §14.1 before the A/B, per A7 |
| N13 | **Commercial release forbids non-commercial-licensed dependencies** | governance | **BINDING — owner decision 2026-08-04** | — | ✅ **MODEL HOSTING VERIFIED 2026-08-23 (owner question): the MediaPipe model is BUNDLED, not hot-linked, on BOTH platforms.** Python loads `model_asset_path` → the local `Python_Server_MediaPipe_vision_pipeline/Resources/hand_landmarker.task`; the web port loads `${BASE_URL}models/hand_landmarker.task`, same-origin. **Zero references to `storage.googleapis.com` / `mediapipe-models` anywhere outside vendored `node_modules`.** ⭐ **The WASM RUNTIME is vendored too**, which is the part that usually leaks even when the model does not: `FilesetResolver.forVisionTasks()` points at `${BASE_URL}mediapipe/wasm`, and a **`postinstall` hook** (`Web/scripts/copy-mediapipe-assets.mjs`) copies the six runtime files out of `node_modules`, so a fresh clone cannot silently fall back to a CDN. `handTracker.js`'s header states the reason and cites `Specification.md` §10. ⚠ Paths use `import.meta.env.BASE_URL`, not a hardcoded `/`, so same-origin resolution survives sub-path hosting. ⚠ **WHY IT MATTERS EVEN THOUGH THE MODEL IS APACHE 2.0**: the Google-hosted endpoint is a developer convenience with no uptime guarantee, and Google's API terms apply to the SERVICE regardless of the model's own licence. Bundling avoids both. ⚠ Dead weight to strip before shipping: `gesture_recognizer.task` (from the REJECTED built-in-gesture experiment, §13.5) and the `_not_used/` copy. ⚠ **Licensing is NOT the main shipping exposure — camera PRIVACY is. See queue U10.** Prior note follows. ⭐ **Check the licence BEFORE proposing any model or package, and state it in the proposal.** Apache-2.0 / BSD / MIT are fine; "research use only", "non-commercial", CC-BY-NC are not. The game is intended for commercial release, so this applies to **offline tooling too**, not only shipped runtime code. **This killed item 0.5** (MANO, and therefore HaMeR and WiLoR). ⚠ **It also constrains item 1.7, which the spec calls "MANO-lite" — do NOT build it with actual MANO.** 1.7 needs a skeleton with *fixed bone proportions*; published anthropometric proportions are free and sufficient (§2f itself says population-average proportions suffice to start). ⚠ Note the trap 0.5 walked into: a permissive licence on the **code** does not cover **data** it generates from research datasets — Hand-BMC-pytorch is MIT but derives its constraint values from RHD/GANerated/STB/FreiHAND |
| N14 | **The recorded corpus contains NO image data** | infra | **established by exhaustive scan 2026-08-04** | — | The whole capture root is **390 `.json` + 25 `.jsonl`, 334 MB, zero image/video bytes of any extension**; `imwrite`/`VideoWriter` appear nowhere in the codebase. Covers all four subfolders, including the richly-annotated `Unsuccessful_grip` / `Pencil_style_grip` pinch corpora and `Position_during_rotation` — **those annotate LANDMARKS, not images.** Consequence: **no image-based model can ever be run over the existing sessions retroactively**, so any such proposal must price in re-recording and operator camera time up front. `--save-frames` now exists (item 0.1) for takes recorded from 2026-08-04 onward |
| N15 | **`2026-08-02_191353_static_hold` has no `raw_landmarks.jsonl`** | infra | **observed 2026-08-04, not investigated** | — | The corpus is **29 session directories but only 28 usable**. The original `static_hold` take is an empty stub — it silently contributes nothing to any pooled metric, including §0.2's baseline. Not diagnosed; noted so a future "why is n smaller than expected" is not re-investigated from scratch. The 2026-08-04 `static_hold` retake supersedes it in practice |
| N16 | **Two 2026-08-04 takes contained an unrequested second hand** | infra | **found and metadata CORRECTED 2026-08-04** | — | `known_right_back` and `occlusion_finger_over_finger` were requested and recorded as `--hand right`, but a second, nearly motionless hand was in view throughout (two hands in essentially every frame, palm-x separated ~200 px and stable to within 3–15 px, **0 duplicate-label frames**). So the hands are genuinely distinct and correctly labelled — §0.8-finding-4 contamination did **not** occur and the takes remain usable — but `hands_used` has been corrected to `both` and per-hand analysis must separate them. **Effect on numbers: the bystander scores 0.00% in every take, so pooled rates are DILUTED** — `known_right_back`'s real figure is 5.12% for the hand under test, not the pooled 2.56%. ⚠ These two are therefore **not** a matched single-hand pair with the same day's `known_left_back`, so they do not settle N11. **Lesson: check the frame for a resting hand before starting a single-hand take** |
| N17 | **`RecordTranslationPivotDebug.py` SYNTHESISES its timestamps** | infra | **found 2026-08-04, not fixed** | — | ⚠ Every pivot take reports **30.33–30.45 fps** — suspiciously constant, and 1000/30.38 = **33 ms**, the exact synthetic cadence §0.3/N1 records older recorders using. **The real rate is ~24 fps**: a 40 s take produced 967 frames (24.2 fps real) which the fake cadence compresses to an apparent 31.9 s, and `jump_test4` claims 11.8 s for a 15 s recording. **Per-frame geometry is unaffected (B4's anchor A/B is safe), but ANY velocity-in-real-time analysis on pivot takes is wrong by ~25%** — including anything that reuses B3′'s windowed derivatives on this corpus. Fix: adopt `RecordPerceptionSequence.py`'s real monotonic `tCapture`. ⚠ **It also has no `--note` option**, so operator annotations have nowhere to live in the recording; the 2026-08-04 takes use `.notes.json` sidecars as a workaround. Add `--note` at the same time |
| N18 | **2026-08-04 daylight corpus additions** | infra | **recorded** | — | Perception (all full duration): `two_hand_overlap` 777 fr/25.96 fps, `two_hand_near_miss` 794/26.51, `yaw_sweep_constant_depth` 741/24.76, `known_right_back` 751/25.09. Pivot (cube held 100% of frames): `n12_pitch_crossing` 967 fr/11 cycles, `t4_yaw_hold` 953 fr/12 cycles. **⭐ N16 CLOSED** — `known_right_back` is genuinely single-hand, restoring the matched pair N11 needs. **⭐ The YAW axis is in the corpus for the first time** (9 cycles, operator confirmed the hand passed through to show the back, so `expected_sign_changes` = 18 is valid) — every prior rotation take is PITCH by design, which is why §14.3.1's palm-width-collapses-under-yaw claim could only be inferred. ⚠ Both two-hand takes **deliberately add rotation** vs the 2026-08-02 originals, because §0.4 established the identity mixup is caused by label instability under ROTATION, not occlusion — a harder test, so 0 jumps would be stronger evidence for T3, not weaker. Control separates cleanly: near-miss 0 one-hand frames, overlap 145 (18.7% occlusion) |
| **UNSCHEDULED / NOT QUEUED** ||||||
| U1 | Open-palm / closed-fist detection (row 2) | feature | **PARKED** | — | Priority decision, not only technical. 5.1 would help; still requires owner sign-off |
| U2 | Real 3D-file import (OBJ/glTF) | feature | **POSTPONED 2026-08-04 (owner) — blocked on a PLATFORM decision, not on effort** | — | ⭐⭐ **CARRY U9's PLAY-AREA CLAMP OVER WHEN THIS IS BUILT (owner decision, 2026-08-23: leave it scalar for now, switch with U2).** `palm_geometry.clamp_to_play_area(x, y, size, frame_size)` needs NO per-object configuration — it derives the bounds from the object's own `size`, so a new object is confined the moment it is added, with nothing to register or precompute. ⚠ **But `size` is one scalar and assumes a SQUARE footprint**, which breaks twice on a real mesh: (a) a non-square object needs separate width/height; (b) **a ROTATING object's footprint changes with orientation**, and everything here rotates — clamping to the current projected extent would make the boundary move as the object turns, which is the "fluctuating margin" complaint reappearing in a new place. ⭐ **THE FIX IS A BOUNDING-SPHERE RADIUS**, not a per-axis size: orientation-INVARIANT by construction, so it is computed once per mesh at load and never recomputed, and the object stops at the same line however it is turned. `Mesh` already stores unit-scale local vertices, so the radius is `max(|v|) * object.size` — one number, derived automatically, still no per-object configuration. ⚠ Cost: slight conservatism for elongated objects, which are held a little further from the edge than strictly necessary. **Left scalar today because cubes are square, so the scalar is EXACT and there is no mesh to test a radius against.** ✅ **4.2 HAS NOW LANDED FIRST (2026-08-23), so expect this code already touched:** the `size` term is gone from the clamp — `clamp_to_play_volume` takes the object's NOMINAL extent and projects it internally, and `set_target_center` derives the top-left from the centre. ⭐ So U2's remaining job is narrower than this row assumed: replace the single scalar with a per-mesh BOUNDING-SPHERE RADIUS in ONE place (`projected_size_px`'s caller), not at every call site. ⚠ **PAIR THIS WITH 4.2's DEPTH FIX**: Z-axis translation also replaces the `size` term (the projected extent changes with depth, because the display is a frustum). Whichever lands second should expect the other to have already touched this call — do them in one pass.  §13.8; not blocking anything. ⚠ **Do not build this against the pygame renderer.** Owner reasoning: the import path depends on the eventual rendering platform (native WebGL, Three.js, or something else), so building it now would mean writing a loader for a renderer the product will not ship on. The current `_draw_object_3d` is a deliberate placeholder and is already **mesh-generic** (verified live by swapping in a non-cube mesh with zero code changes), so nothing is lost by waiting — the remaining work is a file parser, and which parser depends entirely on the target. **Revisit once the platform is chosen** (see U3), not before. Current focus is hand-detection quality, not rendering |
| U3 | Web/mobile port | platform | deferred | — | `HandState` v2 is the contract it reimplements against. ⭐ **Port-readiness discipline established 2026-08-04**: a module designated for the port gets **golden vectors BEFORE the port exists**, not after — see `analysis/verify_frame_rate_estimator.py` (and `verify_observability.py`, the precedent). **This is not ceremony: the very first run caught a real bug.** Python's `round()` is banker's rounding (half-to-even), JavaScript's `Math.round` is half-up, and the DR-1 dwells land exactly on `.5` at odd frame rates (500 ms × 13 fps = 6.5 frames) — Python gave 6, a JS port would have given 7, and nothing in normal testing would have surfaced it. Fixed in shared code via `hand_identity._round_half_up()`. **Reasoning about cross-language equivalence is not evidence.** Port units so far: `palm_observability`, `FrameRateEstimator` (47 dependency-free lines). ⭐⭐ **RE-SCOPED 2026-08-25 BY `IS1`–`IS3`, AND IT IS NOW A MUCH SMALLER JOB THAN THIS ROW ASSUMES.** What a port must reimplement is **`handinput/manifest.py`'s nine modules — 4 416 lines, stdlib-only, numpy-free, `math` the only import anywhere in them** — plus the action layer. `block_predictor`, `confirmation_gate`, `frame_gate`, `hand_skeleton`, `hand_anatomy`, `hand_model`, `features`, `classifier` and `palm_anchor` are parked/archived research and are **NOT** in the port. ⭐ And the acceptance test now exists as DATA rather than as Python asserts: `handinput/conformance/` (7 vector files + an action trace) is runnable by any language, which is what this row's own "reasoning is not evidence" line was asking for. ⛔ **Language DECISION still open and owner-deferred (2026-08-25: *"No need for TypeScript for the moment, no need for C# for the moment"*).** The recommendation on record: keep Python as the development reference, add **TypeScript** as the first shipping peer (it unlocks web + React Native + a Snapchat lens together), **C#** for Unity when Unity is real, and ⛔ **not** a Rust/WASM core — Lens Studio scripts in JS and takes no native modules, so a single binary cannot reach the target that motivated the question |
| **IS1** | ⭐⭐ **INPUT SYSTEM — the package boundary** | platform | ✅ **BUILT 2026-08-25. ⛔ NOT "shipped" until the owner's live look** | — | `handinput/` — a Unity-Input-System-shaped module so the hand pipeline can be lifted into another game, a browser build or a lens. Full record: `GESTURE_PIPELINE_SPEC.md` **§17**; usage: `handinput/README.md`. ⭐⭐ **THE ESTIMATOR MODULES WERE DELIBERATELY NOT MOVED into it**, and that is the row's one real decision: ~15 harnesses import them BARE off `sys.path` and dozens of documented paths in `Claude/*.md` name their location, so a move breaks working code and the project's own memory. Instead the property that matters — *the input system depends on nothing from the game* — is **asserted**: `analysis/verify_handinput.py` §1 parses every file's imports with the **AST** (not a grep: this codebase is mostly comments and a text search for `pygame` hits one) and fails on `CubeWindow`, `HandsTriggeredActions`, `pygame`, `cv2`, `mediapipe`, `numpy`… ⭐ **A folder gives tidiness; the test gives a guarantee.** The closure was checked, not assumed: the only non-local import in all nine modules is `math`. ⭐ `export_package.py <dir>` writes the standalone folder when it is actually wanted (**verified by running the export with no repo on the path**). ⭐ One shared-code fix rode along: `palm_geometry.palm_center_px` now has ONE definition — both tools' `_hand_position` delegate to it, as `_is_thumb_outward` already did, and §5 of the suite asserts the arithmetic is unchanged |
| **IS2** | ⭐⭐ **INPUT SYSTEM — conformance as DATA** | platform | ✅ **BUILT 2026-08-25** | IS1 | `handinput/conformance/`: **vectors** (7 files, 64 cases — signs, chirality, projection round-trips, and the STATEFUL depth/rotation/coast sequences) and a **trace** (18 frames, 65 events walking enter → provisional chirality → ready → rule 3 refusal → armed exception → frozen depth → rotation reference → coast → sustained loss → re-entry). ⭐⭐ **WHY NOT A 26th `verify_*.py`**: those assert in Python, so they can only ever test the Python — **a port cannot run them**. As JSON they turn *"is the port faithful?"* into a test. Rule 6 taken one step further. ⭐ **The TRACE is worth more than the vectors**: it pins WHEN events fire (a held button does not re-fire; a coast cancels the pose but not the track; a dead track drops a rotation reference) — none of which any single-frame vector can catch. ⛔ **Regenerating to turn a red suite green destroys the only thing they are for**; a regeneration belongs in a commit that names the behaviour that changed. ⚠ Floats compare with a 1e-9 TOLERANCE, never equality — the first port bug this project caught was banker's rounding vs half-up |
| **IS3** | ⭐⭐ **INPUT SYSTEM — the action layer, wired into both tools as an OBSERVER** | platform | ✅ **BUILT 2026-08-25. ⛔ Owner's live take still owed** | IS1 | Five actions — `tracked`, `palm_pose`, `palm_facing`, `grab_ready`, `rotation_delta` — with Unity's five phases and `+=` events. ⚠⚠ **IT DRIVES NOTHING, AND THAT IS WHY IT COULD LAND IN ONE SESSION**: every value was already computed by the gesture logic that frame, so behaviour cannot change — `parity_replay` **NO DIVERGENCE** (454 frames), 24 existing suites pass, 95 new checks pass. ⭐ **It reports what RAN rather than recomputing it**, for the same reason `_record_flush` records the cue: four harnesses once reported CLEAN on takes the owner had just watched fail, every one of them a recomputation. ⛔⛔ **SCOPE — `grab_ready` IS ELIGIBILITY, NOT A GRAB.** Unity splits Input System from XR Interaction Toolkit; this is the first only, because "grab WHAT" needs a scene and answering it here welds the module to this game. ⭐ **THE FINDING THAT FELL OUT OF A REAL RECORDING**: replaying `2026-08-24_220415_prod_tau20` gives `tracked` **8** start/cancel pairs against `palm_pose`'s **9** — the extra one is a BRIDGE, where the hand is still held but the pose has stopped updating. Two states a consumer previously had no way to tell apart. ⚠ Live event traces: `HANDINPUT_TRACE=1` in either tool (a recording cannot produce `rotation_delta` — it stores the cube's smoothed orientation, never the hand's reading, and re-running Horn to fill that gap would make a recomputation the reference for a conformance file) |
| **SEC1** | ⭐⭐ **ROBUSTNESS + SECURITY AUDIT of both tools — fixes shipped** | infra | ✅ **DONE 2026-08-25** | — | Full account: `GESTURE_PIPELINE_SPEC.md` **§18**. Suite: `analysis/verify_hardening.py` (**51 checks**). ⭐⭐ **THE CLEAN HALF IS THE POINT AND IT IS NOW CHECKED RATHER THAN BELIEVED**: **no network egress anywhere** — not one HTTP call in the pipeline, so *"nothing leaves the device"* is verifiable **by absence**, the strongest form that claim can take — plus no `eval`/`exec`/`pickle`/`shell=True`/`yaml.load` (no deserialisation or injection surface at all), both `subprocess.Popen` calls in list form, models by absolute path, socket already on loopback. **FIXED, mirrored into both tools:** off-loopback **refused** unless `--allow-remote` (S1 — the launcher forwards it so it cannot be half-applied); session tags **sanitised** in one shared `Resources/session_paths.py`, reject-and-warn rather than silent repair (S2); `meta` resolution **clamped to 8192** and every wire element **type-checked** before it reaches arithmetic — one string used to raise MID-FRAME, after part of the frame had been applied (S3); receive buffer **capped at 1 MB** and decoded per PACKET not per chunk (R1/R2); ⭐ **a single failed `cap.read()` no longer ends the session in either tool** — shared `capture_policy.py`, 30 attempts over ~0.3 s then give up, and on a `--record` take that failure used to cost the whole session (R3); a clear message when a stray holds the port (R4); and `verify_planar_pnp.py` fixed — it printed `ALL GOLDEN VECTORS PASS` then **exited 1** on a cp1252 `⚠`, so **all 26 suites now pass for the first time** (R5). ⭐ Verified additionally by an end-to-end **hostile-server** run against the real `Client.py` (oversized meta, non-numeric array, non-object packet, malformed JSON, a packet **split mid-number across two TCP writes**) — all handled, good frames still dispatched — and by `parity_replay` **NO DIVERGENCE**, which is what says the mirrored edits did not pull the tools apart |
| **SEC2** | **Pin the DEPENDENCY TREE, not just the two direct deps** | infra / shipping | **OPEN 2026-08-25** | — | `requirements.txt` pins `mediapipe==0.10.14` and `pygame==2.6.1` and lets everything transitive float — numpy, opencv-contrib-python, protobuf and the rest. ⚠ For a build that **will be commercialised** that is the realistic supply-chain exposure, and it is also what **N13 needs in order to check licences at all**: you cannot licence-check a set you have not enumerated. ⭐ Fix is a hash-pinned lock (`pip install --require-hashes -r requirements.lock`), not code, and it doubles as the licence inventory. ⚠ Pair it with **U11** (16 MB of dead model files to strip at package time) — both are package-time hygiene |
| **SEC3** | ⛔ **The FACE DETECTOR runs every frame and nothing consumes it — switch added, default NOT flipped** | privacy / perf | **OPEN — OWNER'S CALL 2026-08-25** | — | Its keypoints are computed, serialised and sent over the socket, and the client's dispatch is literally `elif datatype == "face": pass`. (`CursorController.py`, the Part Zero consumer it was for, is likewise defined and imported by **nothing**.) ⭐ **It is also a debug/production DIVERGENCE**: `LiveSnapDebug.py` has no face detector at all, so the two pipelines differ in what they load and compute per frame. ⚠⚠ **AND IT IS A DISCLOSURE QUESTION**: with the audience decided as ALL PUBLIC INCLUDING YOUTH, *"does this app run a face detector"* has a different answer depending on this — and running one **for no consumer** is the worst version of that trade. ⚠ **Do NOT expect a frame-rate win**: the capture rate is measured **camera-bound, not compute-bound** (64.1 vs 64.0 ms with and without a hand in view). ⭐ `--face off` now stops the model, the computation and the wire packet; the default stays `on` because turning it off is **visible** (the preview loses the overlay) and that is the owner's decision, not an audit's. ⚠ If it is turned off for good, delete `CursorController.py` in the same pass |
| **SEC4** | **The DEBUG recorder buffers the whole session in RAM; production streams** | infra | **OPEN 2026-08-25 — deliberately deferred** | — | `LiveSnapDebug.py` accumulates every frame into a list and writes at exit; `HandsTriggeredActions` appends as it goes, and its own comment says why (*"production has no clean shutdown path... a buffered take would be lost whenever the window is closed with the X button"*). The debug tool's `finally` covers a normal close and an exception but **not** `stop.bat`, a crash or a power loss, and a 30-minute take is ~70 MB of live list. ⛔ **Not restructured on 2026-08-25 because that is the tool the owner was about to judge the input system in** — changing the recorder the same evening as an unvalidated live take is how an unrelated bug gets attributed to the thing under test. ⭐ The fix is production's own shape: open the file at the first frame, append per frame, flush every N |
| **SEC5** | **Both tools feed MediaPipe a FAKE clock (`timestamp_ms += 33`)** | perception | **OPEN 2026-08-25 — needs an A10 A/B, not an edit** | — | Both capture loops advance MediaPipe's VIDEO-mode timestamp by a hardcoded 33 ms (30 fps) while **N7 measured the real rate at 15–24 fps** and proved it camera-bound. ⭐ The two tools MIRROR each other here, so it is **not** a divergence — but VIDEO mode uses that timestamp for its own temporal tracking, so the tracker is told the hand moves roughly **2× faster than it does**, which is a plausible contributor to landmark-layer jitter (T1/T2's sensor floor). ⛔ **Not changed by the audit**: it alters what MediaPipe outputs, so it is an A10 measurement with a replay A/B, not a hygiene fix. ⭐ Cheap to test — feed the measured `tCapture` instead and re-run the jitter harness (`t5h`) on the same take |
| **IS4** | **INPUT SYSTEM — extract the INTERACTION tier (grab/hold/arbitration)** | platform | **OPEN, owner-deferred 2026-08-25** — *"Not sure if I need this for the moment... If it can be implemented in the future with little change, let's keep it for the future"* | IS3 | Move snap proximity, arbitration, sticky grab, owner-follows-track, the grab-relative transforms and the play volume out of `HandsTriggeredActions.py` (1 500 lines) and `LiveSnapDebug.py` (2 200) into one engine-agnostic tier that operates on an abstract manipulable (id, position, bounding radius, depth) the host registers. ⭐ **IS3 was built so this stays cheap: it changes WHO CONSUMES the action layer, not what the layer produces.** Nothing in `handinput` presumes it. ⚠⚠ **AND IT IS THE RISKIEST REFACTOR IN THE PROJECT, so it needs its own session and its own live take**: that code is where T3, U7, U8, U9 and the stranded cube were all paid for, and every branch in it is a lesson. Guard with `parity_replay` + the golden suites + a live look, and expect it to change no measured number. ⚠ It also re-opens **U6** (two pipelines KEPT, owner 2026-08-22): a shared interaction tier dissolves most of that duplication as a side effect, which is an owner decision, not a consequence to slip in |
| **U7** | ⛔⛔ **The handedness LABEL is wrong 10.8% of the time, and every chirality-sensitive rule inverts on it** | perception | ✅✅ **SHIPPED AND OWNER-ACCEPTED LIVE 2026-08-22** (*"fix is working. I believe this is good to ship."*), and re-confirmed live in production 2026-08-23. ⛔ **BUT THE SPECIFIED ACCEPTANCE TEST STILL HAS NOT RUN.** A known-hand take was attempted 2026-08-23 and the operator reported BOTH hands were used, so its declaration is false and has been **RETRACTED in that session's `meta.json`** (`known_hand_RETRACTED`, `ground_truth_valid: false`) — see the YOU-ARE-HERE block. ⚠ U7 is shipped and behaviourally confirmed; what is missing is the DECLARED-ground-truth measurement. Low risk, still worth closing. , in BOTH tools, verified on recorded takes: debug `202023_u8_gate_debug_test` and production `202329_u8_gate_production_test`, **0 back-of-hand steals and 0 illegal back-snaps** with real coverage (487/258 two-hand frames). ⚠ **U7 ALONE WAS NOT ENOUGH** — it fixes chirality TRUTH, and two further defects of the same appearance needed **T3's remap** and **U8's confirmation gate**; see the YOU-ARE-HERE block. ⚠ **A LATE CORRECTION to this row's own build note**: it said the new cue needs a conditioning gate. **Measured false** — sweeping thumb-plane thickness 0→7 mm changed nothing to 5 mm and was WORSE at 3–5 mm, and at the production failure the bad frames sat at **11–16 mm, ABOVE the 8.8 mm median**. Good conditioning, wrong answer. Not shipped, per A10. Prior status follows. **BUILT 2026-08-22 — awaiting ONE live known-hand take for acceptance.** Shipped in `Resources/palm_geometry.py` (`signed_palm_volume`, `geometric_chirality`, `ChiralityResolver`) wired into `PalmFacingTracker.update()` — the ONE place the label enters the palm/back cue in either tool, so both are fixed by a single edit (N6). A/B switch `GEOMETRIC_CHIRALITY`; degrades to the label when `world_landmarks` are absent, so never worse than today. ⭐ **Effect: at the 5 recorded snaps rule 3's input changes on exactly 1 — frame 122, the documented failing snap — and the four sound snaps are untouched.** Green: 19 verify suites, `VerifyChiralityFixture.py`, new golden vectors `analysis/verify_geometric_chirality.py`, `guard_sensitivity.py`, `parity_replay.py` (zero divergence, 5534 frames). ⚠⚠ **All of that is OFFLINE** — the 4.1 post-mortem's decisive fact is that its final session measured CLEAN and the owner still saw bugs. ⚠ **Two unplanned findings**: (a) the thumb-plane-thickness GATE earns nothing (identical 0→5 mm, WORSE at 3–5 mm because it stalls the debounce) so under A10 it was **not shipped** — the 3-frame debounce does all the work, and is free because a hand cannot change chirality; ⚠ debounce=3 was picked against **5 errors in one session**, so re-validate live. (b) ⛔ `analysis/guard_sensitivity.py` had been **DEAD since 2026-08-03** — it AST-compared a function that stopped holding the logic when 1.2 moved it to `palm_geometry`, printing "GUARD IS BROKEN" every run for 19 days **about itself**; repointed, with U7 mutants added. **A guard that cannot pass is worse than no guard.** Prior status follows. **STEP 0 DONE 2026-08-22 — remedy (1) is MEASURED VIABLE; the build is now specified and unblocked.** `analysis/u7_geometric_chirality.py`, scored against the operator's DECLARATION. ⛔ **§5's stated MECHANISM was wrong and is corrected**: 3D alone does NOT remove the chirality dependence (the shipped 2D signed area already IS the z-component of that same palm normal, and a left palm and a right back are mirror images). ⭐ **The THUMB is what breaks it** — the signed volume `V = det[index_MCP−wrist, pinky_MCP−wrist, thumb_CMC−wrist]` over `world_landmarks` is rotation-invariant and flips only under reflection. **RESULT: corpus 99.8% vs the label's 98.8%, and on the ONE discriminating take (`known_right_reentry`) 98.3% vs 89.4% — 31 errors down to 5, 84% fewer.** ⚠ Quote the re-entry row, NOT the corpus row: six of seven takes are steady holds where MediaPipe is already 100%, so the average is dominated by frames never in doubt. ⭐ **The signals are independent** — they disagree on 30 frames, geometry right on 28, both wrong on only 3 (checked deliberately: if MediaPipe normalised world landmarks by its own label, `sign(V)` would prove nothing). ⭐⭐ **AND IT FIXES THE SNAP**: across the 5 snaps recorded in that take, rule 3's input changes on **exactly 1 — frame 122, the documented failing snap** — from `thumb_outward=False` (allowed, the defect) to `True` (forbidden, correct); the four sound snaps are untouched. ⚠ **BUILD NOTES**: the new cue needs its OWN conditioning gate, the analogue of `edge_on_measure` — the thumb's perpendicular distance from the palm plane (median 8.8 mm, p10 7.9 mm, min 0.9 mm); residual errors form 4 runs of [2,1,1,1], so **3 of 4 are isolated frames a 2-frame debounce would absorb**. ⛔ **STILL UNMEASURED, and it is the real gap**: the four declared-FACING takes are all takes where MediaPipe never errs, so they cannot demonstrate the facing fix — **acceptance stays a known-hand LIVE take**, never a replay. Prior status follows. **ROOT-CAUSED AND MEASURED 2026-08-22 against DECLARED ground truth. NOT fixed — the remedy is a design decision.** Full write-up: `Claude/HANDEDNESS_LABEL_DEFECT.md` | — | **MEASUREMENT** (`2026-08-22_173948_known_right_reentry`, operator declared RIGHT hand only, `meta.json.known_hand`): **32 of 295 hand-frames labelled WRONG (10.8%)**. At the snap on frame 122 the label was `Right` when it should have been `Left`; the pipeline believed `thumb_outward=False` ("palm") and allowed the grab, while the correct label gives `True` ("back") and forbids it. ⚠ **MediaPipe scored the wrong label 0.94** — high confidence — so score-gating will NOT catch it; `edge_on` was 0.56, so DR-2's freeze was not involved. ⭐ **`is_thumb_outward` applies a handedness-dependent chirality correction, so its answer INVERTS under a wrong label.** This is the owner's *"exits palm, returns back, still grabs — but not systematic"*, and *"not systematic"* is exactly the 10.8%. ⚠⚠ **IT SURVIVED SEVEN PATCHES BECAUSE EVERY CHECK COMPARED THE BELIEF AGAINST `is_thumb_outward(px, label)` USING THE SAME WRONG LABEL** — self-consistent by construction, reporting zero violations every time. **That is the B4 rule re-broken: an anchor metric must not share an expression with the anchor.** Only a declared physical hand breaks the circularity. **ELIMINATED as causes, each by measurement**: rule 3's logic (correct); the two tools' gesture logic (`analysis/parity_replay.py`, 5909 frames, ZERO divergence); detector config and MediaPipe timestamps (identical); DR-2's freeze; low confidence; and the 4.1 migration (this reproduces on the reverted baseline). ⚠ *"Not in production"* was **sampling** — one camera means the tools never run together, so that always compares separate sessions of an intermittent defect. **TWO WAYS OUT**: **(1) recommended** — make the palm/back cue **label-independent** (3D palm normal from `world_landmarks`), removing the dependency rather than improving an input MediaPipe gets confidently wrong; ⚠ touches DR-2 and §13.6.1's convention. **(2)** make DR-1 carry identity across a short absence — weaker, leaves the inversion in place. ⚠ **Acceptance test MUST be a known-hand take** (`LiveSnapDebug --known-hand left|right`), never a replay that trusts the recorded label. ⭐ **Rotation is NOT affected** — `Horn` never reads handedness, which is why there is no visible 180° cube flip (the owner's own observation, which correctly killed a hypothesis of mine) |
| U4 | `PART_ONE.md` §7.4 dangling reference | docs | open | — | §3 cites §7.4 for `gesture_config.json`; that section does not exist |
| **U6** | **Two pipelines are KEPT — so divergence must be PREVENTED mechanically** | architecture | ⭐⭐ **DECIDED 2026-08-22 BY THE OWNER: *"we will keep two: production and debug"*. The collapse proposal below is CLOSED — do not re-propose it.** ⚠ The evidence that motivated it stands and does not go away with the decision: **four defects, all production-only, all in the input path** (§13.6.1's inverted thumb-outward; the `invert_x` mirror, 12–20° of rotation error; out-of-frame `None` stranding cubes; that same `None` teleporting a landmark to (0,0)), plus a fifth found later — the debug tool never reset DR-2 on a dead track while production always did. **So the standing obligation is now PARITY TOOLING, not a refactor**: ⭐ `analysis/parity_replay.py` (drives BOTH implementations from the same recorded frames and names the first divergence — 5909 frames, zero divergence at the time of writing) and ⭐ `analysis/verify_dead_track_reset_parity.py` (compares both tools' dead-track branches from SOURCE). ⚠ **Run `parity_replay.py` whenever either tool's gesture logic is touched, and whenever the owner reports "it does not happen in production"** — that sentence has meant a real divergence three times and sampling once, and only the comparator tells them apart. ⚠ Note one camera means the two can NEVER run simultaneously, so any "it differs" claim compares separate sessions of what may be an intermittent defect. **Superseded proposal follows.** Originally PROPOSED 2026-08-22 (owner question), NOT decided. Owner's framing: *"couldn't I build the whole pipeline on the debug, and then remove the camera and hand overlays at the last moment to ship it as production?"*** | — | **THE EVIDENCE. Four bugs, one root — production RE-IMPLEMENTS the input path while the debug tool does not**: (1) **§13.6.1** thumb-outward shipped INVERTED, production only; (2) the **`invert_x` mirror** is not equivalent to flipping the frame (**7.7–10 mm, 12–20° of rotation**), production only; (3) **out-of-frame landmarks became `None`**, which skipped DR-1 entirely and **stranded held cubes**, production only; (4) the same `None` became **(0, 0)** on the wire, teleporting a landmark to the top-left corner and corrupting translation weighting, production only. ⭐ **N6 ("shared, never copied") was applied to the ESTIMATOR modules and never to the input path — which is exactly where all the damage has been.** **WHAT THE SPLIT BUYS TODAY: nothing functional.** The server also runs FACE detection, and the client's face handler is `pass` (a TODO); exactly ONE consumer connects; no second tool or third client exists. Its only stated value is the **port contract (U3)** — ⚠ **but a contract is a defined `HandState` struct, not a socket**, so that value survives collapsing the processes. **TWO OPTIONS**: **(A)** collapse to one process, keeping `HandState` v2 as an in-process function-call contract — kills the whole divergence class, loses nothing used today; **(B)** keep the split but extract the input path (frame → landmarks → identity) into a module both import — N6 applied where it never was, less disruptive, keeps the socket for a future second consumer. ⭐ **Assistant recommends (A) on the evidence**, ⚠ **with the caveat that "ship the debug tool" is not quite right either**: the debug tool's single-process shape is not what ships to web/mobile, so that framing optimises for the PC target and re-faces the same seam later — keep the v2 boundary explicitly. ⚠ **This is a real refactor of a WORKING pipeline: do it deliberately, with `VerifyChiralityFixture.py` and all golden-vector suites green before AND after, and NOT folded into a build step.** |
| **U8** | ⭐ **Rule 3 must not act on a PROVISIONAL chirality (newly entered hand)** | perception | ✅✅ **SHIPPED AND OWNER-ACCEPTED LIVE 2026-08-22.** `ChiralityResolver.confirmed`, gating `can_snap` in BOTH tools. | U7 | **THE DEFECT** (`2026-08-22_190955_t3_remap_production_test`, f664, owner-reported and then recorded): a hand ENTERING the frame had its geometric chirality measured **wrong for 5 consecutive frames**; the resolver adopted that first sighting immediately and the U7 debounce then DEFENDED it, so a back-of-hand hand read as PALM and took a cube rule 3 forbids. ⭐⭐ **THE OWNER'S PHYSICAL ACCOUNT IS THE JUSTIFICATION, and it is why this is a transit time rather than a tuned constant**: *"you need enough frames for the thumb and the palm to be both present since this will define definitely the hand: if the back of the right hand enters from the right, you do not see the thumb before the last moment."* Chirality IS the thumb's offset from the palm plane, so until the thumb clears the edge the quantity is **not noisy, it is UNDEFINED** — and MediaPipe supplies a hallucinated thumb, which is why the wrong value arrived STABLE and WELL-CONDITIONED. **WINDOW = 400 ms.** ⭐⭐ **EXPRESSED AS A DURATION, NOT A FRAME COUNT** (owner instruction, 2026-08-22) — it is a TRANSIT TIME, and a frame constant is only correct at the rate it was measured at. N7/N10 already burned this project: the SAME camera measured **24.1 fps in daylight and 15.1 in dim light**, so DR-1's 500 ms dwell silently became ~761 ms. ⭐ **AND IT IS GATED ON ELAPSED TIME, NOT ON ms×measured-fps** — that alternative was considered and is strictly worse: `FrameRateEstimator.fps` SORTS a ring buffer on every access (DR-1 pays that 4x per frame), while elapsed time is one subtraction and one comparison, needs no estimator, and has neither rounding nor estimator lag after a lighting change. **Both call sites already hold `now_ms`, so nothing new is sampled** — the debug tool reuses the single clock read it already takes per frame. ⚠ **A FLOOR OF 3 OBSERVATIONS still applies**, because chirality cannot be confirmed from frames that were never delivered (sparse detection would otherwise confirm on almost no evidence). Mirrors `hand_identity.frames_for()`'s existing floors. A caller passing no timestamp falls back to a frame count at the rig rate. **WHY 400 and not 330** (= the validated 6 frames at the failure session's measured 18.14 fps): 330 works but by only **13 ms**, a 4% margin on a quantity that varies with operator speed. Measured trade — suppressed palm-frames vs margin at the recorded grab (317 ms elapsed): **280 ms → 10.7%, MISSES it; 330 → 12.0%, +13 ms; 400 → 14.1%, +83 ms (shipped); 450 → 15.4%, +133 ms**. 400 buys 6x the margin for 2.1 points, and sits inside the measured transit range (median **230 ms**, p75 **453 ms**). **Three independent lines agree** (`analysis/u8_entry_settling.py`): (a) PHYSICAL — palm width **69 px** median / entry speed **11 px/frame** (75 corpus tracks starting at a vertical frame edge) = **4.8 frames**, p75 10.1; (b) EMPIRICAL — leading run of wrong chirality per track: 89.5% correct at frame 0, **93.4% by age 5**, then a PLATEAU (93.9% at age 15); (c) the recorded failure was wrong through age 4 and grabbed at age 5, so ≥6 is required. They agree because **DR-1 already absorbs part of the transit** (it will not lock a track until a 5-frame dwell), so track age 0 is not the hand's first appearance. ⚠⚠ **THE COUNT ALONE IS NOT SUFFICIENT — caught by the test, not by reasoning**: 6 frames landed EXACTLY on the grab frame while the held value was still wrong (the debounce had not switched). So `confirmed` needs a SECOND condition: **the latest observation must AGREE with the held value**. While raw and held disagree the chirality is IN DISPUTE, and a disputed chirality inverts `is_thumb_outward`. That is DR-2's freeze philosophy applied to chirality. ⛔ **THREE CHEAPER REMEDIES WERE MEASURED AND ALL FAILED** — record them so they are not re-proposed: (1) **conditioning gate** — the bad frames were at 11–16 mm, ABOVE the 8.8 mm median; (2) **fall back to the label while unconfirmed** — the label is WORSE at entry, **76.8% vs geometry's 89.7%** at track age 0; (3) **temporal voting** — the wrong value was stable for 5 CONSECUTIVE frames, so any majority still picks it. ⛔ **AND THE TWO-HAND CONSTRAINT IS DETECTABLE BUT NOT RESOLVABLE**: two simultaneously visible hands cannot share a chirality (violated in **191 of 14460** two-hand frames, 1.32%), but choosing WHICH is wrong measures near chance — trust-the-older **46.6%**, trust-the-squarer **53.4%**, trust-the-thicker **63.9%**. Detection yes, resolution no. **Suppress, do not guess.** **COST, priced before shipping**: 8.6% of palm-reading frames suppress snapping, and a 6-frame window would have delayed **17 of 78** corpus snaps (21.8%) by ~380 ms — DELAYED, not refused; the hand is still there when the gate opens. 8 frames would cost 33% for +0.5% coverage. ⚠ **A REGRESSION I CAUSED AND FIXED**: the gate first blocked callers supplying no `world_landmarks` (`frames_seen` never increments, so it stayed shut forever) — `verify_three_arm_bridge` caught it. An un-migrated caller must be UNCHANGED, never blocked. ⛔ **The gate was not weakened to make the test pass** (post-mortem §3.5). ⭐⭐ **LOWERED 400 → 200 ms after the live U9 take** (owner: *"400 ms is too long. Half of it would be good I think"*). ⚠ **Not lowered on the request alone** — 200 ms is BELOW the recorded failure's **317 ms**, so on the original reasoning it should leak. It does not, and the sweep says why: **f664 is refused at 400/300/250/200/150/100 ms**, by TIME only at 400 and by the **DISPUTE condition** at every value below. ⭐ **That inverts the original design story**: the window was believed to be the protection and the dispute check a refinement bolted on when 6 frames landed exactly on the grab frame. Measured, **the dispute check is the primary guard** and the window is a BACKSTOP for a bad chirality that never disagrees with itself — which is a real case (the corpus shows a wrong value stable for 5 consecutive frames), so some window is still right; it just need not cover 317 ms. **COST falls 14.1% → 8.3%** of palm-reading frames. ⚠ U9 now also covers part of what this protected: a half-visible hand cannot grab at all. ✅ **N1 SATISFIED**: the window is a duration, so it no longer drifts with the capture rate — and the OBSERVATION-count concern that first argued for frames survives as the 3-frame floor rather than as the whole mechanism. ⚠ **DR-2's exit dwell deliberately stays a FRAME count** in the same class: it is a consecutive-confirmation debounce, not a duration, and a time-based version was measured to freeze DR-2 47% longer for no gain (N7). Two dwells, two units, each matching what it represents. **Re-derive the 400 ms with `u8_entry_settling.py` (step 3b) if the entry-speed or palm-width distributions change** — not if the frame rate changes, which is now handled. |
| **U9** | ⭐ **PLAY AREA — an object may never reach the display edge** | feature | ✅ **SHIPPED 2026-08-23, live-confirmed in BOTH tools** (owner: *"the build now is good"*). `palm_geometry.clamp_to_play_area`, called from both tools' `set_target_position`. | — | **OWNER'S REQUIREMENT** (2026-08-23): *"I can still push step by step the cube to the edge of the display window, which I would like to avoid: I want the cube to be constrained in a smaller window within a display window (hence the margin)."* **MARGIN = 60 px**, the owner's "half a hand width at 40 cm", derived two agreeing ways: OPTICAL (pinhole, 85 mm hand breadth) 49–65 px across plausible FOVs, **59 px at 60°**; EMPIRICAL — the corpus p99 palm width is **127 px**, implying **0.37 m**, so 40 cm IS the closest the operator works, and half that is **63 px**. Play area = the window inset by that margin; the WHOLE object stays inside, not just its corner. Stateless and absolute. **MEASURED**: debug replay **0 of 786 cube-frames outside the play area**, with the large cube reaching exactly **0.0 px slack** at the boundary — pushed to the limit and stopped. ⛔⛔ **TWO HAND-SIDE TRIGGERS WERE BUILT FIRST AND BOTH WERE REVERTED**, and they are the value of this row: **(1) an ADAPTIVE margin** (half the CURRENT palm width) — failed live on its first take: the measured width **collapsed 45% in one frame** (50.9 → 28.2 px), the margin collapsed with it, and the hand re-grabbed and carried the cube out. ⚠ Not a systematic edge effect that could be corrected for — bucketed by distance-to-edge the median width is FLAT (84 px at 0–25 px, 87 px at 200 px). It is per-frame JITTER. ⭐ **A threshold must not be computed from a quantity that is noisy in the regime the threshold governs.** **(2) a CUBE-DRIVEN check** — it found the hand by the object's owner SLOT, so a relabel that emptied that slot made the check silently skip: the margin fired on the FIRST approach to an edge and never again (owner-reported; 8 such frames measured). Re-driven from the hand, then **removed entirely** on the owner's instruction — *"revert that build as this is not required"* — once the clamp landed. ⭐⭐ **THE LESSON, TRIGGER vs INVARIANT**: translation is GRAB-RELATIVE (§14.1), so an object keeps whatever offset it had from the hand at grab time; it can sit far closer to the edge than the hand centre, and every grab-push-drop cycle establishes a new offset and walks it further out. **A trigger decides WHEN TO LET GO; only a clamp decides WHERE THE OBJECT MAY BE — a trigger cannot enforce an invariant.** The felt symptom of trying is a boundary that appears to *fluctuate*, because the effective limit was hand-position-minus-a-varying-offset rather than a fixed line. ✅ **(a) IS DONE — 4.2 SHIPPED THE WORLD-SPACE VOLUME (2026-08-23).** `clamp_to_play_volume` replaces this call in both tools; the margin is carried as 42.5 mm and projected at the object's own depth, so the on-screen boundary MOVES with depth. ⚠ **This function is NOT dead** — it is the depth-free special case and the fallback `clamp_to_play_volume` degrades to when no depth is available. ⚠ **(b) SHAPE is still open (U2).** ⚠⚠ **THIS WAS A 2D RULE, AND IT HAD TWO KNOWN GENERALISATIONS — do them together, not separately.** **(a) DEPTH (queue 4.2). ✅ DECIDED, OWNER 2026-08-23: THE PLAY AREA IS A WORLD-SPACE VOLUME, FRUSTUM-AWARE.** Today's rule is a screen rectangle applied at one implicit depth; once Z is driven the clamp moves into WORLD coordinates — at the object's depth take the frustum's lateral extent, inset it by the world margin, clamp the object's world position inside that, then project. ⭐ **The on-screen boundary will MOVE with depth** (inward as the object recedes, outward as it approaches). That is the intended consequence of the decision, not a regression — expect it and do not 'fix' it. ⭐⭐ **THE MARGIN IS ALREADY A WORLD QUANTITY, so this is a change of UNITS, not of the number.** It was derived as *half a hand breadth at 40 cm* = **42.5 mm**; 60 px is simply its projection at 40 cm (554 px focal length x 0.0425 m / 0.40 m = 58.9 px). At other depths the same 42.5 mm projects to: **78 px at 0.30 m, 59 px at 0.40 m, 34 px at 0.70 m, 24 px at 1.00 m.** Carry 42.5 mm forward, not 60 px. ⚠ And the object's own extent must become a world extent too — which is (b). **(b) SHAPE (queue U2)**: `size` is one scalar assuming a square footprint; a real imported mesh needs a **bounding-sphere radius** (orientation-invariant, computed once at load) or the boundary will move as the object rotates. Deliberately left scalar and 2D today — cubes are square and nothing drives Z, so the scalar is EXACT. Golden vectors: `analysis/verify_play_area.py`. |
| **U10** | ⚠ **Camera privacy: policy + store disclosures (and minors)** | governance / shipping | **OPEN — raised by the owner 2026-08-23, to tackle before any store submission. Not a build; do not start it as one.** | — | ⭐⭐ **THE REAL SHIPPING EXPOSURE IS PRIVACY, NOT LICENSING.** N13 covers licences and is satisfied (see below); this row is the separate obligation that comes with pointing a camera at a player. **THE ARGUMENT IS STRONG AND SHOULD BE MADE EXPLICITLY**: everything runs client-side, **no frames leave the device**, and the corpus itself is landmarks-only — the pipeline has never captured a pixel to disk (see the `corpus-has-no-image-data` finding: 415 recording files, zero images). ⚠ **But "we don't send anything" is not a defence unless it is WRITTEN DOWN**: a privacy policy has to say exactly that, in those terms. **WHAT IS REQUIRED**: (a) a privacy policy stating that camera frames are processed locally and never transmitted or stored; (b) **store-level camera-permission declarations** — Steam, the App Store and Google Play each have their own, and they are not interchangeable; (c) platform-specific runtime permission prompts (iOS `NSCameraUsageDescription`, Android `CAMERA`, macOS TCC), which the cross-platform target makes unavoidable. ✅✅ **AUDIENCE DECIDED, OWNER 2026-08-23: ALL PUBLIC, INCLUDING YOUTH.** So **COPPA (US) and GDPR-K (EU) are LIVE, not hypothetical**, and the stricter store programmes apply — Google Play's **Families** policy and Apple's **Kids Category**. ⭐⭐ **THE ENGINEERING CONSEQUENCES, which are the part this file can actually hold** (the legal drafting is not ours): **(1) NO THIRD-PARTY ANALYTICS OR ADS SDKs.** Both families programmes restrict them severely. Treat this as **binding architecture, like N13** — not a preference to revisit per-feature. **(2) THE LOCAL-ONLY, NO-TRANSMISSION ARCHITECTURE IS NOW LOAD-BEARING FOR COMPLIANCE**, not merely a nice property. Anything that transmits — cloud inference, crash reporting that captures frames, telemetry on landmarks — becomes a compliance event and must be raised as one BEFORE it is built. **(3) `VISION_RECORD=1` MUST BE COMPILE-TIME-DISABLED IN SHIPPING BUILDS** — see U11. Default-off is not enough for a youth audience. **(4) AGE-RATING QUESTIONNAIRES** (IARC via Play, ESRB/PEGI) will ask directly about camera use and data collection; answering "nothing is collected or transmitted" requires it to be TRUE and demonstrable — which today it is, and (2) is what keeps it so. ⚠ **A NUANCE WORTH RAISING WITH COUNSEL RATHER THAN ASSUMING**: hand landmarks are body-derived, but GDPR's *special-category* biometric definition bites when processing is **"for the purpose of uniquely identifying a natural person"** — gesture control is not that. That distinction is likely favourable here and is worth having the argument prepared. ⛔ **This is not a legal opinion.** ⭐ **The architecture is already the strongest argument available** and is worth preserving deliberately: local-only inference, no telemetry, no frame persistence. ⚠ **Anything that would break that — cloud inference, crash reporting that captures frames, analytics on landmarks — should be weighed against this row before it is built**, not after. ⚠ The recording harness (`VISION_RECORD=1`) DOES write landmark data to disk; it is a development tool and must not ship enabled, and its existence should be considered when the policy is written. ⛔ **This is a legal/compliance question, not an engineering one.** The rows above can be answered by measurement; this one cannot. ⚠⚠ **With youth now in scope, professional advice is not optional** — but the four engineering consequences above are actionable today and are what protects the position. |
| **U11** | ⭐ **Shipping-build hygiene: strip dead assets and hard-disable dev capture** | shipping | **OPEN, recorded 2026-08-23 — do at package time, NOT now.** | U10 | **DEAD MODEL WEIGHT, measured**: `Python_Server_MediaPipe_vision_pipeline/Resources/gesture_recognizer.task` (**8.0 MB**) is a leftover of the **REJECTED** built-in `Open_Palm`/`Closed_Fist` experiment (§13.5, live-tested unreliable and reverted). ✅ **Nothing loads it** — the only surviving mention is a comment in `LiveSnapDebug.py`. And `_not_used/Virtual_drums_fingers_tracking/models/hand_landmarker.task` (**7.5 MB**) is a duplicate of the real model. **16 MB together.** ⚠ `_not_used/` as a whole is **856 MB** — it would never be in a shipping build, but it is worth knowing for clone/repo cost. ⛔⛔ **AND THE PART THAT IS NOT MERELY HYGIENE: `VISION_RECORD=1` MUST BE HARD-DISABLED IN A SHIPPING BUILD, not just default-off.** It writes hand-landmark data to disk. With the audience now decided as **all public including youth** (U10), a dev flag that silently records body-derived data on a minor's machine is a compliance liability, not a tidiness issue. **Compile it out or gate it behind a build flag that cannot be set at runtime** — an environment variable is not sufficient protection. ⚠ Do NOT strip any of this during feature work: the debug tooling and the analysis harnesses are what this project runs on, and `gesture_recognizer.task` costs nothing while it sits unreferenced. This is a package-time checklist. |
| **U12** | ⭐ **A START-OF-GAME CALIBRATION STEP — for PLAYABILITY, not for correctness** | playability | **OPEN, recorded 2026-08-23 by owner instruction — BUILD LATER, when a real game exists and playability starts to matter.** | 4.2, U3 | ⚠⚠ **READ THE HISTORY FIRST, BECAUSE A CALIBRATION SCREEN WAS ALREADY REJECTED ONCE AND THAT REJECTION STILL STANDS.** 4.1 asked *"does the depth signal need a min/max reach calibration?"* and the answer was measured **NO** — the reach envelope is 3.59x and `d0` is captured per grab, so the ratio form re-normalises itself and cancels the unknown hand size EXACTLY (`analysis/m9_depth_envelope.py`). ⛔ **Do not reopen that question. This row is a DIFFERENT one.** ⭐ **WHAT THIS ROW IS ACTUALLY FOR.** 4.2 introduced a SECOND, absolute depth estimator (`palm_depth.HandDepthTracker`) purely to gate the 3D snap, because a hand that has not grabbed anything has no baseline to normalise against. It substitutes ANTHROPOMETRIC MEDIANS for the missing baseline, so it carries a **per-user scale bias**: a player whose hands are 20% off the median reads ~80 mm away from where they really are, CONSTANTLY. Today that is absorbed by making `GRAB_Z_TOLERANCE_M` generous (0.15 m). ⚠ That works, and it costs precision: the axial gate is looser than it needs to be for everyone, to stay reachable for the outliers. ⭐ **A single measured hand size at game start collapses the bias to near zero and would let the tolerance tighten** — one short 'hold your open hand up' moment, storing one number per player. ⚠ **AND THE SAME MOMENT COULD SET THE OTHER SETUP-DEPENDENT CONSTANTS**, which are guesses today and are all properties of the PLAYER'S SETUP rather than of the code: `CAMERA_HFOV_DEG` (assumed 60°, never calibrated), `REFERENCE_DEPTH_M` (measured 0.497 m — but that is THIS operator at THIS desk), and the play volume's walls (this operator's p1–p99). ⭐ Each already has a re-derivation harness: `analysis/m9_working_distance.py`. ⛔ **NOT NOW, and the reason is the owner's standing preference against overbuilding**: nothing is broken, every constant currently measures correctly for the real operator, and a calibration screen is a piece of GAME UX — it needs a game to live in. ⚠ **THE TRIGGER TO BUILD IT** is either a second player who cannot pick things up, or the point where 4.2's loose axial tolerance becomes a felt imprecision. The debug tool's HUD already shows hand depth beside object depth, which is the instrument that would show it. ⚠ **Sequence it with U3 (the port)**: a calibration step is per-platform UX, so building it against the pygame placeholder would be building it twice — the same reason U2 is postponed. ⭐⭐ **T6 ADDS THE FIRST HARD TECHNICAL REASON, AND OWES THIS ROW A NUMBER (2026-08-23).** Planar PnP consumes `CAMERA_HFOV_DEG` *directly*, and focal error corrupts the **out-of-plane** component — i.e. exactly the yaw/pitch T6 exists to fix — so for the first time a wrong FOV is a **correctness** issue and not just a looser grab tolerance. ⚠⚠ **BINDING OWNER CONSTRAINT, SAME DAY**: *"make sure I do not need to recalibrate each time I run the debug or the production for the moment, nor on local pc nor on future web build."* **So T6 introduces NO calibration**: 60.0 stays a compile-time constant, read only through `palm_geometry.focal_px()`, nothing prompts or gates, and when U12 is eventually built it must **override** that default with one stored per-player number — **never become required**. ⭐ **THE OWED NUMBER**: T6's §9 step 7 sweeps the assumed FOV and measures degrees of axis error per degree of FOV error; **write the result into this row.** ⭐⭐ **AND THAT NUMBER IS THE U3 PORT RISK, WHICH IS WHY IT MATTERS MORE THAN IT LOOKS**: a phone or laptop camera is **not** 60° — a tablet is often ~55°, a phone front camera ~70–80° — so the sweep converts *"rotation might read wrong on the web/mobile build"* from a worry into a figure, and tells this row what a calibration step actually buys before anyone builds one. If the sensitivity turns out small, U12 stays a playability item as written; if it is large, U12 becomes a **prerequisite of U3** rather than a nicety, and that re-sequencing is decided by the measurement, not by feel. ⭐⭐⭐ **AND U12 NOW OWNS A SECOND, BIGGER JOB — THE CAMERA'S TILT, i.e. `T7`'s `C` (owner, 2026-08-24).** *"I would prefer we later work on an initial calibration sequence at the beginning of the game which calibrates the game including camera tilt."* ⚠⚠ **NOTE THIS IS AN EXTRINSIC, NOT ANOTHER INTRINSIC — a different KIND of quantity from `CAMERA_HFOV_DEG` above, and conflating them will cost a rebuild.** The FOV describes the **lens**; the tilt describes **how the device is propped up**, changes every time it is moved, and is what decides whether a hand turn about the WORLD vertical reproduces as a cube turn about the SCREEN vertical. ⭐ **It is only TWO DOF and they are exactly the ones gravity fixes** — camera pitch and roll; camera yaw leaves gravity unchanged in camera coordinates and is irrelevant, since the fit is grab-referenced. ⛔ **THE IMU WAS OFFERED AND DECLINED, deliberately**: *"i don't want to introduce a different behavior between desktop and mobile for the moment"* — so `C` is calibrated the SAME way on every platform, `C` defaults to identity (level) until this row is built, and an IMU stays a **recorded second-order fallback** whose trigger is a camera that MOVES DURING PLAY (a hand-held phone), which no start-of-game calibration can track. ⭐ Read **T7**'s row for the mechanism (one conjugation, `ΔR_world = C·ΔR_cam·C⁻¹`) — it is small, and it is why T7 is sequenced to ship WITH this row rather than after T6. ⚠ **So this row now carries FOUR setup constants, not three**: hand size, `CAMERA_HFOV_DEG`, the play-volume walls, **and the camera tilt** — and the tilt is the one with a visible, immediate effect on how the game FEELS rather than on a tolerance. |
| **U5** | **Extend D2's coast so a cube survives hand-crossing occlusion** | feature/perception | ⭐ **PARKED FOR LATER RE-OPENING — owner decision 2026-08-22.** Everything needed to resume is in this row | D2/D3 (shipped) | **OBSERVATION (owner, live, production, 2026-08-22)**: *"when the hands quickly pass in front of each other and one occludes the other, there is no mechanism to continue the cube movement based on extrapolation. The cube grabbed by the occluded hand is ungrabbed and then grabbed again when the occluded hand reappears, which causes a jump in the cube location."* ⭐ **RECORDING**: `2026-08-22_154426_production_4_1` (5114 frames, 205 s, 24.88 fps, 3226 with a hand) — the first PRODUCTION recording; replay it with `VISION_RECORD=1` takes or measure directly. **MEASUREMENT** (gaps where one hand vanishes *while the other is present*, i.e. crossing/occlusion): **60 events, median 402 ms, p90 2130 ms, max 3778 ms — and 42 of 60 (70%) exceed D2's 150 ms coast**, so the cube is released and re-snaps on reappearance, which IS the jump. **EXPLANATION**: D2's coast was sized for sensor dropout, not for one hand hiding behind another; at 402 ms median it is **2.7x too short** for crossing. ⭐⭐ **THE PROPOSED FIX IS A LONGER HOLD, NOT EXTRAPOLATION** — the owner's own framing said "extrapolation", but **B8 already measured every fit LOSING to "hold the last value"**, so a predictor is the known-worse answer here; extend D2's window and reuse D3's existing resync blend. ⭐ **HOW TO PICK THE WINDOW (owner's instruction)**: a **recording test** — sweep the window over recorded takes and choose by measurement, not by feel. ⚠ **PRICE THE COST BEFORE SHIPPING**: a longer hold widens the window for **N8** (cube stolen by an occluding hand) and for holding a cube the operator genuinely released; and it partially overlaps **D4**, which was DECLINED 2026-08-21 (*"I do not see the need"*) with the recorded reopening condition *"only a hand lost LONGER than the sensor gap"* — **that condition is now measured, so this is a legitimate reopening, not a re-proposal**. See also **B5** (grab/release from arcs) and **3.1** (M7 forward prediction), which touch the same failure |

## 4. Known wire-protocol gap (live pipeline, not recording)

> ⚠⚠ **CORRECTED 2026-08-22 — THE GAP DESCRIBED BELOW IS CLOSED. The wire DOES
> carry `world_landmarks`.** `VisionPipeline.py` builds a `hands_world` packet
> (`remap_world_keypoints`, 21x3 per hand) and sends it *before* each `"hands"`
> packet; `PythonApp_Main.py` decodes it as `hands_world` into
> `on_hands_world_frame`. It was extended for rotation-while-snapped (§13.7) and
> the section below was never updated. **Consequence for 4.1: the depth anchor
> needs NO protocol work** — `hand_skeleton.palm_width_world()` can run
> client-side on data already arriving today.
>
> ⭐ **What is genuinely NOT on the wire is DR-1's TRACK IDENTITY.**
> `hand_identity.py` lives only under
> `Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/` and nothing
> client-side imports it; the client receives landmarks keyed by handedness SLOT
> only. **That — not `world_landmarks` — is the real content of the `HandState`
> v2 migration, and it is what T3 needs** (see §3.1's T3 row and
> `PERCEPTION_LAYER_SPEC.md` §2.2's 2026-08-22 addendum).
>
> The original text is kept below for provenance. Read it as history, not status.

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
