import argparse
import json
import os
import time
from datetime import datetime

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Ad hoc diagnostic recorder for the rotation-while-snapped work
# (Claude/GESTURE_PIPELINE_SPEC.md §13, HANDOFF_SNAP_ROTATE_RELEASE.md §2),
# built 2026-08-01 per direct request: "record the full data (landmarks
# positions, cube rotation, blocked or not)" for an 8s session of rotating
# the hand to back-toward-camera and continuing to rotate in that pose, so
# the reported "chaotic" cube rotation there can be diagnosed from data
# instead of guessed at from watching the live window.
#
# Imports CubeState/update_hands/_hand_orientation_quaternion directly from
# LiveSnapDebug.py rather than re-deriving them, so this records EXACTLY
# what that tool computes -- no risk of the two drifting apart (the
# opposite choice from LiveSnapDebug.py's own relationship to the
# production HandsTriggeredActions.py, which duplicates by design because
# that module opens a real pygame window as an import side effect; this
# script has no such conflict with LiveSnapDebug, which is import-safe).
#
# This is NOT corpus-training data (unlike RecordSession.py's Pencil_style_
# grip captures) -- a one-off diagnostic dump, saved locally, not to the
# external drive.
import LiveSnapDebug as debug_tool

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rotation_debug_recordings")

DEFAULT_DURATION_S = 8.0
COUNTDOWN_S = 3.0


def _pixel_landmarks(normalized, width, height):
    return [(lm.x * width, lm.y * height) for lm in normalized]


def _world_landmarks(world_lms):
    return [(lm.x, lm.y, lm.z) for lm in world_lms]


def _window_open(window_name: str) -> bool:
    return cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) >= 1


def _hand_frame_record(handedness, state: "debug_tool.CubeState", pixel_landmarks, world_landmarks, score, thumb_outward):
    raw_quat, conditioning_norm = debug_tool._hand_orientation_quaternion(world_landmarks)
    held_cube = state.cube_owned_by(handedness)
    return {
        "detected": True,
        "score": score,
        "pixel_landmarks": [[round(x, 2), round(y, 2)] for x, y in pixel_landmarks],
        "world_landmarks": [[round(x, 5), round(y, 5), round(z, 5)] for x, y, z in world_landmarks],
        "thumb_outward": thumb_outward,
        "raw_orientation_quat": list(raw_quat),
        "conditioning_norm": conditioning_norm,
        "reliability_alpha": state.last_hand_reliability_alpha[handedness],
        "fused_orientation_quat": list(state.hand_orientation_filters[handedness].last_fused)
        if state.hand_orientation_filters[handedness].last_fused is not None else None,
        "held_cube": held_cube,
        "cube_orientation_quat": list(state.cubes[held_cube].orientation) if held_cube is not None else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record full per-frame rotation-diagnostic data (landmarks, computed orientation, glitch flag, cube orientation).")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S, help=f"Recording duration in seconds (default {DEFAULT_DURATION_S})")
    parser.add_argument("--camera-index", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(RECORDINGS_DIR, exist_ok=True)

    base_options = python.BaseOptions(model_asset_path=debug_tool.HAND_LANDMARKER_MODEL_PATH)
    options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2, running_mode=vision.RunningMode.VIDEO)
    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). Is another program using the camera?")

    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read an initial frame from the webcam.")
    height, width = frame.shape[:2]
    state = debug_tool.CubeState(window_size=(width, height))

    window_name = "Rotation debug recording"
    frames = []
    timestamp_ms = 0

    print(
        f"[RecordRotationDebug] Get ready -- recording starts in {COUNTDOWN_S:.0f}s, "
        f"then captures for {args.duration:.1f}s automatically. Grab a cube, rotate your hand "
        f"to back-toward-camera, and keep rotating in that pose for the diagnostic to be useful."
    )

    try:
        countdown_start = time.time()
        aborted = False
        while True:
            ret, frame = cap.read()
            if not ret:
                aborted = True
                break
            frame = cv2.flip(frame, 1)
            remaining = COUNTDOWN_S - (time.time() - countdown_start)
            if remaining <= 0:
                break
            cv2.putText(frame, f"Get ready... {remaining:.1f}s", (10, 30),
                        cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2, cv2.LINE_AA)
            cv2.imshow(window_name, frame)
            cv2.waitKey(1)
            if not _window_open(window_name):
                aborted = True
                break

        if not aborted:
            record_start = time.time()
            while True:
                elapsed = time.time() - record_start
                if elapsed >= args.duration:
                    break

                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.flip(frame, 1)

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = detector.detect_for_video(mp_image, timestamp_ms)

                hand_data_by_hand = {h: None for h in debug_tool.TRACKED_HANDS}
                normalized_by_hand = {}
                scores_by_hand = {}
                for idx in range(len(result.hand_landmarks)):
                    handedness = result.handedness[idx][0].category_name
                    if handedness not in debug_tool.TRACKED_HANDS:
                        continue
                    normalized = result.hand_landmarks[idx]
                    pixel_landmarks = _pixel_landmarks(normalized, width, height)
                    world_landmarks = _world_landmarks(result.hand_world_landmarks[idx])
                    hand_data_by_hand[handedness] = {
                        "pixel_landmarks": pixel_landmarks,
                        "world_landmarks": world_landmarks,
                        "thumb_outward": debug_tool._is_thumb_outward(pixel_landmarks, handedness),
                    }
                    normalized_by_hand[handedness] = normalized
                    scores_by_hand[handedness] = result.handedness[idx][0].score

                # Drives the SAME state/logic as LiveSnapDebug.py -- this is
                # what actually decides snap/rotate/glitch-flag for this frame.
                # ⚠ Rotation estimator passed EXPLICITLY (2026-08-17): production
                # moved to Horn palm-only, and a recorder that silently kept the
                # old Gram-Schmidt frame would write "ground truth" that no
                # longer matches the thing being debugged.
                debug_tool.update_hands(state, hand_data_by_hand,
                                        rotation=debug_tool.PRODUCTION_ROTATION)

                hands_record = {}
                for handedness in debug_tool.TRACKED_HANDS:
                    data = hand_data_by_hand[handedness]
                    if data is None:
                        hands_record[handedness] = {"detected": False}
                    else:
                        hands_record[handedness] = _hand_frame_record(
                            handedness, state, data["pixel_landmarks"], data["world_landmarks"],
                            scores_by_hand[handedness], data["thumb_outward"],
                        )
                frames.append({"timestamp_ms": timestamp_ms, "hands": hands_record})

                for handedness, normalized in normalized_by_hand.items():
                    data = hand_data_by_hand[handedness]
                    debug_tool._draw_hand(
                        frame, normalized, handedness, data["thumb_outward"],
                        state.thumb_outward_snap_allowed[handedness],
                        state.last_hand_reliability_alpha[handedness], width, height,
                    )
                debug_tool._draw_cubes(frame, state)
                for name, cube in state.cubes.items():
                    debug_tool._draw_orientation_gizmo(frame, cube, state.cube_center(name))

                remaining = args.duration - elapsed
                cv2.putText(frame, f"REC - {remaining:.1f}s left - frames: {len(frames)}", (10, 30),
                            cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.imshow(window_name, frame)
                cv2.waitKey(1)
                if not _window_open(window_name):
                    break

                timestamp_ms += 33
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not frames:
        print("[RecordRotationDebug] No frames captured, nothing saved.")
        return

    out_name = f"rotation_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path = os.path.join(RECORDINGS_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"duration_s": args.duration, "frames": frames}, f)

    print(f"[RecordRotationDebug] Saved {len(frames)} frames to {out_path}")


if __name__ == "__main__":
    main()
