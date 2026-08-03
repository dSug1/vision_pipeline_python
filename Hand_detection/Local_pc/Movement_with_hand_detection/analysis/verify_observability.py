"""Prove the numpy-free observability equals numpy's SVD, on real data.

A hand-rolled closed-form eigensolver is exactly the kind of thing that is subtly
wrong at the degenerate cases -- which, for this metric, are the cases that MATTER
(the pitch crossing is where l2 ~= l3). So compare against numpy on every recorded
frame, and report the worst error IN the danger band separately.
"""
import glob
import json
import os
import sys

import numpy as np

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources import palm_geometry

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
PALM = palm_geometry.PALM_3D_LANDMARKS


def numpy_observability(w):
    P = np.asarray([w[i] for i in PALM], float)
    P = P - P.mean(axis=0)
    S = np.linalg.svd(P, compute_uv=False)
    if S[1] <= 1e-12:
        return 0.0
    return 1.0 - S[2] / S[1]


worst = 0.0
worst_band = 0.0
n = n_band = 0
vals = []

for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        for h in (json.loads(line).get("hands") or []):
            w = h["world_landmarks"]
            got = palm_geometry.palm_observability(w)
            exp = numpy_observability(w)
            err = abs(got - exp)
            worst = max(worst, err)
            n += 1
            vals.append(got)
            if exp < 0.20:                    # the degenerate band that matters
                worst_band = max(worst_band, err)
                n_band += 1

vals.sort()
print(f"frames compared:            {n}")
print(f"max |closed-form - numpy|:  {worst:.3e}")
print(f"  ... within the danger band (obs < 0.20, n={n_band}): {worst_band:.3e}")
print()
print(f"observability distribution: min {vals[0]:.4f}  p1 {vals[n//100]:.4f}  "
      f"median {vals[n//2]:.4f}  max {vals[-1]:.4f}")
print()
if worst < 1e-9:
    print("PASS -- numpy-free implementation is numerically identical.")
    print("       Safe to port to JS/Swift/Kotlin by transliteration.")
    sys.exit(0)
print("FAIL -- closed form disagrees with numpy.")
sys.exit(1)
