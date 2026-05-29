"""Hand landmark detection (hands only — no face).

`ILandmarkSource` is the portable seam; `MediaPipeHandLandmarker` is the
DESKTOP-ONLY implementation using MediaPipe-Python's Tasks API. On mobile, swap
for the native MediaPipe Tasks SDK behind the same interface, reusing the same
models/hand_landmarker.task bundle. Self-contained (no imports outside this app).
See spec section 5.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import cv2  # DESKTOP-ONLY
import mediapipe as mp  # DESKTOP-ONLY
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from core.contracts import Handedness, HandLandmarks, Landmark, LandmarkFrame


class ILandmarkSource(ABC):
    @abstractmethod
    def detect(self, frame_bgr, timestamp_ms: int) -> LandmarkFrame:
        """Run hand landmark detection on a BGR frame; return a LandmarkFrame."""

    @abstractmethod
    def close(self) -> None:
        ...


class MediaPipeHandLandmarker(ILandmarkSource):
    def __init__(
        self,
        model_path: str,
        num_hands: int = 2,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Hand model not found: {model_path}")
        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            num_hands=num_hands,
            running_mode=mp_vision.RunningMode.VIDEO,  # tracking amortizes palm detection
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._detector = mp_vision.HandLandmarker.create_from_options(options)

    def detect(self, frame_bgr, timestamp_ms: int) -> LandmarkFrame:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect_for_video(mp_image, timestamp_ms)

        frame = LandmarkFrame(timestamp_ms=timestamp_ms, frame_w=w, frame_h=h)
        for idx, hand_landmarks in enumerate(result.hand_landmarks):
            handed = result.handedness[idx][0].category_name  # "Left" | "Right"
            landmarks = [
                Landmark(x=lm.x, y=lm.y, z=lm.z, x_px=int(lm.x * w), y_px=int(lm.y * h))
                for lm in hand_landmarks
            ]
            frame.hands.append(HandLandmarks(handedness=Handedness(handed), landmarks=landmarks))
        return frame

    def close(self) -> None:
        self._detector.close()
