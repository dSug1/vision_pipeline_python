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
- **Orientation is a first-class recorded dimension, not an afterthought —
  across a 6-cell grid, not 3.** Every held-state class (positive and
  negative) gets recorded across the full canonical orientation grid: the
  3 axes a palm normal can point along, each in both directions —
  `front`/`palm_away` (toward/away from camera), `palm_up`/`palm_down`, and
  `palm_in`/`palm_out` (toward/away from the body's midline — see §5 for
  the exact definitions and why `palm_away` may show degraded tracking
  confidence). This is a direct response to §1's finding, not a hedge — and
  it's no longer just about the *positive* pinch class: §3.3.1 below found a
  concrete second reason orientation coverage matters specifically for
  **release** (offset), not only pinch (onset).
- **The cyclic/transition sessions need the same full orientation coverage
  as the held-state classes, and for a concrete reason beyond symmetry with
  the rule above**: pinch (grab) mostly happens at or near `front` in
  practice, but **release doesn't** — if the point of grabbing an object is
  to rotate it, the hand (and therefore its orientation) has typically
  moved well away from `front` by the time release happens. A `pinch_cycles`
  session recorded only at `front` validates offset detection at the one
  orientation it's least likely to matter in practice. See §5 for the
  resulting taxonomy change (`pinch_cycles` now spans the full orientation
  grid, plus a new `pinch_rotate_release` session type that grabs at
  `front` and releases mid-rotation, matching the actual use pattern
  instead of only the fixed-orientation cyclic pattern).
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
- **Recordings are stored on the external drive, not the local disk**
  (`E:\Python\Recordings for vision_pipeline`, changed 2026-07-31 to avoid
  the raw-capture corpus growing on the PC — both `RecordSession.py`'s
  `RECORDINGS_DIR` and `train_pinch_classifier.py`'s `RECORDINGS_DIR` point
  there; keep the two in sync if this ever moves again). Not
  git-tracked either way (raw capture data, not source) — this just moves
  where "not tracked" physically lives.

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

### 3.2.1 Stage 3 results, pinch base classifier (2026-07-30)

Trained against the full Stage 1 corpus (53 sessions / 4,566 frames — see
§5's taxonomy): `pinch`/`open_hand`/`fist`/`rotating_no_pinch` held-state
sessions only (`pinch_cycles_*` and `pinch_rotate_release` excluded, per
stage 1's rule that they're event-layer data, never classifier training
data). Session-level split: last recorded session per (class, orientation)
cell → test, the rest → train — 19 cells, 18 held out as test (one,
`fist_palmout`, had only 1 clean session — see the recording handoff notes
— so it contributes to train only). 2,281 train / 2,216 test hand-frame
examples. Code: `train_pinch_classifier.py` +
`Resources/features.py` (both new).

**Compared 2 architectures × 2 input representations, exactly as §6.2
calls for** — plain-numpy logistic regression and a small hand-rolled
2-layer MLP (tanh hidden layer, sigmoid output — Specification.md §7.1's
"few thousand params, re-implementable as a forward pass in JS" budget),
each against both hand-crafted features (7-dim: `pinch_ratio` +
5 curl angles + `curl_worst_deg`) and raw landmark coordinates (63-dim,
wrist-relative and hand-size-normalized). Held-out test F1:

| Architecture / representation | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| **MLP / raw landmarks (winner)** | 0.907 | 0.851 | 0.864 | **0.857** |
| Logistic regression / raw landmarks | 0.815 | 0.752 | 0.640 | 0.692 |
| MLP / hand-crafted features | 0.778 | 0.674 | 0.610 | 0.640 |
| Logistic regression / hand-crafted features | 0.768 | 0.681 | 0.537 | 0.601 |

- **Raw landmarks beat hand-crafted features on both architectures** —
  confirms §6.2's hypothesis was worth testing rather than assuming: the
  hand-picked ratio/curl-angle features apparently discard some of the
  signal that actually separates pinch from the confusable classes across
  a full 6-orientation grid, the same concern §6.2 raised about the
  abandoned rule-based classifier.
- **Logistic regression measurably underperformed** (F1 ≤ 0.692 both
  representations) — triggered stage 3's documented escalation to a small
  MLP, not a default reach. The MLP was **not** run at its first-tried size
  (`hidden_units=12`): that config hit F1=0.758 on test but 0.989 on train,
  a severe generalization gap given how few independent sessions this
  dataset has (19 cells, most 2 sessions each). A small hyperparameter
  sweep (`hidden_units` × `l2`, held-out-test-scored, not guessed) found
  `hidden_units=4, l2=0.001` generalized far better (train F1 0.973 vs test
  0.857 — still some gap, but much smaller).
- **Honest caveat: seed sensitivity.** Retraining the winning config
  (`hidden_units=4, l2=0.001`) across 6 random-init seeds produced test F1
  between 0.737 and 0.859 — a real ~0.12 spread, not noise-free. The
  exported model uses `seed=0` (deterministic, reproducible) which happened
  to land near the top of that range, not the average. This is itself a
  finding, not just a caveat: it's a direct symptom of the dataset still
  being small relative to a 63-input model, consistent with the plan to
  keep growing the Stage 1 corpus (§8's open items) rather than reading
  0.857 as a settled number.
- **Two concrete, orientation-specific failure modes found, both on the
  Right hand** — exactly the kind of measured detail §2's "no heuristic
  pile-up" discipline asks for instead of a vague "needs more data":
  `open_hand_palmup` (Right) is misclassified as pinch on 60/60 test frames
  (28/60 on Left); `pinch_palmout` (Right) is misclassified as *not* pinch
  on 59/60 test frames (21/60 on Left). Both cells already have clean
  recordings in the train set (this isn't a missing-orientation gap), so
  the fix per §2 is **more sessions for these two specific cells**, not a
  patch on the classifier's output — flagged as an open item (§8) rather
  than acted on now, since two mispredicted cells out of 19 on a first
  pass is a reasonable place to checkpoint, not a blocker.
- **Exported**: `Resources/pinch_classifier_weights.json` (flat JSON —
  `architecture`, `representation`, `mean`/`std` standardization params,
  `W1`/`b1`/`W2`/`b2`) — portable per Specification.md §7.1, ready for a
  hand-rolled JS forward-pass port later without retraining.

#### Re-run (2026-07-31): after adding a second, farther-camera-distance corpus — a regression, not an improvement

Per §3.2.2 below, 55 more sessions were recorded (full taxonomy again, all 6
orientations, all classes — not just `pinch`) with the camera moved farther
from the hands, then the classifier was retrained on the combined 108-session
corpus (53 near + 55 far). **This made held-out test performance worse, not
better** — reported here in full per §3.2.2's own rule not to silently
overwrite prior numbers.

| Architecture / representation | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| **MLP / hand-crafted features (new winner)** | 0.809 | 0.767 | 0.516 | **0.617** |
| Logistic regression / hand-crafted features | 0.814 | 0.825 | 0.479 | 0.606 |
| MLP / raw landmarks (previous winner, was 0.857) | 0.760 | 0.648 | 0.426 | 0.514 |
| Logistic regression / raw landmarks | 0.703 | 0.507 | 0.213 | 0.300 |

- **The representation ranking flipped.** Raw landmarks beat hand-crafted
  features in the near-only corpus (§3.2.1's original table); with the far
  corpus added, hand-crafted features now win, and raw landmarks took by far
  the bigger hit (0.857 → 0.514, a ~40% relative drop) versus hand-crafted's
  milder one (0.657 → 0.617, roughly stable). Since the session-level split
  always holds out the *most recently recorded* session per cell as test,
  and the far-distance sessions were recorded most recently, **every test
  session this run is a far-distance session** — this is measuring
  generalization from a near+far training mix to unseen far-distance data
  specifically, not a random mix.
- **Root cause, measured, not guessed**: compared `hand_size_ref` (the
  wrist-to-middle-MCP distance `features.py` uses to normalize everything)
  between near and far `open_hand_front` recordings. The mean stayed close
  (0.092 vs 0.098 — MediaPipe's metric world-landmark scale does hold up
  reasonably well across distance, as it should) but **the standard
  deviation nearly tripled** (0.0023 near vs 0.0062 far). This is the
  expected signature of a real, literature-consistent effect: a hand
  occupying fewer pixels gives MediaPipe less information to localize each
  landmark precisely, so per-frame landmark noise increases with distance,
  even though the underlying detection still works (§3.2.1's original
  smoke test confirmed high detection confidence at the new distance —
  confidence and precision are different things).
- **Why this explains the representation flip**: raw landmark coordinates
  feed all 21 points' noisy `x,y,z` directly into the model (63 independent
  noisy values); hand-crafted features are ratios and angles computed
  *across* multiple points, which partially averages out independent
  per-point noise the same way averaging any noisy measurements reduces
  variance. Raw landmarks had no such averaging to fall back on, so the
  added noise from far-distance sessions hit that representation much
  harder — consistent with, not contradicting, §6.2's original motivation
  for testing raw landmarks in the first place (MediaPipe's own embedding
  network does use raw landmarks, but it's trained on vastly more data than
  this project's corpus, which is exactly the condition under which
  hand-crafted features' built-in noise-averaging matters more).
- **Checked against state-of-the-art literature (2026-07-31) — not a
  project-specific singularity, this is the expected, documented behavior**,
  on two independent fronts:
  - **General ML: hand-crafted features are the known-better choice for
    small models on small/noisy datasets.** "Hand-crafted features
    outperform CNNs for smaller sample sizes," and critically, research
    comparing hand-designed features against raw input found *no*
    improvement from hand-designed features when the model was large, but
    **small models specifically benefit from hand-designed input** —
    exactly this project's regime (`TinyMLP`, a few thousand params, per
    Specification.md §7.1's deliberate size budget). The mechanism cited:
    raw input has a lower signal-to-noise ratio, and "training data with
    high noise levels can cause models to erroneously learn noise
    patterns," which takes a much larger training set to overcome than
    this project's 108 sessions provide.
  - **Pose-estimation literature: geometric features (joint angles,
    inter-point ratios) are specifically documented as robust to camera
    distance/viewing-angle changes, unlike raw coordinates.** Found
    directly on point: "joint angles offer increased robustness to global
    jitter, minor translation noise, and scaling inconsistencies compared
    to raw coordinates, because they are derived from relative geometric
    relationships between neighboring keypoints rather than relying on
    absolute positional coordinates," and this specifically "solves the
    issue of inter-frame inconsistency... aris[ing] from changes in
    shooting distance and viewing angle" — a near-exact description of
    what this project just measured, not an analogy. The general
    statistical mechanism (averaging/combining multiple noisy measurements
    reduces variance versus using one raw measurement) is standard signal
    processing, not specific to this domain.
  - **Also consistent with this project's own earlier, independently-made
    observation**: `PART_ONE.md` §2 already flagged MediaPipe's `z`
    coordinate as "the least reliable of the three coordinates
    monocularly," before this experiment was ever run — raw landmarks
    include `z` directly (21 of 63 values), hand-crafted features only use
    it indirectly through already-noisy-averaging distance/angle
    computations. A GitHub-documented MediaPipe issue and a hand-tracking
    validation paper both confirm single-view depth estimation is a known
    weak point, generally, not specific to this project's data.
  - **Conclusion**: the `hand_size_ref` variance measurement (one cell) is
    still just one data point, but the *direction* of the effect — raw
    landmarks degrading more than hand-crafted features under added
    distance-related noise, for a small model on a small dataset — is
    exactly what independent literature predicts, from two unrelated
    fields (general ML small-data practice, and pose-estimation-specific
    geometric-feature robustness). This changes the earlier "hypothesis,
    not proven" framing: it's now a **literature-confirmed expectation**,
    not a coincidence needing more internal verification before acting on
    it.
- **Decided, not just flagged**: hand-crafted features become this
  project's **default** representation going forward, not merely "whichever
  wins a given retrain." §3 stage 3's instruction to empirically compare
  representations each time a gesture is built is still followed (checking
  is cheap and this project's own §2 discipline requires it), but the prior
  expectation should now be that hand-crafted features win under small/noisy
  data, with raw landmarks only worth reaching for once the corpus is large
  enough to approach the regime real embedding-network approaches
  (MediaPipe's own gesture classifier, §6.2) are trained on. Growing the
  corpus (more far-distance sessions, more of the originally-flagged weak
  cells) remains worthwhile regardless — it's what would eventually let raw
  landmarks close the gap, if that's ever wanted — but isn't required to
  keep building on top of the current hand-crafted-features classifier.

### 3.2.2 Adding more recordings later and retraining (a repeatable workflow)

Accuracy here is not a one-shot number — §3.2.1 already flagged two weak
cells (`open_hand_palmup` and `pinch_palmout`, both Right hand) and a
seed-sensitivity symptom that more data should shrink. This is how to feed
new recordings back in whenever that happens, for pinch or any future
gesture built under this same pipeline.

- **Always retrain from scratch on the full combined corpus — never
  incremental/warm-start fine-tuning from the saved weights file.** Two
  reasons, not just convention: (1) a full retrain is cheap at this dataset
  size (`train_pinch_classifier.py` runs in seconds), so there's no
  performance reason to reach for incremental training's extra complexity;
  (2) fine-tuning only on new sessions risks the model drifting to fit just
  those sessions (a small-scale version of catastrophic forgetting) while
  discarding what the original sessions taught it — and the session-level
  train/test split (§3 stage 3's "hold out whole sessions" rule) has to be
  recomputed anyway, since which session is "last" per (class, orientation)
  cell — the one held out as test — changes as new sessions are added.
  Retraining from the combined raw recordings keeps every reported metric
  traceable to one real training run over one real dataset, not a chain of
  partial updates that's hard to audit later (Specification.md §7.1/§7.3's
  portability-and-auditability discipline, applied here to training
  itself, not just to the exported weights format).
- **Steps**:
  1. Record new sessions exactly as in Stage 1 (`record.bat <label>
     [duration]` — label must be an exact string from §5's taxonomy, or a
     deliberate extension of it, see below). Sanity-check each new
     recording's both-hands-detected frame count the same way the original
     Stage 1 pass did (load the JSON, count `len(frame["hands"])==2` per
     frame) before trusting it — delete and redo anything meaningfully
     below full coverage, the same QA bar used throughout Stage 1.
  2. New JSON files land in `E:\Python\Recordings for vision_pipeline` —
     `RecordSession.py` already saves there by default, no extra step
     needed. Not source-controlled either way; nothing here is tracked
     except the code and the exported weights.
  3. **If the new sessions are just additional reps for an existing
     (class, orientation) cell** (e.g. topping up `open_hand_palmup` or
     `pinch_palmout` per §8's flagged weak cells): re-run
     `train_pinch_classifier.py` with no code changes. It auto-discovers
     every file in that folder, so the session-level split and both
     architecture/representation comparisons automatically pick up the new
     data.
  4. **If adding an entirely new cell** (a class or orientation not
     currently in §5 — e.g. a 7th orientation, or a new negative class):
     extend `classify_label()` / `BASE_CLASS_PREFIXES` in
     `train_pinch_classifier.py` to recognize the new label, **and** update
     §5's taxonomy table and session-label list here so the recorded data
     and the code stay in lockstep — don't let a label exist in one place
     and not the other.
  5. **Update this section (§3.2.1) with the new run's results, don't
     silently overwrite the old numbers** — note what changed (which cells
     got more data) and whether the flagged weak cells actually improved.
     If they did, that confirms more data was the right fix; if they
     didn't, that's itself informative — it points at the feature
     representation or model choice rather than data volume, and is a
     reason to revisit §6.2's comparison rather than keep adding recordings
     to the same cells.
  6. **Because of the seed-sensitivity finding, judge a single retrain's
     test F1 skeptically** — a ~0.12 spread was measured across 6 seeds on
     the current dataset. To confidently confirm an improvement (not just a
     lucky seed), retrain the changed config across a handful of seeds (the
     same sweep pattern used to pick `hidden_units`/`l2` in §3.2.1) and
     compare the distributions, not single point estimates.
- **What not to do**: don't hand-edit `Resources/pinch_classifier_weights.json`
  directly, and don't average or merge two independently-trained weight
  files — always regenerate weights by retraining
  `train_pinch_classifier.py` against the combined raw recordings, so the
  exported file is always the direct, reproducible output of one training
  run over an inspectable dataset, not a hand-patched artifact.

### 3.2.3 Stage 3 redesign (2026-07-31): windowed/derivative features — literature-grounded, but an honest non-fix

Triggered by a direct question: given §3.3.2 found the base classifier
spikes to near-1.0 confidence during pure rotation (no pinching), is this
solvable at all by a trained model, and if so, how — bigger model, or
different input?

**Literature check, done before writing any code** (per §2's discipline):
two independent bodies of research say the same thing. Gesture-recognition
literature: "dynamic gestures that pass through similar static poses can
convey different meanings — clockwise and counterclockwise circular
motions share similar intermediate poses, but their temporal order
distinguishes their respective meanings" — a near-exact description of
this project's rotation/pinch confusion, and proof by example that no
amount of single-frame model capacity can disambiguate two inputs whose
disambiguating information (direction of change) isn't present in one
frame. Biological-motion-perception literature: humans attribute intention
specifically from **motion cues, not static snapshots** — demonstrated with
point-light displays stripped of all static visual information, where
people still perceive intention, driven by a dedicated brain system (the
superior temporal sulcus) for motion-over-time processing. Both point the
same direction: **the fix is temporal input, not a bigger single-frame
model** — consistent with (not contradicting) the project's small-model
portability budget (Specification.md §7.1), since literature also reports
"properly designed small models can achieve competitive results" with
windowed/temporal input specifically.

**Window size, measured not guessed**: `analyze_transition_window.py`
detects real open↔pinch cycles in the `pinch_cycles` recordings (via
`scipy.signal.find_peaks` on `pinch_ratio`, prominence=0.2 — chosen
empirically to match ~6 extrema/session = 3 cycles, per the "repeated ~3
times" recording protocol) and measures how long each transition actually
takes, converting frames to real time via each session's own measured fps
(frame count ÷ known `--duration`, since capture fps varies with hardware
load — ~15fps near-distance vs ~27fps far-distance, not a fixed 30fps).
Results: onset (open→pinch) median 667-967ms depending on distance, offset
(pinch→open) median 724-733ms, p25 220-440ms across both. **Window chosen:
300ms** — near the p25 mark, short enough to trigger before a slow
transition fully completes, long enough to carry signal above frame-to-
frame noise. `RecordSession.py` now stores `duration_s` in every new
recording so this stops depending on hardcoded label-based duration
assumptions (`train_pinch_classifier.py`'s `session_duration_s()` falls
back to a lookup table only for recordings made before this change).

**Implementation**: `features.py` gained `extract_delta_features()` (a
pure function over two landmark snapshots — Δ`pinch_ratio` and
Δ`curl_worst_deg`) and windowed variants of both representations
(`extract_handcrafted_windowed_features()` → 9 values,
`extract_raw_windowed_features()` → 65 values).
`train_pinch_classifier.py` was reworked to build examples per-hand in
strict temporal order (not shuffled single frames) and pair each frame
with one ~300ms earlier, skipping each hand's warm-up period before a full
window exists.

**Honest result: this did not fix the target problem.** Measured the same
rotation stress test (percent of frames with confidence >0.5 during pure
`rotating_no_pinch`, averaged across all 5 sessions / 10 hand-sequences —
not just the one held-out test session, since that would only sample a
fraction of the negative data):

| Model | Rotation false-positive rate |
|---|---|
| Non-windowed hand-crafted (§3.2.1 baseline, re-measured on the same full 10-sequence set for a fair comparison) | 27.2% |
| **Windowed hand-crafted** | **26.9%** — a negligible change |
| Windowed raw landmarks | 31.3% — worse |

Two delta features carried essentially no rotation-robustness benefit.
**This is consistent with, not contradicted by, this project's own prior
history**: the abandoned rule-based classifier's closing-velocity approach
(`PART_ONE.md` §7.2) also only partially helped (62.2%→22.2% false
positives on its own rotation test) and was explicitly diagnosed as
limited because "the two classes overlap in timing because the training
data doesn't have a clean timing signature to key off of, not because the
velocity approach is wrong." The same limitation plausibly applies here: a
real 3D hand rotation moves many geometric relationships at once, so
`pinch_ratio` and `curl_worst_deg` can both shift in a pinch-like direction
during incidental rotation too, not just during a genuine pinch — the 2
chosen delta signals may simply not carry exclusive information, not that
windowing-in-general is the wrong idea.

**A real bug found and fixed along the way, worth keeping as a permanent
guard**: naively selecting the "best" model by rotation false-positive rate
alone picked `logreg/raw_landmarks` — which achieved the *lowest* rotation
FP (18.9%) by being nearly degenerate (recall 0.250, missing 3 of 4 real
pinches) — a model that rarely predicts "pinch" at all trivially avoids
false positives everywhere, including during rotation. `train_pinch_classifier.py`
now gates on `MIN_RECALL = 0.4` before considering rotation robustness, and
runs the full rotation stress test (not just the held-out test session, which
under-samples `rotating_no_pinch`) as a standard part of every training
run, printed alongside F1 for every architecture/representation
combination. Current winner under this corrected selection:
**`logreg/handcrafted`** (rotation FP 22.0%, test F1 0.605, recall 0.479) —
notably not the MLP this time, and not raw landmarks; still hand-crafted,
consistent with §8's decided default.

**Kept, not reverted**: the windowed-feature infrastructure
(`extract_delta_features`, the windowed extraction functions, the
per-session-fps-aware windowing in `train_pinch_classifier.py`,
`analyze_transition_window.py`, the rotation stress test now built into
every training run) — the design is literature-grounded and technically
sound, the *specific 2 signals chosen* just didn't carry enough exclusive
information for this problem. Worth revisiting with different/more delta
signals before concluding the approach itself is wrong (see §8).

### 3.2.4 Follow-up (2026-07-31): more rotation data + a prediction-error feature — real progress, from an unexpected lever

Two follow-ups after §3.2.3's non-fix, both requested directly: (1) record
more `rotating_no_pinch` data (the cheapest lever per §2, and §3.2.3's own
"next steps"), (2) check whether literature on brain-inspired intention
detection suggests a fundamentally different feature, and build it if so.

**Corpus growth**: 4 new `rotating_no_pinch` sessions recorded (9 total, up
from 5), deliberately varied — slow deliberate rotation, fast rapid
wrist-twisting, small quick twitches (mimicking incidental fidgeting), and
rotation while translating the hand through space (not just twisting in
place). All clean (100% both-hands detected). `RecordSession.py`'s new
`duration_s` field (added in §3.2.3) confirmed working on these.

**Literature check on "mimicking the brain," done before writing code**:
found a mechanistically different, well-established computational pattern.
Neuroscience literature on voluntary-action-onset detection: prediction
error is described as "a sudden violation of predicted" trajectory, and
this is literally how the brain is modeled to flag a voluntary movement
against a backdrop of continuous motion — via **forward models / efference
copy** (the brain predicts the sensory consequences of ongoing motion; a
genuine new action produces a prediction-error spike where continuing the
same motion wouldn't). The computational analog for *observing* motion
(not just self-generated) is **predictive coding** — literature describes
biological-motion perception itself as predictive ("self-knowledge is
utilized to recognize similar motion patterns and predict their
progress"), and the equivalent engineering pattern is well-established:
**PredNet**-style next-frame-prediction networks, where "anomaly detection
is triggered by deviations between actual and predicted behavior," and
critically, "predictive coding networks using **smaller** neural
architectures can effectively identify when actual pose deviates from
predicted pose." This is a different mechanism from §3.2.3's plain
velocity delta (a first-order "did the value change" signal) — prediction
error is second-order ("did the *trend* change"), which matters because
smooth continuous rotation has nonzero velocity throughout but should have
*near-zero prediction error*, since a simple extrapolation of "keep doing
what you were doing" tracks it well; a genuine pinch onset breaks from
whatever trajectory preceded it.

**Built**: `features.py` gained `extract_prediction_error_features()` — a
pure function over three landmark snapshots (t-2W, t-1W, now), computing a
constant-velocity extrapolation from the two past points and returning the
signed residual (actual − predicted) for `pinch_ratio` and
`curl_worst_deg`. `extract_handcrafted_full_features()` combines static +
velocity-delta + prediction-error (11 values). `train_pinch_classifier.py`
was generalized to compare 5 named representations
(`handcrafted_static`/`velocity`/`prederror`/`full`/`raw_landmarks`) on
**identical example sets** (all anchored at the same (t-2W, t-1W, now)
triples), so the comparison isolates which *features* help, not which
examples got used.

**Result — real progress, but from the data, not (visibly) from the new
feature**: rotation false-positive rate dropped substantially across
**every** representation tested, including static-only and plain-velocity
variants that don't touch prediction-error at all — from the §3.2.3
baseline of ~22-31% down to 8-17% depending on representation. This
strongly indicates **the corpus growth (5→9 sessions, deliberately varied
speed/path) was the dominant driver**, consistent with §2's "more/better
data" being the default fix, more clearly here than the feature-engineering
attempt demonstrated. The prediction-error features' own isolated
contribution is hard to see in this pass: `handcrafted_full` (velocity +
prederror) got the single best rotation FP among hand-crafted variants for
logistic regression (9.3%), but at recall 0.230 — too confounded with a
recall collapse to call it a clean win for the new feature specifically.

**A precision/recall shift surfaced, not yet resolved**: with 9
`rotating_no_pinch` sessions now in the corpus, every hand-crafted-family
model's recall dropped below the `MIN_RECALL=0.4` eligibility gate
(§3.2.3) — only `mlp/raw_landmarks` (recall 0.594, rotation FP 14.7%, F1
0.654) cleared it, and became the winner. This is a real, measured
best-yet result (previous best rotation FP was 22.0%), but it means the
current winner is raw landmarks again, not hand-crafted — **not a reversal
of §8's literature-grounded default**, just what the eligibility gate found
this specific run; re-check whenever the corpus changes again, per that
same section's own rule. The recall collapse across hand-crafted variants
is itself worth investigating before the next retrain — plausibly the
growing negative-class volume is shifting the decision boundary more than
intended, which class-weighting during training (not yet tried) could
address directly, rather than something to fix by further feature changes.

### 3.2.5 Follow-up (2026-07-31): class-weighted training tried — measured, and rejected

Triggered directly by §3.2.4/§8's top-priority item: is the recall collapse
across hand-crafted representations (every hand-crafted variant dropping
below `MIN_RECALL=0.4` once `rotating_no_pinch` grew to 9 sessions) a
training-procedure problem — fixable by reweighting the loss for class
imbalance — rather than a feature or architecture one?

**Built**: `sample_weights()` in `train_pinch_classifier.py`, sklearn-style
balanced inverse-frequency weighting (`n / (2 * n_class)`), plumbed into
both `LogisticRegression.fit` and `TinyMLP.fit` as an optional
`class_weight="balanced"` argument. Ran every representation × architecture
combination twice — unweighted (existing) and balanced (new) — so the
comparison was measured against the same data/split, not assumed.

**Result: balanced weighting fixes recall, but at a cost that makes it a
strictly worse choice for this project's actual priority.** Hand-crafted
recall did recover (from ~0.2–0.29 unweighted up to 0.7–0.86 balanced —
exactly the intended effect). But rotation false-positive rate got
dramatically worse across every balanced variant: 9–17% unweighted →
35–53% balanced. `mlp_bal/handcrafted_prederror` had the best test F1 of
any run so far (0.807, recall 0.814) but a 50.4% rotation false-positive
rate — worse than even the original abandoned rule-based classifier's
38.5% (§1).

**Why, mechanistically**: class weighting doesn't add information that
separates genuine pinch from rotation-induced false pinch-like poses — it
just reweights the loss to penalize missing the (now-underrepresented)
positive class more, which shifts the decision threshold toward predicting
"pinch" more often globally. That recovers true positives and false
positives together, indiscriminately — including during
`rotating_no_pinch`, which is exactly the failure mode this project has
been trying to suppress since §1. This is the same lesson §3.2.3 already
drew from a different angle (a model that trivially avoids rotation false
positives by rarely predicting pinch at all isn't a real fix either) — here
it's the mirror case: a model tuned to *never* miss a real pinch isn't a
real fix either, if it does so by predicting pinch more often everywhere.

**Decided**: the `_bal` variants are not part of the default sweep in
`main()` — a measured, strictly worse operating point for this project's
current priority doesn't need to run on every future retrain. The
`class_weight` capability (`sample_weights()`, the `fit()` parameter) is
kept, not deleted, in case a smarter weighting scheme is worth trying later
(e.g. weighting `rotating_no_pinch` specifically rather than "all negative
classes," which plain balanced weighting can't express) — but that would be
a new, separately-justified idea, not a re-run of what was just measured
here.

**This closes §8/§4's "try class-weighted training" item as tried and
rejected, not as still-open.** Per §9.1's own next step, the priority queue
reverts to §9.2's data-recording loop (more `rotating_no_pinch` variety
first) as the more promising lever, consistent with §3.2.4's own finding
that corpus growth — not any feature or training-procedure change tried so
far — has been the dominant driver of every real rotation-robustness
improvement to date.

### 3.2.6 Follow-up (2026-07-31): 11-session retrain, then a prediction-error window-size sweep — window size ruled out as the cause of the recall collapse

Two rounds, both per §9.1's loop.

**Retrain, 9→11 `rotating_no_pinch` sessions** (2 new: a large-amplitude
circular/orbital rotation path, and rapid direction-reversal wrist
twisting — both clean, 100% both-hands-detected). Rotation FP 14.7% →
**13.2%**, a ~1.5-point gain — below §9.3's 2-3-point diminishing-returns
bar for this specific lever (more `rotating_no_pinch` variety). Recall also
dipped slightly, 0.594 → 0.540. Winner unchanged: `mlp/raw_landmarks`.

**Prediction-error window-size sweep** (`sweep_prediction_error_window.py`,
new): triggered by a direct question — §3.2.4 built the prediction-error
features at a single fixed 300ms window, but that number came from
`analyze_transition_window.py`'s measurement of real onset/offset
*transition timing*, never validated against classifier performance
directly. Swept window size (100/150/200/300/450/600/900/1200ms) ×
representation (`handcrafted_velocity`/`handcrafted_prederror`/
`handcrafted_full`) × architecture (logreg/MLP) = 48 runs, same held-out
session-level split and same two metrics (test recall/F1, rotation stress
test) `train_pinch_classifier.py` already selects on.

**Result: no window size fixes it — this rules out window mis-tuning as
the cause of the recall collapse, it does not just confirm 300ms was fine.**
Across the entire 100–1200ms range, every window-dependent hand-crafted
representation stayed at recall 0.11–0.28 — never approaching the
`MIN_RECALL=0.4` gate, let alone the raw-landmarks winner's 0.540. Rotation
FP looked good in isolation (as low as 1.5% at 1200ms) but precision was
simultaneously near-perfect everywhere (0.94–1.0) — exactly the degenerate,
overly-conservative-model signature §3.2.3 already identified and built
`MIN_RECALL` specifically to catch: a model that rarely predicts "pinch" at
all trivially posts a low rotation-FP number without solving anything. Both
shorter windows (closer to per-frame noise) and longer windows (further
from the ~220-967ms real transition timing §3.2.3 measured) failed
identically — there's no sweet spot in between.

**What this narrows down**: the recall collapse across hand-crafted
window-dependent features is not a hyperparameter-tuning problem (neither
window size, §3.2.6, nor class weighting, §3.2.5, fixes it) — it's
consistent with (not proof of) a more fundamental representational
limitation of ratio/angle-delta features specifically, under the current
corpus's negative-class volume and composition. Static hand-crafted
features (`handcrafted_static`, no window) are a separate case not covered
by this sweep and shouldn't be assumed to share this finding without
checking — see §8's next-step ordering.

**Kept, not reverted**: `sweep_prediction_error_window.py` — a reusable
one-off tuning script, same category as `analyze_transition_window.py`, not
run automatically as part of every retrain.

**Follow-up, same day: `handcrafted_static` checked and found to share the
collapse — no new experiment needed, already in this section's own 11-
session retrain output.** `handcrafted_static` has no window and no
derivative at all — just the 7-dim ratio/curl-angle features from a single
frame — so it's the cleanest test of whether the recall collapse is
specific to windowing/derivatives. It isn't: `mlp/handcrafted_static`
scored recall **0.214**, `logreg/handcrafted_static` **0.172** — both
squarely inside the same 0.11–0.28 collapsed range every windowed variant
showed in the sweep above, nowhere near `MIN_RECALL=0.4`. **This rules out
"it's something about computing deltas/prediction-error specifically" as
the mechanism** — the collapse affects the underlying 7-dim hand-crafted
representation itself (ratio + curl angles), static or windowed alike, not
something introduced by temporal feature engineering.

**This creates a real tension with §8's decided default** (hand-crafted
features preferred over raw landmarks, based on the near/far-distance
generalization experiment and matching literature on small-model/small-data
robustness). That decision was correct *for the problem it was measured
against* (distance-generalization noise) — but under the current, different
problem (recall as `rotating_no_pinch`'s negative-class volume grows), the
7-dim hand-crafted representation is now the one struggling, raw landmarks
the one holding up. Both findings are real and don't contradict each other,
they're about different failure modes — but it means "hand-crafted features
are the default" can no longer be treated as settled for every situation;
whoever picks this up next should weigh both axes (distance robustness vs.
recall-under-class-imbalance) explicitly rather than defaulting to the
older decision without re-checking it against the current corpus.

### 3.2.7 Follow-up (2026-07-31): a fused raw+hand-crafted representation — the best result yet, on every metric

Triggered by §3.2.6's finding that neither pure representation wins
outright: raw landmarks keep recall up as `rotating_no_pinch` grows, but
lose to hand-crafted features on camera-distance generalization (§3.2.1).
Rather than picking one, checked whether concatenating both into a single
input vector is a real, literature-backed pattern before building it
(§2's discipline) — it is: pose/sign-language recognition work builds
models from "a flat vector representation of pose concatenated with the
2D angle and length of every limb," a documented standard pattern, not a
novel idea specific to this project.

**Built**: `features.py::extract_raw_plus_handcrafted_features()` — the
existing 63-dim raw landmark vector concatenated with the existing 7-dim
hand-crafted vector (70 dims total), static only (no delta/prediction-error
terms, deliberately — keeps this experiment isolated from the temporal-
window question §3.2.3/§3.2.6 already investigated separately). Added as
`raw_plus_handcrafted` to `train_pinch_classifier.py`'s `REPRESENTATIONS`.
The winner-selection logic's "prefer hand-crafted within 2 points" rule
(§8's decided default) was narrowed to apply only to the pure 7-dim
hand-crafted family, not this fused representation — it's 90% raw
landmarks by dimension count, so it shouldn't get an automatic bonus meant
for the pure hand-crafted case.

**Result: `mlp/raw_plus_handcrafted` beats `mlp/raw_landmarks` (the
previous winner) on every metric, not a tradeoff**:

| Model | Rotation FP | Test F1 | Recall | Precision |
|---|---|---|---|---|
| `mlp/raw_landmarks` (previous winner) | 13.2% | 0.625 | 0.540 | 0.743 |
| **`mlp/raw_plus_handcrafted` (new winner)** | **11.4%** | **0.713** | **0.576** | **0.936** |

This is the best rotation-FP result in the project's history (previous
best 13.2%, before that 14.7%/22.0%/27.2%) and the first round where
recall, F1, and rotation-FP all improved together rather than trading off
against each other — unlike every attempted fix in §3.2.5 (class
weighting) and implicitly in §3.2.6 (windowing), which improved one metric
by sacrificing another. Precision also jumped sharply (0.743→0.936),
consistent with the fused input carrying enough of the hand-crafted
features' rotation-robustness signal to cut down the false-positive rate
raw landmarks alone couldn't reach, while keeping enough of raw landmarks'
full information to avoid the recall collapse the pure 7-dim
representation suffered.

**Not yet at §9.3's working target** (rotation FP <~10%, recall
>~0.6-0.7) — 11.4%/0.576 is close on both axes but hasn't cleared either
threshold. The natural next lever, per §9's own loop, is more data
(especially more `rotating_no_pinch` variety, still not confirmed
exhausted per §3.2.6's one below-threshold round) now applied on top of
this better-performing representation, rather than further feature
engineering — consistent with this project's repeated finding that corpus
growth outperforms feature changes.

**Exported**: `Resources/pinch_classifier_weights.json` now holds
`mlp/raw_plus_handcrafted`'s weights (`architecture: "mlp"`,
`representation: "raw_plus_handcrafted"`, 70 input dims) — same flat-JSON
portability shape as every prior export (§7.1).

### 3.2.8 Follow-up (2026-07-31): a third ("medium") distance set, a controlled learning-curve ablation, and a fusion-representation reversal

Triggered by a direct question: would a full third recording set (matching
the near/far protocol's density, at yet another camera distance) push the
classifier to the §9.3 working target, and separately, would tracking
performance vs. training-set size directly (not just round-over-round
deltas) reveal whether the "more data" lever is hitting diminishing
returns? Both pursued together, deliberately: recording the third set
naturally supplies the third point a real learning curve needs (a single
1→2 delta, as in every round through §3.2.6, can't distinguish "still
improving" from "diminishing returns" as reliably as a 3-point trend can).

**Recorded**: 34 clean sessions at a new, "medium" camera distance — full
6-orientation × {pinch, open_hand, fist} taxonomy (2 reps/cell, matching
the near/far sets' density) plus 3 new `rotating_no_pinch` sessions.
**Two accepted gaps**: `pinch_palmout` and `fist_palmout` have zero clean
sessions at this distance — `palm_out` produced a near-total both-hands-
detection failure (0-8%) across 4 repositioning attempts for `fist_palmout`
specifically, and after some improvement still fell short for
`pinch_palmout` (52.9% best attempt). This is the same kind of
camera-framing problem already flagged for `fist_palmout` at other
distances (§9.2) — accepted as a known gap per that same precedent, not
pursued further. `open_hand_palmout` has 1 clean session (98.1%).
Corpus: **148 recordings total** (up from 114).

**Ablation design** (`train_set_ablation.py`, new): distance-set membership
isn't recorded in any label or JSON field — only inferable from capture
timestamp (near = 2026-07-30, far = 2026-07-31 07:14-07:27, medium =
2026-07-31 10:15+, confirmed by manually inspecting the corpus's timestamp
clusters before writing the script). Built a genuine learning curve: **one
fixed held-out test split** (computed once against the complete final
corpus, then held constant), against which three cumulative training pools
are compared — set 1 (near) only, sets 1+2 (near+far), sets 1+2+3
(near+far+medium). `rotating_no_pinch` is deliberately held **constant**
(the full current pool, minus whichever session the global split holds out
as test) across all three runs — it's a separate axis (negative-class
coverage, tracked independently via §9), and holding it fixed isolates one
variable: does held-state (pinch/open_hand/fist) distance diversity help,
independent of rotation-data growth. All three runs use the current
winning representation (`mlp/raw_plus_handcrafted`, §3.2.7).

**Result: F1/recall/precision all improve monotonically, but rotation-FP
gets WORSE, not better — a real trade-off, not a fix**:

| Sets included | Held-state sessions | Test F1 | Recall | Precision | Rotation FP |
|---|---|---|---|---|---|
| 1 (near) | 35 | 0.190 | 0.126 | 0.387 | **2.4%** |
| 1+2 (near+far) | 69 | 0.386 | 0.335 | 0.456 | 11.1% |
| 1+2+3 (near+far+medium) | 84 | 0.514 | 0.494 | 0.536 | 13.9% |

More held-state distance diversity makes the classifier measurably better
at discriminating pinch from open_hand/fist (F1 +0.196 then +0.128 per
round, recall +0.209 then +0.159) — but it does this by making the
decision boundary less conservative, which lets in more rotation-induced
false positives too, even with the rotation-negative training data held
perfectly constant throughout. This is the same recall-vs-rotation-FP
tension §3.2.5 found with class weighting, surfacing again from a
completely different lever (held-state data diversity instead of loss
reweighting) — reinforcing that this is a structural property of the
problem, not an artifact of any one fix attempted so far. One qualified
positive: the rotation-FP degradation itself is slowing (+8.7 points then
+2.8 points per round) — right at §9.3's diminishing-returns threshold,
worth re-checking on a future round rather than assuming it continues
accelerating.

**A second, unexpected finding surfaced by the same corpus growth: the
`raw_plus_handcrafted` fusion representation's §3.2.7 win did not hold up
once the medium-distance set was added — it got substantially worse, while
plain raw landmarks improved.** Retraining the full pipeline (all
representations, all architectures) on the complete 148-recording corpus:

| Model | Rotation FP | Test F1 | Recall | Precision |
|---|---|---|---|---|
| §3.2.7 (108 sessions, pre-medium): `mlp/raw_plus_handcrafted` | 11.4% | 0.713 | 0.576 | 0.936 |
| Now (148 sessions): `mlp/raw_plus_handcrafted` | 13.9% | 0.514 | 0.494 | 0.536 |
| **Now (148 sessions): `mlp/raw_landmarks` (new winner)** | **11.2%** | 0.657 | **0.643** | 0.671 |

`raw_landmarks` alone *improved* with the added corpus (F1 0.625→0.657,
recall 0.540→0.643, rotation FP 13.2%→11.2%, comparing against §3.2.6's
pre-fusion baseline), while the fused representation that beat it a round
ago now underperforms it on every axis except precision. Plausible
mechanism, not yet directly verified: §3.2.1 already measured that the
7-dim hand-crafted features get noisier with camera distance (`hand_size_
ref`'s variance nearly tripled near→far); a third, different distance
regime may be adding a new noise pattern the small hand-crafted component
can't average out as cleanly as it did across just two distances, and with
only `hidden_units=4`, the fused model doesn't have much capacity to learn
around a degraded sub-component. **Not investigated further this round —
flagged as an open item (§8)** rather than chased immediately, since the
practical outcome (raw landmarks winning again) already gives the best
result of the two.

**Net result — new best-ever rotation FP and recall, though not the best
F1**: **`mlp/raw_landmarks`, rotation FP 11.2% (previous best 11.4%),
recall 0.643 (previous best 0.576, and the first result to clear §9.3's
recall >0.6 bar)**, F1 0.657 (below §3.2.7's now-degraded 0.713, because
precision dropped to 0.671 from 0.936). **Still short of §9.3's full
combined working target** (rotation FP <~10% AND recall >~0.6-0.7) — recall
now clears its half, rotation FP (11.2%) is the closest it's ever been to
its half but hasn't crossed it. This directly answers the round's opening
question: a full new distance set was worth doing (new best-ever numbers on
two axes), but it did **not** cleanly resolve the working target — it
traded F1/precision for recall/rotation-FP-adjacent gains, consistent with
this round's own learning-curve finding that the two sides of the target
pull in different directions as held-state data grows.

**Kept, not reverted**: `train_set_ablation.py` — the fixed-test-split,
cumulative-training-pool pattern is reusable for any future learning-curve
question (e.g. re-running this exact ablation once a 4th set exists, to see
if the rotation-FP-degradation slowdown continues).

### 3.2.9 Follow-up (2026-07-31): root-caused — a stale hyperparameter, not distance noise or a representation flaw. Working target met.

Direct follow-up to §3.2.8's open question (§8 item 5): why did
`raw_plus_handcrafted` regress once the medium-distance set was added?
Two hypotheses checked in order, per §2's "measured, not guessed"
discipline:

**Hypothesis 1 (distance noise) — checked and rejected.** Mirrored §3.2.1's
`hand_size_ref` diagnostic across all three distances for `open_hand_front`:
near std=0.0023 (CV 0.025), far std=0.0055 (CV 0.056), **medium std=0.0016
(CV 0.016) — the LOWEST variance of the three, not the highest.** A direct
question raised alongside this check — could camera focus/sharpness matter,
since the medium-distance recordings had the sharpest image definition —
pointed the same direction: sharper focus means more precise landmark
localization, i.e. *less* measurement noise, consistent with (not
contradicting) the variance finding. This rules out "medium distance is
just noisier" as the mechanism.

**Diagnostic: per-cell misclassification comparison, same fixed test
split, `raw_landmarks` vs. `raw_plus_handcrafted`.** Not a uniform
regression — `raw_plus_handcrafted` improved sharply at `pinch_front`
(46%→3% wrong) but regressed badly elsewhere (`open_hand_front` 0%→43%,
`pinch_palmdown` 44%→77%, `pinch_palmin` 10%→51%). This is the signature of
a capacity-constrained model concentrating on a few high-frequency train
patterns rather than generalizing — not a representation-quality problem.

**Hypothesis 2 (stale hyperparameter) — checked and confirmed.**
`hidden_units=4` was chosen via a sweep in §3.2.1, against the
**original near-only corpus (2,281 train examples)** — never revisited as
the corpus grew to 15,408 train examples (~7x) across §3.2.4/§3.2.6/§3.2.8.
Swept `hidden_units` ∈ {4, 8, 12, 16, 24} × `l2` ∈ {0.001, 0.01} for
`raw_plus_handcrafted` on the current full corpus:

| hidden_units (l2=0.001) | Train F1 | Test F1 | Recall | Rotation FP | Train/test gap |
|---|---|---|---|---|---|
| 4 (stale default) | 0.756 | 0.514 | 0.494 | 13.9% | 0.242 |
| 8 | 0.851 | 0.682 | 0.671 | 8.2% | 0.169 |
| 16 | 0.927 | 0.720 | 0.765 | 6.3% | 0.207 |
| 24 | 0.930 | 0.748 | 0.724 | **5.5%** | 0.182 |

**Bigger hidden layers *decreased* the train/test gap** (0.242 at
hidden=4 down to 0.169-0.182 at 8-24) — the small model was **underfitting**
the larger, richer input space, not overfitting a small one. This is the
opposite of §3.2.1's original finding (there, *wider* layers 8-20 clearly
overfit on the much smaller original corpus) — both findings are correct
for the corpus size they were measured against, which is exactly why a
hyperparameter chosen once isn't safe to leave unexamined as the corpus
keeps growing.

**Seed-sensitivity check** (§3.2.2's own required discipline before
trusting a single run): `hidden_units=24` across 6 seeds — F1 range
[0.705, 0.775], recall range **[0.713, 0.822]**, rotation FP range **[4.5%,
6.6%]**. Every single seed clears the working target on both axes — not a
lucky run.

**Updated `train_pinch_classifier.py`'s default to `hidden_units=24`**
(applies to every representation in the standard sweep, not just the fused
one — re-testing the hyperparameter uniformly rather than special-casing
one representation). Full retrain, all representations, current 148-session
corpus:

| Model | Rotation FP | Test F1 | Recall | Precision |
|---|---|---|---|---|
| **`mlp/raw_plus_handcrafted` (winner)** | **5.5%** | **0.748** | **0.724** | 0.773 |
| `mlp/raw_landmarks` (close second) | 6.0% | 0.740 | 0.719 | 0.761 |
| `mlp/handcrafted_full` | 18.0% | 0.651 | 0.602 | 0.708 |
| (logreg variants all far behind, unaffected by the MLP hyperparameter fix) | | | | |

**§9.3's working target is met, for the first time**: rotation FP <~10%
(5.5%) **and** recall >~0.6-0.7 (0.724), simultaneously, on the same model.
`raw_plus_handcrafted` and `raw_landmarks` are now close enough (5.5% vs
6.0% FP, 0.724 vs 0.719 recall) that the fusion representation's original
§3.2.7 rationale (hand-crafted features add real value) holds up once the
confound (undersized model) is removed — the earlier "reversal" (§3.2.8)
was never really evidence against the representation, just against the
stale capacity setting. Params at `hidden_units=24`: 70×24+24+24+1 = 1,729
— still comfortably inside Specification.md §7.1's "few thousand params,
JS-portable" budget, so this fix didn't cost the portability requirement
anything.

**Practical implication**: per §4's prioritized next steps, event-layer
tuning (§3.3.2) was explicitly blocked on base-classifier quality — that
blocker is now lifted. Re-running `tune_event_layer.py` against this
classifier (not the older, worse one §3.3.2 tested against) is the
natural next step, not further base-classifier work.

### 3.2.10/3.3.3 Follow-up (2026-07-31): finger-articulation features — a decisive win, both target axes improve together again

Triggered directly by a question during event-layer re-tuning: nothing in
this project's feature set explicitly measures whether fingers move
*together* (rigid whole-hand motion, e.g. rotation) or *independently*
(a genuine pinch, where thumb+index move while the other three stay
relatively still). Two independent literatures were searched and found to
converge on this being the right signal, **before** building anything —
computer-vision **rigid-vs-articulated motion segmentation** (points on a
rigid body share one low-dimensional motion pattern; independently-moving
parts deviate from it — "A General Framework for Motion Segmentation:
Independent, Articulated, Rigid, Non-rigid, Degenerate and Non-degenerate,"
Yan & Pollefeys) and hand-biomechanics **postural-synergy** research (finger
joints move together during grasping in patterns distinguishable from
whole-hand/wrist movement via correlation analysis; wrist-hand coordination
is measurably lower than within-hand coordination — Analysis of Hand and
Wrist Postural Synergies in Tolerance Grasping, PMC5007036).

**Built**: `features.py::extract_finger_articulation_features()`. Uses the
5 MCP knuckles (already this project's `hand_size_ref` anchor) as a proxy
for the hand's *rigid* motion — they move together under any whole-hand
translation/rotation, since the palm itself doesn't independently deform.
Each fingertip's displacement is then measured *relative to* that rigid
reference (mean MCP displacement subtracted out): near zero if a finger is
just along for the ride, large if it's independently articulating. Two
features: `thumb_index_articulation`, `other_fingers_articulation`. Added
on top of the current winner as `raw_plus_handcrafted_plus_articulation`
(72 dims) — deliberately tested against the practically-relevant baseline,
not in isolation.

**Result: every metric that matters moved together, again** —

| Model | Rotation FP | Recall | F1 | Precision |
|---|---|---|---|---|
| §3.2.9 winner: `mlp/raw_plus_handcrafted` | 5.5% | 0.724 | 0.748 | 0.773 |
| **New winner: `mlp/raw_plus_handcrafted_plus_articulation`** | **2.7%** | **0.739** | 0.679 | 0.628 |

Rotation FP more than halved (5.5%→2.7% — the best result across the
project's entire history by a wide margin) **and** recall improved
(0.724→0.739) **simultaneously** — the model became both more willing to
say "pinch" and dramatically less confused by rotation at the same time,
exactly the two-independent-literatures hypothesis's predicted effect (not
a coincidence this feature happened to help — it's the first time in this
project's history a change improved rotation-robustness by giving the
model new *discriminating* information, rather than by shifting a decision
threshold, which is what every previous rotation-FP-improving lever
—class weighting §3.2.5, held-state data growth §3.2.8—was actually doing
under the hood). F1 dropped slightly (0.748→0.679, precision 0.773→0.628)
— a real, honestly-reported cost, but on the two axes this project has been
tracking as the working target (§9.3: rotation FP, recall), this is an
unambiguous improvement, not a trade-off.

**Also fixed along the way**: `Resources/classifier.py::predict_from_
landmarks()` only supported the original two static representations
(`handcrafted`, raw) — a real integration gap, caught exactly the way §7.1
warned it would be (live/tuning code paths not exercised by the training
loop's own test-set evaluation). Extended to cover every static
representation this project has actually shipped a winner from
(`raw_plus_handcrafted` too). `tune_event_layer.py`'s `hand_sequence()` was
separately extended to support *windowed* representations (needed for
`raw_plus_handcrafted_plus_articulation`, which requires a past+now
landmark pair) — using the same fps-derived `window_frames` scheme
`train_pinch_classifier.py` trains against, so live/tuning behavior
actually matches what the model was evaluated on.

**Exported**: `Resources/pinch_classifier_weights.json` now holds
`mlp/raw_plus_handcrafted_plus_articulation` (72 input dims,
`hidden_units=24`, 72×24+24+24+1 = 1,825 params — still well inside the
JS-portability budget).

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

### 3.3.1 Onset vs. offset: literature check and design consequence (2026-07-30)

Added after a direct question about how state-of-the-art literature treats
release relative to pinch — specifically whether it's a symmetric mirror of
onset (same signal, same threshold, opposite direction) or something that
needs its own treatment. This matters concretely for this project: release
is the trigger this pipeline uses to let go of a grabbed cube, so it needs
its own scrutiny, not an assumption that whatever works for onset
automatically works in reverse for offset.

- **Kendon's gesture-phase model** (Kendon, 2004 — the standard reference in
  gesture-recognition literature, used directly in gesture-phase-
  segmentation systems) formalizes this project's onset/apex/offset
  terminology as an established structure, not an invented one:
  preparation → stroke → retraction (or the fuller five-phase form: rest →
  preparation → stroke → hold → retraction). Stroke is the "meaning-bearing"
  peak (this project's apex), preparation is onset, retraction is offset —
  confirms §3.3's onset/apex/offset framing is the literature's own
  vocabulary, just applied to a manipulation gesture instead of a
  co-speech one.
- **Production XR hand-tracking SDKs treat pinch and release as two events
  read off one continuous signal, via hysteresis — not two independently
  classified gesture shapes.** Both Ultraleap's `PinchDetector` (exposing a
  single `PinchStrength` in `[0,1]`, with distinct `activateDistance` /
  `deactivateDistance` thresholds — Ultraleap's own docs recommend the
  deactivate threshold be looser than the activate one specifically to avoid
  boundary jitter) and Meta Quest's hand-tracking API (`ovrInputStateHand`'s
  `PinchStrength`, also `[0,1]`, also exposed as a single continuous value
  with a boolean derived from it) confirm this shape. **This validates,
  rather than changes, this project's existing hysteresis design**
  (`PART_ONE.md` §2's release-conditions bullet already used a release
  threshold with hysteresis vs. the grab threshold, before this literature
  check — good sign, not a coincidence, since it's the same shape production
  systems converged on independently) — and it confirms the base classifier
  (§3 stage 3) should stay one continuous per-frame confidence signal, not
  two separately trained "pinching" and "releasing" classifiers.
- **But prehension (reach-to-grasp) kinematics literature shows onset and
  offset are not simply time-reversed mirrors of each other.** Aperture
  closure (the pinch-onset movement) is governed predominantly by spatial
  parameters of the reaching hand's own movement (distance-to-target,
  velocity, acceleration) rather than fixed timing; separately, prehension
  studies measuring transport-and-release movements found **release/
  transport-release phases take measurably longer than the reach-grasp
  phase** for the same movement. This is real, literature-documented
  asymmetry between closing and opening hand dynamics — not this project's
  own hypothesis. One weaker, patent-level data point points the same
  direction: some grab-gesture patent implementations describe needing two
  distinct static gesture definitions, one for initiating a grab and a
  separate one for releasing, rather than one symmetric rule.
- **Design consequence**: the base per-frame classifier stays a single
  continuous confidence signal (unchanged from the existing plan) — but the
  event layer's onset-detection and offset-detection derivative-agreement
  checks (§3.3 above) must be **tuned as two independent parameter sets**
  (window size, agreement threshold, each fit separately), not one rule
  mirrored symmetrically around the confidence signal's threshold crossing.
  The kinematics evidence above says they're allowed to behave differently
  in real hands; this project's own rotation-false-positive history (§1) is
  reason enough not to assume symmetry without checking anyway. Concretely,
  this means Stage 1's `pinch_cycles` transition sessions must give the
  event layer enough data to fit offset detection on its own terms, not
  just reuse whatever window/threshold fit onset best — see §5's updated
  taxonomy below for what that means for recording.

### 3.3.2 Implementation attempt and finding (2026-07-31): blocked on base-classifier quality, not event-layer tuning

Built `Resources/event_layer.py` (`PinchEventTracker`, a per-hand state
machine over `idle`/`apex`, confirming onset/offset via derivative
agreement between the base classifier's confidence and the raw
`pinch_ratio`, both over a shared window — exactly §3.3's design) and
`tune_event_layer.py` (loads `pinch_cycles`/`pinch_rotate_release` in
temporal per-hand order, per §3.3's rule, and sweeps window size +
onset/offset thresholds, scored against: cycle sessions should show ~3
onset/offset pairs each — matching the "repeated ~3 times" recording
protocol — and `rotating_no_pinch` sessions should show zero).

**No threshold combination found both targets at once — this is a real
ceiling, not an under-tuned parameter.** Tightening thresholds enough to
suppress false positives on `rotating_no_pinch` also suppressed true
detections on `pinch_cycles` (down to ~1 of the expected ~3 per session);
loosening them to recover true detections pushed `rotating_no_pinch` false
positives up in lockstep (34–46 false onset/offset events across just 10
negative session-hand-sequences, at the loosest tested settings) — a
precision/recall tradeoff with no good operating point in the range swept.

**Root cause, checked directly, not assumed**: measured the base
classifier's confidence output during a pure `rotating_no_pinch` session
(no pinching at all) — it swings from 0.02 to **0.90**, with 6.8%–50.3% of
frames per session exceeding 0.5 ("would call it a pinch"), and sustained
false-high runs up to 28 consecutive frames. **This is the same
rotation-false-positive failure mode that killed the original rule-based
classifier (§1's 38.5% figure), not fixed by moving to a trained model —
just less visible, because it was hiding inside an aggregate F1=0.617
metric rather than being isolated against a pure-rotation stress test the
way §1's evidence trail specifically did.** No event-layer parameter choice
can fully route around a base signal that itself spikes to near-1.0
confidence during genuine non-pinch motion; the derivative-agreement
technique reduces sensitivity to *brief* noise, but a real, multi-frame
false-confidence excursion (up to 28 frames here) can still look enough
like a genuine transition to satisfy an agreement check loose enough to
also catch real pinches.

**A related, separate finding surfaced along the way**: at the `palm_away`
orientation specifically, the base classifier's confidence tracks pinch
correctly (swings 0.15→0.77 across a real cycle), but the raw
`pinch_ratio` signal barely moves (0.43-0.54, versus ~0.16-0.65 at
`front`) — a real, orientation-dependent effect on the underlying geometry
at that orientation, not a bug in `pinch_ratio`'s computation. This meant
`palm_away` produced zero detected events at every threshold tight enough
to say anything about a fixed ratio-magnitude gate — a second reason (on
top of the rotation-noise ceiling above) the "fixed thresholds across all
orientations" design needs revisiting, not just retuning.

**Per §2's discipline, explicitly not treated as an event-layer parameter
problem to keep tuning around**: the fix for "the base classifier isn't
accurate/stable enough yet" is more/better classifier training data (§3.2.1
/ §3.2.2's already-flagged open items — more far-distance sessions,
resolving the near/far regression), not a tighter event-layer threshold or
a bolted-on special case for rotation or for `palm_away`. **Event-layer
tuning is blocked on base-classifier improvement, not the other way
around** — this is new information for Stage 1/Stage 3, exactly per §3.3's
own closing rule ("if the event layer misfires on a case Stage 1 didn't
anticipate... never a reason to add a rule on top of the... output").
`event_layer.py` and `tune_event_layer.py` are kept (the design and tuning
mechanics are sound and reusable), but no threshold values from this pass
are treated as final — re-run `tune_event_layer.py` once the base
classifier's rotation-robustness improves, not before.

### 3.3.4 Re-tuned against the improved classifier (2026-07-31): real progress, but a fixed-threshold ceiling — and the connection to a future context/prior layer

Direct follow-up once §3.2.9/§3.2.10 lifted the base-classifier blocker.
Fixed a real integration gap first: `tune_event_layer.py` called the
single-snapshot `classifier.predict_from_landmarks`, which didn't support
either of this session's newer representations (`raw_plus_handcrafted`,
then the windowed `raw_plus_handcrafted_plus_articulation`) — extended
`predict_from_landmarks` for static representations and added a windowed
path to `tune_event_layer.py`'s `hand_sequence()`, using the same
fps-derived `window_frames` scheme `train_pinch_classifier.py` trains
against (§3.3.3).

Also recorded a fresh `pinch_cycles`/`pinch_rotate_release` set at the
medium distance (10 of 12 orientations clean — `pinch_cycles_palmout`
failed both-hands detection again at this distance after 2 attempts,
accepted per the same precedent as the held-state gap, §3.2.8) — the
original data only covered near/far, never the distance the classifier now
performs best at.

**Three re-tunes, tracking each classifier improvement**:

| Classifier | Cycle onset mean | Cycle offset mean | Rotation false onsets/offsets |
|---|---|---|---|
| §3.3.2 (original, blocked) | not measurable at any threshold | — | 34-46 (loosest tested) |
| §3.2.9 winner (`raw_plus_handcrafted`, near+far cycles only) | 0.79 | 0.67 | 16 / 8 |
| + medium-distance cycles added | 1.07 | 0.96 | 16 / 8 (unchanged, same classifier) |
| §3.2.10 winner (`+articulation`) | **1.15** | **1.00** | **6 / 3** |

Real, consistent progress — false events dropped in near-lockstep with the
classifier's own rotation-FP improvement (5.5%→2.7%), confirming the event
layer's remaining error is now downstream of, not independent from, base
classifier quality. **But detection is still well below the ~3-per-session
target** (target: matching the "repeated ~3 times" recording protocol).

**Root cause of the remaining gap, checked directly**: per-session
breakdown shows `palm_away` at **zero onsets/offsets across every single
session, both hands, no exceptions** — not new, this is exactly §3.3.2's
already-documented finding (`pinch_ratio` barely moves at that
orientation) reproduced with the better classifier, confirming it's a
structural property of the ratio-fall trigger at that orientation, not a
classifier-quality artifact that better training fixes. Elsewhere,
detection is inconsistent but not zero (several `front`/`palmdown`/
`palmout` cells already hit or exceed 3). **This points at the event
layer's single fixed threshold set, applied uniformly across all 6
orientations, as the actual remaining ceiling** — not further
classifier-quality work, and not (per §2's discipline) a special-cased
"palm_away exception" bolted onto the derivative-agreement check.

**This is the concrete, immediate use case for the context/prior-weighted
layer proposed the same session** (see the forward-looking design note,
§10, if written by the time this is read): an orientation-conditioned
prior/threshold — instead of one global `onset_ratio_fall` constant — is a
principled, literature-grounded way to let `palm_away` (and any other
orientation-specific dynamics) use a different effective trigger without
writing a per-orientation if/else into `event_layer.py`. Not implemented
this session (deliberately staged for when the pipeline integrates with
the actual object-control game, per the user's framing), but the tuning
data collected here (per-orientation onset/offset counts, per-orientation
`pinch_ratio` dynamics) is exactly what would be needed to estimate that
prior empirically rather than guess it.

**Not yet fully resolved — an honest open item, not a finished Stage 3.3**:
event-layer tuning is closer than it's ever been (best-yet numbers on every
tracked metric) but hasn't hit the ~3-per-cycle target. Whoever picks this
up next should treat "orientation-aware thresholds" (via the prior layer,
once built) as the next lever, not another blind threshold re-sweep over
the same fixed-constant design.

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

## 5. Worked example: pinch recording taxonomy (revised 2026-07-30 —
orientation grid expanded from 3 to 6 cells, release given its own
orientation coverage; still confirm/adjust before recording, not final)

A starting proposal for re-launching pinch under this pipeline — confirm
or adjust at the start of implementation, don't treat this as final. Pinch
is **episodic** (§3's "decide first" note), so it needs both of Stage 1's
recording types. Revised from the original 3-orientation version after two
follow-up points: (1) release deserves the same scrutiny as pinch itself,
since it's the trigger this pipeline uses to let go of an object, not an
afterthought derivative of pinch — see §3.3.1's literature check; (2) the
orientation grid was underspecified at 3 cells and is replaced below with
the full 6-cell grid a palm's orientation actually spans.

**Classes (for the base classifier, §3 — held-state sessions):**
- `pinch` (positive)
- `open_hand`, `fist`, `rotating_no_pinch` (negative — the first two from
  general gesture-classification practice, the third specifically because
  §1's finding was rotation-induced, not a class this project would have
  picked without that evidence)

Release is **not** a fifth held-state class here — it's inherently a
transition (held-pinch → open), not a state that can be held for a session,
so it's covered entirely by the cyclic/transition sessions below, per
§3.3.1's conclusion that the base classifier stays one continuous signal and
onset/offset are two independently-tuned event detectors on top of it, not
two separately trained held-state classes.

**Orientation grid — 6 cells, the 3 axes a palm normal can point along, each
in both directions** (applied to `pinch`/`open_hand`/`fist`):

| Label | Palm normal points... | Notes |
|---|---|---|
| `front` | toward the camera | palm visible face-on to the camera |
| `palm_away` | away from camera, toward the user's own face | back of hand visible to camera; **expect lower tracking confidence** — fingers are partly self-occluded from the camera's viewpoint, consistent with the monocular-tracking caveats already noted for `world_landmarks`' `z` component (`PART_ONE.md` §2) |
| `palm_up` | up, toward the ceiling | |
| `palm_down` | down, toward the floor | |
| `palm_in` | toward the body's sagittal midline | with both hands recorded symmetrically (per the protocol below) this reads as "palms facing each other"; defined per-hand via the midline so it stays well-defined even for a single hand, not only when both hands are literally present |
| `palm_out` | away from the body's sagittal midline | "palms facing away from each other" when both hands are recorded symmetrically; same per-hand midline definition as `palm_in` |

`rotating_no_pinch` inherently sweeps orientation within the session, so it
doesn't need separate per-orientation sessions the same way.

**Session labels** (`<class>_<orientation>`, e.g. `pinch_front`,
`pinch_palmaway`, `pinch_palmup`, `pinch_palmdown`, `pinch_palmin`,
`pinch_palmout`, `open_hand_front`, ..., plus `rotating_no_pinch` on its
own): **3 classes × 6 orientations = 18 labels**, `rotating_no_pinch`
recorded separately = **19 labels total**, ≥2–3 sessions each per §3 stage
1.

**Recording protocol detail**: record both hands performing the *same*
class/orientation simultaneously per session, so every hand-frame in a
given file is unambiguously the session's label — don't have one hand
pinching while the other rests, that reintroduces the per-frame-ambiguity
problem §3 stage 1 exists to eliminate.

**Second recording type (for the event layer, §3.3 — cyclic/transition
sessions, not classifier training data):**
- `pinch_cycles_<orientation>`: neutral → pinch → release, repeated ~3 times
  per session, **slow and deliberate** (learned the hard way not to rush
  this — see Stage 1's note and `PART_ONE.md` §7.2), recorded across **the
  full 6-cell orientation grid above, not just `front`** — revised from
  "front at minimum, add others only if it turns out to matter" because
  §3.3.1 found a concrete reason it does matter: release dynamics aren't a
  guaranteed mirror of pinch dynamics, so offset detection needs real data
  at every orientation it'll actually be asked to work at, not just the one
  pinch itself is most often performed at.
- `pinch_rotate_release`: a new session type, added specifically for the
  realistic use case behind an object-manipulation grab — pinch-grab at
  `front`, **rotate the hand through several orientations while still
  pinched** (the cube stays "held" throughout, per the sticky-grab design in
  `PART_ONE.md` §2), then release at whatever orientation the rotation ends
  on. This is what a `pinch_cycles_<orientation>` session (fixed orientation
  start-to-finish) structurally cannot exercise: release immediately
  following a rotation transient, at an orientation different from where
  the grab started — exactly the motivating use case (grab to rotate,
  release wherever the rotation ends), and exactly the kind of transition
  this project's own rotation-related false-positive history (§1) says
  shouldn't be assumed to work by extrapolation from same-orientation data.
  Record several repetitions covering different rotation paths/end-
  orientations per session.
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

- ~~Confirm or adjust §5's taxonomy before recording anything.~~ Done —
  §5's 6-orientation taxonomy recorded in full (53 sessions), see the
  Stage 1 recording session for the corpus inventory.
- ~~Logistic regression vs. small MLP~~ — decided empirically, MLP beat
  logistic regression in both the near-only and near+far runs.
- ~~Raw landmarks vs. hand-crafted features~~ — raw landmarks won on the
  near-only corpus (F1 0.857) but hand-crafted features won once
  far-distance data was added (F1 0.617 vs 0.514), and that flip is
  **confirmed by independent literature, not a project-specific fluke**
  (small-model/small-data practice, and pose-estimation-specific
  geometric-feature robustness to distance/viewing-angle changes — both
  found on direct search, see the "Re-run (2026-07-31)" note above).
  **Decided**: hand-crafted features are this project's default
  representation going forward; still re-check empirically per gesture
  (§3 stage 3 requires it), but no longer a coin-flip open question.
- **Grow the corpus, especially far-distance data** — not to chase raw
  landmarks catching up (deprioritized per the decision above), but because
  108 sessions is still small by the literature's own standard for when
  raw/learned representations start to work well, and more data narrows
  the seed-sensitivity spread (next item) regardless of which
  representation is used.
- **Grow the corpus for the originally flagged weak cells**:
  `open_hand_palmup` and `pinch_palmout` (both Right hand) — flagged in the
  near-only run (§3.2.1's original table); re-check whether they're still
  specifically weak now that far-distance data and a different winning
  representation are in the mix, rather than assuming the original
  diagnosis still applies unchanged.
- **Seed sensitivity** (§3.2.1's original near-only run): test F1 ranged
  0.737-0.859 across 6 random inits of the same architecture/
  hyperparameters. Not yet re-checked against the current hand-crafted
  winner or the combined corpus — do that before trusting 0.617 as more
  than a single point estimate, same caveat as before.
- ~~Top-priority blocker: the base classifier is more rotation-robust but
  not solved~~ — **resolved (§3.2.9): the working target is met.**
  `mlp/raw_plus_handcrafted`, rotation FP **5.5%**, recall **0.724** — both
  halves of §9.3's target simultaneously, for the first time. Root cause of
  the long-running recall-vs-rotation-FP tension (§3.2.5, §3.2.6, §3.2.8)
  turned out to include a stale hyperparameter (`hidden_units=4`, sized for
  a corpus 7x smaller than the current one) alongside the already-identified
  data-volume effects. **This no longer blocks event-layer tuning
  (§3.3.2)** — resuming it against the current classifier is the natural
  next step. History retained below for anyone auditing what was tried:
  1. ~~Investigate the recall collapse across hand-crafted variants~~ —
     **done and closed (§3.2.5): class-weighted training was tried and
     measured to be a strictly worse operating point**, not the fix hoped
     for. It does recover recall (0.2–0.29 → 0.7–0.86) but only by shifting
     the decision threshold toward "pinch" globally, which raises rotation
     false positives right alongside it (9–17% → 35–53%, worse than the
     original abandoned rule-based classifier's 38.5%). Not adopted; the
     recall collapse is not currently understood to be a simple
     training-procedure/imbalance fix.
  2. **Keep growing `rotating_no_pinch`** — was the biggest lever by far
     through §3.2.4, but §3.2.6's 9→11 session round only bought ~1.5
     points (14.7%→13.2%), below §9.3's diminishing-returns bar for the
     first time. Not yet conclusively exhausted (one round isn't a trend),
     but worth watching closely on the next round rather than assumed
     inexhaustible.
  3. ~~Isolate the prediction-error features' own contribution~~ — **done
     (§3.2.6): window size is ruled out as the cause, and so is
     windowing/derivatives generally.** A full 100-1200ms sweep found
     recall stuck at 0.11-0.28 for every window-dependent hand-crafted
     representation; `handcrafted_static` (no window, no derivative — just
     the 7-dim ratio/curl-angle features from one frame) was then checked
     against the same 11-session retrain's own output and found to score
     recall 0.172-0.214, in that same collapsed range. **All three
     "training-procedure/hyperparameter" explanations (class weighting
     §3.2.5, window size, windowing/derivatives themselves §3.2.6) are now
     closed off** — the recall collapse is a property of the 7-dim
     hand-crafted representation itself, static or windowed alike, not
     fixable by retuning around it.
  4. ~~Reconsider the feature set or model architecture more
     fundamentally~~ — **done (§3.2.7)**: a fused `raw_plus_handcrafted`
     representation (63-dim raw + 7-dim hand-crafted concatenated,
     literature-precedented) beat pure raw landmarks on every metric at
     once at the time (rotation FP 13.2%→11.4%, F1 0.625→0.713, recall
     0.540→0.576, precision 0.743→0.936) — the first improvement that
     didn't trade one metric for another. **Superseded by item 5 below —
     this win did not hold up once more corpus was added.**
  5. ~~The fusion representation's win reversed once a third ("medium")
     distance set was added~~ — **root-caused and resolved (§3.2.9): a
     stale hyperparameter, not a real representation or distance-noise
     problem.** `hand_size_ref` variance at medium distance was actually
     the *lowest* of the three distances (ruling out "more noise"); the
     real cause was `hidden_units=4`, chosen via a sweep against the
     original 2,281-example corpus and never revisited as the corpus grew
     ~7x. A fresh sweep found `hidden_units=24` **decreased** the
     train/test gap (was underfitting, not overfitting) and cleared the
     working target across all 6 tested seeds. **Working target met**:
     `mlp/raw_plus_handcrafted`, rotation FP **5.5%**, recall **0.724**,
     F1 0.748 — both axes of §9.3's target simultaneously, for the first
     time. `mlp/raw_landmarks` is a close second (6.0%/0.719), confirming
     the fusion representation's original §3.2.7 rationale holds once the
     capacity confound is removed.
- **`palm_away`-specific finding (§3.3.2)**: `pinch_ratio` barely moves at
  this orientation even during a real pinch (0.43-0.54 vs ~0.16-0.65 at
  `front`), while classifier confidence still tracks correctly — a fixed
  ratio-magnitude threshold across all orientations can't work for this
  cell. Worth designing around before the event layer is considered done
  for all 6 orientations, not just `front`.
- **Event layer (§3.3.2)**: `PinchEventTracker` and `tune_event_layer.py`
  are built and the design/tuning mechanics work — what's blocked is
  finding threshold values that hold up, which per the two items above
  needs base-classifier and possibly per-orientation-signal changes first,
  not more sweeping over the current inputs.
- Stage 4 (live debug tool) not yet built — needed before pinch counts as
  done per §2/§3's own rule ("not optional polish"). No longer blocked on
  base-classifier quality (§3.2.9) — worth building against the current
  classifier rather than continuing to wait.

## 9. Continuous improvement playbook (data + retrain only — not a strategy change)

Written 2026-07-31, after three successive retrains (§3.2.1 → §3.2.3 →
§3.2.4) each measurably moved the rotation false-positive rate (27.2% →
22.0% → 14.7%) using the *same* pipeline shape — more/better recordings,
then `train_pinch_classifier.py` re-run unchanged. **This section is that
loop, formalized**: a repeatable maintenance procedure for whoever picks
this up next, explicitly scoped to data + retraining only. **It is not
where feature-set, architecture, or hyperparameter changes belong** — those
are deliberate backbone decisions, live in §8's open items, and should only
be reached for once this loop's own diminishing-returns signal (below)
says so, not swapped in casually mid-loop.

### 9.1 The iteration procedure

1. **Look at the last training run's own diagnostics** — `train_pinch_classifier.py`
   already prints everything needed: the rotation stress test percentage,
   and the "misclassified by (class, orientation, hand)" breakdown per
   representation. Don't guess which cell is weak; read it off the last
   run's output (or §3.2.1/§3.2.3/§3.2.4's logged tables if picking this up
   fresh).
2. **Record 2-4 new sessions targeting the weakest cell(s) specifically**
   — not a scattershot re-recording of everything. §9.2 below is the
   current priority order; re-derive it from fresh diagnostics once this
   round's items are addressed, don't keep using a stale list.
3. **Re-run `train_pinch_classifier.py` unchanged** — no code edits. It
   auto-discovers the combined corpus, re-splits at the session level,
   retrains all representations, and picks a winner via the existing
   recall-gated rotation-robustness selection (§3.2.3's degenerate-model
   fix). Don't hand-pick a representation or architecture; let the
   existing selection logic run, and only override it if it's visibly
   broken again the way the degenerate-model case was.
4. **Compare against the previous logged result, and log the new one** —
   append a new dated entry following §3.2.1/§3.2.3/§3.2.4's pattern
   (what changed, what the numbers did, one honest sentence on why).
   Silently overwriting the previous numbers with no record of the delta
   is explicitly against §3.2.2's rule.
5. **Check the diminishing-returns signal (§9.3)** before starting another
   round. If it says stop, stop — move attention to the event layer
   (§3.3.2) or Stage 4, not another data round for its own sake.

### 9.2 Current priority queue for future recordings (re-derive when stale)

In descending priority as of 2026-07-31 — re-derive from fresh diagnostics
once these are addressed, this list is a snapshot, not a permanent plan:

1. **More `rotating_no_pinch` variety** — the single biggest lever
   measured so far (§3.2.4: 5→9 sessions dropped rotation FP by ~7-15
   points depending on representation, more than any feature change
   tried). Keep prioritizing *variety* (speed, path, amplitude) over
   volume of similar-looking sessions — a 10th session that looks like
   the first nine is worth much less than one covering a genuinely new
   motion pattern.
2. **`open_hand_palmup` and `pinch_palmout`** (both Right hand) — flagged
   since §3.2.1's original near-only run as specifically weak cells; not
   yet re-confirmed as still-weak now that the corpus and winning
   representation have both changed since (§8's own note on this).
3. **`fist_palmout`** — sits at 1 clean recorded rep instead of 2 (Stage 1
   recording session: 4 straight redo attempts came back with 0 hands
   detected, camera framing issue at that specific orientation, not
   pursued further at the time). Low priority (negative class, well
   covered at every other orientation) but cheap to fix if revisiting
   camera framing anyway. **Confirmed reproducible at a second distance
   (§3.2.8)**: `fist_palmout` also failed at the new "medium" distance (0%
   both-hands across all attempts) — `palm_out` specifically, not this one
   camera setup, appears to be a structurally hard orientation for
   both-hands framing. `pinch_palmout` has the same gap at medium distance
   (best attempt only 52.9% both-hands, after 4 tries) — genuinely 0 clean
   medium-distance sessions for both `pinch_palmout` and `fist_palmout`,
   not just thin coverage. Worth a deliberately different capture setup
   (e.g. wider frame, hands closer to center) next time this is revisited,
   rather than assuming the next attempt at any given distance will work.
4. **`palm_away` orientation generally**, for whichever gesture is being
   built — independently flagged twice now as tracking-degraded (§5's
   original taxonomy note, self-occlusion) and dynamics-different
   (§3.3.2: `pinch_ratio` barely moves there even during a real pinch).
   Worth extra recording density here specifically, not just equal
   coverage with the other 5 orientations.

### 9.3 Diminishing returns — how to tell when more data of the same kind has stopped helping

- **Track the rotation-FP delta per round, not just the absolute number.**
  Logged so far: 27.2% → 22.0% (round 1, −5.2) → 14.7% (round 2, −7.3).
  **Rule of thumb: once a round of 4-5 new targeted sessions buys less
  than ~2-3 points of improvement on the metric it targeted**, that
  specific data axis (e.g. "more rotation variety") has likely hit
  diminishing returns — move to a different weak cell (§9.2) rather than
  recording more of the same kind, or conclude the loop for now.
- **Seed sensitivity as a second, independent diminishing-returns signal**
  (§3.2.1's method: retrain the same winning config across ~6 random
  seeds, look at the test-metric spread). A shrinking spread as the corpus
  grows means more data is still buying real stability, not just a lucky
  draw. A spread that stays wide despite several rounds of added data
  means the bottleneck has likely shifted away from data volume — that's
  the signal to stop this loop and consider a §8 backbone item instead,
  not a reason to keep adding data of the same kind.
- **A concrete "good enough" target, set at the system level, not the
  classifier alone.** The classifier doesn't need to approach 0%
  per-frame rotation false-positive rate before the *product* is
  reliable — the event layer (§3.3, once unblocked) requires **sustained
  derivative agreement across several consecutive frames**, not a single
  frame's confidence, before it fires an onset/offset event. A brief 1-2
  frame false spike at 10-15% per-frame FP is exactly the kind of noise
  the event layer's window is designed to reject; it doesn't need a
  perfect base signal to do that. **Working target: base classifier
  rotation FP below ~10% and recall above ~0.6-0.7** — once both are
  met, the better use of further effort is very likely resuming
  event-layer tuning (§3.3.2) rather than continuing to chase base-classifier
  accuracy in isolation, since at that point the event layer's own
  multi-frame filtering is doing real, multiplicative work on top of an
  already-decent signal. This target is a working estimate, not a proven
  threshold — revise it once the event layer is actually re-tuned against
  a classifier in this range and its own false-event rate is measured.
- **What this loop explicitly does not cover**: if diminishing returns are
  hit and the working target still isn't met, that is the signal to open
  a §8 backbone item (class-weighted training, isolating the
  prediction-error features' real contribution, or a more fundamental
  feature/architecture change) — a deliberate, logged decision, not
  something to slide into mid-way through a data-recording round.

## 10. Future design note (not yet implemented): a context/prior-weighted layer for object-pipeline integration

Written 2026-07-31, in response to a direct question about the eventual
integration point: once the gesture pipeline is wired into the actual
object-control game (Specification.md's broader architecture), the
classifier and event layer stop operating in a context vacuum — some
things become much more or less likely given what's actually happening in
the interaction (a pinch onset is far more likely at `front`, the natural
reach-to-grasp posture, than at `palm_out`; a rotation-shaped signal is
essentially never a genuine grab attempt if nothing is currently held,
since there's no reason to rotate before grabbing). **This section is a
design proposal for later, not code written this session** — deliberately
staged for when real object positions/interaction state exist to condition
on, per the discipline that follows.

**Literature check, done before proposing anything (§2's discipline
applied to a not-yet-built layer, same as every feature built this
session)**: two independent bodies of work converge on the same pattern.
Bayesian evidence-fusion frameworks for grasp-intent inference (prosthetics
/HRI: a vision-based grasp-probability classifier fused with an independent
signal via explicit Bayesian combination) establish the precedent that a
trained classifier's output is one likelihood term to combine, not
necessarily the final answer. "Context as Prior" work formalizes context as
a prior-like feasibility constraint P(y|c) — their own example
(P(EXIT|near_door) high, P(FOOD|near_door) negligible) is structurally
identical to this project's P(pinch|front) high, P(pinch|palm_out) low —
combined with the classifier's evidence via **prior-guided
product-of-experts fusion**, with a tunable parameter controlling how much
weight the prior gets, not a hard override. Bayesian HMMs in gesture
recognition already incorporate prior probability distributions over
gesture states, the same mechanism the "gesture spotting" garbage-model
literature (§3.3.3's search) uses, extended here to make the prior
context-dependent. Reach-to-grasp is independently well-established in
psychology/neuroscience/robotics literature as an object-directed,
two-phase movement — supporting that hand orientation *relative to a
target object* (not orientation in isolation) becomes a legitimate,
literature-grounded signal once real object positions exist to condition
on, not a guessed heuristic.

**Proposed mechanism**: a prior-weighted fusion layer between Stage 3 (base
classifier) and Stage 3.3 (event layer), not a hard gate:

```
posterior_logit = logit(classifier_confidence) + β × log( P(pinch | context) / P(not_pinch | context) )
```

— a product-of-experts in probability space, log-odds addition in
practice: trivial arithmetic, no new dependency, stays inside
Specification.md §7.1/§7.3's portability budget the same way every other
feature in this pipeline does. `β` (prior strength) is the load-bearing
parameter: β→0 recovers today's classifier-only behavior; a hard veto
(β→∞, or a literal `if orientation == "palm_out": return False`) would be
exactly the kind of special-case §2's "no heuristic pile-up" rule rejects
— it would break the rare-but-real case of someone grabbing at an unusual
angle. Keeping `β` small and tunable (or eventually learned/estimated, not
hand-picked) keeps the classifier as the primary evidence source and
context as a nudge, auditable rather than hard-coded.

**Concrete context signals available once integrated**:
- **Orientation prior** `P(pinch onset | orientation)` — estimable
  directly from this project's own `pinch_cycles` corpus (which
  orientations onset events actually occurred at during this session's
  event-layer tuning, §3.3.4), not guessed from first principles alone.
- **Grab-state prior** — this project's existing idle→hover→grabbed→
  released state machine (`PART_ONE.md` §2/Specification.md's interaction
  matrix) already has exactly the state notion needed: while nothing is
  held, a rotation-shaped signal's prior should be strongly suppressed
  (matches §3.3.2/§3.3.4's own rotation-false-positive history directly);
  once holding, the offset prior changes shape entirely — the same
  onset/offset asymmetry §3.3.1 already found from prehension-kinematics
  literature, made explicit and probabilistic instead of two independently
  fit-but-still-fixed threshold sets.
- **Proximity/orientation-to-object prior** — once real object positions
  exist in the game, reach-to-grasp's established object-directedness
  means a pinch performed near a grabbable object is intrinsically more
  likely to be genuine intent than the same gesture performed nowhere near
  anything. §10.1 below refines this from "near an object" to a specific,
  literature-grounded predicted orientation, not just proximity.

### 10.1 A more specific orientation prior: grasp axis vs. object geometry and gravity

The orientation prior above was framed as a flat lookup over this
project's 6 recorded canonical orientations. A more principled version —
asked for directly, and checked against literature rather than assumed —
is that grasp orientation isn't really about the hand's orientation in
isolation; it's about the hand's orientation *relative to the geometry of
the object being grabbed*, and this relationship is well-studied in both
adult biomechanics and child motor development.

**Adult biomechanics — grip axis aligns with the object's minor axis, not
the major one.** "On the Relation Between Object Shape and Grasping
Kinematics" (*Journal of Neurophysiology*) found that when grasping
elongated (non-circular) objects, final hand orientation at contact closely
matches one of the object's principal axes — and specifically, subjects
chose the grip axis (the thumb-index contact line) along the object's
**minor (short) axis in 68% of trials**, not the major one. This isn't an
arbitrary preference: it's a biomechanical-stability result — gripping
along the minor axis is the only orientation where the fingers' surface
normals align with the grip direction; any other angle lets the object
slip along the surface in the short-axis direction. Translated to this
project's terms: for an elongated grabbable object, the **pinch grip axis
(thumb-index line) should align with the object's short dimension, and the
hand's overall orientation/approach with the object's long dimension** —
the opposite pairing from what "grab along the long dimension" might
naively suggest, though it amounts to the same geometric picture the user
described (hand oriented along the object's longest extent, fingers
closing across the short one).

**Child motor development — this orientation-matching is learned early,
and becomes anticipatory, not just reactive.** Studies presenting infants
with horizontal/vertical rods found hand-orientation adjustment to object
orientation present from as early as ~5 months, improving through the
first year; by 10-12 months, infants show **anticipatory** (pre-contact)
orientation matching, not just haptic correction after contact — precisely
the "how a small child learns to orient their hand before grabbing a
Lego brick" mechanism asked about. Newell's (1993) developmental framework
for infant reach/grasp coordination explicitly includes **the direction of
gravity as a physical task constraint** alongside object size/shape, not a
detail specific to this project's use case — it's a standard variable in
that literature.

**Why "orthogonal to gravity" follows, not just object shape alone**: most
grabbable objects rest on a surface and are manipulated from above or the
side, so their long axis is typically horizontal — orthogonal to gravity —
by default, unless the object or scene deliberately breaks that assumption
(e.g. a tall, upright object). This isn't a separate mechanism from the
grasp-axis-alignment finding above; it's the default *value* that finding
takes for most objects in a typical tabletop/game layout — "grab along the
object's longest dimension, orthogonal to gravity" is the practically
correct summary even though the more precise biomechanical claim is that
the *grip axis* is perpendicular to that long dimension.

**Concretely, once integrated**: for each grabbable object, precompute its
principal axes (bounding-box or PCA over its mesh) and derive an *expected*
pinch orientation — the hand orientation whose grip axis would run
perpendicular to the object's longest dimension in the plane orthogonal to
gravity. The `P(pinch | context)` term in §10's product-of-experts formula
becomes a function of how closely the *observed* hand orientation matches
that *object-specific expected* orientation, rather than a fixed lookup
table over 6 recorded labels — a genuinely predictive prior, not just a
descriptive one, and the natural refinement of the orientation-prior bullet
above once real object geometry exists to condition on.

**Immediate, already-identified use case (§3.3.4)**: `palm_away`'s
structural zero-detection problem (pinch_ratio barely moves there, a
geometry fact no amount of classifier improvement fixes) is the first
concrete thing an orientation-conditioned prior/threshold would address —
letting that orientation use a different effective trigger without writing
a per-orientation special case into `event_layer.py`'s derivative-agreement
logic.

**Explicitly not started**: no code for this layer exists yet. Revisit
when the object-control integration is actually being built, at which
point real interaction-state and object-position signals exist to condition
on — building this against synthetic/assumed context now would violate the
same "measured, not guessed" discipline that's governed every other
decision in this document.
