"""Golden vectors for `Resources/palm_anchor.py` (B4), on synthetic hands.

⭐ THE LOAD-BEARING TEST IS §5, THE Z-RETROFIT REDUCTION. Everything else here
checks the anchor does what it says; §5 checks that the 3D-native form collapses
EXACTLY onto the 2D similarity form when the offset lies in the image plane. That
is what makes "the retrofit is one function" a proven statement rather than a
hopeful one -- the U3 discipline, which earned its keep by catching a real
banker's-vs-half-up rounding divergence before a port existed.

⚠ Do not edit the expectations to match a port. The port is wrong, not this.

    .venv/Scripts/python.exe analysis/verify_palm_anchor.py
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

from Resources import palm_anchor as PA
from Resources import hand_blocks as HB

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


# --------------------------------------------------------------------------
# A synthetic hand we control exactly: a flat palm in the z = 0 plane, which we
# then rotate/translate/scale at will.
# --------------------------------------------------------------------------
BASE_WORLD = {
    0:  (0.00, 0.045, 0.0),      # wrist
    5:  (-0.040, -0.020, 0.0),   # index MCP
    9:  (-0.013, -0.030, 0.0),   # middle MCP
    13: (0.013, -0.028, 0.0),    # ring MCP
    17: (0.040, -0.018, 0.0),    # pinky MCP
}


def rot_axis(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    return (
        (c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s),
        (y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s),
        (z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)),
    )


def apply_rot(M, v):
    return (M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2],
            M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2],
            M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2])


def make_hand(rot=None, tx=320.0, ty=240.0, k=1400.0):
    """Returns (pixel_landmarks, world_landmarks) for a 21-point hand whose palm
    is BASE_WORLD rotated by `rot`, projected orthographically at scale `k`."""
    world = [(0.0, 0.0, 0.0)] * 21
    px = [(0.0, 0.0)] * 21
    for i, v in BASE_WORLD.items():
        w = apply_rot(rot, v) if rot else v
        world[i] = w
        px[i] = (tx + k * w[0], ty + k * w[1])
    # fill the finger landmarks so len() checks pass; they are never read here
    for i in range(21):
        if i not in BASE_WORLD:
            world[i] = (0.0, 0.0, 0.0)
            px[i] = (tx, ty)
    return px, world


print("=" * 78)
print("palm_anchor (B4) -- golden vectors")
print("=" * 78)

anchor = PA.PalmAnchor()

# ------------------------------------------------------------------ 1. no-pop
print("\n1. NO-POP AT GRAB -- must be EXACT, not approximate")
px, world = make_hand()
for target in ((320.0, 240.0), (400.0, 300.0), (120.0, 90.0), (639.0, 1.0)):
    st = anchor.freeze(target, px, world)
    got = anchor.apply(st, px, world)
    err = math.dist(got, target)
    check(f"grab at {target} returns itself", err < 1e-9, f"err={err:.2e} px")

# ------------------------------------------------- 2. pure translation follows
print("\n2. PURE TRANSLATION -- the offset rides along, unchanged")
st = anchor.freeze((400.0, 300.0), px, world)
px2, world2 = make_hand(tx=320.0 + 55.0, ty=240.0 - 30.0)
got = anchor.apply(st, px2, world2)
check("cube translates with the palm", math.dist(got, (455.0, 270.0)) < 1e-6,
      f"got {tuple(round(v, 4) for v in got)}")

# ------------------------------------------------------ 3. rotation orbits it
print("\n3. ROTATION IN THE IMAGE PLANE -- the offset orbits the palm")
st = anchor.freeze((320.0 + 70.0, 240.0), px, world)     # 70 px to the right
px3, world3 = make_hand(rot=rot_axis((0, 0, 1), 90.0))
got = anchor.apply(st, px3, world3)
# a +90 deg rotation about z takes (+70, 0) to (0, +70) in image coords
check("90 deg in-plane rotation moves the offset 90 deg",
      math.dist(got, (320.0, 240.0 + 70.0)) < 1e-5,
      f"got {tuple(round(v, 3) for v in got)} want (320.0, 310.0)")

# ------------------------------------------ 4. out-of-plane foreshortens (⭐)
print("\n4. ⭐ OUT-OF-PLANE TILT FORESHORTENS ANISOTROPICALLY")
st = anchor.freeze((320.0 + 70.0, 240.0), px, world)      # offset along +x
for deg, name in ((60.0, "60 deg"), (80.0, "80 deg")):
    p, w = make_hand(rot=rot_axis((0, 1, 0), deg))         # yaw about the y axis
    got = anchor.apply(st, p, w)
    dx = got[0] - 320.0
    dy = abs(got[1] - 240.0)
    want = 70.0 * math.cos(math.radians(deg))
    check(f"offset along the tilt axis shortens by cos({name})",
          abs(dx - want) < 1e-4, f"dx={dx:.3f} want {want:.3f}")
    check(f"    and does NOT move perpendicular ({name})", dy < 1e-4, f"dy={dy:.2e}")
st_y = anchor.freeze((320.0, 240.0 + 70.0), px, world)     # offset along +y
p, w = make_hand(rot=rot_axis((0, 1, 0), 60.0))
got = anchor.apply(st_y, p, w)
check("an offset PERPENDICULAR to the tilt axis is NOT shortened",
      abs((got[1] - 240.0) - 70.0) < 1e-4, f"dy={got[1]-240.0:.3f} want 70.000")
print("     ^ this is what a scalar 2D scale term cannot do: it would shrink")
print("       both by the same factor. §16.5 measured that cost as 2.5x jitter.")

# ------------------------------------------------- 5. ⭐ THE Z-RETROFIT PROOF
print("\n5. ⭐⭐ Z-RETROFIT REDUCTION -- 3D form == 2D similarity form at z=0")
print("     With the palm in the image plane the module must reproduce")
print("     P = o + s*(R.x*ex + R.y*ey) EXACTLY. If this ever fails, the")
print("     'retrofit is one function' claim is void.")


def two_d_reference(target, px_g, w_g, px_t, w_t):
    """The flat 2D similarity anchor, computed independently."""
    o_g = HB.palm_position(px_g)
    s_g = HB.palm_scale(px_g)
    ex = (px_g[17][0] - px_g[5][0], px_g[17][1] - px_g[5][1])
    n = math.hypot(*ex)
    ex = (ex[0] / n, ex[1] / n)
    ey = (-ex[1], ex[0])
    d = (target[0] - o_g[0], target[1] - o_g[1])
    R = ((d[0] * ex[0] + d[1] * ex[1]) / s_g, (d[0] * ey[0] + d[1] * ey[1]) / s_g)
    o_t = HB.palm_position(px_t)
    s_t = HB.palm_scale(px_t)
    ex2 = (px_t[17][0] - px_t[5][0], px_t[17][1] - px_t[5][1])
    n2 = math.hypot(*ex2)
    ex2 = (ex2[0] / n2, ex2[1] / n2)
    ey2 = (-ex2[1], ex2[0])
    return (o_t[0] + s_t * (R[0] * ex2[0] + R[1] * ey2[0]),
            o_t[1] + s_t * (R[0] * ex2[1] + R[1] * ey2[1]))


worst = 0.0
for deg in (0.0, 15.0, 45.0, 90.0, 180.0, 275.0):
    for tx, ty, k in ((320.0, 240.0, 1400.0), (200.0, 400.0, 900.0)):
        pg, wg = make_hand()
        pt, wt = make_hand(rot=rot_axis((0, 0, 1), deg), tx=tx, ty=ty, k=k)
        target = (320.0 + 63.0, 240.0 - 21.0)
        st5 = anchor.freeze(target, pg, wg)
        got3d = anchor.apply(st5, pt, wt)
        got2d = two_d_reference(target, pg, wg, pt, wt)
        worst = max(worst, math.dist(got3d, got2d))
check("in-plane poses: 3D form reproduces the 2D form", worst < 1e-6,
      f"worst disagreement {worst:.2e} px over 12 poses")

# -------------------------------------------------------- 6. no fingertip path
print("\n6. ⭐ THE WHOLE POINT: fingertips cannot move the cube")
px6, world6 = make_hand()
st6 = anchor.freeze((400.0, 300.0), px6, world6)
before = anchor.apply(st6, px6, world6)
for i in (4, 8, 12, 16, 20):                       # throw every fingertip 200 px
    px6[i] = (px6[i][0] + 200.0, px6[i][1] - 150.0)
    world6[i] = (world6[i][0] + 0.15, world6[i][1] - 0.1, 0.05)
after = anchor.apply(st6, px6, world6)
check("moving all 5 fingertips moves the cube by 0.000 px",
      math.dist(before, after) < 1e-12,
      f"moved {math.dist(before, after):.2e} px  (§14.1 moves up to 17.51 px)")

# ------------------------------------------------------------- 7. degeneracy
print("\n7. DEGENERACY IS REPORTED, NOT GUESSED")
flat = [(320.0, 240.0)] * 21
flatw = [(0.0, 0.0, 0.0)] * 21
check("collapsed palm -> freeze returns None", anchor.freeze((1.0, 1.0), flat, flatw) is None)
check("collapsed palm -> apply returns None",
      anchor.apply(st6, flat, flatw) is None)
check("apply(None) returns None", anchor.apply(None, px, world) is None)

print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
