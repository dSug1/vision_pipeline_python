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
- **Top-priority blocker, real progress but still open (§3.2.4): the base
  classifier is more rotation-robust but not solved, and a new
  precision/recall tension appeared.** Rotation stress test (mean
  false-positive rate across all 9 `rotating_no_pinch` sessions, up from
  5) sits at 14.7% for the current best model (`mlp/raw_landmarks`) — the
  best result yet (was 22.0% → 27.2% → original ~27-38%), driven mainly by
  **corpus growth** (more/varied `rotating_no_pinch` data), not by the
  prediction-error features tried alongside it (§3.2.4). **This still
  blocks reliable event-layer tuning (§3.3.2)** — 14.7% is progress, not a
  green light to resume. Concrete next steps, in priority order:
  1. **Investigate the recall collapse across hand-crafted variants**
     (§3.2.4) — every hand-crafted representation dropped below
     `MIN_RECALL=0.4` this round, leaving raw landmarks as the only
     eligible winner (in tension with §8's general hand-crafted
     preference). Try class-weighted training (not yet done) before
     assuming this means hand-crafted features are now worse in general —
     it may just mean the growing negative-class volume needs rebalancing
     during training, a training-procedure fix, not a feature or
     architecture one.
  2. **Keep growing `rotating_no_pinch`** — this round's biggest lever by
     far; no sign yet that it's exhausted.
  3. **Isolate the prediction-error features' own contribution** — this
     round's comparison was confounded by simultaneous corpus growth.
     Worth a controlled re-run (same corpus, features on vs. off) once (1)
     is addressed, before concluding prediction error either helps or
     doesn't.
  4. Only after (1)-(3), reconsider the feature set or model architecture
     more fundamentally.
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
  done per §2/§3's own rule ("not optional polish"). Building it now would
  mean debugging a classifier already known to be rotation-fragile, so
  probably sequenced after the blocker above, not before.

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
   camera framing anyway.
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
