import argparse
import json
import os
import time
from datetime import datetime

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Standalone recording tool for Part One's gesture classifier design work
# (Hand_detection/Claude/PART_ONE.md). Captures labeled sessions of both
# hands' NORMALIZED landmarks (image-space, [0,1]) and WORLD landmarks
# (metric, hand-relative 3D) per frame, matching the frame schema in
# Specification.md §6 — this is the data a classifier gets tuned against
# (ratios/angles from world_landmarks), not guessed thresholds.
#
# Deliberately independent of the live socket pipeline (VisionPipeline.py /
# Client.py / PythonApp_Main.py): recording needs no cube window and no
# server/client split, just webcam -> HandLandmarker -> JSON file. Run via
# ..\Movement_with_hand_detection\record.bat (reuses that folder's .venv).
#
# Usage: record.bat <label> [duration_seconds]   e.g. record.bat pinch_x3 4
# Recording starts after a short countdown and stops automatically after
# --duration seconds — no keypress needed once it starts, since your hands
# are busy performing the gesture, not at the keyboard.

RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources")
MODEL_PATH = os.path.join(RESOURCES_DIR, "hand_landmarker.task")
RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")

DEFAULT_DURATION_S = 4.0
COUNTDOWN_S = 3.0


def _landmark_list(landmarks):
    return [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in landmarks]


def _extract_frame(timestamp_ms, result):
    hands = []
    for idx in range(len(result.hand_landmarks)):
        hands.append({
            "handedness": result.handedness[idx][0].category_name,
            "score": result.handedness[idx][0].score,
            "landmarks": _landmark_list(result.hand_landmarks[idx]),
            "world_landmarks": _landmark_list(result.hand_world_landmarks[idx]),
        })
    return {"timestamp_ms": timestamp_ms, "hands": hands}


def _window_open(window_name: str) -> bool:
    return cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) >= 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a labeled hand-landmark session (Claude/PART_ONE.md).")
    parser.add_argument("--label", type=str, required=True, help="Session label, e.g. pinch_x3, open_hand, fist")
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION_S,
        help=f"Recording duration in seconds (default {DEFAULT_DURATION_S}) — capture auto-stops, no keypress needed",
    )
    args = parser.parse_args()

    os.makedirs(RECORDINGS_DIR, exist_ok=True)

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=2,
        running_mode=vision.RunningMode.VIDEO,
    )
    detector = vision.HandLandmarker.create_from_options(options)

    # Same DSHOW backend as VisionPipeline.py — the default MSMF backend can
    # hang for a long time on open, especially after a prior run didn't
    # release the device cleanly.
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam (index 0). Is another program using the camera?")

    window_name = f"Recording '{args.label}'"
    frames = []
    timestamp_ms = 0

    print(
        f"[RecordSession] Get ready — recording '{args.label}' starts in {COUNTDOWN_S:.0f}s, "
        f"then captures for {args.duration:.1f}s automatically. No keypress needed."
    )

    try:
        # Pre-roll countdown: gives time to get hands in frame before capture
        # starts, since there's no "ready" keypress once recording begins —
        # hands are busy performing the gesture, not at the keyboard.
        countdown_start = time.time()
        aborted = False
        while True:
            ret, frame = cap.read()
            if not ret:
                aborted = True
                break
            remaining = COUNTDOWN_S - (time.time() - countdown_start)
            if remaining <= 0:
                break
            preview = frame.copy()
            cv2.putText(
                preview, f"Get ready... {remaining:.1f}s",
                (10, 30), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2, cv2.LINE_AA,
            )
            cv2.imshow(window_name, preview)
            cv2.waitKey(1)
            if not _window_open(window_name):
                aborted = True
                break

        # Capture: runs for exactly --duration seconds, then stops
        # automatically. Window-close still works as an early abort.
        if not aborted:
            record_start = time.time()
            while True:
                elapsed = time.time() - record_start
                if elapsed >= args.duration:
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = detector.detect_for_video(mp_image, timestamp_ms)
                frames.append(_extract_frame(timestamp_ms, result))

                preview = frame.copy()
                remaining = args.duration - elapsed
                cv2.putText(
                    preview, f"REC '{args.label}' - {remaining:.1f}s left - frames: {len(frames)}",
                    (10, 30), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA,
                )
                cv2.imshow(window_name, preview)
                cv2.waitKey(1)

                if not _window_open(window_name):
                    break

                timestamp_ms += 33  # ~30 FPS, matching VisionPipeline.py's pacing
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not frames:
        print("[RecordSession] No frames captured, nothing saved.")
        return

    out_name = f"{args.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path = os.path.join(RECORDINGS_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"label": args.label, "frames": frames}, f)

    print(f"[RecordSession] Saved {len(frames)} frames to {out_path}")


if __name__ == "__main__":
    main()
