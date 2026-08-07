"""Golden vectors for `Resources/palm_rotation.py` (§16.13).

⭐ THE LOAD-BEARING TEST IS §4, CHIRALITY. M6b's Q1 exists because an SVD-based
rotation fit can silently return a REFLECTION and invert handedness, and this
project has shipped exactly that bug once (§13.6.1). Horn's method answers with
a QUATERNION, which is a proper rotation by construction -- §4 proves the
property holds rather than trusting the argument, including on the mirrored
input MediaPipe actually produces (§0.9: a physical right hand is labelled
"Left").

⚠ Do not edit the expectations to match a port. The port is wrong, not this.

    .venv/Scripts/python.exe analysis/verify_palm_rotation.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import palm_rotation as PR

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def rot_matrix(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    return ((c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s),
            (y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s),
            (z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)))


def apply_m(M, v):
    return tuple(M[r][0] * v[0] + M[r][1] * v[1] + M[r][2] * v[2] for r in range(3))


def q_to_m(q):
    w, x, y, z = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
            (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
            (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)))


def det3(M):
    return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
            - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
            + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))


# A realistic palm constellation (metres), plus the four arc tips
PALM = [(0.00, 0.045, 0.0), (-0.040, -0.020, 0.0), (-0.013, -0.030, 0.0),
        (0.013, -0.028, 0.0), (0.040, -0.018, 0.0)]
TIPS = [(-0.045, -0.115, 0.008), (-0.015, -0.125, 0.006),
        (0.015, -0.120, 0.006), (0.042, -0.100, 0.008)]

print("=" * 78)
print("palm_rotation (§16.13) -- golden vectors")
print("=" * 78)

# ------------------------------------------------------------ 1. exactness
print("\n1. EXACT RECOVERY of a known rotation")
for axis, deg in (((0, 0, 1), 30.0), ((0, 1, 0), 75.0), ((1, 0, 0), -50.0),
                  ((1, 1, 1), 120.0), ((0, 1, 0), 179.0)):
    M = rot_matrix(axis, deg)
    src = PALM + TIPS
    dst = [apply_m(M, p) for p in src]
    q = PR.horn_rotation(src, dst)
    got = q_to_m(q)
    err = max(abs(got[r][c] - M[r][c]) for r in range(3) for c in range(3))
    check(f"axis {axis} {deg:+.0f} deg recovered", err < 1e-6, f"max elem err {err:.2e}")

print("\n1b. TRANSLATION IS ABSORBED (centroids are subtracted)")
M = rot_matrix((0, 0, 1), 40.0)
src = PALM + TIPS
dst = [tuple(v + t for v, t in zip(apply_m(M, p), (0.5, -0.3, 0.2))) for p in src]
q = PR.horn_rotation(src, dst)
err = max(abs(q_to_m(q)[r][c] - M[r][c]) for r in range(3) for c in range(3))
check("a large translation does not enter the rotation", err < 1e-6, f"err {err:.2e}")

# ------------------------------------------------------------ 2. robustness
print("\n2. NOISE: least squares must BEAT a 3-point construction")
import random
random.seed(7)
M = rot_matrix((0.3, 1, 0.2), 25.0)
errs_all, errs_three = [], []
for _ in range(200):
    src = PALM + TIPS
    dst = [tuple(c + random.gauss(0, 0.002) for c in apply_m(M, p)) for p in src]
    qa = PR.horn_rotation(src, dst)
    qb = PR.horn_rotation(src[:3], dst[:3])          # a minimal 3-point fit
    for q, acc in ((qa, errs_all), (qb, errs_three)):
        if q:
            acc.append(max(abs(q_to_m(q)[r][c] - M[r][c])
                           for r in range(3) for c in range(3)))
ma = sum(errs_all) / len(errs_all)
mt = sum(errs_three) / len(errs_three)
check("9 points beat 3 points under noise", ma < mt,
      f"9pt mean err {ma:.4f} vs 3pt {mt:.4f}  ({mt/ma:.1f}x)")

# ------------------------------------------------------- 3. weights honoured
print("\n3. WEIGHTS")
M = rot_matrix((0, 0, 1), 20.0)
src = PALM + TIPS
dst = [apply_m(M, p) for p in src]
dst[-1] = (5.0, -5.0, 5.0)                            # one catastrophic outlier
q_bad = PR.horn_rotation(src, dst)
q_ok = PR.horn_rotation(src, dst, weights=[1.0] * 8 + [0.0])
e_bad = max(abs(q_to_m(q_bad)[r][c] - M[r][c]) for r in range(3) for c in range(3))
e_ok = max(abs(q_to_m(q_ok)[r][c] - M[r][c]) for r in range(3) for c in range(3))
check("a zero weight removes a point entirely", e_ok < 1e-6, f"err {e_ok:.2e}")
check("...and that point really was ruining it", e_bad > 0.1, f"unweighted err {e_bad:.3f}")

# ------------------------------------------- 4. ⭐⭐ CHIRALITY, THE KEY TEST
print("\n4. ⭐⭐ CHIRALITY -- a reflection must be UNREPRESENTABLE (§13.6.1, M6b Q1)")
dets = []
for axis, deg in (((0, 0, 1), 15.0), ((0, 1, 0), 90.0), ((1, 0, 0), 170.0)):
    M = rot_matrix(axis, deg)
    src = PALM + TIPS
    dst = [apply_m(M, p) for p in src]
    dets.append(det3(q_to_m(PR.horn_rotation(src, dst))))
check("every fit has det = +1 (proper rotation)",
      all(abs(d - 1.0) < 1e-9 for d in dets), f"dets {[round(d,12) for d in dets]}")

# feed it a genuinely MIRRORED target -- the fit must NOT return a reflection
src = PALM + TIPS
mirrored = [(-p[0], p[1], p[2]) for p in src]
q = PR.horn_rotation(src, mirrored)
d = det3(q_to_m(q))
check("a MIRRORED target still yields det = +1, never a reflection",
      abs(d - 1.0) < 1e-9, f"det {d:.12f}")
print("     ^ SVD-based Kabsch needs an explicit det sign fix here; omit it and")
print("       handedness inverts silently. Horn cannot express a reflection.")

# the mirrored hand MediaPipe actually delivers (§0.9)
M = rot_matrix((0, 1, 0), 35.0)
srcm = [(-p[0], p[1], p[2]) for p in PALM + TIPS]
dstm = [apply_m(M, p) for p in srcm]
q = PR.horn_rotation(srcm, dstm)
check("holds on MIRRORED input (§0.9: a right hand is labelled 'Left')",
      abs(det3(q_to_m(q)) - 1.0) < 1e-9 and
      max(abs(q_to_m(q)[r][c] - M[r][c]) for r in range(3) for c in range(3)) < 1e-6)

# ------------------------------------------------------- 5. the estimators
print("\n5. THE ESTIMATOR INTERFACE")


def hand(M=None, t=(0.0, 0.0, 0.0)):
    world = [(0.0, 0.0, 0.0)] * 21
    src = dict(zip(PR.PALM_LANDMARKS, PALM))
    src.update(dict(zip(PR.ARC_TIPS, TIPS)))
    for i, p in src.items():
        v = apply_m(M, p) if M else p
        world[i] = tuple(a + b for a, b in zip(v, t))
    px = [(320.0 + 1400.0 * w[0], 240.0 + 1400.0 * w[1]) for w in world]
    return px, world


for est in PR.estimators():
    px0, w0 = hand()
    st = est.freeze(px0, w0)
    d0 = est.delta(st, px0, w0)
    ident = PR.quat_angle_deg(d0, (1.0, 0.0, 0.0, 0.0))
    check(f"{est.name}: delta at grab is identity", ident is not None and ident < 1e-4,
          f"{ident:.2e} deg")

for est in PR.estimators():
    px0, w0 = hand()
    st = est.freeze(px0, w0)
    est.delta(st, px0, w0)
    total = 0.0
    for k in range(1, 13):                     # 12 steps of 5 deg about z
        pxk, wk = hand(rot_matrix((0, 0, 1), 5.0 * k))
        dk = est.delta(st, pxk, wk)
    got = PR.quat_angle_deg(dk, (1.0, 0.0, 0.0, 0.0))
    check(f"{est.name}: 60 deg accumulated correctly", abs(got - 60.0) < 0.05,
          f"{got:.3f} deg")

print("\n5b. TRANSLATION MUST NOT PRODUCE ROTATION")
for est in PR.estimators():
    px0, w0 = hand()
    st = est.freeze(px0, w0)
    est.delta(st, px0, w0)
    pxt, wt = hand(None, (0.10, -0.07, 0.03))
    d = PR.quat_angle_deg(est.delta(st, pxt, wt), (1.0, 0.0, 0.0, 0.0))
    check(f"{est.name}: pure translation -> 0 deg", d is not None and d < 1e-3,
          f"{d:.2e} deg")

print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
