"""M2 acceptance test (queue item 1.4).

Spec acceptance: "calibrated lengths stable to <2% across three separate sessions
with the same user; residual-based downweighting measurably reduces resting jitter."

Tested here:
  A1 Does it converge at all, and on how much data?
  A2 Are the frozen lengths stable ACROSS SESSIONS? (the real test -- same hand,
     different recordings, so disagreement is estimator error)
  A3 Does pose-normalisation actually fix what N2 says is broken -- i.e. does the
     RAW residual track hand motion (bad) while the normalised one does not?
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources.hand_model import BoneCalibrator, HandModel, bone_lengths, BONES, _median

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

sessions = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    frames = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    sessions.append((meta["sequence"], frames))

print("A1/A2 -- convergence and cross-session stability")
print(f"{'session':30s} {'hand':>5s} {'used':>6s} {'rej':>6s} {'stable':>8s} {'frozen':>7s}")
print("-" * 74)

models = {}
for seq, frames in sessions:
    for label in ("Left", "Right"):
        cal = BoneCalibrator()
        for rec in frames:
            for h in (rec.get("hands") or []):
                if h["handedness"] != label:
                    continue
                cal.observe([tuple(v) for v in h["world_landmarks"]])
                break
        st, tot, least = cal.progress()
        if cal.accepted < 30:
            continue
        print(f"{seq:30s} {label:>5s} {cal.accepted:6d} {cal.rejected_motion:6d} "
              f"{st:4d}/{tot:<3d} {'YES' if cal.model else 'no':>7s}")
        if cal.model:
            models.setdefault(label, []).append((seq, cal.model))

print()
print("A2 -- cross-session agreement of frozen bone lengths (same hand)")
print("-" * 74)
for label, ms in models.items():
    if len(ms) < 2:
        print(f"{label}: only {len(ms)} converged session(s) -- cannot cross-check")
        continue
    worst = 0.0
    worst_bone = None
    for b in BONES:
        vals = [m.lengths[b] for _s, m in ms if b in m.lengths]
        if len(vals) < 2:
            continue
        med = _median(vals)
        if med <= 1e-9:
            continue
        spread = (max(vals) - min(vals)) / med
        if spread > worst:
            worst, worst_bone = spread, b
    verdict = "PASS (<2%)" if worst < 0.02 else f"FAIL (target <2%)"
    print(f"{label}: {len(ms)} sessions, worst bone spread {worst*100:5.2f}% "
          f"on bone {worst_bone}  -> {verdict}")

print()
print("A3 -- does pose-normalisation fix N2? correlation of |residual| with motion")
print("-" * 74)
ref = None
for label, ms in models.items():
    if ms:
        ref = (label, ms[0][1])
        break
if ref is None:
    print("no frozen model available")
    sys.exit(0)

label, model = ref
raw_by_motion = {"still": [], "moving": []}
norm_by_motion = {"still": [], "moving": []}
for seq, frames in sessions:
    prev = None
    for rec in frames:
        for h in (rec.get("hands") or []):
            if h["handedness"] != label:
                continue
            w = [tuple(v) for v in h["world_landmarks"]]
            if prev is not None:
                # unit-free, same convention as BoneCalibrator._motion
                ref = ((w[0][0]-w[5][0])**2 + (w[0][1]-w[5][1])**2
                       + (w[0][2]-w[5][2])**2) ** 0.5
                motion = max(((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5
                             for a, b in zip(w, prev)) / max(ref, 1e-9)
                bucket = "still" if motion < 0.03 else "moving"
                rr = model.raw_residual(w)
                nr = model.pose_normalised_residual(w)
                if rr:
                    raw_by_motion[bucket].append(sum(abs(v) for v in rr.values()) / len(rr))
                if nr:
                    norm_by_motion[bucket].append(sum(abs(v) for v in nr.values()) / len(nr))
            prev = w
            break

for name, d in (("RAW residual", raw_by_motion), ("POSE-NORMALISED", norm_by_motion)):
    s = d["still"]
    m = d["moving"]
    if not s or not m:
        continue
    ms_, mm = sum(s) / len(s), sum(m) / len(m)
    ratio = mm / ms_ if ms_ > 1e-9 else float("inf")
    print(f"{name:18s} still {ms_:.4f}   moving {mm:.4f}   moving/still = {ratio:5.2f}x")
print()
print("N2's complaint: the raw residual reports 'the hand is moving', not 'landmark")
print("8 is bad'. A moving/still ratio near 1.0 means the pose effect is removed.")
