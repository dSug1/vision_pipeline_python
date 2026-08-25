# Handoff — gesture classifier pipeline, current state and next steps

> **⚠ ARCHIVED (2026-08-01). For current work, start from
> `Claude/HANDOFF_SNAP_ROTATE_RELEASE.md` instead of this file.**
> Everything below documents the pinch gesture's full fix arc, ending in a
> live Stage 4 test (§2 below, added after this file's original writing)
> that found pinch still missed too many real grabs/releases and had a
> perceptible input lag — a real UX problem, not just an offline metric.
> **Pinch is archived** (code/corpus/weights kept, not deleted — reusable
> if revisited later). The project has pivoted to a new primary gesture
> set: proximity-based object snapping (built), open-palm rotation (in
> progress), closed-fist release (blocked, pending a working fist-
> detection approach) — full design and state-of-the-art check in
> `GESTURE_PIPELINE_SPEC.md` §13, plain-language rules in
> `Claude/GAME_RULES.md`, build-sequence pointer in `PART_ONE.md`'s
> updated §3 matrix. This file is kept as the historical record of the
> pinch arc — §0's lessons learned are written to generalize past pinch
> and are worth reading before continuing the new gesture's build.

Written 2026-08-01 (supersedes all earlier versions of this file), for
starting a **new** Claude Code conversation. Read this first, then
`GESTURE_PIPELINE_SPEC.md` §12 (the pencil-grip reset, through §12.7) —
that document is the living technical spec and source of truth; this file
is only an orientation pointer plus a prioritized action list.

**Repo state**: check `git status` before assuming anything — this
session's work (the corpus reset, the `pencil_rest` fix, multiple Stage
3/3.3 retrains, the `palm_up` diagnosis and re-recording, two bug fixes in
`train_pinch_classifier.py`, and the `DELTA_WINDOW_MS` re-derivation) has
not been committed as of this handoff.

## 0. Lessons learned this session, reusable for the NEXT gesture (grab/release/translate/depth/rotate)

Read this before starting Stage 3/3.3 work on any future gesture in the
Part One matrix — full detail and rationale in `GESTURE_PIPELINE_SPEC.md`
§12.7.

1. **Detection confidence and landmark precision are separate failure
   modes.** A fix for one does not fix the other — check MediaPipe's raw
   `score` field AND the raw feature signal (e.g. a ratio/angle time
   series on a held-still recording) independently when an orientation
   underperforms.
2. **Camera distance/framing tolerance is pose-dependent, not just
   orientation-dependent.** A distance fix for a compact pose (fist,
   pencil-grip) can break a spread pose (open hand) at the same position —
   re-verify every class recorded at a new camera position, not just the
   one that motivated the change.
3. **Model/config selection between two competing metrics needs a ceiling
   on the secondary metric, not a minimum with a tolerance band.**
   `min(secondary_metric)` — even tie-broken by a tolerance — always lets
   an arbitrarily small secondary-metric improvement override an
   arbitrarily large primary-metric cost, because the tolerance band just
   relocates the cliff. Select by "max(primary) among candidates with
   secondary under an absolute ceiling" instead.
4. **A hyperparameter that depends on another must be re-tuned every time
   the one it depends on changes**, in the same pass — not scheduled as a
   separate later task. (Event-tracker `window_frames` depends on
   `DELTA_WINDOW_MS`; changing one without the other leaves a stale,
   mismatched config.)
5. **A static per-frame metric (F1/recall on individual frames) can be
   structurally blind to real transition-timing behavior for any
   cyclic/event-based gesture.** Build a real, classifier-independent
   ground-truth signal (e.g. `find_peaks` on a raw geometric feature)
   before trusting that good static numbers mean the event layer will
   fire correctly on real transitions.
6. **Verify a ground-truth-extraction method itself before trusting a
   "bad" number it produces** — inspect the raw signal directly, don't
   just trust an aggregated statistic, whenever a number looks surprising
   in either direction.
7. **When comparing "before"/"after" numbers, confirm both came from the
   exact same pipeline configuration** — re-verify every hardcoded
   parameter in every diagnostic script matches the currently-active
   model/config before reporting a number as authoritative.
8. **Not every pose/orientation needs the same bar, and that decision
   should be explicit, literature-checked where possible, and revisited
   as new evidence arrives** — don't treat an orientation-priority
   decision as permanent.

Plus the standing discipline from earlier sessions, still true (§6 below).

## 1. Where the project stands — read this before doing anything else

**Pinch gesture: corpus reset to a pencil-grip definition, `pencil_rest`
data-gap fixed, `palm_up` diagnosed and corrected, two selection bugs
fixed, delta-window re-derived — Stage 4 live validation is the one thing
left.** Full account: `GESTURE_PIPELINE_SPEC.md` §12 (all subsections,
through §12.7). Short version, in order of what happened across the full
arc (spanning multiple sessions on 2026-07-31 and 2026-08-01):

1. The old (archived) corpus's open-hand pinch definition passed every
   recorded-data metric but failed live (Stage 4). Redefined pinch as
   index+thumb **contact**, other three fingers **curled closed**
   ("pencil grip"). Old corpus archived to `.../Unsuccessful_grip/`.
2. A systematic failure analysis found the held-state training taxonomy
   had no negative class for "pencil-grip shape at rest, not touching" —
   a rare loose-contact tail in `pinch` examples overlapped with that
   resting shape, leaving the model's decision boundary there
   unconstrained. Fix: a new `pencil_rest_<orientation>` class, all 36
   sessions recorded 2026-08-01 (corpus now 196 sessions).
3. Re-running the failure analysis with the new class found `palm_up`
   recalling far worse than `front`/`palm_in`/`palm_down`. Diagnosed to a
   measurably degraded MediaPipe detection confidence at that orientation
   (min 0.61 vs ≥0.94 elsewhere) — fixed by re-recording all 5 `palm_up`
   classes (30 files) at a corrected camera distance. But the cyclic
   `pinch_ratio` signal stayed noisy even after that fix — a landmark-
   *precision* limit, verified two independent ways, distinct from and
   not solved by the confidence fix. **`palm_up` moved to the
   accepted-weaker tier alongside `palm_away`/`palm_out`.**
4. `train_pinch_classifier.py`'s winner-selection logic was found to pick
   badly worse models **twice** in immediate succession, both times
   because it chased the global minimum of `rotation_fp_pct` and let a
   fractional-percentage-point difference override a 30+-point recall/F1
   gap. Redesigned (not just re-tolerance'd) to select the highest-F1
   candidate among those under an absolute rotation-FP ceiling (5.0%).
5. `DELTA_WINDOW_MS` re-derived against a real cycle-detection metric
   (not the old static-only one): 900ms→**200ms**, a deliberate balanced
   point between max cycle-detection recall (100ms, 101%) and rotation
   robustness (900ms, 0.8% FP). Full pipeline (Stage 3 representation
   comparison + Stage 3.3 event-layer tuning) re-run end-to-end at the
   new window, since a window change invalidates every downstream fit.
6. **Final, fully-reconciled numbers**: winner
   `mlp/raw_plus_handcrafted_plus_articulation` (rotation_fp=2.4%,
   F1=0.902, recall=0.927); event layer `window_frames=8`,
   `onset_ratio_fall=0.12` (1 false onset across 20 negative sessions);
   priority-orientation cycle-detection recall `front`=86.0%,
   `palmdown`=78.0%, `palmin`=69.0% (avg 77.7%, up from ~43.5-49.6% at
   the start of this fix arc).
7. **Stage 4 live-validated 2026-08-01, and it wasn't good enough**: ran
   `debug.bat` against the final pipeline state (item 6 above). Result:
   false positives were rare (consistent with the recorded rotation-FP
   numbers), but **false negatives (missed pinches/releases) were
   frequent, noticeably worse off `front`** (consistent with the recorded
   `palmin`=69% vs `front`=86% gap, but the live *feel* of missed
   individual attempts is worse than the aggregate percentage suggests),
   plus **a small but perceptible detection lag** between the real
   gesture and the reported event — a structural property of the event
   tracker's lookback window, not fixable by more tuning. **Decision:
   archive pinch** (code/corpus/weights kept, reusable later) and pivot to
   a simpler gesture set. Full account: `GESTURE_PIPELINE_SPEC.md` §13.
- **Part One's grab/release/translate/depth/rotate build is planned
  (approved plan) but its trigger gestures changed** (§13.3 of the spec,
  `PART_ONE.md`'s updated §3 matrix) — proximity-snap instead of pinch,
  `Closed_Fist` instead of un-pinch, rotation gated on `Open_Palm`. See
  §2 below for the pointer to the current active work.

## 2. Current active work — NOT in this file

This file's remaining sections (§3-§5 below) are the **historical
recording plan and verification steps for pinch**, kept for reference
since the recording workflow discipline (§12.3.1 of the spec) and most of
the general lessons still apply to whatever comes next. **The actual
current build plan lives in `GESTURE_PIPELINE_SPEC.md` §13 (design +
state-of-the-art check) and `PART_ONE.md`'s updated §3 matrix (build
order)** — start a fresh conversation from those two documents, not from
this file's action items, which are all pinch-specific and done/archived.

## 3. Files added/changed across this fix arc (for orientation, not a diff)

- `RecordSession.py`, `record.bat`: `--protocol` requirement, cyclic
  framing convention, uniform 5s duration.
- `Resources/features.py`: `DELTA_WINDOW_MS` now 200 (was 900, then swept
  properly against a real cycle-detection metric — see §1 step 5), new
  `extract_raw_plus_handcrafted_plus_articulation_plus_delta_features`.
- `train_pinch_classifier.py`: `pencil_rest_` added to
  `BASE_CLASS_PREFIXES`; new representations wired into `REPRESENTATIONS`/
  `_extract_by_representation`/`sessions_to_windowed_examples`; protocol
  assertions on load; **winner-selection logic redesigned** (§1 step 4) —
  `ROTATION_FP_CEILING = 5.0`, max-F1-under-ceiling instead of
  min-rotation-fp-with-tolerance.
- `tune_event_layer.py`: `window_frames` added to the sweep grid;
  top-10-by-raw-cycle-closeness diagnostic printout; new representations
  supported.
- `Resources/event_layer.py`: defaults re-tuned twice this arc, currently
  `window_frames=8`, `onset_ratio_fall=0.12` (matched to the 200ms
  classifier window — see §1 step 5, and don't let these drift out of
  sync again per lesson §0.4).
- `analyze_transition_window.py`: fixed a hardcoded-duration bug (now
  reads `duration_s` from each recording).
- `analyze_cycle_detection_failures.py`, `sweep_window_for_cycle_
  detection.py`: reusable diagnostic scripts built this arc — ground-truth
  vs. detected cycle counts by orientation/hand, and window re-sweeping
  against a real cycle-detection metric respectively. Both have their own
  hardcoded `BEST_PARAMS`/`PRIORITY_ORIENTATIONS` constants that must be
  kept in sync with `Resources/event_layer.py`'s actual defaults and the
  current orientation-priority tier (lesson §0.7) — check these first if
  their numbers ever look inconsistent with a fresh `tune_event_layer.py`
  run.

## 4. Environment notes

- **Recordings**: `E:\Python\Recordings for vision_pipeline\Pencil_style_grip\`
  (active corpus, 196 sessions) / `.../Unsuccessful_grip\` (archived, not
  read by anything).
- Python env: `Local_pc/Movement_with_hand_detection/.venv`.
- **Trained weights** (`Resources/pinch_classifier_weights.json`): as of
  this handoff, `mlp/raw_plus_handcrafted_plus_articulation` (200ms
  window, 196-session corpus, post-selection-redesign). Will be
  overwritten by the next `train_pinch_classifier.py` run — re-run the
  full arc (Stage 3 → Stage 3.3 → failure analysis) together if the
  corpus or `DELTA_WINDOW_MS` changes again, per lesson §0.4.

## 5. Standing discipline (accumulated across sessions — read before guessing again)

- **No heuristic pile-up, ever** — fix with better data or a literature-
  justified feature/model change, never a bolted-on special case. This
  applies to selection/tuning logic too, not just gesture features (see
  §0.3 — the winner-selection redesign replaced a patch with a principled
  rule instead of adding a second patch on top of the first).
- **Verify derived numbers before reasoning from them** — an entire wrong
  root-cause theory was once built on a transition-duration statistic
  that was silently 2x wrong due to a stale hardcoded constant, and this
  arc separately found `palm_up`'s own ground-truth cycle count was
  unreliable before the real issue was diagnosed. Check the code that
  computed a number before trusting conclusions drawn from it.
- **Search literature proactively** (see `feedback_proactive_literature_
  search` memory) — applied this arc to the orientation-priority and
  rotation-range questions, not just gesture-discrimination features.
- **Always retrain from scratch on the full combined corpus**, never
  incremental/warm-start fine-tuning.
- **Every representation/hyperparameter/window choice gets re-checked as
  the corpus, taxonomy, or a dependent parameter changes**, not assumed
  to carry over — true for `hidden_units` (found stale once), `DELTA_
  WINDOW_MS` (found stale twice), and the event-layer thresholds (must
  track `DELTA_WINDOW_MS`, see §0.4).
- **Live-test before declaring a gesture done** — Stage 3/3.3's recorded-
  data metrics have looked excellent multiple times now across this
  gesture's whole history and Stage 4 or systematic failure analysis
  found a real problem nearly every time. Don't skip either check for
  pinch or any future gesture, no matter how good the recorded numbers
  look.
