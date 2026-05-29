"""The single app window: shows the camera view with finger landmarks and flashes
a per-finger marker on each strike (the debug 'light signal'). DESKTOP-ONLY
(OpenCV window); swap for native UI on mobile. Self-contained (no imports outside
this app). See spec sections 8 and 9.
"""
from __future__ import annotations

from typing import Dict, Optional

import cv2  # DESKTOP-ONLY

from core.contracts import FINGERS, TIP_LANDMARK, LandmarkFrame, StrikeEvent, finger_id_for
from core.events import EventBus

WINDOW_NAME = "Virtual Drums - Finger Tracking"
_FLASH_MS = 150


class Visualizer:
    def __init__(self, bus: EventBus) -> None:
        self._last_frame: Optional[LandmarkFrame] = None
        self._flash_until: Dict[str, int] = {}  # finger_id.value -> timestamp_ms
        bus.subscribe(LandmarkFrame, self._on_landmark_frame)
        bus.subscribe(StrikeEvent, self._on_strike)

    def _on_landmark_frame(self, frame: LandmarkFrame) -> None:
        self._last_frame = frame

    def _on_strike(self, event: StrikeEvent) -> None:
        self._flash_until[event.finger_id.value] = event.timestamp_ms + _FLASH_MS

    def render(self, frame_bgr, timestamp_ms: int) -> None:
        """Draw finger landmarks + strike flashes onto frame_bgr and show the window."""
        lf = self._last_frame
        if lf is not None:
            for hand in lf.hands:
                if len(hand.landmarks) < 21:
                    continue
                for finger in FINGERS:
                    tip = hand.landmarks[TIP_LANDMARK[finger]]
                    fid = finger_id_for(hand.handedness, finger).value
                    flashing = timestamp_ms <= self._flash_until.get(fid, -1)
                    color = (0, 0, 255) if flashing else (0, 255, 0)
                    radius = 16 if flashing else 6
                    cv2.circle(frame_bgr, (tip.x_px, tip.y_px), radius, color, -1 if flashing else 2)
        cv2.imshow(WINDOW_NAME, frame_bgr)

    @staticmethod
    def should_quit() -> bool:
        if cv2.waitKey(1) & 0xFF == ord("q"):
            return True
        return cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1

    @staticmethod
    def destroy() -> None:
        cv2.destroyAllWindows()
