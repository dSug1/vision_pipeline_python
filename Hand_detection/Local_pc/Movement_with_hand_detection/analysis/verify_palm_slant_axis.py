# -*- coding: utf-8 -*-
"""Golden vectors for `Resources/palm_slant_axis.py` (T6's axis correction).

⛔ THE FIRST CHECK IS THE ACCEPTANCE GATE, same as `verify_tip_trim.py`:
`gain = 0` must return the input quaternion **BIT-EXACT**, not approximately. That
is what makes an A/B arm honest and what lets the module ship defaulted OFF.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_palm_slant_axis.py
Exit code 0 = all pass.
"""
import io
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_rotation as PR                     # noqa: E402
from Resources import palm_slant_axis as SA                   # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []
IDENT = (1.0, 0.0, 0.0, 0.0)


def check(name, got, want, tol=1e-9):
    if want is None or isinstance(want, bool) or isinstance(want, int):
        good = got == want
    else:
        good = got is not None and abs(got - want) <= tol
    print("  [%s] %-56s got %r" % ("PASS" if good else "FAIL", name, got))
    if not good:
        FAILURES.append("%s: got %r, want %r" % (name, got, want))


def ok(name, cond, detail=""):
    print("  [%s] %-56s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


def quat(axis_deg, ang_deg, nz=0.0):
    a = math.radians(axis_deg)
    x, y = math.cos(a), math.sin(a)
    n = math.sqrt(x * x + y * y + nz * nz)
    s = math.sin(math.radians(ang_deg) * 0.5)
    return PR._qnorm((math.cos(math.radians(ang_deg) * 0.5),
                      x / n * s, y / n * s, nz / n * s))


def axis_deg(q):
    return math.degrees(math.atan2(q[2], q[1])) % 180.0


def hand(width=80.0, length=70.0):
    """A 21-landmark face-on right hand, enough for the palm quad and the roll."""
    pts = [(0.0, 0.0)] * 21
    pts[0] = (0.0, 0.0)
    pts[5] = (-width / 2, -length)
    pts[9] = (0.0, -length - 6.0)
    pts[13] = (width / 4, -length)
    pts[17] = (width / 2, -length + 10.0)
    return pts


def main():
    print("=" * 78)
    print("Golden vectors -- palm_slant_axis  (T6: keep Horn's angle, fix its axis)")
    print("=" * 78)

    print("\n--- 1. THE ACCEPTANCE GATE: gain 0 is BIT-EXACT Horn ---")
    q = quat(37.0, 55.0, nz=0.3)
    check("steer_axis(amount=0) returns the SAME object", SA.steer_axis(q, 90.0, 0.0) is q, True)
    check("steer_axis(negative amount) returns the SAME object",
          SA.steer_axis(q, 90.0, -0.5) is q, True)
    check("steer_axis(target=None) returns the SAME object",
          SA.steer_axis(q, None, 1.0) is q, True)
    check("steer_axis(q=None) returns None", SA.steer_axis(None, 90.0, 1.0), None)
    e = SA.SlantAxisHorn(gain=0.0)
    check("SlantAxisHorn ships at gain 0 (production parity)", e.gain, 0.0, 1e-12)
    check("DEFAULT_GAIN is 0", SA.DEFAULT_GAIN, 0.0, 1e-12)

    print("\n--- 2. steering: the axis moves, the ANGLE does not ---")
    for tgt in (90.0, 0.0, 135.0, 12.0):
        s = SA.steer_axis(quat(37.0, 55.0), tgt, 1.0)
        check("full steer to %5.1f -> axis lands there" % tgt, axis_deg(s), tgt, 1e-6)
    for ang in (5.0, 55.0, 120.0, 179.0):
        src = quat(37.0, ang)
        s = SA.steer_axis(src, 90.0, 1.0)
        check("angle preserved exactly at %5.1f deg" % ang,
              PR.quat_angle_deg(IDENT, s), PR.quat_angle_deg(IDENT, src), 1e-6)
    s = SA.steer_axis(quat(37.0, 55.0), 90.0, 0.5)
    check("half steer lands halfway (37 -> 90)", axis_deg(s), 63.5, 1e-6)

    print("\n--- 3. ⛔ THE SIGN TRAP (a flipped axis turns the cube BACKWARDS) ---")
    # Axis at 10 deg, target 170. Naively that is +160 deg of steering, which would
    # very nearly REVERSE the axis -- same line, opposite direction -- and with the
    # angle preserved the cube would turn the wrong way. The near representative is
    # -20 deg, landing at -10, which is the SAME LINE as 170 with the sign intact.
    src = quat(10.0, 40.0)
    s = SA.steer_axis(src, 170.0, 1.0)
    ok("steers the SHORT way (10 -> -10, not 10 -> 170)",
       abs(math.degrees(math.atan2(s[2], s[1])) - (-10.0)) < 1e-6,
       "landed at %.2f deg" % math.degrees(math.atan2(s[2], s[1])))
    ok("axis direction is PRESERVED, not reversed",
       (s[1] * src[1] + s[2] * src[2]) > 0.0,
       "dot %.4f" % (s[1] * src[1] + s[2] * src[2]))
    ok("no steer ever exceeds 90 deg of correction",
       all(abs(((math.degrees(math.atan2(SA.steer_axis(quat(a * 1.0, 40.0), t * 1.0, 1.0)[2],
                                         SA.steer_axis(quat(a * 1.0, 40.0), t * 1.0, 1.0)[1]))
                 - a + 180.0) % 360.0) - 180.0) <= 90.0 + 1e-6
           for a in range(0, 180, 17) for t in range(0, 180, 23)))

    print("\n--- 4. z is left alone, and a camera-facing axis is left alone ---")
    src = quat(37.0, 55.0, nz=0.6)
    s = SA.steer_axis(src, 90.0, 1.0)
    aa_src, aa_s = SA._axis_angle(src), SA._axis_angle(s)
    check("z component of the unit axis unchanged", aa_s[0][2], aa_src[0][2], 1e-9)
    straight = PR._qnorm((math.cos(math.radians(20.0)), 0.0, 0.0, math.sin(math.radians(20.0))))
    check("axis pointing at the camera is returned UNCHANGED",
          SA.steer_axis(straight, 90.0, 1.0) is straight, True)

    print("\n--- 5. knuckle_roll_deg: the two-frame reconciler ---")
    check("face-on hand has a near-flat knuckle row",
          abs(SA.knuckle_roll_deg(hand())) < 12.0, True)
    check("short landmark list -> None", SA.knuckle_roll_deg([(0.0, 0.0)] * 5), None)
    h = hand()
    a = math.radians(30.0)
    rolled = [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))
              for x, y in h]
    check("rolling the hand 30 deg moves the roll by 30",
          SA.knuckle_roll_deg(rolled) - SA.knuckle_roll_deg(h), 30.0, 1e-6)

    print("\n--- 6. the estimator honours its guards ---")
    check("EDGE_ON_FLOOR reuses one definition of edge-on", SA.EDGE_ON_FLOOR, 0.15, 1e-12)
    e = SA.SlantAxisHorn(gain=1.0)
    check("freeze refuses a hand it cannot read", e.freeze([(0.0, 0.0)] * 5, None), None)
    ok("delta with no state returns None or the horn value", e.delta(None, hand(), None) is None)
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "Resources", "palm_slant_axis.py"), encoding="utf-8").read()
    ok("gain is applied as gain * authority, never bare",
       "gain * auth" in src)
    ok("the back branch returns Horn untouched", "self.frames_back_branch += 1" in src)

    print("\n--- 7. the port contract (CONSTRAINTS section 2) ---")
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("import numpy", "import time", "time.", "perf_counter", "datetime", "random"):
        ok("no %-16s (clock-free, numpy-free)" % bad, bad not in body)

    print("\n--- 8. golden digest -- a port must reproduce these EXACTLY ---")
    for a, t, amt in ((37.0, 90.0, 1.0), (37.0, 90.0, 0.35), (150.0, 5.0, 1.0), (80.0, 95.0, 0.5)):
        s = SA.steer_axis(quat(a, 55.0, nz=0.25), t, amt)
        print("  axis %5.1f -> %5.1f @ %.2f :  q = (%.9f, %.9f, %.9f, %.9f)"
              % (a, t, amt, s[0], s[1], s[2], s[3]))

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
