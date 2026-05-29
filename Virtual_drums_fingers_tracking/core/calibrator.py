"""Launch-time contact calibration.

Captures, per finger, the strike-axis value when the fingertip rests on the table
(its 'contact zero'). The StrikeDetector uses these zeros to gate hits to the table
height (arm line + contact band). FRAMEWORK-FREE (portable). See spec section 7.

Fixed-width mode (current): the user holds all fingertips on the table for a short
window; the zero is the median of the samples (robust to a few stray frames).
SWEEP mode (future): the user also slides hands nearer/farther to register the
per-finger range of contact positions -> an auto-sized band. Not yet implemented.
"""
from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional

from core.contracts import (
    FINGERS,
    TIP_LANDMARK,
    FingerId,
    LandmarkFrame,
    finger_id_for,
    strike_axis_value,
)


class ContactCalibrator:
    """Accumulates fingertip strike-axis samples over a capture window and reduces
    them to one contact zero per finger."""

    def __init__(self, axis: str, min_samples: int = 5) -> None:
        self._axis = axis
        self._min_samples = min_samples
        self._samples: Dict[FingerId, List[float]] = {}

    def add_frame(self, frame: LandmarkFrame) -> None:
        for hand in frame.hands:
            if len(hand.landmarks) < 21:
                continue
            for finger in FINGERS:
                tip = hand.landmarks[TIP_LANDMARK[finger]]
                fid = finger_id_for(hand.handedness, finger)
                self._samples.setdefault(fid, []).append(strike_axis_value(tip, self._axis))

    def result(self) -> Dict[FingerId, float]:
        """Per-finger contact zero (median). Fingers with too few samples (never
        reliably on the table) are omitted so the detector leaves them ungated."""
        return {
            fid: float(median(vals))
            for fid, vals in self._samples.items()
            if len(vals) >= self._min_samples
        }

    def amplitude(self, finger_id: FingerId) -> Optional[float]:
        """Strike-axis travel (max - min) observed for one finger over the capture
        window. Used by the arm dry-run to size the arm clearance from a real tap.
        Returns None if the finger had too few samples."""
        vals = self._samples.get(finger_id)
        if vals and len(vals) >= self._min_samples:
            return float(max(vals) - min(vals))
        return None
