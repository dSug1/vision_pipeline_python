# `AS2` — the mate predicate

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · in build 2026-08-28 · **SUB** · 3D · **KIND** · feature · **DEP** · `AS1`

Design of record: [`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §3, §8.

---

## 2026-08-28 — opened

Two connectors mate when **all** of:

```
facing    dot(n_A, n_B) <= -cos(angle_tol)      anti-parallel: surfaces face each other
outward   dot(p_B - p_A, n_A) > 0               B is on A's outward side
capture   |p_B - p_A| <= r_A + r_B              the spheres intersect
```

⛔ **The `outward` line is load-bearing.** A sphere test is direction-blind, so
without it two overlapping objects mate *through* each other.

⚠ **The `facing` sign is the opposite of the owner's first wording** and it is a
convention, not a disagreement — spec §3 records why the outward normal was chosen
(it is the surface's own property, and an imported glTF carries it already).

## The constants, and the bracket each sits in

⭐ Every one is a bracket, not a derivation — the shape `V2`'s 0.66 has.

* `MATE_ANGLE_TOL_DEG = 30.0`. **Floor 25.41°** = `F1`'s shipped per-frame
  orientation-jump p95; below it the pipeline's own noise refuses the mate.
  **Ceiling 45°** = where a cube's adjacent face is an equally good candidate.
* `MATE_RADIUS_FRACTION = 0.5` of the object's half-extent → 9.0 mm + 18.0 mm =
  **27.1 mm** of capture gap. Ceiling is the small object's own edge (36.1 mm),
  beyond which objects mate while visibly apart. ⚠ **The floor is UNKNOWN** — no
  measurement exists of hand placement precision here. **Settle live.**
* `MATE_BREAK_FACTOR = 1.5`, `MATE_DWELL_MS = 100.0` — the hysteresis. Floor on the
  factor is strictly > 1.0 or the mate chatters; the dwell is above `L1`'s measured
  48–64 ms frame gap so no single-frame excursion can toggle a mate.

⭐ **The acceptance metric this row owns**: `snap/break transitions per minute` on
a recorded take. It is what says whether the hysteresis is sized right, and it is
measurable offline.

---

## 2026-08-28 — BUILT

`can_mate` / `facing_deviation_deg` / `is_outward` / `should_break`, with the
constants above.

⚠⚠ **ONE CORRECTION THE VECTORS FORCED: the `outward` gate is `>= 0`, not `> 0`, and
that is not a loosening.** A perfect mate has the two connectors **exactly
coincident**, so the dot product at the target pose is exactly zero — a strict test
refuses the one pose the whole mechanism aims at. A nanometre of slack absorbs float
noise around that point; the gate still rejects a connector that has passed *inside*
the other object, which is what it exists for, and the vectors assert both.

⭐ The gate earns its place, measured: the interpenetrating case **passes the sphere
test alone** and is caught only by the outward clause.

✅ 40 checks passing, including the two boundaries (29° mates / 31° does not; inside
the summed radii mates, outside does not) and the dead band (engages at capture,
does not break there, breaks past 1.5×).

