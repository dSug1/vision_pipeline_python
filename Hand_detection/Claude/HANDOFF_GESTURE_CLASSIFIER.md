# Handoff — gesture classifier pipeline, current state and next steps

Written 2026-07-31 (supersedes the 2026-07-30 version of this file), for
starting a **new** Claude Code conversation. Read this first, then
`GESTURE_PIPELINE_SPEC.md` — that document is the living technical spec
and source of truth for everything below; this file is only an orientation
pointer plus a prioritized action list.

## 1. Where the project stands

- **Part Zero** (PC, cube follows fingertip) and **Part Zero-bis** (browser
  port, live on GitHub Pages) are both done. See `PART_ZERO.md` /
  `PART_ZERO_BIS.md`. Not touched by anything below.
- **Part One step 1** (scaffolding: two-cube live pipeline) is built and
  confirmed working. Not touched by anything below.
- **Part One step 2 (pinch gesture classifier): Stage 3's working target is
  now MET (§3.2.9, 2026-07-31)** — rotation FP 5.5%, recall 0.724, both
  clearing §9.3's bar simultaneously for the first time. Stage 1
  (recording) is done and mature, Stage 3 (base classifier) went through
  nine retrain rounds to get here, Stage 3.3 (event layer) was attempted
  and found blocked on an earlier, much worse classifier — **that blocker
  is now lifted, resuming event-layer tuning is the natural next step**,
  Stage 4 (live debug tool) has not been started. Full detail below.

## 2. Stage 1 — recording corpus (done, mature)

- **148 recordings total** on `E:\Python\Recordings for vision_pipeline`
  (moved off the local disk 2026-07-31 — see §5 below for why this matters
  for anyone continuing on this PC).
- Full 6-orientation taxonomy (`front`/`palm_away`/`palm_up`/`palm_down`/
  `palm_in`/`palm_out`) recorded for `pinch`/`open_hand`/`fist`, at **three
  camera distances** — near, far (§3.2.1's "Re-run (2026-07-31)" note), and
  a third "medium" distance added this session (§3.2.8). **Known gap**:
  `pinch_palmout` and `fist_palmout` have zero clean sessions at the medium
  distance — `palm_out` produced near-total both-hands-detection failure
  (0-8%) across 4 repositioning attempts, confirming this is a genuinely
  hard orientation to keep both hands in frame for, not a one-off framing
  mistake (mirrors the older `fist_palmout` gap at other distances, §9.2).
- **14 `rotating_no_pinch` sessions** (grown from 5 → 9 → 11 → 14,
  deliberately varied: slow, fast, small twitches, translating-while-
  rotating, large circular path, rapid direction-reversal twisting) —
  historically the single biggest lever for reducing rotation-induced
  false positives, but the 9→11 round only bought ~1.5 points (§3.2.6) —
  watch for continued plateau.
- `pinch_cycles` (6 orientations) and `pinch_rotate_release` (4 reps) are
  recorded for the event layer (Stage 3.3) — not classifier training data.

## 3. Stage 3 — base classifier (working target MET, §3.2.9)

Current best model: **`mlp/raw_plus_handcrafted`, `hidden_units=24`** —
rotation false-positive rate **5.5%**, recall **0.724**, F1 0.748,
precision 0.773 (§3.2.9, 2026-07-31). **Both halves of §9.3's working
target (rotation FP <~10%, recall >~0.6-0.7) are now met simultaneously,
for the first time.** History: rotation FP 27.2% → 22.0% → 14.7% → 13.2% →
11.4% → 11.2% → **5.5%** across nine retrains (`GESTURE_PIPELINE_SPEC.md`
§3.2.1 through §3.2.9 have the full history). `mlp/raw_landmarks` is a
close second (6.0% FP, 0.719 recall) — checked across 6 seeds, both
representations hold up (rotation FP range 4.5-6.6%, recall range
0.713-0.822 for the winner), not a lucky single run.

**The key late-session finding (§3.2.9): the recall-vs-rotation-FP tension
that persisted through §3.2.5/§3.2.6/§3.2.8 turned out to include a stale
hyperparameter, not just a structural data trade-off.** `hidden_units=4`
was chosen via a sweep against the *original* 2,281-example corpus
(§3.2.1) and never revisited as the corpus grew ~7x to 15,408 train
examples. A fresh sweep found bigger hidden layers **decreased** the
train/test F1 gap (0.242 at hidden=4 down to 0.169-0.182 at 8-24) — the
small model was *underfitting* the larger input space, not overfitting a
small one, the opposite of §3.2.1's original finding on the smaller
corpus. This also resolved §3.2.8's confusing "fusion representation
regression" — `hand_size_ref` variance at the new medium distance was
checked and found to be the *lowest* of the three distances (not a noise
problem), and the real cause was the same stale `hidden_units=4` capping
what the richer 70-dim fused input could learn.

**What's been tried, briefly** (full detail and citations in the spec):
hand-crafted vs. raw-landmark input representations, logistic regression
vs. a small hand-rolled MLP, a velocity-delta windowed feature (didn't
meaningfully help, §3.2.3), a prediction-error / predictive-coding-inspired
feature (§3.2.4), class-weighted training (rejected, §3.2.5), a
window-size sweep (ruled out window mis-tuning, §3.2.6), a fused
raw+hand-crafted representation (§3.2.7), a third-distance recording set +
learning-curve ablation (§3.2.8, revealed a real recall-vs-rotation-FP
trade-off from data alone), and finally re-sweeping `hidden_units` against
the now much-larger corpus (§3.2.9) — which is what actually closed the
gap.

## 4. Prioritized next steps (in order)

The base classifier is no longer the bottleneck. Current priority:

1. **Resume event-layer tuning** (`GESTURE_PIPELINE_SPEC.md` §3.3.2,
   `tune_event_layer.py`) — built, design/tuning mechanics work, was
   blocked purely on base-classifier quality, and that classifier was far
   worse (0.90 confidence spikes during pure rotation) than the current
   one. Re-run against the current `pinch_classifier_weights.json`, not
   assumed still blocked. Also revisit the `palm_away`-specific finding
   there (fixed ratio-magnitude threshold doesn't work at that
   orientation — `pinch_ratio` barely moves there even during a real
   pinch) before considering the event layer done for all 6 orientations.
2. **Then Stage 4** — the live debug tool. Not built yet; required before
   pinch counts as "done" per the spec's own rule (§2/§3, "not optional
   polish").
3. **Lower priority, still open**: `open_hand_palmup` density (§9.2), and
   the confirmed `palm_out` framing gap (`pinch_palmout`/`fist_palmout`
   have zero clean sessions at the medium distance, reproduced failure
   across 4 attempts — worth a deliberately different capture setup next
   time, not just another attempt at the same one).
4. **Continuous-improvement data loop** (§9) remains available if the
   event layer surfaces a new weak case, per the pipeline's standard
   "record it as an explicit case, retrain" discipline — not a scheduled
   next step on its own anymore now that the working target is met.

## 5. Environment notes

- **Recordings live on the external drive**: `E:\Python\Recordings for vision_pipeline`
  — not the local disk. Both `RecordSession.py` and
  `train_pinch_classifier.py` point there; if the drive isn't plugged in,
  `RecordSession.py` fails fast with a clear error. `RecordSession.py` now
  also stores `duration_s` in every new recording's JSON (added
  2026-07-31) — needed for correct real-time window sizing since capture
  fps varies with hardware load (~15fps near-distance vs ~27fps
  far-distance observed).
- Python env: `Local_pc/Movement_with_hand_detection/.venv` (created by
  `launch.bat` on first run) — used for every script mentioned here,
  including the ones that live in the sibling
  `Python_Server_MediaPipe_vision_pipeline/` folder.
- Key scripts, all in `Local_pc/Movement_with_hand_detection/`:
  `Resources/features.py` (pure feature extraction, including
  `extract_raw_plus_handcrafted_features`, §3.2.7 — the current winning
  representation), `Resources/classifier.py` (loads trained weights, runs
  the forward pass), `Resources/event_layer.py` (`PinchEventTracker`, no
  longer blocked per §4 above — ready for a fresh tuning attempt),
  `train_pinch_classifier.py` (Stage 3, run this to retrain —
  auto-discovers recordings, auto-selects the winning model via
  `hidden_units=24` MLPs per §3.2.9, prints a rotation stress test and
  misclassified-cell breakdown every run), `tune_event_layer.py` (Stage
  3.3, ready to re-run against the current classifier), `analyze_
  transition_window.py` (one-off analysis that produced the 300ms window
  constant), `sweep_prediction_error_window.py` (one-off window-size
  sweep, §3.2.6), `train_set_ablation.py` (one-off learning-curve
  ablation, §3.2.8 — reusable if a 4th distance set is ever added).
- Trained weights: `Resources/pinch_classifier_weights.json` — always
  regenerated by retraining, never hand-edited (`GESTURE_PIPELINE_SPEC.md`
  §3.2.2's rule).

## 6. Standing discipline (unchanged, still applies)

- **No heuristic pile-up, ever** (§2) — a misclassification gets fixed
  with more/better data or a literature-justified feature/model change,
  never a bolted-on special case.
- **Always retrain from scratch on the full combined corpus**, never
  incremental/warm-start fine-tuning (§3.2.2) — cheap at this dataset
  size, and keeps every result traceable to one real training run.
- **The continuous-improvement loop (§9, new) is deliberately separate
  from backbone changes (§8)** — don't let a routine data-recording round
  turn into an ad-hoc architecture tweak; log a diminishing-returns signal
  first, then make a deliberate, logged decision to open a §8 item.
