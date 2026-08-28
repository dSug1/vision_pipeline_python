# ASSEMBLY — the build log, 2026-08-28

> **STATUS** · history · **OWNS** · how the assembly design got to where it is
> **READ IF** · you are about to re-open a decision, or a defect looks familiar
> **LAST VERIFIED** · 2026-08-28
> **SOURCED FROM** · sections lifted verbatim out of
> [`../SPEC_ASSEMBLY_MATE_CONNECTORS.md`](../SPEC_ASSEMBLY_MATE_CONNECTORS.md) when
> that file reached its 800-line cap. ⛔ Nothing was rewritten or summarised.

⚠ **This is NARRATIVE. The design of record is the spec.** Per the tiering rule:
state lives in the spec and `INDEX.md`; the story of how it was reached lives here.

⭐ Read it for the DEFECTS: every one of them was found live, several were caused
by the fix for the previous one, and three golden vectors passed for the wrong
reason along the way.

---

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

---

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

---

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

---

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

---

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

---

## 8quater. ⭐ THE TWO RADII ARE LIVE — sliders, 33 %..300 % (2026-08-28)

The debug tool carries **`MATE snap r %`** and **`MATE preview r %`**, each a
percentage of the SHIPPED value, so 100 % is exactly what ships and the owner's
third-to-triple range is 33 %..300 %.

⭐⭐ **`MATE snap r %` drives the ANGLE TOLERANCE too** (owner: *"the mate snap %
shall also control the tolerance for normal alignment"*). `can_mate` asks how
CLOSE and how ALIGNED; they are one question, and moving only the distance made
*"tighter snap"* mean half of what it says.

| snap % | capture reach | angle tolerance |
|---|---|---|
| 33 | 23.8 mm | 9.9° |
| **100** | **72.2 mm** | **30.0°** |
| 150 | 108.3 mm | 45.0° |
| 300 | 216.5 mm | **89.0°** (clamped) |

⚠⚠ **It crosses BOTH of §8's angle brackets on purpose** — exploring them is what a
slider is for — but the two ends mean different things:
* **below ~85 %** the tolerance drops under **25.41°**, `F1`'s measured p95
  orientation jump: the pipeline's OWN noise begins refusing mates during a steady
  approach, so it feels *unreachable* rather than tight;
* **above ~150 %** it passes **45°**, where an adjacent cube face also qualifies.
  ⭐ That DEGRADES rather than breaks — `mate_score` still picks the best
  candidate, so the wrong face is not chosen; there are simply two in the running.

⛔⛔ **A HARD GEOMETRIC LIMIT the slider may reach and the predicate may not: 89°.**
At 90° two outward normals are perpendicular; past it they point the SAME way and
*"facing each other within tolerance"* stops meaning anything.

⛔ **The PREVIEW angle widens to follow the mate's**, never falling below it —
otherwise the ghost vanishes exactly as the mate becomes possible, which is an aid
that stops guiding at the moment it matters.

⚠ Both scales multiply a baseline captured **at import**. Scaling the modules' live
values would compound every frame and the slider would run away by itself;
`verify_slider_wiring.py` asserts three reads at 100 % change nothing.

---

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

---

## 8quinquies. ⛔⛔ THE CLAMP MUST NOT OVERRIDE A SOLVED MATE (`AS10`)

> **Owner, 2026-08-28:** *"why there are cases when cubes are snapped, their faces
> do not properly align: there is an offset and misalignment between the cubes'
> faces, as if the snap was not done properly on the centers of the faces."*

⭐ **Two causes, and they differ by a factor of thirty.**

### 1. The play-volume clamp, **87 px** — fixed

The mate solves to **0.0000 mm in world space**, and `place_center` then **clamped
the follower into the play area and silently moved it**. Near an edge the faces
genuinely do not meet.

⭐ It is the same rule §4.2 already states for the residual — **the clamp is a
SECOND DRIVER and must not be mistaken for the mate's intent** — applied to
placement instead. A mate-placed follower is no longer clamped: its position is
*determined* by the constraint. ⚠ `U9` is not weakened: ordinary placements still
clamp, and the assembly stays reachable because the **driver** is still clamped by
its own hand logic, so a follower can only sit one object-extent beyond the line —
and it is re-clamped the moment the mate breaks and it becomes its own object again.

### 2. ⛔ The renderer has NO SHARED CAMERA, **~2.7 px** — NOT fixed

Each object is projected through **its own virtual camera, centred on itself**, at a
distance derived from **its own** projected size. The same world point therefore
gets a different perspective scale from each object: measured local `rz` of
**−25.71 for the parent and +28.34 for the child** at a 40° turn.

⛔ **Two objects can never align exactly on screen, however perfect the mate.**
Worst measured **2.73 px** at today's sizes; it grows with object size and with
depth separation, and it is **exactly zero at 0°**, which is why two early probes
read 0.00 px and proved nothing.

⚠ **Deliberately left alone.** Fixing it means giving the scene ONE camera instead
of per-object projections — a real renderer change that belongs with `AS5` and the
platform decision, not a patch. ⭐ It is also a latent trap for `U2`: an imported
mesh assembled from several parts will show the same seam.
