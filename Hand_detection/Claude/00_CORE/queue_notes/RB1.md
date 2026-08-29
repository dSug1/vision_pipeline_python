# `RB1` — the frame — one viewpoint, as a rotation

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅ BUILT 2026-08-29 · **SUB** · HAND · **KIND** · perception

Design of record:
[`../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`](../../10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md).

---

## 2026-08-29 — opened by the rebuild

> **Owner:** *"I think we have patched too much this script … I want to build the
> control by hand detection delta increment from scratch. Strip all the filters and
> multiplicators, etc.: we will rebuild them as we need them."*

⛔⛔ **What justified a rebuild rather than another fix**: the composite mapping had
become a **REFLECTION**. `camera_mount` reversed pitch+yaw, `delta_orbit.AXIS_SIGN`
reversed pitch back — net, yaw reversed alone, det −1. A rigid hand→object
correspondence cannot do that. Every layer was locally reasonable and the stack was
not: `METHOD`'s *no heuristic pile-up*, arriving in the one place nobody measured —
the composition.

See the spec for the full design. This dossier carries what is specific to `RB1`.
