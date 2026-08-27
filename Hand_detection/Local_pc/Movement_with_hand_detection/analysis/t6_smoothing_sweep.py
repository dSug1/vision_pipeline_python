# -*- coding: utf-8 -*-
"""⭐⭐ T6 — HOW MUCH SMOOTHING THE AXIS CORRECTION NEEDS, and what it costs.

The owner rejected the unsmoothed correction on feel: *"no consistency in the
rotation axis, discontinuities everywhere"*. Replacing the two hard gates with one
geometric fade cut the toggle JOLT in half and barely touched the felt defect
(per-frame axis jump p95 40.6 -> 39.2 against Horn's 21.4). ⭐ So the gates were not
the dominant cause; the TARGET is noisy on a gripping hand.

This sweeps the correction's time constant and reports BOTH sides at once, because
either one alone would recommend the wrong answer:

    SMOOTHNESS  per-frame axis jump p95, on the owner's own grabbing take
                -> the bar is HORN's own number. Above it, the correction is
                   adding jitter the shipped estimator does not have.
    LEAN        median axis error on the instructed sweeps
                -> the whole reason the correction exists. Smoothing it to death
                   would score perfectly on the first column and fix nothing.

⚠ Timestamps are the recording's own `tCapture`, so this is what actually happened,
not a synthetic clock at the nominal frame rate.

⛔ A tau that flattens the jump but loses the lean is a FAILURE dressed as a pass.

    .venv/Scripts/python.exe analysis/t6_smoothing_sweep.py
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

LIVE_TAKE = "2026-08-27_174418_slant_rig"          # the owner's grabbing session
SWEEPS = (("yaw  ", "2026-08-22_134553_yaw_sweep_constant_depth", 90.0),
          ("pitch", "2026-08-04_054702_pitch_sweep_slow", 0.0))
TAUS = (0.0, 40.0, 80.0, 150.0, 250.0, 400.0)
GAIN = 0.75


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
            t = r.get("tCapture")
            hands = r.get("hands") or []
            if len(hands) != 1:
                out.append((t, None))
                continue
            h = hands[0]
            out.append((t, (h["landmarks"], h["world_landmarks"])
                        if h.get("landmarks") and h.get("world_landmarks") else None))
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
        pts = [fr[0][k] for k in PS.PALM_LANDMARKS]
        a = ((max(p[0] for p in pts) - min(p[0] for p in pts))
             * (max(p[1] for p in pts) - min(p[1] for p in pts)))
        if a > best:
            best, bi = a, i
    return bi


def jump_p95(frames, est):
    """Per-frame axis jump over a real session, re-freezing on every re-acquisition."""
    st, prev, jumps = None, None, []
    for t, fr in frames:
        if fr is None:
            st, prev = None, None
            continue
        px, wl = fr
        if st is None:
            st = est.freeze(px, wl)
            continue
        q = est.delta(st, px, wl, t) if isinstance(est, SA.SlantAxisHorn) else est.delta(st, px, wl)
        a = axis_deg(q)
        if a is not None and prev is not None:
            jumps.append(PS.tilt_delta(a, prev))
        prev = a
    return pct(jumps, 0.95), med(jumps)


def lean(frames, est, truth, ci):
    """Median axis error on the palm-facing branch of an instructed sweep."""
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
        q = est.delta(st, px, wl, t) if isinstance(est, SA.SlantAxisHorn) else est.delta(st, px, wl)
        if q is None:
            continue
        if PR.quat_angle_deg(IDENT, q) < 20.0:
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
    if not live:
        print("live take not found: %s" % LIVE_TAKE)
        return 1
    sweeps = [(lbl, load(t), truth) for lbl, t, truth in SWEEPS]

    w = 92
    print("=" * w)
    print("  T6 -- SMOOTHING SWEEP   (correction gain %.2f)" % GAIN)
    print("=" * w)
    print("  SMOOTHNESS on %s (the owner's grabbing take)" % LIVE_TAKE)
    print("  LEAN on the instructed sweeps -- the reason the correction exists")
    print()

    hp95, hmed = jump_p95(live, PR.Horn(PR.PALM_LANDMARKS, "ref"))
    base_lean = {}
    for lbl, fr, truth in sweeps:
        if fr:
            base_lean[lbl] = lean(fr, PR.Horn(PR.PALM_LANDMARKS, "ref"), truth,
                                  most_face_on(fr))
    print("  %-12s | %-24s | %s" % ("tau", "axis jump  med / p95", "LEAN med (yaw / pitch)"))
    print("  " + "-" * (w - 4))
    print("  %-12s | %5.2f / %6.2f  %-8s | %5.1f / %5.1f   <- THE BAR"
          % ("HORN", hmed, hp95, "", base_lean.get("yaw  ", float("nan")),
             base_lean.get("pitch", float("nan"))))

    best = None
    for tau in TAUS:
        SA.SMOOTH_TAU_MS = tau
        m, p = jump_p95(live, SA.SlantAxisHorn(gain=GAIN))[1], jump_p95(live, SA.SlantAxisHorn(gain=GAIN))[0]
        ls = {}
        for lbl, fr, truth in sweeps:
            if fr:
                ls[lbl] = lean(fr, SA.SlantAxisHorn(gain=GAIN), truth, most_face_on(fr))
        ratio = p / hp95 if hp95 > 1e-9 else float("inf")
        ly, lp = ls.get("yaw  ", float("nan")), ls.get("pitch", float("nan"))
        # \u2b50 A candidate must beat Horn on the LEAN and not be worse on the JUMP.
        good = (ratio <= 1.05 and ly < base_lean.get("yaw  ", 99) - 2.0)
        print("  %-12s | %5.2f / %6.2f  (%.2fx) | %5.1f / %5.1f   %s"
              % ("%.0f ms" % tau if tau else "0 (off)", m, p, ratio, ly, lp,
                 "<- CANDIDATE" if good else ""))
        if good and (best is None or ly < best[1]):
            best = (tau, ly)
    SA.SMOOTH_TAU_MS = 0.0

    print("  " + "-" * (w - 4))
    print()
    if best:
        print("  \u2b50 %.0f ms keeps the lean fix AND does not add jitter over shipped Horn."
              % best[0])
        print("     \u26a0 It is a STARTING POINT for the slider, not a verdict: `T6d` scored")
        print("       well and was rejected on feel, and so was this correction's first cut.")
    else:
        print("  \u26d4 NO TAU SATISFIES BOTH. Every setting either still adds jitter over")
        print("     shipped Horn, or smooths the correction away until the lean returns.")
        print("     \u2b50 That is a real answer, not a tuning failure: it means the axis")
        print("       signal is too noisy on a GRIPPING hand to be used this way, and the")
        print("       next move is REJECTED.md, not another constant.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
