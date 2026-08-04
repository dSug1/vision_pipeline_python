# Build brief — confirmation gate (B7) and quadratic optimisation (B8)

**Written 2026-08-04 for a fresh conversation.** Self-contained: you should not
need to re-derive anything below. Read this, then build.

> ⚠ **This is NOT a second TODO list.** The single build queue remains
> `PART_ONE.md` §3.1, which carries rows **B7** and **B8** pointing here. This
> file holds the *design and test protocol* for those two rows only.

---

## 0. Read first (10 minutes, and it will save you a day)

| # | read | for |
|---|---|---|
| 1 | `GESTURE_PIPELINE_SPEC.md` **§16 → §16.6** | the block representation, the coasting policy, and the two failed gate attempts |
| 2 | `PERCEPTION_LAYER_SPEC.md` **§0.17, §0.18** | why item 1.6's gate was parked, and why Phase 1 closed |
| 3 | `Local_pc/Movement_with_hand_detection/analysis/README.md` | which script produced which claim, and the measurement bugs found so far |

**The one-paragraph history.** Two predictive outlier gates have been built and
both failed. Item **1.6** used a single channel, a *two-sample* velocity and a
fixed threshold: it rejected ~4 real fast movements per teleport caught, at every
threshold (§0.17). Item **B3″** fixed all of that — seven channels, explicit
`p, v, a` from a least-squares quadratic, a real OLS predictive distribution,
angular velocity *and* acceleration by log map, a horizon that grows while
coasting — and **still failed**, rejecting direction reversals **7.43× more often
than other frames** (§16.6). Both are parked and unwired.

**Why B7 is not a third attempt at the same thing.** Both failures share one
cause: **a reversal is unpredictable from past data by construction.** No
forward extrapolation, however good, can tell "the hand turned around" from "the
landmark jumped" *at the moment it happens*. B7 changes the question rather than
the model — it **defers the decision** until later frames disambiguate.

**The evidence that this will work.** The out-and-back test used as *ground
truth* throughout this project's analyses — "did the hand return to its prior
trajectory within N frames, or continue?" — **separates cleanly**: 7.9% teleport
vs 80.2% real movement (`analysis/m4_rejection_audit.py`). B7 is that same
discriminant made causal-with-lag. The discriminant is known to work; the only
open question is how much lag it needs.

---

## 1. B7 — the confirmation gate (selective fixed-lag smoother)

### 1.1 Design

Owner's formulation, 2026-08-04:

> *"F-7 frames provide the quadratic, the F frame flags if it is an outlier, F+1
> and F+2 confirm if F was an outlier or, if F, F+1 and F+2 are coherent, the
> genuine direction change is confirmed and F+2 resets the position... I would
> rather have F and F+1 at predicted position and then a F+2 slerped into correct
> position: this will create a short latency at direction change but no latency
> at all for all the rest of the cases."*

Per channel, per hand:

```
state NORMAL:
    residual small  -> accept, output = measurement          (no latency, ever)
    residual large  -> FLAG, enter PENDING, output = prediction

state PENDING (holding L frames):
    buffer the incoming measurements F..F+L
    output = prediction (the cube keeps moving; nothing freezes)

at F+L, decide:
    COHERENT      -> the flagged frames form a consistent trajectory of their
                     own => a GENUINE change. Blend the output back to the
                     measured trajectory (slerp/lerp over ~2 frames so the
                     arrival is not a snap), and feed F..F+L into the fit.
    RETURNED      -> the stream came back to the pre-F trajectory => F WAS an
                     outlier. Discard F..F+L-1, resume from the measurement,
                     and do NOT let the discarded frames enter the fit.
    AMBIGUOUS     -> treat as COHERENT. Accepting a real movement late is a
                     smaller sin than rejecting one.
```

### 1.2 The coherence test

Reuse the shape that already works as ground truth. With `p_pre` = last accepted
position before the flag, and `p_k` = measurements at F..F+L:

```
out    = |p_F   - p_pre|
back   = min over k in F+1..F+L of |p_k - p_pre|
return_ratio = back / out

return_ratio < 0.5  -> RETURNED (outlier)
return_ratio > 0.9  -> COHERENT (genuine)
otherwise           -> AMBIGUOUS
```

⚠ Those thresholds come from `m4_rejection_audit.py` where they separated the
populations. **Re-derive them on the block channels rather than inheriting them
blindly** — they were tuned for palm-centroid position, not for arcs or
quaternions.

For the **quaternion** channel use angle instead of distance; for **arcs** and
**scale**, scalar difference.

### 1.3 What must be preserved from the existing design

These are binding and already cost this project real time:

- **Per-channel decisions**, not per-frame (§16.2 rule 1). A confused finger must
  not discard a good palm.
- **The estimator never learns from an inferred value** (§16.2 rule 6). Only
  accepted measurements enter the fit and the residual history.
- **Hard coast cap** as a backstop (`MAX_COAST_FRAMES`). B7's lag bounds the
  decision, but a rule should not depend on the discriminant behaving well.
- **⚠ S3, binding**: predicted state must NEVER reach the grab/release state
  machine. While a channel is PENDING, gesture logic **holds** — no new snap, no
  release — it does not act on the prediction. Rendering uses the output.
- **Full reset on tracking loss / run break.**

### 1.4 Sweep

| parameter | values | why |
|---|---|---|
| **L** (lag) | 2, 3, 4, 6 | ⚠ **The critical one.** The documented Object Jump lasts "a few frames" and self-corrects (§14.1.4). If a teleport persists through F+L it looks coherent and is **accepted**. The ground-truth labeller needed **6** frames to separate. L=2 is ~83 ms; L=6 is ~250 ms |
| blend length | 1, 2, 3 frames | how sharply the output rejoins truth after a COHERENT verdict |
| ambiguous policy | coherent / returned | confirm that "accept when unsure" is the right default |

### 1.5 ⚠ Honest limits — read before expecting too much

1. **B7 will NOT fix edge-on or back-of-hand precision.** Those are *sustained*
   errors: at edge-on the whole palm reconstruction collapses coherently (§0.18)
   and stays wrong for many frames, so F..F+L all agree **in the wrong place**,
   the test reads COHERENT, and the gate **accepts** them. B7 separates
   *transient* from *sustained*; it cannot separate *sustained-correct* from
   *sustained-wrong*. Those two targets need a different mechanism (a second
   camera, or DR-2-style suppression).
2. **Teleports longer than L are accepted**, for the same reason. Hence the sweep.
3. **Latency is real.** L=2 is ~83 ms and the published threshold for clearly
   perceived artifacts is ~75 ms. It is paid only at reversals and outliers, but
   it is not free — **report it in milliseconds, not frames.**

---

## 2. B8 — optimising the quadratic

**A separate lever, and do not conflate them.** B8 improves how *accurately* the
next value is predicted. B7 decides *when to trust the measurement*. Optimising
weights alone would improve jitter and leave B3″'s 7.43× reversal ratio roughly
intact — that was measured.

Current fit (`Resources/block_predictor.py`, `fit_channel`): **unweighted**
least-squares quadratic over **7** accepted frames, all frames counted equally.

| degree of freedom | values | note |
|---|---|---|
| **weighting** | uniform, exponential decay (half-life 2/3/5 frames), linear ramp | ⚠ **Currently unweighted — the most obviously wrong part.** Recent frames should count more |
| window | 5, 7, 9, 11 | ⚠ ≥ order+2 or the residual variance `s²` is meaningless, and `s²` *is* the distribution |
| order | 1 (velocity), 2 (＋acceleration) | B3″ measured order 2 as *worse* than order 1 for rejection quality — re-test with weighting |
| `ACCEL_UNCERTAINTY` | 0, 0.5, 1.0, 2.0 | widens σ by \|½·a·h²\|; measured to scale rejections down without changing the reversal ratio |

**Judge B8 on prediction error, not on gate behaviour**: one-step and L-step
`|measured − predicted|` per channel, and — per **S1, mandatory** — it must beat
**zero-velocity and constant-velocity baselines at every horizon**. That
discipline exists because published predictors have repeatedly lost to those
baselines. `analysis/audit_jump_provenance.py` has the orientation precedent.

---

## 3. Test protocol — the same one both items are judged by

### 3.1 ⚠ The disqualifying test, run FIRST

**Direction-reversal safety.** A failure here disqualifies the configuration
regardless of everything else — it means the gate eats real gestures.

```
rejection rate at reversal frames  vs  rejection rate elsewhere
requirement: ratio -> ~1.0        (B3'' scored 7.43x and was parked)
```

Reversals are labelled **non-causally** from raw velocity sign changes,
independent of the gate (`analysis/b3_full_eval.py::reversals`). The rotation
takes are the clean population: every pitch/yaw cycle contains exactly **two**
reversals, and operator cycle counts are in each session's `meta.json`.

### 3.2 The four targets

| target | corpus | measure |
|---|---|---|
| jitter | still-hand frames (palm move < 1.5 px/frame) | p50/p95/**max** of output step, raw vs gated |
| edge-on | `edge_on_measure < 0.15` | same |
| back-of-hand | `known_*_back`, `palm_back_s*` | orientation step deg/frame, p95 and max |
| teleport | `two_hand_overlap` / `two_hand_near_miss` (2026-08-04, recorded **with rotation** for this) and `jump_test4` | **classified**, see below |

### 3.3 Mandatory counter-metrics

- **⚠ CLASSIFY REJECTIONS, NEVER COUNT THEM.** A count cannot tell removing the
  failure from removing the feature. This reversed item 1.6's verdict after it
  had already "passed" (§0.18). Every rejection must be labelled teleport /
  real-movement / ambiguous by the non-causal test.
- **Tracking cost**: |output − raw| on frames the raw deserves belief. A gate
  that rejects everything scores perfectly on §3.2 and is worthless.
- **Latency in milliseconds**, per configuration.

### 3.4 Binding rules

- **Streams via `audit_jump_provenance.build_v2()`** — DR-1 replay, duplicate-label
  skip, run-break at frame gaps. Never key a stream on the raw MediaPipe label.
- **Never pool rotation axes.** Pitch-sink and yaw-sink have **opposite signs**,
  so pooling cancels them — that is how §16.4 measured a benign 0.138 while the
  isolated axes were 0.822 and 0.323 (§16.5). Report per take.
- **Check `measured_fps` before any cross-session comparison** (N10).

---

## 4. Where everything is

**Modules** (`Local_pc/Movement_with_hand_detection/Resources/`) — all stdlib,
numpy-free, no side effects, web-portable:

| file | role |
|---|---|
| `hand_blocks.py` | the block view: palm transform + 4 arcs (thumb raw) |
| `block_predictor.py` | **B3″ — extend this for B7/B8.** Explicit p/v/a, OLS predictive variance, log-map angular velocity, derived floors |
| `block_tracker.py` | superseded half-version, kept for its ablation record. Do not extend |
| `palm_geometry.py` | `edge_on_measure`, DR-2's `PalmFacingTracker` |
| `hand_identity.py` | DR-1 (lives in the **server** Resources folder) |

**Harnesses** (`analysis/`):

| file | role |
|---|---|
| `b3_full_eval.py` | **the test protocol above, already implemented.** Extend rather than rewrite |
| `verify_block_predictor.py` | synthetic correctness — p/v/a, ω, α, variance growth. Keep it passing |
| `calibrate_floors.py` | derives the absolute floors from `static_hold` |
| `m4_rejection_audit.py` | the non-causal out-and-back classifier B7 is based on |
| `b4_anchor_ab.py` | the anchor A/B to re-run afterwards |

**Data**: perception corpus at
`E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions`
(33 sessions); pivot takes at `...\Position_during_rotation` (9).

### ⚠ Environment traps that will cost you time

- **`Position_during_rotation` is NOT readable from Python** in this environment
  (PermissionError; PowerShell reads it fine). Copy the files elsewhere first.
- **`.notes.json` sidecars** sit alongside pivot recordings, are BOM-encoded and
  are **not recordings** — skip them and read `utf-8-sig`.
- **Pivot takes recorded before 2026-08-04 carry SYNTHESISED 33 ms timestamps**
  (N17) and report ~30.4 fps when the real rate was ~24. Per-frame geometry is
  fine; **any real-time derivative from them is wrong by ~25%.** The recorder is
  fixed; the old files cannot be. Check the `timestamps` field.
- **E: drops out intermittently** (N4, several times per session). Retry loops
  around recorder and analysis invocations.
- `audit_jump_provenance` loads the whole corpus at **import** and silently
  yields 0 sessions if E: is away, then crashes on an empty list.

---

## 5. Acceptance criteria — decide these before running, not after

**B7 ships only if all four hold:**

1. reversal-rejection ratio **≤ 1.5×** (B3″: 7.43×)
2. classified rejections **majority teleport, not real movement** (1.6: 7.9% / 80.2%)
3. jitter and edge-on **improved, and max not worse** (B3″ made max 43× worse)
4. added latency **stated in ms** and accepted by the owner

**B8 ships only if:** prediction error beats **both** the zero-velocity and
constant-velocity baselines at every horizon (S1).

**If B7 fails**, record it as the third measured failure of causal outlier
gating on this sensor and stop — the remaining options are a second camera or
item 3.2's RTS smoothing, which costs latency for everyone.

---

## 6. Then, and only then: reconsider arms A / B / C

The anchor A/B (`b4_anchor_ab.py`) is currently unresolved, and the owner has
withheld acceptance pending a working gate — reasonably, since its metrics are
jitter p95/max and edge-on motion, all dominated by the outlier frames a gate
would remove.

Current state (§16.5), on purpose-built takes:

| | A §14.1 | B palm+scale | C palm rigid |
|---|---|---|---|
| yaw-sink \|r\| | 0.822 | **0.001** | 0.815 |
| pitch-sink \|r\| | 0.323 | **0.005** | 0.194 |
| N12 jitter p95 | 4.173 | 1.431 | **1.423** |
| yaw jitter p95 | **2.235** | 5.486 | 6.848 |

**Arm B leads**, but no arm wins cleanly. Re-run all arms through the winning
gate configuration and re-decide. ⚠ §14.1 must not be modified before that
(A7).

⭐ **And remember why §16.4's first verdict was wrong**: it was measured on takes
containing neither a sustained yaw hold nor a pitch crossing — *neither condition
the claim was about* — and it pooled the axes so the opposite-signed drifts
cancelled. **Before trusting any A/B, ask what is actually in the takes.**
