"""The BLOCK REPRESENTATION of a hand (queue item B1, spec GESTURE_PIPELINE §16).

Owner design, 2026-08-04: for the GRAB, ROTATE and TRANSLATE signals the hand is
six blocks -- the palm as one transform, and each finger as an ARC with a single
"how bent" scalar. Not 21 independent landmarks.

    palm    : 2D position (px), rotation quaternion, scale (palm width px)
    fingers : one arc-extension scalar each

⭐ WHY, AND THE MEASUREMENTS THAT BACK IT (both predate the idea):

    "the palm is one block"     palm rigidity 2.76 mm, already at target,
                                against 13-32% CV on distal bones      (spec 0.2)
    "a finger is an arc"        dot(PIP axis, DIP axis) 0.0% NEGATIVE over
                                ~29,000 hand-frames, min +0.41         (spec 0.16)

The second is the decisive one: PIP and DIP always co-flex, so a finger's bend is
essentially ONE degree of freedom, not three, with a large empirical margin. The
arc scalar is that degree of freedom. This is postural synergies (queue 5.1 /
M3b) in a structured, interpretable form.

SCOPE -- deliberately narrow (owner):
  * GRAB / ROTATE / TRANSLATE only. Future gestures may legitimately need raw
    landmarks, and the landmark stream stays available untouched.
  * ⚠ THE THUMB IS NOT AN ARC. Its CMC is a saddle joint with two coupled axes,
    so "more or less bent" does not describe opposition -- the same reason M3a
    excluded it. `thumb_landmarks` carries it RAW, unmodelled, pending a
    decision.
  * This is a DERIVED VIEW. It computes from landmarks and changes nothing:
    no pipeline change, no wire-protocol change, no production behaviour.

PORT CONTRACT: stdlib only, no numpy, no side effects, deterministic -- the same
contract as `palm_geometry.py` / `hand_identity.py`. Golden vectors before the
port exists (the U3 discipline that caught a banker's-vs-half-up rounding
divergence). Everything here is arithmetic available in any target language.
"""

import math

WRIST = 0
INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 5, 9, 17
PALM_LANDMARKS = (0, 5, 9, 13, 17)
THUMB_LANDMARKS = (1, 2, 3, 4)

# (mcp, pip, dip, tip). The thumb is deliberately absent -- see the scope note.
ARC_FINGERS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm3(v):
    return math.sqrt(_dot(v, v))


def _unit(v):
    n = _norm3(v)
    return None if n < 1e-9 else (v[0] / n, v[1] / n, v[2] / n)


# --------------------------------------------------------------------------
# Palm block
# --------------------------------------------------------------------------
def palm_position(pixel_landmarks):
    """Centroid of the rigid palm landmarks, in pixels.

    Defined locally rather than imported from `hand_identity` (which lives in
    the SERVER's Resources, across the socket) -- the same situation
    `frame_gate.py` documented. `analysis/b2_block_separability.py` verifies
    this against hand_identity's version, so the two cannot silently diverge.
    """
    try:
        pts = [pixel_landmarks[i] for i in PALM_LANDMARKS]
    except (IndexError, TypeError):
        return None
    return (sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts))


def palm_scale(pixel_landmarks):
    """Apparent palm width in pixels: the index-MCP to pinky-MCP span.

    The documented anchor of choice for scale (spec 10.1): near pose-invariant,
    and the most rigid quantity on the hand. ⚠ It COLLAPSES when the hand yaws
    edge-on -- see GESTURE_PIPELINE 14.3.1 for the multi-anchor answer that
    Z-axis work will need. For block-level outlier work its collapse is itself
    a useful signal.
    """
    try:
        a, b = pixel_landmarks[INDEX_MCP], pixel_landmarks[PINKY_MCP]
    except (IndexError, TypeError):
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palm_frame(world_landmarks):
    """Orthonormal palm frame by Gram-Schmidt, and its conditioning.

    Deliberately the SAME construction the shipped rotation path uses -- e1 from
    the knuckle row, e2 from wrist->middle-MCP orthogonalised against it. M6b's
    SVD alternative was measured as a 2.1x REGRESSION (spec 0.12); do not
    "improve" this to a least-squares fit.

    Returns (e1, e2, e3, conditioning) or None if degenerate.
    """
    w = world_landmarks
    e1 = _unit(_sub(w[PINKY_MCP], w[INDEX_MCP]))
    if e1 is None:
        return None
    v2 = _sub(w[MIDDLE_MCP], w[WRIST])
    v2o = _sub(v2, tuple(c * _dot(v2, e1) for c in e1))
    cond = _norm3(v2o)
    e2 = _unit(v2o)
    if e2 is None:
        return None
    return e1, e2, _cross(e1, e2), cond


def _mat_to_quat(e1, e2, e3):
    m00, m10, m20 = e1
    m01, m11, m21 = e2
    m02, m12, m22 = e3
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = (0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        q = ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        q = ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        q = ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)
    n = math.sqrt(sum(c * c for c in q))
    return (1.0, 0.0, 0.0, 0.0) if n < 1e-12 else tuple(c / n for c in q)


def palm_quaternion(world_landmarks):
    f = palm_frame(world_landmarks)
    return None if f is None else _mat_to_quat(f[0], f[1], f[2])


def quat_angle_between(qa, qb):
    """Angle in degrees between two orientations, sign-continuity handled."""
    if qa is None or qb is None:
        return None
    d = abs(sum(a * b for a, b in zip(qa, qb)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


# --------------------------------------------------------------------------
# Finger arcs
# --------------------------------------------------------------------------
def finger_extension(world_landmarks, finger):
    """The ARC DEPLOYMENT scalar: 1.0 = straight, smaller = more curled.

    Chord over contour -- the straight-line MCP->TIP distance divided by the
    summed phalanx lengths:

        extension = |tip - mcp| / (|pip-mcp| + |dip-pip| + |tip-dip|)

    Chosen over "sum of joint angles" for three reasons:
      * SCALE-FREE by construction, so it does not need a palm-width division
        and cannot inherit palm width's edge-on collapse;
      * computed in WORLD space, so it is view-independent -- a straight finger
        pointing at the camera reads as straight, whereas a 2D version would
        read it as fully curled;
      * per-landmark noise partially CANCELS between numerator and denominator,
        which matters because these are the 13-32% CV landmarks.

    Returns None if the finger is degenerate. Values slightly above 1.0 are
    possible from landmark noise on a hyper-extended finger and are NOT clamped
    -- clamping would hide exactly the excursions this feeds.
    """
    try:
        mcp, pip, dip, tip = finger
        w = world_landmarks
        chord = _norm3(_sub(w[tip], w[mcp]))
        contour = (_norm3(_sub(w[pip], w[mcp]))
                   + _norm3(_sub(w[dip], w[pip]))
                   + _norm3(_sub(w[tip], w[dip])))
    except (IndexError, TypeError):
        return None
    return None if contour < 1e-9 else chord / contour


def arc_vector(world_landmarks):
    """The four arc scalars in a fixed order: index, middle, ring, pinky."""
    return tuple(finger_extension(world_landmarks, f)
                 for f in ARC_FINGERS.values())


def arc_distance(a, b):
    """Largest per-finger change between two arc vectors.

    MAX rather than mean, deliberately: a single finger being re-estimated onto
    a different hand is the signal of interest, and a mean over four fingers
    would dilute it by 4x.
    """
    if a is None or b is None:
        return None
    vals = [abs(x - y) for x, y in zip(a, b) if x is not None and y is not None]
    return max(vals) if vals else None


# --------------------------------------------------------------------------
# The assembled state
# --------------------------------------------------------------------------
def block_state(pixel_landmarks, world_landmarks):
    """Full block view of one hand. Never raises; missing pieces come back None.

    Returns a dict:
        position    (x, y) px      palm centroid
        scale       px             palm width
        quaternion  (w,x,y,z)      palm orientation
        conditioning float         palm-frame conditioning (low = degenerate)
        arcs        4-tuple        index/middle/ring/pinky extension
        thumb       4 raw landmarks, UNMODELLED by owner decision
    """
    if pixel_landmarks is None or world_landmarks is None:
        return None
    if len(pixel_landmarks) < 21 or len(world_landmarks) < 21:
        return None
    w = [tuple(p) for p in world_landmarks]
    f = palm_frame(w)
    return {
        "position": palm_position(pixel_landmarks),
        "scale": palm_scale(pixel_landmarks),
        "quaternion": None if f is None else _mat_to_quat(f[0], f[1], f[2]),
        "conditioning": None if f is None else f[3],
        "arcs": arc_vector(w),
        "thumb": tuple(tuple(pixel_landmarks[i]) for i in THUMB_LANDMARKS),
    }
