"""The single app window: shows the camera view with hand landmarks and flashes
a per-finger marker on each strike (the debug 'light signal'). DESKTOP-ONLY
(OpenCV window); swap for native UI on mobile. Self-contained (no imports outside
this app). See spec sections 8 and 9.

For debugging the tracking/strike logic it draws the FULL hand skeleton (every
landmark + the connecting bones), color-coded per finger, not just the fingertips.
Toggle via the constructor flags (wired from config). The fingertips are the
strike points, so they are drawn larger and flash red on a strike.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import cv2  # DESKTOP-ONLY

from core.contracts import FINGERS, TIP_LANDMARK, LandmarkFrame, StrikeEvent, finger_id_for
from core.events import EventBus

WINDOW_NAME = "Virtual Drums - Finger Tracking"
_FLASH_MS = 150

# MediaPipe 21-point hand skeleton: pairs of landmark indices that form a "bone".
_HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # index
    (5, 9), (9, 10), (10, 11), (11, 12),   # middle
    (9, 13), (13, 14), (14, 15), (15, 16), # ring
    (13, 17), (17, 18), (18, 19), (19, 20),# pinky
    (0, 17),                               # palm base
)

# Per-finger color (BGR) so adjacent fingers are distinguishable while debugging.
_FINGER_COLORS: Dict[str, Tuple[int, int, int]] = {
    "thumb":  (255, 0, 0),     # blue
    "index":  (0, 255, 255),   # yellow
    "middle": (255, 0, 255),   # magenta
    "ring":   (255, 255, 0),   # cyan
    "pinky":  (0, 165, 255),   # orange
}
_WRIST_COLOR = (200, 200, 200)
_STRIKE_COLOR = (0, 0, 255)    # red flash on the struck fingertip

# Landmark index -> finger name (0 is the wrist). Used to color each point/bone.
_LANDMARK_FINGER: Dict[int, str] = {0: "wrist"}
for _finger, _base in (("thumb", 1), ("index", 5), ("middle", 9), ("ring", 13), ("pinky", 17)):
    for _i in range(4):
        _LANDMARK_FINGER[_base + _i] = _finger


def _color_for(idx: int) -> Tuple[int, int, int]:
    return _FINGER_COLORS.get(_LANDMARK_FINGER.get(idx, "wrist"), _WRIST_COLOR)


class Visualizer:
    def __init__(
        self,
        bus: EventBus,
        draw_full_skeleton: bool = True,
        draw_labels: bool = False,
    ) -> None:
        self._draw_full_skeleton = draw_full_skeleton
        self._draw_labels = draw_labels
        self._last_frame: Optional[LandmarkFrame] = None
        self._flash_until: Dict[str, int] = {}  # finger_id.value -> timestamp_ms
        bus.subscribe(LandmarkFrame, self._on_landmark_frame)
        bus.subscribe(StrikeEvent, self._on_strike)

    def _on_landmark_frame(self, frame: LandmarkFrame) -> None:
        self._last_frame = frame

    def _on_strike(self, event: StrikeEvent) -> None:
        self._flash_until[event.finger_id.value] = event.timestamp_ms + _FLASH_MS

    def render(self, frame_bgr, timestamp_ms: int) -> None:
        """Draw hand landmarks + strike flashes onto frame_bgr and show the window."""
        lf = self._last_frame
        if lf is not None:
            for hand in lf.hands:
                if len(hand.landmarks) < 21:
                    continue
                self._draw_hand(frame_bgr, hand, timestamp_ms)
        cv2.imshow(WINDOW_NAME, frame_bgr)

    def _draw_hand(self, frame_bgr, hand, timestamp_ms: int) -> None:
        pts = [(lm.x_px, lm.y_px) for lm in hand.landmarks]

        # 1) Bones (skeleton). Skipped in tips-only mode.
        if self._draw_full_skeleton:
            for a, b in _HAND_CONNECTIONS:
                cv2.line(frame_bgr, pts[a], pts[b], _color_for(b), 1, cv2.LINE_AA)

        # 2) Which landmark indices to draw as dots.
        if self._draw_full_skeleton:
            indices = range(21)
        else:
            indices = [TIP_LANDMARK[f] for f in FINGERS]

        for idx in indices:
            x, y = pts[idx]
            finger = _LANDMARK_FINGER.get(idx)
            is_tip = finger in FINGERS and TIP_LANDMARK[finger] == idx

            flashing = False
            if is_tip:
                fid = finger_id_for(hand.handedness, finger).value
                flashing = timestamp_ms <= self._flash_until.get(fid, -1)

            if flashing:
                cv2.circle(frame_bgr, (x, y), 16, _STRIKE_COLOR, -1)
            elif is_tip:
                cv2.circle(frame_bgr, (x, y), 6, _color_for(idx), -1)  # filled = strike point
            else:
                cv2.circle(frame_bgr, (x, y), 4, _color_for(idx), 1)   # hollow = joint

            if self._draw_labels:
                cv2.putText(frame_bgr, str(idx), (x + 5, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, _color_for(idx), 1, cv2.LINE_AA)

    @staticmethod
    def should_quit() -> bool:
        if cv2.waitKey(1) & 0xFF == ord("q"):
            return True
        return cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1

    @staticmethod
    def destroy() -> None:
        cv2.destroyAllWindows()
