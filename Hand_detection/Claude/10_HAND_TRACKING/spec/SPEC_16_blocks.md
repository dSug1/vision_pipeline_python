<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/GESTURE_PIPELINE_SPEC.md lines 5332-6824
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 15. Perception-layer spec integrated (2026-08-02) — the current direction

A design spec for the **hand-perception stack below the gesture layer** was
written by the owner and integrated into the pipeline on 2026-08-02:
**`Claude/PERCEPTION_LAYER_SPEC.md`**. Read it alongside this document —
this file remains the authoritative record of *what failed and why*; that
one is the *forward* design intended to fix it.

**Why this is a direction change worth flagging.** Everything in §13-§14
treated MediaPipe's output as the signal and built gesture logic directly
on it, fixing failures one at a time as they were found live. The
perception spec reframes MediaPipe as a **noisy sensor** and inserts an
estimator layer (L0-L6) between it and the gesture logic, with a versioned
`HandState` contract at the boundary. Several open TODOs in this document
are consequences of that missing layer rather than independent bugs.

**The merged build queue is `PART_ONE.md` §3.1** — the single ordered TODO
list covering both this document's TODOs and the spec's modules. It
supersedes §14's build order and the handoff's own queue.

**Amendments made on integration** (full log in the spec's §0.1 — the
short version, because these correct claims a reader of the spec alone
would get wrong):

- **A1 — retargeted from JavaScript to Python.** The spec was written
  against `gestureConfig.js`/Three.js. That does not exist: `Web/` holds
  only Part Zero-bis, and every Part One gesture is Python. Perception is
  built in `Local_pc/`; `HandState` v2 becomes the versioned **socket wire
  contract**, which doubles as the cross-platform contract a mobile
  rebuild reimplements against.
- **A2 — M5a/M5b are already built.** `_is_thumb_outward()`'s signed cross
  product is byte-identical to the spec's signed-palm-area cue, and its
  per-handedness negation is exactly the chirality factoring. New work is
  DR-1, the `K` fixture test, `edgeOnMeasure`, and DR-2.
- **A4 — M6a is already satisfied.** No Euler angles have ever been in the
  estimation path (`PART_ONE.md` §2 forbids it). Verify and tick.
- **A5 — M4 is scoped to occlusion/outliers, not the pitch crossing.**
  §13.7 recorded that per-landmark selection and averaging schemes are
  statistically indistinguishable at the degenerate frames, because the
  residual is a *correlated* whole-knuckle-row distortion. M6c's
  anisotropic covariance is the mechanism for that failure; M4 is not.
  Do not read a null M4 result there as an implementation failure.
- **A6 — M6 subsumes `HandOrientationFilter`; deleting it is a
  deliverable.** This closes §13.7.1's open "re-test the filter for
  redundancy after a more fundamental fix lands" TODO with a concrete
  trigger.
- **A7 — M8a (palm anchoring) is NOT adopted.** It contradicts §14.1's
  shipped, verified, live-confirmed mechanism, and the pipeline docs
  govern. It is logged as an **A/B candidate** to be measured once M6/M9
  land — because the stated reason for rejecting a palm-anchored design
  (a 2D/3D coordinate mismatch) will no longer hold then. **Do not modify
  §14.1 before that A/B runs.** The spec's anti-pattern #6 ("never anchor
  to fingertips") is downgraded accordingly.
- **A8 — M9 is the concrete fix for §14.1.1's yaw/palm-sinking
  limitation**, whose recorded remedy was an unspecified "startup Z-axis
  calibration." M9's foreshortening correction, using M5a's
  `edgeOnMeasure` as the `|cos θ|` term, is that idea made specific.
- **A9 — §14.1.4 Object Jump Correction now has a fix path.** It was
  absent from the spec's own mapping. DR-1 removes the per-frame identity
  decision that is its structural cause; M4's χ² innovation gate would
  reject the recorded 509 px excursion. Re-test after Phase 2 rather than
  treating it as independent work.
- **A10 — kill-criterion (binding).** Every module must show measured
  improvement on the M0 metrics via replay A/B, or be **reverted**. This
  is the spec's own §7.1 rule elevated to a removal rule, and it is what
  reconciles the spec's substantial machinery with the owner's standing
  preference against accumulating filters that do not earn their keep. The
  precedent is already set: the first Object Jump Correction fix attempt
  was built, measured, found to make no difference, and discarded rather
  than shipped (§14.1.4).

**Two items the spec surfaces that are game-design decisions, not
perception work** — both need the owner, and neither should be introduced
as a side effect of building a module:

1. **M10.7 proposes a ~400 ms grace period on tracking loss.**
   `GAME_RULES.md` rule 2 currently drops the object immediately, and that
   behaviour is built and live-verified. Changing it is a rule change.
2. **§14.3's 3D snap gating is underspecified**: what happens when
   `depthValid` is false at the moment of snap — fall back to 2D
   proximity, or refuse to snap? Not decided.



## 16. THE BLOCK REPRESENTATION (owner design, 2026-08-04) — the current direction

**Owner's formulation**, recorded verbatim because the framing is the
contribution: *"what really matter on the hand are 6 blocks: the palm, and each
of the 5 fingers arcs. The information is contained there, not in the individual
positions of each knuckle landmark... There is no added value to know all the
specifics of a finger knuckles, and each finger may be grouped as an arc which is
more or less extended or bent."*

    palm    : transform -- 2D position, rotation quaternion, scale (z = 0 for now)
    fingers : 5 arcs, each an offset child of the palm transform plus a single
              "arc deployment" scalar (how extended / how bent)

### ⭐ Why this is adopted: the corpus already measured both halves

This is not a plausible idea being tried — it is the representation the data has
been pointing at all along. Both claims were measured **before** they were
proposed:

| claim | measurement | where |
|---|---|---|
| "the palm is one block" | palm rigidity **2.76 mm**, already at target, vs 13–32% CV on distal bones | §0.2 |
| "a finger is an arc, not 3 knuckles" | `dot(PIP axis, DIP axis)` **0.0% negative over ~29,000 hand-frames, min +0.41, p05 +0.69** — PIP and DIP *always* co-flex | §0.16 (item 1.5) |

That second number is the strong one: a finger's bend is essentially **one degree
of freedom**, not three, with an enormous empirical margin. The "arc deployment"
scalar is exactly that quantity.

It also has a name and a home in the literature — **postural synergies**, queue
item 5.1 / M3b, where ~2–3 components are published as explaining most grasp
variance. This is a structured, interpretable instance of it.

**And it reframes three open failures as one cause.** T4 (yaw/palm-sinking), T3
(Object Jump) and N12 (held cube jumps as the hand crosses the horizontal) are
all cases where **noisy per-landmark detail leaked into a quantity that should
have come from the rigid part of the hand**. The block model makes that leak
structurally impossible rather than filtering it afterwards — which matters,
because §0.18 showed filtering, gating and constraining all fail here.

### Scope — deliberately narrow (owner, 2026-08-04)

- **Applies to the GRAB, ROTATE and TRANSLATE signals only.** Future gestures may
  legitimately need raw landmarks; this is not a global replacement for them, and
  the landmark stream stays available.
- **The thumb stays as RAW LANDMARKS for now.** Its CMC is a saddle joint with
  two coupled axes, so "more or less bent" does not describe opposition — the
  same reason M3a excluded it (§0.16). What to do with the thumb is deferred, not
  answered.
- **Stdlib, numpy-free, no side effects, and transportable to the web port** —
  same contract as `palm_geometry.py` / `hand_identity.py`, with golden vectors
  before the port exists (the discipline established in queue U3, which caught a
  real banker's-vs-half-up rounding divergence).

### Why this is the right substrate for prediction

Predicting **6 low-DOF blocks** is far more tractable than 21 noisy points, and
the parent/child structure means palm motion is not re-predicted per landmark.

⭐ **The specific hypothesis worth testing, which item 1.6 lacked:** the recorded
Object Jump is MediaPipe reporting *a different physical hand* under the same
label (§14.1.4). So a teleport should show a large palm displacement **together
with a discontinuous jump in the arc vector** (a different hand, in a different
pose), whereas genuine fast motion shows large palm displacement with
**continuous arcs**. That is a two-channel signature, and it is exactly what
single-channel position innovation could not provide — 1.6 was measured to reject
**4 real fast movements per teleport caught, at every threshold**, because at
this input envelope a teleport and a fast movement are the same signal
(§0.17).

⚠ **This hypothesis is NOT yet evidence.** It must be proven the way 1.6 was
disproven: **classify what gets rejected, never merely count it** (§0.18's
binding rule). A richer state may separate them; that is a measurement, not a
conclusion.

### 16.1 B1 built, B2 measured (2026-08-04) — the anchor claim holds, the outlier claim does not

`Resources/hand_blocks.py` + `analysis/b2_block_separability.py`. Palm
centroid/scale verified against `hand_identity` **29,164/29,164**.

**⭐ THE DECISIVE RESULT — anchor stability, §14.1's 9 points vs the palm**
(frame-to-frame anchor movement in palm widths):

| band | n | §14.1 p50 | §14.1 p95 | palm p50 | palm p95 |
|---|---|---|---|---|---|
| edge-on (<0.15) | 353 | 0.065 | **0.925** | 0.058 | **0.699** |
| near (0.15–0.35) | 617 | 0.083 | 0.425 | 0.065 | 0.390 |
| open (>0.35) | 28,144 | 0.038 | 0.235 | 0.027 | 0.169 |

**The palm is a quieter anchor by ~25–30% in every band.** That is real, it is
consistent, and it is the first positive result for the block model — **B4 (the
3.3 A/B) is worth running on this evidence.**

⚠ **But it does NOT remove the edge-on spike**: both anchors still jump ~4× when
the palm goes edge-on (palm p95 0.169 → 0.699). So **N12 would be REDUCED, not
eliminated**, by palm anchoring. The residual is §0.18's documented floor — at
edge-on the palm reconstruction itself collapses, so there is no quieter point on
the hand to anchor to. DR-2's freeze pattern remains the right answer for that
band, not a better anchor.

**⚠ THE TWO-CHANNEL OUTLIER HYPOTHESIS (B6) IS NOT SUPPORTED BY THIS DATA.**

- **Teleport separability: INCONCLUSIVE, not negative.** Only **3 teleports
  survive in 29,164 frames**, far too few to test anything — and that is itself a
  finding: `build_v2` replays DR-1, **DR-1 is the fix for Object Jump**, so the
  identity-teleport population is largely already gone. It is indirect support
  for T3 being closed.
- **At edge-on, arcs give no distinctive signature.** Both channels degrade by
  about the same factor (palm p95 0.158 → 0.320; arc p95 0.104 → 0.185), so
  "palm moves while arcs stay continuous" does not hold in the band that matters
  for N12.

**Consequence for the plan**: the *representation* earns its place on the anchor
result; the *outlier gate* does not yet have evidence and must not be built on
the strength of the idea. Testing it properly needs a corpus that still contains
teleports — the `Position_during_rotation/translation_pivot_jump_test4` take is
the named reproduction, and it is currently **unreadable from Python** in this
environment (PermissionError on that subfolder; PowerShell reads it fine).

### 16.2 What happens on rejection — the coasting policy (owner question, 2026-08-04)

*"if a next set of frames is outside this probabilities distribution, the flag can
be activated and the cube position is inferred from prediction until the measured
frames return to the correct probabilities."*

Adopted, with one change that is not negotiable: **"until it returns" is
unbounded, and unbounded coasting is the cascade that already failed here.**
§0.13.3: a rejected frame makes the filter coast, the prediction drifts further
from the measurement, so the next frame fails too — **one bad frame booked up to
8 rejections**, and the resulting statistic was mistaken for a weak motion model
and had to be retracted (§0.15). The policy below keeps the inference and bounds
the coast.

**1. Rejection is PER CHANNEL, not per frame.** The block decomposition makes
this possible and it is the main advantage over 1.6's all-or-nothing gate. The
channels are independent quantities — arc extension is a scale-free intra-finger
ratio and does not depend on the palm transform, and vice versa. So:

- fingers confused at a pitch crossing (**N12**) → arcs rejected, **measured palm
  kept**;
- identity teleport (**T3**) → palm position/quaternion rejected, **measured arcs
  kept**.

Rejecting the whole hand because one finger is wrong throws away good data.

**2. A rejected channel is INFERRED from its own prediction** — the windowed
extrapolation, not the last value — and is flagged `valid = False`.

**3. ⚠ THE COAST IS CAPPED AT 2 CONSECUTIVE FRAMES PER CHANNEL.** On the third,
the measurement is **force-accepted** and that channel's estimator is
**re-seeded** (derivative history cleared, residual scale reset). Rationale: a
sustained disagreement means *our model is stale*, not that the sensor is wrong
three times running. Two frames at 24 fps is ~83 ms.

**4. Full reset on tracking loss or run break** — same contract as
`PalmFacingTracker.reset()`. A new track must never be judged against the old
one's trajectory.

**5. ⚠ CONSUMERS SPLIT (S3, binding — Apple ships exactly this).**

| consumer | uses |
|---|---|
| rendering / cube attachment | the output transform, inferred or measured — this is what keeps the cube smooth |
| **grab / release state machine** | **measured state only.** While `valid = False` it must HOLD — take no new snap and trigger no release — rather than decide on inferred data |

A prediction artifact must never latch into a gesture. This mirrors DR-2's
existing `orientation_valid` contract, which already freezes rather than acting
on an unobservable sign.

**6. The estimator never learns from an inferred value.** Only accepted
measurements enter the history and the residual scale. Feeding predictions back
in is how a filter convinces itself it is right.

### 16.3 B3′ built and evaluated (2026-08-04) — INCONCLUSIVE on detection, and the reason matters

`Resources/block_tracker.py` + `analysis/b3_block_gate_eval.py`. Built with every
fix identified against 1.6: windowed least-squares derivatives (not a raw
two-sample velocity — S2(a), the dominant error source), second order, seven
channels, per-channel rejection, adaptive residual scale with absolute floors,
2-frame coast cap, history trained on accepted measurements only.

Evaluated on the `Position_during_rotation` takes — the only corpus containing a
real Object Jump (`jump_test4`) — with rejections **classified**, not counted.

| config | teleports caught | real flagged |
|---|---|---|
| blocks, σ=4, order 2 | **1/1** | 6/16 |
| order 1 (velocity only) | 1/1 | **4/16** |
| order 2 (velocity+accel) | 1/1 | 6/16 |
| window 3 / 5 / 9 | 1/1 | 7 / 6 / 7 of 16 |
| suppress edge-on <0.35 | 1/1 | 5/16 |

**⚠ n = 1 TELEPORT. Detection performance is NOT MEASURABLE from this, and the
"ratio" is one event divided by sixteen.** It is reported as inconclusive.

What the data *does* say, on the false-positive side (n=16, still small):

- The gate flags **~⅓ of real fast movements**, and **the fixes did not help**:
  second-order derivatives scored *worse* than first-order (6 vs 4), and longer
  windows did not improve on 5. The specific weaknesses identified in 1.6 were
  addressed and the false-positive rate did not fall.
- Edge-on suppression barely moves it (6 → 5), so those rejections are **not** the
  known unobservable band — they are ordinary fast rotation.

**⭐ THE STRUCTURAL FINDING, which matters more than the numbers.** The teleport
population is nearly empty *because DR-1 already fixed it*. §0.4: duplicates
25 → 0, longest wrong-hold 225 → 10 frames. A gate that catches identity
teleports is solving a problem that no longer reaches it in production.

So what remains for a gate to do is the **finger** channel — N12's confusion at a
pitch crossing — and §16.1 measured that **anchoring the cube to the palm removes
that path entirely** (palm anchor 25–30% quieter in every band). **B4 and the arc
gate are alternative solutions to the same remaining problem, and B4 is far
simpler**: no prediction, no coasting, no threshold, nothing to cascade.

**Verdict: B3′ stays BUILT AND UNWIRED.** Not disproven — untestable on this
corpus, and aimed at a class DR-1 already handles. Revisit only if B4 leaves a
residual that a gate could plausibly catch, or if a corpus with real teleports is
recorded. Do not wire it on the strength of 1/1.

### 16.4 B4 — the A7 anchor A/B is RUN. Palm-rigid wins. (2026-08-04)

`analysis/b4_anchor_ab.py`, **28 grab intervals** replayed from the
`Position_during_rotation` takes. Three anchors, all in 2D pixel space — which
dissolves A7's "2D/3D coordinate mismatch" objection without needing M6 or M9,
neither of which is going to land.

| metric | A — §14.1 (9 pts) | B — palm+scale | **C — palm rigid** |
|---|---|---|---|
| 1 no-pop at grab (px) | 0.000000 | 0.000000 | **0.000000** |
| 2 jitter still, p95 | 2.270 | 1.769 | **1.736** |
| 2 jitter still, max | **8.543** | 11.941 | 11.712 |
| 3 yaw-sink \|r\| (T4) | 0.138 | 0.097 | **0.003** |
| 4 edge-on motion p95 (N12) | 11.953 | 9.067 | **9.067** |
| 5 teleport max (T3) | **511.3** | 515.9 | 516.5 |

**⭐ VERDICT: arm C — palm frame, rotation only, NO scale — is the best anchor.**

- **T4 is essentially eliminated**: yaw coupling |r| 0.138 → **0.003**. §14.1's
  documented value is −0.25 (§14.1.1); we reproduce the same sign and rough
  magnitude, and arm C removes it.
- **N12 improves 24%**: anchor motion inside the edge-on band 11.95 → 9.07 px,
  matching §16.1's independent 25–30% figure from a different measurement.
- **Jitter bulk is 23% tighter** (p95 2.27 → 1.74), and no-pop is preserved
  exactly — the property that killed the pre-§14.1 zero-offset design.

⭐ **B vs C confirms §14.3.1's prediction.** Including palm width as a scale term
(arm B) is *worse* than omitting it (arm C) on yaw coupling — 0.097 vs 0.003 —
because palm width collapses edge-on and arm B feeds that collapse straight into
cube position. That was predicted from the anchor measurements before this A/B
ran, and it held.

⚠ **Two honest costs, neither disqualifying:**

1. **Jitter MAX is worse** — 11.7 px vs §14.1's 8.5. The bulk is tighter but the
   tail is not, and arm C has no scale term, so the culprit is the **MCP-row
   direction** becoming unstable edge-on — the same collapse as everywhere else.
   The natural remedy is DR-2's pattern: freeze the palm ROTATION inside the
   edge-on band. Untested; do not assume it.
2. **No teleport advantage** — max ~511–516 px for all three. Expected: a
   teleport moves the whole hand, palm included, so no anchor choice helps. T3
   remains DR-1's job.

**Consequence for A7**: the gate has run, and it favours replacing §14.1's
9-point weighted anchor with a palm-rigid frame. ⚠ **Not yet ported to
production, and not yet live-confirmed** — this is replay evidence on 28
intervals from one recording session.

### 16.5 ⚠⚠ B4's VERDICT IS OVERTURNED (2026-08-04, same day) — arm C does not fix T4

§16.4 concluded that **arm C (palm rigid, no scale) is the best anchor**, on
yaw-sink |r| = 0.003 against §14.1's 0.138. That was measured on the seven
`Position_during_rotation` takes recorded in August 2026 for the
*translation-pivot* work — **none of which contains a sustained yaw hold or a
pitch crossing while holding a cube**, i.e. neither of the two conditions the
claim was about.

Two purpose-built takes were then recorded (`t4_yaw_hold`, 12 cycles;
`n12_pitch_crossing`, 11 cycles; cube held in 100% of frames in both). Re-run:

| take | metric | A §14.1 | B palm+scale | C palm rigid |
|---|---|---|---|---|
| `t4_yaw_hold` | jitter p95 | **2.235** | 5.486 | 6.848 |
| | **yaw-sink \|r\|** | 0.822 | **0.001** | 0.815 |
| `n12_pitch_crossing` | jitter p95 | 4.173 | 1.431 | **1.423** |
| | yaw-sink \|r\| | 0.323 | **0.005** | 0.194 |

**⭐ CORRECTIONS, in order of importance:**

1. **Arm C does NOT fix T4.** |r| = 0.815, essentially identical to §14.1's
   0.822. The 0.003 in §16.4 was an artifact of takes without sustained yaw.
2. **Arm B (palm + SCALE) fixes it almost completely** — |r| = 0.001. **The
   scale term is essential, which is the opposite of §16.4's conclusion.**
3. **The mechanism, now understood**: under yaw the palm foreshortens, so an
   offset held at fixed PIXEL length (arm C) juts further out as the hand
   shrinks — *that is the sink*. Scaling the offset with palm width (arm B)
   shrinks it with the hand and removes it. §14.3.2 showed palm width is *noisy*
   under yaw; both are true, and it is still the right term, because the anchor
   must track foreshortening even through a noisy proxy.
4. **§14.1's T4 defect is far worse than documented** — |r| = 0.822 on a
   purpose-built yaw take, against the −0.25 recorded in §14.1.1. The defect was
   under-measured because it had never been provoked deliberately.
5. **On N12 the palm arms win decisively** — jitter p95 4.173 → 1.43, and max
   15.6 → 2.0. That half of §16.4 survives.

### ⚠ AND PITCH-SINK IS REAL TOO — the metric was mis-named, and pooling cancelled it

"Yaw-sink" is a misnomer for what is measured. The metric correlates the anchor's
distance from the palm against `edge_on_measure`, which drops under **both** yaw
and pitch — the axis comes from *which take is run*, not from the metric. Per
axis:

| take (axis) | A §14.1 | B palm+scale | C palm rigid |
|---|---|---|---|
| `n12_pitch_crossing` (**pitch**) | **+0.323** | +0.005 | −0.194 |
| `t4_yaw_hold` (**yaw**) | **−0.822** | +0.001 | −0.815 |

1. **Pitch-sink exists**: §14.1 scores |r| = 0.323 on pure pitch, and the sign is
   **positive** — the anchor sinks *toward* the palm, exactly as §14.1.1
   describes T4.
2. **Under yaw the sign FLIPS to negative** — the anchor drifts *away*. Same
   defect family, opposite direction.
3. ⭐ **That is the second reason §16.4 was wrong.** Pooling yaw and pitch takes
   lets the opposite-signed drifts **partially cancel**, which is how §14.1
   scored a benign 0.138 pooled while being 0.822 and 0.323 on the isolated
   axes. **Always read this metric per take; never pool rotation axes.**
4. **Arm C fixes NEITHER axis** (0.194 pitch, 0.815 yaw) — it is not merely weak
   on yaw. **Arm B decouples both** (0.005, 0.001), and is the only arm that
   does.

**⚠ NO ARM IS A CLEAN WIN, and this is an owner trade-off, not a technical
call.** §14.1 is smoother during yaw (jitter p95 2.235 vs B's 5.486) but
systematically drags the cube toward the palm as the hand turns (|r| 0.822).
Arm B is ~2.5× noisier there but has essentially no systematic bias. A
systematic drift is the defect the operator actually reported; jitter is not.

**Arm B is the leading candidate. Do not port anything to production yet.**

⭐ **THE METHODOLOGICAL POINT, which is the durable output**: §16.4 was measured
on data that did not contain the failure it claimed to fix, and it produced a
confident, wrong, three-decimal answer. **A/B results are only as good as whether
the corpus contains the condition under test** — the same lesson as §0.15's
"a replay harness that reconstructs streams differently silently measures a
pipeline that no longer exists". Before trusting any A/B, ask what is IN the
takes.

### 16.6 B3″ — the FULL prediction model, built and MEASURED. It fails. (2026-08-04)

The owner rejected conclusions drawn with the half-implementation and specified
the model properly: explicit velocity and acceleration, a real predictive
probability distribution, multi-frame horizon, and — the vigilance condition —
**it must not reject genuine changes of direction.**

Built as `Resources/block_predictor.py`: explicit `p, v, a` from a least-squares
quadratic over 7 accepted frames; OLS **prediction variance**
`s²(1 + x(h)ᵀ(XᵀX)⁻¹x(h))` as a real distribution; angular velocity **and**
acceleration by log map; per-channel rejection with a horizon that grows while
coasting. Correctness proven on synthetic data where ground truth is known
(`analysis/verify_block_predictor.py`): p/v/a recovered exactly, ω = 6.0000°/frame,
α = 1.0000°/frame², variance growing with horizon, a 200 px teleport caught while
25 px/frame smooth motion is untouched. Floors **derived** from `static_hold`
(p99.5 of resting residuals), verified 4.0–16.5× below real failure residuals.

**⭐ AND THEN IT FAILS THE VIGILANCE TEST, DECISIVELY:**

| | channel-frames | rejected |
|---|---|---|
| **at a direction reversal** | 20,927 | **11.65%** |
| elsewhere | 214,392 | 1.57% |
| | | **7.43× over-rejection** |

Reversals were labelled **non-causally** from raw velocity sign changes,
independent of the gate. One reversal frame in nine is rejected — in a game
built on pitch and yaw cycles, that is a visible artifact at every direction
change.

**Why, and it is structural rather than a tuning failure**: a reversal is
**unpredictable from past data by construction**. The quadratic says "continue at
the current v and a", the hand turns, the residual spikes — and σ stays narrow,
because the fit residual over the smooth approach *to* the reversal was small.

**The principled remedy was tried and does not work.** Acceleration is the least
trustworthy coefficient, so σ was widened by its own contribution
`|½·a·h²|` (`ACCEL_UNCERTAINTY`). Overall rejections fell 15.81% → 12.12%, but
**the ratio was unchanged: 7.33× → 7.43×**. It scales everything down without
separating reversals, because at a reversal the residual is ≈ 2|v| while the
acceleration term is only ≈ ½|a| — far smaller for a sharp turn.

**And it solves none of the four target problems:**

| target | raw | gated | verdict |
|---|---|---|---|
| jitter, still hand (p95 / max) | 0.0174 / 0.0695 | 0.0179 / **3.0248** | **worse** — 43× worse max |
| edge-on band motion (p95) | 0.3607 | 0.3541 | marginal (2%) |
| back-of-hand orientation | — | identical | **no effect** (gate never fires on still hands) |
| teleport | — | — | already solved by DR-1 (n=1 survives) |

**VERDICT: B3″ is PARKED alongside 1.6 and `block_tracker.py`.** This is the
second, much better-specified attempt at a predictive outlier gate, and it fails
the same way — which is itself the finding.

⭐ **THE GENERALISABLE RESULT, now measured twice with very different models:**
**at this input envelope, a forward-extrapolation gate cannot separate a
genuine direction change from an outlier.** 1.6 failed with a two-sample
velocity and a fixed threshold; B3″ fails with fitted derivatives, a real
predictive distribution and a growing horizon. **The limitation is not model
quality — it is that the information needed is not in the past frames.** Do not
attempt a third variant without a fundamentally new signal (a second camera, or
a non-causal buffer that can see *past* the reversal, i.e. item 3.2's RTS
smoothing, which costs latency for everyone).

⚠ **Consequence for the anchor question**: because the gate does not work, it
cannot clean the outliers that dominate B4's jitter tails, so **it cannot
reorder arms A/B/C**. §16.5's conclusions stand or fall on their own evidence.

### 16.7 B7 — the confirmation gate, BUILT and MEASURED. It does not ship. (2026-08-04)

`Resources/confirmation_gate.py` + `analysis/verify_confirmation_gate.py`
(22 synthetic checks, all passing) + `analysis/b7_eval.py` (15 configurations
over the 33-session corpus, 235,319 channel-frames).

**To see it live**: `debug_prediction.bat` (`LiveBlockPredictionDebug.py`) runs
RAW and GATED cube behaviour **side by side off one camera** — one capture, one
MediaPipe pass, one DR-1/DR-2 pass, then the stream forks, so every visible
difference is the gate and nothing else. It draws the hand as the **six blocks**
rather than the 21 landmarks: palm quad + centroid + scale bar + axis gizmo (the
four palm channels), each finger as an arc whose bow is computed from its
extension scalar alone, and the thumb dashed and labelled RAW because §16 leaves
it unmodelled. Amber = that channel is PENDING, red = its frames were discarded.

The design from `BUILD_PREDICTION_GATE.md` §1, built in full: flag at F but do
**not decide**; buffer F…F+L; coast the *output* while the *measurement* waits;
decide at F+L; discard only what later frames prove was an outlier. Per-channel,
S3-compliant, hard-capped, and — unlike B3″ — a discarded frame genuinely never
enters the fit.

#### ⭐ What worked, and it is the part worth keeping

**Deferring the decision does separate reversals from outliers.** With the flag
rate divided out — *of the flags raised, what fraction was thrown away?* —

| verdict test at F+L | at a reversal | elsewhere | ratio |
|---|---|---|---|
| `p_pre` — m4's inherited shape | 31.8% | 28.3% | **1.13×** (no discrimination at all) |
| `self` — the owner's literal "are F…F+L coherent?" | 31.3% | 42.3% | 0.74× |
| **`pred` — distance from the PREDICTED TRAJECTORY** | **9.3%** | **24.5%** | **⭐ 0.38×** |

⚠ **And the inherited test had to be thrown away, which is a finding in itself.**
`m4_rejection_audit.py`'s out-and-back shape — distance from the last accepted
*value* — **does not discriminate on these channels (1.13×)**. It was measured on
a **2D palm centroid**, where a hand rarely retraces its own path; the block
channels are **signed scalars**, and *a direction reversal comes back through the
value it started from*. "Returned to where it was" and "turned around" are the
same event on one axis. The brief warned that the thresholds would not transfer;
**the shape did not transfer either.** Asking instead whether the later frames
return to the *predicted trajectory* scores 0.38× on identical data.

#### ⚠ And the four acceptance criteria, decided in advance

Best configuration: **L=2, `pred` verdict, `hold` coast, blend 3, B8's fit.**

| # | criterion | result | |
|---|---|---|---|
| 1 | reversal-discard ratio ≤ 1.5× | **9.44×** best (B3″ 7.43×) | ❌ **FAIL** |
| 2 | discards majority outlier, not real movement | **89.5% / 3.4%** (1.6 was 7.9% / 80.2%) | ✅ PASS |
| 3 | jitter and edge-on improved, max not worse | jitter max 0.0695 → **0.4971**; edge-on max 3.4555 → **1.8617** | ❌ FAIL on jitter — ⚠ **OVERTURNED BY §16.9**: this is the PALM level; measured on the CUBE it passes, and the cube is the level the operator sees |
| 4 | latency stated in ms and accepted | **83 ms** at L=2 @ 24.1 fps (124 / 166 / 248 at L=3/4/6) | owner's call |

**VERDICT: B7 is BUILT, MEASURED and UNWIRED**, alongside 1.6, `block_tracker.py`
and B3″. It is the third measured failure of causal outlier gating on this sensor.

#### ⭐ But the diagnosis is now sharper than "gating fails", and that matters

**The decision is fixable; the detection is not.** Split the ratio into its two
factors and the residue is obvious:

    reversal over-rejection  =  FLAG rate ratio  ×  verdict-test ratio
    B3''                        7.43x               1.00x (no deferral)
    B7 + B8                     3.84x               0.83x

The deferred verdict is now *protective* (< 1.0), and the fit change halved the
flag ratio — but **a reversal still trips the residual test 3.8× more often than
an ordinary frame, and no amount of deferral removes that.** §16.6's
generalisable result stands, narrowed: it is the *detector*, not the *decider*,
that cannot see a reversal coming.

⭐ **Two numbers that read the opposite way from the ratio, and both are true:**

- **Absolute harm at reversals fell 2.8×.** Of channel-frames at a labelled
  reversal, B3″ discarded **11.65%**; B7 discards **4.15%**. The *ratio* got
  worse only because discards elsewhere fell even further (1.57% → 0.44%).
  ⚠ A ratio is not harm. The criterion was set on the ratio and the criterion
  fails; the owner should know both figures before treating that as settled.
- ⚠ **The reversal labels themselves are contaminated.** `reversals()` fires on
  a raw velocity sign change — and **a teleport produces two of those**. Every
  ratio in §16.6 and here is therefore an *upper bound* on true reversal
  over-rejection, and the contamination is worst inside the discarded subset,
  which is precisely the population the gate selects. This weakens B3″'s 7.43×
  as much as it weakens B7's numbers.

#### ⚠ What B7 cannot do, confirmed by measurement rather than argued

- **Back-of-hand: no effect**, exactly as predicted. The `known_*_back` takes are
  byte-identical raw vs gated in every one of the 15 configurations — the gate
  never fires there, because those errors are *sustained* and F…F+L agree
  coherently in the wrong place (§0.18's sensor floor).
- **Teleports: nothing left to catch.** After DR-1 the identity-teleport
  population is ~3 events in 29,164 frames (§16.1). What the gate actually
  removes is transient jitter spikes — and its own coast-and-rejoin then puts a
  **7× larger** transient back into the still-hand tail. That is the whole
  failure in one sentence.

### 16.8 B8 — the quadratic optimised, and it LOSES TO DOING NOTHING (2026-08-04)

`analysis/b8_fit_sweep.py`: 15 fit configurations, open loop, against the two
baselines **S1** makes mandatory, **stratified by hand speed** — because a pooled
median is decided by the still-hand majority, while the gate only ever coasts on
a hand that was *moving*. Median |error| in units of each channel's noise floor:

| | still, h=1 | still, h=6 | **fast, h=1** | **fast, h=2** | fast, h=6 |
|---|---|---|---|---|---|
| **BASELINE hold (v=0)** | **0.322** | **0.677** | 3.921 | 6.182 | **10.927** |
| B3″ shipped (w7, order 2) | 0.457 | 2.680 | 4.175 | 8.216 | 34.211 |
| best fit (w7, **order 1**, exp hl2) | 0.362 | 1.043 | **3.648** | **5.462** | 12.875 |

orientation (deg): hold **3.07 / 4.57 / 10.94** vs the log-map fit 3.61 / 6.32 / **23.76**

**⭐ THREE RESULTS:**

1. **ORDER 2 IS WRONG.** The acceleration term differentiates noise twice and the
   error explodes with horizon — 34.2 floors at h=6 against order 1's 12.9.
   §16.3 saw a hint of this (order 2 rejected *worse* than order 1) and did not
   follow it. Order 1 dominates at every horizon in every speed band.
2. **Weighting helps**, as it should for a 7-frame window that counted a 290 ms-old
   sample as heavily as the newest. Exponential, half-life 2 frames, is best.
3. ⚠⚠ **NO CONFIGURATION BEATS "HOLD THE LAST VALUE" AT EVERY HORIZON — S1 FAILS
   for all 15**, and the orientation motion model loses to holding the last
   quaternion at every horizon too. The fit wins **only** in the regime the gate
   actually coasts in (a moving hand, h = 1–2) and loses everywhere else.

⭐ **AND B8 IS NOT THE SEPARATE LEVER THE BRIEF ASSUMED.** The brief stated that
optimising the fit would leave B3″'s reversal ratio "roughly intact — that was
measured". That measurement was of `ACCEL_UNCERTAINTY`, which only widens σ.
Changing the *order and weighting* moves it a great deal:

| with B8's fit | flag ratio | jitter max |
|---|---|---|
| B3″ fit (order 2, unweighted) | 7.03× | 1.3244 |
| **B8 fit (order 1, exp hl2)** | **3.84×** | **0.5816** |

**Consequences already applied**: `confirmation_gate.COAST_MODE` defaults to
`"hold"`, not to the prediction the owner's design assumed — coasting on a model
measured to be worse than nothing is not a defensible default. `fit_channel` now
takes `order` / `weighting` / `half_life`, and ⚠ **its defaults are left exactly
as B3″ shipped them** so every pre-B8 number stays reproducible; B8's
configuration is passed in by the caller.

⚠ **Do not read this as "prediction is useless here."** It says the *quadratic
extrapolator* is, at horizons past ~2 frames, on this sensor. Item 3.1's
dual-pathway work should treat "hold" as the baseline to beat, not as a straw man.

### 16.9 ⚠⚠ B7 MEASURED LIVE — §16.7's criterion 3 is OVERTURNED (2026-08-04)

A **450-second live take** (10,092 frames, 22.43 fps measured, cube held in
86.1% of frames, 14.2% still and 25.3% fast) recorded through
`debug_prediction.bat` and re-measured by `analysis/b7_live_ab.py`, which
replays the whole pipeline offline under any configuration.

#### ⭐ First: a wiring bug that invalidated the first pass, found BY EYE

The owner, watching the two windows: *"if I hold my hand edge-on palm up… in the
prediction gate window, the arc and vertices literally jump all around the
window."*

The gated `scale` channel was being realised as a similarity transform,
`f = gated_scale / raw_scale`, applied to all 21 landmarks. **Its denominator
collapses.** Edge-on, measured palm width fell to **2.43 px** while the gate
coasted ~86 px, so `f` reached **35.4** and threw the landmarks **5235 px**
across a 640 px window. The 118 frames with >100 px of displacement had median
palm width 41.8 px against 91.6 px overall, and median `edge_on` 0.319 against
0.747 — precisely the edge-on band.

⭐ **And it was wrong before it was unstable: edge-on the palm is FORESHORTENED,
NOT SHRUNK.** "Palm width should be 86 px" has no valid realisation as landmark
coordinates. This is the reciprocal of §14.3.1/§16.5's trap, where feeding
palm-width collapse *into* cube position was the measured difference between
anchor arms B and C — **the spec had already written this down twice.**

Fixed by never back-projecting `scale` (it is gated and displayed as the knuckle
bar's *length*): max displacement **5235 → 219.8 px**, frames >100 px **118 → 6**.

⚠ **Every cube number from the first pass measured that bug and is void.** The
lesson is the §0.15 one again: a harness that reconstructs the stream
differently silently measures a pipeline that does not exist. It took a human
looking at the screen to catch it, which is an argument for this tool existing.

#### The corrected live result, on held-only frames

Restricted to frames where the cube is actually held, so the S3 hold cannot
flatter the gate (raw holds 86.1% of frames, gated 80.5%):

| held-only cube step | RAW | B7 | B7 `reject_z`=4.0 |
|---|---|---|---|
| p50 | 7.55 px | 7.66 px | 7.75 px |
| p95 | 41.11 | 39.99 | 40.08 |
| **max** | **156.51** | **124.33** | **109.58** |
| **still-hand max** | **73.16** | **38.65** | **38.65** |
| grabs taken | 144 | 138 | 140 |

| # | criterion | corpus §16.7 | LIVE | |
|---|---|---|---|---|
| 1 | reversal-discard ratio ≤ 1.5× | 9.44× | **5.63×** (best 2.62× at L=6) | ❌ **confirmed FAIL** |
| 2 | discards majority outlier | 89.5% | **95.3%** | ✅ confirmed PASS |
| 3 | max not worse | jitter max 7× worse | **cube max −21%, still-max −47%** | ⭐ **OVERTURNED → PASS** |
| 4 | latency in ms | 83 ms | **89 ms** @22.43 fps | owner's call |

⭐ **WHY CRITERION 3 FLIPPED, AND IT IS A MEASUREMENT-DESIGN LESSON, NOT A
CONTRADICTION.** §16.7 judged it on *palm channels*, because the corpus contains
no cube. But the cube's anchor is a weighted mean over 9 landmarks plus a frozen
residual offset — **it low-passes exactly the coast-and-rejoin transient the gate
adds**, while the raw excursions the gate removes *do* reach the cube. Both
numbers are correct; only the cube one describes what the operator sees.
**The criterion was being evaluated one level above where the defect lives.**

⚠ The out-and-back classifier scored exactly **100.0%** "teleport" for
`verdict_test='p_pre'` on live data too — the tautology of §16.7 reproducing
itself outside the corpus.

#### Degrees of freedom: what actually moves anything

| knob | effect |
|---|---|
| ⭐ **`reject_z` 3.0 → 4.0** | **the best single tune.** Flags −44% (3002→1672), cube max 124→**110**, still-max unchanged, grabs 138→140, reversal discards 6.52%→3.96%. No latency cost |
| `L` (lag) | trades criterion 1 against everything: L=6 reaches 2.62× but costs **267 ms** and pushes still-max 38.65→**148.20**. Bad trade |
| `blend` | 1 is clearly wrong (cube max 229); 3 or 5 are fine |
| `window` | 5 marginally best on cube max, +26% flags |
| `coast_mode` | barely matters once `scale` is out of the wiring |
| ⚠ **`ACCEL_UNCERTAINTY`** | **DEAD PARAMETER.** 0 and 2 give byte-identical results, because B8's order-1 fit makes `a = 0.0` and the term is always zero. The build brief listed it as a DOF to sweep; it cannot act unless order 2 returns, and §16.8 measured order 2 as clearly worse |
| ⭐ **the channel→landmark mask** | **the dominant DOF, and not a gate parameter at all.** No gate knob came close to its effect size — it was the difference between a 5235 px artifact and a working tool |

#### ⭐ Replicated on a SECOND live take (2026-08-04, `gate_z4`)

A second take recorded at `reject_z = 4.0` — 1155 frames, 50 s, 23.12 fps.

⚠ **The two takes are NOT content-comparable**, and that governs how they may be
read (§16.5's rule, applied before the numbers): take 2 has **0.8% still frames
against 14.2%**, is faster (palm p50 11.98 vs 6.83 px/frame), holds a cube 73.2%
vs 86.1% of the time, and its largest palm excursion is 50.9 px against 512.9.
Reversal content is identical at 19.1% of channel-frames. So z=3 vs z=4 is
compared **within** each take by replay, never across them.

| claim | take 1 (450 s) | take 2 (50 s) | |
|---|---|---|---|
| criterion 1 fails at every setting | 5.63× | 4.25× (best 2.39× at L=6) | ✅ replicated |
| criterion 2, discards majority outlier | 95.3% | 83.8% (93.9% at z=4) | ✅ replicated |
| held-cube max step improves | 156.5 → 124.3 | 80.7 → 70.1 | ✅ replicated |
| `ACCEL_UNCERTAINTY` inert | identical | identical | ✅ replicated |
| `p_pre` classifier tautological | 100.0% | 100.0% | ✅ replicated |
| grab loss small | 144 → 138 | 15 → 15 | ✅ replicated |

⭐ **And the wiring fix is visible in the data**: raw-vs-gated cube separation is
now **p50 0.86 px** where the buggy pass measured 80.82 px. The arms track each
other and diverge only during a flag, which is the intended behaviour.

**`reject_z` 3.0 → 4.0, head to head within each take:**

| | take 1 | take 2 |
|---|---|---|
| flags | −44% | **−47%** |
| **S3 hold, % of frames** | 17.1% → **9.4%** | 21.3% → **10.3%** |
| reversal discards | 6.52% → 3.96% | 4.84% → **3.60%** |
| discards that are outliers | 95.3% → 95.2% | 83.8% → **93.9%** |
| held-cube max | 124.3 → **109.6** | 70.1 → 72.4 |

**z=4.0 is CONFIRMED and is the recommended setting**: it roughly halves both the
flag rate and the S3 hold fraction — i.e. halves how often the gate is
intrusive — while *improving* the quality of what it discards.

⚠ **Two honest limits on that.** The cube-max advantage of z=4 over z=3 did
**not** replicate (better on take 1, marginally worse on take 2) — call it
neutral, not a win. And **still-hand metrics cannot be evaluated on take 2 at
all**: 7 qualifying frames, so its `stillMx` figures are one frame's worth of
noise and are not evidence in either direction.

#### ⚠⚠ CRITERION 1 IS RETRACTED AS A DISQUALIFIER (owner challenge, 2026-08-04)

The owner, from watching both windows: *"I did not see flagrant cases where the
change of direction was completely missed, even at relatively high speed. I think
you are over interpreting the reversal-discard ratio."*

**Measured directly, on the cube — the only thing on screen.** Raw-cube direction
changes (>2 px/frame either side), matched against the gated cube's:

| take | direction changes | lag p50 | lag p90 | unmatched |
|---|---|---|---|---|
| 450 s | 1671 | **0 frames (0 ms)** | 0 frames | 10.1% |
| 50 s | 118 | **0 frames (0 ms)** | 0 frames | ~10% |

**The gated cube turns on the SAME FRAME as the raw cube.** The unmatched ~10%
are small reversals that fall below the 2 px/frame detection threshold once
smoothed — not missed turns.

⭐ **FOUR REASONS THE METRIC WAS WRONG, and they are the durable output:**

1. **It was carried across a mechanism change without revalidation.** Criterion 1
   was written for B3″, where a rejection replaced the measurement *and could
   cascade* — §0.13.3 measured one bad frame booking up to 8 rejections. There
   it was a fair proxy for "the cube fails to follow a direction change." Under
   B7 a discard is **bounded to L frames and always resumes from the
   measurement**. The same count means something far milder.
2. **A ratio is not a magnitude.** 5.63× reads as alarming; the absolute rate is
   3.96% of reversal channel-frames, each removing ≤2 frames of ONE channel of
   eight, feeding an anchor that averages 9 landmarks. Several attenuating
   stages sit between the metric and anything visible, and it models none.
3. ⚠ **The operator-visible measurement was available and was not taken.** Both
   cube tracks were in the recording. Reporting the channel-level proxy instead
   is EXACTLY the error §16.9 had just diagnosed in criterion 3 — *measured one
   level above where the defect lives* — found and then not generalised by a
   single section.
4. **The label contamination was flagged and then ignored.** A teleport also
   produces two velocity sign changes, so every such ratio is an upper bound —
   stated in §16.7, then used as if clean.

> **Before treating a criterion as a disqualifier, measure the harm it is a
> proxy for.** All four failures share one root: a proxy was trusted after the
> thing it proxied for had changed.

**B7 passes every criterion that has been measured against observable harm.**
Criterion 1 fails as literally written and is retracted as a blocker; criteria
2-3 pass; criterion 4 (~89 ms hold per flag, ~4% of grabs delayed) is a product
judgement.

### ⭐ 16.9.1 OWNER DECISION: B7 IS PARKED, NOT WIRED (2026-08-04)

> *"I agree there is almost no visual difference between the raw and the
> prediction gated outcomes. I would therefore keep the raw to keep the pipeline
> lean and without adding additional layers. However, I would park the build in
> order not to lose all what we have built."*

**And this is the right call on the evidence, not a rejection of it.** The gate
was cleared of its technical blockers and then declined on a product ground the
measurements support: a 21%/47% cut in the cube's worst steps is real but not
*visible*, and it costs a per-hand predictive layer, ~89 ms of hold at every
flag, and ~4% of grabs delayed. **A layer that cannot be seen is not worth its
own failure modes** — this build produced two of them (the `scale`
back-projection, the quaternion rejoin) inside one session.

⚠ **Nothing was wired.** Production (`HandsTriggeredActions.py`, `CubeWindow.py`,
the client/server pipeline) is untouched; `confirmation_gate.py`,
`hand_blocks.py` and `block_predictor.py` are imported only by
`LiveBlockPredictionDebug.py` and by `analysis/`. The single production-adjacent
change is `LiveSnapDebug.update_hands`'s `snap_blocked=frozenset()` default,
a no-op for every existing caller.

**To revive it, this is the whole configuration — do not re-derive it:**

    reject_z    4.0        (3.0 halves nothing; 4.0 halves flags AND the S3 hold)
    lag L       2          (~89 ms; L=4/6 measurably worse on the cube)
    verdict     "pred"     (distance from the PREDICTED trajectory, 0.38x)
    coast_mode  "hold"     (B8: the fit loses to holding at every horizon)
    blend       3
    fit         order 1, exponential weights, half-life 2 frames

**Still runnable**: `debug_prediction.bat` (live A/B, blocks overlay),
`analysis/b7_live_ab.py` (replay any config over a recorded take),
`analysis/verify_confirmation_gate.py` (24 synthetic checks), plus two live
takes on E: under `Recordings_prediction_gate`.

⚠ **Do not restart this line of work on the strength of the idea.** Three
measured attempts (1.6, B3″, B7) and the conclusion is stable: gating buys
little here because DR-1 already removed the teleports, and what remains is
either sustained (a sensor floor) or already invisible.

### 16.10 ⭐ WHERE THE CUBE'S NOISE ACTUALLY COMES FROM (measured 2026-08-04)

Found while explaining the pipeline to the owner, and it reframes the next step.
**The cube transform has only two live components**, driven by disjoint landmark
sets — they do not mix:

| cube property | driven by | note |
|---|---|---|
| position | `_weighted_position`, the **9 landmarks** (5 fingertips + 4 MCPs) | ⚠ NOT smoothed — assigned directly |
| quaternion | `_hand_orientation_quaternion`, the **4 palm world landmarks** | slerp-smoothed |
| **scale** | **nothing — `size` is a constant** | there is no scale channel on the cube |
| *(grab test only)* | `_hand_position`, the **5 palm landmarks** = `hand_blocks.PALM_LANDMARKS` | never touches the transform |

The translation anchor is a **fixed linear combination of 9 landmark pixel
positions**, its coefficients frozen at grab by inverse distance from the cube,
plus a frozen residual offset.

**⭐ THE MEASUREMENT: A PERFECTLY STILL PALM STILL MOVES THE CUBE.**
On the 450 s take, restricted to frames where the 5 palm landmarks barely moved:

| palm moved | n | anchor moved p50 | p95 | max | amplification p50 |
|---|---|---|---|---|---|
| < 0.5 px | 249 | **0.570 px** | 1.701 | **17.51 px** | **1.66×** |
| < 1.5 px | 1344 | 1.013 px | 3.050 | 22.03 px | 1.15× |

Because the frozen weights include the **5 fingertips**, any finger flex moves
the cube. Even grabbing at the palm centroid — the most MCP-favourable case
there is — the fingertips carry a **median 27% of the total weight** (p95 42%),
and they are the 13-32% CV landmarks (§0.2) against the palm's 2.76 mm rigidity.

⚠ **This is not palm noise leaking through. The anchor deliberately includes the
noisiest points on the hand**, by a §14.1 design chosen to fix a different
problem (the translation pivot). It is the same defect §16.5 measured as
|r| = 0.822 yaw-sink and 0.323 pitch-sink.

⭐ **And the remedy does not add a layer — it REMOVES one.** Anchoring to the
palm transform (the 5-landmark position and the 4-landmark frame, both already
computed every frame) deletes the fingertip path entirely. That is §16.5's
**arm B**, the only arm that decoupled both axes (|r| 0.005 / 0.001). It is
independent of B7, it is a replacement rather than an addition, and it is aimed
at the edge-on/pitch complaint the gate could not touch.

### 16.11 B4 BUILT 3D-NATIVE (2026-08-04) — and the live evidence is MIXED, not a win

`Resources/palm_anchor.py` + `analysis/verify_palm_anchor.py` (18 golden
vectors, all passing). Owner decision: build it 3D-native now, render in 2D
until real depth exists, so the Z retrofit is one function later.

    at grab:   R3  = Rot_G⁻¹ · ( X_G − o_G )      metres, in the PALM's frame
    every t:   P_t = o_t(px) + k_t · proj_xy( Rot_t · R3 )

⭐ **Why 3D-native costs nothing today.** The rotation is *already* computed every
frame (`hand_blocks.palm_frame`); only the offset representation changes, from a
2-vector in pixel-frame units to a **metric 3-vector in the palm's own frame**.
That single choice is what makes the retrofit free: `R3` and `Rot_t` survive
untouched, `o_t` gains a z, and `proj_xy + k_t` are replaced by a real
projection. ⛔ **What is missing for true 3D is not the formula — it is ABSOLUTE
DEPTH**: MediaPipe's world landmarks are hand-RELATIVE (metric shape, origin at
the hand, no world position), so `o_t.z` does not exist in the data at all. That
is the Z-translation item's problem and it is identical for every anchor design,
including §14.1's. `verify_palm_anchor.py` §5 asserts the 3D form reproduces the
2D similarity form to **6.36e-14 px** at z=0, so the reduction is proven, not
hoped.

⭐ **Rotating in 3D then projecting gives anisotropic foreshortening for free** —
an offset along the tilt axis shortens by cos(θ) while a perpendicular one does
not (verified exactly). A scalar 2D scale term shrinks both equally, which is
very likely why §16.5 measured arm B as 2.5× noisier under yaw.

#### The scale term: measured, and palm width is ruled out

| | p50 | CV | r(edge_on) | edge-on → open |
|---|---|---|---|---|
| palm width, PIXELS | 91.5 px | 25.8% | **+0.601** | **0.320** — 3× collapse |
| palm width, WORLD | 0.064 m | 18.5% | **+0.002** | 0.993 |
| weak-perspective `k` | 1403 | 28.9% | +0.091 | 0.809 |

⭐ **The palm never actually collapses — only its projection does.** In metric
space it is the same hand at every pose (r = +0.002), so a scale built from the
projection alone inherits the projection's degeneracy while a least-squares fit
of the known 3D shape to the observed 2D points does not.

#### ⚠⚠ AND THEN THE LIVE MEASUREMENT DOES NOT SUPPORT IT

Replayed over two live takes. Worst cube step while the PALM moved < 0.5 px —
i.e. §16.10's own defect, the one this module exists to remove:

| still-frame cube step | take 1 (450 s) p50 / p95 / max | take 3 (290 s) p50 / p95 / max |
|---|---|---|
| **§14.1 incumbent** | 0.749 / 29.40 / **73.16** | **0.610** / 2.96 / **18.58** |
| palm anchor, `k` live | 1.544 / 35.70 / 81.01 | 0.542 / 5.87 / 39.84 |
| palm anchor, `k` frozen | 1.186 / 31.43 / **59.54** | **0.372** / **2.93** / 24.45 |

1. **The live weak-perspective scale is itself a major noise source.** Freezing
   `k` improves max 81 → 59.5 and p95 5.87 → 2.93. Its 29% CV costs more than
   the collapse it cures — "noise is smoothable, collapse is not" was right in
   principle and wrong in magnitude.
2. **Even at its best the result is MIXED**: better max on take 1, worse on take
   3; better p50/p95 on take 3, worse p50 on take 1. **This is not the clear win
   §16.5's replay predicted.**
3. ⚠ **The likely mechanism, and it is structural**: this anchor makes cube
   POSITION depend on the palm QUATERNION — the least reliable channel on the
   hand (§0.18) — and on `k`, over a lever arm equal to the full grab offset
   (~60 px). §14.1's inverse-distance weighting is not only about fingertips: by
   putting weight NEAR the cube it also keeps the lever arm SHORT, so angular and
   scale errors are not amplified. That advantage was not anticipated in §16.10.
4. ⚠ **Confound, stated because it limits all of the above**: these are replays
   over takes recorded while the operator watched the §14.1 arm. Once the arms'
   cubes diverge they grab at different offsets and stop comparing like with
   like — which penalises the anchor arms far more than the gate arms.
5. ⚠ **`k` frozen is UNVALIDATED FOR DEPTH**: it stops the offset scaling as the
   hand moves toward or away from the camera, and these takes may not exercise
   that. Do not adopt it on the jitter numbers alone.

#### ⚠⚠ AND THE FOUR-ARM LIVE SESSION SETTLES IT: THE ANCHOR IS DISQUALIFIED

A live four-arm take (`four_arm_review`, 2763 frames, 143 s, 19.24 fps, **47%
still frames**, cube held 95%) run through `debug_prediction.bat`:

| live arm, held-only cube step | p50 | p95 | max | **still-hand max** |
|---|---|---|---|---|
| 1 §14.1 anchor, no gate | **1.59** | **9.18** | **36.94** | **11.32** |
| 2 §14.1 anchor + B7 | 1.66 | 9.58 | 38.25 | 15.24 |
| 3 PALM anchor, no gate | 8.38 | 97.57 | 393.03 | **307.46** |
| 4 PALM anchor + B7 | 8.30 | 82.62 | 393.03 | 307.46 |

**A 27× regression on the very defect it was built to remove.** Diagnosed, and
it is the DESIGN, not a wiring bug — on the 399 frames where the palm CENTROID
moved < 0.5 px, the palm QUATERNION still moved:

    palm rotation step   p50 1.59 deg   p95 21.91 deg   MAX 144.19 deg
    weak-persp k step    p50 0.75%      p95  5.99%      max   16.4%
    >30 deg rotation on a still palm: 2.8% of frames;  >60 deg: 0.5%

⭐ **The scale term was never the real problem — the ORIENTATION channel is.**
A 144° swing on a 60 px lever arm throws the cube ~114 px. This is §0.18's
documented defect (the 4-landmark palm frame jumping while the hand is still),
and the palm anchor converts it directly into cube POSITION, amplified by the
lever arm. **§14.1's anchor is structurally immune because it never reads
orientation at all** — a property nobody had noticed was load-bearing.

> ⭐ **THE DURABLE RESULT: an anchor's robustness is not about which landmarks
> it reads, but about WHICH CHANNELS IT COUPLES TO.** §16.10 correctly showed
> §14.1 couples cube position to the noisiest LANDMARKS; the fix coupled it to
> the noisiest CHANNEL instead, which is worse. Removing a defect is not the
> same as improving the system.

**VERDICT: BUILT, VERIFIED, MEASURED, AND DISQUALIFIED AS DESIGNED.** §14.1
stays (A7 holds). ⚠ The risk was named in `palm_anchor.py`'s docstring *before*
the first measurement and then measured as fatal — the naming is what made the
diagnosis take one run.

**The one cheap variant still worth trying**, because it attacks the measured
cause rather than the symptom: feed the anchor the **already-filtered**
orientation (`_predictive_filter_step`'s output, which production ALREADY
computes for cube rotation) instead of the raw palm quaternion. If the 144°
excursions are what the filter exists to suppress, the anchor inherits that for
free. Untested. ⚠ Do not assume it: §0.13.2 measured that most large orientation
jumps occur in WELL-observed frames, so the filter may not catch these either.

### 16.12 ⭐ WHY §14.1 WINS — the error decomposition, and the one change that beats it

Owner question, 2026-08-04: *what exactly differs between the two formulas, which
term carries the noise, and can the palm formula borrow §14.1's answer only for
that term?* Measured on three live takes.

#### The two error structures

| | §14.1 | palm anchor |
|---|---|---|
| form | `P = Σ wᵢ·Lᵢ(t) + R`, `Σwᵢ = 1` | `P = o_t + k_t·proj(Rot_t·R3)` |
| estimates | **nothing** — a linear functional of positions | rotation **and** scale |
| error | **ADDITIVE**, averaged over 9 points | additive `o_t` **+ two MULTIPLICATIVE terms × lever arm** |

Still-frame contributions, lever arm 60 px:

| term | p50 | p95 | max |
|---|---|---|---|
| §14.1 total (mean of 9 landmarks) | 0.432 | 2.18 | **9.49** |
| — worst single fingertip *input* | 1.769 | 10.65 | 47.08 |
| palm (a) centroid — additive | **0.321** | 0.48 | 0.50 |
| palm (b) rotation × lever | 1.667 | 22.95 | **151.00** |
| palm (c) scale × lever | 0.448 | 3.59 | 9.86 |

⭐ **§14.1 absorbs 47 px fingertip excursions and still outputs 9.49 px, because
averaging suppresses them.** And ⭐ **the palm CENTROID is the better translation
term** (0.321 vs 0.432) — that half of §16.10 was right. The whole regression is
term (b).

#### Borrowing §14.1's answer for the offending term

§14.1 never estimates orientation: rotation-following falls out of averaged
POSITIONS. Replacing the 3-point Gram-Schmidt with a least-squares **Procrustes**
similarity fit of the palm constellation in pixel space — same points, averaged —
repairs most of the damage:

| four_arm_review | p50 | p95 | max | still-max |
|---|---|---|---|---|
| §14.1 | **1.59** | **9.18** | **36.94** | **11.32** |
| palm anchor, Gram-Schmidt | 8.38 | 97.56 | 393.04 | 307.50 |
| palm anchor, **Procrustes** | 2.58 | 14.50 | 48.10 | 38.20 |
| Procrustes + 4 tips | 2.30 | 13.14 | 51.40 | 26.58 |

**An 8× repair from changing only how rotation is obtained — and it still loses.**

> ⭐ **THE DURABLE RESULT: estimating a transform costs strictly more variance
> than not estimating one.** Any estimator-based anchor pays a premium that a
> linear functional of positions does not. §14.1's apparent crudeness *is* its
> robustness, and that had not been recognised.

#### ⚠ The arc-extension idea, measured in three forms — all worse

Owner's proposal: weight the fingertips by the arc scalars (or their median),
which are scale-free and noise-cancelling, rather than using raw knuckles.

| four_arm_review | p50 | p95 | max | still-max |
|---|---|---|---|---|
| tips, no arc weighting | **2.30** | **13.14** | 51.40 | **26.58** |
| binary arc gate 0.03 | 3.79 | 54.00 | 129.78 | 75.48 |
| binary MEDIAN-arc gate | 2.92 | 35.84 | 107.65 | 61.95 |
| continuous τ=0.10 / 0.05 / 0.02 | 3.12 / 3.90 / 5.09 | 15.49 / 19.29 / 27.82 | 58.61 / 66.21 / 75.39 | 30.15 / 32.57 / 52.14 |

**Monotonically worse as the arc influence grows**, converging to the unweighted
case as τ→∞. Binary gating is worse still, because switching the active point set
manufactures a discontinuity at every switch.

⭐ **Why: a least-squares fit ALREADY absorbs a moving fingertip as residual.**
Down-weighting it removes a point from the averaging, raising the estimator's
variance more than it lowers its bias. **Averaging beats selecting** — now the
fourth independent measurement of that on this sensor (item 1.6, B3″, B7, here).

#### ⭐ The one change that DOES beat §14.1 — and it changes nothing structural

Keep §14.1 exactly: additive, no estimator, no lever arm. Scale only the
**fingertip share of its own frozen weights**, then renormalise. One line.

| | §14.1 (×1.00) | **×0.60** | **×0.35** | ×0.00 |
|---|---|---|---|---|
| four_arm p95 / max | 9.18 / 36.94 | **8.60 / 33.78** | **8.28 / 30.77** | 10.50 / 42.52 |
| gate_live p50 / p95 | 7.55 / 41.11 | 7.27 / 39.20 | **7.12 / 37.96** | 7.33 / 35.96 |
| z4 max / still-max | 41.08 / 18.58 | **34.41 / 10.42** | 40.04 / **6.22** | 62.22 / 19.48 |

⭐ **×0.00 — deleting the fingertips — is WORSE on all three takes.** There is an
interior optimum near **0.35–0.6**: the fingertips carry both signal (span, extra
averaging) and noise (flex), and neither extreme is right. That also retires
§16.10's implicit premise that the fingertips are simply a defect to remove.

⚠ **Gains are modest (5–17%) and not uniform** — still-max improves hugely on one
take and worsens slightly on another. **Not adopted on this evidence.**

#### ⚠ What is still unmeasured, and it is the metric that matters

All of the above is JITTER. §16.5 records that *"a systematic drift is the defect
the operator actually reported; jitter is not."* The SINK was measured across
these takes and is **inconclusive** (|r| 0.02–0.51, no consistent ordering) —
because **none of these takes contains a sustained yaw hold or a pitch
crossing**, which is precisely the error §16.4 made and §16.5 had to overturn.

**Next step, and the only one that can settle B4: two purpose-built takes**
(sustained yaw hold, pitch crossing, cube held throughout) measured per take and
never pooled. If the sink favours a palm-based anchor, the variant to use is
**Procrustes + tips**, never the Gram-Schmidt form and never an arc-weighted one.

### 16.13 ⭐⭐ THE CUBE'S ROTATION IS THE REAL TARGET — and KABSCH beats Gram-Schmidt 7.5×

⚠ **First, a conflation to kill: §14.1 HAS NO ROTATION COMPONENT.** The two paths
have always been fully separate, and the cube's rotation has always been
palm-based:

    POSITION  9 landmarks (5 tips + 4 MCPs), PIXELS -> weighted mean + frozen offset   [14.1]
    ROTATION  4 palm landmarks (0,5,9,17), WORLD    -> Gram-Schmidt frame -> quaternion
                                                    -> _predictive_filter_step
                                                    -> delta = q_now . conj(q_grab)
                                                    -> target = delta . q_cube_at_grab
                                                    -> slerp(cube.orientation, target, 0.35)

So "improve §14.1's rotation" is not a thing to do, and a hybrid of "palm for
translation, §14.1 for rotation" is already half-shipped: **rotation IS the palm
block**, via the same four landmarks and the same Gram-Schmidt construction
`palm_anchor` used.

#### The measurement: frame-to-frame rotation on a STILL palm

| four_arm_review, n=399 | p50 | p95 | max |
|---|---|---|---|
| RAW Gram-Schmidt quaternion | 1.59 | 21.91 | **144.19** |
| after `_predictive_filter_step` (**SHIPPED**) | 1.59 | 17.54 | **101.61** |
| **KABSCH delta, 5 palm pts** | 1.35 | 11.71 | **25.07** |
| **KABSCH delta, 5 palm + 4 tips** | **0.85** | **2.91** | **19.32** |

⭐⭐ **A least-squares (Kabsch) rotation fit over the palm constellation cuts p95
from 21.91° to 2.91° and max from 144° to 19° — 7.5× on both.** The shipped
predictive filter removes only ~30% of the excursion; the estimator, not the
filter, is where the error lives.

⭐ **AND THE FINGERTIPS HELP HERE — the opposite of the translation case.** Adding
the 4 tips improves p95 11.71 -> 2.91. Rotation is estimated by least squares
over a constellation, so points FAR from the centroid give a long baseline for
angle; their positional noise matters far less for an angle than their span
helps. **The same landmarks that are a liability for translation are an asset for
rotation.** That is why §16.12's "averaging beats selecting" and this result do
not contradict each other — the estimand is different.

⚠ Smaller effect on `gate_live_ab` (p95 7.29 -> 5.65, max slightly worse). Not
yet a settled result: needs purpose-built takes.

#### ⚠ Two design questions this opens, neither yet answered

1. **Frame-to-frame vs grab-referenced.** The cube needs the delta from GRAB.
   A grab-referenced Kabsch gives it with no drift, but is corrupted by finger
   flex during the hold (the constellation changes shape). A frame-to-frame
   Kabsch is immune to slow shape change but ACCUMULATES drift when integrated.
   Palm-only grab-referenced is immune to both and still beats Gram-Schmidt
   (p95 11.71 vs 21.91).
2. ⚠ **The M6b precedent does NOT transfer, but its warning does.** §0.12
   measured "SVD frame 2.1x worse" — but that was an ABSOLUTE frame derived from
   the current point cloud (PCA-style), not a RELATIVE fit between two
   corresponding constellations. Different estimator, different failure mode.
   ⚠ What DOES transfer is M6b's Q1: **an SVD-based rotation can silently invert
   chirality**, a bug this project has shipped once (§13.6.1). Any Kabsch
   implementation must carry the `det` sign correction, and the chirality guard
   must be run against it before it goes anywhere near production.

**This is now the most promising open lead in Phase B**, ahead of the anchor
question — it targets a channel that is measurably broken (144° excursions on a
still hand), it uses information already available every frame, and it changes an
estimator rather than adding a layer.

### 16.14 ⛔⛔ RETRACTED (2026-08-17) — ARM B IS REJECTED, and this section's headline was an ALGEBRAIC IDENTITY

> ⛔ **DO NOT BUILD ON THE TABLE BELOW. Arm B was rejected on the live six-arm
> session of 2026-08-17 (§16.17). The "sink 0.000 on every axis" result is not a
> measurement — it is arm B's own formula restated.**
>
> **The proof, in one line.** `SINK` is defined as
> `corr( |cube − palm_centroid| / palm_width , edge_on_measure )`, and
> `hand_blocks.palm_position` / `palm_scale` are **the same `o` and `s` that
> `palm_anchor.Arm2D` builds its position out of**:
>
> ```
> Arm2D:  P = o + s·(Rx·ex + Ry·ey)     ⇒   |P − o| / s  ≡  |R|  ≡  frozen at grab
> ```
>
> The correlation's numerator is therefore a **constant for the entire grab**,
> and its correlation with anything at all is 0 **for any hand motion
> whatsoever**. Measured on the live takes: arm B's `|R|` has standard deviation
> **0.0000** (range 0.0001) within an uninterrupted grab, against §14.1's
> 0.4752–0.6056. The tiny non-zero residuals reported below (−0.001, −0.026 …)
> come from the `+40 px` cube-centre approximation in the scoring function, not
> from anchor behaviour.
>
> ⭐ **This is trap #4 of `HANDOFF_ANCHOR_ROTATION.md` §5 — *"a classifier that
> shares an expression with the thing it judges measures itself"* — landing on
> the PRIMARY decision criterion of an entire queue row.** It is the same class
> of error as §16.4's, one level deeper: §16.4 measured the right quantity on the
> wrong takes; §16.14 measured a quantity that could not have come out otherwise.
>
> **And the independent criterion goes the other way.** Live, arm B's
> **still-hand** position step is WORSE on all four takes — pitch 6.64 → 8.81,
> yaw 5.18 → **12.72**, back-of-hand 5.66 → **11.27**, free play 57.74 → 65.36 —
> against this section's claim that still-hand "does NOT degrade". Position max
> in free play blows out 49.60 → **261.68 px**. The mechanism is plain: §14.1
> averages **nine** landmarks so noise cancels, while arm B's `s` and `ex` each
> ride **two** (index-MCP, pinky-MCP), amplifying the noisiest quantity on the
> hand.
>
> ⚠ **What survives**: arm B's *rotational* behaviour is the physically honest
> one — its cube keeps a fixed bearing in the palm frame (range **0.0°**) while
> §14.1's sweeps a full **358.8°**, i.e. §14.1's cube does not rotate with the
> hand at all. The owner saw this directly and described it as *"the cube
> rotating around the hand instead of around itself."* If an anchor is ever
> revisited, that is the property worth keeping — with a noise-robust scale
> (`hand_skeleton.palm_width_world()`), not two raw landmarks.
>
> Re-runnable: `analysis/b4_orbit_and_sink_audit.py`. **Any future anchor metric
> must compare against a quantity the anchor does not define.**

Seven purpose-built takes (2026-08-06/07) — the **first** in this project that
contain the conditions §16.4/§16.5 argued about. §16.4 measured the sink on takes
with no sustained yaw and no pitch crossing and produced a confident wrong answer.

⭐ **Validation first**: this harness measures §14.1's pitch sink at **−0.807**;
§16.5 independently measured **0.822**. The harness reproduces the known number
before being trusted for a new one.

| take | §14.1 p95 / max / stillMax | **ARM B** p95 / max / stillMax | SINK §14.1 → **arm B** |
|---|---|---|---|
| 3 yaw | 2.74 / 8.88 / 1.88 | 4.64 / 14.49 / 3.43 | −0.656 → **0.000** |
| **4b pitch** | 5.09 / 13.57 / **4.81** | 8.11 / 25.07 / **4.64** | **−0.807 → −0.000** |
| 5 depth | 1.83 / 5.56 / 1.28 | 1.83 / **4.67** / 1.39 | −0.589 → **−0.001** |
| 6 back-of-hand | 4.91 / 25.61 / 3.56 | 6.35 / 30.52 / **3.44** | −0.083 → **0.000** |

**Arm B eliminates the systematic sink on every axis**, reproducing §16.5's
0.005/0.001 on data that actually contains the conditions. Cost: p95 jitter
+30–70% on yaw/pitch/back-of-hand, **unchanged on depth**. ⭐ **The worst
STILL-HAND step does not degrade** (pitch 4.81→4.64, back 3.56→3.44).

#### ⚠⚠ AND THE 3D-NATIVE DESIGN OF §16.11 IS OVERTURNED

Same palm centroid, same idea, radically different result — pitch axis:

    §14.1 incumbent            p95  5.09   max 13.57   stillMax  4.81
    ARM B (2D)                      8.11       25.07             4.64
    3D-native (palm + Horn)        27.80       72.22            36.43

⭐ **§16.11 argued the 3D palm quaternion was "free, because it is computed every
frame anyway". IT IS NOT FREE — it costs the DEGENERACY of that frame**, which
collapses at edge-on, exactly where the anchor is needed and exactly where pitch
drives the hand. Arm B's axis is a pixel direction and its scale a pixel width,
so both foreshorten with the projection and neither can degenerate.

> ⭐ **FOR THE ANCHOR, STAYING IN 2D IS NOT A LIMITATION — IT IS A SHIELD.**
> The general lesson: prefer the representation that cannot degenerate over the
> one that is more "correct" but shares a failure mode with the sensor.

⚠ Arm C (no scale term) is measurably wrong: yaw −0.745, depth −0.873. **The
scale term is what decouples the sink** — §16.5 said this and it replicates.

### 16.15 ⚠ AMENDED (2026-08-17) — HORN SHIPPED, but the 10× DID NOT REPRODUCE LIVE

> ⚠ **The table below is replay evidence and its headline did not survive.**
> Live (§16.17), the shipped Gram-Schmidt frame and Horn emit **the same ~60°
> jumps to within 1°** on the same frames — 62.38 vs 61.83, 57.73 vs 57.58,
> 49.71 vs 48.53. Nothing like 39.94° → 9.64° occurs.
>
> ⭐⭐ **And that near-identity is itself the most useful finding of the session.
> If two structurally unrelated estimators — a 3-vector Gram-Schmidt frame and a
> least-squares fit over 5 points — reproduce the same 60° jump on the same
> frame, the jump is ALREADY IN THE LANDMARKS. No rotation estimator can remove
> it.** That re-points the residual orientation failure (queue **T1/T2**) at the
> landmark layer — items 1.5 / 1.6 / 1.7 and the SmoothNet-class item 5.4 — and
> closes off further estimator work as a route to it.
>
> ⛔ **`PALM_AND_TIPS` is REJECTED — and this section's protocol is what hid it.**
> The fingertip constellation with `mode="ref"` assumes *"the hand does not change
> shape during the hold"*. In ordinary play the fingers move, so the fit reads
> **finger motion as hand rotation**: orientation p95 **9.85 → 27.79**, ~3× worse
> than the incumbent. The takes that validated it required fingers *"relaxed and
> still"*, which is precisely the condition under which this failure cannot
> appear. ⚠ **A protocol that forbids the motion an estimator is sensitive to has
> not tested it.**
>
> ✅ **What shipped: `Horn(PALM_LANDMARKS, "ref")` — palm-only, no fingertips**,
> ported to `Resources/HandsTriggeredActions.py` on 2026-08-17 and live-confirmed
> by the owner. ⚠ **It shipped on DESIGN grounds, not measured benefit** — the
> balanced blind A/B scored **4–2, p = 0.34**, and p95 was **3–3**. It is not
> better; it is not worse, and a least-squares fit over 5 points cannot degenerate
> the way a 3-vector frame can. State it that way to anyone who asks.

⚠ §16.13's estimator-level result had no cube-level price attached, because the
harness measured cube POSITION only. Measured properly — the shipped rotation
path (delta from grab, slerp 0.35), with the quaternion supplied by each
estimator — **cube orientation step, deg/frame, held cube**:

| take | Gram-Schmidt (SHIPPED) p95 / max / stillMax | **Horn palm+tips (ref)** |
|---|---|---|
| 3 yaw | 2.74 / 5.64 / 5.64 | 2.72 / 6.89 / **3.84** |
| **4b pitch** | 7.42 / **39.94** / **22.89** | 3.82 / **9.64** / **4.21** |
| 5 depth | 0.61 / 1.63 / 1.63 | **0.41 / 0.79 / 0.79** |
| **6 back-of-hand** | 5.36 / **58.86** / **36.54** | 2.18 / **8.40** / **3.48** |

**Pitch: worst step 39.94° → 9.64°, worst still-hand step 22.89° → 4.21°.
Back-of-hand: 58.86° → 8.40° and 36.54° → 3.48° — a 10× reduction** in the two
bands §0.18 calls a sensor floor. Better on every take.

⚠ `ff` (frame-to-frame) edges out `ref` everywhere but **ACCUMULATES DRIFT,
unmeasured**. **`ref` is the ship candidate** — drift-free by construction, and
still 4× on pitch max and 7× at back-of-hand.

⭐ **Horn, not SVD-Kabsch, and that is a safety property**: Horn's answer IS a
quaternion, so a reflection is unrepresentable and handedness cannot silently
invert. §13.6.1 shipped that bug once; M6b's Q1 exists to catch it. Here it is
designed out. `verify_palm_rotation.py` proves it, including on the mirrored
input MediaPipe delivers (§0.9).

⚠ **Power iteration was tried first and was WRONG** — any shift large enough to
guarantee positivity drives λ₂/λ₁ → 1, leaving up to 2.0 of element error, i.e. a
completely wrong rotation at large angles. Caught by the golden vectors before it
reached a measurement. Replaced with a Jacobi eigen-decomposition.

#### Status: BUILT, NOT PORTED

`Resources/palm_rotation.py` (25 golden vectors) and `palm_anchor.Arm2D`
(27 golden vectors). Both are selectable in `debug_prediction.bat`:

    debug_prediction.bat            SIX windows, 3 rows x 2 columns:
        1 §14.1 | 2 §14.1+B7        <- production today
        3 ARM B | 4 ARM B+B7        <- anchor changed
        5 +HORN | 6 +HORN+B7        <- rotation changed

⭐ **Each row is a ONE-VARIABLE change on the row above, verified rather than
assumed** (replayed on the pitch take): the anchor moves ONLY cube position, the
rotation estimator moves ONLY cube orientation.

| row | cube POSITION p95 / max | cube ORIENTATION p95 / max |
|---|---|---|
| 1 §14.1 | 5.09 / 13.57 | 6.22 / 37.57 |
| 3 arm B | **8.11 / 25.07** | 6.22 / 37.57 *(unchanged)* |
| 5 arm B + Horn | 8.11 / 25.07 *(unchanged)* | **3.82 / 9.64** |

Nothing leaks between rows, so a difference seen on screen has exactly one cause.

⚠ **Nothing is in production. A7 holds: §14.1 does not change until the owner
accepts a live look.** ⚠ Both results are REPLAY evidence on seven takes from one
operator, one camera, one session.

### 16.16 ✅ EXECUTED 2026-08-17 — the six-arm live decision (results in §16.17)

> ✅ **This session RAN on 2026-08-17.** Outcome: **§14.1's anchor keeps** (A7
> never broken), **arm B rejected** (§16.14), **`Horn(PALM_LANDMARKS)` shipped**
> (§16.15), **B7's park confirmed under a blind test** (§16.17). The
> pre-registered decision rule below could **not** be applied as written, because
> its primary criterion — SINK — turned out to be degenerate for the candidate it
> was meant to judge. That is recorded in §16.14 and is the session's main
> methodological result.

The owner runs a six-arm live session; the analysis picks the winner and it gets
wired into both the debug tool and production. **The plan, the takes, and the
decision criteria are fixed IN ADVANCE** in `Claude/HANDOFF_ANCHOR_ROTATION.md`
— written before the data exists, so the criteria cannot be chosen to fit it.

Decision rule, binding: **ship the row that minimises the SINK on the pitch
take**, provided its still-hand step is not materially worse than §14.1's, its
cube-orientation max is not worse, and the owner accepts how it looks in free
play. ⭐ **Sink first, jitter second** — §16.5: *"a systematic drift is the defect
the operator actually reported; jitter is not."* ⚠ And the owner's eye outranks
the table: B7 passed every measured criterion and was still, correctly, parked.

Score with `analysis/b4_six_arm_verdict.py` — it reads all six cube tracks
**recorded live**, so no replay confound applies (the offline harness had two).

#### ⚠⚠ What the 2D anchor will cost later, recorded now while it is cheap

**Z-axis.** Arm B's frozen `R` is a 2-vector, so a cube cannot be held in front
of or behind the palm. ⭐ The one decision that makes the retrofit cheap is
already taken — **`R` is stored in PALM WIDTHS, not pixels**, so it is scale-free
and a third component is purely additive. ⚠ But the third axis `ez` can only come
from the 3D palm reconstruction — the channel that degenerates at edge-on and the
measured reason the 3D-native variant loses. So the retrofit adds *a component
whose axis is unreliable in exactly the band arm B was built to survive*; plan a
DR-2-style freeze for it. ⛔ And the real blocker is unchanged: **absolute depth
does not exist in the data at all** (world landmarks are hand-relative), which is
true of every anchor design including §14.1's.

**Web/mobile port.** Both modules are already port-clean (stdlib, numpy-free,
deterministic). Their golden vectors — 27 + 25 — are the executable
specification, written *before* a port exists (U3). ⚠ `palm_rotation` contains a
**Jacobi eigen-decomposition**; a port that "simplifies" it back to power
iteration silently returns wrong rotations at large angles, and
`verify_palm_rotation.py` §1 is the test that catches that. ⚠ A port that swaps
Horn for SVD-Kabsch **must** add the `det` sign correction — §13.6.1 shipped a
silent handedness inversion once, and Horn's quaternion makes it unrepresentable.

### 16.17 ⭐⭐ THE LIVE SESSION — what shipped, what died, and the two method lessons (2026-08-17)

Eleven live six-arm takes plus twelve blind rounds, one operator, one camera.
Everything below is **live**, not replay. Takes:
`E:\…\Recordings_anchor_study\2026-08-17_18*`.

#### ⛔ First: four takes were lost to a one-character bug, and no metric caught it

`LiveBlockPredictionDebug.py` guarded the block that feeds rows 2 **and** 3 with
`if args.arms == 4:`. Commit `2c44634` added the Horn row (`--arms 6`) and made 6
the **default** without widening it, so at the default setting `data_anch` stayed
`None` on every frame: **rows 2–6 never acquired a cube on 4257 recorded frames**,
`owner` null throughout, cube frozen at spawn. `--arms 4` worked; `--arms 6` had
never been run live. **The operator caught it by eye** — *"in the 4 windows
starting from second row, none of the cubes are grabbed nor move"* — after the
takes were recorded and while the verdict script was happily scoring them.

⭐ **Fix + guard**: the end-of-run `[arms]` summary now prints how many frames
each arm held the cube and shouts `NEVER ACQUIRED` on zero, while the take can
still be re-recorded. ⚠ **A take is only comparable while the cube is
CONTINUOUSLY HELD** — after a drop each arm's cube sits somewhere different, so
re-acquisition diverges and the one-variable guarantee dies. That is a recording
requirement, not a nicety.

#### The verdicts

| candidate | verdict | why |
|---|---|---|
| **§14.1 anchor** | **KEEPS** — A7 never broken | arm B lost on the one criterion that could still discriminate |
| **ARM B** | ⛔ **REJECTED** | still-hand worse on all 4 takes; its winning metric is an identity (§16.14) |
| **HORN `PALM_AND_TIPS`** | ⛔ **REJECTED** | p95 9.85 → 27.79 in play; finger motion read as rotation (§16.15) |
| **HORN `PALM_LANDMARKS`** | ✅ **SHIPPED** | not better (4–2, p = 0.34), not worse, structurally safer |
| **B7 confirmation gate** | ⛔ **PARK CONFIRMED** | 4–2 blind, p = 0.34 — real but imperceptible |

#### ⭐⭐ Method lesson 1: a metric that shares an expression with its subject

§16.14 in full. The short form: **SINK could not have said anything other than
"arm B wins."** Any future anchor metric must compare against a quantity the
anchor does not define.

#### ⭐⭐ Method lesson 2: an unbalanced blind test MANUFACTURES results

Two blind series were run on the same operator, same task, same day.

| series | design | result |
|---|---|---|
| horn-palm vs Gram-Schmidt | 6 rounds, **free** random draw | **5–1 for horn-palm** — looked convincing |
| B7 vs no B7 | 6 rounds, **balanced** 3/3 | 4–2, p = 0.34 — nothing |
| horn-palm vs Gram-Schmidt, **redone** | 6 rounds, **balanced** 3/3 | **4–2, p = 0.34 — the 5–1 did NOT replicate** |

The operator answered in a perfectly alternating pattern (A,B,A,B,A,B) in both
early series — the textbook signature of guessing. A free draw put one arm on "A"
in 4 of 6 rounds, and **the alternation alone reproduces 5–1**. Enumerated:
P(alternating guess scores ≥ n−1) is **10.9%** for 6 free rounds, **5.0%**
balanced, **1.4%** for 8 balanced. The 10.9% *is* the 5–1 that was nearly
believed — and it was nearly used to justify shipping.

✅ **Binding for every future blind test: use `--blind-series`**, which draws one
balanced permutation for the whole series and consumes one round per run. Never a
free per-run draw. ⚠ **And no channel may leak the condition** — the hand blocks
had to stop carrying B7's amber/red channel colouring, which would have announced
the gated window outright.

#### What is now in production

`Resources/HandsTriggeredActions.py` drives cube orientation with
`Horn(PALM_LANDMARKS, "ref")`; 25/25 golden vectors pass, live-confirmed by the
owner. `LiveSnapDebug.PRODUCTION_ROTATION` is the single shared definition, and
`debug_snap.bat`, `RecordRotationDebug.py` and `RecordTranslationPivotDebug.py`
all pass it explicitly. ⚠ `update_hands(rotation=None)` **still means
Gram-Schmidt on purpose** — `LiveBlockPredictionDebug` rows 1–2,
`b4_anchor_rotation_ab.py` and `b7_live_ab.py` all rely on it to hold rotation
constant. Change that default and three A/Bs silently start comparing a thing
against itself.

### ⚠ Binding architectural constraint (spec S3, Apple's shipped design)

**Predicted state must NEVER reach a gesture state machine.** The split is:
predicted blocks for *rendering / attachment*, unpredicted blocks for *grab and
release decisions*. Prediction artifacts must not latch into a gesture. Build the
split even if prediction is later skipped entirely.

---

<!-- VERBATIM-END -->
