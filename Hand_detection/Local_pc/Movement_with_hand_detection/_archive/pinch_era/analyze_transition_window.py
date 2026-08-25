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

# Pencil-grip corpus reset (2026-07-31) -- old corpus archived under
# .../Unsuccessful_grip/; must match RecordSession.py's RECORDINGS_DIR.
RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Pencil_style_grip"
# BUG FOUND AND FIXED (2026-07-31, same session): this used to be a
# hardcoded PINCH_CYCLES_DURATION_S = 10.0, a leftover assumption from the
# ARCHIVED corpus's 10s cyclic recordings. The pencil-grip corpus's
# pinch_cycles_* sessions are actually 5.0s ("duration_s" in each file,
# RecordSession.py's uniform-5s direction) -- the hardcoded 10.0 silently
# computed fps at HALF its true value, which doubled every reported
# transition duration below. This is exactly why an earlier analysis this
# session reported a false "median onset 1165ms" (real value ~half that) and
# fed a wrong root-cause conclusion (recording cadence) that direct
# landmark inspection then disproved -- always read duration from the
# recording's own data, never a separately-maintained assumed constant.


def hand_ratio_sequence(path, handedness):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    seq = []
    for frame in data["frames"]:
        for hand in frame["hands"]:
            if hand["handedness"] == handedness:
                seq.append(features.pinch_ratio(hand["world_landmarks"]))
                break
    return seq, data["duration_s"]


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
    for path in files:
        with open(path, encoding="utf-8") as f:
            protocol = json.load(f).get("protocol")
        if protocol != "cyclic":
            raise ValueError(f"{path}: expected protocol='cyclic', got {protocol!r}")

    all_onset, all_offset = [], []
    near_onset, near_offset, far_onset, far_offset = [], [], [], []

    for path in files:
        is_far = "20260731" in os.path.basename(path)
        for handedness in ("Left", "Right"):
            seq, duration_s = hand_ratio_sequence(path, handedness)
            if not seq:
                continue
            fps = len(seq) / duration_s
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
