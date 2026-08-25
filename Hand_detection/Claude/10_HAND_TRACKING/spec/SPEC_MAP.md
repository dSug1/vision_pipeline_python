# SPEC_MAP — old section numbers → new files

> **STATUS** · live · **OWNS** · resolving any `§x.y.z` reference written before
> 2026-08-25
> **READ IF** · a document cites a section number and you cannot find the file
> **LAST VERIFIED** · 2026-08-25

⭐ **Section numbers were NOT renumbered.** `§14.3.4.11` is still `§14.3.4.11`;
only the file it lives in changed. Search for the heading inside the file named
below.

## `GESTURE_PIPELINE_SPEC.md` (was one 443 KB file)

| sections | now in |
|---|---|
| §1 (why rule-based was abandoned) | [`../history/SPEC_01_12_pinch_era.md`](../history/SPEC_01_12_pinch_era.md) |
| **§2 (core discipline)** | [`GESTURE_DEV_WORKFLOW.md`](GESTURE_DEV_WORKFLOW.md) — still binding |
| §3–§12 (pipeline stages, pinch corpus, the whole pinch arc) | [`../history/SPEC_01_12_pinch_era.md`](../history/SPEC_01_12_pinch_era.md) |
| **§13–§13.8** (snap / translate / rotate / release; the mesh-generic renderer) | [`SPEC_13_snap_rotate_release.md`](SPEC_13_snap_rotate_release.md) |
| **§14–§14.3.6** (translation, Z-axis, the yaw investigation, 4.2, the lag fix) | [`SPEC_14_manipulation.md`](SPEC_14_manipulation.md) |
| §15–§16.17 (perception layer integrated; the block representation) | [`SPEC_16_blocks.md`](SPEC_16_blocks.md) |
| **§17** (the input system) | [`../../40_INPUT_SYSTEM/SPEC_17_input_system.md`](../../40_INPUT_SYSTEM/SPEC_17_input_system.md) |
| **§18** (robustness + security audit) | [`../../60_SECURITY_COMPLIANCE/SPEC_18_security_audit.md`](../../60_SECURITY_COMPLIANCE/SPEC_18_security_audit.md) |

Frequently cited, so worth naming directly — all in `SPEC_14_manipulation.md`:
**§14.1** grab-relative translation · **§14.2** the hand-open release trigger ·
**§14.3** Z-axis translation · **§14.3.4–§14.3.4.11** the yaw-lean investigation ·
**§14.3.5** what 4.2 shipped · **§14.3.6** the rotation lag.
And in `SPEC_13_snap_rotate_release.md`: **§13.5** the reverted built-in
classifiers · **§13.6.1** the production-only inversion · **§13.7** rotation while
snapped · **§13.8** the mesh-generic renderer.
And in `SPEC_16_blocks.md`: **§16.14** the retracted "SINK" · **§16.17** *"a jump
both estimators reproduce is already in the landmarks"*.

## `PERCEPTION_LAYER_SPEC.md` (was one 231 KB file)

| sections | now in |
|---|---|
| header, **§0.0** (where the evidence lives), **§0.1** (the amendment log — ⚠ binding) | [`PERCEPTION_LAYER_SPEC.md`](PERCEPTION_LAYER_SPEC.md) |
| §0.2–§0.18 (the dated build log: baselines, DR-1, DR-2, M2, M4, M6, the audit) | [`../history/PERCEPTION_SESSION_LOG.md`](../history/PERCEPTION_SESSION_LOG.md) |
| §0–§10 (framing, target architecture, `HandState` v2, modules M0–M10, test protocol, anti-patterns, the S1–S12 addendum) | [`PERCEPTION_LAYER_SPEC.md`](PERCEPTION_LAYER_SPEC.md) |

⚠ Note the collision: this file has **two** `§0`-numbered runs — the dated `§0.x`
log and the un-numbered `§0 Framing`. They are now in different files, which
removes the ambiguity.

## `PART_ONE.md` (was one 307 KB file)

| sections | now in |
|---|---|
| title + the 2026-07-30/08-01 banners | [`../history/PART_ONE_ORIGINS.md`](../history/PART_ONE_ORIGINS.md) |
| §1 scope, §2 core architecture decisions, §3 gesture/signal matrix, the S1–S12 index | [`PART_ONE_SCOPE_AND_MATRIX.md`](PART_ONE_SCOPE_AND_MATRIX.md) |
| **§3.1 the build queue** | ⭐ [`../../00_CORE/QUEUE.md`](../../00_CORE/QUEUE.md) — compact rows; each row's full text is `00_CORE/queue_notes/<ID>.md`. Its preamble is [`_QUEUE_PREAMBLE.md`](../../00_CORE/queue_notes/_QUEUE_PREAMBLE.md) |
| §3.1's "YOU ARE HERE" blocks | [`../history/SESSION_LOG.md`](../history/SESSION_LOG.md) |
| §4 wire-protocol gap | [`WIRE_PROTOCOL.md`](WIRE_PROTOCOL.md) |
| §5 open items to resolve empirically | [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) |
| §6–§6.1 pinch classifier design basis | [`../history/PART_ONE_PINCH_ERA.md`](../history/PART_ONE_PINCH_ERA.md) |
| §7–§7.2 recording & analysis workflow | [`RECORDING_WORKFLOW.md`](RECORDING_WORKFLOW.md) |
| §8 general gesture classifier workflow | [`GESTURE_DEV_WORKFLOW.md`](GESTURE_DEV_WORKFLOW.md) |

## `HANDOFF_T6_ORIENTATION_FROM_2D.md` (was 94 KB, now closed)

| sections | now in |
|---|---|
| the closed banner, §1 the defect, §2 the cause | [`ORIENTATION_DIAGNOSIS.md`](ORIENTATION_DIAGNOSIS.md) — ⭐ **the part that still stands** |
| §2.0–§2.0.19 the investigation | [`../history/T6_INVESTIGATION_LOG.md`](../history/T6_INVESTIGATION_LOG.md) |
| §3 the fix, §4 the costs, §9 the execution record | [`../history/T6_REJECTED_REMEDY.md`](../history/T6_REJECTED_REMEDY.md) |
| §5 acceptance, §6 rejected, §7 traps, §8 the takes | [`ROTATION_ACCEPTANCE_AND_TRAPS.md`](ROTATION_ACCEPTANCE_AND_TRAPS.md) — ⭐ reusable for `F1` |

## `Specification.md` (the Part Zero-era handoff)

| sections | now in |
|---|---|
| §0 goal & constraints, §13 open decisions | [`../../00_CORE/ORIGINAL_GOAL_AND_CONSTRAINTS.md`](../../00_CORE/ORIGINAL_GOAL_AND_CONSTRAINTS.md) |
| §1 prior art, §2 architecture, §3 repo layout, §7 Pipeline A, §11 build order | [`../history/ORIGINAL_HANDOFF.md`](../history/ORIGINAL_HANDOFF.md) |
| §4 Part Zero, §5 Part Zero-bis, §6 the landmark data contract, §12 Snap Spectacles | [`../../50_PORT_WEB_MOBILE/ORIGINAL_SPEC_PORT_SECTIONS.md`](../../50_PORT_WEB_MOBILE/ORIGINAL_SPEC_PORT_SECTIONS.md) |
| **§8 Pipeline B — Three.js + Blender** | [`../../30_OBJECTS_3D/ORIGINAL_SPEC_PIPELINE_B.md`](../../30_OBJECTS_3D/ORIGINAL_SPEC_PIPELINE_B.md) |
| §9 camera permission, §10 cybersecurity | [`../../60_SECURITY_COMPLIANCE/ORIGINAL_SPEC_PRIVACY.md`](../../60_SECURITY_COMPLIANCE/ORIGINAL_SPEC_PRIVACY.md) |

⚠ `Specification.md` §11's build order is **historical** — the queue superseded
it.

---

## How the split was done, and how to check it

Every extracted range sits between `<!-- VERBATIM-BEGIN -->` and
`<!-- VERBATIM-END -->` markers with a provenance comment naming its source file
and line range. **Nothing between those markers was edited.**

`../../_archive/migration/verify_split.py` rebuilds each original from its
scattered blocks; it reproduced all six **byte-for-byte** before the originals
were removed, and the sha256 of each is recorded in
`../../_archive/MIGRATION_MANIFEST.json`. The pre-reorg `README.md` is kept whole
at `../../_archive/README_2026-08-25_pre_reorg.md`.
