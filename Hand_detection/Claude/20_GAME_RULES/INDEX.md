# 20 — GAME RULES · how the game behaves

> **STATUS** · live · **OWNS** · the behavioural statement of record
> **READ IF** · you need to know what the game *does*, or you are changing
> behaviour a player can see
> **LAST VERIFIED** · 2026-08-25

[`GAME_RULES.md`](GAME_RULES.md) is the **behavioural statement of record** — the
rules in plain language, as confirmed and built. **Add a rule here every time one
is confirmed and implemented**, short and in plain language; the *why* lives in
the specs, the *how* in the code.

⚠ It is the record for behaviour, not for build order. The build order is
[`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md).

## The rules, at a glance (10 live)

| # | rule |
|---|---|
| 1 | **Snap on proximity** — either hand, one object per hand |
| 2 | **Un-snap on tracking loss, after a 150 ms coast** — ⭐ the dropout behaviour of record. ⚠ Not M10.7's grace period: the coast is a **sensor** rule (no measurement, so no evidence), M10.7 would be a **game** rule. `D4` was **declined** |
| 3 | **Thumb-outward snap restriction** — and it must not act on a *provisional* chirality (`U8`) |
| 4 | **Rotation while snapped** — grab-referenced, permanently ungated by open-palm |
| 5 | **Objects are real rotating 3D shapes**, not flat squares |
| 6 | **Translation follows a grab-relative, distance-weighted point** — not the hand centre |
| 7 | **No snapping while depth is frozen** (`4.2`) |
| 8 | **An object moves toward and away from the camera** with the hand holding it (`4.2`) |
| 9 | **An object can only be picked up by a hand beside it — in all three axes** (`4.2`, an ellipsoid, not a sphere) |
| 10 | **The play area is a volume, not a rectangle** (`4.2`, frustum-aware) |

Plus a **Not yet built** section, and a **Status** section.

⭐ **In build 2026-08-28, not yet a rule: objects ASSEMBLE** via mate connectors
(`AS1`–`AS5`). It becomes rule 11 when it is live-confirmed in both tools — design
of record [`../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md).

## Where the *why* lives

| rule area | rationale |
|---|---|
| snap / rotate / release design | [`../10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md`](../10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md) §13 |
| translation, Z-axis, the play volume | [`../10_HAND_TRACKING/spec/SPEC_14_manipulation.md`](../10_HAND_TRACKING/spec/SPEC_14_manipulation.md) §14.1, §14.3, §14.3.5 |
| the dropout coast and resync blend | queue [`D1`](../00_CORE/queue_notes/D1.md) / [`D2`](../00_CORE/queue_notes/D2.md) / [`D3`](../00_CORE/queue_notes/D3.md) |
| chirality and the snap restriction | [`../10_HAND_TRACKING/history/HANDEDNESS_LABEL_DEFECT.md`](../10_HAND_TRACKING/history/HANDEDNESS_LABEL_DEFECT.md) |

## ⚠ Stale pointers inside `GAME_RULES.md`

Its body still cites `PART_ONE.md §3.1` for build order and
`GESTURE_PIPELINE_SPEC.md §13` / `§14.3` for rationale. Those documents were
split on 2026-08-25 — the **section numbers are unchanged**, only their files
moved. Resolve any of them with
[`../10_HAND_TRACKING/spec/SPEC_MAP.md`](../10_HAND_TRACKING/spec/SPEC_MAP.md).

---

## When the game proper starts

This folder is where the *game's* rules go — scoring, levels, objectives,
assembly targets. Today it holds only the manipulation rules, because that is
all that exists. **Do not start a queue here**; add rows to
[`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md) with `Sub = GAME`.
