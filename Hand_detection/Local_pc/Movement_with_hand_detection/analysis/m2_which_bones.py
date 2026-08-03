"""WHICH bones are actually stable enough to calibrate?

Pooled still-frames give 7-16% IQR overall -- far outside M2's <2% freeze gate. But
§0.2 measured the PALM rigid to 2.76 mm, inside target, while fingertips were the
worst (13-32% CV). So the failure may not be uniform: a reliable SUBSET may exist
even though the full 21-bone skeleton does not.

That distinction decides what M2 can deliver: a full body schema, or a smaller
trustworthy scale reference (which is all M9 actually needs).
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources.hand_model import BoneCalibrator, BONES, PALM_BONES, _median, _iqr

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

sessions = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if os.path.exists(p):
        sessions.append([json.loads(l) for l in open(p, encoding="utf-8") if l.strip()])

for label in ("Left", "Right"):
    cal = BoneCalibrator()
    for frames in sessions:
        cal._prev = None
        for rec in frames:
            for h in (rec.get("hands") or []):
                if h["handedness"] != label:
                    continue
                cal.observe([tuple(v) for v in h["world_landmarks"]])
                break

    rows = []
    for b in BONES:
        v = cal.samples.get(b, [])
        if len(v) < 50:
            continue
        m = _median(v)
        if m <= 1e-12:
            continue
        rows.append((_iqr(v) / m, b, len(v)))
    rows.sort()

    print(f"=== {label} ({cal.accepted} still frames pooled) ===")
    print(f"{'bone':>10s} {'IQR/med':>9s}  {'':2s} {'kind'}")
    for frac, b, n in rows:
        kind = "PALM" if b in PALM_BONES else ("fingertip" if b[1] in (4, 8, 12, 16, 20) else "")
        flag = "OK" if frac < 0.02 else "  "
        print(f"{str(b):>10s} {frac*100:8.2f}% {flag:>2s}  {kind}")
    palm = [f for f, b, _ in rows if b in PALM_BONES]
    tips = [f for f, b, _ in rows if b[1] in (4, 8, 12, 16, 20)]
    if palm:
        print(f"  PALM bones      : median {sorted(palm)[len(palm)//2]*100:5.2f}%  "
              f"worst {max(palm)*100:5.2f}%   ({sum(1 for f in palm if f < 0.02)}/{len(palm)} inside 2%)")
    if tips:
        print(f"  FINGERTIP bones : median {sorted(tips)[len(tips)//2]*100:5.2f}%  "
              f"worst {max(tips)*100:5.2f}%   ({sum(1 for f in tips if f < 0.02)}/{len(tips)} inside 2%)")
    print()
