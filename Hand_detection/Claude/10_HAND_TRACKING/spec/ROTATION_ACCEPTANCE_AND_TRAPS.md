# ROTATION — the acceptance bar, the traps, and the takes

> **live · what any rotation change must beat, and how not to be fooled measuring it**
> **SOURCE** · `HANDOFF_T6_ORIENTATION_FROM_2D.md` §5–§8 — extracted verbatim, not edited

⭐⭐ **Reusable, and the most useful page here for `F1`.** §5 is the baseline
table (yaw 14.5° / lean 23.4° / pitch 5.5° / roll 6.7° / jitter p95 25.41°),
§6 what is already rejected, **§7 the six measurement traps — every one hit for
real**, §8 which take to use for which axis and which to distrust.
⚠ Cross-take absolute axis numbers are not comparable: the camera moved between
recordings. Same-take A/B is sound.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/HANDOFF_T6_ORIENTATION_FROM_2D.md lines 1247-1373
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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
| `2026-08-04_054702_pitch_sweep_slow` | ⚠⚠ **A SECOND PITCH TAKE `t5i` ALSO PRINTS — DO NOT USE IT AS THE PITCH BAR, AND DO NOT DISMISS IT EITHER (classified 2026-08-23)** — see below |

⚠⚠ **THE SECOND PITCH TAKE, CLASSIFIED — because "just use the validated one" was
about to be done for the wrong reason.** `t5i` prints
`2026-08-04_054702_pitch_sweep_slow` at **30.0° mean / 55.3° median / gain 0.64**,
against the validated 2026-08-02 take's 5.5° / 20.2° / 0.74. Since A10 requires
"must not regress pitch", *which take is the bar* had to be settled first.

* ⛔ **IT IS NOT CONTAMINATED, so the easy explanation is wrong.** By trap #5's own
  rule (for a PITCH sweep, **WIDTH** collapse is the contamination channel and
  LENGTH is the sweep), it measures **width collapse 0.892** — *cleaner than the
  validated take's 0.808* — and its knuckle-row spread is **18.4°**, so posture
  holds and the reference frame's expected axis stays valid. **Yaw did not leak
  in.**
* ⛔ **NOR IS IT THE NOISE FLOOR OR THE `acos` FOLD.** Stratified by rotation
  magnitude (trap #4), it is elevated in **every** band — and worst of all in the
  *best-conditioned* one: at **110–140°** it reads **64.9°** where the validated
  pitch take reads **10.9°** and the clean yaw take **11.0°**.
* ⭐ **THE ONE CONCRETE ANOMALY**: its chirality signal flips **41 times**, where
  the operator's own `meta.json` reports **12 full cycles** and explicitly warns to
  expect only *"slightly more than 24"* sign changes. The validated take flips 10.
  ~17 flips are unaccounted for, and the `acos` unwrap depends on that signal — so
  its **gain (0.64) and any band-stratified figure are not trustworthy**. ⚠ The
  MEDIAN AXIS DEVIATION does **not** depend on chirality, so *that* number is real.
* ⛔⛔ **A T1 / issue-5156 "back-of-hand collapse" explanation was TESTED AND IS NOT
  SUPPORTED — retracted rather than quietly dropped.** Splitting the deviation by
  palm facing makes back-facing frames **better**, not worse, on both control takes
  (16.8° vs 23.5°, and 11.8° vs 24.5°). ⚠ The split also returns 75%/81% "back" on
  palm→back→palm sweeps, which is not credible — it keys off the reference frame's
  own sign — **so the split is not measuring palm facing and is discarded, not
  interpreted.** The cause of this take's 3× axis error is **UNEXPLAINED**.

⭐ **WHAT TO DO WITH IT, AND WHY NOT SIMPLY DROP IT.** Use **2026-08-02** as the
pitch bar (5.5° / 20.2° / 0.74), as §5 already says — but **run T6's A/B on BOTH
pitch takes.** Planar PnP never consumes world z, so the 08-04 take is a free
discriminator: if its error collapses too, that is a bonus finding; if it does
**not**, then that defect is not depth and it belongs to **T1/T2's landmark-layer
row** (§16.17: *a jump both estimators reproduce is already in the landmarks*).
⚠ **Do not score T6 against it**, and do not let "the harness prints a bad number"
become a silent exclusion — this project has four instances in one session of a
harness being wrong about a take, in both directions.

⚠ Wake the capture drive first: `.venv/Scripts/python.exe wake_e_drive.py`.

⭐ **A live operator aid now exists and is worth reusing for any rotation take**:
the debug HUD shows `Rsq` / `Lsq` — `palm_geometry.edge_on_measure`, which is
**INVARIANT under pure roll** and drops only when yaw/pitch leak in. The owner
discarded a take before it existed because holding perpendicularity by feel is too
hard; with it they held 0.65–0.71 across a whole take.

---

<!-- VERBATIM-END -->
