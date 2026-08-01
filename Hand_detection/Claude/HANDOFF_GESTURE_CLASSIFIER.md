# Handoff — gesture classifier pipeline, current state and next steps

Written 2026-07-31 (supersedes all earlier versions of this file — same
day, after a same-day pivot), for starting a **new** Claude Code
conversation. Read this first, then `GESTURE_PIPELINE_SPEC.md` §12 (the
pivot) and then the rest of that document — it's the living technical spec
and source of truth; this file is only an orientation pointer plus a
prioritized action list.

**Repo state**: everything described below except the last commit (`ef8da56`)
is uncommitted at handoff time — this session's work (Stage 4 build, the
corpus reset, and the wire-protocol/grab-release plan) has not been
committed. Check `git status` before assuming a clean tree.

## 1. Where the project stands

- **Part Zero**, **Part Zero-bis**, and **Part One step 1** (scaffolding)
  are done and untouched by anything below. See `PART_ZERO.md`/
  `PART_ZERO_BIS.md`/`PART_ONE.md` §1.
- **Part One step 2 (pinch gesture classifier) hit a live-validation wall
  and its corpus was reset this session (2026-07-31) — read
  `GESTURE_PIPELINE_SPEC.md` §12 for the full account.** Short version:
  Stage 3 (base classifier, `raw_plus_handcrafted_plus_articulation`,
  rotation FP 2.7%/recall 0.739) and Stage 3.3 (event layer) both passed
  their recorded-data targets. Stage 4 (`LiveGestureDebug.py`, built this
  session) was then run live for the first time — and firing behavior
  didn't match the recorded metrics at all: onset/offset events fired far
  more often and less predictably on both hands than the numbers predicted.
  **Diagnosis**: the pinch gesture itself was under-specified — recorded as
  "thumb/index close, on an otherwise freely-posed hand," not a fixed pose,
  which is consistent with two loose ends this project already found and
  hadn't fully resolved (`PART_ONE.md` §6.1's other-finger curl overlap,
  §7.2's relaxed-hand timing overlap). **Decision**: redefine pinch as
  index+thumb **contact** with the other three fingers **curled closed**
  (a "pencil grip"), and **rebuild the corpus from scratch** under that
  definition — not a patch on the existing model.
- **Corpus reset, already executed this session**: old corpus (163
  recordings) moved to `E:\Python\Recordings for vision_pipeline\Unsuccessful_grip\`
  (archived, not deleted, no longer read by any script). New corpus goes in
  `.../Pencil_style_grip\`. All four scripts that read `RECORDINGS_DIR`
  (`RecordSession.py`, `train_pinch_classifier.py`, `tune_event_layer.py`,
  `analyze_transition_window.py`) are repointed there already.
- **Stage 1 (recording) for the new corpus is DONE** — 160 sessions
  (36 pinch/open_hand/fist each, 36 `pinch_cycles`, 6
  `pinch_rotate_release`, 5+5 `rotating_no_pinch` variants). **A second,
  independent bug was found and fixed before recording started** (spec
  §12.3): an archived "held-state" `pinch_front` session turned out to
  contain three grip/release dips, not one continuous hold — ~60% of its
  frames were silently mislabeled positive "pinch" the whole project
  history. `RecordSession.py` now requires an explicit `--protocol
  {held_state,cyclic}` flag, shown on-screen and saved in the output JSON,
  and the training/tuning scripts assert it on load — see §3 below.
- **Stage 3 is DONE and retrained against the new corpus** (spec §12.4):
  the delta-window (`features.DELTA_WINDOW_MS`) was re-swept first —
  300ms→900ms, rotation FP 2.5%→0.9% on the winning representation — then
  the full representation comparison re-run from scratch.
  `mlp/raw_plus_handcrafted_plus_articulation` wins again, same as the
  archived corpus, but now at **rotation FP 0.9%, recall/F1 1.000**
  (archived corpus: 2.7%/0.739/0.679). Trained weights already saved to
  `Resources/pinch_classifier_weights.json`. **Not yet live-validated** —
  a near-ceiling held-out score on a small test set (20 sessions) is
  exactly the kind of number that needs Stage 4 before being trusted.
- **Part One's grab/release/translate/depth/rotate build is planned
  (approved plan at the time of writing) but paused**, pending a
  live-validated pinch signal against the new corpus — see §4.

## 2. What's still valid from before the reset

- **Methodology, not data.** `GESTURE_PIPELINE_SPEC.md`'s pipeline (§2's
  core discipline, §3's stage structure, §5's 6-orientation/3-distance
  recording taxonomy) is unchanged — only the pinch *pose definition* and
  the *corpus* reset, not the process.
- **Code**: `Resources/features.py`, `classifier.py`, `event_layer.py`,
  `train_pinch_classifier.py`, `tune_event_layer.py` all still work
  unchanged against the new corpus once it exists — nothing about the new
  pose definition requires new feature-extraction code, only new recorded
  examples. `LiveGestureDebug.py`/`debug.bat` (Stage 4) also carries over
  unchanged, and is exactly what will validate the rebuilt classifier live
  once it exists.
- **§9.3's working target** (rotation FP < ~10%, recall > 0.6–0.7) and
  **§3.3's ~3-onset-per-cycle event-layer target** still apply — re-measure
  against the new corpus, don't assume the old numbers transfer.
- **§10/§10.1 (context/prior layer) and §11 (event-layer literature scan)**
  are untouched by the reset — both were already staged for later,
  independent of which corpus trains the base classifier.

## 3. New pinch definition and recording protocol (spec §12.1/§12.3, full detail there)

**Pinch = index tip and thumb tip in contact, middle/ring/pinky held curled
closed** (a "holding a pencil" grip) — not thumb-index proximity on a
freely-posed hand. Still a trained classifier over continuous features,
not a reversion to hand-picked rules — contact/curl define the *recording
label*, not a live runtime rule.

**Two recording protocols, now required and explicit (spec §12.3), never
inferred from the label**:
- **`held_state`**: one continuous hold for the whole capture, every frame
  is unambiguously the labeled class. Used for `pinch_*`/`open_hand_*`/
  `fist_*`/`rotating_no_pinch*`.
- **`cyclic`**: three grip/release repetitions within the capture, frames
  are not uniformly one class — event-layer tuning data only. Used for
  `pinch_cycles_*`/`pinch_rotate_release`.
- Pass via `record.bat <label> <held_state|cyclic> [duration]` (or
  `RecordSession.py --label ... --protocol ...`) — saved in the JSON's
  `"protocol"` field, shown on-screen live during recording, and asserted
  on load by `train_pinch_classifier.py`/`tune_event_layer.py`/
  `analyze_transition_window.py` (raise loudly on mismatch).
- **Uniform 5s duration for every session** (explicit direction,
  2026-07-31) — note this is a faster cadence than `PART_ONE.md` §7.2's own
  "record cyclic gestures slowly, don't rush" lesson recommends for 3 reps;
  a known, flagged tradeoff, not an oversight (spec §12.3's closing note).
- **Cyclic framing**: a `cyclic` capture starts already closing into the
  first grip (no neutral pre-roll) and ends right at the final release (no
  neutral post-roll) — maximizes transition coverage inside 5s. Stored as
  `"protocol_note"` in the saved JSON, not just documented here.

**Recording taxonomy for the new corpus** (same shape as before, §5):
- Full 6-orientation × 3-distance grid for `pinch` (now pencil-grip,
  `held_state`), `open_hand`/`fist` (unchanged, `held_state`), and the
  `pinch_cycles`/`pinch_rotate_release` event-layer sessions (`cyclic`).
- `rotating_no_pinch` (`held_state`) recorded **two ways**: normal relaxed
  hand (as before) **and** `rotating_no_pinch_pencilrest` — a near-
  pencil-grip resting shape (fingers curled, thumb close to but not
  touching index) while rotating — the real adversarial case for the new
  definition. Both variants pool into the same negative class for
  training (`train_pinch_classifier.py`'s `classify_label` handles the
  `_pencilrest` suffix) but stay distinct cells for weak-cell analysis.
- **Do not reuse anything from `Unsuccessful_grip/`** — full fresh corpus.

## 4. Prioritized next steps (in order)

1. ~~Record the new corpus~~ — **done**, 160 sessions.
2. ~~Re-run Stage 3's representation comparison from scratch~~ — **done**
   (spec §12.4). Delta-window re-swept 300ms→900ms first
   (`sweep_prediction_error_window.py`, extended to cover the current
   winning representation). `mlp/raw_plus_handcrafted_plus_articulation`
   wins again — rotation FP **0.9%**, recall/F1 **1.000** (archived corpus:
   2.7%/0.739/0.679). Weights already saved.
3. ~~Re-tune Stage 3.3~~ — **done, mixed result** (spec §12.4.1).
   Specificity solved (0 false events across 40 `rotating_no_pinch`
   hand-sessions, `event_layer.py` defaults updated). Sensitivity
   (~1.3-1.4 onsets/session vs ~3 target) hit a **cadence ceiling, not a
   threshold ceiling** — a 405-point grid (adding `window_frames` to the
   sweep) confirmed it. Root cause: this corpus's own measured transition
   timing (onset median 1165ms, offset median 597ms) doesn't fit inside
   the 5s/3-rep cyclic recording budget (~1.6s/cycle) — reps very likely
   run back-to-back with no settled apex/idle time. Fix is re-recording
   `pinch_cycles`/`pinch_rotate_release` at a longer duration, not more
   tuning — **not done automatically, left for explicit direction**.
4. **Re-validate Stage 4 live** (`debug.bat`) — this is the gate that
   found the problem last time, so it's the gate that confirms the fix,
   not something to skip because the recorded numbers look good (spec
   §12.4's own caveat: near-ceiling scores on a small 20-session test set
   are exactly what needs this check).
5. **Resume the paused Part One plan** (grab acquisition/arbitration,
   release, translation, depth proxy, rotation — `PART_ONE.md` §3 rows
   3–7) once Stage 4 is live-validated against the new corpus. The
   approved plan's content (wire-protocol extension for `world_landmarks`,
   shared live-pinch-state helper, grab/release logic, then
   translate/depth/rotate) is unchanged by the reset — it was paused, not
   redesigned.
6. **Once back to normal priority-ordering**: §10/§10.1's context/prior
   layer and §11's event-layer literature scan (both still staged for
   later, see spec), then `open_hand_palmup` density (§9.2).

## 5. Environment notes

- **Recordings live on the external drive**:
  `E:\Python\Recordings for vision_pipeline\Pencil_style_grip\` (active) /
  `.../Unsuccessful_grip\` (archived, old corpus) — not the local disk.
  `RecordSession.py` fails fast if the drive isn't plugged in.
- Python env: `Local_pc/Movement_with_hand_detection/.venv`.
- Key scripts, all in `Local_pc/Movement_with_hand_detection/` unless noted:
  `Resources/features.py` (pure feature extraction, unchanged by the
  reset), `Resources/classifier.py` (`predict_from_landmarks` covers every
  static representation shipped so far), `Resources/event_layer.py`
  (`PinchEventTracker`), `train_pinch_classifier.py` (Stage 3, retrains all
  representations), `tune_event_layer.py` (Stage 3.3), `train_set_
  ablation.py` (learning-curve ablation), `sweep_prediction_error_
  window.py` (superseded finding, kept), `LiveGestureDebug.py` + `debug.bat`
  (Stage 4 — built and smoke-tested 2026-07-31, then live-tested once and
  found the corpus problem this file documents), `RecordSession.py`
  (`Python_Server_MediaPipe_vision_pipeline/`, recording tool).
- **Trained weights** (`Resources/pinch_classifier_weights.json`) are
  current as of this handoff: `mlp/raw_plus_handcrafted_plus_articulation`,
  retrained against the pencil-grip corpus (spec §12.4) — rotation FP 0.9%,
  recall/F1 1.000. Will be overwritten again if `train_pinch_classifier.py`
  is re-run (e.g. after corpus growth or another representation check).

## 6. Standing discipline (unchanged, still applies)

- **No heuristic pile-up, ever** — a misclassification gets fixed with
  more/better data, a literature-justified feature/model change, or (new
  lesson this session) a **gesture-definition** fix — never a bolted-on
  special case. The corpus reset itself is an instance of this discipline,
  not an exception to it: the fix is cleaner data, not a patch on the
  existing model.
- **Search literature proactively, before being pointed at a direction**
  (see `feedback_proactive_literature_search` memory) — still applies; the
  finger-articulation feature and the context/prior-layer proposal are the
  examples so far.
- **Always retrain from scratch on the full combined corpus**, never
  incremental/warm-start fine-tuning.
- **Every representation and hyperparameter choice gets re-checked as the
  corpus changes**, not assumed to stay optimal — true for corpus *growth*
  (§3.2.9's stale-hyperparameter finding) and now also true for a corpus
  *definition change* like this one.
- **Live-test before declaring a gesture done** — the concrete lesson of
  this session: Stage 3/3.3's recorded-data metrics passed their targets
  and Stage 4 still found a real problem. Held-out test data validates the
  model against its own training distribution; it cannot validate that the
  training distribution matches real use. Don't skip Stage 4 again, for
  pinch or any future gesture, no matter how good the recorded numbers look.
