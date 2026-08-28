# `AS4` — the object tree: parent by size, ROOT by grab

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · in build 2026-08-28 · **SUB** · 3D · **KIND** · feature · **DEP** · `AS3`

Design of record: [`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §6.

---

## 2026-08-28 — opened

The owner's rule: **the smaller object becomes a child of the bigger one.** What
that describes is a **kinematic tree** with an articulation root.

## ⭐⭐ Parent and ROOT are two different things

| | | |
|---|---|---|
| **parent** | who **stores** the relative transform | the bigger object. Static |
| **root** | who is currently **driven** | whoever is held. **Re-rooted every frame** |

⛔ **Without the second row, grabbing the child cannot move anything** — the child is
by definition controlled by its parent. The hierarchy is *storage*; the drive
direction is *dynamic*, and the tree is walked outward from the grabbed node.
Standard floating-base practice, not an invention. **Conflating the two is the bug
this row exists to avoid.**

## Ties

Equal-sized objects need a deterministic tie-break (lowest object id) or the parent
flips between frames and the hierarchy chatters. ⚠ Today's cubes are 2:1 so this
cannot bite yet — written down so it is not rediscovered.

## ⛔ Cycles are REFUSED — owner decision, 2026-08-28

A third mate closing a loop makes the graph not a tree. CAD calls it **closed-loop /
over-constrained**; the standard treatment is cutting a joint to reopen the chain,
which is a solver's job. **v1 refuses such a mate and shows that it refused.**
Revisit only when a real asset needs a loop.

---

## 2026-08-28 — BUILT

`Assembly` in `mate_connector.py` (links, `root_for`, `connected`, `would_cycle`,
`can_link`, `offer`, `offer_break`) plus `order_by_size`; the re-rooting walk is
`object_assembly._driver_for` / `_edges_from`.

⚠ **`would_cycle` was written BACKWARDS and the vectors caught it.** The new link
makes the child hang under the parent, so the loop closes when the **parent** is
already below the **child** — `child_id in [parent_id] + ancestors(parent_id)`. The
first version tested the ancestors of the wrong node and reported no cycle at all.

✅ **RE-ROOTING IS MEASURED, not asserted**: with the SMALL cube (the child) in the
hand, the large cube followed it **60 px**. Without the parent/root split that number
is zero, because a child is by definition placed by its parent.

⚠ Two limits, both known and neither a bug: a **child** pinned at a play-volume wall
can drift off its parent visually (the parent is exempt from the clamp's residual,
the child is clamped after placement); and with **two hands on one assembly** the
structural parent wins the tie — not a deadlock, because that is precisely the case
whose residual grows until the mate breaks.

