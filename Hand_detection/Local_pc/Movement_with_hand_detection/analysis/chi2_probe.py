"""Can the PARKED filter's machinery be repurposed as M4's chi-square gate?

Not a build -- a probe, to decide whether the 5 failed attempts left something of
value for item 1.6 rather than being written off.

The reasoning: a chi-square innovation gate needs (a) a motion-model prediction,
(b) an innovation, (c) an innovation covariance. orientation_filter.py computes all
three. Attempts 1-5 used them for GRADED blending, which pays lag on every frame.
A gate uses them for HARD accept/reject -- bimodal, like the shipped filter that
keeps winning -- and it targets IMPLAUSIBLE jumps wherever they occur, including
the 82% in well-observed frames that anisotropy structurally cannot reach.

Design under test: keep the SHIPPED filter exactly as-is, and add only a gate in
front of it. If the innovation is physically implausible, reject the measurement for
that frame and coast on the model; otherwise behave identically to today.

NIS = sum_i dz_i^2 / (P_i + R_i)  ~ chi2(3);  p=0.01 -> 11.34
Also tested: a plain physical-plausibility gate (reject > MAX_DEG per frame), which
needs no covariance at all -- if that does just as well, the covariance machinery
is NOT what is earning the improvement and should not be resurrected for it.
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

CHI2_3DOF_P01 = 11.34


def run(mode, chi2_thresh=CHI2_3DOF_P01, max_deg=25.0, coast_limit=8):
    ds = []
    ew = ef = 0.0
    nw = nf = 0
    rejected = 0
    total = 0
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
                obs = palm_geometry.palm_observability(w)
                st = state.get(label)
                if st is None:
                    state[label] = {"last": raw, "omega": (1.0, 0.0, 0.0, 0.0),
                                    "praw": raw, "P": [0.05] * 3, "coast": 0}
                    continue
                last, omega, praw = st["last"], st["omega"], st["praw"]
                rawc = cont(raw, last)
                pred = cont(qmul(omega, last), last)
                e = qlog(qmul(qconj(pred), rawc))
                total += 1

                accept = True
                if mode in ("chi2", "physical"):
                    if mode == "physical":
                        # plain plausibility: how far from the PREDICTION, in degrees
                        innov_deg = angle_between(pred, rawc)
                        accept = innov_deg <= max_deg
                    else:
                        P = st["P"]
                        R = 0.02
                        nis = sum(e[i] * e[i] / (P[i] + R) for i in range(3))
                        accept = nis <= chi2_thresh
                    if not accept and st["coast"] >= coast_limit:
                        accept = True          # M4's coast limit: never coast forever
                if accept:
                    fused = qnorm(qmul(pred, qexp(scale(e, alpha_iso(cond)))))
                    st["coast"] = 0
                    st["P"] = [max(0.02, p * 0.7) for p in st["P"]]
                else:
                    fused = pred               # reject: coast on the model
                    rejected += 1
                    st["coast"] += 1
                    st["P"] = [p + 0.05 for p in st["P"]]

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
    return dict(j30=sum(1 for d in s if d > 30), j60=sum(1 for d in s if d > 60),
                p99=s[int(n * 0.99)], mx=s[-1], tw=ew / max(nw, 1),
                tf=ef / max(nf, 1), rej=100.0 * rejected / max(total, 1))


b = run("iso")
print(f"{'config':40s} {'>30':>5s} {'>60':>5s} {'p99':>7s} {'max':>7s} "
      f"{'trk_w':>7s} {'trk_f':>7s} {'rej%':>6s}")
print("-" * 92)
print(f"{'SHIPPED isotropic':40s} {b['j30']:5d} {b['j60']:5d} {b['p99']:7.2f} "
      f"{b['mx']:7.2f} {b['tw']:6.3f}° {b['tf']:6.3f}°  {b['rej']:5.1f}  <- baseline")
print()
for th in (7.81, 11.34, 16.27, 30.0):
    r = run("chi2", chi2_thresh=th)
    ok = r['j60'] < b['j60'] and r['mx'] < b['mx'] and r['tw'] <= b['tw'] * 1.25
    print(f"{'chi2 gate thresh=%.2f' % th:40s} {r['j30']:5d} {r['j60']:5d} {r['p99']:7.2f} "
          f"{r['mx']:7.2f} {r['tw']:6.3f}° {r['tf']:6.3f}°  {r['rej']:5.1f}"
          f"{'  <== WINS BOTH' if ok else ''}")
print()
for md in (15.0, 25.0, 40.0):
    r = run("physical", max_deg=md)
    ok = r['j60'] < b['j60'] and r['mx'] < b['mx'] and r['tw'] <= b['tw'] * 1.25
    print(f"{'physical gate max=%.0f deg' % md:40s} {r['j30']:5d} {r['j60']:5d} {r['p99']:7.2f} "
          f"{r['mx']:7.2f} {r['tw']:6.3f}° {r['tf']:6.3f}°  {r['rej']:5.1f}"
          f"{'  <== WINS BOTH' if ok else ''}")
