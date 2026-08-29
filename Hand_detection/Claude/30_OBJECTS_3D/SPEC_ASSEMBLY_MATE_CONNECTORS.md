# ASSEMBLY — mate connectors, the residual rule, and the object tree

> **STATUS** · live · **OWNS** · how two objects join, hold and separate
> **READ IF** · you are touching assembly, connectors, the object hierarchy, or
> anything that drives more than one object at a time
> **LAST VERIFIED** · 2026-08-28
> **SOURCED FROM** · the owner's specification of 2026-08-28 (§1 below, verbatim),
> the literature review run against it the same day (§9), and the four decisions
> the owner took on its findings (§8, and [`../00_CORE/DECISIONS.md`](../00_CORE/DECISIONS.md))

⭐ **This is the design of record for assembly.** The build rows are `AS1`–`AS5`
in [`../00_CORE/QUEUE.md`](../00_CORE/QUEUE.md); each row's history is its
dossier in `../00_CORE/queue_notes/`.

---

## 1. What the owner asked for

> *"I want the objects to be able to assemble into an assembly. […] an object
> assembles with another through one or several stickers which are positioned on
> the object's surface. A sticker contains: a position, an orientation (which is
> by default the normal of the surface where the sticker is positioned at the
> position of the sticker). 2 parameters are defined by default: the tolerance for
> normal alignment at snap and the sphere radius for snap to occur. For two
> objects to assemble, the normals of two stickers (one on each object) should be
> aligned within the tolerance and not in opposite direction, and their radius
> sphere shall intersect."*

And, after the first review:

> *"call it mate connector · when the object snaps, the smaller one becomes a
> child of the bigger one and the position of the child is controlled so that the
> two mate connector positions are always identical and the normals of the mate
> connectors always align · the two objects remain grabable independently and the
> mate connection can be broken if the hands pull them apart beyond the
> connector's radius sphere intersection"*

## 2. ⭐ The name, and what comes with it

**`MateConnector`** is Onshape's term, adopted deliberately. It is not cosmetic:
adopting the name adopts a **taxonomy that already answers questions this design
will reach**, and it states a lineage rather than inventing one — the same posture
`handinput` took towards OpenXR, and `V2` towards the MEKF.

The same object is called a **socket / snap point** (Unreal), a **connector
primitive** (FabHacks, SCF '24), a **connection** (LEGO / BrickNet), and a
**mating feature** (the CAD assembly literature, where the graph of them is a
**liaison graph**). Every one of those systems arrived at the same abstraction
independently, which is the strongest evidence available that it is the right one.

## 3. ⛔⛔ THE SIGN CONVENTION — one place, stated once

A mate connector stores the surface's **TRUE OUTWARD NORMAL.**

Therefore **two connectors that mate are ANTI-PARALLEL**, because two surfaces
that touch face each other:

```
facing    :  dot(n_A, n_B) <= -cos(angle_tol)
outward   :  dot(p_B - p_A, n_A) >  0
```

⚠ **This is the opposite of the owner's original wording** (*"aligned … and not in
opposite direction"*), and the difference is a convention, not a disagreement: the
alternative is to store the **approach direction**, under which the test is
`dot >= +cos(tol)`. Outward-normal was chosen for two reasons:

1. it is the **surface's own property**, so it derives automatically from the mesh
   — which is exactly the default the owner asked for; and
2. an imported glTF/OBJ carries outward normals already, so an imported asset
   drops in with **no re-interpretation**.

⛔ **The `outward` line is not decoration.** A sphere-intersection test is
direction-blind: without it, two overlapping objects mate *through* each other.

⛔⛔ **`CONSTRAINTS.md` §7bis applies here in full: ONE place knows this sign.**
`V1` cost a session because the build took its mirror from one convention and its
depth from another. Do not let a second module learn the mate sign.

## 4. ⛔⛔ THE RESIDUAL RULE — why the owner's rules 2 and 3 conflict, and the fix

**As specified, the mate is unbreakable by construction.** Rule 2 says the child's
connector is coincident with the parent's *every frame*; rule 3 says the mate
breaks when they are pulled apart. If rule 2 holds, the separation is identically
zero forever and rule 3 can never fire.

⭐ **The fix is the one every physics engine already uses for breakable joints, and
it needs no physics.** PhysX: *"if the force or torque required to **maintain the
joint constraint** exceeds either threshold, the joint will break."* Unity compares
`breakForce` against the **reaction force**. Both test the violation the solver had
to absorb — **not** the observed gap, which is zero by construction.

**So the ordering is load-bearing, and it is the whole of this section:**

```
each frame, for each live mate:
  1. DESIRE    each object's pose from its OWN driver (its hand, or its parent)
  2. RESIDUAL  linear  = || p_A_desired - p_B_desired ||
               angular = departure from anti-parallel of the two desired normals
  3. BREAK ?   residual > break threshold  ->  drop the mate; both keep their desires
  4. ENFORCE   otherwise, move the CHILD onto the parent's connector and draw that
```

**Measure on the unconstrained targets. Apply the constraint after.**

### 4.1 ⭐⭐ A consequence that falls out for free: ONE HAND CAN NEVER BREAK A MATE

If only one object is driven, the other **follows** it and the residual is
identically zero. A residual can exist only when there are **two independent
drivers**. So *"the hands pull them apart"* is literally true — **plural** — and it
costs no rule, no threshold on hand state, and above all **no new gesture**, which
matters because `4.4`'s hand-open release trigger is not built.

⭐ It also lands exactly on **Guiard's kinematic chain model** (1987): in skilled
bimanual work the non-dominant hand holds the frame of reference and the dominant
hand acts within it. The parent/child asymmetry *is* that model, and separation is
the one moment both hands act.

### 4.1bis ⭐⭐ Built 2026-08-28: the free consequence was made STRUCTURAL

The golden vectors found that "one hand cannot break a mate" was **emergent, and
therefore breakable**. An undriven follower has no independent wish, so asking what
it *wanted* has no answer — and answering with its stored pose made a mate snap
when its parent was pushed into a play-volume **wall**.

⛔ **So the residual is only computed when BOTH objects are driven.** An undriven
object's driver *is* the mate, and it cannot disagree with itself. The claim is now
a property of the code rather than a likely outcome of it.

### 4.1ter ⛔ Built 2026-08-28: DESIRE and ACTUAL are both needed, for different readers

A second thing the vectors found, and it is not deducible from §4 alone:

| reader | pose it must use | why |
|---|---|---|
| **ENGAGE** | the **ACTUAL** (post-clamp) pose | a player aims at what is on screen |
| **BREAK** | the **DESIRE** | §4.2 — so a wall cannot break a joint |
| **ENFORCE** | the **ACTUAL** pose | ⛔ otherwise a parent stopped at a wall **visibly sheds its child**, which the first draft did |

⚠ Enforcing from the desire looks like the natural reading of §4 and is wrong.
The ordering is about *what breaks a mate*; where the objects are **drawn** must
follow where they actually are.

### 4.2 ⚠ The play-volume clamp is a second driver — and it is EXEMPT

An object pushed against a play-volume wall while its partner keeps moving
generates a residual, and would break the mate for a reason **no player can see**.

⛔ **Owner decision, 2026-08-28: the clamp does not contribute residual.** A wall
silently breaking a joint is the confident-but-wrong class this project keeps
paying for. Compute the residual from the **hand-driven** desire, before the clamp.

## 5. ⭐ WHAT A MATE REMOVES — and why the connector carries a roll reference

Position coincident + normals aligned removes **5 of 6 DOF**. The roll about the
contact axis stays free. Onshape names this exactly: **Revolute** *"removes all
degrees of freedom except for rotation along the Z axis defined by the selected
Mate Connectors"*; **Fastened** removes all 6.

⚠ **So the owner's rule as first written would leave two assembled objects free to
spin against each other** — which is not what *"align them for assembly"* means.

⭐ **Decision (owner, 2026-08-28): close it on the connector, option (a).** The
connector carries a **`tangent`** (the roll reference) and a **`roll_order`** (the
symmetry order: `1` = one way only, `4` = a square face, `0` = free spin, a round
peg). At snap the child rolls to the **nearest of the `roll_order` valid rolls**.
The mate is then **Fastened**.

⛔ The rejected alternative, recorded because it is the one LEGO uses and it will
come back: **require two simultaneous mates** between the same pair — two coincident
points determine the roll, which is where a 2-stud brick contact gets its rigidity.
It needs no new field, but it must be *hit by hand*, and §8's jitter floor makes
hitting two at once far harder than hitting one.

⭐ **The growth path this buys**: once the mate **type** is a property of the pair,
`Revolute` (hinges), `Slider` and `Ball` are already named and already understood.

## 6. THE OBJECT TREE — parent, root, and the three edge cases

What the owner described is a **kinematic tree** with an articulation root.

### 6.1 ⭐⭐ Parent and ROOT are two different things — conflating them is the bug

| | | |
|---|---|---|
| **parent** | who **stores** the relative transform | the **bigger** object, per the owner's rule. Static |
| **root** | who is currently being **driven** | **whoever is held. Re-rooted every frame** |

⛔ Without the second row, grabbing the **child** cannot move anything: the child is
by definition controlled by its parent. The structural hierarchy is *storage*; the
drive direction is *dynamic*, and the tree is walked outward from the grabbed node.
This is standard floating-base / articulation-root practice; it is not an invention.

### 6.2 Ties

Equal-sized objects need a **deterministic** tie-break (lowest object id), or the
parent flips between frames and the whole hierarchy chatters. Today's two cubes
differ 2:1, so this cannot bite yet — it is written down so it does not have to be
rediscovered.

### 6.3 ⛔ Cycles are REFUSED

A third mate that closes a loop makes the graph not a tree. CAD calls this
**closed-loop / over-constrained**, and the standard treatment is to cut a joint to
reopen the chain — a solver's job.

⛔ **Owner decision, 2026-08-28: v1 REFUSES a mate that would close a cycle**, and
shows that it refused. Correct, cheap, and no solver. Revisit only when an asset
genuinely needs a loop.

## 7. THE SNAP EVENT — who moves, and the trap underneath

§4 governs the steady state. The **instant** of snap is a separate question, and
the owner's parent/child rule does not answer it.

⭐ **The HELD object moves to the mate**, whichever object becomes the child. Unreal
moves the *source* actor — the one being dragged — for the same reason: the person
is aiming the thing in their hand, and moving the *other* one is a surprise.

⛔⛔ **THE TRAP: rewrite the grab baseline at snap, or the hand and the mate fight.**
The held object's pose is anchored to the hand by `grab_grip_offset` and
`grab_hand_depth_m`/`grab_depth_offset_m`. Moving it to the mate without re-seating
those means two authorities driving one transform with different ideas of where it
belongs — **which is exactly the class of defect `R1` fixed** by anchoring
`grab_hand_depth_m` on the grip point. Re-seat at snap; the grab frame stays
continuous, as it does everywhere else in this project.

## 8. THE CONSTANTS — every one a bracket, and where each end comes from

⛔ Per [`../00_CORE/METHOD.md`](../00_CORE/METHOD.md), none of these is guessed.
Where a bound is not measurable today it is **stated as unknown and settled live**,
the way `V2`'s 0.66 and `L1`'s τ were.

Object scale, for reference: `focal_px(640) = 554.26`, so at
`REFERENCE_DEPTH_M = 0.50` the **small** cube is **36.1 mm** on edge and the
**large** is **72.2 mm** (which is `R1`'s independently-quoted "a cube is 7.2 cm
deep" — the two agree).

| constant | value | the bracket |
|---|---|---|
| `MATE_ANGLE_TOL_DEG` | **30.0** | ⭐ **Floor: 25.41°**, `F1`'s shipped per-frame orientation-jump p95 — below it the mate is refused by the pipeline's own noise during an otherwise steady approach. ⛔ **Ceiling: 45°**, where a cube's *adjacent* face becomes an equally good candidate (faces are 90° apart). 30° sits just above the floor, as 0.66 sits just under `V2`'s |
| `MATE_RADIUS_FRACTION` | **1.0** of the object's own half-extent (was 0.5; doubled by the owner 2026-08-28) | gives 9.0 mm (small) + 18.0 mm (large) = **27.1 mm** of capture gap, ≈ 0.75 × the small cube's edge. ⛔ **Ceiling: the small object's own edge** — beyond it two objects mate while *visibly apart*. ⚠ **The floor is NOT known**: no measurement exists of how precisely a hand places an object here. **Settle it live.** ⭐ Expressed as a fraction so it derives from the object with no per-object configuration — the same principle as `U9`'s clamp |
| `MATE_BREAK_FACTOR` | **1.5** × the engage radius | ⛔ **Floor: strictly > 1.0**, or engage and release share a threshold and the mate chatters at 25° of jitter. This is the Schmitt trigger, and Creo's second threshold angle. At 1.5 the pair separates after ≈ 40.6 mm ≈ **one small-cube edge** of pull — legible to a player |
| `MATE_DWELL_MS` | **100.0** | above the measured inter-frame gap (`L1`: **48–64 ms**, and it moves with room lighting), so **no single-frame excursion can toggle a mate**. A duration, not a frame count — `U8`'s reason: a frame count feels twice as long in dim light |
| `roll_order` (cube face) | **4** | a square face has four indistinguishable rolls |
| `REGRAB_RELEASE_FACTOR` | **1.5** | ⛔ **Floor: strictly > 1.0**, or the grab and re-arm thresholds coincide and the latch does nothing. At 1.5 the hand must get about **30 px** from the small cube at the reference depth — three quarters of its own width, and far outside `F1`'s 1.5 mm fingertip noise floor. ⚠ The same 1.5 as `MATE_BREAK_FACTOR` and deliberately a **separate constant**: they answer different questions and need not move together |
| `PREVIEW_RADIUS_FACTOR` | **2.0** (was 3.0; the owner set it to exactly twice the snap radius) | ⛔ **Floor: strictly > 1.0**, or the preview appears only once the mate is already available and guides nothing. At 3× the capture reach that is ~54 mm of approach — about one and a half small-cube widths. ⚠ Settle live alongside the capture radius; they are the same kind of number |
| `PREVIEW_ANGLE_DEG` | **75.0** | ⛔ **Ceiling: strictly < 90°.** At 90° two outward normals are perpendicular, and past it they point the same way — the objects are back to back, not facing, and a ghost there is noise |
| `REGRAB_DWELL_MS` | **100.0** | ⭐ two independent supports: `L1`'s measured 48–64 ms frame gap (so a single frame cannot trip it), and the VR grasp literature reporting a pinch state that bounced until it was required to hold for **100 ms**, which *"resulted in a much smoother user experience"* |

## 8bis. ⛔⛔ ONE SCENE CAMERA — objects are projected together, never separately

Every object's mesh is projected through **the scene's own pinhole**, at the
object's real depth — `object_assembly.project_vertices_px`, the same projection
the mate is solved in.

⛔ **Never give an object its own camera.** Each used to be drawn through a virtual
camera at `3 x its own projected size`, centred on itself, while its CENTRE was
placed by the linear pinhole. **Two inconsistent projections for one scene**: each
object's faces were pulled inward by `s = 6/7`, so two objects whose faces COINCIDE
in world space were drawn up to **18.4 px apart on an 80 px cube — 23% of its
width, and present even at 0° rotation.**

⭐ The scene camera is also more physical: the local camera applied a near/far ratio
of **1.400** where the real camera at 0.50 m gives **1.156**, so it exaggerated
foreshortening by 1.2x.

⚠ **It binds four things that must all share it** — the faces, the silhouette used
for occlusion, the connector markers, and the ghost. A marker projected through a
different camera drifts off the face it marks.

⭐ `CUBE_PERSPECTIVE_DISTANCE_RATIO`'s original purpose is preserved: it existed to
avoid a 2026-08-01 morphing bug where a naive per-vertex scale could drive the
denominator negative. A real pinhole at the object's own depth cannot, because
`depth − half_extent` is 0.464 m at the near wall.

⭐⭐ **Consequence for `U2`**: an imported mesh assembled from several parts would
have shown the same seam. This had to be fixed before real assets, not after.

## 9. HISTORY — how every rule here was arrived at

⭐ The **narrative** of the build — each live defect, its measurement, and the
fixes that caused the next one — is
[`history/ASSEMBLY_BUILD_LOG.md`](history/ASSEMBLY_BUILD_LOG.md). It is lifted
verbatim from this file, which hit its 800-line cap on the day it was written.

⛔ **Read it before re-opening any decision below.** In one day the row produced:
release-at-mate and its Midas-touch latch; an un-snap that lasted one frame; a
0.180 m hand-back teleport; a driver that RATCHETED to the play-volume wall; a
clamp that silently overrode a solved mate by 87 px; and a renderer that drew
coincident faces 18.4 px apart. ⚠ **Three of those were caused by the fix for the
one before it**, and three golden vectors passed for the wrong reason.

## 10. Lineage — the prior art this is built on, and why that is recorded

Same posture as `handinput`'s OpenXR framing and `V2`'s MEKF: reach for named,
long-published prior art and **record the lineage**, rather than build something a
holding entity can point a patent at (`N13`, and the `DECISIONS.md` entry of
2026-08-26).

| what | where it comes from |
|---|---|
| a connector as a **local coordinate system** on a face; mating = making two coincident; the mate **type** decides surviving DOF | **Onshape** mate connectors and the Fastened / Revolute / Slider / Cylindrical / Planar / Ball taxonomy |
| **proximity snapping** — the constraint activates when two features come into proximity and the parts snap to final pose | **PTC Creo**, automatic constraint recognition; the survey literature on constraint- and DOF-based virtual assembly |
| **source/target socket** semantics, and a **rotation-snap increment** to express symmetry | **Unreal** Modular Snap System |
| **connector primitives** that abstract away the real geometry | **FabHacks**, ACM SCF 2024 |
| connections **typed by the DOF they leave** (stud 1 · hinge 1 · ball 3 · fixed 0), and the assembly as a **graph** | **LEGO / BrickNet**, CVPR 2026; the CAD **liaison graph** literature |
| **break on the constraint reaction**, not on the observed gap | **PhysX** / **Unity** breakable joints (`breakForce` / `breakTorque`) |
| snapping that becomes a **persistent** relationship | **Bier & Stone, Snap-Dragging**, SIGGRAPH 1986; *Beyond Snapping*, UIST 2016 |
| the **asymmetric two-handed** division of labour separation relies on | **Guiard 1987**, the kinematic chain model |
| **articulation root / floating base**, and re-rooting the drive | standard multibody practice (Featherstone-lineage kinematic trees) |
| **closed-loop / over-constrained** assemblies, and cutting a joint to reopen the chain | the 3D geometric-constraint-solving literature |

## 11. WHERE IT LIVES — and why it is not blocked on the platform decision

⭐ `U2` (real 3D-file import) is postponed on the **platform decision** because a
file *importer* is written against a renderer. **This is not `U2`.** The mate
geometry is pure state and pure maths: **no renderer, stdlib-only, numpy-free**, so
it ports by transliteration like the rest of the estimator layer
([`../00_CORE/CONSTRAINTS.md`](../00_CORE/CONSTRAINTS.md) §2).

That is the same argument that let `F1` proceed — perception-only, touches no
renderer, accrues no throwaway work.

⭐ **Precedent, and the module to copy**: `Resources/object_extent.py` is geometry
that **both** renderers need, kept stdlib-only in its own module precisely because
neither renderer can host what the other needs, with its own golden vectors and
imported by both. `Resources/mate_connector.py` is that shape exactly.

⚠ **What IS renderer-shaped**: drawing the connectors and the candidate highlight
(`AS5`). Keep it thin and per-tool; it is cheap to throw away.

⚠ **The `IS4` overlap, stated so it is not a surprise**: `IS4` (the interaction
tier, the port's prerequisite) owns *grab-what, arbitration and ownership* — and
assembly changes **what a grab owns**. Whether assembly rides with `IS4` or
precedes it is still open.

## 11bis. ✅✅ WHAT WAS BUILT, 2026-08-28 — and the live look that CLOSED it

| | |
|---|---|
| `Resources/mate_connector.py` | `AS1`–`AS4`'s maths. Stdlib-only, numpy-free, **clock-free** (`now_ms` is passed in, like `hand_state`) |
| `Resources/object_assembly.py` | the seam: pixels ↔ metres, and `step()` — **the one entry point both tools call** |
| `analysis/verify_mate_connector.py` | 40 checks — the sign, the roll, the residual trap, the quaternion at a half turn |
| `analysis/verify_object_assembly.py` | the wiring: mate, re-root, one-hand-cannot-break, two-hands-can, the wall, depth |
| both tools | one connector each on the cubes' **`+X` face** — the large cube's **YELLOW** face against the small cube's **GREEN** one — plus `AS5`'s drawing |

**Evidence**: 42/42 suites pass · `parity_replay` **NO DIVERGENCE on 4 takes**
(`stripped`, `frob`, `steadytrans`, `freeze`).

✅✅ **THE LIVE LOOK IN BOTH TOOLS IS DONE (2026-08-28), AND IT IS WHAT CLOSED THE
ROW.** `METHOD` is explicit that automated green is necessary and not sufficient —
§13.6.1 shipped **inverted** while passing an "end-to-end confirmed" claim. The debug
tool had settled the sliders and the behaviour; ⛔ production had **never been run at
all**, so every judgement stood on one renderer and `parity_replay` covers the LOGIC,
not the DRAWING. The owner ran production: *"production run was done by me and it is
ok"*. `AS1`–`AS9` are **SHIPPED**.

✅ **The capture radius and the angle were settled live at `snap 150 %`** — reach
**108.3 mm = 1.50 × an object's edge**, angle **45° = the 90° aperture** — the way
`V2`'s 0.66 and `L1`'s τ were. ⚠ **The PREVIEW radius was not**, and it is now the
only constant in this spec with no measured floor.

⚠ **Two limits, both known and neither a bug**: a *child* pinned at a play-volume
wall can drift off its parent visually (the parent is exempt, the child is clamped
after placement); and with **two hands on one assembly** the structural parent wins
the tie — which is not a deadlock, because that is exactly the case whose residual
grows until the mate breaks.

## 12. Acceptance

⚠ `A10` is a rule about **estimators** measured by replay A/B; assembly is a
feature, so the letter does not apply — but the discipline does.

1. **Golden vectors before anything is wired** (`CONSTRAINTS` §3):
   `analysis/verify_mate_connector.py`. `AS1`–`AS3` close on these alone.
2. ⭐ **The anti-chatter metric**: `snap/break transitions per minute` on a recorded
   take. Measurable offline once connectors exist, and it is the number that says
   whether §8's hysteresis is sized right.
3. `analysis/parity_replay.py` clean, because both tools change (`U6`).
4. ⛔ **A live look in BOTH tools closes it, and nothing else does** (`METHOD`).
   Automated green is necessary, not sufficient — §13.6.1 shipped inverted while
   passing an "end-to-end confirmed" claim.


---

## 13. ⭐⭐⭐ WHAT IS LEFT TO BUILD — read this first in a new session

✅✅ **`AS1`–`AS9` ARE SHIPPED (2026-08-28).** The owner ran production — *"production
run was done by me and it is ok"* — and that, not the 44/44 suites or the clean
`parity_replay`, is what closed the row: `METHOD` calls automated green necessary and
not sufficient.

### ✅ Was blocking — all three cleared by the one production run

| | |
|---|---|
| ~~**The live verdict on `AS1`–`AS9`**~~ | ✅ **given 2026-08-28**, in both tools |
| ~~**`V2`'s production live look**~~ | ✅ **DONE** — owed from before this work began; the same run covered it, owner-confirmed on asking. ⚠ An acceptance is not a re-measurement: `V2`'s gate is still cleared on 3 of 4 takes |
| ~~**Production has never been run at all**~~ | ✅ **it has now.** ⚠ The reason it mattered stands for next time: `parity_replay` proves the LOGIC matches, it does not cover DRAWING, and **renderer parity remains unguarded** — a future renderer change needs the same two-tool look |
| ✅ **A one-handed detach — DECIDED AND DECLINED** | owner, 2026-08-28: *"unsnapping needs two hands"*. `AS3`'s consequence is now the RULE: one hand can never break a mate, and a mated pair is permanent to a single hand. ⛔ The **tug** (which I had recommended) and **unheld-means-anchored** are declined, not deferred. ⚠ Live with: an assembly cannot be taken apart while only one hand is tracked |

### ⚠ Numbers with no measured floor — two settled, ONE still open

`MATE_RADIUS_FRACTION`, `PREVIEW_RADIUS_FACTOR` and the angle tolerance all have
live sliders (`MATE snap r %`, `MATE preview r %`, 33 %..300 %, the angle riding
the snap one). ✅ **SETTLED LIVE 2026-08-28 at `snap 150 %`** (owner): capture reach **108.3 mm =
1.50 × an object's edge**, angle **45° = the 90° aperture** asked for. ⚠⚠ Both sit
PAST or ON their stated boundaries, deliberately — objects can mate while visibly
apart, and 45° is exactly where an adjacent cube face also qualifies (it degrades
rather than breaks: `mate_score` still picks the better candidate).
⛔ `HOME_SEPARATION_M` had to be re-derived a THIRD time, 260 → **340 mm**, or the
scene would have opened with a ghost already showing. ⚠ The margin is now thin —
at 640 px the objects sit at 132/508 against a play area of 87..553, so a wider
snap radius would start pushing them off the usable area on a low-resolution
camera. **The preview radius is still unsettled.**

⚠⚠ **`AS2`'s own acceptance metric has never been measured, and SHIPPING DID NOT
CLOSE IT**: `snap/break transitions per minute` on a recorded take. **No recording of
an assembly session exists** — the newest take on `E:` is
`2026-08-28_000559_stripped`, which predates this work, and the production run that
shipped the row was not recorded.

⛔⛔ **AND RECORDING ONE TODAY WOULD NOT BE ENOUGH — NEITHER RECORDER CARRIES MATE
STATE.** `HandsTriggeredActions._record_flush` writes, per cube, `owner / position /
size / depth_m / projected_size / orientation`, and the debug recorder matches it;
nothing says whether a pair is **mated**, which pair, or which connectors. So the
metric could only be produced by RE-DERIVING the mate state from positions — a second
implementation of `can_mate` that can silently disagree with the one that ran.
⭐⭐ That is the exact trap `_record_flush`'s own docstring exists to warn about
(*"record what ran; never re-derive it"*), and the trap `METHOD` records as the
project's most expensive lesson: a recomputation once reported a production session
CLEAN on a defect the owner had just watched happen.

⭐ **So the metric's prerequisite is a recorder change, not a recording session**:
add the mate state both tools already know to the frame row, guarded by
`verify_recorder_parity` (the two recorders have diverged before — production once
sampled cubes a frame earlier and skewed every harness that paired hands with cubes).
⚠ It bumps the recorder schema; takes written before it lack the field, exactly as
`4.2`'s `depth_m` did.

### ⛔ Not built at all

1. **More than two objects.** The tree is written for N, but nothing has exercised
   it: `order_by_size`'s tie-break, cycle refusal, and the home row's outer slots
   (which need the play-area clamp — `verify_home_cube` shows a third cube landing
   outside at 1280). ⚠ Broad phase is `O((objects x connectors)^2)`; a spatial
   index earns its weight past ~50 objects, not before.
2. **Gendered connectors.** The `kind` field exists and is unused; v1 is
   deliberately genderless. It becomes real when imported assets have connector
   types.
3. **Roll symmetry has never been live-judged.** `roll_order = 4` snaps to the
   nearest of four rolls; that it *feels* right is unverified.
4. **What an assembly MEANS to the game** — targets, scoring, "is this the right
   assembly" — is `20_GAME_RULES` territory and does not exist. Assembly is
   currently a manipulation capability with no objective attached.
5. **`U2`, real 3D-file import**, still postponed on the PLATFORM DECISION. An
   imported mesh brings its own connectors, which is why §1's face-centroid default
   was built to derive from the mesh rather than be configured.

### ⚠ Known limits that are behaviour, not bugs

* **A mated pair shares one depth.** Move either and both go — that is what an
  assembly is, and it is why "I can't control their z separately" is correct.
* **A child pinned at a play-volume wall can drift off its parent visually**: the
  parent is exempt from the clamp's residual, the child is clamped after placement.
* **Two hands on one assembly**: the structural parent wins the tie. Not a
  deadlock — that is exactly the case whose residual grows until the mate breaks.
