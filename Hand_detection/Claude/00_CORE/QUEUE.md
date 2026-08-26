# THE BUILD QUEUE — one list, every subsystem

> **STATUS** · live · **OWNS** · what gets built next, for the whole project
> **READ IF** · you are starting any build, or wondering where an item stands
> **LAST VERIFIED** · 2026-08-25

⛔ **THIS IS THE ONLY QUEUE.** It replaces `PART_ONE.md` §3.1, which was its
address until 2026-08-25. Do not start a second list, in a subsystem folder or
anywhere else. Do not reorder it to be helpful.

⭐ **Each row's FULL history — every measurement, retraction and decision that
produced its status — is in `queue_notes/<ID>.md`, verbatim.** The `Notes`
column here is a pointer, not a summary of record. When a row's status changes,
update the one-line status here *and* append to its dossier.

**`Sub`** says which folder a row belongs to, so a session can filter to its own
subsystem: `HAND` = 10_HAND_TRACKING · `GAME` = 20_GAME_RULES ·
`3D` = 30_OBJECTS_3D · `INPUT` = 40_INPUT_SYSTEM · `PORT` = 50_PORT_WEB_MOBILE ·
`SEC` = 60_SECURITY_COMPLIANCE · `CORE` = cross-cutting.

The queue's governing rules and the reason it was merged into one list are in
[`queue_notes/_QUEUE_PREAMBLE.md`](queue_notes/_QUEUE_PREAMBLE.md) (verbatim).
The binding one, restated: **A10 — measure or revert.**

---

## ⭐⭐⭐ YOU ARE HERE (2026-08-25)

⭐⭐ **`F1`'s MECHANISM IS COMPLETE AND UNCONFIRMED. THE NEXT THING IS A LIVE
TAKE, NOT A BUILD.** Steps 0/1/2/3/4/5 and the sliders are built and committed;
the three-window rig is `f1_rig.bat` (panel 1 = shipped control, 2 = fingertip
grip, 3 = grip + rotation trim, each one step apart).

⛔ **Both `F1` switches are OFF in the game** (`USE_TIP_BARYCENTER=False`,
`TRIM_GAIN=0.0`) so production is pre-`F1` and every change lives in the rig where
it can be compared. Turning either on is a decision to make WITH the rig, not a
default to inherit.

⭐⭐ **`T6`'s ANALYSIS HAS RUN** (2026-08-26, `analysis/t6_ratio_analysis.py`) —
protocol §4.1/§4.2 and the depth arm §8.1/§8.2, over the six recorded takes. Two
results, and the second one was not what the row was opened for:

* **the ratio table must be 2-D.** Magnitude cannot separate yaw from pitch —
  orthography forbids it — though the excursion's **SIGN** splits them 3/3 on
  single-axis takes. `Rdiag` and `Rbow`, the two cues nominated to break that
  degeneracy, came back sign-inconsistent.
* ⭐⭐ **the DEPTH arm paid before the rotation arm did** — and a verification
  pass replaced the mechanism with a better one. At the **square** pose the four
  rigid palm spans imply depths **13–22% apart**; that is drift-free by
  construction (they read the same frame), `min` over them **is** the absolute
  estimator, and so its output **steps whenever rotation changes which span
  wins** — no foreshortening required. `NOMINAL_SPAN_M[(5,17)]` is the outlier
  for this operator. ⭐ The relative form is immune: a per-grab baseline absorbs
  the per-span error exactly, so this is fixable **without** a calibration step.
  ⛔ The snap gate reads the absolute one: its within-take excursion reaches
  **0.161 m against a 0.15 m tolerance** sized independently of it.
  ⚠ **Two claims were RETRACTED the same day**: the "≤7% drift bound" (its
  premise — that palm-on and back-on project the same spans — is refuted by the
  spans, three of four returning 8–30% short), and a "distance-free" ratio that
  was in fact distance-**squared**. The statistic that does cancel drift is the
  **product**, worst **1.209**.

**Next on the row: §4.3 the transfer test, §8.3 the inversion** — both still
`analysis/` work, nothing in the pipeline changed. ⛔ Read
[`queue_notes/T6.md`](queue_notes/T6.md) first; it also carries the two metric
bugs this harness caught in itself before publishing a number.

⚠ **Still owed on `F1` regardless of the take**: the `A10` acceptance bar has
never been run against it (yaw / lean / pitch / roll / **jitter p95 25.41**), and
the trim-resolution metric of §10.1 does not exist — without it `F1` can pass
every existing metric and still not deliver the fine alignment it was built for.

Last three landings: **`L1`** rotation lag fixed and shipped (τ = 20 ms);
**`IS1`–`IS3`** the input system ✅ **SHIPPED** (`handinput/`, observes-only) —
owner ran both tools 2026-08-25, clean; **`SEC1`** robustness +
security audit shipped, four items left as explicit decisions (`SEC2`–`SEC5`).

⚠ **2026-08-25 live look**: production clean; the debug tool's **white
snap-highlight**, removed as collateral by `febd3fa`, was restored and confirmed
live. ⭐ It exposed that **renderer parity is unguarded** — `parity_replay`
covers gesture logic, not drawing ([`queue_notes/U6.md`](queue_notes/U6.md)).

Still open and still the owner's show-stopper: the **yaw lean** (~27° at a
60–90° hand turn). `T6` was built and A10-rejected; the diagnosis survives, the
remedy does not — [`10_HAND_TRACKING/spec/ORIENTATION_DIAGNOSIS.md`](../10_HAND_TRACKING/spec/ORIENTATION_DIAGNOSIS.md).

⭐ The full block, and every superseded one back to 2026-08-03, is
[`10_HAND_TRACKING/history/SESSION_LOG.md`](../10_HAND_TRACKING/history/SESSION_LOG.md) — newest first.

---

## Phase 0 — instrumentation

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [0.1](queue_notes/0.1.md) | M0 recorder / replay / metrics harness | HAND | perception | partly done — frame capture + stop-reason landed 2026-08-04 | — |
| [0.2](queue_notes/0.2.md) | M0 baseline metrics on current pipeline | HAND | perception | ✅ done 2026-08-02 | — |
| [0.2b](queue_notes/0.2b.md) | Record the scripted sequences | HAND | perception | ✅ 7 takes done 2026-08-02 | — |
| [0.3](queue_notes/0.3.md) | End-to-end latency measurement | HAND | perception | queued | — |
| [0.4](queue_notes/0.4.md) | S1 predictor evaluation harness | HAND | perception | optional, parallelisable | — |
| [0.5](queue_notes/0.5.md) | ~~S8 offline oracle over the corpus~~ | HAND | perception | ⛔ dropped 2026-08-04 — two blockers, one permanent (licence) | — |

## Phase 1 — kill the singularities

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [1.1](queue_notes/1.1.md) | M5d `K` fixture test | HAND | perception | ✅ done 2026-08-03, 13 checks | 0.1 |
| [1.2](queue_notes/1.2.md) | M5a `edgeOnMeasure` | HAND | perception | ✅ done 2026-08-03 | — |
| [1.3](queue_notes/1.3.md) | M6a no Euler in the estimation path | HAND | perception | ✅ already satisfied | — |
| [1.4](queue_notes/1.4.md) | M2 bone-length calibration | HAND | perception | ⛔ **DEAD** — audited and upheld; replaced by 1.7 | — |
| [1.5](queue_notes/1.5.md) | M3a hard anatomical constraints | HAND | perception | ✅ done 2026-08-04 — 0.00% FP on the control | 1.4 |
| [1.6](queue_notes/1.6.md) | M4 precision weighting + χ² gating | HAND | perception | ✅ built 2026-08-04, A10 passes; 2 of 4 cues measured out | 1.5 |
| [1.7](queue_notes/1.7.md) | M2b impose a skeleton | HAND | perception | ⚠ built then **parked** — cannot affect orientation by construction | 1.5, 1.6 |

## Phase 2 — temporal identity

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [2.1](queue_notes/2.1.md) | M5c DR-1 chirality lock | HAND | perception | ✅ done, live-confirmed 2026-08-02 (shipped early as N5) | 1.1 |
| [2.2](queue_notes/2.2.md) | M5e DR-2 edge-on band | HAND | perception | ✅ built + live-tested 2026-08-03 | 1.2, 2.1 |
| [2.3](queue_notes/2.3.md) | M6b–e quaternion UKF, anisotropic covariance | HAND | perception | ⛔ **deprioritised** — 5 attempts all null, audit confirmed genuine | 2.1 |
| [R](queue_notes/R.md) | Re-measure M0; decide whether Phase 3 precedes features | HAND | gate | open | 2.3 |

## Pipeline defects

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [T1](queue_notes/T1.md) | Back-of-hand rotation quality | HAND | pipeline | open — belongs to the **landmark** layer, not the estimator (§16.17) | 1.5, 1.6, 1.7 |
| [T2](queue_notes/T2.md) | Pitch-plane crossing | HAND | pipeline | partly fixed — DR-2 closed the sign-flip half | 2.2, 1.5–1.7 |
| [T3](queue_notes/T3.md) | Object jump / silent handover | HAND | pipeline | ✅✅ **fixed 2026-08-22** by the narrow remap, owner-accepted live | 2.1, N5 |
| [T4](queue_notes/T4.md) | Yaw / palm-sinking in translation | HAND | pipeline | deferred | 1.4, 1.2, 4.1 |
| [T6](queue_notes/T6.md) | Orientation from 2D (planar PnP) | HAND | perception | ⛔⛔ **built and A10-rejected 2026-08-24** — yaw got worse; code in `estimators()` only. ⭐⭐ **A 2D-RATIO-TABLE correction is OPEN and NOT covered by §2.0.12** (owner 2026-08-25) — clean depth-free index, yaw/pitch kept separate, declared ground truth. §2.0.9's refutation used a *contaminated* index so it does not carry. ✅ **ALL SIX TAKES RECORDED 2026-08-26** — 1680 frames, every one on-axis, 3 depths × 2 axes, right hand declared. ⛔ **CAVEAT ZERO (owner): the distance was NOT reliable and the hand very likely moved during the takes.** ⭐ Fine for the ratio table — foreshortening ratios are **scale-free** — but it invalidates every depth-derived reading, and two claims built on one were retracted the same day. ⚠ Grid is **30°** (7 positions), not the protocol's 25.71°: the owner could not set 25.71° by feel, and the declared angle IS the ground truth. ⛔ **Before analysing, read the dossier**: the ratio the tool prints is the take MEDIAN and is contaminated by the sweep — use the 0° hold. ⛔ **TWO claims made and retracted on this data in one afternoon** — "take 6 is the anomaly", then "four of six never return, which geometry forbids". ⭐ Caveat zero answers both: a drifting hand produces a monotone climb, no mystery required. ⭐ The one finding that SURVIVES (it is scale-free): `edge_on_measure` is **blind to pitch** — 0.94–1.00 at pitch-90° vs 0.13–0.28 at yaw-90° — so `Rsq`/`Lsq` cannot judge a pitch take. ✅✅ **§4.1/§4.2/§8.1/§8.2 ANALYSED 2026-08-26** (`analysis/t6_ratio_analysis.py`): magnitude does NOT separate the axes (orthography forbids it), but the **SIGN** of `Rwl`'s 0°→90° excursion splits yaw from pitch **3/3** — so the table must be **2-D**, and `Rdiag`/`Rbow` did not deliver the second observable. ⭐⭐ **THE DEPTH ARM PAID FIRST**, and a verification pass sharpened it: at the **square** pose the four palm spans imply depths **13–22% apart** (drift-free — one frame), `min` over them IS the absolute estimator, so its output **STEPS whenever rotation changes which span wins**. `NOMINAL_SPAN_M[(5,17)]` is the outlier. ⛔ The snap gate inherits it: within-take excursion reaches **0.161 m against a 0.15 m tolerance**. ⚠ Two claims RETRACTED the same day — the drift bound (premise refuted) and a "distance-free" ratio that was distance-SQUARED; the corrected statistic is the product, ≤ **1.209**. **Next: §4.3 transfer, §8.3 inversion** | 4.2 |
| [T6d](queue_notes/T6d.md) | The anisotropic 2×2 fit | HAND | perception | ⛔⛔ built, 4 live sessions, **owner-rejected 2026-08-24** — production never ran it | T6 |
| [L1](queue_notes/L1.md) | Rotation smoothing — a **time constant** | HAND | responsiveness | ✅✅ **shipped 2026-08-24**, owner-settled live at τ = 20 ms | — |
| [F1](queue_notes/F1.md) | ⭐⭐⭐ **The cube's transform from the FINGERTIPS** | HAND | perception + gesture | ⭐⭐⭐ **SPECIFIED + STEP 0 MEASURED + STEP 3 SHIPPED 2026-08-25** (⛔ live take owed). Design = **palm-frame deformation + bounded trim**, gain 0 ⇒ bit-identical to Horn; τ = 20 ms untouched; ⛔ contact-point arm dropped on a **patent** finding. **Census (`analysis/f1_tip_census.py`)**: tip noise floor **1.5 mm** ✅ workable (held only 5–10% worse) · ⛔ rigid tip residual **75–95° inside 0.5 s** — not noise, the rigid model is wrong ⇒ clamp far below it · ⛔ plain barycentre drifts **1 cm median / 6 cm p95** ⇒ `g_pos = 1` needs a clamp · ✅ collinearity floor 0.20 costs 1.9%. ⭐⭐ **Steps 1, 2 and 4 BUILT 2026-08-26** — 1€ filter, fingertip barycentre for snap+translation, and the palm-frame ROTATION TRIM (gain 0 = shipped Horn; a rigidly rotated hand yields **0.0000°** of trim). ⭐ **`f1_rig.bat` runs all three side by side on one camera** for the live take. ⛔ **Live take owed** — and until it happens **BOTH F1 switches are OFF in the game** (`USE_TIP_BARYCENTER=False`, `TRIM_GAIN=0.0`), so production is pre-F1 and every change lives in the rig where it can be compared. ⭐ **Step 1 landed 2026-08-26**: the **1€ filter** + 30 golden vectors, inert until step 2 (⚠ the vectors caught a real divergence from the paper immediately — the speed term used the filtered, not the raw, value). **Back-of-hand snap rule REMOVED** ✅ **live-confirmed both tools 2026-08-25**; debug measured **9 of 15 snaps back-of-hand** (⚠ re-opens `N8`; the rule was refusing **8.3%** of free-hand frames; ⚠ production recorded nothing — `N4`) → [`spec/F1_FINGERTIP_TRANSFORM_SPEC.md`](../10_HAND_TRACKING/spec/F1_FINGERTIP_TRANSFORM_SPEC.md) | L1 ✅ |
| [T7](queue_notes/T7.md) | World-referenced rotation (tilted camera) | HAND | perception | designed 2026-08-24 — ⭐ ships **with U12**, not after T6; no-op until then | T6, U12 |

## Phase B — the block representation

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [B1](queue_notes/B1.md) | `hand_blocks.py` — the derived view | HAND | perception | ✅ done | — |
| [B2](queue_notes/B2.md) | Block separability | HAND | perception | ✅ done 2026-08-04 — anchor claim holds, outlier claim does not | B1 |
| [B3](queue_notes/B3.md) | Palm-transform predictor | HAND | perception | queued | B2 |
| [B4](queue_notes/B4.md) | Anchor + rotation A/B | HAND | decision | ✅ closed 2026-08-17 — `horn-palm` shipped, arm B rejected | B1 |
| [B5](queue_notes/B5.md) | Grab signal from arcs — ⭐ **one project with 4.4** | HAND | feature | queued | B1, B4 |
| [B6](queue_notes/B6.md) | Two-channel outlier test | HAND | perception | research — hypothesis, not evidence | B1, B2 |
| [B7](queue_notes/B7.md) | Confirmation gate | HAND | perception | ⛔ **park confirmed under a blind test** 2026-08-17 | B1 |
| [B8](queue_notes/B8.md) | Optimise the quadratic | HAND | perception | ⛔ done 2026-08-04 — every fit **loses to holding the last value** | B1 |

## Phase 3 — latency and grab

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [3.1](queue_notes/3.1.md) | M7 dual-pathway + forward prediction | HAND | perception | unblocked 2026-08-03 (the blocking warning was an artifact); first task done | 0.3, 2.3 |
| [3.2](queue_notes/3.2.md) | M8b RTS retrospective smoothing | HAND | perception | queued | 2.3 |
| [3.3](queue_notes/3.3.md) | M8a A/B vs §14.1 | HAND | decision | queued | 2.3, 4.1 |
| [3.4](queue_notes/3.4.md) | M8c predictive grasp onset | HAND | perception | blocked | 4.3 |

## Phase D — dropout mitigation

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [D0](queue_notes/D0.md) | Dropout census | HAND | measurement | ✅ done 2026-08-21 | — |
| [D1](queue_notes/D1.md) | `HandState` tracking fields | HAND | perception | ✅ done 2026-08-21 — no behaviour change by construction | D0 |
| [D2](queue_notes/D2.md) | Hold-and-decay bridging (150 ms coast) | HAND | perception | ✅✅ shipped 2026-08-21, accepted live | D1 |
| [D3](queue_notes/D3.md) | Resync blend on reacquisition | HAND | perception | ✅✅ shipped 2026-08-21 — the arm the owner chose | D2 |
| [D4](queue_notes/D4.md) | Grace period before release | HAND | decision | ⛔⛔ **declined** by the owner 2026-08-21 after seeing D2/D3 live — answered, not deferred | D2, D3 |

## Phase 4 — unlock the features

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [4.1](queue_notes/4.1.md) | M9 metric depth | HAND | perception | ✅ estimator built + A10 passed 2026-08-22; ⚠ its trackId ownership half is **reverted** | 1.7 |
| [4.2](queue_notes/4.2.md) | Z-axis translation + 3D snap gate + play volume | HAND | feature | ✅✅ **shipped**, owner-confirmed live in both tools 2026-08-23 | 4.1 |
| [4.3](queue_notes/4.3.md) | M10 commitment dynamics | HAND | perception | M10.7 deferred by owner 2026-08-04 — do not build | 1.6 |
| [4.4](queue_notes/4.4.md) | Hand-open release trigger — ⭐ **one project with B5** | HAND | feature | designed, not built | 4.3 |

## Phase 5 — optional menu (nothing scheduled, nothing waits on it)

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [5.1](queue_notes/5.1.md) | M3b synergy subspace | HAND | perception | optional | 1.5 |
| [5.2](queue_notes/5.2.md) | M3 IK (26-DOF) | HAND | perception | optional | 5.1 |
| [5.3](queue_notes/5.3.md) | Trajectory gesture classification | HAND | perception | optional | 5.1 |
| [5.4](queue_notes/5.4.md) | Causal SmoothNet-class temporal refinement | HAND | perception | optional | 1.5–1.7 |
| [5.5](queue_notes/5.5.md) | Multi-hypothesis / uncertainty-aware prediction | HAND | perception | optional / research | 3.1 |

## Surfaced by measurement (N)

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [N1](queue_notes/N1.md) | Re-express frame-count parameters in ms | HAND | perception | queued | — |
| [N2](queue_notes/N2.md) | Pose-normalise the bone residual | HAND | perception | queued | 1.4 |
| [N3](queue_notes/N3.md) | Speed-threshold sweep | HAND | perception | ✅ closed 2026-08-03 | — |
| [N4](queue_notes/N4.md) | External capture drive is unreliable | CORE | infra | ⭐ **sleep half FIXED 2026-08-25** — it cost a real production acceptance take (recorded nothing). The retry now lives in `Resources/capture_drive.py` and **both recorders call it**; `wake_e_drive` delegates. Verified against the live fault. ⚠ The volume's `Full Repair Needed` flag is untouched | — |
| [N5](queue_notes/N5.md) | DR-1 track-level hand identity | HAND | perception | ✅ done, live-confirmed 2026-08-02 | — |
| [N6](queue_notes/N6.md) | Shared modules are imported, never copied | CORE | infra | ✅ resolved 2026-08-02 — now a binding rule | — |
| [N7](queue_notes/N7.md) | Drive `ASSUMED_FPS` from measured timing | HAND | perception | ✅ done 2026-08-04 (DR-1); ⚠ `palm_geometry` still to do | 0.1 |
| [N8](queue_notes/N8.md) | Cube stolen by occluding the holding hand | HAND | gameplay | ⚠⚠ **RE-OPENED AND WIDENED 2026-08-25** — `F1` removed rule 3, which had been suppressing part of it incidentally (measured: the rule refused **8.3%** of hand-frames where the hand held nothing). ⛔ Do **not** answer it with a facing gate; still routed to B5 + 4.4 | B5 |
| [N9](queue_notes/N9.md) | DR-1 duplicate-repair fires in normal use | HAND | perception | observed, **not diagnosed** — deliberately not tuned | 0.2b |
| [N10](queue_notes/N10.md) | Frame rate is environment-dependent (lighting) | CORE | infra | open — confirmed camera-bound by L1's measurement | — |
| [N11](queue_notes/N11.md) | Left/right asymmetry in sign-cue reliability | HAND | perception | ⛔ **not reproduced** — direction reversed on clean takes | — |
| [N12](queue_notes/N12.md) | Held cube jumps crossing the pitch plane | HAND | pipeline | observed live 2026-08-03, not fixed | 3.3 |
| [N13](queue_notes/N13.md) | No non-commercially-licensed dependencies | SEC | governance | ⛔ **BINDING** — owner decision 2026-08-04 | — |
| [N14](queue_notes/N14.md) | The corpus contains NO image data | CORE | infra | established by exhaustive scan 2026-08-04 | — |
| [N15](queue_notes/N15.md) | One take has no `raw_landmarks.jsonl` | CORE | infra | observed, not investigated | — |
| [N16](queue_notes/N16.md) | Two takes contained an unrequested second hand | CORE | infra | ✅ metadata corrected 2026-08-04 | — |
| [N17](queue_notes/N17.md) | `RecordTranslationPivotDebug.py` synthesises timestamps | CORE | infra | found 2026-08-04, not fixed | — |
| [N18](queue_notes/N18.md) | 2026-08-04 daylight corpus additions | CORE | infra | recorded | — |

## Unscheduled / not queued

| # | Item | Sub | Kind | Status | Dep |
|---|---|---|---|---|---|
| [U1](queue_notes/U1.md) | Open-palm / closed-fist detection | HAND | feature | **parked** — owner's priority call | — |
| [U2](queue_notes/U2.md) | Real 3D-file import (OBJ/glTF) | **3D** | feature | ⛔ postponed 2026-08-04 — blocked on the **platform decision**, not on effort | — |
| [U3](queue_notes/U3.md) | Web / mobile port | **PORT** | platform | deferred — `HandState` v2 is the contract it reinstates | — |
| [U4](queue_notes/U4.md) | Dangling §7.4 reference | CORE | docs | open | — |
| [U5](queue_notes/U5.md) | Extend D2's coast through hand-crossing occlusion | HAND | feature | ⭐ parked for later re-opening — owner decision 2026-08-22 | D2, D3 |
| [U6](queue_notes/U6.md) | Two pipelines are KEPT — divergence prevented mechanically | CORE | architecture | ✅ **decided 2026-08-22** — run `parity_replay.py`; do not re-propose collapsing them | — |
| [U7](queue_notes/U7.md) | Handedness label wrong 10.8% — chirality from geometry | HAND | perception | ✅✅✅ **CLOSED 2026-08-25** — the declared known-hand take finally ran: geometry **98.0%** vs the label **93.2%** (n=1127) | — |
| [U8](queue_notes/U8.md) | No snap on a **provisional** chirality | HAND | perception | ✅✅ shipped + accepted live 2026-08-22 (200 ms, elapsed-time gated) | U7 |
| [U9](queue_notes/U9.md) | Play area — an object may never reach the edge | HAND | feature | ✅ shipped 2026-08-23; superseded by 4.2's world-space volume | — |
| [U10](queue_notes/U10.md) | Camera privacy: policy + store disclosures (minors) | **SEC** | governance | open — before any store submission. Not a build | — |
| [U11](queue_notes/U11.md) | Shipping-build hygiene; hard-disable dev capture | **SEC** | shipping | open — at package time, not now | U10 |
| [U12](queue_notes/U12.md) | Start-of-game calibration (playability, FOV, camera tilt) | HAND | playability | open — build later. ⚠ **First tape measurements exist (2026-08-26) but do NOT carry**: the owner reports the distance was unreliable and the hand moved, so a "bias at depth Y" measures the drift as much as the estimator. ✅ Only "the estimator is in the right ballpark" survives — worth knowing, never checked before. ⛔ Adopt **no** correction. ⭐ What `U12` needs is a **HELD** distance (hand braced, a single 0° hold, no sweep), not a better tape | 4.2, U3 |
| [IS1](queue_notes/IS1.md) | Input system — the package boundary | **INPUT** | platform | ✅✅ **SHIPPED 2026-08-25** — owner ran both tools, clean | — |
| [IS2](queue_notes/IS2.md) | Input system — conformance as DATA | **INPUT** | platform | ✅✅ **SHIPPED 2026-08-25** | IS1 |
| [IS3](queue_notes/IS3.md) | Input system — the action layer, wired as an OBSERVER | **INPUT** | platform | ✅✅ **SHIPPED 2026-08-25** — owner ran both tools back to back, clean | IS1 |
| [IS4](queue_notes/IS4.md) | Input system — extract the **interaction** tier | **INPUT** | platform | ⭐⭐ **PREREQUISITE OF THE PORT** (2026-08-25) — no longer optional now that both hosts ship; do it in Python **before** any port | IS3 |
| [SEC1](queue_notes/SEC1.md) | Robustness + security audit of both tools | **SEC** | infra | ✅ done 2026-08-25 — 7 fixes shipped, 51-check suite | — |
| [SEC2](queue_notes/SEC2.md) | Pin the dependency **tree** | **SEC** | infra | ⭐ half done — environment now recorded; hash-pinning is packaging work | U10, U11 |
| [SEC3](queue_notes/SEC3.md) | Face detector runs every frame, nothing consumes it | **SEC** | privacy / perf | ⛔ **open — owner's call.** `--face off` exists, default deliberately not flipped | — |
| [SEC4](queue_notes/SEC4.md) | Debug recorder buffers a whole session in RAM | **SEC** | infra | open — deliberately deferred | — |
| [SEC5](queue_notes/SEC5.md) | Both tools feed MediaPipe a fake 33 ms clock | **SEC** | perception | open — ⚠ effect **unmeasured**; needs a live two-detector A/B, the corpus cannot settle it | — |
| [SEC6](queue_notes/SEC6.md) | ⭐ Third-party attribution notices at the **ship** boundary | **SEC** | governance | ⭐ **DRAFTED AND VERIFIED 2026-08-26** — `THIRD_PARTY_NOTICES.md` + `licenses/`; the 1€ copyright line (`Copyright 2023 Inria`) was fetched from upstream, **not** guessed. ⭐ `N13` cleared *may we use it*; **nothing cleared *what must travel with a binary***. ⛔ Closes only on a **built** artifact — the export path still does not copy the notices | U11 |

---

## Rows that belong to a future subsystem

Nothing is scheduled in `20_GAME_RULES`, `30_OBJECTS_3D` or `50_PORT_WEB_MOBILE`
beyond the rows above (`U2`, `U3`). When the game proper starts, add rows here
with the right `Sub` tag — **not** a second queue in that folder.
