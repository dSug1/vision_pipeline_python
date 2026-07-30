"""Camera frame source.

`ICameraSource` is the portable seam; `OpenCvCameraSource` is the DESKTOP-ONLY
implementation. On mobile, replace it (CameraX / AVFoundation) behind the same
interface without touching core/. Self-contained (no imports outside this app).
See spec section 3.2.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2  # DESKTOP-ONLY


class ICameraSource(ABC):
    @abstractmethod
    def read(self) -> Tuple[bool, object]:
        """Return (ok, frame_bgr). ok=False when no frame is available."""

    @abstractmethod
    def release(self) -> None:
        ...


class OpenCvCameraSource(ICameraSource):
    """Webcam via OpenCV using the DirectShow backend (reliable on Windows; the
    default MSMF backend can hang on open). DESKTOP-ONLY."""

    def __init__(self, index: int = 0, width: Optional[int] = None, height: Optional[int] = None) -> None:
        self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open webcam (index {index}). Is another program using it?")

    def read(self) -> Tuple[bool, object]:
        return self._cap.read()

    def release(self) -> None:
        self._cap.release()
