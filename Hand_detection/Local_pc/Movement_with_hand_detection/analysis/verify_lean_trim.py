# -*- coding: utf-8 -*-
"""Golden vectors for `Resources/lean_trim.py` — the swing/twist lean trim.

⭐ The load-bearing checks are the algebraic identities, not the table lookups:

  1. `q == swing ⊗ twist` EXACTLY, for arbitrary rotations — if the decomposition
     is wrong, everything built on it is wrong quietly.
  2. the swing's axis is PERPENDICULAR to the twist axis (that is what makes
     "swing == the contamination" true rather than approximate);
  3. gain 0 returns the input UNCHANGED — the A10 baseline;
  4. gain 1 leaves a pure yaw EXACTLY untouched and removes a lean ENTIRELY;
  5. ⛔ a genuine ROLL or PITCH with no yaw is NOT damped — the flaw the
     axis-scaling draft had, and the reason the ramp exists.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_lean_trim.py
"""
import io
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import lean_trim as LT                         # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []


def ok(name, cond, detail=""):
    print("  [%s] %-56s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


def quat(axis, deg):
    n = math.sqrt(sum(c * c for c in axis))
    a = [c / n for c in axis]
    h = math.radians(deg) / 2.0
    s = math.sin(h)
    return (math.cos(h), a[0] * s, a[1] * s, a[2] * s)


def qmul(p, q):
    return LT._qmul(p, q)


def angle_between(a, b):
    """Geodesic angle between two unit quaternions, in degrees.

    ⛔ NOT `2*acos(|dot|)`. That form is ILL-CONDITIONED near identity -- `acos`
    has infinite slope at 1, so for two quaternions equal to machine precision it
    returns ~1e-6 deg of pure noise, and a golden vector asserting exactness then
    fails on correct code. This bit twice on the first run of this suite.
    ⭐ `2*atan2(|a-b|, |a+b|)` is the standard stable form and resolves to ~1e-14
    deg, which is what lets the thresholds below actually mean "exact"."""
    if sum(x * y for x, y in zip(a, b)) < 0.0:      # double cover: same rotation
        b = tuple(-c for c in b)
    dif = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    sm = math.sqrt(sum((x + y) ** 2 for x, y in zip(a, b)))
    return math.degrees(2.0 * math.atan2(dif, sm))


YAW, PITCH, ROLL = (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)


def main():
    print("=" * 78)
    print("GOLDEN VECTORS — lean_trim (swing/twist)")
    print("=" * 78)

    # -- 1. the decomposition identity --------------------------------------
    print("\n1. ⭐ `q == swing ⊗ twist`, EXACTLY")
    cases = [quat((0.2, 0.9, -0.4), 63.0), quat((1.0, 0.0, 0.0), 40.0),
             quat((0.0, 1.0, 0.0), 85.0), quat((0.0, 0.0, 1.0), 30.0),
             qmul(quat(PITCH, 20.0), quat(YAW, 55.0)),
             qmul(quat(ROLL, -18.0), quat(YAW, -70.0))]
    for i, q in enumerate(cases):
        sw, tw = LT.swing_twist(q)
        ok("case %d recomposes" % i, angle_between(qmul(sw, tw), q) < 1e-9,
           "%.2e deg" % angle_between(qmul(sw, tw), q))

    print("\n2. ⭐ the SWING's axis is perpendicular to the twist axis")
    for i, q in enumerate(cases):
        sw, _ = LT.swing_twist(q)
        v = LT._to_rotvec(sw)
        ok("case %d swing has no y component" % i, abs(v[1]) < 1e-9,
           "y=%.2e" % v[1])

    # -- 3. the A10 baseline -------------------------------------------------
    print("\n3. ⛔ GAIN 0 IS THE SHIPPED BUILD, BIT-FOR-BIT")
    for i, q in enumerate(cases):
        ok("case %d untouched at gain 0" % i,
           LT.trim(q, 0.0, 0.0) is q)
    # ✅ SHIPPED 2026-08-28 at 0.66/0.66, settled live by the owner. The gain-0 path
    # above is still asserted bit-exact -- it is the A10 baseline, reachable by
    # passing 0 explicitly or by moving the sliders, and `parity_replay` uses it.
    ok("shipped defaults are 0.66/0.66",
       LT.GAIN_PITCH == 0.66 and LT.GAIN_ROLL == 0.66,
       "%.2f / %.2f" % (LT.GAIN_PITCH, LT.GAIN_ROLL))
    # ⚠ 0.66 sits just BELOW the gain that lands on the pipeline's own accuracy
    # floor. ROLL is the one axis that never touches world z; its mean-axis error is
    # 6.7 deg, and the lean at a 60-90 deg turn is 26.8 deg, so 1 - 6.7/26.8 = 0.750
    # is where correction stops removing measurable bias and starts fighting noise.
    ok("the shipped gain stays below the accuracy floor (0.750)",
       LT.GAIN_PITCH < 1.0 - 6.7 / 26.8 and LT.GAIN_ROLL < 1.0 - 6.7 / 26.8,
       "floor gain = %.3f" % (1.0 - 6.7 / 26.8))
    ok("None passes through", LT.trim(None, 1.0, 1.0) is None)

    # -- 4. a pure yaw must survive untouched at ANY gain --------------------
    print("\n4. ⭐ A PURE YAW IS NEVER ALTERED (the amount is already correct)")
    for deg in (15.0, 45.0, 90.0, -60.0):
        q = quat(YAW, deg)
        out = LT.trim(q, 1.0, 1.0)
        ok("pure yaw %+5.0f deg unchanged" % deg, angle_between(out, q) < 1e-9,
           "%.2e deg" % angle_between(out, q))

    # -- 5. THE POINT: a leaning yaw is straightened ------------------------
    print("\n5. ⭐⭐ A LEANING YAW IS STRAIGHTENED, AND THE YAW AMOUNT SURVIVES")
    for lean_axis, name, gp, gr in ((PITCH, "pitch-lean", 1.0, 0.0),
                                    (ROLL, "roll-lean ", 0.0, 1.0)):
        q = qmul(quat(lean_axis, 25.0), quat(YAW, 60.0))
        before = abs(LT._to_rotvec(LT.swing_twist(q)[0])[0 if lean_axis is PITCH else 2])
        out = LT.trim(q, gp, gr)
        after = abs(LT._to_rotvec(LT.swing_twist(out)[0])[0 if lean_axis is PITCH else 2])
        ok("%s removed at gain 1" % name, after < 1e-9,
           "%.1f deg -> %.2e deg" % (math.degrees(before), math.degrees(after)))
        ok("%s: yaw amount preserved" % name,
           abs(LT.twist_angle_deg(out) - LT.twist_angle_deg(q)) < 1e-9,
           "%.4f deg" % abs(LT.twist_angle_deg(out) - LT.twist_angle_deg(q)))
    # half gain removes half
    q = qmul(quat(PITCH, 24.0), quat(YAW, 60.0))
    got = math.degrees(abs(LT._to_rotvec(LT.swing_twist(LT.trim(q, 0.5, 0.0))[0])[0]))
    ok("gain 0.5 removes about half the lean", 10.0 < got < 14.0, "%.1f deg left" % got)

    # -- 6. ⛔ a genuine roll / pitch must NOT be damped ---------------------
    print("\n6. ⛔ A GENUINE ROLL OR PITCH, WITH NO YAW, IS LEFT ALONE")
    for axis, name in ((ROLL, "pure roll "), (PITCH, "pure pitch")):
        for deg in (20.0, 55.0, -40.0):
            q = quat(axis, deg)
            out = LT.trim(q, 1.0, 1.0)
            ok("%s %+5.0f deg untouched" % (name, deg),
               angle_between(out, q) < 1e-6, "%.2e deg" % angle_between(out, q))

    print("")
    print("7. ⛔⛔ THE RAMP IS YAW-DOMINANCE, NOT TWIST MAGNITUDE")
    # ⛔ The regression that cost a live session. The first version faded in on
    # |twist| ALONE, so a real pitch gesture -- which always carries some incidental
    # yaw -- cleared the 15 deg ramp and had its whole swing damped. Owner:
    # "pitch and roll are heavily damped as a consequence." The vectors passed
    # because they used MATHEMATICALLY PURE pitch, which a hand never produces.
    ok("pure yaw earns FULL authority", LT.authority(quat(YAW, 60.0)) >= 1.0 - 1e-9)
    ok("pure pitch earns NONE", LT.authority(quat(PITCH, 40.0)) == 0.0)
    ok("pure roll earns NONE", LT.authority(quat(ROLL, 40.0)) == 0.0)
    mixed = qmul(quat(PITCH, 40.0), quat(YAW, 15.0))
    ok("⛔ a PITCH gesture with incidental yaw earns NONE",
       LT.authority(mixed) == 0.0, "used to earn 1.00 and damp the pitch")
    ok("a leaning TURN still earns FULL",
       LT.authority(qmul(quat(PITCH, 25.0), quat(YAW, 60.0))) >= 1.0 - 1e-9)
    ok("authority is 0 at identity", LT.authority((1.0, 0.0, 0.0, 0.0)) == 0.0)
    ok("a tiny rotation earns NONE (its axis is noise)",
       LT.authority(quat((0.3, 0.9, 0.2), 2.0)) == 0.0)
    ok("dominance: pure yaw 1.0, pure pitch 0.0",
       abs(LT.yaw_dominance(quat(YAW, 50.0)) - 1.0) < 1e-9
       and LT.yaw_dominance(quat(PITCH, 50.0)) < 1e-9)

    print("")
    print("7b. ⛔ A REAL PITCH GESTURE IS NOT DAMPED, EVEN AT FULL GAIN")
    for pd, yd in ((40.0, 10.0), (55.0, 15.0), (30.0, 8.0)):
        g = qmul(quat(PITCH, pd), quat(YAW, yd))
        ok("pitch %.0f + yaw %.0f unchanged at gain 1" % (pd, yd),
           angle_between(LT.trim(g, 1.0, 1.0), g) < 1e-9,
           "%.2e deg" % angle_between(LT.trim(g, 1.0, 1.0), g))

    # -- 8. continuity: the whole reason this is not the rejected family -----
    print("\n8. ⭐⭐ CONTINUITY — nearby rotations give nearby corrections")
    worst = 0.0
    prev_q = prev_out = None
    for i in range(0, 900):
        deg = i * 0.1
        q = qmul(quat(PITCH, 25.0 * math.sin(math.radians(deg))), quat(YAW, deg * 0.1))
        out = LT.trim(q, 0.8, 0.6)
        if prev_out is not None:
            step_in = angle_between(q, prev_q)
            step_out = angle_between(out, prev_out)
            worst = max(worst, step_out - step_in)
        prev_q, prev_out = q, out
    ok("no step is AMPLIFIED by more than 0.05 deg", worst < 0.05,
       "worst amplification %.4f deg" % worst)

    # -- 8b. the double cover -------------------------------------------------
    # ⛔⛔ THE VECTOR THAT WAS MISSING, AND ITS ABSENCE WAS A LIVE DEFECT
    # (added 2026-08-29). Every vector above builds its quaternion with `quat()`,
    # which always returns `w >= 0` -- so the whole suite only ever exercised the
    # CANONICAL representation. `horn_rotation` returns whichever sign its
    # largest-eigenvalue eigenvector carries, and on a real pitch take 23% of
    # frames came back negated. `twist_angle_deg` then read a 15 deg turn as
    # -345 deg, `yaw_dominance` scored it ~0.99 instead of ~0.2, and `authority`
    # went to 1.0 on a gesture that must receive NO correction.
    # ⭐⭐ THE RULE IT COST, and it generalises past this file: A GOLDEN VECTOR
    # MUST FEED THE REPRESENTATIONS THE PRODUCT ACTUALLY PRODUCES, NOT ONLY THE
    # CANONICAL ONE. `q` and `-q` are the same rotation to the renderer and NOT to
    # any function that reads an angle out of them.
    # ⚠ `parity_replay` cannot catch this class at all: both tools import this one
    # module, so they were wrong identically and agreed perfectly.
    print("\n8b. ⛔⛔ q AND -q ARE THE SAME ROTATION — every reader must agree")
    dc_cases = [quat(YAW, 15.0), quat(YAW, 90.0), quat(YAW, -40.0),
                quat(PITCH, 30.0), quat(ROLL, 55.0),
                qmul(quat(PITCH, 20.0), quat(YAW, 55.0)),
                qmul(quat(ROLL, -18.0), quat(YAW, -70.0)),
                quat((0.2, 0.9, -0.4), 63.0)]
    for i, q in enumerate(dc_cases):
        nq = tuple(-c for c in q)
        ok("case %d  twist_angle_deg(q) == twist_angle_deg(-q)" % i,
           abs(LT.twist_angle_deg(q) - LT.twist_angle_deg(nq)) < 1e-9,
           "%.4f vs %.4f deg" % (LT.twist_angle_deg(q), LT.twist_angle_deg(nq)))
        ok("case %d  yaw_dominance agrees" % i,
           abs(LT.yaw_dominance(q) - LT.yaw_dominance(nq)) < 1e-9,
           "%.4f vs %.4f" % (LT.yaw_dominance(q), LT.yaw_dominance(nq)))
        ok("case %d  authority agrees" % i,
           abs(LT.authority(q) - LT.authority(nq)) < 1e-9,
           "%.4f vs %.4f" % (LT.authority(q), LT.authority(nq)))
        ok("case %d  trim() gives the SAME rotation" % i,
           angle_between(LT.trim(q), LT.trim(nq)) < 1e-9,
           "%.2e deg apart" % angle_between(LT.trim(q), LT.trim(nq)))
    # ⭐ And the specific number from the defect report, pinned so a regression
    # names itself rather than showing up as a vague ratio months later.
    ok("a NEGATED 15 deg yaw still reads 15 deg, not -345",
       abs(LT.twist_angle_deg(tuple(-c for c in quat(YAW, 15.0))) - 15.0) < 1e-9,
       "%.2f deg" % LT.twist_angle_deg(tuple(-c for c in quat(YAW, 15.0))))
    # ⚠ The shortest-arc convention, stated as a vector so it cannot drift: past a
    # half turn the SAME rotation is named the short way round.
    ok("a 190 deg twist is named -170 deg (shortest arc)",
       abs(LT.twist_angle_deg(quat(YAW, 190.0)) + 170.0) < 1e-9,
       "%.2f deg" % LT.twist_angle_deg(quat(YAW, 190.0)))

    # -- 9. the port contract ------------------------------------------------
    print("\n9. PORT CONTRACT (CONSTRAINTS §2)")
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "Resources", "lean_trim.py"),
                  encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("import numpy", "import time", "time.", "perf_counter",
                "datetime", "random", "import cv2"):
        ok("no %-16s" % bad, bad not in body)

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
