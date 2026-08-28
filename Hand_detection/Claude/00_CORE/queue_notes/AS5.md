# `AS5` — drawing the connectors and the mate state

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · in build 2026-08-28 · **SUB** · 3D · **KIND** · render · **DEP** · `AS3`

Design of record: [`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §10.

---

## 2026-08-28 — opened

⚠ **This is the ONE renderer-shaped part of the assembly work**, and it is
deliberately thin and per-tool so it is cheap to throw away when the platform
decision lands. `AS1`–`AS4` are stdlib-only and touch no renderer, which is why the
assembly project as a whole is **not** blocked on that decision the way `U2` is.

**What it draws**, in both tools:

* the connector itself — a marker at its projected position, oriented by its normal
  so the outward direction is visible (⭐ the sign convention is invisible in code
  and obvious on screen; this is the cheapest guard there is against §3 being
  wrong);
* the **candidate** state, when a mate is within capture but not yet engaged;
* the **engaged** state.

⛔ It must go through `palm_geometry.projected_size_px` / `px_from_world`, never
`object.size` — `CONSTRAINTS` §7.

⚠ **Renderer parity is unguarded** (`parity_replay` compares gesture logic, not
drawing) — that is how the debug tool silently lost its snap-highlight for two days
on 2026-08-25. Both tools change here; look at both.

---

## 2026-08-28 — BUILT

`CubeWindow._draw_connectors` (pygame) and the connector block in
`LiveSnapDebug._draw_cube_3d` (cv2). A dot at the connector, a whisker along its
**outward normal**, coloured grey / **amber** (within capture, not yet engaged) /
**green** (mated).

⚠⚠ **THE COLOURS ARE NOT SHARED CONSTANTS AND MUST NOT BECOME ONE**: production
draws in **RGB** (pygame) and the debug tool in **BGR** (cv2), so the same colour is
written with its channels reversed. What *is* shared is the RULE that picks between
them — `object_assembly.step` sets `cube.mate_state` and both renderers read it, so
the two tools cannot disagree about *when* a connector is amber.

⭐ `mate_state` is recomputed from live state every frame rather than toggled on
events, so it cannot get stuck showing a mate that has gone.

⛔ Connectors are drawn **after** the faces and without a depth test of their own, so
one on the far side shows through — deliberate: it is what makes it possible to aim
a face you cannot see.

