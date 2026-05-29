"""Turns LandmarkFrame events into per-finger StrikeEvents.

Subscribes to LandmarkFrame on the bus, extracts each finger's strike point
(fingertip landmark), feeds it to the StrikeDetector, and publishes any resulting
StrikeEvent. FRAMEWORK-FREE (portable). See spec sections 3.1 and 6.
"""
from __future__ import annotations

from core.contracts import (
    FINGERS,
    TIP_LANDMARK,
    HandLandmarks,
    Landmark,
    LandmarkFrame,
    finger_id_for,
)
from core.events import EventBus
from core.strike_detector import StrikeDetector


class FingerTracker:
    def __init__(self, bus: EventBus, detector: StrikeDetector, strike_axis: str = "y") -> None:
        self._bus = bus
        self._detector = detector
        self._axis = strike_axis
        bus.subscribe(LandmarkFrame, self.on_landmark_frame)

    def _axis_value(self, lm: Landmark) -> float:
        if self._axis == "x":
            return float(lm.x_px)
        if self._axis == "z":
            return float(lm.z)
        return float(lm.y_px)  # default: vertical (toward/away from table)

    def on_landmark_frame(self, frame: LandmarkFrame) -> None:
        for hand in frame.hands:
            self._process_hand(hand, frame.timestamp_ms)

    def _process_hand(self, hand: HandLandmarks, timestamp_ms: int) -> None:
        if len(hand.landmarks) < 21:
            return
        for finger in FINGERS:
            tip = hand.landmarks[TIP_LANDMARK[finger]]
            event = self._detector.update(
                finger_id=finger_id_for(hand.handedness, finger),
                handedness=hand.handedness,
                axis_value=self._axis_value(tip),
                timestamp_ms=timestamp_ms,
                x_px=tip.x_px,
                y_px=tip.y_px,
            )
            if event is not None:
                self._bus.publish(event)
