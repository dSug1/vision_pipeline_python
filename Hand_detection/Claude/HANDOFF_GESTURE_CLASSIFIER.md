# Handoff — gesture classifier pipeline, current state and next steps

Written 2026-07-31 (supersedes the earlier 2026-07-31 version of this
file), for starting a **new** Claude Code conversation. Read this first,
then `GESTURE_PIPELINE_SPEC.md` — that document is the living technical
spec and source of truth for everything below; this file is only an
orientation pointer plus a prioritized action list.

**Repo state**: working tree clean, everything described below is
committed (up to and including `ef8da56`, "continue build"). Nothing
pending to commit at handoff time.

## 1. Where the project stands

- **Part Zero** (PC, cube follows fingertip) and **Part Zero-bis** (browser
  port, live on GitHub Pages) are both done. See `PART_ZERO.md` /
  `PART_ZERO_BIS.md`. Not touched by anything below.
- **Part One step 1** (scaffolding: two-cube live pipeline) is built and
  confirmed working. Not touched by anything below.
- **Part One step 2 (pinch gesture classifier): Stage 3's working target is
  MET and then improved further (§3.2.10, 2026-07-31)** — rotation FP
  **2.7%**, recall **0.739**, both well past §9.3's bar. Stage 1
  (recording) is done and mature. Stage 3.3 (event layer) is re-tuned
  against the current classifier and shows real, measured progress (false
  rotation events down from 16/8 to 6/3) but has **not** yet hit its own
  ~3-onset-per-cycle target — the remaining gap looks structural (one fixed
  threshold can't work at every orientation, `palm_away` specifically) not
  a classifier-quality problem anymore. **Stage 4 (live debug tool) is now
  built** (`LiveGestureDebug.py` + `debug.bat`, this session) but not yet
  visually validated against a live hand — see §4 item 1 below. A
  **forward-looking design note (§10, plus §10.1 refinement, of the spec)**
  for a context/prior-weighted layer was written this session, for later —
  no code yet, deliberately staged until real object-interaction state
  exists to condition on.

## 2. Stage 1 — recording corpus (done, mature)

- **148 recordings total** on `E:\Python\Recordings for vision_pipeline`
  (moved off the local disk 2026-07-31).
- Full 6-orientation taxonomy recorded for `pinch`/`open_hand`/`fist` at
  **three camera distances** — near, far, and a third "medium" distance
  added this session (§3.2.8). **Known gap, reproduced twice**:
  `pinch_palmout`/`fist_palmout` have zero clean held-state sessions at
  medium distance, and `pinch_cycles_palmout` also failed there — `palm_out`
  is a genuinely hard orientation to keep both hands in frame for at this
  setup, not a one-off framing mistake. Accepted, not chased further.
- **14 `rotating_no_pinch` sessions** (grown 5→9→11→14) — historically the
  single biggest classifier lever, though recent rounds buy less each time.
- **`pinch_cycles`/`pinch_rotate_release` now recorded at all three
  distances** (medium added §3.3.4) — previously only covered near/far,
  which was a real gap since event-layer tuning was being evaluated against
  data from distances the classifier wasn't even best at.

## 3. Stage 3 — base classifier (target met, then improved again)

Current best model: **`mlp/raw_plus_handcrafted_plus_articulation`,
`hidden_units=24`** — rotation FP **2.7%**, recall **0.739**, F1 0.679,
precision 0.628 (§3.2.10, 2026-07-31). History: rotation FP 27.2% → 22.0%
→ 14.7% → 13.2% → 11.4% → 11.2% → 5.5% → **2.7%** across ten retrains.

**Two findings this session actually closed the long-running
recall-vs-rotation-FP tension** (not just improved it):

1. **A stale hyperparameter** (§3.2.9): `hidden_units=4` was tuned against
   a corpus 7x smaller than current and never revisited. Bigger hidden
   layers *decreased* the train/test gap (was underfitting, not
   overfitting) — `hidden_units=24` cleared the target across 6 seeds.
2. **A genuinely new feature, found via literature search rather than
   hyperparameter search** (§3.2.10/§3.3.3): `extract_finger_articulation_
   features()` measures whether fingertips move *with* the hand's rigid
   (MCP-based) reference frame (rotation) or *independently* of it (a real
   pinch) — grounded in CV rigid-vs-articulated motion segmentation and
   hand-biomechanics postural-synergy literature, found proactively (not
   after being pointed at the idea — see `feedback_proactive_literature_
   search` memory for why that distinction matters going forward). This is
   the first improvement in the whole project's history where rotation-FP
   and recall improved *together* by giving the model new discriminating
   information, rather than by shifting a decision threshold.

**What's been tried, briefly** (full detail and citations in the spec):
hand-crafted vs. raw-landmark representations, logistic regression vs. MLP,
velocity-delta and prediction-error windowed features, class-weighted
training (rejected), a window-size sweep (ruled out), a fused
raw+hand-crafted representation, a third-distance recording set +
learning-curve ablation, re-sweeping `hidden_units`, and finally the
finger-articulation feature — §3.2.1 through §3.2.10 in the spec.

## 4. Prioritized next steps (in order)

1. **Validate the new Stage 4 live debug tool against a real hand** —
   `LiveGestureDebug.py`/`debug.bat` (built this session, in
   `Local_pc/Movement_with_hand_detection/`) opens the webcam, runs
   `HandLandmarker`, and overlays live confidence/`pinch_ratio`/event-layer
   state, console-logging onset/offset transitions. It's been smoke-tested
   (imports cleanly, model/weights paths resolve, ran the live capture loop
   for several seconds with no traceback) but **not watched with an actual
   hand in frame** — that's the one thing this session couldn't do itself,
   and per the spec's own Stage 4 rule ("not optional polish"), it's what
   actually validates the live MediaPipe→model data path and the
   classifier's/event layer's real-world feel, which held-out test data
   structurally cannot. Run it (`debug.bat`, or `debug.bat <camera_index>`
   for a non-default camera) and check whether confidence/state track a
   real pinch the way the recorded metrics (§3.2.10, §3.3.4) suggest — if it
   reveals a systematic failure mode, that's new information for Stage 1/3.3
   per §3's own rule, not something to patch around in the live tool.
2. **Event-layer tuning is in progress, not finished** (§3.3.4) — re-tuned
   against the current classifier, real measured progress (rotation false
   onsets 16→6, offsets 8→3; cycle onset/offset means climbing each round:
   0.79→1.07→1.15 onset, 0.67→0.96→1.00 offset), but still below the
   ~3-per-cycle target. **Root cause identified**: `palm_away` scores zero
   onsets/offsets across every single session (already known —
   `pinch_ratio` barely moves there, not fixable by classifier quality).
   The fixed-threshold event layer design is the ceiling now, not the
   classifier. Next lever: either accept the current numbers (Stage 4 is
   now built, so this no longer blocks moving on), or build the
   orientation-aware prior layer (§10) early to directly address this — a
   deliberate choice, not a default.
3. **The context/prior-weighted layer (§10/§10.1, new, design-only)** — a
   product-of-experts fusion of the classifier's output with a
   context-dependent prior (orientation, grab-state, proximity-to-object),
   literature-grounded (Bayesian grasp-intent fusion, "Context as Prior,"
   Bayesian HMM gesture priors, reach-to-grasp object-directedness).
   **§10.1 adds a specific, literature-checked orientation prior**: grip
   axis (thumb-index line) aligns with an object's *minor* (short) axis,
   hand orientation with its *major* (long) axis — a biomechanical-
   stability finding (*J Neurophysiol*, "On the Relation Between Object
   Shape and Grasping Kinematics"), which for most tabletop objects means
   grabbing along the long dimension, orthogonal to gravity. Child
   development literature (rod-orientation studies, Newell 1993) shows this
   hand-to-object orientation matching is learned from ~5 months and becomes
   *anticipatory* by 10-12 months. Concrete mechanism proposed: precompute
   each grabbable object's principal axes, derive an expected pinch
   orientation from them, and let `P(pinch|context)` measure how closely
   observed hand orientation matches that *object-specific* expectation —
   not a flat 6-orientation lookup table. Explicitly **not implemented** —
   staged for when the object-control pipeline integration gives real
   object geometry/positions to condition on. `palm_away`'s event-layer gap
   is the concrete first use case identified for the base layer.
4. **A literature scan of event-layer alternatives (§11, new, not
   implemented)** — done proactively (2026-07-31) in response to a direct
   ask, logging CUSUM/Page-Hinkley online change-point detection,
   Caramiaux et al.'s particle-filter-based adaptive gesture tracking, and
   rolling-baseline thresholding as options for the `palm_away` ceiling
   beyond §10's context/prior layer. **Notably, the change-point option
   doesn't need real object context and so is buildable independently of
   §10** — but per explicit direction the same day, none of this is being
   built now either: object-scene integration is still too early, and focus
   is moving to the next gesture(s) instead. Revisit §10/§11 together later.
5. **Lower priority, still open**: `open_hand_palmup` density (§9.2).

## 5. Environment notes

- **Recordings live on the external drive**: `E:\Python\Recordings for vision_pipeline`
  — not the local disk. `RecordSession.py` fails fast if the drive isn't
  plugged in.
- Python env: `Local_pc/Movement_with_hand_detection/.venv`.
- Key scripts, all in `Local_pc/Movement_with_hand_detection/`:
  `Resources/features.py` (pure feature extraction — `extract_finger_
  articulation_features` and `extract_raw_plus_handcrafted_plus_
  articulation_features` are the current winning representation, §3.3.3),
  `Resources/classifier.py` (`predict_from_landmarks` now covers every
  static representation this project has shipped a winner from — fixed
  this session after being caught by a real integration gap),
  `Resources/event_layer.py` (`PinchEventTracker`), `train_pinch_
  classifier.py` (Stage 3, retrains all representations incl. the
  articulation one, `hidden_units=24`), `tune_event_layer.py` (Stage 3.3 —
  now supports windowed representations via an explicit
  `WINDOWED_REPRESENTATIONS` set, not just static ones), `train_set_
  ablation.py` (learning-curve ablation, §3.2.8), `sweep_prediction_error_
  window.py` (§3.2.6, superseded finding but kept), `LiveGestureDebug.py` +
  `debug.bat` (Stage 4, new this session — live webcam confidence/event-state
  overlay, not yet visually validated, see §4 item 1).
- Trained weights: `Resources/pinch_classifier_weights.json` — currently
  `raw_plus_handcrafted_plus_articulation`, 72 input dims, `hidden_units=24`
  (1,825 params) — always regenerated by retraining, never hand-edited.

## 6. Standing discipline (unchanged, still applies)

- **No heuristic pile-up, ever** — a misclassification gets fixed with
  more/better data or a literature-justified feature/model change, never a
  bolted-on special case. This applies to the event layer's `palm_away`
  gap too: the fix is an orientation-aware prior (§10), not an
  `if orientation == "palm_away"` special case.
- **Search literature proactively, before being pointed at a direction** —
  new discipline this session (see `feedback_proactive_literature_search`
  memory), after a pattern of the user having to suggest a strategy before
  a literature search happened to back it. The finger-articulation feature
  and the context/prior-layer proposal are the first two things this
  actually applied to correctly (unprompted search generating the
  direction, not just justifying one already given).
- **Always retrain from scratch on the full combined corpus**, never
  incremental/warm-start fine-tuning.
- **Every representation and hyperparameter choice gets re-checked as the
  corpus grows**, not assumed to stay optimal — §3.2.9's stale-hyperparameter
  finding is the concrete lesson: `hidden_units=4` was correct once and
  silently became wrong as the corpus grew 7x.
