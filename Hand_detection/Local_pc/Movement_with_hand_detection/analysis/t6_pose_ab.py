# -*- coding: utf-8 -*-
"""⭐⭐ T6 — THE OWNER'S STRATEGY (halves 1+2) SCORED, before it reaches a hand.

`Resources/palm_slant_pose.py` against shipped Horn, on the two things that decide it:

    LEAN     median axis error on the instructed sweeps  -> why the row exists
    JUMP     per-frame axis jump on the owner's GRABBING take -> why the previous
             attempt was rejected ("no consistency ... discontinuities everywhere")

⛔ The second column is the one the earlier build failed, and it failed it because
its metric came only from smooth instructed sweeps. Both are scored here from the
start, on the same run, so no version of that mistake is available.

⚠ Ground truth is the RECORDING INSTRUCTION, never an estimator (`B4`). The bar in
the JUMP column is HORN's own number: above it, the estimator is adding jitter the
shipped one does not have.

    .venv/Scripts/python.exe analysis/t6_pose_ab.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry as PG                     # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402
from Resources import palm_slant as PS                        # noqa: E402
from Resources import palm_slant_pose as SP                   # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
IDENT = (1.0, 0.0, 0.0, 0.0)
LIVE_TAKE = "2026-08-27_174418_slant_rig"
SWEEPS = (("yaw", "2026-08-22_134553_yaw_sweep_constant_depth", 90.0),
          ("pitch", "2026-08-04_054702_pitch_sweep_slow", 0.0))


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else float("nan")


def med(xs):
    return pct(xs, 0.5)


def load(session):
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        return None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            h = (r.get("hands") or [])
            ok = len(h) == 1 and h[0].get("landmarks") and h[0].get("world_landmarks")
            out.append((r.get("tCapture"),
                        (h[0]["landmarks"], h[0]["world_landmarks"]) if ok else None))
    return out


def axis_deg(q):
    if q is None or math.hypot(q[1], q[2]) < 1e-9:
        return None
    return math.degrees(math.atan2(q[2], q[1])) % 180.0


def most_face_on(frames):
    best, bi = -1.0, 0
    for i, (_t, fr) in enumerate(frames):
        if fr is None or len(fr[0]) <= 17:
            continue
        eo = PG.edge_on_measure(fr[0])
        if eo > best:
            best, bi = eo, i
    return bi


def call(est, st, px, wl, t):
    try:
        return est.delta(st, px, wl, t)
    except TypeError:
        return est.delta(st, px, wl)


def jump(frames, make):
    """Frame-to-frame ORIENTATION change -- how far the cube turned between frames.

    ⛔⛔ THIS REPLACED AN AXIS-JUMP METRIC THAT WAS PARTLY MEASURING NOTHING.
    The axis DIRECTION of a near-identity quaternion is undefined: a 0.5 deg rotation
    has no meaningful axis, and nobody can see one. Smoothing produces MORE
    small-angle frames, so the old metric reported smoothing as making jitter WORSE
    (tau 80 scored 42.0 against tau 0's 30.6) -- a contradiction that was the
    harness, not the estimator.
    ⭐ The quaternion distance is what the eye actually sees, is well defined at
    every magnitude, and needs no threshold to rescue it.
    """
    est = make()
    st, prev, js = None, None, []
    for t, fr in frames:
        if fr is None:
            st, prev = None, None
            continue
        px, wl = fr
        if st is None:
            st = est.freeze(px, wl)
            continue
        q = call(est, st, px, wl, t)
        if q is not None and prev is not None:
            js.append(PR.quat_angle_deg(prev, q))
        prev = q
    return med(js), pct(js, 0.95)


def lean(frames, make, truth, ci):
    est = make()
    ref = frames[ci][1]
    st = est.freeze(ref[0], ref[1])
    if st is None:
        return float("nan")
    sa0 = PG.signed_palm_area(ref[0])
    sign0 = sa0 > 0.0 if sa0 is not None else None
    errs = []
    for t, fr in frames:
        if fr is None:
            continue
        px, wl = fr
        q = call(est, st, px, wl, t)
        if q is None or PR.quat_angle_deg(IDENT, q) < 20.0:
            continue
        sa = PG.signed_palm_area(px)
        if sign0 is not None and sa is not None and (sa > 0.0) != sign0:
            continue
        a = axis_deg(q)
        if a is not None:
            errs.append(PS.tilt_delta(a, truth))
    return med(errs)


def main():
    live = load(LIVE_TAKE)
    sweeps = [(l, load(t), tr) for l, t, tr in SWEEPS]
    if not live:
        print("live take missing")
        return 1

    arms = [("HORN (shipped)", lambda: PR.Horn(PR.PALM_LANDMARKS, "ref"))]
    for feat in ("palm", "fingers"):
        for b in (0.5, 1.0):
            arms.append(("pose %-7s blend %.1f" % (feat, b),
                         (lambda f=feat, bb=b: SP.SlantPoseHorn(f, blend=bb))))

    # ⭐ tau sweep on the arm the columns above actually favour. Both metrics are
    # re-scored per tau, because smoothing the lean away would pass the JUMP column
    # while fixing nothing -- the failure mode the axis attempt died of.
    class _Tau(object):
        def __init__(self, tau):
            self.tau = tau

        def __call__(self):
            SP.SMOOTH_TAU_MS = self.tau
            return SP.SlantPoseHorn("palm", blend=1.0)

    for tau in (80.0, 150.0, 250.0):
        arms.append(("pose palm b1.0 tau %.0f" % tau, _Tau(tau)))

    w = 96
    print("=" * w)
    print("  T6 -- THE OWNER'S STRATEGY (halves 1+2), SCORED")
    print("=" * w)
    print("  LEAN: median axis error on the instructed sweeps (lower = the fix works)")
    print("  JUMP: per-frame axis jump on %s (the GRABBING take)" % LIVE_TAKE)
    print()
    print("  %-26s | %-22s | %s" % ("arm", "LEAN yaw / pitch", "JUMP med / p95  vs HORN"))
    print("  " + "-" * (w - 4))

    base = None
    for name, make in arms:
        ls = []
        for _l, fr, truth in sweeps:
            ls.append(lean(fr, make, truth, most_face_on(fr)) if fr else float("nan"))
        jm, jp = jump(live, make)
        if base is None:
            base = jp
        print("  %-26s | %6.1f / %6.1f       | %5.2f / %6.2f   %5.2fx"
              % (name, ls[0], ls[1], jm, jp, jp / base if base > 1e-9 else float("inf")))

    print("  " + "-" * (w - 4))
    print()
    print("  \u2b50 A winner must LOWER the lean AND stay at or under 1.00x on JUMP.")
    print("  \u26d4 The previous attempt scored 16.2/12.3 on lean and 1.84x on JUMP,")
    print("     and the owner rejected it on feel. The jump column is why.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
