"""M6c with the spec's TWO independent parameters, as written:

    R = diag(sigma_long^2, sigma_base^2/obs, sigma_base^2/obs)

sigma_long  -> tracking tightness on the well-observed axis (small = follows hand)
sigma_base  -> how hard the degenerate axes blow up at the crossing (large = damps)

Both previous attempts collapsed these into one value, which forces a trade the
spec never intended: tight tracking AND strong degenerate-axis damping are supposed
to be independently settable. This is the actual formulation.

A config must beat the shipped filter on the tail (p99/max/>60) WITHOUT losing
tracking fidelity. Either metric alone is gameable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from m6c_ab import (SESSIONS, frame, mat_to_quat, qnorm, qmul, qconj, cont,
                    qlog, qexp, angle_between, alpha_iso, scale, EPS)
from Resources import palm_geometry


def run(mode, s_long=0.3, s_base=1.0, blown=(1, 2)):
    ds = []
    ew = ef = 0.0
    nw = nf = 0
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
                    state[label] = {"last": raw, "omega": (1.0, 0.0, 0.0, 0.0), "praw": raw}
                    continue
                last, omega, praw = st["last"], st["omega"], st["praw"]
                rawc = cont(raw, last)
                pred = cont(qmul(omega, last), last)
                e = qlog(qmul(qconj(pred), rawc))
                obs = palm_geometry.palm_observability(w)
                if mode == "iso":
                    fused = qnorm(qmul(pred, qexp(scale(e, alpha_iso(cond)))))
                else:
                    R = [s_long * s_long] * 3
                    for a in blown:
                        R[a] = (s_base * s_base) / max(obs, EPS)
                    k = [1.0 / (1.0 + R[i]) for i in range(3)]
                    fused = qnorm(qmul(pred, qexp((e[0] * k[0], e[1] * k[1], e[2] * k[2]))))
                ds.append(angle_between(fused, last))
                te = angle_between(fused, rawc)
                if obs > 0.6:
                    ew += te
                    nw += 1
                if angle_between(rawc, cont(praw, last)) > 5.0:
                    ef += te
                    nf += 1
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
                st["praw"] = raw
    s = sorted(ds)
    n = len(s)
    return dict(j60=sum(1 for d in s if d > 60), p99=s[int(n * 0.99)], mx=s[-1],
                tw=ew / max(nw, 1), tf=ef / max(nf, 1))


b = run("iso")
print(f"SHIPPED isotropic:  >60 {b['j60']}  p99 {b['p99']:.1f}  max {b['mx']:.1f}  "
      f"track {b['tw']:.3f}/{b['tf']:.3f}")
print()
print(f"{'s_long':>7s} {'s_base':>7s} {'>60':>6s} {'p99':>7s} {'max':>7s} "
      f"{'trk_well':>9s} {'trk_fast':>9s}  verdict")
print("-" * 78)
wins = []
for s_long in (0.1, 0.2, 0.3):
    for s_base in (0.5, 1.0, 2.0, 4.0):
        r = run("aniso", s_long, s_base)
        tail_better = r['j60'] < b['j60'] and r['p99'] < b['p99'] and r['mx'] < b['mx']
        track_ok = r['tw'] <= b['tw'] * 1.25 and r['tf'] <= b['tf'] * 1.25
        v = ""
        if tail_better and track_ok:
            v = "WINS BOTH"
            wins.append((s_long, s_base, r))
        elif tail_better:
            v = "tail better, tracking worse"
        elif track_ok:
            v = "tracks fine, tail no better"
        print(f"{s_long:7.2f} {s_base:7.2f} {r['j60']:6d} {r['p99']:7.2f} {r['mx']:7.2f} "
              f"{r['tw']:8.3f}° {r['tf']:8.3f}°  {v}")
print()
if wins:
    print(f"{len(wins)} config(s) beat the shipped filter on BOTH families of metric.")
else:
    print("NO config beats the shipped filter on both. M6c not demonstrated here.")
