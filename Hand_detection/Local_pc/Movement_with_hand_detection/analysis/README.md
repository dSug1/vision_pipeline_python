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

## The claims and the scripts that produced them

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
| `chi2_probe.py` | salvage probe: χ² / physical gate → **3.7× and 24× worse**; also the source of the M7 motion-model warning |

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
