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

# Make this folder the import root so `core`/`vision`/`output` resolve when the
# app is run from anywhere (and when the folder is copied elsewhere).
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import config
from core.events import EventBus
from core.contracts import LandmarkFrame
from core.strike_detector import StrikeDetector
from core.finger_tracker import FingerTracker
from vision.camera_source import OpenCvCameraSource
from vision.hand_landmarker import MediaPipeHandLandmarker
from output.sound_engine import LoggingSoundEngine
from output.visualizer import Visualizer


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
        smoothing_window=config.SMOOTHING_WINDOW,
        speed_threshold=config.STRIKE_SPEED_THRESHOLD,
        refractory_ms=config.REFRACTORY_MS,
        gap_reset_ms=config.GAP_RESET_MS,
        approach_sign=config.APPROACH_SIGN,
    )
    FingerTracker(bus, detector, strike_axis=config.STRIKE_AXIS)  # subscribes to the bus

    # Consumers
    LoggingSoundEngine(bus, config.FINGER_SOUNDS)  # debug; swap for AudioSoundEngine later
    visualizer = Visualizer(
        bus,
        draw_full_skeleton=config.DRAW_FULL_SKELETON,
        draw_labels=config.DRAW_LANDMARK_LABELS,
    )

    return bus, camera, landmarker, visualizer


def main() -> None:
    bus, camera, landmarker, visualizer = build()
    timestamp_ms = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            landmark_frame = landmarker.detect(frame, timestamp_ms)
            bus.publish(landmark_frame)            # -> FingerTracker -> StrikeEvents -> consumers
            visualizer.render(frame, timestamp_ms)
            if visualizer.should_quit():
                break
            timestamp_ms += 33                     # ~30 FPS monotonic clock for VIDEO mode
    finally:
        camera.release()
        landmarker.close()
        visualizer.destroy()
        print("[VirtualDrums] Stopped.")


if __name__ == "__main__":
    main()
