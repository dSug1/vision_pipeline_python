# `AS9` — the grip marker, the depth gauge, and the z readout

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅✅ **SHIPPED 2026-08-28** — built and live-confirmed in BOTH tools · **SUB** · 3D
> **KIND** · render · **DEP** · `AS7`

---

## 2026-08-28 — the hand needed a depth cue too

> **Owner:** *"instead of all the landmarks, draw a circle to show the center of
> the hand (where the grab would lock) and scale the center to display the z
> position. this will help me figure out where are my hands."*
> …then: *"the scale of circle has to be from much wider to much smaller … it
> shall be inversed … When 2 circles are the same scale, it means the hands are at
> the same position on z axis."*

## ⭐ What it is

A ring at the **fingertip barycentre** — the exact `hand_pos` the snap test
consumes, **handed to the renderer, never recomputed there**. Plus a centre dot,
and in the debug tool the depth in metres beside it.

## ⛔⛔ The first version was wrong twice, and both were instructive

**1. THE RANGE WAS ARITHMETICALLY STUCK.** It drew a real 85 mm through
`projected_size_px`, so its size ratio across the play volume was **fixed at
`0.85/0.30 = 2.83x`** — and no choice of nominal size can change that, because a
bigger marker scales both ends equally. ⭐ **The fix was to stop imitating an
object and become an INSTRUMENT.** Once it is a gauge, exaggeration is a
calibration choice, not a lie: **22 px → 192 px, 8.6x**, and **linear in depth**
rather than in `1/depth`, because a perspective curve compresses the far half —
which is exactly where matching is hardest.

⭐⭐ The property the owner actually named survives, because it needs only
**MONOTONICITY**: two rings that match are two hands at the same depth.

**2. THE DIRECTION WAS INVERTED, AND THAT WAS A DEFECT, NOT A PREFERENCE.** `V1`
recorded the artifact: with a **facing** camera, pushing the hand toward the camera
pushes the held object AWAY from the user, so `depth_from_ratio` sends
`cube.depth_m` UP and the cube SHRINKS — while a marker sized on raw camera depth
GREW. The ring and its own object moved in opposite directions.

⭐ The owner stated BOTH mounts and they are opposite, which is why the sign lives
in `camera_mount.near_camera_reads_small()` (`CONSTRAINTS` §7bis) and `legacy`
follows `head_worn`, exactly as `depth_from_ratio` does.

⚠⚠ **THE COST, STATED: the ring no longer shares the objects' projection law, so
comparing a ring to a CUBE by size means nothing.** Ring-to-ring is what it is for.
That still serves the goal — an object's depth is anchored to its hand's at grab
(`A1`), so two hands level in z carry two objects level in z.

## ⭐⭐ The `z` readout, and why it exists

A per-object / per-hand HUD (debug only, same standing as `home_cube`): each
object's `depth` · `owner` · **`role`** · whether it has a grab anchor; each hand's
grip depth.

⛔ **It exists because guessing failed.** A z defect was reported four times and
reproduced offline zero times. `METHOD` says print the aggregation and suspect the
instrument — there was no instrument. **The readout found `AS8` in one line**:
`mated=True` immediately after an `unlink()`.

⭐ The row that matters is `role`: a **follower** is placed BY the mate, so its
depth is not its own however hard the hand pushes.

## Also in this row

* **A held object is outlined by its own CONTOUR** (owner: *"highlight its contour
  in white instead of adding a white square in front of it"*). The square was the
  object's AXIS-ALIGNED footprint, so it sat in front of the shape and stayed
  square however the cube turned — the same complaint `object_extent` fixed for the
  grab radius. Production also stopped whitening every face edge, which read the
  same way face-on.
* ⛔ **A production startup crash, caught by a headless render smoke test and by no
  suite**: `_hand_grips` was created only in `set_hand_landmarks`, but
  `pump_and_draw` reads it every frame — and production draws frames before the
  first hand packet arrives. Initialised in `__init__`.

⚠ [SUPERSEDED — the live look was GIVEN 2026-08-28; see the closing section below] ⛔ **LIVE LOOK OWED**, including whether 22→192 px is enough range.


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

⚠ The instrument's cost is accepted with it: **a ring can no longer be compared to a CUBE by size** — ring-to-ring is what the gauge is for.

⚠ **What a live acceptance is not**: it is not a measurement, and it retires
no number that was never taken. See `QUEUE.md`'s YOU-ARE-HERE
block and the spec's §13 for what remains open across the whole `AS` row.
