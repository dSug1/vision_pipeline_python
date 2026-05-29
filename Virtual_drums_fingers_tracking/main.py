"""Virtual Drums — composition root.

Wires the producer (camera + hand landmarker) to the consumers (sound engine,
visualizer) via the in-process EventBus, then runs the capture -> inference ->
render loop. Launching this file launches the whole vision pipeline (one process).
Self-contained: this folder has no dependency on any other folder. See spec 3.4.

Run:  launch.bat   (or, with a venv active:  python main.py)
"""
from __future__ import annotations

import os
import sys
import time

# Make this folder the import root so `core`/`vision`/`output` resolve when the
# app is run from anywhere (and when the folder is copied elsewhere).
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import config
from core.events import EventBus
from core.contracts import FingerId, LandmarkFrame
from core.calibrator import ContactCalibrator
from core.strike_detector import StrikeDetector
from core.finger_tracker import FingerTracker
from vision.camera_source import OpenCvCameraSource
from vision.hand_landmarker import MediaPipeHandLandmarker
from output.sound_engine import LoggingSoundEngine
from output.visualizer import Visualizer
from output.debug_logger import DebugLogger


def build():
    bus = EventBus()

    # Producer (vision)
    camera = OpenCvCameraSource(config.CAMERA_INDEX, config.CAPTURE_WIDTH, config.CAPTURE_HEIGHT)
    landmarker = MediaPipeHandLandmarker(
        model_path=os.path.join(APP_DIR, config.MODEL_PATH),
        num_hands=config.NUM_HANDS,
        min_hand_detection_confidence=config.MIN_HAND_DETECTION_CONFIDENCE,
        min_hand_presence_confidence=config.MIN_HAND_PRESENCE_CONFIDENCE,
        min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
    )

    # Core (portable): landmark frames -> strikes
    detector = StrikeDetector(
        smoothing_frames=config.POS_SMOOTHING_FRAMES,
        velocity_delta_frames=config.VELOCITY_DELTA_FRAMES,
        speed_threshold=config.STRIKE_SPEED_THRESHOLD,
        decel_threshold=config.DECEL_SPEED_THRESHOLD,
        gap_reset_ms=config.GAP_RESET_MS,
        approach_sign=config.APPROACH_SIGN,
        contact_gate_enabled=config.CONTACT_GATE_ENABLED,
        contact_band_px=config.CONTACT_BAND_PX,
        arm_clearance_px=config.ARM_CLEARANCE_PX,
    )
    FingerTracker(bus, detector, strike_axis=config.STRIKE_AXIS)  # subscribes to the bus

    # Consumers
    LoggingSoundEngine(bus, config.FINGER_SOUNDS)  # debug; swap for AudioSoundEngine later
    visualizer = Visualizer(
        bus,
        draw_full_skeleton=config.DRAW_FULL_SKELETON,
        draw_labels=config.DRAW_LANDMARK_LABELS,
        draw_fps=config.DRAW_FPS,
    )

    return bus, camera, landmarker, detector, visualizer


class MonotonicMsClock:
    """Real wall-clock timestamps in integer milliseconds, strictly increasing.

    Replaces the old synthetic '+33 ms per frame' clock so velocity is measured in
    real time (px/second) and is independent of the actual frame rate. The same
    clock instance spans calibration + play because MediaPipe's VIDEO mode requires
    strictly increasing timestamps for the life of the detector."""

    def __init__(self) -> None:
        self._epoch = time.monotonic()
        self._last = -1

    def now_ms(self) -> int:
        ms = int((time.monotonic() - self._epoch) * 1000.0)
        if ms <= self._last:      # guarantee strictly increasing for MediaPipe
            ms = self._last + 1
        self._last = ms
        return ms


def measure_fps(camera, visualizer, clock, seconds: float, warmup_frames: int = 5):
    """Measure the real camera/loop FPS over a short window. Returns FPS (float) or
    None if it could not be measured. The camera's CAP_PROP_FPS is unreliable with
    DirectShow, so we time real frames. Discards the first few frames (camera spin-up)
    so the estimate isn't skewed by initialization lag."""
    for _ in range(warmup_frames):
        ok, frame = camera.read()
        if not ok:
            return None
        visualizer.render(frame, clock.now_ms(), banner=["Measuring camera FPS...", "One moment."])
        if visualizer.should_quit():
            return None

    first_ts = last_ts = None
    n = 0
    start = time.monotonic()
    while (time.monotonic() - start) < seconds:
        ok, frame = camera.read()
        if not ok:
            break
        ts = clock.now_ms()
        if first_ts is None:
            first_ts = ts
        last_ts = ts
        n += 1
        visualizer.render(frame, ts, banner=["Measuring camera FPS...", "One moment."])
        if visualizer.should_quit():
            break

    if n >= 2 and first_ts is not None and last_ts > first_ts:
        return (n - 1) / ((last_ts - first_ts) / 1000.0)
    return None


def _frames_from_ms(window_ms: float, fps: float) -> int:
    """Convert a real-time window (ms) to a frame count at the given FPS (>= 1)."""
    return max(1, round(window_ms * fps / 1000.0))


def configure_kinematics(detector, camera, visualizer, clock) -> dict:
    """Measure FPS and set the detector's smoothing/velocity windows from the
    ms-based config, so the real-time spans hold regardless of frame rate. Falls back
    to the frame-count config if measurement fails or auto-mode is off. Returns the
    chosen settings (for the debug-log metadata)."""
    if not config.KINEMATICS_AUTO_FROM_FPS:
        print(f"[fps] auto-from-FPS off -> smoothing={config.POS_SMOOTHING_FRAMES} frames, "
              f"velocity_delta={config.VELOCITY_DELTA_FRAMES} frames.")
        return {"fps": None, "smoothing_frames": config.POS_SMOOTHING_FRAMES,
                "velocity_delta_frames": config.VELOCITY_DELTA_FRAMES}
    fps = measure_fps(camera, visualizer, clock, config.MEASURE_FPS_SECONDS)
    if fps is None or fps <= 0:
        print("[fps] measurement failed -> using POS_SMOOTHING_FRAMES / VELOCITY_DELTA_FRAMES.")
        return {"fps": None, "smoothing_frames": config.POS_SMOOTHING_FRAMES,
                "velocity_delta_frames": config.VELOCITY_DELTA_FRAMES}
    smoothing = _frames_from_ms(config.POS_SMOOTHING_MS, fps)
    delta = _frames_from_ms(config.VELOCITY_DELTA_MS, fps)
    detector.set_kinematics(smoothing, delta)
    print(f"[fps] measured {fps:.1f} FPS -> smoothing={smoothing} frames "
          f"({config.POS_SMOOTHING_MS:.0f}ms), velocity_delta={delta} frames "
          f"({config.VELOCITY_DELTA_MS:.0f}ms).")
    return {"fps": fps, "smoothing_frames": smoothing, "velocity_delta_frames": delta}


def _debug_meta_lines(kin: dict, contact_zeros: dict, arm_clearance) -> list:
    """Compose the `#`-commented header for the debug CSV so the data is self-describing."""
    arm = arm_clearance if arm_clearance is not None else config.ARM_CLEARANCE_PX
    fps = kin.get("fps")
    zeros = ", ".join(f"{fid.value}={z:.1f}" for fid, z in contact_zeros.items()) or "(none - kinematic only)"
    return [
        "Virtual Drums debug log (per finger per frame)",
        f"measured_fps={fps:.2f}" if fps else "measured_fps=unknown(fallback)",
        f"smoothing_frames={kin.get('smoothing_frames')}  velocity_delta_frames={kin.get('velocity_delta_frames')}",
        f"STRIKE_SPEED_THRESHOLD(px/s)={config.STRIKE_SPEED_THRESHOLD}  DECEL_SPEED_THRESHOLD(px/s)={config.DECEL_SPEED_THRESHOLD}",
        f"CONTACT_BAND_PX={config.CONTACT_BAND_PX}  arm_clearance_px={arm:.1f}",
        f"strike_axis={config.STRIKE_AXIS}  approach_sign={config.APPROACH_SIGN}",
        f"contact_zeros: {zeros}",
        "events: warmup/vel_warmup/dt_zero/approach/medium/FIRE/impact_noarm/impact_noreach/slow_stop",
    ]


class _CalibrationAborted(Exception):
    """Raised when the user closes the window / presses q during calibration."""


def _capture_phase(camera, landmarker, visualizer, clock, countdown_s, capture_s,
                   prompt_lines, capture_lines):
    """Run one countdown + timed-capture phase. Feeds every captured frame to a fresh
    ContactCalibrator and returns it. Timed only — the keyboard is not used, so the
    user can keep hands on the table. Raises _CalibrationAborted if the window is
    closed. Frame timestamps come from the real-time clock (shared with play)."""
    calibrator = ContactCalibrator(config.STRIKE_AXIS)
    phase_start = time.monotonic()
    capturing = False
    while True:
        ok, frame = camera.read()
        if not ok:
            break
        ts = clock.now_ms()
        landmark_frame = landmarker.detect(frame, ts)
        visualizer.set_frame(landmark_frame)
        elapsed = time.monotonic() - phase_start

        if not capturing:
            remaining = countdown_s - elapsed
            if remaining <= 0:
                capturing = True
                phase_start = time.monotonic()
                continue
            banner = list(prompt_lines) + [f"Starting in {int(remaining) + 1}..."]
        else:
            calibrator.add_frame(landmark_frame)
            left = capture_s - elapsed
            banner = list(capture_lines) + [f"{max(0.0, left):.1f}s left"]
            if left <= 0:
                break

        visualizer.render(frame, ts, banner=banner)
        if visualizer.should_quit():
            raise _CalibrationAborted()
    return calibrator


def run_calibration(camera, landmarker, visualizer, clock):
    """Two-phase launch calibration. Returns (contact_zeros, arm_clearance_px).
    Phase 1 captures each finger's table-contact height; phase 2 is an index-finger
    dry-run that sizes the arm clearance from a real tap. Aborting (window close / q)
    falls back to kinematic-only. See spec section 7."""
    if not config.CALIBRATION_ENABLED:
        return {}, None

    try:
        # Phase 1: per-finger contact zero (all fingers resting on the table).
        contact_cal = _capture_phase(
            camera, landmarker, visualizer, clock,
            config.CALIBRATION_COUNTDOWN_SECONDS, config.CALIBRATION_CAPTURE_SECONDS,
            ["CALIBRATION 1/2 - table contact", "Rest ALL 10 fingertips flat on the table."],
            ["Hold fingers still on the table..."],
        )
        zeros = contact_cal.result()
        print(f"[calibration] captured contact zero for {len(zeros)}/10 fingers.")

        # Phase 2: arm-clearance dry-run (tap with one index finger).
        arm_clearance = None
        if config.ARM_CALIBRATION_ENABLED:
            fname = config.ARM_DRYRUN_FINGER.lower()
            dryrun_cal = _capture_phase(
                camera, landmarker, visualizer, clock,
                config.ARM_DRYRUN_COUNTDOWN_SECONDS, config.ARM_DRYRUN_SECONDS,
                ["CALIBRATION 2/2 - tap amplitude",
                 f"Tap the table a few times with your {fname.upper()} finger."],
                [f"Keep tapping with your {fname} finger..."],
            )
            amps = []
            for hand in ("LEFT", "RIGHT"):
                fid = FingerId.__members__.get(f"{hand}_{fname.upper()}")
                a = dryrun_cal.average_swing_amplitude(fid, config.ARM_SWING_MIN_PROMINENCE_PX) if fid else None
                if a:
                    amps.append(a)
            if amps:
                swing = max(amps)   # the actively-tapped hand (resting hand gives ~0)
                arm_clearance = config.ARM_CALIBRATION_FRACTION * swing
                print(f"[calibration] {fname} avg swing {swing:.0f}px "
                      f"-> arm clearance {arm_clearance:.0f}px "
                      f"({config.ARM_CALIBRATION_FRACTION:.0%}).")
            else:
                print(f"[calibration] no {fname}-finger swings captured -> using ARM_CLEARANCE_PX fallback.")
        return zeros, arm_clearance
    except _CalibrationAborted:
        print("[calibration] aborted -> running kinematic-only (no contact gate).")
        return {}, None


def main() -> None:
    bus, camera, landmarker, detector, visualizer = build()
    clock = MonotonicMsClock()
    logger = None
    try:
        # Measure FPS and set the smoothing/velocity windows from the ms-based config.
        kin = configure_kinematics(detector, camera, visualizer, clock)

        # Calibrate the per-finger table height + the arm clearance, then apply.
        contact_zeros, arm_clearance = run_calibration(camera, landmarker, visualizer, clock)
        detector.set_contact_zeros(contact_zeros)
        if arm_clearance is not None:
            detector.set_arm_clearance(arm_clearance)

        # Optional debug logging of the detector internals, for finetuning.
        if config.DEBUG_LOG_ENABLED:
            logger = DebugLogger(os.path.join(APP_DIR, config.DEBUG_LOG_PATH),
                                 hands=config.DEBUG_LOG_HANDS)
            logger.write_meta(_debug_meta_lines(kin, contact_zeros, arm_clearance))
            detector.set_debug_sink(logger.record)
            print(f"[debug-log] logging to {config.DEBUG_LOG_PATH} "
                  f"(hands: {', '.join(config.DEBUG_LOG_HANDS)}).")

        # Play.
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            timestamp_ms = clock.now_ms()          # real wall-clock ms (FPS-independent)
            landmark_frame = landmarker.detect(frame, timestamp_ms)
            bus.publish(landmark_frame)            # -> FingerTracker -> StrikeEvents -> consumers
            visualizer.render(frame, timestamp_ms)
            if visualizer.should_quit():
                break
    finally:
        if logger is not None:
            logger.close()
        camera.release()
        landmarker.close()
        visualizer.destroy()
        print("[VirtualDrums] Stopped.")


if __name__ == "__main__":
    main()
