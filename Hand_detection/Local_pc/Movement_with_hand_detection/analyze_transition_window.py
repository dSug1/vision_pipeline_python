import glob
import json
import os

import numpy as np
from scipy.signal import find_peaks

from Resources import features

# Stage 3 redesign (2026-07-31): before building windowed/derivative
# features into the base classifier, measure how long a real onset
# (open->pinch) and offset (pinch->open) transition actually takes in the
# pinch_cycles recordings -- empirically, not guessed, matching this
# project's discipline throughout. Drives the window size used by
# features.py's new windowed-feature extraction.

RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline"
PINCH_CYCLES_DURATION_S = 10.0  # every pinch_cycles_* session was recorded
# with --duration 10 -- used to convert frame counts to real time, since
# actual capture fps varies with hardware load (seen ~15fps near-distance
# vs ~27fps far-distance sessions, not a fixed 30fps).


def hand_ratio_sequence(path, handedness):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    seq = []
    for frame in data["frames"]:
        for hand in frame["hands"]:
            if hand["handedness"] == handedness:
                seq.append(features.pinch_ratio(hand["world_landmarks"]))
                break
    return seq


def transition_durations_ms(ratio_seq, fps):
    """Returns (onset_durations_ms, offset_durations_ms) -- onset = a
    local max (open) followed by the next local min (pinched); offset =
    a local min followed by the next local max."""
    ratio = np.array(ratio_seq)
    if len(ratio) < 5:
        return [], []
    # prominence filters out tiny wobbles that aren't real open/close
    # cycles -- 0.2 chosen empirically (swept 0.08-0.3, picked the value
    # giving ~6 extrema/session, matching the "repeated ~3 times" recording
    # protocol's 3 open<->pinch cycles = 3 maxima + 3 minima)
    prominence = 0.2
    maxima, _ = find_peaks(ratio, prominence=prominence)
    minima, _ = find_peaks(-ratio, prominence=prominence)
    extrema = sorted([(i, "max") for i in maxima] + [(i, "min") for i in minima])

    onset_ms, offset_ms = [], []
    for (i1, k1), (i2, k2) in zip(extrema, extrema[1:]):
        duration_ms = (i2 - i1) / fps * 1000.0
        if k1 == "max" and k2 == "min":
            onset_ms.append(duration_ms)
        elif k1 == "min" and k2 == "max":
            offset_ms.append(duration_ms)
    return onset_ms, offset_ms


def main():
    files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "pinch_cycles_*.json")))
    all_onset, all_offset = [], []
    near_onset, near_offset, far_onset, far_offset = [], [], [], []

    for path in files:
        is_far = "20260731" in os.path.basename(path)
        for handedness in ("Left", "Right"):
            seq = hand_ratio_sequence(path, handedness)
            if not seq:
                continue
            fps = len(seq) / PINCH_CYCLES_DURATION_S
            onset_ms, offset_ms = transition_durations_ms(seq, fps)
            all_onset.extend(onset_ms)
            all_offset.extend(offset_ms)
            (far_onset if is_far else near_onset).extend(onset_ms)
            (far_offset if is_far else near_offset).extend(offset_ms)

    def report(name, vals):
        if not vals:
            print(f"{name}: no data")
            return
        v = np.array(vals)
        print(f"{name}: n={len(v)} min={v.min():.0f}ms p25={np.percentile(v,25):.0f}ms "
              f"median={np.median(v):.0f}ms p75={np.percentile(v,75):.0f}ms max={v.max():.0f}ms")

    print("=== Onset (open -> pinch) duration ===")
    report("all", all_onset)
    report("near-distance", near_onset)
    report("far-distance", far_onset)

    print("\n=== Offset (pinch -> open) duration ===")
    report("all", all_offset)
    report("near-distance", near_offset)
    report("far-distance", far_offset)


if __name__ == "__main__":
    main()
