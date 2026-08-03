"""M6b evaluation (queue item 2.3, stage 1) -- MEASURE BEFORE ADOPTING.

Compares the SHIPPED Gram-Schmidt palm frame against M6b's proposed SVD frame on
identical recorded input, and answers three questions in the order that matters:

  Q1 CHIRALITY. Does the SVD frame preserve handedness of the rotation? The spec
     warns explicitly that yaw/roll invert silently if the vector order changes,
     and this project has shipped that bug once (§13.6.1). If Q1 fails, nothing
     else matters.

  Q2 OBSERVABILITY. A6 forbids shipping two competing observability signals, so
     `observability = 1 - S[2]/S[1]` must either replace `conditioning_norm` or be
     shown equivalent. How do they relate?

  Q3 DOES IT PREDICT THE FAILURE? The point of M6c is that the covariance blows up
     in the normal-determining axes at the pitch crossing. So observability should
     DROP where the pitch sweeps degrade. If it does not, M6c has no signal to act
     on and the whole approach is unfounded.
"""
import glob
import json
import math
import os
import sys

import numpy as np

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 0, 5, 9, 13, 17
PALM = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)


def shipped_frame(w):
    """Exactly HandsTriggeredActions._orthonormal_frame, in numpy."""
    e1 = w[PINKY_MCP] - w[INDEX_MCP]
    n1 = np.linalg.norm(e1)
    if n1 < 1e-9:
        return None
    e1 = e1 / n1
    v2 = w[MIDDLE_MCP] - w[WRIST]
    v2o = v2 - e1 * float(v2 @ e1)
    cond = float(np.linalg.norm(v2o))
    if cond < 1e-9:
        return None
    e2 = v2o / cond
    e3 = np.cross(e1, e2)
    return np.column_stack([e1, e2, e3]), cond


def svd_frame(w):
    """M6b: SVD over the 5 palm points (landmark 1 / thumb CMC excluded)."""
    P = np.asarray([w[i] for i in PALM], float)
    P = P - P.mean(axis=0)
    U, S, Vt = np.linalg.svd(P)
    e1, e2, n = Vt[0], Vt[1], Vt[2]
    if S[0] < 1e-12:
        return None
    observability = 1.0 - (S[2] / S[1] if S[1] > 1e-12 else 1.0)
    # Fix the sign so the frame is right-handed AND its long axis points the same
    # way as the shipped frame's width axis, so the two are comparable at all.
    if float(np.cross(e1, e2) @ n) < 0:
        n = -n
    return np.column_stack([e1, e2, n]), observability


def rel_angle_deg(A, B):
    """Angle of the relative rotation A^T B, in degrees."""
    R = A.T @ B
    c = max(-1.0, min(1.0, (np.trace(R) - 1.0) / 2.0))
    return math.degrees(math.acos(c))


rows = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    seq = meta["sequence"]
    frames = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

    conds, obs, dets, jumps_shipped, jumps_svd = [], [], [], 0, 0
    # Per-HAND previous frame. Stepping through rec["hands"] with a single `prev`
    # measures Left->Right->Left and reports the angle BETWEEN THE TWO HANDS as a
    # per-frame jump -- which produced 575/576 "jumps" in a static hold on the
    # first run of this script. Same bug class as the per-hand stream issue in the
    # §0.8 analysis; caught the same way, by a number that could not be true.
    prev = {}
    for rec in frames:
        for h in (rec.get("hands") or []):
            _label = h["handedness"]
            w = np.asarray(h["world_landmarks"], float)
            fs, fv = shipped_frame(w), svd_frame(w)
            if fs is None or fv is None:
                continue
            Ms, cond = fs
            Mv, ob = fv
            conds.append(cond)
            obs.append(ob)
            # Q1: right-handedness of each frame (det must be +1, never -1)
            dets.append((float(np.linalg.det(Ms)), float(np.linalg.det(Mv))))
            # per-frame orientation jump, both constructions
            if _label in prev:
                ps, pv = prev[_label]
                if rel_angle_deg(ps, Ms) > 30.0:
                    jumps_shipped += 1
                if rel_angle_deg(pv, Mv) > 30.0:
                    jumps_svd += 1
            prev[_label] = (Ms, Mv)

    if len(conds) < 30:
        continue
    conds = np.asarray(conds)
    obs = np.asarray(obs)
    ds = np.asarray([d[0] for d in dets])
    dv = np.asarray([d[1] for d in dets])
    r = float(np.corrcoef(conds, obs)[0, 1]) if conds.std() > 0 and obs.std() > 0 else float("nan")
    rows.append((seq, len(conds), conds.mean(), obs.mean(), obs.min(), r,
                 int((ds < 0).sum()), int((dv < 0).sum()),
                 jumps_shipped, jumps_svd))

print(f"{'sequence':30s} {'n':>5s} {'cond':>7s} {'obs':>6s} {'obsmin':>7s} {'corr':>6s} "
      f"{'LH_ship':>8s} {'LH_svd':>7s} {'>30ship':>8s} {'>30svd':>7s}")
print("-" * 104)
tot_lh_s = tot_lh_v = tot_js = tot_jv = 0
for seq, n, c, o, omin, r, lhs, lhv, js, jv in rows:
    print(f"{seq:30s} {n:5d} {c:7.4f} {o:6.3f} {omin:7.3f} {r:6.2f} "
          f"{lhs:8d} {lhv:7d} {js:8d} {jv:7d}")
    tot_lh_s += lhs
    tot_lh_v += lhv
    tot_js += js
    tot_jv += jv
print("-" * 104)
print(f"LEFT-HANDED frames (must be 0): shipped {tot_lh_s}   SVD {tot_lh_v}")
print(f">30 deg per-frame jumps:        shipped {tot_js}   SVD {tot_jv}")
print()
print("obs = M6b observability (1 - S3/S2); cond = shipped conditioning_norm")
print("corr = per-session Pearson correlation between the two signals")
