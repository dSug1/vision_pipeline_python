"""A/B the REAL propagated-covariance filter vs the shipped isotropic one.

Judged on BOTH families, because either alone is gameable:
  jumps  (>30/>60, p99, max) -- rewarded by over-damping
  track  (angle(fused, raw) where observability > 0.6) -- rewarded by no filtering

A config only counts as a win if it beats the shipped filter on the tail WITHOUT
losing tracking fidelity. That rule is what caught the previous attempt (spec §0.13).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from m6c_ab import (SESSIONS, frame, mat_to_quat, qnorm, qmul, qconj, cont,
                    qlog, qexp, angle_between, alpha_iso, scale)
from Resources import palm_geometry
from Resources.orientation_filter import OrientationFilter


def run(mode, **kw):
    ds = []
    ew = ef = 0.0
    nw = nf = 0
    for frames in SESSIONS:
        state = {}
        filters = {}
        for rec in frames:
            for h in (rec.get("hands") or []):
                label = h["handedness"]
                w = [tuple(v) for v in h["world_landmarks"]]
                e1, e2, e3, cond = frame(w)
                if cond < 1e-9:
                    continue
                raw = qnorm(mat_to_quat(e1, e2, e3))
                obs = palm_geometry.palm_observability(w)

                if mode == "iso":
                    st = state.get(label)
                    if st is None:
                        state[label] = {"last": raw, "omega": (1.0, 0.0, 0.0, 0.0), "praw": raw}
                        continue
                    last, omega, praw = st["last"], st["omega"], st["praw"]
                    rawc = cont(raw, last)
                    pred = cont(qmul(omega, last), last)
                    e = qlog(qmul(qconj(pred), rawc))
                    fused = qnorm(qmul(pred, qexp(scale(e, alpha_iso(cond)))))
                    st["omega"] = qmul(fused, qconj(last))
                    prev_raw = praw
                    st["praw"] = raw
                    st["last"] = fused
                else:
                    f = filters.get(label)
                    if f is None:
                        f = filters[label] = OrientationFilter(**kw)
                        f.update(raw, obs)
                        state[label] = {"last": f.q, "praw": raw}
                        continue
                    st = state[label]
                    last, prev_raw = st["last"], st["praw"]
                    rawc = cont(raw, last)
                    fused = f.update(rawc, obs)
                    st["praw"] = raw
                    st["last"] = fused

                ds.append(angle_between(fused, last))
                te = angle_between(fused, rawc)
                if obs > 0.6:
                    ew += te
                    nw += 1
                if angle_between(rawc, cont(prev_raw, last)) > 5.0:
                    ef += te
                    nf += 1
    s = sorted(ds)
    n = len(s)
    return dict(j30=sum(1 for d in s if d > 30), j60=sum(1 for d in s if d > 60),
                p99=s[int(n * 0.99)], mx=s[-1],
                tw=ew / max(nw, 1), tf=ef / max(nf, 1))


b = run("iso")
print(f"{'config':44s} {'>30':>5s} {'>60':>5s} {'p99':>7s} {'max':>7s} "
      f"{'trk_w':>7s} {'trk_f':>7s}")
print("-" * 88)
print(f"{'SHIPPED isotropic':44s} {b['j30']:5d} {b['j60']:5d} {b['p99']:7.2f} "
      f"{b['mx']:7.2f} {b['tw']:6.3f}° {b['tf']:6.3f}°   <- baseline")
print()

wins = []
for sl in (0.2, 0.3):
    for sb in (0.6, 1.0, 2.0):
        for q in (0.005, 0.02, 0.08):
            r = run("ukf", sigma_long=sl, sigma_base=sb, process_noise=q)
            tail_better = r['j60'] < b['j60'] and r['p99'] < b['p99'] and r['mx'] < b['mx']
            track_ok = r['tw'] <= b['tw'] * 1.25 and r['tf'] <= b['tf'] * 1.25
            v = ""
            if tail_better and track_ok:
                v = "  <== WINS BOTH"
                wins.append(((sl, sb, q), r))
            elif tail_better:
                v = "  tail better, tracking worse"
            tag = f"UKF s_long={sl} s_base={sb} Q={q}"
            print(f"{tag:44s} {r['j30']:5d} {r['j60']:5d} {r['p99']:7.2f} {r['mx']:7.2f} "
                  f"{r['tw']:6.3f}° {r['tf']:6.3f}°{v}")

print()
if wins:
    print(f"{len(wins)} config(s) beat the shipped filter on BOTH families:")
    for (sl, sb, q), r in sorted(wins, key=lambda x: (x[1]['j60'], x[1]['mx'])):
        print(f"   s_long={sl} s_base={sb} Q={q}: >60 {r['j60']} (was {b['j60']}), "
              f"max {r['mx']:.1f} (was {b['mx']:.1f}), "
              f"track {r['tw']:.3f}/{r['tf']:.3f} (was {b['tw']:.3f}/{b['tf']:.3f})")
else:
    print("NO config wins both. Propagation did not rescue M6c either -- record and stop.")
