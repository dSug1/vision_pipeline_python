"""T5c -- is the yaw take's 33 deg axis tilt the ESTIMATOR's error or the OPERATOR's?

t5/t5b measured the fitted axis using `world_landmarks`. That cannot answer this
question on its own: a freehand "yaw sweep" naturally carries some pitch, and an
estimator error and an operator error would look identical to a metric built on
the same data the estimator uses.

⚠ This is the B4 rule ("an anchor metric must not share an expression with the
anchor") applied to the axis question. So this script deliberately uses ONLY the
2D PIXEL landmarks, which never pass through MediaPipe's world-landmark z --
the coordinate the whole depth problem lives in.

THE INDEPENDENT SIGNATURE
--------------------------
The palm is a rigid plate (2.76 mm, spec §0.2). Rotating it about an axis
foreshortens the plate dimension PERPENDICULAR to that axis, in projection, and
leaves the parallel one alone:

    pure YAW   (vertical axis)   -> image WIDTH  (5<->17, knuckle row) collapses
                                    image LENGTH (0<->9,  wrist->mid) survives
    pure PITCH (horizontal axis) -> image LENGTH collapses
                                    image WIDTH  survives

So the ratio of the two collapses is a direct, z-free read on WHICH axis the
operator actually rotated about. If the yaw take shows width collapsing while
length holds, the operator did a clean yaw and the tilt is the estimator's.
If both collapse, the operator mixed in pitch and the tilt is partly theirs.

Reported as the 5th-percentile of each span normalised by its own 95th
percentile -- "how far down did this dimension get squashed, relative to its own
face-on size". 1.00 = never foreshortened; 0.00 = fully collapsed.

Stdlib only. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5c_operator_or_estimator.py
"""

import json
import math
import os

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

TAKES = [
    ("2026-08-22_134553_yaw_sweep_constant_depth", "YAW take CLEAN (2026-08-22)"),
    ("2026-08-04_164647_yaw_sweep_constant_depth", "YAW take CONTAMINATED (2026-08-04)"),
    ("2026-08-04_054702_pitch_sweep_slow",         "PITCH take (expect LENGTH to collapse)"),
    ("2026-08-03_171314_palm_back_s2_slow",        "PITCH take [RIGHT]"),
    ("2026-08-03_171417_palm_back_s2_slow",        "PITCH take [LEFT]"),
]

WIDTH = (5, 17)     # knuckle row  -- perpendicular to the VERTICAL axis
LENGTH = (0, 9)     # wrist->middle-MCP -- perpendicular to the HORIZONTAL axis


def spans(session):
    w, l = [], []
    path = os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            hands = (json.loads(line).get("hands") or [])
            if not hands:
                continue
            px = hands[0].get("landmarks")
            if not px or len(px) != 21:
                continue
            def d(a, b):
                return math.hypot(px[a][0] - px[b][0], px[a][1] - px[b][1])
            w.append(d(*WIDTH))
            l.append(d(*LENGTH))
    return w, l


def pct(xs, p):
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, int(len(s) * p)))]


def main():
    print("=" * 78)
    print("T5c  OPERATOR OR ESTIMATOR?  (2D pixel landmarks only -- no world z)")
    print("=" * 78)
    print("  collapse ratio = p5(span) / p95(span);  1.00 = never foreshortened,")
    print("  0.00 = fully collapsed. The axis the hand turned about is the one whose")
    print("  PERPENDICULAR span collapses.\n")
    print(f"  {'take':38s} {'WIDTH':>8s} {'LENGTH':>8s}   verdict")
    print("  " + "-" * 74)

    for session, label in TAKES:
        if not os.path.isdir(os.path.join(CAPTURE_ROOT, session)):
            print(f"  {label:38s}   (missing)")
            continue
        w, l = spans(session)
        if not w:
            print(f"  {label:38s}   (no frames)")
            continue
        rw = pct(w, 0.05) / pct(w, 0.95)
        rl = pct(l, 0.05) / pct(l, 0.95)
        if rw < rl * 0.75:
            verdict = "WIDTH collapsed  -> rotated about VERTICAL (yaw)"
        elif rl < rw * 0.75:
            verdict = "LENGTH collapsed -> rotated about HORIZONTAL (pitch)"
        else:
            verdict = "BOTH collapsed   -> MIXED axis, not a clean single-axis take"
        print(f"  {label:38s} {rw:8.3f} {rl:8.3f}   {verdict}")

    print()
    print("=" * 78)
    print("READING THIS")
    print("=" * 78)
    print("  A clean single-axis take shows ONE span collapsing and the other holding.")
    print("  If the yaw take reads 'WIDTH collapsed', the operator rotated about the")
    print("  vertical as instructed, and t5's 33 deg axis tilt is the ESTIMATOR's error.")
    print("  If it reads 'MIXED', part of that 33 deg is real operator pitch and the")
    print("  estimator is being blamed for the hand's actual motion.")


if __name__ == "__main__":
    main()
