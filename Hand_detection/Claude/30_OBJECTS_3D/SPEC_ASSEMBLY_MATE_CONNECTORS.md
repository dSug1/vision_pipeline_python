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

## 7bis. ⭐⭐ AS6 — RELEASE AT MATE, AND RE-ARM ON EXIT (live finding, 2026-08-28)

> **Owner, from the first live run:** *"the smaller object must ungrab at snap
> otherwise the snap breaks immediately."*

⛔ **Why it broke.** With a cube in each hand **both are driven**, so the residual
is real — and the hand that just placed the child keeps moving, because nobody
stops dead at the instant of contact. Within a few frames the residual passes the
break threshold and the mate lets go.

⭐ **The owner's fix is the STRONGER of the two the spec had on the table.** §7's
was to re-seat the grab baseline — but that leaves **two authorities on one
transform** and merely agrees them for an instant. Releasing the child's grab
removes one of them, and §4.1's rule then makes the mate unbreakable by the other.

### ⛔⛔ And it creates a second problem, which has a name: the MIDAS TOUCH

The hand is still exactly where the object is, so the next frame's proximity snap
takes it straight back — **mate, release, re-grab, break, repeat.**

⭐⭐ **Buxton's three-state model (1990) states the constraint exactly: you cannot
go from State 2 (dragging) to State 2. The transition must pass through State 1
(tracking).** So there has to be a state in which the hand is over the object and
not holding it, and the system must be able to reach it.

### The mechanism: positional, not a timer and not a gesture

After an automatic release, the hand that placed the object must **leave** it —
past `REGRAB_RELEASE_FACTOR ×` the grab radius, sustained for a dwell — before it
may take it again.

| why this one | |
|---|---|
| it is what the **Midas-touch** literature settles on | *"leave the zone before it can re-trigger"* |
| it is the **VR grasp** literature's asymmetric threshold | grab at ≥ 0.75, release at ≤ 0.25, precisely so the state cannot bounce |
| ⭐⭐ it is the shape **this project already paid for twice** | `U9`'s two hand-side TRIGGERS were built and reverted before a POSITIONAL rule shipped. `METHOD`: *"a trigger cannot enforce an invariant"* |
| it is **self-clearing** | a player who simply stands still keeps their assembly — a cooldown timer would silently undo it |
| it needs **no new gesture** | `4.4`'s hand-open release is still unbuilt, and stays unbuilt |

⭐ **The latch is per (object, HAND), not per object** — so the *other* hand may
take the child immediately, which is exactly what a two-handed detach needs. Only
the hand that just let go has to step away.

⚠ **Consequence, and check it feels right live**: to pull a mated pair apart you
hold the assembly with one hand and pull the child with the other. One hand alone
moves the whole assembly instead (§6.1's re-rooting). That is physically what
taking a brick off a model requires, but it is a choice, not a law.

## 7ter. ⭐⭐ AS7 — THE MATE PREVIEW: a ghost and a drop line (live finding, 2026-08-28)

> **Owner, after the second live run:** *"it is very difficult to judge the
> relative positions of the objects on z axis and therefore to align them for
> snap … draw the small object projected to the mate in translucent highlighted.
> that will also help select which mate to choose."*

### ⛔ Why depth is unreadable here, and it is not a drawing bug

The play volume is 0.30–0.85 m — **personal space**, where **Cutting & Vishton**
rank **occlusion** the strongest depth cue by a wide margin, and where their data
show its presence drives motion parallax's weight to near zero. `R1` already ships
occlusion.

⛔ **But occlusion is SILENT until the two shapes overlap on screen**, which in a
face-to-face approach is not until they are nearly touching. **The strongest cue
available is absent for exactly the phase that needs it.** What is left is relative
size, which is confounded because the two cubes really are different sizes. There
is no stereo. **So the depth information has to be drawn.**

### ⭐⭐ The canonical answer is a shadow / drop line, from a manipulation paper

**Herndon et al., "Interactive Shadows" (UIST 1992)** introduced shadow widgets so
that a user could position objects in 3D **with a 2D input device** — which is this
situation precisely: a hand whose z is *estimated*, driving an object in a 3D
scene. The gap between an object and its projection reads as depth where the object
alone does not.

⭐ **The ghost is the other half**, from a different tradition — the translucent
**placement preview** universal in building games and CAD placement tools.

⭐⭐ **The owner's two proposals are not alternatives; they answer different
questions, which is why both were built:**

| | |
|---|---|
| **the GHOST** | *where would it land, and turned which way?* |
| **the DROP LINE** | *how far is there still to go?* — **the half that z hides** |

### ⚠⚠ The preview must appear BEFORE the mate is possible

A preview that only shows once you have already succeeded is a report, not an aid.
So it has its own, wider gates: `PREVIEW_RADIUS_FACTOR × ` the capture reach, and
`PREVIEW_ANGLE_DEG`.

⭐ **And its colour carries the one thing the player cannot otherwise tell — WHICH
condition is failing.** Amber while out of reach; **green the instant only the
dwell is left**, which says *hold still* rather than *keep pushing*.

### ⭐⭐ Choosing between several mates — the bubble cursor

`mate_score` normalises each clause by its own threshold and takes the worse, so
**`score ≤ 1` is true exactly when `can_mate` is** — a strict generalisation, not a
second opinion (`METHOD`: a recomputation is a second implementation that can
silently disagree). The best-scoring candidate is the only one drawn.

That is **Grossman & Balakrishnan's bubble cursor** (CHI 2005): dynamically ensure
exactly one target is selectable, and make *which* one visible.

⛔ **The ghost pose comes from `snap_pose` — the same function that would actually
place the object.** A lookalike would teach the player something the mate then
contradicts.

## 7quater. ⛔⛔ ONE CONNECTOR PER OBJECT WAS UNREACHABLE — found live, 2026-08-28

> **Owner, third live run:** *"can't see any ghost nor dashed line."*

**Every offline check passed and the feature was invisible.** The first build put
**one** connector on each cube, both on the `+X` face — and both cubes start
unrotated, so the two outward normals point the **same** way. Facing deviation
**180°**: the worst value there is. Nothing could mate, and nothing could even be
**previewed**, until one cube was turned a full half-turn — which is the hardest
thing to ask of a hand carrying a 27° yaw lean and 25° of jitter.

⭐⭐ **THE METHOD RULE, and it is a new one: A FIXTURE THAT CONSTRUCTS THE
CONFIGURATION IT TESTS CANNOT DISCOVER THAT THE PRODUCT NEVER REACHES IT.** Every
vector in `verify_object_assembly.py` built its scene by *placing the small cube at
`MATED_SMALL_X` with `FLIP_Y` applied* — i.e. each one rotated a cube into position
before asserting anything. The assertions were all true. The **starting state** was
never in the suite, and the starting state was the whole defect. It is `T6`'s
lesson in a new place: *a corpus whose motion does not match the product's cannot
validate the product* — here, a fixture whose **pose** does not match the product's.

⚠ It also made the owner's own requirement untestable: *"that will also help select
which mate to choose if the small object can be mated to more than 1 mates"* — with
one connector each there is exactly ONE possible pair, so there was never a choice
to make.

⭐⭐ **The default is now ALL SIX FACES**, and it pays three ways:

1. **any face mates any face**, so an approach from any direction works;
2. **several candidates exist**, so §7ter's bubble-cursor choice is real rather
   than theoretical;
3. ⭐ **six outward normals drawn on a cube ARE an orientation gizmo** — which is
   the first thing the owner asked for (*"a gizmo to display a projection of the
   normal"*), obtained for free.

⚠ Cost is nil at this scale: 6 × 6 = **36 pair tests a frame** for two objects. A
spatial index earns its weight past ~50 objects, not here.

⛔ The regression is pinned in `verify_object_assembly.py`: the default set must
cover all six axes, **two UNROTATED cubes side by side must be able to mate**, and
more than one pair must be available.

## 7quinquies. ⛔⛔ OBJECTS MUST NOT START ON TOP OF EACH OTHER — live, 2026-08-28

> **Owner, fourth live run:** *"the z axis movement seems broken: I can't get the
> cube to move on the z axis."*

⭐⭐ **AND Z WAS NOT BROKEN.** Both cubes started at the **window centre** —
interpenetrating, at the same depth. That was invisible while each carried a single
`+X` connector, because two unrotated cubes could not mate at all. The moment §7quater
went to six faces, an ordinary drag walked a connector pair into capture: **measured
from the real startup pose, a 72 px drag mated on frame 12**, `AS6` correctly took the
cube out of the hand, and it stopped dead. **In every axis.** z was simply the one
being tested.

⚠ **The report named the symptom, not the mechanism — and the symptom pointed at a
subsystem that was innocent.** `4.2`'s Z-translation was untouched; verified by
simulation, depth tracks freely at every stage of an approach (0.500 → 0.580 m while
the ghost is showing).

⭐ **The separation is DERIVED, not chosen**: two objects must start further apart
than the **preview** reach, or the scene opens already showing a ghost and the aid
means nothing. Connector gap at centre distance `D` is `D − 36.1 − 18.0` mm; the
preview reaches `3 × 27.1 = 81.2` mm; so `D > 135` mm. `HOME_SEPARATION_M = 0.160`
leaves margin — a measured **105.9 mm** gap against an **81.2 mm** preview.
⚠ In **metres**, so it means the same on any camera resolution — `U9`'s reason.

⛔ It binds three call sites in each tool: the initial layout, `resize()`, and the
debug tool's SPACE-to-home (which also **breaks any mate first** — a homed child
would otherwise be dragged straight back by its parent on the next frame).

⚠⚠ **`verify_home_cube.py` FAILED on this change, and was UPDATED rather than
silenced.** It asserted *"home is the frame centre"*, which is precisely the
behaviour that was wrong. The property under test is unchanged — homing sends an
object to a **deterministic, known** place — and that place is now its own slot.
⛔ `V1` recorded the opposite mistake as a method rule: a harness reporting a real
defect explained away with a guard. This is the other case, and the vector says so
in place.

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

## 8bis. ⚠⚠ THE CONSTANTS MOVED THREE TIMES ON 2026-08-28 — the current set

| constant | value | note |
|---|---|---|
| `MATE_RADIUS_FRACTION` | **1.0** | capture reach **72.2 mm** for the equal cubes |
| `PREVIEW_RADIUS_FACTOR` | **2.0** | preview reach **144.3 mm** — the owner's *"twice the radius for snap"* |
| `HOME_SEPARATION_M` | **0.260** | gap **187.8 mm**, re-derived twice as the others moved |
| object edge | **72.2 mm** | both cubes, equal since 2026-08-28 |

⛔⛔ **THE CAPTURE REACH NOW EQUALS AN OBJECT'S OWN EDGE, which is the stated
ceiling** (§8): beyond it two objects mate while *visibly apart*. The owner set it
there deliberately. A mate can therefore pull an object a full cube-width, and may
read as a teleport. The golden vector's comparison moved from `<` to `<=` and says
so in place — any further increase crosses a boundary chosen on purpose.

⭐ **`HOME_SEPARATION_M` is a DERIVED value and it has already gone stale twice in
one day** — once when the cubes were equalised (the smaller one grew), once when
the capture radius doubled. Both times it would have failed *silently*, opening
the scene with a ghost already showing. `verify_home_cube.py` now checks it against
the SHIPPED object sizes at 640, 1280 and 1920 — and the narrow camera is the hard
case, because `size` is in pixels so an 80 px cube is 72 mm at 640 and 36 mm at 1280.

## 8ter. ⛔⛔ AN UN-SNAP MUST SURVIVE MORE THAN ONE FRAME (`AS8`)

> **Owner, fourth report:** *"once a cube has been un-snapped, I cannot move it on
> z axis. it's a bug I repeatedly asked you to correct."*

**Breaking a mate lasted exactly one frame.** §4 measures the two **desires**
diverging; it never requires the objects to **move apart**. So the instant the mate
dropped the cubes were still touching, `can_mate` was true again, and the dwell
re-engaged it. The object returned to `role=follower` — **and a follower's depth is
owned by its parent**, which is z looking dead from the outside.

⛔ **It was never a depth defect.** `4.2`'s Z-translation was correct throughout;
what was broken was that a mate could not be undone.

⭐ **The fix is the same principle as `AS6`, one level up:** after a break, that
connector pair may not re-engage until the two objects are **genuinely apart** —
past the BREAK distance, for the dwell. **You cannot go from mated to mated; the
transition must pass through APART.** Homing passes `cooldown=False`, because it
moves the objects apart itself.

⭐⭐⭐ **THE METHOD LESSON, AND IT COST FOUR REPORTS: every probe broke the mate and
then measured something else. None of them broke it and simply LOOKED at whether
it was still broken.** The defect was visible in one line of the `z` HUD —
`mated=True` immediately after a call to `unlink()`. ⚠ Three of those probes were
also invalid for a second reason each (driving `depth_m` directly instead of
through the ratio; never reaching the mated state at all), and each was reported as
a pass before the flaw was noticed.

## 9. Lineage — the prior art this is built on, and why that is recorded

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

## 10. WHERE IT LIVES — and why it is not blocked on the platform decision

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

## 10bis. ✅ WHAT WAS BUILT, 2026-08-28 — and the live look that is owed

| | |
|---|---|
| `Resources/mate_connector.py` | `AS1`–`AS4`'s maths. Stdlib-only, numpy-free, **clock-free** (`now_ms` is passed in, like `hand_state`) |
| `Resources/object_assembly.py` | the seam: pixels ↔ metres, and `step()` — **the one entry point both tools call** |
| `analysis/verify_mate_connector.py` | 40 checks — the sign, the roll, the residual trap, the quaternion at a half turn |
| `analysis/verify_object_assembly.py` | the wiring: mate, re-root, one-hand-cannot-break, two-hands-can, the wall, depth |
| both tools | one connector each on the cubes' **`+X` face** — the large cube's **YELLOW** face against the small cube's **GREEN** one — plus `AS5`'s drawing |

**Evidence**: 42/42 suites pass · `parity_replay` **NO DIVERGENCE on 4 takes**
(`stripped`, `frob`, `steadytrans`, `freeze`).

⛔⛔ **THE LIVE LOOK IN BOTH TOOLS IS OWED, and nothing above closes it.** `METHOD`
is explicit: automated green is necessary, not sufficient — §13.6.1 shipped
**inverted** while passing an "end-to-end confirmed" claim.

⚠ **The capture radius has no measured floor** (§8) and is the first thing to
settle live, the way `V2`'s 0.66 and `L1`'s τ were.

⚠ **Two limits, both known and neither a bug**: a *child* pinned at a play-volume
wall can drift off its parent visually (the parent is exempt, the child is clamped
after placement); and with **two hands on one assembly** the structural parent wins
the tie — which is not a deadlock, because that is exactly the case whose residual
grows until the mate breaks.

## 11. Acceptance

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
