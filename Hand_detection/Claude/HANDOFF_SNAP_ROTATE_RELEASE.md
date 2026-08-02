# Handoff — snap/rotate/release gesture set, current state and next steps

Rewritten 2026-08-01, updated through 2026-08-02, for starting a **new**
Claude Code conversation. Read this first. The three other living documents for this work, in order of
how detailed they are:

1. **`Claude/PART_ONE.md` §3.1** — **the merged build queue: the single
   authoritative TODO list.** Start here for *what to do next*. §3 above
   it is the gesture/signal matrix (*what's built vs. not, per row*).
2. **`Claude/GAME_RULES.md`** — plain-language inventory of confirmed game
   rules, no implementation detail. Read this to know *what the game does
   today*.
3. **`Claude/PERCEPTION_LAYER_SPEC.md`** — the perception-layer design
   (M0–M10) integrated 2026-08-02, now the active direction. **Read its
   §0.1 amendment log first** — several modules are already built or were
   amended on integration, and reading the module bodies alone will give
   you a wrong picture.
4. **`Claude/GESTURE_PIPELINE_SPEC.md` §13-§15** — full design rationale,
   state-of-the-art checks, and build history. Read this to know *why*
   things are the way they are, and for full technical detail on anything
   summarized below. §15 records the perception-spec integration.

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

## 2. What happened in the last two sessions (2026-08-01 / 08-02) — read before starting new work

Five things, in order. §2.5 is the current head of the work. Full technical
detail is in `GESTURE_PIPELINE_SPEC.md` §14.1-§14.1.4 / §13.6.1 and
`PERCEPTION_LAYER_SPEC.md` §0.2-§0.5 — this section is a summary, not the
full account.

**One-line status**: translation redesign done and live-confirmed;
thumb-outward inversion fixed and live-confirmed; Object Jump Correction
root-caused and a fix (DR-1) built, replay-verified **and now
live-confirmed against a camera (2026-08-02)** — so the immediate next
step has moved on to item 0.2b, the remaining scripted sequences (§3).

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

### 2.3 "Object Jump Correction" — root-caused; FIXED by DR-1 (§2.5), live-confirmed 2026-08-02

> **Status note (2026-08-02).** DR-1's live test passed and the reported symptom
> (a cube teleporting between hands) did not occur while the operator actively
> tried to provoke it. **But the M0 regression metric has NOT been re-measured**
> — "2 jumps → 0" needs a fresh recording replayed through
> `AnalyzePerceptionBaseline.py`, which the live test does not produce. Treat
> this as live-confirmed by observation, not yet closed by measurement (A10).

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

**Root cause was later REFINED and a fix built — see §2.5.** The account below
is the first-pass diagnosis (two-hand proximity); a controlled near-miss experiment
subsequently disproved that and identified handedness-label instability instead.
Read §2.5 for the current state; this subsection is kept for the reasoning trail.

**Originally deferred**, not attempted blind. A real fix needs a filter design
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

### 2.5 DR-1 track-level hand identity — BUILT, replay-verified, and LIVE-CONFIRMED 2026-08-02

**DONE.** Object Jump Correction (§2.3) was
root-caused to **MediaPipe's handedness label being unstable**, not to two hands
being confused: it flips on a *single* hand under rotation (18 recorded events at
score ~0.66 vs a 0.95–0.99 baseline) and sometimes labels *both* hands the same
(25 frames). Ownership is keyed by handedness, so either one teleports a cube or
makes a hand read as not-detected and drops it.

**Built**: `_HandIdentityTracker` in `hands_visualizer.py` — associate detections
to tracks by **position**, lock the label after a short vote, hold brief
mismatches, **switch on long + confident ones**, and re-decide freely when a
track ends.

**Two things were built and then removed/corrected the same day — don't
re-introduce either:**

1. A **stateless score-based duplicate resolver** was built first, then removed:
   choosing by handedness score was a coin flip (gap < 0.05) on 36% of frames and
   was blind to the 28 label flips entirely.
2. A **"never switch a locked label"** rule was implemented and **disproved by
   replay**: position association swaps identities when two hands cross, so
   never-switching locks the error in — 528 overrides in runs of up to 225
   frames (~9 s of confidently wrong labels). The switch branch is required.

**Replay results across all 7 sessions**: duplicates **25 → 0**; longest
wrong-hold **225 → 10 frames**; and **0 overrides and 0 switches in all three
control sequences**, so it is inert when nothing is wrong.

**One parameter is deliberately tunable and worth revisiting**: `SWITCH_MS`
(currently **12 frames / ~500 ms**) — the dwell before a confident disagreement
is accepted as a real association swap. Lower = faster correction after a
crossing but closer to false switches (the worst *glitch* actually recorded ran
7 frames, so 7 or below would have fired falsely); higher = safer but the wrong
label persists longer. Real swaps run 62–225 frames so they can never be missed
by raising it. **Re-derive from fresh recordings if the camera, frame rate or
lighting change.** A "both tracks mismatched" shortcut was proposed and
**refuted by measurement** — don't retry it without new evidence (spec §0.5).

**Code review done 2026-08-02** (this session added and removed a lot in
`hands_visualizer.py`, so it was reviewed rather than assumed):

- All touched files compile; the removed stateless resolver left **no dead code**.
- **One real bug was found by testing and fixed**: with both track slots full, a
  detection that jumped beyond the association limit fell through to a raw-label
  fallback that could emit a **duplicate label** — the exact thing this module
  exists to prevent. Now there is an explicit end-of-function invariant: never
  emit two hands with the same label, track-backed assignment wins.
- Re-verified after the fix: 7 real sessions unchanged, plus edge cases (no
  hands, one hand, track end and re-acquire, identical positions, zero palm
  width, scores exactly at the 0.90 gate) and a **3000-frame fuzz** — zero
  duplicates, zero `None` labels.

**Debug/production parity — RESOLVED 2026-08-02.** DR-1 was briefly
production-only, because `LiveSnapDebug.py` runs MediaPipe in-process and never
imported `hands_visualizer.py`. Rather than copy ~150 lines, the tracker was
**extracted to `Resources/hand_identity.py`** (standalone, pure stdlib, no
cv2/mediapipe/window side effects) and is now **imported by both**. Verified:
production and the debug tool produce **byte-identical identity output across all
7 recorded sessions**, and exactly one tracker definition exists in the codebase.
The same change fixed a latent bug in `LiveSnapDebug.py` — it keyed hands by
handedness in a dict, silently overwriting one of a duplicate pair, which is the
same defect that hid Object Jump Correction in the old recorder.

**So `debug_snap.bat` and `launch.bat` now behave the same way**, and either can
be used to test DR-1.

**LIVE-CONFIRMED 2026-08-02** via `launch.bat`, deliberately rotating hands
back-to-camera and crossing them while holding cubes — operator verdict *"it's
working"*, no teleport and no spurious drop. 16 tracker events, **0 errors**;
crucially the failure conditions were genuinely provoked, not merely absent —
the glitch branch **held** a 3-frame mismatch and the swap branch **switched**
on a full 12, the exact separation replay predicted.

**One new finding, undiagnosed**: the duplicate-repair invariant — documented as
a fuzz-found edge case — fired **3× in one short session**. No duplicate was
emitted (it did its job), but the frequency wasn't predicted by the 7 recorded
sessions. **Deliberately not tuned**; logged as queue item **N9**.

**Also open**: `ASSUMED_FPS = 24.0` is hard-coded in `hand_identity.py` and should
come from measured timing (N7); acquisition can still lock wrong — seen live
twice, and the switch branch recovered it both times, which is exactly why that
branch must exist. Full account: `PERCEPTION_LAYER_SPEC.md` §0.4–§0.6.

## 3. Next build targets — see the merged build queue

**⚠ This section no longer holds the build order.** As of 2026-08-02 the
project has **one merged TODO list**: **`PART_ONE.md` §3.1**. It covers
both the gesture features and the newly-integrated perception-layer
modules, in dependency order, with status per item. Read it before
starting anything.

**What changed (2026-08-02).** The owner wrote a perception-layer design
spec — now integrated as **`Claude/PERCEPTION_LAYER_SPEC.md`** — which
reframes MediaPipe as a *noisy sensor* and inserts an estimator layer
between it and the gesture logic, with a versioned `HandState` contract at
the boundary. Several open TODOs turn out to be consequences of that
missing layer rather than independent bugs. Consequently:

- **Perception Phases 0–2 come first** (owner decision), then reassess.
- **Object Jump Correction (§2.3) now has a fix path** it didn't have when
  it was deferred: DR-1 (make handedness track-level, not a per-frame
  decision — the structural cause) plus M4's χ² innovation gate. Expected
  to close in Phases 1–2 rather than needing bespoke work.
- **The yaw/palm-sinking limitation (§2.1)** likewise maps to M9's
  foreshortening correction.
- **The two features** (hand-open release, Z-axis translation) are
  unchanged as designs but gated behind their hard prerequisites — M4/M10
  and M2/M9 respectively.

**Item 0.2 is DONE (2026-08-02): baselines measured before anything was
built** — `AnalyzePerceptionBaseline.py`, 7 existing recordings, no new
capture. Headlines: bone-length CV **10.0%** against a <3% target (worst
on fingertips — but the **palm is already rigid to 2.76 mm, inside
target**); **DR-2 empirically validated** (zero sign flips across 3130
well-conditioned frames, 41.5× flip concentration in the edge-on band);
object-jump metric baselined at exactly 2 jumps, both the known bug. Full
results and the careful interpretation: `PERCEPTION_LAYER_SPEC.md` §0.2.

**DR-1's live test is DONE (2026-08-02, §2.5) — passed.** It was the previous
head of this list.

**Immediate next step (paused 2026-08-02 at the owner's request, to resume in
better daylight): record the four `palm_back_s1..s4` takes, then continue item
0.2b.** They are already built into `RecordPerceptionSequence.py` — just run
them; cycle counts and the pitch-axis briefing are baked in.

Three things happened on 0.2b this evening — full account in
`PERCEPTION_LAYER_SPEC.md` §0.7 / §0.7.1:

1. **`palm_back` recorded, then DELETED along with an aborted take** — both ran
   at 15–16 fps in poor light, and the owner discarded them rather than let that
   pollute the analysis. Their indicative result (the sign cue **UNDER-detects**
   crossings, 52/50 against 58 expected — reversing the prior suspicion of a
   *spurious*-flip population) is **no longer backed by data**; don't cite it.
   **Replaced by four speed-decoupled takes** that locate the *threshold* at
   which crossings start being missed, with prescribed cycle counts and an
   explicit **PITCH** axis (not yaw — yaw is T4's separate problem).
2. **⚠ A unit trap that already caused one wrong reading.** The operator counts
   palm→back→palm as ONE crossing; the analyser counts sign inversions — 2× apart.
   Compare against `expected_sign_changes`, never the raw cycle count. Both are
   stored in the session's `meta.json`.
3. **⚠ Frame rate is environment-dependent, not the fixed ~24 fps finding N1
   recorded** — 15.1/15.77 fps measured at 22:18 vs 24.09–24.14 earlier the same
   evening, same camera and machine. This makes **N7 a correctness item**
   (DR-1's 12-frame `SWITCH_MS` dwell is ~761 ms at 15.77 fps, not the intended
   500) and is logged as **N10**. It is also the confound blocking N3 — hence
   the re-record in better light.

**Then: the rest of item 0.2b — the remaining §7.2 scripted sequences.**
This remains the binding constraint: three M0 metrics (resting jitter,
palm-normal jitter, crossing survival) simply cannot be computed from the
existing grab-and-rotate recordings, and the *scripted non-crossing*
sequence is what decides whether the mid-band sign flips are spurious —
which in turn decides `EDGE_ON_THRESHOLD`.

**Then item 1.1, the `K` fixture test** — hours of work, and it
permanently guards the exact production-only sign inversion described in
§2.2 above, which survived a "confirmed working" claim once already. It
needs one short recording with the ground truth stated up front ("right
hand, palm to camera, whole clip") — existing recordings hold only the
*computed* thumb-outward value, not independent truth.

**Binding rule going forward (spec A10):** every perception module must
show a measured improvement on the M0 metrics via replay A/B on identical
recorded input, or be **reverted**. This is what keeps the spec's
machinery from becoming filter accumulation — see §2.4.

**Two open decisions the spec surfaced that are yours, not technical**:
(a) M10.7 proposes a ~400 ms grace period on tracking loss, which would
change `GAME_RULES.md` rule 2's current immediate-drop behaviour;
(b) §14.3's 3D snap gating is undefined when `depthValid` is false.

**Known gameplay defect, recorded but deliberately NOT fixed (queue N8)**:
**a hand can steal another hand's cube by occluding it.** Hand A holds a cube,
hand B moves in front of it, A's tracking is lost, rule 2 releases the cube, and
B — right where A was, so inside the grab radius — snaps it a frame or two
later. §13.5's same-frame ordering fix only blocks re-snap on the *same* tick.
Expected to resolve as a side effect of refining snap control (M10.7's grace
period would leave nothing to steal). Recorded so it isn't rediscovered as a new
bug. Mechanism is inferred from the rules, not instrumented.

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
