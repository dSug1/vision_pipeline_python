"""T6 -- POSE OF A PLANAR TARGET FROM 2D<->3D CORRESPONDENCES. Stdlib, numpy-free.

⭐⭐ WHY THIS EXISTS. `palm_rotation.Horn` fits 3D<->3D: the palm constellation
against MediaPipe's `world_landmarks`, **depth included**. Measurement established
that the predicted depth is what breaks the rotation -- ROLL, the one axis needing
no depth, measures gain 1.02 while YAW (1.13, over) and PITCH (0.74, under) are
wrong in OPPOSITE directions, and scaling world z slides the yaw tilt 14.5 -> 0.6
deg. This module solves the pose that best **projects** a canonical palm onto the
observed **pixel** landmarks, so predicted z is never consumed at all.

⛔⛔ THE PORT CONTRACT IS WHY THIS IS HAND-ROLLED. `cv2.solvePnP` would end U3 (the
web/mobile port) as a transliteration job. Everything here is stdlib and
numpy-free, deterministic, no side effects -- the same contract `palm_rotation`,
`palm_geometry` and `palm_depth` hold.

⭐ AND THE ALGORITHM IS DELIBERATELY THE OLD, UNENCUMBERED ONE. The literature
prescribes IPPE (Collins & Bartoli, IJCV 2014) for planar targets, and OpenCV
bundles an implementation. **We use neither.** What is implemented here is the
textbook chain -- normalised DLT homography (Abdel-Aziz & Karara 1971; Hartley's
normalisation 1997), Zhang-style decomposition (2000), the classical planar
two-fold twin, then Gauss-Newton on reprojection error. All of it is decades-old
prior art, which keeps N13's licence question from ever arising, and it reaches the
same two minima IPPE derives analytically. ⚠ If IPPE's closed form is ever wanted
for speed, it is a drop-in for `_initial_pose` + `_twin` -- but measure first, this
is not on any hot path (5 points, ~10 iterations).

⭐⭐ THE TWO SOLUTIONS ARE THE POINT, NOT AN ARTEFACT. A near-planar target has a
genuine two-fold pose ambiguity: tilt the plane toward or away from the camera and
it projects almost identically (exactly so under orthography). Under the image-plane
mirror `S = diag(1, 1, -1)` the twin of `R` is `S R S` -- the model's x and y image
components are preserved and only the depth components flip. Both are returned,
each with its reprojection error.
⛔ **DO NOT pick by reprojection error alone.** It separates the two only when the
perspective effect is strong, and a palm at 0.5 m is nearly orthographic. **U7's
`palm_geometry.geometric_chirality` is the disambiguator** (measured 89.7% even at
track age 0, vs the handedness label's 76.8%); reprojection error breaks the tie
when chirality is provisional, and temporal continuity is the last resort. That
selection is step 4 and lives in `palm_rotation.PlanarPnP`, NOT here -- this module
answers "which poses are consistent with these pixels", never "which hand is it".

⚠ UNITS. `image_xy`, `focal` and the principal point must share one unit (pixels).
The model points are metres. Rotation is unaffected by the model's scale -- only the
translation carries it -- which `analysis/verify_planar_pnp.py` §5 pins.
"""

import math

_JACOBI_SWEEPS = 60
_GN_ITERATIONS = 12
_GN_DAMPING = 1e-9
_MIRROR = (1.0, 1.0, -1.0)


# --------------------------------------------------------------------------
# Linear algebra, only as much as the chain above needs
# --------------------------------------------------------------------------
def _jacobi_eigen(a, n):
    """Eigen-decomposition of a symmetric n x n matrix. Returns (values, vectors).

    `vectors[i][j]` is component i of eigenvector j, matching the column
    convention `palm_rotation.horn_rotation` already uses for its 4x4.

    ⚠ JACOBI, NOT POWER ITERATION, AND THE REASON IS ON RECORD: power iteration on
    a shifted matrix converges at lambda2/lambda1, and any shift large enough to
    guarantee positivity drives that ratio to ~1 -- 60 iterations still left up to
    2.0 of element error in `palm_rotation`, i.e. a completely wrong rotation.
    Jacobi is exact for a small symmetric matrix in a handful of sweeps.
    """
    m = [row[:] for row in a]
    v = [[1.0 if r == c else 0.0 for c in range(n)] for r in range(n)]
    for _sweep in range(_JACOBI_SWEEPS):
        off = 0.0
        pr = pc = 0
        big = 0.0
        for r in range(n):
            for c in range(r + 1, n):
                x = abs(m[r][c])
                off += x * x
                if x > big:
                    big, pr, pc = x, r, c
        if off < 1e-30:
            break
        app, aqq, apq = m[pr][pr], m[pc][pc], m[pr][pc]
        theta = (aqq - app) / (2.0 * apq)
        t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
        cs = 1.0 / math.sqrt(t * t + 1.0)
        sn = t * cs
        for k in range(n):
            akp, akq = m[k][pr], m[k][pc]
            m[k][pr] = cs * akp - sn * akq
            m[k][pc] = sn * akp + cs * akq
        for k in range(n):
            akp, akq = m[pr][k], m[pc][k]
            m[pr][k] = cs * akp - sn * akq
            m[pc][k] = sn * akp + cs * akq
        for k in range(n):
            vkp, vkq = v[k][pr], v[k][pc]
            v[k][pr] = cs * vkp - sn * vkq
            v[k][pc] = sn * vkp + cs * vkq
    return [m[i][i] for i in range(n)], v


def _solve_linear(a, b, n):
    """Gaussian elimination with partial pivoting. Returns None if singular."""
    m = [a[r][:] + [b[r]] for r in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-14:
            return None
        m[col], m[piv] = m[piv], m[col]
        d = m[col][col]
        for c in range(col, n + 1):
            m[col][c] /= d
        for r in range(n):
            if r == col:
                continue
            f = m[r][col]
            if f == 0.0:
                continue
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    return [m[r][n] for r in range(n)]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm3(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return None if n < 1e-12 else (v[0] / n, v[1] / n, v[2] / n)


def _rodrigues(w):
    """Rotation matrix (rows) for the axis-angle vector `w`."""
    th = math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])
    if th < 1e-12:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    kx, ky, kz = w[0] / th, w[1] / th, w[2] / th
    c, s, t = math.cos(th), math.sin(th), 1.0 - math.cos(th)
    return [
        [t * kx * kx + c,      t * kx * ky - s * kz, t * kx * kz + s * ky],
        [t * kx * ky + s * kz, t * ky * ky + c,      t * ky * kz - s * kx],
        [t * kx * kz - s * ky, t * ky * kz + s * kx, t * kz * kz + c],
    ]


def _matmul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def _apply(r, p):
    return (r[0][0] * p[0] + r[0][1] * p[1] + r[0][2] * p[2],
            r[1][0] * p[0] + r[1][1] * p[1] + r[1][2] * p[2],
            r[2][0] * p[0] + r[2][1] * p[1] + r[2][2] * p[2])


def quat_from_matrix(r):
    """Unit quaternion (w, x, y, z) from a rotation matrix, branch-stable.

    ⚠ The branch on the largest diagonal term is not an optimisation -- the naive
    `w = sqrt(1 + trace)/2` form loses all precision near 180 deg, which is inside
    the range a hand actually reaches (the yaw take sweeps 142 deg).
    """
    m00, m11, m22 = r[0][0], r[1][1], r[2][2]
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        q = (0.25 * s, (r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s)
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        q = ((r[2][1] - r[1][2]) / s, 0.25 * s, (r[0][1] + r[1][0]) / s, (r[0][2] + r[2][0]) / s)
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        q = ((r[0][2] - r[2][0]) / s, (r[0][1] + r[1][0]) / s, 0.25 * s, (r[1][2] + r[2][1]) / s)
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        q = ((r[1][0] - r[0][1]) / s, (r[0][2] + r[2][0]) / s, (r[1][2] + r[2][1]) / s, 0.25 * s)
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q) if n > 1e-12 else (1.0, 0.0, 0.0, 0.0)


# --------------------------------------------------------------------------
# 1. The homography, by NORMALISED DLT
# --------------------------------------------------------------------------
def homography(model_xy, image_xy):
    """3x3 H (rows) with `image ~ H * model`, from >= 4 planar correspondences.

    ⚠⚠ THE NORMALISATION IS NOT OPTIONAL AND IS NOT COSMETIC. Raw DLT on pixel
    coordinates conditions the 9x9 system on quantities spanning ~1 to ~640, and
    the recovered pose degrades visibly. Hartley's fix -- shift each set's centroid
    to the origin and scale so the mean radius is sqrt(2), solve, then undo -- costs
    a dozen lines and is what makes this usable.
    """
    n = len(model_xy)
    if n < 4 or n != len(image_xy):
        return None

    def _normalise(pts):
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        d = sum(math.hypot(p[0] - cx, p[1] - cy) for p in pts) / len(pts)
        if d < 1e-12:
            return None, None
        s = math.sqrt(2.0) / d
        return ([((p[0] - cx) * s, (p[1] - cy) * s) for p in pts],
                [[s, 0.0, -s * cx], [0.0, s, -s * cy], [0.0, 0.0, 1.0]])

    mp, tm = _normalise(model_xy)
    ip, ti = _normalise(image_xy)
    if mp is None or ip is None:
        return None

    # A is 2n x 9; solve A h = 0 as the smallest eigenvector of A^T A (9x9 sym).
    ata = [[0.0] * 9 for _ in range(9)]
    for (x, y), (u, v) in zip(mp, ip):
        rows = ([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u],
                [0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v])
        for row in rows:
            for i in range(9):
                if row[i] == 0.0:
                    continue
                for j in range(9):
                    ata[i][j] += row[i] * row[j]
    vals, vecs = _jacobi_eigen(ata, 9)
    k = min(range(9), key=lambda i: vals[i])
    h = [vecs[i][k] for i in range(9)]
    hn = [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], h[8]]]

    # denormalise: H = Ti^-1 * Hn * Tm
    si, cxi, cyi = ti[0][0], -ti[0][2] / ti[0][0], -ti[1][2] / ti[1][1]
    tiinv = [[1.0 / si, 0.0, cxi], [0.0, 1.0 / si, cyi], [0.0, 0.0, 1.0]]
    return _matmul(tiinv, _matmul(hn, tm))


# --------------------------------------------------------------------------
# 2. Pose from the homography, and 3. the planar twin
# --------------------------------------------------------------------------
def _initial_pose(h, focal, cx, cy):
    """(R, t) from H, Zhang-style. ⚠ An INITIALISER only -- refined immediately."""
    # K^-1 H, with K = [[f,0,cx],[0,f,cy],[0,0,1]]
    a = [[(h[0][c] - cx * h[2][c]) / focal for c in range(3)],
         [(h[1][c] - cy * h[2][c]) / focal for c in range(3)],
         [h[2][c] for c in range(3)]]
    h1 = (a[0][0], a[1][0], a[2][0])
    h2 = (a[0][1], a[1][1], a[2][1])
    h3 = (a[0][2], a[1][2], a[2][2])
    n1 = math.sqrt(sum(c * c for c in h1))
    n2 = math.sqrt(sum(c * c for c in h2))
    if n1 < 1e-12 or n2 < 1e-12:
        return None
    lam = 2.0 / (n1 + n2)               # the two columns should be equal-length
    t = (h3[0] * lam, h3[1] * lam, h3[2] * lam)
    if t[2] < 0.0:                      # cheirality: the hand is IN FRONT of the lens
        lam, t = -lam, (-t[0], -t[1], -t[2])
    r1 = _norm3((h1[0] * lam, h1[1] * lam, h1[2] * lam))
    if r1 is None:
        return None
    h2l = (h2[0] * lam, h2[1] * lam, h2[2] * lam)
    d = sum(r1[i] * h2l[i] for i in range(3))
    r2 = _norm3((h2l[0] - d * r1[0], h2l[1] - d * r1[1], h2l[2] - d * r1[2]))
    if r2 is None:
        return None
    r3 = _cross(r1, r2)
    return ([[r1[0], r2[0], r3[0]], [r1[1], r2[1], r3[1]], [r1[2], r2[2], r3[2]]], t)


def _twin(r):
    """The planar ambiguity's other pose: `S R S`, with `S = diag(1, 1, -1)`.

    ⭐ WHY THIS IS THE RIGHT MIRROR AND NOT A GUESS. Under orthography the image
    keeps the x and y components of the model axes and discards the z ones, so
    flipping every z leaves the projection identical: r1 -> S r1, r2 -> S r2, and
    r3 = r1 x r2 -> -S r3. Collecting the columns gives exactly `S R S`, whose
    determinant is det(S)^2 det(R) = +1 -- **a rotation, never a reflection.** That
    matters here for the same reason it does in `palm_rotation`: a reflection would
    invert chirality silently (§13.6.1).
    """
    s = _MIRROR
    return [[s[i] * r[i][j] * s[j] for j in range(3)] for i in range(3)]


def _translation_for(r, model_xy, image_xy, focal, cx, cy):
    """Least-squares translation given a fixed rotation. Linear: 2n rows, 3 unknowns."""
    ata = [[0.0] * 3 for _ in range(3)]
    atb = [0.0, 0.0, 0.0]
    for (mx, my, mz), (u, v) in zip(model_xy, image_xy):
        p = _apply(r, (mx, my, mz))
        du, dv = (u - cx) / focal, (v - cy) / focal
        # (p0 + tx) - du*(p2 + tz) = 0  and  (p1 + ty) - dv*(p2 + tz) = 0
        for row, rhs in (((1.0, 0.0, -du), du * p[2] - p[0]),
                         ((0.0, 1.0, -dv), dv * p[2] - p[1])):
            for i in range(3):
                atb[i] += row[i] * rhs
                for j in range(3):
                    ata[i][j] += row[i] * row[j]
    return _solve_linear(ata, atb, 3)


# --------------------------------------------------------------------------
# 4. Reprojection error, and 5. Gauss-Newton refinement
# --------------------------------------------------------------------------
def reprojection_rms(r, t, model_xy, image_xy, focal, cx, cy):
    """RMS reprojection error in pixels. None if any point falls behind the lens."""
    total = 0.0
    for (mx, my, mz), (u, v) in zip(model_xy, image_xy):
        p = _apply(r, (mx, my, mz))
        z = p[2] + t[2]
        if z <= 1e-9:
            return None
        du = focal * (p[0] + t[0]) / z + cx - u
        dv = focal * (p[1] + t[1]) / z + cy - v
        total += du * du + dv * dv
    return math.sqrt(total / len(model_xy))


def _refine(r, t, model_xy, image_xy, focal, cx, cy):
    """Gauss-Newton on reprojection error, 6 parameters (omega, t).

    ⭐ THIS IS WHAT MAKES THE TWO REPROJECTION ERRORS COMPARABLE. `_twin` is exact
    only under orthography, so the mirrored pose starts slightly off ITS own local
    minimum; scoring the two before refining would compare a settled solution
    against an unsettled one and systematically favour the first. Both are refined,
    then both are scored.

    ⚠ The update is a LEFT-multiplied increment, `R <- exp(omega^) R`, so the
    parameterisation never leaves SO(3) and no re-orthonormalisation is needed.
    """
    best_r, best_t = r, t
    best = reprojection_rms(r, t, model_xy, image_xy, focal, cx, cy)
    if best is None:
        return None
    for _ in range(_GN_ITERATIONS):
        ata = [[0.0] * 6 for _ in range(6)]
        atb = [0.0] * 6
        ok = True
        for (mx, my, mz), (u, v) in zip(model_xy, image_xy):
            p = _apply(best_r, (mx, my, mz))
            x, y, z = p[0] + best_t[0], p[1] + best_t[1], p[2] + best_t[2]
            if z <= 1e-9:
                ok = False
                break
            iz = 1.0 / z
            # d(proj)/d(camera point)
            dudp = (focal * iz, 0.0, -focal * x * iz * iz)
            dvdp = (0.0, focal * iz, -focal * y * iz * iz)
            # d(camera point)/d(omega) = -[p]^ ; d/d(t) = I
            gx = ((0.0, p[2], -p[1]), (-p[2], 0.0, p[0]), (p[1], -p[0], 0.0))
            ju = [sum(dudp[k] * gx[k][c] for k in range(3)) for c in range(3)] + list(dudp)
            jv = [sum(dvdp[k] * gx[k][c] for k in range(3)) for c in range(3)] + list(dvdp)
            for jrow, res in ((ju, focal * x * iz + cx - u), (jv, focal * y * iz + cy - v)):
                for i in range(6):
                    atb[i] -= jrow[i] * res
                    for j in range(6):
                        ata[i][j] += jrow[i] * jrow[j]
        if not ok:
            break
        for i in range(6):
            ata[i][i] += _GN_DAMPING
        d = _solve_linear(ata, atb, 6)
        if d is None:
            break
        cand_r = _matmul(_rodrigues((d[0], d[1], d[2])), best_r)
        cand_t = (best_t[0] + d[3], best_t[1] + d[4], best_t[2] + d[5])
        err = reprojection_rms(cand_r, cand_t, model_xy, image_xy, focal, cx, cy)
        if err is None or err >= best:
            break                       # converged, or the step did not help
        best_r, best_t, best = cand_r, cand_t, err
        if best < 1e-12:
            break
    return best_r, best_t, best


# --------------------------------------------------------------------------
# The entry point
# --------------------------------------------------------------------------
def solve(model_xy, image_xy, focal, cx, cy):
    """Both poses consistent with these correspondences, best reprojection first.

    `model_xy`  planar model points, metres, in the model's own plane (z = 0);
    `image_xy`  the observed pixels, in correspondence;
    `focal`, `cx`, `cy`  intrinsics, in the SAME unit as `image_xy`.

    Returns `[(R, t, rms_px), ...]` -- normally two entries, one if the twin fails
    to refine. `R` is row-major. Empty list if the input is degenerate.

    ⛔ THIS FUNCTION DOES NOT CHOOSE. Returning both is the contract; the caller
    disambiguates with U7's geometric chirality (see the module docstring).

    ⭐⭐ THE MODEL MAY BE NON-PLANAR, AND THAT IS THE POINT OF THE 3-TUPLE FORM.
    Points may be given as (x, y) -- implicitly z = 0 -- or as (x, y, z). A PLANAR
    model is DEGENERATE for depth-from-2D by construction: the two candidate poses
    merge as the plane turns to face the camera, measured at 7.0 deg of out-of-plane
    error face-on against 0.6 deg at 75 deg of tilt. **An off-plane point breaks
    that**, which is why `palm_rotation.canonical_palm(with_thumb=True)` exists.
    ⚠ The homography INITIALISER still needs >= 4 COPLANAR points, so the model must
    contain a planar subset of at least four -- the palm plate always does. The
    refinement and both reprojection errors then use EVERY point, planar or not, and
    it is the off-plane ones that make the twins separable.
    """
    if len(model_xy) < 4 or len(model_xy) != len(image_xy) or focal is None or focal <= 0.0:
        return []
    m3 = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in model_xy]
    flat = [(p[0], p[1]) for p in m3 if abs(p[2]) < 1e-9]
    flat_img = [uv for p, uv in zip(m3, image_xy) if abs(p[2]) < 1e-9]
    if len(flat) < 4:
        return []
    h = homography(flat, flat_img)
    if h is None:
        return []
    seed = _initial_pose(h, focal, cx, cy)
    if seed is None:
        return []
    out = []
    for rot in (seed[0], _twin(seed[0])):
        t = _translation_for(rot, m3, image_xy, focal, cx, cy)
        if t is None or t[2] <= 1e-9:
            continue
        got = _refine(rot, tuple(t), m3, image_xy, focal, cx, cy)
        if got is not None:
            out.append(got)
    out.sort(key=lambda e: e[2])
    return out
