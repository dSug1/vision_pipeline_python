# 30 — 3D OBJECTS · meshes, import, rendering

> **STATUS** · ⭐ **live — `AS1`–`AS9` BUILT 2026-08-28, none SHIPPED**
> **OWNS** · imported 3D assets, the mesh pipeline, object assembly, whatever renders them
> **READ IF** · you are touching assembly or connectors, starting real 3D-file
> import, or choosing the renderer
> **LAST VERIFIED** · 2026-08-28

---

## ⭐⭐ ASSEMBLY IS THE ACTIVE WORK — start here

Owner, 2026-08-28: *"we will stop working on the hands and start working on the
cube objects. I want the objects to be able to assemble into an assembly."*

**Design of record → [`SPEC_ASSEMBLY_MATE_CONNECTORS.md`](SPEC_ASSEMBLY_MATE_CONNECTORS.md).**
⭐⭐ **A NEW SESSION SHOULD READ ITS §12 FIRST — *what is left to build*.**
Rows `AS1`–`AS9` in [`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md).

✅ **`AS1`–`AS9` are all BUILT in both tools (2026-08-28); NONE is SHIPPED.**
44/44 suites, `parity_replay` clean — ⛔ necessary and not sufficient, because only
a live look in both tools closes a change and **production has never been run**.

⛔⛔ **One design fork is open and unanswered: a ONE-HANDED DETACH.** An un-snap
needs TWO hands today. *A tug* was recommended; nothing was chosen.

The four things a session must not rediscover:

* ⛔⛔ **A connector stores the TRUE OUTWARD NORMAL, so a mate is ANTI-PARALLEL.**
  One place knows that sign (`CONSTRAINTS` §7bis). ⚠ It is the opposite of the
  owner's first wording, and the spec §3 records why.
* ⛔⛔ **Break on the RESIDUAL of the unconstrained desires, never on the observed
  gap** — the gap is zero by construction, so the mate would be unbreakable.
  Spec §4.
* ⭐⭐ **Parent ≠ root.** Parent (the bigger object) stores the transform; the root
  is whoever is *held*, re-rooted every frame. Spec §6.1.
* ⭐ **`AS1`–`AS4` are NOT blocked on the platform decision** — no renderer,
  stdlib-only. Only `AS5` (drawing) is renderer-shaped. Spec §11.
* ⛔⛔ **ONE SCENE CAMERA — never give an object its own.** Two projections for one
  scene drew coincident faces **18.4 px apart**. Spec §8bis.

---

## What already exists, and it is more than you'd expect

⭐ **The renderer is already mesh-generic.** The cube was made a real rotating 3D
shape with a proper mesh path on 2026-08-01 precisely so it could be replaced —
*"the cube is a placeholder for future imported 3D objects"*. See
[`../10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md`](../10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md) §13.8
and `GAME_RULES.md` rule 5.

⭐ **Objects already live in a world with depth.** Since `4.2` an object has a
metric depth, moves toward and away from the camera, is grabbed through a 3D
**ellipsoid** gate, and is clamped inside a frustum-aware **play volume**. An
imported mesh inherits all of that.

⛔⛔ **The one rule that will bite an importer immediately:** anything needing an
object's **on-screen size** must use `palm_geometry.projected_size_px`, **never**
`object.size`. Since Z-translation shipped, `size` means only *"how big it is at
the resting depth"*. This binds the centre, the play-area clamp, the grab radius
and both renderers — and `_top_left_for_center` was **deleted from both tools**
for exactly this reason. Do not reintroduce it.
([`../00_CORE/CONSTRAINTS.md`](../00_CORE/CONSTRAINTS.md) §7.)

## The blocker, and it is not effort

Queue [`U2`](../00_CORE/queue_notes/U2.md) — **real 3D-file import (OBJ/glTF)** —
is **postponed on the PLATFORM DECISION**, owner, 2026-08-04.

⛔ **Do not build it against the pygame renderer.** The original design targets
**Blender → glTF/GLB → Three.js**; the current pygame renderer is a PC-side
prototype. Building an importer for the prototype means building it twice. The
platform call is `U3`'s, and it is still the owner's to make
([`../00_CORE/DECISIONS.md`](../00_CORE/DECISIONS.md)).

## Read

| | |
|---|---|
| ⭐⭐ **assembly — connectors, the residual rule, the object tree** | [`SPEC_ASSEMBLY_MATE_CONNECTORS.md`](SPEC_ASSEMBLY_MATE_CONNECTORS.md) — **§13 says what is left** |
| the NARRATIVE — every live defect, and the fixes that caused the next one | [`history/ASSEMBLY_BUILD_LOG.md`](history/ASSEMBLY_BUILD_LOG.md) ⚠ opened by name, never loaded by default |
| the original asset pipeline design (Blender → glTF → Three.js) | [`ORIGINAL_SPEC_PIPELINE_B.md`](ORIGINAL_SPEC_PIPELINE_B.md) (was `Specification.md` §8) |
| the mesh-generic renderer as built | [`../10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md`](../10_HAND_TRACKING/spec/SPEC_13_snap_rotate_release.md) §13.8 |
| what depth and the play volume already give you | [`../10_HAND_TRACKING/spec/SPEC_14_manipulation.md`](../10_HAND_TRACKING/spec/SPEC_14_manipulation.md) §14.3.5 |
| how objects behave today | [`../20_GAME_RULES/GAME_RULES.md`](../20_GAME_RULES/GAME_RULES.md) rules 5, 7–10 |
| the platform question | [`../50_PORT_WEB_MOBILE/INDEX.md`](../50_PORT_WEB_MOBILE/INDEX.md) |

## ⚠ The use case the game is aimed at

`F1` exists because the owner wants **assembly-style alignment of small
objects** — *"If I want to mimick grabbing and rotating small objects, I need to
use fingertips to be able to rotate them subtely to align them for assembly."*
That is the manipulation precision an imported asset will have to be worth. It
also implies meshes with meaningful **alignment features**, not decorative props.

## Adding work here

Add rows to [`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md) with `Sub = 3D`, next to
the `AS` block. **Do not start a queue in this folder.**
