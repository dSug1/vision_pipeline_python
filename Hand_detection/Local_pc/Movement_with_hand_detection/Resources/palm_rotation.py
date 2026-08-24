"""Palm ORIENTATION by least-squares fit over the whole constellation (B4/§16.13).

THE DEFECT THIS ADDRESSES, measured on live takes
--------------------------------------------------
The shipped orientation comes from a Gram-Schmidt frame over THREE vectors
(`_orthonormal_frame`: e1 from the knuckle row, e2 from wrist->middle
orthogonalised, e3 = e1 x e2). Nothing is averaged, and the orthogonalisation
denominator collapses exactly where the palm foreshortens. Measured
frame-to-frame on a STILL palm:

    raw Gram-Schmidt              p50 1.59   p95 21.91   MAX 144.19 deg
    after the SHIPPED filter      p50 1.59   p95 17.54   MAX 101.61 deg
    KABSCH, 5 palm points         p50 1.35   p95 11.71   max  25.07 deg
    KABSCH, 5 palm + 4 tips       p50 0.85   p95  2.91   max  19.32 deg

⭐ 7.5x on both p95 and max, from changing the ESTIMATOR -- not the filter. The
shipped predictive filter removes only ~30% of the excursion because the error
is in the estimate it is being fed, not in the smoothing.

⭐ AND THE FINGERTIPS HELP HERE, opposite to the translation case (§16.12).
Rotation is fitted over a constellation, so points FAR from the centroid give a
long baseline for angle; their positional noise costs little for an ANGLE while
their span buys precision. The same landmarks that are a liability for
translation are an asset for rotation.


⚠⚠ WHY HORN'S QUATERNION METHOD AND NOT SVD -- THIS IS A SAFETY PROPERTY
-------------------------------------------------------------------------
The usual least-squares rotation is Kabsch-via-SVD, which needs an explicit
`det` sign correction: without it the fit can return a REFLECTION, silently
inverting handedness. This project has shipped a silent handedness inversion
once already (§13.6.1), and M6b's Q1 was written specifically to catch that
class (§0.12).

Horn's method solves the same least-squares problem by finding the largest
eigenvector of a 4x4 symmetric matrix, and **its answer IS a quaternion**. A
unit quaternion is a proper rotation BY CONSTRUCTION -- det = +1 always, no
reflection is representable, and there is no sign correction to forget. The
chirality bug is not guarded against here; it is made unrepresentable.

It is also numpy-free in a way a 3x3 SVD is not: a Jacobi eigen-decomposition of
a 4x4 symmetric matrix is ~30 lines and exact in a few sweeps. ⚠ Power iteration
was tried first and is WRONG here -- any shift large enough to guarantee
positivity drives lambda2/lambda1 to ~1, and 60 iterations still left up to 2.0
of element error, i.e. a completely wrong rotation at large angles. Caught by
`verify_palm_rotation.py` §1 before it reached any measurement.


TWO WAYS TO USE IT, AND THEY FAIL DIFFERENTLY
----------------------------------------------
    GRAB-REFERENCED   fit the CURRENT constellation against the one frozen at
                      grab. Gives the delta the cube needs directly, with NO
                      drift. ⚠ Corrupted if the hand CHANGES SHAPE during the
                      hold -- a curled finger is not the same constellation.
    FRAME-TO-FRAME    fit against the previous frame and compose. Immune to slow
                      shape change. ⚠ ACCUMULATES DRIFT, without bound.

Palm-only grab-referenced is immune to both (the palm is rigid: 2.76 mm, §0.2)
and still beat Gram-Schmidt by 2x. Which to ship is a measurement, not a
preference -- `analysis/b4_anchor_rotation_ab.py` decides it per take.

Stdlib only, numpy-free, deterministic, no side effects -- the port contract.
"""

import math

try:                                        # imported, never copied (N6)
    from . import hand_blocks as HB
except ImportError:
    import hand_blocks as HB

try:                                        # T6's metric anchor -- see canonical_palm
    from . import palm_depth as _PD
except ImportError:
    import palm_depth as _PD

try:                                        # T6's solver and its chirality cue
    from . import planar_pnp as PPNP
    from . import palm_geometry as PG
except ImportError:
    import planar_pnp as PPNP
    import palm_geometry as PG

quat_from_matrix = PPNP.quat_from_matrix    # one implementation, not two (N6)

# ⚠ IMPORTED, NEVER COPIED (N6). The hand breadth lives in ONE place; a second
# literal here is how the two tools drift, and 4.2 paid for exactly that class of
# error when a constant was carried across from another row's derivation.
_NOMINAL_BREADTH_M = _PD.NOMINAL_SPAN_M[(5, 17)]

PALM_LANDMARKS = HB.PALM_LANDMARKS               # (0, 5, 9, 13, 17)
ARC_TIPS = (8, 12, 16, 20)                       # the 4 tips that HAVE an arc;
                                                 # the thumb is unmodelled (§16)
PALM_AND_TIPS = PALM_LANDMARKS + ARC_TIPS

_JACOBI_SWEEPS = 60
_IDENTITY = (1.0, 0.0, 0.0, 0.0)


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
    return _IDENTITY if n < 1e-12 else tuple(c / n for c in q)


def quat_angle_deg(a, b):
    if a is None or b is None:
        return None
    d = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


def horn_rotation(src, dst, weights=None, seed=None):
    """Least-squares rotation taking `src` onto `dst` (Horn 1987), as a quaternion.

    Both are sequences of 3-vectors in correspondence. Returns a UNIT QUATERNION,
    i.e. a proper rotation -- a reflection is not representable, so handedness
    cannot silently invert (see the module docstring; §13.6.1).

    `seed` only fixes the SIGN (q and -q are the same rotation); the solve
    itself is exact and needs no warm start.
    """
    n = len(src)
    if n < 3 or n != len(dst):
        return None
    w = [1.0] * n if weights is None else list(weights)
    tw = sum(w)
    if tw < 1e-12:
        return None
    ca = [sum(w[i] * src[i][k] for i in range(n)) / tw for k in range(3)]
    cb = [sum(w[i] * dst[i][k] for i in range(n)) / tw for k in range(3)]
    # 3x3 correlation matrix M = sum w_i (src_i - ca)(dst_i - cb)^T
    M = [[0.0] * 3 for _ in range(3)]
    for i in range(n):
        a = (src[i][0] - ca[0], src[i][1] - ca[1], src[i][2] - ca[2])
        b = (dst[i][0] - cb[0], dst[i][1] - cb[1], dst[i][2] - cb[2])
        for r in range(3):
            for c in range(3):
                M[r][c] += w[i] * a[r] * b[c]
    sxx, sxy, sxz = M[0]
    syx, syy, syz = M[1]
    szx, szy, szz = M[2]
    # Horn's symmetric 4x4
    K = [
        [sxx + syy + szz, syz - szy,        szx - sxz,        sxy - syx],
        [syz - szy,       sxx - syy - szz,  sxy + syx,        szx + sxz],
        [szx - sxz,       sxy + syx,       -sxx + syy - szz,  syz + szy],
        [sxy - syx,       szx + sxz,        syz + szy,       -sxx - syy + szz],
    ]
    # ⚠ Solved by JACOBI EIGEN-DECOMPOSITION, not power iteration. Power
    # iteration on a shifted K converges at a rate set by lambda2/lambda1, and
    # any shift big enough to guarantee positivity drives that ratio to ~1 --
    # measured: 60 iterations still left up to 2.0 of element error, i.e. a
    # completely wrong rotation at large angles. Jacobi is exact for a 4x4
    # symmetric matrix in a handful of sweeps and has no such failure mode.
    V = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    for _sweep in range(_JACOBI_SWEEPS):
        off = 0.0
        pr = pc = 0
        big = 0.0
        for r in range(4):
            for c in range(r + 1, 4):
                a = abs(K[r][c])
                off += a * a
                if a > big:
                    big, pr, pc = a, r, c
        if off < 1e-30:
            break
        kpp, kqq, kpq = K[pr][pr], K[pc][pc], K[pr][pc]
        theta = (kqq - kpp) / (2.0 * kpq)
        t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
        cs = 1.0 / math.sqrt(t * t + 1.0)
        sn = t * cs
        for k in range(4):
            akp, akq = K[k][pr], K[k][pc]
            K[k][pr] = cs * akp - sn * akq
            K[k][pc] = sn * akp + cs * akq
        for k in range(4):
            akp, akq = K[pr][k], K[pc][k]
            K[pr][k] = cs * akp - sn * akq
            K[pc][k] = sn * akp + cs * akq
        for k in range(4):
            vkp, vkq = V[k][pr], V[k][pc]
            V[k][pr] = cs * vkp - sn * vkq
            V[k][pc] = sn * vkp + cs * vkq
    best = max(range(4), key=lambda i: K[i][i])
    v = [V[r][best] for r in range(4)]
    q = _qnorm(tuple(v))
    if seed and sum(a * b for a, b in zip(q, seed)) < 0:
        q = tuple(-c for c in q)             # shortest arc / sign continuity
    return q


def _pts(world_landmarks, indices):
    try:
        return [tuple(world_landmarks[i]) for i in indices]
    except (IndexError, TypeError):
        return None


# --------------------------------------------------------------------------
# Estimators. Common interface so the harness can swap them blind:
#     freeze(px, world) -> state       (at grab)
#     delta(state, px, world) -> quaternion rotation SINCE GRAB
#     step(state, px, world) -> degrees rotated since the PREVIOUS call
# --------------------------------------------------------------------------
class GramSchmidt:
    """The SHIPPED estimator: absolute frame from 3 vectors, delta by composition."""

    name = "gram_schmidt"

    def __init__(self, indices=None):
        pass

    @staticmethod
    def _q(world):
        return HB.palm_quaternion(world)

    def freeze(self, px, world):
        q = self._q(world)
        return None if q is None else {"q0": q, "prev": q}

    def delta(self, state, px, world):
        q = self._q(world)
        if q is None or state is None:
            return None
        return _qmul(q, _qconj(state["q0"]))

    def step(self, state, px, world):
        q = self._q(world)
        if q is None or state is None:
            return None
        d = quat_angle_deg(state["prev"], q)
        state["prev"] = q
        return d


class Horn:
    """Least-squares over a landmark constellation.

    mode='ref'  fit against the GRAB constellation -- no drift, but assumes the
                hand does not change shape during the hold.
    mode='ff'   fit against the PREVIOUS frame and compose -- immune to shape
                change, accumulates drift.
    """

    def __init__(self, indices=PALM_LANDMARKS, mode="ref"):
        self.indices = tuple(indices)
        self.mode = mode
        self.name = f"horn_{'palm' if self.indices == PALM_LANDMARKS else 'palmtips'}_{mode}"

    def freeze(self, px, world):
        p = _pts(world, self.indices)
        if p is None:
            return None
        return {"ref": p, "prev": p, "acc": _IDENTITY, "seed": None, "sstep": None}

    def delta(self, state, px, world):
        if state is None:
            return None
        p = _pts(world, self.indices)
        if p is None:
            return None
        if self.mode == "ref":
            q = horn_rotation(state["ref"], p, seed=state["seed"])
            if q is not None:
                state["seed"] = q
            return q
        q = horn_rotation(state["prev"], p, seed=state["seed"])
        if q is None:
            return state["acc"]
        state["seed"] = q
        state["prev"] = p
        state["acc"] = _qnorm(_qmul(q, state["acc"]))
        return state["acc"]

    def step(self, state, px, world):
        """Degrees rotated since the previous call -- the stability metric."""
        if state is None:
            return None
        p = _pts(world, self.indices)
        if p is None:
            return None
        q = horn_rotation(state["prev"], p, seed=state["sstep"])
        if q is None:
            return None
        state["sstep"] = q
        state["prev"] = p
        return quat_angle_deg(_IDENTITY, q)


# --------------------------------------------------------------------------
# T6 -- THE CANONICAL PLANAR PALM (the model the 2D<->3D fit projects)
# --------------------------------------------------------------------------
# ⚠⚠ THE HANDOFF SAYS "build the 3D model from `palm_depth.NOMINAL_SPAN_M`" AND
# THAT IS NOT ENOUGH. `NOMINAL_SPAN_M` carries FOUR distances -- (5,17), (0,9),
# (0,5), (0,17) -- while a planar 5-point model has 2*5-3 = 7 shape DOF:
#   * (0, 5, 17) is fully determined -- three points, three distances;
#   * 9 gets ONE constraint and needs two;
#   * 13 gets NONE -- no span in `NOMINAL_SPAN_M` touches the ring MCP.
# ⛔ And "9 and 13 lie on the segment 5->17" is provably wrong: |0-9| = |0-5| =
# 0.100 with 9 laterally BETWEEN 5 and 17 forces 9 OFF that line. The knuckle row
# BOWS away from the wrist, and `verify_planar_pnp.py` §7 asserts that it does --
# the bow is 10.6 mm and it is also what CONDITIONS the homography, since the four
# MCPs alone are nearly collinear.
#
# ⭐ SO THE SHAPE IS MEASURED AND `NOMINAL_SPAN_M` IS THE METRIC ANCHOR PLUS AN
# INDEPENDENT CHECK -- 59 corpus sessions, 2792 face-on frames, from the 2D PIXEL
# landmarks.
#   ⛔ NOT from `world_landmarks`: M2 established they carry no pose-consistent
#      skeleton (0/21 bones inside target), so a length taken from them measures
#      the ESTIMATOR, not a hand -- which is `NOMINAL_SPAN_M`'s own stated reason
#      for using anthropometry in the first place.
#   ⭐ 2D pixels are the one signal T6's premise says is GOOD.
#   ⭐ Only the (5,17) breadth is shared between the two sources, so the other
#      three spans are a real cross-validation. **They agree to 10 mm.**
#
# ⭐⭐ AND THE SCALE BARELY MATTERS, WHICH IS WHY 10 MM IS COMFORTABLE RATHER THAN A
# DEFECT: for a planar target, scaling the model scales the recovered TRANSLATION
# and leaves the ROTATION untouched, and T6 consumes only the rotation. It is the
# SHAPE that must be right. `verify_planar_pnp.py` §5 pins the scale linearity so
# the port cannot quietly break that property.
#
# ⛔⛔ A SELECTION RULE THAT WAS TRIED AND IS THE OPPOSITE OF CORRECT, kept so it is
# not re-tried: `edge_on_measure >= 0.90` reads like a face-on filter but is
# |sin(theta)| BETWEEN THE TWO PALM VECTORS, so it PEAKS when the palm is
# foreshortened along its length. A genuinely face-on palm scores ~0.72 there.
# Selecting on it reported the palm 45 mm too short.
#
# Units: hand breadths, wrist at the origin, knuckle row along +x, fingers at
# negative y (image convention: y is DOWN, so the MCPs sit ABOVE the wrist).
_CANONICAL_PALM_SHAPE = {
    0:  (0.0000, 0.0000),
    5:  (-0.6531, -1.1172),
    9:  (-0.3126, -1.2413),
    13: (0.0274, -1.2270),
    17: (0.3469, -1.1172),
}


# ⭐⭐ THE 6th POINT, AND IT IS THE ONE THAT BREAKS THE DEGENERACY. A PLANAR rigid
# body cannot be lifted unambiguously from 2D by ANY method -- PnP, homography and
# structure-from-motion all inherit the two-fold ambiguity, worst exactly when the
# plane faces the camera (`verify_planar_pnp.py` §2.4: 7.0 deg of out-of-plane error
# face-on vs 0.6 deg at 75 deg of tilt). That is why T6's first attempt lost to Horn,
# and it is a property of the MODEL, not of the solver.
#
# ⭐ THUMB_CMC sits OFF the palm plane, so it breaks it. The project already depends
# on exactly this: U7's chirality works BECAUSE the thumb is off-plane, and the
# README records that "3D alone does not remove the chirality dependence; the THUMB
# is what does."
#
# ⛔ NOT B4's REJECTED `PALM_AND_TIPS`. That added finger TIPS, which MOVE, and their
# motion was fitted as rotation (p95 9.85 -> 27.79 in real play). THUMB_CMC is a base
# joint on the rigid plate.
#
# ⚠ x, y MEASURED from 2D face-on frames the same way as the palm (43 sessions,
# 2792 frames; x IQR 0.040, y IQR 0.120). ⛔ z is NOT measurable from face-on 2D --
# at face-on the thumb projects into the palm plane whatever its depth -- so it is a
# swept parameter. `palm_geometry.palm_plane_thickness` reports a corpus median of
# 8.8 mm, quoted as a SCALE ONLY and deliberately not trusted, since it is computed
# from the world z that is under indictment.
THUMB_CMC = 1
_CANONICAL_THUMB_XY = (-0.5394, -0.1834)
CANONICAL_THUMB_Z_M = 0.010


def canonical_palm(breadth_m=None, mirrored=False, with_thumb=False, thumb_z_m=None):
    """The rigid 5-point palm as coplanar 3-vectors, in `PALM_LANDMARKS` order.

    `breadth_m` scales the model; it defaults to the (5,17) hand breadth in
    `palm_depth.NOMINAL_SPAN_M`. ⭐ The ROTATION a planar PnP recovers does not
    depend on it -- only the translation does -- so this is an anchor, not a
    tuning knob.

    ⚠ `mirrored` IS A REAL DEGREE OF FREEDOM, NOT A CONVENIENCE. A left palm is
    the mirror of a right one, and a planar target has a two-fold pose ambiguity
    that IPPE returns both halves of. **U7's `palm_geometry.geometric_chirality`
    is the disambiguator** (89.7% even at track age 0, vs the handedness label's
    76.8%). The convention is pinned by golden vector: the default model has a
    POSITIVE `signed_palm_area`, the mirrored one negative. ⛔ Do not "simplify"
    by dropping one -- a chirality convention that lives in only one of the two
    tools is exactly how §13.6.1 shipped inverted.
    """
    if breadth_m is None:
        breadth_m = _NOMINAL_BREADTH_M
    sx = -1.0 if mirrored else 1.0
    out = [(sx * _CANONICAL_PALM_SHAPE[lm][0] * breadth_m,
            _CANONICAL_PALM_SHAPE[lm][1] * breadth_m,
            0.0)
           for lm in PALM_LANDMARKS]
    if with_thumb:
        z = CANONICAL_THUMB_Z_M if thumb_z_m is None else thumb_z_m
        out.append((sx * _CANONICAL_THUMB_XY[0] * breadth_m,
                    _CANONICAL_THUMB_XY[1] * breadth_m,
                    z))
    return out


def canonical_palm_indices(with_thumb=False):
    """The landmark ids `canonical_palm` returns, in the same order."""
    return PALM_LANDMARKS + ((THUMB_CMC,) if with_thumb else ())


# --------------------------------------------------------------------------
# T6 -- THE ESTIMATOR: pose from the PIXELS, never from predicted depth
# --------------------------------------------------------------------------
# ⚠ THE DEFAULT FRAME SIZE IS A REAL DEPENDENCY, NOT A DETAIL. PnP needs
# intrinsics, `palm_geometry.focal_px` needs the frame WIDTH, and the principal
# point needs both. Every corpus recording and both tools currently capture
# 640x480, which is why that is the default -- but a caller at another resolution
# MUST `configure()` it, or the focal is wrong and the error lands on exactly the
# out-of-plane component T6 exists to fix.
DEFAULT_FRAME_SIZE = (640, 480)

# ⛔⛔ A CHIRALITY CONVENTION CONSTANT. §13.6.1 shipped INVERTED and survived every
# automated check, so this is NOT derived by reasoning -- it is MEASURED against
# the corpus and pinned by `analysis/verify_planar_pnp.py` §3. It says which sign
# of the model normal's z-component corresponds to the BACK of the hand facing the
# camera. If a future change makes rotation invert, look here first.
#
# ⭐⭐ AND MEASURING IT WAS NOT CEREMONY: the value reasoned out from the canonical
# model's construction was **TRUE, and the corpus says FALSE** -- 9403 frames over
# 61 sessions in the band where both cues are trustworthy split 81.2% / 18.8% the
# other way. Shipping the derived value would have inverted every rotation, which
# is precisely how §13.6.1 happened.
BACK_TO_CAMERA_NZ_POSITIVE = False

# ⭐ Re-referencing targets. `_REREF_TARGET_NZ` is cos(tilt) of the ideal reference:
# the measured sweet spot is 46-66 deg of tilt (|nz| 0.41..0.69), where the planar
# PnP is neither face-on-ambiguous nor edge-on-singular. `_REREF_MARGIN` stops it
# thrashing between two near-equal frames.
_REREF_TARGET_NZ = 0.55
_REREF_MARGIN = 0.05


class PlanarPnP:
    """T6: the pose that best PROJECTS the canonical palm onto the PIXEL landmarks.

    Same interface as `Horn`, so it is a drop-in at the two call sites and the
    A/B harnesses pick it up from `estimators()` unchanged.

    ⭐⭐ WHY IT IS A REPLACEMENT AND NOT A FILTER. `Horn` fits 3D<->3D against
    `world_landmarks`, so MediaPipe's predicted depth enters the rotation. This
    consumes only `px`. ⚠ `world` is still read, but ONLY for a SIGN -- U7's
    chirality -- which is stable under any positive scaling of z and therefore does
    not reintroduce the defect. That distinction is the whole design; do not
    "simplify" by feeding world coordinates into the fit.

    ⭐ THE MODEL MIRROR IS NOT A SEPARATE DECISION, and noticing this removed half
    the intended machinery: for a PLANAR model, mirroring the model is the same
    thing as flipping the pose over, so `planar_pnp.solve`'s two candidates ALREADY
    span both hand chiralities. There is exactly ONE binary to resolve -- which way
    the palm plate faces -- and U7 answers it.
    """

    def __init__(self, frame_size=DEFAULT_FRAME_SIZE, mode="ref",
                 with_thumb=False, thumb_z_m=None, reref=False):
        self.mode = mode
        self.with_thumb = with_thumb
        self.thumb_z_m = thumb_z_m
        self.reref = reref
        self.name = (f"planar_pnp_{mode}" + ("_thumb" if with_thumb else "")
                     + ("_reref" if reref else ""))
        self.configure(frame_size)

    # ⭐⭐ CONDITIONING. |R[2][2]| is cos(tilt) of the model plane -- free from the
    # solve, identical for both twins, and needing no ground truth. A planar PnP is
    # DEGENERATE face-on (|nz| -> 1) and also degrades once the plane turns edge-on
    # (the homography goes singular), so the best reference is MID-TILT. The measured
    # sweet spot is 46-66 deg of tilt, i.e. |nz| ~ 0.41..0.69.
    @staticmethod
    def _conditioning(r):
        return -abs(abs(r[2][2]) - _REREF_TARGET_NZ)

    def configure(self, frame_size):
        """Set the capture resolution. ⚠ Call this if you are not at 640x480."""
        self.frame_size = tuple(frame_size)
        self.focal = PG.focal_px(self.frame_size)
        self.cx = self.frame_size[0] / 2.0
        self.cy = self.frame_size[1] / 2.0
        self.indices = canonical_palm_indices(self.with_thumb)
        self.model = canonical_palm(with_thumb=self.with_thumb,
                                    thumb_z_m=self.thumb_z_m)

    # -- step 4: which of the two candidates ---------------------------------
    def _choose(self, cands, px, world, prev):
        """CHIRALITY decides at grab; CONTINUITY holds the branch during the hold.

        ⛔ NOT reprojection error as the primary cue. A palm at 0.5 m is nearly
        orthographic, so the twins reproject almost identically -- measured, taking
        the lower error picks WRONG 11-22% of the time below 10 deg of tilt and is a
        coin flip face-on. It is a last resort only.

        ⭐⭐ AND NOT CHIRALITY EVERY FRAME EITHER, WHICH IS THE NON-OBVIOUS PART.
        U7's facing cue agrees with the fitted tilt sign **81%** of the corpus
        overall (89-95% in the best-conditioned bands) -- good, but re-deciding at
        that rate EVERY frame would flip the branch mid-hold, and the twins sit ~95
        deg apart, so a flip is a violent visible jump. **Within a hold the branch
        must be CONSISTENT, not independently re-derived**: the pose moves
        continuously, the twin does not, so continuity is a far stronger
        discriminator than an 81% cue. Same shape as DR-2's sign FREEZE.
        ⚠ The cost is a wrong branch at grab persisting through the hold. That is
        the trade step 6's A/B has to price; the alternative if it bites is a
        DEBOUNCED chirality override (`palm_geometry.ChiralityResolver`'s pattern),
        not a per-frame one.
        """
        if len(cands) == 1:
            return cands[0]
        if prev is not None:            # inside a hold: hold the branch
            return min(cands, key=lambda c: _quat_distance(quat_from_matrix(c[0]), prev))
        # ⭐ at grab. DR-2's gate: near edge-on the 2D palm sign is a coin flip, so
        # SUPPRESS rather than guess and let reprojection take it.
        if world is not None and not PG.is_edge_on(px):
            hand = None
            if PG.GEOMETRIC_CHIRALITY:
                try:
                    hand = PG.geometric_chirality(world)
                except (IndexError, TypeError):
                    hand = None
            if hand is not None:
                back = PG.is_thumb_outward(px, hand)
                want = 1.0 if (back == BACK_TO_CAMERA_NZ_POSITIVE) else -1.0
                for c in cands:
                    if (1.0 if c[0][2][2] >= 0.0 else -1.0) == want:
                        return c
        return cands[0]                 # last resort: best reprojection

    def _pose(self, px, world, prev):
        pts = _pts2(px, self.indices)
        if pts is None or self.focal is None:
            return None
        cands = PPNP.solve(self.model, pts, self.focal, self.cx, self.cy)
        if not cands:
            return None
        return self._choose(cands, px, world, prev)

    # -- the Horn-compatible interface ---------------------------------------
    def freeze(self, px, world):
        got = self._pose(px, world, None)
        if got is None:
            return None
        q0 = quat_from_matrix(got[0])
        return {"r0": got[0], "q0": q0, "prev": q0, "seed": None, "sstep": None,
                "cond": self._conditioning(got[0]),
                "base": _IDENTITY}

    def delta(self, state, px, world):
        if state is None:
            return None
        got = self._pose(px, world, state["prev"])
        if got is None:
            return None
        q = quat_from_matrix(got[0])
        state["prev"] = q
        # rotation taking the REFERENCE pose onto the current one: R * R0^T,
        # then composed with whatever was accumulated before the last re-reference.
        r0 = state["r0"]
        rd = [[sum(got[0][i][k] * r0[j][k] for k in range(3)) for j in range(3)]
              for i in range(3)]
        d = _qmul(quat_from_matrix(rd), state["base"])
        if state["seed"] and sum(a * b for a, b in zip(d, state["seed"])) < 0:
            d = tuple(-c for c in d)    # sign continuity, as `horn_rotation` does
        state["seed"] = d
        # ⭐⭐ OPPORTUNISTIC RE-REFERENCING. ⛔ In the GAME the reference is the GRAB
        # frame, which the PLAYER chooses -- we cannot ask for a grab at 46 deg of
        # tilt. So instead of choosing the reference, MIGRATE to a better-conditioned
        # one as soon as the hand offers it, carrying the accumulated rotation across
        # so the output is CONTINUOUS BY CONSTRUCTION (no pop at the switch).
        if self.reref:
            c = self._conditioning(got[0])
            if c > state["cond"] + _REREF_MARGIN:
                state["r0"] = got[0]
                state["cond"] = c
                state["base"] = d       # everything accumulated so far is preserved
        return d

    def step(self, state, px, world):
        """Degrees rotated since the previous call -- the stability metric."""
        if state is None:
            return None
        got = self._pose(px, world, state["sstep"] or state["prev"])
        if got is None:
            return None
        q = quat_from_matrix(got[0])
        prev = state["sstep"] or state["prev"]
        state["sstep"] = q
        return quat_angle_deg(prev, q)


def _pts2(px, indices):
    try:
        return [(float(px[i][0]), float(px[i][1])) for i in indices]
    except (IndexError, TypeError, ValueError):
        return None


def _quat_distance(a, b):
    return 1.0 - abs(sum(x * y for x, y in zip(a, b)))


# --------------------------------------------------------------------------
# T6b -- THE WORLD-Z GATE: keep Horn, fix only the coordinate that is wrong
# --------------------------------------------------------------------------
# ⭐⭐ WHY A GATE AND NOT ANOTHER ESTIMATOR. Two A10 rejects (planar PnP, and the
# 6-point thumb model) both failed the SAME way, and together they name the shape of
# the answer:
#   * HORN's problem is BIAS -- it consumes a fabricated z, so its grab reference is
#     tilted ~25 deg before the hand moves; but it averages five 3D points and is
#     therefore STABLE (production step() p95 25.51 deg).
#   * EVERY PnP VARIANT's problem is VARIANCE -- a per-frame algebraic solve from
#     five or six noisy 2D points has no such averaging, and lost the jitter bar by
#     2.5x (62.79 deg).
# So the remedy must KEEP Horn's averaging and attack ONLY its bias. That is this.
#
# ⭐ THE GEOMETRY, and it needs no calibration and no absolute depth. For a palm
# landmark at true distance L from the wrist, seen with an in-plane offset p, the
# out-of-plane component cannot exceed `sqrt(L^2 - p^2)` -- a right triangle. The
# scale is recovered parameter-free from the landmarks themselves: foreshortening
# only ever SHORTENS, so the largest observed (pixels / true-length) ratio over the
# palm's own spans is the un-foreshortened scale.
#
# ⛔⛔ IT MAY ONLY EVER **REDUCE** |z|, NEVER INVENT IT, and that asymmetry is the
# whole safety argument. Face-on, geometry forces z_max ~ 0 and the fabricated z is
# clamped away -- which is exactly where it was measured wrong (|world z|/|world xy|
# median 0.40 when it should be ~0). Genuinely tilted, z_max is large and MediaPipe's
# z passes through untouched. **A gate that can only remove what is provably
# impossible cannot manufacture a new defect.**
#
# ⚠ x and y are LEFT ALONE. They were measured faithful (1.1 deg vs the pixels'
# 1.2 deg on a face-on frame); only z is under indictment.
def gate_world_z(px, world, indices=PALM_LANDMARKS, model=None):
    """Clamp each palm landmark's world z to what the hand's proportions permit.

    Returns a NEW list; `world` is not mutated. Returns `world` unchanged if the
    geometry is unusable, so the caller degrades to today's behaviour rather than
    to a guess.
    """
    try:
        wrist_px = px[indices[0]]
        wrist_w = world[indices[0]]
    except (IndexError, TypeError):
        return world
    if model is None:
        model = canonical_palm()
    # true wrist->landmark lengths, and the observed pixel offsets
    spans = []
    for k, lm in enumerate(indices):
        if k == 0:
            continue
        try:
            d = math.hypot(px[lm][0] - wrist_px[0], px[lm][1] - wrist_px[1])
        except (IndexError, TypeError):
            return world
        m = model[k]
        L = math.sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2])
        if L < 1e-9 or d < 1e-9:
            continue
        spans.append((lm, d, L))
    if not spans:
        return world
    # ⭐ scale, parameter-free: foreshortening only shortens, so the LARGEST
    # observed-per-true ratio is the un-foreshortened one.
    # ⛔⛔ IT MUST RANGE OVER **ALL PAIRS**, NOT JUST THE WRIST-RELATIVE SPANS, AND
    # THE FIRST VERSION GOT THIS WRONG. Every wrist->MCP span carries a length
    # component, so a PITCH foreshortens all of them AT ONCE -- leaving no
    # un-foreshortened reference, underestimating the scale, and over-clamping z.
    # Measured cost of that bug: pitch mean-axis 5.5 -> 43.0 deg. The knuckle-row
    # span (5<->17) is untouched by pitch, and some pair is near-unforeshortened
    # under any single-axis rotation, so all pairs it is.
    scale = 0.0
    for a in range(len(indices)):
        for b in range(a + 1, len(indices)):
            la, lb = indices[a], indices[b]
            try:
                d = math.hypot(px[la][0] - px[lb][0], px[la][1] - px[lb][1])
            except (IndexError, TypeError):
                return world
            ma, mb = model[a], model[b]
            L = math.sqrt(sum((ma[k] - mb[k]) ** 2 for k in range(3)))
            if L > 1e-9 and d > 1e-9:
                scale = max(scale, d / L)
    if scale < 1e-9:
        return world
    out = list(world)
    for lm, d, L in spans:
        inplane = d / scale
        zmax = math.sqrt(max(0.0, L * L - inplane * inplane))
        zrel = world[lm][2] - wrist_w[2]
        if abs(zrel) <= zmax:
            continue                                   # plausible -- leave it alone
        clamped = zmax if zrel >= 0 else -zmax
        out[lm] = (world[lm][0], world[lm][1], wrist_w[2] + clamped)
    return out


class GatedHorn:
    """Horn, unchanged, fed world landmarks whose z has been geometrically gated.

    ⭐ Deliberately a WRAPPER, not a fork: the fit, the quaternion maths, the sign
    continuity and the five-point averaging are the shipped ones, so anything this
    changes is attributable to the gate alone.
    """

    def __init__(self, indices=PALM_LANDMARKS, mode="ref"):
        self.indices = tuple(indices)
        self.inner = Horn(indices, mode)
        self.name = f"gated_horn_{mode}"
        self.model = canonical_palm()

    def _g(self, px, world):
        return gate_world_z(px, world, self.indices, self.model)

    def freeze(self, px, world):
        return self.inner.freeze(px, self._g(px, world))

    def delta(self, state, px, world):
        return self.inner.delta(state, px, self._g(px, world))

    def step(self, state, px, world):
        return self.inner.step(state, px, self._g(px, world))


def estimators():
    """The candidate set the A/B compares, in a fixed order."""
    return [
        GramSchmidt(),
        Horn(PALM_LANDMARKS, "ref"),
        Horn(PALM_LANDMARKS, "ff"),
        Horn(PALM_AND_TIPS, "ref"),
        Horn(PALM_AND_TIPS, "ff"),
        PlanarPnP(),
    ]
