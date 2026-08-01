import collections

# Stage 3.3 of Claude/GESTURE_PIPELINE_SPEC.md: onset/apex/offset event
# detection on top of the base classifier's continuous per-frame confidence.
# Onset and offset are each confirmed by DERIVATIVE AGREEMENT across two
# signals (confidence rising/falling AND the underlying pinch_ratio
# falling/rising over the same window) -- not a threshold crossing on
# confidence alone, which is exactly the rule-based approach's original
# failure mode (PART_ONE.md §1). Onset and offset get independently tuned
# thresholds (§3.3.1) -- release is not assumed to mirror pinch.

DEFAULT_WINDOW_FRAMES = 8  # re-tuned 2026-08-01, twice: first to 12 against
# the just-fixed classifier (pencil_rest fix + corrected palm_up
# recordings + winner-selection fix), then back to 8 after
# features.DELTA_WINDOW_MS itself moved 900ms->200ms (GESTURE_PIPELINE_SPEC.md
# §12.4.4) on the strength of sweep_window_for_cycle_detection.py's real
# cycle-detection metric -- re-tuning this tracker window is required every
# time the classifier's own input window changes, since a shorter
# DELTA_WINDOW_MS changes how smoothed the per-frame confidence signal is.
# 8 was the best-scoring point across window_frames in {5,8,12,18,24} run
# against the 200ms-window classifier.


class PinchEventTracker:
    """Stateful per-hand tracker. Feed (confidence, pinch_ratio) once per
    frame via update(); read back the current state and whether an onset/
    offset event fired this frame."""

    def __init__(
        self,
        window_frames=DEFAULT_WINDOW_FRAMES,
        # Re-tuned 2026-08-01 against the 200ms-window classifier
        # (tune_event_layer.py's grid search, GESTURE_PIPELINE_SPEC.md
        # §12.4.4) -- near-zero false positives (1 across 40 held-out
        # hand-sessions, up from a perfect 0 at the 900ms-window classifier,
        # the expected robustness cost of shortening DELTA_WINDOW_MS).
        onset_conf_rise=0.20,
        onset_ratio_fall=0.12,
        onset_conf_floor=0.5,
        offset_conf_fall=0.20,
        offset_ratio_rise=0.08,
    ):
        self.window_frames = window_frames
        self.onset_conf_rise = onset_conf_rise
        self.onset_ratio_fall = onset_ratio_fall
        self.onset_conf_floor = onset_conf_floor
        self.offset_conf_fall = offset_conf_fall
        self.offset_ratio_rise = offset_ratio_rise
        self._buf = collections.deque(maxlen=window_frames + 1)
        self.state = "idle"  # "idle" | "apex"

    def update(self, confidence, pinch_ratio):
        self._buf.append((confidence, pinch_ratio))
        onset_event = False
        offset_event = False
        if len(self._buf) == self._buf.maxlen:
            d_conf = self._buf[-1][0] - self._buf[0][0]
            d_ratio = self._buf[-1][1] - self._buf[0][1]
            if self.state == "idle":
                if (
                    d_conf > self.onset_conf_rise
                    and d_ratio < -self.onset_ratio_fall
                    and self._buf[-1][0] >= self.onset_conf_floor
                ):
                    self.state = "apex"
                    onset_event = True
            elif self.state == "apex":
                if d_conf < -self.offset_conf_fall and d_ratio > self.offset_ratio_rise:
                    self.state = "idle"
                    offset_event = True
        return self.state, onset_event, offset_event
