"""Analyse the scripted perception sequences (merged queue item 0.2b).

Reads sessions written by `RecordPerceptionSequence.py` and computes the M0
metrics that CANNOT be obtained from the older grab-and-rotate recordings,
plus the measurement that decides `EDGE_ON_THRESHOLD`.

Per sequence:
  static_hold       -> resting jitter (hand frame), palm-normal jitter, bone CV
  non_crossing      -> chirality flip rate. The hand never turns palm-to-back
                       here BY CONSTRUCTION, so every sign flip is spurious.
                       This is the measurement DR-2's threshold rests on.
  pitch_sweep_*     -> crossing survival: how the sign behaves through a
                       deliberate edge-on crossing, and how wide the
                       low-conditioning band actually is in practice.

Read-only. Imports no gesture logic; recomputes everything from raw landmarks.
"""

import glob
import json
import math
import os
import time

import numpy as np

ROOTS = [
    r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "perception_recordings", "sessions"),
]

PALM = [0, 5, 9, 13, 17]
BONES = [
    (0, 1), (0, 5), (0, 17), (5, 9), (9, 13), (13, 17),
    (1, 2), (2, 3), (3, 4), (5, 6), (6, 7), (7, 8),
    (9, 10), (10, 11), (11, 12), (13, 14), (14, 15), (15, 16),
    (17, 18), (18, 19), (19, 20),
]


def _retry(fn, attempts=5, delay=1.5):
    """The external capture drive drops out intermittently (observed repeatedly
    2026-08-02: the same read failing then succeeding seconds later). Retry
    rather than silently skipping a session -- a skipped session looks exactly
    like a session that was never recorded, which is the dangerous failure."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except OSError as e:
            last = e
            if i < attempts - 1:
                time.sleep(delay)
    raise last


def load_session(d):
    def _read():
        with open(os.path.join(d, "meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
        frames = []
        with open(os.path.join(d, "raw_landmarks.jsonl"), "r", encoding="utf-8") as f:
            for line in f:
                frames.append(json.loads(line))
        return meta, frames
    return _retry(_read)


def per_hand_stream(frames, handedness):
    """(frame_index, record) for frames where this handedness label appears."""
    for i, fr in enumerate(frames):
        for h in fr["hands"]:
            if h["handedness"] == handedness:
                yield i, h
                break


def kabsch(P, Q):
    H = P.T @ Q
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    return Vt.T @ np.diag([1.0, 1.0, d]) @ U.T


def edge_on(landmarks):
    p0, p5, p17 = (np.asarray(landmarks[i], float) for i in (0, 5, 17))
    v1, v2 = p5 - p0, p17 - p0
    s = v1[0] * v2[1] - v1[1] * v2[0]
    den = np.linalg.norm(v1) * np.linalg.norm(v2)
    return s, (abs(s) / den if den > 1e-9 else 0.0)


def palm_normal(world):
    P = np.asarray([world[i] for i in PALM], float)
    P -= P.mean(axis=0)
    return np.linalg.svd(P)[2][2]


def analyse(d):
    meta, frames = load_session(d)
    seq = meta["sequence"]
    print("=" * 78)
    print(f"{seq}   ({meta['frames']} frames, {meta['measured_fps']} fps, "
          f"{meta['actual_span_s']}s)")
    print("=" * 78)

    for handedness in ("Left", "Right"):
        stream = list(per_hand_stream(frames, handedness))
        if len(stream) < 30:
            continue
        idxs = [i for i, _ in stream]
        world = [np.asarray(h["world_landmarks"], float) for _, h in stream]
        pix = [h["landmarks"] for _, h in stream]

        eos, signs = [], []
        for p in pix:
            s, eo = edge_on(p)
            eos.append(eo)
            signs.append(1 if s > 0 else -1)
        eos = np.asarray(eos)

        # ---- bone CV ----
        B = np.vstack([[np.linalg.norm(w[b] - w[a]) for a, b in BONES] for w in world])
        cv = B.std(axis=0) / np.maximum(B.mean(axis=0), 1e-9)

        # ---- resting jitter in the HAND FRAME ----
        # Procrustes-align each frame's palm to a reference, apply the same
        # transform to all 21 points, then measure per-landmark scatter. This
        # removes bulk hand motion, which is what "hand frame" means here.
        ref = world[0][PALM] - world[0][PALM].mean(axis=0)
        aligned = []
        for w in world:
            pc = w[PALM] - w[PALM].mean(axis=0)
            R = kabsch(pc, ref)
            aligned.append((R @ (w - w[PALM].mean(axis=0)).T).T)
        A = np.stack(aligned)                       # frames x 21 x 3
        jitter_mm = A.std(axis=0).mean(axis=1) * 1000.0   # per-landmark, mm

        # ---- palm-normal jitter ----
        normals = [palm_normal(w) for w in world]
        ang = []
        for k in range(1, len(normals)):
            if idxs[k] != idxs[k - 1] + 1:
                continue
            c = float(np.clip(abs(np.dot(normals[k], normals[k - 1])), -1, 1))
            ang.append(math.degrees(math.acos(c)))

        # ---- sign flips ----
        flips = []
        for k in range(1, len(signs)):
            if idxs[k] != idxs[k - 1] + 1:
                continue
            if signs[k] != signs[k - 1]:
                flips.append(min(eos[k], eos[k - 1]))
        dur_min = meta["actual_span_s"] / 60.0

        print(f"\n  [{handedness}]  frames={len(stream)}")
        print(f"    bone CV            mean {cv.mean()*100:5.2f}%   "
              f"median {np.median(cv)*100:5.2f}%   (target < 3%)")
        print(f"    resting jitter     mean {jitter_mm.mean():5.2f} mm  "
              f"palm-only {jitter_mm[PALM].mean():5.2f} mm  "
              f"fingertips {jitter_mm[[4,8,12,16,20]].mean():5.2f} mm   (target < 1.5 mm)")
        if ang:
            print(f"    palm-normal jitter mean {np.mean(ang):5.2f}°   "
                  f"p95 {np.percentile(ang,95):5.2f}°   (target < 1.5°)")
        print(f"    edge-on measure    mean {eos.mean():5.3f}   min {eos.min():5.3f}   "
              f"frac<0.15 {np.mean(eos<0.15)*100:4.1f}%   frac<0.60 {np.mean(eos<0.60)*100:4.1f}%")
        print(f"    sign flips         {len(flips)}  ({len(flips)/dur_min:.1f}/min)", end="")
        if flips:
            print("   at edge-on: " + ", ".join(f"{v:.3f}" for v in sorted(flips)))
        else:
            print()

        if seq == "non_crossing" and flips:
            print(f"    ** {len(flips)} SPURIOUS flips (hand never crossed) **")
            above = [f for f in flips if f >= 0.15]
            print(f"       {len(above)} of them at edge-on >= 0.15 "
                  f"(i.e. NOT caught by the proposed threshold)")
            if above:
                print(f"       highest spurious flip at edge-on = {max(above):.3f}")


def main():
    dirs = []
    for root in ROOTS:
        dirs.extend(sorted(glob.glob(os.path.join(root, "*"))))
    dirs = [d for d in dirs if _retry(lambda d=d: os.path.isfile(os.path.join(d, "meta.json")))]
    if not dirs:
        print("[sequences] No sessions found. Record some with "
              "record_perception_sequence.bat first.")
        return
    for d in dirs:
        analyse(d)


if __name__ == "__main__":
    main()
