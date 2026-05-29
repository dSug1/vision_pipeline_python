"""Kinematic strike detection.

A finger 'hits the table' when its motion along the strike axis decelerates and
reverses (velocity sign inversion) after exceeding a noise threshold. See spec
section 6. This is a FIRST-PASS implementation — the thresholds in config.py MUST
be calibrated for the real camera/table setup (spec section 16).

FRAMEWORK-FREE (portable).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from core.contracts import FingerId, Handedness, StrikeEvent


@dataclass
class _FingerState:
    positions: Deque[float] = field(default_factory=lambda: deque(maxlen=16))
    last_velocity: float = 0.0
    last_strike_ms: int = -10_000


class StrikeDetector:
    """Per-finger velocity-derivative strike detector. Call `update(...)` once per
    finger per frame; it returns a StrikeEvent on a detected hit, else None."""

    def __init__(
        self,
        smoothing_window: int,
        speed_threshold: float,
        refractory_ms: int,
        approach_sign: int = +1,  # +1 if "toward the table" => increasing axis value
    ) -> None:
        self._smoothing_window = max(1, smoothing_window)
        self._speed_threshold = speed_threshold
        self._refractory_ms = refractory_ms
        self._approach_sign = approach_sign
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
        st.positions.append(axis_value)

        if len(st.positions) < self._smoothing_window + 1:
            return None

        # Smoothed velocity: latest sample minus the mean of the preceding window.
        recent = list(st.positions)[-(self._smoothing_window + 1):]
        smoothed_prev = sum(recent[:-1]) / len(recent[:-1])
        velocity = recent[-1] - smoothed_prev

        prev_velocity = st.last_velocity
        st.last_velocity = velocity

        # Strike = was approaching the table above threshold, now reversed (rebound).
        approaching = prev_velocity * self._approach_sign >= self._speed_threshold
        reversed_now = velocity * self._approach_sign <= 0
        debounced = (timestamp_ms - st.last_strike_ms) >= self._refractory_ms

        if approaching and reversed_now and debounced:
            st.last_strike_ms = timestamp_ms
            return StrikeEvent(
                finger_id=finger_id,
                handedness=handedness,
                timestamp_ms=timestamp_ms,
                strike_speed=abs(prev_velocity),
                x_px=x_px,
                y_px=y_px,
            )
        return None
