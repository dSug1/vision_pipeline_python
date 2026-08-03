"""AUDIT (2026-08-03): are the orientation-jump findings artifacts of stream identity?

Every 2.3-era A/B and where_are_jumps.py builds per-hand streams keyed by the RAW
MediaPipe handedness label, with no frame-continuity guard. The corpus deliberately
contains label flips, duplicate labels and association swaps -- the exact defects
DR-1 was built to remove, and DR-1 (Resources/hand_identity.py) is SHIPPED in
production. So the A/Bs measured a pipeline that no longer exists, on the sessions
chosen to break it.

Three variants of the same raw >30/>60 jump census:

  V0  raw label, no guards            -- reproduces where_are_jumps.py exactly
  V1  raw label + skip duplicate-label frames + require consecutive record index
  V2  DR-1 identity-corrected streams (replay the shipped tracker) + same guards

If V2's tail and its observability distribution differ materially from V0's, the
82% claim and the five nulls were (at least partly) measuring identity artifacts.

Also: the OPEN-LOOP one-frame motion-model error on V2 streams. chi2_probe.py's
"60% of frames disagree >25 deg" was a CLOSED-LOOP rejection rate with cascading
(a rejected frame coasts, the prediction drifts, later frames keep failing until
the 8-frame coast limit) -- not a one-frame prediction error. This measures the
honest quantity: omega from the last two RAW frames, applied to the last RAW
frame, compared against the current RAW frame.
"""
import glob
import importlib.util
import json
import math
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources import palm_geometry

_HI_PATH = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
            r"\Hand_detection\Local_pc\Python_Server_MediaPipe_vision_pipeline"
            r"\Resources\hand_identity.py")
_spec = importlib.util.spec_from_file_location("hand_identity", _HI_PATH)
hand_identity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hand_identity)
HandIdentityTracker = hand_identity.HandIdentityTracker
palm_centroid = hand_identity.palm_centroid
palm_width = hand_identity.palm_width

WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 5, 9, 17


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _scale(v, s):
    return (v[0] * s, v[1] * s, v[2] * s)


def _vnorm(v):
    n = math.sqrt(_dot(v, v))
    return (0.0, 0.0, 0.0) if n < 1e-9 else (v[0] / n, v[1] / n, v[2] / n)


def frame(w):
    e1 = _vnorm(_sub(w[PINKY_MCP], w[INDEX_MCP]))
    v2 = _sub(w[MIDDLE_MCP], w[WRIST])
    v2o = _sub(v2, _scale(e1, _dot(v2, e1)))
    cond = math.sqrt(_dot(v2o, v2o))
    e2 = _vnorm(v2o)
    return e1, e2, _cross(e1, e2), cond


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


def angle_between(qa, qb):
    d = abs(sum(a * b for a, b in zip(qa, qb)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

BANDS = [(0.0, 0.15), (0.15, 0.30), (0.30, 0.45), (0.45, 0.60),
         (0.60, 0.75), (0.75, 0.90), (0.90, 1.01)]

SESSIONS = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    frames = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    SESSIONS.append((meta.get("sequence", os.path.basename(d)), frames))


def quat_of(h):
    w = [tuple(v) for v in h["world_landmarks"]]
    e1, e2, e3, cond = frame(w)
    if cond < 1e-9:
        return None, None
    return qnorm(mat_to_quat(e1, e2, e3)), palm_geometry.palm_observability(w)


def census(streams_per_session):
    """streams: {key: [(rec_idx, quat, obs), ...]} per session, already ordered."""
    counts = {b: 0 for b in BANDS}
    j30 = {b: 0 for b in BANDS}
    j60 = {b: 0 for b in BANDS}
    per_session = {}
    for name, streams in streams_per_session:
        s60 = 0
        for entries in streams.values():
            for k in range(len(entries)):
                idx, q, obs = entries[k]
                band = next((b for b in BANDS if b[0] <= obs < b[1]), BANDS[-1])
                counts[band] += 1
                if k == 0:
                    continue
                pidx, pq, _ = entries[k - 1]
                d = angle_between(q, cont(pq, q))
                if d > 30:
                    j30[band] += 1
                if d > 60:
                    j60[band] += 1
                    s60 += 1
        per_session[name] = per_session.get(name, 0) + s60
    return counts, j30, j60, per_session


def build_v0():
    out = []
    for name, frames in SESSIONS:
        streams = {}
        for i, rec in enumerate(frames):
            for h in (rec.get("hands") or []):
                q, obs = quat_of(h)
                if q is None:
                    continue
                streams.setdefault(h["handedness"], []).append((i, q, obs))
        out.append((name, streams))
    return out


def build_v1():
    out = []
    for name, frames in SESSIONS:
        streams = {}
        last_idx = {}
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            labels = [h["handedness"] for h in hands]
            for h in hands:
                if labels.count(h["handedness"]) > 1:
                    continue                      # duplicate-label frame: skip
                q, obs = quat_of(h)
                if q is None:
                    continue
                lab = h["handedness"]
                st = streams.setdefault(lab, [])
                # continuity guard: break the stream (start fresh run) on a gap
                if lab in last_idx and last_idx[lab] != i - 1:
                    st.append(None)               # sentinel: run break
                st.append((i, q, obs))
                last_idx[lab] = i
        out.append((name, {k: v for k, v in streams.items()}))
    return out


def build_v2():
    out = []
    for name, frames in SESSIONS:
        trk = HandIdentityTracker(log=lambda *a, **k: None)
        streams = {}
        last_idx = {}
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs_list = []
            keep = []
            for h in hands:
                pts = [tuple(p) for p in h["landmarks"]]
                cen = palm_centroid(pts)
                if cen is None:
                    continue
                obs_list.append((cen, h["handedness"], h.get("score", 1.0),
                                 palm_width(pts)))
                keep.append(h)
            if not obs_list:
                trk.update([])
                continue
            assigned = trk.update(obs_list)
            for h, lab in zip(keep, assigned):
                q, obs = quat_of(h)
                if q is None:
                    continue
                st = streams.setdefault(lab, [])
                if lab in last_idx and last_idx[lab] != i - 1:
                    st.append(None)
                st.append((i, q, obs))
                last_idx[lab] = i
        out.append((name, streams))
    return out


def census_with_breaks(streams_per_session):
    counts = {b: 0 for b in BANDS}
    j30 = {b: 0 for b in BANDS}
    j60 = {b: 0 for b in BANDS}
    per_session = {}
    for name, streams in streams_per_session:
        s60 = 0
        for entries in streams.values():
            prev = None
            for e in entries:
                if e is None:
                    prev = None
                    continue
                idx, q, obs = e
                band = next((b for b in BANDS if b[0] <= obs < b[1]), BANDS[-1])
                counts[band] += 1
                if prev is not None:
                    d = angle_between(q, cont(prev, q))
                    if d > 30:
                        j30[band] += 1
                    if d > 60:
                        j60[band] += 1
                        s60 += 1
                prev = q
        per_session[name] = per_session.get(name, 0) + s60
    return counts, j30, j60, per_session


def report(tag, res):
    counts, j30, j60, per_session = res
    tot = sum(counts.values())
    t30 = sum(j30.values())
    t60 = sum(j60.values())
    hi = sum(j60[b] for b in BANDS if b[0] >= 0.60)
    print(f"--- {tag} ---")
    print(f"  frames {tot}   >30 {t30}   >60 {t60}   "
          f">60 at obs>=0.60: {hi} ({100.0*hi/max(t60,1):.1f}%)")
    worst = sorted(per_session.items(), key=lambda kv: -kv[1])[:8]
    print("  worst sessions (>60):", ", ".join(f"{k}={v}" for k, v in worst if v))
    print()
    return t30, t60, hi


v0 = census(build_v0())
v1 = census_with_breaks(build_v1())
v2 = census_with_breaks(build_v2())

report("V0 raw label, no guards (published method)", v0)
report("V1 + dup-frame skip + continuity guard", v1)
report("V2 DR-1 identity-corrected + guards", v2)

# ------------- open-loop 1/2/3-frame motion model error on V2 -----------------
# This IS M7's "required first task" (measure the model's prediction error at 1,
# 2 and 3 frames ahead) -- done here on identity-corrected streams.
HORIZONS = (1, 2, 3)
errs = {h: [] for h in HORIZONS}
errs_sane = {h: [] for h in HORIZONS}
for name, streams in build_v2():
    for entries in streams.values():
        run = []
        for e in entries:
            if e is None:
                run = []
                continue
            run.append(e)
            for h in HORIZONS:
                if len(run) < 2 + h:
                    continue
                (_, q0, _), (_, q1, _) = run[-2 - h], run[-1 - h]
                (_, qt, _) = run[-1]
                q1c = cont(q1, q0)
                qtc = cont(qt, q1c)
                omega = qmul(q1c, qconj(q0))
                pred = q1c
                for _ in range(h):
                    pred = qmul(omega, pred)
                err = angle_between(qnorm(pred), qtc)
                errs[h].append(err)
                if angle_between(q1c, q0) < 30.0:
                    errs_sane[h].append(err)

for h in HORIZONS:
    for tag, es in ((f"{h}-frame, all", errs[h]),
                    (f"{h}-frame, seed<30deg", errs_sane[h])):
        es = sorted(es)
        n = len(es)
        if not n:
            continue
        mean = sum(es) / n
        med = es[n // 2]
        p90 = es[int(n * 0.90)]
        p99 = es[int(n * 0.99)]
        g15 = 100.0 * sum(1 for e in es if e > 15) / n
        g25 = 100.0 * sum(1 for e in es if e > 25) / n
        print(f"OPEN-LOOP model error ({tag:22s} n={n}): "
              f"median {med:6.2f}  mean {mean:6.2f}  p90 {p90:6.2f}  p99 {p99:7.2f}  "
              f">15deg {g15:4.1f}%  >25deg {g25:4.1f}%")
print()
print("chi2_probe's published figure was 59.9% rejected at >25 deg -- that number")
print("included closed-loop cascade rejections, not one-frame prediction error.")

# ---------------- filter A/B re-run on identity-corrected streams -------------
# Does the "no config wins both" UKF verdict survive once artifact frames are
# removed? Streams: V2 (DR-1 labels, dup-safe, run breaks at gaps). Filters are
# RESET at every run break, exactly as a live filter would be on tracking loss.
from Resources.orientation_filter import OrientationFilter


def quat_cond_of(h):
    w = [tuple(v) for v in h["world_landmarks"]]
    e1, e2, e3, cond = frame(w)
    if cond < 1e-9:
        return None, None, None
    return qnorm(mat_to_quat(e1, e2, e3)), palm_geometry.palm_observability(w), cond


def build_v2_cond():
    out = []
    for name, frames in SESSIONS:
        trk = HandIdentityTracker(log=lambda *a, **k: None)
        streams = {}
        last_idx = {}
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs_list = []
            keep = []
            for h in hands:
                pts = [tuple(p) for p in h["landmarks"]]
                cen = palm_centroid(pts)
                if cen is None:
                    continue
                obs_list.append((cen, h["handedness"], h.get("score", 1.0),
                                 palm_width(pts)))
                keep.append(h)
            if not obs_list:
                trk.update([])
                continue
            assigned = trk.update(obs_list)
            for h, lab in zip(keep, assigned):
                q, obs, cond = quat_cond_of(h)
                if q is None:
                    continue
                st = streams.setdefault(lab, [])
                if lab in last_idx and last_idx[lab] != i - 1:
                    st.append(None)
                st.append((q, obs, cond))
                last_idx[lab] = i
        out.append((name, streams))
    return out


def alpha_iso(cond, lo=0.015, hi=0.06):
    if cond <= lo:
        return 0.0
    if cond >= hi:
        return 1.0
    return (cond - lo) / (hi - lo)


def qlog(q):
    w = max(-1.0, min(1.0, q[0]))
    v = (q[1], q[2], q[3])
    sn = math.sqrt(_dot(v, v))
    if sn < 1e-9:
        return (2.0 * v[0], 2.0 * v[1], 2.0 * v[2])
    ang = 2.0 * math.atan2(sn, w)
    k = ang / sn
    return (v[0] * k, v[1] * k, v[2] * k)


def qexp(v):
    a = math.sqrt(_dot(v, v))
    if a < 1e-9:
        return qnorm((1.0, 0.5 * v[0], 0.5 * v[1], 0.5 * v[2]))
    h = a * 0.5
    s = math.sin(h) / a
    return (math.cos(h), v[0] * s, v[1] * s, v[2] * s)


V2C = build_v2_cond()


def run_clean(mode, **kw):
    ds, ew, nw = [], 0.0, 0
    for _name, streams in V2C:
        for entries in streams.values():
            st = None
            f = None
            for e in entries:
                if e is None:
                    st = None
                    f = None
                    continue
                q, obs, cond = e
                if mode == "none":
                    if st is not None:
                        rawc = cont(q, st)
                        ds.append(angle_between(rawc, st))
                        st = rawc
                    else:
                        st = q
                    continue
                if mode in ("iso", "iso_obs"):
                    if st is None:
                        st = {"last": q, "omega": (1.0, 0.0, 0.0, 0.0)}
                        continue
                    last, omega = st["last"], st["omega"]
                    rawc = cont(q, last)
                    pred = cont(qmul(omega, last), last)
                    err = qlog(qmul(qconj(pred), rawc))
                    if mode == "iso_obs":
                        a = alpha_iso(obs, kw.get("lo", 0.15), kw.get("hi", 0.60))
                    else:
                        a = alpha_iso(cond)
                    fused = qnorm(qmul(pred, qexp((err[0] * a, err[1] * a, err[2] * a))))
                    st["omega"] = qmul(fused, qconj(last))
                    st["last"] = fused
                else:
                    if f is None:
                        f = OrientationFilter(**kw)
                        f.update(q, obs)
                        st = f.q
                        continue
                    last = st
                    rawc = cont(q, last)
                    fused = f.update(rawc, obs)
                    st = fused
                d = angle_between(fused, last)
                ds.append(d)
                te = angle_between(fused, rawc)
                if obs > 0.6:
                    ew += te
                    nw += 1
    s = sorted(ds)
    n = len(s)
    return dict(j30=sum(1 for d in s if d > 30), j60=sum(1 for d in s if d > 60),
                p99=s[int(n * 0.99)], mx=s[-1], tw=ew / max(nw, 1))


print()
print("FILTER A/B RE-RUN ON IDENTITY-CORRECTED (V2) STREAMS")
print(f"{'config':46s} {'>30':>5s} {'>60':>5s} {'p99':>7s} {'max':>7s} {'trk_w':>8s}")
for tag, mode, kw in (
        ("no filter", "none", {}),
        ("shipped isotropic", "iso", {}),
        ("UKF best-tail  sl=0.3 sb=2.0 Q=0.005", "ukf",
         dict(sigma_long=0.3, sigma_base=2.0, process_noise=0.005, passthrough_obs=None)),
        ("UKF best-track sl=0.02 sb=0.6 Q=0.3", "ukf",
         dict(sigma_long=0.02, sigma_base=0.6, process_noise=0.3, passthrough_obs=None)),
        ("UKF gated      sl=0.05 sb=1.0 Q=0.02 gate=0.6", "ukf",
         dict(sigma_long=0.05, sigma_base=1.0, process_noise=0.02, passthrough_obs=0.6)),
        ("iso blend driven by OBSERVABILITY 0.15/0.60", "iso_obs", dict(lo=0.15, hi=0.60)),
        ("iso blend driven by OBSERVABILITY 0.40/0.90", "iso_obs", dict(lo=0.40, hi=0.90)),
):
    r = run_clean(mode, **kw)
    tw = "" if mode == "none" and False else f"{r['tw']:7.2f}°"
    print(f"{tag:46s} {r['j30']:5d} {r['j60']:5d} {r['p99']:7.2f} {r['mx']:7.2f} {tw:>8s}")
