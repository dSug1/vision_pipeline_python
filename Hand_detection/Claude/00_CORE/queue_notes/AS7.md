# `AS7` — the mate preview: a ghost and a drop line

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅✅ **SHIPPED 2026-08-28** — built and live-confirmed in BOTH tools · **SUB** · 3D
> **KIND** · render · **DEP** · `AS3`

Design of record:
[`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §7ter.

---

## 2026-08-28 — opened by the SECOND live run

> **Owner:** *"it is very difficult to judge the relative positions of the objects
> on z axis and therefore to align them for snap … draw the small object projected
> to the mate in translucent highlighted. that will also help select which mate to
> choose."*

## ⛔ Why depth is unreadable, and it is not a drawing bug

The play volume is 0.30–0.85 m — **personal space**, where **Cutting & Vishton**
rank **occlusion** the strongest depth cue by a wide margin, and where their data
show its presence drives motion parallax's weight to near zero. `R1` ships
occlusion already.

⛔ **But occlusion is SILENT until the two shapes overlap on screen**, which in a
face-to-face approach is not until they nearly touch. **The strongest cue available
is absent for exactly the phase that needs it.** What remains is relative size, and
that is confounded because the two cubes genuinely differ in size. No stereo. So
the depth has to be **drawn**.

## ⭐⭐ The literature's answer, and it comes from a MANIPULATION paper

**Herndon et al., "Interactive Shadows" (UIST 1992)** introduced shadow widgets so
a user could position objects in 3D **with a 2D input device** — this situation
precisely: a hand whose z is *estimated*, driving an object in a 3D scene. The gap
between an object and its projection reads as depth where the object alone does not.

⭐ The **ghost** is the other half, from the building-game / CAD *placement preview*
tradition.

⭐⭐ **The owner's two proposals are not alternatives.** They answer different
questions, which is why both were built: the **ghost** says *where would it land*,
the **drop line** says *how far is there still to go* — the half z hides.

## ⚠⚠ The preview must appear BEFORE the mate is possible

Or it is a report, not an aid. Hence its own wider gates (`PREVIEW_RADIUS_FACTOR`,
`PREVIEW_ANGLE_DEG`). ⭐ And its colour carries what the player cannot otherwise
tell — **which condition is failing**: amber while out of reach, **green the instant
only the dwell is left**, which says *hold still* rather than *keep pushing*.

## ⭐⭐ Choosing between several mates — the bubble cursor

`mate_connector.mate_score` normalises each clause by its own threshold and takes
the worse, so **`score ≤ 1` is true exactly when `can_mate` is** — a strict
generalisation, not a second opinion (`METHOD`: a recomputation is a second
implementation that can silently disagree). Only the best-scoring candidate is
drawn: **Grossman & Balakrishnan's bubble cursor** (CHI 2005), where exactly one
target is selectable and which one is made visible.

⛔ **The ghost pose comes from `snap_pose`**, the same function that would actually
place the object — a lookalike would teach the player something the mate then
contradicts. The vectors assert it lands **0.0000 mm / 0.0000°** from the real one.

## Built

`MatePreview` + `_preview_for` in `object_assembly`; `mate_score` in
`mate_connector`; `Cube.mate_preview` in both tools;
`CubeWindow._draw_mate_preview` and `LiveSnapDebug._draw_mate_preview`.

⚠ **The two renderers differ deliberately, and it is not drift.** Production fills
the ghost translucently (`SRCALPHA` surface, alpha 70/190) because its cubes are
opaque. The debug tool draws **outline only**, because it already alpha-blends the
whole overlay — a filled ghost there would come out at the same weight as a real
cube, which is the exact confusion the ghost exists to remove. The **rule** is
shared; only the primitives differ.

⚠ The drop line is **dashed** on purpose: a solid line reads as a link that already
exists.

✅ 42/42 suites; `parity_replay` **NO DIVERGENCE on 4 takes**. Headless render smoke
tests pass in both tools.

⚠ [SUPERSEDED — the live look was GIVEN 2026-08-28; see the closing section below] ⛔ **LIVE LOOK OWED.**


## ✅✅ 2026-08-28 — SHIPPED. THE LIVE LOOK IN BOTH TOOLS IS DONE

> **Owner, after running production:** *"production run was done by me and it is
> ok"*.

⭐⭐ **THIS IS WHAT THE ROW WAS WAITING FOR, AND NOTHING ELSE WOULD HAVE DONE.**
44/44 golden-vector suites and a clean `parity_replay` on four takes had been true
since the build — `METHOD` calls that necessary and not sufficient, and §13.6.1
once shipped **inverted** while passing an *"end-to-end confirmed"* claim. The
debug tool had settled the sliders and the behaviour; ⚠ **production had never
been run at all**, so every judgement stood on one renderer. It has now been run
and accepted, and the row moves **BUILT → SHIPPED**.

⚠ **The PREVIEW RADIUS is the one constant still with no measured floor** (`PREVIEW_RADIUS_FACTOR`); the snap radius and angle were settled live at `snap 150 %`, the preview one was not. Its live slider is still there.

⚠ **What a live acceptance is not**: it is not a measurement, and it retires
no number that was never taken. See `QUEUE.md`'s YOU-ARE-HERE
block and the spec's §13 for what remains open across the whole `AS` row.
