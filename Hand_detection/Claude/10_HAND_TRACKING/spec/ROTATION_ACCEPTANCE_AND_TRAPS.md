# ROTATION — the acceptance bar, the traps, and the takes

> **live · what any rotation change must beat, and how not to be fooled measuring it**
> **SOURCE** · `HANDOFF_T6_ORIENTATION_FROM_2D.md` §5–§8 — extracted verbatim, not edited

⭐⭐ **Reusable, and the most useful page here for `F1`.** §5 is the baseline
table (yaw 14.5° / lean 23.4° / pitch 5.5° / roll 6.7° / jitter p95 25.41°),
§6 what is already rejected, **§7 the six measurement traps — every one hit for
real**, §8 which take to use for which axis and which to distrust.
⚠ Cross-take absolute axis numbers are not comparable: the camera moved between
recordings. Same-take A/B is sound.

⛔⛔ **AMENDMENT 2026-08-26 — `edge_on_measure` IS BLIND TO PITCH.** §8's closing
paragraph recommends the `Rsq`/`Lsq` HUD readout (`palm_geometry.edge_on_measure`)
as *"a live operator aid worth reusing for any rotation take"*, saying it *"drops
only when yaw/pitch leak in"*. ⚠ **The pitch half of that is wrong**, and the
sentence is inside the VERBATIM block below, so it is corrected here instead of
edited there.

Measured on the six `T6` ratio-table takes, median at the **90° hold**:

| axis | `edge_on_measure` @90° |
|---|---|
| yaw (takes 1, 3, 5) | **0.13 – 0.28** |
| pitch (takes 2, 4, 6) | **0.94 – 1.00** — *higher* than at 0° |

⭐ **The metric is not broken.** It measures knuckle-row squareness, which is
exactly the condition under which the palm/back **sign** degenerates — and pitch
does not foreshorten the knuckle row, so the sign is never in danger and `DR-2`
correctly stays silent through a pitch sweep.

⚠ **The consequence for an operator is real**: `Rsq`/`Lsq` **cannot judge a PITCH
take**. Watching it while holding one means watching an instrument that cannot see
the axis being rotated about. ✅ Use it for **yaw and roll**. For pitch there is no
equivalent aid yet, which is worth remembering when reading §8's warning that the
second pitch take's 3× axis error is *unexplained* — every pitch take in this
corpus was held without a working squareness readout.

---

## ⭐⭐⭐ AMENDMENT 2026-08-29 — THE POST-`V2` ACCURACY TABLE, AND THE THREE FLOORS

> **Owner:** *"I want the accuracies on yaw, roll and pitch after we have shipped
> v2. I want to find the ranges for each where the rotation accuracy is the best."*
> — and then *"is there a min hand orientation in yaw and pitch for them to be
> reliable?"*

⛔ §5's table below is the **pre-`V2` baseline** and stays that way — it is the bar
a change must beat. This amendment is what the pipeline does **after** `V2`.
Harness: **`analysis/rotation_accuracy_bands.py`**, which reproduces §5's numbers
first (yaw 14.5° / 1.13, pitch 5.5° / 0.74) before reporting anything new.

### ⚠⚠ THERE ARE **THREE DIFFERENT FLOORS** AND THEY GIVE DIFFERENT ANSWERS

Conflating them is why an earlier answer said *"yaw is best 20–60°"* and a later one
said *"best under 40°"*. Both were reading a different floor.

1. **RESOLVABILITY** — is the pose distinguishable from the pipeline's own wobble?
2. **SCALE** — does it turn the *right amount*?
3. **THE PRODUCT'S OWN GATE** — `RELEASE 60 deg/s` + `FREEZE 1`. A **rate** gate, not
   an angle gate: below 60°/s of hand speed the object freezes dead still. ⭐ This is
   the floor the player actually feels, and it is why none of the wobble below
   reaches the screen during a hold.

⛔ **The “~30° axis noise floor” in §7 trap 4 is NONE of these.** It is about the AXIS
DIRECTION being undefined near identity — a caveat on a diagnostic column, not a
statement that the product cannot track a small turn. It has been quoted as if it
were, including by me.

### 1. RESOLVABILITY — signal against the wobble **during holds**

⚠ Measured against the p95 jump on frames where the hand is nearly still, **not**
the take-wide p95: on the yaw take the take-wide figure is 7.17° and the holds-only
figure is **2.02°**, and the difference is the sweep, i.e. motion the operator asked
for. Using the wrong one overstates every floor.

| axis | wobble at rest (p95) | resolves from |
|---|---|---|
| **ROLL** | **3.22°** | **~3–5°** |
| **YAW** | **4.04°** | **~8–10°** |
| **PITCH** | **58.6°** (2nd take 23.2°) | **~50–60°** |

⛔⛔ **THESE THREE DOUBLED ON 2026-08-29 and the first version of this table was
half.** `lean_trim_ab.geo_deg` returned the geodesic on the quaternion sphere S³,
which double-covers SO(3) — so it reported **half the rotation angle**, for the whole
life of that file. ⭐⭐ **Every `V2` verdict is unaffected**, because that gate is a
RATIO and a constant factor cancels exactly (1.072x, 1.166x, 0.892x all stand).
⭐ Caught by `analysis/verify_delta_orbit.py`, which asserts a hand-computed 20°
instead of only asserting two things are close. ⚠ `analysis/` only — no shipped
module imports it. ⭐⭐⭐ **THE RULE: A METRIC USED ONLY IN RATIOS IS NEVER
SCALE-CHECKED BY ITS OWN CONSUMERS.**

⛔⛔ **PITCH IS THE FINDING: its orientation wobbles ±59° at p95 WHILE THE HAND IS
STILL** — 15x yaw's and 18x roll's. ⚠⚠ **AND THIS FIGURE IS POOLED ACROSS POSES,
WHICH LATER TURNED OUT TO BE THE WRONG CUT** — it is almost entirely the 120–180°
bin, past edge-on. Per pose, on a GRIPPING hand, pitch is 1.1–4.8°. See
`analysis/delta_orbit_window.py` and `SPEC_DELTA_ORBIT.md` §14. Every pitch band under 60° sits at snr ≤ 0.7,
so a 25° pitch hold is *smaller than the pipeline's own frame-to-frame noise*.
⚠ Confirmed on both pitch takes (58.6° and 23.2°): they agree on the direction and
disagree on the size, so *"far worse"* is solid and the number is not.

### 2. SCALE — the gain, about each axis's OWN axis

⚠ Reported as rotation **about the take's expected axis**, never total-angle: the
total conflates the wanted turn with the spurious lean, so `V2` removing lean reads
there as a lower gain, which is error being removed rather than signal.

| true turn | YAW fitted | YAW gain | ROLL gain | PITCH gain |
|---|---|---|---|---|
| 10–20° | 8.1° | **~0.5** | 1.05 | 0.12 |
| 20–30° | 12.8° | ~0.5 | 1.05 | 0.21 |
| 30–40° | 21.2° | ~0.6 | 1.06 | 0.16 |
| 40–50° | 33.6° | ~0.75 | 1.04 | 0.18 |
| 50–60° | 47.4° | ~0.86 | 1.03 | 0.43 |
| 60–75° | 76.2° | **1.13** | 1.01 | **0.82** |
| 90–120° | 125.6° | 1.20 | 0.99 | 0.77 |

⭐⭐ **YAW'S GAIN IS NOT THE CONSTANT 1.13 THIS FILE RECORDS — IT RAMPS**, ~0.5 at
15° to ~1.2 at 105°, crossing 1.0 near 60°. §5's single number is the LARGE-TURN
average (it is measured over 40–140°). So a 15° hand turn moves the object ~8°:
perfectly resolvable, and visibly short.

⭐ **Roll shows no ramp at all** — gain ~1.00 from 5° up. Roll is the axis that never
touches MediaPipe's world `z`, so this is the depth defect appearing as a SCALE
error rather than as a lean. It is also what says the ramp is mostly real rather
than an artifact of the foreshortening truth (which is ill-conditioned near
face-on and would bias the low bands).

### 3. THE POST-`V2` LEAN, on the yaw take

| hand turned | lean, trim OFF | lean, trim ON | p90 ON |
|---|---|---|---|
| 10–20° | 5.6° | **1.9°** | 3.1° |
| 20–30° | 8.4° | **2.8°** | 4.4° |
| 30–40° | 8.6° | **2.9°** | 3.8° |
| 40–50° | 14.6° | **5.0°** | 6.4° |
| 50–60° | 22.4° | **7.6°** | 8.0° |
| 60–75° | 27.3° | **9.3°** | 10.9° |
| 75–90° | 23.4° | **8.0°** | 10.5° |
| 90–120° | 28.5° | **9.7°** | 11.8° |

⛔⛔ **`B4`: THIS COLUMN IS SELF-MEASURING AND MUST NOT BE READ AS A DISCOVERY.**
The metric is the swing; `V2` multiplies the swing by 0.34. *"27.3 → 9.3"* is that
multiplication, not evidence the object looks upright. ⭐ What IS independent: the
authority is **1.00 on 100% of frames** here (so the factor really does apply across
the whole range), and the per-frame jump **improves** (3.39°→2.98° median,
14.34°→13.52° p95) rather than being bought with tail steadiness — which is how the
three predecessors died.

### ⭐ THE ANSWER, PER AXIS

| | best range | why it ends there |
|---|---|---|
| **ROLL** | **anywhere, from ~5°** | no floor worth naming; gain ~1.00 throughout, steadiest by 2–3x. **The precision axis** |
| **YAW** | **10–40°** for faithful DIRECTION (lean 1.9–2.9°) · **60–90°** for faithful AMOUNT | ⚠ **no band gives both** — that gap is the world-`z` defect showing up as scale |
| **PITCH** | **nothing reliable below ~50–60°**, and snr is only 2–3 above it | design around it, not with it |

⭐ For the stated use case — assembly-style alignment of small objects — the usable
envelope is **roll at any angle, yaw and pitch under ~40°**, which is where fine
alignment lives anyway.

⚠ **Cross-take absolute numbers remain non-comparable** (§7 trap 5, the camera moved
between recordings). Compare bins WITHIN a take; compare axes by shape and by gain.
⚠ The roll take is the **card** take and the only roll recording that exists — §7
trap 6 says the card perturbs the hand, so read its error magnitudes as an upper
bound. Its **gain** is not affected the same way.

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
