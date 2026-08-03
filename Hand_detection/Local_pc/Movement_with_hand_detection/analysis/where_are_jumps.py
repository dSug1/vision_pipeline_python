"""WHERE do the big raw orientation jumps actually happen?

Five attempts to fix the tail via observability-keyed anisotropy have failed. The
gated attempt (5) tracked perfectly but left the tail UNTOUCHED, which implies the
big jumps are not in low-observability frames at all.

If true, the whole M6c premise -- that the tail lives where the palm normal is
unobservable -- is unfounded FOR THIS DATA, and that single fact explains all five
failures at once.

Measured on the RAW (unfiltered) frame-to-frame orientation change, so no filter
choice contaminates the answer.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from m6c_ab import (SESSIONS, frame, mat_to_quat, qnorm, cont, angle_between)
from Resources import palm_geometry

BANDS = [(0.0, 0.15), (0.15, 0.30), (0.30, 0.45), (0.45, 0.60),
         (0.60, 0.75), (0.75, 0.90), (0.90, 1.01)]

counts = {b: 0 for b in BANDS}
j30 = {b: 0 for b in BANDS}
j60 = {b: 0 for b in BANDS}

for frames in SESSIONS:
    prev = {}
    for rec in frames:
        for h in (rec.get("hands") or []):
            label = h["handedness"]
            w = [tuple(v) for v in h["world_landmarks"]]
            e1, e2, e3, cond = frame(w)
            if cond < 1e-9:
                continue
            raw = qnorm(mat_to_quat(e1, e2, e3))
            obs = palm_geometry.palm_observability(w)
            band = next((b for b in BANDS if b[0] <= obs < b[1]), BANDS[-1])
            counts[band] += 1
            if label in prev:
                d = angle_between(raw, cont(prev[label], raw))
                if d > 30:
                    j30[band] += 1
                if d > 60:
                    j60[band] += 1
            prev[label] = raw

print("RAW frame-to-frame orientation change, bucketed by observability")
print(f"{'obs band':>14s} {'frames':>8s} {'%frames':>8s} {'>30':>6s} {'>60':>6s} "
      f"{'>60/1k':>8s}")
print("-" * 60)
tot = sum(counts.values())
t30 = sum(j30.values())
t60 = sum(j60.values())
for b in BANDS:
    n = counts[b]
    rate = (1000.0 * j60[b] / n) if n else 0.0
    print(f"  [{b[0]:.2f},{b[1]:.2f}) {n:8d} {100.0*n/tot:7.1f}% {j30[b]:6d} {j60[b]:6d} "
          f"{rate:8.1f}")
print("-" * 60)
print(f"{'TOTAL':>14s} {tot:8d} {100.0:7.1f}% {t30:6d} {t60:6d}")
print()
low = sum(j60[b] for b in BANDS if b[1] <= 0.60)
lowf = sum(counts[b] for b in BANDS if b[1] <= 0.60)
print(f">60 jumps in obs < 0.60 : {low}/{t60} ({100.0*low/max(t60,1):.1f}% of jumps) "
      f"in {100.0*lowf/tot:.1f}% of frames")
print(f">60 jumps in obs >= 0.60: {t60-low}/{t60} ({100.0*(t60-low)/max(t60,1):.1f}%)")
print()
if (t60 - low) > low:
    print("=> THE TAIL IS NOT AN OBSERVABILITY PROBLEM.")
    print("   Most large jumps occur where the palm normal IS well observed, so")
    print("   anisotropy keyed to observability cannot address them. This explains")
    print("   all five failed attempts at once.")
else:
    print("=> The tail IS concentrated at low observability; the premise holds and")
    print("   the failures are implementation, not premise.")
