# PROTOCOL — the ON-AXIS 2D-ratio calibration takes

> **STATUS** · ready to run, **not yet recorded** · **OWNS** · how the six
> reference takes are made and what is done with them
> **READ IF** · you are recording the ratio-table takes, or analysing them
> **LAST VERIFIED** · 2026-08-25
> **OWNER'S SEQUENCING** · *"I will anyway do that after I build `F1`."*
> **BACKGROUND** · [`../../00_CORE/queue_notes/T6.md`](../../00_CORE/queue_notes/T6.md)
> (the method, what is new about it, and the retraction of a first wrong reading)

⭐ **This file is self-contained enough to open a new conversation on.** Read it,
plus `T6`'s dossier, and you can record and analyse without re-deriving anything.

---

## 1. What is being tested

**Hypothesis (owner).** MediaPipe's palm **2D** landmarks are trustworthy; its
world **z** is not. So build a table `2D distance ratios → true palm angle` from
takes where the true angle is **declared**, then use it per frame to recover the
true orientation and correct Horn's biased one.

**Decoupled by construction**: under pure **yaw** only the **x**-ratios change;
under pure **pitch** only the **y**-ratios. Two independent 1-D tables, not one
pooled magnitude.

### The prize, and it is large

§2.0.9 measured, on a clean yaw take:

| true yaw | bias | within-bin scatter |
|---|---:|---:|
| 40–60° | 27.0° | 3.5° |
| **60–80°** | **22.6°** | **5.0°** |
| 80–100° | 17.0° | 2.7° |
| 120–140° | 11.2° | 1.9° |

Between-bin spread **15.8°** against within-bin **3.1°** — ratio **5.17**, no
hysteresis. **The bias is large and repeatable at a fixed pose**, which is exactly
the premise a table needs, and it is already measured true. Removing it would be
four times `T6d`'s invisible 4.83°, at the poses where the show-stopper lives.

### ⛔ Read before proposing changes to the method

* **§2.0.9 refuted transfer** (*worst disagreement 13.4°*) — **but it binned by
  the FITTED pose, which comes from Horn, which is corrupted by the very error
  being modelled.** A contaminated index. This protocol indexes by depth-free 2D
  ratios, so that verdict does **not** carry.
* **§2.0.12** had a clean index but **pooled yaw and pitch** into one magnitude —
  collapsing the two axes this project proved need opposite corrections.
* **Per-user palm shape is not the missing variable**: forcing a session's own
  shape moved yaw only **29.3° → 27.5°**.
* Everything already rejected: [`../REJECTED.md`](../REJECTED.md).

---

## 2. ⛔ Why the takes must be ON-AXIS — first-order, not a nicety

The ratios are set by the angle to the **viewing ray**, not the optical axis. A
hand `r` px from the principal point is seen along a ray tilted by
`alpha = atan(r / focal_px)`. At 640×480 and the assumed 60° HFOV,
`focal_px = 554.26`:

| offset | alpha | fraction of a 25° table step |
|---:|---:|---:|
| **25 px** | **2.6°** | 10% |
| 50 px | 5.2° | 21% |
| 100 px | 10.2° | 41% |
| 200 px | 19.8° | 79% |
| 250 px | 24.3° | 97% |

⚠ **A palm is ~94 px wide at 0.5 m — one palm width off centre is already ~10°.**
A table built off-axis bakes that in **unrecoverably**, because alpha is not
stored. Hence the reticle, the tolerance gate, and the per-frame `alpha_deg`.

⭐ **The same relation is the runtime compensation** — simple *because* the axes
are decoupled:

```
yaw_true   ≈ yaw_from_table   − atan(x_offset_px / focal_px)
pitch_true ≈ pitch_from_table − atan(y_offset_px / focal_px)
```

⚠ **Verify it, do not assume it.** Every frame stores its own offset and alpha
precisely so this can be checked against data.

---

## 3. The six takes

**Three yaw + three pitch, ALTERNATING, one depth per PAIR** (owner):

| # | command | depth |
|---|---|---|
| 1 | `--axis yaw --hand right --tag dA --declared-depth-m 0.35` | A — near |
| 2 | `--axis pitch --hand right --tag dA --declared-depth-m 0.35` | **A — same as 1** |
| 3 | `--axis yaw --hand right --tag dB --declared-depth-m 0.50` | B — mid |
| 4 | `--axis pitch --hand right --tag dB --declared-depth-m 0.50` | **B — same as 3** |
| 5 | `--axis yaw --hand right --tag dC --declared-depth-m 0.70` | C — far |
| 6 | `--axis pitch --hand right --tag dC --declared-depth-m 0.70` | **C — same as 5** |

⭐ **Why pair the depths**: ratios are invariant under *scaling* but **not** under
*perspective* — a nearer palm has more depth spread across itself, so its
foreshortening ratios differ. Pairing yaw and pitch at one depth makes
depth-dependence separable from axis-dependence. ⚠ Suggested spread: roughly
**0.35 m / 0.50 m / 0.70 m** — the corpus working range is p5 0.372 to p95 0.668,
median **0.497**. The tool prints a live `depth ~x.xx m` and stores
`median_depth_est_m` per position and per take, so the three depths can be
*confirmed* rather than remembered.

### ⭐⭐ MEASURE THE REAL DISTANCE AND DECLARE IT

Owner offered, 2026-08-25: *"I can measure and tell you the distance from my palm
to the camera for each recording."* **Do it** — `--declared-depth-m`.

It is **optional for the ratio table** (ratios are scale-free), so it does not
gate this work. But it is worth far more than it costs:

* ⭐⭐ **It would be the ONLY declared depth ground truth in the entire corpus.**
  Every depth number the project has — including the 0.497 m working median —
  comes from the estimator, i.e. from an assumed 60° HFOV and anthropometric
  medians. Nothing has ever been checked against a tape measure.
* ⭐ **It measures the absolute estimator's per-user scale bias directly.** That
  bias is real and is currently *absorbed* by a deliberately generous
  `GRAB_Z_TOLERANCE_M = 0.15 m`, which costs precision for everyone in order to
  stay reachable for outliers. Collapsing it is exactly what **`U12`** exists to
  do — and three declared depths would hand `U12` its number for free.
* ⭐ It also checks `CAMERA_HFOV_DEG = 60` independently, because a wrong focal
  length shows up as a **depth-proportional** error rather than a constant one.

⚠ **Measure lens-front to palm centre, palm at 0°** (square to the camera), and
use the same reference for all six. The tool prints `declared / estimated / ratio`
when the take closes — **that ratio is the scale bias at that depth**, readable on
the spot.

### Running one take

```
.venv/Scripts/python.exe tools/wake_e_drive.py
.venv/Scripts/python.exe tools/RecordRatioCalibration.py --axis yaw --hand right --tag dA --declared-depth-m 0.35
```

* **8 holds, 0° → 180°**, prompted one at a time.
* **SPACE** starts/stops a hold · **R** redoes the current hold · **N** skips ·
  **ESC/Q** aborts.
* Keep the palm centre inside the **green** reticle. Amber ≤ 50 px is salvageable;
  red is not counted.
* A hold completes at **40 on-axis frames** (~2 s) — ⭐ **it records every frame of
  the hold, so medians and averages come later; one shot is never the datum.**
  `--hold-frames` raises it.

### ⚠ After take 1, STOP and check before recording the other five

```
python -c "import json;m=json.load(open(r'<session>/meta.json'));print(json.dumps(m,indent=1)[:1200])"
```

Look for: **8 positions**, each with `on_axis_frames` at the target and a
`median_offset_px` well inside tolerance, a sane `median_depth_est_m`, and
`aborted: false`. A protocol mistake then costs **one** take, not six.

### ⚠ Posture notes

* **Hand vertical** for both axes. 0° = palm square to the camera, 180° = back of
  the hand square.
* ⛔ **Do not use a physical reference card.** Measured: card takes read the tilt
  **17–19°** against the card-free **12.6–13.0°**, because holding the card
  perturbs the hand. Good for sweep cleanliness, never for magnitude.
* ⚠ **0° and 180° are the hard ones** — the ratios change slowest with angle there,
  so the table's resolution is worst at the ends. Near 90° is edge-on, where `DR-2`
  already freezes the sign. Expect the **middle bands to carry the signal**; 60–90°
  is where the defect lives anyway.

---

## 4. The analysis, in order

1. **Premise check — is the decoupling real?** Measure the cross-talk: does yaw
   move the y-ratios, does pitch move the x-ratios? ⚠ The decoupling is exact only
   under *orthographic* projection on-axis; perspective and the palm's measured
   **10.6 mm knuckle-row bow** both break it. If cross-talk is small the method is
   far simpler than the alternatives; if not, the tables must be 2-D.
2. **Build the table** from one take: per declared angle, the **median** ratio
   vector over that hold's on-axis frames.
3. ⛔ **THE DECIDING TEST — TRANSFER.** Build on take A, apply to take B (same
   axis, **different depth**), and report **how much of the 22.6° bias comes out**.

   | result | verdict |
   |---|---|
   | **> 15°** | transformative — proceed to the continuous refinement |
   | **5–15°** | real but needs per-session calibration — folds into `U12` |
   | **< 5°** | dead, and it cost a harness rather than a build |

4. **Depth dependence**: repeat 3 across the three depths. If a single table
   serves all three, the ratios are effectively scale-free and the method is
   simple. If not, depth becomes a table index — and depth is already available
   from `palm_depth`.
5. **Off-axis compensation**: verify `alpha = atan(offset/focal)` against frames
   the takes recorded off-axis, rather than assuming it.
6. Only then: continuous refinement, and only then any pipeline change.
7. ⭐ **Bonus, independent of everything above** — with `--declared-depth-m`
   set on all six, plot `estimated / declared` across the three depths. A
   **constant** ratio is a pure per-user scale bias (`U12` stores one
   number); a ratio that **drifts with depth** indicts `CAMERA_HFOV_DEG = 60`
   instead. Those are different fixes, and this is the first data able to
   tell them apart.

⚠ **Everything up to step 5 is `analysis/` work — no pipeline change, no risk.**

---

## 5. Acceptance — the bar is VISIBLE, not measured

⛔ **`T6d` had the best numbers of any correction attempted and was still
rejected.** The two A/B panels differed by a median **4.83°** (p90 17.4), flat
across every palm-tilt band — **below what an eye resolves on a 40–80 px cube**.

So: `A10` in full against
[`ROTATION_ACCEPTANCE_AND_TRAPS.md`](ROTATION_ACCEPTANCE_AND_TRAPS.md) — all three
axes plus **jitter in real handling** — **and** a visible improvement in a live
take, in both tools. Automated green has never been sufficient here.

⚠ And read that file's **six measurement traps** before quoting any number. Every
one was hit for real.
