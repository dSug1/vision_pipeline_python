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
- **Part One step 2 (pinch gesture classifier) is in active, iterative
  development under `GESTURE_PIPELINE_SPEC.md`'s pipeline** — Stage 1
  (recording) is done and mature, Stage 3 (base classifier) has been built
  and retrained eight times with measured, logged improvement most rounds,
  Stage 3.3 (event layer) was attempted and found blocked on an earlier,
  worse classifier — worth a fresh attempt now, not assumed still blocked,
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

## 3. Stage 3 — base classifier (eight rounds of iteration, not finished, but real progress)

Current best model: **`mlp/raw_landmarks`** — rotation false-positive rate
**11.2% (best-ever)**, recall **0.643 (best-ever, first to clear the >0.6
target)**, F1 0.657, precision 0.671 (§3.2.8, 2026-07-31). History: rotation
FP 27.2% → 22.0% → 14.7% → 13.2% → 11.4% → **11.2%** across seven retrains
(`GESTURE_PIPELINE_SPEC.md` §3.2.1/§3.2.3/§3.2.4/§3.2.6/§3.2.7/§3.2.8 have
the full history). **Not a finished, reliable classifier yet** — still
short of §9.3's working target (rotation FP <~10%; recall now clears its
half).

**A real trade-off surfaced this round, worth reading before assuming "more
data" is a free lunch (§3.2.8)**: a controlled learning-curve ablation
(fixed test split, train on 1/1+2/1+2+3 distance-sets, rotation-negative
data held constant) found F1/recall/precision all improve monotonically as
held-state distance diversity grows, but **rotation-FP gets *worse*, not
better** (2.4%→11.1%→13.9% across the three set-counts) — the model
discriminates pinch from open_hand/fist better with more diverse data, but
does it via a less conservative decision boundary that also lets in more
rotation false positives. Same tension §3.2.5 found with class weighting,
now confirmed from a completely different lever.

**The §3.2.7 fusion representation's win did not hold up**: adding the
medium-distance set made `raw_plus_handcrafted` degrade sharply (F1
0.713→0.514, recall 0.576→0.494, rotation FP 11.4%→13.9%) while plain
`raw_landmarks` improved on the same corpus growth and is the new winner.
Root cause not yet verified (§8 item 5) — plausibly the third distance adds
noise the small hand-crafted component can't average out as cleanly across
three distances as it could across two.

**What's been tried, briefly** (full detail and citations in the spec):
hand-crafted vs. raw-landmark input representations, logistic regression
vs. a small hand-rolled MLP, a velocity-delta windowed feature (didn't
meaningfully help, §3.2.3), a prediction-error / predictive-coding-inspired
feature (§3.2.4), class-weighted training (rejected, §3.2.5), a
window-size sweep (ruled out window mis-tuning, §3.2.6), a fused
raw+hand-crafted representation (won at the time, later reversed, §3.2.7),
and a third-distance recording set + learning-curve ablation (§3.2.8,
this session) — real progress on rotation-FP/recall, but revealed the
recall-vs-rotation-FP tension is structural, not an artifact of any one
fix tried so far.

## 4. Prioritized next steps (in order)

Everything through §3.2.7 has been tried in sequence — summarized in §3
above, full detail in the spec. Current priority:

1. **Root-cause the fusion-representation reversal** (§8 item 5, new) —
   check `hand_size_ref` variance at the medium distance (mirroring
   §3.2.1's near/far diagnostic) before the next representation decision,
   rather than re-guessing why `raw_plus_handcrafted` degraded.
2. **Continue the continuous-improvement data loop** (`GESTURE_PIPELINE_SPEC.md`
   §9) on top of the new `raw_landmarks` winner — more `rotating_no_pinch`
   variety historically the strongest lever, though recent rounds are
   buying less each time (watch for a confirmed plateau). Also still-open
   from §9.2: `open_hand_palmup` density, and the confirmed `palm_out`
   framing gap (now reproduced at 2 distances — worth a deliberately
   different capture setup, not just another attempt).
3. **Working target**: base classifier rotation FP below ~10% and recall
   above ~0.6-0.7. Recall now clears its half (0.643); rotation FP (11.2%)
   is the closest yet but not there.
4. **Once that target is met (or the data loop plateaus per §9.3), resume
   event-layer tuning** (`GESTURE_PIPELINE_SPEC.md` §3.3.2,
   `tune_event_layer.py`) — built, and the design/tuning mechanics work,
   but blocked on base-classifier quality per the last attempt (which
   predates the current, better classifier — worth a fresh attempt once
   the working target is met). Also revisit the `palm_away`-specific
   finding there (fixed ratio-magnitude threshold doesn't work at that
   orientation) before considering the event layer done for all 6
   orientations.
5. **Then Stage 4** — the live debug tool. Not built yet; required before
   pinch counts as "done" per the spec's own rule (§2/§3, "not optional
   polish").

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
  `Resources/features.py` (pure feature extraction, including the
  windowed/prediction-error features and `extract_raw_plus_handcrafted_
  features`, §3.2.7 — not the current winner but still a compared
  representation every retrain), `Resources/classifier.py` (loads trained
  weights, runs the forward pass), `Resources/event_layer.py`
  (`PinchEventTracker`, blocked per §4 above), `train_pinch_classifier.py`
  (Stage 3, run this to retrain — auto-discovers recordings, auto-selects
  the winning model, prints a rotation stress test and misclassified-cell
  breakdown every run), `tune_event_layer.py` (Stage 3.3, currently
  blocked), `analyze_transition_window.py` (one-off analysis that produced
  the 300ms window constant), `sweep_prediction_error_window.py` (one-off
  window-size sweep, §3.2.6), `train_set_ablation.py` (one-off
  learning-curve ablation, §3.2.8 — reusable if a 4th distance set is ever
  added).
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
