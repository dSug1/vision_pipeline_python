"""Is M6c's >60 deg reduction a real fix or just redistribution?

Three questions the headline counts cannot answer:
  Q1 Does it disturb the CONTROLS (static_hold, non_crossing, known_*, depth_sweep)?
     Those should have ~zero jumps already; any increase is a regression.
  Q2 Is the >60 reduction redistribution? If 60 deg jumps merely become 55 deg
     jumps it looks equally wrong. Check the full tail: p99, p99.9, max.
  Q3 Does it add noise in the quiet case? Mean per-frame angular change on
     static_hold should NOT rise.
"""
import glob
import json
import math
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from m6c_ab import (SESSIONS, frame, mat_to_quat, qnorm, qmul, qconj, cont,
                    qlog, qexp, angle_between, alpha_iso, scale, EPS)
from Resources import palm_geometry

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

NAMES = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    if os.path.exists(os.path.join(d, "raw_landmarks.jsonl")):
        NAMES.append(json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["sequence"])

CONTROLS = ("static_hold", "non_crossing", "known_", "depth_sweep",
            "occlusion_finger", "occlusion_behind")


def run_collect(mode, sigma_base=1.0, p_var=1.0, spin_axis=0):
    """Returns per-session list of per-frame angular deltas."""
    out = []
    for frames in SESSIONS:
        deltas = []
        state = {}
        for rec in frames:
            for h in (rec.get("hands") or []):
                label = h["handedness"]
                w = [tuple(v) for v in h["world_landmarks"]]
                e1, e2, e3, cond = frame(w)
                if cond < 1e-9:
                    continue
                raw = qnorm(mat_to_quat(e1, e2, e3))
                st = state.get(label)
                if st is None:
                    state[label] = {"last": raw, "omega": (1.0, 0.0, 0.0, 0.0)}
                    continue
                last, omega = st["last"], st["omega"]
                rawc = cont(raw, last)
                pred = cont(qmul(omega, last), last)
                err = qlog(qmul(qconj(pred), rawc))
                if mode == "iso":
                    a = alpha_iso(cond)
                    fused = qnorm(qmul(pred, qexp(scale(err, a))))
                else:
                    obs = palm_geometry.palm_observability(w)
                    R = [sigma_base ** 2] * 3
                    R[spin_axis] = sigma_base ** 2 / max(obs, EPS)
                    k = [p_var / (p_var + R[i]) for i in range(3)]
                    fused = qnorm(qmul(pred, qexp((err[0] * k[0], err[1] * k[1], err[2] * k[2]))))
                deltas.append(angle_between(fused, last))
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
        out.append(deltas)
    return out


def tail(ds):
    s = sorted(ds)
    n = len(s)
    return (s[int(n * 0.99)], s[int(n * 0.999)], s[-1], sum(s) / n)


CFGS = [("iso  (shipped)", dict(mode="iso")),
        ("aniso sb=1.0", dict(mode="aniso", sigma_base=1.0)),
        ("aniso sb=2.0", dict(mode="aniso", sigma_base=2.0))]

results = {n: run_collect(**k) for n, k in CFGS}

print("Q1/Q3 -- CONTROL sequences: mean per-frame angular change (deg) and >30 count")
print(f"{'sequence':30s} " + "".join(f"{n:>22s}" for n, _ in CFGS))
print("-" * 96)
for i, seq in enumerate(NAMES):
    if not any(c in seq for c in CONTROLS):
        continue
    row = f"{seq:30s} "
    for n, _ in CFGS:
        ds = results[n][i]
        if not ds:
            row += f"{'-':>22s}"
            continue
        row += f"{sum(ds)/len(ds):10.3f} /{sum(1 for d in ds if d > 30):5d}      "
    print(row)

print()
print("Q2 -- TAIL of the whole corpus (deg): p99 / p99.9 / max / mean")
print("-" * 96)
for n, _ in CFGS:
    allds = [d for s in results[n] for d in s]
    p99, p999, mx, mean = tail(allds)
    print(f"{n:20s} p99 {p99:7.2f}   p99.9 {p999:7.2f}   max {mx:7.2f}   mean {mean:6.3f}")

print()
print("Q2b -- pitch/crossing sequences only, >60 count")
print("-" * 96)
for n, _ in CFGS:
    tot = 0
    for i, seq in enumerate(NAMES):
        if "pitch" in seq or "palm_back" in seq:
            tot += sum(1 for d in results[n][i] if d > 60)
    print(f"{n:20s} >60 in pitch/palm_back sequences: {tot}")
