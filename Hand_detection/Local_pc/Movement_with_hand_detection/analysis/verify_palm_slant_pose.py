# -*- coding: utf-8 -*-
"""Golden vectors for `Resources/palm_slant_pose.py` — the owner's halves 1+2.

⛔ FIRST CHECK IS THE ACCEPTANCE GATE: `blend = 0` must return Horn's quaternion as
the SAME OBJECT, so an A/B panel pinned at 0 is production itself.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_palm_slant_pose.py
"""
import io
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_rotation as PR                     # noqa: E402
from Resources import palm_slant_pose as SP                   # noqa: E402
from Resources import palm_slant_table as PT                  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []


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


def hand(sx=1.0, sy=1.0):
    """A 21-landmark face-on hand, optionally foreshortened."""
    p = [(0.0, 0.0)] * 21
    p[0] = (0.0, 0.0)
    p[5] = (-40.0 * sx, -70.0 * sy)
    p[9] = (-4.0 * sx, -76.0 * sy)
    p[13] = (24.0 * sx, -72.0 * sy)
    p[17] = (46.0 * sx, -62.0 * sy)
    for i, k in enumerate((6, 7, 8, 10, 11, 12, 14, 15, 16, 18, 19, 20)):
        p[k] = (p[5][0] + 6.0 * i * sx, p[5][1] - 8.0 * i * sy)
    return p


def world():
    return [(x / 1000.0, y / 1000.0, 0.0) for x, y in hand()]


def main():
    print("=" * 78)
    print("Golden vectors -- palm_slant_pose  (owner's halves 1+2)")
    print("=" * 78)

    print("\n--- 1. THE ACCEPTANCE GATE ---")
    e = SP.SlantPoseHorn("palm", blend=0.0)
    st = e.freeze(hand(), world())
    ok("freeze succeeds on a readable hand", st is not None)
    q = e.delta(st, hand(0.6), world())
    qh = PR.Horn(PR.PALM_LANDMARKS, "ref")
    sth = qh.freeze(hand(), world())
    ok("blend 0 returns HORN's own answer, unchanged",
       q == qh.delta(sth, hand(0.6), world()))
    check("DEFAULT_BLEND is 0", SP.DEFAULT_BLEND, 0.0, 1e-12)
    check("module BLEND starts at 0 (production parity)", SP.BLEND, 0.0, 1e-12)
    check("SMOOTH_TAU_MS starts at 0 (off)", SP.SMOOTH_TAU_MS, 0.0, 1e-12)

    print("\n--- 2. the fitted table is data, and it is well formed ---")
    for feat in ("palm", "fingers"):
        t = PT.TABLES[feat]
        for axis in ("yaw", "pitch"):
            for side in ("front", "back"):
                ks = t[axis][side]
                ok("%s/%s/%s has knots" % (feat, axis, side), len(ks) >= 3, "%d" % len(ks))
                ok("%s/%s/%s sigma strictly falls" % (feat, axis, side),
                   all(ks[i][0] > ks[i + 1][0] for i in range(len(ks) - 1)))
                # ⛔ The BACK branch must FALL in angle along falling sigma. An
                # earlier emit forced it to rise and flattened the whole back half
                # to 180 -- a table that is not a fit at all.
                rising = side == "front"
                # ⚠ NON-STRICT on purpose. The emitted curve has FLAT PLATEAUS --
                # three depths hold the same declared angle, and their sigmas differ a
                # lot (declared 30 deg reads 0.942 / 0.855 / 0.756). A plateau is the
                # honest record of that disagreement; a strictly-rising fit would
                # invent an ordering the data does not contain.
                # ⛔ What the plateaus MEAN is a live limitation, not a formatting
                # detail: pooling the three depths smears a real DEPTH DEPENDENCE
                # (§4.3 already measured that one table does not serve all depths)
                # into regions where sigma moves and the angle does not.
                mono = all((ks[i][1] <= ks[i + 1][1]) if rising
                           else (ks[i][1] >= ks[i + 1][1]) for i in range(len(ks) - 1))
                ok("%s/%s/%s angle is monotone (%s)"
                   % (feat, axis, side, "rising" if rising else "falling"), mono,
                   "%.0f..%.0f deg" % (ks[0][1], ks[-1][1]))

    print("\n--- 3. lookup: monotone in, single value out (BIJECTIVE) ---")
    t = PT.TABLES["palm"]
    vals = [SP.lookup(t, "yaw", "front", x / 200.0) for x in range(1, 201)]
    ok("yaw/front lookup is monotone",
       all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1)))
    check("lookup clamps above the table", SP.lookup(t, "yaw", "front", 2.0),
          t["yaw"]["front"][0][1], 1e-9)
    check("lookup clamps below the table", SP.lookup(t, "yaw", "front", -1.0),
          t["yaw"]["front"][-1][1], 1e-9)
    check("lookup(nan) is None", SP.lookup(t, "yaw", "front", float("nan")), None)
    check("lookup of an unknown axis is None", SP.lookup(t, "roll", "front", 0.5), None)

    print("\n--- 4. the yaw/pitch blend picks the right curve ---")
    sig = 0.5
    y = SP.lookup(t, "yaw", "front", sig)
    p = SP.lookup(t, "pitch", "front", sig)
    check("tilt 90 deg gives the YAW curve exactly", SP.angle_from(t, "front", sig, 90.0), y, 1e-9)
    check("tilt 0 deg gives the PITCH curve exactly", SP.angle_from(t, "front", sig, 0.0), p, 1e-9)
    check("tilt 180 deg also gives PITCH", SP.angle_from(t, "front", sig, 180.0), p, 1e-9)
    mid = SP.angle_from(t, "front", sig, 45.0)
    ok("tilt 45 deg lands between the two curves", min(y, p) <= mid <= max(y, p),
       "%.1f between %.1f and %.1f" % (mid, min(y, p), max(y, p)))

    print("\n--- 5. roll comes from the knuckle row, depth-free ---")
    h = hand()
    a = math.radians(25.0)
    rolled = [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))
              for x, y in h]
    check("a 25 deg roll reads as 25 deg",
          SP.knuckle_roll_deg(rolled) - SP.knuckle_roll_deg(h), 25.0, 1e-6)
    check("short landmark list -> None", SP.knuckle_roll_deg([(0.0, 0.0)] * 5), None)

    print("\n--- 6. guards ---")
    check("freeze refuses an unreadable hand", SP.SlantPoseHorn().freeze([(0, 0)] * 5, None), None)
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "Resources", "palm_slant_pose.py"), encoding="utf-8").read()
    ok("the sign flip has hysteresis, not a bare threshold", "sign_votes" in src)
    ok("the face-on reference needs a real margin", "FACE_ON_MARGIN = 0.08" in src)
    ok("smoothing is on u, not on the quaternion", 'pose["u_s"]' in src)
    e2 = SP.SlantPoseHorn("palm", blend=1.0)
    st2 = e2.freeze(hand(), world())
    ok("a full-blend delta returns a unit quaternion",
       abs(sum(c * c for c in e2.delta(st2, hand(0.5), world())) - 1.0) < 1e-9)

    print("\n--- 7. the port contract (CONSTRAINTS section 2) ---")
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("import numpy", "import time", "time.", "perf_counter", "datetime", "random"):
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
