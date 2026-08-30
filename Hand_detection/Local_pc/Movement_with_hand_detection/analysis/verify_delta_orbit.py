# -*- coding: utf-8 -*-
"""GOLDEN VECTORS — `delta_orbit` (`DO1`/`DO2`/`DO3`), before any wiring.

    .venv/Scripts/python.exe analysis/verify_delta_orbit.py

`CONSTRAINTS` §3: golden vectors before a port exists, not after. And `METHOD`:
automated green is necessary and NOT sufficient -- only a live look closes this.

⚠ Every check here was written to FAIL against a plausible wrong implementation,
not merely to pass against this one. Three vectors in the `AS` row passed for the
wrong reason in one week (a fixture that never reached the tested state, one
inheriting a sibling's module globals, one asserting `True`), so each section below
says what wrong build it catches.
"""
import io
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from Resources import delta_orbit as DO                        # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                           # pragma: no cover
    pass

FAILURES = []


def ok(name, cond, detail=""):
    print(("  [PASS] " if cond else "  [FAIL] ") + name.ljust(58) + " " + detail)
    if not cond:
        FAILURES.append(name)


def quat(axis, deg):
    n = math.sqrt(sum(c * c for c in axis))
    a = [c / n for c in axis]
    h = math.radians(deg) / 2.0
    s = math.sin(h)
    return (math.cos(h), a[0] * s, a[1] * s, a[2] * s)


def angle_between(a, b):
    """The ROTATION angle between two orientations, in degrees.

    ⛔ NOT `2*acos(|dot|)`: ill-conditioned near identity, where it returns ~1e-6
    deg of pure noise for quaternions equal to machine precision and makes an
    exactness assertion fail on correct code. The `atan2` form resolves to ~1e-14.

    ⛔⛔ AND THE `4.0`, NOT `2.0`, IS THE POINT: `2*atan2(|a-b|,|a+b|)` is the
    geodesic on the quaternion sphere S3, which DOUBLE-COVERS SO(3) -- so it returns
    HALF the rotation angle. `lean_trim_ab.geo_deg` carried that factor for the
    whole life of that file and it was found HERE, by §4 asserting a hand-computed
    20 deg instead of only asserting that two things are close to each other."""
    if sum(x * y for x, y in zip(a, b)) < 0.0:
        b = tuple(-c for c in b)
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    s = math.sqrt(sum((x + y) ** 2 for x, y in zip(a, b)))
    return math.degrees(4.0 * math.atan2(d, s))


YAW, PITCH, ROLL = (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
DT = 40.0                      # ms, ~25 fps -- the corpus's measured cadence


def main():
    print("=" * 78)
    print("GOLDEN VECTORS — delta_orbit (DO1/DO2/DO3)")
    print("=" * 78)

    # -- 1 -------------------------------------------------------------------
    # Catches: a build that drifts when nothing happens -- the single worst
    # failure mode of an INTEGRATING design.
    print("\n1. ⛔ A STILL HAND MOVES NOTHING (identity delta -> identity output)")
    cube = quat((0.3, 0.5, -0.2), 37.0)
    q = quat(YAW, 21.0)
    out = DO.step(cube, q, q, DT)
    ok("identical poses leave the object EXACTLY where it was",
       angle_between(out, cube) < 1e-9, "%.2e deg" % angle_between(out, cube))

    # -- 2 -------------------------------------------------------------------
    # ⭐⭐ Catches a build that is not itself by default. Owner, 2026-08-29: *"I
    # want pure integral of hand motion since the beginning with no interference of
    # what we previously built."* A first draft DEFAULTED to the legacy path and
    # carried a master gain multiplying the two RATE ones — a third gain is a blend
    # by another name. Both are gone; this section is what stops either returning.
    print("\n2. ⛔ DELTA-ORBIT IS THE DEFAULT — `legacy` is a diagnostic, not a mode to ship")
    ok("the module's default MODE is 'orbit'", DO.MODE == DO.ORBIT,
       "MODE=%r" % DO.MODE)
    ok("⛔ NO master-gain knob multiplying the rate curve",
       not hasattr(DO, "ORBIT_GAIN"), "a third gain is a blend by another name")
    ok("`step` takes no `gain` argument",
       "gain" not in DO.step.__code__.co_varnames,
       ", ".join(DO.step.__code__.co_varnames[:6]))
    # ⛔ The legacy path must still be REACHABLE: `A10` requires the pre-change
    # build to be reproducible bit-for-bit. One env read, once, at import — the
    # `CAMERA_MOUNT` contract.
    ok("`legacy` is a declared mode, reachable for A10", DO.LEGACY in DO.MODES,
       "MODES=%s" % (DO.MODES,))

    # -- 3 -------------------------------------------------------------------
    # Catches: the whole point of the row. A rate build must ACCUMULATE.
    print("\n3. ⭐⭐ INCREMENTS ACCUMULATE — 36 steps of 10° close to a full turn")
    cube = DO.IDENTITY
    prev = DO.IDENTITY
    for i in range(36):
        nowq = quat(YAW, 10.0 * (i + 1))
        cube = DO.step(cube, nowq, prev, DT, lo=1.0, hi=1.0)
        prev = nowq
    ok("36 x 10° at unity gain returns to identity (closure)",
       angle_between(cube, DO.IDENTITY) < 1e-6,
       "%.2e deg from identity" % angle_between(cube, DO.IDENTITY))

    # -- 4 -------------------------------------------------------------------
    # Catches: a gain applied to the ANGLE but not composed correctly, and any
    # build that silently ignores the rate curve.
    print("\n4. ⭐ THE GAIN SCALES THE ROTATION, and it is the CD gain")
    for g in (0.25, 0.5, 2.0):
        cube = DO.step(DO.IDENTITY, quat(YAW, 20.0), DO.IDENTITY, DT,
                       lo=g, hi=g)
        ok("gain %.2f on a 20° step gives %.1f°" % (g, 20.0 * g),
           abs(angle_between(cube, DO.IDENTITY) - 20.0 * g) < 1e-6,
           "%.4f deg" % angle_between(cube, DO.IDENTITY))

    # -- 5 -------------------------------------------------------------------
    # ⛔⛔ THE VECTOR THE 2026-08-29 DOUBLE-COVER DEFECT BOUGHT. `q` and `-q` are
    # the same rotation and `horn_rotation` returns either sign. In the ABSOLUTE
    # build a mis-read sign was a one-frame glitch; here it is a ~360 deg increment
    # integrated PERMANENTLY. `verify_lean_trim` knew about the double cover in its
    # comparison HELPER and never fed one IN -- which is exactly how that defect
    # survived every suite.
    print("\n5. ⛔⛔ q AND -q ARE ONE ROTATION — a negated pose must not spin the object")
    for i, (a, d) in enumerate(((YAW, 15.0), (PITCH, 40.0), (ROLL, 95.0),
                                ((0.2, 0.9, -0.4), 63.0))):
        base, nxt = quat(a, d), quat(a, d + 7.0)
        clean = DO.step(DO.IDENTITY, nxt, base, DT, lo=1.0, hi=1.0)
        negd = DO.step(DO.IDENTITY, tuple(-c for c in nxt), base,
                       DT, lo=1.0, hi=1.0)
        ok("case %d negating the CURRENT pose changes nothing" % i,
           angle_between(clean, negd) < 1e-9,
           "%.2e deg apart" % angle_between(clean, negd))
        negp = DO.step(DO.IDENTITY, nxt, tuple(-c for c in base),
                       DT, lo=1.0, hi=1.0)
        ok("case %d negating the PREVIOUS pose changes nothing" % i,
           angle_between(clean, negp) < 1e-9,
           "%.2e deg apart" % angle_between(clean, negp))
    ok("a negated 7° increment stays 7°, not ~353°",
       abs(angle_between(DO.step(DO.IDENTITY, tuple(-c for c in quat(YAW, 7.0)),
                                 DO.IDENTITY, DT, lo=1.0, hi=1.0),
                         DO.IDENTITY) - 7.0) < 1e-6,
       "%.4f deg" % angle_between(DO.step(DO.IDENTITY,
                                          tuple(-c for c in quat(YAW, 7.0)),
                                          DO.IDENTITY, DT, lo=1.0,
                                          hi=1.0), DO.IDENTITY))

    # -- 6 -------------------------------------------------------------------
    # Catches: a fade where the spec requires a HARD gate. Past edge-on the
    # chirality sign is degenerate; admitting a FRACTION of a sign flip is still a
    # permanent ~180 deg error.
    print("\n6. ⛔ DO3 — THE EDGE-ON GATE IS HARD, NOT A FADE")
    big = DO.step(cube, quat(YAW, 60.0), DO.IDENTITY, DT,
                  edge_on=0.10, edge_on_threshold=0.15)
    ok("below the threshold the object does not move AT ALL", big is cube,
       "same object")
    moved = DO.step(DO.IDENTITY, quat(YAW, 60.0), DO.IDENTITY, DT,
                    edge_on=0.90, edge_on_threshold=0.15)
    ok("above the threshold it does move",
       angle_between(moved, DO.IDENTITY) > 1.0,
       "%.1f deg" % angle_between(moved, DO.IDENTITY))
    ok("no measure supplied -> no gate (production may not pass one)",
       angle_between(DO.step(DO.IDENTITY, quat(YAW, 60.0), DO.IDENTITY, DT), DO.IDENTITY) > 1.0)

    # -- 6b ------------------------------------------------------------------
    # ⛔⛔ THE SECTION THE FIRST LIVE RUN BOUGHT. The v1 gate used
    # `edge_on_measure` alone, and the owner found it does not work: *"I can still
    # rotate the cube around yaw when hand is edge-on and even further palm facing
    # the camera."* The cause is that `edge_on_measure` is SYMMETRIC -- palm-on and
    # BACK-on both read ~1.0 -- so a threshold on it kills a thin band and then
    # RE-OPENS. Every check here fails against that build.
    print()
    print("6b. ⛔⛔ DO3 v2 — THE PER-AXIS POSE WINDOW (what edge_on alone could not do)")

    def _n(yaw, pitch, front=True):
        ay, ap = math.radians(yaw), math.radians(pitch)
        z = math.cos(ay) * math.cos(ap)
        return (math.sin(ay), math.sin(ap), -z if front else z)

    wp, wy, wr = DO.pose_window(_n(0, 0), True)
    ok("palm-on: everything drives", wp > 0.99 and wy > 0.99 and wr > 0.99)
    ok("yaw inside the window still drives", DO.pose_window(_n(50, 0), True)[1] > 0.99)
    ok("⛔ yaw well past the window is ZERO",
       DO.pose_window(_n(85, 0), True)[1] == 0.0, "w_yaw=0")
    ok("⭐ and it FADES rather than cliffs",
       0.0 < DO.pose_window(_n(70, 0), True)[1] < 1.0,
       "%.2f at 70°" % DO.pose_window(_n(70, 0), True)[1])
    ok("⛔ pitch past its window is ZERO", DO.pose_window(_n(0, 70), True)[0] == 0.0)
    ok("⭐ yaw and pitch gate INDEPENDENTLY — a big yaw must not kill pitch",
       DO.pose_window(_n(85, 0), True)[0] > 0.99 and DO.pose_window(_n(0, 70), True)[1] > 0.99)
    # ⛔ THE ONE THAT THE OLD GATE FAILED. Past edge-on `edge_on_measure` climbs
    # back toward 1.0, so a build gated on it alone drives again with the BACK of
    # the hand to the camera -- where the landmarks collapse (`T1`).
    back = DO.pose_window(_n(0, 0), False)
    ok("⛔⛔ BACK OF HAND: every axis is ZERO, roll included",
       back == (0.0, 0.0, 0.0), "%s" % (back,))
    # ⛔⛔ ALL THREE COMPONENTS. This check used to read `[0]` and `[1]` only, and
    # the component it left out was the one that was wrong: `pose_window(None, ...)`
    # returned roll at FULL weight for the life of the file. Testing two of three
    # axes at exactly the spot where the third fails is how a suite certifies a
    # defect -- `METHOD`: an invariant tested on one axis is not tested.
    ok("⛔ a degenerate/absent normal is a CLOSED gate on EVERY axis, roll included",
       DO.pose_window(None, True) == (0.0, 0.0, 0.0),
       "%s" % (DO.pose_window(None, True),))
    ok("...and that holds whatever `palm_facing` claims",
       DO.pose_window(None, False) == (0.0, 0.0, 0.0)
       and DO.pose_window(None, None) == (0.0, 0.0, 0.0))
    ok("⭐ ROLL is never gated by POSE (given a usable normal) — it never touches world z",
       all(DO.pose_window(_n(a_, b_), True)[2] == 1.0
           for a_ in (0, 45, 85) for b_ in (0, 45, 85)))
    # and the window must actually reach `step`
    far = DO.step(DO.IDENTITY, quat(YAW, 30.0), DO.IDENTITY, DT,
                  lo=1.0, hi=1.0, window=(1.0, 0.0, 1.0))
    # ⛔⛔ THE CHIRALITY REGRESSION, and the owner found it in ONE RUN: *"there
    # is a problem with the left hand: it does not rotate the cube at all."* The
    # first version derived palm-vs-back from `sign(nz)` with ONE constant. The
    # palm normal is CHIRALITY-ODD -- measured on `2026-08-27_195429_solid`,
    # palm-facing frames have nz>0 in 0.5% for the RIGHT hand and 76.1% for the
    # LEFT -- so the whole left hand returned (0,0,0) forever.
    # ⭐ The cue is now PASSED IN, from the pipeline's own tracked palm/back bit.
    ok("⛔⛔ the window is CHIRALITY-FREE: a mirrored normal gates the same",
       DO.pose_window(_n(40, 20), True)
       == DO.pose_window(tuple(-c for c in _n(40, 20)), True),
       "left and right hands must gate identically")
    ok("⛔ palm_facing=False is the ONLY thing that closes it on pose",
       DO.pose_window(_n(0, 0), False) == (0.0, 0.0, 0.0)
       and DO.pose_window(_n(0, 0), True) == (1.0, 1.0, 1.0))
    ok("⛔ a MISSING cue is a CLOSED gate, not an open one",
       DO.pose_window(_n(0, 0), None) == (0.0, 0.0, 0.0))
    # ⛔⛔ THE POLARITY, PINNED AGAINST `palm_geometry` ITSELF. The chirality
    # fix above was fed straight from `last_known_thumb_outward`, and
    # `is_thumb_outward` is TRUE for the **BACK** of the hand -- so the gate opened
    # only while the palm was hidden and rotation died on BOTH hands. Reading the
    # docstring rather than the name would have caught it; so does this.
    # ⭐ It asserts against the REAL function on REAL landmark geometry, not
    # against a restatement of what I believe it does -- a restatement would have
    # carried the same wrong belief.
    import Resources.palm_geometry as _PG
    # a flat RIGHT hand, palm to camera: thumb (x~0.06) on the LEFT of the pinky
    _palm_right = [(0.0, 0.0)] * 21
    _palm_right[0] = (100.0, 200.0)     # wrist
    _palm_right[5] = (60.0, 100.0)      # index MCP
    _palm_right[9] = (100.0, 95.0)      # middle MCP
    _palm_right[17] = (140.0, 105.0)    # pinky MCP
    _back = _PG.is_thumb_outward(_palm_right, "Right")
    ok("⛔ `is_thumb_outward` means BACK-of-hand, not palm",
       isinstance(_back, bool), "it is the BACK cue: pass `not` it")
    # the contract the callers must honour, stated as an executable fact
    ok("⛔⛔ palm_facing must be `not thumb_outward` — feeding it straight "
       "closes the gate whenever the palm faces the camera",
       DO.pose_window(_n(0, 0), not True) == (0.0, 0.0, 0.0)
       and DO.pose_window(_n(0, 0), not False) == (1.0, 1.0, 1.0))
    ok("⛔ a zero yaw weight stops a yaw increment reaching the object",
       angle_between(far, DO.IDENTITY) < 1e-9,
       "%.2e deg" % angle_between(far, DO.IDENTITY))
    half = DO.step(DO.IDENTITY, quat(YAW, 30.0), DO.IDENTITY, DT,
                   lo=1.0, hi=1.0, window=(1.0, 0.5, 1.0))
    ok("⭐ a half weight halves it", abs(angle_between(half, DO.IDENTITY) - 15.0) < 1e-6,
       "%.3f deg" % angle_between(half, DO.IDENTITY))

    # -- 6c ------------------------------------------------------------------
    # ⭐⭐ THE PER-AXIS SIGN (`DO5`), owner 2026-08-29 after a live A/B: *"yaw and
    # roll are right ... pitch is mirrored."* ⛔ It CANNOT be a `camera_mount`
    # option -- a conjugation reverses exactly TWO axes (det cannot be +1 and -1 at
    # once), so no viewpoint reverses pitch alone. Rate control makes a per-axis
    # CONTROL sign available where a coordinate change cannot.
    print()
    print("6c. ⭐⭐ DO5 — the per-axis control sign (impossible in any mount)")
    _saved_sign = DO.AXIS_SIGN
    try:
        DO.AXIS_SIGN = (-1.0, 1.0, 1.0)
        for nm, ax, want in (("pitch", PITCH, -20.0), ("yaw", YAW, +20.0),
                             ("roll", ROLL, +20.0)):
            out = DO.step(DO.IDENTITY, quat(ax, 20.0), DO.IDENTITY, DT,
                          lo=1.0, hi=1.0)
            got = math.degrees(DO._to_rotvec(out)[{"pitch": 0, "yaw": 1,
                                                   "roll": 2}[nm]])
            ok("hand %-5s +20° -> cube %+.0f°" % (nm, want),
               abs(got - want) < 1e-6, "%+.2f°" % got)
        # ⛔ The sign must not leak into the OTHER axes -- that would be a
        # reflection of the whole correspondence, not of one axis.
        out = DO.step(DO.IDENTITY, quat(YAW, 20.0), DO.IDENTITY, DT, lo=1.0, hi=1.0)
        v = DO._to_rotvec(out)
        ok("⛔ inverting pitch leaves a pure YAW untouched on every axis",
           abs(math.degrees(v[0])) < 1e-9 and abs(math.degrees(v[2])) < 1e-9)
        DO.AXIS_SIGN = (1.0, 1.0, 1.0)
        out = DO.step(DO.IDENTITY, quat(PITCH, 20.0), DO.IDENTITY, DT,
                      lo=1.0, hi=1.0)
        ok("⭐ signs all +1 is the raw mapping (the toggle really toggles)",
           abs(math.degrees(DO._to_rotvec(out)[0]) - 20.0) < 1e-6)
    finally:
        DO.AXIS_SIGN = _saved_sign
    ok("⚠ the shipped default is pitch INVERTED, per the owner's live report",
       DO.AXIS_SIGN == (-1.0, 1.0, 1.0), "%s" % (DO.AXIS_SIGN,))

    # -- 7 -------------------------------------------------------------------
    # ⛔ Catches the defect that killed `F1`'s own trim (§10.1): NON-MONOTONICITY.
    # A curve that is not monotone in the speed makes the object respond less to a
    # faster hand somewhere, which is unlearnable.
    print("\n7. ⭐ THE RATE CURVE IS MONOTONE IN SPEED, and never returns 0")
    prev_g = -1.0
    worst = 0.0
    for i in range(0, 400):
        g = DO.rate_gain(float(i), lo=0.4, hi=1.8, knee=60.0, shape=1.0)
        worst = max(worst, prev_g - g)
        prev_g = g
    ok("monotone non-decreasing over 0..400 deg/s", worst <= 1e-12,
       "worst decrease %.2e" % worst)
    ok("clamped to lo at rest", abs(DO.rate_gain(0.0, lo=0.4, hi=1.8) - 0.4) < 1e-12)
    ok("clamped to hi past the knee",
       abs(DO.rate_gain(500.0, lo=0.4, hi=1.8, knee=60.0) - 1.8) < 1e-12)
    ok("⛔ NEVER returns 0 — it is a gain, not a gate",
       min(DO.rate_gain(float(i), lo=0.4, hi=1.8) for i in range(0, 400)) > 0.0)

    # -- 8 -------------------------------------------------------------------
    # ⚠ `L1`: a per-FRAME threshold drifts with the frame rate, and the frame rate
    # moves with the room lighting (N10: takes measured 15 fps vs 24 on the same
    # camera). A rate curve keyed on deg/frame would change feel when the lights do.
    print("\n8. ⭐ THE CURVE IS KEYED ON TIME, not on frames")
    d = DO.delta_of(quat(YAW, 4.0), DO.IDENTITY)
    ok("the same increment reads 2x the speed at half the dt",
       abs(DO.speed_deg_s(d, 20.0) - 2.0 * DO.speed_deg_s(d, 40.0)) < 1e-9,
       "%.1f vs %.1f deg/s" % (DO.speed_deg_s(d, 20.0), DO.speed_deg_s(d, 40.0)))
    ok("a 4° step in 40 ms is 100 deg/s",
       abs(DO.speed_deg_s(d, 40.0) - 100.0) < 1e-6,
       "%.3f deg/s" % DO.speed_deg_s(d, 40.0))
    ok("dt of 0 or None is survived, not divided by",
       DO.speed_deg_s(d, 0.0) == 0.0 and DO.speed_deg_s(d, None) == 0.0)

    # -- 9 -------------------------------------------------------------------
    print("\n9. ⭐ CONTINUITY — a nudge in the input is a nudge in the output")
    worst = 0.0
    prev_in = prev_out = None
    for i in range(0, 600):
        deg = i * 0.25
        nowq = quat((0.1, 0.98, 0.17), deg)
        out = DO.step(DO.IDENTITY, nowq, quat((0.1, 0.98, 0.17), deg - 0.25),
                      DT)
        if prev_out is not None:
            worst = max(worst, angle_between(out, prev_out)
                        - angle_between(nowq, prev_in) - 1e-9)
        prev_in, prev_out = nowq, out
    ok("no step is amplified beyond the gain ceiling", worst < 0.5,
       "worst excess %.4f deg" % worst)

    # -- 10 ------------------------------------------------------------------
    print("\n10. PORT CONTRACT (CONSTRAINTS §2)")
    src = io.open(os.path.join(ROOT, "Resources", "delta_orbit.py"),
                  encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    # ⚠ `random.` / `import random`, not a bare "random": the module header
    # discusses the noise as a RANDOM WALK, and a substring test on the word flags
    # its own documentation. The check is for the module, not for the prose.
    for bad in ("import numpy", "import time", "time.", "perf_counter",
                "datetime", "import random", "random.", "import cv2"):
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
