import argparse
import json
import os
import time
from datetime import datetime

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Ad hoc diagnostic recorder for the translation-pivot fix
# (GESTURE_PIPELINE_SPEC.md §14.1, HANDOFF_SNAP_ROTATE_RELEASE.md §2.1),
# built 2026-08-01 per direct request to verify the distance-weighted
# live-landmark translation mechanism against real grab+rotate data before
# implementing it in the debug tool / production.
#
# Same lineage as RecordRotationDebug.py: imports CubeState/update_hands
# from LiveSnapDebug.py rather than re-deriving them, so this records
# EXACTLY what that tool's REAL, already-working snap/translate logic
# produces -- including real grab events (owner transitions) and the
# cube's real per-frame center, which the offline analysis
# (AnalyzeTranslationPivot.py) uses as ground truth for "where the object
# was at the moment of grab." No synthetic/simulated object position is
# needed: the user grabs a real cube (large or small) via the already
# live-verified proximity-snap system, and the analysis script reads the
# grab instant and position directly off the recording.
#
# Unlike RecordRotationDebug.py, this ALSO logs each cube's per-frame
# owner/center/size (RecordRotationDebug.py only logged orientation,
# since it wasn't testing a translation fix) -- that's the only structural
# difference from that file's schema.
import LiveSnapDebug as debug_tool

# Saved to the external-drive corpus location (direct request 2026-08-01),
# not locally like RecordRotationDebug.py's one-off diagnostic dump was --
# these sessions are meant to be kept/reusable, same convention as
# RecordSession.py's training corpus.
RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Position_during_rotation"

DEFAULT_DURATION_S = 12.0
COUNTDOWN_S = 3.0


def _pixel_landmarks(normalized, width, height):
    return [(lm.x * width, lm.y * height) for lm in normalized]


def _world_landmarks(world_lms):
    return [(lm.x, lm.y, lm.z) for lm in world_lms]


def _window_open(window_name: str) -> bool:
    return cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) >= 1


def _hand_frame_record(pixel_landmarks, world_landmarks, score, thumb_outward, held_cube):
    return {
        "detected": True,
        "score": score,
        "pixel_landmarks": [[round(x, 2), round(y, 2)] for x, y in pixel_landmarks],
        "world_landmarks": [[round(x, 5), round(y, 5), round(z, 5)] for x, y, z in world_landmarks],
        "thumb_outward": thumb_outward,
        "held_cube": held_cube,
    }


def _cubes_record(state: "debug_tool.CubeState"):
    # Ground truth the offline analysis anchors to: the REAL cube center
    # LiveSnapDebug.py's already-working (pre-fix) snap/translate logic
    # produced this frame -- at the exact frame a cube's owner first
    # becomes non-None, this IS "the object's position at the moment of
    # grab" (today's zero-offset design snaps the cube onto the hand
    # anchor the same frame it's claimed -- see §14.1's root-cause
    # analysis), which is exactly the ground truth the new distance-
    # weighted mechanism needs to be tested against.
    return {
        name: {
            "owner": cube.owner,
            "center": [round(c, 2) for c in state.cube_center(name)],
            "size": cube.size,
        }
        for name, cube in state.cubes.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record full per-frame landmark + real cube ownership/position data, "
        "for offline verification of the §14.1 distance-weighted translation mechanism."
    )
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S, help=f"Recording duration in seconds (default {DEFAULT_DURATION_S})")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument(
        "--label", type=str, default="session",
        help="Free-text label for the filename only (e.g. 'large_pos1', 'small_pos2') -- "
        "purely organizational, the actual grabbed cube/position is read from the recording itself.",
    )
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

    window_name = "Translation-pivot debug recording"
    frames = []
    timestamp_ms = 0

    print(
        f"[RecordTranslationPivotDebug] Get ready -- recording starts in {COUNTDOWN_S:.0f}s, "
        f"then captures for {args.duration:.1f}s automatically. Grab a cube (either size), "
        f"then rotate your wrist in place -- try to keep the hand's overall position still, "
        f"only twisting -- for as much of the recording as you can. Run this multiple times "
        f"across different real hand positions and for both cube sizes (use --label to keep "
        f"them organized)."
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

                # Drives the SAME state/logic as LiveSnapDebug.py -- real
                # snap/translate/rotate happens here, exactly as it would
                # live. This is what makes the recorded cube centers real
                # ground truth rather than a simulation.
                debug_tool.update_hands(state, hand_data_by_hand)

                hands_record = {}
                for handedness in debug_tool.TRACKED_HANDS:
                    data = hand_data_by_hand[handedness]
                    if data is None:
                        hands_record[handedness] = {"detected": False}
                    else:
                        hands_record[handedness] = _hand_frame_record(
                            data["pixel_landmarks"], data["world_landmarks"],
                            scores_by_hand[handedness], data["thumb_outward"],
                            state.cube_owned_by(handedness),
                        )
                frames.append({
                    "timestamp_ms": timestamp_ms,
                    "hands": hands_record,
                    "cubes": _cubes_record(state),
                })

                for handedness, normalized in normalized_by_hand.items():
                    data = hand_data_by_hand[handedness]
                    debug_tool._draw_hand(
                        frame, normalized, handedness, data["thumb_outward"],
                        state.thumb_outward_snap_allowed[handedness],
                        state.last_hand_reliability_alpha[handedness], width, height,
                    )
                debug_tool._draw_cubes(frame, state)

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
        print("[RecordTranslationPivotDebug] No frames captured, nothing saved.")
        return

    out_name = f"translation_pivot_{args.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path = os.path.join(RECORDINGS_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"duration_s": args.duration, "label": args.label, "frames": frames}, f)

    print(f"[RecordTranslationPivotDebug] Saved {len(frames)} frames to {out_path}")


if __name__ == "__main__":
    main()
