"""How long does DR-2 actually hold the sign? Measured, not felt.

The live test asked the operator to perceive this latency, which was a bad test:
production has no on-screen indicator for the thumb-outward state, so there was
nothing to observe. It IS measurable from the recordings.

For every band entry, count frames until per-frame updates resume, and convert to
ms using that session's own measured fps (fps varies 19-27 -- finding N10).
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources import palm_geometry

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

durations_ms = []
per_seq = {}

for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    seq = meta["sequence"]
    fps = meta["measured_fps"] or 24.0
    ms_per_frame = 1000.0 / fps
    frames = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

    for label in ("Left", "Right"):
        tracker = palm_geometry.PalmFacingTracker()
        held = 0
        was_in_band = False
        seen = 0
        for rec in frames:
            hand = next((h for h in (rec.get("hands") or [])
                         if h["handedness"] == label), None)
            if hand is None:
                continue
            seen += 1
            _v, valid = tracker.update(hand["landmarks"], label)
            if not valid:
                held += 1
                was_in_band = True
            elif was_in_band:
                durations_ms.append(held * ms_per_frame)
                per_seq.setdefault(seq, []).append(held * ms_per_frame)
                held = 0
                was_in_band = False
        if was_in_band and held:            # ended still inside the band
            durations_ms.append(held * ms_per_frame)
            per_seq.setdefault(seq, []).append(held * ms_per_frame)

durations_ms.sort()
n = len(durations_ms)


def pct(p):
    return durations_ms[min(n - 1, int(n * p / 100.0))]


print(f"DR-2 freeze episodes across the corpus: {n}")
print(f"  min    {durations_ms[0]:7.1f} ms")
print(f"  median {pct(50):7.1f} ms")
print(f"  p90    {pct(90):7.1f} ms")
print(f"  p99    {pct(99):7.1f} ms")
print(f"  max    {durations_ms[-1]:7.1f} ms")
print(f"  mean   {sum(durations_ms)/n:7.1f} ms")
print()
print("per sequence (median / max ms, n episodes):")
for seq in sorted(per_seq):
    v = sorted(per_seq[seq])
    print(f"  {seq:30s} {v[len(v)//2]:7.1f} / {v[-1]:7.1f}   n={len(v)}")
