"""Kinematic strike detection with a per-finger arm/contact state machine.

A finger 'hits the table' when it (1) was raised above an arm line, (2) descended
toward the table fast enough for a few frames, and (3) decelerated sharply to
almost-zero speed while inside the contact band at the calibrated table height.
Each condition rejects a different false positive; together they make one real tap
fire exactly one hit. See spec section 6.

The conditions, in order:

  * ARM (position).   The fingertip must first rise ABOVE the table by the arm
    clearance before a hit can be registered. This rejects derivative noise (a
    resting/jittering finger never crossed the line) and guards re-acquisition: a
    finger that was masked (e.g. an occluded thumb) and reappears near the table
    starts DISARMED and cannot fire until lifted. Small lifts re-arm it, so fast
    rolls still work. The clearance is set by the launch-time dry-run calibration
    (a fraction of the measured tap amplitude), or the config fallback.
  * FAST APPROACH (kinematic). The toward-table velocity must reach >= the speed
    threshold (V_high) during the descent. This is the speed gate.
  * DECELERATION = impact (kinematic). The hit fires on the frame velocity drops
    BELOW V_low ('almost zero') right after the fast approach — i.e. the finger
    slammed to a stop at the table. We deliberately do NOT wait for the velocity to
    reverse (go negative), because by then the finger has already left the table;
    firing on the deceleration removes that latency.
  * CONTACT (position, min-depth). The deepest point reached must be at least
    table-deep (within the contact band of the calibrated zero); deeper is fine.
    This rejects mid-air taps that decelerate above the table.

No refractory/debounce: the arm is consumed on each hit and the finger must rise
back above the arm line to re-arm, so a micro-bounce at the table cannot re-fire —
the arm-consume rule IS the debounce. (Caveat: with the contact gate disabled
[kinematic-only fallback] there is then no debounce; see the noise-work TODO in spec
§16. A consecutive-fast-frames requirement was also removed and may be reinstated.)

Velocity is computed flexibly and in REAL time: position is moving-average smoothed
over `smoothing_frames`, then differentiated across `velocity_delta_frames` and
divided by the actual elapsed wall-clock time between those samples -> **px/second**
(FPS-independent, so the thresholds don't shift when the frame rate does). (MediaPipe
does NOT smooth landmark coordinates, so this is the only smoothing in the chain.)

FRAMEWORK-FREE (portable).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from core.contracts import FingerId, Handedness, StrikeEvent

_NEG_INF = -1e18


@dataclass
class _FingerState:
    """Per-finger running state for the strike state machine."""
    raw: Deque[float] = field(default_factory=lambda: deque(maxlen=8))       # raw axis samples (smoothing)
    smoothed: Deque[float] = field(default_factory=lambda: deque(maxlen=8))  # smoothed positions (velocity)
    stamps: Deque[int] = field(default_factory=lambda: deque(maxlen=8))      # timestamps (ms) of the smoothed samples
    armed: bool = False              # has the tip risen above the arm line since the last hit / re-acquisition?
    was_fast: bool = False           # did velocity reach >= V_high during the current descent?
    burst_max_speed: float = 0.0     # fastest speed in the current fast approach (reported as strike_speed)
    deepest_depth: float = _NEG_INF  # deepest (most toward-table) point reached this approach
    last_seen_ms: Optional[int] = None

    def reset_motion(self) -> None:
        """Drop motion history AND disarm. Used on re-acquisition after a finger was
        out of frame, so (a) we never differentiate across the absence gap, and
        (b) a finger that reappears near the table cannot fire until it is lifted."""
        self.raw.clear()
        self.smoothed.clear()
        self.stamps.clear()
        self.armed = False
        self._reset_burst()

    def _reset_burst(self) -> None:
        self.was_fast = False
        self.burst_max_speed = 0.0
        self.deepest_depth = _NEG_INF


class StrikeDetector:
    """Per-finger strike detector. Call `update(...)` once per finger per frame; it
    returns a StrikeEvent on a detected hit, else None. After calibration, call
    `set_contact_zeros(...)` and (optionally) `set_arm_clearance(...)` to enable the
    position-based arm/contact gating."""

    def __init__(
        self,
        smoothing_frames: int,
        velocity_delta_frames: int,
        speed_threshold: float,        # V_high: min toward-table speed of the approach (px/sec)
        decel_threshold: float,        # V_low: 'almost zero' speed that marks the impact (px/sec)
        gap_reset_ms: int = 100,
        approach_sign: int = +1,        # +1 if "toward the table" => increasing axis value
        contact_gate_enabled: bool = True,
        contact_band_px: float = 25.0,  # min-depth tolerance below the contact zero
        arm_clearance_px: float = 35.0, # fallback height above the zero needed to (re)arm
    ) -> None:
        self._smoothing_frames = max(1, smoothing_frames)
        self._velocity_delta = max(1, velocity_delta_frames)
        self._speed_threshold = speed_threshold
        self._decel_threshold = decel_threshold
        self._gap_reset_ms = gap_reset_ms
        self._sign = 1 if approach_sign >= 0 else -1
        self._contact_gate_enabled = contact_gate_enabled
        self._contact_band = contact_band_px
        self._arm_clearance = arm_clearance_px
        # Per-finger contact depth (calibrated zero, in depth units = axis * sign).
        self._contact_depth: Dict[FingerId, float] = {}
        self._state: Dict[FingerId, _FingerState] = {}
        self._raw_len = self._smoothing_frames
        self._smooth_len = self._velocity_delta + 1

    def set_contact_zeros(self, zeros: Dict[FingerId, float]) -> None:
        """Apply calibration: per-finger strike-axis value when the tip touches the
        table (raw axis units). Stored as depth (axis * approach_sign). Fingers
        absent from `zeros` are NOT gated (they pass through, kinematic-only)."""
        self._contact_depth = {fid: value * self._sign for fid, value in zeros.items()}

    def set_kinematics(self, smoothing_frames: int, velocity_delta_frames: int) -> None:
        """Reconfigure the smoothing window and velocity baseline (in frames). Called
        after the launch-time FPS measurement converts the ms-based windows to frame
        counts. Safe to call before play (clears any partial per-finger state)."""
        self._smoothing_frames = max(1, int(smoothing_frames))
        self._velocity_delta = max(1, int(velocity_delta_frames))
        self._raw_len = self._smoothing_frames
        self._smooth_len = self._velocity_delta + 1
        self._state.clear()

    def set_arm_clearance(self, clearance_px: float) -> None:
        """Override the arm clearance (height above the table needed to re-arm a hit)
        with a value measured by the launch-time dry-run calibration."""
        if clearance_px > 0:
            self._arm_clearance = clearance_px

    def _gate_active_for(self, finger_id: FingerId) -> bool:
        return self._contact_gate_enabled and finger_id in self._contact_depth

    def update(
        self,
        finger_id: FingerId,
        handedness: Handedness,
        axis_value: float,
        timestamp_ms: int,
        x_px: int,
        y_px: int,
    ) -> Optional[StrikeEvent]:
        st = self._state.get(finger_id)
        if st is None:
            st = _FingerState(
                raw=deque(maxlen=self._raw_len),
                smoothed=deque(maxlen=self._smooth_len),
                stamps=deque(maxlen=self._smooth_len),
            )
            self._state[finger_id] = st

        # Re-acquisition guard: a long gap means stale history -> disarm & forget.
        if st.last_seen_ms is not None and (timestamp_ms - st.last_seen_ms) > self._gap_reset_ms:
            st.reset_motion()
        st.last_seen_ms = timestamp_ms

        st.raw.append(axis_value)
        if len(st.raw) < self._smoothing_frames:
            return None
        smoothed = sum(st.raw) / len(st.raw)
        st.smoothed.append(smoothed)
        st.stamps.append(timestamp_ms)

        depth = smoothed * self._sign  # larger == more toward the table
        gate = self._gate_active_for(finger_id)

        # ARM: the tip must rise above the table by the clearance to (re)arm a hit.
        if gate and depth <= self._contact_depth[finger_id] - self._arm_clearance:
            st.armed = True

        if len(st.smoothed) < self._velocity_delta + 1:
            return None

        # Smoothed velocity over the frame gap, normalized by REAL elapsed time
        # (px/second); +ve == toward the table. FPS-independent.
        dt_ms = st.stamps[-1] - st.stamps[-1 - self._velocity_delta]
        if dt_ms <= 0:
            return None
        velocity = (st.smoothed[-1] - st.smoothed[-1 - self._velocity_delta]) / dt_ms * 1000.0 * self._sign

        if velocity >= self._speed_threshold:
            # Fast approach: mark it and remember the burst peak / depth.
            st.was_fast = True
            if velocity > st.burst_max_speed:
                st.burst_max_speed = velocity
            if depth > st.deepest_depth:
                st.deepest_depth = depth
            return None

        if velocity >= self._decel_threshold:
            # Decelerating but not yet 'stopped': hold the burst, keep tracking depth.
            if depth > st.deepest_depth:
                st.deepest_depth = depth
            return None

        # velocity < V_low: the finger has (almost) stopped -> the impact moment.
        strike: Optional[StrikeEvent] = None
        if st.was_fast:
            if depth > st.deepest_depth:
                st.deepest_depth = depth
            if gate:
                armed_ok = st.armed
                reached_table = st.deepest_depth >= (self._contact_depth[finger_id] - self._contact_band)
            else:
                armed_ok = True          # no calibration -> kinematic-only fallback
                reached_table = True
            if armed_ok and reached_table:
                st.armed = False         # consume the arm; must lift again to re-arm
                strike = StrikeEvent(
                    finger_id=finger_id,
                    handedness=handedness,
                    timestamp_ms=timestamp_ms,
                    strike_speed=st.burst_max_speed,
                    x_px=x_px,
                    y_px=y_px,
                )
        # The fast approach is over (fired or not); arm the trackers for the next one.
        st._reset_burst()
        return strike
