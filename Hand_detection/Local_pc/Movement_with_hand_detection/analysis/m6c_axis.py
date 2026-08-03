"""Settle the axis-ordering question AT THE WINNING CONFIG (sigma_base=2.0).

Earlier the spec's ordering was only tried at sigma_base=1.0, which is not a fair
comparison. Sweep sigma_base for BOTH orderings and compare like for like.

  axis 0  = rotation ABOUT the long axis is unobservable   (my reading: at the
            crossing the palm points go rod-like -- the rod's direction is known,
            its spin about itself is not)
  axes 1,2 = the spec's literal diag(sigma_long^2, base^2/obs, base^2/obs)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from m6c_ab import (SESSIONS, frame, mat_to_quat, qnorm, qmul, qconj, cont,
                    qlog, qexp, angle_between, EPS)
from Resources import palm_geometry


def run(blown_axes, sigma_base, p_var=1.0):
    ds = []
    for frames in SESSIONS:
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
                obs = palm_geometry.palm_observability(w)
                R = [sigma_base ** 2] * 3
                for a in blown_axes:
                    R[a] = sigma_base ** 2 / max(obs, EPS)
                err = qlog(qmul(qconj(pred), rawc))
                k = [p_var / (p_var + R[i]) for i in range(3)]
                fused = qnorm(qmul(pred, qexp((err[0] * k[0], err[1] * k[1], err[2] * k[2]))))
                ds.append(angle_between(fused, last))
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
    s = sorted(ds)
    n = len(s)
    return (sum(1 for d in s if d > 30), sum(1 for d in s if d > 60),
            s[int(n * 0.99)], s[-1], sum(s) / n)


print(f"{'ordering':28s} {'sb':>5s} {'>30':>6s} {'>60':>6s} {'p99':>8s} {'max':>8s} {'mean':>7s}")
print("-" * 72)
for name, axes in (("axis0 (about long axis)", (0,)), ("axes1,2 (spec literal)", (1, 2))):
    for sb in (1.0, 1.5, 2.0, 3.0, 4.0):
        j30, j60, p99, mx, mean = run(axes, sb)
        print(f"{name:28s} {sb:5.1f} {j30:6d} {j60:6d} {p99:8.2f} {mx:8.2f} {mean:7.3f}")
    print()
