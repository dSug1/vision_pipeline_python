import glob
import json
import os

import numpy as np

from Resources import classifier, event_layer, features
from train_pinch_classifier import hand_landmark_sequence, session_duration_s

# Stage 3.3 of Claude/GESTURE_PIPELINE_SPEC.md: tune the onset/offset
# event-detection layer against the pinch_cycles (+ pinch_rotate_release)
# transition recordings -- NOT the held-state sessions, which contain no
# real transitions to tune against (spec §3.3's own rule).

RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline"
WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Resources", "pinch_classifier_weights.json"
)
MODEL = classifier.load(WEIGHTS_PATH)

# Windowed representations (need a past + now landmark pair, per the same
# fps-derived window_frames math train_pinch_classifier.py uses) vs. static
# ones (single snapshot, classifier.predict_from_landmarks handles them
# directly). Kept as an explicit set rather than a static/windowed flag on
# the model JSON itself -- cheap to extend when a new representation is
# added, and fails loudly (KeyError-free explicit branch) instead of
# silently mis-predicting if a representation is missing from both paths.
WINDOWED_REPRESENTATIONS = {"raw_plus_handcrafted_plus_articulation"}


def hand_sequence(path, handedness):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    representation = MODEL["representation"]
    if representation not in WINDOWED_REPRESENTATIONS:
        seq = []
        for frame in data["frames"]:
            for hand in frame["hands"]:
                if hand["handedness"] == handedness:
                    lm = hand["world_landmarks"]
                    conf = classifier.predict_from_landmarks(MODEL, lm, handedness=handedness)
                    ratio = features.pinch_ratio(lm)
                    seq.append((conf, ratio))
                    break
        return seq

    # Windowed path: same (fps-derived window_frames, warm-up skip) scheme
    # as train_pinch_classifier.sessions_to_windowed_examples, so live/tuning
    # behavior matches what the model was actually trained and evaluated on.
    lm_seq = hand_landmark_sequence(data, handedness)
    if len(lm_seq) < 2:
        return []
    duration_s = session_duration_s(data)
    fps = len(lm_seq) / duration_s
    window_frames = max(1, round(fps * features.DELTA_WINDOW_MS / 1000))
    seq = []
    for i in range(window_frames, len(lm_seq)):
        now, past = lm_seq[i], lm_seq[i - window_frames]
        if representation == "raw_plus_handcrafted_plus_articulation":
            x = features.extract_raw_plus_handcrafted_plus_articulation_features(past, now, handedness=handedness)
        conf = classifier.predict_from_features(MODEL, x)
        ratio = features.pinch_ratio(now)
        seq.append((conf, ratio))
    return seq


def run_tracker(seq, **tracker_kwargs):
    tracker = event_layer.PinchEventTracker(**tracker_kwargs)
    onsets = offsets = 0
    for conf, ratio in seq:
        _, onset_event, offset_event = tracker.update(conf, ratio)
        onsets += onset_event
        offsets += offset_event
    return onsets, offsets


def evaluate(params, verbose=False):
    cycle_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_cycles_*.json")))
    rotate_release_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_rotate_release_*.json")))
    neg_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "rotating_no_pinch_*.json")))

    cycle_onsets, cycle_offsets = [], []
    for path in cycle_files:
        for handedness in ("Left", "Right"):
            seq = hand_sequence(path, handedness)
            if len(seq) <= params.get("window_frames", event_layer.DEFAULT_WINDOW_FRAMES):
                continue
            o, r = run_tracker(seq, **params)
            cycle_onsets.append(o)
            cycle_offsets.append(r)
            if verbose:
                print(f"  {os.path.basename(path)} [{handedness}]: onsets={o} offsets={r}")

    rr_onsets, rr_offsets = [], []
    for path in rotate_release_files:
        for handedness in ("Left", "Right"):
            seq = hand_sequence(path, handedness)
            if len(seq) <= params.get("window_frames", event_layer.DEFAULT_WINDOW_FRAMES):
                continue
            o, r = run_tracker(seq, **params)
            rr_onsets.append(o)
            rr_offsets.append(r)

    neg_onsets, neg_offsets = [], []
    for path in neg_files:
        for handedness in ("Left", "Right"):
            seq = hand_sequence(path, handedness)
            if len(seq) <= params.get("window_frames", event_layer.DEFAULT_WINDOW_FRAMES):
                continue
            o, r = run_tracker(seq, **params)
            neg_onsets.append(o)
            neg_offsets.append(r)

    return {
        "cycle_onset_mean": np.mean(cycle_onsets), "cycle_offset_mean": np.mean(cycle_offsets),
        "cycle_onset_min": np.min(cycle_onsets), "cycle_offset_min": np.min(cycle_offsets),
        "rotate_release_onset_mean": np.mean(rr_onsets), "rotate_release_offset_mean": np.mean(rr_offsets),
        "neg_onset_total": sum(neg_onsets), "neg_offset_total": sum(neg_offsets),
        "neg_n_sessions": len(neg_onsets),
    }


def main():
    print("Sweeping onset/offset thresholds...\n")
    best = None
    for onset_conf_rise in [0.20, 0.30, 0.40]:
        for onset_ratio_fall in [0.08, 0.12, 0.18]:
            for offset_conf_fall in [0.20, 0.30, 0.40]:
                for offset_ratio_rise in [0.08, 0.12, 0.18]:
                    params = dict(
                        onset_conf_rise=onset_conf_rise, onset_ratio_fall=onset_ratio_fall,
                        offset_conf_fall=offset_conf_fall, offset_ratio_rise=offset_ratio_rise,
                    )
                    r = evaluate(params)
                    # Score: want cycle onset/offset counts near 3 (pinch_x3
                    # cadence) with zero false positives on rotating_no_pinch.
                    score = (
                        -abs(r["cycle_onset_mean"] - 3) - abs(r["cycle_offset_mean"] - 3)
                        - 2 * r["neg_onset_total"] - 2 * r["neg_offset_total"]
                    )
                    if best is None or score > best[0]:
                        best = (score, params, r)

    score, params, r = best
    print("Best params:", params)
    print("Results:", r)
    print("\n--- verbose run of best params ---")
    evaluate(params, verbose=True)


if __name__ == "__main__":
    main()
