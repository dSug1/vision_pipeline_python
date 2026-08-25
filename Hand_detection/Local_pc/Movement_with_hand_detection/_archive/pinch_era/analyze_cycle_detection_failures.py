import glob
import json
import os

import numpy as np
from scipy.signal import find_peaks

from Resources import event_layer, features
from train_pinch_classifier import hand_landmark_sequence
from tune_event_layer import hand_sequence

# Systematic failure analysis (2026-07-31, GESTURE_PIPELINE_SPEC.md §12.4.3):
# neither a 405-point threshold/window sweep nor a targeted feature fix
# (delta_pinch_ratio added to the articulation representation) closed the
# event-layer sensitivity gap in aggregate, and the "recording cadence"
# theory was independently disproven (direct landmark inspection + a fixed
# duration-measurement bug, see analyze_transition_window.py's history
# comment). Rather than guess a third explanation, this computes an
# independent GROUND-TRUTH cycle count per session directly from raw
# pinch_ratio (the same find_peaks method analyze_transition_window.py
# uses, not the classifier's own confidence signal), and compares it
# against what the event tracker actually detects -- broken down by
# orientation and hand -- to find where and how detection actually fails,
# rather than assuming a single cause.

RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Pencil_style_grip"
BEST_PARAMS = dict(
    window_frames=8, onset_conf_rise=0.20, onset_ratio_fall=0.12,
    offset_conf_fall=0.20, offset_ratio_rise=0.08,
)


def ground_truth_cycle_count(ratio_seq):
    """Independent of the classifier entirely -- counts real open->pinch
    dips directly from pinch_ratio via the same prominence-filtered
    find_peaks method analyze_transition_window.py uses (prominence=0.2,
    tuned to match the ~3-cycle recording protocol)."""
    ratio = np.array(ratio_seq)
    if len(ratio) < 5:
        return 0
    minima, _ = find_peaks(-ratio, prominence=0.2)
    return len(minima)


def orientation_of(label):
    prefix = "pinch_cycles_"
    return label[len(prefix):] if label.startswith(prefix) else label


def main():
    files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_cycles_*.json")))
    rows = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        orientation = orientation_of(data["label"])
        for handedness in ("Left", "Right"):
            lm_seq = hand_landmark_sequence(data, handedness)
            if len(lm_seq) < 3:
                continue
            ratio_seq = [features.pinch_ratio(lm) for lm in lm_seq]
            gt = ground_truth_cycle_count(ratio_seq)

            conf_ratio_seq = hand_sequence(path, handedness)
            tracker = event_layer.PinchEventTracker(**BEST_PARAMS)
            onsets = offsets = 0
            for conf, ratio in conf_ratio_seq:
                _, onset_event, offset_event = tracker.update(conf, ratio)
                onsets += onset_event
                offsets += offset_event

            rows.append({
                "file": os.path.basename(path), "orientation": orientation,
                "handedness": handedness, "ground_truth": gt,
                "detected_onsets": onsets, "detected_offsets": offsets,
                "missed": gt - onsets,
            })

    print(f"{'file':40s} {'hand':6s} {'orient':10s} {'gt':>3s} {'det_on':>7s} {'det_off':>8s} {'missed':>7s}")
    for r in rows:
        print(f"{r['file']:40s} {r['handedness']:6s} {r['orientation']:10s} "
              f"{r['ground_truth']:>3d} {r['detected_onsets']:>7d} {r['detected_offsets']:>8d} {r['missed']:>7d}")

    print("\n=== Aggregate by orientation ===")
    by_orient = {}
    for r in rows:
        by_orient.setdefault(r["orientation"], []).append(r)
    for orient, rs in sorted(by_orient.items()):
        gt_mean = np.mean([r["ground_truth"] for r in rs])
        det_mean = np.mean([r["detected_onsets"] for r in rs])
        missed_mean = np.mean([r["missed"] for r in rs])
        print(f"  {orient:12s} n={len(rs):3d} ground_truth_mean={gt_mean:.2f} "
              f"detected_mean={det_mean:.2f} missed_mean={missed_mean:.2f}")

    print("\n=== Aggregate by hand ===")
    by_hand = {}
    for r in rows:
        by_hand.setdefault(r["handedness"], []).append(r)
    for hand, rs in sorted(by_hand.items()):
        gt_mean = np.mean([r["ground_truth"] for r in rs])
        det_mean = np.mean([r["detected_onsets"] for r in rs])
        print(f"  {hand:8s} n={len(rs):3d} ground_truth_mean={gt_mean:.2f} detected_mean={det_mean:.2f}")

    total_gt = sum(r["ground_truth"] for r in rows)
    total_det = sum(r["detected_onsets"] for r in rows)
    print(f"\nTotal ground-truth cycles: {total_gt}, total detected onsets: {total_det} "
          f"({100.0 * total_det / total_gt:.1f}% recall)")


if __name__ == "__main__":
    main()
