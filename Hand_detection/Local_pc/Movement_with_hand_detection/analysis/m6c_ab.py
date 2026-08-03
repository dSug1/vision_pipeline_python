"""M6c: anisotropic per-axis orientation update -- measured before shipping.

WHAT M6C ACTUALLY CHANGES. Today's filter blends prediction and measurement with a
SINGLE scalar alpha: every rotation axis is trusted equally. M6c's claim is that at
the pitch crossing the uncertainty is NOT isotropic -- one axis stays precise while
the others collapse -- so the update should be per-axis.

Implemented as an ERROR-STATE update rather than a full UKF:
    q_err_body = q_pred^-1 (x) q_meas       -> log map -> 3-vector in the BODY frame
    scale each component by its own Kalman-like gain k_i = P/(P + R_i)
    exp map back, compose onto q_pred
This IS 6c's mechanism (diagonal R in the body frame). Sigma points buy handling of
process nonlinearity, which a small-angle error state around the nominal quaternion
largely removes -- and the error-state form is numpy-free, so it ports to the web
target by transliteration. Recorded as a deliberate deviation, not an oversight.

THE ORDERING QUESTION THIS SCRIPT SETTLES. The spec writes
    R = diag(sigma_long^2, sigma_base^2/obs, sigma_base^2/obs)
i.e. axes 2 and 3 blow up. But at the crossing the palm points become ROD-like: the
rod's DIRECTION stays well determined while its SPIN ABOUT ITSELF does not -- which
makes the rotation about the long axis (component 1) the unobservable one. So the
spec's ordering may be inverted. Both are run below; data decides.

Metric: >30 / >60 deg per-frame jumps in the filtered output, same as the audit.
"""
import glob
import json
import math
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources import palm_geometry

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 5, 9, 17
EPS = 1e-6


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def scale(v, s):
    return (v[0] * s, v[1] * s, v[2] * s)


def vnorm(v):
    n = math.sqrt(dot(v, v))
    return (0.0, 0.0, 0.0) if n < 1e-9 else (v[0] / n, v[1] / n, v[2] / n)


def frame(w):
    e1 = vnorm(sub(w[PINKY_MCP], w[INDEX_MCP]))
    v2 = sub(w[MIDDLE_MCP], w[WRIST])
    v2o = sub(v2, scale(e1, dot(v2, e1)))
    cond = math.sqrt(dot(v2o, v2o))
    e2 = vnorm(v2o)
    return e1, e2, cross(e1, e2), cond


def mat_to_quat(e1, e2, e3):
    m00, m10, m20 = e1
    m01, m11, m21 = e2
    m02, m12, m22 = e3
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return (0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        return ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        return ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2
    return ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)


def qnorm(q):
    n = math.sqrt(sum(c * c for c in q))
    return (1.0, 0.0, 0.0, 0.0) if n < 1e-12 else tuple(c / n for c in q)


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def cont(q, ref):
    return tuple(-c for c in q) if sum(a * b for a, b in zip(q, ref)) < 0 else q


def qlog(q):
    """Rotation-vector (3) from a unit quaternion. Small-angle safe."""
    w = max(-1.0, min(1.0, q[0]))
    v = (q[1], q[2], q[3])
    sn = math.sqrt(dot(v, v))
    if sn < 1e-9:
        return (2.0 * v[0], 2.0 * v[1], 2.0 * v[2])
    ang = 2.0 * math.atan2(sn, w)
    k = ang / sn
    return (v[0] * k, v[1] * k, v[2] * k)


def qexp(v):
    """Unit quaternion from a rotation-vector."""
    a = math.sqrt(dot(v, v))
    if a < 1e-9:
        return qnorm((1.0, 0.5 * v[0], 0.5 * v[1], 0.5 * v[2]))
    h = a * 0.5
    s = math.sin(h) / a
    return (math.cos(h), v[0] * s, v[1] * s, v[2] * s)


def angle_between(qa, qb):
    d = abs(sum(a * b for a, b in zip(qa, qb)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


def alpha_iso(cond, lo=0.015, hi=0.06):
    if cond <= lo:
        return 0.0
    if cond >= hi:
        return 1.0
    return (cond - lo) / (hi - lo)


SESSIONS = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    SESSIONS.append([json.loads(l) for l in open(p, encoding="utf-8") if l.strip()])


def run(mode, spin_axis=0, p_var=1.0, sigma_base=1.0):
    """mode: 'iso' (shipped) or 'aniso'. spin_axis = which body axis is treated as
    the UNOBSERVABLE one (0 = about the long axis; 1,2 = the spec's ordering)."""
    j30 = j60 = 0
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

                if mode == "iso":
                    a = alpha_iso(cond)
                    err = qlog(qmul(qconj(pred), rawc))
                    fused = qnorm(qmul(pred, qexp(scale(err, a))))
                else:
                    obs = palm_geometry.palm_observability(w)
                    # per-axis measurement variance in the BODY frame
                    R = [sigma_base * sigma_base] * 3
                    R[spin_axis] = sigma_base * sigma_base / max(obs, EPS)
                    err = qlog(qmul(qconj(pred), rawc))
                    k = [p_var / (p_var + R[i]) for i in range(3)]
                    fused = qnorm(qmul(pred, qexp((err[0] * k[0],
                                                   err[1] * k[1],
                                                   err[2] * k[2]))))
                a_jump = angle_between(fused, last)
                if a_jump > 30.0:
                    j30 += 1
                if a_jump > 60.0:
                    j60 += 1
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
    return j30, j60


base = run("iso")
print(f"{'config':56s} {'>30':>6s} {'>60':>6s}")
print("-" * 72)
print(f"{'SHIPPED isotropic (conditioning_norm 0.015/0.06)':56s} {base[0]:6d} {base[1]:6d}")
print()
print("M6c anisotropic -- axis 0 = rotation ABOUT the long axis (my reading)")
for p_var, sb in ((1.0, 1.0), (2.0, 1.0), (4.0, 1.0), (1.0, 0.5), (1.0, 2.0)):
    r = run("aniso", 0, p_var, sb)
    mark = "  <-- better on both" if r[0] < base[0] and r[1] <= base[1] else ""
    print(f"  {'P=%.1f sigma_base=%.1f' % (p_var, sb):54s} {r[0]:6d} {r[1]:6d}{mark}")
print()
print("M6c anisotropic -- axes 1&2 blow up (spec's literal ordering)")
for p_var, sb in ((1.0, 1.0), (2.0, 1.0), (4.0, 1.0)):
    j30 = j60 = 0
    # emulate 'two axes blow up' by running spin_axis=1 and 2 together
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
                R = [sb * sb, sb * sb / max(obs, EPS), sb * sb / max(obs, EPS)]
                err = qlog(qmul(qconj(pred), rawc))
                k = [p_var / (p_var + R[i]) for i in range(3)]
                fused = qnorm(qmul(pred, qexp((err[0] * k[0], err[1] * k[1], err[2] * k[2]))))
                a_jump = angle_between(fused, last)
                if a_jump > 30.0:
                    j30 += 1
                if a_jump > 60.0:
                    j60 += 1
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
    mark = "  <-- better on both" if j30 < base[0] and j60 <= base[1] else ""
    print(f"  {'P=%.1f sigma_base=%.1f' % (p_var, sb):54s} {j30:6d} {j60:6d}{mark}")
