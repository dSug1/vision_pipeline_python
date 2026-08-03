"""M6c, corrected parameterisation.

FIRST ATTEMPT WAS WRONG. The spec writes
    R = diag(sigma_long^2, sigma_base^2/obs, sigma_base^2/obs)
-- TWO parameters. I used one value for all three axes, so raising it damped every
axis uniformly: isotropic over-damping wearing an anisotropic costume. It scored
beautifully on jump counts (>60 -> 0) while sitting 37 deg away from a trustworthy
measurement, because jump counts reward a filter that ignores the hand.

CORRECTED: one small sigma for the well-observed axis, and the blown axes get
sigma^2/obs. When obs ~ 0.85 (normal) that is barely different from sigma^2, so the
filter behaves like the baseline; only when obs collapses at the crossing do those
axes damp. That is the actual intent of anisotropy.

Reports BOTH families of metric together, because either alone is misleading:
  jumps  -- rewarded by over-damping
  track  -- rewarded by no filtering at all
A good config must beat the baseline on jumps WITHOUT losing on tracking.
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


def run(mode, sigma=0.3, blown=(1, 2)):
    ds = []
    err_well = err_fast = 0.0
    n_well = n_fast = 0
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
                    s2 = sigma * sigma
                    R = [s2, s2, s2]
                    for a in blown:
                        R[a] = s2 / max(obs, EPS)
                    k = [1.0 / (1.0 + R[i]) for i in range(3)]
                    fused = qnorm(qmul(pred, qexp((e[0] * k[0], e[1] * k[1], e[2] * k[2]))))

                ds.append(angle_between(fused, last))
                te = angle_between(fused, rawc)
                if obs > 0.6:
                    err_well += te
                    n_well += 1
                if angle_between(rawc, cont(praw, last)) > 5.0:
                    err_fast += te
                    n_fast += 1
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
                st["praw"] = raw
    s = sorted(ds)
    n = len(s)
    return dict(j30=sum(1 for d in s if d > 30), j60=sum(1 for d in s if d > 60),
                p99=s[int(n * 0.99)], mx=s[-1],
                tw=err_well / max(n_well, 1), tf=err_fast / max(n_fast, 1))


b = run("iso")
print(f"{'config':30s} {'>30':>6s} {'>60':>6s} {'p99':>7s} {'max':>7s} "
      f"{'track_well':>11s} {'track_fast':>11s}")
print("-" * 84)
print(f"{'SHIPPED isotropic':30s} {b['j30']:6d} {b['j60']:6d} {b['p99']:7.2f} "
      f"{b['mx']:7.2f} {b['tw']:10.3f}° {b['tf']:10.3f}°")
print()
for sg in (0.1, 0.2, 0.3, 0.4, 0.5, 0.7):
    r = run("aniso", sg)
    better_jumps = r['j60'] < b['j60'] and r['mx'] < b['mx']
    keeps_track = r['tw'] <= b['tw'] * 1.25 and r['tf'] <= b['tf'] * 1.25
    mark = "  <== WINS BOTH" if better_jumps and keeps_track else ""
    if better_jumps and not keeps_track:
        mark = "  (jumps better, tracking worse)"
    print(f"{'aniso sigma=%.2f' % sg:30s} {r['j30']:6d} {r['j60']:6d} {r['p99']:7.2f} "
          f"{r['mx']:7.2f} {r['tw']:10.3f}° {r['tf']:10.3f}°{mark}")
