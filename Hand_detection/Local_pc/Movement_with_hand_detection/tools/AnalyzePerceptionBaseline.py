"""M0 baseline metrics on ALREADY-RECORDED sessions (merged build queue item 0.2).

Claude/PERCEPTION_LAYER_SPEC.md M0 defines a set of ground-truth-free,
self-supervised metrics for the hand-perception stack. This script computes the
subset of them that is obtainable from the recordings this project already has
(`RecordTranslationPivotDebug.py` sessions), WITHOUT any new capture -- so the
kill-criterion in that spec (A10: every module must show a measured improvement
or be reverted) has baseline numbers to be judged against.

It is read-only: it imports nothing from the live pipeline, opens no camera, and
changes no production code.

WHAT IT COMPUTES (from `world_landmarks` and `pixel_landmarks`):
  * Bone-length CV        -- bones are rigid; variance is estimator error (M0)
  * Palm rigidity residual-- RMS of the 5 palm points vs. a Procrustes-fitted
                             mean palm shape, isolating palm-frame error (M0)
  * Palm-normal change    -- frame-to-frame palm-normal angle; on LOW-MOTION
                             frames this approximates the spec's palm-normal
                             jitter (see the caveat below)
  * Hand-position jump    -- frame-to-frame motion of the tracked anchor, and
                             the >100 px discontinuity rate (the Object Jump
                             Correction metric, spec M0 as amended)
  * ** Chirality flips vs. edge-on measure ** -- the hypothesis test, see below

WHAT IT CANNOT COMPUTE, and why (needs the scripted sequences in spec §7.2):
  * Resting jitter, palm-normal jitter proper -- require the hand held STILL.
    These recordings are all grab-and-rotate sessions. Low-motion frames are
    reported as an approximation and labelled as such; they are NOT the spec's
    metric and must not be quoted as if they were.
  * Crossing survival  -- requires scripted +/-120 deg sweeps.
  * Reacquisition time -- requires deliberate in/out-of-frame events.

THE HYPOTHESIS TEST (the reason to run this before building anything):
M5's entire design rests on the claim that the palm/back sign is reliable
everywhere EXCEPT where the palm is edge-on to the camera (|s| -> 0), and that
this is the only place temporal machinery (DR-2) is needed. That is checkable
against data already on disk: compute the edge-on measure per frame, then see
whether the recorded `thumb_outward` sign flips actually concentrate at low
values. If they do, DR-2 is validated. If flips are spread evenly across the
range, M5's story is wrong and Phase 2 needs rethinking before it is built.
"""

import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Position_during_rotation"
METRICS_OUT_DIR = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\metrics"

TRACKED_HANDS = ("Left", "Right")
WRIST = 0
PALM_LANDMARKS = [0, 5, 9, 13, 17]

# 21 edges over the standard MediaPipe hand topology: 6 palm/carpal + 15
# phalangeal. The spec says "20 bones"; the exact count depends on whether the
# redundant 0-17 closing edge is included. Reported per-bone, so the count
# itself is not load-bearing.
BONES = [
    (0, 1), (0, 5), (0, 17), (5, 9), (9, 13), (13, 17),      # palm / carpal
    (1, 2), (2, 3), (3, 4),                                   # thumb
    (5, 6), (6, 7), (7, 8),                                   # index
    (9, 10), (10, 11), (11, 12),                              # middle
    (13, 14), (14, 15), (15, 16),                             # ring
    (17, 18), (18, 19), (19, 20),                             # pinky
]
BONE_NAMES = [f"{a}-{b}" for a, b in BONES]

# Frames whose anchor moved less than this (px) are treated as "low motion" and
# used as a rough stand-in for the spec's hand-held-still metrics.
LOW_MOTION_PX = 2.0
# Object Jump Correction threshold (spec M0, added on integration).
JUMP_PX = 100.0


def _hands_frames(frames, handedness):
    """Yields (frame_index, hand_record) for frames where this hand is detected."""
    for i, f in enumerate(frames):
        hand = f["hands"].get(handedness, {"detected": False})
        if hand.get("detected"):
            yield i, hand


def _bone_lengths(world):
    w = np.asarray(world, dtype=float)
    return np.array([np.linalg.norm(w[b] - w[a]) for a, b in BONES])


def _kabsch(P, Q):
    """Rotation aligning centred P onto centred Q (both N x 3)."""
    H = P.T @ Q
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    return Vt.T @ D @ U.T


def _palm_rigidity_residual_mm(palms):
    """Generalised-Procrustes RMS residual of the palm points, in mm.

    `palms` is a list of 5x3 arrays (world landmarks, metres). Returns the
    per-frame RMS residual against the iteratively-refined mean palm shape.
    """
    if len(palms) < 3:
        return None
    centred = [p - p.mean(axis=0) for p in palms]
    ref = centred[0].copy()
    for _ in range(3):  # converges fast; 3 passes is ample for 5 points
        aligned = []
        for c in centred:
            R = _kabsch(c, ref)
            aligned.append((R @ c.T).T)
        ref = np.mean(aligned, axis=0)
    residuals = []
    for c in centred:
        R = _kabsch(c, ref)
        a = (R @ c.T).T
        residuals.append(np.sqrt(np.mean(np.sum((a - ref) ** 2, axis=1))))
    return np.array(residuals) * 1000.0  # m -> mm


def _palm_normal(world):
    """Palm normal via SVD over the 5 rigid palm landmarks (spec M6b)."""
    P = np.asarray([world[i] for i in PALM_LANDMARKS], dtype=float)
    P = P - P.mean(axis=0)
    _, _, Vt = np.linalg.svd(P)
    return Vt[2]


def _edge_on_measure(pixel):
    """Scale-free edge-on measure from the signed palm area (spec M5a).

    s = (p5-p0) x (p17-p0) in image coords -- the exact quantity
    `_is_thumb_outward` already computes. Normalising by |v1||v2| yields
    |sin(angle)| in [0,1]: 1 = palm square to the camera (best conditioned),
    0 = palm edge-on (sign unobservable). Scale-free, so no M2 calibration is
    needed to compute it retroactively.
    """
    p0 = np.asarray(pixel[0], dtype=float)
    p5 = np.asarray(pixel[5], dtype=float)
    p17 = np.asarray(pixel[17], dtype=float)
    v1, v2 = p5 - p0, p17 - p0
    s = v1[0] * v2[1] - v1[1] * v2[0]
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-9:
        return s, 0.0
    return s, abs(s) / denom


def _hand_anchor(pixel):
    """The tracked hand position (wrist + 4 non-thumb MCP centroid)."""
    pts = np.asarray([pixel[i] for i in PALM_LANDMARKS], dtype=float)
    return pts.mean(axis=0)


def analyse_session(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    frames = data["frames"]
    label = data.get("label", os.path.basename(path))

    out = {"file": os.path.basename(path), "label": label, "frames": len(frames), "hands": {}}

    for handedness in TRACKED_HANDS:
        recs = list(_hands_frames(frames, handedness))
        if len(recs) < 10:
            continue

        bone_rows, palms, normals, anchors, idxs, edge_ons, signs, thumb_out = [], [], [], [], [], [], [], []
        for i, hand in recs:
            world = hand["world_landmarks"]
            pixel = hand["pixel_landmarks"]
            bone_rows.append(_bone_lengths(world))
            palms.append(np.asarray([world[j] for j in PALM_LANDMARKS], dtype=float))
            normals.append(_palm_normal(world))
            anchors.append(_hand_anchor(pixel))
            s, eo = _edge_on_measure(pixel)
            edge_ons.append(eo)
            signs.append(1 if s > 0 else -1)
            thumb_out.append(bool(hand.get("thumb_outward")))
            idxs.append(i)

        B = np.vstack(bone_rows)
        cv = B.std(axis=0) / np.maximum(B.mean(axis=0), 1e-9)

        rig = _palm_rigidity_residual_mm(palms)

        # frame-to-frame palm-normal angle change (contiguous frames only)
        normal_deltas, anchor_deltas, low_motion_normal = [], [], []
        for k in range(1, len(idxs)):
            if idxs[k] != idxs[k - 1] + 1:
                continue  # skip across a tracking gap
            d = float(np.clip(np.dot(normals[k], normals[k - 1]), -1.0, 1.0))
            ang = math.degrees(math.acos(abs(d)))  # abs(): normal sign is not the subject here
            move = float(np.linalg.norm(anchors[k] - anchors[k - 1]))
            normal_deltas.append(ang)
            anchor_deltas.append(move)
            if move < LOW_MOTION_PX:
                low_motion_normal.append(ang)

        # --- the hypothesis test: do sign flips concentrate at low edge-on? ---
        flips = []  # (edge_on at the flip, using the smaller of the two frames)
        for k in range(1, len(idxs)):
            if idxs[k] != idxs[k - 1] + 1:
                continue
            if thumb_out[k] != thumb_out[k - 1]:
                flips.append(min(edge_ons[k], edge_ons[k - 1]))

        held_frames = sum(1 for _, h in recs if h.get("held_cube"))

        out["hands"][handedness] = {
            "detected_frames": len(recs),
            "held_frames": held_frames,
            "bone_cv_mean_pct": float(cv.mean() * 100),
            "bone_cv_median_pct": float(np.median(cv) * 100),
            "bone_cv_worst_pct": float(cv.max() * 100),
            "bone_cv_worst_bone": BONE_NAMES[int(cv.argmax())],
            "palm_rigidity_rms_mm": float(np.mean(rig)) if rig is not None else None,
            "palm_rigidity_p95_mm": float(np.percentile(rig, 95)) if rig is not None else None,
            "palm_normal_delta_mean_deg": float(np.mean(normal_deltas)) if normal_deltas else None,
            "palm_normal_lowmotion_mean_deg": float(np.mean(low_motion_normal)) if low_motion_normal else None,
            "palm_normal_lowmotion_n": len(low_motion_normal),
            "anchor_delta_mean_px": float(np.mean(anchor_deltas)) if anchor_deltas else None,
            "anchor_jumps_over_100px": int(sum(1 for d in anchor_deltas if d > JUMP_PX)),
            "anchor_delta_max_px": float(max(anchor_deltas)) if anchor_deltas else None,
            "edge_on_mean": float(np.mean(edge_ons)),
            "edge_on_min": float(np.min(edge_ons)),
            "frac_frames_below_0_15": float(np.mean(np.asarray(edge_ons) < 0.15)),
            "sign_flips": len(flips),
            "flip_edge_on_values": [round(f, 4) for f in flips],
            "_edge_ons": edge_ons,      # kept for the aggregate bucket table
            "_flips": flips,
        }
    return out


def main():
    paths = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.json")))
    if not paths:
        print(f"[baseline] No recordings in {RECORDINGS_DIR}")
        return

    results = [analyse_session(p) for p in paths]

    print("=" * 78)
    print("M0 BASELINE — current pipeline, computed on existing recordings")
    print(f"({len(paths)} sessions, no new capture)")
    print("=" * 78)

    print("\n--- Bone-length CV (spec target < 3%) ---")
    print(f"{'session':<22} {'hand':<6} {'mean%':>7} {'median%':>8} {'worst%':>7}  worst bone")
    all_cv = []
    for r in results:
        for h, m in r["hands"].items():
            all_cv.append(m["bone_cv_mean_pct"])
            print(f"{r['label'][:22]:<22} {h:<6} {m['bone_cv_mean_pct']:>7.2f} "
                  f"{m['bone_cv_median_pct']:>8.2f} {m['bone_cv_worst_pct']:>7.2f}  {m['bone_cv_worst_bone']}")
    print(f"{'OVERALL MEAN':<22} {'':<6} {np.mean(all_cv):>7.2f}")

    print("\n--- Palm rigidity residual (spec target < 3 mm) ---")
    print(f"{'session':<22} {'hand':<6} {'RMS mm':>8} {'p95 mm':>8}")
    all_rig = []
    for r in results:
        for h, m in r["hands"].items():
            if m["palm_rigidity_rms_mm"] is not None:
                all_rig.append(m["palm_rigidity_rms_mm"])
                print(f"{r['label'][:22]:<22} {h:<6} {m['palm_rigidity_rms_mm']:>8.2f} {m['palm_rigidity_p95_mm']:>8.2f}")
    if all_rig:
        print(f"{'OVERALL MEAN':<22} {'':<6} {np.mean(all_rig):>8.2f}")

    print("\n--- Palm-normal frame-to-frame change (deg) ---")
    print("    NOTE: not the spec's 'palm-normal jitter' — that needs a held-still")
    print("    recording. 'low-motion' column is a rough stand-in only.")
    print(f"{'session':<22} {'hand':<6} {'all':>7} {'low-motion':>11} {'n':>5}")
    for r in results:
        for h, m in r["hands"].items():
            lm = m["palm_normal_lowmotion_mean_deg"]
            print(f"{r['label'][:22]:<22} {h:<6} {m['palm_normal_delta_mean_deg']:>7.2f} "
                  f"{(f'{lm:.2f}' if lm is not None else 'n/a'):>11} {m['palm_normal_lowmotion_n']:>5}")

    print("\n--- Hand-anchor motion / Object Jump Correction (target: 0 jumps) ---")
    print(f"{'session':<22} {'hand':<6} {'mean px':>8} {'max px':>8} {'>100px':>7}")
    total_jumps = 0
    for r in results:
        for h, m in r["hands"].items():
            total_jumps += m["anchor_jumps_over_100px"]
            print(f"{r['label'][:22]:<22} {h:<6} {m['anchor_delta_mean_px']:>8.2f} "
                  f"{m['anchor_delta_max_px']:>8.1f} {m['anchor_jumps_over_100px']:>7}")
    print(f"{'TOTAL >100px jumps':<29} {total_jumps:>25}")

    # ---------------- the hypothesis test ----------------
    print("\n" + "=" * 78)
    print("HYPOTHESIS TEST — do palm/back sign flips concentrate at low edge-on?")
    print("(spec M5/DR-2 assumes YES; this is the claim Phase 2 is built on)")
    print("=" * 78)

    buckets = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.25),
               (0.25, 0.40), (0.40, 0.60), (0.60, 1.01)]
    frame_counts = defaultdict(int)
    flip_counts = defaultdict(int)
    for r in results:
        for _h, m in r["hands"].items():
            for eo in m["_edge_ons"]:
                for b in buckets:
                    if b[0] <= eo < b[1]:
                        frame_counts[b] += 1
                        break
            for fv in m["_flips"]:
                for b in buckets:
                    if b[0] <= fv < b[1]:
                        flip_counts[b] += 1
                        break

    total_flips = sum(flip_counts.values())
    total_frames = sum(frame_counts.values())
    print(f"\n{'edge-on band':<16} {'frames':>8} {'flips':>7} {'flips/1k frames':>17}")
    for b in buckets:
        n, fl = frame_counts[b], flip_counts[b]
        rate = (fl / n * 1000) if n else float("nan")
        marker = "   <-- DR-2 band" if b[1] <= 0.15 else ""
        print(f"[{b[0]:.2f},{b[1]:.2f})     {n:>8} {fl:>7} "
              f"{(f'{rate:.2f}' if n else 'n/a'):>17}{marker}")
    print(f"\ntotal frames analysed: {total_frames}   total sign flips: {total_flips}")

    below = sum(frame_counts[b] for b in buckets if b[1] <= 0.15)
    flips_below = sum(flip_counts[b] for b in buckets if b[1] <= 0.15)
    if total_flips:
        print(f"\nflips occurring inside the proposed DR-2 band (edge-on < 0.15): "
              f"{flips_below}/{total_flips} = {flips_below/total_flips*100:.1f}%")
        print(f"frames inside that band:                                       "
              f"{below}/{total_frames} = {below/total_frames*100:.1f}%")
        if below and total_frames:
            base = below / total_frames
            obs = flips_below / total_flips
            print(f"\n=> flips are {obs/base:.1f}x over-represented in the band "
                  f"(1.0x would mean NO relationship)" if base > 0 else "")
    else:
        print("\nNo sign flips found in any recording — the sign was stable throughout.")

    os.makedirs(METRICS_OUT_DIR, exist_ok=True)
    out_path = os.path.join(METRICS_OUT_DIR, "baseline_current_pipeline.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            slim = {"file": r["file"], "label": r["label"], "frames": r["frames"], "hands": {}}
            for h, m in r["hands"].items():
                slim["hands"][h] = {k: v for k, v in m.items() if not k.startswith("_")}
            f.write(json.dumps(slim) + "\n")
    print(f"\n[baseline] Metrics written to {out_path}")


if __name__ == "__main__":
    main()
