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

print()
print("=" * 78)
if FAILURES:
    print(f"FAILED: {len(FAILURES)}")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ALL GOLDEN VECTORS PASS  (§1 canonical palm)")
print("⚠ §2 (the IPPE solve itself) lands with step 3 -- this file is written to grow.")
