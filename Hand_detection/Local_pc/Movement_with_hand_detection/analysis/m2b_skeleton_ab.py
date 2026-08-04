"""M2b imposed-skeleton A/B under A10 (queue item 1.7).

The question 1.7 exists to answer: if the orientation frame is computed from a
LENGTH-CONSISTENT skeleton instead of raw worldLandmarks, do the large
orientation jumps behind T1/T2 shrink?

TWO DIRECTIONS, BOTH MANDATORY. 1.7 cannot over-filter -- it never rejects a
frame -- but it can DISTORT, by dragging landmarks away from a perfectly good
observation. So:

  1. STABILITY   >30 / >60 deg per-frame orientation jumps, raw vs fitted
  2. DISTORTION  mean |observation - fit| in palm widths, reported overall AND
                 on well-observed frames specifically, where the raw data
                 deserved to be left alone

⚠ The 1.6 lesson, applied: a metric that cannot tell a good change from a bad
one is worthless. "Jumps went down" is not sufficient -- a fit that snaps every
hand to a rigid mannequin would score perfectly on stability and destroy the
signal. Distortion is what catches that.

Streams built as build_v2() builds them (binding rule, spec 0.15).

    .venv/Scripts/python.exe analysis/m2b_skeleton_ab.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import hand_skeleton as HS
from Resources import palm_geometry

WELL_OBSERVED = 0.60      # observability above which the raw frame is trustworthy


def quat_of_points(world):
    e1, e2, e3, cond = AJP.frame(world)
    if cond < 1e-9:
        return None
    return AJP.qnorm(AJP.mat_to_quat(e1, e2, e3))


def run(warm_start=True, iterations=HS.ITERATIONS, fingers_only=True):
    raw_j30 = raw_j60 = fit_j30 = fit_j60 = 0
    dist_all, dist_well = [], []
    bone_cv_raw, bone_cv_fit = [], []
    n = 0

    for _name, frames in AJP.SESSIONS:
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        last_idx, prev_raw, prev_fit, prev_skel = {}, {}, {}, {}
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs_list, keep = [], []
            for h in hands:
                pts = [tuple(p) for p in h["landmarks"]]
                cen = AJP.palm_centroid(pts)
                if cen is None:
                    continue
                obs_list.append((cen, h["handedness"], h.get("score", 1.0),
                                 AJP.palm_width(pts)))
                keep.append(h)
            if not obs_list:
                trk.update([])
                continue
            for h, lab in zip(keep, trk.update(obs_list)):
                if not h.get("world_landmarks"):
                    continue
                world = [tuple(v) for v in h["world_landmarks"]]
                broke = lab in last_idx and last_idx[lab] != i - 1
                if broke:
                    prev_raw.pop(lab, None)
                    prev_fit.pop(lab, None)
                    prev_skel.pop(lab, None)
                last_idx[lab] = i

                skel = HS.fit(world,
                              initial=prev_skel.get(lab) if warm_start else None,
                              iterations=iterations, fingers_only=fingers_only)
                q_raw = quat_of_points(world)
                q_fit = quat_of_points(skel)
                if q_raw is None or q_fit is None:
                    continue
                n += 1

                r = HS.residual(world, skel)
                obs_score = palm_geometry.palm_observability(world)
                if r is not None:
                    dist_all.append(r)
                    if obs_score >= WELL_OBSERVED:
                        dist_well.append(r)

                # bone-length consistency, the property 1.4 could not achieve
                for src, acc in ((world, bone_cv_raw), (skel, bone_cv_fit)):
                    pw = HS.palm_width_world(src)
                    if pw > 1e-9:
                        acc.append([HS._norm(HS._sub(src[b], src[a])) / pw
                                    for a, b in ((0, 5), (5, 6), (6, 7), (7, 8))])

                if lab in prev_raw:
                    if AJP.angle_between(q_raw, AJP.cont(prev_raw[lab], q_raw)) > 30:
                        raw_j30 += 1
                    if AJP.angle_between(q_raw, AJP.cont(prev_raw[lab], q_raw)) > 60:
                        raw_j60 += 1
                if lab in prev_fit:
                    if AJP.angle_between(q_fit, AJP.cont(prev_fit[lab], q_fit)) > 30:
                        fit_j30 += 1
                    if AJP.angle_between(q_fit, AJP.cont(prev_fit[lab], q_fit)) > 60:
                        fit_j60 += 1

                prev_raw[lab] = q_raw
                prev_fit[lab] = q_fit
                prev_skel[lab] = skel

    return (raw_j30, raw_j60, fit_j30, fit_j60, dist_all, dist_well,
            bone_cv_raw, bone_cv_fit, n)


def cv(cols):
    """Coefficient of variation per bone, across frames."""
    if not cols:
        return []
    out = []
    for k in range(len(cols[0])):
        vals = [c[k] for c in cols]
        m = sum(vals) / len(vals)
        if m < 1e-12:
            out.append(0.0)
            continue
        var = sum((v - m) ** 2 for v in vals) / len(vals)
        out.append(math.sqrt(var) / m)
    return out


def main():
    print("=" * 78)
    print("M2b imposed skeleton -- A/B under A10 (queue item 1.7)")
    print("=" * 78)

    (r30, r60, f30, f60, d_all, d_well, cv_raw, cv_fit, n) = run()

    print(f"\nhand-frames fitted: {n}")

    print("\n--- METRIC 1: orientation stability ---")
    print(f"  {'':<12}{'>30 deg':>10}{'>60 deg':>10}")
    print(f"  {'raw':<12}{r30:>10}{r60:>10}")
    print(f"  {'fitted':<12}{f30:>10}{f60:>10}")
    if r30:
        print(f"  {'change':<12}{100.0*(f30-r30)/r30:>9.1f}%"
              f"{(100.0*(f60-r60)/r60 if r60 else 0):>9.1f}%")

    print("\n--- METRIC 2: distortion imposed on the observation ---")
    for label, d in (("all frames", d_all), ("well-observed only", d_well)):
        if not d:
            continue
        s = sorted(d)
        print(f"  {label:<22} n={len(d):<6} mean={sum(d)/len(d):.4f}  "
              f"p50={s[len(s)//2]:.4f}  p95={s[int(0.95*(len(s)-1))]:.4f}  "
              f"max={max(d):.4f}   (palm widths)")

    print("\n--- bone-length consistency (CV across frames, index chain) ---")
    print(f"  raw    {['%.3f' % c for c in cv(cv_raw)]}")
    print(f"  fitted {['%.3f' % c for c in cv(cv_fit)]}")
    print("  (1.4 died needing <0.02 here and reaching 0.06-0.22; the fit gets")
    print("   consistency BY CONSTRUCTION, so ~0 is expected, not an achievement)")

    print("\n--- sensitivity: iterations and warm start ---")
    print(f"  {'config':<24}{'>30':>8}{'>60':>8}{'distortion':>13}")
    for label, kw in (("fingers only (default)", {}),
                      ("WHOLE hand (circular)", {"fingers_only": False}),
                      ("fingers only, cold", {"warm_start": False}),
                      ("fingers only, 2 iters", {"iterations": 2})):
        a30, a60, b30, b60, da, _dw, _cr, _cf, _n = run(**kw)
        print(f"  {label:<24}{b30:>8}{b60:>8}"
              f"{(sum(da)/len(da) if da else 0):>13.4f}")

    print("\n" + "=" * 78)
    print("A10 VERDICT needs BOTH: jumps materially down AND distortion small on")
    print("well-observed frames. A fit that snaps every hand to a mannequin wins")
    print("metric 1 outright and is worthless -- metric 2 is what catches it.")
    print("=" * 78)


if __name__ == "__main__":
    main()
