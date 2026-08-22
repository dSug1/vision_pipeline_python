"""T5b -- WHY is the fitted rotation axis tilted? (companion to t5_rotation_axis_fidelity.py)

t5 established THAT a yaw sweep produces a cube axis 33 deg off vertical, and that
the x-mirror is NOT the cause (negating x flips the axis SIGN and leaves the tilt
bit-identical, exactly as M R M^-1 = R(-Mn, theta) predicts).

This script separates the two remaining candidate mechanisms, which make OPPOSITE
predictions:

  (A) CONSTANT FRAME MISALIGNMENT -- the estimator's frame differs from the
      render frame by a fixed rotation. Prediction: the tilt is the SAME at every
      rotation angle. A fixed correction would fix it.

  (B) CONSTELLATION DEGENERACY -- the 5 palm landmarks lose rank as the palm turns
      edge-on, so the fit's axis wanders where the geometry stops constraining it.
      Prediction: the tilt is SMALL at small angles and BLOWS UP near 90 deg
      (edge-on), tracking `palm_observability` down. No fixed correction can fix it.

Binned by rotation angle and by M6b `palm_observability` (0 = palm points
collinear-in-projection, normal unobservable; 1 = well-conditioned).

Also runs the 5-point palm constellation against the 9-point palm+tips one --
`palm_rotation.py`'s header measured palm+tips 4x better on orientation JITTER,
and production deliberately ships palm-only (HandsTriggeredActions L482, because
tips scored worse in free play). Whether the extra span helps the AXIS is a
separate question from jitter, and it is cheap to answer.

Stdlib only. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5b_rotation_axis_mechanism.py
"""

import json
import math
import os
import sys

_RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources")
sys.path.insert(0, _RES)
import palm_rotation as PR      # noqa: E402
import palm_geometry as PG      # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# Only SINGLE-HAND takes: a two-hand take makes hands[0] ambiguous, and the
# project's binding rule forbids keying a stream on the raw MediaPipe label.
TAKES = [
    ("2026-08-04_164647_yaw_sweep_constant_depth", 1, "YAW  -> expect VERTICAL (Y)"),
    ("2026-08-04_054702_pitch_sweep_slow",         0, "PITCH-> expect HORIZONTAL (X)"),
    ("2026-08-03_171314_palm_back_s2_slow",        0, "PITCH-> expect HORIZONTAL (X)  [RIGHT]"),
    ("2026-08-03_171417_palm_back_s2_slow",        0, "PITCH-> expect HORIZONTAL (X)  [LEFT]"),
]

ANGLE_BINS = [(0, 30), (30, 60), (60, 120), (120, 181)]


def load(d):
    out = []
    with open(os.path.join(CAPTURE_ROOT, d, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def axis_angle(q):
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    ang = math.degrees(2.0 * math.acos(w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, 0.0
    return (x / s, y / s, z / s), ang


def dev_from_axis(axis, k):
    """Angle between the fitted axis LINE and world axis k, in degrees."""
    return math.degrees(math.acos(min(1.0, abs(axis[k]))))


def run(session, indices):
    """Returns per-frame rows: (rotation_angle, deviation_from_each_axis, observability)."""
    horn = PR.Horn(indices, "ref")
    state = None
    rows = []
    for fr in load(session):
        hands = fr.get("hands") or []
        if not hands:
            continue
        h = hands[0]
        wl = h.get("world_landmarks")
        if not wl or len(wl) != 21:
            continue
        px = h.get("landmarks")
        if state is None:
            state = horn.freeze(px, wl)
            continue
        q = horn.delta(state, px, wl)
        if q is None:
            continue
        axis, ang = axis_angle(q)
        if axis is None:
            continue
        obs = PG.palm_observability(wl)
        rows.append((ang, [dev_from_axis(axis, k) for k in range(3)], obs))
    return rows


def summarise(rows, expect):
    print(f"    {'rotation':>14s}  {'n':>5s}  {'off-expected':>13s}  {'observability':>13s}")
    for lo, hi in ANGLE_BINS:
        sel = [r for r in rows if lo <= r[0] < hi]
        if not sel:
            print(f"    {f'{lo}-{hi} deg':>14s}  {0:5d}          --             --")
            continue
        dev = sorted(r[1][expect] for r in sel)
        obs = sum(r[2] for r in sel) / len(sel)
        print(f"    {f'{lo}-{hi} deg':>14s}  {len(sel):5d}  "
              f"p50 {dev[len(dev)//2]:5.1f} deg  {obs:11.3f}")


def main():
    print("=" * 78)
    print("T5b  MECHANISM: constant frame misalignment, or constellation degeneracy?")
    print("=" * 78)
    print("  (A) constant misalignment -> tilt FLAT across angle bins")
    print("  (B) degeneracy            -> tilt GROWS toward 90 deg, observability FALLS\n")

    for session, expect, label in TAKES:
        if not os.path.isdir(os.path.join(CAPTURE_ROOT, session)):
            print(f"[{session}] missing -- skipped\n")
            continue
        print(f"[{label}]  {session}")
        rows = run(session, PR.PALM_LANDMARKS)
        if not rows:
            print("  no usable frames\n")
            continue
        summarise(rows, expect)

        # 5-point palm vs 9-point palm+tips, on the axis question specifically.
        rows9 = run(session, PR.PALM_AND_TIPS)
        for name, rr in (("palm 5pt ", rows), ("palm+tips", rows9)):
            sel = [r for r in rr if r[0] >= 20.0]
            if sel:
                d = sorted(r[1][expect] for r in sel)
                print(f"    {name}: median off-expected over all rotating frames "
                      f"= {d[len(d)//2]:5.1f} deg  (n={len(sel)})")
        print()

    print("=" * 78)
    print("OBSERVABILITY vs TILT, pooled over the yaw take -- the direct test of (B)")
    print("=" * 78)
    rows = run(TAKES[0][0], PR.PALM_LANDMARKS)
    rows = [r for r in rows if r[0] >= 20.0]
    bands = [(0.0, 0.15), (0.15, 0.4), (0.4, 0.7), (0.7, 1.01)]
    print(f"    {'observability':>16s}  {'n':>5s}  {'median off-vertical':>20s}")
    for lo, hi in bands:
        sel = [r for r in rows if lo <= r[2] < hi]
        if not sel:
            print(f"    {f'{lo:.2f}-{hi:.2f}':>16s}  {0:5d}                    --")
            continue
        d = sorted(r[1][1] for r in sel)
        note = "   <- DR-2 edge-on band" if hi <= 0.15 else ""
        print(f"    {f'{lo:.2f}-{hi:.2f}':>16s}  {len(sel):5d}  {d[len(d)//2]:17.1f} deg{note}")


if __name__ == "__main__":
    main()
