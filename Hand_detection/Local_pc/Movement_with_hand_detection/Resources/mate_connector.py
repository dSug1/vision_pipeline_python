"""⭐⭐ MATE CONNECTORS — how two objects join, hold and separate.

> **Owner, 2026-08-28:** *"I want the objects to be able to assemble into an
> assembly. […] an object assembles with another through one or several
> [connectors] which are positioned on the object's surface."* and *"call it mate
> connector · when the object snaps, the smaller one becomes a child of the bigger
> one and the position of the child is controlled so that the two mate connector
> positions are always identical and the normals of the mate connectors always
> align · the two objects remain grabable independently and the mate connection
> can be broken if the hands pull them apart"*.

Design of record: `Claude/30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`.
Queue rows `AS1`-`AS4`. Golden vectors: `analysis/verify_mate_connector.py`.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE THREE THINGS THAT ARE EASY TO GET BACKWARDS

**1. A connector stores the surface's TRUE OUTWARD NORMAL, so a mate is
ANTI-PARALLEL.** Two surfaces that touch face each other. This is the opposite of
the owner's first wording (*"aligned … and not in opposite direction"*) and it is a
CONVENTION, not a disagreement -- outward-normal was chosen because it is the
surface's own property (so it derives from the mesh automatically, which is the
default the owner asked for) and because an imported glTF/OBJ already carries it.
⛔ `CONSTRAINTS` §7bis: ONE place knows this sign. It is this module. `V1` cost a
session because the build took its mirror from one convention and its depth from
the other.

**2. The `outward` half of the test is load-bearing.** A sphere-intersection test
is direction-blind: without it, two OVERLAPPING objects mate *through* each other.

**3. The break test reads the RESIDUAL of the UNCONSTRAINED desires, never the
observed gap.** Once a mate is enforced the observed gap is zero by construction,
so a break test on it can never fire and the mate is unbreakable. This is exactly
how physics engines do breakable joints -- PhysX breaks when *"the force required
to MAINTAIN the constraint"* exceeds a threshold, Unity compares against the
REACTION force -- and it needs no physics here at all. See `residual()`.

⭐⭐ A consequence falls out for free: **one hand can never break a mate.** With a
single driver the other object simply follows and the residual is identically zero;
a residual needs TWO independent drivers. So *"the hands pull them apart"* is
literally true, plural, with no new gesture (`4.4` is not built) -- and it is
Guiard's 1987 kinematic chain, where one hand holds the frame and the other acts.

────────────────────────────────────────────────────────────────────────────────
⛔ WHY THIS IS ITS OWN MODULE, AND STDLIB-ONLY

Same reason as `object_extent.py`, and the same shape: the two renderers are kept
deliberately separate (`U6`), neither can host geometry the other needs, so the
maths lives here -- **stdlib only, numpy-free, clock-free, no side effects** -- and
both tools import the one copy (`N6`). That is also the port contract
(`CONSTRAINTS` §2), and it is why `AS1`-`AS4` are NOT blocked on the platform
decision the way `U2` is: nothing here touches a renderer.

⚠ Clock-free: every function that needs time takes `now_ms`, like `hand_state`.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

# ⭐⭐ THE CONSTANTS. Each is a BRACKET, not a derivation -- the shape `V2`'s 0.66
# has. `METHOD.md` forbids a guessed constant; where a bound is not measurable
# today it is stated as unknown and settled live.

# ⭐ FLOOR: 25.41 deg, `F1`'s shipped per-frame orientation-jump p95. Below it the
# mate is refused by the pipeline's OWN noise during an otherwise steady approach.
# ⛔ CEILING: 45 deg, where a cube's ADJACENT face becomes an equally good
# candidate (faces are 90 deg apart). 30 sits just above the floor.
# ⭐⭐ 30 -> 45 deg, riding the same 150 % (the two are one question -- how CLOSE
# and how ALIGNED). 45 deg half-angle IS the owner's **90 deg aperture**.
# ⚠⚠ AND IT IS EXACTLY THE ADJACENT-FACE BOUNDARY: cube normals are 90 deg apart,
# so below 45 deg at most ONE face can qualify and above it TWO do. ⭐ It degrades
# rather than breaks -- `mate_score` still picks the better candidate, so the wrong
# face is not chosen; there are simply two in the running.
MATE_ANGLE_TOL_DEG = 45.0

# The capture sphere, as a fraction of the object's own half-extent -- so it
# derives from the object with NO per-object configuration, the same principle as
# U9's play-area clamp. At today's sizes: 9.0 mm (small) + 18.0 mm (large) =
# 27.1 mm of capture gap, about 0.75x the small cube's 36.1 mm edge.
# ⛔ CEILING: the small object's own edge -- beyond that two objects mate while
# VISIBLY APART.
# ⚠⚠ THE FLOOR IS NOT KNOWN. No measurement exists of how precisely a hand places
# an object here. SETTLE IT LIVE, the way `V2`'s 0.66 and `L1`'s tau were.
# ⭐ DOUBLED 2026-08-28 (owner: *"make the sphere radius for snap twice bigger"*),
# 0.5 -> 1.0. Capture reach is now 36.1 + 36.1 = 72.2 mm for the equal cubes.
# ⚠⚠ THAT EQUALS AN OBJECT'S OWN EDGE (72.2 mm), which was the stated CEILING --
# beyond it two objects mate while visibly apart. At 1.0 it sits exactly ON the
# ceiling: a mate can now pull an object a full cube-width, so watch for a visible
# jump at snap. It is the owner's deliberate maximum, not an oversight.
# ⭐⭐ 1.0 -> 1.5, owner 2026-08-28 after live trial: *"set 150% for snap"*, which
# is the **90 deg cone aperture** they specified (+/-45 deg tilt around the normal).
# Capture reach is now **108.3 mm = 1.50 x an object's own edge**.
# ⚠⚠ THAT IS PAST THE STATED CEILING of one edge, deliberately: two objects can now
# mate while VISIBLY APART, so a snap may pull an object one and a half widths and
# read as a jump. Settled by eye on the slider, which is the project's way of
# settling a number that has no measured floor.
MATE_RADIUS_FRACTION = 1.5

# ⛔ FLOOR: strictly > 1.0, or engage and release share a threshold and the mate
# chatters at 25 deg of jitter. This is the Schmitt trigger, and Creo's second
# threshold angle. At 1.5 the pair separates after ~40.6 mm of pull, about one
# small-cube edge -- legible to a player.
MATE_BREAK_FACTOR = 1.5

# Above `L1`'s MEASURED inter-frame gap (48-64 ms, and it moves with room
# lighting), so no single-frame excursion can toggle a mate. ⭐ A DURATION, not a
# frame count -- `U8`'s reason: a frame count feels twice as long in dim light.
MATE_DWELL_MS = 100.0

_EPS = 1e-12

# Float slack for the `outward` test only, in metres. A perfect mate sits exactly
# at zero, so the test cannot be strict; a nanometre is far below any real
# geometry here (the smaller cube is 36.1 mm) and far above float noise.
_OUTWARD_SLACK_M = 1e-9


# ────────────────────────────────────────────────────────────────────────────
# Vector / quaternion helpers. Deliberately local, stdlib-only copies: this
# module must not depend on a pygame-importing one, and these are closed-form
# identities that cannot drift. The golden vectors pin them against the
# renderers' own versions.
# ────────────────────────────────────────────────────────────────────────────

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    if n < _EPS:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def quat_rotate(q, v):
    """Rotate `v` by unit quaternion `q = (w, x, y, z)`."""
    w, x, y, z = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def quat_from_axis_angle(axis, angle_rad):
    u = _unit(axis)
    if u is None:
        return (1.0, 0.0, 0.0, 0.0)
    h = angle_rad / 2.0
    s = math.sin(h)
    return (math.cos(h), u[0] * s, u[1] * s, u[2] * s)


def quat_mul(a, b):
    """`a` then... no: the rotation `a` APPLIED AFTER `b` (standard Hamilton order)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def quat_normalize(q):
    n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    if n < _EPS:
        return (1.0, 0.0, 0.0, 0.0)
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def quat_from_basis(x_axis, y_axis, z_axis):
    """Unit quaternion for the rotation whose COLUMNS are the given world axes.

    ⚠ Shepperd's method (pick the largest diagonal term) rather than the
    textbook `w`-first form: the latter divides by `w` and loses all precision
    -- or the sign -- at a 180 deg rotation, which a mate reaches routinely
    because anti-parallel normals ARE a half turn.
    """
    m00, m10, m20 = x_axis
    m01, m11, m21 = y_axis
    m02, m12, m22 = z_axis
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        q = ((0.25 * s), (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        q = ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        q = ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        q = ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)
    return quat_normalize(q)


def _orthonormalize(normal, tangent):
    """A right-handed frame `(t, b, n)` from a normal and a rough tangent."""
    n = _unit(normal)
    if n is None:
        return None
    t = _sub(tangent, _scale(n, _dot(tangent, n)))
    t = _unit(t)
    if t is None:
        # The proposed tangent was parallel to the normal; any perpendicular
        # will do, and which one is arbitrary only when roll_order is 0 or 1.
        seed = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
        t = _unit(_sub(seed, _scale(n, _dot(seed, n))))
    b = _cross(n, t)
    return (t, b, n)


# ────────────────────────────────────────────────────────────────────────────
# AS1 -- the data model
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MateConnector:
    """One connection point on an object's surface, in the object's LOCAL frame.

    ⭐ `position`, `normal` and `tangent` are in the mesh's unit-scale local
    coordinates -- the same +/-1 convention `Mesh.vertices` uses -- so a connector
    survives the object being resized or moved in depth, exactly as the mesh does.

    ⛔ `normal` is the TRUE OUTWARD NORMAL. See this module's header.

    `tangent` is the ROLL REFERENCE, and it is what makes a mate Onshape's
    **Fastened** (0 DOF) rather than **Revolute** (1 DOF). Position coincident plus
    aligned normals removes only 5 of 6 degrees of freedom; without a roll
    reference two assembled objects are free to spin against each other, which is
    not what "align them for assembly" means.

    `roll_order` is the symmetry order: 4 for a square face (four indistinguishable
    rolls), 1 for a keyed connector that fits one way only, 0 for a free-spinning
    round peg (the roll is then left wherever the player put it).

    `radius_fraction` scales the capture sphere off the object's OWN half-extent,
    so a new object is capturable the moment it is added with nothing to register
    or precompute -- the same property `U9`'s clamp has.

    `kind` is reserved. v1 is GENDERLESS: any connector may mate any connector.
    The field exists so that adding gendered connectors later is not a schema
    change.
    """
    position: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    tangent: Tuple[float, float, float]
    roll_order: int = 4
    radius_fraction: float = MATE_RADIUS_FRACTION
    kind: str = ""
    name: str = ""


@dataclass(frozen=True)
class ConnectorPose:
    """A connector resolved into world metres: where it is and how it is turned."""
    position: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    tangent: Tuple[float, float, float]
    radius: float


def face_center_connector(vertices, face_vertex_indices, face_normal,
                          roll_order=4, radius_fraction=MATE_RADIUS_FRACTION,
                          name=""):
    """A connector at the CENTROID of a mesh face, oriented by that face's normal.

    ⭐ This is free on today's meshes -- `MeshFace` already carries its own
    `normal` and its vertex indices -- and it is also Onshape's own default
    ("click a face -> the connector lands at the centroid").

    The tangent points from the centroid towards the face's FIRST vertex, which is
    an arbitrary but DETERMINISTIC choice: it must not vary between runs or the
    roll a mate settles into would vary with it.
    """
    pts = [vertices[i] for i in face_vertex_indices]
    if not pts:
        return None
    n = float(len(pts))
    centroid = (sum(p[0] for p in pts) / n,
                sum(p[1] for p in pts) / n,
                sum(p[2] for p in pts) / n)
    unit_normal = _unit(face_normal)
    if unit_normal is None:
        return None
    frame = _orthonormalize(unit_normal, _sub(pts[0], centroid))
    if frame is None:
        return None
    return MateConnector(position=centroid, normal=unit_normal, tangent=frame[0],
                         roll_order=int(roll_order),
                         radius_fraction=float(radius_fraction), name=name)


def world_pose(connector, center_m, orientation, half_extent_m):
    """Resolve a connector into world metres.

    `center_m` is the object's centre in world metres, `orientation` its
    (w,x,y,z) quaternion, `half_extent_m` the metric half-size the unit mesh is
    multiplied by.
    """
    if connector is None or center_m is None or half_extent_m is None:
        return None
    local = _scale(connector.position, float(half_extent_m))
    return ConnectorPose(
        position=_add(center_m, quat_rotate(orientation, local)),
        normal=quat_rotate(orientation, connector.normal),
        tangent=quat_rotate(orientation, connector.tangent),
        radius=float(connector.radius_fraction) * float(half_extent_m),
    )


# ────────────────────────────────────────────────────────────────────────────
# AS2 -- the mate predicate
# ────────────────────────────────────────────────────────────────────────────

def facing_deviation_deg(pose_a, pose_b):
    """How far the two normals are from ANTI-PARALLEL, in degrees. 0 = mated."""
    d = _dot(pose_a.normal, pose_b.normal)
    # ⛔ Anti-parallel is dot == -1, so the deviation is acos(-dot), NOT acos(dot).
    return math.degrees(math.acos(max(-1.0, min(1.0, -d))))


def is_outward(pose_a, pose_b):
    """Has B's connector stayed on A's OUTWARD side, rather than passing through?

    ⛔ Load-bearing. A sphere test is direction-blind, so without this a connector
    that has already passed INSIDE the other object still reads as "close enough"
    and the two mate interpenetrating.

    ⚠⚠ IT IS `>= 0`, NOT `> 0`, AND THAT IS NOT A LOOSENING. **A perfect mate has
    the two connectors exactly coincident**, so the dot product at the target pose
    is exactly zero -- a strict test would refuse the one pose the whole mechanism
    is aiming at. The slack below only absorbs float noise around that exact point.

    ⭐ It is symmetric in practice even though it names `pose_a`: with the normals
    anti-parallel, `dot(pB-pA, nA)` and `dot(pA-pB, nB)` agree, so which connector
    is tested first cannot change the answer.
    """
    return _dot(_sub(pose_b.position, pose_a.position), pose_a.normal) >= -_OUTWARD_SLACK_M


def separation_m(pose_a, pose_b):
    return _norm(_sub(pose_b.position, pose_a.position))


def can_mate(pose_a, pose_b, angle_tol_deg=MATE_ANGLE_TOL_DEG):
    """The predicate, all three clauses. See the module header.

        facing    the normals are anti-parallel within tolerance
        outward   B is on A's outward side
        capture   the two spheres intersect
    """
    if pose_a is None or pose_b is None:
        return False
    if facing_deviation_deg(pose_a, pose_b) > float(angle_tol_deg):
        return False
    if not is_outward(pose_a, pose_b):
        return False
    return separation_m(pose_a, pose_b) <= pose_a.radius + pose_b.radius


def mate_score(pose_a, pose_b, angle_tol_deg=MATE_ANGLE_TOL_DEG):
    """How close this pair is to mating. **Lower is better; <= 1.0 means it mates.**

    ⭐⭐ THE SCORE IS A STRICT GENERALISATION OF `can_mate`, DELIBERATELY. Both
    clauses are normalised by their own threshold and the WORSE one is taken, so
    `max(...) <= 1` is true exactly when both clauses pass. There is therefore no
    second opinion about what is matable — which is `METHOD`'s rule that a
    recomputation is a second implementation that can silently disagree.

    ⭐ It is also what ranks CANDIDATES when more than one mate is in range: the
    best score wins, and only the winner is previewed. That is the **bubble
    cursor**'s principle (Grossman & Balakrishnan, CHI 2005) — dynamically ensure
    exactly one target is selectable, and make which one visible.
    """
    reach = pose_a.radius + pose_b.radius
    lin = separation_m(pose_a, pose_b) / reach if reach > _EPS else float("inf")
    ang = facing_deviation_deg(pose_a, pose_b) / float(angle_tol_deg) \
        if angle_tol_deg > 0 else float("inf")
    return max(lin, ang)


def residual(pose_a, pose_b):
    """(linear_m, angular_deg) between two connectors' DESIRED poses.

    ⛔⛔ THE ONE THING NOT TO GET WRONG: this must be fed the poses each object
    WANTS from its own driver -- its hand, or its parent -- computed BEFORE the
    mate is enforced. Feeding it the enforced poses returns zero forever and the
    mate becomes unbreakable. That is the whole of `AS3`, and it is why this
    function takes poses rather than reading any state itself.
    """
    return (separation_m(pose_a, pose_b), facing_deviation_deg(pose_a, pose_b))


def should_break(pose_a_desired, pose_b_desired,
                 angle_tol_deg=MATE_ANGLE_TOL_DEG,
                 break_factor=MATE_BREAK_FACTOR):
    """Has the residual exceeded the RELEASE threshold?

    ⛔ The release thresholds are deliberately WIDER than the engage ones
    (`MATE_BREAK_FACTOR` > 1). Sharing one threshold with 25 deg of jitter in the
    pipeline is a chatter generator -- Schmitt trigger, and Creo's second
    threshold angle.
    """
    lin, ang = residual(pose_a_desired, pose_b_desired)
    capture = (pose_a_desired.radius + pose_b_desired.radius) * float(break_factor)
    return lin > capture or ang > float(angle_tol_deg) * float(break_factor)


# ────────────────────────────────────────────────────────────────────────────
# AS3 -- the snap transform
# ────────────────────────────────────────────────────────────────────────────

def _roll_candidates(normal, tangent, roll_order):
    if roll_order is None or roll_order <= 0:
        return None                      # free spin -- caller keeps current roll
    step = 2.0 * math.pi / float(roll_order)
    out = []
    for j in range(int(roll_order)):
        q = quat_from_axis_angle(normal, step * j)
        out.append(quat_rotate(q, tangent))
    return out


def snap_pose(parent_pose, child_connector, child_orientation, child_half_extent_m):
    """Where the child must be, and how turned, for its connector to mate.

    Returns `(orientation, center_m)`.

    The construction is the one Onshape describes: **make the two coordinate
    systems coincident**. The child's connector frame is rotated onto a target
    frame built from the parent's -- anti-parallel normal, and a tangent chosen
    from the `roll_order` symmetric candidates as the one NEAREST the child's
    current roll, so snapping never spins the object further than it has to.

    ⭐ With a roll reference this is Onshape's **Fastened** mate: 0 DOF. With
    `roll_order == 0` it degrades to **Revolute** deliberately -- a round peg.
    """
    target_normal = _scale(parent_pose.normal, -1.0)
    current_tangent = quat_rotate(child_orientation, child_connector.tangent)

    candidates = _roll_candidates(parent_pose.normal, parent_pose.tangent,
                                  child_connector.roll_order)
    if candidates is None:
        # Free spin: keep whatever roll the player has, projected onto the plane.
        seed = _sub(current_tangent,
                    _scale(target_normal, _dot(current_tangent, target_normal)))
        target_tangent = _unit(seed)
        if target_tangent is None:
            target_tangent = parent_pose.tangent
    else:
        target_tangent = max(candidates, key=lambda t: _dot(t, current_tangent))

    tgt = _orthonormalize(target_normal, target_tangent)
    loc = _orthonormalize(child_connector.normal, child_connector.tangent)
    if tgt is None or loc is None:
        return (child_orientation, None)

    # R = M_target * M_local^T, built column-wise so no matrix type is needed:
    # M_local^T maps the child's local connector frame onto the canonical axes,
    # and M_target maps those onto the world target frame.
    tt, tb, tn = tgt
    lt, lb, ln = loc
    cols = []
    for axis in range(3):
        e = (lt[axis], lb[axis], ln[axis])          # row `axis` of M_local
        cols.append((tt[0] * e[0] + tb[0] * e[1] + tn[0] * e[2],
                     tt[1] * e[0] + tb[1] * e[1] + tn[1] * e[2],
                     tt[2] * e[0] + tb[2] * e[1] + tn[2] * e[2]))
    orientation = quat_from_basis(cols[0], cols[1], cols[2])

    # The centre follows once the orientation is known: the child's connector must
    # land exactly on the parent's.
    offset = quat_rotate(orientation,
                         _scale(child_connector.position, float(child_half_extent_m)))
    return (orientation, _sub(parent_pose.position, offset))


# ────────────────────────────────────────────────────────────────────────────
# AS4 -- the object tree, and the engage/break state machine
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class MateLink:
    """One live mate. `child` is the SMALLER object, per the owner's rule."""
    parent: object
    child: object
    parent_connector: int
    child_connector: int
    since_ms: float = 0.0
    breaking_since_ms: Optional[float] = None


@dataclass
class Assembly:
    """The object tree: which object is a child of which, and through what.

    ⭐⭐ PARENT AND ROOT ARE TWO DIFFERENT THINGS, and conflating them is the bug
    this class exists to prevent:

        parent  who STORES the relative transform -- the bigger object. Static.
        root    who is currently DRIVEN -- whoever is held. Re-rooted every frame.

    ⛔ Without the second, grabbing the CHILD moves nothing, because the child is
    by definition controlled by its parent. `root_for()` walks the structure from
    whichever node the hand has hold of.
    """
    links: Dict[object, MateLink] = field(default_factory=dict)
    _pending: Dict[Tuple[object, object, int, int], float] = field(default_factory=dict)
    # ⭐⭐ AFTER A BREAK, THAT PAIR MAY NOT RE-MATE UNTIL IT HAS ACTUALLY SEPARATED.
    # ⛔⛔ WITHOUT THIS THERE IS NO SUCH THING AS UN-SNAPPING, and it took four
    # reports to find: a break only requires the two DESIRES to diverge, it never
    # requires the objects to MOVE APART -- so the instant the mate drops they are
    # still touching, `can_mate` is satisfied again, and the dwell re-engages it.
    # The object goes straight back to being a FOLLOWER, whose depth is driven by
    # its parent, which reads exactly as *"I cannot move it on the z axis"*.
    # ⭐ Same shape as `AS6`'s re-grab latch and the same reason -- Buxton: you
    # cannot go from mated to mated, the transition must pass through APART.
    _cooldown: Dict[Tuple[object, object, int, int], float] = field(default_factory=dict)

    # -- structure -------------------------------------------------------
    def parent_of(self, obj_id):
        link = self.links.get(obj_id)
        return link.parent if link else None

    def ancestors(self, obj_id):
        seen, cur = [], self.parent_of(obj_id)
        while cur is not None and cur not in seen:
            seen.append(cur)
            cur = self.parent_of(cur)
        return seen

    def root_for(self, obj_id):
        """The topmost ancestor -- the object whose pose the others hang off."""
        anc = self.ancestors(obj_id)
        return anc[-1] if anc else obj_id

    def children_of(self, obj_id):
        return [cid for cid, link in self.links.items() if link.parent == obj_id]

    def connected(self, obj_id):
        """Every object in `obj_id`'s assembly, root first, parents before children."""
        out, stack = [], [self.root_for(obj_id)]
        while stack:
            node = stack.pop(0)
            if node in out:
                continue
            out.append(node)
            stack.extend(self.children_of(node))
        return out

    def would_cycle(self, parent_id, child_id):
        """⛔ Owner decision 2026-08-28: a mate that would close a CYCLE is REFUSED.

        A loop is not a tree, and reopening a closed chain is a solver's job (the
        CAD literature's 'cut a joint, then paste the cut links'). Refusing is
        correct, cheap and honest; revisit only when a real asset needs a loop.
        """
        # ⚠ The direction is easy to write backwards, and the golden vectors caught
        # it written backwards on their first run. The new link makes `child_id`
        # hang under `parent_id`, so the loop is closed when `parent_id` is
        # ALREADY somewhere below `child_id` — i.e. when `child_id` is `parent_id`
        # itself or one of its ancestors.
        return child_id in ([parent_id] + self.ancestors(parent_id))

    def connector_busy(self, obj_id, connector_index):
        link = self.links.get(obj_id)
        if link and link.child_connector == connector_index:
            return True
        for other in self.links.values():
            if other.parent == obj_id and other.parent_connector == connector_index:
                return True
        return False

    # -- transitions -----------------------------------------------------
    def can_link(self, parent_id, child_id, parent_connector, child_connector):
        if child_id in self.links:
            return False                      # one parent per object -- it is a tree
        if self.would_cycle(parent_id, child_id):
            return False
        if self.connector_busy(parent_id, parent_connector):
            return False
        if self.connector_busy(child_id, child_connector):
            return False
        return True

    def cooling(self, parent_id, child_id, parent_connector, child_connector,
                apart, now_ms, dwell_ms=MATE_DWELL_MS):
        """Is this pair still barred from re-mating after a break? Feed it
        `apart` = "they are now genuinely separated, beyond the BREAK distance".

        ⚠ Coming back together RESETS the dwell rather than banking it, exactly as
        the re-grab latch does: a pair that hovers at the boundary has not parted.
        """
        key = (parent_id, child_id, parent_connector, child_connector)
        if key not in self._cooldown:
            return False
        if not apart:
            self._cooldown[key] = None
            return True
        since = self._cooldown[key]
        if since is None:
            self._cooldown[key] = now_ms
            return True
        if now_ms - since >= dwell_ms:
            del self._cooldown[key]
            return False
        return True

    def offer(self, parent_id, child_id, parent_connector, child_connector,
              satisfied, now_ms, dwell_ms=MATE_DWELL_MS):
        """Feed one candidate pair per frame. Returns True on the frame it engages.

        ⚠ The DWELL is why this is a state machine rather than a predicate: a
        single-frame excursion must not be able to make or break a mate, and the
        threshold is a DURATION so it feels the same at 15 fps and at 30.
        """
        key = (parent_id, child_id, parent_connector, child_connector)
        if not satisfied or not self.can_link(parent_id, child_id,
                                              parent_connector, child_connector):
            self._pending.pop(key, None)
            return False
        started = self._pending.setdefault(key, now_ms)
        if now_ms - started < dwell_ms:
            return False
        self._pending.pop(key, None)
        self.links[child_id] = MateLink(parent=parent_id, child=child_id,
                                        parent_connector=parent_connector,
                                        child_connector=child_connector,
                                        since_ms=now_ms)
        return True

    def offer_break(self, child_id, over_threshold, now_ms, dwell_ms=MATE_DWELL_MS):
        """Feed the break test's verdict per frame. Returns True when it breaks."""
        link = self.links.get(child_id)
        if link is None:
            return False
        if not over_threshold:
            link.breaking_since_ms = None
            return False
        if link.breaking_since_ms is None:
            link.breaking_since_ms = now_ms
            return False
        if now_ms - link.breaking_since_ms < dwell_ms:
            return False
        del self.links[child_id]
        # ⛔ ARM THE COOLDOWN, or the pair re-mates on the very next frame: the two
        # objects are still touching, because breaking measured their DESIRES
        # diverging and not their positions separating.
        self._cooldown[(link.parent, child_id,
                        link.parent_connector, link.child_connector)] = None
        return True

    def unlink(self, child_id, cooldown=True):
        """Drop a mate. ⚠ `cooldown=True` also bars that pair from re-mating until
        the objects have parted -- otherwise an un-snap lasts exactly one frame.
        Pass False only when the caller is about to MOVE the objects apart itself
        (homing does exactly that)."""
        link = self.links.pop(child_id, None)
        if link is not None and cooldown:
            self._cooldown[(link.parent, child_id,
                            link.parent_connector, link.child_connector)] = None

    def clear(self):
        self.links.clear()
        self._pending.clear()
        self._cooldown.clear()


def order_by_size(id_a, size_a, id_b, size_b):
    """(parent, child) -- the BIGGER object parents the smaller.

    ⚠ The tie-break is deterministic on purpose. Equal-sized objects with a
    non-deterministic parent would swap roles between frames and the whole
    hierarchy would chatter. Today's cubes are 2:1 so this cannot bite yet; it is
    written down so it does not have to be rediscovered.
    """
    if size_a > size_b:
        return (id_a, id_b)
    if size_b > size_a:
        return (id_b, id_a)
    return (id_a, id_b) if str(id_a) <= str(id_b) else (id_b, id_a)
