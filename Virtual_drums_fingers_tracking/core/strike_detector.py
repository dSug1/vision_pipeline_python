"""Kinematic strike detection.

A finger 'hits the table' when its motion along the strike axis accelerates
toward the surface and then decelerates/reverses (velocity sign inversion at
impact). We fire on that reversal, gated by the *peak* approach speed reached
during the descent (noise rejection) and a per-finger refractory period
(debounce). See spec section 6.

Why peak-tracking (and not just the previous frame's velocity): at a real impact
the fingertip decelerates over 2-3 frames (fast -> slow -> reverse), so the frame
immediately before the sign-flip is often already below threshold. Remembering the
fastest approach since the descent began is what makes a hard tap register
reliably. The thresholds in config.py still MUST be calibrated for the real
camera/table setup (spec section 16).

FRAMEWORK-FREE (portable).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from core.contracts import FingerId, Handedness, StrikeEvent


@dataclass
class _FingerState:
    """Per-finger running state for the strike state machine."""
    positions: Deque[float] = field(default_factory=lambda: deque(maxlen=8))
    smoothed_prev: Optional[float] = None   # previous smoothed strike-axis position
    peak_approach_speed: float = 0.0        # fastest toward-table speed in this descent
    in_approach: bool = False               # currently moving toward the table?
    last_strike_ms: int = -10_000
    last_seen_ms: Optional[int] = None       # timestamp of the last frame this finger was tracked

    def reset_motion(self) -> None:
        """Drop motion history without forgetting the refractory clock. Used when a
        finger reappears after being out of frame, so we never differentiate across
        the absence gap (which would fake a huge velocity -> a phantom strike)."""
        self.positions.clear()
        self.smoothed_prev = None
        self.peak_approach_speed = 0.0
        self.in_approach = False


class StrikeDetector:
    """Per-finger velocity-derivative strike detector. Call `update(...)` once per
    finger per frame; it returns a StrikeEvent on a detected hit, else None."""

    def __init__(
        self,
        smoothing_window: int,
        speed_threshold: float,
        refractory_ms: int,
        gap_reset_ms: int = 100,
        approach_sign: int = +1,  # +1 if "toward the table" => increasing axis value
    ) -> None:
        self._smoothing_window = max(1, smoothing_window)
        self._speed_threshold = speed_threshold
        self._refractory_ms = refractory_ms
        self._gap_reset_ms = gap_reset_ms
        self._approach_sign = 1 if approach_sign >= 0 else -1
        self._state: Dict[FingerId, _FingerState] = {}

    def update(
        self,
        finger_id: FingerId,
        handedness: Handedness,
        axis_value: float,
        timestamp_ms: int,
        x_px: int,
        y_px: int,
    ) -> Optional[StrikeEvent]:
        st = self._state.setdefault(finger_id, _FingerState())

        # Re-acquisition guard: if this finger was not tracked for a while, its
        # history is stale. Differentiating across that gap would invent a strike.
        if st.last_seen_ms is not None and (timestamp_ms - st.last_seen_ms) > self._gap_reset_ms:
            st.reset_motion()
        st.last_seen_ms = timestamp_ms

        st.positions.append(axis_value)
        if len(st.positions) < self._smoothing_window:
            return None

        # Moving-average smoothing, then a clean 1-frame velocity between
        # consecutive smoothed positions. Sign-normalized so +ve == toward table.
        recent = list(st.positions)[-self._smoothing_window:]
        smoothed = sum(recent) / len(recent)
        if st.smoothed_prev is None:
            st.smoothed_prev = smoothed
            return None
        velocity = (smoothed - st.smoothed_prev) * self._approach_sign
        st.smoothed_prev = smoothed

        if velocity > 0:
            # Still descending toward the table: remember the fastest approach.
            st.in_approach = True
            if velocity > st.peak_approach_speed:
                st.peak_approach_speed = velocity
            return None

        # velocity <= 0: the finger stopped or rebounded -> the impact moment.
        strike: Optional[StrikeEvent] = None
        was_hard_enough = st.peak_approach_speed >= self._speed_threshold
        debounced = (timestamp_ms - st.last_strike_ms) >= self._refractory_ms
        if st.in_approach and was_hard_enough and debounced:
            st.last_strike_ms = timestamp_ms
            strike = StrikeEvent(
                finger_id=finger_id,
                handedness=handedness,
                timestamp_ms=timestamp_ms,
                strike_speed=st.peak_approach_speed,
                x_px=x_px,
                y_px=y_px,
            )

        # Either way the descent is over; arm for the next one.
        st.in_approach = False
        st.peak_approach_speed = 0.0
        return strike
