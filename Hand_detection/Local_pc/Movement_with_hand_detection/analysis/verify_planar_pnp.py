"""Golden vectors for T6's 2D<->3D planar palm fit. Section 1: the CANONICAL PALM.

⭐ WRITTEN BEFORE THE IMPLEMENTATION, and before the JS/Swift port exists, which is
rule 6 and the U3 precedent -- the very first run of the last such file caught a
real banker's-rounding bug. Every number here is hand-checkable.

⚠⚠ WHY THIS FILE EXISTS AT ALL, i.e. what went wrong with the handoff's step 2.
`HANDOFF_T6_ORIENTATION_FROM_2D.md` §3.2 says to "build the 3D model from
`palm_depth.NOMINAL_SPAN_M`". **THAT IS NOT SUFFICIENT AND THE GAP IS STRUCTURAL**:
`NOMINAL_SPAN_M` carries FOUR distances -- (5,17), (0,9), (0,5), (0,17) -- while a
planar 5-point model has 2*5-3 = 7 shape degrees of freedom.
  * (0, 5, 17) IS fully determined: three points, three distances.
  * 9 gets ONE constraint and needs two.
  * 13 gets NONE -- no span in `NOMINAL_SPAN_M` touches the ring MCP.
And the tempting patch ("9 and 13 lie on the segment 5->17") is provably wrong:
|0-9| = |0-5| = 0.100 with 9 laterally BETWEEN 5 and 17 forces 9 off that line,
because the knuckle row bows away from the wrist.

⭐ SO THE SHAPE IS MEASURED FROM THE 2D PIXEL LANDMARKS and `NOMINAL_SPAN_M` is
kept as the METRIC ANCHOR plus an INDEPENDENT CHECK. That split is deliberate:
  * ⛔ NOT from `world_landmarks` -- the M2 audit found they carry no
    pose-consistent skeleton (0/21 bones inside target), so a length taken from
    them measures the ESTIMATOR, not a hand. `NOMINAL_SPAN_M`'s own comment gives
    exactly this reason for using anthropometry.
  * ⭐ 2D pixels are the one signal T6's whole premise says is GOOD.
  * ⭐ Only the (5,17) breadth is shared between the two sources, so the other
    THREE spans are a genuine cross-validation. They agree to **10 mm**.

⭐⭐ AND THE SCALE BARELY MATTERS, WHICH IS WHY THE 10 MM IS COMFORTABLE. For a
planar target, scaling the model scales the recovered TRANSLATION and leaves the
ROTATION untouched. T6 only consumes the rotation. It is the SHAPE that has to be
right, and the shape is what was measured.

Provenance of the shape (see §1 constants): 59 corpus sessions, 2792 face-on
frames, selected as "both palm spans within 5% of that session's own p99" --
foreshortening only ever SHORTENS, so a session's p99 is that span's
un-foreshortened value and the ratio of two p99s is scale-free.

⛔⛔ A REJECTED SELECTION RULE, KEPT SO IT IS NOT RE-TRIED: `edge_on_measure >= 0.90`
looks like a face-on filter and is the OPPOSITE of one. It is |sin(theta)| between
the two palm vectors, so it peaks when those vectors are 90 deg apart IN THE IMAGE
-- which happens when the palm is FORESHORTENED ALONG ITS LENGTH. A genuinely
face-on anatomical palm scores about **0.72**. Selecting on it reported the palm
45 mm too short. Trap #5 in a new costume: a shape measure wearing a quality
gate's clothes.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_planar_pnp.py
"""

import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Resources"))
import palm_rotation as PR          # noqa: E402
import palm_depth as PD             # noqa: E402
import palm_geometry as PG          # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(f"    {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def close(a, b, tol):
    return abs(a - b) <= tol


def dist(p, q):
    return math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3)))


print("=" * 78)
print("verify_planar_pnp -- §1  THE CANONICAL PALM")
print("=" * 78)

idx = {lm: i for i, lm in enumerate(PR.PALM_LANDMARKS)}
palm = PR.canonical_palm()

# -- 1. structure -----------------------------------------------------------
print("\n  1. structure and the port contract")
check("returns one point per PALM_LANDMARKS",
      len(palm) == len(PR.PALM_LANDMARKS),
      f"{len(palm)} points for {PR.PALM_LANDMARKS}")
check("every point is a 3-vector of floats",
      all(len(p) == 3 and all(isinstance(c, float) for c in p) for p in palm))
check("PLANAR -- every z is exactly 0.0",
      all(p[2] == 0.0 for p in palm),
      "a PnP that is not planar cannot use IPPE's two-solution form")

# -- 2. the metric anchor ---------------------------------------------------
print("\n  2. the (5,17) hand-breadth anchor is exact, not approximate")
b = PD.NOMINAL_SPAN_M[(5, 17)]
w = dist(palm[idx[5]], palm[idx[17]])
check("|5-17| == NOMINAL_SPAN_M[(5,17)]", close(w, b, 1e-12),
      f"{w:.6f} m vs {b:.6f} m")

# -- 3. the independent cross-check -----------------------------------------
# ⭐ THE POINT OF THIS BLOCK: the shape came from the 2D corpus and the metres from
# anthropometry, sharing ONLY the (5,17) anchor above. These three spans are
# therefore a real cross-validation and not a restatement.
print("\n  3. the three spans the measured shape did NOT get to choose")
print(f"       {'span':>8s}  {'NOMINAL_SPAN_M':>14s}  {'model':>9s}  {'delta':>9s}")
worst = 0.0
for (a, c), nominal in sorted(PD.NOMINAL_SPAN_M.items()):
    if (a, c) == (5, 17):
        continue
    m = dist(palm[idx[a]], palm[idx[c]])
    print(f"       {str((a,c)):>8s}  {nominal:14.3f}  {m:9.3f}  {m-nominal:+9.4f}")
    worst = max(worst, abs(m - nominal))
check("anthropometry and the 2D corpus agree within 12 mm", worst <= 0.012,
      f"worst {worst*1000:.1f} mm")

# -- 4. shape, which is what the rotation actually depends on ---------------
print("\n  4. shape ratio inside the measured corpus band")
ratio = dist(palm[idx[0]], palm[idx[9]]) / w
check("palm length / breadth within the corpus p10..p90 (1.092..1.386)",
      1.092 <= ratio <= 1.386, f"{ratio:.3f}  (corpus median 1.263)")
check("and within 10% of the anthropometric 1.176",
      abs(ratio - 1.176) / 1.176 <= 0.10, f"{ratio:.3f} vs 1.176")

# -- 5. scale invariance ----------------------------------------------------
# ⭐ A PLANAR PnP's ROTATION IS SCALE-FREE. Asserting the model scales exactly
# linearly is what lets the 10 mm above be a comfort rather than a correctness bug,
# and it is the property the port must preserve.
print("\n  5. exact scale linearity (rotation must not depend on the anchor)")
twice = PR.canonical_palm(2.0 * b)
check("canonical_palm(2b) == 2 * canonical_palm(b), exactly",
      all(close(twice[i][k], 2.0 * palm[i][k], 1e-12)
          for i in range(len(palm)) for k in range(3)))
ratio2 = dist(twice[idx[0]], twice[idx[9]]) / dist(twice[idx[5]], twice[idx[17]])
check("every shape ratio is unchanged by scaling", close(ratio2, ratio, 1e-12),
      f"{ratio2:.9f} vs {ratio:.9f}")

# -- 6. chirality -----------------------------------------------------------
# ⭐ THE MIRROR IS A REAL DEGREE OF FREEDOM, NOT AN ACCIDENT. A left palm is the
# mirror of a right one, and the planar PnP's two-fold ambiguity is resolved by
# U7's `geometric_chirality` (handoff §3.3). So the model must offer BOTH and the
# convention has to be pinned here, or §13.6.1's production-only inversion happens
# again in a new place.
print("\n  6. chirality convention, pinned")
flat = [(p[0], p[1]) for p in palm]
area = PG.signed_palm_area([flat[idx[lm]] if lm in idx else (0.0, 0.0)
                            for lm in range(18)])
check("the default model's signed_palm_area is POSITIVE", area > 0.0,
      f"{area:.6f}")
mir = PR.canonical_palm(mirrored=True)
fm = [(p[0], p[1]) for p in mir]
marea = PG.signed_palm_area([fm[idx[lm]] if lm in idx else (0.0, 0.0)
                             for lm in range(18)])
check("the mirrored model's signed_palm_area is NEGATIVE", marea < 0.0,
      f"{marea:.6f}")
check("mirroring flips the sign and nothing else", close(abs(marea), abs(area), 1e-12))
check("mirroring preserves every NOMINAL span",
      all(close(dist(mir[idx[a]], mir[idx[c]]), dist(palm[idx[a]], palm[idx[c]]), 1e-12)
          for (a, c) in PD.NOMINAL_SPAN_M))

# -- 7. conditioning --------------------------------------------------------
# ⚠ A homography needs 4 points in GENERAL POSITION. The four MCPs are nearly
# collinear (they are a knuckle ROW), so the wrist is what conditions the solve --
# assert it is genuinely off that line, or the DLT is near-singular and the pose
# will be noise.
print("\n  7. conditioning -- the wrist must be well off the knuckle row")
p5, p17, p0 = palm[idx[5]], palm[idx[17]], palm[idx[0]]
ex = ((p17[0] - p5[0]) / w, (p17[1] - p5[1]) / w)
off = abs(-(p0[0] - p5[0]) * ex[1] + (p0[1] - p5[1]) * ex[0])
check("wrist offset from the knuckle row >= 0.5 * breadth", off >= 0.5 * w,
      f"{off:.4f} m = {off/w:.3f} breadths")
rowspread = max(abs(-(palm[idx[m]][0] - p5[0]) * ex[1] + (palm[idx[m]][1] - p5[1]) * ex[0])
                for m in (9, 13))
check("the knuckle row BOWS (9 and 13 off the 5-17 line), as anatomy requires",
      rowspread > 1e-4, f"{rowspread*1000:.2f} mm of bow")


# ==========================================================================
# §2  THE PLANAR PnP SOLVE
# ==========================================================================
import planar_pnp as PP               # noqa: E402

FOCAL, CX, CY = PG.focal_px((640, 480)), 320.0, 240.0
MODEL = [(p[0], p[1]) for p in palm]


def rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]
    if axis == "y":
        return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def mul(a, bb):
    return [[sum(a[r][k] * bb[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def project(r, t, model, focal=None, cx=CX, cy=CY):
    focal = FOCAL if focal is None else focal
    out = []
    for mx, my in model:
        x = r[0][0] * mx + r[0][1] * my + t[0]
        y = r[1][0] * mx + r[1][1] * my + t[1]
        z = r[2][0] * mx + r[2][1] * my + t[2]
        out.append((focal * x / z + cx, focal * y / z + cy))
    return out


def angle_between(a, bb):
    tr = sum(a[k][0] * bb[k][0] + a[k][1] * bb[k][1] + a[k][2] * bb[k][2] for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


print("\n" + "=" * 78)
print("verify_planar_pnp -- §2  THE PLANAR PnP SOLVE")
print("=" * 78)

# -- 2.1 exact round-trip ---------------------------------------------------
# ⭐ THE CORE CLAIM. Project a known pose, hand the pixels back, demand the pose
# returns. ⚠ Poses stop at 75 deg deliberately: at 90 deg the palm is edge-on, its
# projection collapses to a LINE and the homography is singular -- that is a
# genuine property of one RGB camera (DR-2 suppresses there), not a solver bug.
print("\n  2.1 exact recovery of a known pose (noise-free)")
T0 = (0.02, -0.01, 0.50)
CASES = [
    ("face-on", [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
    ("yaw 30", rot("y", 30)),
    ("yaw 60", rot("y", 60)),
    ("yaw 75", rot("y", 75)),
    ("pitch 40", rot("x", 40)),
    ("pitch -55", rot("x", -55)),
    ("roll 50", rot("z", 50)),
    ("yaw 45 + pitch 25", mul(rot("y", 45), rot("x", 25))),
    ("all three", mul(mul(rot("y", 35), rot("x", -20)), rot("z", 15))),
]
print(f"       {'case':>18s}  {'axis err':>9s}  {'t err (mm)':>11s}  {'rms px':>9s}")
worst_ang, worst_t = 0.0, 0.0
for name, R in CASES:
    px = project(R, T0, MODEL)
    sol = PP.solve(MODEL, px, FOCAL, CX, CY)
    if not sol:
        check(f"2.1 {name}: a solution exists", False)
        continue
    Rr, tr, err = sol[0]
    ang = angle_between(R, Rr)
    dt = math.sqrt(sum((tr[i] - T0[i]) ** 2 for i in range(3))) * 1000.0
    print(f"       {name:>18s}  {ang:8.5f}d  {dt:11.5f}  {err:9.2e}")
    worst_ang, worst_t = max(worst_ang, ang), max(worst_t, dt)
check("every pose recovered to < 0.01 deg", worst_ang < 0.01, f"worst {worst_ang:.6f} deg")
check("every translation recovered to < 0.01 mm", worst_t < 0.01, f"worst {worst_t:.6f} mm")

# -- 2.2 both solutions, and the mirror relation ----------------------------
# ⭐⭐ THE TWO-FOLD AMBIGUITY IS THE CONTRACT, not an artefact -- step 4 needs both
# to hand to U7's chirality. Assert the twin is a proper ROTATION: a reflection
# here would invert chirality silently, which is exactly §13.6.1.
print("\n  2.2 the planar two-fold ambiguity")
R = rot("y", 45)
px = project(R, T0, MODEL)
sol = PP.solve(MODEL, px, FOCAL, CX, CY)
check("two candidate poses are returned", len(sol) == 2, f"{len(sol)}")
check("they are sorted by reprojection error",
      len(sol) == 2 and sol[0][2] <= sol[1][2],
      f"{sol[0][2]:.3e} <= {sol[1][2]:.3e}" if len(sol) == 2 else "")
check("the true pose is the better one", angle_between(R, sol[0][0]) < 0.01,
      f"{angle_between(R, sol[0][0]):.6f} deg")
if len(sol) == 2:
    check("the twin is genuinely different", angle_between(R, sol[1][0]) > 1.0,
          f"{angle_between(R, sol[1][0]):.2f} deg away")
tw = PP._twin(R)
det = (tw[0][0] * (tw[1][1] * tw[2][2] - tw[1][2] * tw[2][1])
       - tw[0][1] * (tw[1][0] * tw[2][2] - tw[1][2] * tw[2][0])
       + tw[0][2] * (tw[1][0] * tw[2][1] - tw[1][1] * tw[2][0]))
check("_twin returns a PROPER rotation (det = +1), never a reflection",
      close(det, 1.0, 1e-12), f"det {det:.12f}")
check("_twin is an involution", all(close(PP._twin(tw)[i][j], R[i][j], 1e-12)
                                    for i in range(3) for j in range(3)))
check("a face-on pose is its own twin (the ambiguity vanishes at zero tilt)",
      all(close(PP._twin([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])[i][j],
                1.0 if i == j else 0.0, 1e-12) for i in range(3) for j in range(3)))

# -- 2.3 scale invariance of the ROTATION -----------------------------------
# ⭐⭐ THE PROPERTY THAT MAKES §1's 10 mm ANCHOR DISAGREEMENT HARMLESS. Scale the
# model, and the rotation must not move at all -- only the translation scales.
print("\n  2.3 rotation is scale-free; only translation carries the anchor")
big = [(x * 2.0, y * 2.0) for x, y in MODEL]
R = mul(rot("y", 50), rot("x", -15))
s1 = PP.solve(MODEL, project(R, T0, MODEL), FOCAL, CX, CY)
s2 = PP.solve(big, project(R, (T0[0] * 2, T0[1] * 2, T0[2] * 2), big), FOCAL, CX, CY)
check("a 2x model gives the SAME rotation",
      bool(s1) and bool(s2) and angle_between(s1[0][0], s2[0][0]) < 1e-6,
      f"{angle_between(s1[0][0], s2[0][0]):.3e} deg")
check("...and exactly 2x the translation",
      bool(s1) and bool(s2) and all(close(s2[0][1][i], 2.0 * s1[0][1][i], 1e-6)
                                    for i in range(3)))

# -- 2.4 noise and CONDITIONING vs TILT --------------------------------------
# ⭐⭐ THE MOST DECISION-RELEVANT BLOCK IN THIS FILE: it predicts whether T6 can pass
# A10's JITTER bar, the criterion that killed the 9-point constellation. A planar
# target's OUT-OF-PLANE tilt is weakly observable when the plane is nearly parallel
# to the image (the two ambiguous poses merge there); the IN-PLANE component stays
# well determined. Measured, 400 draws at +/-1 px, medians:
#
#     tilt |  out-of-plane  |  in-plane
#       0d |     4.27d      |    0.24d
#      10d |     4.38d      |    0.49d
#      30d |     1.48d      |    0.41d
#      75d |     0.56d      |    0.36d
#
# ⭐ TWO CONSEQUENCES TO CARRY INTO STEP 6:
#   * the defect T6 exists to fix lives at **60-90 deg of hand turn**, which is
#     exactly where this is most accurate (p95 ~1.5 deg);
#   * ROLL is the in-plane component, flat-excellent at every tilt -- and it is the
#     axis Horn already gets RIGHT (gain 1.02) and A10 forbids regressing.
# ⚠ THE OPEN RISK IS NEAR-FACE-ON HANDLING, where p95 reaches 10-21 deg. Horn's own
# jitter p95 is 25.41 deg on a real take, so this is not obviously worse -- but it
# is what the A/B must actually check, not assume.
#
# ⛔⛔ AN LCG WAS USED HERE FIRST AND WAS THE WRONG INSTRUMENT -- kept so it is not
# reintroduced "for determinism". `(1103515245*s+12345) mod 2^31` has consecutive
# tuples on a lattice (Marsaglia) and this draws TEN values per frame, so the
# "noise" was structured. **The tell was a NON-MONOTONIC tail**: p95 fine at 45 deg,
# **72 deg** at 60 deg, fine again at 75 deg. Mersenne Twister with a fixed seed is
# equally reproducible and actually distributed -- the 72 deg became 1.6.
print("\n  2.4 pixel noise, and conditioning vs TILT (seeded MT, +/- 1.0 px)")
rng = random.Random(987654321)
DRAWS = 200
print(f"       {'tilt':>6s}  {'out-of-plane':>13s}  {'in-plane':>9s}")
oop_by_tilt, inp_by_tilt = {}, {}
for tilt in (0, 10, 30, 60, 75):
    R = rot("y", tilt)
    oops, inps = [], []
    for _ in range(DRAWS):
        px = [(u + rng.uniform(-1.0, 1.0), v + rng.uniform(-1.0, 1.0))
              for u, v in project(R, T0, MODEL)]
        sol = PP.solve(MODEL, px, FOCAL, CX, CY)
        if not sol:
            continue
        m = [[sum(R[k][i] * sol[0][0][k][j] for k in range(3)) for j in range(3)]
             for i in range(3)]
        q = PP.quat_from_matrix(m)
        w = max(-1.0, min(1.0, abs(q[0])))
        d = math.degrees(2.0 * math.acos(w))
        s = math.sqrt(max(0.0, 1.0 - w * w))
        if s < 1e-12:
            oops.append(0.0)
            inps.append(0.0)
            continue
        oops.append(d * math.hypot(q[1] / s, q[2] / s))
        inps.append(d * abs(q[3] / s))
    oop_by_tilt[tilt] = sorted(oops)[len(oops) // 2]
    inp_by_tilt[tilt] = sorted(inps)[len(inps) // 2]
    print(f"       {tilt:5d}d  {oop_by_tilt[tilt]:12.2f}d  {inp_by_tilt[tilt]:8.2f}d")

check("IN-PLANE (roll) stays under 1 deg at EVERY tilt -- the axis A10 protects",
      max(inp_by_tilt.values()) < 1.0, f"worst {max(inp_by_tilt.values()):.2f} deg")
check("OUT-OF-PLANE is accurate where the defect lives (60-90 deg of turn)",
      oop_by_tilt[60] < 1.5 and oop_by_tilt[75] < 1.5,
      f"{oop_by_tilt[60]:.2f}d at 60, {oop_by_tilt[75]:.2f}d at 75")
check("...and DEGRADES toward face-on, as the planar geometry REQUIRES",
      oop_by_tilt[0] > 2.0 * oop_by_tilt[60],
      f"{oop_by_tilt[0]:.2f}d at 0 vs {oop_by_tilt[60]:.2f}d at 60")

# -- 2.5 refusals ------------------------------------------------------------
# ⭐ REFUSING IS A FEATURE HERE. The house rule from DR-2, U8 and 4.2's decision 1
# is SUPPRESS, DO NOT GUESS -- a confidently wrong pose is the failure mode this
# project keeps paying for.
print("\n  2.5 degenerate input is REFUSED, not guessed")
check("fewer than 4 points -> []", PP.solve(MODEL[:3], [(0.0, 0.0)] * 3, FOCAL, CX, CY) == [])
check("mismatched lengths -> []", PP.solve(MODEL, [(0.0, 0.0)] * 3, FOCAL, CX, CY) == [])
check("a null focal -> []", PP.solve(MODEL, project(rot("y", 20), T0, MODEL), None, CX, CY) == [])
collinear = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)]
check("collinear MODEL points -> [] (the homography is singular)",
      PP.solve(collinear, project(rot("y", 20), T0, MODEL), FOCAL, CX, CY) == [])
allsame = [(300.0, 200.0)] * 5
check("collapsed IMAGE points -> []", PP.solve(MODEL, allsame, FOCAL, CX, CY) == [])

# -- 2.6 the quaternion bridge ----------------------------------------------
print("\n  2.6 quat_from_matrix, including the near-180 deg branch")
worst_q = 0.0
for axis in ("x", "y", "z"):
    for deg in (5, 90, 179, 179.9):
        R = rot(axis, deg)
        q = PP.quat_from_matrix(R)
        check_ang = 2.0 * math.degrees(math.acos(min(1.0, abs(q[0]))))
        worst_q = max(worst_q, abs(check_ang - deg))
        check(f"{axis} {deg} deg -> quaternion angle", abs(check_ang - deg) < 1e-6, "")
check("unit norm everywhere",
      close(sum(c * c for c in PP.quat_from_matrix(rot("y", 179.9))), 1.0, 1e-12))

print()
print("=" * 78)
if FAILURES:
    print(f"FAILED: {len(FAILURES)}")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ALL GOLDEN VECTORS PASS  (§1 canonical palm, §2 the planar PnP solve)")
print("⚠ §3 (chirality disambiguation) lands with step 4 -- this file is written to grow.")
