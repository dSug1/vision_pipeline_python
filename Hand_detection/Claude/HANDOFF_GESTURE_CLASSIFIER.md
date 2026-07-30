# Handoff — gesture classifier pipeline, pinch reset

Written 2026-07-30, for starting a **new** Claude Code conversation. Read
this first, then the two docs it points to. This is a mid-project handoff,
not a project overview — `Specification.md` is the overview if that's
needed too.

## 1. Where the project stands

- **Part Zero** (PC, cube follows fingertip) and **Part Zero-bis** (browser
  port, live on GitHub Pages) are both done. See `PART_ZERO.md` /
  `PART_ZERO_BIS.md`. Not touched by anything below.
- **Part One** step 1 (scaffolding: red cube added, both hands' landmarks
  flowing through `Local_pc/Movement_with_hand_detection/`) is **built and
  confirmed working live** — run `launch.bat` in that folder, blue cube
  follows the left hand, red cube follows the right. Not touched by
  anything below.
- **Part One step 2 (pinch detection) was built, tested, found
  insufficient, and reset today.** This handoff is about what happened
  there and what to do next. Full evidence trail: `PART_ONE.md` §6–§8
  (marked historical at the top of that file). The short version is §2
  below.

## 2. Why pinch detection was reset (short version — full evidence in `PART_ONE.md`)

A rule-based pinch classifier (hand-tuned thresholds: a thumb-index
distance ratio + a finger-curl angle, later a closing-velocity window) was
built, and it worked well for the hand orientation it was calibrated
against. Then:

1. Live testing found it triggered falsely when the hand rotated, and
   didn't detect real pinches palm-up at all (an orientation not in any
   recording).
2. Quantified: 38.5% false positives on a dedicated `rotating_hand`
   baseline (62.2% on one hand).
3. Added a closing-velocity requirement (a real, literature-backed idea —
   see a VR-controller pinch-detection paper, AtaTouch) — helped
   (62.2%→22.2%) but didn't fix it.
4. Recorded more rotation data to check if the remaining false positive was
   a one-off: **it wasn't** — reproducible across 3 independent rotation
   recordings, with sustained false-positive runs of 14–34 frames
   (0.5–1.1 seconds). MediaPipe's own confidence score stayed >97%
   throughout those runs, which rules out tracking noise as the cause —
   this is genuine, high-confidence 3D geometry that happens to look like a
   pinch during natural hand rotation.
5. Once cleaner, slower/deliberate pinch data was recorded (fixing a
   separate problem — the original recordings' 3-cycles-in-4-seconds
   cadence made genuine pinch holds too brief to have any distinct timing
   signature), genuine pinch-hold durations grew to overlap with the
   rotation false-positives' duration range too. **Duration/debounce
   couldn't separate them either.**
6. A further heuristic ("require the closing transition itself to be fast,
   not just the end state") was proposed and **explicitly rejected** — not
   backed by literature for this problem, doesn't generalize, and is
   exactly the kind of ad-hoc special-casing this project doesn't want to
   accumulate.

**Conclusion**: a purely geometric single/short-window rule cannot cleanly
separate "genuinely pinching" from "hand relaxed into a similar shape
mid-rotation" — sometimes the two are actually geometrically identical.
This is a structural limit, not a threshold that needed more tuning. The
fix is a trained classifier over labeled data, not another hand-picked
rule. This is exactly the fallback `Specification.md` §7.1 already
anticipated ("start rule-based... revisit only if rules prove
insufficient") — that condition has now been met, with real evidence.

## 3. What to do next: read `GESTURE_PIPELINE_SPEC.md`

That document is **the actual spec for the new approach** — a
project-wide, gesture-agnostic pipeline (labeled recording → literature
benchmark → trained classifier → live debug tool), meant to apply
identically to pinch and every gesture after it. It includes:

- The hard rule this reset exists to enforce: no heuristic pile-up, ever —
  fix a misclassification with better data or a better-justified
  model/feature choice, never a bolted-on special case.
- The four pipeline stages in detail, including the session-level
  train/test split requirement (frame-level splitting leaks information)
  and the rule that classifier-training sessions must be one unambiguous
  held state each (the old `pinch_x3` sessions had no ground-truth
  per-frame label, which is why they couldn't train a classifier).
- **§3's "decide first" note and §3.3 — episodic vs. continuous gesture
  architecture, added after a direct question about whether derivative/
  time-based approaches show up
  in state-of-the-art literature (they do — layered on a per-frame
  classifier, not replacing one).** Pinch is **episodic** (a discrete
  onset→apex→offset event, matching how gesture literature and production
  XR SDKs — Ultraleap, Meta Quest — both treat pinch/grab); translation,
  the depth proxy, and rotation (matrix rows #5–#7) are **continuous**
  (always-on values, no event to detect). This changes the plan
  concretely for pinch: the base classifier now outputs a **continuous
  confidence value** (like Ultraleap's pinch-strength score), not a
  thresholded bool, and a **separate event-detection layer** confirms
  onset/offset via **derivative agreement across multiple signals** (a
  named technique — "derivative classifiers" — for rejecting gestures made
  "too slowly, unintentionally, or due to noise," i.e. this project's exact
  rotation false-positive problem, but sourced this time instead of
  invented ad hoc). Tuned against a **second recording type**,
  `pinch_cycles` (slow, deliberate, repeated transitions — the old
  `pinch_x3` cadence, but now with a distinct label and a clear, correct
  purpose: event-layer validation, never classifier training data).
- A **proposed** (not yet executed) pinch recording taxonomy — both the
  held-state classes (`pinch` / `open_hand` / `fist` / `rotating_no_pinch`
  × a front/palm-up/palm-away orientation grid) and the `pinch_cycles`
  transition sessions above — confirm or adjust before recording, don't
  just execute it blindly.
- **§6: what MediaPipe's own Gesture Recognizer actually does**, researched
  directly (not assumed) — two findings that should shape stage 3: (a)
  MediaPipe's own classifier is static/per-frame, **not** derivative- or
  velocity-based, real precedent for not reaching back to the
  velocity-window approach this project already tried; (b) MediaPipe feeds
  a small model **raw landmark coordinates** rather than hand-crafted
  ratio/angle features — stage 3 should empirically compare both input
  representations rather than assuming hand-crafted features (like the
  abandoned classifier's) are the right choice.
- **§7: cross-platform portability (Local_pc → Web) plan**, compared
  directly against how MediaPipe's own `.task`-bundle/TFLite approach
  works — this project's classifier is deliberately small enough to use a
  hand-rolled forward-pass (flat JSON weights, Specification.md §7.1)
  instead of pulling in a real inference runtime, but the discipline that
  makes that work (portable feature-extraction code, a parity test once
  the JS port exists, `world_landmarks`-only camera-frame independence) is
  spelled out there — worth reading before writing any classifier code,
  not just before the eventual web port.

**First concrete action for the new conversation**: confirm the taxonomy
in `GESTURE_PIPELINE_SPEC.md` §5 with the user, then start recording per
§3 stage 1.

## 4. Current repo state

**Deleted today** (obsolete, tied to the abandoned rule-based classifier):
- `Local_pc/Movement_with_hand_detection/Resources/GestureRules.py`
- `Local_pc/Movement_with_hand_detection/AnalyzeRecordings.py`
- `Local_pc/Movement_with_hand_detection/ValidateWindowedClassifier.py`
- `Local_pc/Movement_with_hand_detection/LiveGestureDebug.py`
- `Local_pc/Movement_with_hand_detection/debug_gestures.bat`
- Every file under `Local_pc/Python_Server_MediaPipe_vision_pipeline/recordings/`
  (now empty — old recordings used the abandoned cyclic-session labeling
  and aren't valid supervised-training data)

**Kept, still valid:**
- `Local_pc/Python_Server_MediaPipe_vision_pipeline/RecordSession.py` +
  `Local_pc/Movement_with_hand_detection/record.bat` — the recording tool.
  Usage unchanged: `record.bat <label> [duration_seconds]`, 3s countdown
  then auto-stop, no keypress needed. **What changes going forward is
  which labels get recorded** (see §3 above / `GESTURE_PIPELINE_SPEC.md`
  §5) — one unambiguous state per session, not a multi-cycle mix.
- `Local_pc/Movement_with_hand_detection/{PythonApp_Main.py,
  Resources/{CubeWindow.py, HandsTriggeredActions.py}}` — Part One step 1's
  live two-cube pipeline. Confirmed working, untouched by any of this.
- `Local_pc/Python_Server_MediaPipe_vision_pipeline/` (the MediaPipe
  server) — untouched.
- All docs: `Specification.md`, `PART_ZERO.md`, `PART_ZERO_BIS.md`,
  `PART_ONE.md` (now with a historical-content banner at the top),
  `GESTURE_PIPELINE_SPEC.md` (new).

**Not yet built** (this is the actual work for the new conversation):
- Feature-extraction module (rebuild fresh — the deleted `GestureRules.py`'s
  math was correct, e.g. hand-size-normalized distance ratios, PIP-joint
  curl angles, but rebuild clean rather than resurrect it, since it was
  structured around the abandoned classification approach).
- Training script + a small hand-rolled classifier (logistic regression or
  tiny 2-layer MLP, plain Python/math, no ML framework dependency — weights
  export as flat JSON arrays per `Specification.md` §7.1's portability
  requirement).
- A rebuilt live debug tool against the new trained-model interface.
- The wire-protocol extension to send `world_landmarks` over the existing
  socket (`VisionPipeline.py`/`Server.py`) — still needed before any
  classifier can run in the *live* two-cube pipeline
  (`HandsTriggeredActions.py`), same gap as before (`PART_ONE.md` §4),
  unaffected by today's reset. Not needed for recording/training/offline
  debug-tool work, only for the final live-wiring step.

## 5. Environment notes

- Python env: `Local_pc/Movement_with_hand_detection/.venv` (created by
  `launch.bat` on first run) — this is the interpreter used for
  `RecordSession.py`, the server, and everything else in `Local_pc/`, even
  though some scripts live in the sibling
  `Python_Server_MediaPipe_vision_pipeline/` folder (they're launched via
  `sys.executable` from the client side, so there's only one `.venv` for
  both).
- `Local_pc/` and `Web/` were renamed from `Part_Zero_local_pc/` and
  `Part_Zero_Bis_Web/` when Part One started building on Part Zero's code
  in place — see `PART_ONE.md` §1 if old paths show up anywhere unexpected
  (git history, old branches, etc.).
- `recordings/` is gitignored — expect it empty on a fresh checkout, that's
  correct, not a bug.
