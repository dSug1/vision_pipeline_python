"""M3a -- hard anatomical constraints on a hand pose (merged queue item 1.5).

⚠ PARKED AS A GATE / VALIDITY BIT (2026-08-04, owner decision) -- but KEPT AND
STILL USED: item 1.7 (`hand_skeleton.py`) consumes the joint limits below to
build its constrained skeleton fit. Do not delete this file; deleting it would
only mean rewriting these limits inside 1.7.

**Why the validity bit itself is parked.** It is measurably a superb detector --
0.00% false positives on the control, 92% coverage and 33.8x lift on >60 deg
orientation jumps (spec 0.16) -- but it has no viable CONSUMER:
  * item 1.6 measured that wiring it into the position gate makes results
    WORSE, because 80.8% of position teleports occur on anatomically valid
    frames (a teleport moves every landmark coherently). Different failure
    class; the two do not compose.
  * using it to gate ORIENTATION would repeat 1.6's over-filtering failure in a
    worse form: it flags 33-59% of frames during rotation, so it would reject a
    third to a half of every fast rotation -- legitimate input under the owner's
    stated bar.

So it is a good measurement instrument and a bad gate. It stays available for
analysis, and its CONSTRAINTS live on in 1.7, which CORRECTS poses rather than
rejecting frames and therefore cannot over-filter.

--- original design notes follow ---


Delivers the two things item 1.5 owes the queue:
  (a) a per-frame anatomical VALIDITY BIT, to be consumed by item 1.6's
      consistency gate as one of its cues;
  (b) a BAS-RELIEF DISAMBIGUATION term -- see `unidirectional` below, which is
      the constraint that actually carries that job.

Pure stdlib, numpy-free, no import side effects -- same contract as
`palm_geometry.py` and `hand_identity.py`, so production and the debug tool can
both import this rather than each keeping a copy. Copying a geometry helper is
what caused the 2026-08-01 production-only sign inversion (spec 13.6.1); do not
reintroduce that pattern.


WHERE THE NUMBERS COME FROM, AND WHY NOT FROM THE OBVIOUS PLACE
---------------------------------------------------------------
S6 cites Spurr et al. (ECCV 2020, arXiv 2003.09282), which measures
biomechanical constraints as reducing FreiHAND depth error by 50% versus 15%
without them -- the "halves depth error" claim in the queue, and the reason 1.5
is the primary attack-the-source item.

That paper does NOT publish a table of angle limits. Its limits are FITTED FROM
DATA: the reference implementation (MengHao666/Hand-BMC-pytorch, MIT) ships no
constraint values at all, it generates `bone_len_{min,max}.npy`,
`curvatures_{min,max}.npy`, `PHI_{min,max}.npy` and `CONVEX_HULLS.npy` from RHD,
GANerated, STB and FreiHAND. The MIT licence covers that code, NOT those
datasets, which carry their own research-use terms.

This project is intended for commercial release, so dataset-derived constraint
values are not usable here. Instead:

    * the constraint FORM is taken from the paper (a method, freely usable):
      joint limits, unidirectional flexion, planar articulation;
    * the NUMBERS are clinical goniometry norms -- anatomical facts, unlicensed:
        MCP  flexion 0-90 deg, hyperextension to 45 deg, abduction +-25 deg
        PIP  flexion 0-100 deg, no hyperextension, NO abduction (hinge)
        DIP  flexion 0-80 deg,  no hyperextension, NO abduction (hinge)
      Abduction/adduction occurs ONLY at the MCP joints, never at the
      interphalangeal joints -- that is the planar-articulation constraint, and
      it is an anatomical fact rather than a tuned threshold.

Tolerances below are deliberately GENEROUS. This is a gross-implausibility
detector, not a pose critic: it must fire on reconstructions no hand can adopt,
and essentially never on a real hand held oddly. A validity bit with false
positives is worse than none, because 1.6 would gate away good frames.


WHAT IS AND IS NOT CHIRALITY-DEPENDENT
--------------------------------------
Every constraint here is formulated to be CHIRALITY-FREE -- none of them needs
to know whether this is a left or right hand, and none reads the handedness
label. That is deliberate. The label carried through this pipeline is the
MIRRORED/apparent hand (a physical RIGHT hand is labelled "Left", spec 0.9), the
two code paths reach that convention by different routes, and a sign error there
has already shipped once. A constraint set that never asks cannot get it wrong.

`unidirectional` achieves this by comparing the ROTATION SENSE of successive
bends within one finger against each other, rather than against the palm normal:
a finger curls one way, so consecutive bends must agree in sign, whichever hand
it is. This is also exactly why it disambiguates bas-relief: a depth-mirrored
reconstruction flips the out-of-plane component of the bends, so the senses stop
agreeing, while every 2D projection stays identical.
"""

import math

WRIST = 0

# (mcp, pip, dip, tip) per finger. MediaPipe hand-landmark topology.
FINGERS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
# The thumb is deliberately EXCLUDED. Its CMC joint is a saddle with two coupled
# axes and a far wider, less standardised envelope, so the finger constraints
# below are simply wrong for it -- "no abduction at the IP joint" does not hold
# for a thumb in opposition. The corpus also records the thumb/fingertips as the
# worst-tracked landmarks (bone CV 13-32% distally). Constraining it needs its
# own model; a wrong constraint here would manufacture false positives in
# exactly the frames 1.6 is meant to trust.
THUMB = (1, 2, 3, 4)

# --- clinical limits, degrees (see module docstring for provenance) ---
MCP_FLEXION_MAX = 90.0
MCP_HYPEREXTENSION_MAX = 45.0
MCP_ABDUCTION_MAX = 25.0
PIP_FLEXION_MAX = 100.0
DIP_FLEXION_MAX = 80.0

# --- tolerances (engineering margin on top of the clinical numbers) ---
# Rationale for each, so they are not read as free parameters to tune until the
# corpus goes quiet (that is the "do not tune the gate to make it pass" trap
# recorded against M2 in spec 0.14).
ANGLE_TOLERANCE_DEG = 20.0   # slack on every joint limit: MediaPipe's own mean
                             # 3D error is 1.3-1.5 cm (~15% of a palm), which at
                             # phalanx scale is worth well over 10 deg of joint
                             # angle on its own.
HINGE_TOLERANCE_DEG = 35.0   # out-of-plane slack at PIP/DIP. Large because the
                             # finger plane is ESTIMATED from two noisy bones;
                             # only a gross violation is meaningful.
MIN_BEND_DEG = 15.0          # below this a joint is "straight" and its rotation
                             # axis is numerically meaningless -- cross products
                             # of near-parallel vectors are pure noise. Straight
                             # joints are SKIPPED, never judged.
MIN_BONE_LENGTH = 1e-6       # degenerate/collapsed landmark guard.

# ⭐ THE 21-POINT TOPOLOGY, as index pairs. Anatomy, so it lives here.
# ⚠ It exists because PRODUCTION cannot reach MediaPipe's own
# `solutions.hands.HAND_CONNECTIONS`: the client receives landmarks over a socket
# and does not import mediapipe at all. ⛔ The alternative was hard-coding the
# same 21 pairs inside `CubeWindow.py`, i.e. a second copy of the hand's skeleton
# that could drift from this one (N6: imported, never copied).
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),                 # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),                 # index
    (5, 9), (9, 10), (10, 11), (11, 12),            # middle
    (9, 13), (13, 14), (14, 15), (15, 16),          # ring
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),  # pinky + palm closure
)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v):
    return math.sqrt(_dot(v, v))


def _unit(v):
    n = _norm(v)
    return None if n < MIN_BONE_LENGTH else (v[0] / n, v[1] / n, v[2] / n)


def _angle_between(a, b):
    """Unsigned angle in degrees between two vectors, or None if degenerate."""
    ua, ub = _unit(a), _unit(b)
    if ua is None or ub is None:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(ua, ub)))))


def bend_angles(world_landmarks, finger):
    """Bend angle at MCP, PIP, DIP for one finger. 0 deg == perfectly straight.

    These are UNSIGNED. Direction is handled by `unidirectional`, which needs a
    rotation sense rather than a magnitude.
    """
    mcp, pip, dip, tip = finger
    w = world_landmarks
    metacarpal = _sub(w[mcp], w[WRIST])
    proximal = _sub(w[pip], w[mcp])
    middle = _sub(w[dip], w[pip])
    distal = _sub(w[tip], w[dip])
    return (_angle_between(metacarpal, proximal),
            _angle_between(proximal, middle),
            _angle_between(middle, distal))


def unidirectional(world_landmarks, finger):
    """Do the successive bends of this finger agree in rotation sense?

    THE BAS-RELIEF TERM. A finger curls one way: the rotation carrying the
    metacarpal onto the proximal phalanx, the proximal onto the middle, and the
    middle onto the distal must all turn about axes pointing the same way. The
    axis of each is the cross product of the two bones it joins, so agreement is
    just a positive dot product between successive axes.

    Returns (ok, dot). `dot` is a cosine-like agreement score in [-1, 1]:
    negative means the DIP bends backwards relative to its own PIP, which no
    hand can do.

    ⚠ THE PIP<->DIP PAIR ONLY -- the MCP IS DELIBERATELY EXCLUDED, and this is a
    correction of a real error rather than a simplification. The first version
    required all three joints of a finger to agree, and that fired on 93.7% of
    the `static_hold` CONTROL take. Diagnosis (analysis/m3a_diagnose.py):

        dot(MCP axis, PIP axis)   31.1% NEGATIVE   <- on valid, still hands
        dot(PIP axis, DIP axis)    0.0% NEGATIVE   min +0.41, p05 +0.69

    The MCP is a condyloid joint that extends (indeed hyperextends to ~45 deg)
    while the interphalangeal joints flex -- an ordinary resting hand posture,
    which legitimately reverses the MCP axis against the IP axes. Only the IP
    joints are obligate co-flexors. The measured margin on the surviving pair is
    enormous: worst observed +0.41 against a threshold of 0.0.

    Joints bent less than MIN_BEND_DEG are skipped -- their axis is the cross
    product of near-parallel vectors, i.e. noise. If either is straight there is
    nothing to compare and this returns (True, None): unjudged, NOT
    judged-and-passed.
    """
    mcp, pip, dip, tip = finger
    w = world_landmarks
    proximal = _sub(w[pip], w[mcp])
    middle = _sub(w[dip], w[pip])
    distal = _sub(w[tip], w[dip])

    pip_bend = _angle_between(proximal, middle)
    dip_bend = _angle_between(middle, distal)
    if (pip_bend is None or pip_bend < MIN_BEND_DEG
            or dip_bend is None or dip_bend < MIN_BEND_DEG):
        return True, None

    pip_axis = _unit(_cross(proximal, middle))
    dip_axis = _unit(_cross(middle, distal))
    if pip_axis is None or dip_axis is None:
        return True, None

    d = _dot(pip_axis, dip_axis)
    return d >= 0.0, d


def hinge_violation(world_landmarks, finger):
    """How far out of its own flexion plane does the distal phalanx bend?

    The DIP is a hinge: it flexes only in the plane the finger is already
    bending in. That plane is defined here by the PROXIMAL and MIDDLE phalanges,
    and the DISTAL phalanx is tested against it.

    ⚠ The plane was originally taken from the metacarpal and the proximal
    phalanx. That is badly conditioned: the MCP bend has a median of only ~14
    deg on a resting hand, so the two vectors are near-parallel and their cross
    product is dominated by noise. Measured on the `static_hold` control
    (analysis/m3a_diagnose.py):

        plane from metacarpal x proximal : median 25.5 deg, max 43.6 deg
        plane from proximal  x middle    : median 11.5 deg, max 19.4 deg

    The second is the same anatomy expressed through better-conditioned
    geometry, and it leaves real headroom under HINGE_TOLERANCE_DEG instead of
    sitting on top of it.

    Returns the out-of-plane angle in degrees, or None if the finger is too
    straight for the plane to be defined.
    """
    mcp, pip, dip, tip = finger
    w = world_landmarks
    proximal = _sub(w[pip], w[mcp])
    middle = _sub(w[dip], w[pip])
    distal = _sub(w[tip], w[dip])

    pip_bend = _angle_between(proximal, middle)
    if pip_bend is None or pip_bend < MIN_BEND_DEG:
        return None
    normal = _unit(_cross(proximal, middle))
    u = _unit(distal)
    if normal is None or u is None:
        return None
    # angle between the bone and the plane == 90deg - angle to the plane normal
    return abs(90.0 - math.degrees(
        math.acos(max(-1.0, min(1.0, _dot(u, normal))))))


def mcp_abduction(world_landmarks, finger, palm_normal):
    """MCP side-to-side deviation, in degrees, out of the palm plane's sagittal
    direction. Needs the palm normal because abduction is defined relative to
    the palm, not to the finger.
    """
    mcp, pip, _dip, _tip = finger
    proximal = _unit(_sub(world_landmarks[pip], world_landmarks[mcp]))
    if proximal is None or palm_normal is None:
        return None
    metacarpal = _unit(_sub(world_landmarks[mcp], world_landmarks[WRIST]))
    if metacarpal is None:
        return None
    # Abduction axis: within the palm plane, perpendicular to the finger's own
    # long axis. Deviation along it is abduction; deviation along the palm
    # normal is flexion and must not be counted here.
    side = _unit(_cross(palm_normal, metacarpal))
    if side is None:
        return None
    return abs(math.degrees(math.asin(max(-1.0, min(1.0, _dot(proximal, side))))))


def palm_normal(world_landmarks):
    """Unit normal of the palm plane, from the wrist/index-MCP/pinky-MCP triangle.

    Sign is chirality-dependent and therefore MEANINGLESS on its own -- it is
    used here only for the abduction axis, which is symmetric in sign.
    """
    w = world_landmarks
    return _unit(_cross(_sub(w[5], w[WRIST]), _sub(w[17], w[WRIST])))


def evaluate(world_landmarks):
    """Full M3a evaluation of one hand's 21 world landmarks.

    Returns a dict:
        valid          bool   -- the per-frame validity bit for item 1.6
        violations     list   -- human-readable strings, one per broken rule
        n_violations   int
        worst_sense    float  -- worst unidirectional agreement (None if unjudged)
        detail         dict   -- per-finger measurements, for analysis/tuning

    Never raises on degenerate input: a hand it cannot evaluate comes back
    valid=True with an empty violation list, because "unjudgeable" must not be
    reported as "anatomically impossible".
    """
    if world_landmarks is None or len(world_landmarks) < 21:
        return {"valid": True, "violations": [], "n_violations": 0,
                "worst_sense": None, "detail": {}}

    w = [tuple(p) for p in world_landmarks]
    n = palm_normal(w)
    violations = []
    detail = {}
    worst_sense = None

    for name, finger in FINGERS.items():
        mcp_a, pip_a, dip_a = bend_angles(w, finger)
        sense_ok, sense = unidirectional(w, finger)
        hinge = hinge_violation(w, finger)
        abd = mcp_abduction(w, finger, n)

        detail[name] = {"mcp": mcp_a, "pip": pip_a, "dip": dip_a,
                        "sense": sense, "hinge": hinge, "abduction": abd}

        if sense is not None:
            worst_sense = sense if worst_sense is None else min(worst_sense, sense)
        if not sense_ok:
            violations.append(f"{name}: DIP bends against its PIP (sense {sense:+.2f})")

        if mcp_a is not None and mcp_a > MCP_FLEXION_MAX + MCP_HYPEREXTENSION_MAX + ANGLE_TOLERANCE_DEG:
            violations.append(f"{name}: MCP bend {mcp_a:.0f} deg")
        if pip_a is not None and pip_a > PIP_FLEXION_MAX + ANGLE_TOLERANCE_DEG:
            violations.append(f"{name}: PIP bend {pip_a:.0f} deg")
        if dip_a is not None and dip_a > DIP_FLEXION_MAX + ANGLE_TOLERANCE_DEG:
            violations.append(f"{name}: DIP bend {dip_a:.0f} deg")
        if hinge is not None and hinge > HINGE_TOLERANCE_DEG:
            violations.append(f"{name}: IP chain {hinge:.0f} deg out of plane")
        if abd is not None and abd > MCP_ABDUCTION_MAX + ANGLE_TOLERANCE_DEG:
            violations.append(f"{name}: MCP abduction {abd:.0f} deg")

    return {"valid": not violations, "violations": violations,
            "n_violations": len(violations), "worst_sense": worst_sense,
            "detail": detail}
