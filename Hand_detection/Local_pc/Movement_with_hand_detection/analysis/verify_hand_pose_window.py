# -*- coding: utf-8 -*-
"""GOLDEN VECTORS for `Resources/hand_pose_window.py` (`RB5`'s pose gate).

    .venv/Scripts/python.exe analysis/verify_hand_pose_window.py

`CONSTRAINTS` §3: golden vectors land with the code, not after it.

⭐⭐⭐ WHAT THIS SUITE IS ACTUALLY FOR, AND IT IS `RB0`'s LESSON: **A SIGN IS NOT
TESTED BY ANY AMOUNT OF TESTING THE MAGNITUDE.** Four defects in one day on
2026-08-29 -- a symmetric edge-on gate, a chirality-odd palm normal, an inverted
palm/back polarity, and a composite that came out a REFLECTION -- shared one shape:
the magnitude right, the sign wrong, in code that runs identically either way. Not
one was caught by a suite. So every section below pins a SIGN or a POLARITY against
a hand built from declared geometry.

⭐ §3 is the one that would not have existed without that lesson: the obvious roll
construction (the KNUCKLE ROW) is chirality-ODD, and this suite proves it by
FAILING on it -- the counter-example is kept, in the way `hand_frame` keeps
negate-z, so nobody re-proposes the cheaper axis.

⚠ METHOD: the suite builds its own hands and its own rotation matrices, so it can
FAIL on the module; it takes the readings themselves FROM the module. It re-derives
nothing it checks.

Stdlib only. Writes nothing.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_frame                      # noqa: E402
from Resources import hand_pose_window as HPW         # noqa: E402

FAILURES = []
CHECKS = [0]


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append("%s  %s" % (name, detail))
    print("  %s %-58s %s" % ("ok " if ok else "FAIL", name, detail))


def close(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


# ─────────────────────────────────────────────────────────────────────────────
# A synthetic hand, built in the USER's frame from declared anatomy.
#
# ⚠ MediaPipe's world landmarks put **+y DOWN**: on a fingers-up hand the wrist's y
# is GREATER than the MCPs'. Every coordinate below obeys that, and §1 is what pins
# it -- a suite that silently agreed with a flipped convention would be worthless.
#
# ⭐ `to_user_frame` for `facing_user` is `Ry180` (negate x and z), and `Ry180` is its
# OWN INVERSE. So to hand the module a world-landmark input that becomes `pts` in the
# user frame, apply `Ry180` to `pts`. That is why `_as_world` exists rather than the
# suite quietly testing the untransformed path.
PALM_W = 0.080          # index MCP to pinky MCP, metres
PALM_L = 0.090          # wrist to middle MCP
PALM_CUP = 0.008        # ⭐ how far the outer knuckles stand proud of the middle

# ⛔⛔ `PALM_CUP` IS NOT DECORATION, AND ITS ABSENCE WAS A REAL FIXTURE DEFECT.
# The first version of this suite built a PERFECTLY PLANAR palm, whose triple
# product is exactly zero -- so its chirality is undefined and the shipped code
# rightly REFUSES it (`CONFIDENT_DET`). Every vector here was therefore exercising a
# hand shape that cannot occur, and the refusal only surfaced once the module
# started reading the determinant. ⭐ A real gripping palm measures 8.7-56.8 mm of
# z-spread (`RB3`'s two-hand take); 8 mm of cup puts |det| at ~5.8e-05, two orders
# above the 3.0e-06 floor and in line with the corpus's 4.5e-05 palm-take median.
# §1 now asserts BOTH: that this hand is accepted, and that a flat one is not.


def _canonical_user_hand(right=True):
    """Palm facing the camera, fingers UP. 21 points; only the palm five matter.

    ⭐ For a RIGHT hand seen palm-on with fingers up, the INDEX side is on the
    viewer's LEFT... and for a LEFT hand it is on the viewer's RIGHT. That single
    swap is the whole of §3: it flips the knuckle row and leaves wrist->middle
    alone.
    ⭐ The sign it produces is not invented: this hand's determinant is NEGATIVE for
    `right=True`, which is what the un-mirrored declared-right take measured
    (`2026-08-29_202939_rb2_facing_right_palm`, `is_right_hand` 201/201)."""
    half = PALM_W / 2.0
    index_x = -half if right else +half
    pinky_x = +half if right else -half
    pts = [(0.0, 0.0, 0.0)] * 21
    pts[hand_frame.WRIST] = (0.0, 0.0, 0.0)
    pts[hand_frame.INDEX_MCP] = (index_x, -PALM_L, PALM_CUP)
    pts[hand_frame.MIDDLE_MCP] = (0.0, -PALM_L, 0.0)
    pts[hand_frame.RING_MCP] = (pinky_x * 0.45, -PALM_L, PALM_CUP * 0.4)
    pts[hand_frame.PINKY_MCP] = (pinky_x, -PALM_L * 0.95, PALM_CUP)
    return list(pts)


def _rot(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    if axis == "x":
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == "y":
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _apply(m, pts):
    return [(m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2],
             m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2],
             m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2]) for p in pts]


def _as_world(user_pts):
    """User-frame points -> the world landmarks that produce them. `Ry180`, self-inverse."""
    return [(-p[0], p[1], -p[2]) for p in user_pts]


def pose_of(user_pts):
    return HPW.pose_angles(_as_world(user_pts))


def main():
    print("GOLDEN VECTORS -- hand_pose_window (`RB5` pose gate)")
    print("mount=%s  CALIBRATED=%s\n" % (hand_frame.MOUNT, HPW.CALIBRATED))

    # ── §1 the canonical pose reads zero on all three axes ───────────────────
    print("§1 the reference pose -- vertical, palm to camera -- is 0 on every axis")
    base = _canonical_user_hand(right=True)
    p = pose_of(base)
    check("canonical pose is readable", p is not None)
    if p is None:
        return 1
    check("pitch == 0", close(p[0], 0.0, 0.5), "got %+.3f" % p[0])
    check("yaw   == 0", close(p[1], 0.0, 0.5), "got %+.3f" % p[1])
    check("roll  == 0", close(p[2], 0.0, 0.5), "got %+.3f" % p[2])
    check("+y is DOWN (wrist below the MCPs in y)",
          base[hand_frame.WRIST][1] > base[hand_frame.MIDDLE_MCP][1],
          "wrist y=%+.3f  middle y=%+.3f"
          % (base[hand_frame.WRIST][1], base[hand_frame.MIDDLE_MCP][1]))

    # ⭐ The fixture must be a hand the SHIPPED code accepts, and a flat one must be
    # refused -- the first version of this suite was built on a planar palm.
    det = hand_frame.signed_palm_volume(_as_world(base))
    check("the synthetic palm is CUPPED enough to have a chirality",
          abs(det) > HPW.CONFIDENT_DET, "|det|=%.2e vs floor %.1e"
          % (abs(det), HPW.CONFIDENT_DET))
    check("...and its sign matches the measured right hand (negative)", det < 0.0,
          "det=%+.2e" % det)
    flat_palm = list(base)
    for _i in (hand_frame.INDEX_MCP, hand_frame.MIDDLE_MCP,
               hand_frame.RING_MCP, hand_frame.PINKY_MCP):
        flat_palm[_i] = (base[_i][0], base[_i][1], 0.0)
    check("⛔ a PERFECTLY PLANAR palm is REFUSED, not guessed",
          HPW.pose_angles(_as_world(flat_palm)) is None)
    check("the canonical pose reads PALM TOWARD THE CAMERA",
          HPW.palm_faces_camera(_as_world(base)) is True)

    # ── §2 each axis responds to its OWN rotation, and reports the right sign ─
    # ⛔⛔ SIGNED, NOT `abs()`. A first version of this section compared MAGNITUDES
    # and passed while yaw came back NEGATED -- which is `METHOD`'s most expensive
    # rule ("a sign is not tested by any amount of testing the magnitude") being
    # broken by the suite written to enforce it. The polarities below are measured
    # from the construction and PINNED, so a change that flips one fails loudly
    # instead of propagating into a build that INTEGRATES what it is given.
    #
    # ⭐⭐ AND THE POLARITY CHANGED ONCE, FOR A GOOD REASON. Before the palm normal
    # was chirality-corrected it was pitch `+1` / yaw `-1`; correcting it negates the
    # normal on this hand and so flips both. ⭐ The new pitch polarity is the one the
    # OWNER specified -- `+` = fingertips toward the camera -- which §2b asserts
    # semantically rather than as a matrix sign. That the fix landed on the owner's
    # convention is corroboration, not a coincidence to lean on.
    POLARITY = {"pitch": -1.0, "yaw": +1.0, "roll": +1.0}
    print("\n§2 one rotation at a time -- magnitude AND SIGN (polarity %s)"
          % ", ".join("%s%+.0f" % (k, v) for k, v in sorted(POLARITY.items())))
    for deg in (20.0, -20.0, 40.0):
        y = pose_of(_apply(_rot("y", deg), base))
        check("yaw %+.0f deg about the vertical -> yaw %+.0f" % (deg, POLARITY["yaw"] * deg),
              y is not None and close(y[1], POLARITY["yaw"] * deg, 2.0),
              "yaw=%+.2f (pitch %+.2f, roll %+.2f)" % (y[1], y[0], y[2]) if y else "None")
        x = pose_of(_apply(_rot("x", deg), base))
        check("pitch %+.0f deg -> pitch %+.0f" % (deg, POLARITY["pitch"] * deg),
              x is not None and close(x[0], POLARITY["pitch"] * deg, 2.0),
              "pitch=%+.2f (yaw %+.2f, roll %+.2f)" % (x[0], x[1], x[2]) if x else "None")
        z = pose_of(_apply(_rot("z", deg), base))
        check("roll %+.0f deg -> roll %+.0f" % (deg, POLARITY["roll"] * deg),
              z is not None and close(z[2], POLARITY["roll"] * deg, 1.0),
              "roll=%+.2f (pitch %+.2f, yaw %+.2f)" % (z[2], z[0], z[1]) if z else "None")

    # ⭐⭐ §2b -- THE OWNER'S OWN WORDS, AS AN ASSERTION. "pitch: + = fingertips
    # toward the camera, palm tilting UP" (2026-08-30). The corrected palm normal
    # points OUT of the palm, so `+z` in the user frame is toward the camera, and the
    # finger direction's z is what "toward the camera" means. A sign convention
    # written only in a docstring is a sign convention nobody can fail.
    for _d in (25.0, -25.0):
        _pts = _apply(_rot("x", _d), base)
        _toward = _pts[hand_frame.MIDDLE_MCP][2] > 0.0
        _pitch = pose_of(_pts)[0]
        check("fingertips %s the camera -> pitch %s"
              % ("TOWARD" if _toward else "AWAY from", "positive" if _toward else "negative"),
              (_pitch > 0.0) == _toward,
              "middle-MCP z=%+.4f, pitch=%+.2f" % (_pts[hand_frame.MIDDLE_MCP][2], _pitch))

    # ⭐ And the polarity must be a function of the ROTATION, not of its SIZE: the
    # same axis at two magnitudes must agree in sign, or the reading folds somewhere.
    for _ax, _i, _nm in (("y", 1, "yaw"), ("x", 0, "pitch"), ("z", 2, "roll")):
        a = pose_of(_apply(_rot(_ax, 10.0), base))
        b = pose_of(_apply(_rot(_ax, 35.0), base))
        check("%s keeps ONE sign from 10 to 35 deg" % _nm,
              a is not None and b is not None and (a[_i] * b[_i]) > 0.0,
              "%+.2f then %+.2f" % (a[_i], b[_i]) if (a and b) else "None")

    # ⭐ A rotation about the vertical must not be reported as roll, and vice versa.
    y40 = pose_of(_apply(_rot("y", 40.0), base))
    check("a pure YAW leaks < 3 deg into roll", y40 is not None and abs(y40[2]) < 3.0,
          "roll=%+.2f" % y40[2] if y40 else "None")
    z40 = pose_of(_apply(_rot("z", 40.0), base))
    check("a pure ROLL leaks < 3 deg into yaw", z40 is not None and abs(z40[1]) < 3.0,
          "yaw=%+.2f" % z40[1] if z40 else "None")

    # ── §3 ⭐⭐⭐ THE ROLL AXIS IS CHIRALITY-EVEN, and the cheap one is NOT ─────
    print("\n§3 EVERY axis is CHIRALITY-EVEN -- the two hands must agree")
    # ⛔⛔ THE DEFECT THIS SECTION EXISTS FOR. The first version tested ROLL only --
    # the one axis that never had the problem -- while the palm NORMAL, and with it
    # PITCH and YAW, was chirality-ODD: the same +20 deg physical yaw read -20 on
    # the right hand and +20 on the left. With the owner's ASYMMETRIC windows
    # (pitch +15..+50, yaw 0..+60) that gates the opposite motion on the left hand.
    # A chirality-odd palm normal was one of the four sign defects of 2026-08-29.
    for _axis, _idx, _nm in (("y", 1, "yaw"), ("x", 0, "pitch")):
        for _d in (20.0, -20.0, 40.0):
            pr = pose_of(_apply(_rot(_axis, _d), _canonical_user_hand(right=True)))
            pl = pose_of(_apply(_rot(_axis, _d), _canonical_user_hand(right=False)))
            check("%s at %+.0f deg agrees between the hands" % (_nm, _d),
                  pr is not None and pl is not None
                  and abs(pr[_idx] - pl[_idx]) < 1.0,
                  "right=%+.2f left=%+.2f" % (pr[_idx], pl[_idx])
                  if (pr and pl) else "None")
    nr = HPW.palm_normal(_as_world(_canonical_user_hand(right=True)))
    nl = HPW.palm_normal(_as_world(_canonical_user_hand(right=False)))
    check("the corrected palm NORMAL itself is chirality-even",
          nr is not None and nl is not None
          and max(abs(nr[i] - nl[i]) for i in range(3)) < 1e-6,
          "right=%s left=%s" % (tuple(round(x, 3) for x in nr),
                                tuple(round(x, 3) for x in nl)))

    for deg in (0.0, 30.0, -30.0):
        r_right = pose_of(_apply(_rot("z", deg), _canonical_user_hand(right=True)))
        r_left = pose_of(_apply(_rot("z", deg), _canonical_user_hand(right=False)))
        check("roll at %+.0f deg agrees between the hands" % deg,
              r_right is not None and r_left is not None
              and close(r_right[2], r_left[2], 1.0),
              "right=%+.2f left=%+.2f" % (r_right[2], r_left[2])
              if (r_right and r_left) else "None")

    # ⛔⛔ THE COUNTER-EXAMPLE, KEPT ON PURPOSE. The obvious construction -- the
    # KNUCKLE ROW, index MCP -> pinky MCP -- points the opposite anatomical way on
    # the two hands, so it reads 180 deg apart. This section must FAIL on it, or §3
    # above is not testing anything. A chirality-odd palm normal was one of the four
    # sign defects of 2026-08-29; this is that class, refused in advance.
    def knuckle_roll(user_pts):
        i, k = user_pts[hand_frame.INDEX_MCP], user_pts[hand_frame.PINKY_MCP]
        return math.degrees(math.atan2(k[0] - i[0], -(k[1] - i[1])))

    kr = knuckle_roll(_canonical_user_hand(right=True))
    kl = knuckle_roll(_canonical_user_hand(right=False))
    spread = abs(((kr - kl) + 180.0) % 360.0 - 180.0)
    check("the REJECTED knuckle-row axis is chirality-ODD (~180 deg apart)",
          spread > 170.0, "right=%+.1f left=%+.1f  spread=%.1f deg" % (kr, kl, spread))

    # ── §3bis ⛔⛔ PAST EDGE-ON IS A HARD ZERO ON EVERY AXIS ─────────────────
    print("\n§3bis past edge-on -- the back of the hand drives NOTHING")
    # ⛔⛔ THE SECOND DEFECT THE REVIEW FOUND. `atan2(nx, |nz|)` FOLDS: with the back
    # of the hand to the camera, yaw +180 deg read -0.0 deg with weights (1, 1, 1) --
    # full gain in the most degenerate region there is, integrated permanently. It is
    # the same defect `SPEC_DELTA_ORBIT` §8bis records against `edge_on_measure`
    # ("~1.0 palm-on, ~0.15 at edge-on, and ~1.0 again with the BACK of the hand
    # toward the camera"), re-introduced by dropping `sign(nz)`.
    for _d in (0.0, 40.0, 70.0):
        check("palm side at yaw %+.0f deg still faces the camera" % _d,
              HPW.palm_faces_camera(_as_world(_apply(_rot("y", _d), base))) is True)
    for _d in (100.0, 120.0, 140.0, 170.0, 180.0):
        pts = _apply(_rot("y", _d), base)
        facing = HPW.palm_faces_camera(_as_world(pts))
        w = HPW.weights(_as_world(pts))
        check("yaw %+.0f deg is PAST edge-on and hard-gated" % _d,
              facing is False and w == (0.0, 0.0, 0.0),
              "facing=%s weights=%s" % (facing, tuple(round(x, 2) for x in w)))
    # ⭐ And the reading still EXISTS out there -- it is the pose that is refused,
    # not the sensor. That distinction is what lets `hand_control` treat it as a
    # GATE (reference advances, clutch preserved) rather than a REFUSAL.
    check("...but the angles are still reported, for diagnosis",
          HPW.pose_angles(_as_world(_apply(_rot("y", 140.0), base))) is not None)

    # ── §4 a degenerate hand is a CLOSED gate, never an open one ─────────────
    print("\n§4 degeneracy closes the gate")
    check("pose_angles(None) is None", HPW.pose_angles(None) is None)
    check("weights(None) is (0,0,0)", HPW.weights(None) == (0.0, 0.0, 0.0))
    flat = [(0.0, 0.0, 0.0)] * 21
    check("a collapsed hand reads None", HPW.pose_angles(flat) is None)
    check("a collapsed hand gets zero weight", HPW.weights(flat) == (0.0, 0.0, 0.0))
    check("a short landmark list reads None", HPW.pose_angles([(0.0, 0.0, 0.0)] * 5) is None)

    # ── §5 ⭐⭐ THE FADE IS OUTSIDE THE WINDOW, NOT INSIDE IT ─────────────────
    print("\n§5 the fade sits OUTSIDE the stated window (spec §8sexies-c)")
    f = HPW._smoothstep_out
    lo, hi, fade = 10.0, 50.0, 15.0
    check("weight at the LOWER edge is 1.0, not 0.5",
          close(f(lo, lo, hi, fade), 1.0, 1e-9), "got %.6f" % f(lo, lo, hi, fade))
    check("weight at the UPPER edge is 1.0, not 0.5",
          close(f(hi, lo, hi, fade), 1.0, 1e-9), "got %.6f" % f(hi, lo, hi, fade))
    check("weight in the middle is 1.0", close(f(30.0, lo, hi, fade), 1.0, 1e-9))
    check("weight one full fade beyond is 0.0",
          close(f(hi + fade, lo, hi, fade), 0.0, 1e-9))
    check("weight beyond that stays 0.0", close(f(hi + 3 * fade, lo, hi, fade), 0.0, 1e-9))
    check("half a fade out is strictly between", 0.0 < f(hi + fade / 2, lo, hi, fade) < 1.0,
          "got %.4f" % f(hi + fade / 2, lo, hi, fade))
    mono = all(f(hi + fade * t / 20.0, lo, hi, fade) >= f(hi + fade * (t + 1) / 20.0, lo, hi, fade)
               for t in range(20))
    check("the fade is MONOTONE across its whole width", mono)
    # ⭐ zero SLOPE at both ends: `F1`'s trim died on being non-monotone in the
    # declared angle, and a kink mid-gesture is felt.
    eps = fade / 1000.0
    d_in = (f(hi, lo, hi, fade) - f(hi + eps, lo, hi, fade)) / eps
    d_out = (f(hi + fade - eps, lo, hi, fade) - f(hi + fade, lo, hi, fade)) / eps
    check("slope is ~0 at the window edge", abs(d_in) < 1e-3, "d=%.2e" % d_in)
    check("slope is ~0 where the fade ends", abs(d_out) < 1e-3, "d=%.2e" % d_out)
    check("a zero fade is a HARD edge", f(hi + 0.001, lo, hi, 0.0) == 0.0)

    # ── §6 the gate is PER-AXIS (owner, 2026-08-30) ──────────────────────────
    print("\n§6 the gate is per-axis: one axis out must not silence the others")
    # Roll far outside its window, yaw and pitch at the canonical zero.
    far = _apply(_rot("z", 80.0), base)
    w = HPW.weights(_as_world(far))
    check("roll outside its window gets weight 0", close(w[2], 0.0, 1e-6), "w_roll=%.3f" % w[2])
    check("...while pitch keeps its weight", w[0] > 0.99, "w_pitch=%.3f" % w[0])
    check("...and yaw keeps its weight", w[1] > 0.99, "w_yaw=%.3f" % w[1])

    # ── §7 the owner's specification is carried as DATA, not as prose ────────
    print("\n§7 the specification, and the guard on it")
    check("owner window pitch is +15..+50", HPW.OWNER_WINDOW_REAL_DEG["pitch"] == (15.0, 50.0))
    check("owner window yaw is 0..+60", HPW.OWNER_WINDOW_REAL_DEG["yaw"] == (0.0, 60.0))
    check("owner window roll is -45..+45", HPW.OWNER_WINDOW_REAL_DEG["roll"] == (-45.0, 45.0))
    check("the cube span is 180 deg", HPW.OWNER_CUBE_SPAN_DEG == 180.0)
    # ⛔ The owner's REAL-degree numbers must never be pasted into the gate's own
    # constants -- the readings are compressed against the real angle by a measured
    # factor of ~0.5-0.9. This asserts the confusion has not happened.
    check("⛔ the gate does NOT gate on the owner's real-degree numbers",
          (HPW.WINDOW_PITCH_DEG != HPW.OWNER_WINDOW_REAL_DEG["pitch"]
           or HPW.CALIBRATED),
          "uncalibrated gate must not equal the real-degree window")
    if not HPW.CALIBRATED:
        print("  ⚠ CALIBRATED is False -- the window constants are PLACEHOLDERS.")
        print("    Run analysis/rb5_window_calibration.py on an UN-MIRRORED")
        print("    declared-angle take and paste its constants block.")

    print("\n%d checks, %d failure(s)" % (CHECKS[0], len(FAILURES)))
    for f_ in FAILURES:
        print("  FAIL  %s" % f_)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
