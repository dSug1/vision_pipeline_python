# `AS3` — ⭐⭐ the residual ordering, and the snap transform

> **Dossier.** The full history of this queue row.
> Its one-line status and its place in the order are in [`../QUEUE.md`](../QUEUE.md)
> — update **both** when it changes.
>
> **STATUS** · ✅✅ **SHIPPED 2026-08-28** — built and live-confirmed in BOTH tools · **SUB** · 3D · **KIND** · feature · **DEP** · `AS2`

Design of record: [`../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../../30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md) §4, §5, §7.

---

## 2026-08-28 — opened. ⛔⛔ This row exists because the owner's rules 2 and 3 conflict

**As first specified the mate is unbreakable by construction.** *"The child's
connector is always coincident with the parent's"* makes the separation identically
zero, so *"breaks when pulled apart beyond the sphere intersection"* can never fire.

⭐ **The fix is what every physics engine already does for breakable joints, and it
needs no physics.** PhysX breaks a joint when *"the force or torque required to
**maintain** the constraint"* exceeds a threshold; Unity compares `breakForce`
against the **reaction force**. Both read the violation the solver absorbed — not
the observed gap, which is zero by construction.

```
each frame, per live mate:
  1. DESIRE    each object's pose from its OWN driver (its hand, or its parent)
  2. RESIDUAL  linear + angular departure between the two DESIRED connector poses
  3. BREAK ?   over threshold -> drop the mate, both keep their desires
  4. ENFORCE   otherwise -> child onto the parent's connector, and draw that
```

**Measure on the unconstrained targets; apply the constraint after.**

## ⭐⭐ The consequence that falls out for free

**One hand can never break a mate.** With a single driver the other object follows
and the residual is identically zero; a residual needs **two independent drivers**.
So *"the hands pull them apart"* is literally true, plural — no new rule, no
threshold on hand state, and **no new gesture**, which matters because `4.4`'s
hand-open release trigger is not built. It is also **Guiard's kinematic chain**
(1987): one hand holds the frame, the other acts.

## ⚠ The clamp is exempt — owner decision, 2026-08-28

The play-volume clamp is a second driver, so an object at a wall would break its
mate for a reason **no player can see**. Residual is computed from the hand-driven
desire, **before** the clamp.

## The snap transform

Child rolls to the **nearest of `roll_order` valid rolls** about the contact axis →
the mate is **Fastened** (0 DOF), not Onshape's **Revolute** (which is what
normals-only would have given).

⭐ **The HELD object moves** at the instant of snap, whichever becomes child — the
person is aiming the thing in their hand. Unreal's snap system moves the *source*
actor for the same reason.

⛔⛔ **THE TRAP**: re-seat `grab_grip_offset` and the depth anchor at snap, or the
hand anchor and the mate drive one transform with two different ideas of where it
belongs. That is the class of defect `R1` fixed by anchoring `grab_hand_depth_m` on
the grip point.

⭐ **Reuse `F1`'s motion-masked walk** for the approach, not a fourth damper design.
Three were live-rejected before `R1`'s FREEZE stuck.

---

## 2026-08-28 — BUILT

`snap_pose` in `mate_connector.py`; the ordering in `object_assembly.resolve` /
`step`, called from **both** tools at the same point in the frame — after the
per-hand loop, before the draw.

⭐⭐ **THE FREE CONSEQUENCE WAS MADE STRUCTURAL, and that was not the first design.**
The vectors showed "one hand cannot break a mate" was **emergent, and therefore
breakable**: an undriven follower has no independent wish, and answering "what did
it want?" with its **stored pose** made a mate snap when its parent was pushed into
a play-volume **wall**. ⛔ The residual is now computed **only when BOTH objects are
driven** — an undriven object's driver *is* the mate, so it cannot disagree with
itself. The claim is a property of the code now, not a likely outcome of it.

⛔⛔ **AND A SECOND FINDING THAT IS NOT DEDUCIBLE FROM THE ORDERING ALONE: ENGAGE and
ENFORCE read the ACTUAL pose; only BREAK reads the DESIRE.** The first draft enforced
from the desire — which reads like the natural interpretation — and the child
**sailed on through the play-volume wall while the parent stopped dead**. The
ordering is about *what breaks a mate*; where objects are **drawn** must follow where
they actually are.

⚠ **A third bug was in the HARNESS, not the module**: it fed desires without first
applying them to the cube, which is not the order either tool runs. Three checks
failed and the module was innocent. `METHOD`: the instrument is a suspect, always.

⭐ The quaternion is built by **Shepperd's method**, not the textbook `w`-first form:
anti-parallel normals mean a mate routinely lands on a **half turn**, which is
exactly where the textbook form loses precision or sign. Pinned at 180° about all
three axes.

✅ `analysis/verify_object_assembly.py`: mates at the pose a player aims for
(connectors **0.0000 mm** apart, **0.0000°**), survives a 156 px one-handed drag,
survives 0.50 → 0.72 m in depth, breaks only under two hands.


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

⚠ The residual rule is now load-bearing in a shipped build. Its consequence — **one hand can never break a mate** — is the RULE, decided the same day (*"unsnapping needs two hands"*), and the live look is the owner accepting it in practice, not merely in principle.

⚠ **What a live acceptance is not**: it is not a measurement, and it retires
no number that was never taken. See `QUEUE.md`'s YOU-ARE-HERE
block and the spec's §13 for what remains open across the whole `AS` row.
