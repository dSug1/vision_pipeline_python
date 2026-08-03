"""Does M6c over-damp? Jump counts REWARD a filter that ignores the hand.

A filter with gain ~0 has zero jumps and is useless. The jump metric cannot see
that, so measure tracking fidelity directly:

  tracking_error = angle(fused, raw_measurement), per frame.
      Rises if the filter lags or coasts away from reality.
      Measured on WELL-CONDITIONED frames only (observability > 0.6), where the
      raw measurement is trustworthy and the filter has NO excuse to disagree.

  lag on real motion: same, restricted to frames where the hand is genuinely
      moving fast (raw frame-to-frame change > 5 deg).

Baseline = the shipped isotropic filter. Anything much worse on these is
over-damped regardless of how good its jump counts look.
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


def run(mode, sigma_base=1.0, p_var=1.0, blown=(1, 2)):
    err_well, err_fast, n_well, n_fast = 0.0, 0.0, 0, 0
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
                    R = [sigma_base ** 2] * 3
                    for a in blown:
                        R[a] = sigma_base ** 2 / max(obs, EPS)
                    k = [p_var / (p_var + R[i]) for i in range(3)]
                    fused = qnorm(qmul(pred, qexp((e[0] * k[0], e[1] * k[1], e[2] * k[2]))))

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
    return (err_well / max(n_well, 1), err_fast / max(n_fast, 1), n_well, n_fast)


print("tracking error = mean angle(fused, raw). LOWER = follows the hand better.")
print(f"{'config':34s} {'well-cond':>11s} {'fast-motion':>13s}")
print("-" * 62)
w, f, nw, nf = run("iso")
print(f"{'SHIPPED isotropic':34s} {w:10.3f}° {f:12.3f}°     <- baseline")
for sb in (1.0, 1.5, 2.0, 3.0, 4.0):
    w2, f2, _, _ = run("aniso", sb)
    flag = ""
    if w2 > w * 1.5 or f2 > f * 1.5:
        flag = "  OVER-DAMPED vs baseline"
    print(f"{'aniso spec-ordering sb=%.1f' % sb:34s} {w2:10.3f}° {f2:12.3f}°{flag}")
print()
print(f"(well-conditioned frames n={nw}, fast-motion frames n={nf})")
