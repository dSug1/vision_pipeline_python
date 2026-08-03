"""AUDIT (2026-08-03): did the M2 measurement test the quantity M2 actually claims?

Spec 2f states the calibration target is "proportions plus a per-session scale
constant that is arbitrary but internally consistent", and hand_model.py's own
header says worldLandmarks units are "self-consistent-but-unscaled". Yet
m2_which_bones.py / m2_pooled.py pool ABSOLUTE metre lengths across sessions and
poses, and apply the <2% gate to those. If MediaPipe applies a pose- or
session-dependent GLOBAL scale to world landmarks, absolute lengths fail the gate
even when proportions are stable -- i.e. the "premise does not exist in this
sensor" conclusion would be an artifact of measuring the wrong quantity.

Measured here, same still-frame gating as the published scripts:

  A  absolute lengths (reproduces the published 6-22% IQR numbers)
  B  per-frame scale-normalised: L_b / (sum of the 5 palm bone lengths that frame)
     -> tests pure PROPORTIONS
  C  cross-session agreement of B (worst bone, session-median vs corpus-median)
     -> tests "proportions + per-session scale constant" exactly as 2f words it

Also guarded against identity contamination: frames where two hands carry the
same label are skipped (the published scripts took the first, which can be the
other physical hand).
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources.hand_model import (BoneCalibrator, bone_lengths, BONES, PALM_BONES,
                                  _median, _iqr)

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

sessions = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if os.path.exists(p):
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        sessions.append((os.path.basename(d),
                         [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]))


def palm_scale(meas):
    s = sum(meas[b] for b in PALM_BONES if b in meas)
    return s if s > 1e-9 else None


for label in ("Left", "Right"):
    abs_samples = {b: [] for b in BONES}       # absolute metres, pooled
    norm_samples = {b: [] for b in BONES}      # per-frame palm-sum normalised
    per_session_norm = {}                      # session -> {bone: [normalised]}

    for name, frames in sessions:
        cal = BoneCalibrator()                 # reuse ONLY its motion gate
        sess_norm = per_session_norm.setdefault(name, {b: [] for b in BONES})
        for rec in frames:
            hands = rec.get("hands") or []
            labs = [h["handedness"] for h in hands]
            match = [h for h in hands if h["handedness"] == label]
            if len(match) != 1 or labs.count(label) != 1:
                if not match:
                    continue
                continue                       # duplicate-label frame: skip
            w = [tuple(v) for v in match[0]["world_landmarks"]]
            if not cal.observe(w):             # same still-frame gate as published
                continue
            meas = bone_lengths(w)
            sc = palm_scale(meas)
            if sc is None:
                continue
            for b, L in meas.items():
                abs_samples[b].append(L)
                norm_samples[b].append(L / sc)
                sess_norm[b].append(L / sc)

    print(f"===== {label} =====")
    for tag, samples in (("A: ABSOLUTE (published method)", abs_samples),
                         ("B: per-frame palm-normalised PROPORTIONS", norm_samples)):
        fracs = []
        for b in BONES:
            v = samples[b]
            if len(v) < 50:
                continue
            m = _median(v)
            if m > 1e-12:
                fracs.append((_iqr(v) / m, b))
        fracs.sort()
        if not fracs:
            continue
        med = fracs[len(fracs) // 2][0]
        worst = fracs[-1]
        inside = sum(1 for f, _ in fracs if f < 0.02)
        print(f"  {tag}")
        print(f"    median IQR/med {med*100:5.2f}%   worst {worst[0]*100:5.2f}% on "
              f"{worst[1]}   bones inside 2%: {inside}/{len(fracs)}")
        show = ", ".join(f"{b}:{f*100:.1f}%" for f, b in fracs[:6])
        print(f"    best bones: {show}")

    # C: per-session scale constant -- 2f's literal wording
    corpus_med = {}
    for b in BONES:
        v = norm_samples[b]
        if len(v) >= 50:
            corpus_med[b] = _median(v)
    worst = 0.0
    worst_bone = None
    n_sessions_used = 0
    for name, sess in per_session_norm.items():
        usable = {b: _median(v) for b, v in sess.items()
                  if len(v) >= 30 and b in corpus_med}
        if len(usable) < 8:
            continue
        n_sessions_used += 1
        for b, m in usable.items():
            spread = abs(m - corpus_med[b]) / corpus_med[b]
            if spread > worst:
                worst, worst_bone = spread, (name, b)
    if worst_bone:
        print(f"  C: cross-session worst disagreement of normalised medians: "
              f"{worst*100:5.2f}% ({worst_bone[1]} in {worst_bone[0]}, "
              f"{n_sessions_used} sessions)")
    print()
