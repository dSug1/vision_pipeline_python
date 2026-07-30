# Gesture Classifier Pipeline — Specification

Written 2026-07-30, after abandoning a rule-based (hand-tuned threshold)
pinch classifier. This is the **project-wide, gesture-agnostic**
specification for how every gesture classifier gets built from here on —
pinch, and every gesture added after it. It is deliberately separate from
`PART_ONE.md`, which stays as the historical record of what was tried for
pinch and why the rule-based approach was abandoned (real evidence, worth
keeping — see §1 below for the summary and the pointer back).

**This document is the actual deliverable.** The specific pinch classifier
is one instance of running this pipeline; the pipeline itself — labeled
recording → literature benchmark → trained classifier → live debug tool,
applied identically to every gesture — is what's meant to outlast any one
gesture and is worth getting right.

## 1. Why rule-based thresholds were abandoned (full detail: `PART_ONE.md` §6–§8)

Summary, for context on why this document exists:

- A pinch classifier built from hand-tuned geometric thresholds (a
  thumb-index distance ratio, a finger-curl angle, later a closing-velocity
  window) worked well against the specific hand orientation it was
  calibrated on, but **rotating the hand caused false positives 38.5% of
  the time** (62.2% on one hand), and this wasn't tracking noise — MediaPipe
  reported >97% confidence throughout, meaning the false positives reflect
  genuine, high-confidence 3D geometry.
- Adding a closing-velocity requirement helped (62.2% → 22.2%) but didn't
  fix it, and recording more data revealed the false positive was
  **reproducible across every rotation recording**, with sustained runs of
  14–34 frames — a range that came to overlap with genuine pinch-hold
  durations once cleaner pinch data was recorded. Duration-based debouncing
  couldn't separate the two either.
- Conclusion: **a purely geometric single/short-window rule cannot cleanly
  separate "genuinely pinching" from "hand relaxed into a similar shape
  mid-rotation," because the two are sometimes actually geometrically
  identical.** This is a structural limit of the approach, not a threshold
  that needed more tuning.
- The considered alternative — bolting a hand-crafted heuristic onto the
  rule-based classifier to patch this one failure case (e.g. "require the
  transition to be fast") — was explicitly rejected. It isn't backed by
  literature for this problem, it doesn't generalize, and it's exactly the
  kind of heuristic pile-up this document exists to prevent (§2).

## 2. Core discipline (governs everything below — read this even if skimming the rest)

- **No heuristic pile-up, ever.** If a trained classifier misclassifies
  something, the fix is (a) more/better labeled data covering that failure
  case as its own explicit class, or (b) reconsidering the feature set or
  model with literature backing — **never** a special-case rule bolted onto
  the classifier's output to patch one observed failure.
- **Every gesture goes through the same four stages below**, in order, no
  skipping. A gesture "seeming simple" is not a reason to shortcut this —
  pinch looked simple too.
- **Every design decision — which features, which model, which
  hyperparameters — must be justified by measured data from our own
  recordings, a cited state-of-the-art source, or both.** Never guessed.
  "Compare with state-of-the-art literature" is a required step, not an
  optional nicety — it's what previously surfaced the curl-angle feature,
  Otsu's method, and the AtaTouch closing-velocity precedent.

## 3. Pipeline stages (apply identically to every gesture)

### Decide first: episodic or continuous?

Every gesture in §3 of `PART_ONE.md`'s matrix is one of two structurally
different things, and the decision changes stages 1, 3, and 4 below — make
it before recording anything.

- **Episodic**: a discrete event with a beginning and an end — pinch/grab,
  release, a future point/click, a future swipe. Literature treats these as
  having **onset → apex → offset** phases (onset = neutral-state → peak,
  apex = held, offset = peak → neutral-state again) — a named structure,
  not something specific to this project. Needs an **event-detection
  layer** on top of a per-frame classifier (§3.3).
- **Continuous**: an always-on signal with no "detected" moment — hand
  translation (matrix row #5), the depth proxy driving scale/color (row
  #6), rotation (row #7). These are regression-shaped outputs, sampled and
  (optionally) smoothed every frame — there's no onset/apex/offset to
  detect, so §3.3's event layer doesn't apply. Simpler: stage 3 trains/
  computes a per-frame value, stage 4 just displays it live.

Pinch (matrix row #2) is **episodic** — the rest of this section uses it as
the running example, but the episodic/continuous split applies to every
future gesture the same way.

### Stage 1 — Labeled recording

- **Define the full taxonomy of classes before recording anything** — one
  positive class, plus every negative/confusable class stage 2's
  literature check identifies. Don't improvise session-by-session.
- **Classifier-training sessions: exactly one label = one unambiguous, held
  physical state for the session's entire duration.** This is a hard rule
  change from the earlier workflow: the old `pinch_x3` sessions (3 cycles
  per file) had no ground-truth per-frame boundary between pinching and
  not-pinching, which made them unusable as supervised training data — the
  Otsu-split trick used to approximate labels post-hoc was itself an
  unlabeled-data workaround, not a substitute for real labels. **No
  mixed-state sessions used as classifier training data.**
- **Episodic gestures also need a second, distinct recording type: cyclic/
  transition sessions, used only to tune and validate the event-detection
  layer (§3.3) — never as classifier training data.** These record the
  gesture repeated a few times in one session (the old `pinch_x3`-style
  cadence, but now with an explicit, separate purpose and a distinct label,
  e.g. `pinch_cycles` vs. the held-state `pinch`) — what matters for the
  event layer is the *shape and timing* of real onset→apex→offset
  transitions, which a held-state session never contains and a per-frame
  label isn't needed to evaluate (the event layer is tuned by inspecting
  the confidence-over-time signal, not by a ground-truth label per frame).
  Record these with deliberate, sustained holds (not rushed) — recording
  cadence directly affects whether genuine transitions have a distinguishable
  timing signature at all (this was learned the hard way: the original
  `pinch_x3` sessions were recorded too fast — 3 cycles in 4 seconds — and
  genuine holds ended up barely longer than incidental noise, see
  `PART_ONE.md` §7.2).
- **Orientation is a first-class recorded dimension, not an afterthought.**
  Every class — positive and negative — gets recorded across a small fixed
  orientation grid (front-facing, palm-up, palm-away, at minimum). This is
  a direct response to §1's finding, not a hedge.
- **Camera-in-front for now.** The same taxonomy gets re-recorded later
  with a forward/outward-facing camera once the project moves toward the
  glasses use case (Specification.md §12) — not now, and not assumed to
  transfer unchanged.
- **Recording tool**: `Local_pc/Movement_with_hand_detection/record.bat`
  (wraps `Local_pc/Python_Server_MediaPipe_vision_pipeline/RecordSession.py`)
  — kept from the old approach, its mechanics are sound and gesture-
  agnostic: timed auto-stop (no keypress needed while both hands are busy),
  captures both normalized `landmarks` and metric `world_landmarks` per
  hand per frame (Specification.md §6 schema), saves one JSON file per
  session with a `label` field. **The `label` argument must be an exact
  string from the pre-defined taxonomy** — not an improvised name.
- **At least 2–3 sessions per class×orientation cell**, so stage 3 can hold
  out whole sessions for testing rather than splitting within one.
- `recordings/` stays gitignored (raw capture data, not source) and is
  currently **empty** — all prior recordings were deleted with the
  rule-based approach (they used the old cyclic-session labeling and can't
  be reused as supervised training data).

### Stage 2 — Benchmark against state-of-the-art literature

- Before writing any feature-extraction or model code: research how
  similar gestures are classified in existing implementations and papers.
  This is what determines (a) which negative/confusable classes stage 1
  needs, (b) which geometric features are worth extracting as model input,
  (c) what model architecture actually fits this kind of task.
- Record findings and sources inline (in this document's per-gesture
  appendix, or `PART_ONE.md` for pinch specifically) so the reasoning is
  auditable later — "we picked X" is not sufficient, "we picked X because
  \[source\]" is.

### Stage 3 — Train the base per-frame classifier

Applies to both episodic and continuous gestures — this stage produces a
per-frame value; §3.3 (episodic only) turns that into discrete events.

- **Feature extraction**: pure functions over `world_landmarks` (metric,
  hand-relative 3D — not pixels, not normalized image-space). Camera-frame
  independence is unchanged from the old approach and remains a hard
  requirement. Rebuild this fresh — the deleted `GestureRules.py`'s math
  (distance/angle helpers, hand-size normalization) was correct, but the
  module is being rewritten clean rather than resurrected, so it isn't
  structured around the abandoned rule-based classification approach.
  **Compare hand-crafted features against raw landmark coordinates as
  model input** — see §6.2, MediaPipe's own classifier uses the latter.
- **Model output is a continuous value, not a thresholded boolean** — for
  episodic gestures, a probability/confidence in `[0,1]` (logistic
  regression's natural sigmoid output), not a hard classification. This
  matches how production XR hand-tracking SDKs do it: Ultraleap's pinch
  detection reports pinch strength as a continuous 0–1 confidence value,
  not a binary. The thresholding (if any) happens in §3.3's event layer,
  not here — keeping the base classifier's output continuous is what makes
  the event layer's derivative/agreement checks possible at all (you can't
  take a meaningful derivative of an already-thresholded boolean).
- **Model**: a small, hand-rolled classifier with **no heavy ML framework
  dependency** — logistic regression or a tiny 2-layer MLP, implemented in
  plain Python/math. This matches Specification.md §7.1's portability
  requirement (weights export as flat arrays, re-implementable as a
  forward pass in JS later) — don't add scikit-learn/PyTorch/TensorFlow as
  a dependency for something this small. Start with logistic regression as
  the simpler baseline; escalate to a small MLP only if it measurably
  underperforms.
- **Train/test split at the session level, not the frame level.** Frames
  within one recording are highly correlated (~30fps of the same held
  pose, near-duplicates of each other) — a random per-frame split leaks
  information between train and test and overstates accuracy. Hold out
  whole sessions, ideally spanning different orientations, for testing.
  (Cyclic/transition sessions per Stage 1 are never part of this
  train/test split — they're §3.3's data, not the classifier's.)
- **Report accuracy, precision, recall, and a confusion matrix per class on
  the held-out test sessions** — training-set numbers are not sufficient
  evidence a classifier works.
- **Export trained weights as plain JSON (flat arrays)**, not a
  framework-specific serialization (pickle, `.pt`, etc.) — keeps them
  portable and human-inspectable, and ready for an eventual JS port.
- **Continuous gestures stop here.** The trained (or, if simple enough,
  hand-derived) per-frame value *is* the output — feed it to matrix rows
  #5/#6/#7 directly, smoothed/lerped as those rows already specify. No
  event layer, no onset/offset — skip straight to Stage 4.

### Stage 3.3 — Event-detection layer (episodic gestures only)

This is new, added in response to a direct question about whether
state-of-the-art literature uses time-derivative approaches — it does, but
as a layer on top of a per-frame classifier, not a replacement for one, and
not the ad-hoc heuristic considered and rejected earlier in this project
(§1). Three literature-backed pieces, cited so this stays auditable:

- **Onset → apex → offset structure.** Episodic gestures are formally
  understood in the gesture-recognition literature as having three phases:
  onset (neutral state → peak), apex (held at peak), offset (peak → neutral
  again). Build the event layer as an explicit state machine over these
  three phases, driven by Stage 3's continuous confidence signal — this is
  the same shape as the matrix's existing grab/release design (row #3's
  idle→hover→grabbed→released, row #4's release), so this isn't new
  complexity, it's naming and grounding a structure the matrix already
  assumed.
- **Onset (and offset) confirmed by multi-signal derivative agreement, not
  by the confidence value crossing a threshold alone.** A described
  technique ("derivative classifiers" in gesture-recognition literature)
  computes velocity (from consecutive-frame pairs) and/or acceleration
  (from short multi-frame windows) from **several underlying signals at
  once** — not just the final confidence score's own slope — and confirms
  an onset only when the sign and magnitude of those derivatives *agree*
  across signals. This is what rejects a gesture "made too slowly,
  unintentionally, or due to noise" — precisely this project's rotation
  false-positive failure mode (§1), but as a named, sourced technique
  instead of a one-off rule invented to patch that specific case. Concretely
  for pinch: derivatives of the confidence score itself, plus 1–2 of the
  underlying geometric signals feeding it (e.g. the raw thumb-index
  distance), checked for agreement — not a single signal's derivative
  alone, which is what the earlier (rejected) "fast transition" heuristic
  amounted to.
- **Production precedent for the overall shape**: Ultraleap's and Meta
  Quest's hand-tracking SDKs both implement pinch/grab as **separate
  start-event and stop-event detection**, not one continuous binary
  classification — validating the onset/offset event-machine shape above
  as how this is actually done in shipped systems, not just academic
  literature.
- **Tune the event layer's parameters (window size, agreement threshold)
  against the cyclic/transition recordings from Stage 1** — not the
  held-state sessions (those don't contain real transitions) and not by
  guessing. Validate against the `rotating_no_pinch`-equivalent negative
  session too, the same way the abandoned rule-based attempt's rotation
  data was used, so this doesn't repeat that failure blind.
- **This layer's parameters are still subject to §2's discipline**: if the
  event layer misfires on a case Stage 1 didn't anticipate, the fix is
  recording that case explicitly and re-tuning against it — not adding a
  further special case on top of the event layer itself.

### Stage 4 — Live debug/run tool

- A standalone script: open the webcam, run MediaPipe `HandLandmarker`,
  load the trained model's exported weights, compute the forward pass per
  hand per frame, and display results live — **the continuous confidence
  value** (not just a boolean) for every gesture, **plus the onset/apex/
  offset state** for episodic gestures once §3.3 exists. Console log on
  each event transition (onset/offset), not every frame. Same UX concept as
  the deleted `LiveGestureDebug.py`, rebuilt against the new trained-model
  and event-layer interfaces.
- **Not optional polish — required before a gesture counts as done.** It
  validates things Stage 3/3.3's held-out test data structurally cannot:
  (a) the live MediaPipe→model data path actually works end-to-end (a real
  integration bug was caught here last time: MediaPipe's live result
  objects use `.x`/`.y`/`.z` attributes, not the `{"x","y","z"}` dict shape
  JSON recordings use — easy to miss if a classifier is only ever tested
  against recorded data), and (b) the classifier's and event layer's
  real-world feel, independent of what held-out test accuracy says.
- **If live testing reveals a systematic failure mode, that is new
  information for Stage 1 (record it as an explicit new class or a new
  cyclic/transition session) and Stage 3/3.3 (retrain / re-tune) — never a
  reason to add a rule on top of the trained classifier's or event layer's
  output.** This is §2's discipline, operationalized at the exact point
  where the temptation to patch instead of retrain is strongest.

## 4. What's reusable from the old attempt, and what was deleted

**Kept:**
- `RecordSession.py` / `record.bat` — capture mechanics are gesture-
  agnostic and sound; only the labeling *protocol* used with them changes
  (§3 stage 1).
- The data schema (Specification.md §6) — normalized + world landmarks per
  hand per frame.
- The four-stage shape of the workflow itself (record → benchmark → build
  classifier → run/debug) — this was correct; only stage 3's *method*
  changes (trained model instead of hand-picked thresholds).
- `PART_ONE.md`'s existing write-up of the rule-based attempt — kept as
  historical evidence for *why* this pivot happened, marked accordingly
  (see that file's top-of-document note), not deleted.

**Deleted** (obsolete — tied to the abandoned rule-based classifier, not
reusable as-is): `Resources/GestureRules.py`, `AnalyzeRecordings.py`,
`ValidateWindowedClassifier.py`, `LiveGestureDebug.py`, `debug_gestures.bat`,
and every recording under `recordings/` (old cyclic-session labels aren't
valid supervised-training labels under §3 stage 1's new rule).

## 5. Worked example: proposed pinch recording taxonomy (not yet executed)

A starting proposal for re-launching pinch under this pipeline — confirm
or adjust at the start of implementation, don't treat this as final. Pinch
is **episodic** (§3's "decide first" note), so it needs both of Stage 1's
recording types.

**Classes (for the base classifier, §3 — held-state sessions):**
- `pinch` (positive)
- `open_hand`, `fist`, `rotating_no_pinch` (negative — the first two from
  general gesture-classification practice, the third specifically because
  §1's finding was rotation-induced, not a class this project would have
  picked without that evidence)

**Orientation grid** (applied to `pinch`/`open_hand`/`fist`):
`front` (palm toward camera), `palm_up`, `palm_away` (back of hand to
camera). `rotating_no_pinch` inherently sweeps orientation within the
session, so it doesn't need separate per-orientation sessions the same way.

**Session labels** (`<class>_<orientation>`, e.g. `pinch_front`,
`pinch_palmup`, `pinch_palmaway`, `open_hand_front`, ..., plus
`rotating_no_pinch` on its own): **3 classes × 3 orientations = 9 labels**,
`rotating_no_pinch` recorded separately = 10 labels total, ≥2–3 sessions
each per §3 stage 1.

**Recording protocol detail**: record both hands performing the *same*
class/orientation simultaneously per session, so every hand-frame in a
given file is unambiguously the session's label — don't have one hand
pinching while the other rests, that reintroduces the per-frame-ambiguity
problem §3 stage 1 exists to eliminate.

**Second recording type (for the event layer, §3.3 — cyclic/transition
sessions, not classifier training data):**
- `pinch_cycles`: neutral → pinch → release, repeated ~3 times per session,
  **slow and deliberate** (learned the hard way not to rush this — see
  Stage 1's note and `PART_ONE.md` §7.2), recorded at `front` orientation
  at minimum; add `palmup`/`palmaway` variants if the event layer's timing
  behavior turns out to be orientation-sensitive (check empirically, don't
  assume either way).
- These are what actually validates onset/offset detection — the held
  `pinch_*` sessions above never contain a real transition to tune against.

## 6. What MediaPipe's own Gesture Recognizer actually does (researched 2026-07-30)

Researched directly in response to two questions: does MediaPipe use
derivative/time-based features, and if it does, how — and separately, how
does MediaPipe itself solve the same-model-different-platform problem this
project will eventually face (Local_pc → Web, §7 below). Sourced from
MediaPipe's own docs/API reference and source, not third-party summaries
alone.

### 6.1 Temporal/derivative features — MediaPipe does NOT use them

- MediaPipe's `GestureRecognizer` task classifies **one frame/image at a
  time** — no velocity, rate-of-change, or sliding-window feature anywhere
  in its architecture or its training data. Model Maker's custom-gesture
  training explicitly takes **labeled still images** in folders, one
  gesture per image — not video/session sequences.
- Architecture: `HandLandmarker` → 21 landmarks → a **gesture embedding
  model** (Fully Connected Neural Network with residual blocks) taking the
  landmarks as a flat **1×63 tensor** (21 landmarks × x,y,z, normalized by
  image size) → a **128-dimensional embedding** → a small **classification
  head** (FC network) → per-class probabilities. Custom training (Model
  Maker) only retrains the classification head via transfer learning
  (embedding model stays frozen) — split 80% train / 10% validation / 10%
  test.
- **Direct answer**: no, MediaPipe's own gesture classifier is static/
  per-frame, not derivative-based. This is real precedent for §3 stage 3's
  static-classifier-first default, and for *not* reaching back for the
  velocity-window approach this project already tried and found
  insufficient (§1) — MediaPipe's own production system, running
  real-time on-device, doesn't need it for this class of problem.
- One adjacent, non-MediaPipe finding worth knowing: some third-party work
  normalizes each frame relative to the **wrist position from the first
  frame of the gesture** (not the current frame) as a lightweight way to
  add temporal context without a full derivative — ~1 point of accuracy
  difference vs. per-current-frame normalization in one cited study. Not
  adopted here, just worth knowing if a static classifier ever proves
  borderline for a future gesture.

### 6.2 Feature input — MediaPipe uses raw landmark coordinates, not hand-crafted features

- MediaPipe's embedding model takes **raw normalized landmark coordinates
  directly** (the flat 63-value vector) — it does **not** compute
  hand-crafted geometric features (no distance ratios, no joint-curl
  angles) before feeding the network. The embedding network learns
  whatever internal representation turns out to be discriminative.
- **This is a real alternative for this project's stage 3**, not just the
  hand-picked-ratio/curl-angle approach the abandoned rule-based
  classifier used: feed a small model raw (hand-relative) `world_landmarks`
  coordinates directly, and let training find the structure, rather than
  assuming which hand-crafted ratios/angles matter. A hand-crafted feature
  is a manual projection of the geometry that can discard exactly the
  signal needed — arguably part of why the rotation problem was so
  stubborn: the chosen ratio+curl features may simply not have captured
  what actually distinguishes a genuine pinch from a rotation-induced false
  one.
- **Stage 3 should empirically compare both** — raw landmark coordinates
  vs. hand-crafted features (or a mix) as classifier input — rather than
  assuming either is correct. Choosing a model's *input representation*
  based on literature precedent and held-out validation accuracy is normal
  ML practice, not a contradiction of §2's "no heuristic pile-up" rule
  (that rule is about patching a trained classifier's *output* with
  special cases, not about how the input features are chosen).

## 7. Cross-platform portability (Local PC → Web) — plan, and how it compares to MediaPipe's own approach

Researched directly in response to: build with the eventual Local_pc →
Web port in mind from the start, and check how MediaPipe itself handles
the same-model-different-platform problem.

### 7.1 How MediaPipe does it

- Train once → convert to an optimized **TensorFlow Lite (`.tflite`)**
  model → bundle it (with metadata/labels) into a cross-platform **`.task`
  file**. Every platform — Python, Web/JavaScript (via WASM), Android,
  iOS — loads and runs **the identical `.task` file** through a native
  TFLite inference runtime, behind each platform's thin MediaPipe Tasks
  API wrapper. The trained weights and architecture never change per
  platform; only the surrounding runtime/API glue does.
- This project already relies on exactly this mechanism one layer down:
  `Web/scripts/copy-mediapipe-assets.mjs` copies the same
  `hand_landmarker.task` file both the Python server and the browser page
  use, unmodified (`PART_ZERO_BIS.md`). One binary artifact, same bytes,
  every platform — what MediaPipe does for its own gesture classifier too,
  just for a bigger model than this project's will be.

### 7.2 Why this project's classifier can reasonably do it differently

- MediaPipe's embedding network (FC + residual blocks, 128-dim) is
  nontrivial enough to justify a real cross-platform inference runtime
  (TFLite/WASM) — hand-reimplementing it correctly in a second language
  would be error-prone and hard to verify.
- This project's classifier (logistic regression, or a tiny 2-layer MLP
  per §3 stage 3) is dramatically smaller — a handful of weights,
  computable as one or two matrix-vector products plus an activation
  function. A **hand-rolled forward pass**, written once in Python and
  once in JS, is small enough to write, read, and verify by eye in both
  languages — no WASM build step, no inference-runtime dependency, no risk
  of a framework-version mismatch between the two sides. This is exactly
  what Specification.md §7.1 already specifies (flat JSON weight arrays, a
  hand-rolled forward pass) — this research confirms it's a deliberate,
  justified choice given this project's model scale, not a shortcut taken
  in ignorance of how MediaPipe does it at theirs.

### 7.3 Concrete portability discipline (apply from the start, not bolted on later)

- **Feature-extraction math must be trivially 1:1 portable.** Simple
  arithmetic (distances, dot products, basic trig) only — no
  Python-specific idioms without an obvious JS equivalent (no numpy
  broadcasting tricks, no comprehension-heavy one-liners that hide the
  actual computation). Specification.md §7.1 already requires this; the
  reason is that MediaPipe's portability rests on the *model* being
  platform-agnostic, while ours rests on the *code* being trivially
  re-expressible — so the code has to actually stay simple.
- **Trained weights are exported once, as flat JSON arrays**, and both the
  Python and (later) JS forward-pass implementations load the *same*
  file — never independently retrained or hand-copied constants on each
  side, which would let the two silently drift apart.
- **A parity test is required once the JS port exists** (Specification.md
  §7.3, restated here since it's directly a portability discipline): run
  the same recorded/labeled test sessions through both the Python and JS
  forward-pass implementations and assert numerically equal outputs. This
  is how this project gets MediaPipe's "same model runs identically
  everywhere" guarantee, just via a verified-identical hand-rolled
  implementation instead of a shared runtime.
- **Camera-frame independence stays a hard requirement** (§1's original
  reasoning, unchanged): classification runs on `world_landmarks` (or
  another hand-relative, resolution/pose-independent representation — see
  §6.2), never on pixels or a browser's raw video-frame dimensions, so the
  same trained weights work whether the input came from the Python
  server's webcam loop or the browser's `HandLandmarker` — no separate
  calibration per platform.

## 8. Open questions for whoever picks this up next

- Confirm or adjust §5's taxonomy before recording anything.
- Logistic regression vs. small MLP: decide empirically once training data
  exists, starting with logistic regression per §3 stage 3's "simpler
  baseline first" rule.
- **Raw landmark coordinates vs. hand-crafted features as model input**
  (§6.2): compare both empirically once training data exists, rather than
  assuming the hand-crafted approach from the abandoned rule-based
  classifier is the right input representation.
- Exact session count per class×orientation cell: start at 2–3, add more
  only if held-out test performance says so — don't over-record
  speculatively.
- **Event layer (§3.3) specifics, all to decide empirically against the
  `pinch_cycles` recordings, not guess**: window size for the derivative
  computation; which signals besides the confidence score itself to check
  for derivative agreement (the raw thumb-index distance is the obvious
  first candidate, per §3.3); the actual agreement threshold; whether
  orientation affects the event layer's behavior enough to need its own
  `pinch_cycles` variants beyond `front`.
