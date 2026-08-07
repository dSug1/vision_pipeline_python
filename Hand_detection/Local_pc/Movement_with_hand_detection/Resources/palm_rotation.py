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


def estimators():
    """The candidate set the A/B compares, in a fixed order."""
    return [
        GramSchmidt(),
        Horn(PALM_LANDMARKS, "ref"),
        Horn(PALM_LANDMARKS, "ff"),
        Horn(PALM_AND_TIPS, "ref"),
        Horn(PALM_AND_TIPS, "ff"),
    ]
