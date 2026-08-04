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
