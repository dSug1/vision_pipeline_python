# Handoff — snap/rotate/release gesture set, current state and next steps

Fully rewritten 2026-08-01 (not patched — see the note at the bottom of
this file for why), for starting a **new** Claude Code conversation. Read
this first. The three other living documents for this work, in order of
how detailed they are:

1. **`Claude/GAME_RULES.md`** — plain-language inventory of confirmed game
   rules, no implementation detail. Read this to know *what the game does
   today*.
2. **`Claude/PART_ONE.md` §3** — the gesture/signal matrix (build order,
   status per row). Read this to know *what's built vs. not, in one
   table*.
3. **`Claude/GESTURE_PIPELINE_SPEC.md` §13-§14** — full design rationale,
   state-of-the-art checks, and build history. Read this to know *why*
   things are the way they are, and for full technical detail on anything
   summarized below.

This handoff file is only an orientation pointer plus a prioritized
action list — don't duplicate the above, link to them.

**Repo state**: check `git status` before assuming anything.

## 1. Where the project stands

**Built, live-confirmed, and in production**: proximity snap, translation
(redesigned — see §2 below), rotation, real 3D object rendering,
thumb-outward snap restriction (recently fixed — see §2), tracking-loss
release. **Not built**: a deliberate release trigger (only tracking-loss
release exists today), Z-axis translation, open-palm/closed-fist
detection (PARKED, not being pursued). Full rule-by-rule detail:
`GAME_RULES.md`. Full row-by-row build matrix: `PART_ONE.md` §3.

**Pinch is archived** (not deleted — code/corpus/weights kept, reusable
later). Full account: `GESTURE_PIPELINE_SPEC.md` §13.1,
`_archived_old_HANDOFF_GESTURE_CLASSIFIER.md` (archived/historical, renamed 2026-08-02 to make its archived status obvious from the filename).

## 2. What just happened this session (2026-08-01) — read before starting new work

Three things were resolved or discovered, in order. Full technical detail
for all three is in `GESTURE_PIPELINE_SPEC.md` §14.1-§14.1.4 and §13.6.1
— this section is a summary, not the full account.

### 2.1 Translation-pivot fix — DONE (designed, verified, live-confirmed, ported to production)

The old translation design forced the cube to sit exactly on one tracked
anchor point every frame, with no grab-time offset — this caused both a
visible pop at grab and incorrect coupling when the hand only rotated in
place. **Redesigned** as distance-weighted live landmark tracking: at
grab, freeze a weighted set of ~9 phalange-adjacent landmarks (5
fingertips + 4 knuckles), weighted by proximity to the object; every
frame after, recompute the weighted position from those same landmarks'
live tracked motion. Literature-grounded (Napier's grasp taxonomy;
Unity XRI's Dynamic Attach / Meta Horizon's GripPoint — the "capture the
hand-object relationship once at grab, follow it thereafter" principle is
industry-standard, not novel).

**Fully verified before shipping**: synthetic math checks, 7 real
recorded hold intervals (no-pop exact, jitter comparable to the old
design, translation scales with real rotation as expected), a replay of
real camera data through the actual production code path, then live
camera confirmation ("it's working"), then ported to `HandsTriggeredActions.py`/
`CubeWindow.py` with a parity review (production can't be safely
replay-tested — it opens a real pygame window on import), then a live
production test.

**One known, deliberately deferred limitation**: swings toward the palm
under yaw specifically (pitch/roll are fine) — likely shares root cause
with the not-yet-built Z-axis translation gesture; a future startup
Z-axis calibration step is the proposed direction, not yet designed.
Full account: `GESTURE_PIPELINE_SPEC.md` §14.1.1.

**Considered DONE.** The one thing still open on translation is §2.3
below (a separate, more serious bug), not this redesign itself.

### 2.2 Thumb-outward restriction — bug found and FIXED (production only, debug tool was always correct)

Live report: grab was only possible with the thumb pointing OUTWARD in
production — the opposite of the intended rule (and opposite of the
already-correct debug tool). **Root-caused, not guessed**:
`VisionPipeline.py` runs MediaPipe detection on the raw, un-mirrored
camera frame; pixel/world landmark *coordinates* get mirrored afterward
for display (`invert_x=True`), but the handedness *label* never was.
MediaPipe assumes an already-mirrored ("selfie") input for its Left/Right
classification, so on an unmirrored frame it reports the true anatomical
hand — inverting `_is_thumb_outward`'s handedness-dependent chirality
correction specifically (the one place in the whole pipeline that isn't
handedness-symmetric, which is why nothing else broke).

**Fixed** at the single source (`hands_visualizer.py`'s new
`_mirror_handedness()`), not by patching the consumer. Compiles, smoke-
tested. **Not yet independently live-tested** — confirm thumb-inward now
correctly permits grab in production before considering this fully
closed. Full account: `GESTURE_PIPELINE_SPEC.md` §13.6.1.

### 2.3 "Object Jump Correction" — NEW open TODO, root-caused, NOT YET FIXED

**Use this exact name in future conversations to refer to this item.**

A live report ("the cube jumped from one hand to another and came back")
was first thought spurious/unreproducible, then made reproducible via a
record-and-confirm-per-take workflow (record a short session, ask the
operator immediately afterward whether the bug actually occurred, discard
takes that didn't reproduce it, keep going until one does — this
workflow itself is reusable for any future hard-to-reproduce live bug).

**Root cause, confirmed from real recorded data**: for a few consecutive
frames, MediaPipe briefly mixes up hand identity — all landmarks of the
tracked hand move together, coherently, to a completely different
on-screen location (in the captured case, a 509px jump in a 640px-wide
frame) under the *same* handedness label, with normal-to-high confidence
throughout, then self-corrects a few frames later. This is **not**
frame-edge extrapolation and **not** per-landmark noise — a first fix
attempt built around the frame-edge-extrapolation hypothesis (exclude
out-of-bounds candidate landmarks, renormalize) was built and verified
against real data to make **no measurable difference**, and was
correctly discarded rather than shipped anyway.

**Not yet fixed — explicitly deferred to a future round of
improvements**, not attempted blind. A real fix needs a filter design
comparable in complexity to rotation's own predictive/reliability-
weighted filter (§13.7), which itself took two iterations to get right
(a self-reinforcing rejection trap, then a stale-reference bug) — this
bug has an analogous trap risk (a wrong state that's internally
consistent across several frames can fool a naive "compare to the
previous frame" filter). **Sequencing not yet decided** — ask the user
where this fits relative to §3's other targets before starting it.

Full account, including the exact frame-by-frame data and what's still
needed to design a fix: `GESTURE_PIPELINE_SPEC.md` §14.1.4. Reusable
recorded data: `E:\Python\Recordings for vision_pipeline\Position_during_rotation\translation_pivot_jump_test4_20260802_174438.json`.

### 2.4 Filter audit — direct request to strip anything not earning its keep

Audited every accumulated filter/smoothing mechanism against the shipped
code (not just discussion history), per direct request to keep the game
logic pure and simple.

- **Translation: nothing to strip.** The Object Jump Correction
  investigation's candidate mitigations (out-of-bounds exclusion +
  renormalize + freeze; temporal smoothing) were never merged into the
  actual game code — one was tested and verified to not help (correctly
  discarded before shipping), the other was proposed but never built.
  Today's translation mechanism has no filters layered on it at all.
- **Rotation: one real filter exists** (predictive/reliability-weighted,
  §13.7's "Attempt 3"), no dead code from its two earlier abandoned
  attempts. Its impact is measured and substantial (eliminates all
  `>30°`/`>60°` jumps in tested data), not marginal — **decision: KEEP
  it**, removing it now would be a real regression against the still-open
  back-of-hand rotation TODO. **New TODO added**: re-test whether it's
  redundant once future improvements land (Object Jump Correction,
  Z-axis/depth calibration) — don't keep it out of inertia if a later fix
  resolves the underlying depth-ambiguity problem at its source. Full
  account: `GESTURE_PIPELINE_SPEC.md` §13.7.1.

## 3. Next build targets — order below is NOT fully decided, ask the user

Three items are queued, but their relative order is only partially
confirmed:

1. **Hand-open-quick release trigger** (design confirmed, not yet built)
   — unsnap by rapidly fully opening the hand, provided the wrist stays
   stable (distinguishes it from the future Z-translation gesture below).
   Supersedes the closed-fist release plan outright (open-palm/closed-fist
   detection is parked). Proposed recording/discrimination plan:
   `GESTURE_PIPELINE_SPEC.md` §14.2.
2. **Z-axis (camera-view-axis) translation** (design confirmed, not yet
   built) — moving a snapped hand closer to/farther from the camera
   translates the object along that axis, driven by apparent hand-span
   ratio. Snap becomes a 3D proximity check. Full design:
   `GESTURE_PIPELINE_SPEC.md` §14.3.
3. **"Object Jump Correction"** (§2.3 above) — root-caused, not designed.

**Before this session, the confirmed order was 1 → 2.** §2.3 was added
mid-session and its place in that order was never decided — don't assume
it's last just because it's listed last here. Ask the user.

## 4. Environment notes

- Python env: `Local_pc/Movement_with_hand_detection/.venv` — shared by
  the client (`PythonApp_Main.py`), the server (`VisionPipeline.py`,
  launched via the same `sys.executable`), and all debug/recording tools.
- **Recording tools available**: `RecordTranslationPivotDebug.py`/
  `record_translation_pivot_debug.bat` (imports `LiveSnapDebug.py`'s real
  snap/translate logic — recorded grab events and cube centers are real
  ground truth, not simulated) + `AnalyzeTranslationPivot.py` (offline
  analysis: no-pop check, jitter, rotation-coupling, yaw-foreshortening
  diagnostics — all reusable/extensible for future translation work,
  including §2.3). Recordings save to
  `E:\Python\Recordings for vision_pipeline\Position_during_rotation`
  (external-drive corpus convention, direct request — not the local
  one-off-diagnostic pattern `RecordRotationDebug.py` uses).
  **When launching a recording via a non-interactive shell**: the `.bat`
  files end in `pause` (meant for a human running them directly) — pipe a
  newline into stdin (`printf '\n' | ./x.bat`) so it doesn't hang waiting
  for a keypress that will never come.
- **Ask permission before each individual live-camera recording take** —
  established convention this session, the user wants to confirm
  readiness before each launch, not have several queued up at once.
- Model files: `Local_pc/Python_Server_MediaPipe_vision_pipeline/
  Resources/hand_landmarker.task` (in active use) and
  `gesture_recognizer.task` (kept on disk, not currently used — see §1).
- **Live pipeline processes hold the webcam device** — if a debug/launch
  session's window isn't explicitly closed, the process keeps running and
  the *next* attempt to open the camera fails with "Could not open webcam
  ... Is another program using the camera?". Check running `python.exe`
  processes and stop stale ones before relaunching if this happens.
- `debug_snap.bat`/`LiveSnapDebug.py` duplicates (not imports)
  `HandsTriggeredActions.py`'s/`CubeWindow.py`'s snap/translate/orientation/
  rendering logic by design (its `cube_window` is a module-level object
  that opens a real pygame window as an import side effect, which this
  single-OpenCV-window tool must not trigger). **Any production logic OR
  rendering change needs to be mirrored there too, in both directions** —
  true for every gesture built so far, still applies going forward.

## 5. Standing discipline (carried over, still applies)

- **Live-verify before trusting any claim, including your own geometric
  assumptions or a previous fix's stated rationale.** This session alone:
  the thumb-outward inversion was a real production-only bug despite an
  earlier "confirmed working end-to-end" claim; the first Object-Jump-
  Correction fix attempt looked reasonable but was verified to not work;
  the translation redesign's own literature-grounded design still needed
  full recorded-data verification before shipping.
- **Recorded-data-first empiricism, not guessing** — every fix or design
  decision this session went through record → analyze → verify → THEN
  implement, never the reverse. When a fix attempt fails verification
  (Object Jump Correction's first attempt), report that honestly and
  don't ship it anyway.
- **A live bug report that seems unreproducible may still be real and
  root-causable** — Object Jump Correction was first written off as
  "spurious," then made reproducible with a disciplined record-and-
  confirm-per-take workflow. Don't give up after one non-reproducing
  attempt if the user wants to keep trying.
- **No heuristic pile-up** — if a value needs tuning (grab radius,
  rotation slerp factor, `TRANSLATION_EPSILON_PX`, etc.), tune it live
  and record the reasoning, don't guess-and-forget. Extended this session
  (direct request) into a periodic discipline: **audit accumulated
  filters against the actual shipped code, not just discussion history**
  — a filter only earns its keep with measured, non-marginal impact
  (§2.4's rotation-filter audit is the worked example: kept because the
  numbers are real and large, flagged for re-test once other work might
  make it redundant, not kept out of inertia).
- **Same-frame ordering matters** in per-hand stateful loops — the
  release/re-snap jump bug (§13.3) is the concrete precedent; think
  through what state a second hand's pass can observe from the first
  hand's pass in the same frame before assuming independence.
- **Keep `GAME_RULES.md` updated** every time a new rule is confirmed and
  built — it's the one place meant to answer "what does the game do
  today" without reading code or design prose.
- **A filter distinguishing "brief bad blip" from "real sustained new
  state" is genuinely hard, not a quick patch** — rotation's own filter
  took two iterations; expect Object Jump Correction's fix to need the
  same care, not a one-shot attempt.

---

**Why this file was fully rewritten (not patched) this time**: it had
accumulated multiple sessions' worth of layered patches (one section
alone had grown to ~150 lines of interleaved history) and had drifted
from its own stated purpose ("only an orientation pointer... don't
duplicate the above, link to them"). Full technical history for
everything summarized above is preserved in `GESTURE_PIPELINE_SPEC.md` —
nothing was lost, just moved to where it already belonged.
