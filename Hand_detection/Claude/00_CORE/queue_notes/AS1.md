# `AS1` — the `MateConnector` data model

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · in build 2026-08-28 · **SUB** · 3D · **KIND** · feature · **DEP** · —

Design of record: [`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md).

---

## 2026-08-28 — opened

The owner specified assembly-by-connector and, after a literature review, took the
four decisions in [`../DECISIONS.md`](../DECISIONS.md). This row is the data model
alone — no behaviour, so nothing here can be wrong in a way a golden vector cannot
catch.

**What it carries**, in the object's own local (unit-mesh) frame:

| field | why |
|---|---|
| `position` | where on the surface |
| `normal` | ⛔ the **TRUE OUTWARD NORMAL** — spec §3. Anti-parallel is the mate condition |
| `tangent` | the roll reference. Without it a mate is Onshape's **Revolute**, not **Fastened** (spec §5) |
| `roll_order` | symmetry order — `4` for a square face, `0` = free spin |
| `radius` | the capture sphere, defaulted from the object's own half-extent |
| `kind` | reserved. Genderless in v1: any connector may mate any connector |

⭐ **The default constructor is free on today's meshes**: `MeshFace` already carries
its own `normal` and its vertex indices, so a face-centre connector is
`mean(vertices), face.normal` — which is also Onshape's own default (*"click a face
→ connector at the centroid"*).

⛔ **Stdlib-only, numpy-free, no side effects**, the port contract of
`CONSTRAINTS` §2. It is modelled on `Resources/object_extent.py`, which exists for
exactly this reason: geometry both renderers need, hosted by neither.

---

## 2026-08-28 — BUILT

`Resources/mate_connector.py` — `MateConnector`, `ConnectorPose`,
`face_center_connector`, `world_pose`. Stdlib-only, numpy-free and **clock-free**
(`now_ms` is passed in, like `hand_state`).

⛔⛔ **THE FIRST BUILD GAVE EACH CUBE ONE CONNECTOR AND IT WAS UNREACHABLE.** Both
were on the `+X` face, and both cubes start unrotated — so the two outward normals
pointed the **same** way, facing deviation **180°**, the worst value there is.
Nothing could mate, and nothing could even be previewed, until a cube was turned a
full half-turn. The owner found it by seeing an empty screen (2026-08-28); every
offline check had passed.

⭐⭐ **THE METHOD RULE IT COST: a fixture that CONSTRUCTS the configuration it tests
cannot discover that the product never reaches it.** Every vector built its scene by
placing the small cube already rotated into position. The assertions were true. The
**starting state** was never in the suite, and the starting state was the defect.

✅ **The default is now ALL SIX FACES.** Any face mates any face; several candidates
exist, so `AS7`'s bubble-cursor choice is real; and ⭐ six outward normals drawn on a
cube **are** an orientation gizmo — the first thing the owner asked for, for free.
⚠ 6 × 6 = 36 pair tests a frame at this scale: nil.

Built by `object_assembly.cube_face_connectors` from the mesh itself, so there is
nothing per-object to register: an imported OBJ or glTF carries the outward normals
this reads.

⚠ `radius` is stored as a **fraction of the object's own half-extent** rather than
an absolute number, so a new object is capturable the moment it is added — the same
property `U9`'s clamp has. At today's sizes that is 9.0 mm (small) and 18.0 mm
(large).

✅ `analysis/verify_mate_connector.py`, 40 checks, all passing.

