# Gesture Classifier Pipeline — Specification

> **⚠ Pinch gesture ARCHIVED (2026-08-01): read §13 first.** After the
> pencil-grip corpus reset (§12, below) drove priority-orientation
> cycle-detection recall from ~45% to 77.7% on recorded data, Stage 4 live
> validation still showed too few real pinches/releases detected (fine on
> false positives, weak on recall, worse off `front`) plus a perceptible
> input-lag cost to the UX — a real, live-observed shortfall the recorded
> numbers didn't fully capture. **Decision: archive pinch (may be revisited
> later), pivot to a simpler gesture set** — proximity-based object
> snapping, open-palm rotation, closed-fist release. Full account and the
> new gesture's design: §13. §1–§2 (why rule-based thresholds were
> abandoned, core discipline) and the pipeline stages themselves (§3's
> structure) are still current and still apply to whatever gesture needs a
> **custom-trained** classifier — but §13 also found that two of the three
> new gestures (open-palm, closed fist) may not need this pipeline at all,
> since MediaPipe ships pretrained classifiers for exactly those poses.
> §12 (all subsections) is kept as the full historical/technical record of
> the pinch arc — genuinely useful precedent (the lessons in §12.7
> generalize directly), not superseded/wrong, just not the active gesture.

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

**Built (2026-07-31)**: `LiveGestureDebug.py` (+ `debug.bat`), in
`Local_pc/Movement_with_hand_detection/`. Webcam → `HandLandmarker` (VIDEO
mode, same DSHOW-backend convention as `RecordSession.py`/
`VisionPipeline.py`) → loads `Resources/pinch_classifier_weights.json` →
per-hand forward pass → live overlay of continuous confidence, `pinch_ratio`,
and `PinchEventTracker` state, with onset/offset events console-logged on
transition only. Handles the current windowed winner
(`raw_plus_handcrafted_plus_articulation`) via a real wall-clock (not
frame-count) delta lookup — a small rolling per-hand history buffer finds
the frame closest to `now - DELTA_WINDOW_MS`, which is more robust to a live
capture rate that isn't exactly the 30fps the training/tuning scripts
estimate from recorded-session duration, and doesn't need a live fps
estimate at all. Falls back to `classifier.predict_from_landmarks` for any
future static-representation winner, same as `tune_event_layer.py`'s
dispatch. Smoke-tested (imports, model/weights paths resolve, runs the live
capture loop for several seconds with no traceback) but **not yet visually
validated against a live hand** — that human-in-the-loop check (does it
feel right, does confidence/state track a real pinch the way the recorded
metrics suggest) is the one thing this session couldn't do and is the
immediate next step for whoever picks this up, per this section's own "not
optional polish" rule.

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

## 11. Literature scan (2026-07-31): alternatives to a single fixed event-layer threshold

Written in direct response to a request to search proactively — not after
being pointed at a specific idea (see the `feedback_proactive_literature_
search` memory) — for approaches to the event layer's `palm_away` ceiling
(§3.3.4) beyond §10's context/prior layer. **Not implemented, per explicit
direction the same day**: object-scene integration is still too early, and
near-term effort is moving to the next gesture(s) in Part One's matrix
instead. Logged here purely so the option is on record when event-layer
work is picked up again.

- **CUSUM / Page-Hinkley online change-point detection** (classical
  sequential-analysis/statistical-process-control tests). Both accumulate a
  signal's deviation from its own recent running mean and fire when that
  cumulative sum crosses a bound, rather than comparing the raw signal to
  one fixed magnitude threshold — lightweight, single-pass, designed for
  exactly this streaming/real-time setting. **Directly relevant to
  `palm_away`**: since `pinch_ratio`'s own baseline differs by orientation
  (§3.3.2/§3.3.4's finding, not new here), a change-point test keyed to each
  hand's own recent trajectory would not need a separate hand-picked
  constant per orientation the way the current derivative-agreement design
  does. This is a structurally different route to the same "adapts per
  orientation" goal §10's prior layer targets — and notably **doesn't
  require real object context to condition on**, only the signal's own
  recent history, so it's buildable independently of the object-pipeline
  integration §10 is staged behind. Logged as an option, not started, per
  the direction above.
- **Caramiaux, Montecchio, Tanaka & Bevilacqua, "Adaptive Gesture
  Recognition with Variation Estimation for Interactive Systems"** (*ACM
  Transactions on Interactive Intelligent Systems*, 2014) — a template-based
  recognizer using Sequential Monte Carlo (particle-filter) inference that
  continuously tracks a gesture's progress and variation in real time,
  rather than firing a boolean at a threshold crossing. A genuinely
  different paradigm from this project's onset/apex/offset state machine —
  continuous probabilistic progress-tracking instead of discrete event
  detection — evidence that "adaptive, continuously re-estimated"
  recognition is an established alternative design point in this
  literature, not a novel idea being reached for.
- **Rolling-baseline/adaptive thresholding** (applied signal-processing
  practice and gesture-input patents: periodically recomputing a threshold
  from a window of the signal's own recent range/SNR, rather than a fixed
  constant). The cheapest version of the same idea, and the lowest-effort
  next experiment if this line is picked up before reaching for CUSUM/
  Page-Hinkley's more principled but heavier machinery.

**Status**: all three are options for a future session, not this one —
current priority is the next gesture(s), per direction, with §10 and this
section both left as staged, literature-grounded starting points for
whenever event-layer work resumes.

## 12. Pinch corpus reset (2026-07-31): the open-hand pinch definition doesn't hold up live

Stage 4 (the live debug tool, `LiveGestureDebug.py`) was built and run live
for the first time this session — the actual point of Stage 4, per §3's own
rule, is that held-out recorded-data metrics can't validate what only a live
run can. It found exactly that: with the classifier that scored rotation FP
**2.7%** / recall **0.739** (§3.2.10) and an event layer re-tuned against it
(§3.3.4), live onset/offset events fired far more often and far less
predictably, on both hands, than the recorded numbers implied — a live/
recorded behavior gap the recorded metrics could not have caught, by
construction (the whole reason Stage 4 exists).

**Root cause, per the user's diagnosis**: the pinch gesture itself was
under-specified. It was recorded and trained as "thumb and index close
together, on an otherwise freely-posed hand" — the other three fingers'
pose and thumb-index *proximity* (not contact) were never constrained. This
is consistent with two things this project already found and, at the time,
accepted as unresolved noise rather than fixed at the source:

- §6.1 (`PART_ONE.md`): the other-three-fingers curl gate showed "tail
  overlap with `fist`" even on confirmed-pinch frames — never fully
  resolved, just given a percentile-based margin instead of a clean split.
- §7.2 (`PART_ONE.md`): a fast open-close on a *relaxed, freely-posed* open
  hand has the same timing signature as a genuine pinch, because "closing"
  was defined as *ratio crossing a threshold*, not *fingers actually
  touching*.

Both findings point at the same structural issue: an unconstrained hand
pose gives the model (and, before it, the abandoned rule-based classifier)
a fundamentally ambiguous input distribution. No amount of further
retraining against *that* corpus was going to close the gap — this is a
gesture-*definition* fix, not another representation/hyperparameter round,
and is being treated as one: a new corpus, not a patch on the old model.

### 12.1 New pinch definition

**Pinch = index and thumb tip in contact, with the middle/ring/pinky
fingers held curled closed** (a "holding a pencil" grip) — not merely
thumb-index proximity on a freely-posed hand. Two effects, both aimed
directly at the two findings above:

- Curling the other three fingers **during the pinch pose itself** removes
  their pose as a free variable — `curl_worst_deg` stops being a fuzzy,
  overlapping gate and becomes close to constant during genuine pinch,
  by construction. It also reinforces §3.3.3's finger-articulation feature
  directly: those fingers are now genuinely rigid/motionless during a
  pinch, not just assumed to be.
- Requiring **contact, not proximity**, moves the true-pinch region of
  `pinch_ratio`'s distribution close to its structural floor (near 0)
  instead of "below some threshold," sharpening the boundary against
  incidental closeness during rotation/relaxed poses.

**This is still a trained classifier over continuous features, not a
reversion to the abandoned rule-based approach (§1)** — contact is what
defines the *ground truth label* during recording, the model still learns
from continuous distance/curl/articulation features, same as before.

### 12.2 Corpus reset, mechanics

- Old corpus (163 recordings, all of Stage 1's held-state + event-layer
  sessions) moved from `E:\Python\Recordings for vision_pipeline\` into
  `.../Unsuccessful_grip\` — **archived, not deleted**, but no script reads
  it anymore.
- New corpus recorded under `.../Pencil_style_grip\`. `RECORDINGS_DIR` in
  `RecordSession.py`, `train_pinch_classifier.py`, `tune_event_layer.py`,
  and `analyze_transition_window.py` all repointed there (2026-07-31).
- **Same overall taxonomy as before** (§5's 6-orientation × 3-distance
  grid, cyclic `pinch_cycles`/`pinch_rotate_release` sessions) — but see
  §12.3: the held-state *recording protocol itself* also got a fix this
  session, discovered while re-launching this corpus, not carried over
  unchanged.
- **`rotating_no_pinch` gets a new adversarial variant**: recorded both in
  a normal relaxed hand pose (as before) **and** in a near-pencil-grip
  resting shape (fingers curled, thumb close to but not touching index)
  while rotating — the closest-to-genuine-pinch adversarial case for the
  new definition, not just arbitrary rotation. `open_hand`/`fist`
  themselves are unchanged (they're not the gesture being redefined).
- **All previously-compared representations get re-run against the new
  corpus, not just retrained on top of the old winner** — hand-crafted,
  raw landmarks, `raw_plus_handcrafted`, and
  `raw_plus_handcrafted_plus_articulation` all get re-compared from
  scratch (§3.2's own methodology, applied again), since which one wins
  under a less-ambiguous pose distribution is an open question, not an
  assumption to carry over.

### 12.3 A second, independent bug found while re-launching this corpus: held-state sessions weren't actually held

Before recording the new corpus, an archived `pinch_front` session (nominally
a **held-state** file — every frame was supposed to be unambiguously the
labeled class, per §3 stage 1's own rule) was inspected directly. Its
`pinch_ratio` time series showed **three separate dips**, not one continuous
hold:

```
0.40 0.39 0.43 ... [dip to 0.09] ... 0.43 0.48 ... [dip to 0.18] ... 0.42 0.43 ... [dip to 0.17] ... 0.46
```

i.e. the hand was open/transitioning for roughly **60% of the frames in a
file `train_pinch_classifier.py` treated as 100% positive "pinch."** This
had been happening the entire project history, undetected — a second,
independent source of label noise alongside the pose-ambiguity issue §12.1
fixes, and a plausible further contributor to the recall-vs-rotation-FP
tension documented throughout §3.2.

**Root cause**: the recording protocol never actually distinguished, in
data, between "one continuous hold" (what Stage 3 held-state sessions are
*supposed* to be) and "repeated grip/release cycles" (what
`pinch_cycles`/`pinch_rotate_release` event-layer sessions are *supposed*
to be) — both were just recorded via the same `RecordSession.py --label X`
call and the distinction lived only in the operator's head, not in the
file. It's the same failure shape as §12's main finding: an implicit
convention that silently drifted.

**Fix — a required, explicit `--protocol` flag, saved as data**:
`RecordSession.py` now requires `--protocol {held_state,cyclic}`, shown
live on-screen during both the countdown and capture (so the operator
always sees which one is active) and saved in the output JSON's
`"protocol"` field. `held_state` means one continuous hold, every frame is
the labeled class (used for `pinch_*`/`open_hand_*`/`fist_*`/
`rotating_no_pinch*`); `cyclic` means 3 grip/release repetitions, frames
are not uniformly one class (used for `pinch_cycles_*`/
`pinch_rotate_release`). **Never inferred from the label string** — that's
exactly how the original mixup went unnoticed. `train_pinch_classifier.py`
(`load_sessions`, `rotation_stress_test`) and `tune_event_layer.py`
(`evaluate`) now assert the expected protocol on every file they read and
raise loudly on a mismatch, rather than silently trusting the filename.
`record.bat` takes `<label> <protocol> [duration]` accordingly.

**Recording duration**: uniform 5s for every session, held-state and
cyclic alike (explicit direction, 2026-07-31) — a departure from the old
corpus's longer cyclic durations (8-10s, to fit 3 *deliberately slow*
reps per `PART_ONE.md` §7.2's own lesson about rushing cyclic timing). 5s
for 3 reps is a faster cadence than that lesson recommends; noted here as
a known, explicit tradeoff, not an oversight — revisit if the new cyclic
data shows the same too-fast-to-separate timing problem §7.2 already found
once.

**Cyclic framing convention** (added same session, per direction): to
maximize actual transition coverage inside the compressed 5s window, a
`cyclic` capture **starts already closing into the first grip** (no
neutral pre-roll) and **ends right at the final release** (no neutral
post-roll) — not neutral→pinch→release×3→neutral. Stored as a
`"protocol_note"` field in the saved JSON (not just this document), so the
convention is legible from the data itself.

### 12.3.1 Recording session workflow: prompt and authorization

How an assistant (or anyone else) actually drives a recording session with
the operator, established this session and meant to carry forward
unchanged for future recording rounds:

- **One capture at a time, never chained/unattended.** Each invocation of
  `RecordSession.py`/`record.bat` is its own separate command — never
  scripted as a batch/loop of several captures in a row. The operator
  needs a moment to get into position and mentally prepare for each
  specific label/orientation/distance/rep before the 3s countdown starts;
  chaining captures removes that moment and was explicitly rejected when
  tried.
- **A one-line prompt before every single capture**, stating exactly what's
  about to be recorded: the label, the distance (if applicable — near/far/
  medium), the rep number (e.g. "rep 1/2"), the protocol (`held_state` or
  `cyclic`), and a brief pose reminder (e.g. "pencil grip, hold
  continuously for 5s" or "start already closing into the first grip, 3
  full cycles, end at the final release"). This is not optional framing —
  it's the operator's only cue for what to physically do next, since the
  on-screen countdown text only shows the label/protocol, not orientation
  or distance or rep count.
- **The tool invocation's own permission prompt is the authorization
  gate — no separate verbal "go" is needed.** Earlier in this same session
  the workflow required the operator to type "go" after each one-line
  prompt, then separately approve the tool call; this was later simplified
  (explicit direction) to just showing the prompt and immediately issuing
  the recording command, since the harness's own permission dialog already
  serves as the confirmation step. Don't reintroduce the double-
  confirmation step.
- **Redo mechanics**: if a capture wasn't performed correctly (wrong pose,
  not ready in time, etc.), the operator says "redo the previous
  recording" (or "redo the last two/three," etc.) — the corresponding
  saved JSON file(s) get deleted first, then the exact same label/
  distance/rep/protocol is re-recorded. Never leave a bad capture in the
  corpus silently; always delete before re-recording, and confirm the
  deletion succeeded (recordings live on an external drive, §5, which has
  shown transient access hiccups — verify the file is actually gone, don't
  assume a single `rm` succeeded).
- **Distance-blocked, orientation-cycled ordering**: for the held-state
  6-orientation × 3-distance grid, sessions are grouped **by distance
  first** (all 6 orientations × 2 reps at near, then all 6 at far, then all
  6 at medium) rather than by orientation first — this means the operator
  only physically repositions (changes distance) 3 times total per class,
  not 18 times, since rotating the hand between orientations at a fixed
  distance is far less disruptive than walking closer/farther repeatedly.

### 12.4 Stage 3 retrained against the pencil-grip corpus (2026-07-31): target not just met, essentially ceiling

With the new corpus complete (160 sessions: 36 each pinch/open_hand/fist,
36 `pinch_cycles`, 6 `pinch_rotate_release`, 5+5 `rotating_no_pinch`
variants) and `DELTA_WINDOW_MS` re-swept to 900ms (below), the full
representation comparison (`train_pinch_classifier.py`) was re-run from
scratch, per §12.2's own instruction not to assume the old ranking holds.

**It held, decisively, with far wider margins**: `mlp/raw_plus_handcrafted_
plus_articulation` wins again — rotation FP **0.9%** (was 2.7% on the
archived corpus), recall **1.000**, F1 **1.000**, precision **0.999**.
Every representation's relative ranking is unchanged (hand-crafted-only
variants still ~38-42% rotation FP; `raw_plus_handcrafted` without the
articulation feature reaches only 4.8%), but the winning representation's
absolute numbers moved from "comfortably past target" to "at ceiling."

**Window sweep, done first** (`sweep_prediction_error_window.py`, extended
this session to cover `raw_plus_handcrafted_plus_articulation` — the prior
sweep only covered superseded hand-crafted variants): rotation FP fell
monotonically as the window grew, from 2.5% at the old 300ms default to
**0.9% at 900ms** (recall/F1 reaching 1.000/1.000), with 1200ms showing no
further gain. `features.DELTA_WINDOW_MS` updated 300→900 accordingly — see
that file's updated comment for the full number trail.

**Honest caveat, not a reason to distrust the result but a reason not to
declare victory yet**: F1/recall of 1.000 is a near-ceiling score, and the
session-level held-out test set is small (20 sessions, one per class/
orientation cell) — a real, measured result, not a guess, but exactly the
kind of good-looking number that needs live validation (Stage 4) before
being trusted the way the *archived* corpus's good recorded metrics weren't
(§12's whole premise). Re-validate live before declaring pinch done.

### 12.4.1 Stage 3.3 re-tuned against the new classifier (2026-07-31): specificity solved, sensitivity hits a cadence ceiling, not a threshold ceiling

Re-tuned `tune_event_layer.py` against the retrained classifier (§12.4).
Extended the sweep to also search `event_layer`'s own `window_frames`
(5/8/12/18/24, previously always 5 and never itself re-checked) alongside
the four onset/offset thresholds, since `features.DELTA_WINDOW_MS` tripling
300ms→900ms changes how smoothed the classifier's per-frame confidence
signal is — a live staleness risk for the event tracker's *own*, separate
window, the same shape as the `hidden_units=4` finding.

**Specificity is now excellent**: the best-scoring config (`window_frames=8`,
`onset_conf_rise=0.20`, `onset_ratio_fall=0.12`, `offset_conf_fall=0.20`,
`offset_ratio_rise=0.08` — `Resources/event_layer.py`'s new defaults)
produces **zero false onset/offset events across all 40 `rotating_no_pinch`
hand-sessions** (was 6/3 on the archived corpus).

**Sensitivity did not improve, and the full 405-point grid shows why it
structurally can't from here**: cycle onset/offset means stayed at
~1.18/0.90 (archived corpus: 1.15/1.00) — barely moved, despite the base
classifier going from 2.7%→0.9% rotation FP. Printing the top 10 configs by
raw closeness to the ~3-per-cycle target (ignoring the false-positive
penalty entirely) shows **the ceiling is ~1.3-1.4 onsets/session even at
the most permissive settings tested** — this is not a threshold or window
that further sweeping will fix.

**Root cause, diagnosed not guessed**: `analyze_transition_window.py`
re-run against this corpus (§12.4) measured the pencil-grip pinch's own
transition timing — **median onset (open→pinch) 1165ms, median offset
(pinch→open) 597ms**. A cyclic recording is 5s holding 3 reps (§12.3's
explicit, flagged tradeoff), i.e. ~1.6s budget per cycle. Onset alone
(1165ms) already consumes most of that budget; onset+offset together
(1.76s median) *exceeds* it. The 3 reps very likely run back-to-back with
little or no settled apex/idle time between them, which is exactly the
"too fast to separate" failure mode `PART_ONE.md` §7.2 found once before
and this section's own duration note flagged as a foreseeable risk, not
a surprise.

**This is not a classifier-quality or event-layer-quality problem
anymore — it's a recording-cadence problem**, and per §2's "no heuristic
pile-up" discipline the fix is different data (re-record `pinch_cycles`/
`pinch_rotate_release` at a longer duration, giving real separation
between reps, matching the pre-reset corpus's 8-10s convention), not
another threshold sweep. **Deliberately not done automatically this
session** — re-recording cyclic sessions is a real time cost and a
judgment call on the tradeoff already flagged in §12.3, left for explicit
direction rather than assumed.

### 12.4.3 Systematic failure analysis (2026-07-31): the actual root cause, after two wrong/incomplete guesses

§12.4.1's "recording cadence" root cause was **wrong** — retracted after the
user directly inspected raw index-fingertip landmark data and found three
clean, well-separated dips per `pinch_cycles` session, not back-to-back
transitions. Tracing this further found a **second bug this session**:
`analyze_transition_window.py` used a hardcoded `PINCH_CYCLES_DURATION_S =
10.0`, a leftover assumption from the archived corpus's 10s cyclic
sessions — the pencil-grip corpus's are actually 5.0s, so fps (and every
reported transition duration) was off by exactly 2x. Corrected: median
onset **583ms** (not 1165ms), median offset **299ms** (not 597ms) — fully
consistent with the clean, separated dips actually observed. **Lesson,
stated plainly: don't assert a root cause from a derived statistic without
checking the code that computed it — this one was checked only after the
user's direct data inspection forced it.**

**Targeted feature fix, partial**: tracing one session's confidence signal
frame-by-frame found `thumb_index_articulation` climbing (0.08→0.41) during
a genuinely-still open hold (ratio and curl both flat) — the feature
measures motion *magnitude*, not *direction*, so it can't distinguish
closing from incidental non-converging motion. Added
`raw_plus_handcrafted_plus_articulation_plus_delta` (72-dim representation
+ signed `delta_pinch_ratio`/`delta_curl_worst_deg`,
`Resources/features.py`) — it won Stage 3 again (rotation FP 0.7% vs 0.9%)
and fixed that specific traced instance, but **did not move the aggregate
event-layer sensitivity number** (`analyze_cycle_detection_failures.py`,
new diagnostic script — computes an independent ground-truth cycle count
per session directly from raw `pinch_ratio` via `find_peaks`, compared
against detected onsets). One real, traced fix; not the dominant cause.

**Window-size test, partial**: re-swept `DELTA_WINDOW_MS` retraining from
scratch at each candidate (`sweep_window_for_cycle_detection.py`, new
script), evaluating BOTH the static held-state metric (what the original
900ms sweep used, §12.4) AND real cycle-detection recall restricted to
`front`/`palmin`/`palmdown`/`palmup` (the priority orientations — see
below). Shorter windows help somewhat (100ms: 49.6% priority recall vs
900ms: 43.5%) but the relationship is **not monotonic** (300-450ms are the
*worst* of the whole grid, worse than both shorter and longer) — window
size is a real but insufficient factor, capped around 50% even at the best
setting tested.

**The actual root cause, verified two independent ways**: tracing a
completely-missed `front` session found confidence pinned at 0.99-1.00
almost constantly — including during clearly-open plateaus — only dipping
*during* the real pinch dips (backwards from expected). That session's
resting "not touching" pencil-grip gap sits at `pinch_ratio` ≈ 0.42-0.52.
Checked directly against the held-state `pinch` training corpus's own
ratio distribution (`pinch_front`/`pinch_palmin`): **median 0.18, p90 0.25,
max 0.51** — a rare high-end tail of (presumably loose/imperfect-contact)
positive examples overlaps almost exactly with this hand's resting,
not-touching gap. **The model learned from a few loose "pinch" training
examples that ratio up to ~0.5 can mean contact, and can't distinguish
that from a hand whose natural pencil-grip resting gap also happens to sit
there — because the held-state taxonomy has no explicit negative class for
"pencil-grip shape at rest, not touching."** Only `pinch`/`open_hand`/
`fist`/`rotating_no_pinch` were ever recorded; the specific resting shape
that naturally occurs between cyclic reps was never its own class. This is
a genuine data-taxonomy gap, not a tuning, window, or single-feature
problem — consistent with §2's "fix with better data, not a patch"
discipline, now pointing at a specific, concrete missing class rather than
a guess.

**Not yet fixed — options logged, not decided**: (a) record a new
held-state negative class ("pencil-grip at rest, not touching," 6
orientations) to explicitly teach this boundary, and/or (b) tighten the
`pinch` held-state recording discipline itself so genuine contact examples
never drift into the ambiguous 0.4-0.5 range in the first place. Left for
explicit direction, not assumed.

**Orientation priority, reframed by direct instruction and checked against
literature (not just asserted)**: not every orientation needs to hit the
same bar. `palm_away` and `palm_out` are structurally low-priority — a
real pinch attempt is unlikely to happen there in the first place, and
`palm_away` specifically has a camera-visibility constraint (the index/
thumb are on the far side of the hand from the camera). Checked against
biomechanics literature: the neutral, comfortable forearm position is
~thumb-up (roughly this project's `front`/`palm_in` region); from there,
active range is **~85° supination / ~75° pronation (~157-160° combined)**,
and people spend **50% of daily-living time in just the central 20% of
that range** — i.e., they actively avoid extreme rotations even within the
mechanically available range. `palm_away` requires near-maximal pronation.
Reach-to-grasp literature specifically notes a neutral forearm position is
preferred when approaching/grasping an object, reinforcing that a genuine
grab is unlikely to happen at an orientation like `palm_away`. Separately,
MediaPipe's own documentation and the existence of dedicated "dorsal hand
pose" research (e.g. DorsalNet) confirm back-of-hand-facing-camera tracking
is a distinct, harder problem from standard palm-visible tracking, not an
artifact of this project's data. **Revised target (superseded below,
2026-08-01): `front`/`palm_in`/`palm_down`/`palm_up` should be reliably
discriminated; `palm_away` and especially `palm_out` are accepted as
structurally weaker, not chased to the same bar.**

### 12.4.4 `palm_up` downgraded to the low-priority tier (2026-08-01): a landmark-precision limit, verified two ways, survives a targeted fix

After the `pencil_rest_<orientation>` negative class was recorded (§12.4.3's
fix) and Stage 3/the failure analysis re-run, `palm_up`'s real cycle-
detection recall came back far worse than `front`/`palm_in`/`palm_down`
(12.5% vs 55-72%), and inspecting the raw `pinch_ratio` signal directly
showed why: MediaPipe's hand-detection confidence at `palm_up` was
measurably degraded (mean 0.979, **min 0.61**, 5.7% of frames below 0.9,
vs ≥0.94 min / 0% below 0.9 for every other priority orientation) — a
tracking-quality problem, not a tuning one.

**Tested and ruled out**: switching `pinch_ratio`'s distance calculation
from 3D `world_landmarks` to 2D image-plane `landmarks` (removing the
noisier depth axis) fixed `front` almost perfectly (ground truth became
exactly 3.00 for all 12 hand-sessions, matching the 3-cycle protocol) and
helped `palm_down`, but made `palm_up` *worse* (mean ground truth jumped to
23.9, from noise) — ruling out "wrong coordinate space" as the cause.

**Repositioning worked, partially**: closer camera distance recovered
detection confidence dramatically (diagnostic capture: min 0.94-0.98,
0-1.6% below 0.9, both static and during real pinch/release motion) —
confirmed camera framing/distance, not an inherent angle limit, was
degrading confidence. All 5 `palm_up` classes across the corpus (30
files — `pinch`/`open_hand`/`fist`/`pencil_rest`/`pinch_cycles`) were
deleted and re-recorded at the corrected distance; one `open_hand_palmup`
file needed a further redo after coming back with the spread-fingers pose
clipping frame edges (zero detections) — final corpus confidence is
in line with the rest of the corpus (`pinch_palmup`/`fist_palmup`/
`pencil_rest_palmup` all ≥99% mean, `open_hand_palmup` 3.6% below 0.9,
comparable to `open_hand_palmout`'s already-accepted 2.6% baseline).

**But the cyclic (motion) ground truth stayed broken even after the fix**:
re-running the failure analysis against the corrected corpus, `palm_up`'s
raw `pinch_ratio` signal during actual pinch/release cycles still never
approaches true contact (checked directly: oscillates noisily in the
0.2-0.85 range) *despite* detection confidence staying high throughout
(mean 0.99) — a different failure mode than the confidence problem just
fixed. **Conclusion, verified two independent ways (2D-projection test,
then the confidence-fixed re-recording): `palm_up` has a genuine
landmark-*precision* limit for the fine thumb/index-tip separation
specifically, distinct from and not resolved by the detection-*confidence*
fix.** Further recording attempts at this orientation are not expected to
close this gap.

**Final target, superseding §12.4.3's revised target above**: `front`/
`palm_in`/`palm_down` are the reliably-discriminated priority tier;
`palm_up` moves to the same accepted-weaker tier as `palm_away`/`palm_out`
(not chased to the same bar). Stage 3.3 event-layer tuning and any live
validation should treat `front`/`palm_in`/`palm_down` as the trustworthy
priority signal.

**Same literature check, forward-looking for rotation gestures (§10's
staged design)**: the ~157-160° combined pronation-supination range means
a future rotation gesture only needs to handle roughly this span, not a
full 360° — consistent with the ~180-200° estimate that prompted the
check, slightly more conservative per the literature's own number. Relevant
once rotation (Part One matrix row 7) is built.

### 12.5 What this means for the rest of this document and for Part One

- Every Stage 3/3.3 number above this section (§3.2.1–§3.2.10, §3.3.1–
  §3.3.4) describes the **archived** corpus and is historical evidence of
  method, not a current result — re-derive, don't assume, once the new
  corpus exists.
- §10/§10.1 (context/prior layer) and §11 (event-layer literature scan)
  are unaffected in substance — both were already staged for later,
  independent of which corpus the base classifier is trained on.
- The approved Part One plan (grab acquisition/arbitration, release,
  translation, depth proxy, rotation — `PART_ONE.md` §3 rows 3–7) is
  **paused**, not abandoned: it depends on a live-validated pinch signal,
  which is exactly what this reset is for. Resume it once Stage 3/3.3/4 are
  redone against `Pencil_style_grip/` and Stage 4 is live-validated again.

### 12.6 Final pipeline state after the full 2026-08-01 follow-through (pre-Stage-4)

Continuing directly from §12.4.4, three more things changed before Stage 4
live validation:

**Winner-selection logic redesigned, not just tolerance-patched**. The
`min(rotation_fp_pct)`-based selection in `train_pinch_classifier.py`
picked a badly worse model **twice** in immediate succession: first a
0.0% vs 0.1% rotation-FP gap (one frame of noise) beat a 34-point recall
advantage; widening the tolerance to 1.0 point then let a 1.0% vs 2.4% gap
do the same thing to a 30-point F1 advantage. The tolerance band just
relocates this failure mode rather than fixing it — chasing the
**global minimum** of a secondary metric always lets some low-primary-
metric candidate win by an arbitrarily small margin. Replaced with a
**ceiling**: `ROTATION_FP_CEILING = 5.0` — any candidate at or under the
ceiling is "robust enough," and the highest-F1 candidate among those wins
outright, full stop. No more chasing the theoretical minimum. See §12.7
below for the generalized version of this lesson.

**`DELTA_WINDOW_MS` re-swept 900ms→200ms** (`sweep_window_for_cycle_
detection.py`, against the corrected classifier): the effect was much
larger than the pre-`pencil_rest`-fix sweep suggested (§12.4.3's own
100ms-vs-900ms numbers were 49.6%/43.5%, both weak) — priority-orientation
cycle-detection recall went from 72.3% at 900ms to 96.4% at 200ms, at the
cost of rotation-FP roughly tripling (0.8%→2.9% on the sweep's own quick
single-representation check). 100ms scored even higher (101%) but nearly
quadrupled rotation-FP (3.8%); **200ms chosen as the deliberate balanced
point**, not the max-recall extreme — a judgment call, not a computed
optimum.

**Full pipeline re-run end-to-end at the new window** (required — a window
change invalidates every downstream fit): Stage 3 representation
comparison re-run at 200ms (winner: `mlp/raw_plus_handcrafted_plus_
articulation`, rotation_fp=2.4%, F1=0.902, recall=0.927); Stage 3.3
event-layer re-tuned to match (`window_frames=8`, `onset_ratio_fall=0.12`,
others unchanged — near-zero false positives: 1 across 20 negative
sessions). **Final, apples-to-apples confirmed numbers**:

| orientation | ground truth | detected | recall |
|---|---|---|---|
| `front` | 3.00 | 2.58 | 86.0% |
| `palmdown` | 1.50 | 1.17 | 78.0% |
| `palmin` | 2.42 | 1.67 | 69.0% |

Average 77.7% across the priority tier — up from this session's starting
point (~43.5–49.6%), and more evenly distributed across orientations than
an earlier intermediate reading (which had `palmdown` disproportionately
high at 94.7% while `front` lagged at 66.7%, an artifact of comparing
numbers generated from different classifier/event-layer combinations
rather than one consistent pipeline state — see §12.7's "apples-to-apples"
lesson).

**Not yet done**: Stage 4 live validation via `debug.bat` — the gate that
actually matters, per this whole section's own repeated lesson that good
recorded-data numbers have failed live twice already.

### 12.7 Lessons learned, generalized for the next gesture (grab/release/translate/depth/rotate)

These are written to be reusable beyond pinch — read this section before
starting Stage 3/3.3 work on any future gesture in the Part One matrix.

1. **Detection confidence and landmark precision are separate failure
   modes; a fix for one does not fix the other.** `palm_up` had both: low
   MediaPipe hand-detection confidence (fixable by camera distance/
   framing) AND, independently, imprecise fine-grained landmark
   positioning for the specific measurement that mattered (thumb-index
   gap) even once confidence was fixed. When an orientation or pose
   underperforms, check the raw `score` field AND the raw feature signal
   (e.g. `pinch_ratio` time series on a held-still recording) separately —
   don't assume fixing one explains or fixes the other.

2. **Camera distance/framing tolerance is pose-dependent, not just
   orientation-dependent.** The same corrected distance that fixed
   compact poses (fist, pencil-grip) at `palm_up` caused a *different*
   problem for the open-hand pose (spread fingers clipping the frame
   edge, one file with zero detections). When adjusting camera position
   to fix one class, re-verify EVERY class recorded at that position, not
   just the one that motivated the change.

3. **Model/config selection between two competing metrics needs a
   ceiling on the secondary metric, not a minimum with a tolerance
   band.** If metric A (e.g. recall/F1) is what you actually care about
   and metric B (e.g. a robustness/false-positive rate) is a constraint,
   selecting by `min(B)` — even with a tie-break tolerance — will always
   let an arbitrarily-small B-improvement override an arbitrarily-large
   A-cost, because tolerance bands just relocate where the cliff is.
   Select by "max(A) among candidates with B under an absolute ceiling"
   instead. This generalizes past this specific classifier: any pipeline
   with two competing objectives should ask "is B here a target to
   minimize, or a constraint to satisfy?" and design selection
   accordingly.

4. **A hyperparameter that depends on another hyperparameter must be
   re-tuned every time the one it depends on changes — not just
   re-checked for staleness independently.** The event tracker's
   `window_frames` depends on how smoothed the classifier's confidence
   signal is, which depends on `DELTA_WINDOW_MS`. Changing
   `DELTA_WINDOW_MS` without re-tuning `window_frames` left a stale,
   mismatched config that produced numbers that looked worse than either
   piece actually was — always re-tune the dependent parameter in the
   same pass as the parameter it depends on, not as a separately-scheduled
   task.

5. **A static held-out metric (F1/recall/rotation-FP on individual
   frames) can be structurally blind to real transition-timing behavior
   for any cyclic/event-based gesture.** Build a real, classifier-
   independent ground-truth signal (e.g. `find_peaks` on a raw geometric
   feature) before trusting that good static numbers mean the event layer
   will actually fire correctly on real transitions. This matters for
   every future cyclic gesture (grab/release cycles, rotation reversals),
   not just pinch.

6. **Verify a ground-truth-extraction method itself before trusting a
   "bad" number it produces.** `palm_up`'s ground-truth cycle count was
   itself unreliable in two different ways (undercounting via
   insufficient dip depth, then overcounting via signal noise) before the
   underlying tracking issue was even diagnosed — inspect the raw signal
   directly (don't just trust an aggregated statistic) whenever a number
   looks surprising, in either direction.

7. **When comparing "before" and "after" numbers, confirm both came from
   the exact same pipeline configuration.** This session generated two
   different sets of "current" cycle-detection numbers from mismatched
   classifier/event-layer-parameter combinations at one point, purely
   from re-running scripts with stale hardcoded constants in between
   pipeline changes — always re-verify every hardcoded parameter in every
   diagnostic script matches the currently-active model/config before
   reporting a number as authoritative.

8. **Not every pose/orientation needs the same bar, and that decision
   should be explicit, literature-checked where possible, and revisited
   as new evidence arrives** — `palm_up` moved tiers mid-session on new
   evidence (§12.4.4). Don't treat an orientation-priority decision as
   permanent; re-open it if a later diagnostic contradicts the original
   reasoning.

## 13. Pinch archived (2026-08-01); pivot to snap / open-palm rotate / closed-fist release

> **See `Claude/GAME_RULES.md` for the plain-language rules inventory** —
> this section documents design/rationale/build history; that file lists
> only the confirmed rules themselves, updated every time a new one is
> added. Check both: this section for *why*, `GAME_RULES.md` for *what*.

### 13.1 Stage 4 live-validation result — why pinch is being archived, not just re-tuned again

Live-tested via `debug.bat` against the final pipeline state from §12.6
(200ms window, `mlp/raw_plus_handcrafted_plus_articulation`, re-tuned event
layer, 77.7% avg priority-orientation recall on recorded data). Direct,
observed result:

- **False positives: rare** — consistent with the recorded rotation-FP
  numbers staying low throughout this arc.
- **False negatives (missed pinches/releases): frequent**, and
  **noticeably worse off the `front` orientation** — consistent with the
  recorded numbers (`palmin`=69%, weaker than `front`=86%), but the live
  *feel* of a missed grab/release is a harder failure than the aggregate
  percentage suggests, since a game interaction needs each individual
  attempt to register, not just a good hit-rate averaged over many.
- **A small but perceptible detection lag** between the real gesture and
  the reported event — small in absolute terms, but the kind of latency
  that measurably degrades direct-manipulation UX (well-established in
  HCI latency literature: even sub-100ms delays are detectable and
  degrade a sense of direct control). This is a structural property of
  the current design (the event tracker needs a `window_frames`-sized
  lookback of confidence/ratio history before it can confirm an
  onset/offset — see `Resources/event_layer.py`), not a bug fixable by
  more tuning.

**Decision**: archive the pinch classifier (all code, corpus, and trained
weights kept, not deleted — genuinely reusable if pinch is revisited
later) and pivot to a simpler gesture set that doesn't share pinch's core
difficulty (discriminating a *fine, low-amplitude, easily-occluded*
finger-contact signal from incidental motion). This is consistent with
§12.7's lesson #8: a bar that turns out to be structurally hard to clear
is a legitimate reason to change strategy, not just push harder on the
same one.

### 13.2 State-of-the-art check for the replacement gesture set (2026-08-01)

Per the standing "search literature proactively" discipline
(`feedback_proactive_literature_search` memory), checked three things
before committing to the new design:

**1. MediaPipe already ships pretrained `Open_Palm`/`Closed_Fist`
classifiers.** MediaPipe Tasks' **Gesture Recognizer** (distinct from the
Hand Landmarker this project already uses) outputs one of 7 built-in
gesture labels per detected hand: `Closed_Fist`, `Open_Palm`,
`Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, `ILoveYou` (plus
`Unknown`), trained on ~30K real-world images plus rendered synthetic hand
models. **This means open-palm and closed-fist detection may not need
this document's Stage 1-3 custom-training pipeline at all** — a
significant simplification opportunity, and consistent with the intuition
that these are coarse, high-amplitude poses (a fully open hand vs. a
fully closed fist), structurally easier to discriminate than pinch's fine
near-contact measurement. **Still subject to this project's own
hard-won Stage 4 discipline**: try the built-in recognizer, live-verify
it (per §12.7 lesson #6 — don't trust a claim, even Google's own, without
checking it against this project's actual camera/lighting/hand setup),
and only fall back to a custom-trained classifier (reusing
`RecordSession.py`/`train_pinch_classifier.py`'s infrastructure,
generalized past pinch-specific label parsing) if the built-in one proves
insufficient live. [Gesture recognition task guide — MediaPipe / Google AI
Edge](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer).

**2. Proximity-based "snap" grabbing is an established, validated VR/HCI
interaction technique**, not a simplification that sacrifices UX quality.
Literature on hand-tracking object manipulation in VR describes the
"virtual hand technique" with pose-snapping as increasing presence and
usability, and proximity/psychological-closeness cues as reducing
interaction demand versus more indirect techniques (e.g. raycasting) —
directly relevant since this project's UX goal is the same "reach out and
grab" interaction. This validates the "snap when hand position is close
to the object" trigger as a reasonable, literature-backed design, not an
ad-hoc shortcut. [Controller-Free Hand Tracking for Grab-and-Place Tasks
in Immersive Virtual Reality](https://www.researchgate.net/publication/346966176_Controller-Free_Hand_Tracking_for_Grab-and-Place_Tasks_in_Immersive_Virtual_Reality_Design_Elements_and_Their_Empirical_Study),
[Evaluating Hand-tracking Interaction for Performing Motor-tasks in VR
Learning Environments](https://www.researchgate.net/publication/352866232_Evaluating_Hand-tracking_Interaction_for_Performing_Motor-tasks_in_VR_Learning_Environments).

**3. Quaternion-based rotation tracking (already the existing design —
`PART_ONE.md` §2, `Specification.md` §7.5) is confirmed correct and
doesn't need to change.** Orientation-control and robotics/graphics
literature consistently confirms quaternions avoid gimbal lock (a
property of Euler-angle decomposition specifically, not of rotation
itself) and are the standard representation for this exact problem —
nothing found that changes or improves on the orthonormal-frame-from-
landmarks → quaternion → slerp approach already specified. [A quaternionic
approach to teaching 3D rotations and the resolution of gimbal
lock](https://arxiv.org/pdf/2511.04452), [Quaternion Rotation in 3D: A
Solution to Gimbal Lock](https://medium.com/@ratwolf/quaternion-3d-rotation-32a3de61a373).

**4. MediaPipe's monocular depth (`world_landmarks` `z`) is
literature-confirmed unreliable for absolute positioning.** Directly
relevant to "how to measure hand position in the camera-view direction":
validation literature explicitly notes MediaPipe Hands' positional
landmarks are "not suitable for augmented or mixed reality applications"
in terms of depth accuracy for monocular setups — confirming
`PART_ONE.md` §2's existing decision (depth proxy via apparent hand span,
not raw `z`, and no Z-axis translation) was already correct, not a
compromise to revisit. [Hand tracking for clinical applications:
validation of the Google MediaPipe Hand (GMH) and the depth-enhanced
GMH-D frameworks](https://arxiv.org/pdf/2308.01088).

### 13.3 New gesture design: snap / translate / open-palm rotate / closed-fist release

Replaces pinch as the primary manipulation gesture. Reuses
`PART_ONE.md` §2's already-correct architecture decisions (sticky grab,
shared-registry arbitration, image-space translation, depth-proxy-not-
raw-z, quaternion rotation) — only the **trigger conditions** change, not
the underlying object-manipulation architecture.

- **Hand position** (new concept, replaces "pinch midpoint" throughout):
  the palm-center point — centroid of `wrist(0)` + the four non-thumb
  MCP joints (`index_MCP(5)`, `middle_MCP(9)`, `ring_MCP(13)`,
  `pinky_MCP(17)`). A standard palm-center approximation, more stable
  than the wrist alone (which is offset from the palm) or any single MCP
  (asymmetric). Used in **image-space X/Y** for translation, per §13.2
  point 4 above (no Z-axis translation, matching the existing
  depth-proxy-only decision).
- **Snap (acquisition)**: pure proximity trigger — no pose/gesture
  precondition. When a hand's position enters grab-radius of an unowned
  object, snap it (claim in the same shared-registry arbitration scheme
  `PART_ONE.md` §2 already specifies for pinch — reused unchanged, just
  triggered by proximity instead of a pinch rising-edge).
  - Snap should probably be *inert* if that hand is currently
    closed-fist (so nothing weird happens if a hand loitering in a fist
    passes near an object without intending to grab) — worth deciding as
    that step is built, not blocking design now.
- **Translate**: while snapped, object position = mapped(hand position),
  X/Y only — identical mechanism to the old pinch-midpoint version, new
  input signal.
- **Rotate**: while snapped **and** the hand is classified `Open_Palm`,
  track hand orientation via the existing quaternion design (`PART_ONE.md`
  §2/§7.5) and slerp the object's orientation toward it. Gating rotation
  on `Open_Palm` specifically (rather than applying it whenever snapped)
  avoids rotation jitter/noise while the hand is transitioning through
  other shapes (e.g. mid-way into closing a fist) — **this gating choice
  is a design inference, not explicitly stated by direction; confirm or
  adjust once live-tested.**
- **Un-snap (release)**: `Closed_Fist` detected on a hand currently
  holding a snapped object → release: clear ownership, freeze object at
  last position, hand returns to idle. Same freeze-in-place semantics
  `PART_ONE.md` §2 already specifies for pinch release.
- **Both hands can each independently snap/translate/rotate/release their
  own object** — no fixed hand-to-object pairing, same "either hand, any
  unowned object" arbitration already designed for pinch.

### 13.4 Open questions, to resolve empirically once building starts (not blocking design)

- Exact grab-radius value (likely scaled to object size — same open item
  `PART_ONE.md` §5 already flagged for pinch, unresolved, still open).
- ~~Whether `Open_Palm`/`Closed_Fist` from MediaPipe's built-in Gesture
  Recognizer are reliable enough live~~ — **checked and answered, see
  §13.5: no, reverted.**
- ~~Whether snap should be blocked while closed-fist (see §13.3's inert-fist
  note)~~ — **moot (2026-08-01, later conversation): open-palm/closed-fist
  detection (row 2) is now PARKED, not being actively pursued.** The
  mechanism was built and worked once, but was reverted along with the
  Gesture Recognizer integration (§13.5); revisit only if row 2 is
  explicitly un-parked later.
- ~~Whether rotation should be gated on `Open_Palm` specifically~~ —
  **resolved (2026-08-01, later conversation): rotation stays permanently
  ungated**, not just pending a working open-palm signal — row 2 being
  parked makes this the settled answer, not a temporary gap.
- ~~Depth (Z-axis) translation and/or the old depth-proxy scale/color
  effect~~ — **superseded (2026-08-01, later conversation).** Depth-proxy
  scale/color (`PART_ONE.md` §2's last bullet, row 6 of the matrix) stays
  dropped, but Z-axis translation itself is no longer just "not mentioned"
  — it has a confirmed design now, matrix row 9, full detail §14.3.

### 13.5 Build progress (2026-08-01) — proximity snap/translate live-verified; MediaPipe's built-in Closed_Fist reverted

**Phase A (hand position, proximity snap, translation, tracking-loss
release) built and live-verified.** New combined debug tool
`LiveSnapDebug.py`/`debug_snap.bat` (temporary, single-window: video +
hand landmarks + a semi-transparent cube overlay in one OpenCV window,
replacing the old troubleshooting need for the depth-proxy color effect —
directly requested, and confirms translation visually against the real
hand position without needing that old technique). Production code
(`Resources/HandsTriggeredActions.py`, `Resources/CubeWindow.py`) updated
in parallel with matching logic.

**A same-frame ordering bug was found live and fixed**: releasing a cube
(tracking lost) and re-snapping it (the other hand's check) happened in
one combined per-hand pass, so a cube could instantly "jump" to the other
hand the instant one hand disappeared, whenever the other hand was
already within grab radius — the release and the re-snap were two steps
of the same tick with no ordering guarantee against each other. Fixed:
split into two passes (release everyone who needs releasing, across both
hands, *then* snap/translate), and any cube released this frame is
excluded from this frame's snap pass — a cube can only be re-claimed
starting the next frame at the earliest, never the same tick as its
release. Applied identically in both the production module and the debug
tool (kept in sync by hand, documented in both files' docstrings).

**Phase B (`Open_Palm`/`Closed_Fist` via MediaPipe's built-in Gesture
Recognizer) tried, live-tested, and reverted.** Downloaded
`gesture_recognizer.task` (Google's official MediaPipe model repository,
`storage.googleapis.com/mediapipe-models/gesture_recognizer/...`) and
wired it into `LiveSnapDebug.py`, replacing `HandLandmarker` (the
Recognizer conveniently returns gestures + both landmark coordinate types
in one call). Wired `Closed_Fist` to block snap and to trigger release,
per §13.3/§13.4's confirmed design. **Live result: closed-fist detection
was unreliable across different hand positions/orientations — a lot of
missed fist closures.** This is exactly the failure mode §13.2 flagged as
a risk ("still subject to Stage 4 discipline... don't trust a claim
without checking it") — the built-in classifier is evidently tuned to a
narrow set of canonical poses, not usable as-is for this project's
purpose (the hand needs to be trackable as closed-fist across the same
range of positions/orientations pinch needed, not just head-on).
**Decision: revert the Gesture Recognizer integration** (both files back
to `HandLandmarker`, bug fix retained) **but keep `gesture_recognizer.task`
on disk** — its `Thumb_Up` class may be useful for a later, different
game interaction, unrelated to this open-palm/closed-fist need.

**Not yet decided**: the replacement approach for `Open_Palm`/
`Closed_Fist` detection. Candidates, not yet evaluated: (a) a simple
geometric heuristic reusing `features.py`'s existing finger-curl-angle
functions (`curl_worst_deg` etc., already built for pinch/fist
discrimination in the archived corpus) — plausible since fist/open-palm
are coarse, large-amplitude poses that a hand-crafted rule might
discriminate robustly across orientations without needing MediaPipe's
canonical-pose-biased classifier; (b) a custom-trained classifier via
this document's own Stage 1-3 pipeline (proven to work, but the heavier
option, and pinch's own difficulty was in a much finer-grained
measurement than fist/open-palm need). Evaluate (a) first — cheaper to
try, and directly matches this project's literature-grounded intuition
that these are structurally easier poses than pinch, only unreliable in
MediaPipe's *specific* pretrained classifier, not necessarily inherently
hard to detect geometrically.

**PARKED (2026-08-01, later conversation)**: `Open_Palm`/`Closed_Fist`
detection (matrix row 2) is not intended to be pursued for the moment —
neither candidate (a) nor (b) above is being evaluated now. This is a
deprioritization, not a rejection of either candidate's merit; revisit if
explicitly requested again. Its two former dependents have already moved
on without it: rotation (row 7) stays permanently ungated by design;
release (row 4) now relies on the hand-open-quick-release gesture (§14.2)
as its sole deliberate trigger instead of `Closed_Fist`.

### 13.6 Thumb-outward snap restriction (2026-08-01) — new rule, built and live-verified

Direct request, added to the current (Phase A) snap/translate build: a
hand should not be able to snap an object while oriented thumb-outward
(back of hand facing the camera), with a specific exception for
continuity across a release/re-grab in that same orientation. Full rule
text: `Claude/GAME_RULES.md`.

**Detection approach**: a purely 2D geometric signal, no wire-protocol or
model changes needed — the sign of the 2D cross product of
`(index_MCP - wrist) × (pinky_MCP - wrist)` in the already-available
mirrored pixel-space landmarks, mirrored again per handedness for a
consistent sign across both hands (their landmark geometry is chirally
opposite). **Calibrated live before being trusted** (per §13.5's own
lesson, not repeating the Closed_Fist mistake): a calibration-only build
showed the raw sign/a tentative "A"/"B" label on screen, the operator
showed palm then back of hand for both hands, and confirmed the mapping
(positive, mirrored-for-Left = thumb-outward) before the label was wired
into any gating logic.

**State machine**: two bits of per-hand state — `last_known_thumb_outward`
(the most recent orientation reading while the hand WAS detected, persists
through frames where it's lost, so a tracking-loss release still has an
orientation to record) and `thumb_outward_snap_allowed` (the armed/
disarmed exception: armed on release with whatever orientation held at
that moment, disarmed the instant the hand is next seen thumb-inward).
Built and live-verified in both `LiveSnapDebug.py` and
`Resources/HandsTriggeredActions.py` (kept in sync), confirmed working
end-to-end (block-from-neutral, allow-immediately-after-same-orientation-
release, re-block-after-showing-thumb-inward) by the operator, 2026-08-01.

### 13.6.1 Correction (2026-08-01, later conversation): production's thumb-outward was actually INVERTED — root-caused and fixed

**The "confirmed working end-to-end" claim above was wrong for
production specifically**, discovered live: "in the production pipeline,
it seems you inverted the logic for the grab: I can grab only if the
hands are with the thumbs facing outwards: this is the opposite of the
debug pipeline where rightfully the grab was done when the thumbs were
facing inwards." The `_is_thumb_outward` formula itself was byte-for-byte
identical in both files (ruled out first, not assumed) — the actual cause
was upstream, in the wire protocol.

**Root cause, confirmed by reading the code (not guessed)**:
`VisionPipeline.py` runs MediaPipe detection on the RAW, un-mirrored
camera frame (no `cv2.flip` anywhere in that file), then mirrors the
pixel/world landmark COORDINATES afterward for display consistency
(`remap_keypoints`/`remap_world_keypoints`, `invert_x=True`). But
MediaPipe's own Left/Right handedness classification assumes an
already-mirrored ("selfie") input by convention — fed an un-mirrored
frame, it reports the TRUE anatomical hand, the opposite of what the
mirrored display shows. `hands_visualizer.py` took that raw handedness
label with no correction (`"handedness": handedness[0].category_name`).
Every OTHER hand behavior (snap, translate, rotate, release) is
handedness-symmetric and was unaffected — `_is_thumb_outward` is the ONE
place with an explicit `if handedness == "Left": cross = -cross`
chirality correction, so it was the only visible symptom.
`LiveSnapDebug.py` never had this problem because it flips the frame
BEFORE detection, so MediaPipe's handedness comes out already
display-consistent — this is exactly the same class of unverified
mirroring risk `remap_world_keypoints`'s own docstring already flagged
for `world_landmarks` ("has NOT been live-verified yet... confirm the
rotation's sign/axis feel live"), just materializing on the 2D pixel/
handedness side instead, and for a different consumer (thumb-outward, not
rotation).

**Fix**: `hands_visualizer.py` gained `_mirror_handedness()`, applied at
the single source point where handedness first enters the pipeline (both
the on-screen debug label and the `"handedness"` field every downstream
packet — "hands" AND "hands_world" — reads from), rather than patching
`_is_thumb_outward` or any other individual consumer. Verified by reading
the full call chain (`VisionPipeline.py`'s `extract_hand_by_type(...,
"Left")`/`"Right"` lookups → `hands_visualizer.py`'s `all_hands_coords` →
this fix) to confirm this is genuinely the single source, not one of
several. Compiles and the swap function smoke-tested (`Left ↔ Right`).
**Not yet independently live-tested** — recommend the user re-run
`launch.bat` and confirm thumb-inward now (correctly) permits grab in
production, matching the debug tool.

### 13.7 Rotation while snapped (2026-08-01) — built in the debug tool, relative not absolute, two noise filters, one open TODO

**Confirmed direction**: rotation is **UNGATED** (active for any snapped
hand regardless of pose) rather than gated on `Open_Palm` — a pragmatic
choice since `Open_Palm` detection has no working implementation (§13.5);
a gate can be added later. Built entirely in `LiveSnapDebug.py` first
(fast iteration — that tool already runs `HandLandmarker` in-process and
gets `hand_world_landmarks` for free, no wire-protocol change needed to
prototype). **Not yet ported to production** (`HandsTriggeredActions.py`/
`CubeWindow.py`) or the wire protocol (§4's `world_landmarks` gap still
applies there).

**Quaternion math is hand-rolled**, not via scipy: scipy is only an
incidental transitive dependency of mediapipe's `jax` in this project's
venv, not a declared requirement, so not something to build a core
mechanic on. Gram-Schmidt orthonormal frame → quaternion (Shepperd's
method, numerically stable across all rotation angles) → shortest-path
slerp. Offline-sanity-checked (identity round-trip, a known 90° rotation,
slerp endpoints/midpoint) before ever touching the camera.

**Rotation is RELATIVE to the hand's orientation at grab time, not
absolute** — direct request, superseding an initial absolute-follow
attempt that made the cube visibly pop/snap-rotate to match whatever
twist the hand happened to be at the moment of the grab. Fixed via a
grab-time baseline pair stored on the cube (`grab_hand_orientation`,
`grab_cube_orientation`) and applying the hand's world-frame rotation
*delta* since grab on top of the cube's own orientation at grab time. On
the grab frame itself the delta is identity by construction — no pop.

**Two independent noise-filtering mechanisms**, found necessary by live
testing (a naive slerp-only or single-filter approach was insufficient):
1. **Reactive raw-jump filter** (`RAW_ORIENTATION_GLITCH_DEG = 60`):
   compares each frame's raw hand-orientation reading only to the
   IMMEDIATELY PRECEDING raw reading (never a lagged/smoothed value),
   substituting rather than freezing when the jump exceeds a threshold no
   real hand can physically achieve in one ~33ms frame. Went through two
   live-caught bugs before landing here: v1 compared against the cube's
   own (lagging) slerped orientation, which created a self-reinforcing
   trap (one rejection made the cube fall further behind, making the next
   frame's gap look bigger, causing MANY consecutive frames to be
   rejected instead of a brief blip); v2's fix still had the substituted
   reference reassigned to the SUBSTITUTED (i.e., stale) value instead of
   the frame's true raw reading, silently never advancing on a flagged
   frame and reproducing the same stuck-trap one level down — this
   specifically caused PROLONGED (not brief) glitch flags whenever the
   hand settled into a genuinely different but stable pose. Both found via
   live testing, not by inspection, and fixed with offline regression
   tests added for each (including a "transitions to a new stable pose"
   case that the v2 bug's fix specifically had to pass).
2. **Proactive geometric confidence gate** (`GEOMETRIC_DEGENERACY_NORM =
   0.035`), added after root-causing the pitch-vs-yaw asymmetry below —
   checks the actual numerical conditioning of the frame construction
   directly (before any jump ever shows up downstream), substituting when
   the orthogonalized second axis's pre-normalization length falls below a
   data-derived threshold.

**Root-caused the "chaotic" rotation report (2026-08-01) with recorded
data, not guesses** — built a new ad hoc recorder, `RecordRotationDebug.py`
+ `record_rotation_debug.bat` (imports directly from `LiveSnapDebug.py`
rather than duplicating, so it records exactly what that tool computes;
saves locally under `rotation_debug_recordings/`, NOT the external-drive
corpus dir, since this is diagnostic data, not training data):
- User reported rotation was chaotic specifically with the back of the
  hand facing the camera, and separately that a **pitch** crossing (hand
  tipping through edge-on about the screen's horizontal axis) had the
  problem while a **yaw** crossing (about the vertical axis) did not.
- A no-slerp test (slerp temporarily disabled entirely, `cube.orientation
  = target_quat` directly) proved the chaos was a faithful, unmodified
  reflection of the raw signal — not a slerp artifact, not the
  relative-delta math, not the (then-only) raw-jump filter.
- Geometric analysis of the recorded `world_landmarks` pinned the exact
  mechanism: the original frame (`wrist→index_MCP`, `wrist→pinky_MCP`)
  uses two vectors that both point from the wrist toward opposite ends of
  the SAME knuckle row — only moderately non-parallel even at rest. A
  PITCH rotation sweeps exactly that knuckle-row axis edge-on to the
  camera at the crossing, driving the two vectors toward collinearity
  right when the hand is edge-on; normalizing then divides by a near-zero
  orthogonalized component, amplifying ordinary landmark noise into wild
  swings. A YAW rotation instead foreshortens the wrist→fingertip axis,
  which the frame never used at all — explaining the asymmetry exactly.
  Quantified: across a full recording, this conditioning norm correlated
  with the per-frame rotation jump at r=-0.52; the most-degenerate
  quartile of frames averaged a 36.3° jump vs. 2.2° for the
  best-conditioned quartile (16x).
- **Fix**: switched to `index_MCP→pinky_MCP` (width axis, taken directly,
  larger magnitude, one less wrist-noise term) and `wrist→middle_MCP`
  (length axis) — much closer to genuinely orthogonal at rest, giving far
  more margin before collinearity. **Chirality was explicitly verified
  preserved** against real recorded data before shipping (211/211 frames,
  palm-normal dot product with the old construction averaged 0.991 — not
  flipped) specifically so yaw/roll, which the user confirmed were
  already working correctly, would not regress; the vector order
  (`index_MCP→pinky_MCP`, not the reverse) is chosen deliberately for this
  reason and must be re-verified the same way before ever being swapped.
- **Measured improvement**, matched recordings of the same pitch-sweep
  test, back-toward-camera pose only: mean per-frame jump 20.6°→12.1°;
  frames jumping >30° in one frame 14-18%→4% (4-5x fewer); frames jumping
  >60° 6-10%→3% (2-3x fewer). A real, substantial, data-confirmed
  improvement — not a complete elimination.

**Open TODO (2026-08-01, direct request)**: rotation quality is still
reportedly poor specifically with the **back of the hand** facing the
camera — i.e. this is NOT a new/different failure mode, it's the SAME
pitch-crossing pose already diagnosed and fixed above, just not fully
eliminated. Consistent with the data: the fix substantially reduced the
frequency and severity of large per-frame jumps in that pose (see the
"measured improvement" bullet above) but did not bring it to zero — a few
percent of frames still exceed the raw-jump threshold.

**Three alternative geometric constructions tested against already-
recorded data (2026-08-01), all NEGATIVE — this avenue is reasonably
exhausted for now**:
1. Thumb-based fallback vector (`wrist→thumb_CMC`, `wrist→thumb_MCP`,
   `wrist→thumb_TIP` in place of `wrist→middle_MCP`) — literature-motivated
   (the thumb is the one MediaPipe landmark NOT coplanar with the rest of
   the palm; Horn's classic absolute-orientation method documents that
   coplanar point sets are mathematically degenerate for full 3D
   orientation and need an out-of-plane reference). Tested against the
   exact 15 frames the current fix flags as degenerate in a real
   recording: CMC and MCP were degenerate on 15/15 (mean conditioning
   0.023-0.036 vs. the current pair's 0.074 overall — substantially
   WORSE, not better); TIP only resolved 8/15 and was roughly on par
   overall. Root cause: anatomically, the thumb emerges near the wrist on
   the index side, so its direction from the wrist isn't much more
   orthogonal to the knuckle-row width axis than the wrist itself is —
   `wrist→middle_MCP` ("straight up the palm") was already the
   better-conditioned choice, independent of viewing angle. Also
   independently flagged as a reliability risk: a robustness study
   testing MediaPipe Hands specifically found thumb occlusion causes far
   larger accuracy drops than occluding other fingers (~20% recall drop on
   FreiHand, ~40% on Panoptic) — the thumb is a documented weak point in
   this exact model, for reasons unrelated to viewing angle (self-occlusion
   against the palm/other fingers, more kinematic freedom than the other
   MCPs).
2. PCA-fit width axis (best-fit line through all 4 non-thumb MCPs via
   first principal component, instead of the raw `index_MCP→pinky_MCP`
   two-point vector) and/or a centroid-based length axis (`wrist→mean(4
   MCPs)` instead of `wrist→middle_MCP`) — motivated by "average out
   individual-landmark noise using more points." Tested against the same
   recording: conditioning values were statistically indistinguishable
   from the current simple pair (differences of ~0.002-0.005, within
   noise) at every one of the 15 degenerate frames, and nearly identical
   overall (mean 0.073-0.075 across all variants). **This is the more
   informative negative result**: if the residual noise were independent
   per-landmark measurement error, averaging over more points should have
   visibly reduced it — it didn't, at all, and all variants rise and fall
   together in lockstep at the same frames. This means the degradation is
   a SYSTEMATIC, CORRELATED distortion of the whole knuckle-row
   reconstruction at that viewing angle (consistent with genuine reduced
   monocular depth-disambiguation at edge-on views), not independent noise
   on any single landmark — no choice or combination of landmarks *within
   the palm plane* can fix this, since they're all subject to the same
   correlated degradation together.

**Prospective directions for further improvement (2026-08-01, literature
review, NOT YET IMPLEMENTED)** — since all three tested approaches worked
*within a single frame* (picking/combining landmarks), and none helped,
the productive next axis is *across frames* (temporal), which hasn't been
tried yet:

- **Literature context — why a human doesn't perceive this the same way a
  per-frame geometric estimator does**: Ernst & Banks (2002, *Nature*)
  showed human sensory integration is reliability-weighted (Bayesian/MLE)
  — multiple cues are combined in proportion to their inverse variance, so
  a momentarily-degraded cue is automatically down-weighted rather than
  trusted at face value. Wolpert's forward-model work (and Friston's
  predictive-coding/active-inference framework) shows the brain regulates
  perception and action against a *predicted* sensory state (from an
  efference copy of the motor command / a forward model of ongoing
  motion), not raw instantaneous sensory input — this is specifically
  valuable when sensory feedback is noisy, delayed, or has gaps, exactly
  this project's situation at an edge-on crossing. Johansson's biological-
  motion-perception work (point-light displays) shows humans reconstruct
  plausible body structure from extremely sparse/ambiguous visual data by
  applying strong learned priors on which configurations and motions are
  kinematically plausible for a human body — the visual system doesn't
  entertain wildly implausible instantaneous readings the way an
  unconstrained per-frame estimator can. Note one important asymmetry that
  bounds how far this analogy goes: a person moving their OWN hand also
  has proprioception plus an efference copy of the motor command — a
  non-visual channel with no camera-viewing-angle ambiguity at all, which
  this vision-only pipeline has no equivalent of and cannot replicate in
  software; the achievable parallel is specifically the
  temporal-prediction/reliability-weighting mechanism, not full parity
  with biological perception.
  Sources: [Predictions not commands: active inference in the motor
  system](https://link.springer.com/article/10.1007/s00429-012-0475-5);
  [Humans integrate visual and haptic information in a statistically
  optimal
  fashion](https://www.researchgate.net/publication/11550808_Humans_integrate_visual_and_haptic_information_in_a_statistically_optimal_fashion)
  (Ernst & Banks 2002); [Biological motion
  perception](https://en.wikipedia.org/wiki/Biological_motion_perception)
  (Johansson).
- **Directly translatable engineering parallel, and already standard CV
  practice for exactly this problem** (not just a neuroscience analogy):
  Kalman/Extended-Kalman/Unscented-Kalman filtering is the established
  technique for monocular hand-pose tracking specifically under depth
  ambiguity — literature confirms EKF has been used "to estimate the pose
  of the hand... even when using only a monocular camera and without any
  depth information." The concrete, incremental proposal: maintain a
  short-window estimate of the hand's recent angular velocity from the
  last few ACCEPTED good frames; each frame, predict this frame's expected
  orientation by extrapolating that velocity (a constant-angular-velocity
  motion model); then blend the raw geometric reading with that
  prediction, weighted by real-time reliability — using
  `conditioning_norm` (already computed every frame) directly as the
  inverse-variance-style reliability signal, exactly mirroring Ernst &
  Banks' MLE cue-weighting. This upgrades the current binary
  accept/substitute gate into a continuous, principled fusion that can
  distinguish "the raw signal disagrees because of noise" from "the raw
  signal disagrees because the hand genuinely accelerated," which a fixed
  jump threshold cannot. This is a materially different, untried axis (temporal
  integration) from the three geometric (spatial, single-frame) attempts
  above, so there's real reason to expect it could help where those
  plateaued — but per this project's standing discipline, build small and
  verify against recorded data (the existing `rotation_debug_recordings/`
  captures plus fresh ones) before trusting it, the same way every other
  claim in this section was checked rather than assumed. Source:
  [Predictive Tracking in Vision-based Hand Pose Estimation Using
  Unscented Kalman
  Filter](https://www.intechopen.com/books/human-robot-interaction/predictive-tracking-in-vision-based-hand-pose-estimation-using-unscented-kalman-filter-and-multi-vie).
- **Kinematic-plausibility prior** (softer version of the current hard
  `RAW_ORIENTATION_GLITCH_DEG` threshold): Johansson-style body-constraint
  priors suggest replacing the fixed 60°/frame cutoff with a proper
  probabilistic plausibility weight derived from measured human wrist
  angular-velocity statistics, feeding into the same reliability-weighted
  fusion above rather than a hard reject/accept boundary.
- **Out of scope but worth naming**: the fundamental reason binocular
  human vision doesn't hit this exact ambiguity is stereo depth — an
  actual second camera or an IMU on the hand would structurally resolve
  it the way no amount of single-RGB-camera processing can. Not pursued
  here (this project's whole premise is a single webcam), but worth
  remembering as the ceiling on what pure software can achieve.

**Predictive filter IMPLEMENTED and live-tested (2026-08-01)** — the
Kalman-style proposal above was built (`HandOrientationFilter`,
`_predictive_filter_step`, `_reliability_alpha`, replacing BOTH earlier
binary filter mechanisms entirely) and offline-verified against recorded
data before ever touching the live tool (no-pop-at-grab preserved, healthy
rotation stays fully raw-trusted with zero added lag, tracking-loss reset
confirmed clean, an engineered degenerate frame correctly drives
reliability to 0 instead of freezing) — see `LiveSnapDebug.py`'s module
comment above `CONDITIONING_ALPHA_LOW` for the full implementation
account. Same-recording analysis showed it eliminating >30°/>60° jumps
entirely in the back-toward-camera pose. **Live test result: a real but
INSUFFICIENT improvement** — user reports rotation quality with the back
of the hand facing the camera is "slightly better but not yet solving the
issue." **TODO remains OPEN.** Kept in place (it's a measured net
improvement, not a regression), but this is now four attempts (three
geometric, one temporal) that have each helped without fully resolving
it — worth treating the residual as looking increasingly like a genuine
floor of this pipeline's single-monocular-RGB-camera setup (see the
"out of scope" stereo/IMU note above) rather than assuming a fifth
software-only attempt will fully close the gap. If picking this up again:
check whether `ROTATION_SLERP_FACTOR` (raised 0.25→0.35 the same session,
for unrelated general responsiveness) changed the felt severity before
concluding anything new about the filter itself, and consider whether
further tuning of `CONDITIONING_ALPHA_LOW`/`CONDITIONING_ALPHA_HIGH`
(not yet tuned beyond the initial data-derived guess) or a wider
angular-velocity averaging window (currently a single-frame delta, no
smoothing of `omega` itself) are worth testing before reaching for a
fifth fundamentally different approach.

**Ported to production (2026-08-01)** — `HandsTriggeredActions.py`/
`CubeWindow.py` and the wire protocol (`VisionPipeline.py`→`Server.py`→
`PythonApp_Main.py`, new `"hands_world"` packet type, 21×3×2=126 floats,
sent before `"hands"` each frame) now carry the exact same design verified
in `LiveSnapDebug.py`: relative-to-grab quaternion math, the
better-conditioned landmark pair, and the predictive/reliability-weighted
filter, ported essentially verbatim rather than re-derived. Offline-
verified end-to-end with synthetic landmark data before ever touching a
real camera (same discipline as everything else in this section): snap +
no-pop-at-grab confirmed; rotation tracking a moving synthetic target
converged to EXACTLY the theoretically-predicted steady-state slerp lag
(0.000° error against the closed-form `Δ×(1-α)/α` formula) — a strong
signal the ported math is bit-for-bit equivalent to the debug tool's,
not just superficially similar. `CubeWindow.py`'s orientation gizmo
(`_draw_orientation_gizmo`) was also ported and smoke-tested (opens,
draws, closes cleanly).

**NOT YET tested against a real camera or the real wire protocol** — only
offline/synthetic verification so far. One specific item is genuinely
new, untested code with no prior verification anywhere: the world-landmark
mirroring/x-negation convention in `utils_for_remapping_coordinates_and_
output_formatting.py`'s `remap_world_keypoints` (`invert_x=True` default).
`LiveSnapDebug.py` never needed this — it runs detection on an
already-mirrored frame, so MediaPipe's own output was already mirror-
consistent there. The production pipeline mirrors pixel coordinates AFTER
detection on an un-mirrored frame, so world landmarks need an explicit
x-negation to represent the same visually-mirrored hand — this negation
was added by inference/reasoning, not verified live. If rotation feels
mirrored/inverted on any axis once live-tested, check this exact function
first, same "verify the sign convention live before trusting it"
discipline as the thumb-outward rule's calibration (§13.6).

**Real 3D cube rendering (2026-08-01, direct request, live-confirmed
working)** — once rotation was confirmed working end-to-end, the
flat-square + axis-gizmo placeholder no longer made sense: replaced with
actual rotating 3D cubes in `CubeWindow.py`'s `_draw_cube_3d` (8 local
vertices rotated by the cube's orientation quaternion, weak-perspective
projected, 6 faces backface-culled then painter's-algorithm depth-sorted
farthest-to-nearest). Each cube's 6 faces are 3 opposite-pair color
families, one side of each pair a computed darker shade (`_darken`) of the
other, not hand-picked separately — guarantees the pairing stays
consistent. **Large** cube: yellow/violet/turquoise, exactly 2x the
**small** cube (green/red/blue) in every dimension. Cube identifiers
renamed "blue"/"red" → "large"/"small" (the old names stopped describing
anything once every cube got 3 face colors and different sizes).
Renaming surfaced a real, now-fixed issue: grab radius previously used a
single shared `cube_window.cube_size`, which stopped making sense once
cube sizes actually differ — `_try_snap` now scales grab radius to EACH
candidate cube's own size (`PART_ONE.md` §5's long-open "grab radius
scaled to object size" item, resolved as a side effect). Offline-verified
(sizes, face-color pairing, no-pop-at-grab and rotation-vs-theory checks
all re-run and passing after the rewrite).

**Morphing bug found live and fixed (2026-08-01)**: the first version of
`_draw_cube_3d` reused the axis-gizmo's per-vertex scale formula
(`1/(1+K*rz/half)`), which is only ever safe for a point at distance
<= half from the origin (true of a gizmo's axis endpoints, NOT of cube
corners, whose distance from the origin is the body diagonal,
`half*sqrt(3)`). Verified numerically: at some rotations a corner's
denominator went NEGATIVE (worst case -0.039 with K=0.6), flipping that
vertex to the wrong side of the cube -- exactly the reported "vertices
moving so faces morph and the cube doesn't stay a cube." **Fixed** with a
proper, physically-correct perspective projection instead: a virtual
camera at a FIXED distance (`CUBE_PERSPECTIVE_DISTANCE_RATIO = 3.0` times
cube.size, comfortably beyond the half-diagonal) using the standard
pinhole-camera divide `scale = camera_distance / (camera_distance + rz)`.
Verified via a full rotation sweep (9 axes x 180 angle steps, both cube
sizes): the projection scale never drops below ~0.71x camera_distance
(nowhere near the old bug's zero-crossing), and small rotation steps
produce correspondingly small, continuous screen movement (max ~1.7px per
2° step, no discontinuities) — ported the same fix into `LiveSnapDebug.py`
(same design, cv2 primitives instead of pygame) so the combined video +
landmarks + transparent-cube-overlay debug view (`debug_snap.bat`) stays
an accurate, synchronized stand-in for production while it's still in
active use for testing (direct request 2026-08-01: keep this debug view
around for now, remove only once final production no longer needs
landmark-level debugging).

### 13.7.1 Filter audit (2026-08-01, later conversation) — keep for now, TODO: re-test for redundancy after future improvements

Direct request: audit all accumulated filters/smoothing across the
gesture pipeline (rotation, translation) and strip anything that didn't
measurably contribute to solving rotation quality or "Object Jump
Correction" (§14.1.4), or that only helped marginally at the cost of
complexity/lag — the stated goal being to keep the game logic pure and
simple, not accumulate filters that don't earn their keep.

**Audit result, translation: nothing to strip.** Checked the actual
shipped code, not just what was discussed — the Object Jump Correction
investigation's candidate mitigations (exclude out-of-bounds candidate
landmarks + renormalize + freeze-if-too-few-remain; light temporal
smoothing on the combined position) were never merged into
`LiveSnapDebug.py`/`HandsTriggeredActions.py`. The first was built and
verified against real data to make no measurable difference and was
correctly discarded before shipping (§14.1.4); the second was proposed
but left conditional on data that never arrived, and was never built.
Today's translation mechanism is exactly the weighted-average + no-pop
residual, nothing layered on top.

**Audit result, rotation: one real filter exists** (the predictive/
reliability-weighted mechanism — "Attempt 3" above `CONDITIONING_ALPHA_LOW`),
with no dead code left over from its two earlier, abandoned attempts
(both were fully replaced in place, confirmed via grep — no orphaned
`GEOMETRIC_DEGENERACY_NORM`/`RAW_ORIENTATION_GLITCH_DEG` constants remain,
only historical comments referencing them). This filter's impact is
**measured and substantial, not marginal**: eliminates all `>30°` jumps
(4%→0%) and all `>60°` jumps (3%→0%) in the recorded back-toward-camera
test data, mean jump 11.4°→7.8° — on top of an earlier geometric fix that
had already reduced it from ~20.6°→12.1°. `ROTATION_SLERP_FACTOR` (basic
easing, not bug-specific — already confirmed via a direct live test to
not be the noise source, §13.7 above) was flagged separately as an
ordinary responsiveness knob, not "accumulated complexity," and isn't in
scope of this audit.

**Decision (direct request): KEEP the predictive rotation filter for
now.** The back-of-hand rotation-quality TODO remains open (this filter
substantially reduces but doesn't eliminate it), so removing it now would
be a real regression, not a simplification of dead weight. **New TODO,
added to the future-improvements queue**: once future improvements land
(candidates: "Object Jump Correction," Z-axis translation / the proposed
startup depth-calibration step, or anything else that touches monocular
depth ambiguity), **re-test whether this filter has become redundant** —
if a later fix resolves the underlying depth-ambiguity problem at its
source, the filter may no longer be pulling its weight and should be
re-audited with the same cost-benefit discipline used here, not kept out
of inertia.

**TRIGGER NOW IDENTIFIED (2026-08-02, perception-spec integration — §15,
and `PERCEPTION_LAYER_SPEC.md` A6)**: that "re-test for redundancy" TODO
is no longer open-ended. **M6's quaternion UKF with anisotropic covariance
subsumes this filter** — it is a hand-rolled, simplified instance of
exactly what M6c + M7 describe (a predictive angular-velocity model
blended against the raw reading, weighted by a conditioning-derived
reliability signal). **When M6 ships, this filter is deleted, not kept
alongside it** — two overlapping predictive filters is precisely the
accumulation this audit exists to prevent. Its removal is a listed
deliverable of M6 (merged queue item 2.3), justified by an A/B diff rather
than assumed. Related: M6b's `observability` overlaps with this filter's
`conditioning_norm` — reconcile into one metric, don't ship both.

### 13.8 Mesh-generic 3D rendering (2026-08-01) — the cube is a placeholder for future imported 3D objects

Direct request, immediately after the morphing-bug fix above was
confirmed live: "make sure what you have done for the 3d representation
of the cube can be later applied to any 3d object which is imported into
the scene. The cube should act as a placeholder for 3d complex objects
which will be imported later on." This was a real architectural gap in
the first version — `_draw_cube_3d` hardcoded the cube's 8 vertices and 6
quad faces directly (`CUBE_VERTICES`/`CUBE_FACES` module constants) and
looked up colors via a cube-specific `{"+x": color, "-x": color, ...}`
dict keyed by axis-aligned face direction — none of which would extend to
an arbitrary imported mesh (different vertex/face counts, triangulated
faces, real per-face materials, no "+x"-style axis-alignment).

**Refactored (both `CubeWindow.py` and its `LiveSnapDebug.py` mirror) to
separate geometry from rendering**, so an imported object later needs
only a new geometry constructor, not a single change to the
rendering/projection/culling/sorting code:

- **`MeshFace`**: `vertex_indices` (a tuple of ANY length — 3 for a
  triangle, 4 for a quad, so this scales directly to real imported meshes,
  which are almost always triangulated), a local outward `normal` (for
  backface culling after rotation), and its own `color` stored directly on
  the face (not looked up via an axis-keyed dict) — an imported mesh's
  faces will carry real per-face colors/materials the same way.
- **`Mesh`**: local-space (unit-scale, ±1-ish per axis) `vertices` +
  `faces`. This is the piece meant to be swapped out later.
- **`_make_cube_mesh(color_x, color_y, color_z) -> Mesh`**: the ONE
  cube-specific construction function left in either file — builds the
  placeholder cube's 8 vertices / 6 quad faces (darker-opposite color
  pairing per `_darken`, unchanged from §13.7's cube-color work). A future
  "import a 3D object" step needs an equivalent factory (e.g. loading an
  OBJ/glTF file into vertices+faces+materials) — nothing else changes.
- **`Cube.mesh: Mesh`** replaces the old `face_colors` dict field. `Cube`
  keeps its name (every object today IS cube-shaped) but is really "the
  snappable scene object, whatever `mesh` says it looks like."
- **`CubeWindow._draw_object_3d`** (renamed from `_draw_cube_3d`) and
  `LiveSnapDebug.py`'s mirrored `_draw_cube_3d` now iterate `obj.mesh.faces`
  generically — rotate `obj.mesh.vertices`, perspective-project (same
  fixed-camera-distance formula as §13.7's bug fix), backface-cull via each
  face's own rotated `normal`, depth-sort, draw each face's own `color`.
  Zero cube-specific logic remains in either drawing function.

**Verified concretely, not just asserted**: after the refactor, all
previously-passing checks (sizes, color pairing, no-pop-at-grab,
rotation-vs-theory, rigidity) were re-run and still pass in both files.
Additionally, in both `CubeWindow.py` and `LiveSnapDebug.py`, a completely
different `Mesh` (a 4-vertex, 4-triangular-face tetrahedron, arbitrary
per-face colors) was assigned to a live `Cube` instance at runtime and
rendered successfully with **zero changes to any rendering code** — direct
proof the pipeline is genuinely object-agnostic, not just cube-shaped code
that happens to also technically accept other inputs.

**What a real future "import a 3D object" step would still need** (not
built, just the scoped remaining gap): (1) a loader for an actual 3D file
format (OBJ is the simplest — plain text, vertex/face lists, easy to
parse without a new dependency; glTF is more capable but needs a real
parser library) that produces a `Mesh`; (2) if imported meshes are large
(hundreds+ of triangles), the current O(faces) per-frame Python loop and
painter's-algorithm sort may need a faster depth-sorting or GPU-backed
approach — not a concern for a cube (6 faces) or anything of similarly
modest complexity, but worth flagging before importing something detailed;
(3) real per-face colors from the imported file's own materials, instead
of `_make_cube_mesh`'s procedural light/dark color-family assignment.

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

## 15. Perception-layer spec integrated (2026-08-02) — the current direction

A design spec for the **hand-perception stack below the gesture layer** was
written by the owner and integrated into the pipeline on 2026-08-02:
**`Claude/PERCEPTION_LAYER_SPEC.md`**. Read it alongside this document —
this file remains the authoritative record of *what failed and why*; that
one is the *forward* design intended to fix it.

**Why this is a direction change worth flagging.** Everything in §13-§14
treated MediaPipe's output as the signal and built gesture logic directly
on it, fixing failures one at a time as they were found live. The
perception spec reframes MediaPipe as a **noisy sensor** and inserts an
estimator layer (L0-L6) between it and the gesture logic, with a versioned
`HandState` contract at the boundary. Several open TODOs in this document
are consequences of that missing layer rather than independent bugs.

**The merged build queue is `PART_ONE.md` §3.1** — the single ordered TODO
list covering both this document's TODOs and the spec's modules. It
supersedes §14's build order and the handoff's own queue.

**Amendments made on integration** (full log in the spec's §0.1 — the
short version, because these correct claims a reader of the spec alone
would get wrong):

- **A1 — retargeted from JavaScript to Python.** The spec was written
  against `gestureConfig.js`/Three.js. That does not exist: `Web/` holds
  only Part Zero-bis, and every Part One gesture is Python. Perception is
  built in `Local_pc/`; `HandState` v2 becomes the versioned **socket wire
  contract**, which doubles as the cross-platform contract a mobile
  rebuild reimplements against.
- **A2 — M5a/M5b are already built.** `_is_thumb_outward()`'s signed cross
  product is byte-identical to the spec's signed-palm-area cue, and its
  per-handedness negation is exactly the chirality factoring. New work is
  DR-1, the `K` fixture test, `edgeOnMeasure`, and DR-2.
- **A4 — M6a is already satisfied.** No Euler angles have ever been in the
  estimation path (`PART_ONE.md` §2 forbids it). Verify and tick.
- **A5 — M4 is scoped to occlusion/outliers, not the pitch crossing.**
  §13.7 recorded that per-landmark selection and averaging schemes are
  statistically indistinguishable at the degenerate frames, because the
  residual is a *correlated* whole-knuckle-row distortion. M6c's
  anisotropic covariance is the mechanism for that failure; M4 is not.
  Do not read a null M4 result there as an implementation failure.
- **A6 — M6 subsumes `HandOrientationFilter`; deleting it is a
  deliverable.** This closes §13.7.1's open "re-test the filter for
  redundancy after a more fundamental fix lands" TODO with a concrete
  trigger.
- **A7 — M8a (palm anchoring) is NOT adopted.** It contradicts §14.1's
  shipped, verified, live-confirmed mechanism, and the pipeline docs
  govern. It is logged as an **A/B candidate** to be measured once M6/M9
  land — because the stated reason for rejecting a palm-anchored design
  (a 2D/3D coordinate mismatch) will no longer hold then. **Do not modify
  §14.1 before that A/B runs.** The spec's anti-pattern #6 ("never anchor
  to fingertips") is downgraded accordingly.
- **A8 — M9 is the concrete fix for §14.1.1's yaw/palm-sinking
  limitation**, whose recorded remedy was an unspecified "startup Z-axis
  calibration." M9's foreshortening correction, using M5a's
  `edgeOnMeasure` as the `|cos θ|` term, is that idea made specific.
- **A9 — §14.1.4 Object Jump Correction now has a fix path.** It was
  absent from the spec's own mapping. DR-1 removes the per-frame identity
  decision that is its structural cause; M4's χ² innovation gate would
  reject the recorded 509 px excursion. Re-test after Phase 2 rather than
  treating it as independent work.
- **A10 — kill-criterion (binding).** Every module must show measured
  improvement on the M0 metrics via replay A/B, or be **reverted**. This
  is the spec's own §7.1 rule elevated to a removal rule, and it is what
  reconciles the spec's substantial machinery with the owner's standing
  preference against accumulating filters that do not earn their keep. The
  precedent is already set: the first Object Jump Correction fix attempt
  was built, measured, found to make no difference, and discarded rather
  than shipped (§14.1.4).

**Two items the spec surfaces that are game-design decisions, not
perception work** — both need the owner, and neither should be introduced
as a side effect of building a module:

1. **M10.7 proposes a ~400 ms grace period on tracking loss.**
   `GAME_RULES.md` rule 2 currently drops the object immediately, and that
   behaviour is built and live-verified. Changing it is a rule change.
2. **§14.3's 3D snap gating is underspecified**: what happens when
   `depthValid` is false at the moment of snap — fall back to 2D
   proximity, or refuse to snap? Not decided.



## 16. THE BLOCK REPRESENTATION (owner design, 2026-08-04) — the current direction

**Owner's formulation**, recorded verbatim because the framing is the
contribution: *"what really matter on the hand are 6 blocks: the palm, and each
of the 5 fingers arcs. The information is contained there, not in the individual
positions of each knuckle landmark... There is no added value to know all the
specifics of a finger knuckles, and each finger may be grouped as an arc which is
more or less extended or bent."*

    palm    : transform -- 2D position, rotation quaternion, scale (z = 0 for now)
    fingers : 5 arcs, each an offset child of the palm transform plus a single
              "arc deployment" scalar (how extended / how bent)

### ⭐ Why this is adopted: the corpus already measured both halves

This is not a plausible idea being tried — it is the representation the data has
been pointing at all along. Both claims were measured **before** they were
proposed:

| claim | measurement | where |
|---|---|---|
| "the palm is one block" | palm rigidity **2.76 mm**, already at target, vs 13–32% CV on distal bones | §0.2 |
| "a finger is an arc, not 3 knuckles" | `dot(PIP axis, DIP axis)` **0.0% negative over ~29,000 hand-frames, min +0.41, p05 +0.69** — PIP and DIP *always* co-flex | §0.16 (item 1.5) |

That second number is the strong one: a finger's bend is essentially **one degree
of freedom**, not three, with an enormous empirical margin. The "arc deployment"
scalar is exactly that quantity.

It also has a name and a home in the literature — **postural synergies**, queue
item 5.1 / M3b, where ~2–3 components are published as explaining most grasp
variance. This is a structured, interpretable instance of it.

**And it reframes three open failures as one cause.** T4 (yaw/palm-sinking), T3
(Object Jump) and N12 (held cube jumps as the hand crosses the horizontal) are
all cases where **noisy per-landmark detail leaked into a quantity that should
have come from the rigid part of the hand**. The block model makes that leak
structurally impossible rather than filtering it afterwards — which matters,
because §0.18 showed filtering, gating and constraining all fail here.

### Scope — deliberately narrow (owner, 2026-08-04)

- **Applies to the GRAB, ROTATE and TRANSLATE signals only.** Future gestures may
  legitimately need raw landmarks; this is not a global replacement for them, and
  the landmark stream stays available.
- **The thumb stays as RAW LANDMARKS for now.** Its CMC is a saddle joint with
  two coupled axes, so "more or less bent" does not describe opposition — the
  same reason M3a excluded it (§0.16). What to do with the thumb is deferred, not
  answered.
- **Stdlib, numpy-free, no side effects, and transportable to the web port** —
  same contract as `palm_geometry.py` / `hand_identity.py`, with golden vectors
  before the port exists (the discipline established in queue U3, which caught a
  real banker's-vs-half-up rounding divergence).

### Why this is the right substrate for prediction

Predicting **6 low-DOF blocks** is far more tractable than 21 noisy points, and
the parent/child structure means palm motion is not re-predicted per landmark.

⭐ **The specific hypothesis worth testing, which item 1.6 lacked:** the recorded
Object Jump is MediaPipe reporting *a different physical hand* under the same
label (§14.1.4). So a teleport should show a large palm displacement **together
with a discontinuous jump in the arc vector** (a different hand, in a different
pose), whereas genuine fast motion shows large palm displacement with
**continuous arcs**. That is a two-channel signature, and it is exactly what
single-channel position innovation could not provide — 1.6 was measured to reject
**4 real fast movements per teleport caught, at every threshold**, because at
this input envelope a teleport and a fast movement are the same signal
(§0.17).

⚠ **This hypothesis is NOT yet evidence.** It must be proven the way 1.6 was
disproven: **classify what gets rejected, never merely count it** (§0.18's
binding rule). A richer state may separate them; that is a measurement, not a
conclusion.

### 16.1 B1 built, B2 measured (2026-08-04) — the anchor claim holds, the outlier claim does not

`Resources/hand_blocks.py` + `analysis/b2_block_separability.py`. Palm
centroid/scale verified against `hand_identity` **29,164/29,164**.

**⭐ THE DECISIVE RESULT — anchor stability, §14.1's 9 points vs the palm**
(frame-to-frame anchor movement in palm widths):

| band | n | §14.1 p50 | §14.1 p95 | palm p50 | palm p95 |
|---|---|---|---|---|---|
| edge-on (<0.15) | 353 | 0.065 | **0.925** | 0.058 | **0.699** |
| near (0.15–0.35) | 617 | 0.083 | 0.425 | 0.065 | 0.390 |
| open (>0.35) | 28,144 | 0.038 | 0.235 | 0.027 | 0.169 |

**The palm is a quieter anchor by ~25–30% in every band.** That is real, it is
consistent, and it is the first positive result for the block model — **B4 (the
3.3 A/B) is worth running on this evidence.**

⚠ **But it does NOT remove the edge-on spike**: both anchors still jump ~4× when
the palm goes edge-on (palm p95 0.169 → 0.699). So **N12 would be REDUCED, not
eliminated**, by palm anchoring. The residual is §0.18's documented floor — at
edge-on the palm reconstruction itself collapses, so there is no quieter point on
the hand to anchor to. DR-2's freeze pattern remains the right answer for that
band, not a better anchor.

**⚠ THE TWO-CHANNEL OUTLIER HYPOTHESIS (B6) IS NOT SUPPORTED BY THIS DATA.**

- **Teleport separability: INCONCLUSIVE, not negative.** Only **3 teleports
  survive in 29,164 frames**, far too few to test anything — and that is itself a
  finding: `build_v2` replays DR-1, **DR-1 is the fix for Object Jump**, so the
  identity-teleport population is largely already gone. It is indirect support
  for T3 being closed.
- **At edge-on, arcs give no distinctive signature.** Both channels degrade by
  about the same factor (palm p95 0.158 → 0.320; arc p95 0.104 → 0.185), so
  "palm moves while arcs stay continuous" does not hold in the band that matters
  for N12.

**Consequence for the plan**: the *representation* earns its place on the anchor
result; the *outlier gate* does not yet have evidence and must not be built on
the strength of the idea. Testing it properly needs a corpus that still contains
teleports — the `Position_during_rotation/translation_pivot_jump_test4` take is
the named reproduction, and it is currently **unreadable from Python** in this
environment (PermissionError on that subfolder; PowerShell reads it fine).

### 16.2 What happens on rejection — the coasting policy (owner question, 2026-08-04)

*"if a next set of frames is outside this probabilities distribution, the flag can
be activated and the cube position is inferred from prediction until the measured
frames return to the correct probabilities."*

Adopted, with one change that is not negotiable: **"until it returns" is
unbounded, and unbounded coasting is the cascade that already failed here.**
§0.13.3: a rejected frame makes the filter coast, the prediction drifts further
from the measurement, so the next frame fails too — **one bad frame booked up to
8 rejections**, and the resulting statistic was mistaken for a weak motion model
and had to be retracted (§0.15). The policy below keeps the inference and bounds
the coast.

**1. Rejection is PER CHANNEL, not per frame.** The block decomposition makes
this possible and it is the main advantage over 1.6's all-or-nothing gate. The
channels are independent quantities — arc extension is a scale-free intra-finger
ratio and does not depend on the palm transform, and vice versa. So:

- fingers confused at a pitch crossing (**N12**) → arcs rejected, **measured palm
  kept**;
- identity teleport (**T3**) → palm position/quaternion rejected, **measured arcs
  kept**.

Rejecting the whole hand because one finger is wrong throws away good data.

**2. A rejected channel is INFERRED from its own prediction** — the windowed
extrapolation, not the last value — and is flagged `valid = False`.

**3. ⚠ THE COAST IS CAPPED AT 2 CONSECUTIVE FRAMES PER CHANNEL.** On the third,
the measurement is **force-accepted** and that channel's estimator is
**re-seeded** (derivative history cleared, residual scale reset). Rationale: a
sustained disagreement means *our model is stale*, not that the sensor is wrong
three times running. Two frames at 24 fps is ~83 ms.

**4. Full reset on tracking loss or run break** — same contract as
`PalmFacingTracker.reset()`. A new track must never be judged against the old
one's trajectory.

**5. ⚠ CONSUMERS SPLIT (S3, binding — Apple ships exactly this).**

| consumer | uses |
|---|---|
| rendering / cube attachment | the output transform, inferred or measured — this is what keeps the cube smooth |
| **grab / release state machine** | **measured state only.** While `valid = False` it must HOLD — take no new snap and trigger no release — rather than decide on inferred data |

A prediction artifact must never latch into a gesture. This mirrors DR-2's
existing `orientation_valid` contract, which already freezes rather than acting
on an unobservable sign.

**6. The estimator never learns from an inferred value.** Only accepted
measurements enter the history and the residual scale. Feeding predictions back
in is how a filter convinces itself it is right.

### 16.3 B3′ built and evaluated (2026-08-04) — INCONCLUSIVE on detection, and the reason matters

`Resources/block_tracker.py` + `analysis/b3_block_gate_eval.py`. Built with every
fix identified against 1.6: windowed least-squares derivatives (not a raw
two-sample velocity — S2(a), the dominant error source), second order, seven
channels, per-channel rejection, adaptive residual scale with absolute floors,
2-frame coast cap, history trained on accepted measurements only.

Evaluated on the `Position_during_rotation` takes — the only corpus containing a
real Object Jump (`jump_test4`) — with rejections **classified**, not counted.

| config | teleports caught | real flagged |
|---|---|---|
| blocks, σ=4, order 2 | **1/1** | 6/16 |
| order 1 (velocity only) | 1/1 | **4/16** |
| order 2 (velocity+accel) | 1/1 | 6/16 |
| window 3 / 5 / 9 | 1/1 | 7 / 6 / 7 of 16 |
| suppress edge-on <0.35 | 1/1 | 5/16 |

**⚠ n = 1 TELEPORT. Detection performance is NOT MEASURABLE from this, and the
"ratio" is one event divided by sixteen.** It is reported as inconclusive.

What the data *does* say, on the false-positive side (n=16, still small):

- The gate flags **~⅓ of real fast movements**, and **the fixes did not help**:
  second-order derivatives scored *worse* than first-order (6 vs 4), and longer
  windows did not improve on 5. The specific weaknesses identified in 1.6 were
  addressed and the false-positive rate did not fall.
- Edge-on suppression barely moves it (6 → 5), so those rejections are **not** the
  known unobservable band — they are ordinary fast rotation.

**⭐ THE STRUCTURAL FINDING, which matters more than the numbers.** The teleport
population is nearly empty *because DR-1 already fixed it*. §0.4: duplicates
25 → 0, longest wrong-hold 225 → 10 frames. A gate that catches identity
teleports is solving a problem that no longer reaches it in production.

So what remains for a gate to do is the **finger** channel — N12's confusion at a
pitch crossing — and §16.1 measured that **anchoring the cube to the palm removes
that path entirely** (palm anchor 25–30% quieter in every band). **B4 and the arc
gate are alternative solutions to the same remaining problem, and B4 is far
simpler**: no prediction, no coasting, no threshold, nothing to cascade.

**Verdict: B3′ stays BUILT AND UNWIRED.** Not disproven — untestable on this
corpus, and aimed at a class DR-1 already handles. Revisit only if B4 leaves a
residual that a gate could plausibly catch, or if a corpus with real teleports is
recorded. Do not wire it on the strength of 1/1.

### 16.4 B4 — the A7 anchor A/B is RUN. Palm-rigid wins. (2026-08-04)

`analysis/b4_anchor_ab.py`, **28 grab intervals** replayed from the
`Position_during_rotation` takes. Three anchors, all in 2D pixel space — which
dissolves A7's "2D/3D coordinate mismatch" objection without needing M6 or M9,
neither of which is going to land.

| metric | A — §14.1 (9 pts) | B — palm+scale | **C — palm rigid** |
|---|---|---|---|
| 1 no-pop at grab (px) | 0.000000 | 0.000000 | **0.000000** |
| 2 jitter still, p95 | 2.270 | 1.769 | **1.736** |
| 2 jitter still, max | **8.543** | 11.941 | 11.712 |
| 3 yaw-sink \|r\| (T4) | 0.138 | 0.097 | **0.003** |
| 4 edge-on motion p95 (N12) | 11.953 | 9.067 | **9.067** |
| 5 teleport max (T3) | **511.3** | 515.9 | 516.5 |

**⭐ VERDICT: arm C — palm frame, rotation only, NO scale — is the best anchor.**

- **T4 is essentially eliminated**: yaw coupling |r| 0.138 → **0.003**. §14.1's
  documented value is −0.25 (§14.1.1); we reproduce the same sign and rough
  magnitude, and arm C removes it.
- **N12 improves 24%**: anchor motion inside the edge-on band 11.95 → 9.07 px,
  matching §16.1's independent 25–30% figure from a different measurement.
- **Jitter bulk is 23% tighter** (p95 2.27 → 1.74), and no-pop is preserved
  exactly — the property that killed the pre-§14.1 zero-offset design.

⭐ **B vs C confirms §14.3.1's prediction.** Including palm width as a scale term
(arm B) is *worse* than omitting it (arm C) on yaw coupling — 0.097 vs 0.003 —
because palm width collapses edge-on and arm B feeds that collapse straight into
cube position. That was predicted from the anchor measurements before this A/B
ran, and it held.

⚠ **Two honest costs, neither disqualifying:**

1. **Jitter MAX is worse** — 11.7 px vs §14.1's 8.5. The bulk is tighter but the
   tail is not, and arm C has no scale term, so the culprit is the **MCP-row
   direction** becoming unstable edge-on — the same collapse as everywhere else.
   The natural remedy is DR-2's pattern: freeze the palm ROTATION inside the
   edge-on band. Untested; do not assume it.
2. **No teleport advantage** — max ~511–516 px for all three. Expected: a
   teleport moves the whole hand, palm included, so no anchor choice helps. T3
   remains DR-1's job.

**Consequence for A7**: the gate has run, and it favours replacing §14.1's
9-point weighted anchor with a palm-rigid frame. ⚠ **Not yet ported to
production, and not yet live-confirmed** — this is replay evidence on 28
intervals from one recording session.

### 16.5 ⚠⚠ B4's VERDICT IS OVERTURNED (2026-08-04, same day) — arm C does not fix T4

§16.4 concluded that **arm C (palm rigid, no scale) is the best anchor**, on
yaw-sink |r| = 0.003 against §14.1's 0.138. That was measured on the seven
`Position_during_rotation` takes recorded in August 2026 for the
*translation-pivot* work — **none of which contains a sustained yaw hold or a
pitch crossing while holding a cube**, i.e. neither of the two conditions the
claim was about.

Two purpose-built takes were then recorded (`t4_yaw_hold`, 12 cycles;
`n12_pitch_crossing`, 11 cycles; cube held in 100% of frames in both). Re-run:

| take | metric | A §14.1 | B palm+scale | C palm rigid |
|---|---|---|---|---|
| `t4_yaw_hold` | jitter p95 | **2.235** | 5.486 | 6.848 |
| | **yaw-sink \|r\|** | 0.822 | **0.001** | 0.815 |
| `n12_pitch_crossing` | jitter p95 | 4.173 | 1.431 | **1.423** |
| | yaw-sink \|r\| | 0.323 | **0.005** | 0.194 |

**⭐ CORRECTIONS, in order of importance:**

1. **Arm C does NOT fix T4.** |r| = 0.815, essentially identical to §14.1's
   0.822. The 0.003 in §16.4 was an artifact of takes without sustained yaw.
2. **Arm B (palm + SCALE) fixes it almost completely** — |r| = 0.001. **The
   scale term is essential, which is the opposite of §16.4's conclusion.**
3. **The mechanism, now understood**: under yaw the palm foreshortens, so an
   offset held at fixed PIXEL length (arm C) juts further out as the hand
   shrinks — *that is the sink*. Scaling the offset with palm width (arm B)
   shrinks it with the hand and removes it. §14.3.2 showed palm width is *noisy*
   under yaw; both are true, and it is still the right term, because the anchor
   must track foreshortening even through a noisy proxy.
4. **§14.1's T4 defect is far worse than documented** — |r| = 0.822 on a
   purpose-built yaw take, against the −0.25 recorded in §14.1.1. The defect was
   under-measured because it had never been provoked deliberately.
5. **On N12 the palm arms win decisively** — jitter p95 4.173 → 1.43, and max
   15.6 → 2.0. That half of §16.4 survives.

### ⚠ AND PITCH-SINK IS REAL TOO — the metric was mis-named, and pooling cancelled it

"Yaw-sink" is a misnomer for what is measured. The metric correlates the anchor's
distance from the palm against `edge_on_measure`, which drops under **both** yaw
and pitch — the axis comes from *which take is run*, not from the metric. Per
axis:

| take (axis) | A §14.1 | B palm+scale | C palm rigid |
|---|---|---|---|
| `n12_pitch_crossing` (**pitch**) | **+0.323** | +0.005 | −0.194 |
| `t4_yaw_hold` (**yaw**) | **−0.822** | +0.001 | −0.815 |

1. **Pitch-sink exists**: §14.1 scores |r| = 0.323 on pure pitch, and the sign is
   **positive** — the anchor sinks *toward* the palm, exactly as §14.1.1
   describes T4.
2. **Under yaw the sign FLIPS to negative** — the anchor drifts *away*. Same
   defect family, opposite direction.
3. ⭐ **That is the second reason §16.4 was wrong.** Pooling yaw and pitch takes
   lets the opposite-signed drifts **partially cancel**, which is how §14.1
   scored a benign 0.138 pooled while being 0.822 and 0.323 on the isolated
   axes. **Always read this metric per take; never pool rotation axes.**
4. **Arm C fixes NEITHER axis** (0.194 pitch, 0.815 yaw) — it is not merely weak
   on yaw. **Arm B decouples both** (0.005, 0.001), and is the only arm that
   does.

**⚠ NO ARM IS A CLEAN WIN, and this is an owner trade-off, not a technical
call.** §14.1 is smoother during yaw (jitter p95 2.235 vs B's 5.486) but
systematically drags the cube toward the palm as the hand turns (|r| 0.822).
Arm B is ~2.5× noisier there but has essentially no systematic bias. A
systematic drift is the defect the operator actually reported; jitter is not.

**Arm B is the leading candidate. Do not port anything to production yet.**

⭐ **THE METHODOLOGICAL POINT, which is the durable output**: §16.4 was measured
on data that did not contain the failure it claimed to fix, and it produced a
confident, wrong, three-decimal answer. **A/B results are only as good as whether
the corpus contains the condition under test** — the same lesson as §0.15's
"a replay harness that reconstructs streams differently silently measures a
pipeline that no longer exists". Before trusting any A/B, ask what is IN the
takes.

### 16.6 B3″ — the FULL prediction model, built and MEASURED. It fails. (2026-08-04)

The owner rejected conclusions drawn with the half-implementation and specified
the model properly: explicit velocity and acceleration, a real predictive
probability distribution, multi-frame horizon, and — the vigilance condition —
**it must not reject genuine changes of direction.**

Built as `Resources/block_predictor.py`: explicit `p, v, a` from a least-squares
quadratic over 7 accepted frames; OLS **prediction variance**
`s²(1 + x(h)ᵀ(XᵀX)⁻¹x(h))` as a real distribution; angular velocity **and**
acceleration by log map; per-channel rejection with a horizon that grows while
coasting. Correctness proven on synthetic data where ground truth is known
(`analysis/verify_block_predictor.py`): p/v/a recovered exactly, ω = 6.0000°/frame,
α = 1.0000°/frame², variance growing with horizon, a 200 px teleport caught while
25 px/frame smooth motion is untouched. Floors **derived** from `static_hold`
(p99.5 of resting residuals), verified 4.0–16.5× below real failure residuals.

**⭐ AND THEN IT FAILS THE VIGILANCE TEST, DECISIVELY:**

| | channel-frames | rejected |
|---|---|---|
| **at a direction reversal** | 20,927 | **11.65%** |
| elsewhere | 214,392 | 1.57% |
| | | **7.43× over-rejection** |

Reversals were labelled **non-causally** from raw velocity sign changes,
independent of the gate. One reversal frame in nine is rejected — in a game
built on pitch and yaw cycles, that is a visible artifact at every direction
change.

**Why, and it is structural rather than a tuning failure**: a reversal is
**unpredictable from past data by construction**. The quadratic says "continue at
the current v and a", the hand turns, the residual spikes — and σ stays narrow,
because the fit residual over the smooth approach *to* the reversal was small.

**The principled remedy was tried and does not work.** Acceleration is the least
trustworthy coefficient, so σ was widened by its own contribution
`|½·a·h²|` (`ACCEL_UNCERTAINTY`). Overall rejections fell 15.81% → 12.12%, but
**the ratio was unchanged: 7.33× → 7.43×**. It scales everything down without
separating reversals, because at a reversal the residual is ≈ 2|v| while the
acceleration term is only ≈ ½|a| — far smaller for a sharp turn.

**And it solves none of the four target problems:**

| target | raw | gated | verdict |
|---|---|---|---|
| jitter, still hand (p95 / max) | 0.0174 / 0.0695 | 0.0179 / **3.0248** | **worse** — 43× worse max |
| edge-on band motion (p95) | 0.3607 | 0.3541 | marginal (2%) |
| back-of-hand orientation | — | identical | **no effect** (gate never fires on still hands) |
| teleport | — | — | already solved by DR-1 (n=1 survives) |

**VERDICT: B3″ is PARKED alongside 1.6 and `block_tracker.py`.** This is the
second, much better-specified attempt at a predictive outlier gate, and it fails
the same way — which is itself the finding.

⭐ **THE GENERALISABLE RESULT, now measured twice with very different models:**
**at this input envelope, a forward-extrapolation gate cannot separate a
genuine direction change from an outlier.** 1.6 failed with a two-sample
velocity and a fixed threshold; B3″ fails with fitted derivatives, a real
predictive distribution and a growing horizon. **The limitation is not model
quality — it is that the information needed is not in the past frames.** Do not
attempt a third variant without a fundamentally new signal (a second camera, or
a non-causal buffer that can see *past* the reversal, i.e. item 3.2's RTS
smoothing, which costs latency for everyone).

⚠ **Consequence for the anchor question**: because the gate does not work, it
cannot clean the outliers that dominate B4's jitter tails, so **it cannot
reorder arms A/B/C**. §16.5's conclusions stand or fall on their own evidence.

### 16.7 B7 — the confirmation gate, BUILT and MEASURED. It does not ship. (2026-08-04)

`Resources/confirmation_gate.py` + `analysis/verify_confirmation_gate.py`
(22 synthetic checks, all passing) + `analysis/b7_eval.py` (15 configurations
over the 33-session corpus, 235,319 channel-frames).

**To see it live**: `debug_prediction.bat` (`LiveBlockPredictionDebug.py`) runs
RAW and GATED cube behaviour **side by side off one camera** — one capture, one
MediaPipe pass, one DR-1/DR-2 pass, then the stream forks, so every visible
difference is the gate and nothing else. It draws the hand as the **six blocks**
rather than the 21 landmarks: palm quad + centroid + scale bar + axis gizmo (the
four palm channels), each finger as an arc whose bow is computed from its
extension scalar alone, and the thumb dashed and labelled RAW because §16 leaves
it unmodelled. Amber = that channel is PENDING, red = its frames were discarded.

The design from `BUILD_PREDICTION_GATE.md` §1, built in full: flag at F but do
**not decide**; buffer F…F+L; coast the *output* while the *measurement* waits;
decide at F+L; discard only what later frames prove was an outlier. Per-channel,
S3-compliant, hard-capped, and — unlike B3″ — a discarded frame genuinely never
enters the fit.

#### ⭐ What worked, and it is the part worth keeping

**Deferring the decision does separate reversals from outliers.** With the flag
rate divided out — *of the flags raised, what fraction was thrown away?* —

| verdict test at F+L | at a reversal | elsewhere | ratio |
|---|---|---|---|
| `p_pre` — m4's inherited shape | 31.8% | 28.3% | **1.13×** (no discrimination at all) |
| `self` — the owner's literal "are F…F+L coherent?" | 31.3% | 42.3% | 0.74× |
| **`pred` — distance from the PREDICTED TRAJECTORY** | **9.3%** | **24.5%** | **⭐ 0.38×** |

⚠ **And the inherited test had to be thrown away, which is a finding in itself.**
`m4_rejection_audit.py`'s out-and-back shape — distance from the last accepted
*value* — **does not discriminate on these channels (1.13×)**. It was measured on
a **2D palm centroid**, where a hand rarely retraces its own path; the block
channels are **signed scalars**, and *a direction reversal comes back through the
value it started from*. "Returned to where it was" and "turned around" are the
same event on one axis. The brief warned that the thresholds would not transfer;
**the shape did not transfer either.** Asking instead whether the later frames
return to the *predicted trajectory* scores 0.38× on identical data.

#### ⚠ And the four acceptance criteria, decided in advance

Best configuration: **L=2, `pred` verdict, `hold` coast, blend 3, B8's fit.**

| # | criterion | result | |
|---|---|---|---|
| 1 | reversal-discard ratio ≤ 1.5× | **9.44×** best (B3″ 7.43×) | ❌ **FAIL** |
| 2 | discards majority outlier, not real movement | **89.5% / 3.4%** (1.6 was 7.9% / 80.2%) | ✅ PASS |
| 3 | jitter and edge-on improved, max not worse | jitter max 0.0695 → **0.4971**; edge-on max 3.4555 → **1.8617** | ❌ FAIL on jitter — ⚠ **OVERTURNED BY §16.9**: this is the PALM level; measured on the CUBE it passes, and the cube is the level the operator sees |
| 4 | latency stated in ms and accepted | **83 ms** at L=2 @ 24.1 fps (124 / 166 / 248 at L=3/4/6) | owner's call |

**VERDICT: B7 is BUILT, MEASURED and UNWIRED**, alongside 1.6, `block_tracker.py`
and B3″. It is the third measured failure of causal outlier gating on this sensor.

#### ⭐ But the diagnosis is now sharper than "gating fails", and that matters

**The decision is fixable; the detection is not.** Split the ratio into its two
factors and the residue is obvious:

    reversal over-rejection  =  FLAG rate ratio  ×  verdict-test ratio
    B3''                        7.43x               1.00x (no deferral)
    B7 + B8                     3.84x               0.83x

The deferred verdict is now *protective* (< 1.0), and the fit change halved the
flag ratio — but **a reversal still trips the residual test 3.8× more often than
an ordinary frame, and no amount of deferral removes that.** §16.6's
generalisable result stands, narrowed: it is the *detector*, not the *decider*,
that cannot see a reversal coming.

⭐ **Two numbers that read the opposite way from the ratio, and both are true:**

- **Absolute harm at reversals fell 2.8×.** Of channel-frames at a labelled
  reversal, B3″ discarded **11.65%**; B7 discards **4.15%**. The *ratio* got
  worse only because discards elsewhere fell even further (1.57% → 0.44%).
  ⚠ A ratio is not harm. The criterion was set on the ratio and the criterion
  fails; the owner should know both figures before treating that as settled.
- ⚠ **The reversal labels themselves are contaminated.** `reversals()` fires on
  a raw velocity sign change — and **a teleport produces two of those**. Every
  ratio in §16.6 and here is therefore an *upper bound* on true reversal
  over-rejection, and the contamination is worst inside the discarded subset,
  which is precisely the population the gate selects. This weakens B3″'s 7.43×
  as much as it weakens B7's numbers.

#### ⚠ What B7 cannot do, confirmed by measurement rather than argued

- **Back-of-hand: no effect**, exactly as predicted. The `known_*_back` takes are
  byte-identical raw vs gated in every one of the 15 configurations — the gate
  never fires there, because those errors are *sustained* and F…F+L agree
  coherently in the wrong place (§0.18's sensor floor).
- **Teleports: nothing left to catch.** After DR-1 the identity-teleport
  population is ~3 events in 29,164 frames (§16.1). What the gate actually
  removes is transient jitter spikes — and its own coast-and-rejoin then puts a
  **7× larger** transient back into the still-hand tail. That is the whole
  failure in one sentence.

### 16.8 B8 — the quadratic optimised, and it LOSES TO DOING NOTHING (2026-08-04)

`analysis/b8_fit_sweep.py`: 15 fit configurations, open loop, against the two
baselines **S1** makes mandatory, **stratified by hand speed** — because a pooled
median is decided by the still-hand majority, while the gate only ever coasts on
a hand that was *moving*. Median |error| in units of each channel's noise floor:

| | still, h=1 | still, h=6 | **fast, h=1** | **fast, h=2** | fast, h=6 |
|---|---|---|---|---|---|
| **BASELINE hold (v=0)** | **0.322** | **0.677** | 3.921 | 6.182 | **10.927** |
| B3″ shipped (w7, order 2) | 0.457 | 2.680 | 4.175 | 8.216 | 34.211 |
| best fit (w7, **order 1**, exp hl2) | 0.362 | 1.043 | **3.648** | **5.462** | 12.875 |

orientation (deg): hold **3.07 / 4.57 / 10.94** vs the log-map fit 3.61 / 6.32 / **23.76**

**⭐ THREE RESULTS:**

1. **ORDER 2 IS WRONG.** The acceleration term differentiates noise twice and the
   error explodes with horizon — 34.2 floors at h=6 against order 1's 12.9.
   §16.3 saw a hint of this (order 2 rejected *worse* than order 1) and did not
   follow it. Order 1 dominates at every horizon in every speed band.
2. **Weighting helps**, as it should for a 7-frame window that counted a 290 ms-old
   sample as heavily as the newest. Exponential, half-life 2 frames, is best.
3. ⚠⚠ **NO CONFIGURATION BEATS "HOLD THE LAST VALUE" AT EVERY HORIZON — S1 FAILS
   for all 15**, and the orientation motion model loses to holding the last
   quaternion at every horizon too. The fit wins **only** in the regime the gate
   actually coasts in (a moving hand, h = 1–2) and loses everywhere else.

⭐ **AND B8 IS NOT THE SEPARATE LEVER THE BRIEF ASSUMED.** The brief stated that
optimising the fit would leave B3″'s reversal ratio "roughly intact — that was
measured". That measurement was of `ACCEL_UNCERTAINTY`, which only widens σ.
Changing the *order and weighting* moves it a great deal:

| with B8's fit | flag ratio | jitter max |
|---|---|---|
| B3″ fit (order 2, unweighted) | 7.03× | 1.3244 |
| **B8 fit (order 1, exp hl2)** | **3.84×** | **0.5816** |

**Consequences already applied**: `confirmation_gate.COAST_MODE` defaults to
`"hold"`, not to the prediction the owner's design assumed — coasting on a model
measured to be worse than nothing is not a defensible default. `fit_channel` now
takes `order` / `weighting` / `half_life`, and ⚠ **its defaults are left exactly
as B3″ shipped them** so every pre-B8 number stays reproducible; B8's
configuration is passed in by the caller.

⚠ **Do not read this as "prediction is useless here."** It says the *quadratic
extrapolator* is, at horizons past ~2 frames, on this sensor. Item 3.1's
dual-pathway work should treat "hold" as the baseline to beat, not as a straw man.

### 16.9 ⚠⚠ B7 MEASURED LIVE — §16.7's criterion 3 is OVERTURNED (2026-08-04)

A **450-second live take** (10,092 frames, 22.43 fps measured, cube held in
86.1% of frames, 14.2% still and 25.3% fast) recorded through
`debug_prediction.bat` and re-measured by `analysis/b7_live_ab.py`, which
replays the whole pipeline offline under any configuration.

#### ⭐ First: a wiring bug that invalidated the first pass, found BY EYE

The owner, watching the two windows: *"if I hold my hand edge-on palm up… in the
prediction gate window, the arc and vertices literally jump all around the
window."*

The gated `scale` channel was being realised as a similarity transform,
`f = gated_scale / raw_scale`, applied to all 21 landmarks. **Its denominator
collapses.** Edge-on, measured palm width fell to **2.43 px** while the gate
coasted ~86 px, so `f` reached **35.4** and threw the landmarks **5235 px**
across a 640 px window. The 118 frames with >100 px of displacement had median
palm width 41.8 px against 91.6 px overall, and median `edge_on` 0.319 against
0.747 — precisely the edge-on band.

⭐ **And it was wrong before it was unstable: edge-on the palm is FORESHORTENED,
NOT SHRUNK.** "Palm width should be 86 px" has no valid realisation as landmark
coordinates. This is the reciprocal of §14.3.1/§16.5's trap, where feeding
palm-width collapse *into* cube position was the measured difference between
anchor arms B and C — **the spec had already written this down twice.**

Fixed by never back-projecting `scale` (it is gated and displayed as the knuckle
bar's *length*): max displacement **5235 → 219.8 px**, frames >100 px **118 → 6**.

⚠ **Every cube number from the first pass measured that bug and is void.** The
lesson is the §0.15 one again: a harness that reconstructs the stream
differently silently measures a pipeline that does not exist. It took a human
looking at the screen to catch it, which is an argument for this tool existing.

#### The corrected live result, on held-only frames

Restricted to frames where the cube is actually held, so the S3 hold cannot
flatter the gate (raw holds 86.1% of frames, gated 80.5%):

| held-only cube step | RAW | B7 | B7 `reject_z`=4.0 |
|---|---|---|---|
| p50 | 7.55 px | 7.66 px | 7.75 px |
| p95 | 41.11 | 39.99 | 40.08 |
| **max** | **156.51** | **124.33** | **109.58** |
| **still-hand max** | **73.16** | **38.65** | **38.65** |
| grabs taken | 144 | 138 | 140 |

| # | criterion | corpus §16.7 | LIVE | |
|---|---|---|---|---|
| 1 | reversal-discard ratio ≤ 1.5× | 9.44× | **5.63×** (best 2.62× at L=6) | ❌ **confirmed FAIL** |
| 2 | discards majority outlier | 89.5% | **95.3%** | ✅ confirmed PASS |
| 3 | max not worse | jitter max 7× worse | **cube max −21%, still-max −47%** | ⭐ **OVERTURNED → PASS** |
| 4 | latency in ms | 83 ms | **89 ms** @22.43 fps | owner's call |

⭐ **WHY CRITERION 3 FLIPPED, AND IT IS A MEASUREMENT-DESIGN LESSON, NOT A
CONTRADICTION.** §16.7 judged it on *palm channels*, because the corpus contains
no cube. But the cube's anchor is a weighted mean over 9 landmarks plus a frozen
residual offset — **it low-passes exactly the coast-and-rejoin transient the gate
adds**, while the raw excursions the gate removes *do* reach the cube. Both
numbers are correct; only the cube one describes what the operator sees.
**The criterion was being evaluated one level above where the defect lives.**

⚠ The out-and-back classifier scored exactly **100.0%** "teleport" for
`verdict_test='p_pre'` on live data too — the tautology of §16.7 reproducing
itself outside the corpus.

#### Degrees of freedom: what actually moves anything

| knob | effect |
|---|---|
| ⭐ **`reject_z` 3.0 → 4.0** | **the best single tune.** Flags −44% (3002→1672), cube max 124→**110**, still-max unchanged, grabs 138→140, reversal discards 6.52%→3.96%. No latency cost |
| `L` (lag) | trades criterion 1 against everything: L=6 reaches 2.62× but costs **267 ms** and pushes still-max 38.65→**148.20**. Bad trade |
| `blend` | 1 is clearly wrong (cube max 229); 3 or 5 are fine |
| `window` | 5 marginally best on cube max, +26% flags |
| `coast_mode` | barely matters once `scale` is out of the wiring |
| ⚠ **`ACCEL_UNCERTAINTY`** | **DEAD PARAMETER.** 0 and 2 give byte-identical results, because B8's order-1 fit makes `a = 0.0` and the term is always zero. The build brief listed it as a DOF to sweep; it cannot act unless order 2 returns, and §16.8 measured order 2 as clearly worse |
| ⭐ **the channel→landmark mask** | **the dominant DOF, and not a gate parameter at all.** No gate knob came close to its effect size — it was the difference between a 5235 px artifact and a working tool |

#### ⭐ Replicated on a SECOND live take (2026-08-04, `gate_z4`)

A second take recorded at `reject_z = 4.0` — 1155 frames, 50 s, 23.12 fps.

⚠ **The two takes are NOT content-comparable**, and that governs how they may be
read (§16.5's rule, applied before the numbers): take 2 has **0.8% still frames
against 14.2%**, is faster (palm p50 11.98 vs 6.83 px/frame), holds a cube 73.2%
vs 86.1% of the time, and its largest palm excursion is 50.9 px against 512.9.
Reversal content is identical at 19.1% of channel-frames. So z=3 vs z=4 is
compared **within** each take by replay, never across them.

| claim | take 1 (450 s) | take 2 (50 s) | |
|---|---|---|---|
| criterion 1 fails at every setting | 5.63× | 4.25× (best 2.39× at L=6) | ✅ replicated |
| criterion 2, discards majority outlier | 95.3% | 83.8% (93.9% at z=4) | ✅ replicated |
| held-cube max step improves | 156.5 → 124.3 | 80.7 → 70.1 | ✅ replicated |
| `ACCEL_UNCERTAINTY` inert | identical | identical | ✅ replicated |
| `p_pre` classifier tautological | 100.0% | 100.0% | ✅ replicated |
| grab loss small | 144 → 138 | 15 → 15 | ✅ replicated |

⭐ **And the wiring fix is visible in the data**: raw-vs-gated cube separation is
now **p50 0.86 px** where the buggy pass measured 80.82 px. The arms track each
other and diverge only during a flag, which is the intended behaviour.

**`reject_z` 3.0 → 4.0, head to head within each take:**

| | take 1 | take 2 |
|---|---|---|
| flags | −44% | **−47%** |
| **S3 hold, % of frames** | 17.1% → **9.4%** | 21.3% → **10.3%** |
| reversal discards | 6.52% → 3.96% | 4.84% → **3.60%** |
| discards that are outliers | 95.3% → 95.2% | 83.8% → **93.9%** |
| held-cube max | 124.3 → **109.6** | 70.1 → 72.4 |

**z=4.0 is CONFIRMED and is the recommended setting**: it roughly halves both the
flag rate and the S3 hold fraction — i.e. halves how often the gate is
intrusive — while *improving* the quality of what it discards.

⚠ **Two honest limits on that.** The cube-max advantage of z=4 over z=3 did
**not** replicate (better on take 1, marginally worse on take 2) — call it
neutral, not a win. And **still-hand metrics cannot be evaluated on take 2 at
all**: 7 qualifying frames, so its `stillMx` figures are one frame's worth of
noise and are not evidence in either direction.

#### ⚠⚠ CRITERION 1 IS RETRACTED AS A DISQUALIFIER (owner challenge, 2026-08-04)

The owner, from watching both windows: *"I did not see flagrant cases where the
change of direction was completely missed, even at relatively high speed. I think
you are over interpreting the reversal-discard ratio."*

**Measured directly, on the cube — the only thing on screen.** Raw-cube direction
changes (>2 px/frame either side), matched against the gated cube's:

| take | direction changes | lag p50 | lag p90 | unmatched |
|---|---|---|---|---|
| 450 s | 1671 | **0 frames (0 ms)** | 0 frames | 10.1% |
| 50 s | 118 | **0 frames (0 ms)** | 0 frames | ~10% |

**The gated cube turns on the SAME FRAME as the raw cube.** The unmatched ~10%
are small reversals that fall below the 2 px/frame detection threshold once
smoothed — not missed turns.

⭐ **FOUR REASONS THE METRIC WAS WRONG, and they are the durable output:**

1. **It was carried across a mechanism change without revalidation.** Criterion 1
   was written for B3″, where a rejection replaced the measurement *and could
   cascade* — §0.13.3 measured one bad frame booking up to 8 rejections. There
   it was a fair proxy for "the cube fails to follow a direction change." Under
   B7 a discard is **bounded to L frames and always resumes from the
   measurement**. The same count means something far milder.
2. **A ratio is not a magnitude.** 5.63× reads as alarming; the absolute rate is
   3.96% of reversal channel-frames, each removing ≤2 frames of ONE channel of
   eight, feeding an anchor that averages 9 landmarks. Several attenuating
   stages sit between the metric and anything visible, and it models none.
3. ⚠ **The operator-visible measurement was available and was not taken.** Both
   cube tracks were in the recording. Reporting the channel-level proxy instead
   is EXACTLY the error §16.9 had just diagnosed in criterion 3 — *measured one
   level above where the defect lives* — found and then not generalised by a
   single section.
4. **The label contamination was flagged and then ignored.** A teleport also
   produces two velocity sign changes, so every such ratio is an upper bound —
   stated in §16.7, then used as if clean.

> **Before treating a criterion as a disqualifier, measure the harm it is a
> proxy for.** All four failures share one root: a proxy was trusted after the
> thing it proxied for had changed.

**B7 passes every criterion that has been measured against observable harm.**
Criterion 1 fails as literally written and is retracted as a blocker; criteria
2-3 pass; criterion 4 (~89 ms hold per flag, ~4% of grabs delayed) is a product
judgement.

### ⭐ 16.9.1 OWNER DECISION: B7 IS PARKED, NOT WIRED (2026-08-04)

> *"I agree there is almost no visual difference between the raw and the
> prediction gated outcomes. I would therefore keep the raw to keep the pipeline
> lean and without adding additional layers. However, I would park the build in
> order not to lose all what we have built."*

**And this is the right call on the evidence, not a rejection of it.** The gate
was cleared of its technical blockers and then declined on a product ground the
measurements support: a 21%/47% cut in the cube's worst steps is real but not
*visible*, and it costs a per-hand predictive layer, ~89 ms of hold at every
flag, and ~4% of grabs delayed. **A layer that cannot be seen is not worth its
own failure modes** — this build produced two of them (the `scale`
back-projection, the quaternion rejoin) inside one session.

⚠ **Nothing was wired.** Production (`HandsTriggeredActions.py`, `CubeWindow.py`,
the client/server pipeline) is untouched; `confirmation_gate.py`,
`hand_blocks.py` and `block_predictor.py` are imported only by
`LiveBlockPredictionDebug.py` and by `analysis/`. The single production-adjacent
change is `LiveSnapDebug.update_hands`'s `snap_blocked=frozenset()` default,
a no-op for every existing caller.

**To revive it, this is the whole configuration — do not re-derive it:**

    reject_z    4.0        (3.0 halves nothing; 4.0 halves flags AND the S3 hold)
    lag L       2          (~89 ms; L=4/6 measurably worse on the cube)
    verdict     "pred"     (distance from the PREDICTED trajectory, 0.38x)
    coast_mode  "hold"     (B8: the fit loses to holding at every horizon)
    blend       3
    fit         order 1, exponential weights, half-life 2 frames

**Still runnable**: `debug_prediction.bat` (live A/B, blocks overlay),
`analysis/b7_live_ab.py` (replay any config over a recorded take),
`analysis/verify_confirmation_gate.py` (24 synthetic checks), plus two live
takes on E: under `Recordings_prediction_gate`.

⚠ **Do not restart this line of work on the strength of the idea.** Three
measured attempts (1.6, B3″, B7) and the conclusion is stable: gating buys
little here because DR-1 already removed the teleports, and what remains is
either sustained (a sensor floor) or already invisible.

### 16.10 ⭐ WHERE THE CUBE'S NOISE ACTUALLY COMES FROM (measured 2026-08-04)

Found while explaining the pipeline to the owner, and it reframes the next step.
**The cube transform has only two live components**, driven by disjoint landmark
sets — they do not mix:

| cube property | driven by | note |
|---|---|---|
| position | `_weighted_position`, the **9 landmarks** (5 fingertips + 4 MCPs) | ⚠ NOT smoothed — assigned directly |
| quaternion | `_hand_orientation_quaternion`, the **4 palm world landmarks** | slerp-smoothed |
| **scale** | **nothing — `size` is a constant** | there is no scale channel on the cube |
| *(grab test only)* | `_hand_position`, the **5 palm landmarks** = `hand_blocks.PALM_LANDMARKS` | never touches the transform |

The translation anchor is a **fixed linear combination of 9 landmark pixel
positions**, its coefficients frozen at grab by inverse distance from the cube,
plus a frozen residual offset.

**⭐ THE MEASUREMENT: A PERFECTLY STILL PALM STILL MOVES THE CUBE.**
On the 450 s take, restricted to frames where the 5 palm landmarks barely moved:

| palm moved | n | anchor moved p50 | p95 | max | amplification p50 |
|---|---|---|---|---|---|
| < 0.5 px | 249 | **0.570 px** | 1.701 | **17.51 px** | **1.66×** |
| < 1.5 px | 1344 | 1.013 px | 3.050 | 22.03 px | 1.15× |

Because the frozen weights include the **5 fingertips**, any finger flex moves
the cube. Even grabbing at the palm centroid — the most MCP-favourable case
there is — the fingertips carry a **median 27% of the total weight** (p95 42%),
and they are the 13-32% CV landmarks (§0.2) against the palm's 2.76 mm rigidity.

⚠ **This is not palm noise leaking through. The anchor deliberately includes the
noisiest points on the hand**, by a §14.1 design chosen to fix a different
problem (the translation pivot). It is the same defect §16.5 measured as
|r| = 0.822 yaw-sink and 0.323 pitch-sink.

⭐ **And the remedy does not add a layer — it REMOVES one.** Anchoring to the
palm transform (the 5-landmark position and the 4-landmark frame, both already
computed every frame) deletes the fingertip path entirely. That is §16.5's
**arm B**, the only arm that decoupled both axes (|r| 0.005 / 0.001). It is
independent of B7, it is a replacement rather than an addition, and it is aimed
at the edge-on/pitch complaint the gate could not touch.

### 16.11 B4 BUILT 3D-NATIVE (2026-08-04) — and the live evidence is MIXED, not a win

`Resources/palm_anchor.py` + `analysis/verify_palm_anchor.py` (18 golden
vectors, all passing). Owner decision: build it 3D-native now, render in 2D
until real depth exists, so the Z retrofit is one function later.

    at grab:   R3  = Rot_G⁻¹ · ( X_G − o_G )      metres, in the PALM's frame
    every t:   P_t = o_t(px) + k_t · proj_xy( Rot_t · R3 )

⭐ **Why 3D-native costs nothing today.** The rotation is *already* computed every
frame (`hand_blocks.palm_frame`); only the offset representation changes, from a
2-vector in pixel-frame units to a **metric 3-vector in the palm's own frame**.
That single choice is what makes the retrofit free: `R3` and `Rot_t` survive
untouched, `o_t` gains a z, and `proj_xy + k_t` are replaced by a real
projection. ⛔ **What is missing for true 3D is not the formula — it is ABSOLUTE
DEPTH**: MediaPipe's world landmarks are hand-RELATIVE (metric shape, origin at
the hand, no world position), so `o_t.z` does not exist in the data at all. That
is the Z-translation item's problem and it is identical for every anchor design,
including §14.1's. `verify_palm_anchor.py` §5 asserts the 3D form reproduces the
2D similarity form to **6.36e-14 px** at z=0, so the reduction is proven, not
hoped.

⭐ **Rotating in 3D then projecting gives anisotropic foreshortening for free** —
an offset along the tilt axis shortens by cos(θ) while a perpendicular one does
not (verified exactly). A scalar 2D scale term shrinks both equally, which is
very likely why §16.5 measured arm B as 2.5× noisier under yaw.

#### The scale term: measured, and palm width is ruled out

| | p50 | CV | r(edge_on) | edge-on → open |
|---|---|---|---|---|
| palm width, PIXELS | 91.5 px | 25.8% | **+0.601** | **0.320** — 3× collapse |
| palm width, WORLD | 0.064 m | 18.5% | **+0.002** | 0.993 |
| weak-perspective `k` | 1403 | 28.9% | +0.091 | 0.809 |

⭐ **The palm never actually collapses — only its projection does.** In metric
space it is the same hand at every pose (r = +0.002), so a scale built from the
projection alone inherits the projection's degeneracy while a least-squares fit
of the known 3D shape to the observed 2D points does not.

#### ⚠⚠ AND THEN THE LIVE MEASUREMENT DOES NOT SUPPORT IT

Replayed over two live takes. Worst cube step while the PALM moved < 0.5 px —
i.e. §16.10's own defect, the one this module exists to remove:

| still-frame cube step | take 1 (450 s) p50 / p95 / max | take 3 (290 s) p50 / p95 / max |
|---|---|---|
| **§14.1 incumbent** | 0.749 / 29.40 / **73.16** | **0.610** / 2.96 / **18.58** |
| palm anchor, `k` live | 1.544 / 35.70 / 81.01 | 0.542 / 5.87 / 39.84 |
| palm anchor, `k` frozen | 1.186 / 31.43 / **59.54** | **0.372** / **2.93** / 24.45 |

1. **The live weak-perspective scale is itself a major noise source.** Freezing
   `k` improves max 81 → 59.5 and p95 5.87 → 2.93. Its 29% CV costs more than
   the collapse it cures — "noise is smoothable, collapse is not" was right in
   principle and wrong in magnitude.
2. **Even at its best the result is MIXED**: better max on take 1, worse on take
   3; better p50/p95 on take 3, worse p50 on take 1. **This is not the clear win
   §16.5's replay predicted.**
3. ⚠ **The likely mechanism, and it is structural**: this anchor makes cube
   POSITION depend on the palm QUATERNION — the least reliable channel on the
   hand (§0.18) — and on `k`, over a lever arm equal to the full grab offset
   (~60 px). §14.1's inverse-distance weighting is not only about fingertips: by
   putting weight NEAR the cube it also keeps the lever arm SHORT, so angular and
   scale errors are not amplified. That advantage was not anticipated in §16.10.
4. ⚠ **Confound, stated because it limits all of the above**: these are replays
   over takes recorded while the operator watched the §14.1 arm. Once the arms'
   cubes diverge they grab at different offsets and stop comparing like with
   like — which penalises the anchor arms far more than the gate arms.
5. ⚠ **`k` frozen is UNVALIDATED FOR DEPTH**: it stops the offset scaling as the
   hand moves toward or away from the camera, and these takes may not exercise
   that. Do not adopt it on the jitter numbers alone.

#### ⚠⚠ AND THE FOUR-ARM LIVE SESSION SETTLES IT: THE ANCHOR IS DISQUALIFIED

A live four-arm take (`four_arm_review`, 2763 frames, 143 s, 19.24 fps, **47%
still frames**, cube held 95%) run through `debug_prediction.bat`:

| live arm, held-only cube step | p50 | p95 | max | **still-hand max** |
|---|---|---|---|---|
| 1 §14.1 anchor, no gate | **1.59** | **9.18** | **36.94** | **11.32** |
| 2 §14.1 anchor + B7 | 1.66 | 9.58 | 38.25 | 15.24 |
| 3 PALM anchor, no gate | 8.38 | 97.57 | 393.03 | **307.46** |
| 4 PALM anchor + B7 | 8.30 | 82.62 | 393.03 | 307.46 |

**A 27× regression on the very defect it was built to remove.** Diagnosed, and
it is the DESIGN, not a wiring bug — on the 399 frames where the palm CENTROID
moved < 0.5 px, the palm QUATERNION still moved:

    palm rotation step   p50 1.59 deg   p95 21.91 deg   MAX 144.19 deg
    weak-persp k step    p50 0.75%      p95  5.99%      max   16.4%
    >30 deg rotation on a still palm: 2.8% of frames;  >60 deg: 0.5%

⭐ **The scale term was never the real problem — the ORIENTATION channel is.**
A 144° swing on a 60 px lever arm throws the cube ~114 px. This is §0.18's
documented defect (the 4-landmark palm frame jumping while the hand is still),
and the palm anchor converts it directly into cube POSITION, amplified by the
lever arm. **§14.1's anchor is structurally immune because it never reads
orientation at all** — a property nobody had noticed was load-bearing.

> ⭐ **THE DURABLE RESULT: an anchor's robustness is not about which landmarks
> it reads, but about WHICH CHANNELS IT COUPLES TO.** §16.10 correctly showed
> §14.1 couples cube position to the noisiest LANDMARKS; the fix coupled it to
> the noisiest CHANNEL instead, which is worse. Removing a defect is not the
> same as improving the system.

**VERDICT: BUILT, VERIFIED, MEASURED, AND DISQUALIFIED AS DESIGNED.** §14.1
stays (A7 holds). ⚠ The risk was named in `palm_anchor.py`'s docstring *before*
the first measurement and then measured as fatal — the naming is what made the
diagnosis take one run.

**The one cheap variant still worth trying**, because it attacks the measured
cause rather than the symptom: feed the anchor the **already-filtered**
orientation (`_predictive_filter_step`'s output, which production ALREADY
computes for cube rotation) instead of the raw palm quaternion. If the 144°
excursions are what the filter exists to suppress, the anchor inherits that for
free. Untested. ⚠ Do not assume it: §0.13.2 measured that most large orientation
jumps occur in WELL-observed frames, so the filter may not catch these either.

### 16.12 ⭐ WHY §14.1 WINS — the error decomposition, and the one change that beats it

Owner question, 2026-08-04: *what exactly differs between the two formulas, which
term carries the noise, and can the palm formula borrow §14.1's answer only for
that term?* Measured on three live takes.

#### The two error structures

| | §14.1 | palm anchor |
|---|---|---|
| form | `P = Σ wᵢ·Lᵢ(t) + R`, `Σwᵢ = 1` | `P = o_t + k_t·proj(Rot_t·R3)` |
| estimates | **nothing** — a linear functional of positions | rotation **and** scale |
| error | **ADDITIVE**, averaged over 9 points | additive `o_t` **+ two MULTIPLICATIVE terms × lever arm** |

Still-frame contributions, lever arm 60 px:

| term | p50 | p95 | max |
|---|---|---|---|
| §14.1 total (mean of 9 landmarks) | 0.432 | 2.18 | **9.49** |
| — worst single fingertip *input* | 1.769 | 10.65 | 47.08 |
| palm (a) centroid — additive | **0.321** | 0.48 | 0.50 |
| palm (b) rotation × lever | 1.667 | 22.95 | **151.00** |
| palm (c) scale × lever | 0.448 | 3.59 | 9.86 |

⭐ **§14.1 absorbs 47 px fingertip excursions and still outputs 9.49 px, because
averaging suppresses them.** And ⭐ **the palm CENTROID is the better translation
term** (0.321 vs 0.432) — that half of §16.10 was right. The whole regression is
term (b).

#### Borrowing §14.1's answer for the offending term

§14.1 never estimates orientation: rotation-following falls out of averaged
POSITIONS. Replacing the 3-point Gram-Schmidt with a least-squares **Procrustes**
similarity fit of the palm constellation in pixel space — same points, averaged —
repairs most of the damage:

| four_arm_review | p50 | p95 | max | still-max |
|---|---|---|---|---|
| §14.1 | **1.59** | **9.18** | **36.94** | **11.32** |
| palm anchor, Gram-Schmidt | 8.38 | 97.56 | 393.04 | 307.50 |
| palm anchor, **Procrustes** | 2.58 | 14.50 | 48.10 | 38.20 |
| Procrustes + 4 tips | 2.30 | 13.14 | 51.40 | 26.58 |

**An 8× repair from changing only how rotation is obtained — and it still loses.**

> ⭐ **THE DURABLE RESULT: estimating a transform costs strictly more variance
> than not estimating one.** Any estimator-based anchor pays a premium that a
> linear functional of positions does not. §14.1's apparent crudeness *is* its
> robustness, and that had not been recognised.

#### ⚠ The arc-extension idea, measured in three forms — all worse

Owner's proposal: weight the fingertips by the arc scalars (or their median),
which are scale-free and noise-cancelling, rather than using raw knuckles.

| four_arm_review | p50 | p95 | max | still-max |
|---|---|---|---|---|
| tips, no arc weighting | **2.30** | **13.14** | 51.40 | **26.58** |
| binary arc gate 0.03 | 3.79 | 54.00 | 129.78 | 75.48 |
| binary MEDIAN-arc gate | 2.92 | 35.84 | 107.65 | 61.95 |
| continuous τ=0.10 / 0.05 / 0.02 | 3.12 / 3.90 / 5.09 | 15.49 / 19.29 / 27.82 | 58.61 / 66.21 / 75.39 | 30.15 / 32.57 / 52.14 |

**Monotonically worse as the arc influence grows**, converging to the unweighted
case as τ→∞. Binary gating is worse still, because switching the active point set
manufactures a discontinuity at every switch.

⭐ **Why: a least-squares fit ALREADY absorbs a moving fingertip as residual.**
Down-weighting it removes a point from the averaging, raising the estimator's
variance more than it lowers its bias. **Averaging beats selecting** — now the
fourth independent measurement of that on this sensor (item 1.6, B3″, B7, here).

#### ⭐ The one change that DOES beat §14.1 — and it changes nothing structural

Keep §14.1 exactly: additive, no estimator, no lever arm. Scale only the
**fingertip share of its own frozen weights**, then renormalise. One line.

| | §14.1 (×1.00) | **×0.60** | **×0.35** | ×0.00 |
|---|---|---|---|---|
| four_arm p95 / max | 9.18 / 36.94 | **8.60 / 33.78** | **8.28 / 30.77** | 10.50 / 42.52 |
| gate_live p50 / p95 | 7.55 / 41.11 | 7.27 / 39.20 | **7.12 / 37.96** | 7.33 / 35.96 |
| z4 max / still-max | 41.08 / 18.58 | **34.41 / 10.42** | 40.04 / **6.22** | 62.22 / 19.48 |

⭐ **×0.00 — deleting the fingertips — is WORSE on all three takes.** There is an
interior optimum near **0.35–0.6**: the fingertips carry both signal (span, extra
averaging) and noise (flex), and neither extreme is right. That also retires
§16.10's implicit premise that the fingertips are simply a defect to remove.

⚠ **Gains are modest (5–17%) and not uniform** — still-max improves hugely on one
take and worsens slightly on another. **Not adopted on this evidence.**

#### ⚠ What is still unmeasured, and it is the metric that matters

All of the above is JITTER. §16.5 records that *"a systematic drift is the defect
the operator actually reported; jitter is not."* The SINK was measured across
these takes and is **inconclusive** (|r| 0.02–0.51, no consistent ordering) —
because **none of these takes contains a sustained yaw hold or a pitch
crossing**, which is precisely the error §16.4 made and §16.5 had to overturn.

**Next step, and the only one that can settle B4: two purpose-built takes**
(sustained yaw hold, pitch crossing, cube held throughout) measured per take and
never pooled. If the sink favours a palm-based anchor, the variant to use is
**Procrustes + tips**, never the Gram-Schmidt form and never an arc-weighted one.

### 16.13 ⭐⭐ THE CUBE'S ROTATION IS THE REAL TARGET — and KABSCH beats Gram-Schmidt 7.5×

⚠ **First, a conflation to kill: §14.1 HAS NO ROTATION COMPONENT.** The two paths
have always been fully separate, and the cube's rotation has always been
palm-based:

    POSITION  9 landmarks (5 tips + 4 MCPs), PIXELS -> weighted mean + frozen offset   [14.1]
    ROTATION  4 palm landmarks (0,5,9,17), WORLD    -> Gram-Schmidt frame -> quaternion
                                                    -> _predictive_filter_step
                                                    -> delta = q_now . conj(q_grab)
                                                    -> target = delta . q_cube_at_grab
                                                    -> slerp(cube.orientation, target, 0.35)

So "improve §14.1's rotation" is not a thing to do, and a hybrid of "palm for
translation, §14.1 for rotation" is already half-shipped: **rotation IS the palm
block**, via the same four landmarks and the same Gram-Schmidt construction
`palm_anchor` used.

#### The measurement: frame-to-frame rotation on a STILL palm

| four_arm_review, n=399 | p50 | p95 | max |
|---|---|---|---|
| RAW Gram-Schmidt quaternion | 1.59 | 21.91 | **144.19** |
| after `_predictive_filter_step` (**SHIPPED**) | 1.59 | 17.54 | **101.61** |
| **KABSCH delta, 5 palm pts** | 1.35 | 11.71 | **25.07** |
| **KABSCH delta, 5 palm + 4 tips** | **0.85** | **2.91** | **19.32** |

⭐⭐ **A least-squares (Kabsch) rotation fit over the palm constellation cuts p95
from 21.91° to 2.91° and max from 144° to 19° — 7.5× on both.** The shipped
predictive filter removes only ~30% of the excursion; the estimator, not the
filter, is where the error lives.

⭐ **AND THE FINGERTIPS HELP HERE — the opposite of the translation case.** Adding
the 4 tips improves p95 11.71 -> 2.91. Rotation is estimated by least squares
over a constellation, so points FAR from the centroid give a long baseline for
angle; their positional noise matters far less for an angle than their span
helps. **The same landmarks that are a liability for translation are an asset for
rotation.** That is why §16.12's "averaging beats selecting" and this result do
not contradict each other — the estimand is different.

⚠ Smaller effect on `gate_live_ab` (p95 7.29 -> 5.65, max slightly worse). Not
yet a settled result: needs purpose-built takes.

#### ⚠ Two design questions this opens, neither yet answered

1. **Frame-to-frame vs grab-referenced.** The cube needs the delta from GRAB.
   A grab-referenced Kabsch gives it with no drift, but is corrupted by finger
   flex during the hold (the constellation changes shape). A frame-to-frame
   Kabsch is immune to slow shape change but ACCUMULATES drift when integrated.
   Palm-only grab-referenced is immune to both and still beats Gram-Schmidt
   (p95 11.71 vs 21.91).
2. ⚠ **The M6b precedent does NOT transfer, but its warning does.** §0.12
   measured "SVD frame 2.1x worse" — but that was an ABSOLUTE frame derived from
   the current point cloud (PCA-style), not a RELATIVE fit between two
   corresponding constellations. Different estimator, different failure mode.
   ⚠ What DOES transfer is M6b's Q1: **an SVD-based rotation can silently invert
   chirality**, a bug this project has shipped once (§13.6.1). Any Kabsch
   implementation must carry the `det` sign correction, and the chirality guard
   must be run against it before it goes anywhere near production.

**This is now the most promising open lead in Phase B**, ahead of the anchor
question — it targets a channel that is measurably broken (144° excursions on a
still hand), it uses information already available every frame, and it changes an
estimator rather than adding a layer.

### 16.14 ⛔⛔ RETRACTED (2026-08-17) — ARM B IS REJECTED, and this section's headline was an ALGEBRAIC IDENTITY

> ⛔ **DO NOT BUILD ON THE TABLE BELOW. Arm B was rejected on the live six-arm
> session of 2026-08-17 (§16.17). The "sink 0.000 on every axis" result is not a
> measurement — it is arm B's own formula restated.**
>
> **The proof, in one line.** `SINK` is defined as
> `corr( |cube − palm_centroid| / palm_width , edge_on_measure )`, and
> `hand_blocks.palm_position` / `palm_scale` are **the same `o` and `s` that
> `palm_anchor.Arm2D` builds its position out of**:
>
> ```
> Arm2D:  P = o + s·(Rx·ex + Ry·ey)     ⇒   |P − o| / s  ≡  |R|  ≡  frozen at grab
> ```
>
> The correlation's numerator is therefore a **constant for the entire grab**,
> and its correlation with anything at all is 0 **for any hand motion
> whatsoever**. Measured on the live takes: arm B's `|R|` has standard deviation
> **0.0000** (range 0.0001) within an uninterrupted grab, against §14.1's
> 0.4752–0.6056. The tiny non-zero residuals reported below (−0.001, −0.026 …)
> come from the `+40 px` cube-centre approximation in the scoring function, not
> from anchor behaviour.
>
> ⭐ **This is trap #4 of `HANDOFF_ANCHOR_ROTATION.md` §5 — *"a classifier that
> shares an expression with the thing it judges measures itself"* — landing on
> the PRIMARY decision criterion of an entire queue row.** It is the same class
> of error as §16.4's, one level deeper: §16.4 measured the right quantity on the
> wrong takes; §16.14 measured a quantity that could not have come out otherwise.
>
> **And the independent criterion goes the other way.** Live, arm B's
> **still-hand** position step is WORSE on all four takes — pitch 6.64 → 8.81,
> yaw 5.18 → **12.72**, back-of-hand 5.66 → **11.27**, free play 57.74 → 65.36 —
> against this section's claim that still-hand "does NOT degrade". Position max
> in free play blows out 49.60 → **261.68 px**. The mechanism is plain: §14.1
> averages **nine** landmarks so noise cancels, while arm B's `s` and `ex` each
> ride **two** (index-MCP, pinky-MCP), amplifying the noisiest quantity on the
> hand.
>
> ⚠ **What survives**: arm B's *rotational* behaviour is the physically honest
> one — its cube keeps a fixed bearing in the palm frame (range **0.0°**) while
> §14.1's sweeps a full **358.8°**, i.e. §14.1's cube does not rotate with the
> hand at all. The owner saw this directly and described it as *"the cube
> rotating around the hand instead of around itself."* If an anchor is ever
> revisited, that is the property worth keeping — with a noise-robust scale
> (`hand_skeleton.palm_width_world()`), not two raw landmarks.
>
> Re-runnable: `analysis/b4_orbit_and_sink_audit.py`. **Any future anchor metric
> must compare against a quantity the anchor does not define.**

Seven purpose-built takes (2026-08-06/07) — the **first** in this project that
contain the conditions §16.4/§16.5 argued about. §16.4 measured the sink on takes
with no sustained yaw and no pitch crossing and produced a confident wrong answer.

⭐ **Validation first**: this harness measures §14.1's pitch sink at **−0.807**;
§16.5 independently measured **0.822**. The harness reproduces the known number
before being trusted for a new one.

| take | §14.1 p95 / max / stillMax | **ARM B** p95 / max / stillMax | SINK §14.1 → **arm B** |
|---|---|---|---|
| 3 yaw | 2.74 / 8.88 / 1.88 | 4.64 / 14.49 / 3.43 | −0.656 → **0.000** |
| **4b pitch** | 5.09 / 13.57 / **4.81** | 8.11 / 25.07 / **4.64** | **−0.807 → −0.000** |
| 5 depth | 1.83 / 5.56 / 1.28 | 1.83 / **4.67** / 1.39 | −0.589 → **−0.001** |
| 6 back-of-hand | 4.91 / 25.61 / 3.56 | 6.35 / 30.52 / **3.44** | −0.083 → **0.000** |

**Arm B eliminates the systematic sink on every axis**, reproducing §16.5's
0.005/0.001 on data that actually contains the conditions. Cost: p95 jitter
+30–70% on yaw/pitch/back-of-hand, **unchanged on depth**. ⭐ **The worst
STILL-HAND step does not degrade** (pitch 4.81→4.64, back 3.56→3.44).

#### ⚠⚠ AND THE 3D-NATIVE DESIGN OF §16.11 IS OVERTURNED

Same palm centroid, same idea, radically different result — pitch axis:

    §14.1 incumbent            p95  5.09   max 13.57   stillMax  4.81
    ARM B (2D)                      8.11       25.07             4.64
    3D-native (palm + Horn)        27.80       72.22            36.43

⭐ **§16.11 argued the 3D palm quaternion was "free, because it is computed every
frame anyway". IT IS NOT FREE — it costs the DEGENERACY of that frame**, which
collapses at edge-on, exactly where the anchor is needed and exactly where pitch
drives the hand. Arm B's axis is a pixel direction and its scale a pixel width,
so both foreshorten with the projection and neither can degenerate.

> ⭐ **FOR THE ANCHOR, STAYING IN 2D IS NOT A LIMITATION — IT IS A SHIELD.**
> The general lesson: prefer the representation that cannot degenerate over the
> one that is more "correct" but shares a failure mode with the sensor.

⚠ Arm C (no scale term) is measurably wrong: yaw −0.745, depth −0.873. **The
scale term is what decouples the sink** — §16.5 said this and it replicates.

### 16.15 ⚠ AMENDED (2026-08-17) — HORN SHIPPED, but the 10× DID NOT REPRODUCE LIVE

> ⚠ **The table below is replay evidence and its headline did not survive.**
> Live (§16.17), the shipped Gram-Schmidt frame and Horn emit **the same ~60°
> jumps to within 1°** on the same frames — 62.38 vs 61.83, 57.73 vs 57.58,
> 49.71 vs 48.53. Nothing like 39.94° → 9.64° occurs.
>
> ⭐⭐ **And that near-identity is itself the most useful finding of the session.
> If two structurally unrelated estimators — a 3-vector Gram-Schmidt frame and a
> least-squares fit over 5 points — reproduce the same 60° jump on the same
> frame, the jump is ALREADY IN THE LANDMARKS. No rotation estimator can remove
> it.** That re-points the residual orientation failure (queue **T1/T2**) at the
> landmark layer — items 1.5 / 1.6 / 1.7 and the SmoothNet-class item 5.4 — and
> closes off further estimator work as a route to it.
>
> ⛔ **`PALM_AND_TIPS` is REJECTED — and this section's protocol is what hid it.**
> The fingertip constellation with `mode="ref"` assumes *"the hand does not change
> shape during the hold"*. In ordinary play the fingers move, so the fit reads
> **finger motion as hand rotation**: orientation p95 **9.85 → 27.79**, ~3× worse
> than the incumbent. The takes that validated it required fingers *"relaxed and
> still"*, which is precisely the condition under which this failure cannot
> appear. ⚠ **A protocol that forbids the motion an estimator is sensitive to has
> not tested it.**
>
> ✅ **What shipped: `Horn(PALM_LANDMARKS, "ref")` — palm-only, no fingertips**,
> ported to `Resources/HandsTriggeredActions.py` on 2026-08-17 and live-confirmed
> by the owner. ⚠ **It shipped on DESIGN grounds, not measured benefit** — the
> balanced blind A/B scored **4–2, p = 0.34**, and p95 was **3–3**. It is not
> better; it is not worse, and a least-squares fit over 5 points cannot degenerate
> the way a 3-vector frame can. State it that way to anyone who asks.

⚠ §16.13's estimator-level result had no cube-level price attached, because the
harness measured cube POSITION only. Measured properly — the shipped rotation
path (delta from grab, slerp 0.35), with the quaternion supplied by each
estimator — **cube orientation step, deg/frame, held cube**:

| take | Gram-Schmidt (SHIPPED) p95 / max / stillMax | **Horn palm+tips (ref)** |
|---|---|---|
| 3 yaw | 2.74 / 5.64 / 5.64 | 2.72 / 6.89 / **3.84** |
| **4b pitch** | 7.42 / **39.94** / **22.89** | 3.82 / **9.64** / **4.21** |
| 5 depth | 0.61 / 1.63 / 1.63 | **0.41 / 0.79 / 0.79** |
| **6 back-of-hand** | 5.36 / **58.86** / **36.54** | 2.18 / **8.40** / **3.48** |

**Pitch: worst step 39.94° → 9.64°, worst still-hand step 22.89° → 4.21°.
Back-of-hand: 58.86° → 8.40° and 36.54° → 3.48° — a 10× reduction** in the two
bands §0.18 calls a sensor floor. Better on every take.

⚠ `ff` (frame-to-frame) edges out `ref` everywhere but **ACCUMULATES DRIFT,
unmeasured**. **`ref` is the ship candidate** — drift-free by construction, and
still 4× on pitch max and 7× at back-of-hand.

⭐ **Horn, not SVD-Kabsch, and that is a safety property**: Horn's answer IS a
quaternion, so a reflection is unrepresentable and handedness cannot silently
invert. §13.6.1 shipped that bug once; M6b's Q1 exists to catch it. Here it is
designed out. `verify_palm_rotation.py` proves it, including on the mirrored
input MediaPipe delivers (§0.9).

⚠ **Power iteration was tried first and was WRONG** — any shift large enough to
guarantee positivity drives λ₂/λ₁ → 1, leaving up to 2.0 of element error, i.e. a
completely wrong rotation at large angles. Caught by the golden vectors before it
reached a measurement. Replaced with a Jacobi eigen-decomposition.

#### Status: BUILT, NOT PORTED

`Resources/palm_rotation.py` (25 golden vectors) and `palm_anchor.Arm2D`
(27 golden vectors). Both are selectable in `debug_prediction.bat`:

    debug_prediction.bat            SIX windows, 3 rows x 2 columns:
        1 §14.1 | 2 §14.1+B7        <- production today
        3 ARM B | 4 ARM B+B7        <- anchor changed
        5 +HORN | 6 +HORN+B7        <- rotation changed

⭐ **Each row is a ONE-VARIABLE change on the row above, verified rather than
assumed** (replayed on the pitch take): the anchor moves ONLY cube position, the
rotation estimator moves ONLY cube orientation.

| row | cube POSITION p95 / max | cube ORIENTATION p95 / max |
|---|---|---|
| 1 §14.1 | 5.09 / 13.57 | 6.22 / 37.57 |
| 3 arm B | **8.11 / 25.07** | 6.22 / 37.57 *(unchanged)* |
| 5 arm B + Horn | 8.11 / 25.07 *(unchanged)* | **3.82 / 9.64** |

Nothing leaks between rows, so a difference seen on screen has exactly one cause.

⚠ **Nothing is in production. A7 holds: §14.1 does not change until the owner
accepts a live look.** ⚠ Both results are REPLAY evidence on seven takes from one
operator, one camera, one session.

### 16.16 ✅ EXECUTED 2026-08-17 — the six-arm live decision (results in §16.17)

> ✅ **This session RAN on 2026-08-17.** Outcome: **§14.1's anchor keeps** (A7
> never broken), **arm B rejected** (§16.14), **`Horn(PALM_LANDMARKS)` shipped**
> (§16.15), **B7's park confirmed under a blind test** (§16.17). The
> pre-registered decision rule below could **not** be applied as written, because
> its primary criterion — SINK — turned out to be degenerate for the candidate it
> was meant to judge. That is recorded in §16.14 and is the session's main
> methodological result.

The owner runs a six-arm live session; the analysis picks the winner and it gets
wired into both the debug tool and production. **The plan, the takes, and the
decision criteria are fixed IN ADVANCE** in `Claude/HANDOFF_ANCHOR_ROTATION.md`
— written before the data exists, so the criteria cannot be chosen to fit it.

Decision rule, binding: **ship the row that minimises the SINK on the pitch
take**, provided its still-hand step is not materially worse than §14.1's, its
cube-orientation max is not worse, and the owner accepts how it looks in free
play. ⭐ **Sink first, jitter second** — §16.5: *"a systematic drift is the defect
the operator actually reported; jitter is not."* ⚠ And the owner's eye outranks
the table: B7 passed every measured criterion and was still, correctly, parked.

Score with `analysis/b4_six_arm_verdict.py` — it reads all six cube tracks
**recorded live**, so no replay confound applies (the offline harness had two).

#### ⚠⚠ What the 2D anchor will cost later, recorded now while it is cheap

**Z-axis.** Arm B's frozen `R` is a 2-vector, so a cube cannot be held in front
of or behind the palm. ⭐ The one decision that makes the retrofit cheap is
already taken — **`R` is stored in PALM WIDTHS, not pixels**, so it is scale-free
and a third component is purely additive. ⚠ But the third axis `ez` can only come
from the 3D palm reconstruction — the channel that degenerates at edge-on and the
measured reason the 3D-native variant loses. So the retrofit adds *a component
whose axis is unreliable in exactly the band arm B was built to survive*; plan a
DR-2-style freeze for it. ⛔ And the real blocker is unchanged: **absolute depth
does not exist in the data at all** (world landmarks are hand-relative), which is
true of every anchor design including §14.1's.

**Web/mobile port.** Both modules are already port-clean (stdlib, numpy-free,
deterministic). Their golden vectors — 27 + 25 — are the executable
specification, written *before* a port exists (U3). ⚠ `palm_rotation` contains a
**Jacobi eigen-decomposition**; a port that "simplifies" it back to power
iteration silently returns wrong rotations at large angles, and
`verify_palm_rotation.py` §1 is the test that catches that. ⚠ A port that swaps
Horn for SVD-Kabsch **must** add the `det` sign correction — §13.6.1 shipped a
silent handedness inversion once, and Horn's quaternion makes it unrepresentable.

### 16.17 ⭐⭐ THE LIVE SESSION — what shipped, what died, and the two method lessons (2026-08-17)

Eleven live six-arm takes plus twelve blind rounds, one operator, one camera.
Everything below is **live**, not replay. Takes:
`E:\…\Recordings_anchor_study\2026-08-17_18*`.

#### ⛔ First: four takes were lost to a one-character bug, and no metric caught it

`LiveBlockPredictionDebug.py` guarded the block that feeds rows 2 **and** 3 with
`if args.arms == 4:`. Commit `2c44634` added the Horn row (`--arms 6`) and made 6
the **default** without widening it, so at the default setting `data_anch` stayed
`None` on every frame: **rows 2–6 never acquired a cube on 4257 recorded frames**,
`owner` null throughout, cube frozen at spawn. `--arms 4` worked; `--arms 6` had
never been run live. **The operator caught it by eye** — *"in the 4 windows
starting from second row, none of the cubes are grabbed nor move"* — after the
takes were recorded and while the verdict script was happily scoring them.

⭐ **Fix + guard**: the end-of-run `[arms]` summary now prints how many frames
each arm held the cube and shouts `NEVER ACQUIRED` on zero, while the take can
still be re-recorded. ⚠ **A take is only comparable while the cube is
CONTINUOUSLY HELD** — after a drop each arm's cube sits somewhere different, so
re-acquisition diverges and the one-variable guarantee dies. That is a recording
requirement, not a nicety.

#### The verdicts

| candidate | verdict | why |
|---|---|---|
| **§14.1 anchor** | **KEEPS** — A7 never broken | arm B lost on the one criterion that could still discriminate |
| **ARM B** | ⛔ **REJECTED** | still-hand worse on all 4 takes; its winning metric is an identity (§16.14) |
| **HORN `PALM_AND_TIPS`** | ⛔ **REJECTED** | p95 9.85 → 27.79 in play; finger motion read as rotation (§16.15) |
| **HORN `PALM_LANDMARKS`** | ✅ **SHIPPED** | not better (4–2, p = 0.34), not worse, structurally safer |
| **B7 confirmation gate** | ⛔ **PARK CONFIRMED** | 4–2 blind, p = 0.34 — real but imperceptible |

#### ⭐⭐ Method lesson 1: a metric that shares an expression with its subject

§16.14 in full. The short form: **SINK could not have said anything other than
"arm B wins."** Any future anchor metric must compare against a quantity the
anchor does not define.

#### ⭐⭐ Method lesson 2: an unbalanced blind test MANUFACTURES results

Two blind series were run on the same operator, same task, same day.

| series | design | result |
|---|---|---|
| horn-palm vs Gram-Schmidt | 6 rounds, **free** random draw | **5–1 for horn-palm** — looked convincing |
| B7 vs no B7 | 6 rounds, **balanced** 3/3 | 4–2, p = 0.34 — nothing |
| horn-palm vs Gram-Schmidt, **redone** | 6 rounds, **balanced** 3/3 | **4–2, p = 0.34 — the 5–1 did NOT replicate** |

The operator answered in a perfectly alternating pattern (A,B,A,B,A,B) in both
early series — the textbook signature of guessing. A free draw put one arm on "A"
in 4 of 6 rounds, and **the alternation alone reproduces 5–1**. Enumerated:
P(alternating guess scores ≥ n−1) is **10.9%** for 6 free rounds, **5.0%**
balanced, **1.4%** for 8 balanced. The 10.9% *is* the 5–1 that was nearly
believed — and it was nearly used to justify shipping.

✅ **Binding for every future blind test: use `--blind-series`**, which draws one
balanced permutation for the whole series and consumes one round per run. Never a
free per-run draw. ⚠ **And no channel may leak the condition** — the hand blocks
had to stop carrying B7's amber/red channel colouring, which would have announced
the gated window outright.

#### What is now in production

`Resources/HandsTriggeredActions.py` drives cube orientation with
`Horn(PALM_LANDMARKS, "ref")`; 25/25 golden vectors pass, live-confirmed by the
owner. `LiveSnapDebug.PRODUCTION_ROTATION` is the single shared definition, and
`debug_snap.bat`, `RecordRotationDebug.py` and `RecordTranslationPivotDebug.py`
all pass it explicitly. ⚠ `update_hands(rotation=None)` **still means
Gram-Schmidt on purpose** — `LiveBlockPredictionDebug` rows 1–2,
`b4_anchor_rotation_ab.py` and `b7_live_ab.py` all rely on it to hold rotation
constant. Change that default and three A/Bs silently start comparing a thing
against itself.

### ⚠ Binding architectural constraint (spec S3, Apple's shipped design)

**Predicted state must NEVER reach a gesture state machine.** The split is:
predicted blocks for *rendering / attachment*, unpredicted blocks for *grab and
release decisions*. Prediction artifacts must not latch into a gesture. Build the
split even if prediction is later skipped entirely.

---

## 17. ⭐⭐ THE INPUT SYSTEM (`handinput`) — BUILT 2026-08-25, queue IS1/IS2/IS3

> **Owner, 2026-08-24:** *"I want to be able to later ship independently this hand
> detection system as an input system (for my game, or for any other purpose such as
> a filter on Snapchat for example) ... mimicking the input system of Unity: the hand
> detection system would trigger callbacks with context, etc."* And on scope:
> *"I have no preference for the language. The current setup seems to work so if we
> can continue as current, with minimum modifications later on, this is fine."*

### 17.1 What was built, and what was deliberately NOT

`Local_pc/Movement_with_hand_detection/handinput/` — a Unity-Input-System-shaped
surface: five **actions**, Unity's five **phases**, `+=` **callbacks** carrying a
context, a **polling** API beside them, and `HandState` v2 as the serialisable
contract. Package README: `handinput/README.md`. Suite:
`analysis/verify_handinput.py` (**95 checks**).

⛔⛔ **THE SCOPE LINE, AND IT IS THE WHOLE ARCHITECTURE.** Unity ships **two**
packages — the **Input System** (devices → actions → callbacks, no scene
knowledge) and the **XR Interaction Toolkit** (grab, hold, arbitration, which has
it). This is the FIRST only. Snap proximity, arbitration, sticky grab,
owner-follows-track, the grab-relative transforms and the play volume all stay in
`HandsTriggeredActions.py` / `LiveSnapDebug.py`. ⭐ That is why the action is
`grab_ready` (**eligibility**) and never `grab`: "grab WHAT" needs a scene, and
answering it inside the module would weld it to this one game.

### 17.2 ⭐⭐ THE DECISION THAT MADE IT SHIPPABLE IN ONE SESSION: it OBSERVES, it does not DRIVE

Every value it publishes was computed by the gesture logic that already ran that
frame. It recomputes nothing and it drives nothing — **no cube is snapped, moved
or released by it.** So the change could not alter behaviour, and the evidence
says it did not: `parity_replay` **NO DIVERGENCE** on 454 frames, and 24 of 25
existing suites pass (the 25th, `verify_planar_pnp.py`, fails on a **console
encoding error printing a `⚠` character** and fails identically with the change
reverted — pre-existing, unrelated, worth fixing separately).

⚠⚠ **AND THE REASON IS THE PROJECT'S OWN SCAR TISSUE, NOT TASTE.** A layer that
re-derived the palm centre, the depth or the cue from landmarks would be a THIRD
implementation of the pipeline. Four harnesses in one session reported CLEAN on
takes the owner had just watched fail, every time because they recomputed what
production had already decided — which is why `_record_flush` records the cue
instead of re-deriving it. **The input system reports what RAN**, for the same
reason and by the same mechanism.

### 17.3 The five actions, and where each one's rule already lived

| action | kind | live when | the rule it publishes |
|---|---|---|---|
| `tracked` | button | `holds_track` — TRACKING **or** BRIDGING | ⭐ D2's 150 ms coast: a dropout does NOT cancel it, matching `GAME_RULES.md` rule 2 |
| `palm_pose` | value | TRACKING only | ⛔ a bridge has no measurement; publishing the last pose as current is the extrapolation **B8** measured losing to "hold the last value" |
| `palm_facing` | value | TRACKING | the palm/back cue + U8's `confirmed` + DR-2's `orientation_valid` |
| `grab_ready` | button | rule 3 **and** U8 **and** 4.2 DECISION 1 | the hand-side half of snapping, in one place |
| `rotation_delta` | value | reference set | the grab-referenced delta, starting at **identity** (§14.1's no-pop, expressed without an object) |

⭐ **The split between `tracked` and `palm_pose` is the most useful thing the layer
produces, and it fell out of a real recording rather than being designed**: a
replay of `2026-08-24_220415_prod_tau20` gives `tracked` **8** start/cancel pairs
against `palm_pose`'s **9** — the extra one is a bridge, where the hand is still
held but the pose has stopped updating. Two facts a consumer had no way to tell
apart before.

### 17.4 ⭐ CONFORMANCE — the authority moved out of Python

`handinput/conformance/` holds **vectors** (7 files, 64 cases: signs, chirality,
projection round-trips, the stateful depth/rotation/coast sequences) and a
**trace** (18 frames, 65 events: enter → provisional chirality → ready → rule 3
refusal → armed exception → frozen depth → rotation reference → coast → sustained
loss → re-entry).

⭐⭐ **WHY THIS AND NOT A 26th `verify_*.py`.** Those suites assert in Python, so
they can only ever test the Python; **a port cannot run them.** The same inputs
and outputs as JSON can be run by any language, which turns *"is the port
faithful?"* from an argument into a test. It is rule 6 (*golden vectors before a
port exists*) taken one step further. ⭐ And the **trace** is worth more than the
vectors: it pins **when** events fire — that a held button does not re-fire, that
a coast cancels the pose but not the track, that a dead track drops a rotation
reference — none of which is visible in any single-frame vector.

⛔ **Regenerating to turn a red suite green destroys the only thing they are for.**
A regeneration belongs in a commit that names the behaviour that changed.

### 17.5 ⭐⭐ THE ESTIMATOR MODULES WERE NOT MOVED — a decision, with its reasoning

The obvious shape would be `handinput/core/palm_geometry.py` and friends. **They
stay in `Resources/`,** because moving them costs real things and buys none:

* **~15 harnesses import them BARE** off `sys.path` (`sys.path.insert(0, ROOT +
  "/Resources")` then `import palm_geometry`), and **dozens of paths in
  `Claude/*.md` name their current location.** A move breaks working code and the
  project's own memory.
* The property that actually matters — *the input system depends on nothing from
  the game* — can be **asserted instead of arranged**. `verify_handinput.py` §1
  parses every file's imports with the **AST** (not a text search — this codebase
  is mostly comments, and a grep for `pygame` would hit one) and fails if any of
  `CubeWindow`, `HandsTriggeredActions`, `pygame`, `cv2`, `mediapipe`, `numpy` …
  appears. **A folder gives tidiness; the test gives a guarantee.**
* ⭐ **The closure was checked, not assumed**: the only non-local import anywhere
  in the nine manifest modules is `math`. `hand_state`, `hand_tracks` and
  `owner_remap` import nothing at all.
* And when the folder IS wanted, it is one command:
  `handinput/export_package.py <dir>` writes the package plus `core/` — **9
  modules, 4 416 lines, stdlib-only, numpy-free** — plus the conformance data.
  ⚠ Verified by running the exported copy standalone, with no repo on the path.

### 17.6 One shared-code fix that came with it

`palm_geometry.palm_center_px` — the §13.3 palm centre (wrist + four MCPs) — now
has **one** definition. It was written out identically in
`HandsTriggeredActions._hand_position` and `LiveSnapDebug._hand_position`; both
now delegate, exactly as `_is_thumb_outward` already did, and
`verify_handinput.py` §5 asserts the arithmetic is unchanged. ⚠ A duplicated
geometric convention is precisely how the palm/back sign drifted into the
production-only inversion of §13.6.1.

### 17.7 What is NOT done, so nobody assumes it is

* ⛔ **No live take yet.** The owner's own look in both tools is what closes a
  change here (§13.6.1's rule), and it had not happened when this was written.
  Automated evidence only: 95 new checks, 24 existing suites, `parity_replay` no
  divergence, a 454-frame real-recording replay, and a standalone export.
* ⛔ **No port.** TypeScript and C# were explicitly deferred by the owner. The
  conformance data exists so that when one happens it is checkable.
* ⛔ **The interaction tier is not extracted** and was left for later by the owner
  (*"if it can be implemented in the future with little change, let's keep it for
  the future"*). ⭐ It can: it changes **who consumes** this layer, not what the
  layer produces. Nothing in `handinput` presumes it.
* ⚠ `sources/recording.py` cannot produce `rotation_delta` events — a recording
  stores the cube's smoothed orientation, never the hand's reading. ⛔ Re-running
  Horn there to fill the gap would make a recomputation the reference for a
  conformance file. Use `HANDINPUT_TRACE=1` on a live session instead.

---

## 18. ⭐⭐ ROBUSTNESS & SECURITY AUDIT of the debug and production scripts (2026-08-25)

> **Owner:** *"do a full audit of the scripts of the debug and production and
> verify the robustness of the scripts, and if they are cybersecurity safe. If you
> correct any of the debug or production scripts, make sure you also correct the
> production or debug scripts so they keep mirroring each other."*

Scope: both capture loops and everything they import —
`LiveSnapDebug.py`, `HandsTriggeredActions.py`, `CubeWindow.py`, `Client.py`,
`PythonApp_Main.py`, `Launcher_for_Server_and_Client.py`, `VisionPipeline.py`,
`Server.py`, `inference.py`, `hands_visualizer.py`, the remap utilities,
`hand_identity.py`, the three `.bat` entry points, `requirements.txt`, and the
new `handinput/`. Suite: **`analysis/verify_hardening.py` (51 checks)**.

### 18.1 ⭐ WHAT THE AUDIT FOUND ALREADY RIGHT — this is the compliance evidence

Worth recording as findings, not assumed: these are the claims the store
declarations and the COPPA/GDPR-K position rest on, and they are now checked
rather than believed.

* ⭐⭐ **NO NETWORK EGRESS ANYWHERE.** Not one `urlopen`, `requests`, or HTTP call
  in the entire pipeline. *"Nothing leaves the device"* is verifiable **by
  absence**, which is the strongest form that claim can take.
* ⭐ **No `eval`, `exec`, `pickle`, `marshal`, `os.system`, `shell=True` or
  `yaml.load`** — so there is no deserialisation or command-injection surface at
  all. The wire format is `json.loads`, which cannot construct objects.
* ⭐ Both `subprocess.Popen` calls use the **list form** with paths derived from
  `__file__`, so neither argument-splitting nor PATH substitution applies.
* ⭐ Models load by **absolute path from the package directory** — bundled, never
  fetched (already verified for N13; re-confirmed here).
* ⭐ The socket **already defaulted to `127.0.0.1`**. Nothing shipped bound wider.

### 18.2 What was fixed — and both tools were corrected together

| # | finding | severity | fix | mirrored |
|---|---|---|---|---|
| **S1** | `--host` accepted **any interface**. `0.0.0.0` would put a live stream of hand *and face* landmarks on the LAN, unauthenticated | ⚠ **medium in the COMPLIANCE frame** — local-only is load-bearing for a youth audience, so a transmission is a reportable event, not a bug | non-loopback **refused** unless `--allow-remote` is passed deliberately; the refusal names the reason | ✅ server **and** client, plus the launcher forwards the flag so it cannot be half-applied |
| **S2** | the session tag is interpolated into a **path** in three places (`VISION_RECORD_TAG`, `--tag`, `HANDINPUT_TRACE_TAG`) with no check — `..\..\x` escapes the capture root, `:` or `*` fail with an OSError that reads like a broken drive | low (local, operator-supplied) but the classic finding of any review | one shared `Resources/session_paths.py`; **reject-and-substitute with a printed warning**, never silent repair — a recording whose name lies about the take is worse than a refused one | ✅ both recorders + `handinput/trace.py` |
| **S3** | the `meta` packet's resolution goes straight to `pygame.display.set_mode()` with **no upper bound** — `[100000, 100000]` asks for a ~40 GB surface | low-medium (needs a local process to hold the port first) | clamped to 8192, plus a **type check on every array element**: the consumers do arithmetic, so one string raised *mid-frame*, after part of the frame had been applied | n/a (client-only path) |
| **R1** | `Client.py`'s receive buffer was **unbounded** — a peer that never sends `\n` grows it until the process dies, and a server wedged mid-`sendall` has that exact shape | robustness | capped at 1 MB (~400× the largest real packet) and the connection dropped with a clear message | n/a |
| **R2** | `recv(4096).decode()` **per chunk** splits any multi-byte UTF-8 sequence straddling a chunk boundary | latent — today's payload is all-ASCII | buffer **bytes**, decode each complete packet. ⚠ Left as-is it would fail ~once every few hundred frames, at random, the first time a non-ASCII field is added | n/a |
| **R3** | ⭐ **a single failed `cap.read()` ended the session — in BOTH tools.** A USB hiccup or an exposure re-negotiation closes the window mid-take, and on a `--record` take that is the whole session | robustness, and it bites hardest exactly when it costs most | shared `capture_policy.read_frame()`: 30 attempts over ~0.3 s, then give up with a message naming the cause. ⛔ Deliberately **not** retry-forever — a tool that hangs on a dead camera is worse than one that exits | ✅ **both loops and both cold-start probes**, one module, identical constants |
| **R4** | `bind()` failure surfaced as a bare traceback, and *"a stray from the previous run holds the port"* is the normal cause (the children outlive their launcher by design) | robustness | a clear message that names `stop.bat` | n/a |
| **R5** | `analysis/verify_planar_pnp.py` printed `ALL GOLDEN VECTORS PASS` and then **exited 1** on a `UnicodeEncodeError` writing `⚠` to a cp1252 console | ⚠ worse than it sounds | added the `sys.stdout.reconfigure` guard every other suite already had. ⭐ **A permanently-red suite is worse than no suite: it teaches the reader to skip the red.** All 26 now pass | n/a |

### 18.3 ⛔ Found and deliberately NOT fixed — with the reason, so it is a decision

* ⛔⛔ **THE FACE DETECTOR RUNS EVERY FRAME AND NOTHING CONSUMES IT.** Its
  keypoints are computed, serialised and sent over the socket, and the client's
  dispatch is literally `elif datatype == "face": pass`. (`CursorController.py`,
  the Part Zero consumer it was for, is likewise defined and imported by nothing.)
  ⭐ It is **also a debug/production divergence** — `LiveSnapDebug.py` has no face
  detector at all — so the two pipelines differ in what they load and compute per
  frame. ⚠ **And it is a disclosure question**: with the audience decided as all
  public including youth, *"does this app run a face detector"* has a different
  answer depending on this, and running one for no consumer is the worst version
  of that trade. ⚠ **Do not expect a frame-rate win** — the capture rate is
  measured **camera-bound, not compute-bound**.
  ⭐ **A switch was added and the default was NOT flipped**: `--face off` stops
  the model, the computation and the wire packet. Turning it off is visible (the
  preview loses the overlay), so it is the owner's call, not an audit's.
  **Queue `SEC3`.**
* ⚠ **The debug recorder buffers the ENTIRE session in RAM and writes at exit;
  production streams.** Production's own comment says why streaming matters
  (*"production has no clean shutdown path... a buffered take would be lost"*).
  The debug tool's `finally` covers normal exits and exceptions but **not**
  `stop.bat` or a crash, and a 30-minute take is ~70 MB of live list. ⛔ Not
  restructured **on the same day as an unvalidated live take** — it is the tool
  the owner is about to judge the input system in. **Queue `SEC4`.**
* ⚠ **Both tools feed MediaPipe a FAKE clock**: `timestamp_ms += 33` per frame, a
  hardcoded 30 fps, while N7 measured the real rate at 15–24 fps. ⭐ They MIRROR
  each other, so this is not a divergence, and the timestamps are monotonic so
  MediaPipe's contract holds. ⛔ **Not changed here**, and see §18.4 — the first
  version of this bullet asserted a mechanism it had not measured. **Queue `SEC5`.**
* ⚠ **Only two direct dependencies are pinned** (`mediapipe==0.10.14`,
  `pygame==2.6.1`); the other **24 are transitive from mediapipe and float**.
  ⭐ Measured, not assumed: they have **already drifted past what mediapipe 0.10.14
  was built against** — numpy 2.4.6 and opencv-contrib-python 5.0.0.93. So the
  environment the corpus's numbers came from was unrecorded and not reproducible.
  `requirements.lock.txt` now records it; hash pinning and the licence inventory
  N13 needs belong to packaging. **Queue `SEC2`.**
* ⚠ `Client.py` connects **at import time**, so its packet-parsing loop cannot be
  unit-tested without a live socket. Verified this time by an ad-hoc fake server
  (below); restructuring it is more risk than value today.

### 18.4 ⚠⚠ A CORRECTION TO §18.3, MADE THE SAME DAY — and it is the audit's own lesson

The first version of §18.3's `SEC5` bullet said the fake clock means *"the tracker
is told the hand moves ~2× faster than it does, a plausible contributor to
landmark-layer jitter."*

⛔ **That is a hypothesis about MediaPipe's internals, and it was written as
though it were a finding.** In the Tasks API the VIDEO-mode timestamp is primarily
a **graph packet timestamp**; it is not established that the hand-landmarker graph
runs any velocity- or time-based filter that would consume it. The honest
statement is narrower: **the clock is wrong, and the effect on the output is
unmeasured — quite possibly nil.**

⭐ It is corrected here rather than quietly edited because it is exactly the
failure this project keeps a rejected-list for: *"a mechanism that sounds right"*
becoming a recorded fact, and then a build being sequenced around it. An audit is
not exempt from A10 just because its other findings are code-shaped.

⭐⭐ **AND THE CONSTRAINT THAT MAKES IT INTERESTING: THE CORPUS CANNOT TEST IT.**
Changing MediaPipe's *input* means re-running MediaPipe, and the corpus holds **no
image data at all** — 415 files, landmarks only, deliberately. There is nothing to
replay. ⭐ But a clean test needs no pixels and no new recording format: **two
`HandLandmarker` instances fed the SAME `mp_image` each frame**, one on `+= 33`,
one on the measured `tCapture`. Same camera, same frames, one variable, each
keeping its own tracking state — the multi-arm pattern `update_hands_all` already
implements, with the second inference free because the pipeline is camera-bound.
Both arms record through the existing recorder, so `t5h` scores it with no new
harness. A **null closes the item permanently**, which is worth as much as a hit.

### 18.5 How the fixes were verified

* **`analysis/verify_hardening.py`, 51 checks** — tag traversal (including the
  *property* that any tag joined under the root stays under it), the capture
  retry's recover **and** give-up paths with their exact call counts, the loopback
  refusal on both ends including the `--allow-remote` override, and the `meta`
  clamp — with a check that a **real** resolution is still accepted, because a
  guard that refuses everything passes every other check and breaks the pipeline.
* **An end-to-end hostile-server run** against the real `Client.py`: an oversized
  `meta`, a non-numeric array, a non-object packet, malformed JSON, and a packet
  **split mid-number across two TCP writes**. Every one was handled, the split
  packet reassembled silently, and the good frames still dispatched.
* **All 26 `verify_*` suites pass** (26/26 for the first time), `VerifyChirality
  Fixture` passes, and **`parity_replay` reports NO DIVERGENCE** — which is what
  says the mirrored edits did not pull the two tools apart.

---
