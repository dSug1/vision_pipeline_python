# PERCEPTION_LAYER_SPEC.md

**Scope:** Improvements to the hand-perception stack that sit *below* the gesture-logic layer.
**Status:** Design spec — integrated into the pipeline 2026-08-02. Phases 0–2 are the immediate next build step; see the merged build queue in `PART_ONE.md` §3.1 (the single authoritative TODO list).
**Architectural rule honoured:** every module in this document lives in the perception layer and is invisible to the gesture-logic layer. The only thing that changes at the boundary is the *quality and richness of the `HandState` struct*, whose schema is versioned in §2.

**Precedence:** the project pipeline `.md` files are the authoritative record of failure
analysis and lessons learned. Where this spec conflicts with them, they govern.

**Revision 2** (author) — §3 replaced by a pointer to the pipeline docs; M5 rewritten around the
signed-palm-area cue per owner review; M2 extended with per-user calibration policy (2f);
M8/M9 flagged as subject to amendment; one earlier claim retracted (M5f).

**Revision 3** (integration into the pipeline, 2026-08-02) — see §0.1 for the full amendment
log. Summary: retargeted from JavaScript to Python (the JS target named in Rev. 2 does not
exist); M5a/M5b and M6a marked **already built**; M8a conflict with `GESTURE_PIPELINE_SPEC.md`
§14.1 resolved in favour of the pipeline docs; M4's scope narrowed per recorded evidence;
governance kill-criterion added; §5's mapping superseded by the merged queue in `PART_ONE.md`
§3.1.

---

## 0.0 WHERE THE EVIDENCE LIVES — measurement harnesses (added 2026-08-03)

Every non-obvious number in §0.6–§0.14 was produced by a script in:

> ### **`Local_pc/Movement_with_hand_detection/analysis/`**
> **See that folder's `README.md`** — it maps each claim to the script that produced
> it, and flags the four measurement bugs found mid-session.

Run them from the parent directory:

```
cd Local_pc/Movement_with_hand_detection
.venv/Scripts/python.exe analysis/where_are_jumps.py
```

**Why this matters more than usual here.** Several §0.x conclusions are *negative* —
"the spec's premise does not hold for this sensor" — and they were used to kill or
re-point queue items (2.3 deprioritised; T1/T2 re-pointed; 1.4's acceptance declared
unreachable). **A negative result that cannot be re-run is an assertion, not a
finding.** The load-bearing ones:

| claim | script | consequence if wrong |
|---|---|---|
| 82% of large orientation jumps sit at observability ≥ 0.60 | `where_are_jumps.py` | 2.3 revives; T1/T2 re-point back |
| no bone reaches M2's <2% gate (6–22% IQR) | `m2_which_bones.py`, `m2_pooled.py` | 1.4, M9, T4 and M4's error signal all revive |
| the handedness label is the MIRRORED hand | `resolve_convention.py` | the chirality fixture test's expectations invert |

**⚠ Four measurement bugs were caught DURING the session**, each having already
produced confident wrong numbers (per-hand stream mixing, a mm-vs-metre units gate,
`sigma_long`/`sigma_base` conflated twice, and a live test for a state the UI does
not display). That is evidence of error density, not of rigour — **assume more
survived, and start any audit in this folder.**

---

## 0.1 Amendment log — integration into the pipeline (2026-08-02)

Recorded per this project's standing rule that the pipeline docs govern. Each item below was
found by checking the spec against the **actual shipped code**, not against discussion history.

### A1 — Retargeted from JavaScript to Python (decided with the owner)

Revision 2 was written throughout against `gestureConfig.js`, Three.js and `localStorage`.
**That target does not exist:**

- `gestureConfig.js` is not present anywhere in the repository.
- `Web/src/` contains only `camera.js`, `cubeScene.js`, `handTracker.js`, `main.js` — that is
  **Part Zero-bis** (a cube following a fingertip). It has no gesture layer at all: no snap, no
  rotation, no thumb-outward rule, no 3D object manipulation.
- Every Part One gesture actually built — snap, translate, rotate, thumb-outward restriction,
  mesh-generic 3D rendering — is **Python**, under `Local_pc/`.
- `PART_ONE.md` §1 records the confirmed sequencing: PC-only first, no parallel JS
  implementation, specifically to avoid maintaining tuned thresholds in two languages.

`gestureConfig.js` appears to have been the author's shorthand for the planned engine-agnostic
`gesture_config.json` referenced in `PART_ONE.md` §3. (Note: `PART_ONE.md` §7.4, which that
reference points to for the definition, **does not exist in the file** — a dangling reference,
logged as a separate documentation defect.)

**Resolution (owner decision): build L0–L6 in Python, under `Local_pc/`, and keep this spec's
language engine-neutral so the eventual web/mobile rebuild can reimplement it directly.**
Throughout this document:

| Rev. 2 term | Read as |
|---|---|
| `gestureConfig.js` | **the gesture-logic layer** — today `Resources/HandsTriggeredActions.py` |
| Three.js / scene graph | **the engine binding** — today `Resources/CubeWindow.py` (pygame); Three.js in the future web port |
| `localStorage` | **a persisted profile file** — JSON under the capture root's `profiles/` |
| "JS" / browser assumptions | language-neutral; the reference implementation is Python |

**This is a strengthening, not a compromise.** The `HandState` v2 boundary maps directly onto
the **existing socket wire protocol** (`hands` and `hands_world` packets between
`VisionPipeline.py` and `PythonApp_Main.py`). That protocol is already designated in the
project's cross-platform planning as *the contract a mobile rebuild reimplements against*.
Making `HandState` v2 the versioned wire contract therefore serves the iOS/Android/Windows
goal directly, rather than adding a second parallel abstraction.

### A2 — M5a and M5b are already built and live-calibrated

`Resources/HandsTriggeredActions.py`'s `_is_thumb_outward()` already computes:

```python
v1 = index_MCP - wrist          # p5 - p0
v2 = pinky_MCP - wrist          # p17 - p0
cross = v1.x*v2.y - v1.y*v2.x   # identical to M5a's `s`
if handedness == "Left":
    cross = -cross              # exactly M5b's chirality factoring
```

This is **byte-identical** to M5a's signed-area formula, and the per-handedness negation is
precisely M5b's `sign(s) = chirality × palmFacing` factoring. The sign convention was
calibrated live 2026-08-01 (`GESTURE_PIPELINE_SPEC.md` §13.6) and the rule built on it is
`GAME_RULES.md` rule 3.

**What is genuinely new in M5, and worth building:**

1. **DR-1 — track-level chirality lock.** Not present today; handedness is read per frame.
2. **The `K` fixture test (M5d).** Not present today. **Highest priority item in Phase 1** —
   see A3.
3. **`edgeOnMeasure` = |s| normalised.** The project currently uses only `sign(s)` and
   discards the magnitude. Recovering it costs one division and yields the observability
   signal M4/M6 need.
4. **DR-2 — the edge-on band** and its gesture-suppression contract.

### A3 — The `K` fixture test is validated by a real, recent production bug

M5d warns that the sign convention depends on three independent flips (image-y direction,
preview mirroring, MediaPipe's selfie-view handedness convention) and says *"one fixture test
with a recorded known-hand-known-orientation clip settles it permanently."*

**This project shipped exactly that bug on 2026-08-01** and it survived a "confirmed working
end-to-end" claim: the thumb-outward rule was silently **inverted in production only**, because
`VisionPipeline.py` runs detection on an un-mirrored frame while mirroring the landmark
*coordinates* afterward — leaving the handedness *label* un-mirrored and inverting
`_is_thumb_outward`'s chirality correction. Root cause and fix: `GESTURE_PIPELINE_SPEC.md`
§13.6.1.

M5d's fixture test is the permanent guard against that class of regression, and the recordings
needed to build it (both hands, both orientations) already exist. **Build it first.**

### A4 — M6a is already satisfied

M6a ("remove Euler angles from the estimation path entirely") is **already true**. This project
has used quaternions since rotation was first built, and `PART_ONE.md` §2 makes it a standing
architectural rule: *"Never decompose into separate roll/pitch/yaw Euler angles at any point."*
Verified against the shipped code — no Euler representation exists anywhere in the estimation
path.

**Phase 1's M6a line is a no-op: verify and tick, do not budget time for it.**

### A5 — M4 is an occlusion/outlier mechanism, NOT a pitch-crossing fix

M4 proposes per-landmark inverse-variance weighting. **The pipeline has recorded empirical
evidence that this class of approach cannot fix the pitch-crossing failure**
(`GESTURE_PIPELINE_SPEC.md` §13.7): both a thumb-based vector pair and a PCA/centroid fit over
all four non-thumb MCPs were tested against recorded data and produced values *statistically
indistinguishable* from the simple pair at the degenerate frames — proving the residual is a
**systematic, correlated distortion of the whole knuckle-row reconstruction**, not independent
per-landmark noise.

Revision 2 already hedges correctly (§5 lists M4 as *Helpful*, not *Necessary*, for the
pitch-crossing; M6c is the *Necessary* one). **This amendment makes the reason explicit so it
is not re-litigated:** M4's value is occlusion detection, hallucinated-landmark gating and
outlier rejection. Do not expect it to improve back-of-hand orientation precision, and do not
read a null result there as an M4 implementation failure.

M6c's anisotropic covariance is a *different* mechanism — it models the **direction** of
uncertainty rather than per-landmark magnitude — and is fully consistent with the recorded
finding.

### A6 — M6 subsumes the existing rotation filter; removal is the success criterion

`HandsTriggeredActions.py`'s `HandOrientationFilter` / `_predictive_filter_step` /
`_reliability_alpha` is a hand-rolled, simplified instance of exactly what M6c and M7 describe:
a predictive angular-velocity model blended against the raw reading, weighted by a
conditioning-derived reliability signal.

A filter audit on 2026-08-02 (`GESTURE_PIPELINE_SPEC.md` §13.7.1) kept that filter — its
measured impact is real and substantial (all `>30°` and `>60°` per-frame jumps eliminated in
the tested back-of-hand data) — but logged a TODO to **re-test it for redundancy once a more
fundamental fix lands.** M6 is that fix.

**Amendment: when M6 ships, the existing filter must be removed, not kept alongside it.**
Two overlapping predictive filters is precisely the accumulation the owner has asked the
project to avoid. Retiring it is a deliverable of M6, not an afterthought — and the A/B
harness (M0) is how that removal gets justified rather than guessed.

Related: M6b's `observability = 1 - S[2]/S[1]` overlaps with the existing `conditioning_norm`
(the pre-normalisation length of the orthogonalised second frame vector). **Reconcile these
into one metric; do not ship two competing observability signals.**

### A7 — M8a is deferred to an A/B, not adopted (owner decision)

**The conflict:** M8a states *"Anchor to the palm, not the fingertips… Fingertips determine
whether a grab occurred; they must not determine where"*, and anti-pattern #6 names landmarks
4 and 8 as "the worst points on the hand for position."

`GESTURE_PIPELINE_SPEC.md` §14.1 — designed, verified and **shipped to production on
2026-08-01** — does the opposite: a distance-weighted average of 5 fingertips + 4 MCPs, with
weights frozen at the moment of grab. It was chosen deliberately over a single-frozen-offset
design, is literature-grounded (Napier's grasp taxonomy; Unity XRI Dynamic Attach; Meta
Horizon `GripPoint`), and was verified across 7 real hold intervals then live-confirmed.

Revision 2 itself marks M8 "subject to amendment" and defers to the pipeline docs, so **§14.1
governs.** But two facts complicate a simple "spec loses":

1. The stated reason for rejecting the frozen-offset design was an unresolved **2D-pixel vs.
   3D-world coordinate mismatch**. M6 and M9 supply a metric palm pose, which **dissolves that
   specific objection.** The conditions under which the decision was made will have changed.
2. Both open translation defects — the **yaw/palm-sinking limitation** (§14.1.1) and possibly
   **Object Jump Correction** (§14.1.4) — are symptoms of exactly the fingertip/2D weakness
   M8a predicts.

**Resolution (owner decision): §14.1 stands unchanged for now. M8a is logged as a candidate
replacement, to be A/B-tested against §14.1 on already-recorded data once M6 and M9 land** —
decided by measurement on the M0 harness, not by which document is more recent. Until that
A/B runs, do not modify §14.1's mechanism.

M8b (RTS retrospective smoothing) and M8c (predictive grasp onset) are **additive to §14.1**
and are not affected by this deferral — they can proceed independently.

### A8 — M9 addresses the recorded yaw/palm-sinking limitation

§14.1.1 recorded a deliberately-deferred defect: the computed grasp point swings toward the
palm under **yaw** specifically (pitch and roll are fine), because a purely-2D weighting cannot
distinguish yaw-driven foreshortening from genuine repositioning. The proposed direction at the
time was a vague "startup Z-axis calibration step."

**M9's foreshortening-corrected measure is a better-specified version of that idea**, and M5a's
`edgeOnMeasure` supplies the `|cos θ|` correction term it needs. M2 + M5a + M9 together are the
concrete fix. This mapping is now recorded in the merged queue (`PART_ONE.md` §3.1).

### A9 — Object Jump Correction is absent from §5 but is likely addressed here

§5 of Revision 2 notes that some pipeline TODOs are missing from its table, naming Object Jump
Correction explicitly. Analysing it against this spec:

The root cause (`GESTURE_PIPELINE_SPEC.md` §14.1.4) is a **MediaPipe hand-identity mix-up** —
for a few frames all landmarks of the tracked hand move together, coherently, to a different
on-screen location under the *same* handedness label, at high confidence, then self-correct.

Three modules bear on it directly:

- **M5 DR-1 (chirality lock)** removes the handedness label as a mechanism of confusion, and
  embodies anti-pattern #5 ("deciding per frame what should be decided over time") — which is
  the deeper structural cause.
- **M4's χ² / NIS innovation gate** would reject a 509 px single-frame jump as physically
  implausible and coast on the model instead of absorbing it.
- **M10.7 (grace on loss of tracking)** prevents the recovery transient from causing a drop.

**This is a genuine integration finding, not a restatement:** Object Jump Correction now has a
credible fix path it did not have when it was deferred, and it should be re-tested after Phase 2
rather than treated as independent work. Recorded in the merged queue.

### A10 — Governance: the kill-criterion (added on integration)

The owner has an explicit standing preference (recorded as project feedback) against
accumulating filters that do not earn their keep: *"I do not want to keep accumulating filters
which are useless, as they distort a game logic which shall be pure and simple."*

This spec proposes a substantial amount of machinery. Two things reconcile it with that
preference, and both are binding:

1. **The boundary does the work.** Every module here lives below the `HandState` line. Today's
   `HandsTriggeredActions.py` mixes perception (quaternion math, predictive filtering,
   thumb-outward geometry) *with* game logic (ownership, snapping, translation). Moving
   perception below the boundary makes the gesture layer **simpler than it is today**, not more
   complex. If a module's implementation leaks complexity upward into the gesture layer, it has
   been implemented wrongly.
2. **Kill-criterion (binding).** Revision 2 §7.1 already says *"No perception change ships
   without a replay A/B diff table."* This is hereby elevated to a removal rule:

   > **Every module must demonstrate a measured improvement on the M0 metrics, via replay A/B
   > on identical recorded input, or be reverted.** "It should help in principle" is not
   > sufficient grounds to keep code. A module that shows a null result is removed, and the
   > null result is recorded so it is not retried blindly.

   Precedent: the first Object Jump Correction fix attempt was built, measured, found to make
   no difference, and **discarded rather than shipped** (§14.1.4). That is the standard.

---

## 0.2 Baseline results (2026-08-02) — measured, before any module was built

Merged-queue item 0.2, run via
`Local_pc/Movement_with_hand_detection/AnalyzePerceptionBaseline.py` on the **7
existing recordings** in `Position_during_rotation` — no new capture. Raw output:
`Recordings_perception_layer/metrics/baseline_current_pipeline.jsonl`.

These are the numbers every subsequent module is judged against under A10.

| Metric | Target | **Measured** | Verdict |
|---|---|---|---|
| Bone-length CV | < 3% | **10.0%** mean (6.0–13.4 per session/hand) | **3.3× over target** |
| Palm rigidity residual | < 3 mm | **2.76 mm** mean | **already at target** |
| Palm-normal change, low-motion frames | < 1.5° | ~2.2° mean | indicative only — see caveat |
| Object jumps > 100 px | 0 | **2**, both in `jump_test4`/Right (max 513.9 px) | the known §14.1.4 bug, nothing else |

> **⚠ Finding 1 below was CORRECTED by the scripted-sequence results — read §0.3.**
> The "3.3× over target" reading treated 10% bone CV as a static sensor floor. It
> is not: held still, the same pipeline measures **0.9–1.1%**, comfortably inside
> target. The 10% is motion- and rotation-induced. The *conclusion* (M2 is worth
> building, and fingertips are the weak point) survives; the *reason* does not.

**Finding 1 — M2 is strongly justified, but its value is in the fingers, not the
palm.** Bone-length CV is 3.3× over target, and **the worst bones are consistently
the distal phalanges** (`3-4` thumb tip, `7-8` index tip, `11-12`, `19-20`) at
13–32%. That is exactly what the spec predicts: depth error dominates and is worst
distally. But the **palm is already rigid to 2.76 mm, inside the < 3 mm target** —
so M2's error-signal value, and M4's downweighting, apply mainly to fingertips. The
palm frame that M6b builds on is already well-conditioned.
*(Caveat: short bones inflate CV mechanically — `9-13`, adjacent MCPs, appears as a
worst-bone in 3 sessions largely because its mean length is small. Do not read
short-bone CV as equivalent to long-bone CV.)*

**Finding 2 — the object-jump metric works and is clean.** Exactly 2 jumps across
3801 frames, both in the one recording with a confirmed reproduction of Object Jump
Correction, max 513.9 px (matching the 509 px figure in §14.1.4). Every other
session: zero. This is now a usable regression metric — if M4's χ² gate works,
these 2 go to 0 and nothing else changes.

**Finding 3 — palm-normal jitter cannot be properly measured yet.** The ~2.2°
low-motion figure is a stand-in computed from frames where the anchor moved < 2 px;
it is **not** the spec's held-still metric and must not be quoted as one. It needs
the §7.2 *static hold* sequence. Reported only to show the order of magnitude.

### The hypothesis test: DR-2 validated

M5/DR-2 assumes the palm/back sign is reliable everywhere **except** near edge-on.
Tested by computing the edge-on measure retroactively per frame and bucketing the
recorded sign flips:

| edge-on band | frames | flips | flips / 1k frames |
|---|---|---|---|
| [0.00, 0.05) | 17 | 13 | **764.7** |
| [0.05, 0.10) | 27 | 6 | **222.2** |
| [0.10, 0.15) | 24 | 7 | **291.7** |
| [0.15, 0.25) | 57 | 1 | 17.5 |
| [0.25, 0.40) | 205 | 3 | 14.6 |
| [0.40, 0.60) | 341 | 5 | 14.7 |
| [0.60, 1.01) | **3130** | **0** | **0.00** |

3801 frames, 35 flips. **74.3% of flips fall inside the proposed DR-2 band
(< 0.15), which is only 1.8% of frames — a 41.5× over-representation**, with a
cleanly monotonic gradient.

**Two conclusions, at different confidence levels — the distinction matters:**

1. **Solid: the sign is rock-stable when well-conditioned.** *Zero* flips across
   3130 frames above edge-on 0.60 — 82% of all frames. The cue is trustworthy in
   the bulk of normal operation, and every instability is confined to a narrow
   band. This is what makes DR-2 both viable and cheap.
2. **Solid: the lowest buckets are demonstrably chatter, not real rotation.** A
   concentration of flips near edge-on is *expected even with a perfect sensor* —
   a genuine palm↔back rotation must pass through edge-on, so a correct flip
   happens there. Concentration alone therefore proves nothing. **But the rate
   does**: 13 flips across 17 frames (≈0.57 s) is physically impossible as
   genuine rotation; likewise 6 flips in 27 frames. Those are noise chatter,
   confirmed by rate rather than assumed from position.
3. **Not yet established: whether the mid-band flips (0.15–0.60) are spurious.**
   1, 3 and 5 flips over 57–341 frames are entirely consistent with genuine
   rotations. Separating them requires the §7.2 *scripted non-crossing motion*
   sequence, which is what M0's chirality-flip-rate metric actually specifies.

**Parameter amendment flagged, not applied.** `EDGE_ON_THRESHOLD = 0.15` was a
starting guess. The data shows flips continuing at a flat ~15/1k rate up to 0.60
and then stopping dead. That *may* argue for a higher threshold — but per
conclusion 3, those mid-band flips may be legitimate rotations, and raising the
threshold would suppress valid gestures over a much wider range (0.60 covers ~18%
of frames vs. 1.8%). **Do not raise it on this evidence.** Re-derive it once the
scripted non-crossing sequence exists.

---

## 0.3 Scripted-sequence results (2026-08-02) — item 0.2b, and one correction to §0.2

Four §7.2 sequences recorded with `RecordPerceptionSequence.py` (pure raw capture,
no gesture logic) and analysed with `AnalyzePerceptionSequences.py`. Sessions in
`Recordings_perception_layer/sessions/`.

| sequence | bone CV | resting jitter (mean / fingertips) | palm-normal | edge-on min | sign flips |
|---|---|---|---|---|---|
| **static_hold** | **0.89 / 1.14 %** ✅ | **0.45 mm** / 0.83 mm ✅ | **0.88 / 0.92°** ✅ | 0.714 | **0** |
| **non_crossing** | 9.47 / 9.86 % | 5.73 / 10.45 mm | 3.49 / 3.88° | **0.353** | **0** |
| pitch_sweep_slow | 24.96 % | 14.75 / 26.31 mm | 11.05° | 0.010 | 10 |
| pitch_sweep_fast | 21.39 % | 12.22 / 21.80 mm | 13.17° | 0.088 | 11 |

### Correction to §0.2: the 10% bone CV is not a sensor floor

**Held still, this pipeline meets every M0 target it can be measured against** —
bone CV 0.89–1.14% (target < 3%), resting jitter 0.45 mm (target < 1.5 mm),
palm-normal jitter 0.88–0.92° (target < 1.5°). MediaPipe at rest is *excellent*.

The error is **motion- and pose-driven**, and the gradient is steep and monotonic:

```
still 1%   ->   free translation 9.5%   ->   pitch rotation through edge-on 25%
```

§0.2 read the 10% figure (measured on grab-and-rotate recordings) as a static
floor and concluded M2 was needed to fix a noisy sensor. **That reasoning was
wrong.** The corrected picture:

- **M2's calibration is much easier than assumed.** Clean 1%-CV samples are
  readily available — just gate collection on low motion. The spec's §2f freeze
  criterion (IQR < 2%) is comfortably achievable.
- **But M2's bone-length *residual* is a weaker error signal than the spec
  assumes.** M4 treats it as a per-landmark quality cue; this data says it will
  mostly be reporting *"the hand is rotating"*, not *"landmark 8 is bad"*. It
  conflates pose with per-landmark reliability. **Amendment: M4 must not use the
  raw bone residual directly — it needs normalising against the current
  pose/motion, or it will down-weight every landmark uniformly whenever the hand
  moves**, which is both useless and actively harmful during fast gestures.
- §2f's recorded pitfall is about pose diversity removing *bias*. This is a
  different and additional effect: pose drives *variance*. Both matter.

### The `EDGE_ON_THRESHOLD` question is settled: keep 0.15, do not raise it

§0.2 flagged a temptation to raise the threshold toward 0.60, because flips in the
old recordings continued up to that value. **The `non_crossing` sequence answers
this decisively:**

- **Zero sign flips across 723 frames on both hands**, during 30 s of deliberately
  varied motion — translation, tilting, near the frame edges — with the palms
  never turning over.
- **Edge-on never dropped below 0.353** (Left) / **0.437** (Right). Normal
  non-crossing motion *does not enter the danger band at all*: 0.0% of frames
  below 0.15.
- But **4.6–8.0% of those normal frames sit below 0.60.** A 0.60 threshold would
  therefore suppress `palmFacing`-dependent gestures during ordinary use, for no
  benefit — there were no flips to prevent.

**Conclusion: `EDGE_ON_THRESHOLD = 0.15` is correct and safe.** It is never
reached in normal motion, so DR-2 will only ever fire during a deliberate
crossing — exactly its intent. Raising it toward 0.60 is now positively
contraindicated, not merely unsupported.

### Pitch sweeps: honest limits of what this shows

Flips occur across the whole edge-on range (0.010–0.807). During a pitch sweep the
hand *genuinely* crosses palm↔back, so most of these flips are **correct**, not
errors — the slow sweep's 10 flips in 30 s is about right for ~3 s per sweep.

What cannot be concluded without a ground-truth crossing count: whether the
high-edge-on flips (0.584, 0.599, 0.729 in the *slow* sweep) are genuine fast
crossings or glitches. At 24 fps (41.5 ms/frame) a fast rotation can legitimately
jump the whole band between two frames, which explains the fast sweep's
high-edge-on flips — but a *slow* sweep should linger near zero and flip there.
**Flagged as suspicious, not diagnosed.** Resolving it needs a sequence with a
counted number of deliberate crossings.

### Two incidental findings worth carrying forward

1. **The pipeline runs at ~24 fps, not 30.** All four sequences measured
   24.09–24.14 fps from real `tCapture` timestamps. The older recorders
   *synthesised* a 33 ms cadence, so this was invisible until now. Real interval is
   ~41.5 ms. **Every "N frames at 30 fps" parameter in this spec is therefore
   ~38% longer in wall-clock than intended** — M5e's 3-frame dwell, M10's 3/4-frame
   dwells, M4's 8-frame coast limit. Re-express them in milliseconds.
2. **14 of 480 frames lost detection entirely during the fast sweep** (2.9%), vs.
   0 lost in every other sequence. Motion blur costs whole frames, not just
   precision — which is what M4's coast limit and M7's prediction horizon exist to
   ride out.

---

## 0.4 Object Jump Correction — root cause REFINED and confirmed (2026-08-02)

Three more sequences recorded (`two_hand_overlap`, `two_hand_near_miss` as a
matched control, and re-using `pitch_sweep_*`), analysed with
`AnalyzeHandIdentity.py`. **The result overturned the working hypothesis and
produced a complete, concrete mechanism.**

### The hypothesis that was wrong

§14.1.4 and A9 assumed the mixup came from **two hands being confused with each
other** when close together, and the fix was framed as DR-1 + M4's χ² gate. The
controlled comparison does not support the proximity story:

| sequence | one-hand frames | teleports > 100 px | identity swaps |
|---|---|---|---|
| two_hand_overlap (hands genuinely occlude) | 205 / 717 | 2 | **0** |
| two_hand_near_miss (visible gap, CONTROL) | 0 / 723 | **0** | **0** |

Occlusion clearly *happened* (28.6% single-hand frames vs. 0% in the control),
but produced no identity swap at all. **Proximity and occlusion are not the
mechanism.**

### The actual mechanism: MediaPipe's handedness label is unstable

The mixups appeared in **`pitch_sweep_fast` — a ONE-HANDED sequence**, where
confusing two hands is impossible by construction:

| sequence | frames | duplicate-label frames | label flips | mean score at flip |
|---|---|---|---|---|
| static_hold | 288 | 0 | 0 | — |
| non_crossing | 723 | 0 | 0 | — |
| pitch_sweep_slow | 722 | 0 | 0 | — |
| **pitch_sweep_fast** | 480 | **4** | **18** | **0.663** |
| two_hand_crossing | 723 | **9** | 5 | 0.970 |
| **two_hand_overlap** | 717 | **12** | 5 | 0.986 |
| two_hand_near_miss | 723 | 0 | 0 | — |

Two distinct failures, both real, both absent from every control:

1. **Label flips on a single physical hand.** In `pitch_sweep_fast` one physical
   hand was labelled `Left` on 448 frames and **`Right` on 14** — with continuous
   position across the flip (e.g. frame 254 `Left` x=268.9 → 255 `Right` x=258.0
   → 256 `Left` x=272.7). Obviously the same hand; only the label moved.
2. **Duplicate labels — both detections carrying the SAME label** (`('Left','Left')`).
   4 frames in fast rotation, 9 and 12 in the two-hand sequences. Zero in all
   controls.

Handedness confidence degrades monotonically with rotation, and flips cluster at
the bottom of it:

```
static 0.981  ->  non_crossing 0.976  ->  pitch_slow 0.960  ->  pitch_fast 0.941
                                          (11.5% of frames < 0.90, min 0.501)
flips occur at mean score 0.663, against a ~0.95-0.99 baseline
```

**This is exactly what §5b predicts** — handedness is decided from *appearance*
(knuckles, creases, shading), not landmark geometry, so it degrades under blur and
when the back of the hand is shown. Handedness and palm-facing are the same bit,
and rotation is what breaks it. The two-hand sequences did **not** reproduce it
because the palms stayed toward the camera throughout, keeping those cues intact.

### Why this produces the observed cube jump — confirmed in production code

Cube ownership is keyed by handedness (`cube_owned_by(handedness)`,
`_thumb_outward_snap_allowed[handedness]`), and the wire protocol resolves hands
by label:

```python
def extract_hand_by_type(hands_array, handedness):
    hand = next((h for h in hands_array if h.get("handedness") == handedness), None)
    return hand.get("landmarks", []) if hand else []      # <- first match, or NOTHING
```

With duplicate labels `('Left','Left')`:

- the `"Left"` lookup returns **whichever came first** — possibly the physically
  *right* hand → that cube snaps across the screen to the other hand's position;
- the `"Right"` lookup returns `[]` → `remap_keypoints` emits 21 zero points →
  `_is_detected()` is False → **tracking-loss release fires and the cube is
  dropped.**

A transient label flip does the same thing one frame at a time. This accounts for
both halves of the recorded §14.1.4 event — the 509 px teleport *and* its
self-correction a few frames later.

### Why this was invisible until now

The older recorder stored hands in a **dict keyed by handedness**
(`hand_data_by_hand[handedness] = {...}`). A duplicate label silently
**overwrote** the first entry, so the failure mode was destroyed at record time
and could never appear in analysis. The new recorder keeps the raw MediaPipe
**list**, which is why the same bug that had resisted diagnosis for two sessions
showed up within minutes.

*This vindicates the pure-raw-capture design (§M0's integration note): derived or
re-keyed data at record time can erase the very defect you are hunting.*

### Consequences for the plan

- **DR-1 (chirality lock) is confirmed as the correct fix, and is now the
  primary one** — not DR-1 *plus* M4 as A9 assumed. Making handedness a
  track-level property removes both failure modes at their source.
- **A ready-made gate exists**: the handedness `score`. Flips occur at ~0.66
  against a 0.95–0.99 baseline, so DR-1's acquisition rule ("accumulate over
  frames where quality is high") has a directly usable signal.
- **A stateless duplicate-label resolver was built and then REMOVED the same day
  (2026-08-02) — see §0.5.** It chose between two same-labelled detections by
  handedness score. Measurement killed it: the score gap was < 0.05 (a coin
  flip) on 36% of affected frames, it disagreed with position continuity on 16%,
  and it was structurally blind to the larger half of the problem — 28 recorded
  single-hand label flips. It addressed ~47% of identity events. **DR-1 was built
  in its place** (§0.5).
- **M4's χ² gate is demoted** for this TODO from "necessary" to "useful
  belt-and-braces": it would catch the *symptom* (an implausible jump) but not
  the cause, and per A5 it should not be relied on where the real fix is upstream.

---

## 0.5 DR-1 built (2026-08-02) — and a design correction the data forced

Owner decision: remove the stateless resolver ("it does not address the issue")
and implement a **hysteresis-based track identity** instead. Built in
`hands_visualizer.py` as `_HandTrack` / `_HandIdentityTracker`, at the same
single source as `_mirror_handedness`.

### The design

1. **Associate detections to tracks by POSITION**, never by MediaPipe's label
   (greedy nearest-neighbour, gated at `MAX_ASSOC_PALM_RATIO = 3.0` palm widths —
   normal frame-to-frame motion measured 0.6–1.4 palm widths, the Object Jump
   excursion was 513 px).
2. **Lock the label** after a short weighted vote (`LOCK_VOTE_FRAMES`), or
   immediately as the complement when a second track appears (DR-1's
   two-simultaneous-hands rule).
3. **A raw-label mismatch flags the track**: brief → hold (transient glitch);
   long *and confident* → switch.
4. **Re-decide freely when a track genuinely ends** (absent > `TRACK_END_MS`).

All dwell constants are expressed in **milliseconds and converted at the measured
~24 fps**, per finding N1 — not the 30 fps the spec's frame counts assumed.

### The correction: "never switch mid-track" was wrong

The first implementation followed a refinement suggested during design — *never*
switch a locked label, on the reasoning that handedness cannot change within a
track (your left hand does not become your right hand). **Replay disproved it.**

That reasoning holds only if the track genuinely follows one physical hand — and
**position-based association cannot guarantee that.** When two hands cross,
nearest-neighbour association swaps them, the track identity itself becomes
wrong, and a never-switch rule then locks that error in permanently.

Measured on `two_hand_crossing` with the never-switch rule: **528 overrides,
96.6% at score > 0.90**, in runs of **62 and 225 consecutive frames** — the
tracker confidently holding a *wrong* label for ~9 seconds after a crossing.

The owner's original "switch after YYY frames" was correct. What made it safe to
implement was that the two cases separate cleanly in the data:

| case | run length | score | correct action |
|---|---|---|---|
| transient sensor glitch | 1–2 frames | **0.52** | hold the lock |
| association swap at a crossing | 62–225 frames | **0.97–0.98** | switch |

So only mismatches at `score >= 0.90` accumulate toward a switch, and the dwell is
longer than any observed glitch. Switches are applied **at tracker level,
exchanging both labels together**, so two tracks can never transiently hold the
same label.

### ⚠ `SWITCH_MS` is a TUNABLE latency-vs-false-glitch trade-off

Currently **12 frames (~500 ms)**. This is the one parameter here most worth
revisiting, and the trade-off is genuinely two-sided. Measured populations:

| | run length |
|---|---|
| longest glitch run correctly **held** | **7 frames (~292 ms)** |
| genuine association swaps (raw disagreement) | **62–225 frames** |

- **Lower** → faster correction after a real crossing, but the margin above the
  7-frame glitch shrinks. At 7 or below, a glitch that actually occurred in these
  recordings **would have caused a false switch** — a cube visibly jumping to the
  wrong hand for no reason.
- **Higher** → more margin, and real swaps still cannot be missed (they run
  62–225 frames), at the cost of the wrong label persisting longer after a
  genuine crossing.

12 was chosen as the balance: 5 frames of margin above the worst observed glitch,
half a second of worst-case correction latency. **Re-derive from fresh recordings
if the camera, frame rate or lighting change** — the glitch population sets the
floor and is blur/lighting dependent, so the safe minimum will move with them.

*A cheaper structural discriminator was proposed and **refuted by measurement**:
"both tracks mismatched simultaneously" does not separate the populations. Real
swaps frequently have no second visible track at all (5 of 8 occurred with one
hand detected — `pitch_sweep_fast` is one-handed throughout, and hands occlude
during crossings), while two correctly-held glitches DID show both tracks
mismatched for 5 frames each. Using it as a fast-track would have caused false
switches on exactly the runs the current rule correctly rejects. Do not retry it
without new evidence.*

### Verified by replaying all seven recorded sessions

| sequence | duplicates out | overrides (before → after) | longest wrong-hold run | switches |
|---|---|---|---|---|
| static_hold | 0 | 0 → **0** | 0 | 0 |
| non_crossing | 0 | 0 → **0** | 0 | 0 |
| pitch_sweep_slow | 0 | 0 → **0** | 0 | 0 |
| pitch_sweep_fast | 0 | 116 → **41** | 26 | 1 |
| two_hand_crossing | 0 | 528 → **71** | **225 → 10** | 4 |
| two_hand_overlap | 0 | 322 → **24** | 10 | 1 |
| two_hand_near_miss | 0 | 0 → **0** | 0 | 0 |

- **Duplicate labels eliminated entirely** (25 → 0) — structurally, since two
  detections associate to two different tracks each emitting its own label.
- **Longest wrong-hold collapsed from 225 frames (~9 s) to 10 (~420 ms)** — the
  intended dwell before a switch confirms, not a stuck error.
- **Zero overrides and zero switches in all three control sequences.** The
  tracker is inert when nothing is wrong, so it cannot introduce regressions in
  normal use.

`pitch_sweep_fast`'s 26-frame run exceeds the 12-frame dwell because low-score
frames legitimately do not count toward a switch — correct behaviour (never
switch on unreliable evidence), at the cost of a longer correction under heavy
blur.

### Shared by production AND the debug tool (2026-08-02)

DR-1 was initially built inside `hands_visualizer.py`, which is server-side —
making it **production-only**, since `LiveSnapDebug.py` runs MediaPipe in-process
and never imports it. Owner instruction: *"I do not want to have a debug tool
which is not in tune with the production."*

Resolved the architecturally correct way rather than by copying: the tracker was
extracted to **`Resources/hand_identity.py`** — standalone, pure stdlib, no
cv2/mediapipe and no window side effects, operating on plain `(x, y)` tuples so
each caller adapts its own landmark shape. Both consumers now **import** it.

This is the §1 boundary discipline applied to the tooling itself: perception
lives below the `HandState` line and is shared, not duplicated. Duplication is
what let the thumb-outward sign convention drift between the two paths once
already (§13.6.1).

**The same change fixed a latent bug in the debug tool**: it stored hands in a
dict keyed by handedness, so a duplicate label silently overwrote one of the
pair — the very defect that hid Object Jump Correction in the old recorder.

**Verified**: production and the debug tool produce **byte-identical identity
output across all 7 recorded sessions**, and exactly one tracker definition
exists in the codebase.

### Still open

- ~~**Not yet live-tested.**~~ **DONE 2026-08-02 — see §0.6 below.**
- **Acquisition can still lock wrong.** If the first frames are mislabelled, the
  switch branch is what recovers it — which is now another reason that branch
  must exist. **Observed live twice (§0.6), and recovered both times.**
- `_ASSUMED_FPS = 24.0` is hard-coded. It should come from measured frame timing
  once `HandState.tCapture` exists (M0/N1).

---

## 0.6 DR-1 LIVE-CONFIRMED against a camera (2026-08-02)

Run via `launch.bat`'s exact code path (production: `VisionPipeline.py` +
`Client.py`), the operator deliberately rotating hands to show the backs of
them and crossing/overlapping them while holding cubes. **Operator verdict:
"it's working"** — no cube teleported to the other hand and none was
spuriously dropped.

This closes the item the handoff called out as the one thing standing between
replay verification and trust, and it matters because this project has shipped
a production-only bug that survived a "confirmed working end-to-end" claim
once already (§13.6.1 / handoff §2.2).

**Console record — 16 tracker events, 0 errors or tracebacks:**

| event | count | reading |
|---|---|---|
| `identity locked` | 5 | 3 by vote, 2 as the complement of an existing track |
| `track ended` | 4 | hands leaving frame — identity correctly re-decidable |
| **`duplicate label would have been emitted`** | **3** | the end-of-function invariant firing — **new, see below** |
| `switch confirmed after 12 confident frames` | 2 | lone track, `Right`→`Left`: acquisition locked wrong, switch branch recovered it |
| `switch confirmed` (with clash) | 1 | `Left`→`Right`, other track took `Left` — an association swap through a crossing |
| **`transient glitch rejected, lock held`** | **1** | 3 confident mismatched frames held, then agreement — **the core design behaviour, proven live** |

**The failure conditions were genuinely exercised, not merely absent.** Those
events only fire when MediaPipe actually disagreed with the track, so this was
not a run that passed by never provoking the bug — the glitch-rejection and
switch branches both fired and both did the right thing.

### One genuinely new finding: the duplicate-repair fallback is reachable in normal use

§0.5 reported duplicates eliminated **structurally** ("two detections associate
to two different tracks each emitting its own label"), and the explicit
end-of-function invariant was described as an edge case found by fuzzing —
reachable only when a detection jumps beyond the association limit with both
track slots full.

**It fired 3 times in a single short live session.** No duplicate was emitted —
the invariant did exactly its job, which is why the run passed — but the
frequency is new information that the 7 recorded sessions did not predict.

Two readings, and this is **not yet diagnosed**:

- `MAX_ASSOC_PALM_RATIO = 3.0` may be too tight for live motion. It was derived
  from recorded frame-to-frame motion of 0.6–1.4 palm widths; a live operator
  deliberately crossing hands fast may simply exceed it.
- Or the association is failing for a different reason (a dropped frame — recall
  §0.3's finding that 2.9% of frames lost detection entirely under fast motion —
  leaves a stale `avg` position for a track).

**Do not tune `MAX_ASSOC_PALM_RATIO` on this evidence.** Per A10, that is a
measurement question, not a guess: the fallback firing is currently *harmless*
(the invariant catches it), so the cost of leaving it alone is zero, and the
next scripted-sequence recordings (queue 0.2b) can quantify it properly.
**Logged as queue item N9.**

### Also observed: `SWITCH_MS = 12` frames behaved correctly at both extremes

The single transient glitch ran 3 confident frames and was **held** (correctly
rejected), while the real association swap accumulated its full 12 and
**switched**. That is the exact separation §0.5 predicted from the recorded
populations (glitches ≤7 frames, real swaps 62–225), now confirmed against a
live camera rather than replay. **No reason to re-derive `SWITCH_MS` at this
time** — but the standing instruction still holds: re-derive it if the camera,
frame rate or lighting change.

---

## 0.7 `palm_back` recorded (2026-08-02) — N3 ground truth, and a frame-rate surprise

Queue item 0.2b continued. §7.2's *palm↔back rotation at 4 speeds* recorded with
`RecordPerceptionSequence.py --sequence palm_back`, to E: per owner instruction.
Session: `2026-08-02_221948_palm_back` (630 frames, 39.95 s, 628 with a hand).

> **⚠ BOTH `palm_back` TAKES WERE DELETED (2026-08-02, owner instruction)** — the
> counted one above and an earlier aborted one — because both were recorded in
> poor light at 15–16 fps: *"I don't want the lack of light to pollute our
> analysis."* **The numeric result below is retained as INDICATIVE ONLY; the data
> behind it no longer exists and it must not be cited as a measurement.** What
> survives as durable is the *method* — the unit trap, the frame-rate finding, and
> the redesign in §0.7.1. Re-record in daylight before concluding anything.

### The counting convention — read this before using the number

**The operator counts one "crossing" as palm → back → palm, i.e. a full CYCLE.**
The analyser counts per-frame **sign inversions**. One cycle is **two** sign
changes, so the two units differ by 2×.

> **This ambiguity produced a wrong reading on the first pass** — 29 was briefly
> compared against 52 detected flips and misreported as a ~40% *spurious* rate,
> when the correct comparison (58 expected) shows the opposite. Both numbers are
> now stored explicitly in the session's `meta.json` as `counted_crossing_cycles`
> (29) and `expected_sign_changes` (58). **Always compare against
> `expected_sign_changes`.**

### Result: the sign cue UNDER-detects crossings

| | expected | detected | delta |
|---|---|---|---|
| Left | 58 | **52** | −6 |
| Right | 58 | **50** | −8 |

*(58 is a lower bound: the clip ends with the hand edge-on mid-turn and that
trailing incomplete transition was not counted, so the true figure may be 59.)*

**There is no evidence here of a large spurious-flip population** — the earlier
working suspicion. If anything the cue misses genuine crossings. Detected flips
span the whole edge-on range (0.015–0.949), and per the operator several cycles
were deliberately fast, which is consistent with genuine crossings traversing the
band between frames.

**What totals alone CANNOT settle** — and this is the honest limit of this take:
a compensating mix (some genuine crossings missed *plus* some spurious flips)
also nets to 52. Separating them needs per-flip matching against the rotation
timeline, not counts. **N3 is therefore advanced, not closed.**

### ⚠ The pipeline does NOT run at a fixed ~24 fps — it is environment-dependent

Finding N1 (§0.3) recorded ~24 fps as a property of the pipeline. **Two takes
this evening measured 15.1 and 15.77 fps** — same recorder, same camera, same
machine, same resolution. The seven earlier sequences were recorded 19:13–20:51
and measured 24.09–24.14; these at 22:18–22:19.

The likely mechanism is webcam **auto-exposure lengthening frame duration in
dimmer light** — untested, so treat it as the leading hypothesis rather than a
diagnosis. What matters is the consequence, which does not depend on the cause:

- **Frame rate varies with ambient conditions**, so `ASSUMED_FPS = 24.0` in
  `hand_identity.py` is not a constant to be measured once and hard-coded.
- **Every DR-1 dwell derives from it.** `SWITCH_FRAMES = round(500 × 24/1000) =
  12`. At 15.77 fps those 12 frames are **~761 ms, not the intended 500** — a 52%
  overshoot, in the parameter §0.5 identified as the one most worth getting right.
  The live test (§0.6) that validated the 12-frame dwell was itself run at an
  unmeasured frame rate.
- **N7 is therefore a correctness item, not tidiness.** Promoted. New queue item
  **N10** records the environment-dependence itself.
- This take is **not frame-rate-comparable** to the seven earlier sequences, and
  the wider 63.4 ms interval is precisely the confound for the high-edge-on
  question above. **Re-record `palm_back` in better light** before drawing
  conclusions about where spurious flips live.

### Housekeeping — both takes deleted

`2026-08-02_221831_palm_back` (aborted, 24.9 s of 40) and
`2026-08-02_221948_palm_back` (the counted one) were **both deleted on owner
instruction**. The seven earlier sessions are intact and verified after the fact.

*Incidental confirmation of N4: the delete itself failed part-way with `The device
is not ready` — the E: dropout, live rather than historical. It completed on
retry, and the result was re-verified rather than assumed.*

---

## 0.7.1 Redesign: four speed-decoupled `palm_back` takes (owner request, 2026-08-02)

> *"It may be worth decoupling and do 4 recordings at different speeds, so we can
> gauge what is the threshold where we lose detection."*

**Why this is better than the single blended take.** Mixing four speeds into one
clip yields one flip count that cannot answer the question that matters — *at what
speed does the cue start missing crossings?* One take says "6–8 missed"; four
takes locate the **threshold**, which is what a fix or a quality gate has to be
designed against.

Built into `RecordPerceptionSequence.py`:

| sequence | cycle time | prescribed cycles | expected sign changes | duration |
|---|---|---|---|---|
| `palm_back_s1_very_slow` | ~4 s | 10 | 20 | 40 s |
| `palm_back_s2_slow` | ~2 s | 15 | 30 | 30 s |
| `palm_back_s3_medium` | ~1 s | 20 | 40 | 20 s |
| `palm_back_s4_fast` | ~0.5 s | 30 | 60 | 15 s |

Three deliberate design choices, each fixing something that bit us:

1. **Cycle counts are PRESCRIBED, not recalled.** Ground truth comes from the
   protocol, not from the operator remembering a number afterwards. `--cycles`
   overrides when the actual count differs; whichever is used is written to
   `meta.json` along with `expected_sign_changes = 2 × cycles`. **Both units are
   always stored**, so the §0.7 unit trap cannot recur.
2. **The axis is PITCH, stated explicitly** (owner instruction). Not incidental:
   the open TODO is the *pitch*-plane crossing (T2 / §13.7), and the
   `pitch_sweep_*` takes these are compared against are pitch — a yaw take would
   not be comparable. Yaw has its own separate item (T4, §14.1.1) and must not be
   mixed in. The recorder now prints the full axis description at briefing time
   and stores `rotation_axis: "pitch"` in `meta.json`.
3. **A low-frame-rate guard.** The recorder warns loudly at save time when
   `measured_fps < 20`, telling the operator to add light and re-record. A quiet
   15 fps take is worse than a failed one: it looks valid in analysis while being
   non-comparable to the rest of the corpus.

The original `palm_back` sequence is kept runnable but marked **SUPERSEDED**.

**Not yet recorded** — deferred to daylight at the owner's request.

---

## 0.8 Speed-threshold sweep (2026-08-03, daylight) — N3 CLOSED, and totals were lying

The four `palm_back_s*` takes recorded in daylight, all at **24.1–24.5 fps** (the
N10 guard stayed silent), 100% detection on every take, both hands simultaneously.
Operator-counted actual cycles, patched into each `meta.json`.

| speed (s/cycle) | hand | expected | detected | delta | **implausible** | **implaus %** | dup-label frames |
|---|---|---|---|---|---|---|---|
| 4.44 very slow | L | 18 | 17 | −1 | 1 | **6%** | 0 |
| 4.44 | R | 18 | 17 | −1 | 4 | **24%** | 0 |
| 2.14 slow | L | 28 | 30 | +2 | 2 | **7%** | 1 |
| 2.14 | R | 28 | 31 | +3 | 7 | **23%** | 1 |
| 1.29 medium | L | 31 | 27 | −4 | 4 | **15%** | 8 |
| 1.29 | R | 31 | 37 | +6 | 15 | **41%** | 8 |
| 0.96 fast | L | 31 | 28 | −3 | 14 | **50%** | 11 |
| 0.96 | R | 31 | 40 | +9 | 23 | **58%** | 11 |

**"Implausible"** = a flip whose *both* straddling frames sit at edge-on > 0.60.
The analyser reports a flip at `min(eos[k], eos[k-1])`, so this means the hand
would have crossed s = 0 and re-emerged strongly oriented within one ~41 ms frame.
That is beyond plausible hand-rotation speed, so these cannot be genuine crossings.
*(The 0.60 cut is a judgement call, inherited from §0.2's observation that the cue
was stable above it; the monotonic trend below does not depend on the exact value.)*

### Finding 1 — the totals were lying, and this is the headline

**Delta stays small at every speed** (−4 to +9). Judged on totals alone — which is
all §0.7 could do — you would conclude the cue works fine at all four speeds.

**It does not.** The implausible fraction rises monotonically from **6%** to
**58%**. At the fast end, *half or more of every detected flip is physically
impossible*, yet the total still lands near ground truth — because genuine
crossings are being **missed** at roughly the same rate spurious ones are being
**added**. The two errors cancel in the total.

**This resolves the question §0.7 declared unresolvable.** §0.7 said a compensating
mix of missed-plus-spurious "needs per-flip matching against the rotation
timeline." It does not — the edge-on plausibility test separates them from the
recorded data alone, with no timeline needed. **N3 is closed.**

### Finding 2 — the knee is around 1.3 s/cycle

6–24% at 4.44 s/cycle and 7–23% at 2.14 are broadly flat; degradation accelerates
at 1.29 (15–41%) and is severe by 0.96 (50–58%). **Between ~2 s and ~1 s per cycle
is where the sign cue stops being trustworthy.**

**Honest limit:** the "fast" take only reached **0.96 s/cycle, not the 0.5 s
prescribed** — the operator could not sustain the target rate. So the breakdown is
bracketed, not bounded: we know it is already severe by ~1 s/cycle, but not where
it saturates. A genuinely faster take would be needed for that, and may not be
physically achievable by hand.

### Finding 3 — the Left/Right asymmetry is systematic

Right is worse than Left at **every** speed (24 vs 6, 23 vs 7, 41 vs 15, 58 vs 50).
Consistent across four independent takes, so not noise. **Not diagnosed** — a
candidate is the handedness-dependent chirality correction being the one
non-symmetric step in the pipeline (§13.6.1's bug lived exactly there), but that is
a hypothesis, not a finding. Logged as **N11**.

### Finding 4 — duplicate labels scale with rotation speed

Duplicate-label frames per take: **0 → 1 → 8 → 11**, monotonic with speed. This is
precisely DR-1's target failure mode, and it independently reproduces §0.4's
"handedness degrades under rotation" on fresh daylight data. These takes are **raw
pre-DR-1 capture**, so this is the *unmitigated* rate — a direct measure of what
DR-1 has to absorb, and further justification for it.

*Tooling note: a first pass of this analysis under-counted flips because it
appended every hand matching a label, while `AnalyzePerceptionSequences.py`'s
`per_hand_stream` takes only the first per frame. Duplicate-label frames therefore
produced same-index entries that the consecutive-frame check silently dropped. The
discrepancy (33 vs 37) was chased rather than reported, and the corrected numbers
above reconcile exactly with the analyser.*

---

## 0.9 M5d `K` fixture test — BUILT AND PASSING (2026-08-03). Item 1.1 DONE.

`Local_pc/Movement_with_hand_detection/VerifyChiralityFixture.py`. Four ground-truth
clips recorded in daylight (24–25 fps, 100% detection). **All 13 checks pass,
exit 0.**

**It exercises production's real `_is_thumb_outward`**, imported headlessly via
`SDL_VIDEODRIVER=dummy` to work around the `CubeWindow()` import side effect
(§7.3). This is the whole point: a fixture test carrying its own copy of the
formula would have passed happily on 2026-08-01 while the game was inverted, and
would have guarded nothing. When the L7 cleanup removes that side effect, two
env-var lines can simply be deleted.

Three checks per clip, plus a drift guard:

| check | result |
|---|---|
| label matches ground truth | **788/788** across four clips |
| **production sign is correct** | **788/788** — both hands, both facings |
| negative control (label un-mirrored → answer must invert) | **788/788** |
| drift guard: production vs. `LiveSnapDebug` copy | identical |

### THE LABEL CONVENTION — established from data, and it is counter-intuitive

**The label carried through this pipeline is the MIRRORED (apparent) hand, not the
physical hand. A clip of the operator's physical RIGHT hand carries the label
`"Left"`.**

The first version of this test assumed the opposite and failed **0/788** on all
four clips. That was resolved by measurement rather than by flipping the
expectation until it went green:

> In a mirrored preview the operator's physical right hand *necessarily* appears
> on the right of the image — the mirror property, not an interpretation. Across
> every recorded session, for frames holding exactly two distinctly-labelled
> hands, the `"Right"` label fell on the image-**left** hand **100%** of the time
> in every take where hands stay on their natural sides: `static_hold` (288
> frames), `non_crossing` (723), `palm_back_s1_very_slow` (980). The two-hand
> crossing takes sit near 30% precisely *because* the hands deliberately swap
> sides — corroborating, not contradicting.

**Both paths converge on this convention by different routes**, which is exactly
what §13.6.1's fix established and why `_is_thumb_outward` is correct in both:

| path | detection frame | MediaPipe returns | after | final label |
|---|---|---|---|---|
| recorder / debug tool | **mirrored** | mirrored/apparent hand | — | apparent |
| production | **un-mirrored** | true anatomical hand | `_mirror_handedness()` | apparent |

⚠ **Do not "simplify" either path to make the label the physical hand** without
re-deriving this test. The asymmetry is load-bearing.

### The drift guard was fixed, then PROVEN to still have power

`LiveSnapDebug.py` keeps its own copy of `_is_thumb_outward` by design (it must not
import production). Duplication is how the convention drifted once already, so the
guard compares the two ASTs.

Its first run was a **false positive**: it dumped identifiers, so production's
`landmarks` vs the debug copy's `pixel_landmarks` read as drift. Now the landmarks
parameter is canonicalised before comparison.

**A guard changed until it passes is worthless unless it still fails on real
drift**, so it was re-validated against mutants. It accepts a renamed parameter and
different docstring, and **rejects all five**: sign inverted (the §13.6.1 bug
itself), chirality correction dropped, chirality applied to `Right` instead,
cross-product operands swapped, and pinky→ring landmark substitution.

---

## 0.10 M5a `edgeOnMeasure` built (2026-08-03) — item 1.2 DONE, and the duplicate is gone

New shared module **`Local_pc/Movement_with_hand_detection/Resources/palm_geometry.py`**.

**Two deliverables in one change**, and the second was not in the original scope:

1. **The magnitude is recovered.** `_is_thumb_outward` computed the signed area `s`
   and used only `sign(s)`. `edge_on_measure` = `|s| / (‖v1‖·‖v2‖)` = `|sin θ|`
   between the palm vectors: 0 = edge-on (sign is a coin flip), 1 = knuckle row
   square to camera. One division, and it is the observability signal DR-2, M4 and
   M6 all need.
2. **The hand-synced duplicate is retired.** `HandsTriggeredActions.py` and
   `LiveSnapDebug.py` each carried their own copy of the sign formula. **That
   duplication is the direct cause of §13.6.1's production-only inversion.** Both
   now *delegate* to the shared module — the same fix already applied to the
   identity tracker (N6) on the owner's instruction. The module is pure stdlib with
   no cv2/pygame, so the debug tool can import it without triggering
   `CubeWindow()`'s window side effect.

### Verification

| check | result |
|---|---|
| `edge_on_measure` vs `AnalyzePerceptionSequences.edge_on()` | **max abs diff 5.55e-16 over 22,345 hand-frames / 24 sessions** |
| fixture test (item 1.1) after the refactor | **15/15, exit 0** — production sign unchanged, 788/788 |
| corpus below `EDGE_ON_THRESHOLD = 0.15` | 1.54%, matching §0.3's predicted shape |

The exact-match check is not ceremony: **every recorded threshold — above all
`EDGE_ON_THRESHOLD = 0.15`, settled by measurement in §0.3 — is expressed in the
analyser's normalisation.** A different scale in production would silently
invalidate it, with no test failing. `palm_geometry.verify_matches_analyser()`
keeps the two locked together and lives next to the code it constrains.

### The drift guard was re-pointed, not deleted

With both sides delegating, comparing their two one-line bodies is nearly vacuous.
The fixture test now *additionally* asserts that **neither file has reinlined the
maths** — that is the invariant that actually prevents drift now. Both the
body-equality check and the delegation check are kept.

### LIVE-CONFIRMED 2026-08-03

Run via `launch.bat`'s production path immediately after the refactor. **Operator
verdict: "everything working."** Checked: the thumb-outward rule in *both*
orientations on *both* hands (the one non-handedness-symmetric step, and the exact
thing §13.6.1 inverted), plus grab / translate / rotate / tracking-loss release.

Console: **18 DR-1 events, all benign** — 9 identity locks, 9 track-ends as hands
left frame — and **0 switches, 0 duplicate-label repairs, 0 glitch rejections,
0 errors or tracebacks.** The tracker sitting inert is the correct result for
normal use.

This was a **regression test by design**: item 1.2 is behaviour-preserving, so
"nothing changed" *is* the pass condition. It confirms the refactor — production
and the debug tool now sharing one chirality implementation — did not disturb the
shipped behaviour.

*Incidental: this run produced no duplicate-repair events at all, where the first
DR-1 live test (§0.6) produced three. Not enough to conclude anything about N9's
frequency, and N9 stays open.*

### Still open

- **Nothing consumes `edgeOnMeasure` yet.** DR-2 (item 2.2) is the consumer, and
  gating gesture rules on it is a real behaviour change that needs its own live
  test — unlike this one, "nothing changed" will NOT be the pass condition there.

---

## 0.11 DR-2 edge-on exclusion built (2026-08-03) — item 2.2, and a real rule-3 bug it closes

`PalmFacingTracker` in `Resources/palm_geometry.py`, per hand, **shared by
production and the debug tool** (same class, same policy — the tool cannot apply a
different edge-on rule than the game).

### The concrete defect this removes

Rule 3 disarms its snap exception on a single reading:

```python
if not thumb_outward:
    _thumb_outward_snap_allowed[handedness] = False
```

Near edge-on the raw sign chatters at up to **765 flips per 1000 frames** (§0.2) —
impossible as real rotation. So **one** spurious flip silently revokes the
exception. In play: release a cube showing the back of your hand (which arms the
exception), pass through edge-on, and your re-grab is refused with nothing on
screen explaining why. Freezing the sign through the band removes that path
entirely.

### Behaviour

- `edge_on_measure >= 0.15` → measure per frame, as before.
- `< 0.15` → **freeze** at the last confident value; `orientation_valid = False`.
- Exit → resume only after edge-on exceeds `0.15 × 1.6 = 0.24` for ~100 ms
  (`EXIT_DWELL_MS`, expressed in ms per finding N1 rather than the spec's
  30 fps-assuming "3 frames").
- Hand lost → `reset()`, so a stale sign is never carried across a reacquire.
  `_last_known_thumb_outward` deliberately survives (rule 3 needs an orientation to
  record at a tracking-loss release); only the frozen value is dropped.

### A/B under A10 — modest but real, with zero regressions

Replayed over all 24 sessions, measuring what the *gesture layer* sees:

| | result |
|---|---|
| ground-truth streams improved | **2 of 10** |
| ground-truth streams **worsened** | **0** |
| unchanged | 8 |
| chirality controls (`static_hold`, `non_crossing`) where DR-2 did anything | **0** |
| fixture test after wiring | 15/15, exit 0 |

Best case: `palm_back_s2_slow`/Right went from **4 off** ground truth to **exactly
matching**. `two_hand_near_miss` shed 14 flips (10→0, 4→0) in a take where no
crossing was ever scripted. **The effect is modest — 8 of 10 streams unchanged —
and that is stated rather than dressed up**; it passes A10 on "measured
improvement, no regression, inert on controls," not on magnitude.

> **Test-design error worth recording:** the first A/B run flagged
> `two_hand_near_miss` as a violated control. It is not a chirality control — it is
> the *identity* control from §0.4, and 9.7–12% of its frames sit below edge-on
> 0.15 because hands naturally turn edge-on as they pass each other. The true
> chirality controls are `static_hold` and `non_crossing`, and DR-2 was inert on
> both. The fault was in the test's control list, not in DR-2.

### ⚠ Partial vs. the spec, deliberately

M5e also specifies **carrying the sign through the band by integrating angular
velocity from M6** (the kinetic-depth effect), so a genuine crossing registers
instantly on exit. **M6 is item 2.3 and is not built.** Consequence: a real
crossing is still detected correctly, but only after the hand leaves the band and
the exit dwell elapses — **late by ~100 ms+, never wrong**. Revisit when 2.3 lands.

### Live test 2026-08-03 — passed, with one test-design failure of mine

Operator: **test 4 (regression) clean — "it does not seem anything regressed."**
Zero errors across two runs; 3 identity switches, 0 duplicate repairs.

**Test 3 was unobservable and that was my error.** I asked the operator to judge
whether "the game agrees you have turned over" — but production exposes **no
on-screen indicator** for the thumb-outward state; its only observable consequence
is whether a grab is permitted. The operator correctly reported they could not
tell. *Lesson: do not ask a human to verify a state the UI does not surface —
measure it instead.*

**Measured properly afterwards, over 144 freeze episodes in the corpus:**

| | freeze duration |
|---|---|
| median | **96 ms** |
| p90 | 163 ms |
| p99 | **1781 ms** |
| max | **3480 ms** |

The median matches the ~100 ms design intent and is imperceptible (the operator
felt nothing). **The tail was not anticipated**: `two_hand_near_miss` medians
1.6 s and peaks at 3.5 s, because the hand is held *sustained sideways-on* and the
cue is genuinely unreadable that whole time. Not a mechanism defect — but it means
rule 3 can act on a reading up to ~3.5 s stale in that pose. Recorded in
`GAME_RULES.md` rather than left implicit. A max-freeze cap was considered and
**not** added: the spec's answer is to suppress `palmFacing`-dependent gestures via
`orientationValid`, which is the correct fix once a consumer exists — inventing a
cap now would be exactly the heuristic pile-up the project avoids.

### A separate defect surfaced by the same test — see queue N12

The operator observed a **held cube jumping as the hand crosses the horizontal
(pitch) plane**, settling once the crossing completes. **Not DR-2** (which never
touches a held cube's position). It is the **third independent symptom** of
§14.1's fingertip-anchored translation, alongside T4's yaw/palm-sinking and Object
Jump Correction — and precisely what M8a predicted. Strengthens the case for the
M8a A/B (item 3.3). Full entry: `PART_ONE.md` §3.1 N12.

### Still open
- `orientation_valid` is computed and returned but **no rule consumes it yet** —
  it is the natural hook for `HandState.quality.orientationValid`.
- `_ASSUMED_FPS = 24.0` is hard-coded here as well as in `hand_identity.py`.
  **N7 covers both; do not fix one alone.**

---

## 0.12 M6b measured BEFORE adoption (2026-08-03) — the SVD frame is a REGRESSION; keep the shipped frame, take the observability metric

Item 2.3, stage 1. The spec warns that changing the frame construction can silently
invert yaw/roll (§13.7's recorded lesson), so M6b's SVD frame was **measured against
the shipped Gram-Schmidt frame on identical recorded input before any production
change.** That decision paid for itself immediately.

### Result: do NOT adopt M6b's frame

| | shipped Gram-Schmidt | M6b SVD |
|---|---|---|
| left-handed frames (must be 0) | 0 | 0 |
| **>30° per-frame orientation jumps** | **1533** | **3233** |

**2.1× worse overall, and worse specifically where the shipped frame is clean:**

| control sequence | shipped | SVD |
|---|---|---|
| `non_crossing` | 1 | **175** |
| `depth_sweep` | 0 | **64** |
| `two_hand_near_miss` | 0 | **57** |
| `known_right_palm` | 0 | **15** |
| `static_hold` | 0 | 0 |

**Diagnosis (likely, not proven):** singular vectors are defined only up to sign,
and when `S[1] ≈ S[2]` the 2nd and 3rd axes can **swap between consecutive
frames**. The implementation enforced right-handedness but not *temporal
continuity*. A continuity-enforcing variant may well fix it — but that is a **new
design, not M6b as specified**, and would have to be measured the same way.

**Under A10 this is a null/negative result and is recorded rather than retried
blindly.** Chirality was never violated (0 left-handed frames in either
construction), so this is a *stability* failure, not the inversion the spec warned
about.

### What IS validated: `observability` is a far better conditioning signal

| signal | range across the whole corpus |
|---|---|
| **`observability` = 1 − S₃/S₂ (M6b)** | **0.046 → 0.908** |
| `conditioning_norm` (shipped) | 0.058 → 0.092 |

`observability` collapses to **0.05–0.15 at exactly the pitch crossings**
(`pitch_sweep_slow` 0.046, `palm_back_s2_slow` 0.071–0.096) and sits at
**0.75–0.91 on every control** (`static_hold` 0.818, `non_crossing` 0.749,
`known_*` 0.834–0.890). `conditioning_norm` spans a narrow band across
*everything* and barely discriminates. Per-session correlation between the two is
only 0.27–0.81, with several near zero or negative — **they are not the same
signal.**

> ### ⚠ CORRECTION (same day): "adopt observability as the conditioning signal" was WRONG
>
> This section originally concluded that `observability` should **replace**
> `conditioning_norm`, inferring it from the wider dynamic range. **That inference
> was not tested when it was written, and when tested it failed.**
>
> A/B driving the *shipped* filter with each signal, identical input, same metric
> the 2026-08-02 filter audit used (§13.7.1):
>
> | config | >30° jumps | >60° jumps |
> |---|---|---|
> | no filter at all (α ≡ 1) | 1533 | 730 |
> | **shipped: `conditioning_norm` 0.015/0.06** | **1386** | **611** |
> | best `observability` (0.40/0.90, swept) | 1473 | 663 |
>
> Observability beats no-filter but **loses to what is already shipped**, at every
> threshold pair swept (0.10/0.40 through 0.40/0.90).
>
> **Why, and it is not mysterious:** `conditioning_norm` measures the conditioning
> of *the frame actually in use* — the orthogonalised `wrist→middle_MCP` length
> against the knuckle axis. `observability` measures the conditioning of the
> **palm-plane fit**, i.e. of the construction rejected above. The useful
> conditioning signal is the one matched to the estimator you are actually running.
>
> **Lesson: a wider dynamic range is not evidence of a better signal.** Measure the
> thing you care about, not a proxy for it.

**Revised conclusion:**

- **Keep** the shipped Gram-Schmidt frame for orientation. *(unchanged)*
- **Keep** `conditioning_norm` driving the current reliability blend. **Do not
  swap it for `observability`.**
- `palm_observability()` is built, numpy-free and verified to 1.6e-11 against
  numpy — **retained for M6c**, where it is used to shape a *per-axis* covariance
  rather than as a scalar blend weight. That is a different use, and this null
  result does not condemn it there.
- **A6's "one metric, not two" is therefore NOT yet settled.** It becomes a real
  decision only when M6c ships and something actually consumes observability. Until
  then only one metric is in the estimation path, so the constraint is not violated.

*Implementation note for whoever builds M6c: computing singular values needs numpy,
which `HandsTriggeredActions.py` does not currently import (it is pure `math`).
Decide deliberately whether to add the dependency or compute the 3×3 eigenvalues in
closed form.*

### A tooling error caught in the same pass

The first run of this comparison reported **575 of 576 frames in `static_hold` as
>30° jumps** — impossible for a hand held still. Cause: iterating `rec["hands"]`
with a single `prev`, so consecutive entries alternated Left→Right→Left and the
angle *between the two hands* was being counted as a per-frame jump. **This is the
same bug class as the §0.8 per-hand-stream error, caught the same way — by a number
that could not be true.** Fixed to track the previous frame per hand; corrected
figures are the ones above.

---

## 0.13 M6c anisotropic covariance — NOT DEMONSTRATED (2026-08-03). Nothing shipped.

Item 2.3, stage 3. Three parameterisations tried, replayed over all 24 sessions.
**None beat the shipped isotropic filter. `HandOrientationFilter` stays.**

### What was built

An **error-state** update rather than a full UKF: `q_err = q_pred⁻¹ ⊗ q_meas` →
log map → 3-vector in the body frame → per-axis gain `k_i = P/(P + R_i)` → exp map
→ compose. That is 6c's mechanism (diagonal `R` in the body frame), numpy-free so
it ports to the web target. Sigma points buy process-nonlinearity handling that a
small-angle error state largely removes.

### Why the first two attempts looked like wins and were not

**Attempt 1 (single sigma for all axes) scored spectacularly** — `>60°` jumps
589 → **0**, max 180° → 53°. It was over-damping wearing an anisotropic costume:
one parameter damped every axis uniformly.

**The metric that caught it** — and which must be used in any future attempt:

> `tracking_error = angle(fused, raw_measurement)` on frames where
> `observability > 0.6`, i.e. where the measurement is trustworthy and the filter
> has **no excuse to disagree**.

| | well-cond | fast motion |
|---|---|---|
| shipped | **1.40°** | **5.04°** |
| attempt 1, σ=4 | **37.32°** | 59.28° |

**Jump counts reward a filter that ignores the hand.** A filter with gain ≈ 0 has
zero jumps and is useless. Never judge an orientation filter on jump counts alone.

**Attempt 2** conflated the two parameters again (one σ for both the well-observed
and the blown axes), forcing a trade the spec never intended.

### Attempt 3 — the spec's actual two-parameter form, and the honest result

`R = diag(σ_long², σ_base²/obs, σ_base²/obs)`, swept σ_long ∈ {0.1, 0.2, 0.3} ×
σ_base ∈ {0.5, 1, 2, 4}:

| σ_long | σ_base | >60 | p99 | max | trk_well | trk_fast |
|---|---|---|---|---|---|---|
| *(shipped)* | | **589** | 120.2 | 180.0 | **1.40°** | **5.04°** |
| 0.30 | 1.00 | 649 | 92.5 | 177.2 | 5.79° | 11.81° |
| 0.30 | 2.00 | 562 | 85.7 | 173.7 | 13.92° | 25.12° |
| 0.30 | 4.00 | 472 | 82.4 | 166.6 | 29.05° | 45.12° |

**Every config that improves the tail costs 3–10× worse tracking.** No config wins
both. Under A10 that is a null result: **not shipped, not tuned into looking good.**

### ⚠ This does NOT disprove M6c — it disproves *this approximation of it*

The implementation holds **P fixed at 1.0**; there is no covariance propagation. A
real UKF grows `P` while coasting on an unobservable axis, which *raises* the gain
when observability returns and lets it re-converge fast. That is materially
different behaviour and is exactly where 6c's benefit is supposed to live.

**A fair next attempt must propagate the covariance** — i.e. build the actual
filter, not the fixed-gain approximation. Do not re-run the fixed-P version and
expect a different answer.

### 0.13.1 — The propagated-covariance filter WAS built, and it also loses (2026-08-03)

§0.13 said the fixed-P approximation was not a fair test and that a real filter must
propagate covariance. **That filter was then built** — `Resources/orientation_filter.py`,
a full error-state multiplicative Kalman filter on SO(3), numpy-free:

```
predict   q_pred = q ⊗ exp(ω);  ω *= OMEGA_DECAY;  P += Q      <- uncertainty GROWS while coasting
update    dz = log(q_pred⁻¹ ⊗ q_meas)                          <- innovation, body frame
          R  = diag(σ_long², σ_base²/obs, σ_base²/obs)         <- 6c anisotropy
          K_i = P_i/(P_i+R_i);  q = q_pred ⊗ exp(K·dz)
          P_i = (1-K_i)·P_i                                    <- shrinks ONLY when trusted
```

This is the growing-while-lost / snapping-back-when-found mechanism §0.13 identified
as missing. **It works exactly as intended and still loses.**

**54 configurations swept** (σ_long ∈ {0.02…0.3} × σ_base ∈ {0.6, 1, 2} × Q ∈ {0.005…0.3}):

| config | >60 | p99 | max | trk_well | trk_fast |
|---|---|---|---|---|---|
| **shipped isotropic** | 589 | 120.2 | 180.0 | **1.40°** | **5.04°** |
| UKF σ_l=0.3 σ_b=2.0 Q=0.005 | **1** | **38.0** | **62.7** | 23.65° | 42.40° |
| UKF σ_l=0.02 σ_b=0.6 Q=0.3 | 596 | 102.7 | 175.9 | 3.56° | 7.55° |

**The trade is absolute.** Push the tail down and tracking collapses; tighten
tracking and the tail benefit vanishes entirely. **No configuration wins both.**

### ⭐ Why the shipped heuristic is so hard to beat — the actual insight

The shipped filter is **not really a continuous filter — it is a switch.**
`alpha_iso` saturates at 1 when well-conditioned (so `fused == raw`, a pure
passthrough, zero lag) and drops to 0 when degenerate (hard damp, full prediction
trust). **That bimodality is matched to the failure mode**: degeneracy here is
*rare and severe*, not gradual. A Kalman filter necessarily applies **graded**
damping on every frame, so it pays lag continuously to buy protection that is only
needed occasionally.

**This reframes A6's "delete `HandOrientationFilter`" obligation.** The filter is
not a crude stand-in for a principled estimator — its crudeness *is* the fit to the
problem. Any replacement must reproduce that near-bimodal response, not smooth it
away. **Four independent attempts have now failed to beat it** (SVD frame,
observability-as-blend-weight, fixed-P anisotropic, propagated-covariance
anisotropic).

**Do not attempt a fifth without a new idea.** Candidates not yet tried, recorded so
the next attempt is not a repeat: (a) gate the Kalman update so it is a passthrough
above an observability threshold and only engages below it — i.e. keep the
bimodality and use the covariance only inside the bad band; (b) full 3×3 `P` with
the frame-rotation cross-term this diagonal version omits; (c) accept the tail and
address it at the *source* (M2/M4 landmark quality) rather than by filtering.

### 0.13.2 — ROOT CAUSE FOUND: the tail is NOT an observability problem (2026-08-03)

Attempt 5 gated the KF to passthrough above an observability threshold, keeping the
shipped filter's zero-lag bimodality and using the covariance only inside the bad
band. **It tracked perfectly (0.000°) and left the tail untouched** (>60: 698–742 vs
baseline 589; max unchanged at 180°).

That result prompted the diagnostic that should have come first — **where do the
large RAW jumps actually occur?**

| observability | % of frames | >60° jumps | >60 per 1k frames |
|---|---|---|---|
| [0.00, 0.15) | 0.1% | 2 | **166.7** |
| [0.15, 0.30) | 0.3% | 22 | **318.8** |
| [0.30, 0.45) | 0.6% | 37 | **278.2** |
| [0.45, 0.60) | 1.4% | 72 | **235.3** |
| [0.60, 0.75) | 4.2% | 155 | 166.3 |
| **[0.75, 0.90)** | **82.6%** | **349** | **18.9** |
| [0.90, 1.01) | 10.9% | 93 | 38.3 |

**Both readings are true and the second is the one that matters:**

1. **Per frame, low observability IS ~17× more dangerous** (319/1k vs 19/1k). The
   premise is not nonsense.
2. **But 82% of all large jumps occur at observability ≥ 0.60** — because that is
   97.7% of frames. **Only 18% of the problem lives in the band M6c can reach.**

### This single fact explains all five failures

- **Attempts 1–4** keyed damping to observability. To catch the 82% they had to damp
  *everywhere*, which is why every tail improvement cost 3–17× worse tracking.
- **Attempt 5** acted only inside the band. It therefore addressed only 18% of the
  jumps and produced no tail benefit at all — while tracking perfectly.

Two failure modes, one cause, seen from opposite sides. **M6c's mechanism is sound
and simply does not apply to the dominant failure here.**

### Consequence for the plan — redirect, do not iterate

A sixth attempt at anisotropy is **not** warranted. The 82% of jumps occurring in
well-conditioned frames are a **landmark-quality** problem, not a pose-estimation
one: at 24 fps a >60° change in 41 ms implies >1460°/s, at or beyond the human wrist
limit, so most of these are bad landmarks rather than real motion.

That points at option (c) from §0.13.1, now with evidence behind it:

- **1.4 (M2 bone-length calibration)** and **1.6 (M4 precision weighting + χ²
  gating)** attack the tail at its source. M4's χ² innovation gate in particular is
  designed to reject exactly this: a physically implausible single-frame excursion.
- **T1/T2 were queued behind 2.3 on the assumption that better pose filtering would
  fix them. That assumption is now measured false for 82% of the failures.** They
  should be re-tested after 1.4/1.6, not after 2.3.

**2.3 is therefore DEPRIORITISED, not merely paused** — and `orientation_filter.py`
stays parked and unwired.

### 0.13.3 — Salvage assessment: what the 5 failed attempts left behind (2026-08-03)

Owner question: *do the built artifacts have value somewhere we did not think of?*
Probed rather than assumed.

**Tested and REJECTED — repurposing the machinery as M4's χ² gate.** A χ² innovation
gate needs a prediction, an innovation and an innovation covariance; the parked
filter has all three, and unlike graded anisotropy a gate is **bimodal** (the shape
that keeps winning) and targets implausible jumps *wherever* they occur — including
the 82% in well-observed frames. It looked like the right salvage. It is not:

| | >60 | max | trk_well | rejected |
|---|---|---|---|---|
| shipped | **589** | 180° | **1.40°** | — |
| χ² gate p=0.01 | **2167** | 180° | 17.16° | 14.6% |
| physical gate 25° | **14319** | 180° | 102.96° | 59.9% |

**3.7× and 24× worse.** Rejecting a measurement means coasting on the model; the
model diverges; the eventual re-acceptance produces a *larger* jump than the one
suppressed. **The gate manufactures the failure it targets.**

### ⭐ The finding underneath ALL of it: the motion model is weak

The physical gate rejects **60% of frames at a 25° threshold**, i.e. a one-frame
constant-angular-velocity prediction routinely disagrees with the measurement by
more than the typical motion (mean frame-to-frame change: 9.9°).

**This unifies every failure in §0.13–§0.13.2.** The shipped filter wins because
`alpha` saturates at 1 and it therefore *ignores the prediction almost always*.
Graded blending, coasting and gating all lean on the model to different degrees, and
all inherit its weakness.

### Verdict

**No value:** the anisotropic update; the χ² / physical gate for orientation.
Both measured, both worse, both recorded so they are not retried.

**Real value, two items:**

1. **`palm_observability()` → `HandState.quality.orientationValid` (M6e).** It is a
   *correct* observability signal — collapses at crossings, 0.046–0.908, matched to
   numpy at 1.6e-11, numpy-free and portable. It simply is not what drives the tail.
   Its home is the §2 quality contract that gestures branch on, not the filter.
2. **⚠ A WARNING FOR ITEM 3.1 (M7), worth more than the code.** M7's forward
   prediction extrapolates with *this same* constant-angular-velocity model, up to
   ~80 ms ≈ 2 frames. **The model is measurably unreliable at ONE frame.**
   **Before building M7, measure the model's prediction error and confirm it is fit
   to extrapolate with.** M7's premise — "net perceived latency can go to zero" —
   assumes a predictor this data does not yet support.

*Caveat, stated because it bounds the claim: M4's χ² gate was designed for the
Object Jump case — a whole-hand POSITION teleport, where the excursion is
unambiguous and position is far easier to coast. **This result condemns the gate for
ORIENTATION only**; item 1.6 should still evaluate it for position.*

### What this run did establish

The shipped hand-rolled filter was **re-validated a third time** on the full
24-session corpus (1533 → 1374 `>30°`, 730 → 589 `>60°` versus no filter). The
2026-08-02 audit kept it on a smaller sample; it has now survived a deliberate
attempt to replace it.

**A6's "delete `HandOrientationFilter`" obligation is therefore NOT met and the
filter stays.** The bar is a replacement that is measurably better on *both*
families of metric — which is a higher bar than "more principled".

---

## 0.14 M2 built and MEASURED (2026-08-03) — the fixed-bone-length prior does not exist in this sensor

Queue item 1.4. `Resources/hand_model.py` built (numpy-free, portable): 21-bone
topology, low-motion-gated collection, running **median** (never mean — occlusion
outliers are severe and one-sided), IQR freeze gate, per-user persistence, plus
`pose_normalised_residual()` for N2.

**Then measured against the spec's own acceptance criterion, and it fails.**

### The measurement

Pooled **still frames only** (motion < 3% of hand size) across all 24 sessions —
i.e. calibrated exactly as §2f prescribes, with pose diversity:

| | IQR / median, per bone |
|---|---|
| **freeze gate requires** | **< 2%** |
| Left, palm bones | median **10.49%**, worst 11.93% — **0/5 inside 2%** |
| Left, fingertip bones | median 11.37%, worst 15.46% — 0/5 |
| Right, palm bones | median **6.28%**, worst 12.59% — **0/5 inside 2%** |
| Right, fingertip bones | median 11.36%, worst **22.21%** — 0/5 |

Independent half-vs-half check (calibrate on half the sessions, verify on the
other): worst bone disagreement **4.02%** (Left) and **24.33%** (Right), against a
< 2% target.

**Not a single bone, in any group, converges.** The best subset is Right-hand palm
bones at ~6%, still 3× outside the gate.

### This does NOT contradict §0.2 — it is a different quantity

§0.2 measured the palm **rigidity residual** at 2.76 mm (inside target): a
rigid-body fit of the palm *within* a pose. This measures bone length *across*
poses. **Within a pose the palm is rigid; across poses the measured lengths shift
by 6–12%.** Both are true, and the second is what a persistent body schema needs.

### What it means

**MediaPipe's `worldLandmarks` do not encode a pose-consistent hand skeleton.**
Depth error is pose-dependent, so bone lengths derived from them inherit that
dependence. M2's premise — that ~20 fixed lengths are "the strongest prior
available, free to obtain" — **does not hold for this sensor at the stated
precision.**

Consequences, stated plainly because several queue items rest on this:

- **1.4's acceptance criterion is unreachable as written.** Do not tune the gate to
  make it pass; 2% is not available.
- **N2 is confirmed and my proposed fix FAILED.** `pose_normalised_residual()`
  (dividing out the rigid palm's common-mode scale) moved the moving/still residual
  ratio only from **2.05× to 1.99×**. The pose effect is not common-mode, so it does
  not divide out. **N2 stays open and needs a different idea.**
- **1.6 (M4) loses its intended per-landmark error signal.** M4 was to consume the
  bone residual; that residual is dominated by pose, not by landmark quality.
- **4.1 (M9 metric depth) and T4 are at risk** — both depend on 1.4 supplying a
  reliable scale reference, which it cannot at better than ~6–10%.

### Options, none yet chosen

1. **Relax the target and use bone lengths as a SOFT prior (~6–10%).** Still useful
   for gross outlier rejection (a bone 3× too long is certainly wrong), useless for
   precision depth.
2. **Calibrate per-pose rather than globally.** Within a pose, bone CV is ~1%
   (§0.3), so short-horizon consistency is achievable — but it does not persist,
   which is most of what a body schema was for.
3. **Question the input.** Bone lengths from `worldLandmarks` inherit its depth
   error. Screen landmarks are far better conditioned (§0.2); a screen-based
   foreshortening formulation may be the better route to M9 than a metric skeleton.

*Implementation note: `_try_freeze` currently fires as soon as all bones pass with
`MIN_SAMPLES`, which can freeze prematurely on an early tight window (observed:
"0/21 stable" reported alongside "frozen=YES"). Fix before any use — though given
the above, nothing should be relying on the frozen model yet.*

---

## 0. Framing: what MediaPipe is, and what it is not

MediaPipe Hands is a **stateless, per-frame, monocular shape estimator**. It answers "what configuration of a hand best explains this single image crop?"

It does not answer:

- *How is the hand moving?* (you are differentiating a noisy signal to get this)
- *Which way is the palm facing?* (bas-relief ambiguity — sign of depth is under-determined from one monocular view)
- *How far away is the hand?* (there is no metric scale in the screen landmarks)
- *How confident should I be right now?* (there is no per-landmark precision output)

Every one of the open TODO items is a direct consequence of one of those four missing answers. The strategy in this document is not "tune MediaPipe better." It is: **treat MediaPipe as a noisy sensor and build the estimator that the visual system builds around it.**

The organising principle from biology:

| Brain mechanism | What it buys | Module |
|---|---|---|
| Body schema (internal limb model) | Metric scale, rigidity, depth-sign disambiguation | M2 |
| Postural synergies (Santello et al.) | 63 noisy DOF → ~7 real DOF | M3 |
| Precision-weighted prediction error | Ignore bad frames instead of averaging them in | M4 |
| Evidence accumulation to a bound (LIP/drift-diffusion) | Stable commitment on ambiguous sign | M5 |
| Vestibular/proprioceptive fill-in through singularities | Survive the pitch-plane crossing | M6 |
| Magno/parvo split + forward models | Low-lag motion channel + stable form channel | M7 |
| Anticipatory grip aperture (peak aperture at ~75% of reach) | Fire the grab *on time*, not late | M8 |
| Size-distance invariance from known object size | Real depth without a depth camera | M9 |
| Perceptual hysteresis (bistable percepts) | No dithering at snap/unsnap | M10 |

---

## 1. Target architecture

```
L0  Capture          frame + monotonic timestamp + blur metric
L1  MediaPipe        landmarks[21], worldLandmarks[21], handedness, scores
L2  Observability    per-landmark precision, palm conditioning, edge-on measure   [M1, M4]
L3  Body schema      calibrated skeleton, IK, synergy projection                  [M2, M3]
L4  Hypothesis bank  chirality lock + evidence accumulator                        [M5]
L5  Pose filter      quaternion UKF, anisotropic covariance, metric depth         [M6, M9]
L6  Dorsal channel   velocity, angular velocity, trajectory features, prediction  [M7]
══════════════════════ HandState v2 boundary ══════════════════════
L7  Gesture logic    pure, engine-agnostic: HandState -> Intents                  [M8, M10]
L8  Engine binding   pygame today; Three.js in the web port
```

**Current mapping (Python reference implementation):**

| Layer | Today | After this spec |
|---|---|---|
| L0–L1 | `VisionPipeline.py`, `hands_visualizer.py` | unchanged in role; extended to emit timing + quality |
| L2–L6 | *does not exist* — scattered inside `HandsTriggeredActions.py` | new perception modules, server-side |
| boundary | `hands` + `hands_world` socket packets | **`HandState` v2** — the versioned wire contract |
| L7 | `HandsTriggeredActions.py` (mixed with perception) | `HandsTriggeredActions.py`, perception removed |
| L8 | `CubeWindow.py` (pygame) | unchanged |

**Boundary discipline:** L0–L6 must not import the engine binding and must know nothing about
objects, snapping, or scene units. L7 must not import from L0–L6 except the `HandState` type.
This is testable — see §7.3.

---

## 2. `HandState` v2 — the contract

Freeze this before starting implementation; the modules below are all *producers* of fields in this struct, so it is the integration point.

**Integration note:** expressed below in JS-object notation for readability, but this is a
**language-neutral wire contract**, versioned by `schema`. The Python reference implementation
serialises it over the existing socket protocol, superseding the current `hands` /
`hands_world` packet pair. Keep it serialisable and free of engine types — a future
web/mobile rebuild reimplements against this, per the project's cross-platform planning.

```js
/**
 * All positions in metres, hand-centric unless stated.
 * All timestamps in ms, monotonic, from the same clock as capture.
 */
HandState = {
  schema: 2,

  // --- timing ---
  tCapture,              // when the photons were captured (not when inference finished)
  tPredicted,            // timestamp this state is valid FOR (may be > now; see M7)
  latencyBudgetMs,       // measured end-to-end, used by consumers that need it

  // --- existence ---
  present,               // bool
  handedness,            // 'left' | 'right'  -- track-level, locked (DR-1)
  handednessConfidence,  // 0..1, from the accumulator (M5), NOT raw MediaPipe

  // --- rigid pose of the palm ---
  palm: {
    position,            // vec3, metric, camera frame, origin = palm centroid
    orientation,         // quaternion, camera frame  (NEVER expose Euler here)
    linearVelocity,      // vec3 m/s
    angularVelocity,     // vec3 rad/s, body frame
    covTrace,            // scalar summary of positional uncertainty
    orientationSigma,    // vec3, per-axis angular 1-sigma (rad) -- anisotropic!
  },

  // --- articulation ---
  joints,                // 20 joint angles, radians, anatomical convention
  synergyCoeffs,         // ~7 latent coefficients (M3)
  landmarksCanonical,    // 21 x vec3, reconstructed from skeleton, hand frame
  landmarksScreen,       // 21 x vec2, for debug overlay only

  // --- derived scalars the gesture layer actually wants ---
  aperture,              // thumb-index metric distance, m
  apertureRate,          // d(aperture)/dt, m/s   <-- required by M8
  palmFacing,            // -1..1, signed cos(theta) between palm normal and view axis
  palmFacingConfidence,  // 0..1, from evidence accumulator
  edgeOnMeasure,         // 0..1, normalised |s| from M5a -- drives DR-2
  depth,                 // metric distance camera -> palm centroid (M9)
  depthRate,

  // --- quality gates: the gesture layer MUST branch on these ---
  quality: {
    overall,             // 0..1
    orientationValid,    // bool  -- false during pitch-plane crossing
                         // ✅ PRODUCER ALREADY BUILT: palm_geometry.palm_observability()
                         //    (numpy-free, verified to 1.6e-11 vs numpy over 22,345
                         //    frames; 0.75-0.91 on controls, collapses to 0.05-0.15 at
                         //    crossings). See M6e. Threshold not yet chosen.
                         //    NOTE: this flags "is the palm normal well determined",
                         //    NOT "will orientation jump" -- 82% of large jumps occur
                         //    at observability >= 0.60 (§0.13.2). Do not use it as a
                         //    jump predictor; that mistake cost five attempts.
    depthValid,          // bool
    occlusionLevel,      // 0..1
    motionBlur,          // 0..1
    framesSinceMeasurement, // >0 means we are coasting on the model
  },
}
```

**Rule:** the gesture layer must never read `quality` and silently proceed. Every gesture
definition declares its minimum quality requirements, and the dispatcher suppresses gestures
whose requirements are unmet. This is what stops the pitch-crossing from producing a spurious
unsnap later.

**Migration note.** `HandState` v2 replaces the current wire protocol, which sends only raw
pixel landmarks plus raw world landmarks. Two existing consumers must be migrated in the same
change: `_is_thumb_outward` (becomes `palmFacing` + `edgeOnMeasure`, produced server-side) and
the rotation quaternion path (becomes `palm.orientation`). Do not run both protocols in
parallel — that reintroduces the debug/production divergence that caused the §13.6.1 bug.

---

## 3. Root-cause analysis — see the pipeline documentation

**Deliberately not restated here.** The failure analysis for the open TODOs — back-of-hand
tracking, pitch-axis rotation across the pitch plane, object positioning at the grab moment,
and Object Jump Correction — has already been carried out and captured in the project pipeline
`.md` files. **Refer to those documents as the authoritative record** of observed failure
modes, root causes, and lessons learned.

This spec does not re-derive that analysis and must not be read as amending it. Where any
module below states a rationale that conflicts with the recorded pipeline analysis, **the
pipeline `.md` files take precedence.** Raise the conflict and amend this spec; do not silently
follow this document over the recorded lessons learned. §0.1 is the log of amendments made
under that rule on integration.

What this spec contributes is the *forward* half: the estimator design intended to address
those recorded failures. The merged module → TODO mapping is in `PART_ONE.md` §3.1.

---

## 4. Modules

Each module: brain analogue → design → math/pseudocode → parameters → acceptance test.

---

### M0 — Instrumentation and ground-truth-free metrics

**Build this first. Nothing else is verifiable without it.**

You have no motion-capture ground truth. You don't need it — the hand's own rigidity supplies self-supervised error metrics:

| Metric | Definition | Why it works | Target |
|---|---|---|---|
| **Bone-length CV** | per-bone coefficient of variation of `‖p_child − p_parent‖` over a window, from `worldLandmarks` | bones are rigid; any variance is estimator error, and it is dominated by depth error | < 3% |
| **Palm rigidity residual** | RMS residual of `{0,5,9,13,17}` against a rigidly-fitted calibrated palm | isolates palm-frame error from finger error | < 3 mm |
| **Resting jitter** | std-dev of each landmark in the *hand frame* with the hand held still | separates true jitter from intentional motion | < 1.5 mm |
| **Palm-normal jitter** | std-dev of the angle of the palm normal, hand still | direct proxy for rotation stability | < 1.5° |
| **Chirality flip rate** | sign inversions of `palmFacing` per minute during scripted non-crossing motion | should be exactly zero | 0 |
| **Crossing survival** | fraction of scripted ±120° pitch sweeps completed without a spurious flip or unlock | the pitch-crossing TODO metric | > 98% |
| **Reacquisition time** | ms from hand re-entering frame to `quality.overall > 0.8` | occlusion robustness | < 200 ms |
| **Object jump rate** *(added on integration)* | position discontinuities > 100 px per minute of held-object time | the Object Jump Correction metric (§14.1.4) | 0 |

**Implementation:** a `PerceptionProbe` that writes a rolling JSONL of
`{t, metrics, moduleVersions, configHash}`, plus a headless replay harness (§7).
**Record raw MediaPipe output to disk, timestamped, at
`E:\Python\Recordings for vision_pipeline\Recordings_perception_layer`, so every subsequent
module can be A/B tested offline on identical input. This single decision will save more time
than any other item in this document.**

**Integration note — build on what exists, don't restart.** The project already has this
discipline and two working tools: `RecordTranslationPivotDebug.py` (records real landmark
streams by driving the actual snap/translate logic, so recorded state is real ground truth,
not simulated) and `AnalyzeTranslationPivot.py` (offline replay + metric diffs). **M0
generalises these**; it does not replace them. Two concrete extensions are needed:

1. Record `tCapture` per frame (currently the recorders synthesise a 33 ms cadence).
2. Optional frame capture, off by default — M4's motion-blur cue is the only consumer.

**Immediate quick win:** the bone-length CV, resting-jitter and palm-normal-jitter baselines can
be computed **today, on already-recorded sessions** in
`E:\Python\Recordings for vision_pipeline\Position_during_rotation`. No new capture is required
to establish the first baseline numbers.

Suggested layout under the capture root:

```
Recordings_perception_layer\
  sessions\
    2026-08-02_143012_<label>\
      raw_landmarks.jsonl      # per frame: landmarks[21], worldLandmarks[21],
                               #            handedness, scores, tCapture
      frames\                  # optional; needed only for blur-metric work (M4)
      meta.json                # camera model, resolution, fps, MediaPipe version,
                               #            config hash, user profile id
  profiles\
    <profileId>.json           # persisted M2 skeleton (see 2f)
  metrics\
    <configHash>.jsonl         # PerceptionProbe output, for A/B diff tables
```

Keep `frames\` optional and off by default — it dominates disk use, and most module A/B
testing needs only the landmark stream.

**Acceptance:** you can replay a recorded session through two pipeline configs and get a numeric diff table.

---

### M1 — Cue separation and fusion (screen vs. world landmarks)

**Brain analogue:** maximum-likelihood cue combination (Ernst & Banks) — the brain weights each cue by its reliability rather than picking one.

**Design.** MediaPipe gives you *two* outputs with complementary error structure, and most pipelines use only the first:

- `landmarks` — normalised image coordinates. **Excellent x,y. Effectively no usable z.**
- `worldLandmarks` — approximately metric 3D, origin at the hand's geometric centre. **Much better relative 3D structure and far better for orientation. Carries no screen position.**

Fuse rather than choose:

```
screen position of hand    <- landmarks (x,y)  +  M9 depth
orientation / articulation <- worldLandmarks, weighted by M4 precision
metric scale               <- M2 calibration cross-checked against both
```

Weight each cue by inverse variance, with variances estimated online in M4 rather than hard-coded.

**Integration note.** The project already uses both streams and already splits them this way by
instinct — translation from pixel landmarks, rotation from `worldLandmarks`
(`GESTURE_PIPELINE_SPEC.md` §13.7). M1 formalises the split and adds reliability weighting. Note
also the recorded mirroring hazard: the two streams are mirrored at *different points* in the
pipeline (`remap_keypoints` vs. `remap_world_keypoints`), which has already produced one live
bug (§13.6.1). Any fusion code must handle both in one place with one convention.

**Acceptance:** bone-length CV computed from the fused estimate is lower than from either cue alone, on the same recorded session.

---

### M2 — Body schema: online skeleton calibration

**Brain analogue:** the body schema — a persistent internal model of limb dimensions, continuously recalibrated (cf. prism adaptation, the rubber-hand effect).

**Why it matters here:** MediaPipe emits 21 *free* points, 63 DOF. A real hand has ~26 DOF with **20 fixed bone lengths**. Those 20 constants are the strongest prior available to you, they are free to obtain, and they unlock: depth-sign disambiguation, metric depth (M9), foreshortening-based pose, and a per-frame quality signal.

**Design.**

1. Define the 20 bones over the standard MediaPipe topology.
2. During a short calibration (or continuously, gated on `quality.overall > 0.85`), collect `‖p_child − p_parent‖` from `worldLandmarks`.
3. Robust estimate per bone: running **median** (not mean — outliers during occlusion are severe and one-sided).
4. Converge when the interquartile range of each bone falls below 2%; then freeze into `HandModel`, persist per-user across sessions.
5. Thereafter, per-frame **bone-length residual is your primary per-landmark error signal** feeding M4.

```python
# per frame, per bone
r_b = (measured_length_b - calibrated_length_b) / calibrated_length_b
# large |r_b| on a distal bone => that fingertip's depth is wrong => downweight it
```

**Foreshortening is a signal, not an error.** A bone whose projected length is 60% of its calibrated length is tilted ~53° out of the image plane. This gives you `|z|` per bone directly from the well-conditioned screen landmarks. Only the *sign* remains, which M5 handles.

#### 2f. Per-user anatomy: what is calibrated, when, and by whom

**Yes, the skeleton is person-specific — but not in the way that requires a calibration screen.**

Separate two things that behave very differently:

| Quantity | Inter-person variation | Observable monocularly? |
|---|---|---|
| **Bone *proportions*** (ratios between the 20 bones) | Modest — hands are geometrically similar across adults | Yes, well |
| **Absolute hand *size*** | Substantial — adult hand length spans roughly 165–200 mm | **No** — not without a known focal length *and* a known reference size |

The second row is the important one. Absolute metric scale is **fundamentally unobservable**
from a single uncalibrated camera looking at a hand of unknown size: a large hand far away
and a small hand close by are the same image. **You do not need it.** M9's depth control uses
the ratio form `d/d₀`, in which the unknown scale factor cancels exactly. So the calibration
target is *proportions plus a per-session scale constant that is arbitrary but internally
consistent* — a much easier problem.

**Recommended approach — implicit online calibration, no calibration step:**

1. **Ship population-average proportions as the prior**, baked in at build time. This is the
   starting point, not the answer.
2. **Adapt online during normal play** with a fast-then-slow schedule: high adaptation rate
   for the first ~200 tracked frames, then decay to the slow drift rate (α ≈ 0.001). Converges
   within a few seconds of ordinary hand motion. The user never sees a calibration screen.
3. **Persist the converged profile** (a JSON file under the capture root's `profiles/`, keyed
   to a profile id) so returning users start converged. One profile per tracked hand.
4. **Freeze** when per-bone IQR < 2%; thereafter allow only slow drift, gated on high quality.

**Why fixed build-time geometry is not sufficient:** the whole value of M2 is the per-frame
bone-length *residual* as an error signal (M4). If the model is 10% off for this user, every
frame reports a 10% residual and the quality signal is swamped by a constant bias — you lose
the outlier detection, which is the point. A per-user model is needed for the *error signal*
even more than for the geometry.

**One non-obvious pitfall.** Bone lengths measured from `worldLandmarks` carry the same depth
error you are trying to characterise. The median over many frames works only because that
error is roughly zero-mean *across varied hand orientations*. If the user holds the hand in
one orientation throughout calibration, the bias will not average out and you will converge to
a wrong skeleton with high confidence.

*Mitigation:* **weight calibration samples by pose diversity.** Accept a sample only if the
palm orientation differs by more than ~20° from recently-accepted samples. Track coverage of
the orientation sphere and expose `calibrationCoverage` in the probe log. Do not freeze the
profile until coverage is adequate, regardless of IQR.

**Parameters:** calibration window 300 frames; freeze threshold IQR < 2%; slow drift adaptation α = 0.001/frame gated on high quality.

**Acceptance:** calibrated lengths stable to <2% across three separate sessions with the same user; residual-based downweighting measurably reduces resting jitter.

---

### M3 — Postural synergies and anatomical constraints

**Brain analogue:** hand postural synergies — roughly 7 principal components account for ~90%+ of the variance in natural human grasp postures. The CNS does not control 26 DOF independently.

**Design.** Two layers, cheap → expensive. Implement the cheap one first; it may be sufficient.

**3a. Hard anatomical constraints (implement first, ~1 day)**

Project each frame's joint angles onto the feasible set:

- Joint limits: MCP flexion ∈ [−20°, +90°]; PIP ∈ [0°, 110°]; DIP ∈ [0°, 80°]; MCP abduction ∈ [−20°, +20°].
- **Interphalangeal coupling:** `DIP ≈ (2/3) · PIP` (tendon linkage). Enforce as a soft constraint.
- **Unidirectional flexion.** Fingers do not hyperextend at PIP/DIP beyond a few degrees. **This is the constraint that breaks the bas-relief mirror symmetry** — a depth-reversed hand hypothesis implies backward-bending joints and is therefore anatomically impossible. Feed the violation magnitude as a log-likelihood term into M5. This is the single highest-value line of code in the back-of-hand fix.
- Inter-finger: adjacent MCP abduction difference bounded.

**3b. Synergy subspace (implement if 3a leaves too much jitter)**

Collect a few thousand frames of your own gameplay postures; PCA the 20-dim joint-angle vector; keep k = 7 components at ~92% variance. Per frame, MAP-estimate in the latent space:

```
minimise  ‖J_measured − (μ + Φ·c)‖²_Σ⁻¹  +  λ‖c‖²_Λ⁻¹
```

with `Λ` the training eigenvalues. Expose `c` as `synergyCoeffs` — a 7-dim, near-noise-free, semantically meaningful gesture descriptor. Gesture classification on `c` is far more robust than on raw landmarks, and it is a *smaller* interface, which helps the engine-agnostic boundary.

**Caveat:** a synergy prior will suppress genuinely unusual postures. Keep the residual `‖J_measured − reconstruction‖` and fall back to unconstrained joints when it exceeds threshold — the brain does the same thing (synergies are a default, not a cage).

**IK (optional, phase 5):** solve for the 26-DOF pose minimising reprojection error against screen landmarks + fit to worldLandmarks + synergy prior + limits, via Levenberg–Marquardt warm-started from the previous frame (typically 2–3 iterations at 30 fps). Output `landmarksCanonical`. This subsumes 3a/3b but costs more; do not start here.

**Integration note.** Joint-angle machinery from the archived pinch work already exists
(`features.py`'s finger-curl-angle functions) and is directly reusable for 3a. Also note: if
M3 delivers reliable joint angles and `synergyCoeffs`, the **parked** open-palm/closed-fist
detection (`PART_ONE.md` §3 row 2) becomes materially more tractable than it was when it was
parked. **Do not un-park it on that basis without asking the owner** — it was parked as a
priority decision, not solely a technical one.

**Acceptance:** resting jitter and bone-length CV both drop; visually, fingers stop passing through anatomically impossible configurations during occlusion.

---

### M4 — Observability estimation and precision weighting

> **Scope amendment (A5).** M4 is an **occlusion / hallucinated-landmark / outlier-rejection**
> mechanism. It is **not** a fix for back-of-hand orientation precision: the pipeline has
> recorded empirical evidence (§13.7) that the residual error there is a *correlated* whole-
> knuckle-row distortion, and that per-landmark selection and weighting schemes produce
> statistically indistinguishable results at the degenerate frames. Expect no improvement there,
> and do not read that null result as an implementation failure. M6c is the mechanism for that
> failure mode.

**Brain analogue:** predictive coding — prediction errors are weighted by their estimated precision. Low-precision evidence barely moves the posterior. This is also what saccadic suppression is doing: during fast motion, discount the sensory stream and rely on the model.

**Design.** Produce a per-landmark inverse-variance `1/σᵢ²` each frame, combining:

| Cue | Computation | Effect |
|---|---|---|
| Bone-length residual | from M2 | isolates 3D error per landmark |
| Motion blur | variance-of-Laplacian on the hand crop, normalised | global downweight during fast motion |
| Self-occlusion | fingertip projected inside the palm polygon, or distal bone strongly foreshortened | downweight the specific occluded landmarks |
| Palm conditioning | σ₂/σ₃ from the palm SVD | drives `orientationValid` |
| Edge-on measure | `edgeOnMeasure` from M5a (normalised signed palm area) — computed once there, consumed here | inflates orientation covariance about the unobservable axis |
| Inter-frame acceleration | implausible acceleration vs. human limits | outlier rejection |
| MediaPipe presence/tracking score | as published | weak prior only |

Then, crucially: **the filter innovation itself is a quality signal.** Normalised innovation squared (NIS) exceeding its χ² bound means the measurement disagrees with the model beyond what the noise model allows — gate it out rather than absorbing it.

```python
nis = innovation.T @ inv(S) @ innovation
if nis > CHI2_GATE_3DOF:   # ~11.34 at p=0.01
    # reject as an outlier; coast on the model; increment framesSinceMeasurement
else:
    # accept, weighted by S
```

**This replaces "hallucinated landmarks during occlusion get silently averaged in" — which is currently a live failure mode, because MediaPipe reports occluded landmarks with the same apparent confidence as visible ones.**

**Integration note — this is the Object Jump Correction gate (A9).** The recorded 509 px
single-frame jump (§14.1.4) is exactly the case the χ² gate exists to reject. Verify M4 against
`translation_pivot_jump_test4_20260802_174438.json`, which contains a confirmed reproduction.

**Parameters:** χ² gate at p = 0.01; coast limit 8 frames before declaring `present = false`; blur normalisation calibrated per-camera during M0.

**Acceptance:** injecting synthetic occlusion into a recorded session produces `occlusionLevel` rising and object pose *freezing* rather than jumping; the `jump_test4` excursion is rejected without suppressing legitimate fast motion in the same recording.

---

### M5 — Chirality lock and palm-facing determination

> **Status amendment (A2).** **M5a and M5b are already implemented and live-calibrated** in
> `_is_thumb_outward()` — the signed-area formula is byte-identical and the per-handedness
> negation is exactly the chirality factoring. What is new and worth building is **DR-1**
> (5c), the **`K` fixture test** (5d), **`edgeOnMeasure`** (the magnitude, currently
> discarded), and **DR-2** (5e). Build the `K` fixture test first — see A3.

**Brain analogue:** object constancy — perceptual identity is assigned once and held, not
re-litigated each glance. Bistable percepts (Necker cube) commit and resist switching.

---

#### 5a. The primary cue: signed projected palm area — ALREADY BUILT

Take three palm landmarks — **wrist (0), index MCP (5), pinky MCP (17)** — and compute the
2D signed area in image coordinates (the scalar z-component of the 2D cross product):

```python
# image-plane coordinates from `landmarks`, NOT worldLandmarks
s = (p5.x - p0.x) * (p17.y - p0.y) - (p5.y - p0.y) * (p17.x - p0.x)
```

This single scalar carries **both** quantities you need:

```
sign(s)  ->  which surface faces the camera        (the boolean already in use)
|s|      ->  proportional to |cos θ|, the edge-on / observability measure
```

`|s|`, normalised by the calibrated palm triangle area at current scale (M2), *is* the
edge-on measure referenced elsewhere in this document. Compute it here once; do not compute
a separate projected-area metric in M4.

**Why these three landmarks rather than the thumb:**

- 0, 5 and 17 are wrist and MCP landmarks on the rigid palm. They are the **least
  self-occluded** points on the hand and the **least mobile** — they do not move relative to
  each other under finger articulation.
- The thumb (landmarks 1–4) carries the same information in principle, but it is the most
  mobile and most frequently occluded landmark group. **Use it as a redundant confirmation
  cue, not the primary.**
- No pinky-identification fallback is required: landmark indices are assigned by MediaPipe,
  so finger identity is given, not inferred. The "smallest dimension = pinky" idea is
  nevertheless worth keeping as a **validation check** — see 5d.

#### 5b. The structural correction: `s` gives the product, not the answer — ALREADY BUILT

`sign(s)` does not directly give palm-vs-back. The triangle 0–5–17 traverses in opposite
rotational sense for a left hand versus a right hand. So:

```
sign(s)  =  chirality  ×  palmFacing
```

`s` is a robust measurement of the **product** of two bits. You need one more independent bit
to factor it.

This is not a defect in the approach — it is the actual structure of the problem, and it
explains an observation that would otherwise be confusing: **a right hand seen from the back
and a left hand seen from the palm have near-identical 2D landmark geometry.** The landmark
skeleton is mirror-symmetric; it cannot distinguish them. MediaPipe's `handedness` classifier
distinguishes them from *appearance* (knuckles, tendons, palmar creases, shading), not from
landmark geometry — which is why handedness and palm-facing degrade together under blur, poor
lighting and near-edge-on views. They are the same bit.

**Consequence, and this is the whole design:** pin chirality independently, then `sign(s)`
gives palm-facing deterministically, per frame, with no accumulator.

#### 5c. Chirality lock (Design Rule DR-1) — NEW

> **DR-1 — Handedness is a track-level property, not a per-frame observation.**
> It is established once when a hand track is acquired, then held for the life of that track.
> The gesture layer and all downstream consumers read `HandState.handedness`, never
> MediaPipe's per-frame `handedness` output.

Establish it at acquisition using whichever of these is available, in priority order:

| Source | Strength | Notes |
|---|---|---|
| **Application context** | **Decisive** | Single-hand game with a declared or configured dominant hand. If the game is one-handed, this bit is free — take it and skip everything below. |
| **Persisted user profile** | **Decisive** | Stored alongside the M2 skeleton profile. Returning users start locked. |
| **Accumulated MediaPipe handedness at high quality** | Strong | Accumulate over the first ~20 frames where `quality.overall > 0.85` **and** `\|s\|` is well above the edge-on band **and** the thumb is visible. Under those conditions the classifier is reliable. Require a clear majority before locking. |
| **Two simultaneous hands** | Strong | If two hands are tracked, they are almost certainly one of each; assign by horizontal ordering plus the classifier, jointly rather than independently. |

Once locked, changing it requires the track to be dropped and reacquired (hand fully out of
frame for > 500 ms). Do not permit mid-track chirality changes under any other condition.

**Integration note.** This project's game uses **two hands simultaneously**, either of which can
hold either object — so the fourth row is the operative one, and the first (single-hand
context) does not apply. DR-1 is also a direct structural fix for **Object Jump Correction**
(A9): the recorded failure is precisely a per-frame identity decision being allowed to change
mid-track.

#### 5d. Per-frame determination — the `K` fixture test is NEW and is the priority

With chirality locked, per frame:

```python
palm_facing_raw = K * chirality_sign * sign(s)   # K = fixed convention constant
edge_on_measure = abs(s) / calibrated_palm_area(scale)
```

**Determine `K` empirically once and lock it in a unit test.** The sign convention depends on
(a) whether image y increases downward, (b) whether the camera preview is mirrored, and
(c) MediaPipe's handedness convention, which assumes a mirrored (selfie-view) input image.
Three independent sign flips is three chances to get it wrong by reasoning; one fixture test
with a recorded known-hand-known-orientation clip settles it permanently. **Do this before
anything else in M5.**

> **A3 — this is not hypothetical.** This project shipped exactly this bug on 2026-08-01: the
> thumb-outward rule was silently inverted **in production only**, because detection runs on an
> un-mirrored frame while the landmark *coordinates* are mirrored afterward and the handedness
> *label* was not. It survived an earlier "confirmed working end-to-end" claim. Full account:
> `GESTURE_PIPELINE_SPEC.md` §13.6.1. Recordings of both hands in both orientations already
> exist to build the fixture from.

**Redundant confirmation cues** (use to raise `palmFacingConfidence`, and to alarm on
disagreement rather than to override):

1. **Thumb laterality** — signed offset of landmark 2 (thumb MCP) from the 0–9 palm axis.
   Same information as `s`, computed from a different landmark. Agreement is a health check;
   persistent disagreement means a landmark misassignment.
2. **Finger flexion direction** in `worldLandmarks` — fingers curl toward the palm, never
   away. Independent of the 2D projection and therefore a genuine second opinion. Weaker
   (depends on the noisy z) but valuable when it fires.
3. **Chain-length sanity (the pinky check)** — with the M2 calibrated skeleton, confirm the
   index chain (5→8) is longer than the pinky chain (17→20). This does not determine
   palm-facing, but it **catches gross landmark misassignment after re-detection**, which is a
   real and otherwise-silent failure. Log it; don't gate on it.

#### 5e. The edge-on band (Design Rule DR-2) — NEW

`sign(s)` is reliable everywhere **except** where `|s| → 0`, i.e. when the palm is edge-on to
the camera. There the sign is determined by noise and will chatter. This is the *only* place
temporal machinery is required.

> **DR-2 — Edge-on exclusion.** While `edgeOnMeasure < EDGE_ON_THRESHOLD` (start at 0.15),
> the pipeline sets `quality.orientationValid = false`. The gesture layer must suppress every
> gesture whose definition depends on `palmFacing` or on the palm normal for the duration.
> Gestures depending only on the hand's long axis, on aperture, or on translation remain live
> and must keep working — this band is a routine part of normal hand motion, not an error
> state.

Inside the band:

- **Freeze** `palmFacing` at its last confident value. Do not update it from `sign(s)`.
- **Carry the sign through** by integrating angular velocity from M6 across the crossing.
  On exit, if the integrated rotation implies a surface change, apply it; otherwise restore
  the frozen value. This is the kinetic depth effect: the motion, not the instantaneous
  geometry, resolves the ambiguity.
- On exit, require `|s|` to exceed `EDGE_ON_THRESHOLD × 1.6` (**hysteresis**) for 3
  consecutive frames before resuming per-frame updates.

**Integration note.** DR-2 interacts directly with `GAME_RULES.md` rule 3 (the thumb-outward
snap restriction), which is a `palmFacing`-dependent gesture and must therefore be suppressed
inside the band. Rule 3's existing "armed exception" state machine already has
freeze-through-loss semantics and should be reconciled with DR-2's freeze rather than
duplicating it.

#### 5f. Correction to an earlier claim

An earlier draft asserted that a **flat, fully-extended hand is maximally ambiguous** for
palm/back determination. **That is wrong and is retracted.** It was true only of the
flexion-direction cue. Under the signed-area cue, a flat hand facing the camera produces the
*maximum* possible `|s|` and is the *best*-conditioned case.

The ambiguous configuration is **edge-on**, not flat. This materially relaxes the gesture
design constraints: flat-hand gestures are fine. Gestures that require the user to hold the
palm perpendicular to the camera axis are not.

**Parameters:** `EDGE_ON_THRESHOLD` 0.15; exit hysteresis ×1.6; exit dwell 3 frames; chirality
lock 20 high-quality frames; track drop 500 ms.

**Acceptance:** chirality flip rate = 0 across all scripted sequences (§7.2), including the
palm↔back rotation set; crossing survival > 98%; `K` fixture test passes on recorded clips of
both hands in both orientations.

---

### M6 — Quaternion pose filter with anisotropic covariance

> **Status amendment (A4/A6).** **6a is already satisfied** — this project has never used Euler
> angles in the estimation path and `PART_ONE.md` §2 forbids it. Verify and tick; budget no
> time. **6b–6e also carry a removal obligation:** M6 subsumes the existing
> `HandOrientationFilter`, and shipping M6 means **deleting** that filter, not running both.
> Reconcile `observability` with the existing `conditioning_norm` into a single metric.

**Brain analogue:** vestibular/proprioceptive fill-in through visually degenerate configurations; the CNS never parametrises limb orientation in a singular chart.

**Design.**

**6a. Remove Euler angles from the estimation path entirely.** Non-negotiable. Represent orientation as a unit quaternion; use an error-state formulation (small-angle 3-vector error in the tangent space around the nominal quaternion) so the covariance is 3×3 and well-behaved. Euler angles may exist *only* as a final display convenience, and must be computed after filtering, never fed back. *(Already satisfied — see A4.)*

**6b. Palm frame construction.**

```
P = [p0, p5, p9, p13, p17] centred        # exclude landmark 1 (thumb CMC) -- it moves
[U, S, V] = svd(P)
e1 = V[:,0]   # long axis, best conditioned
e2 = V[:,1]
n  = V[:,2]   # palm normal -- ILL-CONDITIONED as S[1]/S[2] -> 1
observability = 1 - S[2]/S[1]
```

Prefer `worldLandmarks` for this fit (M1). Orthonormalise; apply the M5 sign.

**Integration note.** The existing frame construction uses `index_MCP→pinky_MCP` (width) +
`wrist→middle_MCP` (length), chosen over an earlier wrist-anchored pair after a data-driven
investigation, with **chirality preservation explicitly verified against recorded data**
(§13.7). If M6b's SVD changes the frame, that chirality verification **must be repeated the
same way** — the recorded lesson is that yaw/roll silently invert if the vector order changes.

**6c. Anisotropic process/measurement noise — the crux.**

The orientation covariance during the crossing is **not** large in all axes. Rotation *about* the well-observed long axis stays precise; rotation *about the axes that determine the normal* becomes unobservable. Encode this:

```python
# measurement covariance in the body frame, not isotropic
R_orient = diag(
    sigma_long**2,                                  # well observed throughout
    sigma_base**2 / max(observability, eps),        # blows up at the crossing
    sigma_base**2 / max(observability, eps),
)
```

With this, a UKF will automatically coast on angular velocity along the unobservable directions and keep tracking precisely along the observable one — which is exactly the behaviour you want and exactly what isotropic smoothing cannot give you.

**6d. Motion model.** Constant angular velocity with a decay term. Human wrist angular velocity rarely exceeds ~15 rad/s; use that to set process noise and to gate outliers.

**6e. Expose `orientationSigma` (per-axis) in `HandState`.** Gestures that depend on the palm normal must check it. Gestures that depend only on the hand's long axis need not — and will keep working through the crossing. This is a real capability gain, not just a safety gate.

> ### ✅ 6e's INPUT IS ALREADY BUILT — `palm_observability()` (2026-08-03)
>
> `Local_pc/Movement_with_hand_detection/Resources/palm_geometry.py` implements
> M6b's `observability = 1 − S₃/S₂` and it is the **one piece of the five failed
> 2.3 attempts that carries real value** (§0.13.3). Do not rebuild it.
>
> | property | status |
> |---|---|
> | correctness | matched to numpy's SVD to **1.6e-11 over 22,345 frames** |
> | discriminative range | **0.046 – 0.908** |
> | behaviour at crossings | collapses to **0.05–0.15** |
> | behaviour on controls | **0.75–0.91** (`static_hold` 0.818, `known_*` 0.834–0.890) |
> | dependencies | **none** — closed-form 3×3 symmetric eigenvalues, no numpy, ports to JS/Swift/Kotlin by transliteration |
>
> **Its proper home is `HandState.quality.orientationValid` in §2, not the
> orientation filter.** Five attempts to drive a filter with it failed, for a
> measured reason: **82% of large orientation jumps occur at observability ≥ 0.60**
> (§0.13.2), so it cannot gate the tail. But it is a *correct* observability signal —
> it simply answers "is the palm normal well determined right now?", which is
> exactly what a quality flag is for and what gestures branch on.
>
> **What is NOT yet built:** the per-axis `orientationSigma` vector. Only the scalar
> exists. Deriving anisotropic sigmas from it is unfinished work — and note §0.13.2
> before assuming per-axis sigmas will help, since the anisotropy premise is what
> failed.

**Acceptance:** during a scripted pitch sweep, yaw and roll remain finite and continuous; no discontinuity in the rendered object's orientation; `orientationSigma` visibly rises and falls around the crossing; **the existing `HandOrientationFilter` is deleted and the A/B diff shows no regression from its removal.**

---

### M7 — Dual-pathway filtering and forward-model prediction

**Brain analogue:** the magnocellular/parvocellular split — a fast, transient, low-spatial-resolution motion pathway alongside a slow, sustained, high-resolution form pathway; plus cerebellar forward models that extrapolate to cancel ~100 ms of neural conduction delay (why the flash-lag illusion exists).

**Key insight:** you currently have **one** filter serving two incompatible requirements. Position for rendering wants heavy smoothing. Interaction triggers want minimum lag. Any single cutoff frequency is wrong for one of them.

**Design — split the channel:**

```
FORM  (parvo):  heavy smoothing, ~6 Hz cutoff
                -> hand skeleton rendering, articulation display, static pose classification
                -> lag is acceptable and invisible

MOTION (magno): light smoothing, ~15 Hz, velocity/acceleration estimated as filter STATES
                -> triggers, aperture rate, angular velocity, trajectory features
                -> lag is unacceptable; some jitter is acceptable because
                   downstream consumers integrate over a window anyway
```

Never compute velocity by finite-differencing the *smoothed* position — that combines the worst of both (noise amplification *and* group delay). Velocity is a **filter state** in M6, obtained from the motion model.

**Forward prediction — spend the effort here, it is the biggest subjective quality win.**

> ## ⚠⚠ STOP — MEASURE THE MOTION MODEL BEFORE BUILDING THIS (added 2026-08-03)
>
> **M7's forward prediction extrapolates with the constant-angular-velocity model.
> That model has been measured on this project's own 24-session corpus and it is
> WEAK.**
>
> | measurement | result |
> |---|---|
> | mean frame-to-frame orientation change | **9.9°** |
> | one-frame prediction disagreeing with the measurement by >25° | **60% of frames** |
> | ... by >15° | **66% of frames** |
>
> **The predictor is unreliable at ONE frame. M7 proposes extrapolating it to
> ~80 ms — roughly TWO frames at the measured ~24 fps.**
>
> This is not speculation; it is the finding that explains why five separate
> attempts at item 2.3 failed (§0.13–§0.13.3). Every approach that leaned on this
> model — graded blending, coasting, χ² gating — inherited its weakness. The shipped
> `HandOrientationFilter` wins precisely *because* its `alpha` saturates at 1 and it
> therefore **ignores the prediction almost always**.
>
> ### Required first task for item 3.1
>
> **Measure the model's prediction error at 1, 2 and 3 frames ahead on the recorded
> corpus, and decide whether it is fit to extrapolate with — BEFORE building
> anything.** If it is not, M7's headline claim ("net perceived latency can go to
> zero or slightly negative") does not follow, and steps 2–5 below should not be
> built as written.
>
> ### What is still worth having even if prediction is unfit
>
> **The FORM/MOTION channel split (above) does not require prediction at all.** Its
> value — one filter cannot serve both rendering smoothness and trigger latency — is
> independent and stands on its own. If the predictor fails its measurement, build
> the split and skip the extrapolation.
>
> *Substrate note: the motion model, `omega` as a public state, and
> `predict_forward()` already exist in the parked `Resources/orientation_filter.py`
> (§0.13.1). 3.1's old dependency on 2.3 was for exactly those and is satisfied
> without shipping 2.3 — but inheriting the code does NOT inherit a working
> predictor. Measure first.*

1. **Measure** your end-to-end latency (§6.2 procedure). Do not guess it.
2. Predict the state forward by `L_total` using the constant-velocity/constant-angular-velocity model.
3. Scale prediction horizon by confidence: `L_effective = L_total · clamp(quality.overall, 0, 1)`. Never extrapolate far on a low-quality state — overshoot looks worse than lag.
4. Cap the prediction horizon at ~80 ms regardless; beyond that, model error dominates.
5. Set `HandState.tPredicted` accordingly so consumers know what instant they are looking at.

Net perceived latency can go to zero or slightly negative. Users read this as "responsive" far more strongly than they read jitter as "noisy."

**Integration note.** `ROTATION_SLERP_FACTOR` (currently 0.35, raised from 0.25 for
responsiveness) is the project's existing single-cutoff compromise and is exactly the knob M7
replaces. When M7 lands, that constant should be retired into the FORM channel rather than
left as an independent tuning parameter.

**Acceptance:** measured end-to-end latency (§7.2) drops by ≥ 40 ms with no increase in overshoot on direction reversals.

---

### M8 — Grasp-onset prediction and retrospective anchoring

> **Amended on integration (A7).** **M8a is NOT adopted.** `GESTURE_PIPELINE_SPEC.md` §14.1's
> distance-weighted phalange-landmark mechanism is shipped, verified and live-confirmed, and it
> governs. M8a is retained below **as a logged A/B candidate only**, to be measured against
> §14.1 on recorded data once M6/M9 supply a metric palm pose — because the stated reason for
> rejecting a palm-anchored design (a 2D/3D coordinate mismatch) will no longer hold at that
> point. **Do not modify §14.1's mechanism before that A/B runs.** Anti-pattern #6 is
> correspondingly downgraded — see §8.
>
> **M8b and M8c are additive to §14.1 and are not affected by this deferral.**

**Brain analogue:** anticipatory grip aperture. In reach-to-grasp, aperture peaks at ~70–80% of the movement and scales with target size — the contact configuration is committed well before contact. The motor system does not wait to observe contact and then react.

**Design — three independent fixes:**

**8a. Anchor to the palm, not the fingertips.** *(A/B CANDIDATE ONLY — NOT ADOPTED, see above.)*

The grab *position* would come from the palm frame (M6): a rigid, well-conditioned, 5-landmark fit. Fingertips determine *whether* a grab occurred; they would not determine *where*.

```python
grab_anchor_world = palm.position + palm.orientation * calibrated_grasp_offset
# where calibrated_grasp_offset is a constant in the palm frame,
# determined once during calibration, not per-grab from fingertips.
```

If you need a pinch point, use the midpoint of thumb IP (3) and index PIP (6) rather than the tips (4, 8) — one joint proximal, markedly less noisy and less occluded, and it moves with the same rigid transform.

*Counter-evidence on record (§14.1):* the shipped mechanism deliberately includes fingertips
because the object's grasp point genuinely depends on where in the phalange volume it was
seized, which is object-size-dependent (Napier). The A/B must therefore test **grab-placement
accuracy**, not just jitter — a palm anchor will trivially win on stability while potentially
losing on correctness.

**8b. Retrospective (backward) smoothing at the trigger instant.** *(Additive — proceed.)*

Keep a 15-frame ring buffer of filter states *and* measurements. When a grab fires at `t_g`, do not use the live estimate. Run a **Rauch–Tung–Striebel backward pass** over the buffer to produce a smoothed estimate at `t_g` that uses frames from *after* `t_g`.

```
forward filter:   x̂(t | t)        -- what you have live, noisy at t_g
RTS smoother:     x̂(t_g | t_g+k)  -- uses future frames, far more accurate
```

This costs one frame-time of extra lag on the *anchor computation only* (the object can appear immediately at the predicted pose and be corrected within one frame, imperceptibly), and it typically halves anchor error. **You already have this information; you are currently throwing it away.**

**8c. Predict grasp onset instead of detecting it.** *(Additive — proceed.)*

Track `apertureRate` (a filter state from M7, not a difference). Extrapolate to the closure threshold:

```python
t_contact = (aperture - APERTURE_CLOSED) / max(-aperture_rate, eps)
if t_contact < latency_budget_ms and aperture_rate < -RATE_MIN and evidence > BOUND:
    fire_grab_intent(anchor_from_rts)
```

Fire at `t_contact − L_total` so the object appears *as* the hand closes, not after. Guard with evidence accumulation (M10) and an asymmetric cost: a late grab is mildly annoying; a false early grab is much worse. Bias the bound accordingly.

**Note.** Today's snap trigger is **proximity-based**, not aperture-based
(`GAME_RULES.md` rule 1) — there is no aperture threshold in the shipped game. 8c therefore
depends on a gesture-design decision that has not been made, and is **blocked on the
hand-open release trigger work** (§14.2), which is where aperture first enters the design.

**Acceptance:** grab-placement spread (§7.2 fiducial test) reduced by ≥ 50%; user-reported "the object appears where I grabbed."

---

### M9 — Metric depth from the body schema

**Prerequisite for Z-axis control. Do not build Z-axis control on MediaPipe's `z`.**

> **Amended on integration (A8).** This module is **compatible with, and a refinement of,**
> `GESTURE_PIPELINE_SPEC.md` §14.3's confirmed Z-axis design — which already specifies an
> apparent-hand-span *ratio* against a grab-time baseline, and already rejects raw
> `world_landmarks` z. M9 improves it in two specific ways: **never use a single bone** (§14.3
> currently specifies `wrist↔middle-MCP` alone) and **correct for foreshortening**. That second
> point is the concrete fix for the recorded **yaw/palm-sinking** limitation (§14.1.1), whose
> proposed remedy was an unspecified "startup Z-axis calibration."

**Brain analogue:** size–distance invariance — known object size plus retinal size yields distance. Your "known object" is the user's own calibrated hand (M2).

**Design.**

```
d = f · L_metric / L_pixels
```

where `L_metric` is a calibrated bone length (M2), `L_pixels` its projected length, and `f` the focal length in pixels.

**Practical details that matter:**

- **Focal length.** Either a one-time calibration (hold hand at a measured distance) or, better, express everything as a *ratio* `d/d₀` against a reference captured at snap time — this cancels `f` entirely and is sufficient for relative Z control. Prefer the ratio form; it removes a whole calibration step. *(§14.3 already chose the ratio form — keep it.)*
- **Use a foreshortening-corrected measure.** Palm width (landmark 5 → 17) corrected by `|cos θ|` from M5/M6, or better, a robust fit over *all* bones weighted by M4 precision, with each bone's foreshortening accounted for by the current pose estimate. Never use a single bone.
- **Noise scales as d².** Depth precision degrades quadratically with distance. Budget for this: define a working volume where precision is acceptable, and set `depthValid = false` outside it rather than letting Z control silently degrade.
- **Sanity cross-check** against `worldLandmarks` scale; disagreement is a quality signal.
- **Control–display gain.** Do not map depth linearly to object Z. Use a velocity-dependent gain (small hand movements → precise control; fast movements → large range), the analogue of the brain's mixed position/velocity control. This is also what makes limited depth resolution feel adequate.

**Note on §14.3's 3D snap gating.** §14.3 specifies that snap becomes a 3D proximity check
(X, Y **and** Z). That requires `depthValid` to be true at the moment of snap; the gating rule
must define what happens when it is false — fall back to 2D proximity, or refuse to snap. **Not
yet decided; raise with the owner when §14.3 is built.**

**Acceptance:** `d/d₀` reproducible to < 5% at fixed distance with varied hand orientation (this is the test that catches foreshortening bugs); monotonic and jitter-free through a slow push-pull sweep; the §14.1.1 yaw/palm-sinking bias measurably reduced on the existing recordings.

---

### M10 — Commitment dynamics for snap/unsnap

**Prerequisite for the unsnap feature.**

**Brain analogue:** hysteresis in bistable perception; perception commits and resists switching. Also: release actions are *ballistic* — an intentional release has a characteristic velocity profile, whereas incidental hand drift does not.

**Design.**

1. **Schmitt triggers, never thresholds.** `apertureOpen > apertureClose` with a meaningful gap. A single threshold guarantees dithering at the boundary.
2. **Dwell time.** A state change requires the condition to hold for N consecutive frames (suggest 3 at 30 fps for grab, 4 for release).
3. **Evidence accumulation, not instantaneous test.** Bounds are asymmetric and *task-dependent*: accidental unsnap is far more costly than delayed unsnap, so `B_release > B_grab`.
4. **Rate as a requirement, not just level.** Require `apertureRate > RATE_MIN` for release — an intentional open is fast; a slow drift past the threshold is not a release. This alone eliminates most accidental drops.
5. **Refractory period.** ~200 ms lockout after any state change, mirroring the psychological refractory period.
6. **Quality gating.** Release must not fire while `quality.overall` is low or `framesSinceMeasurement > 0`. **Occlusion must never cause a drop.** During the pitch crossing specifically, `orientationValid = false` — and unsnap must be suppressed unless it is unambiguously intentional by the rate criterion.
7. **Grace on loss of tracking.** If the hand disappears, hold the object for ~400 ms and reacquire; only then drop. Losing tracking is not the same as letting go.

**Integration note — item 7 changes an existing shipped rule.** `GAME_RULES.md` rule 2
currently drops the object **immediately** on tracking loss, and that behaviour is live and
verified. M10.7 proposes a ~400 ms grace period instead. This is a **deliberate game-rule
change, not a perception improvement**, and must be raised with the owner rather than
introduced as a side effect of building M10. Note also that the existing same-frame
release/re-snap ordering fix (§13.5) interacts with any grace period — a cube held in limbo
must be excluded from other hands' snap passes for the duration.

**M10.7 also fixes a recorded gameplay defect (merged queue N8).** Observed
2026-08-02: **a hand can steal another hand's cube simply by occluding it.** Hand A holds a
cube, hand B moves in front of it, A's tracking is lost, rule 2 releases the cube, and B —
which is by definition right where A was, therefore inside the grab radius — snaps it a frame
or two later. §13.5's fix only blocks re-snapping on the *same* tick, not the next one. A
grace period would keep the cube held through the occlusion, leaving nothing to steal.
Recorded and deliberately **not** fixed now; the expectation is that refining snap control
resolves it. *(Mechanism inferred from the rules, not instrumented — if it is ever worth
confirming, the `two_hand_overlap` recorded sequence already reproduces the occlusion
condition, with 205 of 717 frames showing only one hand detected.)*

**Acceptance:** zero accidental unsnaps across a 10-minute scripted manipulation session including deliberate occlusions and pitch crossings.

---

## 5. Mapping: modules → TODOs

**Superseded on integration.** The authoritative, merged, single build queue — covering both
this spec's modules and the pipeline's own TODOs, in one ordered list — is
**`PART_ONE.md` §3.1**. It is the only list; do not maintain a second one here.

Two dependency facts from Revision 2 are preserved because they are load-bearing:

- **M2 is a hard prerequisite for Z-axis control** (no calibrated skeleton → no metric scale →
  no usable depth).
- **M4 is a hard prerequisite for unsnap** (no occlusion detection → objects get dropped when a
  hand is partially hidden).

Building either feature before its prerequisite means building it twice.

---

## 6. Build order

### 6.1 Phases

**Owner decision (2026-08-02): execute Phases 0–2, then reassess** before committing to
Phase 3+. Phases 0–2 are expected to close back-of-hand tracking, the pitch-plane crossing,
and — per A9 — plausibly Object Jump Correction. Whether the release trigger and Z-axis
control still need Phase 3 first is a decision to make with those results in hand.

**Phase 0 — Instrumentation (do not skip).**
M0. Recording + replay harness + metric dashboard, generalised from the existing
`RecordTranslationPivotDebug.py` / `AnalyzeTranslationPivot.py` tools. Establish baseline
numbers for every M0 metric on the current pipeline — **the first baselines can be computed
from already-recorded sessions, no new capture needed.** Everything after this is measurable.

**Phase 1 — Kill the singularities. Highest value per hour.**
- **M5d `K` fixture test** — do this first (hours, not days; guards a bug this project has
  already shipped once).
- M5a `edgeOnMeasure` — recover the magnitude already being discarded.
- M6a: *verify already satisfied* (A4) — no work expected.
- M2: bone-length calibration (proportions online, per 2f).
- M3a: hard anatomical constraints, including the unidirectional-flexion prior.
- M4: bone-residual precision weighting + χ² innovation gating. **Verify against
  `jump_test4`** (A9).

*Expected: bone-length CV and resting jitter both drop; anatomically impossible poses
disappear; Object Jump Correction's excursion is gated out.*

**Phase 2 — Temporal identity.**
- M5c–M5e: chirality lock (DR-1), redundant confirmation cues, edge-on band (DR-2) with
  angular-velocity carry-through.
- M6b–e: quaternion UKF with anisotropic covariance; expose `orientationSigma`,
  `orientationValid`; **delete the superseded `HandOrientationFilter`** (A6).

*Expected: back-of-hand and pitch-crossing TODOs closed. This is the phase that makes them
genuinely work rather than merely not crash.*

**→ REASSESS HERE (owner decision).** Re-measure all M0 metrics; re-test Object Jump
Correction; decide whether Phase 3 precedes the feature work.

**Phase 3 — Latency and grab.**
- M7: dual-pathway split + measured-latency forward prediction; retire `ROTATION_SLERP_FACTOR`.
- M8b: RTS retrospective smoothing (additive to §14.1).
- **M8a A/B against §14.1** (A7) — measure, then decide.
- M8c: predictive grasp onset — *blocked on the aperture-based gesture design (§14.2).*

**Phase 4 — Unlock the next features.**
- M9: metric depth → then build Z-axis control (§14.3).
- M10: commitment dynamics → then build the hand-open release trigger (§14.2).
  *Raise M10.7's grace-period game-rule change with the owner first.*

**Phase 5 — Optional refinement.**
- M3b: synergy subspace.
- M3 IK: full 26-DOF inverse kinematics.
- Trajectory-based gesture classification (small TCN/GRU over a 15–30 frame window of
  `synergyCoeffs` + palm kinematics).

### 6.2 Latency measurement procedure (needed by M7, do it in Phase 0)

Guessing latency and then predicting by the guess is worse than not predicting.

1. Display a large high-contrast element driven directly by hand position, with a frame counter burned into a corner of the screen.
2. Film the screen *and* the hand together with a phone at 240 fps.
3. Perform a sharp direction reversal.
4. Count frames between the physical reversal and the on-screen reversal. At 240 fps each frame is 4.17 ms.
5. Repeat 20×, take the median.
6. Break the total down by instrumenting each stage (capture timestamp → inference done → filter done → render submitted) so you know which stage to attack.

Typical budget to expect:

| Stage | Typical |
|---|---|
| Camera exposure + readout | 10–30 ms |
| MediaPipe inference | 8–20 ms |
| Filter group delay (current smoothing) | 10–40 ms |
| Render + compositor | 16–33 ms |
| **Total** | **50–120 ms** |

Note that "filter group delay" is entirely self-inflicted and is the first thing M7 removes.
This project has an **additional** stage the table omits: **socket IPC between the vision
server and the client process.** Instrument it separately — it is a real contributor here and
is absent in a single-process design.

---

## 7. Test protocol

### 7.1 Replay harness

Record raw MediaPipe output (both landmark sets, handedness, scores, timestamps, and optionally the source frames) to the capture root per M0. Every module is then evaluated offline, deterministically, on identical input. Config is hashed into the metrics log. **No perception change ships without a replay A/B diff table** — and per A10, a module that shows a null result is **removed**, not kept hopefully.

### 7.2 Scripted test sequences

Record each once, reuse forever:

| Sequence | Duration | Targets |
|---|---|---|
| **Static hold**, 5 poses × 10 s | 50 s | resting jitter, palm-normal jitter, bone CV |
| **Slow pitch sweep**, −120° → +120°, 3 s per sweep, ×10 | 60 s | crossing survival, orientation continuity, sign stability, DR-2 entry/exit behaviour |
| **Fast pitch sweep**, same range, 0.5 s per sweep, ×10 | 20 s | crossing survival under blur; angular-velocity carry-through |
| **Palm↔back rotation** at 4 speeds | 40 s | chirality flip rate, hysteresis behaviour |
| **Reach-and-grab to fiducials**: 5 marked physical positions, ×10 each | 3 min | grab-placement spread |
| **Occlusion**: hand behind object, in/out of frame, finger-over-finger | 60 s | coast behaviour, reacquisition time, **zero accidental unsnaps** |
| **Two-hand crossing** *(added on integration)*: hands pass close together and swap sides | 60 s | **Object Jump Correction** — the identity-mixup repro condition (§14.1.4) |
| **Push–pull depth sweep**, 30 cm → 80 cm, varied orientation | 60 s | depth monotonicity, foreshortening-correction correctness |
| **Direction reversals** for latency | 2 min | end-to-end latency, overshoot |
| **Free manipulation**, 10 min unscripted | 10 min | regression net; catches what scripts miss |

**Recording protocol note (from recorded project experience).** Ask the operator to confirm
after **each** take whether the target behaviour actually occurred, and discard takes that did
not reproduce it. Object Jump Correction took four takes to capture; analysing the first
available recording instead would have produced a confident wrong conclusion. Also: request
permission before each individual live-camera take rather than queueing several.

### 7.3 Boundary enforcement

- Static check (lint rule or build step): the perception layer (L0–L6) must not import the
  engine binding or any scene module; the gesture layer must not import from L0–L6 other than
  the `HandState` type.
- The gesture layer must be unit-testable against synthetic `HandState` fixtures with no
  camera and no renderer. If it isn't, the boundary has leaked.
  *(Today it cannot be: `HandsTriggeredActions.py` opens a real pygame window as an import side
  effect. Fixing that is part of the L7 cleanup and is a prerequisite for this test.)*
- Ship a synthetic `HandState` generator (scripted trajectories, injectable noise and quality
  drops) — this lets you test unsnap and Z-control logic *before* the perception work lands, in
  parallel.

---

## 8. Anti-patterns to avoid

1. **Increasing smoothing to fix jitter.** Trades a visible problem for an invisible one (lag), which users dislike more. Fix the estimator, not the low-pass.
2. **Euler angles anywhere in the estimation path.** Guaranteed to fail at exactly the configuration in the pitch-crossing TODO. *(This project already complies.)*
3. **Trusting MediaPipe's `z` for anything metric.** It is wrist-relative and weakly supervised. Use M9.
4. **Trusting MediaPipe's handedness as an observation.** It is derived from the ambiguous cue and is often the thing that flips. Prior only.
5. **Deciding per frame what should be decided over time.** Chirality, palm-facing, and gesture state are *persistent* properties. Re-deriving them each frame discards the temporal evidence that is the only thing capable of resolving them. *(This is the structural cause of Object Jump Correction.)*
6. ~~**Anchoring to fingertips.**~~ **Downgraded on integration (A7).** The shipped, verified
   mechanism (§14.1) deliberately includes fingertips because grasp location is genuinely
   object-size-dependent. Fingertips are noisier — that is true and worth weighting for — but
   "never anchor to them" overstates it and conflicts with the pipeline record. Revisit only
   via the M8a A/B.
7. **Averaging in hallucinated landmarks.** Occluded landmarks come back confident and wrong. Gate them out (M4).
8. **Making an edge-on palm orientation a critical gesture.** When the palm is perpendicular to the camera axis, palm-facing is genuinely unobservable and no software fix exists. *(Flat, fully-extended hands are fine — that was an error in an earlier draft, retracted in M5f.)*
9. **Guessing latency.** Measure it (§6.2).
10. **Building Z-control before M2/M9, or unsnap before M4/M10.** You will build them twice.
11. **Keeping a module that measured no improvement.** *(Added on integration, A10.)* Revert it
    and record the null result.
12. **Verifying only in the debug tool.** *(Added on integration.)* "Works in `LiveSnapDebug.py`"
    and "works in production" are different claims whenever a wire-protocol boundary sits
    between them — this project has shipped a production-only bug that survived exactly that
    conflation (§13.6.1).

---

## 9. Selected background

- Johansson (1973) — point-light biological motion; kinematics alone carry action identity.
- Santello, Flanders & Soechting (1998) — postural synergies; ~2 PCs cover >80% of static grasp variance, ~7 for high fidelity.
- Jeannerod (1984) — anticipatory grip aperture; peak aperture timing and size scaling in reach-to-grasp.
- Ernst & Banks (2002) — statistically optimal, reliability-weighted multisensory cue integration.
- Wallach & O'Connell (1953) — the kinetic depth effect; motion resolves monocular depth ambiguity.
- Wolpert, Ghahramani & Jordan (1995) — internal forward models for motor prediction and delay compensation.
- Gold & Shadlen (2007) — evidence accumulation to a bound as the mechanism of perceptual decision.
- Friston (2009) — predictive coding and precision-weighted prediction error.
- Casiez, Roussel & Vogel (2012) — 1€ filter; useful as a *baseline* for the jitter/lag trade-off you are trying to escape.
- Napier (1956) — prehensile movements of the human hand; power vs. precision grip, object-size dependence. *(Added on integration — the basis for §14.1's shipped mechanism.)*
