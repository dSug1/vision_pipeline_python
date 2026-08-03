"""M2, calibrated the way spec 2f prescribes: POOLED ACROSS POSES.

The first acceptance run calibrated each session separately -- i.e. from a single
pose -- and got 8.35% cross-session spread against a <2% target. But 2f's whole
point is that pose DIVERSITY is what removes the bias: a bone measured only
palm-to-camera carries that pose's foreshortening bias baked in.

So: pool still-frames from ALL sessions for one physical hand, calibrate once, and
then ask the real question -- how much does a bone's measured length vary with pose
even after pooling? That number is what decides whether "20 fixed bone lengths" is
a usable prior for this sensor.
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources.hand_model import (BoneCalibrator, bone_lengths, BONES,
                                  _median, _iqr, MAX_MOTION_FRAC)

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# Split sessions into two independent halves so the cross-check is honest:
# calibrate on half A, verify against half B.
sessions = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if os.path.exists(p):
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        sessions.append((meta["sequence"],
                         [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]))

half_a = sessions[0::2]
half_b = sessions[1::2]


def calibrate(sess_list, label):
    cal = BoneCalibrator()
    for _seq, frames in sess_list:
        cal._prev = None                     # new session -> no motion continuity
        for rec in frames:
            for h in (rec.get("hands") or []):
                if h["handedness"] != label:
                    continue
                cal.observe([tuple(v) for v in h["world_landmarks"]])
                break
    return cal


for label in ("Left", "Right"):
    a = calibrate(half_a, label)
    b = calibrate(half_b, label)
    sa, ta, _ = a.progress()
    sb, tb, _ = b.progress()
    print(f"--- {label} ---")
    print(f"  half A: {a.accepted:5d} still frames, {sa}/{ta} bones stable, "
          f"frozen={'YES' if a.model else 'no'}")
    print(f"  half B: {b.accepted:5d} still frames, {sb}/{tb} bones stable, "
          f"frozen={'YES' if b.model else 'no'}")

    # Compare the POOLED medians directly, frozen or not -- that is the quantity
    # that matters, and requiring the freeze gate to trip first would hide it.
    worst = 0.0
    worst_bone = None
    n_cmp = 0
    for bone in BONES:
        va, vb = a.samples.get(bone, []), b.samples.get(bone, [])
        if len(va) < 30 or len(vb) < 30:
            continue
        ma, mb = _median(va), _median(vb)
        if ma <= 1e-12:
            continue
        spread = abs(ma - mb) / ma
        n_cmp += 1
        if spread > worst:
            worst, worst_bone = spread, bone
    if n_cmp:
        verdict = "PASS (<2%)" if worst < 0.02 else "FAIL (target <2%)"
        print(f"  pooled A-vs-B: worst bone disagreement {worst*100:5.2f}% "
              f"on {worst_bone} over {n_cmp} bones -> {verdict}")

    # How much does a single bone vary across the whole corpus, still frames only?
    if a.samples:
        spreads = []
        for bone in BONES:
            v = a.samples.get(bone, [])
            if len(v) >= 30:
                m = _median(v)
                if m > 1e-12:
                    spreads.append(_iqr(v) / m)
        if spreads:
            spreads.sort()
            print(f"  within-half IQR/median: median {spreads[len(spreads)//2]*100:5.2f}%  "
                  f"worst {spreads[-1]*100:5.2f}%   (freeze gate needs <2%)")
    print()
