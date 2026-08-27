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

⭐⭐ **`T6`'s analysis has RUN** — protocol §4.1/§4.2 and the depth arm §8.1/§8.2,
over the six recorded takes (`analysis/t6_ratio_analysis.py`, no pipeline change).
Two results change what happens next. **The ratio table must be 2-D**: magnitude
cannot separate yaw from pitch (orthography forbids it) though the excursion's
**sign** splits them 3/3 on single-axis takes. And **the depth arm paid before the
rotation arm did**: at the **square** pose the four rigid palm spans imply depths
**13–22% apart** — drift-free, since they read the same frame — and `min` over
them *is* the absolute estimator, so its output **steps whenever rotation changes
which span wins**. ⛔ The snap gate reads it: a within-take excursion of **0.161 m
against a 0.15 m tolerance**. ⭐ The relative form is immune and the fix needs no
calibration step. ⚠ A verification pass **retracted two claims the same day** — a
drift bound whose premise the spans refute, and a "distance-free" ratio that was
distance-squared; see the dossier.
**Next: §4.3 the transfer test, §8.3 the inversion** — both still `analysis/` work.
⛔ Read [`../00_CORE/queue_notes/T6.md`](../00_CORE/queue_notes/T6.md) first, for
its **caveat zero**: the owner reports the distance was unreliable and the hand
moved during the takes. ⭐ Harmless for the ratio table — foreshortening ratios are
**scale-free** — but it invalidates every depth-derived reading, and two claims
built on one were retracted the same day. ⚠ Also: the ratio the recording tool
prints is the take median and is contaminated by the sweep; use the 0° hold.

**Open, deliberately not next**: the two-hand swap · `N8` cube-stealing
palm-first (routed to `B5`) · `T1` back-of-hand rotation quality · `T4`
yaw/palm-sink · `N12` pitch-crossing jump · `U5` occlusion coast.

---

## What to read, for what

| you want to… | read |
|---|---|
| ⛔ **check whether an idea has already failed** | [`REJECTED.md`](REJECTED.md) — **do this first, it is the cheapest page here** |
| know the processes, modules and every command | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| know what to build next | [`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md) |
| ⭐⭐ **judge `F1`** — the transform from the fingertips | [`spec/F1_FINGERTIP_TRANSFORM_SPEC.md`](spec/F1_FINGERTIP_TRANSFORM_SPEC.md) — the owner's specification, the palm-frame-deformation design, the acceptance bar, and the build order (all steps ✅ built; **the take is what is left**) |
| understand the yaw lean before touching rotation | [`spec/ORIENTATION_DIAGNOSIS.md`](spec/ORIENTATION_DIAGNOSIS.md) |
| **measure** a rotation change without being fooled | [`spec/ROTATION_ACCEPTANCE_AND_TRAPS.md`](spec/ROTATION_ACCEPTANCE_AND_TRAPS.md) — the baselines to beat, the six traps, the takes to use |
| ⭐⭐ **fix orientation or touch the world landmarks** | [`spec/SLANT_TILT_AND_Z_RECONSTRUCTION.md`](spec/SLANT_TILT_AND_Z_RECONSTRUCTION.md) — drafted 2026-08-27, NOT built. Why the ratio table is a **lossy projection** (one number, two unknowns), the **bijective** slant/tilt replacement measured on the takes, remedies for its three degeneracies, and a strategy to repair `z` upstream. ⛔ Carries a **patent finding**: resolving the planar two-fold ambiguity via orientation sensors or viewing-angle range is patented |
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
