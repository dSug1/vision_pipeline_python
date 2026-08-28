# 10 — HAND TRACKING · perception + gesture

> **STATUS** · live · **OWNS** · everything from the webcam to the object's transform
> **READ IF** · you are building or debugging detection, identity, chirality,
> snap, translate, rotate, release, depth or the play volume
> **LAST VERIFIED** · 2026-08-26

⭐ **Load this file plus [`../00_CORE/`](../00_CORE/) and you have the subsystem.**
Everything else here is opened **by name**, when this file points at it.

---

## Where it stands

**Live and owner-confirmed**: snap acquisition + arbitration · grab-relative
translation · rotation while snapped (Horn over the palm, grab-referenced) ·
release on tracking loss · DR-1 track identity · DR-2 edge-on sign freeze ·
Phase D's 150 ms coast + 3-frame resync blend · the `horn-palm` anchor · the
mirror fix · geometric chirality (`U7`) · the narrow owner remap (`T3`) · the
provisional-chirality snap gate (`U8`) · **Z-axis translation, the 3D snap gate
and the world-space play volume** (`4.2`) · **τ = 20 ms rotation smoothing** (`L1`).

**Shipped 2026-08-25**: the input system — see
[`../40_INPUT_SYSTEM/INDEX.md`](../40_INPUT_SYSTEM/INDEX.md).

⚠ **2026-08-25, both tools run back to back.** Production clean. The debug tool
had **lost its white snap-highlight** on a held object — removed as collateral by
`febd3fa` — now **restored and owner-confirmed live**. ⭐ **Renderer parity is
unguarded**: `parity_replay` compares gesture logic, not drawing, so it was green
throughout and correctly so. See [`../00_CORE/queue_notes/U6.md`](../00_CORE/queue_notes/U6.md)
and the log's newest entry.

⛔⛔ **The open show-stopper is the YAW LEAN.** Turning the hand like a page does
not turn the object purely about the vertical — **it leans, up to ~27° at a
60–90° turn.** ⚠ Always state it that way; *"13° of axis deviation"* is the same
fact and is why an earlier pass wrongly recommended accepting it.
**The diagnosis is proven twice over and still stands; the remedy is not found.**
→ [`spec/ORIENTATION_DIAGNOSIS.md`](spec/ORIENTATION_DIAGNOSIS.md)

✅✅ **`F1` IS SHIPPED (2026-08-27).** The object is carried by the **fingertip
barycentre**, settles onto it with a motion-masked walk (it only closes the gap
while the hand is moving, and never faster than the hand), has its depth
**anchored to the hand at each grab**, and is picked up only when the barycentre
falls inside the object's **projected footprint**.
⛔⛔ **The rotation TRIM was REMOVED.** §10.1's declared-angle take measured it
**non-monotonic in the declared finger angle at every gain and clamp**, so it is
not a fine control at any setting. ⚠ That **retracts** the rig's 21.2°-vs-32.9°
lean result: it was a constant 10° offset, not the fingers steering the cube.
⭐ Step 0's `M2` had already named the cause — the rigid fit over five non-rigid
points tumbles.
✅ `A10` reproduces exactly (jitter p95 **25.41°**) and `parity_replay` is clean on
four takes. ⭐⭐ The reusable finding: **every per-hand estimator must die with its
track** — three were missing that reset.
→ [`spec/F1_FINGERTIP_TRANSFORM_SPEC.md`](spec/F1_FINGERTIP_TRANSFORM_SPEC.md) ·
[`../00_CORE/queue_notes/F1.md`](../00_CORE/queue_notes/F1.md)

⛔ **`F1` did NOT fix the yaw lean.** The apparent improvement was the trim's
constant offset, and it is gone. The show-stopper stands.

✅✅ **RENDERING WAS REBUILT AND SHIPPED (2026-08-27) — see [`../00_CORE/queue_notes/R1.md`](../00_CORE/queue_notes/R1.md).** Depth-ordered
occlusion as ONE rule for every object, per-landmark and PER-SEGMENT bone occlusion,
a SOLID near-face occluder, and ⭐ **landmarks in PRODUCTION for the first time**.
⛔⛔ The defect the owner spotted by eye — every fingertip in front of a held cube —
was OUR logic: cube **x,y** from the FINGERTIPS, cube **z** from the PALM. Fixed.
⭐⭐ **AND IT PRODUCED A YAW FINDING FOR FREE**: the palm quad's z spread is 0.0658 m
face-on and 0.0681 m at 90° — essentially CONSTANT — so Horn's z input carries almost
no yaw information at all. `T6`'s 24.9° result by an independent route.
⭐ A FREEZE damper ships for rotation AND translation (`RELEASE 60 / FREEZE 1`);
three earlier designs were live-rejected, and a directional-coherence gate was built
twice and removed twice — a good measure, a bad trigger.

⭐⭐⭐ **`T6` BECAME A REGRESSION, AND THE RATIO TABLE IS DEAD.** `Rwl` measures
compression along one fixed direction, so it carries `cos(yaw)/cos(pitch)` — one
number, two unknowns, a **lossy projection**. That is why §4.1's cross-talk was
~1.0 and §4.3's yaw transfer came out dead (mean +2.4° recovered).
⭐ What replaced it: **slant/tilt from the trimmed affine SVD, FITTED from the six
takes**. Beats Horn on both axes — **yaw 8.7° vs 11.5°, pitch 17.6° vs 30.7°** —
and is **bijective** by construction (monotone fit per branch · palm/back sign for
the branch · tilt for the axis).
⭐ **The owner's freeze-a-matrix-at-grab architecture is validated** (10.6°/17.4°).
It works because the cube's rotation is already grab-relative, so the absolute
error at grab cancels. ⛔ The composition must be **multiplicative**; additively it
is worse than Horn.
⛔ **Palm-only for orientation**: under grip the finger feature jitters 0.013–0.458
per frame against palm-5's 0.004–0.070, so the fingers keep their own channel.
⛔ **Two retractions**: the "pitch collapse" and §4.3's pitch verdict — the
established z-free truth under-reports pitch too, so the DECLARATION is the
outlier, and the takes cannot ground-truth the 30–60° band.
⛔⛔ **AND THE SCOPE IS NARROWER THAN THOSE NUMBERS SUGGEST.** Scored against
independent, depth-free truth, `σ` reads **0.94–0.96 on a hand that barely moved**
— a **17–20° static false-tilt floor** from landmark noise alone, because `arccos`
is nearly vertical as `σ → 1`. Roll invariance survives (~7–8° across 40–103° of
roll); small tilts do not. ⭐ **Large-angle correction, NOT a replacement for
Horn** — which still covers the yaw lean, worst at 60–90°.
⛔⛔ **AND IT WAS ALL LIVE-REJECTED ON 2026-08-27 — READ `REJECTED.md` BEFORE
PROPOSING ANY OF IT AGAIN.** Two builds, two verdicts: the axis correction (*"discontinuities everywhere"*) and the owner's own halves 1+2 (*"much worse than
panel 1 ... lot of jumps, lot of jitter"*). ⭐⭐ The scores were GOOD — halves 1+2 gave
the best yaw this row ever measured, **lean 27.2° → 8.6°** — and the p95 orientation
jump went **12.6° → 30.3°** while the median improved. Smoother most of the time,
occasionally much worse; **the tail decides the feel every time**, and three estimators
in a row have now died of exactly that. ⭐⭐⭐ **THE METHOD RULE: a corpus whose MOTION
does not match the product's cannot validate an estimator for the product** — all six
takes are OPEN hands and the game GRIPS. ✅ Nothing to revert; production untouched.

✅✅ **THE ESTIMATOR IS BUILT** (2026-08-27): `Resources/palm_slant.py`, stdlib-only
/numpy-free/clock-free, authority fade in from the start, golden vectors passing.
⭐⭐⭐ **AND THE CORRECTION FOLLOWED THE SAME DAY, BECAUSE `t5f`'s WORDING
REFRAMED THE DEFECT**: *"the cube turns about as far as the hand — AXIS is not"*.
The row had been aiming at the ANGLE, which was already fine, and which is the half
needing the per-user thickness table. ⭐ **The AXIS needs no table, so `U12` is off
the critical path.** `affine_svd`'s major direction IS the in-image rotation axis
(10.4° vs Horn's 22.8°). ✅ `Resources/palm_slant_axis.py` keeps Horn's ANGLE and
steers only its axis: **yaw lean 22.0° → 13.6°, pitch 14.8° → 10.0°, with no rise
in axis wander**. `gain 0` is bit-exact Horn; production untouched; parity clean.
⛔ Two harness bugs printed the OPPOSITE verdict first — a canonical frozen on
`frames[0]` of a SWEEP, and `tilt` scored against an image-frame truth when it lives
in the palm's frame. ⛔⛔ **The owner's live look HAPPENED THE SAME DAY AND REJECTED BOTH BUILDS** — see `REJECTED.md`. The rig is retired: `slant_rig.bat` is ARCHIVED to `_archive/launchers/`, though the `--slant-rig` flag is still live.
→ [`spec/SLANT_TILT_AND_Z_RECONSTRUCTION.md`](spec/SLANT_TILT_AND_Z_RECONSTRUCTION.md)
· [`../00_CORE/queue_notes/T6.md`](../00_CORE/queue_notes/T6.md)

✅✅ **`V1` — THE CAMERA MOUNT — IS SHIPPED (2026-08-28).** `CAMERA_MOUNT` defaults to
`facing_user`; landmarks now default to HIDDEN in both tools (`'l'` shows them).
⚠ The DEPTH direction and the size artifact were never separately judged.
The owner reported yaw, pitch and z-translation all reading BACKWARDS. ⭐⭐⭐ The cause
is that the shipped build is a **hybrid of two camera mountings**: the frame is
mirrored before detection, so `x` is in the USER's frame while `z` is still in the
CAMERA's — a REFLECTION, which is no physical viewpoint at all. ⭐ The diagnosis
**predicted** the symptom rather than being fitted to it: conjugating by
`D = diag(1,1,−1)` reverses yaw and pitch and leaves **roll exactly alone**, and roll
is the one axis the owner did not name. ⛔ Z-translation is a **second mechanism** —
pixel-span driven, so no landmark change could reach it; and `grab / ratio` is
CORRECT for a head-worn camera, which is what proves the hybrid.
⭐⭐ **The landmarks are NOT touched, and it is proven not to matter** (Horn obeys
`R'_opt = D R_opt D` exactly) — negating them would invert `U7`'s chirality
determinant and `R1`'s camera-referenced occlusion.
✅ Offline evidence only, as the owner asked: **2041 recorded hand-frames** — yaw
reversed **100.00%**, pitch **100.00%**, roll **0.00%**, angle changed **0.000e+00°**;
`parity_replay` clean on 4 takes; 37/37 suites under both `legacy` and `facing_user`.
⚠ One artifact cannot be coded away: the hand's **video** still grows as it moves
away (the video is the camera's) while the cube shrinks.
⛔⛔ **TWO RETRACTIONS FROM THE OWNER'S FIRST LIVE RUNS — both found by LOOKING,
after every offline check had passed.** (1) `head_worn` showed left/right inverted:
a real defect in `anatomical_name`, plus **my own error making the chirality bit
mount-dependent when it is not** — and `verify_geometric_chirality` had ALREADY
FAILED saying so and was **silenced with a guard**. ⭐⭐ **The method rule, which is
`METHOD.md`'s inverted: a harness reporting a REAL defect can be explained away —
suspecting the instrument is not the same as dismissing it.** (2) ✅✅ **THE ORIENTATION IS
SETTLED: `pitch_yaw`** — reverses PITCH and YAW, leaves ROLL alone, owner-confirmed
live. ⭐⭐⭐ **A viewpoint change is a CONJUGATION and there are EXACTLY THREE, each
reversing EXACTLY TWO axes — reversing one alone is geometrically impossible.**
⚠⚠ But three options tried ONE PER RESTART produced three MUTUALLY INCONSISTENT
reports. ⭐⭐⭐ **The method rule: when one-option-per-restart yields inconsistent
reports, the INSTRUMENT is the problem, not the observer — A/B on one pose.** An
`'m'` key now cycles the options live and settled in one session what three had
not. ⚠ Why it mattered here: **the open yaw lean makes the cube ROLL while it
YAWS**, so two of the three axes were coupled by a known bug.
→ [`../00_CORE/queue_notes/V1.md`](../00_CORE/queue_notes/V1.md)

✅✅ **`V2` IS SHIPPED (2026-08-28) — THE YAW LEAN HAS A SURVIVING CORRECTION AT LAST.**
`Resources/lean_trim.py` trims the **SWING** of a swing/twist decomposition about
the vertical, leaving the **TWIST** — the turn amount — exact. Gains **0.66/0.66** in
both tools; `gain 0` is bit-exact shipped Horn.
⭐⭐ **The owner proposed the architecture and it is TEXTBOOK**: a multiplicative
correction quaternion reset to identity at grab is the **MEKF's multiplicative error
quaternion**. ⛔ The literature changed the FORMULA — swing/twist, not axis scaling.
⭐ **Measured, not assumed**: the yaw is contaminated by BOTH pitch and roll (~1.3x),
and **both are one-directional BIASES**, which is what a deterministic correction can
remove. ⛔ **No depth dependence** — binned within takes, the four disagree on sign.
⛔⛔ **A regression cost a live session**: the fade-in used twist MAGNITUDE, so a real
pitch gesture had its whole swing damped. ⭐⭐⭐ **THE METHOD RULE: A GOLDEN VECTOR
BUILT FROM A MATHEMATICALLY PURE INPUT TESTS A CASE THE PRODUCT NEVER SEES.**
⚠ **The gate is cleared on 3 of 4 takes**; `stripped` is 1.072x, 7% over the bar.
⚠ **OWED: the production live look.**
→ [`../00_CORE/queue_notes/V2.md`](../00_CORE/queue_notes/V2.md)

**Open, deliberately not next**: the two-hand swap · `N8` cube-stealing
palm-first (routed to `B5`) · `T1` back-of-hand rotation quality · `T4`
yaw/palm-sink · `N12` pitch-crossing jump · `U5` occlusion coast.

---

## What to read, for what

| you want to… | read |
|---|---|
| ⭐⭐ **touch the yaw lean, or any rotation CORRECTION** | [`../00_CORE/queue_notes/V2.md`](../00_CORE/queue_notes/V2.md) — swing/twist, two gains, the gate it had to clear, and why 0.66 is a BRACKET and not a derivation. ⛔ Read `REJECTED.md` first: three predecessors died of VARIANCE |
| ⭐⭐ **change anything that depends on where the CAMERA is** | [`../00_CORE/queue_notes/V1.md`](../00_CORE/queue_notes/V1.md) — `Resources/camera_mount.py` owns the mirror, the orientation sign, the depth direction and the chirality bit. ⛔ Do not add a fourth place that knows about the camera |
| ⛔ **check whether an idea has already failed** | [`REJECTED.md`](REJECTED.md) — **do this first, it is the cheapest page here** |
| know the processes, modules and every command | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| know what to build next | [`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md) |
| ⭐⭐ **judge `F1`** — the transform from the fingertips | [`spec/F1_FINGERTIP_TRANSFORM_SPEC.md`](spec/F1_FINGERTIP_TRANSFORM_SPEC.md) — the owner's specification, the palm-frame-deformation design, the acceptance bar, and the build order. ✅✅ **ALL STEPS SHIPPED 2026-08-27**; ⛔ the rotation TRIM was removed on §10.1's take |
| understand the yaw lean before touching rotation | [`spec/ORIENTATION_DIAGNOSIS.md`](spec/ORIENTATION_DIAGNOSIS.md) |
| **measure** a rotation change without being fooled | [`spec/ROTATION_ACCEPTANCE_AND_TRAPS.md`](spec/ROTATION_ACCEPTANCE_AND_TRAPS.md) — the baselines to beat, the six traps, the takes to use |
| ⭐⭐ **fix orientation or touch the world landmarks** | [`spec/SLANT_TILT_AND_Z_RECONSTRUCTION.md`](spec/SLANT_TILT_AND_Z_RECONSTRUCTION.md) — drafted 2026-08-27; ✅ **Strategy A was BUILT, WIRED to a live A/B rig, and ⛔⛔ OWNER-REJECTED, all on 2026-08-27** — `Resources/palm_slant.py` + `Resources/palm_slant_axis.py` are kept and default to gain 0; `slant_rig.bat` is ARCHIVED to `_archive/launchers/` (the `--slant-rig` flag is still live). ⛔ **Strategy B is untouched and now UNSUPPORTED**: it needs an orientation that survives live, and none does. ⭐ The shipped form corrects the **AXIS**, not the angle, so it needs no per-user table. ⛔ Read its top note first: a measured **17–20° false-tilt floor** makes this a large-angle correction, not a replacement for Horn. Why the ratio table is a **lossy projection** (one number, two unknowns), the **bijective** slant/tilt replacement measured on the takes, remedies for its three degeneracies, and a strategy to repair `z` upstream. ⛔ Carries a **patent finding**: resolving the planar two-fold ambiguity via orientation sensors or viewing-angle range is patented |
| ⭐ **ANALYSE the 2D-ratio takes** (✅ all six recorded 2026-08-26) | [`spec/RATIO_TABLE_CALIBRATION_PROTOCOL.md`](spec/RATIO_TABLE_CALIBRATION_PROTOCOL.md) §4 — the analysis order and the decision thresholds. ⛔ Its two recording-time corrections are in the protocol and in [`../00_CORE/queue_notes/T6.md`](../00_CORE/queue_notes/T6.md) |
| know how snap / translate / rotate / release behave and why | [`spec/SPEC_13_snap_rotate_release.md`](spec/SPEC_13_snap_rotate_release.md), [`spec/SPEC_14_manipulation.md`](spec/SPEC_14_manipulation.md) |
| know the forward design below the gesture layer | [`spec/PERCEPTION_LAYER_SPEC.md`](spec/PERCEPTION_LAYER_SPEC.md) — ⚠ **read its §0.1 amendment log before any module body** |
| know the block representation (palm transform + finger arcs) | [`spec/SPEC_16_blocks.md`](spec/SPEC_16_blocks.md) |
| build a **new gesture** from scratch | [`spec/GESTURE_DEV_WORKFLOW.md`](spec/GESTURE_DEV_WORKFLOW.md) |
| make a recording, or replay one | [`spec/RECORDING_WORKFLOW.md`](spec/RECORDING_WORKFLOW.md) |
| know what the wire carries | [`spec/WIRE_PROTOCOL.md`](spec/WIRE_PROTOCOL.md) |
| map an old `§x.y.z` reference to its new file | [`spec/SPEC_MAP.md`](spec/SPEC_MAP.md) |
| know how the game **behaves** | [`../20_GAME_RULES/GAME_RULES.md`](../20_GAME_RULES/GAME_RULES.md) |

## Read before touching a specific area

| area | read first |
|---|---|
| **chirality, handedness, mirroring** | [`history/HANDEDNESS_LABEL_DEFECT.md`](history/HANDEDNESS_LABEL_DEFECT.md) — the label is still **10.8% wrong**; nothing chirality-sensitive reads it any more. It records **three distinct defects with one appearance**, and two cheaper fixes that were measured and failed |
| **ownership or per-hand state** | [`history/POSTMORTEM_4_1_IDENTITY_MIGRATION.md`](history/POSTMORTEM_4_1_IDENTITY_MIGRATION.md) — built, patched five times, **reverted**. `TRACK_OWNERSHIP = False`, nothing deleted. `T3` was fixed **narrowly** instead (`Resources/owner_remap.py`): ownership stays a slot **name** and only follows its track across a relabel, so there is no seam |
| **rotation estimators** | [`history/T6_INVESTIGATION_LOG.md`](history/T6_INVESTIGATION_LOG.md) §2.0.4 — where four rejects leave it, and why |

---

## History (opened by name, never loaded by default)

| file | what it is |
|---|---|
| [`history/SESSION_LOG.md`](history/SESSION_LOG.md) | every "YOU ARE HERE" block back to 2026-08-03, newest first — the narrative of how the project got here |
| [`history/T6_INVESTIGATION_LOG.md`](history/T6_INVESTIGATION_LOG.md) | the 20-section orientation investigation (§2.0–§2.0.19) |
| [`history/T6_REJECTED_REMEDY.md`](history/T6_REJECTED_REMEDY.md) | T6's proposed fix, its costs, and the execution record of all 8 steps |
| [`history/PERCEPTION_SESSION_LOG.md`](history/PERCEPTION_SESSION_LOG.md) | the perception spec's §0.2–§0.18 build log (DR-1, DR-2, M2, M4, M6…) |
| [`history/SPEC_01_12_pinch_era.md`](history/SPEC_01_12_pinch_era.md) | the whole pinch project, §1–§12 — archived direction, kept for its lessons |
| [`history/PART_ONE_PINCH_ERA.md`](history/PART_ONE_PINCH_ERA.md), [`history/PART_ONE_ORIGINS.md`](history/PART_ONE_ORIGINS.md) | Part One's rule-based origins and its banners |
| [`history/ORIGINAL_HANDOFF.md`](history/ORIGINAL_HANDOFF.md) | the Part Zero-era spec: prior art, repo layout, Pipeline A, the superseded build order |
| [`history/HANDOFF_SNAP_ROTATE_RELEASE.md`](history/HANDOFF_SNAP_ROTATE_RELEASE.md), [`history/HANDOFF_ANCHOR_ROTATION.md`](history/HANDOFF_ANCHOR_ROTATION.md), [`history/BUILD_PREDICTION_GATE.md`](history/BUILD_PREDICTION_GATE.md) | closed session briefs — executed, results folded into the specs |

⚠ `current/` is **empty**: every handoff is closed. When `F1` is specified, its
brief goes there.
