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
  and retrained three times with measured, logged improvement each round,
  Stage 3.3 (event layer) has been attempted and is currently blocked,
  Stage 4 (live debug tool) has not been started. Full detail below.

## 2. Stage 1 — recording corpus (done, mature)

- **112 recordings total** on `E:\Python\Recordings for vision_pipeline`
  (moved off the local disk 2026-07-31 — see §5 below for why this matters
  for anyone continuing on this PC).
- Full 6-orientation taxonomy (`front`/`palm_away`/`palm_up`/`palm_down`/
  `palm_in`/`palm_out`) recorded for `pinch`/`open_hand`/`fist`, at **two
  camera distances** (near + far — a deliberate second pass after the
  first distance's classifier was found to generalize poorly to a
  different distance, see `GESTURE_PIPELINE_SPEC.md` §3.2.1's "Re-run
  (2026-07-31)" note).
- **9 `rotating_no_pinch` sessions** (grown from 5, deliberately varied:
  slow, fast, small twitches, translating-while-rotating) — this has been
  the single biggest lever for reducing rotation-induced false positives,
  bigger than any feature-engineering attempt tried so far.
- `pinch_cycles` (6 orientations) and `pinch_rotate_release` (4 reps) are
  recorded for the event layer (Stage 3.3) — not classifier training data.
- Known small gap: `fist_palmout` has only 1 clean rep (camera-framing
  issue at that specific orientation, not resolved — low priority, see
  `GESTURE_PIPELINE_SPEC.md` §9.2).

## 3. Stage 3 — base classifier (three rounds of measured improvement, not finished)

Current best model: **`mlp/raw_landmarks`** — rotation false-positive rate
**14.7%**, recall **0.594**, F1 **0.654**. This is real, measured
improvement (27.2% → 22.0% → 14.7% rotation FP across three retrains — see
`GESTURE_PIPELINE_SPEC.md` §3.2.1/§3.2.3/§3.2.4 for the full history of
what was tried each round and why), but **not a finished, reliable
classifier yet** — 14.7% per-frame false positives during pure rotation is
still meaningful, and a precision/recall tension appeared in the latest
round (every hand-crafted-feature variant's recall collapsed below the
eligibility gate as the `rotating_no_pinch` corpus grew, leaving raw
landmarks — usually the less-preferred representation per this project's
own literature-grounded default — as the only eligible winner). This is
flagged as likely a training-procedure issue (class imbalance, fixable
with class-weighted training) rather than a reason to abandon hand-crafted
features generally — see `GESTURE_PIPELINE_SPEC.md` §8's top item.

**What's been tried, briefly** (full detail and citations in the spec):
hand-crafted vs. raw-landmark input representations, logistic regression
vs. a small hand-rolled MLP, a velocity-delta windowed feature (didn't
meaningfully help — literature-grounded but an honest non-fix, §3.2.3), a
prediction-error / predictive-coding-inspired feature modeled directly on
neuroscience literature about voluntary-action-onset detection (built,
tested, real progress but confounded with simultaneous corpus growth so
its isolated effect isn't yet cleanly measured, §3.2.4).

## 4. Prioritized next steps (in order)

1. ~~Try class-weighted training~~ — **done, 2026-07-31, and rejected**
   (`GESTURE_PIPELINE_SPEC.md` §3.2.5): balanced class weighting does fix
   the hand-crafted recall collapse (0.2–0.29 → 0.7–0.86) but only by
   shifting the decision threshold toward predicting "pinch" more often
   globally, which raises rotation false positives right along with it
   (9–17% → 35–53%, worse than the original abandoned rule-based
   classifier's 38.5%, §1). Not adopted. Current winner is unchanged:
   `mlp/raw_landmarks`, rotation FP 14.7%, recall 0.594, F1 0.654. The
   `class_weight="balanced"` capability is kept in the code (not deleted)
   in case a smarter, more targeted weighting scheme is worth trying later
   — but that's a new idea, not a re-run of what was just measured.
1b. ~~Isolate the prediction-error features' contribution~~ — **partially
   done, 2026-07-31, via a window-size sweep** (`GESTURE_PIPELINE_SPEC.md`
   §3.2.6, `sweep_prediction_error_window.py`): swept 100-1200ms ×
   velocity/prederror/full × logreg/MLP (48 runs). **Window size is ruled
   out as the cause of the recall collapse** — recall stayed stuck at
   0.11-0.28 across the entire range for every window-dependent
   representation, never near `MIN_RECALL=0.4`. Combined with §3.2.5
   (class weighting also doesn't fix it), two of three "maybe it's just a
   tuning problem" explanations are now closed off, narrowing toward a more
   fundamental representational limitation of these features under the
   current corpus. `handcrafted_static` (no window) not covered — check
   separately before assuming it shares this finding.
2. **Continue the continuous-improvement data loop** (`GESTURE_PIPELINE_SPEC.md`
   §9) — one round done since, 2026-07-31: 9→11 `rotating_no_pinch` sessions
   (added a large-amplitude circular path and rapid direction-reversal
   twisting), retrained. Rotation FP 14.7%→13.2%, only ~1.5 points — below
   §9.3's 2-3-point diminishing-returns bar for the first time. Not yet a
   confirmed trend (one round), but watch closely on the next round.
   Winner unchanged: `mlp/raw_landmarks`.
3. **Working target before moving on**: base classifier rotation FP below
   ~10% and recall above ~0.6-0.7. Not there yet (13.2% / 0.540, current
   winner `mlp/raw_landmarks`).
4. **Once that target is met (or the data loop plateaus per §9.3), resume
   event-layer tuning** (`GESTURE_PIPELINE_SPEC.md` §3.3.2,
   `tune_event_layer.py`) — built, and the design/tuning mechanics work,
   but blocked on base-classifier quality per the last attempt. Also
   revisit the `palm_away`-specific finding there (fixed ratio-magnitude
   threshold doesn't work at that orientation — `pinch_ratio` barely moves
   there even during a real pinch) before considering the event layer done
   for all 6 orientations.
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
  windowed/prediction-error features), `Resources/classifier.py` (loads
  trained weights, runs the forward pass), `Resources/event_layer.py`
  (`PinchEventTracker`, blocked per §4 above), `train_pinch_classifier.py`
  (Stage 3, run this to retrain — auto-discovers recordings, auto-selects
  the winning model, prints a rotation stress test and misclassified-cell
  breakdown every run), `tune_event_layer.py` (Stage 3.3, currently
  blocked), `analyze_transition_window.py` (one-off analysis that produced
  the 300ms window constant, not needed again unless the window itself is
  being reconsidered).
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
