# -*- coding: utf-8 -*-
"""⭐⭐ `RB3` — ORIENTATION. Horn over the palm, in the corrected frame. Nothing else.

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`.
Branch `1.7.42-`.

⛔ WHAT THIS DELIBERATELY IS NOT. No smoothing, no predictive filter, no lean trim,
no fingertip trim, no per-axis gain, no window. `1.7.42` strips those and rebuilds
each one ONLY when a measurement asks for it (spec §6). The 2026-08-29 stack was
locally reasonable at every layer and a REFLECTION as a whole; this module exists so
there is a layer with nothing hidden in it.

⭐ `horn_rotation` is IMPORTED, never re-derived (`N6`). It is exact to 0.000 deg on
synthetic input and four estimator replacements have died against it under `A10`.
The rebuild is about the FRAME and the CONTROL LAW; the fit was never the problem.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE ONE TRAP THIS MODULE MUST NOT REPEAT: THE DOUBLE COVER

`q` and `-q` are the SAME rotation, and a least-squares fit returns whichever sign
its eigenvector carries. On 2026-08-29 that made `lean_trim.twist_angle_deg` read a
15 deg turn as -345 deg, which drove a correction to full strength on gestures that
must receive none -- and it survived every suite because the suite's own helper knew
about the double cover and never fed one IN.

⭐ So: every quaternion leaving this module is canonicalised to `w >= 0`, and
`verify_frame_signs` feeds negated inputs to prove it.

⚠ `RELATIVE ROTATIONS ONLY.` The absolute orientation of a hand in the camera frame
is not a thing this pipeline needs or can validate; what the object follows is the
CHANGE. `delta` is therefore the primary entry point and `freeze` merely names the
reference it is measured from.

PORT CONTRACT (`CONSTRAINTS` §2): stdlib only, no numpy, CLOCK-FREE.
"""
import math

from . import hand_frame
from .palm_rotation import horn_rotation

# ⭐ The five palm landmarks. ⛔ NOT the fingertips: a 9-point palm+tips
# constellation was measured on 2026-08-23 to buy +1.4 deg of axis for +4.9 deg of
# p95 jitter and was `A10`-REJECTED. The tips move relative to the palm -- that is
# articulation, not hand rotation -- and `F1` uses them for the grip POINT, which is
# a different question.
PALM = hand_frame.PALM

IDENTITY = (1.0, 0.0, 0.0, 0.0)


def _canon(q):
    """`w >= 0`. See the header: this is the double cover, and it is load-bearing."""
    if q is None:
        return None
    return q if q[0] >= 0.0 else tuple(-c for c in q)


def _qmul(p, q):
    w1, x1, y1, z1 = p
    w2, x2, y2, z2 = q
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def palm_points(world_landmarks, mount=None):
    """The five palm points, in the USER's frame. `None` if the input is unusable.

    ⭐ THE VIEWPOINT IS APPLIED HERE AND NOWHERE ELSE IN THIS MODULE. One call, one
    frame -- which is the whole point of `1.7.42`: `V1` corrected the orientation
    and left chirality, depth and occlusion in the old frame, and that hybrid is
    what produced a reflection."""
    if world_landmarks is None or len(world_landmarks) < 21:
        return None
    pts = hand_frame.to_user_frame(world_landmarks, mount=mount)
    return [pts[i] for i in PALM]


def freeze(world_landmarks, mount=None):
    """Name a reference pose. Returns an opaque state, or `None` if degenerate."""
    p = palm_points(world_landmarks, mount)
    return None if p is None else {"ref": p}


def delta(state, world_landmarks, mount=None):
    """The rotation from the reference pose to this one. Canonicalised.

    ⚠ NO SEED / NO CONTINUITY ARGUMENT, deliberately. `palm_rotation.Horn` carries a
    `seed` so successive fits keep a consistent sign; that is the right thing for a
    filtered stream and it hides the double cover from the caller. Here the answer
    is canonical on its own, so a caller cannot accidentally depend on history."""
    if state is None:
        return None
    p = palm_points(world_landmarks, mount)
    if p is None:
        return None
    return _canon(horn_rotation(state["ref"], p))


def between(world_a, world_b, mount=None):
    """Rotation taking pose A to pose B. Convenience; same maths as `delta`."""
    a = palm_points(world_a, mount)
    b = palm_points(world_b, mount)
    if a is None or b is None:
        return None
    return _canon(horn_rotation(a, b))


def compose(first, second):
    """Apply `first`, then `second`. ⚠ Left-multiplication: both are world-frame."""
    if first is None or second is None:
        return None
    return _canon(_qmul(second, first))


def rotvec_deg(q):
    """(pitch, yaw, roll) in degrees, about x, y, z. Shortest arc.

    ⚠ The three components are independent only for SMALL rotations. That is exact
    enough for a per-frame increment (0.3-2.4 deg measured) and NOT for an absolute
    pose -- do not read a large rotation component-wise and call it an Euler angle.
    ⛔ `M6a` / queue `1.3`: no Euler in the estimation path."""
    return hand_frame.rotvec_deg(q) if q is not None else (0.0, 0.0, 0.0)


def from_rotvec_deg(v):
    """`(x, y, z)` degrees about the axes -> quaternion. ⭐ The inverse of `rotvec_deg`.

    ⚠ It lives HERE, beside its inverse, and not in the one module that happens to
    call it: a log map and an exp map in different files drift apart, and this pair
    is the whole arithmetic of `RB5`'s control law (`N6`)."""
    ang = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if ang < 1e-12:
        return IDENTITY
    half = math.radians(ang) * 0.5
    s = math.sin(half) / ang
    return _canon((math.cos(half), v[0] * s, v[1] * s, v[2] * s))


def angle_deg(q):
    """Total rotation magnitude, degrees. Stable near identity."""
    if q is None:
        return 0.0
    w, x, y, z = _canon(q)
    n = math.sqrt(x * x + y * y + z * z)
    return math.degrees(2.0 * math.atan2(n, w))
