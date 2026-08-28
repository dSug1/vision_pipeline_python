"""⭐⭐ THE YAW LEAN, TRIMMED AT THE QUATERNION -- swing/twist, two gains, no table.

Owner, 2026-08-28: *"can I just introduce a matrix multiplicator M(current
quaternion rotation): at the moment of grab, the multiplication is reset to
identity. Then, according to the value of quaternion rotation on each of the 4
quaternion axis, the multiplicator M multiplies the current quaternion to correct
the bias."*

⭐ THE ARCHITECTURE IS TEXTBOOK AND THE LITERATURE NAMES IT. Correcting an
attitude by MULTIPLYING a small correction quaternion onto a nominal estimate --
rather than adding to it -- is the **multiplicative error quaternion** of the
**MEKF (Multiplicative Extended Kalman Filter)**, the standard method in satellite
attitude determination and inertial navigation, chosen for exactly the reason it is
right here: a multiplicative update preserves the unit-norm constraint, where an
additive one does not. "Reset to identity at grab" is the same nominal-state +
multiplicative-correction split, and it composes cleanly with the cube's rotation
already being grab-relative.

────────────────────────────────────────────────────────────────────────────────
⛔ WHAT THE LITERATURE CHANGED: SWING/TWIST, NOT AXIS-COMPONENT SCALING

The first draft scaled the rotation AXIS's off-vertical components and
renormalised. That is ad-hoc. The standard tool is **swing-twist decomposition**:

    q  =  q_swing  ⊗  q_twist          twist = rotation about the chosen axis
                                        swing = everything else, axis ⊥ twist

Factor about the VERTICAL and the split IS the question: the **twist is the yaw**
the operator asked for, and the **swing is precisely the contamination**. Trimming
the swing while leaving the twist untouched preserves the turn AMOUNT exactly --
which matters, because `ORIENTATION_DIAGNOSIS.md` measured the amount as already
fine (gain 1.13) and the UPRIGHTNESS as the thing that fails.

⭐ It also disposes of a real flaw in the first draft for free. Scaling axis
components would damp a GENUINE roll, because a pure roll has large off-vertical
components too. Under swing/twist a pure roll has **no twist**, so ramping the
correction on `|twist|` leaves real roll and pitch untouched by construction.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ WHY THIS IS NOT THE FOURTH ATTEMPT `REJECTED.md` FORBIDS

The gate: *"demonstrate a per-frame orientation jump at or under shipped Horn's on
a GRABBING take BEFORE quoting a lean number."* Three 2-D-shape estimators scored
BETTER on the lean and WORSE on the tail, and the tail decided every verdict.

⛔ **Their flaw was VARIANCE, and it came from their INPUT.** Each derived its
correction from a noisy 2-D shape feature -- `σ` jitters 0.11 p95 on a GRIPPING
hand, against a curve that is steepest exactly where `σ` is highest.

⭐ **This reads no new signal at all.** It is a smooth, deterministic function of
the quaternion Horn already produced and `L1` already smoothed (τ = 20 ms). It adds
no noise source; it reshapes a stable one. Two frames that produced nearly equal
quaternions produce nearly equal corrections -- that is the whole difference.

⚠ THAT IS AN ARGUMENT, NOT A MEASUREMENT. The gate still has to be cleared with
`analysis/lean_trim_ab.py` on a grabbing take before any lean number is quoted.

────────────────────────────────────────────────────────────────────────────────
⭐ WHY TWO GAINS AND NO DEPTH TERM -- both measured, not assumed
(`analysis/lean_decomposition.py`, 7511 yaw-like frames over four takes)

    nx  toward PITCH   mean +0.375   mean|.| 0.431   one-directional bias (0.87)
    nz  toward ROLL    mean +0.300   mean|.| 0.323   one-directional bias (0.93)

* **Both axes are contaminated**, pitch ~1.3x roll -> they need SEPARATE gains.
* **Both are one-directional BIASES relative to the turn direction**, not symmetric
  noise -> a deterministic correction can remove them. This is the finding that
  makes the whole approach viable.
* ⛔ **NO depth term.** Binned WITHIN each take, the four takes DISAGREE on the
  sign of the trend for both axes. ⚠ An earlier pass of that harness pooled the
  takes and THEN binned, which confounds depth with take identity, and duly
  reported roll as depth-dependent on numbers that were not even monotone.

Stdlib only, numpy-free, clock-free (`CONSTRAINTS` §2). Golden vectors:
`analysis/verify_lean_trim.py`.
"""

import math

# The axis the twist is taken about: the image vertical. ⚠ MediaPipe's world y
# points DOWN, which does not matter here -- the twist axis is a line, and both
# gains are signed by the owner's eye anyway.
TWIST_AXIS = (0.0, 1.0, 0.0)

# ⛔ BOTH GAINS DEFAULT TO 0.0 -- bit-identical to shipped Horn, by construction and
# not by hope: at gain 0 the corrected swing IS the swing and the function returns
# its input unchanged. Every A10 baseline and `parity_replay` run stays valid.
GAIN_PITCH = 0.66
GAIN_ROLL = 0.66

# ⛔⛔ REPLACED 2026-08-28, THE DAY IT WAS BUILT, AND THE OWNER FOUND THE FLAW.
# The first version faded in on the TWIST MAGNITUDE alone (`min(1, |twist|/15deg)`).
# It passed its golden vectors -- which used MATHEMATICALLY PURE pitch and roll,
# where the twist is exactly zero. A real hand never produces that: a pitch gesture
# carries incidental yaw, so it cleared the 15 deg ramp and had its ENTIRE swing --
# which for a mostly-pitch rotation is nearly the whole rotation -- scaled down.
# Owner: *"pitch and roll are heavily damped as a consequence."*
#
# ⭐ THE FIX IS TO ASK A RATIO, NOT A MAGNITUDE: how much of THIS rotation is yaw?
#
#     r = |twist| / (|twist| + |swing|)      0 = pure pitch/roll, 1 = pure yaw
#
# MEASURED over 9880 rotating frames on four grabbing takes: yaw-dominant frames
# sit at r = 0.805, pitch/roll-dominant frames at r = 0.191. The populations barely
# overlap, so a ramp between them separates the two gestures cleanly.
DOMINANCE_LO = 0.35        # at/below: a pitch or roll gesture -- correct NOTHING
DOMINANCE_HI = 0.65        # at/above: a turn -- correct in full

# ⚠ Below this total rotation the axis is noise, so the ratio is meaningless and
# the correction stays at exactly 0. Same defect an earlier A/B hit by measuring
# axis direction on a near-identity rotation (`REJECTED.md`).
MIN_TOTAL_DEG = 5.0

# ⛔⛔ THE OWNER ASKED WHETHER THE HAND RATIOS FROM THE SIX `T6` TAKES COULD DRIVE
# THIS INSTEAD. MEASURED, AND THE ANSWER IS NO -- `edge_on_measure` (T6's one
# scale-free survivor) separates the two gestures by **0.078** where the twist ratio
# separates them by **0.613**, and it is **1.6x noisier** per frame at p95. It is
# worse on both axes that matter. ⭐ And it is a 2-D SHAPE feature, which is the
# exact class whose VARIANCE killed the three estimators in `REJECTED.md`; the twist
# ratio reads only the quaternion, so it adds no new noise source at all.


def _qmul(p, q):
    w1, x1, y1, z1 = p
    w2, x2, y2, z2 = q
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def _qnorm(q):
    n = math.sqrt(sum(c * c for c in q))
    return (1.0, 0.0, 0.0, 0.0) if n < 1e-12 else tuple(c / n for c in q)


def swing_twist(q, axis=TWIST_AXIS):
    """Factor `q` into `(swing, twist)` with `q == swing ⊗ twist`.

    `twist` is the rotation about `axis`; `swing`'s axis is perpendicular to it.
    The construction is the standard one: project the quaternion's vector part onto
    the axis, renormalise that as the twist, and take the swing as what is left.

    ⚠ SINGULAR CASE, HANDLED RATHER THAN IGNORED: when the vector part is entirely
    perpendicular to the axis AND the scalar part is 0 (a 180 deg swing), the twist
    is undefined. The identity twist is returned, which makes `swing == q` -- the
    honest answer, and one that leaves `trim` a no-op there rather than guessing."""
    w, x, y, z = q
    ax, ay, az = axis
    d = x * ax + y * ay + z * az
    tw = (w, ax * d, ay * d, az * d)
    if sum(c * c for c in tw) < 1e-18:
        return q, (1.0, 0.0, 0.0, 0.0)
    twist = _qnorm(tw)
    swing = _qmul(q, _qconj(twist))
    return swing, twist


def _to_rotvec(q):
    """Quaternion -> rotation vector (axis * angle, radians), shortest arc."""
    w, x, y, z = _qnorm(q)
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    ang = 2.0 * math.atan2(n, w)
    return (x / n * ang, y / n * ang, z / n * ang)


def _from_rotvec(v):
    ang = math.sqrt(sum(c * c for c in v))
    if ang < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    s = math.sin(ang / 2.0) / ang
    return (math.cos(ang / 2.0), v[0] * s, v[1] * s, v[2] * s)


def twist_angle_deg(q, axis=TWIST_AXIS):
    """Signed rotation about `axis`, in degrees -- the yaw the operator asked for."""
    _, twist = swing_twist(q, axis)
    w, x, y, z = twist
    d = x * axis[0] + y * axis[1] + z * axis[2]
    return math.degrees(2.0 * math.atan2(d, w))


def swing_deg(q, axis=TWIST_AXIS):
    """Magnitude of the swing -- how far off a pure twist this rotation is."""
    v = _to_rotvec(swing_twist(q, axis)[0])
    return math.degrees(math.sqrt(sum(c * c for c in v)))


def yaw_dominance(q, axis=TWIST_AXIS):
    """0..1 -- the fraction of this rotation that is TWIST rather than swing.

    ⭐ This is the whole discriminator: a turn reads ~0.8, a pitch or roll gesture
    reads ~0.2, and it costs one extra decomposition of a quaternion the caller
    already has."""
    tw = abs(twist_angle_deg(q, axis))
    sw = swing_deg(q, axis)
    if tw + sw < MIN_TOTAL_DEG:
        return 0.0
    return tw / (tw + sw)


def authority(q, lo=None, hi=None, axis=TWIST_AXIS):
    """0..1 -- how much correction this rotation has earned.

    0 for a pitch or roll gesture (nothing is damped), 1 for a turn, ramped
    between. ⛔ Deliberately NOT a function of any 2-D shape feature: measured
    worse at separating AND noisier (see the header)."""
    lo = DOMINANCE_LO if lo is None else lo
    hi = DOMINANCE_HI if hi is None else hi
    r = yaw_dominance(q, axis)
    if hi <= lo:
        return 1.0 if r >= hi else 0.0
    return max(0.0, min(1.0, (r - lo) / (hi - lo)))


def trim(q, gain_pitch=None, gain_roll=None, axis=TWIST_AXIS):
    """The corrected rotation: trim the SWING, leave the TWIST exact.

    `q` is the grab-relative rotation (identity at the grab, so the correction is
    identity there too -- the owner's reset requirement is satisfied by the input,
    not by extra state). Returns a unit quaternion.

    ⛔ gains 0 -> returns `q` UNCHANGED, and the early return makes that exact
    rather than merely arithmetically-equal."""
    gp = GAIN_PITCH if gain_pitch is None else gain_pitch
    gr = GAIN_ROLL if gain_roll is None else gain_roll
    if q is None or (gp == 0.0 and gr == 0.0):
        return q
    swing, twist = swing_twist(q, axis)
    w = authority(q, axis=axis)
    sx, sy, sz = _to_rotvec(swing)
    # ⚠ `sy` is ~0 by construction (the swing axis is perpendicular to the twist
    # axis). It is carried through untouched rather than zeroed, so a numerical
    # residue shows up as a vector-golden mismatch instead of being silently eaten.
    s2 = ((1.0 - gp * w) * sx, sy, (1.0 - gr * w) * sz)
    return _qnorm(_qmul(_from_rotvec(s2), twist))
