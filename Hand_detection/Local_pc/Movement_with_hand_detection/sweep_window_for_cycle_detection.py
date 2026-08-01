import glob
import json
import os

import numpy as np
from scipy.signal import find_peaks

from Resources import classifier, event_layer, features
from train_pinch_classifier import (
    RECORDINGS_DIR, LogisticRegression, TinyMLP, evaluate,
    hand_landmark_sequence, load_sessions, session_duration_s,
    session_level_split,
)

# Follow-up to GESTURE_PIPELINE_SPEC.md §12.4.3's failure analysis: the
# original DELTA_WINDOW_MS sweep (features.py's comment trail) only ever
# validated window size against STATIC held-state data (rotation-FP/recall/
# F1) -- it could not see, by construction, whether a window is too LARGE
# relative to real cyclic transition timing, since held-state data has no
# transitions at all. This sweep retrains raw_plus_handcrafted_plus_
# articulation_plus_delta at each candidate window from scratch (not just
# swapping the window at inference on an already-trained model, which would
# have a real train/inference mismatch) and evaluates BOTH: (a) the
# existing static held-state metric, and (b) a NEW cycle-detection metric --
# ground-truth cycle count (independent, from raw pinch_ratio via find_peaks,
# analyze_transition_window.py's method) vs. detected onsets, per orientation.
#
# Per direction (2026-07-31): front/palmin/palmdown/palmup are the
# orientations that matter for this decision -- palmaway/palmout are
# structurally low-priority (low real-world likelihood of pinching in those
# orientations, and palm_away specifically has a camera-visibility
# constraint on the index/thumb) and are reported separately, not folded
# into the primary score.

WINDOW_SIZES_MS = [100, 150, 200, 300, 450, 600, 900]
PRIORITY_ORIENTATIONS = {"front", "palmin", "palmdown", "palmup"}
BEST_EVENT_PARAMS = dict(
    window_frames=8, onset_conf_rise=0.20, onset_ratio_fall=0.12,
    offset_conf_fall=0.20, offset_ratio_rise=0.08,
)


def build_examples(session_list, window_ms):
    examples = []
    for (base_class, orientation), path, data in session_list:
        y = 1 if base_class == "pinch" else 0
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            seq = hand_landmark_sequence(data, handedness)
            if len(seq) < 3:
                continue
            fps = len(seq) / duration_s
            window_frames = max(1, round(fps * window_ms / 1000))
            for i in range(2 * window_frames, len(seq)):
                now, t1 = seq[i], seq[i - window_frames]
                x = features.extract_raw_plus_handcrafted_plus_articulation_plus_delta_features(
                    t1, now, handedness=handedness
                )
                examples.append((x, y, {"base_class": base_class, "orientation": orientation, "handedness": handedness}))
    return examples


def rotation_stress_test_window(model_json, window_ms):
    pcts = []
    for path in sorted(glob.glob(os.path.join(RECORDINGS_DIR, "rotating_no_pinch_*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            seq = hand_landmark_sequence(data, handedness)
            if len(seq) < 3:
                continue
            fps = len(seq) / duration_s
            window_frames = max(1, round(fps * window_ms / 1000))
            confs = []
            for i in range(window_frames, len(seq)):
                now, t1 = seq[i], seq[i - window_frames]
                x = features.extract_raw_plus_handcrafted_plus_articulation_plus_delta_features(
                    t1, now, handedness=handedness
                )
                confs.append(classifier.predict_from_features(model_json, x))
            pcts.append(100.0 * float(np.mean(np.array(confs) > 0.5)))
    return float(np.mean(pcts)) if pcts else float("nan")


def ground_truth_cycle_count(ratio_seq):
    ratio = np.array(ratio_seq)
    if len(ratio) < 5:
        return 0
    minima, _ = find_peaks(-ratio, prominence=0.2)
    return len(minima)


def cycle_detection_recall(model_json, window_ms):
    """Returns (recall over PRIORITY_ORIENTATIONS, recall over all
    orientations, per-orientation dict of (gt_total, detected_total))."""
    files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_cycles_*.json")))
    by_orient = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        orientation = data["label"][len("pinch_cycles_"):]
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            lm_seq = hand_landmark_sequence(data, handedness)
            if len(lm_seq) < 3:
                continue
            ratio_seq = [features.pinch_ratio(lm) for lm in lm_seq]
            gt = ground_truth_cycle_count(ratio_seq)

            fps = len(lm_seq) / duration_s
            window_frames = max(1, round(fps * window_ms / 1000))
            tracker = event_layer.PinchEventTracker(**BEST_EVENT_PARAMS)
            onsets = 0
            for i in range(window_frames, len(lm_seq)):
                now, past = lm_seq[i], lm_seq[i - window_frames]
                x = features.extract_raw_plus_handcrafted_plus_articulation_plus_delta_features(
                    past, now, handedness=handedness
                )
                conf = classifier.predict_from_features(model_json, x)
                ratio = features.pinch_ratio(now)
                _, onset_event, _ = tracker.update(conf, ratio)
                onsets += onset_event

            gt_total, det_total = by_orient.get(orientation, (0, 0))
            by_orient[orientation] = (gt_total + gt, det_total + onsets)

    priority_gt = sum(v[0] for k, v in by_orient.items() if k in PRIORITY_ORIENTATIONS)
    priority_det = sum(v[1] for k, v in by_orient.items() if k in PRIORITY_ORIENTATIONS)
    all_gt = sum(v[0] for v in by_orient.values())
    all_det = sum(v[1] for v in by_orient.values())
    priority_recall = priority_det / priority_gt if priority_gt else float("nan")
    all_recall = all_det / all_gt if all_gt else float("nan")
    return priority_recall, all_recall, by_orient


def main():
    cells = load_sessions()
    train_sessions, test_sessions = session_level_split(cells)
    print(f"train sessions: {len(train_sessions)}, test sessions: {len(test_sessions)}\n")

    results = []
    for window_ms in WINDOW_SIZES_MS:
        train_ex = build_examples(train_sessions, window_ms)
        test_ex = build_examples(test_sessions, window_ms)
        X_train = [ex[0] for ex in train_ex]
        y_train = [ex[1] for ex in train_ex]
        X_test = [ex[0] for ex in test_ex]
        y_test = [ex[1] for ex in test_ex]

        model = TinyMLP(n_features=len(X_train[0]), hidden_units=24)
        model.fit(X_train, y_train, l2=0.001)
        test_report = evaluate(model, X_test, y_test, [ex[2] for ex in test_ex], f"{window_ms}ms/test")
        model_json = model.to_json(
            features.RAW_PLUS_HANDCRAFTED_PLUS_ARTICULATION_PLUS_DELTA_FEATURE_NAMES,
            "raw_plus_handcrafted_plus_articulation_plus_delta",
        )
        rotation_fp = rotation_stress_test_window(model_json, window_ms)
        priority_recall, all_recall, by_orient = cycle_detection_recall(model_json, window_ms)

        print(f"--- window={window_ms}ms: static test f1={test_report['f1']:.3f} "
              f"recall={test_report['recall']:.3f} rotation_fp={rotation_fp:.1f}% | "
              f"cycle-detection recall (priority orient.)={priority_recall:.2%} (all)={all_recall:.2%} ---")
        for orient, (gt, det) in sorted(by_orient.items()):
            tag = "priority" if orient in PRIORITY_ORIENTATIONS else "low-priority"
            print(f"    {orient:10s} ({tag:12s}) gt={gt:3d} detected={det:3d} recall={det/gt if gt else float('nan'):.2%}")

        results.append({
            "window_ms": window_ms, "f1": test_report["f1"], "recall": test_report["recall"],
            "rotation_fp": rotation_fp, "priority_cycle_recall": priority_recall,
            "all_cycle_recall": all_recall,
        })

    print("\n=== Summary, sorted by priority-orientation cycle-detection recall ===")
    for r in sorted(results, key=lambda r: -r["priority_cycle_recall"]):
        print(f"  window={r['window_ms']:4d}ms static_f1={r['f1']:.3f} static_recall={r['recall']:.3f} "
              f"rotation_fp={r['rotation_fp']:5.1f}% priority_cycle_recall={r['priority_cycle_recall']:.2%} "
              f"all_cycle_recall={r['all_cycle_recall']:.2%}")


if __name__ == "__main__":
    main()
