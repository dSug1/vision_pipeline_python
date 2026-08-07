# Measurement harnesses — the evidence behind the 2026-08-03 findings

Every non-obvious claim in `Claude/PERCEPTION_LAYER_SPEC.md` §0.6–§0.14 was produced
by a script in this folder. They are kept **because the conclusions are only as good
as the code that produced them**, and several of those conclusions are negative
("the spec's premise does not hold for this sensor"). A reader who cannot re-run the
measurement cannot check the claim.

**Run from the parent directory**, e.g.:

```
cd Local_pc/Movement_with_hand_detection
.venv/Scripts/python.exe analysis/where_are_jumps.py
```

They read the recorded corpus from
`E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions`
(24 sessions) and import the shared perception modules from `Resources/`.

---

## ⚠ Read this before trusting any number here

**Four measurement bugs were found and fixed *during* the session, each of which had
already produced confident, wrong numbers:**

| bug | symptom that exposed it |
|---|---|
| iterated `rec["hands"]` without separating hands, so the angle *between* the two hands counted as a per-frame jump | 575 of 576 "jumps" in a **static hold** |
| motion gate written in millimetres against metre-valued `worldLandmarks` | gate never fired; every frame accepted |
| `sigma_long` and `sigma_base` conflated (twice) | "anisotropic" filter was isotropically over-damped, and scored beautifully |
| live test asked the operator to judge a state the UI does not display | operator correctly reported they could not tell |

Four self-caught errors is not evidence of rigour — it is evidence of error density.
**Assume more survived.** These harnesses are the right place to look for them.

---

## ⚠⚠ THEY DID SURVIVE — audit of 2026-08-03. Read this before running anything here.

The instruction above was acted on. **A fifth and sixth bug were found, both in
scripts listed below**, and the corrected harnesses are:

| script | what it audits |
|---|---|
| **`audit_jump_provenance.py`** | the jump census + every 2.3-era filter A/B + the motion-model claim, on identity-corrected streams |
| **`audit_m2_proportions.py`** | M2's acceptance test, re-measured against *proportions* rather than absolute lengths |

### Bug 5 — every 2.3-era A/B measured a pipeline that no longer exists

`where_are_jumps.py`, `m6c_ab.py` (whose stream loop the others import),
`obs_ab.py`, `m6_ukf_ab.py`, `m6_gated_ab.py` and `chi2_probe.py` all build
per-hand streams keyed on the **raw MediaPipe handedness label**, with **no
duplicate-label guard and no frame-continuity guard** — on the corpus recorded
specifically *because* it contains label flips, duplicate labels and association
swaps. Production runs DR-1 (`hand_identity.py`); these replayed pre-DR-1
streams. Effect: **>60° jumps 730 → 572, and "82% at observability ≥ 0.60" →
~77%.** The §0.13.2 *conclusion* survives; its numbers do not. **Re-running the
filter A/Bs on corrected streams reproduces every null verdict** — the discards
are safe.

> **Binding rule now: build streams with `audit_jump_provenance.build_v2()`**
> (DR-1 replay + dup-label skip + run-break at frame-index gaps). The old
> raw-label loader survives there as `build_v0()` **only** to reproduce
> historical numbers. Never key a stream on the raw label again.

### Bug 6 — `chi2_probe.py`'s headline was a cascade statistic, not a prediction error

Its "60% of frames disagree by >25°" was read as *the motion model is weak* and
that claim reached the spec (M7's ⚠⚠ STOP block) and the queue. It is **closed
loop**: a rejected frame makes the filter coast, the prediction drifts, and
following frames keep failing until the 8-frame coast limit force-accepts — one
bad frame books up to 8 rejections. Measured open loop, the one-frame model
error is a **4.2–4.5° median** (>25° on 6.4–11.4%). **Claim retracted; item 3.1
unblocked.** `audit_jump_provenance.py` also prints the full 1/2/3-frame horizon
table, which is item 3.1's "required first task", done.

### And the M2 kill was measured against the wrong quantity — but survives anyway

`m2_which_bones.py` / `m2_pooled.py` pool **absolute metre lengths**, while the
spec's §2f target is *proportions plus a per-session scale constant*.
`audit_m2_proportions.py` re-measures proportions: **still 0/21 bones inside
2%**, cross-session disagreement 32–40%. Verdict upheld on the correct quantity.

**Lesson, for the next harness: state which quantity the module CLAIMS, and
measure that one.** Two of three load-bearing negatives had a measurement-design
flaw; only one of them changed the answer.

---

## The claims and the scripts that produced them

### Audit harnesses (2026-08-03) — run these before trusting the two tables below

| script | produces |
|---|---|
| `audit_jump_provenance.py` | V0/V1/V2 jump census (V0 reproduces the published numbers exactly); open-loop 1/2/3-frame motion-model error; the 2.3 filter A/B re-run on identity-corrected streams |
| `audit_m2_proportions.py` | M2 acceptance on absolute lengths (A), palm-normalised proportions (B) and cross-session normalised medians (C) |

### Load-bearing — if these are wrong, plans change

| script | claim it produces | where recorded |
|---|---|---|
| `where_are_jumps.py` | **82% of >60° orientation jumps occur at observability ≥ 0.60.** Killed item 2.3 and re-pointed T1/T2 from 2.3 to 1.4/1.6 | §0.13.2 |
| `m2_which_bones.py` | **0/5 palm and 0/5 fingertip bones reach M2's <2% gate** (6–22% IQR). Killed 1.4's acceptance; puts M9, T4 and M4's error signal at risk | §0.14 |
| `m2_pooled.py` | Pooled cross-pose calibration, half-vs-half: 4.0% / 24.3% disagreement vs <2% target | §0.14 |
| `resolve_convention.py` | **The handedness label is the MIRRORED hand** — a physical right hand is labelled `"Left"`. Settled by which side the label falls on in two-hand frames | §0.9 |

### Filter A/Bs — five failed attempts at item 2.3

| script | what it tested |
|---|---|
| `m6b_compare.py` | M6b's SVD frame vs the shipped Gram-Schmidt frame → **SVD 2.1× worse** |
| `obs_ab.py` | `observability` vs `conditioning_norm` driving the shipped filter → **observability loses** |
| `m6c_ab.py` | attempt 1: single-sigma anisotropic (**over-damped**; also defines the shared helpers the others import) |
| `m6c_detail.py` | controls / tail / redistribution check for attempt 1 |
| `m6c_axis.py` | axis-ordering question — **the spec's ordering is marginally better**, my rod-spin hypothesis was wrong |
| `m6c_lag.py` | **introduced the tracking-error metric** that exposed the over-damping (37° from a trustworthy measurement) |
| `m6c_fixed.py`, `m6c_2d.py` | attempts 2–3, two-parameter form |
| `m6_ukf_ab.py`, `m6_ukf_tight.py` | attempt 4: **propagated covariance** (the real filter) — 54 configs, none wins both |
| `m6_gated_ab.py` | attempt 5: gated passthrough — tracked perfectly, **fixed nothing**, which triggered `where_are_jumps.py` |
| `chi2_probe.py` | salvage probe: χ² / physical gate → **3.7× and 24× worse**. ⚠ **Also the source of the RETRACTED M7 motion-model warning — see bug 6 above.** The gate's own failure is real (cascade); the generalisation drawn from it was not |

### M3a anatomical constraints (item 1.5, 2026-08-04)

| script | produces |
|---|---|
| `m3a_violations.py` | violation rates per session for `Resources/hand_anatomy.py`, with the **control first** (`static_hold` — every violation there is a false positive) and a **per-hand-label breakdown**. Headline: **0/1446 control hand-frames, 5–59% on the failure poses** |
| `m3a_diagnose.py` | the distributions behind the constraint design — bend angles, rotation-sense agreement per axis pair, and both candidate hinge-plane definitions. **This is what caught the first version's 93.7% false-positive rate** |
| `m3a_predicts_jumps.py` | **the A10 gate on item 1.5, and the design input for 1.6.** Crosses the validity bit against the large orientation jumps on `build_v2` streams: **lift 33.8×, coverage 92.0%** on >60°, but only 7.5% of flagged frames jump. Verifies its own stream construction by reproducing `build_v2()`'s census before reporting anything |

⚠ **`m3a_diagnose.py` is the reason the module is correct**, and the pattern
generalises: the first M3a constraint set fired on 93.7% of a *still, valid* hand.
Dumping distributions showed why in one run — `dot(MCP axis, PIP axis)` was 31.1%
negative on valid hands (the MCP extends while the IPs flex, so that pair is not
an anatomical constraint at all) while `dot(PIP axis, DIP axis)` was 0.0%
negative. **Always have a control take, and diagnose against it rather than
loosening the threshold until the corpus goes quiet.**

⚠ **The thresholds are clinical goniometry norms, NOT corpus-fitted.** Do not
"improve" them by tuning against these recordings: item 0.5 (the external oracle
that would have caught such circularity) is dropped and is not coming back, so
nothing downstream would notice.

### M4 frame gate (item 1.6, 2026-08-04)

| script | produces |
|---|---|
| `m4_cue_distributions.py` | the cue distributions the gate's thresholds are DERIVED from (not guessed), plus the measurement that **80.8% of large position innovations occur on anatomically valid frames** — which is why M3a is not wired into the gate |
| `m4_gate_ab.py` | the A10 A/B: **54% of >1.0 palm-width excursions removed at 0.40% rejection and 0.00004 palm widths of tracking cost**, plus the per-cue ablation that removed two of the four cues. Verifies its own centroid/width primitives against `hand_identity`'s before reporting |

⚠ **Report BOTH metric families or the result is void** — excursions removed AND
tracking cost on trustworthy frames. This is the same discipline the orientation
work learned the hard way (see "Two metrics" below): a gate that rejects
everything scores perfectly on the first.

⚠ **Do not re-add bone-length deviation or M3a tightening to the gate.** Both
were built, measured and removed on 2026-08-04; the ablation table is preserved
in `Resources/frame_gate.py`'s docstring so the null result is not retried
blindly.

### Phase 1 closure (items 1.5 / 1.6 / 1.7, all PARKED 2026-08-04)

| script | produces |
|---|---|
| `m4_rejection_audit.py` | ⭐ **the measurement that reversed 1.6's A10 pass.** Classifies each rejection as teleport (came back within 6 frames) or real movement (kept going): **7.9% vs 80.2%**, and a threshold sweep showing the ~4:1 ratio never improves |
| `m4_speed_tradeoff.py` | rejection rate vs hand speed and acceleration, per-session and within-session. Locates the operator's speed-ramp take and shows the deliberately fast `palm_back_s4_fast` at **0 rejections** |
| `m2b_skeleton_ab.py` | the 1.7 A/B: fingers-only fit changes orientation by **0.0%** (structural — the frame uses no finger bones), whole-hand fit costs 3× the distortion for a noise-level change |

⚠⚠ **BINDING RULE, learned the expensive way here.** Item 1.6 initially PASSED
its A/B: "54% of position excursions removed at near-zero tracking cost." The
metric could not tell a *correct* rejection from a *wrong* one, so deleting the
owner's real fast movements scored as success. `m4_rejection_audit.py` exists
because of that.

> **Any module that rejects or suppresses data must CLASSIFY what it removed,
> not merely count it.** A count cannot tell you whether you removed the failure
> or the feature. This is the same trap as "jump counts reward an over-damped
> filter" (below), and it was walked into by a harness quoting that very lesson.

Owner's acceptance bar, recorded because it is a product decision rather than a
technical one: *"what I captured in the recordings are rapid movements but still
acceptable expected inputs for my game."* **Rapid movement is input, not noise.**

### B7 / B8 — the confirmation gate and the fit behind it (2026-08-04)

| script | produces |
|---|---|
| `verify_confirmation_gate.py` | synthetic correctness for `Resources/confirmation_gate.py` on signals whose ground truth is known by construction: a teleport is DISCARDED, a reversal is CONFIRMED (accepted late, never thrown away), per-channel isolation, the S3 valid-bit, the hard cap, and the coast-mode overshoot ordering. ⚠ B3″ passed *its* synthetic test and then failed on the corpus — passing here proves the mechanism, never the usefulness |
| `b7_eval.py` | the B7 sweep: verdict test × coast mode × lag × fit, judged on reversal safety first. Imports `b3_full_eval`'s stream builder and reversal labeller so every row is comparable to B3″'s line by line |
| `b8_fit_sweep.py` | 15 fit configurations (weighting × window × order) against the two baselines **S1** makes mandatory, open loop, **stratified by hand speed**. ⚠⚠ **All 15 lose to "hold the last value"** at some horizon — including the orientation model. Order 2 is measurably worse than order 1 everywhere |

| `verify_palm_anchor.py` | ⭐ **GOLDEN VECTORS for `palm_anchor.py` (B4)**, including §5, the **Z-retrofit reduction**: the 3D-native form must reproduce the flat 2D similarity form to 1e-6 px when the offset lies in the image plane. That test is what makes "the retrofit is one function" provable rather than hopeful. ⚠ Do not edit the expectations to match a port |
| `b4_six_arm_verdict.py` | ⭐ **the decision script** — scores all six live arms per take from a `--arms 6` recording. ⚠ No replay: the arms ran LIVE on the same frames, so none of the replay confounds apply. Ranks by |sink| with jitter as tie-break, because §16.5 says a systematic drift is the reported defect and jitter is not |
| `verify_palm_rotation.py` | ⭐ **GOLDEN VECTORS for `palm_rotation.py`**, incl. §4 CHIRALITY: Horn's answer is a quaternion, so a reflection is unrepresentable and handedness cannot silently invert (§13.6.1, M6b Q1). ⚠ Its §1 caught a real bug before any measurement: power iteration on the shifted 4x4 leaves up to 2.0 of element error because the shift drives lambda2/lambda1 to ~1 |
| `b4_anchor_rotation_ab.py` | ⭐ **the anchor x rotation A/B on the 7 purpose-built takes**, per take, never pooled. ⚠ Two of its own bugs are documented in-file: the trim removed the grab so the replay never held a cube (all-NaN), and a stale `raw`/`win` leak made 7 takes print IDENTICAL rows |
| `b7_live_ab.py` | ⭐ **the LIVE A/B** on a take recorded by `debug_prediction.bat`: what the gate did to the **CUBE**, plus a replay sweep over every degree of freedom. Replays the full pipeline offline and deterministically, so a config sweep is an exact A/B rather than a second live session |

**Verdicts**: ⛔ **B7 is PARKED** (owner, 2026-08-04, §16.9.1) — measured, cleared
of both its apparent blockers, then declined because the gain is real but **not
visible**. B8's S1 check fails for every configuration (§16.8).

⚠⚠ **BOTH of B7's "failed" criteria were MEASUREMENT ERRORS, and they were the
same error twice.** Criterion 3 was judged on palm channels because the corpus
has no cube; on the cube it passes. Criterion 1 was a B3″-era proxy for a
*cascading* mechanism B7 does not have — measured directly, the gated cube turns
on the **same frame** as the raw one (lag p50 = p90 = 0 ms over 1671 direction
changes). Both were caught only after someone looked at what the criterion was a
proxy *for*.

> **Ask what level a criterion is evaluated at, and what harm it proxies for —
> not merely whether it passes.** A corpus can only measure what it contains, and
> a proxy inherited across a mechanism change measures the old mechanism.

⚠⚠ **§16.7's criterion 3 was measured ONE LEVEL ABOVE THE DEFECT, and live data
overturned it.** The corpus contains no cube, so "max not worse" was evaluated on
palm channels — where the gate does make things worse. On the cube, whose anchor
is a weighted mean over 9 landmarks and therefore low-passes exactly the
coast/rejoin transient the gate adds, the same gate *improves* the worst step by
21% and the worst still-hand step by 47%.

> **Ask what level a criterion is evaluated at, not just whether it passes.** A
> corpus can only measure what it contains, and a metric one level above the
> defect can invert the verdict.

⚠ **And the first live pass measured a bug, not the gate.** The gated `scale`
channel was back-projected onto landmarks as `gated_scale / raw_scale` — a ratio
whose denominator COLLAPSES edge-on. It reached 35.4 and threw the hand 5235 px
across a 640 px window. **It was caught by the owner watching the screen, not by
any harness here**, which is the argument for `debug_prediction.bat` existing at
all. Fixed by never back-projecting `scale` (see
`LiveBlockPredictionDebug.LANDMARK_CHANNELS`); the numbers from that pass are void.

⚠⚠ **A TAUTOLOGY GOT INTO THE FIRST RUN OF `b7_eval.py`, and it printed a
triumph.** Discards were classified with the out-and-back test at a 6-frame
lookahead — while the gate's own verdict was the same expression over L frames.
A minimum over 6 frames is never larger than a minimum over 2, so **every discard
was labelled "teleport" by algebra**, and the harness duly reported
*"discards: 100.0% teleport, 0.0% real movement"*.

> **A classifier that shares an expression with the thing it judges is measuring
> itself.** The load-bearing evidence in that harness is the reversal cross-tab
> instead — reversal labels come from raw velocity sign changes and share nothing
> with any verdict test. This is §0.18's lesson in a new costume, and the third
> time this project has walked into it.

⚠ **Do not re-derive the coherence test from `m4_rejection_audit.py` again.**
Its shape (distance from the last accepted value) was measured to discriminate
**not at all** on these channels — 1.13× — because m4 measured a 2D palm
centroid while the block channels are signed scalars, and *a reversal comes back
through the value it started from*. Distance from the PREDICTED TRAJECTORY
scores 0.38× on the same data.

### N7 — measured frame rate (2026-08-04)

| script | produces |
|---|---|
| `n7_measured_fps_ab.py` | the DR-1 A/B: **20 of 21 sessions within 1 fps of 24 give IDENTICAL assignments** (a no-op where the old assumption held is the pass condition), while 19–21 fps sessions move from a 12- to a 10–11-frame switch dwell |
| `n7_dr2_dwell_ab.py` | ⭐ **the REJECTED half.** A time-based dwell for DR-2 froze **+47.4% more frames (595 → 877)** — the variant lives in this script, not in the shipped module, so the null result stays reproducible without dead code in production |

⚠ **Lesson worth carrying beyond N7**: `exit_run >= 2` exits on the SECOND
consecutive frame — **one frame interval, ~42 ms at 24 fps, not the ~83 ms that
"2 frames" suggests.** Mis-reading that produced a confident wrong prediction
(~20% ceiling) which the measurement then blew past, and that mismatch is what
forced the re-think.

**The distinction it established**: a *"resume after N consecutive
confirmations"* **debounce** belongs in frames. N1's "re-express frame parameters
in ms" applies to dwells representing real elapsed **time** — DR-1's voting
windows do; a debounce does not. Converting one to the other silently doubles it.

### Web/mobile port contracts

| script | verifies |
|---|---|
| `verify_frame_rate_estimator.py` | ⭐ **GOLDEN VECTORS for `FrameRateEstimator`** (N7). Timestamp sequences → expected fps and dwells. **This is the executable specification for the JS port**: a reimplementation is correct when it reproduces the table, and untrusted until it does. Do not edit the expectations to match a port |
| `verify_observability.py` | the same idea for `palm_observability` — numpy-free closed form matches numpy SVD to 1.6e-11 |

⚠ **The vectors earned their keep on their first run**, by catching a real
portability bug: Python's `round()` is banker's rounding (half-to-even) while
JavaScript's `Math.round` is half-up, and the DR-1 dwells land exactly on `.5`
at odd frame rates (500 ms × 13 fps = 6.5 frames). Python gave 6, a JS port
would have given 7 — a divergence that would never surface in normal testing.
`hand_identity._round_half_up()` now fixes the convention in shared code.

**Rule this establishes**: anything designated for the port gets golden vectors
*before* the port exists, not after. Reasoning about equivalence is not
evidence — the two languages disagreed on arithmetic nobody would have thought
to check.

### Shipped-module verification

| script | verifies |
|---|---|
| `verify_edge_on.py` | `edge_on_measure` matches the analyser to **5.55e-16** over 22,345 frames (item 1.2) |
| `verify_observability.py` | numpy-free `palm_observability` matches numpy SVD to **1.6e-11** (web-port readiness) |
| `guard_sensitivity.py` | the chirality drift guard still **rejects 5 real mutations** after being fixed — i.e. it is not vacuous |
| `dr2_ab.py` | DR-2 A/B: 2 of 10 ground-truth streams improved, 0 worsened, controls inert (item 2.2) |
| `dr2_latency.py` | DR-2 freeze duration: median **96 ms**, but p99 **1.8 s** / max **3.5 s** — the tail recorded in `GAME_RULES.md` rule 3 |
| `m2_verify.py` | M2 acceptance test (also shows the pose-normalised residual **failing** to fix N2: 2.05× → 1.99×) |
| `n11_compare.py` | N11 retest on clean single-hand takes — **asymmetry did not reproduce, direction reversed** |
| `speed_threshold.py` | the speed sweep that closed N3: implausible-flip fraction rises **6% → 58%** |

### Recording-corpus utilities

| script | purpose |
|---|---|
| `patch_cycles.py` | patch operator-reported cycle counts into a session's `meta.json` (`<frag> <cycles> [hands]`) |
| `patch_note.py` | append an operator observation to a session's `meta.json` |
| `patch_meta.py` | one-off used for the deleted `palm_back` take; kept as a template |
| `inspect_labels.py` | dump recorded handedness labels + thumb geometry per known-ground-truth clip |

---

## Two metrics, and why both are mandatory

Judging an orientation filter needs **both** families, because each alone is gameable:

- **jump counts** (>30/>60, p99, max) — a filter that ignores the hand scores perfectly
- **tracking error** = `angle(fused, raw)` on frames with `observability > 0.6`, where
  the measurement is trustworthy and the filter has no excuse to disagree — a filter
  that does no filtering scores perfectly

Attempt 1 looked like a triumph on the first (>60: 589 → 0) while sitting **37°**
from the truth on the second. **Any future orientation work must report both.**
