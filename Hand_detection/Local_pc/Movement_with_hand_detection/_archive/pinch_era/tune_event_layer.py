import glob
import json
import os

# ⚠ MOVED 2026-08-25 out of the app root. This file's own directory is no
# longer the app root, so every path that used to resolve from `__file__`
# now goes one level up. Behaviour is unchanged; only the anchor moved.
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from Resources import classifier, event_layer, features
from train_pinch_classifier import hand_landmark_sequence, session_duration_s

# Stage 3.3 of Claude/GESTURE_PIPELINE_SPEC.md: tune the onset/offset
# event-detection layer against the pinch_cycles (+ pinch_rotate_release)
# transition recordings -- NOT the held-state sessions, which contain no
# real transitions to tune against (spec §3.3's own rule).

# Pencil-grip corpus reset (2026-07-31) -- must match RecordSession.py/
# train_pinch_classifier.py's RECORDINGS_DIR; old corpus archived under
# .../Unsuccessful_grip/, not read here anymore.
RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Pencil_style_grip"
WEIGHTS_PATH = os.path.join(
    _APP_ROOT, "Resources", "pinch_classifier_weights.json"
)
MODEL = classifier.load(WEIGHTS_PATH)

# Windowed representations (need a past + now landmark pair, per the same
# fps-derived window_frames math train_pinch_classifier.py uses) vs. static
# ones (single snapshot, classifier.predict_from_landmarks handles them
# directly). Kept as an explicit set rather than a static/windowed flag on
# the model JSON itself -- cheap to extend when a new representation is
# added, and fails loudly (KeyError-free explicit branch) instead of
# silently mis-predicting if a representation is missing from both paths.
WINDOWED_REPRESENTATIONS = {
    "raw_plus_handcrafted_plus_articulation",
    "raw_plus_handcrafted_plus_articulation_plus_delta",
}


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
        elif representation == "raw_plus_handcrafted_plus_articulation_plus_delta":
            x = features.extract_raw_plus_handcrafted_plus_articulation_plus_delta_features(
                past, now, handedness=handedness
            )
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


def _check_protocol(path, expected):
    """Defensive check, added 2026-07-31 after finding an archived
    "held-state" pinch_front session actually contained three pinch-release
    dips -- a recording's declared protocol (RecordSession.py's --protocol,
    saved in the JSON) must match what this loop assumes about it, not be
    inferred from the filename alone."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("protocol") != expected:
        raise ValueError(f"{path}: expected protocol={expected!r}, got {data.get('protocol')!r}")


def evaluate(params, verbose=False):
    cycle_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_cycles_*.json")))
    rotate_release_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_rotate_release_*.json")))
    neg_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "rotating_no_pinch_*.json")))
    for path in cycle_files + rotate_release_files:
        _check_protocol(path, "cyclic")
    for path in neg_files:
        _check_protocol(path, "held_state")

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
    # window_frames added to the grid (2026-07-31, pencil-grip corpus,
    # GESTURE_PIPELINE_SPEC.md §12.4's retrain) -- previously always
    # event_layer.DEFAULT_WINDOW_FRAMES (5, ~150-200ms), never itself swept.
    # That's now a live stale-hyperparameter risk of exactly the same shape
    # §3.2.9 found for hidden_units=4: features.DELTA_WINDOW_MS just tripled
    # 300ms->900ms (§12.4), which smooths the classifier's own per-frame
    # confidence signal over a much longer lookback -- the event tracker's
    # OWN derivative-agreement window (a completely separate window over the
    # confidence/ratio sequence, not the same thing as the classifier's
    # input-feature window) was never re-checked against that changed
    # smoothing profile.
    best = None
    all_results = []  # every (params, r) -- lets us inspect the raw
    # cycle-detection/false-positive tradeoff directly afterward, since the
    # scalar `score` below weights false positives heavily (-2 each) and
    # could hide a config that's much closer to the ~3-per-cycle target at
    # the cost of one or two false positives, not just report the single
    # most conservative winner.
    for window_frames in [5, 8, 12, 18, 24]:
        for onset_conf_rise in [0.20, 0.30, 0.40]:
            for onset_ratio_fall in [0.08, 0.12, 0.18]:
                for offset_conf_fall in [0.20, 0.30, 0.40]:
                    for offset_ratio_rise in [0.08, 0.12, 0.18]:
                        params = dict(
                            window_frames=window_frames,
                            onset_conf_rise=onset_conf_rise, onset_ratio_fall=onset_ratio_fall,
                            offset_conf_fall=offset_conf_fall, offset_ratio_rise=offset_ratio_rise,
                        )
                        r = evaluate(params)
                        all_results.append((params, r))
                        # Score: want cycle onset/offset counts near 3
                        # (pinch_x3 cadence) with zero false positives on
                        # rotating_no_pinch.
                        score = (
                            -abs(r["cycle_onset_mean"] - 3) - abs(r["cycle_offset_mean"] - 3)
                            - 2 * r["neg_onset_total"] - 2 * r["neg_offset_total"]
                        )
                        if best is None or score > best[0]:
                            best = (score, params, r)

    score, params, r = best
    print("Best params (FP-penalized score):", params)
    print("Results:", r)
    print("\n--- verbose run of best params ---")
    evaluate(params, verbose=True)

    print("\n--- Top 10 by raw cycle-detection closeness to 3, ignoring the FP penalty ---")

    def _raw_cycle_score(item):
        _, res = item
        return abs(res["cycle_onset_mean"] - 3) + abs(res["cycle_offset_mean"] - 3)

    for p, res in sorted(all_results, key=_raw_cycle_score)[:10]:
        print(
            f"  window_frames={p['window_frames']:2d} onset_conf_rise={p['onset_conf_rise']:.2f} "
            f"onset_ratio_fall={p['onset_ratio_fall']:.2f} offset_conf_fall={p['offset_conf_fall']:.2f} "
            f"offset_ratio_rise={p['offset_ratio_rise']:.2f} -> cycle_onset={res['cycle_onset_mean']:.2f} "
            f"cycle_offset={res['cycle_offset_mean']:.2f} neg_onset_total={res['neg_onset_total']} "
            f"neg_offset_total={res['neg_offset_total']}"
        )


if __name__ == "__main__":
    main()
