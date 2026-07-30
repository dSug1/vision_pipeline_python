"""Portable data contracts shared between the vision producer and the consumers.

FRAMEWORK-FREE (no cv2 / mediapipe). This is the stable API a future mobile
rebuild would reimplement 1:1. See spec section 4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Handedness(str, Enum):
    LEFT = "Left"
    RIGHT = "Right"


class FingerId(str, Enum):
    LEFT_THUMB = "left_thumb"
    LEFT_INDEX = "left_index"
    LEFT_MIDDLE = "left_middle"
    LEFT_RING = "left_ring"
    LEFT_PINKY = "left_pinky"
    RIGHT_THUMB = "right_thumb"
    RIGHT_INDEX = "right_index"
    RIGHT_MIDDLE = "right_middle"
    RIGHT_RING = "right_ring"
    RIGHT_PINKY = "right_pinky"


# Finger name -> MediaPipe 21-landmark index (see spec section 4).
FINGERS = ("thumb", "index", "middle", "ring", "pinky")
TIP_LANDMARK = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
DIP_LANDMARK = {"thumb": 3, "index": 7, "middle": 11, "ring": 15, "pinky": 19}


def finger_id_for(handedness: "Handedness", finger: str) -> "FingerId":
    """Map (handedness, finger-name) -> FingerId, e.g. (LEFT, "index") -> LEFT_INDEX."""
    return FingerId[f"{handedness.name}_{finger.upper()}"]


def strike_axis_value(lm: "Landmark", axis: str) -> float:
    """The fingertip's coordinate along the strike axis (image axis 'toward the
    table'). Shared by the finger tracker and the calibrator so they cannot drift.
    'x'/'y' are pixels; 'z' is the normalized depth relative to the wrist."""
    if axis == "x":
        return float(lm.x_px)
    if axis == "z":
        return float(lm.z)
    return float(lm.y_px)  # default: vertical (toward/away from table)


@dataclass
class Landmark:
    """A single hand landmark. x/y/z are normalized to [0,1] (z relative to the
    wrist); x_px/y_px are pixel coordinates in the captured frame."""
    x: float
    y: float
    z: float
    x_px: int
    y_px: int


@dataclass
class HandLandmarks:
    handedness: Handedness
    landmarks: List[Landmark]  # 21 MediaPipe hand points


@dataclass
class LandmarkFrame:
    """One frame's detected hands (0..2)."""
    timestamp_ms: int
    frame_w: int
    frame_h: int
    hands: List[HandLandmarks] = field(default_factory=list)


@dataclass
class StrikeEvent:
    """Emitted when a finger 'hits the table'. strike_speed can drive volume later."""
    finger_id: FingerId
    handedness: Handedness
    timestamp_ms: int
    strike_speed: float
    x_px: int
    y_px: int
