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
# Usage: record.bat <label> <protocol> [duration_seconds]
#   e.g. record.bat pinch_front held_state
#        record.bat pinch_cycles_front cyclic
# Recording starts after a short countdown and stops automatically after
# --duration seconds — no keypress needed once it starts, since your hands
# are busy performing the gesture, not at the keyboard.
#
# --protocol is REQUIRED and stored in the saved JSON's "protocol" field --
# added 2026-07-31 after finding that an archived "held-state" pinch_front
# session actually contained three separate pinch-release dips, not one
# continuous hold, silently mislabeling ~60% of its frames as positive
# "pinch" when the hand was actually open/transitioning. Two protocols,
# never inferred from the label string alone (that's exactly how the mixup
# happened) -- always passed explicitly and always saved as data, not just
# implied by filename convention:
#   - "held_state": ONE CONTINUOUS HOLD for the whole capture -- every frame
#     is unambiguously the labeled class. Used for pinch_*/open_hand_*/
#     fist_*/rotating_no_pinch* (Stage 3 base-classifier training data,
#     GESTURE_PIPELINE_SPEC.md §3/§12) -- rotating_no_pinch is "held_state"
#     in this sense despite the hand moving, since the label is uniform
#     across every frame, which is what this protocol distinction is
#     actually about, not literal stillness.
#   - "cyclic": THREE grip/release (or pinch/rotate/release) REPETITIONS
#     within the capture -- frames are NOT uniformly one class, this is
#     event-layer (Stage 3.3) tuning data only. Used for
#     pinch_cycles_*/pinch_rotate_release.

RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources")
MODEL_PATH = os.path.join(RESOURCES_DIR, "hand_landmarker.task")

# Recordings live on the external drive, not the local disk (2026-07-31) --
# keeps the growing raw-capture corpus off the PC. If this path isn't
# reachable, the external drive is probably unplugged.
#
# Pencil-grip corpus reset (2026-07-31, GESTURE_PIPELINE_SPEC.md's handoff):
# the open-hand pinch definition's live behavior didn't meet expectations
# despite passing every recorded-data metric (Stage 4 live test) -- the old
# corpus is archived under Unsuccessful_grip/, not deleted, and is no longer
# read by any script. New recordings go under Pencil_style_grip/: pinch is
# now index+thumb CONTACT with the other three fingers held curled closed
# (a "holding a pencil" grip), not just thumb-index proximity on an
# otherwise freely-posed hand.
RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Pencil_style_grip"

DEFAULT_DURATION_S = 5.0  # uniform 5s for all sessions, held_state and cyclic alike (2026-07-31 direction)
COUNTDOWN_S = 3.0

PROTOCOL_HINTS = {
    "held_state": "HOLD CONTINUOUSLY -- do not release",
    # Framing convention added 2026-07-31, per direction: with the uniform
    # 5s duration, start the capture already closing into the FIRST grip
    # (not from a neutral pre-roll) and end right at the FINAL release (not
    # a neutral post-roll) -- maximizes actual transition coverage inside a
    # short window, rather than wasting frames on neutral padding at either
    # end. This is stored below (not just in this on-screen hint) so it's
    # legible from the saved JSON alone, not just tribal knowledge.
    "cyclic": "3 REPS -- START at grip onset, END at final release (no neutral padding)",
}


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
    parser.add_argument("--label", type=str, required=True, help="Session label, e.g. pinch_front, pinch_cycles_front")
    parser.add_argument(
        "--protocol", type=str, required=True, choices=sorted(PROTOCOL_HINTS),
        help="held_state (one continuous hold, every frame = the labeled class) or "
             "cyclic (3 grip/release reps, event-layer tuning data only)",
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION_S,
        help=f"Recording duration in seconds (default {DEFAULT_DURATION_S}) — capture auto-stops, no keypress needed",
    )
    args = parser.parse_args()
    protocol_hint = PROTOCOL_HINTS[args.protocol]

    drive_root = os.path.splitdrive(RECORDINGS_DIR)[0] + os.sep
    if not os.path.isdir(drive_root):
        raise RuntimeError(
            f"{drive_root} isn't reachable -- is the external drive plugged in? "
            f"(RECORDINGS_DIR = {RECORDINGS_DIR})"
        )
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
        f"[RecordSession] Get ready — recording '{args.label}' [{args.protocol.upper()}: {protocol_hint}] "
        f"starts in {COUNTDOWN_S:.0f}s, then captures for {args.duration:.1f}s automatically. "
        f"No keypress needed."
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
            cv2.putText(
                preview, f"[{args.protocol.upper()}] {protocol_hint}",
                (10, 65), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 200, 255), 2, cv2.LINE_AA,
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
                cv2.putText(
                    preview, f"[{args.protocol.upper()}] {protocol_hint}",
                    (10, 65), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA,
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
        json.dump(
            {
                "label": args.label,
                "protocol": args.protocol,
                "protocol_note": protocol_hint,
                "duration_s": args.duration,
                "frames": frames,
            },
            f,
        )

    print(f"[RecordSession] Saved {len(frames)} frames to {out_path}")


if __name__ == "__main__":
    main()
