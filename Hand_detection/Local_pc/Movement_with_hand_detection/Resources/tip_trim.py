"""⭐⭐⭐ `F1` STEP 4 — THE FINGERTIP TRIM. Rotation from the tips, bounded.

> **Owner, 2026-08-26:** *"fingertips shall also be used for rotation quaternion
> control to the extent they are robust enough."*

⭐ That sentence is the whole design brief, and the second half is the load-bearing
part: the tips get authority **in proportion to how well-conditioned they are this
frame**, not a fixed share. Spec:
`Claude/10_HAND_TRACKING/spec/F1_FINGERTIP_TRANSFORM_SPEC.md` §3 and §6.2.

────────────────────────────────────────────────────────────────────────────────
THE FORM, AND WHY IT IS NOT THE ARM THAT DIED TWICE

    q_i(t)    = conj(R_palm) . (tip_i - c_palm) . R_palm     tips IN THE PALM FRAME
    R_res(t)  = horn( q_i(grab) -> q_i(t) )                  PURE articulation
    R_trim(t) = clamp( gain * fade * R_res )                 bounded, faded
    dR(t)     = R_palm(t) . R_trim(t) . R_palm(grab)^-1

⛔ A rigid fit over palm+tips is **A10-dead twice** (`B4`'s `PALM_AND_TIPS`, p95
jitter 9.85 -> 27.79 deg; the 9-point constellation, +1.4 deg of axis for +4.9 deg
of jitter). Both failed for one reason: the tips move relative to the palm, and a
rigid fit has nowhere to put that motion except whole-object rotation.

⭐⭐ Expressing the tips IN THE PALM FRAME removes whole-hand rotation **by
construction** -- `R_res` cannot contain wrist motion, because the wrist motion is
what the frame change divides out. The dead arm's failure mode is structurally
absent here, not tuned away.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ WHAT THE CENSUS SAYS, AND WHY THE CLAMP IS SMALL

`analysis/f1_tip_census.py`, over 123 takes:

  * the tip NOISE FLOOR is only **1.5 mm** median per tip, and held is a mere
    5-10% worse than free -- so the tips are usable at all. Good news.
  * ⛔ but the RIGID TIP RESIDUAL swings **75-95 deg at p90-p95 WITHIN HALF A
    SECOND**, and the short-horizon figure barely differs from the long one -- so
    it is neither slow drift nor sensor noise. **It is the rigid model being
    wrong**: Horn's best rigid explanation of a non-rigid 5-point set tumbles.

⭐ Therefore `TRIM_MAX_DEG` is deliberately **far below the data's own spread**
(10 deg against a 15.9 deg short-horizon MEDIAN). This is a FINE TRIM for
assembly-style alignment, which is what the owner asked for -- it is not, and must
not become, "the object follows the fingers".

────────────────────────────────────────────────────────────────────────────────
⛔ GAIN 0 IS THE SHIPPED PIPELINE, EXACTLY

`TRIM_GAIN = 0.0` makes `R_trim` the identity quaternion object, so
`dR = R_palm(t) . R_palm(grab)^-1` -- today's expression, unchanged. The default
is 0.0: this lands **switched off** and the live take turns it up.
"""
import math

from . import palm_geometry
from . import palm_rotation

TIPS = (4, 8, 12, 16, 20)
PALM = palm_rotation.PALM_LANDMARKS          # (0, 5, 9, 13, 17)
IDENTITY = (1.0, 0.0, 0.0, 0.0)

# ⛔ LANDS OFF. The live take raises it; `analysis/verify_f1_trim.py` pins that 0.0
# is bit-identical to shipped Horn.
TRIM_GAIN = 0.0

# The hard bound on the trim, in degrees. ⚠ Set from the census (see the header),
# not from taste: real short-horizon articulation has a 15.9 deg MEDIAN, so 10 deg
# is a fine correction rather than a follow.
TRIM_MAX_DEG = 10.0

# ⚠ A magnitude clamp alone still permits a full-clamp jump in ONE frame if the
# fit flips branch. Bound the RATE too.
TRIM_MAX_RATE_DEG_S = 60.0

# ⭐ CONDITIONING FLOORS -- "to the extent they are robust enough", made numeric.
# `spread` = sqrt(l2/l1) of the tip cloud: how far it is from a LINE. ⛔ It is
# COLLINEARITY that destroys observability, NOT flatness -- a planar tip set is
# perfectly well conditioned. Census: p1 = 0.172, and a 0.20 floor freezes 1.89%
# of frames, so this is cheap.
SPREAD_FLOOR = 0.20
SPREAD_FULL = 0.32          # full authority at or above this

# `scale` = sqrt(l1) / palm span: the cloud's absolute size. A closed fist puts
# every tip in one place and no angle is determined. Census median 1.553, p1 0.700.
SCALE_FLOOR = 0.45
SCALE_FULL = 0.80


def _smoothstep(x, lo, hi):
    """0 below `lo`, 1 above `hi`, smooth in between -- never a hard switch.

    ⚠ A hard gate IS a rotation step: authority snapping from 0 to 1 moves the
    object on that frame. `DR-2` freezes rather than switches for the same reason.
    """
    if hi <= lo:
        return 1.0 if x >= hi else 0.0
    t = (x - lo) / (hi - lo)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def _rotate(q, v):
    """Rotate vector `v` by quaternion `q`."""
    w, x, y, z = q
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def tips_in_palm_frame(world_landmarks, q_palm):
    """The five tips expressed in the palm's own frame, or None.

    ⭐ THIS IS THE STEP THAT MAKES THE DESIGN SAFE. `q_palm` maps the track's
    frozen reference to the current palm pose, so conjugating by it removes the
    hand's own rotation and leaves ARTICULATION ONLY.
    """
    if world_landmarks is None or len(world_landmarks) <= TIPS[-1]:
        return None
    try:
        c = [sum(world_landmarks[i][k] for i in PALM) / len(PALM) for k in range(3)]
    except (TypeError, IndexError):
        return None
    inv = _qconj(q_palm)
    out = []
    for i in TIPS:
        p = world_landmarks[i]
        if p is None or len(p) < 3:
            return None
        out.append(_rotate(inv, (p[0] - c[0], p[1] - c[1], p[2] - c[2])))
    return out


def palm_span_m(world_landmarks):
    """Index-MCP to pinky-MCP, in metres -- the rigid width `scale` normalises by.

    ⚠ The PALM quad, never a fingertip span: fingers bend, so a tip-to-tip
    distance has no fixed baseline. This is the same width `palm_depth`'s ratio
    form is built on, and the same one `analysis/f1_tip_census.py` measured
    against. Returns 0.0 when it cannot be computed, which makes `scale` 0 and
    fades the trim out -- the safe direction.
    """
    if world_landmarks is None or len(world_landmarks) <= PALM[4]:
        return 0.0
    a, b = world_landmarks[PALM[1]], world_landmarks[PALM[4]]   # index MCP, pinky MCP
    if a is None or b is None or len(a) < 3 or len(b) < 3:
        return 0.0
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3)))


def conditioning(points, palm_span_m):
    """(spread, scale) for a tip cloud. See the constants above for what they mean.

    Reuses `palm_geometry._symmetric_3x3_eigenvalues` -- the same routine
    `palm_observability` runs, so the two cannot drift apart (N6).
    """
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    cz = sum(p[2] for p in points) / n
    a00 = a01 = a02 = a11 = a12 = a22 = 0.0
    for x, y, z in points:
        dx, dy, dz = x - cx, y - cy, z - cz
        a00 += dx * dx
        a01 += dx * dy
        a02 += dx * dz
        a11 += dy * dy
        a12 += dy * dz
        a22 += dz * dz
    l1, l2, _l3 = palm_geometry._symmetric_3x3_eigenvalues(a00, a01, a02, a11, a12, a22)
    if l1 <= 1e-18:
        return 0.0, 0.0
    spread = math.sqrt(max(0.0, l2) / l1)
    scale = math.sqrt(l1) / palm_span_m if palm_span_m > 1e-9 else 0.0
    return spread, scale


def _scale_quat(q, factor, max_deg):
    """Scale a rotation's ANGLE by `factor`, then clamp it to `max_deg`.

    ⚠ Axis-angle, not component scaling: scaling a quaternion's components
    changes its axis as well as its angle, which would tilt the correction.
    """
    w = q[0]
    w = -1.0 if w < -1.0 else (1.0 if w > 1.0 else w)
    ang = 2.0 * math.acos(abs(w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9 or ang < 1e-9:
        return IDENTITY, 0.0
    sign = 1.0 if w >= 0.0 else -1.0        # shortest arc
    axis = (sign * q[1] / s, sign * q[2] / s, sign * q[3] / s)
    ang *= factor
    cap = math.radians(max_deg)
    if ang > cap:
        ang = cap
    if ang < 1e-9:
        return IDENTITY, 0.0
    h = ang * 0.5
    sh = math.sin(h)
    return (math.cos(h), axis[0] * sh, axis[1] * sh, axis[2] * sh), math.degrees(ang)


class TipTrim:
    """Per-hand fingertip trim, frozen at grab and cleared on release.

    ⚠ FROZEN AT THE GRAB, not per track: the trim is "how much have the fingers
    turned the object SINCE I PICKED IT UP", so its reference is the grab. That is
    also what makes `R_trim(grab) = I` and therefore no pop -- the same guarantee
    `4.2` gets by making its depth ratio 1.0 at the grab frame.
    """

    __slots__ = ("_ref", "_last_q", "_last_deg", "_last_ms",
                 "last_spread", "last_scale", "last_fade", "last_applied_deg",
                 "last_raw_deg")

    def __init__(self):
        self.reset()

    def reset(self):
        self._ref = None
        self._last_q = IDENTITY
        self._last_deg = 0.0
        self._last_ms = None
        self.last_spread = 0.0
        self.last_scale = 0.0
        self.last_fade = 0.0
        self.last_applied_deg = 0.0
        self.last_raw_deg = 0.0

    @property
    def frozen(self):
        return self._ref is not None

    def freeze(self, world_landmarks, q_palm):
        """Capture the grab-time tip constellation. Returns True if it took."""
        pts = tips_in_palm_frame(world_landmarks, q_palm)
        if pts is None:
            return False
        self._ref = pts
        self._last_q = IDENTITY
        self._last_deg = 0.0
        self._last_ms = None
        return True

    def update(self, world_landmarks, q_palm, palm_span_m, now_ms, gain=None):
        """The trim quaternion for this frame. Identity when off or unusable.

        ⛔ HOLDS the previous trim rather than extrapolating whenever the fit is
        unavailable -- `B8` measured that holding the last value beats every fit,
        and `D4`'s extrapolation was declined by the owner after seeing D2/D3 live.
        """
        g = TRIM_GAIN if gain is None else gain
        if g == 0.0 or self._ref is None:
            # ⛔ The identity OBJECT, so gain 0 is bit-identical to shipped Horn.
            self.last_fade = 0.0
            self.last_applied_deg = 0.0
            return IDENTITY

        pts = tips_in_palm_frame(world_landmarks, q_palm)
        if pts is None:
            return self._last_q

        self.last_spread, self.last_scale = conditioning(pts, palm_span_m)
        fade = (_smoothstep(self.last_spread, SPREAD_FLOOR, SPREAD_FULL) *
                _smoothstep(self.last_scale, SCALE_FLOOR, SCALE_FULL))
        self.last_fade = fade
        if fade <= 0.0:
            # Not "no trim" -- the LAST trim. Dropping to identity here would snap
            # the object back every time the hand passed through a bad pose.
            self.last_applied_deg = self._last_deg
            return self._last_q

        q = palm_rotation.horn_rotation(self._ref, pts)
        if q is None:
            return self._last_q
        self.last_raw_deg = palm_rotation.quat_angle_deg(IDENTITY, q)

        trim, deg = _scale_quat(q, g * fade, TRIM_MAX_DEG)

        # ⚠ RATE LIMIT. The magnitude clamp alone still allows a full-clamp jump
        # in one frame if the fit flips branch; this bounds how fast the trim can
        # travel, in DEGREES PER SECOND so it does not change with the frame rate
        # (`L1`/`N10`: the rate here is camera-bound and moves with the lighting).
        if self._last_ms is not None and now_ms is not None:
            dt = (now_ms - self._last_ms) / 1000.0
            if dt > 0.0:
                room = TRIM_MAX_RATE_DEG_S * dt
                if abs(deg - self._last_deg) > room:
                    deg = self._last_deg + room * (1.0 if deg > self._last_deg else -1.0)
                    frac = deg / max(1e-9, palm_rotation.quat_angle_deg(IDENTITY, q) * g * fade)
                    trim, deg = _scale_quat(q, g * fade * max(0.0, min(1.0, frac)),
                                            TRIM_MAX_DEG)
        self._last_ms = now_ms
        self._last_q = trim
        self._last_deg = deg
        self.last_applied_deg = deg
        return trim
