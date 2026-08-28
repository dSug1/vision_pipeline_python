"""GOLDEN VECTORS for `Resources/mate_connector.py` — object assembly.

`CONSTRAINTS` §3: new shared geometry lands with its fixture in the same change,
not after. Queue rows `AS1`–`AS4`; design of record
`Claude/30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`.

⭐ The three decisive checks, and each pins something a plausible-looking
implementation gets wrong:

  * **the SIGN** — two connectors mate ANTI-PARALLEL, and two pointing the SAME
    way must be refused. A flipped comparison passes every other check here.
  * **the RESIDUAL TRAP** — the enforced gap is zero by construction, so a break
    test that reads it can never fire. Both are measured, side by side.
  * **FASTENED, not REVOLUTE** — after a snap the roll must land on one of the
    connector's symmetric rolls, or the mate leaves a degree of freedom the owner
    did not ask to keep.

    .venv/Scripts/python.exe analysis/verify_mate_connector.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import mate_connector as MC                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # pragma: no cover
    pass

IDENT = (1.0, 0.0, 0.0, 0.0)
CUBE_V = ((-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
          (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0))
PLUS_X_FACE = (1, 2, 6, 5)

# The real object scale, so the numbers in the spec are the numbers tested here.
HALF_SMALL = 0.0361 / 2.0
HALF_LARGE = 0.0722 / 2.0

_fails = []


def check(name, ok, detail=""):
    print("  [%s] %-62s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        _fails.append(name)


def q_axis(ax, deg):
    return MC.quat_from_axis_angle(ax, math.radians(deg))


def angle_between(a, b):
    """⚠ NORMALISES first. The first draft of this helper did not, and reported a
    constant 11.48° of error for every quaternion round-trip below — the entire
    'failure' was one non-unit probe vector in the harness. `METHOD.md`: the
    instrument is a suspect, always."""
    ua, ub = MC._unit(a), MC._unit(b)
    if ua is None or ub is None:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, MC._dot(ua, ub)))))


print("=" * 82)
print("AS1 — the data model, and the face-centre default")
print("=" * 82)

conn = MC.face_center_connector(CUBE_V, PLUS_X_FACE, (1.0, 0.0, 0.0), roll_order=4)
check("face-centre connector lands on the face centroid",
      conn is not None and max(abs(conn.position[i] - (1.0, 0.0, 0.0)[i]) for i in range(3)) < 1e-12,
      str(conn.position))
check("it carries the face's own OUTWARD normal",
      max(abs(conn.normal[i] - (1.0, 0.0, 0.0)[i]) for i in range(3)) < 1e-12)
check("its tangent is unit and perpendicular to the normal",
      abs(MC._norm(conn.tangent) - 1.0) < 1e-12 and abs(MC._dot(conn.tangent, conn.normal)) < 1e-12,
      "|t|=%.15f  t.n=%.3e" % (MC._norm(conn.tangent), MC._dot(conn.tangent, conn.normal)))
again = MC.face_center_connector(CUBE_V, PLUS_X_FACE, (1.0, 0.0, 0.0), roll_order=4)
check("it is DETERMINISTIC — the roll a mate settles into must not vary by run",
      again.tangent == conn.tangent)

pose = MC.world_pose(conn, (0.0, 0.0, 0.5), IDENT, HALF_SMALL)
check("world_pose scales the local position by the object's half-extent",
      abs(pose.position[0] - HALF_SMALL) < 1e-12, "%.6f m" % pose.position[0])
check("the capture radius derives from the object — no per-object configuration",
      abs(pose.radius - MC.MATE_RADIUS_FRACTION * HALF_SMALL) < 1e-15,
      "%.4f mm" % (pose.radius * 1000.0))

print()
print("=" * 82)
print("AS2 — the predicate. ⛔ THE SIGN IS THE ONE THAT MATTERS")
print("=" * 82)

# A at the origin, its +X face out. B is the mirror partner: rotated a half turn
# so its +X face looks back, and placed so the two faces touch exactly.
a_pose = MC.world_pose(conn, (0.0, 0.0, 0.5), IDENT, HALF_SMALL)
b_orient = q_axis((0.0, 1.0, 0.0), 180.0)
b_center = (2.0 * HALF_SMALL, 0.0, 0.5)
b_pose = MC.world_pose(conn, b_center, b_orient, HALF_SMALL)

check("two faces brought together are ANTI-PARALLEL, deviation 0°",
      MC.facing_deviation_deg(a_pose, b_pose) < 1e-9,
      "%.3e°" % MC.facing_deviation_deg(a_pose, b_pose))
check("...and their connectors coincide, so they mate",
      MC.can_mate(a_pose, b_pose),
      "gap %.3e m" % MC.separation_m(a_pose, b_pose))

# ⛔ The sign check. Same place, but B NOT turned round: both normals point +X.
b_parallel = MC.world_pose(conn, b_center, IDENT, HALF_SMALL)
check("⛔ two connectors pointing the SAME WAY are REFUSED",
      not MC.can_mate(a_pose, b_parallel),
      "deviation %.1f°" % MC.facing_deviation_deg(a_pose, b_parallel))

# ⛔ The outward gate: B's connector has passed through A's face.
b_inside = MC.world_pose(conn, (HALF_SMALL, 0.0, 0.5), b_orient, HALF_SMALL)
check("⛔ a connector that has passed INSIDE the other object is REFUSED",
      not MC.can_mate(a_pose, b_inside),
      "gap %.4f m, but on the inward side" % MC.separation_m(a_pose, b_inside))
check("...and it would have passed the sphere test alone — so the gate earns its place",
      MC.separation_m(a_pose, b_inside) <= a_pose.radius + b_inside.radius)

# The exact-mate degeneracy the outward gate must NOT refuse.
check("⚠ the PERFECT mate sits exactly at zero — the gate must not refuse it",
      MC.is_outward(a_pose, b_pose) and MC.is_outward(b_pose, a_pose))

# Capture boundary.
reach = a_pose.radius + b_pose.radius
just_in = MC.world_pose(conn, (2.0 * HALF_SMALL + reach * 0.999, 0.0, 0.5), b_orient, HALF_SMALL)
just_out = MC.world_pose(conn, (2.0 * HALF_SMALL + reach * 1.001, 0.0, 0.5), b_orient, HALF_SMALL)
check("capture: inside the summed radii mates, outside does not",
      MC.can_mate(a_pose, just_in) and not MC.can_mate(a_pose, just_out),
      "reach %.2f mm" % (reach * 1000.0))

# Angle boundary, either side of the tolerance. Tilt about an axis in the contact
# plane so the connector stays put and only its NORMAL turns.
def tilted(deg):
    p = MC.world_pose(conn, b_center, b_orient, HALF_SMALL)
    qq = q_axis((0.0, 0.0, 1.0), deg)
    return MC.ConnectorPose(position=p.position,
                            normal=MC.quat_rotate(qq, p.normal),
                            tangent=MC.quat_rotate(qq, p.tangent),
                            radius=p.radius)


check("angle: %.0f° mates, %.0f° does not" % (MC.MATE_ANGLE_TOL_DEG - 1.0, MC.MATE_ANGLE_TOL_DEG + 1.0),
      MC.can_mate(a_pose, tilted(MC.MATE_ANGLE_TOL_DEG - 1.0))
      and not MC.can_mate(a_pose, tilted(MC.MATE_ANGLE_TOL_DEG + 1.0)))

check("⭐ the tolerance clears F1's measured jitter floor and stays under 45°",
      25.41 < MC.MATE_ANGLE_TOL_DEG < 45.0,
      "%.1f° in (25.41, 45)" % MC.MATE_ANGLE_TOL_DEG)
# ⚠⚠ THE CEILING, AND WE ARE NOW SITTING EXACTLY ON IT. The rule is that capture
# must not exceed an object's own edge, or two objects mate while VISIBLY APART and
# the snap becomes a jump. The owner doubled `MATE_RADIUS_FRACTION` to 1.0 on
# 2026-08-28, which makes the reach EQUAL the edge — the deliberate maximum.
# ⛔ The comparison was `<` and now reads `<=`; that is a real loosening and it is
# recorded here rather than buried, because ANY further increase crosses a boundary
# this project chose on purpose. If snaps look like teleports live, this is why.
_edge = 2.0 * HALF_SMALL
check("⚠ capture is AT the object's own edge — the deliberate ceiling",
      reach <= _edge + 1e-9,
      "%.1f mm vs a %.1f mm edge (ratio %.2f, ceiling 1.00)"
      % (reach * 1000.0, _edge * 1000.0, reach / _edge))

print()
print("=" * 82)
print("AS3 — the snap transform: FASTENED, not REVOLUTE")
print("=" * 82)

# Child starts somewhere arbitrary and badly turned; snap must fix both.
child_q = q_axis((0.3, -0.7, 0.4), 137.0)
snapped_q, snapped_c = MC.snap_pose(a_pose, conn, child_q, HALF_SMALL)
after = MC.world_pose(conn, snapped_c, snapped_q, HALF_SMALL)

check("after the snap the two connectors COINCIDE",
      MC.separation_m(a_pose, after) < 1e-12,
      "%.3e m" % MC.separation_m(a_pose, after))
check("after the snap the normals are exactly ANTI-PARALLEL",
      MC.facing_deviation_deg(a_pose, after) < 1e-7,
      "%.3e°" % MC.facing_deviation_deg(a_pose, after))
check("the snapped orientation is a unit quaternion",
      abs(math.sqrt(sum(c * c for c in snapped_q)) - 1.0) < 1e-12)

# Fastened: the roll must land on one of the connector's symmetric rolls.
cands = MC._roll_candidates(a_pose.normal, a_pose.tangent, conn.roll_order)
best = min(angle_between(after.tangent, c) for c in cands)
check("⭐ the roll lands ON one of the %d symmetric rolls — FASTENED, 0 DOF" % conn.roll_order,
      best < 1e-4, "%.3e° from the nearest, against a %.0f° step"
      % (best, 360.0 / conn.roll_order))

# ⭐ NEAREST roll. Start the child already correctly mated, then spin it about the
# contact axis by a known amount: the snap must undo only the part that is not a
# whole symmetry step, so the residual spin never exceeds half a step.
step_half = 180.0 / conn.roll_order
worst = 0.0
for deg in range(0, 360, 5):
    spun = MC.quat_mul(q_axis(a_pose.normal, float(deg)), snapped_q)
    sq, sc = MC.snap_pose(a_pose, conn, spun, HALF_SMALL)
    before = MC.world_pose(conn, (0.0, 0.0, 0.0), spun, HALF_SMALL)
    resolved = MC.world_pose(conn, (0.0, 0.0, 0.0), sq, HALF_SMALL)
    worst = max(worst, angle_between(before.tangent, resolved.tangent))
check("⭐ the snap picks the NEAREST valid roll — never more than %.0f° of spin"
      % step_half,
      worst <= step_half + 1e-6, "worst %.2f° over 72 start rolls" % worst)

# Free spin degrades to Revolute deliberately.
round_conn = MC.face_center_connector(CUBE_V, PLUS_X_FACE, (1.0, 0.0, 0.0), roll_order=0)
rq, rc = MC.snap_pose(a_pose, round_conn, child_q, HALF_SMALL)
r_after = MC.world_pose(round_conn, rc, rq, HALF_SMALL)
check("roll_order 0 still mates — it just keeps the player's roll (REVOLUTE)",
      MC.separation_m(a_pose, r_after) < 1e-12
      and MC.facing_deviation_deg(a_pose, r_after) < 1e-7)

print()
print("=" * 82)
print("AS3 — ⛔⛔ THE RESIDUAL TRAP, measured both ways")
print("=" * 82)

# Enforced: the child is placed by the mate, so the observed gap is zero.
enforced_lin, enforced_ang = MC.residual(a_pose, after)
check("⛔ the ENFORCED gap is zero — a break test reading THIS can never fire",
      enforced_lin < 1e-12 and enforced_ang < 1e-7,
      "%.3e m / %.3e°" % (enforced_lin, enforced_ang))

# Desired: a second hand drags the child 60 mm away. THIS is what breaks it.
pulled = MC.world_pose(conn, (2.0 * HALF_SMALL + 0.060, 0.0, 0.5), b_orient, HALF_SMALL)
pulled_lin, _ = MC.residual(a_pose, pulled)
check("⭐ the DESIRED residual sees the pull, and breaks the mate",
      pulled_lin > 0.0 and MC.should_break(a_pose, pulled),
      "%.1f mm of pull" % (pulled_lin * 1000.0))

# ⛔ HYSTERESIS: there must be a DEAD BAND — a whole range of separations where a
# mate both engages and refuses to break. Without it the two thresholds coincide
# and the mate chatters at 25° of pipeline jitter.
at_engage = MC.world_pose(conn, (2.0 * HALF_SMALL + reach * 0.999, 0.0, 0.5), b_orient, HALF_SMALL)
mid_band = MC.world_pose(conn, (2.0 * HALF_SMALL + reach * 1.2, 0.0, 0.5), b_orient, HALF_SMALL)
past_band = MC.world_pose(conn, (2.0 * HALF_SMALL + reach * MC.MATE_BREAK_FACTOR * 1.001, 0.0, 0.5),
                          b_orient, HALF_SMALL)
check("⛔ HYSTERESIS: engages at the capture radius and does NOT break there",
      MC.can_mate(a_pose, at_engage) and not MC.should_break(a_pose, at_engage),
      "engage %.1f mm / break %.1f mm" % (reach * 1000.0, reach * MC.MATE_BREAK_FACTOR * 1000.0))
check("...the DEAD BAND is real — past capture, still held",
      not MC.can_mate(a_pose, mid_band) and not MC.should_break(a_pose, mid_band))
check("...and past the break radius it lets go",
      MC.should_break(a_pose, past_band))
check("...and the break factor is strictly greater than 1, or it would chatter",
      MC.MATE_BREAK_FACTOR > 1.0, "%.2f" % MC.MATE_BREAK_FACTOR)

print()
print("=" * 82)
print("AS4 — the tree: parent by size, ROOT by grab, cycles refused")
print("=" * 82)

check("the BIGGER object parents the smaller, whichever order it is asked in",
      MC.order_by_size("small", 40, "large", 80) == ("large", "small")
      and MC.order_by_size("large", 80, "small", 40) == ("large", "small"))
check("equal sizes tie-break DETERMINISTICALLY — or the hierarchy chatters",
      MC.order_by_size("b", 40, "a", 40) == MC.order_by_size("a", 40, "b", 40))

asm = MC.Assembly()
check("a single satisfied frame does NOT engage — the dwell is %.0f ms" % MC.MATE_DWELL_MS,
      not asm.offer("large", "small", 0, 0, True, 0.0))
check("...still not engaged one frame later (48–64 ms is L1's measured gap)",
      not asm.offer("large", "small", 0, 0, True, 60.0))
check("...engages once the dwell has elapsed",
      asm.offer("large", "small", 0, 0, True, 120.0))
check("the small cube's parent is the large one",
      asm.parent_of("small") == "large" and asm.parent_of("large") is None)

asm2 = MC.Assembly()
asm2.offer("large", "small", 0, 0, True, 0.0)
asm2.offer("large", "small", 0, 0, False, 60.0)          # interrupted
check("an interrupted approach RESTARTS the dwell rather than banking it",
      not asm2.offer("large", "small", 0, 0, True, 120.0))

check("⭐⭐ ROOT BY GRAB: grabbing the CHILD still finds the assembly's root",
      asm.root_for("small") == "large" and asm.root_for("large") == "large")
check("...and the assembly lists parents before children",
      asm.connected("small") == ["large", "small"])

check("⛔ a mate that would close a CYCLE is refused",
      asm.would_cycle("small", "large") and not asm.can_link("small", "large", 1, 1))
check("⛔ an object may not take a second parent — it is a tree",
      not asm.can_link("other", "small", 0, 1))
check("⛔ a connector already in use cannot be mated again",
      not asm.can_link("large", "third", 0, 0))

check("a single break-frame does not break it — the dwell guards both directions",
      not asm.offer_break("small", True, 200.0))
check("...it breaks once the dwell has elapsed",
      asm.offer_break("small", True, 400.0) and asm.parent_of("small") is None)

print()
print("=" * 82)
print("The quaternion construction, at the pose a mate actually reaches")
print("=" * 82)

# ⚠ Anti-parallel normals mean the snap routinely lands on a HALF TURN, which is
# exactly where the textbook w-first quaternion form loses precision or sign.
for ax, deg in (((0.0, 1.0, 0.0), 180.0), ((1.0, 0.0, 0.0), 180.0),
                ((0.0, 0.0, 1.0), 180.0), ((0.577, 0.577, 0.577), 240.0)):
    q = q_axis(ax, deg)
    cols = [MC.quat_rotate(q, e) for e in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))]
    back = MC.quat_from_basis(*cols)
    err = max(angle_between(MC.quat_rotate(q, v), MC.quat_rotate(back, v))
              for v in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.3, -0.5, 0.8)))
    check("basis→quaternion round-trips at %3.0f° about %s" % (deg, tuple(round(c, 2) for c in ax)),
          err < 1e-6, "%.3e°" % err)

print("=" * 82)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — the mate is anti-parallel, fastened, and breakable.")
