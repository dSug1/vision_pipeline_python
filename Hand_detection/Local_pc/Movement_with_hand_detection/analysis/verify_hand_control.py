# -*- coding: utf-8 -*-
"""GOLDEN VECTORS for `Resources/hand_control.py` (`RB5`'s control law).

    .venv/Scripts/python.exe analysis/verify_hand_control.py

`CONSTRAINTS` §3: golden vectors land with the code, not after it.

⭐⭐ WHAT THIS SUITE IS FOR. A rate-control build keeps every mistake it makes: in
absolute mode a bad frame is a bad frame and the next good frame recovers, and here
each one is added to the object permanently. So the properties worth pinning are not
"is the number about right" but "can this ever inject a rotation nobody performed" --
the clutch/catapult distinction (§4, §5), the refusal path (§6), and the clamp (§9).

⚠ METHOD: the hands and the rotation matrices are the suite's own, so it can FAIL on
the module; the control law, the pose reading and the orientation come FROM their
modules. The hand builder is IMPORTED from `verify_hand_pose_window` rather than
copied (`N6`).

Stdlib only. Writes nothing.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_control as HC              # noqa: E402
from Resources import hand_orientation as HO          # noqa: E402
from Resources import hand_pose_window as HPW         # noqa: E402

# ⭐ Imported, never copied: one synthetic hand, one rotation helper, two suites.
from verify_hand_pose_window import (                 # noqa: E402
    _canonical_user_hand, _rot, _apply, _as_world)

FAILURES = []
CHECKS = [0]


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append("%s  %s" % (name, detail))
    print("  %s %-58s %s" % ("ok " if ok else "FAIL", name, detail))


def matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


BASE = _canonical_user_hand(right=True)


def hand_at(m):
    """World landmarks for the canonical hand rotated by matrix `m`."""
    return _as_world(_apply(m, BASE))


IDENT3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def run(matrices, gain=(1.0, 1.0, 1.0), ctrl=None):
    """Feed a pose sequence through a fresh controller. Returns it."""
    c = ctrl or HC.ObjectRotationControl()
    for m in matrices:
        c.update(hand_at(m), gain=gain)
    return c


def obj_angle(c):
    return HO.angle_deg(c.orientation)


def main():
    print("GOLDEN VECTORS -- hand_control (`RB5` control law)")
    print("GAIN=%s  CALIBRATED=%s  MAX_STEP_DEG=%.1f\n"
          % (HC.GAIN, HC.CALIBRATED, HC.MAX_STEP_DEG))

    # ── §1 the log/exp pair is a round trip ──────────────────────────────────
    print("§1 rotvec_deg and from_rotvec_deg are inverses")
    for v in ((0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, -12.0, 0.0),
              (3.0, -4.0, 12.0), (60.0, 0.0, 0.0)):
        back = HO.rotvec_deg(HC.from_rotvec_deg(v))
        err = max(abs(back[i] - v[i]) for i in range(3))
        check("round trip %s" % (v,), err < 1e-6, "max err %.2e" % err)
    check("a zero rotvec is exactly IDENTITY",
          HC.from_rotvec_deg((0.0, 0.0, 0.0)) == HC.IDENTITY)

    # ── §2 the first usable frame seeds and drives nothing ───────────────────
    print("\n§2 the first frame seeds a reference and drives nothing")
    c = HC.ObjectRotationControl()
    c.update(hand_at(IDENT3))
    check("one frame leaves the object at identity", obj_angle(c) < 1e-9,
          "%.3e deg" % obj_angle(c))
    check("...and counts as gated, not driven",
          c.frames_driven == 0 and c.frames_gated == 1,
          "driven=%d gated=%d" % (c.frames_driven, c.frames_gated))

    # ── §3 a still hand injects EXACTLY nothing ──────────────────────────────
    print("\n§3 a perfectly still hand injects exactly nothing")
    c = run([IDENT3] * 200)
    check("200 identical frames -> 0 deg", obj_angle(c) < 1e-9,
          "%.3e deg" % obj_angle(c))
    check("the quaternion is still unit and canonical",
          abs(math.sqrt(sum(x * x for x in c.orientation)) - 1.0) < 1e-12
          and c.orientation[0] >= 0.0)
    print("  ⚠ this is the MATHS being drift-free. Real drift is landmark noise,")
    print("    measured 43/35/48 deg/min on the old stack -- `RB5` step 5, not here.")

    # ── §4 ⭐⭐ CLOSURE: out and back returns the object ─────────────────────
    print("\n§4 closure -- the hand returns to a pose, the object returns")
    path = [_rot("y", a) for a in (0, 10, 20, 30, 20, 10, 0)]
    for g in ((1.0, 1.0, 1.0), (5.143, 3.0, 2.0)):
        c = run(path, gain=g)
        check("single-axis out-and-back closes at gain %s" % (g[1],),
              obj_angle(c) < 0.01, "%.4f deg left over" % obj_angle(c))

    # ⛔⛔ AND THE LIMIT OF THAT CLAIM, WHICH QUALIFIES `RB5`'s OWN ACCEPTANCE TEST.
    # A closed loop that returns by a DIFFERENT route closes only at gain 1: scaling
    # a rotation vector does not commute with composition, so the scaled integral is
    # PATH-DEPENDENT. `RB5`'s acceptance ("hand returns to a pose -> object returns")
    # is therefore only a valid test single-axis, or at unity gain.
    ry = _rot("y", 30.0)
    rx = _rot("x", 25.0)
    loop = [IDENT3, ry, matmul(rx, ry), IDENT3]
    w_mid = HPW.weights(hand_at(matmul(rx, ry)))
    check("the loop stays inside the window (so gating cannot confound it)",
          min(w_mid) > 0.99, "weights=%s" % (tuple(round(x, 3) for x in w_mid),))
    c1 = run(loop, gain=(1.0, 1.0, 1.0))
    check("a multi-axis loop DOES close at unity gain", obj_angle(c1) < 0.01,
          "%.4f deg" % obj_angle(c1))
    c2 = run(loop, gain=(2.0, 2.0, 2.0))
    check("⛔ the same loop does NOT close at gain 2 -- path dependence is REAL",
          obj_angle(c2) > 1.0, "%.2f deg left on the object" % obj_angle(c2))

    # ── §5 ⭐⭐⭐ THE CLUTCH, AND THE CATAPULT IT MUST NOT BE ─────────────────
    print("\n§5 the clutch: a gated excursion leaves nothing behind")
    # Roll far outside its window and back by a different amount of travel.
    out = [_rot("z", a) for a in (0, 60, 80, 100, 80, 60, 0)]
    gated = [a for a in (60, 80, 100) if HPW.weights(hand_at(_rot("z", a)))[2] == 0.0]
    check("the excursion really is gated (roll weight 0 out there)", len(gated) == 3,
          "gated at %s" % (gated,))
    c = run(out)
    check("a gated round trip leaves the object where it started",
          obj_angle(c) < 0.5, "%.3f deg" % obj_angle(c))
    check("...and the frames were counted as GATED, not driven",
          c.frames_gated >= 3, "driven=%d gated=%d" % (c.frames_driven, c.frames_gated))

    # ⛔ THE COUNTER-EXAMPLE, COMPUTED RATHER THAN ASSERTED. If the reference did NOT
    # advance while gated, the first in-window frame would deliver the whole
    # excursion at once. This is the harness's own arithmetic, and it exists so §5
    # is shown to be testing something.
    stale = HO.between(hand_at(_rot("z", 0.0)), hand_at(_rot("z", 100.0)))
    raw = HO.angle_deg(stale)
    catapult = HO.angle_deg(HC.scaled_delta(stale, (1.0, 1.0, 1.0)))
    check("a NON-advancing reference holds a large unsent rotation",
          raw > 90.0, "%.1f deg of hand motion accumulated while gated" % raw)
    # ⚠ And the clamp is the ONLY thing that would have bounded it -- which is a
    # reason to keep the clamp, not a reason to relax the clutch. 45 deg in one
    # frame is still a visible glitch; the clamp bounds the damage, it does not
    # prevent it. This is why the reference advances instead.
    check("...which even CLAMPED would be a %.0f deg jump" % HC.MAX_STEP_DEG,
          abs(catapult - HC.MAX_STEP_DEG) < 1e-6,
          "%.1f deg -- bounded by MAX_STEP_DEG, not made harmless" % catapult)

    # ── §6 a refused frame drops the reference; no increment spans the gap ───
    print("\n§6 refusal: no increment may span an unobserved interval")
    flat = [(0.0, 0.0, 0.0)] * 21
    c = HC.ObjectRotationControl()
    c.update(hand_at(IDENT3))
    c.update(flat)                                   # degenerate -> refused
    check("a degenerate frame is counted as refused", c.frames_refused == 1,
          "refused=%d" % c.frames_refused)
    c.update(hand_at(_rot("y", 30.0)))               # re-seed, must NOT drive
    check("the frame after a refusal re-seeds and drives nothing",
          obj_angle(c) < 1e-9 and c.frames_driven == 0,
          "%.3e deg, driven=%d" % (obj_angle(c), c.frames_driven))
    c.update(hand_at(_rot("y", 40.0)))               # now it may drive
    check("the frame after THAT does drive", c.frames_driven == 1,
          "driven=%d, object at %.2f deg" % (c.frames_driven, obj_angle(c)))

    print("\n§6b reset() -- every per-hand estimator must die with its track (`F1`)")
    c = HC.ObjectRotationControl()
    c.update(hand_at(IDENT3))
    c.reset()
    c.update(hand_at(_rot("y", 30.0)))
    check("after reset the next frame only re-seeds", obj_angle(c) < 1e-9,
          "%.3e deg" % obj_angle(c))

    # ── §7 the gate is PER-AXIS ──────────────────────────────────────────────
    print("\n§7 per-axis gating -- one axis out does not silence the others")
    # Start rolled far out of the roll window, then YAW while staying there.
    far = _rot("z", 80.0)
    seq = [far, matmul(_rot("y", 15.0), far), matmul(_rot("y", 30.0), far)]
    c = run(seq)
    v = HO.rotvec_deg(c.orientation)
    check("roll is gated to ~nothing", abs(v[2]) < 2.0, "roll=%+.2f deg" % v[2])
    check("...while yaw still drove the object", abs(v[1]) > 5.0,
          "yaw=%+.2f deg" % v[1])

    # ── §8 the gain is linear in a single-axis motion ────────────────────────
    print("\n§8 gain scales the object's travel, linearly, per axis")
    ramp = [_rot("y", a) for a in (0, 10, 20, 30)]
    a1 = obj_angle(run(ramp, gain=(1.0, 1.0, 1.0)))
    a2 = obj_angle(run(ramp, gain=(1.0, 2.0, 1.0)))
    a3 = obj_angle(run(ramp, gain=(1.0, 3.0, 1.0)))
    check("gain 2 travels twice as far as gain 1", abs(a2 - 2 * a1) < 0.05,
          "%.3f vs 2x%.3f" % (a2, a1))
    check("gain 3 travels three times as far", abs(a3 - 3 * a1) < 0.05,
          "%.3f vs 3x%.3f" % (a3, a1))
    check("gain 0 travels nowhere", obj_angle(run(ramp, gain=(0.0, 0.0, 0.0))) < 1e-9)

    # ── §9 the clamp catches one corrupt frame ───────────────────────────────
    print("\n§9 MAX_STEP_DEG bounds a single frame")
    huge = HO.between(hand_at(IDENT3), hand_at(_rot("y", 150.0)))
    got = HO.angle_deg(HC.scaled_delta(huge, (1.0, 1.0, 1.0), gain=(10.0, 10.0, 10.0)))
    check("an absurd increment is clamped", got <= HC.MAX_STEP_DEG + 1e-6,
          "%.2f deg <= %.1f" % (got, HC.MAX_STEP_DEG))
    small = HO.between(hand_at(IDENT3), hand_at(_rot("y", 2.0)))
    got_s = HO.angle_deg(HC.scaled_delta(small, (1.0, 1.0, 1.0)))
    check("an ordinary increment is NOT clamped", got_s < HC.MAX_STEP_DEG * 0.5,
          "%.2f deg" % got_s)
    check("⛔ the clamp SCALES, it does not reject (a deadzone measured WORSE)",
          HO.angle_deg(HC.scaled_delta(small, (1.0, 1.0, 1.0))) > 0.0)

    # ── §10 numerical hygiene over a long run ────────────────────────────────
    print("\n§10 numerical hygiene -- an integrator runs for thousands of frames")
    c = HC.ObjectRotationControl()
    for i in range(2000):
        c.update(hand_at(_rot("y", 20.0 * math.sin(i * 0.05))))
    n = math.sqrt(sum(x * x for x in c.orientation))
    check("the quaternion is still unit after 2000 frames", abs(n - 1.0) < 1e-9,
          "|q|-1 = %.2e" % (n - 1.0))
    check("...and still canonical (w >= 0)", c.orientation[0] >= 0.0)

    # ── §11 a fully gated stream never touches the object ────────────────────
    print("\n§11 nothing drives a fully gated stream")
    c = HC.ObjectRotationControl()
    for a in (80.0, 85.0, 90.0, 95.0):
        c.update(hand_at(matmul(_rot("z", a), _rot("y", 90.0))))
    check("no frame was counted as driven", c.frames_driven == 0,
          "driven=%d gated=%d refused=%d"
          % (c.frames_driven, c.frames_gated, c.frames_refused))
    check("the object never moved", obj_angle(c) < 1e-9, "%.3e deg" % obj_angle(c))

    # ── §12 the calibration guard ────────────────────────────────────────────
    print("\n§12 the calibration guard")
    check("GAIN has one entry per axis", len(HC.GAIN) == 3)
    check("every gain is positive", all(g > 0.0 for g in HC.GAIN), "%s" % (HC.GAIN,))
    if not HC.CALIBRATED:
        print("  ⚠ CALIBRATED is False -- GAIN holds the owner's NOMINAL numbers,")
        print("    measured 1.7-3.1x out on the 2026-08-30 dry run. Run")
        print("    analysis/rb5_window_calibration.py on an UN-MIRRORED take.")
    check("the gains and the window agree about being calibrated",
          HC.CALIBRATED == HPW.CALIBRATED,
          "control=%s window=%s" % (HC.CALIBRATED, HPW.CALIBRATED))

    print("\n%d checks, %d failure(s)" % (CHECKS[0], len(FAILURES)))
    for f in FAILURES:
        print("  FAIL  %s" % f)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
