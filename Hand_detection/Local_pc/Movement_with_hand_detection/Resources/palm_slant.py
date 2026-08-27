"""⭐⭐ PALM SLANT AND TILT — orientation from 2D, with no depth at all.

`T6`'s answer, after the ratio table died. Fit the 2x2 affine map from a frozen
canonical palm to the current one, TRIMMED, and take its SVD:

    sigma = s2/s1     how compressed the shape is   -> how far it is turned
    tilt              the minor axis, in the palm frame -> which way

⭐ Both are computed from PIXEL landmarks only. MediaPipe's world `z` -- the
coordinate `T6` exists because we do not trust -- is never read.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ WHAT THIS IS, AND WHAT IT IS NOT

It is a **LARGE-ANGLE CORRECTION**, not a replacement for `palm_rotation.Horn`.

Measured 2026-08-27 on `roll_card_axis_check_b`, whose ground truth is `t5j`'s
in-image knuckle-row angle -- depth-free and declaration-free:

    hand barely moved   ->  sigma 0.94-0.96  ->  17-20 deg of FALSE tilt

MediaPipe's landmark noise ALONE produces ~20 deg of apparent tilt at the square
pose, because `arccos` is nearly vertical as sigma -> 1. Averaging the canonical
over 31 frames recovers only 3 deg of it, so it is irreducible by sampling.

⭐ Hence `authority()`. Below the floor this module contributes NOTHING, and it
says so, rather than inventing 20 deg of rotation. ⚠ Any caller that ignores the
authority is using this wrong.

⭐ ROLL INVARIANCE HOLDS, which is the property that makes it worth having: 40-103
deg of real roll adds only ~7-8 deg of false tilt, because roll happens WITHIN the
image plane and does not foreshorten.

────────────────────────────────────────────────────────────────────────────────
⭐ THE ARCHITECTURE IS THE OWNER'S: FREEZE AT GRAB

`freeze()` captures the canonical at the moment of the grab, exactly as
`DepthRatioTracker`, `Horn(mode='ref')` and `tip_trim` each freeze a per-grab
baseline. Everything after is measured RELATIVE to that.

⭐⭐ It works because the cube's rotation is ALREADY grab-relative
(`delta = q_now . conj(q_grab)`), so an absolute error at the grab instant CANCELS.
Only the delta has to be right. ⭐ And the noise floor above then applies to the
DELTA -- a hand that has barely moved reports nothing, which is correct behaviour
rather than 20 deg of invention.

────────────────────────────────────────────────────────────────────────────────
⛔ PALM LANDMARKS ONLY

Including the fingers halves the cross-take feature spread on an OPEN hand
(0.162 -> 0.067) and is a disaster on a GRIPPING one: measured frame-to-frame
jitter 0.013-0.458 against the palm quad's 0.004-0.070, i.e. up to 60x worse. The
game grips. The fingers keep their own channel (`fingertips`, `tip_trim`).

⛔ THE ANGLE TABLE IS NOT IN THIS MODULE. Mapping `sigma -> angle` needs a fitted
curve, and that curve carries the operator's HAND THICKNESS (it is why sigma
bottoms at 0.07-0.30 instead of 0). A per-user artefact must not be frozen into a
shared module: `invert()` takes the table as an argument, so calibration stays data
(`U12`'s territory) and this file stays geometry.

Stdlib only, numpy-free, CLOCK-FREE, no side effects -- the port contract
(`CONSTRAINTS` §2), same as `palm_geometry` / `palm_depth`.
Golden vectors: `analysis/verify_palm_slant.py`.
"""
import math

# The rigid palm quad plus the wrist -- the same five `palm_rotation` fits.
PALM_LANDMARKS = (0, 5, 9, 13, 17)

# ⭐ MEASURED, not chosen. Fraction of points dropped by residual before the refit.
# Trimming is what lets a near-rigid set tolerate the one landmark that moved.
TRIM_FRACTION = 0.25
TRIM_PASSES = 3

# ⛔ KEEP AT LEAST FOUR. Not a safety floor -- it is what `analysis/t6_regression_fit.py`
# used to produce every sigma in this row, the 0.94 noise floor included. With five
# palm points `int(5 * 0.75) = 3`, so a "cleaner" floor of 3 would trim harder than
# the harness did and silently invalidate the fitted tables. The shipped module and
# the harness that measured it must agree exactly, or the numbers stop transferring.
TRIM_MIN_KEEP = 4

# ⛔⛔ THE NOISE FLOOR, and the reason `authority()` exists. Landmark noise alone
# puts sigma at 0.94-0.96 on a hand that has barely moved (roll take, independent
# ground truth). Above this, any "tilt" this module reports is indistinguishable
# from MediaPipe jitter.
SLANT_NOISE_FLOOR = 0.94

# Full authority once the shape is unmistakably compressed. Between the two the
# fade is smooth -- a hard gate would step the correction on and off across the
# threshold, which is the artefact `tip_trim`'s own fade was added to avoid.
SLANT_FULL = 0.80


def smoothstep(x, zero_at, one_at):
    """0 at `zero_at`, 1 at `one_at`, smooth between. ⚠ DESCENDING here --
    authority rises as sigma FALLS, and the first version of this function assumed
    the ascending convention and returned a hard step, backwards. The golden
    vectors caught it before it reached a caller."""
    span = one_at - zero_at
    if abs(span) < 1e-12:
        return 0.0 if x == zero_at else 1.0
    t = (x - zero_at) / span
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


# ⚠ The private name is kept so nothing that already imports it breaks. It is
# PUBLIC now because `palm_slant_axis` needs the same curve, and N6 says imported
# never copied -- a second hand-rolled smoothstep is a second thing to get wrong.
_smoothstep = smoothstep


def _points(landmarks, indices):
    if not landmarks or len(landmarks) <= max(indices):
        return None
    out = []
    for i in indices:
        p = landmarks[i]
        if p is None or len(p) < 2:
            return None
        out.append((float(p[0]), float(p[1])))
    return out


def affine_svd(src, dst, trim=TRIM_FRACTION):
    """(sigma, tilt_deg) for the trimmed affine map `src` -> `dst`. None if degenerate.

    ⚠ Centred, so translation drops out and only the SHAPE change is measured.
    `sigma = s2/s1` is scale-free, so the distance to the camera cancels -- which
    is why `T6`'s caveat zero (an unreliable tape measure) cannot reach it.
    """
    if not src or not dst or len(src) != len(dst) or len(src) < 3:
        return None
    idx = list(range(len(src)))
    A = None
    for _ in range(TRIM_PASSES if trim > 0.0 else 1):
        n = len(idx)
        cs0 = sum(src[i][0] for i in idx) / n
        cs1 = sum(src[i][1] for i in idx) / n
        cd0 = sum(dst[i][0] for i in idx) / n
        cd1 = sum(dst[i][1] for i in idx) / n
        s00 = s01 = s11 = t00 = t01 = t10 = t11 = 0.0
        for i in idx:
            ax, ay = src[i][0] - cs0, src[i][1] - cs1
            bx, by = dst[i][0] - cd0, dst[i][1] - cd1
            s00 += ax * ax
            s01 += ax * ay
            s11 += ay * ay
            t00 += bx * ax
            t01 += bx * ay
            t10 += by * ax
            t11 += by * ay
        det = s00 * s11 - s01 * s01
        if abs(det) < 1e-12:
            return None
        i00, i01, i11 = s11 / det, -s01 / det, s00 / det
        A = ((t00 * i00 + t01 * i01, t00 * i01 + t01 * i11),
             (t10 * i00 + t11 * i01, t10 * i01 + t11 * i11))
        if trim > 0.0:
            res = []
            for i in range(len(src)):
                ax, ay = src[i][0] - cs0, src[i][1] - cs1
                bx, by = dst[i][0] - cd0, dst[i][1] - cd1
                res.append((math.hypot(A[0][0] * ax + A[0][1] * ay - bx,
                                       A[1][0] * ax + A[1][1] * ay - by), i))
            res.sort()
            keep = max(TRIM_MIN_KEEP, int(len(res) * (1.0 - trim)))
            idx = [i for _r, i in res[:keep]]

    a, b = A[0]
    c, d = A[1]
    e, f = (a + d) * 0.5, (a - d) * 0.5
    g, h = (c + b) * 0.5, (c - b) * 0.5
    q, r = math.hypot(e, h), math.hypot(f, g)
    s1, s2 = q + r, abs(q - r)
    if s1 < 1e-9:
        return None
    # ⭐ The RIGHT singular direction, i.e. the axis read in the CANONICAL palm's
    # own frame -- which is what makes it roll-invariant: the palm's roll lands in
    # the left factor and never reaches this angle.
    # ⚠ Convention is deliberately IDENTICAL to `analysis/t6_regression_fit.py`
    # (major axis, mod 180). Every fitted table in `T6` is expressed in it. Rotating
    # it by 90 to match the textbook's "tilt = minor axis" would be more correct in
    # name and would offset every table by a quarter turn.
    tilt = math.degrees((math.atan2(h, e) - math.atan2(g, f)) * 0.5) % 180.0
    return s2 / s1, tilt


def authority(sigma):
    """0..1 — how much of this module's answer a caller may use.

    ⛔ ZERO at and above `SLANT_NOISE_FLOOR`, where MediaPipe's own jitter reads as
    ~20 deg of tilt. A caller that ignores this will act on invented rotation.
    """
    if sigma is None or sigma != sigma:
        return 0.0
    return smoothstep(sigma, SLANT_NOISE_FLOOR, SLANT_FULL)


def tilt_delta(a, b):
    """Signed-free angular distance between two TILTS, in degrees, 0..90.

    ⛔ TRAP, and the golden vectors walked straight into it: tilt is an AXIS, not
    a direction -- it lives mod 180. A tilt of 179.9 and a tilt of 0.1 are 0.2 deg
    apart, not 179.8. Any consumer that subtracts naively will read a hand that has
    barely moved as having flipped. Use this instead.
    """
    if a is None or b is None:
        return None
    d = (a - b) % 180.0
    return d if d <= 90.0 else 180.0 - d


def invert(table, sigma):
    """Read an angle off a MONOTONE (sigma, angle) table, by interpolation.

    ⭐ The table is an argument, never a constant: it carries the operator's hand
    THICKNESS and is therefore per-user (`U12`). Monotone in, single-valued out --
    which is what keeps the map bijective.
    ⚠ Outside the table's range it CLAMPS. Extrapolating a foreshortening curve
    past its measured span is the kind of confident guess this project retracts.
    """
    if not table or sigma is None or sigma != sigma:
        return None
    pts = sorted(table, key=lambda p: -p[0])
    if sigma >= pts[0][0]:
        return pts[0][1]
    if sigma <= pts[-1][0]:
        return pts[-1][1]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x2 <= sigma <= x1:
            t = 0.0 if abs(x1 - x2) < 1e-12 else (x1 - sigma) / (x1 - x2)
            return y1 + t * (y2 - y1)
    return pts[-1][1]


class SlantTracker:
    """Per-hand. `freeze()` at the grab, `update()` every frame after.

    Reports the shape change RELATIVE to the grab, which is the only thing the
    cube needs -- its orientation is grab-relative, so the absolute error at the
    grab instant cancels.
    """

    __slots__ = ("_canon", "last_sigma", "last_tilt", "frames_refused")

    def __init__(self):
        self.reset()

    def reset(self):
        """Hand lost / released. ⚠ The canonical belongs to the dead grab: a
        reference outliving its hand is §16.15's rule, and this module is not
        exempt from it."""
        self._canon = None
        self.last_sigma = 1.0
        self.last_tilt = None
        self.frames_refused = 0

    @property
    def frozen(self):
        return self._canon is not None

    def freeze(self, landmarks):
        """Capture the grab pose. Returns True when a canonical was taken."""
        pts = _points(landmarks, PALM_LANDMARKS)
        if pts is None:
            return False
        self._canon = pts
        self.last_sigma = 1.0
        self.last_tilt = None
        return True

    def update(self, landmarks):
        """(sigma, tilt, authority). ⚠ `authority == 0` means DO NOT ACT.

        ⛔ Holds the last value when the landmarks are unusable rather than
        snapping to identity -- `B8` measured holding beating every fit, and a snap
        to identity would jerk the object every time a frame degraded.
        """
        if self._canon is None:
            return self.last_sigma, self.last_tilt, 0.0
        pts = _points(landmarks, PALM_LANDMARKS)
        if pts is None:
            self.frames_refused += 1
            return self.last_sigma, self.last_tilt, 0.0
        r = affine_svd(self._canon, pts)
        if r is None:
            self.frames_refused += 1
            return self.last_sigma, self.last_tilt, 0.0
        self.last_sigma, self.last_tilt = r
        return self.last_sigma, self.last_tilt, authority(self.last_sigma)
