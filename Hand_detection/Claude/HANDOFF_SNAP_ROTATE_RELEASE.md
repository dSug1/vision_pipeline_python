# Handoff — read this first when starting a new conversation

Rewritten **2026-08-03** (previous rewrite 2026-08-01). This file is an
**orientation pointer and a prioritised starting point only** — it does not hold
the build order and must not duplicate the specs. When it starts accumulating
layered patches again, rewrite it rather than appending.

---

## 0. Read order

| # | Document | Read it for |
|---|---|---|
| **1** | **`Claude/PART_ONE.md` §3.1** | ⭐ **THE single build queue — what to do next.** Starts with a "YOU ARE HERE" block giving the exact ordered path. §3 above it is the gesture/signal matrix (what is built vs not, per row) |
| 2 | `Claude/GAME_RULES.md` | what the game does *today*, in plain language, no implementation detail |
| 3 | `Claude/PERCEPTION_LAYER_SPEC.md` | the perception design (M0–M10). **Read §0.1 (amendment log), then §0.15 (audit of our own null results), then §10 (state-of-the-art addendum, S1–S12) BEFORE any module body** — several modules are already built, several conclusions were amended, and one was retracted. Reading module bodies alone gives a wrong picture |
| 4 | `Claude/GESTURE_PIPELINE_SPEC.md` §13–§15 | *why* things are the way they are: full design rationale, failure analysis, build history |
| 5 | `Local_pc/Movement_with_hand_detection/analysis/README.md` | every measured claim mapped to the script that produced it — **and the six measurement bugs found so far.** Start any audit here |

**Repo state**: run `git status` before assuming anything.

---

## 1. ⭐ START HERE — the next build step

**Next item: `PART_ONE.md` §3.1 item 1.6 (M4 — consistency gate).**
Then **1.7 → T1/T2 retest → reassess (R)**. The queue's "YOU ARE HERE"
block explains why each is next; do not re-derive that ordering.

**Item 1.5 (M3a anatomical constraints) is DONE (2026-08-04)** —
`Resources/hand_anatomy.py`, 0.00% false positives on a 1446-hand-frame control,
firing on 5–59% of the poses MediaPipe is documented to fail. Full account:
`PERCEPTION_LAYER_SPEC.md` **§0.16**. It produces a per-frame validity bit that
**nothing consumes yet** — 1.6 is what turns it into a measured improvement under
A10, which is why 1.6 is next.

**⚠ Two binding constraints established 2026-08-04 — read before proposing any
model or dependency:**
- **N13: the game is intended for commercial release, so non-commercial /
  research-only licences are out**, including for offline tooling that never
  ships. This **killed item 0.5** (MANO → HaMeR/WiLoR). ⚠ It also means item
  **1.7 must NOT be built with real MANO** despite the spec calling it
  "MANO-lite" — population-average bone proportions are free and sufficient.
  Note the trap: a permissive licence on *code* does not cover *data* it
  generates from research datasets.
- **N14: the recorded corpus contains no image data at all** — 415 files, 334 MB,
  zero pixels. No image-based model can be run over the existing sessions
  retroactively. `--save-frames` now exists for new takes.

**⚠ If you find work in progress on M6 (queue item 2.3): stop there.** It is
deprioritised, five attempts all produced null results, and an audit on
2026-08-03 **confirmed that verdict on corrected data**. M6's mechanism cannot
reach ~77% of the large orientation jumps, because those occur in *well-observed*
frames — they are **bad landmarks, not bad pose filtering**. `orientation_filter.py`
stays parked and unwired. The shipped `HandOrientationFilter` stays.

**0.4** (predictor evaluation harness) remains optional, parallelisable and
blocks nothing. **0.5 is dropped — do not restart it** (see the two constraints
above). Its loss has a real consequence to be honest about: 1.5/1.6's gates have
**no external referee and will not get one**, which is exactly why 1.5's
thresholds are published clinical norms rather than values fitted to this
corpus. If an external reference is genuinely needed later, the
commercially-clean route is **ArUco/ChArUco fiducials** (BSD, `opencv-contrib`
already installed, real ground truth rather than pseudo).

---

## 2. Where the project stands

**Built, live-confirmed and in production**: proximity snap, translation
(distance-weighted phalange anchoring, §14.1), rotation, real 3D object
rendering, thumb-outward snap restriction, tracking-loss release, **DR-1
track-level hand identity**, **DR-2 edge-on exclusion**, the shared
`palm_geometry.py` / `hand_identity.py` perception modules.

**Not built**: a deliberate release trigger (only tracking-loss release exists),
Z-axis translation, open-palm/closed-fist detection (**parked** — a priority
decision, needs owner sign-off to revive).

**Archived, not deleted**: pinch (code, corpus and weights kept and reusable).

Rule-by-rule detail: `GAME_RULES.md`. Row-by-row build matrix: `PART_ONE.md` §3.

---

## 3. What happened recently — the minimum you need to know

Full accounts are in the specs; these are the load-bearing facts that change how
you work, not a history.

### 3.1 The perception layer is the active direction (2026-08-02)

`PERCEPTION_LAYER_SPEC.md` reframes MediaPipe as a **noisy sensor** and inserts
an estimator layer (L0–L6) below the gesture logic, with a versioned `HandState`
contract at the boundary. Several long-open bugs turned out to be consequences
of that missing layer rather than independent defects. All TODO lists were
merged into `PART_ONE.md` §3.1 — **do not create a second list anywhere.**

**Binding governance (spec A10)**: every module must show a measured improvement
via replay A/B on identical recorded input, **or be reverted**. A null result is
recorded so it is not retried blindly, not shipped hopefully.

### 3.2 Shipped since: DR-1, DR-2, `edgeOnMeasure`, the chirality fixture test

- **DR-1** (`Resources/hand_identity.py`) — track-level hand identity by
  position, not by MediaPipe's label. Fixed **Object Jump Correction**, whose
  real cause was handedness-label instability under rotation (flips on a
  *single* hand; duplicate labels on both). Replay-verified across 7 sessions
  and live-confirmed.
- **`edgeOnMeasure` + `PalmFacingTracker`** (`Resources/palm_geometry.py`) —
  shared by production and the debug tool, retiring the duplicated
  `_is_thumb_outward` that caused the 2026-08-01 production-only inversion.
  DR-2 freezes the palm/back sign inside the edge-on band.
- **`VerifyChiralityFixture.py`** — 788/788 on every check; guards the exact
  sign-inversion class of bug that once survived a "confirmed working" claim.

> ⚠ **Counter-intuitive fact, established by measurement across 1991 frames —
> know it before touching any handedness code:** the label carried through this
> pipeline is the **MIRRORED/apparent** hand, so a physical RIGHT hand is
> labelled `"Left"`. The production path and the recorder/debug path reach that
> convention by *different* routes. **Do not "simplify" either path** — the
> asymmetry is load-bearing (spec §0.9).

### 3.3 The 2026-08-03 audit — two claims were measurement artifacts

The owner asked for this session's null results to be treated as artifacts until
proven otherwise. Two were. Full account: spec **§0.15**.

- **CONFIRMED, do not revisit**: the five item-2.3 nulls, the M6b SVD-frame
  rejection, observability-as-blend-signal, and the whole Kalman/UKF discard.
  Re-run on identity-corrected streams the shipped filter still wins.
- **CONFIRMED: M2 (item 1.4) is dead** — and externally corroborated.
  MediaPipe's `worldLandmarks` are a **GHUM average-hand fit with a documented
  1.3–1.5 cm mean 3D error**, and Google has an **open issue (#5156) for palm
  world landmarks collapsing when the back of the hand faces the camera** — the
  same failure mode as T1. **Do not retry M2**; item **1.7** replaces it by
  *imposing* a skeleton via constrained IK instead of measuring one.
- **RETRACTED: "the constant-angular-velocity motion model is weak."** The "60%
  of frames" figure was a **closed-loop cascade statistic**, not a prediction
  error. Measured open loop: **median 4.2–4.5° at one frame.** **Item 3.1 (M7)
  is unblocked** and its "required first task" is already done.
- **Numbers corrected, conclusion intact**: the raw jump tail was inflated ~25%
  by identity contamination (>60° jumps 730 → 572; "82% at observability ≥ 0.60"
  → ~77%). Quote the corrected figures.

> ### ⚠⚠ BINDING RULE FOR EVERY REPLAY HARNESS FROM NOW ON
> **Build per-hand streams with `analysis/audit_jump_provenance.py`'s
> `build_v2()`** — replay DR-1 for identity, drop duplicate-label frames, break
> runs at frame-index gaps. **Never key a stream on the raw MediaPipe label
> again.** Every 2.3-era A/B did, which meant they measured a pre-DR-1 pipeline
> that production no longer runs, on a corpus recorded specifically because it
> contains label flips. `build_v0()` exists only to reproduce historical numbers.

### 3.4 The state-of-the-art review (2026-08-03)

Twelve adopted items **S1–S12** live in spec **§10** (rationale + sources) and
are **folded into the queue rows** (what to build), with an S→row index at the
top of §3.1. The three that most change the plan:

- **S6 → item 1.5**: published biomechanical constraints (joint limits,
  unidirectional flexion) **halve depth error** — the strongest available lever
  on T1/T2, and why 1.5 is now first.
- **S7 → item 1.7**: the literature's answer to inconsistent bone lengths is to
  fit a **fixed-bone-length model** so lengths are consistent by construction,
  not to average harder.
- **S2/S3 → item 3.1**: prediction is usable to ~30–50 ms (**one frame at
  24 fps, never two**); filter the derivative *before* extrapolating; and
  **predicted state must never reach a gesture state machine** (Apple ships
  exactly this split — predicted for rendering, unpredicted for gestures).

---

## 4. Environment notes

- **Python env**: `Local_pc/Movement_with_hand_detection/.venv` — shared by the
  client (`PythonApp_Main.py`), the server (`VisionPipeline.py`, launched via
  the same `sys.executable`), and all debug/recording/analysis tools.
- **Analysis scripts** run from the parent directory:
  `.venv/Scripts/python.exe analysis/<name>.py`.
- **Recorded corpus**: 24 sessions at
  `E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions`
  (raw MediaPipe capture, `RecordPerceptionSequence.py`), plus
  `Position_during_rotation` (older gesture-driven recordings). **Capture to
  E:, never `--local`** — standing owner instruction.
  ⚠ **N4: the E: drive drops out intermittently** (WinError 21); the recorder
  preflights and the analyser retries, but expect it.
  ⚠ **N10: frame rate is environment-dependent** (24 fps in daylight, 15–16 fps
  in poor light — auto-exposure is the leading hypothesis). **Check
  `meta.json`'s `measured_fps` before any cross-session A/B.**
- **Ask permission before each individual live-camera take** — one at a time,
  not queued. Confirm with the operator immediately after each take whether the
  target behaviour actually occurred, and discard takes that did not reproduce it.
- **Live pipeline processes hold the webcam** — a window left open keeps the
  device busy and the next launch fails with "Could not open webcam". Kill stale
  `python.exe` processes before relaunching.
- **`.bat` files end in `pause`** — from a non-interactive shell, pipe a newline
  (`printf '\n' | ./x.bat`) or it hangs forever.
- **Debug/production parity**: `LiveSnapDebug.py` duplicates
  `HandsTriggeredActions.py`/`CubeWindow.py`'s snap/translate/render logic by
  design (its `cube_window` opens a real pygame window as an import side
  effect). **Any production logic or rendering change must be mirrored there, in
  both directions.** New *perception* code goes in a shared module that both
  import (`hand_identity.py`, `palm_geometry.py` are the precedents) — never
  copied.
- **Model files**: `Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/
  hand_landmarker.task` (in use); `gesture_recognizer.task` (on disk, unused).
- **Existing tooling — extend it, do not restart.** Recording:
  `RecordPerceptionSequence.py` (raw MediaPipe capture, no gesture logic — the
  right tool for perception work) and `RecordTranslationPivotDebug.py` (drives
  the real snap/translate logic, so recorded grabs and cube centres are genuine
  ground truth). Analysis: `AnalyzePerceptionSequences.py`,
  `AnalyzePerceptionBaseline.py`, `AnalyzeTranslationPivot.py`, plus the
  `analysis/` folder. Verification: `VerifyChiralityFixture.py` — run it after
  **any** change touching handedness, chirality or `palm_geometry.py`.
  Item 1.6's χ² work has a confirmed reproduction to verify against:
  `Position_during_rotation/translation_pivot_jump_test4_20260802_174438.json`.

---

## 5. Standing discipline

- **Live-verify before trusting any claim, including your own.** This project
  has shipped a production-only bug that survived a "confirmed working
  end-to-end" claim, and has had a first fix attempt look reasonable and
  measurably do nothing.
- **Recorded-data-first empiricism**: record → analyse → verify → *then*
  implement. When a fix fails verification, report that and do not ship it.
- **Audit the harness, but expect the finding to survive.** Of three
  load-bearing negative results audited on 2026-08-03, two had a
  measurement-design flaw and only one changed the answer. The two specific
  traps, both worth checking in any new harness: **(a)** a replay harness that
  reconstructs streams differently from production silently measures a pipeline
  that no longer exists; **(b)** a rejection *rate* from a closed loop is not an
  *error* measurement. And always ask: **which quantity does this module
  actually claim?** — M2's acceptance test measured absolute lengths while the
  spec claimed proportions.
- **No heuristic pile-up.** A value that needs tuning gets tuned against data
  and the reasoning recorded. Periodically **audit accumulated filters against
  the shipped code, not discussion history** — a filter earns its keep only with
  measured, non-marginal impact.
- **Do not ask a human to verify a state the UI does not display.** That test
  design failed once (the operator correctly reported they could not tell).
  Measure it from recordings instead.
- **Same-frame ordering matters** in per-hand stateful loops — think through
  what a second hand's pass can observe from the first hand's pass in the same
  frame before assuming independence.
- **Keep `GAME_RULES.md` updated** whenever a rule is confirmed and built.
- **When proposing a refinement to the owner's design, check whether its premise
  survives the failure modes of the mechanism it sits on.** "Handedness cannot
  change mid-track" was true of *hands* and false of *tracks*, because the
  association layer can silently reassign which hand a track follows. Replay
  caught it in minutes; reasoning alone had endorsed it.

---

## 6. Open decisions that are the owner's, not technical

Raise these rather than deciding them inside a module:

1. **M10.7's ~400 ms grace period on tracking loss** would change
   `GAME_RULES.md` rule 2's current immediate-drop behaviour. It would also
   close **N8** (a hand can steal another hand's cube by occluding it — recorded
   deliberately unfixed).
2. **§14.3's 3D snap gating is undefined when `depthValid` is false** — fall
   back to 2D proximity, or refuse to snap?
3. **U1 — open-palm/closed-fist detection is PARKED** as a priority decision.
   Item 5.1 would make it more tractable, but do not un-park it on that basis.
