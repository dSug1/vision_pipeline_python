import collections

# Stage 3.3 of Claude/GESTURE_PIPELINE_SPEC.md: onset/apex/offset event
# detection on top of the base classifier's continuous per-frame confidence.
# Onset and offset are each confirmed by DERIVATIVE AGREEMENT across two
# signals (confidence rising/falling AND the underlying pinch_ratio
# falling/rising over the same window) -- not a threshold crossing on
# confidence alone, which is exactly the rule-based approach's original
# failure mode (PART_ONE.md §1). Onset and offset get independently tuned
# thresholds (§3.3.1) -- release is not assumed to mirror pinch.

DEFAULT_WINDOW_FRAMES = 8  # re-tuned 2026-07-31 against the pencil-grip
# corpus (GESTURE_PIPELINE_SPEC.md §12.4's retrain + the follow-up event-
# layer sweep) -- was 5. Needed re-checking (not assumed to carry over)
# once features.DELTA_WINDOW_MS tripled 300ms->900ms for the base
# classifier: a much longer classifier lookback smooths per-frame
# confidence more, so this tracker's OWN derivative-agreement window (a
# separate concept from the classifier's input-feature window) needed a
# wider grid search too. 8 was the best-scoring point across window_frames
# in {5,8,12,18,24}; the grid did NOT find window_frames alone able to
# close the remaining cycle-detection gap -- see the tuning comment below.


class PinchEventTracker:
    """Stateful per-hand tracker. Feed (confidence, pinch_ratio) once per
    frame via update(); read back the current state and whether an onset/
    offset event fired this frame."""

    def __init__(
        self,
        window_frames=DEFAULT_WINDOW_FRAMES,
        # Re-tuned 2026-07-31 against the pencil-grip corpus
        # (tune_event_layer.py's grid search, GESTURE_PIPELINE_SPEC.md
        # §12.4 follow-up) -- was 0.30/0.15/0.30/0.15. Best-scoring point
        # (near-zero false positives: 0 across 40 held-out hand-sessions)
        # but the grid's OWN top-10-by-raw-cycle-closeness table shows even
        # the most permissive settings tested only reach ~1.3-1.4 onsets per
        # session against a ~3 target -- this is not a threshold-tuning
        # problem anymore, see the spec for the diagnosed root cause
        # (recording cadence, not classifier or event-layer quality).
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
