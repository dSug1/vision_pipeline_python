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
| 1 | Scaffolding | both, independent | full 21-landmark list per hand | n/a — plumbing only | red cube added to scene; both hands' landmarks flow through (not just left); no ownership/grab logic yet | **Built, not yet live-verified** — code in `Local_pc/Movement_with_hand_detection/`; run `launch.bat` and confirm blue cube follows left hand, red cube follows right hand |
| 2 | Open-palm / closed-fist detection | each hand independently | `world_landmarks` (or MediaPipe's own Gesture Recognizer output — try that first) | MediaPipe's built-in `Open_Palm`/`Closed_Fist` classes if live-verified sufficient; else a **trained classifier** per `GESTURE_PIPELINE_SPEC.md`'s pipeline | `Open_Palm` gates rotation (row 7); `Closed_Fist` triggers release (row 4) | **Superseded pinch (2026-08-01)** — pinch archived after Stage 4 live testing (`GESTURE_PIPELINE_SPEC.md` §13.1); this row replaces the old "pinch detection" row. Not started |
| 3 | Snap acquisition + arbitration | each hand vs. shared registry | hand position (palm-center, §13.3) vs. cube positions | pure proximity trigger — nearest **unowned** cube within grab radius of hand position → claim in shared registry | idle/hover → snapped | Not started — replaces the old pinch-rising-edge trigger; arbitration logic itself (shared registry, nearest-unowned-cube) unchanged from the original design |
| 4 | Release (un-snap) | each hand | `Closed_Fist` (row 2), or tracking loss | closed-fist detected on a hand holding a snapped cube **or** hand tracking lost | snapped → idle; cube frozen in place; ownership cleared; requires fresh proximity-snap to reacquire | Not started — replaces the old un-pinch trigger; freeze/ownership-clear semantics unchanged |
| 5 | Translation | each hand, while snapped | hand position (palm-center, image-space X/Y) | cube position = mapped(hand position), X/Y only | cube follows hand | Not started — replaces "pinch midpoint" with palm-center; mechanism otherwise unchanged |
| 6 | Depth proxy → scale + color | each hand, while snapped | apparent hand span (image coords) vs. calibration baseline | `ratio = current_span / baseline_span` | cube scale ∝ ratio; color lerps light↔dark by ratio | **Dropped for now (2026-08-01)** — not part of the new gesture set as directed; not carried forward automatically, revisit only if explicitly wanted again |
| 7 | Rotation (quaternion) | each hand, while snapped **and** `Open_Palm` | `world_landmarks`: wrist(0), index_MCP(5), pinky_MCP(17) | orthonormal frame → quaternion → slerp | cube orientation follows hand orientation | Not started — design unchanged from original (§2); now additionally gated on `Open_Palm` (row 2) to avoid rotation noise during pose transitions — **requires sending `world_landmarks` over the wire, not currently sent** (server only sends 2D pixel landmarks today, see §4) |

**Rows 2-4 replaced (2026-08-01)**: pinch's onset/offset event pair (the
original rows 2/4, decomposed per the 2026-07-30 note below) is replaced
by a proximity trigger (snap) and a `Closed_Fist` trigger (release) —
full rationale and state-of-the-art check in `GESTURE_PIPELINE_SPEC.md`
§13. The original pinch/release decomposition note is preserved below for
historical context, since the same "onset and offset are independently-
tuned, not assumed symmetric" discipline likely still applies to
open-palm/closed-fist detection if a custom classifier ends up needed.

**Original row 2 (pinch/onset) and row 4 (release/offset) note
(2026-07-30, historical)**: these were the same episodic gesture's two
event boundaries, not independent gestures — decomposed and cross-checked
against literature in `GESTURE_PIPELINE_SPEC.md` §3.3.1, which also drove
the 6-orientation recording grid in that document's §5 (`front`/
`palm_away`/`palm_up`/`palm_down`/`palm_in`/`palm_out`) replacing the
earlier 3-orientation version. See §2's release-conditions bullet above
for the design consequence (still applies to the new release trigger).

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
- Exact grab-radius value (likely scaled to cube size) — still open,
  applies to the new proximity-snap trigger now instead of the old
  pinch-based one.
- Tie-break rule if both hands' proximity triggers land on the same free
  cube in the same frame (currently unspecified — low-probability edge
  case, revisit only if it's actually hit in practice).
- Exact hand-span metric for the depth proxy (wrist↔middle-MCP vs. a full
  bounding-box diagonal) — moot for now since row 6 is dropped; revisit
  only if depth-proxy scale/color comes back.
- See `GESTURE_PIPELINE_SPEC.md` §13.4 for the new gesture set's own open
  questions (whether `Open_Palm`/`Closed_Fist` need custom training,
  whether snap should be blocked while closed-fist, whether rotation's
  `Open_Palm` gate is the right design).

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
