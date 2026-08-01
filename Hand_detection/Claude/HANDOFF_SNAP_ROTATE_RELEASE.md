# Handoff — snap/rotate/release gesture set, current state and next steps

Refreshed 2026-08-01, for starting a **new** Claude Code conversation.
Read this first. The three other living documents for this work, in
order of how detailed they are:

1. **`Claude/GAME_RULES.md`** — plain-language inventory of confirmed game
   rules, no implementation detail. Read this to know *what the game does
   today*.
2. **`Claude/PART_ONE.md` §3** — the gesture/signal matrix (build order,
   status per row). Read this to know *what's built vs. not, in one
   table*.
3. **`Claude/GESTURE_PIPELINE_SPEC.md` §13-§14** — full design rationale,
   state-of-the-art checks, and build history (§13, all subsections
   through §13.8), plus the three next build targets, confirmed build
   order pivot-fix → release-trigger → Z-translation (§14). Read this to
   know *why* things are the way they are, and *what's next*.

This handoff file is only an orientation pointer plus a prioritized
action list — don't duplicate the above, link to them.

**Repo state**: check `git status` before assuming anything — this
work has not been committed as of this handoff.

## 1. Where the project stands

**Pinch is archived** (not deleted — code/corpus/weights kept, reusable
later). Full account: `GESTURE_PIPELINE_SPEC.md` §13.1,
`HANDOFF_GESTURE_CLASSIFIER.md` (now itself archived/historical).

**Current gesture set: proximity snap, translation, rotation — all built,
ported to production, and CONFIRMED WORKING LIVE against a real camera.**
Open-palm/closed-fist detection is PARKED (2026-08-01, later
conversation) — not being pursued for the moment. Release currently
relies on tracking-loss only; the hand-open-quick-release gesture (§2.2)
is the sole active plan for a deliberate release trigger, not yet built.
Status, in build order:

- **Hand position, proximity snap, translation, tracking-loss release,
  thumb-outward snap restriction: all built and live-verified.**
  `Resources/HandsTriggeredActions.py` (production) +
  `LiveSnapDebug.py`/`debug_snap.bat` (combined debug view — one OpenCV
  window with video + hand landmarks + a semi-transparent 3D-cube
  overlay, kept in logic-sync with the production module by hand — **kept
  in active use past its original "temporary" framing, per direct
  request**, since it's easier to debug with video+landmarks+object
  visible together than via production's split windows; remove only once
  final production no longer needs this level of visibility). Exact
  rules: `GAME_RULES.md` rules 1-3.
- **A same-frame release/re-snap ordering bug** was found live and fixed
  (a cube could instantly "jump" to the other hand the instant one hand
  lost tracking nearby) — see `on_hands_frame`'s docstring in
  `HandsTriggeredActions.py` for the fix if touching that logic again.
- **MediaPipe's built-in Gesture Recognizer (`Open_Palm`/`Closed_Fist`)
  was tried and reverted** — live-tested unreliable across hand
  positions/orientations for `Closed_Fist` specifically (many missed
  fist closures). `gesture_recognizer.task` is kept on disk
  (`Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/`) for a
  possible later `Thumb_Up` use, unrelated to this. Full account:
  `GESTURE_PIPELINE_SPEC.md` §13.5. **Open-palm/closed-fist detection
  itself (matrix row 2) is now PARKED (2026-08-01, later conversation)** —
  not intended to be pursued for the moment, a deprioritization rather
  than a rejection of the geometric-heuristic candidate §13.5 proposed
  next. Revisit only if explicitly requested again.
- **Rotation while snapped: BUILT, PORTED TO PRODUCTION, AND CONFIRMED
  WORKING LIVE (2026-08-01).** Confirmed UNGATED (not gated on
  `Open_Palm`). Relative-to-grab (not absolute — a cube keeps its own
  orientation at grab, only rotates by however much the hand rotates
  afterward), hand-rolled quaternion math, the predictive/reliability-
  weighted orientation filter. Wire protocol extended (`hands_world`
  packet, `VisionPipeline.py`→`Server.py`→`PythonApp_Main.py`). User
  confirmed "it is working" against the real camera — the previously-
  unverified world-landmark mirroring convention needed no fix. Full
  account: `GESTURE_PIPELINE_SPEC.md` §13.7.
  - **Known open TODO**: rotation quality is still imperfect with the
    BACK of the hand facing the camera. Four attempts total (three
    geometric landmark-selection fixes, one temporal/predictive filter)
    have each helped without fully resolving it — increasingly looks like
    a genuine floor of a single-monocular-camera setup, not a software fix
    away. §13.7's last paragraph has what to check before a fifth attempt
    (tuning `CONDITIONING_ALPHA_LOW`/`HIGH`, widening the angular-velocity
    averaging window) before reaching for a fundamentally different
    approach.
  - **Known open TODO, REFRAMED 2026-08-01 (later conversation),
    mechanism resolved in a follow-up discussion, not yet started**: the
    object translates when the hand rotates. Root cause corrected — it's
    not that the tracked anchor isn't precisely at the true pivot, it's
    that translation has no grab-time offset at all. Chosen fix:
    distance-weighted live landmark tracking (freeze a weighted set of
    phalange-adjacent landmarks at grab, weighted by proximity to the
    object; recompute live each frame from those landmarks' real tracked
    motion — no reuse of rotation's quaternion math, stays purely
    2D/pixel-based). Some translation during pure rotation is now
    understood to be physically correct once fixed properly (an
    off-center held object swings when the wrist twists). Full redesign +
    literature: §14.1 below.
- **Real 3D object rendering: BUILT and CONFIRMED WORKING LIVE
  (2026-08-01)**, once rotation was confirmed. Replaced the flat-square +
  axis-gizmo placeholder with actual rotating 3D shapes — 2 objects,
  **large** (yellow/violet/turquoise faces, one side of each opposite
  pair a darker shade) and **small** (green/red/blue), large exactly 2x
  small in every dimension. Grab radius now scales per-object size (an
  old open item, resolved as a side effect).
  - **A morphing bug was found live and fixed same day**: the first
    version's per-vertex projection scale could go negative for cube
    corners at certain rotations, flipping vertices to the wrong side.
    Fixed with a proper, bounded perspective projection (verified safe
    across a full rotation sweep). Full account: `GESTURE_PIPELINE_SPEC.md`
    §13.7's morphing-bug note.
  - **Refactored the same day to be mesh-generic** (direct request: "the
    cube should act as a placeholder for 3d complex objects which will be
    imported later on"): geometry (`Mesh`/`MeshFace`) is now fully
    decoupled from the rendering pipeline (`CubeWindow._draw_object_3d`),
    which operates on ANY mesh's vertices/faces/colors with zero
    cube-specific logic. Verified by swapping in a completely different
    mesh (a tetrahedron) at runtime with no code changes. A real 3D-file
    import (OBJ/glTF) is NOT built yet — that's a separate, scoped future
    step (loader + maybe a faster depth-sort for many-triangle meshes),
    not blocking anything currently planned. Full account:
    `GESTURE_PIPELINE_SPEC.md` §13.8.
- **Release via closed fist: PARKED**, not just blocked — it depended on
  row 2 (open-palm/closed-fist detection), which is itself now parked
  (see above). Candidates that were logged for it (§13.5) stay on record
  in case row 2 is ever un-parked, but this is not the active release
  plan.
- **Release trigger — quick full hand-open, confirmed as the sole active
  plan (2026-08-01, later conversation), not yet started**: unsnap by
  quickly fully opening the hand. Design + a proposed
  recording/discrimination plan: §14.2 below. Supersedes the closed-fist
  plan above (row 2 being parked settles this), not an alternative to
  weigh against it anymore.

## 2. Immediate next actions — three build targets, confirmed build order

All three are NEW and NOT YET STARTED. The first two (§2.1, §2.2) were
proposed 2026-08-01 and specifically deferred to a fresh conversation
(this handoff) rather than built the same session; the third (§2.3, Z-axis
translation) was added and design-confirmed in a later conversation.
**Confirmed order: §2.1 → §2.2 → §2.3** — do the pivot fix first. Full
design detail for all three is in `GESTURE_PIPELINE_SPEC.md` §14 (§14.1,
§14.2, §14.3) — this section only summarizes; read the relevant spec
section before starting any of them.

### 2.1 Fix: translation needs a grab-relative offset — mechanism resolved via follow-up discussion, this is not an anchor-selection problem

**Corrected understanding (direct user correction)**: the earlier framing
("which tracked anchor drifts least") was wrong. Reading the actual code
(`HandsTriggeredActions.py`'s `on_hands_frame`) confirmed the real defect:
translation has **no grab-time offset at all** — the cube's center is
forced to exactly equal one tracked anchor's position every single frame.
No choice of anchor landmark fixes a zero-offset design.

**First redesign draft (single frozen offset + reapply rotation's 3D
quaternion each frame) left a real gap**: it never specified how a 2D
pixel-space offset and rotation's 3D `world_landmarks`-based delta are
supposed to combine — translation has always been deliberately kept in
2D image-space (§1), unlike rotation. A direct follow-up question ("how
do you define the offset at grab? In relation to the phalanges?")
surfaced this gap and led to picking a different, more literal mechanism.

**Chosen mechanism: distance-weighted live landmark tracking**, not a
frozen-offset-plus-rotation-transform:
- At grab: pick ~9 phalange-adjacent candidate landmarks (5 fingertips +
  4 non-thumb MCPs), weight each by inverse distance from the object at
  that instant, normalize, and **freeze** those weights for the hold —
  the literal, computable version of "phalanges locked once grabbed": the
  landmark SET and their relative influence is decided once, from real
  grab-instant geometry.
- A small constant residual offset is also stored so the grab frame
  itself is exactly continuous (no pop), same discipline as rotation's
  own baseline capture.
- Every frame after: recompute the weighted combination using the SAME
  frozen weights but each landmark's CURRENT tracked position (plus the
  residual). No rotation math is reused at all — translation stays purely
  2D/pixel-based throughout, sidestepping the 2D/3D space-mismatch the
  first draft left unresolved. Rotation-coupling falls out naturally
  because real fingertip/knuckle landmarks genuinely swing more than the
  wrist during a twist.
- **Gets Napier's grip-size distinction for free**: a small object grabbed
  near the fingertips concentrates weight on TIP landmarks
  (precision-grip-like); a large object grabbed more centrally spreads
  weight across MCPs (power-grip-like) — emergent from the actual grab
  geometry, not a hardcoded per-cube-size branch. This **supersedes** the
  first draft's "maybe use a different single anchor per object size"
  idea entirely.

**Literature-grounded, not a guess**: human grasp biomechanics (Napier's
1956 power-grip/precision-grip taxonomy — object size determines where on
the hand an object sits, not one fixed landmark) and VR/AR industry
practice (Unity XR Interaction Toolkit's Dynamic Attach, Meta Horizon
OS's `GripPoint`) establish the broader "capture the hand-object
relationship once at grab, follow it thereafter" principle as standard,
not an edge case — this project's weighted-multi-landmark mechanism is a
finer-grained instantiation of that same principle, going further because
per-landmark data is already available. Full citations and the caveat
about this pipeline's landmarks not being mechanically constrained by a
real object (unlike VR controllers/assumed hand conformance):
`GESTURE_PIPELINE_SPEC.md` §14.1 (fully rewritten).

**Important consequence, unchanged from the first draft**: once fixed
correctly, some translation during pure rotation is EXPECTED and
physically correct (an object held off-center from the wrist's rotation
axis genuinely swings when the wrist twists) — this is no longer "the
cube shouldn't translate at all." Verification should confirm the
coupling now looks proportional/grounded, not check for zero translation.

**Known risk to verify, not assume**: individual landmarks are noisier
than the existing multi-point centroid — if weights concentrate sharply
(small object grabbed right at the fingertips), the signal could be
jitterier than today's stable translation. Mitigations (a weight-
concentration cap, light temporal smoothing) are only worth adding if
recorded data actually shows they're needed. Full verification
methodology: §14.1.

**Verified against real recordings (2026-08-01, same conversation
continued)**: built `RecordTranslationPivotDebug.py`/
`record_translation_pivot_debug.bat` + `AnalyzeTranslationPivot.py`
(saved to `E:\Python\Recordings for vision_pipeline\Position_during_rotation`,
direct request). 7 real hold intervals across 3 valid takes (both cube
sizes): **no-pop exact (0.0000px always), jitter comparable to today,
translation now measurably scales with real rotation** (~2x jitter under
high vs. low rotation amount, consistent across all 7 intervals).

**Known, deliberately DEFERRED limitation found the same session**: the
computed point swings toward the palm specifically under **yaw** (hand
turning sideways, knuckle row going edge-on to the camera) — confirmed
empirically (correlation −0.25 across intervals, using the same
recordings, no new capture needed). Pitch/roll are fine. Root cause: pure
2D pixel-distance weighting can't distinguish yaw-driven foreshortening
from real repositioning — a depth-ambiguity problem, same class as §14.3's
Z-axis-at-grab issue, likely the SAME underlying cause. **Decision:
implement as-is** (still a strict improvement over today's zero-offset
forcing), revisit yaw together with a **proposed future startup Z-axis
calibration step** (not yet designed) when Z-axis translation is actually
picked up. Full account: `GESTURE_PIPELINE_SPEC.md` §14.1.1.

**Implemented in `LiveSnapDebug.py` and replay-verified against real
recorded data (2026-08-01, same conversation continued)**: `Cube` gained
`grab_landmark_weights`/`grab_residual_offset` (mirrors the
`grab_hand_orientation`/`grab_cube_orientation` pattern), `_compute_grab_weights`/
`_weighted_position` added, `update_hands` now computes the grab-time
weights from the cube's own pre-existing position (not the hand anchor)
and tracks live thereafter. **Verified by replaying a real recording's
landmarks through the actual (modified) `update_hands` function**: at the
exact grab frame, the cube stayed at its own resting position (320.0,
240.0) with zero pop; the OLD recorded data at that same frame had already
popped to (395.9, 255.3) — a ~76px discontinuous jump the new mechanism
eliminates, confirmed against real camera data through the real code path,
not just synthetic math.

**Confirmed working live (2026-08-01, same conversation continued)** —
user tested the redesigned mechanism against a real camera via
`debug_snap.bat`: "it's working." Same confirmation pattern as rotation's
own live test (§13.7).

**Ported to production (2026-08-01, same conversation continued)**:
`CubeWindow.py`'s `Cube` gained the identical `grab_landmark_weights`/
`grab_residual_offset` fields; `HandsTriggeredActions.py` gained
`_weighted_position`/`_compute_grab_weights` (verbatim formula) and
`on_hands_frame`'s translation logic now mirrors `LiveSnapDebug.py`'s.
**Verification method differs from usual** because
`HandsTriggeredActions.py` opens a real pygame window as an import side
effect (module-level `cube_window = CubeWindow()`), so it can't be
safely replayed through a script the way `LiveSnapDebug.py` was — instead
verified by careful line-by-line parity review against the already
live-verified debug-tool version (same candidate landmarks, same epsilon,
same formulas, same no-pop construction). One intentional, justified
divergence: translation's grab-weight capture is unconditional (not
gated on `hand_quat_now is not None` the way rotation's baseline is),
since translation only needs 2D `landmarks` (always available), not the
slower-arriving `world_landmarks` — no "missed the grab-frame capture"
fallback needed for it.

**Status: implemented, replay-verified, live-camera-confirmed in the
debug tool, ported to production and parity-reviewed, AND live production
tested (2026-08-01)** — user ran the actual client/server pipeline
(`launch.bat`) and confirmed it mostly works.

**One spurious, NOT-YET-ROOT-CAUSED glitch found during that live
production test**: "the cube jumped from one hand to another and came
back to the hand" — not reproducible on demand. Leading, UNVERIFIED
hypothesis: the mechanism has no outlier rejection across its 9 candidate
landmarks (unlike rotation's reliability-weighted predictive filter) — a
single fingertip briefly misread (e.g. hand occlusion) could pull the
weighted average toward a bad reading for a frame or two, looking exactly
like a jump-and-recover. This is exactly the risk flagged as
deferred-but-unverified when the mechanism was designed — real evidence
it can happen, even without a controlled repro. **Decision (direct
request): document only, no code change** — this project's standing
discipline is not to fix without verifying against real data, and there's
no repro to verify against. Revisit if this recurs or becomes
reproducible. Full account: `GESTURE_PIPELINE_SPEC.md` §14.1.3.

**Considered done for now**, with this known open glitch tracked
separately, not blocking moving on to §2.2 (release trigger).

**Separate, unrelated bug found and FIXED the same session: thumb-outward
restriction (rule 3) was silently INVERTED in production only** — "I can
grab only if the hands are with the thumbs facing outwards... opposite of
the debug pipeline where rightfully the grab was done when the thumbs
were facing inwards." Root-caused (not guessed): `VisionPipeline.py`
detects on the raw, un-mirrored frame; pixel/world COORDINATES get
mirrored afterward (`invert_x=True`) but the handedness LABEL never was —
MediaPipe's Left/Right classification assumes a mirrored input, so on an
unmirrored frame it reports the true anatomical hand, inverting
`_is_thumb_outward`'s handedness-dependent chirality correction
specifically (the one place that's not handedness-symmetric). Fixed at
the single source (`hands_visualizer.py`'s new `_mirror_handedness()`),
not by patching the consumer. **Not yet independently live-tested** —
recommend confirming thumb-inward now correctly permits grab in
production. Full account: `GESTURE_PIPELINE_SPEC.md` §13.6.1.

### 2.2 New candidate: unsnap by quickly fully opening the hand

**Design**: while holding an object, rapidly and fully opening the hand
(fingers extending fast) unsnaps it — **provided the wrist/hand base
doesn't translate much at the same time**. That qualifier exists
specifically to distinguish this from a **different, NOT YET BUILT**
future gesture: moving the whole hand toward/away from the camera to
control depth/Z-axis translation, where fingers AND wrist would scale
together in the image, unlike this release gesture where only the
fingers change quickly while the wrist stays comparatively stable.

**Proposed data-collection plan** (direct request): record 6 sessions of
the target gesture (grab, then quickly fully open the hand) and 6 of the
confound to rule out (moving the whole hand toward/away from the camera,
no release intent) — across a few different hand positions/distances so
whatever signal is found generalizes. Reuse/extend `RecordRotationDebug.py`'s
recording harness (same schema: full landmark data, pixel + world, both
hands, per frame). Offline, compare candidate discriminating signals
(rate of finger-extension/curl-angle change vs. rate of overall hand-scale
change) across all 12 recordings before designing any threshold — full
detail and reasoning in §14.2.

**Resolved (2026-08-01, later conversation)**: this supersedes the
closed-fist release plan, not coexists with it — open-palm/closed-fist
detection (row 2) is parked, so closed-fist release has no working
detection path regardless. This is the sole active release-trigger plan,
second in the confirmed build order.

### 2.3 New: Z-axis (camera-view-axis) translation — design confirmed, NOT YET BUILT

**Design, confirmed with the user 2026-08-01 (later conversation)**:
moving a snapped hand closer to/farther from the camera translates the
object along that same axis.

- **Signal**: apparent hand-span ratio (`wrist↔middle-MCP` image-space
  distance vs. a grab-time baseline) — the same metric the old, dropped
  depth-proxy row used — **not** raw `world_landmarks` `z` (established
  unreliable monocularly).
- **Mapping**: absolute and continuous, like today's X/Y translation (cube
  position = mapped(hand position) every frame) — **not** a
  grab-time-baseline delta like rotation.
- **Snap becomes a 3D proximity check**: a hand can only snap a cube if
  it's close enough on X, Y, **and** this new Z axis — not just X/Y as
  today. This changes existing snap/grab-radius logic (`_try_snap`), not
  just adding something new on top of it.
- **Scope**: Z-translation only — the old dropped depth-proxy scale/color
  effect is not being revived alongside this.

Queued **third**, after §2.1 and §2.2 above. Open unknowns (exact
ratio→Z mapping function, how Z-tolerance relates to the existing grab
radius, hand-size recalibration) deliberately left unresolved until this
is actually picked up — full detail: `GESTURE_PIPELINE_SPEC.md` §14.3.

## 3. Environment notes

- Python env: `Local_pc/Movement_with_hand_detection/.venv` — shared by
  the client (`PythonApp_Main.py`), the server (`VisionPipeline.py`,
  launched via the same `sys.executable`), and all debug tools
  (`LiveSnapDebug.py`, `debug_snap.bat`, `RecordRotationDebug.py`,
  `record_rotation_debug.bat`; the archived `LiveGestureDebug.py`/
  `debug.bat` for pinch).
- **§14.1 verification tooling built AND RUN against real camera data
  (2026-08-01, later conversation)**: `RecordTranslationPivotDebug.py`/
  `record_translation_pivot_debug.bat` (same lineage as
  `RecordRotationDebug.py` — imports `LiveSnapDebug.py`'s real, already
  live-verified snap/translate logic, so recorded grab events and cube
  centers are real ground truth, not simulated), saved to
  `E:\Python\Recordings for vision_pipeline\Position_during_rotation`
  (direct request), and `AnalyzeTranslationPivot.py` (offline: finds each
  real grab event, freezes distance-weighted candidate-landmark weights,
  replays the new mechanism frame-by-frame, checks no-pop/jitter/
  rotation-coupling/yaw-foreshortening). Core math synthetically
  sanity-checked before ever touching the camera. **Verified against 7
  real hold intervals**: no-pop exact, jitter comparable to today,
  rotation-coupling confirmed proportional. **One deferred limitation
  found and accepted** (yaw/palm-sinking, see §2.1 above and
  `GESTURE_PIPELINE_SPEC.md` §14.1.1). Next step: wire the mechanism into
  `LiveSnapDebug.py` for a true live visual check.
- Model files: `Local_pc/Python_Server_MediaPipe_vision_pipeline/
  Resources/hand_landmarker.task` (in active use) and
  `gesture_recognizer.task` (downloaded 2026-08-01, kept on disk, not
  currently used by any code path — see §1).
- **Live pipeline processes hold the webcam device** — if a debug/launch
  session's window isn't explicitly closed, the process keeps running and
  the *next* attempt to open the camera fails with "Could not open webcam
  ... Is another program using the camera?". Check `Get-Process python`
  and stop stale ones before relaunching if this happens.
- `debug_snap.bat`/`LiveSnapDebug.py` duplicates (not imports)
  `HandsTriggeredActions.py`'s/`CubeWindow.py`'s snap/translate/orientation/
  rendering logic by design (see the file's own header comment for why —
  its `cube_window` is a module-level object that opens a real pygame
  window as an import side effect, which this single-OpenCV-window tool
  must not trigger). **Any production logic OR rendering change needs to
  be mirrored there too** — this was true throughout the 2026-08-01
  session (rotation, the mesh-generic refactor, the morphing-bug fix all
  had to be applied in both places) and still applies going forward.

## 4. Standing discipline (carried over, still applies)

- **Live-verify before trusting any claim, including your own geometric
  assumptions** — the whole 2026-08-01 session is full of concrete
  examples: MediaPipe's built-in `Closed_Fist` classifier looked correct
  in isolation but failed across real hand positions; the thumb-outward
  sign convention was calibrated live before being trusted; the rotation
  quaternion's world-landmark mirroring convention was flagged as
  unverified and then confirmed fine only once actually tested against a
  real camera; the cube-morphing bug was only found by watching it live,
  not by inspection. Apply the same pattern to both new build targets in
  §2 — test against recorded data before committing to a fix, same as
  every prior step.
- **No heuristic pile-up** — if a value needs tuning (grab radius,
  rotation slerp factor, `CONDITIONING_ALPHA_LOW/HIGH`, etc.), tune it
  live and record the reasoning, don't guess-and-forget.
- **Same-frame ordering matters** in per-hand stateful loops — the
  release/re-snap jump bug is the concrete example; think through what
  state a second hand's pass can observe from the first hand's pass in
  the same frame before assuming independence.
- **Keep `GAME_RULES.md` updated** every time a new rule is confirmed and
  built — it's the one place meant to answer "what does the game do
  today" without reading code or design prose.
- **Recorded-data-first empiricism, not guessing** — this is now a deeply
  established pattern in this project (the entire pitch-crossing rotation
  investigation, the thumb/PCA landmark tests, the predictive-filter
  verification, the morphing-bug fix all followed it): when a design
  decision is unclear, build a small recorder, capture real data, analyze
  it offline, THEN decide. Both new build targets in §2 are explicitly
  designed to be approached this way — don't skip straight to an
  implementation guess for either.
- The full, generalized lessons-learned list from the pinch arc (still
  broadly applicable) lives in `HANDOFF_GESTURE_CLASSIFIER.md` §0 /
  `GESTURE_PIPELINE_SPEC.md` §12.7 — worth a skim if this build hits a
  wall that feels familiar.
