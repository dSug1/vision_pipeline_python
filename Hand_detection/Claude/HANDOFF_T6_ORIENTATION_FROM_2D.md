# HANDOFF — T6: orientation from 2D, not from predicted depth

> **Owner, 2026-08-23:** *"I want to implement the fix before anything else is
> built."* — and, on the defect itself: *"this is a show-stopper for me as I can't
> tolerate a cube which rotates differently than what it should to reflect the
> physical world."*

⭐ **This file is a COMPLETE brief. A new conversation should be able to read this
one file plus the four sections it names and start implementing.** It is a
handoff, not a source of record: the record is `GESTURE_PIPELINE_SPEC.md`
§14.3.4.7 → §14.3.4.11 and the queue's **T6** row.

---

## 1. The defect, in the owner's terms

When the hand turns like a page (yaw about the vertical), the object **does not
turn purely about the vertical — it LEANS as it turns**:

| hand turned | object tipped out of upright |
|---|---|
| 20° | 6.8° |
| 40° | 12.3° |
| 60° | 21.9° |
| **60–90°** | **26.8°** (p90 32.2°) |

⚠⚠ **ALWAYS STATE IT THIS WAY, NEVER AS "13° of axis deviation".** They are the
same fact. The degrees-of-axis framing is why an earlier pass recommended
*accepting* it — the number sounds minor and the visible effect is not.
⭐ The rotation **amount** is fine (gain 1.13). It is the **uprightness** that fails.

---

## 2. The cause is PROVEN, not suspected — two independent routes

| axis | mean-axis error | gain | uses MediaPipe's world z? |
|---|---|---|---|
| **ROLL** | **6.7°** | **1.02** | ⭐ **NO** — pure image plane |
| YAW | 14.5° | 1.13 (over-turns) | yes |
| PITCH | 5.5° | 0.74 (under-turns) | yes |

1. **The axis that never touches depth is the accurate one**, and the two that do
   are wrong in **opposite** directions (§14.3.4.10).
2. **Scaling world z by `k` slides the yaw tilt smoothly 14.5° → 0.6°** (§14.3.4.9).

⭐ **Everything code-side is therefore EXONERATED**: the Horn fit (exact to 0.000°
on synthetic input), the quaternion maths, the frame conventions, the mirror, the
renderer. Roll exercises all of them and comes out right. **MediaPipe's 2D
landmarks are good; its predicted depth breaks the rotation.**

---

## 3. The fix

Today `palm_rotation.Horn` fits **3D↔3D**: the palm constellation against
MediaPipe's `world_landmarks`, depth included.

⭐ **Replace it with a 2D↔3D fit**: solve the pose that best **projects** a
canonical 3D palm onto the observed **pixel** landmarks. Predicted depth is then
never consumed at all.

This is what the current literature prescribes — *Monocular 3D Hand Pose
Estimation with Implicit Camera Alignment* (arXiv **2506.11133**) does exactly
this with a PnP formulation on MediaPipe 2D keypoints; *EPro-PnP* (arXiv
**2303.12787**) is the general end-to-end form. Depth ambiguity is the stated
motivation in both.

### 3.1 ⭐⭐ THE INTEGRATION POINT IS ALREADY THERE — this is not a re-plumbing

`palm_rotation.Horn` already has the right signature:

```python
def freeze(self, px, world)          # px is passed and currently IGNORED
def delta(self, state, px, world)    # same
```

Both call sites already pass pixels:

* `Resources/HandsTriggeredActions.py` — `_hand_rotation = palm_rotation.Horn(palm_rotation.PALM_LANDMARKS, "ref")`
* `LiveSnapDebug.py` — `PRODUCTION_ROTATION = _PRot.Horn(_PRot.PALM_LANDMARKS, "ref")`

⭐ **So T6 is a SIBLING CLASS behind the same interface** (e.g.
`palm_rotation.PlanarPnP`), swapped at those two lines. `palm_rotation.estimators()`
already exists as the A/B registry — add it there and every harness picks it up.

### 3.2 The model: five points, and we already own it

The fit needs only the **rigid palm**: `PALM_LANDMARKS = (0, 5, 9, 13, 17)` —
wrist + four MCPs.

⛔ **NO MANO. NO HaMeR. NO WiLoR.** They are licence-blocked (**N13**, binding —
the game will be commercialised). The papers use MANO; **we do not need it.** The
canonical palm's dimensions are **already in the codebase**:
`palm_depth.NOMINAL_SPAN_M` (added for 4.2) gives 5↔17, 0↔9, 0↔5, 0↔17 in metres.
Build the 3D model from those, in the palm plane.

### 3.3 ⭐ The planar ambiguity is ALREADY SOLVED HERE

A near-planar target has a two-fold pose ambiguity — a mirror flip about the line
of sight. This is expected, not a surprise, and both halves are handled:

* **IPPE** (Collins & Bartoli, IJCV 2014; `cv::SOLVEPNP_IPPE`) is built for planar
  targets and **returns BOTH solutions with their reprojection errors**.
* ⭐ **U7's geometric chirality is the disambiguator** —
  `palm_geometry.signed_palm_volume` / `geometric_chirality` is exactly a
  palm-front/palm-back decision, it is already live, and it was measured at
  **89.7%** even at track age 0 (vs the label's 76.8%).
* Temporal continuity is the tie-break of last resort.

⚠ This is also the "bas-relief / mirror hypothesis" parked as research under
**S11(c)** — it arrives here as a *solved* sub-problem, not a new one.

### 3.4 The camera model already exists

`palm_geometry.focal_px(frame_size)` and its documented `CAMERA_HFOV_DEG = 60.0`
assumption shipped with 4.2.

---

## 4. ⚠⚠ THE COSTS — read before starting

* ⛔ **THE PORT CONTRACT IS BINDING.** `palm_rotation`, `palm_geometry`,
  `palm_depth` etc. are **stdlib-only and numpy-free BY CONTRACT** so they can be
  transliterated to JS/Swift/Kotlin (**U3**). **`cv2.solvePnP` would break that.**
  IPPE's core is compact — a homography (DLT) plus a local analytic solve — and is
  implementable in stdlib. **Budget it, or the port debt is real.**
  ⛔ Do not quietly import cv2 into the client estimator layer.
  ⭐ Golden vectors BEFORE the port exists (**U3 precedent**, rule 6): write
  `analysis/verify_planar_pnp.py` with hand-checkable cases as you build.
* ⚠ **PnP NEEDS INTRINSICS, AND OURS ARE ASSUMED (60° FOV, never calibrated).**
  Focal-length error mostly corrupts the **out-of-plane** component — i.e.
  precisely yaw and pitch, the thing being fixed. ⭐ **This is the first hard
  technical reason for queue U12** (the start-of-game calibration step), which
  until now was only about grab reach. Measure the sensitivity: sweep the assumed
  FOV and see how much the axis error moves.
* ⚠ **THIS IS NOT A RERUN OF 2.3.** Those five null attempts re-weighted the
  **fusion** of a bad signal. T6 replaces the **input**. Say so in any write-up so
  the history is not misread as a sixth attempt at the same thing.
* ⚠ **A10 APPLIES IN FULL.** It must beat Horn on **all three axes** AND not
  regress **jitter in real handling**. Jitter is the trap that killed the 9-point
  constellation (see §6).

---

## 5. Acceptance — the rig is COMPLETE, and these are the numbers to beat

⭐ For the first time all three axes are measurable on recorded takes, one
variable, no camera needed. **Run these before you change anything, to reproduce
the baseline, then after.**

```
.venv/Scripts/python.exe analysis/t5i_zscale_sweep.py
.venv/Scripts/python.exe analysis/t5j_roll_axis.py roll_card_axis_check_b 4
.venv/Scripts/python.exe analysis/t5h_constellation_ab.py 2026-08-22_134553_yaw_sweep 2026-08-22_154426_production_4_1
```

| metric | take | baseline (shipped Horn) | target |
|---|---|---|---|
| YAW axis, mean | `2026-08-22_134553_yaw_sweep_constant_depth` | **14.5°** | ↓ |
| YAW gain | same | 1.13 | → 1.00 |
| **visible LEAN @60–90°** | same | **23.4°** | ⭐ **the number that matters** |
| PITCH axis, mean | `2026-08-02_191816_pitch_sweep_slow` | **5.5°** | must NOT regress |
| PITCH gain | same | 0.74 | → 1.00 |
| ROLL axis, mean | `roll_card_axis_check_b` | 6.7° | must NOT regress |
| ROLL gain | same | **1.02** | must NOT regress |
| **JITTER p95** | `2026-08-22_154426_production_4_1` | **25.41°** | must NOT regress |

⚠ **A live take closes it, not the harnesses.** §13.6.1 shipped inverted while
passing an "end-to-end confirmed" claim. Both tools, back to back.

---

## 6. ⛔ ALREADY TRIED AND REJECTED — do not re-propose

| what | verdict |
|---|---|
| **9-point palm+tips constellation** | ⛔ **A10 REJECT 2026-08-23** — +1.4° axis for **+4.9° p95 jitter**. Its "wins in every take" reputation came from the axis-CONTAMINATED 2026-08-04 take |
| **Down-weighting world z (`k`)** | ⛔ **REJECTED 2026-08-23** — the `k` that fixes yaw **doubles pitch**. Yaw and pitch need opposite things from the same coordinate, which closes the whole "weight z less" family |
| **Anisotropic covariance / UKF (2.3)** | ⛔ 5 attempts, all null, audited and confirmed genuine |
| **"Fix the Horn fit"** | ⛔ Horn is EXACT — 0.000° on synthetic input. Do not touch it |
| **The mirror, the frame convention, hand anatomy, constellation degeneracy** | ⛔ all eliminated by control (§14.3.4/§14.3.4.1) |

---

## 7. ⚠⚠ MEASUREMENT TRAPS — every one of these was hit for real

1. ⛔ **The `acos` FOLD.** Any foreshortening-based angle folds past edge-on (140°
   reads as 40°). It has produced bogus gains of **3.57**, **2.41** and **21.5** in
   three separate sessions. **Unwrap with DR-2's palm-facing sign**, always.
2. ⛔ **The reference frame must be the MOST FACE-ON, never the first.** Using the
   first frame of a window moved a measured axis by **12°**.
3. ⛔ **Two harnesses aggregating differently under the same name.**
   `t5_rotation_axis_fidelity.py` averages the axes FIRST and reports the MEAN
   axis's deviation (bias); `t5i` reports the MEDIAN PER-FRAME deviation (bias +
   scatter). Reading one against the other reported pitch as "45–55°, broken" when
   the mean axis was 5.5°. ⭐ **Print the aggregation, not just the value.**
4. ⛔ **The axis noise floor.** Below ~30° of rotation the axis is barely
   determined — a *clean pitch* take reads **44–63°** off its own axis there.
   **Never quote an axis deviation without the rotation magnitude.**
5. ⛔ **Width collapse measures SWEEP SIZE, not cleanliness.** It is ~cos(sweep) by
   construction. **LENGTH** collapse measures contamination and is
   sweep-independent. Read them separately.
6. ⛔ **A physical reference card perturbs the hand.** Owner: *"I had to tilt the
   hand and arm to keep the card straight up."* Card takes read the tilt **17–19°**
   vs the card-free **12.6–13.0°**. ⭐ Use the card for sweep CLEANLINESS, never
   for tilt magnitude.

---

## 8. The takes to use

| take | what it is |
|---|---|
| `2026-08-22_134553_yaw_sweep_constant_depth` | ⭐ the **card-free clean yaw** take — the reference for yaw. 77°+ sweep, contamination 0.751 |
| `2026-08-02_191816_pitch_sweep_slow` | the **validated pitch** take (mean-axis 5.5° reproduces the documented 5.0°) |
| `2026-08-23_211528_roll_card_axis_check_b` | ⭐ the **first roll take ever recorded**. Drop the first 4 s (operator) |
| `2026-08-22_154426_production_4_1` | real handling, for **jitter** |
| `2026-08-23_203307_yaw_card_axis_check_b` | the card yaw take — good sweep, but ⚠ **do not use for tilt magnitude** |
| `2026-08-23_211203_roll_card_axis_check` | ⛔ **DISCARDED** by the operator, marked in its `meta.json` |

⚠ Wake the capture drive first: `.venv/Scripts/python.exe wake_e_drive.py`.

⭐ **A live operator aid now exists and is worth reusing for any rotation take**:
the debug HUD shows `Rsq` / `Lsq` — `palm_geometry.edge_on_measure`, which is
**INVARIANT under pure roll** and drops only when yaw/pitch leak in. The owner
discarded a take before it existed because holding perpendicularity by feel is too
hard; with it they held 0.65–0.71 across a whole take.

---

## 9. Suggested order of work

1. Reproduce the baseline table in §5. **If it does not reproduce, stop** — the
   instrument is the suspect, and that has been true five times this session.
2. Build the canonical 3D palm from `palm_depth.NOMINAL_SPAN_M`. Write golden
   vectors for it first.
3. Implement planar PnP (IPPE-style) in **stdlib**, returning **both** pose
   candidates plus reprojection errors.
4. Disambiguate with `palm_geometry` chirality; fall back to temporal continuity.
5. Register as `palm_rotation.PlanarPnP`, add to `estimators()`.
6. A/B against Horn with `t5i` / `t5j` / `t5h` on the takes in §8 — all three
   axes plus jitter.
7. Sweep the assumed FOV to measure intrinsics sensitivity; feed the result into
   the **U12** row.
8. Swap the two call sites only if §5's targets are met. Then a live take in
   **both** tools.
