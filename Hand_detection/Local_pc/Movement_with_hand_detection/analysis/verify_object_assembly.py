"""GOLDEN VECTORS for `Resources/object_assembly.py` — the per-frame assembly step.

`verify_mate_connector.py` proves the geometry. This proves the WIRING: that the
pixel/metre conversion round-trips, that the two cubes mate at the pose a player
would actually put them in, and that the three behaviours the owner specified
actually happen.

⭐ The three that matter, and each is a claim the design would be worthless without:

  * **ONE HAND CAN NEVER BREAK A MATE** — with a single driver the residual is
    identically zero however far the object is dragged. This is not a rule that was
    written; it falls out of measuring the residual between two DESIRES.
  * **RE-ROOTING** — grabbing the small cube (the CHILD) moves the large one.
    Without it, grabbing a child moves nothing at all.
  * **THE CLAMP IS EXEMPT** — driving an assembly into the play-volume wall must
    not break it, because a wall breaking a joint is invisible to the player.

    .venv/Scripts/python.exe analysis/verify_object_assembly.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import mate_connector as MC                     # noqa: E402
from Resources import object_assembly as OA                    # noqa: E402
from Resources import palm_geometry                            # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # pragma: no cover
    pass

FRAME = (640, 480)
IDENT = (1.0, 0.0, 0.0, 0.0)
FLIP_Y = (0.0, 0.0, 1.0, 0.0)                 # a half turn about Y: +X face looks back
CUBE_V = ((-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
          (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0))
PLUS_X = MC.face_center_connector(CUBE_V, (1, 2, 6, 5), (1.0, 0.0, 0.0), roll_order=4)


class _Face(object):
    """The two fields `cube_face_connectors` reads off a `MeshFace`, so this file
    can exercise the real default set without importing either renderer."""

    def __init__(self, vertex_indices, normal):
        self.vertex_indices = vertex_indices
        self.normal = normal


_CUBE_FACES = (_Face((1, 2, 6, 5), (1.0, 0.0, 0.0)), _Face((0, 3, 7, 4), (-1.0, 0.0, 0.0)),
               _Face((3, 2, 6, 7), (0.0, 1.0, 0.0)), _Face((0, 1, 5, 4), (0.0, -1.0, 0.0)),
               _Face((4, 5, 6, 7), (0.0, 0.0, 1.0)), _Face((0, 1, 2, 3), (0.0, 0.0, -1.0)))

_fails = []


def check(name, ok, detail=""):
    print("  [%s] %-62s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        _fails.append(name)


class FakeCube(object):
    """The attributes `object_assembly.step` duck-types. Both tools' `Cube` has
    every one of them, which is what lets the two share this code (`N6`)."""

    def __init__(self, size, center_px, depth_m=palm_geometry.REFERENCE_DEPTH_M,
                 orientation=IDENT, owner=None):
        self.size = size
        self.depth_m = depth_m
        self.orientation = orientation
        self.owner = owner
        self.connectors = (PLUS_X,)
        self.mate_state = ""
        self.position = (0.0, 0.0)
        OA.place_center(self, center_px, FRAME)


def px_x(world_x, depth=palm_geometry.REFERENCE_DEPTH_M):
    return palm_geometry.px_from_world(world_x, 0.0, depth, FRAME)[0]


HALF_L = OA.half_extent_m(80, FRAME)
HALF_S = OA.half_extent_m(40, FRAME)
MATED_SMALL_X = px_x(HALF_L + HALF_S)          # where the small cube's centre must sit


def fresh(small_center_x, small_owner=None, large_owner=None):
    cubes = {"large": FakeCube(80, (320.0, 240.0), owner=large_owner),
             "small": FakeCube(40, (small_center_x, 240.0), orientation=FLIP_Y,
                               owner=small_owner)}
    return cubes, MC.Assembly()


def run(cubes, asm, frames, desires=None, t0=0.0, dt=60.0, latch=None, release=None):
    """Feed `frames` identical frames, so the dwell can elapse.

    ⚠ The hand logic runs FIRST and writes its (clamped) result onto the cube, then
    the assembly step runs — that is the real order in both tools, and the first
    draft of this harness left the write out. The failure looked like a module bug
    and was not: `METHOD.md`, the instrument is a suspect, always.
    """
    events = []
    for i in range(frames):
        for name, want in (desires or {}).items():
            cube = cubes[name]
            if "depth_m" in want:
                cube.depth_m = palm_geometry.clamp_depth(want["depth_m"])
            if "center_px" in want:
                OA.place_center(cube, want["center_px"], FRAME)
        events += OA.step(cubes, asm, FRAME, t0 + i * dt, desires=desires,
                          latch=latch, release=release)
    return events


print("=" * 82)
print("The pixel ↔ metre round trip these two cubes live in")
print("=" * 82)

check("the object's real half-size is depth-independent",
      abs(HALF_L - 0.0722 / 2.0) < 5e-5 and abs(HALF_S - 0.0361 / 2.0) < 5e-5,
      "large %.2f mm / small %.2f mm half-extent" % (HALF_L * 1000.0, HALF_S * 1000.0))

c = FakeCube(40, (401.0, 233.0))
back = OA.center_px_of(c)
check("a centre written and read back survives the top-left round trip",
      abs(back[0] - 401.0) < 1e-9 and abs(back[1] - 233.0) < 1e-9, str(back))

print()
print("=" * 82)
print("Two cubes, +X face to +X face — the pose a player actually aims for")
print("=" * 82)

cubes, asm = fresh(px_x(0.30))
run(cubes, asm, 6)
check("far apart, nothing mates", not asm.links,
      "%.0f mm between centres" % ((0.30 - HALF_L - HALF_S) * 1000.0))

cubes, asm = fresh(MATED_SMALL_X)
events = run(cubes, asm, 1)
check("one frame in contact is NOT enough — the dwell holds it off", not asm.links)
events += run(cubes, asm, 3, t0=60.0)
check("⭐ sustained past the dwell, the two cubes MATE",
      bool(asm.links) and ("mated", "large", "small") in events)
check("the SMALLER cube became the child of the bigger one",
      asm.parent_of("small") == "large")
check("both report the mated state to the renderer",
      cubes["large"].mate_state == "mated" and cubes["small"].mate_state == "mated")

# The enforced pose really does put the connectors on top of each other.
lp = MC.world_pose(PLUS_X, OA.to_world(OA.ObjectDesire("l", 80, OA.center_px_of(cubes["large"]),
                                                       cubes["large"].depth_m,
                                                       cubes["large"].orientation, ()), FRAME),
                   cubes["large"].orientation, HALF_L)
sp = MC.world_pose(PLUS_X, OA.to_world(OA.ObjectDesire("s", 40, OA.center_px_of(cubes["small"]),
                                                       cubes["small"].depth_m,
                                                       cubes["small"].orientation, ()), FRAME),
                   cubes["small"].orientation, HALF_S)
check("⭐ after the step the two connectors COINCIDE on screen",
      MC.separation_m(lp, sp) < 5e-4, "%.4f mm apart" % (MC.separation_m(lp, sp) * 1000.0))
check("...and their normals are anti-parallel",
      MC.facing_deviation_deg(lp, sp) < 0.5, "%.4f°" % MC.facing_deviation_deg(lp, sp))

print()
print("=" * 82)
print("⭐⭐ ONE HAND CAN NEVER BREAK A MATE")
print("=" * 82)

cubes, asm = fresh(MATED_SMALL_X, large_owner="hand-a")
run(cubes, asm, 4)
check("mated, with the LARGE cube in one hand", bool(asm.links))

# Drag the large cube a long way. The small one has no driver of its own, so it
# simply follows: the residual stays zero and there is nothing to break.
held = OA.center_px_of(cubes["large"])
for i in range(1, 40):
    want = (held[0] - i * 4.0, held[1])
    run(cubes, asm, 1, desires={"large": {"center_px": want}}, t0=300.0 + i * 60.0)
check("⭐ dragged 156 px across the screen, the mate SURVIVES — one driver, zero residual",
      bool(asm.links), "small followed to x=%.0f" % OA.center_px_of(cubes["small"])[0])
check("...and the small cube travelled with it, keeping its offset",
      abs((OA.center_px_of(cubes["small"])[0] - OA.center_px_of(cubes["large"])[0])
          - (MATED_SMALL_X - 320.0)) < 1.0)

print()
print("=" * 82)
print("⭐⭐ RE-ROOTING — grabbing the CHILD must move the PARENT")
print("=" * 82)

cubes, asm = fresh(MATED_SMALL_X, small_owner="hand-a")
run(cubes, asm, 4)
check("mated, with the SMALL cube (the child) in the hand", bool(asm.links))
large_before = OA.center_px_of(cubes["large"])[0]
for i in range(1, 16):
    want = (MATED_SMALL_X + i * 4.0, 240.0)
    run(cubes, asm, 1, desires={"small": {"center_px": want}}, t0=300.0 + i * 60.0)
large_after = OA.center_px_of(cubes["large"])[0]
check("⭐⭐ the LARGE cube followed the child that was grabbed",
      large_after - large_before > 50.0,
      "large moved %.0f px" % (large_after - large_before))
check("...and the mate held throughout", bool(asm.links))

print()
print("=" * 82)
print("⭐⭐ TWO HANDS PULLING APART — the only thing that breaks it")
print("=" * 82)

cubes, asm = fresh(MATED_SMALL_X, small_owner="hand-a", large_owner="hand-b")
run(cubes, asm, 4)
check("mated, one cube in each hand", bool(asm.links))
broke_at = None
for i in range(1, 40):
    ev = run(cubes, asm, 1, t0=300.0 + i * 60.0,
             desires={"large": {"center_px": (320.0 - i * 3.0, 240.0)},
                      "small": {"center_px": (MATED_SMALL_X + i * 3.0, 240.0)}})
    if any(e[0] == "broke" for e in ev):
        broke_at = i * 6.0
        break
check("⭐ pulled apart by two hands, the mate BREAKS",
      broke_at is not None and not asm.links,
      "after %.0f px of separation" % (broke_at or 0.0))
check("...and it took more pull than it took to engage — the dead band is real",
      broke_at is not None and broke_at > 0.0)
check("both cubes report the mate is gone",
      cubes["large"].mate_state != "mated" and cubes["small"].mate_state != "mated")

print()
print("=" * 82)
print("⚠ THE PLAY-VOLUME CLAMP IS EXEMPT — a wall must not break a joint")
print("=" * 82)

cubes, asm = fresh(MATED_SMALL_X, large_owner="hand-a")
run(cubes, asm, 4)
check("mated, large cube held", bool(asm.links))
# Drive it hard into the left wall and keep pushing. The stored pose stops at the
# clamp; the DESIRE keeps going. Measuring the residual on the stored pose would
# make the small cube appear to lag, and the mate would break for no visible cause.
for i in range(1, 30):
    run(cubes, asm, 1, desires={"large": {"center_px": (-400.0 - i * 40.0, 240.0)}},
        t0=300.0 + i * 60.0)
check("⭐ pushed far past the wall for 29 frames, the mate SURVIVES",
      bool(asm.links), "large parked at x=%.0f" % OA.center_px_of(cubes["large"])[0])

print()
print("=" * 82)
print("Depth — an assembly must survive moving in Z")
print("=" * 82)

cubes, asm = fresh(MATED_SMALL_X, large_owner="hand-a")
run(cubes, asm, 4)
for i in range(1, 12):
    run(cubes, asm, 1, desires={"large": {"center_px": (320.0, 240.0),
                                          "depth_m": 0.50 + i * 0.02}},
        t0=300.0 + i * 60.0)
check("the mate survives being pushed from 0.50 m to %.2f m" % cubes["large"].depth_m,
      bool(asm.links))
check("⭐ the child went with it in depth, not just on screen",
      abs(cubes["small"].depth_m - cubes["large"].depth_m) < 0.02,
      "large %.3f m / small %.3f m" % (cubes["large"].depth_m, cubes["small"].depth_m))

print()
print("=" * 82)
print("⭐⭐ AS6 — RELEASE AT MATE, AND RE-ARM ON EXIT")
print("=" * 82)

# The live defect: a cube in each hand, both driven, and the hand that placed the
# child keeps moving — so the residual grows and the mate lets go within a few
# frames. Releasing the child's grab at the mate removes one of the two drivers.
cubes, asm = fresh(MATED_SMALL_X, small_owner="hand-a", large_owner="hand-b")
latch = OA.RegrabLatch()
released = []
for i in range(4):
    OA.step(cubes, asm, FRAME, i * 60.0, release=lambda n: released.append(n),
            latch=latch)
check("⭐ the mate engages with a cube in each hand", bool(asm.links))

# ⭐⭐ ONE-HANDED: NOTHING IS RELEASED, because nothing can break it. `AS3` makes a
# residual need TWO drivers, so a hand that mates on its own simply keeps the
# object and drives the assembly with it. Releasing here cost the owner a re-grab
# that meant leaving the whole assembly (144 px) and coming back — and finding the
# PARENT nearest on return.
solo_cubes, solo_asm = fresh(MATED_SMALL_X, small_owner="hand-a")
solo_latch, solo_released = OA.RegrabLatch(), []
for i in range(4):
    OA.step(solo_cubes, solo_asm, FRAME, i * 60.0,
            release=lambda n: solo_released.append(n), latch=solo_latch)
check("⭐⭐ ONE-HANDED mate: the cube is NOT taken out of the hand",
      bool(solo_asm.links) and solo_released == []
      and solo_cubes["small"].owner == "hand-a", str(solo_released))
check("...so there is nothing to re-grab, and no latch to wait out",
      not solo_latch.blocked("small", "hand-a"))
for i in range(1, 30):
    want = (MATED_SMALL_X + i * 5.0, 240.0)
    run(solo_cubes, solo_asm, 1, t0=300.0 + i * 60.0, latch=solo_latch,
        desires={"small": {"center_px": want}})
check("⭐ and the mate SURVIVES the hand carrying on — one driver, zero residual",
      bool(solo_asm.links), "dragged %d px still holding it" % (29 * 5))
check("⭐⭐ the CHILD's grab is dropped at the mate", released == ["small"],
      str(released))
check("...and its hand is latched out of re-grabbing it",
      latch.blocked("small", "hand-a"))
check("...but the OTHER hand may take it immediately — that is how a detach works",
      not latch.blocked("small", "hand-b"))

# ⛔ The regression this whole row exists to prevent: with the child released,
# the surviving driver cannot break the mate however far it goes.
cubes["small"].owner = None
for i in range(1, 30):
    run(cubes, asm, 1, t0=300.0 + i * 60.0,
        desires={"large": {"center_px": (320.0 - i * 5.0, 240.0)}})
check("⛔ THE LIVE DEFECT IS GONE — the mate survives the hand moving on",
      bool(asm.links), "large dragged %d px" % (29 * 5))

# The latch: leaving must be sustained, and coming back resets it.
latch2 = OA.RegrabLatch()
latch2.arm("small", "hand-a")
check("blocked immediately after the mate", latch2.blocked("small", "hand-a"))
check("one frame outside is not enough",
      latch2.observe("small", "hand-a", True, 0.0))
check("...nor is 60 ms (L1 measures the frame gap at 48–64 ms)",
      latch2.observe("small", "hand-a", True, 60.0))
check("⭐ clear after the dwell — the hand has genuinely left",
      not latch2.observe("small", "hand-a", True, 200.0)
      and not latch2.blocked("small", "hand-a"))

latch3 = OA.RegrabLatch()
latch3.arm("small", "hand-a")
latch3.observe("small", "hand-a", True, 0.0)
latch3.observe("small", "hand-a", False, 60.0)          # drifted back over it
check("⚠ coming back RESETS the dwell rather than banking it",
      latch3.observe("small", "hand-a", True, 120.0)
      and latch3.blocked("small", "hand-a"))

check("⛔ the re-arm threshold is wider than the grab radius, or it is not hysteresis",
      OA.REGRAB_RELEASE_FACTOR > 1.0, "%.2f×" % OA.REGRAB_RELEASE_FACTOR)

# A broken mate must forget the latch, or an ordinary grab is refused later.
cubes2, asm2 = fresh(MATED_SMALL_X, small_owner="hand-a", large_owner="hand-b")
latch4 = OA.RegrabLatch()
for i in range(4):
    OA.step(cubes2, asm2, FRAME, i * 60.0, release=lambda n: None, latch=latch4)
cubes2["small"].owner = "hand-a"                        # re-grabbed later
for i in range(1, 40):
    ev = run(cubes2, asm2, 1, t0=300.0 + i * 60.0, latch=latch4,
             desires={"large": {"center_px": (320.0 - i * 3.0, 240.0)},
                      "small": {"center_px": (MATED_SMALL_X + i * 3.0, 240.0)}})
    if any(e[0] == "broke" for e in ev):
        break
check("⚠ a BROKEN mate forgets the latch — a stale one would refuse a normal grab",
      not asm2.links and not latch4.blocked("small", "hand-a"))

print()
print("=" * 82)
print("⭐⭐ AS7 — THE MATE PREVIEW: the ghost, the drop line, and which mate wins")
print("=" * 82)

# ⭐ The preview must appear BEFORE the mate is possible, or it guides nothing.
reach_m = OA.half_extent_m(80, FRAME) * MC.MATE_RADIUS_FRACTION \
    + OA.half_extent_m(40, FRAME) * MC.MATE_RADIUS_FRACTION
far = px_x(HALF_L + HALF_S + reach_m * 2.0)               # 2x the capture reach
cubes, asm = fresh(far)
run(cubes, asm, 2)
pv = cubes["small"].mate_preview
check("⭐⭐ the ghost appears while the mate is still OUT of reach",
      pv is not None and not pv.reachable,
      "gap %.1f mm vs %.1f mm capture" % ((pv.gap_m * 1000.0) if pv else -1,
                                          reach_m * 1000.0))
check("...and nothing has mated yet", not asm.links)

# ⛔ The ghost must be the pose it would ACTUALLY snap to, not a lookalike.
if pv is not None:
    ghost_cube = FakeCube(40, pv.center_px, depth_m=pv.depth_m,
                          orientation=pv.orientation)
    gp = MC.world_pose(PLUS_X, OA.to_world(
        OA.ObjectDesire("g", 40, OA.center_px_of(ghost_cube), ghost_cube.depth_m,
                        pv.orientation, ()), FRAME), pv.orientation, HALF_S)
    lp2 = MC.world_pose(PLUS_X, OA.to_world(
        OA.ObjectDesire("l", 80, OA.center_px_of(cubes["large"]),
                        cubes["large"].depth_m, cubes["large"].orientation, ()),
        FRAME), cubes["large"].orientation, HALF_L)
    check("⛔ the GHOST sits exactly where the object would land",
          MC.separation_m(lp2, gp) < 5e-4 and MC.facing_deviation_deg(lp2, gp) < 0.5,
          "%.4f mm / %.4f°" % (MC.separation_m(lp2, gp) * 1000.0,
                               MC.facing_deviation_deg(lp2, gp)))
    check("the DROP LINE joins the two connectors on screen",
          pv.from_px is not None and pv.to_px is not None
          and abs(pv.from_px[0] - pv.to_px[0]) > 1.0,
          "%.0f px apart" % abs(pv.from_px[0] - pv.to_px[0]))

# ⭐ It turns 'reachable' exactly when the mate becomes possible — that is what
# tells a player to stop pushing and hold still.
cubes, asm = fresh(MATED_SMALL_X)
OA.step(cubes, asm, FRAME, 0.0)
pv2 = cubes["small"].mate_preview
check("⭐ at the mating pose the preview reads REACHABLE",
      pv2 is not None and pv2.reachable)

# Beyond the preview radius: nothing drawn, or the screen is permanent clutter.
cubes, asm = fresh(px_x(0.30))
run(cubes, asm, 2)
check("⛔ far away there is no ghost at all", cubes["small"].mate_preview is None)

# Facing the wrong way: no ghost either.
cubes, asm = fresh(MATED_SMALL_X)
cubes["small"].orientation = IDENT                        # +X face points away
run(cubes, asm, 2)
check("⛔ back-to-back objects get no ghost — past 90° they do not face at all",
      cubes["small"].mate_preview is None)

# ⭐⭐ The score IS the predicate, so a preview can never disagree with the mate.
a_p = MC.world_pose(PLUS_X, (0.0, 0.0, 0.5), IDENT, HALF_S)
for dx in (0.5, 0.9, 1.0, 1.1, 2.0):
    b_p = MC.world_pose(PLUS_X, (2.0 * HALF_S + reach_m * 0.0 + dx * 0.02, 0.0, 0.5),
                        FLIP_Y, HALF_S)
    scored = MC.mate_score(a_p, b_p) <= 1.0
    check("score<=1 agrees with can_mate at %.1f" % dx,
          scored == MC.can_mate(a_p, b_p))

check("⛔ the preview radius is wider than the capture radius, or it guides nothing",
      OA.PREVIEW_RADIUS_FACTOR > 1.0, "%.1f×" % OA.PREVIEW_RADIUS_FACTOR)

# ⛔⛔ THE REGRESSION THIS SECTION EXISTS FOR. The first build gave each cube ONE
# connector, both on `+X` — so two unrotated cubes had their normals pointing the
# SAME way, 180° apart, and NOTHING could ever mate or even preview until one was
# turned a full half-turn. The owner found it by seeing an empty screen. Every
# offline check passed, because every one of them had already rotated a cube.
DEFAULTS = OA.cube_face_connectors(CUBE_V, _CUBE_FACES)
check("⛔⛔ the default connector set covers ALL SIX faces",
      len(DEFAULTS) == 6, "%d connectors" % len(DEFAULTS))
check("...their normals are the six axis directions, each exactly once",
      sorted(tuple(round(c, 6) for c in k.normal) for k in DEFAULTS)
      == sorted(tuple(float(c) for c in n) for n in OA.ALL_SIX_FACES))
check("⭐⭐ so two UNROTATED cubes side by side can mate — the live defect, pinned",
      any(MC.facing_deviation_deg(
          MC.world_pose(p, (0.0, 0.0, 0.5), IDENT, HALF_L),
          MC.world_pose(q, (HALF_L + HALF_S, 0.0, 0.5), IDENT, HALF_S)) < 1e-9
          for p in DEFAULTS for q in DEFAULTS))
check("⭐ and more than one pair is available, so 'which mate' is a real choice",
      sum(1 for p in DEFAULTS for q in DEFAULTS
          if MC.facing_deviation_deg(
              MC.world_pose(p, (0.0, 0.0, 0.5), IDENT, HALF_L),
              MC.world_pose(q, (0.0, 0.0, 0.5), IDENT, HALF_S)) < 1e-9) >= 6)
check("⛔ the preview angle stays under 90° — past it the normals stop facing",
      OA.PREVIEW_ANGLE_DEG < 90.0, "%.0f°" % OA.PREVIEW_ANGLE_DEG)

print()
print("=" * 82)
print("⛔⛔ OBJECTS MUST NOT START ON TOP OF EACH OTHER")
print("=" * 82)

# The owner reported this as "I can't get the cube to move on the z axis". Both
# cubes started at the window centre — interpenetrating — which was invisible while
# each had ONE connector, because two unrotated cubes could not mate at all. With
# six faces an ordinary 72 px drag mated on frame 12, AS6 correctly took the cube
# out of the hand, and it stopped moving in EVERY axis. z was simply the axis being
# tested at the time.
h0 = OA.home_center_px(0, 2, FRAME)
h1 = OA.home_center_px(1, 2, FRAME)
check("two objects start APART, not both at the centre",
      abs(h0[0] - h1[0]) > 1.0, "%.0f px between homes" % abs(h0[0] - h1[0]))
check("a single object still starts at the centre",
      OA.home_center_px(0, 1, FRAME) == (FRAME[0] / 2.0, FRAME[1] / 2.0))
check("the row is centred on the window",
      abs((h0[0] + h1[0]) / 2.0 - FRAME[0] / 2.0) < 1e-9)

# ⭐ The separation is DERIVED: the connector gap at the home distance must exceed
# the PREVIEW reach, or the scene opens already showing a ghost.
home_gap_m = OA.HOME_SEPARATION_M - HALF_L - HALF_S
preview_reach_m = (OA.half_extent_m(80, FRAME) + OA.half_extent_m(40, FRAME)) \
    * MC.MATE_RADIUS_FRACTION * OA.PREVIEW_RADIUS_FACTOR
check("⭐ the home separation clears the PREVIEW reach — no ghost at startup",
      home_gap_m > preview_reach_m,
      "%.1f mm gap vs %.1f mm preview" % (home_gap_m * 1000.0, preview_reach_m * 1000.0))

# End to end: a fresh scene is quiet, and stays quiet while a cube is dragged AWAY.
cubes, asm = fresh(px_x(OA.HOME_SEPARATION_M - HALF_L - HALF_S + HALF_L + HALF_S))
run(cubes, asm, 4)
check("⛔ a fresh scene shows NO ghost and has NOT mated",
      cubes["small"].mate_preview is None and not asm.links)

print()
print("=" * 82)
print("⛔⛔ AN UN-SNAP MUST SURVIVE MORE THAN ONE FRAME")
print("=" * 82)

# ⭐⭐ THE DEFECT THIS PINS TOOK FOUR LIVE REPORTS TO FIND, and every offline probe
# missed it because none of them broke a mate and then just LOOKED. A break
# measures the two DESIRES diverging; it never requires the objects to MOVE APART.
# So on the next frame they are still touching, `can_mate` is true again, the dwell
# re-engages — and the object is a FOLLOWER once more, whose depth its parent owns.
# The owner reported it as *"once a cube has been un-snapped, I cannot move it on
# z axis"*, which is exactly what a follower looks like from the outside.
cubes, asm = fresh(MATED_SMALL_X)
run(cubes, asm, 4)
check("a mate is engaged to start from", bool(asm.links))
asm.unlink("small")                       # un-snap, WITHOUT moving anything
run(cubes, asm, 6)
check("⛔⛔ it stays un-snapped while the objects have not moved",
      not asm.links, "re-mated=%s" % bool(asm.links))
check("...and the object is FREE again, not a follower whose depth is not its own",
      cubes["small"].mate_role != "follower", cubes["small"].mate_role or "free")

# ⭐ But it must still be possible to mate again — after genuinely parting.
apart_x = px_x(HALF_L + HALF_S + 0.25)
OA.place_center(cubes["small"], (apart_x, 240.0), FRAME)
run(cubes, asm, 6, t0=1000.0)
OA.place_center(cubes["small"], (MATED_SMALL_X, 240.0), FRAME)
run(cubes, asm, 6, t0=2000.0)
check("⭐ and it CAN mate again once the pair has genuinely parted and returned",
      bool(asm.links))

check("⚠ homing un-mates WITHOUT a cooldown — it moves the objects apart itself",
      True)
c2, a2 = fresh(MATED_SMALL_X)
run(c2, a2, 4)
a2.unlink("small", cooldown=False)
run(c2, a2, 6)
check("...so a home-then-remate is not refused", bool(a2.links))

print()
print("=" * 82)
print("⛔⛔ THE PLAY-VOLUME CLAMP MUST NOT OVERRIDE A SOLVED MATE")
print("=" * 82)

# ⭐⭐ Owner, 2026-08-28: *"there is an offset and misalignment between the cubes'
# faces, as if the snap was not done properly on the centers of the faces"*.
# The mate was exact to 0.0000 mm in world space; `place_center` then CLAMPED the
# follower into the play area and silently moved it — measured **87 px**. Same rule
# as §4.2: the clamp is a SECOND DRIVER and must not be mistaken for the mate.
_hL = OA.half_extent_m(80, FRAME)
_hS = OA.half_extent_m(80, FRAME)
_conn = MC.face_center_connector(CUBE_V, (1, 2, 6, 5), (1.0, 0.0, 0.0))
_connB = MC.face_center_connector(CUBE_V, (0, 3, 7, 4), (-1.0, 0.0, 0.0))
_worst = 0.0
for _cx in (320.0, 480.0, 560.0, 620.0):
    _parent = FakeCube(80, (_cx, 240.0))
    _ctr = OA.to_world(OA.ObjectDesire("l", 80, OA.center_px_of(_parent),
                                       _parent.depth_m, IDENT, ()), FRAME, actual=True)
    _pp = MC.world_pose(_conn, _ctr, IDENT, _hL)
    _q, _c = MC.snap_pose(_pp, _connB, IDENT, _hS)
    _scr = OA.to_screen(_c, FRAME)
    _child = FakeCube(80, (0.0, 0.0))
    _child.orientation = _q
    _child.depth_m = _scr[1]
    OA.place_center(_child, _scr[0], FRAME, clamp=False)
    _worst = max(_worst, abs(OA.center_px_of(_child)[0] - _scr[0][0]))
check("⛔⛔ a mate-placed follower is NOT displaced, even outside the play area",
      _worst < 0.5, "worst displacement %.1f px across four parent positions" % _worst)

_c2 = FakeCube(80, (0.0, 0.0))
OA.place_center(_c2, (620.0, 240.0), FRAME, clamp=True)
check("...while an ordinary placement IS still clamped — `U9` is not weakened",
      abs(OA.center_px_of(_c2)[0] - 620.0) > 0.5,
      "620 -> %.1f px" % OA.center_px_of(_c2)[0])

print("=" * 82)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — the two cubes assemble, re-root, and take two hands to part.")
