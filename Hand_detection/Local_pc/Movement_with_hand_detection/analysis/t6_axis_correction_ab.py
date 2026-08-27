# -*- coding: utf-8 -*-
"""⭐⭐ T6 — THE AXIS CORRECTION, SCORED END TO END. The A10 gate before any wiring.

`t6_tilt_is_the_axis.py` showed the FEATURE beats Horn's axis on the palm branch
(10.4 deg vs 22.8). ⛔ That is not the same claim as "the ESTIMATOR is better":
between the two sit the branch gate, the edge-on gate, the authority fade, the
roll reconciliation and the steering itself, and any of them can eat the gain.

⭐ This runs the SHIPPED `PR.Horn` against `SA.SlantAxisHorn` on identical frames
and scores the three things the owner has ever complained about, plus the one that
must not regress:

    AXIS     deviation from the instructed axis     <- the show-stopper (the LEAN)
    ANGLE    gain vs the true rotation              <- t5f: already fine, keep it
    WANDER   per-frame axis movement, p95           <- the jitter proxy
    n        frames the correction actually touched <- a gate that never fires is
                                                       an improvement that is not real

Ground truth is the RECORDING INSTRUCTION -- `yaw_sweep_constant_depth` says turn
about the vertical, `pitch_sweep_*` says about the horizontal -- so no estimator
supplies the truth it is judged against (`B4`).

⚠ `gain 0` must reproduce shipped Horn EXACTLY. It is printed as a row rather than
asserted in prose: if that row is not identical to the HORN row, the harness is
wrong and nothing below it means anything.

    .venv/Scripts/python.exe analysis/t6_axis_correction_ab.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry as PG                     # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402
from Resources import palm_slant as PS                        # noqa: E402
from Resources import palm_slant_axis as SA                   # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
IDENT = (1.0, 0.0, 0.0, 0.0)

# ⛔ CLEAN takes only. t5f measured the 2026-08-04 yaw take MIXED AXIS and said its
# numbers are not interpretable; including it would reward whichever arm tolerates
# contamination better, which is not the question.
TAKES = (
    ("yaw  ", "2026-08-22_134553_yaw_sweep_constant_depth", 90.0),
    ("pitch", "2026-08-04_054702_pitch_sweep_slow", 0.0),
)
GAINS = (0.0, 0.25, 0.50, 0.75, 1.00)


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return float("nan")
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def p95(xs):
    xs = sorted(xs)
    return xs[int(len(xs) * 0.95)] if xs else float("nan")


def load(take):
    path = os.path.join(CAPTURE, take, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        return None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            hands = r.get("hands") or []
            if len(hands) != 1:
                continue
            h = hands[0]
            if h.get("landmarks") and h.get("world_landmarks"):
                out.append((h["landmarks"], h["world_landmarks"]))
    return out


def most_face_on(frames):
    best, bi = -1.0, 0
    for i, (px, _wl) in enumerate(frames):
        if len(px) <= 17:
            continue
        pts = [px[k] for k in PS.PALM_LANDMARKS]
        a = ((max(p[0] for p in pts) - min(p[0] for p in pts))
             * (max(p[1] for p in pts) - min(p[1] for p in pts)))
        if a > best:
            best, bi = a, i
    return bi


def axis_deg(q):
    n = math.hypot(q[1], q[2])
    if n < 1e-9:
        return None
    return math.degrees(math.atan2(q[2], q[1])) % 180.0


def run(frames, est, ci):
    """(axis errors, angles, wander, touched) over the palm-facing branch."""
    ref_px, ref_wl = frames[ci]
    st = est.freeze(ref_px, ref_wl)
    if st is None:
        return None
    sa0 = PG.signed_palm_area(ref_px)
    sign0 = sa0 > 0.0 if sa0 is not None else None
    errs, angs, wander, prev = [], [], [], None
    touched = 0
    for px, wl in frames:
        q = est.delta(st, px, wl)
        if q is None:
            continue
        ang = PR.quat_angle_deg(IDENT, q)
        ad = axis_deg(q)
        if ad is None:
            continue
        if prev is not None:
            wander.append(PS.tilt_delta(ad, prev))
        prev = ad
        if getattr(est, "last_applied", 0.0) > 0.0:
            touched += 1
        # \u26d4 scored on the GRAB's branch only -- the correction deliberately does
        # nothing off it, so pooling the back half would dilute both arms equally
        # and hide the effect the test exists to measure.
        sa = PG.signed_palm_area(px)
        if sign0 is not None and sa is not None and (sa > 0.0) != sign0:
            continue
        if ang < 20.0:                    # axis is meaningless on a hand barely turned
            continue
        errs.append(ad)
        angs.append(ang)
    return errs, angs, wander, touched


def main():
    w = 92
    print("=" * w)
    print("  T6 -- THE AXIS CORRECTION, A10-SCORED (shipped Horn vs SlantAxisHorn)")
    print("=" * w)

    for label, take, truth in TAKES:
        frames = load(take)
        if not frames:
            print("\n  [%s] take not found: %s" % (label, take))
            continue
        ci = most_face_on(frames)
        print("\n  [%s] %s   frames %d   canonical #%d   truth = %.0f deg"
              % (label, take, len(frames), ci, truth))
        print("  %-22s %6s | %-22s | %-14s | %s"
              % ("arm", "n", "AXIS err vs truth", "WANDER p95", "touched"))
        print("  " + "-" * (w - 4))

        base = None
        for gain in (None,) + GAINS:
            est = PR.Horn(PR.PALM_LANDMARKS, "ref") if gain is None \
                else SA.SlantAxisHorn(gain=gain)
            r = run(frames, est, ci)
            if r is None:
                continue
            errs, angs, wander, touched = r
            if not errs:
                continue
            e = [PS.tilt_delta(a, truth) for a in errs]
            name = "HORN (shipped)" if gain is None else "slant-axis g=%.2f" % gain
            mark = ""
            if gain is None:
                base = (med(e), p95(e), p95(wander))
            else:
                d = base[0] - med(e)
                mark = "  %+5.1f deg" % d if abs(d) > 0.05 else "   (same)"
            print("  %-22s %6d | med %5.1f  p95 %5.1f | %5.1f          | %6d%s"
                  % (name, len(e), med(e), p95(e), p95(wander), touched, mark))
            if gain == 0.0 and base is not None:
                same = (abs(med(e) - base[0]) < 1e-9 and abs(p95(e) - base[1]) < 1e-9
                        and abs(p95(wander) - base[2]) < 1e-9)
                print("  %-22s        | %s"
                      % ("", "\u2705 g=0 reproduces shipped Horn EXACTLY"
                         if same else "\u26d4 g=0 DIFFERS FROM HORN -- harness is wrong, stop here"))

    print()
    print("=" * w)
    print("  HOW TO READ THIS")
    print("=" * w)
    print("  \u2b50 AXIS err is the LEAN. A drop here is the show-stopper getting better.")
    print("  \u26a0 WANDER is the cost side: steering the axis every frame can trade lean")
    print("     for jitter, and the owner rejected T6d for feeling worse, not for")
    print("     scoring worse. A big wander rise is a reason NOT to ship even a win.")
    print("  \u26d4 'touched' is the honesty column. If it is near zero the gates are")
    print("     eating the correction and any improvement above is noise, not effect.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
