<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PERCEPTION_LAYER_SPEC.md lines 1-300
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
# PERCEPTION_LAYER_SPEC.md

**Scope:** Improvements to the hand-perception stack that sit *below* the gesture-logic layer.
**Status:** Design spec — integrated into the pipeline 2026-08-02. Phases 0–2 are the immediate next build step; see the merged build queue in `PART_ONE.md` §3.1 (the single authoritative TODO list).
**Architectural rule honoured:** every module in this document lives in the perception layer and is invisible to the gesture-logic layer. The only thing that changes at the boundary is the *quality and richness of the `HandState` struct*, whose schema is versioned in §2.

**Precedence:** the project pipeline `.md` files are the authoritative record of failure
analysis and lessons learned. Where this spec conflicts with them, they govern.

**Revision 2** (author) — §3 replaced by a pointer to the pipeline docs; M5 rewritten around the
signed-palm-area cue per owner review; M2 extended with per-user calibration policy (2f);
M8/M9 flagged as subject to amendment; one earlier claim retracted (M5f).

**Revision 4** (audit + state-of-the-art review, 2026-08-03) — **§0.15** audits this
project's own negative results (two artifacts found: the jump-tail numbers were inflated
by identity contamination, and the "motion model is weak" claim is **retracted**; the
five 2.3 nulls and the M2 premise-kill are **confirmed**), and **§10** is a literature
addendum with adopted items **S1–S12**, each mapped to a build step. Correction boxes
were added in place at §0.0, §0.13.2, §0.13.3, §0.14 and M7 — **read those before
quoting any number from them.**

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

> **⚠ THE FIRST TWO ROWS WERE AUDITED 2026-08-03 AND PARTLY CORRECTED — see
> §0.15.** Row 1's number is wrong (82% → ~77%) though its conclusion holds;
> row 2's verdict holds but was measured against the wrong quantity. A third
> claim, *"the motion model is weak"*, was **retracted outright** as a
> measurement artifact. The audit harnesses are
> `analysis/audit_jump_provenance.py` and `analysis/audit_m2_proportions.py`;
> both reproduce the published numbers before correcting them.

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

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/PERCEPTION_LAYER_SPEC.md lines 2190-3901
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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
                         // ⭐ THIS IS THE MISS-COUNTER. `DROPOUT_MITIGATION.md`
                         //    proposed `framesSinceGoodDetection`; same field,
                         //    same semantics -- do not add a second one.
    trackingState,       // 'TRACKING' | 'BRIDGING' | 'SUSTAINED_LOST'
                         // ⭐ ADDED 2026-08-21 (queue D1). The ONE field
                         //    `DROPOUT_MITIGATION.md` contributed that this
                         //    contract did not already have. TRACKING = fresh
                         //    detection; BRIDGING = no detection but still
                         //    inside the coast window; SUSTAINED_LOST = coast
                         //    window exhausted. Consumers branch on this the
                         //    same way they branch on the other quality gates.
  },
}
```

### 2.1 ⚠ THIS IS THE SINGLE SCHEMA OF RECORD (2026-08-21)

`DROPOUT_MITIGATION.md` §2 proposed a **second** `HandState` schema for the same
object. It is **superseded by this one** — do not implement both, and do not keep
both documents' field lists alive. The mapping, so nothing is lost:

⭐⭐ **`DROPOUT_MITIGATION.md` IS NOT A FILE IN THIS REPOSITORY, AND THE TABLE
BELOW IS WHY IT DOES NOT NEED TO BE.** It was owner-supplied, and the owner's
decision (2026-08-21) was to **distil it rather than file it**: its schema is this
table, its build tiers are `PART_ONE.md` §3.1's Phase D rows (each one either
adopted with the correction that this project's own measurements force, or struck
and named as already-rejected work), and its premise is queue **D0** and
`analysis/d0_dropout_census.py` — the measurement that refuted it. ⚠ It is still
NAMED here and in those rows, because a claim's provenance is worth recording;
**those are citations of a document that was read, not links to one that can be
opened.** Do not read an unresolvable reference to it as a missing file, and do
not try to reconstruct it — everything that survived review is already below.

| `DROPOUT_MITIGATION.md` §2 | here | note |
|---|---|---|
| `position`, `velocity` | `palm.position`, `palm.linearVelocity` | same |
| `orientation`, `angularVelocity` | `palm.orientation`, `palm.angularVelocity` | same |
| `positionConfidence` | `palm.covTrace` | ⭐ **this contract is better** — real uncertainty, not a fixed time-decay ramp |
| `orientationConfidence` | `palm.orientationSigma` + `quality.orientationValid` | ⭐ **better** — **per-axis anisotropic**. Collapsing it to one scalar would discard exactly the asymmetry §16.17 measured (orientation fragile, position calm) |
| `framesSinceGoodDetection` | `quality.framesSinceMeasurement` | already present |
| `lastGoodTimestampMs` | derive from `tCapture` + the miss-counter | dropped |
| `trackingState` | `quality.trackingState` | ⭐ the one real addition, now above |

⚠ **A third `HandState` existed in code and was NOT this contract**:
`LiveGestureDebug.py` defined an unrelated gesture-history buffer under the same
name. Renamed to `GestureHistory` on 2026-08-21 so the identifier is free for the
real implementation.

### 2.2 ⚠ Scope of the FIRST implementation — a subset, deliberately, and NOT the wire

⭐ **Owner decision, 2026-08-21.** The migration note below requires replacing the
wire protocol and forbids running two protocols in parallel — correctly, since
that divergence caused §13.6.1. **Read literally it would put a socket migration
in front of a measured defect** (queue D0: 98 spurious cube releases).

It does not have to. **Dropouts surface CLIENT-side**: the server already sends 21
zero landmarks on a miss (`remap_keypoints`'s `expected_count` fallback) and
`HandsTriggeredActions._is_detected` reads them. So `trackingState` and the
miss-counter can be produced **on the client, from the existing wire data**.

So queue **D1 implements a SUBSET of this contract, client-side, using these field
names and semantics — and does NOT touch the wire protocol.** No second protocol
exists, so the rule below is not engaged. ⚠ **The full migration remains required
and is a separate decision, naturally paired with 4.1/M9** — which is what makes
this contract's metric fields (`palm.position` in metres, `depth`) meaningful at
all. Until then, do not serialise this struct.

⭐⭐ **AND THE MIGRATION NOW HAS A SECOND, MEASURED CUSTOMER — ADD A TRACK ID TO
IT (2026-08-22).** Queue **T3** measured that **113 of 205 spurious cube releases
are the owner's own hand reappearing under the other handedness label**: cube
ownership keys on the label, so any relabel — DR-1 erring *or* correcting itself —
orphans a held cube. A client-side repair was built, live-tested and **reverted**,
because it had to infer "same hand" from POSITION and two hands in the same place
are indistinguishable by position (that is what occlusion IS); it handed a held
cube to the operator's other hand. ⭐ **v2 makes the whole question vanish: carry
the DR-1 track identity on the wire and key ownership on it.** So when this
migration is done alongside 4.1/M9, **`trackId` is a required field, not an
optional nicety**, and `HandsTriggeredActions`'s `cube_owned_by(handedness)` moves
to it. Evidence: `analysis/t3_relabel_threshold.py`, `analysis/d2_bridge_ab.py`.

### 2.2.1 ✅ THE `trackId` WIRE MIGRATION IS BUILT (2026-08-22) — queue 4.1 / T3

§2.2's addendum required that when the migration happens with 4.1, **`trackId` is
a required field, not an optional nicety**, and that `cube_owned_by(handedness)`
moves to it. **Done.**

**⚠ DR-1 had no stable id to send — that had to be built first.** `HandTrack`
identified tracks only by LIST POSITION, and `HandIdentityTracker.update()`
rebuilds that list every frame as tracks age out. A monotonic `track_id` was
added, never reused, plus `tracker.last_track_ids` parallel to the observations.
⭐ Exposed as an ATTRIBUTE rather than folded into `update()`'s return, so the
existing callers (both tools and the analysis harnesses) keep working unchanged.

⚠⚠ **A real bug was caught while writing it, and it is the kind that would have
been silent**: the ids were first published AFTER the age-out filter, but
`obs_to_track` holds INDICES into `self.tracks` — and the filter rebuilds that
list, so every index after a removed track shifts by one. It would have attached
the wrong track's id to a hand, intermittently, only when a track ended.
Publication now happens BEFORE the age-out, with a comment saying why.

**The path, end to end:**

| step | where |
|---|---|
| stable id assigned | `hand_identity.HandTrack.track_id` (monotonic, never reused) |
| published per frame | `HandIdentityTracker.last_track_ids` |
| attached to each hand | `hands_visualizer.py` → `hand["trackId"]` |
| pulled per slot | `extract_hand_track_id()` — ⚠ **same lookup key** as the pixel and world extractors, so all three describe the same hand |
| sent | `Server.SendHandTracksPacket` → `{"type": "hand_tracks", "data": [left, right]}`, **before** the frame's `"hands"` packet |
| decoded | `PythonApp_Main` → `on_hand_tracks_frame()` |
| used | `HandsTriggeredActions._owner_key()` → `snap_cube` / `cube_owned_by` |

⭐ **`_owner_key()` returns the track id when there is one and the handedness
string otherwise.** ⚠ **The fallback is not optional**: with an older server, or
on a frame where DR-1 cannot resolve identity, ownership degrades to the old
behaviour instead of breaking. **A cube must never become unreleasable because an
id went missing.**

⚠ **`Cube.owner` is now an OWNER KEY, not a hand name** — compare it, never parse
it. Typed loosely on purpose.

⭐ **N6 parity kept**: `LiveSnapDebug.py` has the same `_owner_key`, reading the
ids straight off the in-process tracker instead of the wire. Same value, same
semantics.

**Verification**: `analysis/verify_track_ownership.py` (10 checks, exercising
production's own `_owner_key` and `CubeWindow`'s own ownership primitives — not a
reimplementation, per `VerifyChiralityFixture.py`'s reasoning). It proves the
headline case directly: **a relabel no longer orphans a held cube**, while a
genuinely different track still does not inherit it — the exact distinction the
reverted position-based fix got wrong. ⚠ It also pins that **id 0 is a valid
track**, not "absent"; a truthiness test instead of `>= 0` would break the first
hand of every session. Full suite 13/13 + chirality fixture PASS.

⛔ **NOT yet live-tested.** The T3 defect is measured at 113/205 spurious releases;
whether that number actually falls needs a live session, and `d2_bridge_ab.py` is
the harness that would show it.

### 2.2.2 ⭐ THE `trackId` MIGRATION IS MEASURED ON A LIVE SESSION (2026-08-22)

Session `2026-08-22_151348_t3_ownership_ab` — 1187 frames, 816 with a hand, ~48 s.
Rig: `LiveSnapDebug --ownership-ab`, two panels, **identical bridge config, one
camera, one detection, one identity resolution — ownership keying is the only
variable**. Harness: `analysis/t3_ownership_live_ab.py`.

| scheme | frames the held cube was orphaned **while the holding hand was still on screen** |
|---|---|
| LABEL (pre-4.1) | **794** |
| TRACK id (shipped) | **0** |

⭐⭐ **READ THE SHAPE, NOT THE SIZE.** There was exactly **ONE** relabel event in
the session. A relabel is a one-off with a **LASTING** consequence: once the
holding hand moves to the other slot it STAYS there, so that single flip left the
label-keyed cube orphaned for the remaining ~32 s of the hold. ⭐ **That is the
mechanism behind T3's 113-of-205 spurious releases — few flips, each permanent
until the operator re-grabs.**

⚠⚠ **A MEASUREMENT ARTIFACT WAS CAUGHT AND CORRECTED HERE — the first version of
this harness was WRONG.** It counted every frame on which the holding LABEL was
absent, and reported 779 vs 3. But that counts the operator putting the hand down
or switching hands, which **no ownership scheme can or should survive** — it is
not evidence about keying at all. The corrected metric counts only frames where
**the holding PHYSICAL hand is still on screen** (its track id is present), which
is the only place a failure to resolve means the key lost a hand it should have
kept. ⚠ The suspicious signal was the ratio itself: 779 of 816 hand-frames from a
single relabel is not a mechanism, it is a bug in the metric.

⭐⭐ **SECOND SESSION, MUCH STRONGER (2026-08-22)** —
`2026-08-22_152603_t3_ownership_ab2`, **3530 frames, 1703 with a hand (~2.2 min)**.
The owner provoked the failure properly this time: the DR-1 log is full of
`switch confirmed: 'Right' -> 'Left'` events.

| | session 1 | **session 2** |
|---|---|---|
| relabel events | 1 | **24** |
| ids | reconstructed by replay | ⭐ **read from the recording** |
| LABEL orphaned frames | 794 | **377** |
| TRACK orphaned frames | 0 | **0** |

⭐ **24 independent relabels, and the track-keyed cube was orphaned on ZERO of
them.** The label-keyed control lost the cube for 377 frames (~15 s cumulative)
while the holding hand was plainly still on screen. **This is the result 4.1/T3
was built for.** ⚠ Still n=1 SESSION — 24 events is a real sample of the
mechanism, not a population rate; do not convert it into a per-minute figure.

⚠ **Limits of this result, stated plainly:**
1. **n = 1 session, 1 relabel event.** The direction is unambiguous and the
   mechanism is understood, but the magnitude must not be quoted as a rate.
2. **It exercises the DEBUG tool's parity path**, which reads ids from the
   in-process tracker. **Production reads them off the wire** — same values, same
   semantics, different code path. ⛔ **A production run is still owed.**
3. Ids were **reconstructed by replay** rather than read from the recording,
   because `--record` stored no `trackId` at the time. Sound (DR-1 is
   deterministic on identical input) but weaker than stored evidence. ⭐ **Fixed:
   the recorder now writes `trackId`**, so future takes carry it.

### ⛔⛔ 2.2.3 THE STRANDED-CUBE BUG — INTRODUCED BY THIS MIGRATION, FOUND LIVE BY THE OWNER (2026-08-22)

**Owner, during session 2**: *"in the shipped window, at one point there was a
bug: the cube was indicated as grabbed but did not move at all and the free hand
could not grab it again."*

**Cause — the migration's own fallback, turned against it.** The release pass read
`cube_owned_by(_owner_key(handedness))`. When a hand's track ENDS,
`_hand_track_ids[hand]` becomes -1, so `_owner_key` degrades to the handedness
LABEL — but the cube is owned by an **int track id**, so the lookup misses,
`continue` runs, and release never fires. ⚠ **Track ids are monotonic and never
reused**, so the cube stays owned by an id that can never appear again:

| symptom | mechanism |
|---|---|
| "indicated as grabbed" | `owner is not None` → the snap border still draws |
| "did not move at all" | no live hand resolves to that owner key |
| "could not grab it again" | `unowned_cube_names()` excludes any owned cube |

⚠⚠ **THE LESSON: the fallback fires exactly when the id is missing, which is
exactly when release needs to find the cube owned by that now-absent id.** It was
described (in §2.2.1, and in the code) as a safety net; it was the defect. Under
the OLD label keying this was unreachable — **the migration introduced it.**

⭐ **FIX**: drive release from the **CUBES**, not from the current frame's owner
key, and govern each held cube by the tracker of whichever slot its owning TRACK
occupies now (`_owner_hand_of_cube`, refreshed per frame):

- **relabel** → the track changes slot, the governing hand follows → cube HELD
- **dropout** → track absent, the LAST governing hand is deliberately KEPT so its
  tracker coasts D2's 150 ms → then releases. ⚠ Clearing it here instead would
  release on the first missed frame and **undo Phase D**
- **track ends** → same path → the cube RELEASES instead of stranding

⚠ **Why the tests missed it**: `verify_track_ownership.py` checked that a
*relabel* keeps the cube, but never that a *track ending* releases it. The case is
now covered (it asserts the old lookup returns None while the cube is still owned
— reproducing the strand — that the governing hand is KEPT when the track vanishes,
and that it FOLLOWS a relabel). N6 parity kept in `LiveSnapDebug`, per-arm.

⚠ **A second instrumentation gap surfaced while verifying this**: `--record` stored
only `arms[0].cubes`, and in the ownership rig arms[0] is the LABEL control — so
the SHIPPED arm's cubes were the ones missing from the file, and no recording made
before this could answer the stranding question. **The recorder now stores every
arm**, and `analysis/t3_stranded_cube_check.py` measures the defect directly
(longest run of frames a cube is owned by a track present in no slot; a short run
is D2's coast working, a long run is the bug).

✅⭐ **THE FIX IS CONFIRMED FROM DATA (2026-08-22, session 4)** —
`2026-08-22_153609_t3_strand_check`, 1280 frames, only **398 with a hand** (the
operator repeatedly took the holding hand fully out of frame, which is the
protocol this defect needs). First recording able to answer the question, because
it stores **both** arms.

| arm | cube | longest run owned by an ABSENT track |
|---|---|---|
| `blend:label` | — | never owned by an absent track (string owners cannot strand) |
| **`blend:track`** | large | **4 frames** |
| **`blend:track`** | small | **5 frames** |

⭐ At 26.7 fps, D2's 150 ms coast is ~4 frames. So the cube is held briefly across
a dropout — **exactly the designed behaviour** — and then released. ⚠ Before the
fix the run would have continued to the END of the session. **No strand.**
⭐ The runs also prove the scenario was genuinely exercised: a cube must be GRABBED
before its hand can leave, so a non-zero run is itself evidence the test ran.

⚠ Still to do: the same confirmation on **production**, which reaches the ids over
the wire rather than in-process.

### 2.3 ✅ D1 AS BUILT (2026-08-21) — `Resources/hand_state.py`

| | |
|---|---|
| module | `Resources/hand_state.py` — stdlib only, numpy-free, **clock-free** (`now_ms` is injected, so it stays deterministic and golden-vector testable), same port contract as `palm_geometry.py` / `hand_blocks.py` |
| shipped fields | `tracking_state` → `quality.trackingState`; `frames_since_measurement` → `quality.framesSinceMeasurement`; `orientation_valid` → `quality.orientationValid`; plus two derived: `ms_since_measurement` (**the quantity D2 thresholds**) and `reacquired_after_ms` (**D3 needs the gap length after the counter has reset and cannot recover it otherwise**) |
| deliberately absent | `occlusionLevel`, `motionBlur` (nothing client-side measures them — a fabricated field is worse than an absent one) and every `palm.*` metric field (those need the wire migration, which is 4.1/M9's) |
| wired into | `Resources/HandsTriggeredActions.py` **and** `LiveSnapDebug.py`, in the same change, per §13.6.1 |
| verification | `analysis/verify_hand_state.py` (37 vectors, dependency-free — this is the artifact a port must reproduce) and `analysis/verify_d1_wiring.py` (production behaviour, needs pygame, kept separate so the golden vectors stay portable) |

⭐⭐ **`BRIDGE_WINDOW_MS` SHIPS AT 0.0 AND THAT IS THE DESIGN, NOT AN OVERSIGHT.**
With a zero window `BRIDGING` is unreachable, so `holds_track` is False on exactly
the frames `_is_detected` was False on, and **D1 changes no behaviour at all**.
What it buys is that the release decision and the filter resets now read a
tracking *state*; **D2 is then one constant plus the coasting pose.** Anyone who
raises this constant has shipped D2's behaviour change without D2's A/B —
`verify_hand_state.py` §2 fails if the default stops being 0.

⚠ **The reset gating is the subtle half.** The orientation filter, the Horn
reference constellation and DR-2's frozen sign are cleared on `SUSTAINED_LOST`,
**not** on "this frame missed". Those two coincide exactly today. The moment the
window opens they do not, and clearing them on the first missed frame would throw
away precisely the state a bridge coasts on — the bridge would resume from a cold
start, i.e. a visible pop replacing the drop it was built to remove.

✅ **`orientationValid` has landed.** DR-2 has computed it since 2.2 shipped and
`HandsTriggeredActions` discarded it every frame, with a comment naming this
contract as where it belonged. It is now recorded on the quality block. ⚠ It is
still read by **no rule** — that stays a separate, deliberate decision (see the
Rule below), and this is the field that would carry it.

### 2.4 ✅ D2 + D3 AS BUILT (2026-08-21) — and what the measurement found instead

**Shipped**: `BRIDGE_WINDOW_MS = 150.0`; `omega` zeroed on the resume frame;
`RESYNC_BLEND_FRAMES = 3` position lerp. Harness: `analysis/d2_bridge_ab.py`.

⭐ **The window is 150 ms because the measured median true-dropout gap is 128 ms**
— 2–3 frames at this pipeline's 14–24 fps. 300 ms buys 9 more saves for 2 more
pops and triples the worst added hang; **the hang is the ceiling, not the ratio**,
because a long enough window stops being sensor bridging and becomes D4/M10.7's
grace period, which the owner gated.

| of 83 true dropouts, at 150 ms | |
|---|---|
| SAVED (hand returns in time, cube barely moves) | **39** |
| POP (returns in time, cube jumps > 1 palm width) | **19** |
| LATE_RELEASE (released anyway, ≤ 150 ms later) | **25** |

⚠⚠ **THE POP CLASS IS WHY D3 SHIPS WITH D2 AND NOT AFTER IT.** Bridging alone does
not remove a defect — it **trades a drop for a jump**, and the jump is §14.1.4's
teleport. Replayed over the hand's real post-gap trajectory (not modelled — the
hand keeps moving during the blend), the 3-frame blend takes the **worst
single-frame cube step from median 0.62 → 0.38, p90 1.95 → 0.87, max 2.47 → 1.49
palm widths, making 3 of 47 resumes worse.** Those 3 are reported, not hidden.

⛔ **"Confidence-scaled follow" (the source document's §3.7) needed nothing built.**
Position has no follow to scale — `set_target_position` assigns exactly, so a
skipped frame IS a frozen cube, which is also why "hold the last value" cost zero
lines. Orientation's follow is `_reliability_alpha`, shipped since §13.7.

⭐⭐ **AND THE HARNESS FOUND SOMETHING BIGGER THAN THE ROW IT WAS WRITTEN FOR.**
Classifying all 205 spurious cube releases by cause: **83 are dropouts, 113 are
the owner's hand reappearing under the other handedness label, 9 are a different
hand.** Ownership is keyed by label, so any relabel orphans a held cube — **that
is queue T3, it is the LARGEST cause, and DR-1 was running in every one of these
recordings.** T3 is re-opened; the proposed fix is to key ownership on the DR-1
track rather than the label. ⚠ **Bridging hides relabels cleanly (pop/save 0.00)
and that is precisely why it must not be used to "fix" them.**

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

> ## ⚠ AMENDED 2026-08-03 (§0.15) — the "STOP" warning is LIFTED; build with the amended parameters
>
> **The earlier warning here ("the motion model is WEAK — 60% of one-frame
> predictions disagree by >25°") was an ARTIFACT** of a closed-loop cascade
> statistic and contaminated streams. **Retracted — see §0.13.3's retraction box.**
>
> **The required first task is now DONE** (§0.15, `audit_jump_provenance.py`),
> measured open-loop on DR-1 identity-corrected streams:
>
> | horizon | median | mean | p90 | >25° |
> |---|---|---|---|---|
> | **1 frame (~42 ms)** | **4.2–4.5°** | 8.6–12.6° | 18.6–28.4° | **6.4–11.4%** |
> | 2 frames (~83 ms) | 7.3–8.0° | 15–20° | 34–51° | 15–20% |
> | 3 frames (~125 ms) | 10.8–11.8° | 21–26° | 51–72° | 25–29% |
>
> **Verdict: the model is fit to extrapolate ONE frame, not two.** That matches
> the published envelope independently (~30–50 ms usable, artifacts clearly
> perceived by 75 ms — §10.4/S2). Amendments to steps 2–5, all in **S2**:
> robust/filtered derivative before extrapolating; speed-gated horizon with a
> dead-band; damped extrapolation with a shorter orientation horizon; post-filter
> the prediction; prefer LaViola double-exponential smoothing over a Kalman
> predictor. **S3 additionally forbids predicted state reaching a gesture state
> machine.** Cap the horizon at ~40 ms, not the 80 ms step 4 currently states.
> *(This is orientation prediction; position prediction is still unmeasured and
> expected to be more benign — measure it as part of 3.1.)*
>
> *Substrate note: the motion model, `omega` as a public state, and
> `predict_forward()` already exist in the parked `Resources/orientation_filter.py`
> (§0.13.1) — but that `omega` is a decayed finite difference, which is exactly
> what S2(a) says not to extrapolate raw. Filter it first.*

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

## 10. ADDENDUM (2026-08-03) — state-of-the-art audit
### *(placed after §9's bibliography in reading order; §9 remains the historical background list)*

Produced with the §0.15 measurement audit, per owner request: compare the spec and
the build record against (a) Google/MediaPipe's own publications and source, (b)
2023–2026 monocular hand-pose SOTA, (c) prediction/latency-compensation
literature incl. VR industry practice and AV motion forecasting (Waymo). Each
adopted item carries a **Build at** step referencing the merged queue
(`PART_ONE.md` §3.1). Sources at the end of each block.

### 10.1 What the spec already gets right (external confirmation — no action)

- **"Treat MediaPipe as a noisy sensor and build the estimator around it" is
  exactly how shipping systems work.** Meta (MEgATrack/UmeTrack), Ultraleap and
  Apple all use temporal state fed into the tracker plus forward prediction;
  none relies on per-frame estimation alone. A raw MediaPipe pipeline is the
  outlier, not the norm.
- **DR-1 is correct practice, confirmed at the source.** MediaPipe's handedness
  is a per-frame appearance classification head of the landmark CNN (Zhang et
  al. 2020); **no persistent hand identity exists in any MediaPipe API** — the
  Tasks API's `min_tracking_confidence` is only an IoU association threshold.
  Track-level identity by position is the standard community remedy. The
  mirrored-input handedness convention (§0.9, §13.6.1) is documented verbatim in
  Google's docs.
- **DR-2's premise is confirmed as fundamental.** HandFlow (VMV 2022) shows the
  edge-on/depth-sign family of configurations is genuinely ill-posed for one
  RGB view — the posterior over poses is multimodal, and no per-frame fix
  exists. Meta's stated reason for multi-camera rigs is exactly this. Freezing
  + suppressing (DR-2) and motion carry-through (M5e) are the right class of
  answer for a single camera.
- **M9's ratio-form depth is the right call.** Absolute camera-space hand
  position from monocular RGB is ~3.5 cm state-of-the-art per frame (ScaleHP
  2026; RootNet lineage); relative scale-ratio control needs only temporal
  consistency of one anchor length. Palm width is the documented anchor of
  choice (near pose-invariant). **One addition — see 10.4/S10.**
- **MediaPipe applies NO smoothing to hand landmarks** — verified in both the
  legacy graph and the Tasks graph. Every filter this project ships operates on
  genuinely raw output; nothing is redundant with upstream.

*Sources: arXiv 2006.10214; MediaPipe hand_landmark_tracking_cpu.pbtxt +
hand_landmarker_graph.cc (no smoothing calculators); Tasks docs
(min_tracking_confidence = IoU); HandFlow handtracker.mpi-inf.mpg.de; MEgATrack
SIGGRAPH 2020; UmeTrack SIGGRAPH Asia 2022; arXiv 2606.25619 (ScaleHP); arXiv
1907.11346 (RootNet); arXiv 2504.01888 (palm-width anchor).*

### 10.2 Corrections to spec premises, from Google's own record

1. **M2's premise-death (§0.14/§0.15) is documented sensor behaviour, not a
   surprise.** `worldLandmarks` are produced by fitting the statistical **GHUM**
   hand model to 2D annotations — a near-average-hand reconstruction with
   documented mean 3D error of **1.3–1.5 cm** (~15% of a palm), with focal
   length *assumed* when unknown. A pose-consistent personal skeleton was never
   in this signal. There is also an **open, Google-acknowledged issue: palm/MCP
   world landmarks collapse when the back of the hand faces the camera**
   (#5156) — matching both §0.15's worst offenders (`known_*_back`) and T1.
2. **The z of screen landmarks was trained on synthetic data only** (paper,
   verbatim) — reinforcing anti-pattern #3 with a documented mechanism.
3. **Google's own production One Euro tunings exist** (MediaPipe Pose filtering
   graph): screen landmarks `min_cutoff 0.05, beta 80`; world landmarks
   `min_cutoff 0.1, beta 40, disable_value_scaling`. These are the reference
   starting parameters for any One Euro use here (10.4/S4).

*Sources: TensorFlow blog Nov 2021 (3D hand pose / GHUM); arXiv 2111.00038
(Sung et al. 2021 — also documents the improved 2021 landmark model and the
two-vector ROI rotation scheme); github issues #5156, #3156, #742;
pose_landmark_filtering.pbtxt.*

### 10.3 The redirect after §0.13.2/§0.15, grounded in literature

The corrected finding stands: ~75% of large orientation jumps occur in
well-observed frames, i.e. **bad landmark frames, not pose-filter failures**.
SmoothNet's published analysis of pose estimators says exactly this: errors are
"highly unbalanced" — most frames fine, failures are large deviations over
short runs. The field's remedies, in cost order: (1) consistency-cue outlier
gating inside a recursive filter (never per-frame confidence scores, which are
documented as poorly calibrated for exactly these failures); (2) anatomical
validity constraints; (3) skeleton-constrained fitting; (4) small learned
temporal networks. These are S5–S7 and S9 below and they replace the broken
"redirect to 1.4" (M2 is dead and cannot supply the error signal).

### 10.4 Adopted improvements — each with its build step

> Numbering S1–S12 (S≠A to avoid clashing with §0.1's amendment log). Ordering
> follows the queue, not importance.
>
> **⚠ These are NOT a second TODO list.** All twelve are folded into the merged
> queue at `PART_ONE.md` §3.1, which carries an S→row index and remains the only
> list to follow. What lives here is the *rationale and sources*; what lives
> there is *what to build next*. S1→0.4, S2/S3/S4→3.1, S5→1.6, S6→1.5, S7→1.7,
> S8→0.5, S9→5.4, S10→4.1, S11→5.5, S12→3.4.

**S1 — Predictor evaluation harness: side-effect metrics + mandatory baselines.**
Adopt Nancel et al.'s perceptual side-effect metrics (lateness, over-anticipation,
wrong orientation, jitter, jumps, spring) for any prediction work, and require
every predictor to beat **zero-velocity and constant-velocity baselines per
horizon** — the AV literature's hard-won discipline (a constant-velocity model
beat published LSTMs; zero-velocity beat published human-motion models).
§0.15's horizon table is the seed. **Build at: 0.1 / first task of 3.1.**
*Sources: UIST 2016 Nancel; arXiv 1903.07933 (Schöller); Martinez CVPR 2017.*

**S2 — M7 prediction, amended parameters (replaces M7 steps 2–4 as written).**
The convergent published envelope for kinematic prediction on noisy vision
signals is **~30–50 ms usable, hard ceiling < 80 ms** (Azuma; Meta's 20–40 ms
operating range; TurboTouch's best-in-class 32–48 ms; artifacts clearly
perceived at 75 ms). At 24 fps that means: **predict ONE frame, never two**;
hide ~40 ms and accept the rest. Mechanics, in priority order, all documented
practice: (a) **robust derivative first** — never extrapolate a raw two-sample
difference; low-pass ω/v before predicting (TurboTouch's 2–3× horizon gain came
mostly from this); (b) **speed-gated horizon with a dead-band** — prediction
OFF below ~0.03 rad/s, τ ramping with speed to the cap (shipped Oculus design);
(c) **damped extrapolation** (λ ≈ 0.3–0.5 on the extrapolation term), orientation
horizon shorter than position (hypothesis to measure, motivated by §0.15's
horizon table); (d) **post-filter the predicted signal separately**; (e) use
**LaViola double-exponential smoothing** as the predictor form — published
≈equivalent accuracy to Kalman predictors at ~1/135 the cost, degrades to
smoothing as τ→0. **Build at: 3.1.**
*Sources: cs.unc.edu/~azuma/s95paper.pdf; Meta "Latent Power of Prediction";
US9063330; UIST 2018 TurboTouch; LaViola 2003.*

**S3 — Split predicted-for-rendering from smoothed-for-gestures (Apple's shipped
design).** visionOS exposes exactly two hand streams: *predicted* (rendering /
attachment, "at the expense of some accuracy") and *continuous/unpredicted*
(gesture detection). Amendment to M7's channel split: the MOTION channel feeds
triggers, but **predicted state must never reach a gesture state machine** —
prediction artifacts must not latch. This subsumes and sharpens M7's existing
FORM/MOTION rationale, and the split is worth building **even if prediction is
skipped entirely**. **Build at: 3.1.**
*Source: WWDC24 "Create enhanced spatial computing experiences with ARKit".*

**S4 — One Euro on the FORM channel, Google's tunings as the starting point.**
The FORM (rendering) channel's smoother should start from MediaPipe Pose's own
production parameters (10.2.3) rather than guesses. Note the documented
limitation: One Euro trades jitter/lag only — **it does not reject glitches**
(a large excursion looks like fast motion and is followed). Glitch rejection is
S5's job; do not tune One Euro to do it. **Build at: 3.1 (FORM channel).**
*Sources: CHI 2012 1€ filter; pose_landmark_filtering.pbtxt.*

**S5 — Consistency-gated frame rejection (M4's revised core, and the T1/T2
redirect).** Per-frame confidence is documented as poorly calibrated for
well-conditioned-pose failures; the field gates on **consistency cues**:
bone-length deviation (as a *gross* outlier flag at the ~6–10% precision the
sensor actually supports — not M2's dead 2%), frame-to-frame
velocity/acceleration plausibility, palm-pixel-width collapse, and anatomical
validity (S6). Rules learned from §0.13.3/§0.15, binding: compare candidates
against the **last accepted measurement**, cap consecutive rejections at 1–2
frames (anti-cascade — the χ² gate's cascade is what manufactured its own
failure), evaluate **position first** (the Object Jump metric; the χ² verdict
condemned orientation gating only). **Build at: 1.6 (M4), rescoped.**
*Sources: arXiv 2112.13715 (SmoothNet, failure structure); arXiv 2605.02708
(outlier-rejecting temporal recursion for 6D pose).*

**S6 — Anatomical validity from published constraint sets (M3a, upgraded
priority).** Spurr et al. (ECCV 2020) show biomechanical constraints (joint
limits, unidirectional flexion, planar articulation) **halve depth error** on
FreiHAND — the single strongest published lever on exactly the depth-error
family behind T1/T2 — and a reusable PyTorch constraint set exists
(Hand-BMC-pytorch). Use violations as (a) the per-frame validity bit feeding
S5, (b) the bas-relief disambiguation term M5 already specifies. With M2 dead,
**M3a is now the primary "attack the source" item — build it before any T1/T2
retest.** **Build at: 1.5.**
> ✅ **BUILT 2026-08-04 — see §0.16.** 0.00% false positives on the control;
> 5–59% on the failure poses. ⚠ **Two corrections to this item as written:**
> (1) the reusable constraint set is **not** reusable here — Hand-BMC-pytorch is
> MIT but ships no values, generating them from research-licensed datasets, and
> the paper publishes no table; §0.16 uses **clinical goniometry norms** instead.
> (2) The unidirectional-flexion prior applies to the **PIP↔DIP pair only** — the
> MCP legitimately extends while the IPs flex, measured at 31.1% "violation" on
> valid hands when included.
*Sources: arXiv 2003.09282; github MengHao666/Hand-BMC-pytorch.*

**S7 — NEW MODULE M2b: impose a skeleton instead of measuring one
(fixed-skeleton constrained IK / MANO-lite fit).** The literature's answer to
"worldLandmarks are not length-consistent" is not better averaging — it is
fitting a **fixed-bone-length kinematic model** to the landmarks each frame, so
lengths are consistent *by construction* (MANO's raison d'être; documented
precedents fit to 2D keypoints with bone-length preservation, warm-started
~few LM iterations/frame, plausibly a few ms in Python). Deliverables: a
pose-consistent 21-point skeleton, clean joint angles for M3, a better-
conditioned orientation source, and the **per-session scale reference M9
needs** — everything M2 was supposed to supply, from a mechanism that cannot
have M2's failure mode. Population-average proportions suffice to start (§2f's
own point); per-user refinement optional. **Build at: NEW queue item 1.7, after
1.5/1.6, before 4.1 (M9); T1/T2 retest after it.**
*Sources: ACM PETRA 2023 (MANO to 2D keypoints); arXiv 2409.13347 (V-Hands);
Aristidou 2010/2018 constrained IK; arXiv 2605.09258 (2026, biomechanical IK on
foundation models).*

**S8 — ~~Offline oracle for the corpus~~ — DROPPED 2026-08-04, do not restart.**
Standard evaluation trick in this literature: run a heavyweight offline model
(HaMeR or WiLoR) over the recorded sessions to produce pseudo-ground-truth,
giving S5/S6 gates something to be tuned against that is not MediaPipe judging
itself. **Killed by two independent blockers, one permanent:**
**(a) Licensing, decisive** — both models depend on **MANO**, licensed for
non-commercial scientific research only (commercial licensing is separate, via
Meshcapade). This project is intended for commercial release, so MANO is out
even for offline tooling that never ships (queue **N13**).
**(b) The corpus has no pixels** — the entire capture root is landmark JSON,
**zero image bytes**, and no recorder ever wrote frames, so "over the 24 recorded
sessions" was never achievable at any budget (queue **N14**).
**Commercially-clean substitutes if an external reference is ever needed:**
ArUco/ChArUco fiducials (BSD, `opencv-contrib-python` already installed, and they
give REAL ground truth rather than pseudo — the corpus plan already pencils in a
fiducial take for item 3.3), or RTMPose-Hand (Apache-2.0, but 2D keypoints only,
so it cannot bound the depth errors behind T1/T2).
⚠ **Consequence for S5/S6: their gates have no external referee and will not get
one.** That is why §0.16's constraint thresholds are clinical norms rather than
corpus-fitted values — with 0.5 gone, nothing would catch the circularity.
*Sources: arXiv 2409.12259 (WiLoR); CVPR 2024 HaMeR.*

**S9 — Causal SmoothNet-class refinement (learned upgrade path).** If S5+S6
leave residual glitch tail, the documented next step is a tiny per-joint
temporal MLP (SmoothNet): plug-and-play, transfers across estimators, fixes
exactly the short-run large-deviation failures — but verify the causal-mode
accuracy drop (paper ablation) and window latency first. **Build at: NEW Phase
5 item 5.4 — only after 1.5/1.6/1.7 are measured.**
*Source: arXiv 2112.13715.*

**S10 — M9 amendment: gate Z on the edge-on band.** The palm-width pixel anchor
collapses edge-on; the depth ratio must freeze (reuse DR-2's tracker pattern)
while `edgeOnMeasure` is in the band, else Z-control inherits the crossing
failure. One sentence, but absent from §14.3 and M9 as written. **Build at:
4.1/4.2.**

**S11 — Multi-hypothesis prediction & tracking (Waymo's transferable core,
minimal form).** What transfers from MultiPath++/MotionLM is a *principle*:
predict distributions, not points, and keep discrete hypotheses where the
future genuinely branches. Honest non-transfers: their data scale, 3–8 s
horizons, lane-graph context, GPU inference — all inapplicable at 40 ms on a
CPU; and at short horizons their own literature shows physics baselines win.
Minimal adoptable forms: (a) prediction emits a variance growing with horizon
and recent residual, used as the render blend weight (cheap MultiPath++);
(b) 3-mode reversal blending {continue, decelerate, reverse} weighted by
acceleration-sign consistency — targets exactly the overshoot-on-reversal
failure; (c) research option: carry the mirror (bas-relief) pose hypothesis
through the DR-2 band and let motion continuity select on exit (HandFlow's
thesis, applied). **Build at: NEW Phase 5 item 5.5 — after S2 ships and only if
its measured side-effect metrics (S1) justify more machinery.**
*Sources: arXiv 2111.14973 (MultiPath++); arXiv 2309.16534 (MotionLM); arXiv
2307.08243 (USST); HandFlow.*

**S12 — Endpoint/intent prediction (the brain-mimicking layer, correctly
placed).** Minimum-jerk models predict *where a ballistic reach ends*, not the
next frame: published results are ~0.8 cm at 100 ms for ballistic VR reaches
(min-jerk-derived model), and endpoint prediction needs ~50% of the movement
observed. That is an **intent** signal — pre-arm snap/grab, choose the target
object — not a render-latency tool. It is the published version of M8c's
"anticipatory grip" idea and lands in the same place. **Build at: 3.4 (with
M8c, still blocked on the aperture gesture design §14.2).**
*Sources: UIST 2021 Gamage "So Predictable!"; CHI 2007 Lank; CHI 2014 Pasqual &
Wobbrock (kinematic template matching).*

### 10.5 Explicitly considered and NOT adopted

- **Replacing MediaPipe with HaMeR/WiLoR/Hamba-class models live**: none is
  CPU-real-time; MobRecon-class is the only plausible family and would be a
  platform rewrite. Offline use only (S8). Revisit for the web/mobile port only
  if MediaPipe proves insufficient there.
- **Learned trajectory predictors (LSTM/transformer/diffusion) for latency
  hiding**: repeatedly beaten by simple baselines at short horizons in
  published comparisons; inference cost eats the frame budget. Revisit only
  after S1–S3 ship and an intent layer exists.
- **Two-thirds power law as a predictor**: constraint/sanity check at most; no
  published use as an interface predictor found.
- **MediaPipe Holistic switch** (body-pose-conditioned hand ROI): Google's own
  answer to hand-ROI instability, but a pipeline swap with unknown fps cost on
  this hardware; note kept here for the day T1-class failures dominate again.
  Not queued.

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

### 9.1 Added by the §10 addendum (2026-08-03) — the sources behind S1–S12

**Sensor (what MediaPipe actually is):**
- Zhang et al. (2020) — *MediaPipe Hands*, arXiv 2006.10214. Palm detector + landmark model; **handedness is a per-frame appearance classification head**; screen `z` trained on synthetic data only.
- Sung et al. (2021) — *On-device Real-time Hand Gesture Recognition*, arXiv 2111.00038, + TensorFlow blog Nov 2021. **World landmarks come from fitting the GHUM model to 2D annotations; documented mean 3D error 1.3–1.5 cm**; focal length assumed when unknown.
- MediaPipe source: `hand_landmark_tracking_cpu.pbtxt`, `hand_landmarker_graph.cc` (**no smoothing anywhere in the hand graphs**); `pose_landmark_filtering.pbtxt` (**Google's own One Euro tunings**); Tasks docs (`min_tracking_confidence` = IoU association, **no persistent hand ID in any API**).
- Open issue #5156 — **palm/MCP world landmarks collapse when the back of the hand faces the camera** (T1's failure mode, unfixed upstream). Also #3156, #742, #3047/#4785 (handedness).

**Estimator quality (S5–S9):**
- Zeng et al. (2022) — *SmoothNet*, arXiv 2112.13715. Pose-estimator error is "highly unbalanced": large deviations over short runs, not white noise.
- Spurr et al. (2020) — *Biomechanical constraints*, arXiv 2003.09282. **Joint-limit + flexion-direction constraints halve depth error** on FreiHAND.
- MANO-to-2D-keypoint fitting (ACM PETRA 2023); V-Hands (arXiv 2409.13347); Aristidou (2010/2018) constrained IK; arXiv 2605.09258 (2026) biomechanical IK on foundation models — the S7 lineage.
- Pavlakos et al. (2024) *HaMeR*; Potamias et al. (2025) *WiLoR*, arXiv 2409.12259 — offline oracle candidates (S8).
- Wang et al. (2022) — *HandFlow*, VMV 2022. The **edge-on/bas-relief configuration is genuinely ill-posed**; the pose posterior is multimodal.

**Prediction and latency (S1–S4, S11, S12):**
- Azuma & Bishop (1995), SIGGRAPH — prediction error grows with interval **and signal frequency**; effective only below ~80 ms.
- LaValle, *The Latent Power of Prediction* (Meta) — constant-rate vs constant-acceleration error tables; **recommended 20–40 ms operating range**.
- Nancel et al. (2016), UIST — **perceptual side-effect metrics**; over/undershoot clearly perceived at 75 ms compensation.
- Nancel et al. (2018), UIST — *TurboTouch*: robust derivative + speed-gated smoothing + post-filtering; **usable to 32–48 ms, 2–3× further than prior art**.
- LaViola (2003) — **double-exponential smoothing ≈ Kalman accuracy at ~1/135 the cost** for predictive tracking.
- Oculus patent family US9063330 — **velocity-gated prediction with a dead-band and a ramped horizon**.
- Apple WWDC24, ARKit `handAnchors(at:)` — shipped **predicted-for-rendering vs unpredicted-for-gesture** split (S3).
- Gamage et al. (2021), UIST — *So Predictable!*: minimum-jerk-derived hand trajectory prediction, ~0.8 cm at 100 ms for **ballistic** reaches. Lank et al. (2007) CHI; Pasqual & Wobbrock (2014) CHI — endpoint prediction (S12).
- Varadarajan et al. (2022) *MultiPath++*; Seff et al. (2023) *MotionLM* (Waymo) — **predict distributions, not points**; learned anchors; intent conditioning (S11's transferable core).
- Schöller et al. (2020) RA-L — **constant velocity beats LSTM/SR-LSTM**; last-step motion carries 68% of the signal. Martinez et al. (2017) CVPR — **zero-velocity baseline beat published learned models**. *(Together: S1's mandatory baselines.)*
- Han et al. (2020) *MEgATrack*, SIGGRAPH; Han et al. (2022) *UmeTrack*, SIGGRAPH Asia — detection-by-tracking and temporal fusion; multi-view exists precisely for degenerate/occluded views.
- Mueller et al. (2026) *ScaleHP*, arXiv 2606.25619; Moon et al. (2019) *RootNet*, arXiv 1907.11346; arXiv 2504.01888 (palm-width depth anchor) — the S10/M9 evidence.
<!-- VERBATIM-END -->
