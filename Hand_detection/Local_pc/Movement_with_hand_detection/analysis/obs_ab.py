"""A/B: drive the SHIPPED orientation filter with `conditioning_norm` (current)
vs `observability` (M6b's metric), on identical recorded input.

Replicates HandsTriggeredActions' filter chain exactly -- same frame construction,
same Shepperd quaternion, same _predictive_filter_step, same slerp -- and changes
ONLY which conditioning signal feeds _reliability_alpha, plus its two thresholds.

Metric: >30 deg and >60 deg per-frame orientation jumps in the FILTERED output.
That is the same metric the 2026-08-02 filter audit used to justify keeping the
filter (§13.7.1), so the comparison is like-for-like.

Thresholds are SWEPT, not guessed: conditioning_norm's 0.015/0.06 are meaningless
on observability's 0.046-0.997 scale.
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


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def scale(v, s):
    return (v[0] * s, v[1] * s, v[2] * s)


def norm(v):
    n = math.sqrt(dot(v, v))
    return (0.0, 0.0, 0.0) if n < 1e-9 else (v[0] / n, v[1] / n, v[2] / n)


def frame(w):
    e1 = norm(sub(w[PINKY_MCP], w[INDEX_MCP]))
    v2 = sub(w[MIDDLE_MCP], w[WRIST])
    v2o = sub(v2, scale(e1, dot(v2, e1)))
    cond = math.sqrt(dot(v2o, v2o))
    e2 = norm(v2o)
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
    return (1.0, 0.0, 0.0, 0.0) if n < 1e-9 else tuple(c / n for c in q)


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


def slerp(q0, q1, t):
    d = sum(a * b for a, b in zip(q0, q1))
    if d < 0:
        q1 = tuple(-c for c in q1)
        d = -d
    d = max(-1.0, min(1.0, d))
    if d > 0.9995:
        return qnorm(tuple(a + t * (b - a) for a, b in zip(q0, q1)))
    th0 = math.acos(d)
    th = th0 * t
    q2 = qnorm(tuple(b - a * d for a, b in zip(q0, q1)))
    return tuple(a * math.cos(th) + b * math.sin(th) for a, b in zip(q0, q2))


def alpha_of(v, lo, hi):
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def angle_between(qa, qb):
    d = abs(sum(a * b for a, b in zip(qa, qb)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


SESSIONS = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    frames = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    SESSIONS.append((os.path.basename(d), frames))


def run(signal, lo, hi):
    j30 = j60 = 0
    for _name, frames in SESSIONS:
        state = {}
        for rec in frames:
            for h in (rec.get("hands") or []):
                label = h["handedness"]
                w = [tuple(v) for v in h["world_landmarks"]]
                e1, e2, e3, cond = frame(w)
                if cond < 1e-9:
                    continue
                raw = qnorm(mat_to_quat(e1, e2, e3))
                sig = cond if signal == "cond" else palm_geometry.palm_observability(w)

                st = state.get(label)
                if st is None:
                    state[label] = {"last": raw, "omega": (1.0, 0.0, 0.0, 0.0)}
                    continue
                last, omega = st["last"], st["omega"]
                rawc = cont(raw, last)
                pred = cont(qmul(omega, last), last)
                fused = slerp(pred, rawc, alpha_of(sig, lo, hi))
                a = angle_between(fused, last)
                if a > 30.0:
                    j30 += 1
                if a > 60.0:
                    j60 += 1
                st["omega"] = qmul(fused, qconj(last))
                st["last"] = fused
    return j30, j60


print("baseline and unfiltered reference")
print(f"  {'config':44s} {'>30':>6s} {'>60':>6s}")
base30, base60 = run("cond", 0.015, 0.06)
print(f"  {'SHIPPED: conditioning_norm 0.015/0.06':44s} {base30:6d} {base60:6d}")
print(f"  {'(no filter at all: alpha always 1)':44s} "
      f"{run('cond', -1, -0.5)[0]:6d} {run('cond', -1, -0.5)[1]:6d}")
print()
print("observability threshold sweep")
best = None
for lo, hi in ((0.10, 0.40), (0.15, 0.60), (0.20, 0.60), (0.25, 0.70),
               (0.30, 0.80), (0.15, 0.85), (0.40, 0.90)):
    j30, j60 = run("obs", lo, hi)
    tag = f"observability {lo:.2f}/{hi:.2f}"
    mark = ""
    if j30 < base30 and j60 <= base60:
        mark = "  <-- better on both"
    if best is None or (j30, j60) < best[0]:
        best = ((j30, j60), (lo, hi))
    print(f"  {tag:44s} {j30:6d} {j60:6d}{mark}")

print()
print(f"shipped baseline : >30 {base30}  >60 {base60}")
print(f"best observability: {best[1]} -> >30 {best[0][0]}  >60 {best[0][1]}")
