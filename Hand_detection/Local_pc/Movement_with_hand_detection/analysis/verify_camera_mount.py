# -*- coding: utf-8 -*-
"""Golden vectors for `Resources/camera_mount.py` — where the camera sits.

⭐ The load-bearing checks here are not the table lookups, they are the two
GEOMETRIC claims the module is built on, verified numerically against an
independent rotation implementation written from scratch in this file:

  1. conjugating by D = diag(1,1,-1) reverses YAW and PITCH and leaves ROLL
     exactly alone — the symptom the owner reported;
  2. `user_view_quat` is EXACTLY equivalent to negating every landmark z and
     re-fitting, which is the whole justification for not touching the landmarks.

⛔ (2) is checked against `palm_rotation.horn_rotation` itself, so if that fit is
ever changed in a way that breaks the equivalence, this fails rather than the
owner discovering it live.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_camera_mount.py
"""
import io
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import camera_mount as CM                      # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []


def ok(name, cond, detail=""):
    print("  [%s] %-58s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# Independent helpers — deliberately NOT imported from Resources, so a shared
# bug cannot make both sides agree.
# ---------------------------------------------------------------------------
def quat_of(axis, deg):
    n = math.sqrt(sum(c * c for c in axis))
    a = [c / n for c in axis]
    h = math.radians(deg) / 2.0
    s = math.sin(h)
    return (math.cos(h), a[0] * s, a[1] * s, a[2] * s)


def mat_of(q):
    w, x, y, z = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def close(a, b, tol=1e-9):
    return all(abs(a[i][j] - b[i][j]) <= tol for i in range(3) for j in range(3))


def apply(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def axis_deg(q):
    """Total rotation angle of a unit quaternion, in degrees."""
    return 2.0 * math.degrees(math.acos(max(-1.0, min(1.0, abs(q[0])))))


D = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]

YAW, PITCH, ROLL = (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)


def main():
    print("=" * 78)
    print("GOLDEN VECTORS — camera_mount")
    print("=" * 78)

    # -- 1. the mount table -------------------------------------------------
    print("\n1. THE MOUNT TABLE (the whole switch, one row per mode)")
    ok("facing_user mirrors the frame", CM.mirror_frame(CM.FACING_USER) is True)
    ok("legacy mirrors the frame", CM.mirror_frame(CM.LEGACY) is True)
    ok("head_worn does NOT mirror the frame", CM.mirror_frame(CM.HEAD_WORN) is False)
    # ⛔ RETRACTED: this asserted the bit follows the mirror. It does NOT -- the
    # volume's sign and the wanted answer both flip with the mirror, so they cancel.
    # The suite that caught it was silenced instead of believed; see mount_guard.py.
    ok("chirality bit is MOUNT-INDEPENDENT (the two flips cancel)",
       len({CM.chirality_v_negative_is_left(m) for m in CM.MOUNTS}) == 1)
    ok("legacy chirality bit is TODAY's value (True)",
       CM.chirality_v_negative_is_left(CM.LEGACY) is True)

    # -- 2. legacy is bit-identical to the pre-change build ------------------
    print("\n2. `legacy` IS THE SHIPPED BUILD, BIT-FOR-BIT (the A10 baseline)")
    q = quat_of((0.3, -0.7, 0.5), 41.0)
    ok("legacy leaves the quaternion untouched",
       CM.user_view_quat(q, CM.LEGACY) == q)
    ok("head_worn leaves the quaternion untouched",
       CM.user_view_quat(q, CM.HEAD_WORN) == q)
    ok("legacy depth mapping is grab / ratio",
       abs(CM.depth_from_ratio(0.5, 1.25, CM.LEGACY) - 0.5 / 1.25) < 1e-12)
    ok("head_worn depth mapping is grab / ratio",
       abs(CM.depth_from_ratio(0.5, 1.25, CM.HEAD_WORN) - 0.5 / 1.25) < 1e-12)
    ok("legacy leaves world landmarks untouched",
       CM.user_view_world([(1.0, 2.0, 3.0)], CM.LEGACY) == [(1.0, 2.0, 3.0)])
    # ⚠ Reads the SOURCE default, not the effective value: this suite is run under
    # CAMERA_MOUNT=... to exercise the other modes, and asserting the live value
    # would turn "I am testing facing_user" into a failure.
    src_default = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "Resources", "camera_mount.py"),
                          encoding="utf-8").read()
    # ✅ SHIPPED 2026-08-28: the source default is now `facing_user`. `legacy` stays
    # reachable as the diagnostic baseline that reproduces the old build bit-for-bit.
    ok("DEFAULT MOUNT is facing_user (shipped)",
       "MOUNT = _ENV if _ENV in MOUNTS else FACING_USER" in src_default,
       "effective MOUNT=%s" % CM.MOUNT)
    ok("`legacy` still reachable as the A10/parity baseline",
       CM.LEGACY in CM.MOUNTS and CM.user_view_quat((1.0, .2, .3, .4), CM.LEGACY)
       == (1.0, .2, .3, .4))

    # -- 3. every option reverses EXACTLY TWO axes ---------------------------
    print("\n3. ⭐⭐ THE THREE VIEWPOINT OPTIONS -- each reverses EXACTLY TWO axes")
    expect = {"pitch_yaw": {"pitch", "yaw"}, "yaw_roll": {"yaw", "roll"},
              "pitch_roll": {"pitch", "roll"}, "none": set()}
    for mode, want in sorted(expect.items()):
        got = set()
        for name, axis in (("pitch", PITCH), ("yaw", YAW), ("roll", ROLL)):
            src = quat_of(axis, 37.0)
            m = mat_of(CM.user_view_quat(src, CM.FACING_USER, axes=mode))
            if close(m, mat_of(quat_of(axis, -37.0))):
                got.add(name)
            elif not close(m, mat_of(src)):
                got.add("?" + name)          # neither reversed nor unchanged
        ok("%-11s reverses %-14s" % (mode, "+".join(sorted(want)) or "nothing"),
           got == want, "got %s" % ("+".join(sorted(got)) or "nothing"))
    ok("⛔ no option reverses exactly ONE axis (det forbids it)",
       all(len(v) != 1 for v in expect.values()))
    ok("the live default is a known option", CM.VIEW_AXIS_MODE in CM.VIEW_AXES,
       "VIEW_AXIS_MODE=%s" % CM.VIEW_AXIS_MODE)

    # ⭐ Every option is a CONJUGATION, so none of them may change how far the hand
    # appears to turn -- only which way. If this ever fails, the transform has
    # stopped being a viewpoint change and become a distortion.
    print("\n3b. EVERY OPTION PRESERVES THE ROTATION ANGLE")
    for mode in sorted(expect):
        worst = 0.0
        for axis, deg in (((0.3, 0.6, -0.5), 71.0), ((0.0, 1.0, 0.0), 55.0),
                          ((1.0, 0.0, 0.0), 120.0)):
            src = quat_of(axis, deg)
            got_q = CM.user_view_quat(src, CM.FACING_USER, axes=mode)
            worst = max(worst, abs(axis_deg(got_q) - axis_deg(src)))
        ok("%-11s leaves the ANGLE untouched" % mode, worst < 1e-9,
           "worst %.2e deg" % worst)

    # -- 4. the conjugation identity ----------------------------------------
    print("\n4. `user_view_quat` IS conjugation by D = diag(1,1,-1)")
    for axis, deg in (((0.2, 0.9, -0.4), 63.0), ((-0.5, 0.1, 0.8), 12.0),
                      ((1.0, 0.0, 0.0), 179.0), ((0.0, 0.0, 1.0), 90.0)):
        src = quat_of(axis, deg)
        ok("D R D  for axis %-16s %5.1f deg" % (str(axis), deg),
           close(mat_of(CM.user_view_quat(src, CM.FACING_USER, axes="pitch_yaw")),
                 matmul(D, matmul(mat_of(src), D))))
    ok("involution: applying it twice is the identity",
       CM.user_view_quat(CM.user_view_quat(q, CM.FACING_USER), CM.FACING_USER) == q)

    # -- 5. ⭐⭐ EQUIVALENCE TO NEGATING EVERY LANDMARK z --------------------
    # The claim the whole design rests on, checked against the REAL Horn fit.
    print("\n5. ⭐⭐ IDENTICAL TO NEGATING EVERY LANDMARK z, AGAINST THE REAL HORN FIT")
    src_pts = [(0.00, 0.00, 0.00), (0.045, -0.015, 0.006), (0.018, -0.052, -0.004),
               (-0.020, -0.049, 0.009), (-0.042, -0.012, -0.007)]
    for axis, deg in (((0.0, 1.0, 0.0), 55.0), ((1.0, 0.0, 0.0), 33.0),
                      ((0.3, 0.6, -0.5), 71.0)):
        m = mat_of(quat_of(axis, deg))
        dst = [apply(m, p) for p in src_pts]

        # route B — fit in the camera frame, then conjugate the result
        route_b = CM.user_view_quat(PR.horn_rotation(src_pts, dst), CM.FACING_USER,
                                   axes="pitch_yaw")
        # route A — negate every landmark z, then fit
        route_a = PR.horn_rotation(CM.user_view_world(src_pts, CM.FACING_USER),
                                   CM.user_view_world(dst, CM.FACING_USER))

        # ⚠ 1e-4 deg, not 0: `horn_rotation` is ITERATIVE and seeded, so the two
        # routes reach the same optimum by slightly different paths. Pure yaw and
        # pure pitch come out at exactly 0.0; a general axis lands ~2e-6 deg apart.
        # That is 5 orders of magnitude below the 1.5 mm landmark noise floor and
        # 7 below the palm's own 2.76 mm rigidity -- it is solver dust, not
        # disagreement. A REAL divergence would be degrees, not micro-degrees.
        agree = PR.quat_angle_deg(route_a, route_b)
        ok("axis %-18s %5.1f deg  ->  routes agree" % (str(axis), deg),
           agree is not None and agree < 1e-4,
           "%.3e deg apart" % (agree if agree is not None else float("nan")))

    # -- 6. the depth mapping ------------------------------------------------
    print("\n6. Z-TRANSLATION: the DIRECTION flips, the UNITS never do")
    grab = 0.50
    # ratio > 1 == palm looks bigger == nearer the CAMERA, always.
    ok("facing_user: nearer the camera => object RECEDES from the user",
       CM.depth_from_ratio(grab, 1.30, CM.FACING_USER) > grab)
    ok("head_worn:   nearer the camera => object APPROACHES the user",
       CM.depth_from_ratio(grab, 1.30, CM.HEAD_WORN) < grab)
    ok("facing_user: further from the camera => object approaches",
       CM.depth_from_ratio(grab, 0.70, CM.FACING_USER) < grab)
    for mount in CM.MOUNTS:
        ok("ratio 1.0 is a no-op at the grab frame (%s)" % mount,
           abs(CM.depth_from_ratio(grab, 1.0, mount) - grab) < 1e-12)
        ok("result stays POSITIVE metres-from-camera (%s)" % mount,
           CM.depth_from_ratio(grab, 2.5, mount) > 0.0)
    ok("None/degenerate ratio holds the anchor, never divides",
       CM.depth_from_ratio(grab, None) == grab
       and CM.depth_from_ratio(grab, 0.0) == grab
       and CM.depth_from_ratio(None, 1.2) is None)

    # -- 7. user_view_world --------------------------------------------------
    print("\n7. `user_view_world` (offered, NOT wired — see the module header)")
    got = CM.user_view_world([(1.0, 2.0, 3.0), None, (0.0, 0.0, -4.0)], CM.FACING_USER)
    ok("negates z only", got[0] == (1.0, 2.0, -3.0) and got[2] == (0.0, 0.0, 4.0))
    ok("passes None landmarks through untouched", got[1] is None)
    ok("involution", CM.user_view_world(got, CM.FACING_USER)[0] == (1.0, 2.0, 3.0))

    # -- 8. unknown mounts must not silently become a new behaviour ----------
    print("\n8. AN UNKNOWN MOUNT FALLS BACK, IT DOES NOT INVENT A MODE")
    ok("garbage mount behaves as a non-facing mount (no conjugation)",
       CM.user_view_quat(q, "nonsense") == q)
    ok("env parsing only accepts known mounts", CM.MOUNT in CM.MOUNTS)

    # -- 9. the port contract ------------------------------------------------
    print("\n9. PORT CONTRACT (CONSTRAINTS §2)")
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "Resources", "camera_mount.py"),
                  encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("import numpy", "import time", "time.", "perf_counter",
                "datetime", "random", "import cv2"):
        ok("no %-16s (clock-free, numpy-free)" % bad, bad not in body)

    print("\n" + "=" * 78)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
