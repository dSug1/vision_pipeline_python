import collections

# Stage 3.3 of Claude/GESTURE_PIPELINE_SPEC.md: onset/apex/offset event
# detection on top of the base classifier's continuous per-frame confidence.
# Onset and offset are each confirmed by DERIVATIVE AGREEMENT across two
# signals (confidence rising/falling AND the underlying pinch_ratio
# falling/rising over the same window) -- not a threshold crossing on
# confidence alone, which is exactly the rule-based approach's original
# failure mode (PART_ONE.md §1). Onset and offset get independently tuned
# thresholds (§3.3.1) -- release is not assumed to mirror pinch.

DEFAULT_WINDOW_FRAMES = 5  # ~150-200ms at typical webcam fps -- same
# precedent as the abandoned rule-based PinchTracker (PART_ONE.md §7.2);
# recalibrate if live capture fps differs meaningfully from recording fps.


class PinchEventTracker:
    """Stateful per-hand tracker. Feed (confidence, pinch_ratio) once per
    frame via update(); read back the current state and whether an onset/
    offset event fired this frame."""

    def __init__(
        self,
        window_frames=DEFAULT_WINDOW_FRAMES,
        onset_conf_rise=0.30,
        onset_ratio_fall=0.15,
        onset_conf_floor=0.5,
        offset_conf_fall=0.30,
        offset_ratio_rise=0.15,
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
