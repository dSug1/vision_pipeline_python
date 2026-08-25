import argparse
import os

# ⚠ MOVED 2026-08-25 out of the app root. This file's own directory is no
# longer the app root, so every path that used to resolve from `__file__`
# now goes one level up. Behaviour is unchanged; only the anchor moved.
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import time
from collections import deque

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from Resources import classifier, event_layer, features
from tune_event_layer import WINDOWED_REPRESENTATIONS

# Stage 4 of Claude/GESTURE_PIPELINE_SPEC.md: live webcam debug tool. Opens
# the webcam, runs MediaPipe HandLandmarker, loads the trained pinch
# classifier's exported weights (Resources/pinch_classifier_weights.json,
# currently mlp/raw_plus_handcrafted_plus_articulation, §3.2.10), computes
# the forward pass per hand per frame, and displays the CONTINUOUS
# confidence value (not just a boolean) plus the event layer's onset/apex/
# offset state (§3.3/PinchEventTracker) live. Console-logs only on state
# transitions, not every frame.
#
# Deliberately independent of the live socket pipeline
# (VisionPipeline.py/Client.py/PythonApp_Main.py), same rationale as
# RecordSession.py: this needs no cube window and no server/client split,
# just webcam -> HandLandmarker -> model -> screen. Rebuilt from scratch
# against the current trained-model/event-layer interfaces, not resurrected
# from the deleted original -- required before pinch counts as "done" per
# the spec's own rule (§3's Stage 4 note, §8): held-out test data can't
# catch a live integration bug (e.g. MediaPipe's live result objects use
# .x/.y/.z attributes, not the {"x","y","z"} dict shape recordings use --
# features.to_dict_landmarks() handles that conversion here) or tell you
# how the classifier/event layer actually feel in real use.

HAND_LANDMARKER_MODEL_PATH = os.path.join(
    _APP_ROOT,
    "..", "Python_Server_MediaPipe_vision_pipeline", "Resources", "hand_landmarker.task",
)
WEIGHTS_PATH = os.path.join(
    _APP_ROOT, "Resources", "pinch_classifier_weights.json"
)

# Wall-clock seconds, not a frame count -- matches how DELTA_WINDOW_MS is
# defined (features.py: "~300ms", a real-time gap), and is robust to a live
# capture rate that isn't exactly the 30fps the training/tuning scripts
# assume from recorded-session duration/frame-count averages.
DELTA_WINDOW_S = features.DELTA_WINDOW_MS / 1000
HISTORY_SECONDS = 2.0  # generous margin over DELTA_WINDOW_S so a brief FPS dip never starves the delta lookup

TRACKED_HANDS = ("Left", "Right")


def _closest_past(history, target_t):
    """history: deque of (t, landmarks) ordered oldest-first. Returns the
    entry closest to target_t without going past it, or None if the buffer
    doesn't reach back that far yet (hand only just appeared -- not enough
    history for a delta feature this frame)."""
    if not history or history[0][0] > target_t:
        return None
    best = history[0]
    for entry in history:
        if entry[0] > target_t:
            break
        best = entry
    return best


class GestureHistory:
    """Rolling landmark history + pinch tracker for THIS debug tool.

    (Renamed 2026-08-21.) It was never the `HandState` contract of
    `PERCEPTION_LAYER_SPEC.md` section 2 -- it is a local history buffer --
    and the shared name would have collided with the real contract the
    moment queue D1 implements it.
    """
    def __init__(self):
        self.history = deque()  # (t_seconds, landmarks)
        self.tracker = event_layer.PinchEventTracker()

    def push(self, t, landmarks):
        self.history.append((t, landmarks))
        cutoff = t - HISTORY_SECONDS
        while self.history and self.history[0][0] < cutoff:
            self.history.popleft()


def build_detector():
    base_options = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options, num_hands=2, running_mode=vision.RunningMode.VIDEO,
    )
    return vision.HandLandmarker.create_from_options(options)


def predict_confidence(model, representation, handedness, hand_state, now, landmarks):
    """Returns the classifier confidence for this hand this frame, or None
    if a windowed representation doesn't have enough history yet."""
    if representation not in WINDOWED_REPRESENTATIONS:
        return classifier.predict_from_landmarks(model, landmarks, handedness=handedness)

    past_entry = _closest_past(hand_state.history, now - DELTA_WINDOW_S)
    if past_entry is None:
        return None
    _, past_landmarks = past_entry
    if representation == "raw_plus_handcrafted_plus_articulation":
        x = features.extract_raw_plus_handcrafted_plus_articulation_features(
            past_landmarks, landmarks, handedness=handedness
        )
    else:
        raise ValueError(f"predict_confidence: unsupported windowed representation {representation!r}")
    return classifier.predict_from_features(model, x)


def _draw_hand_points(frame, normalized_landmarks, width, height, color):
    for lm in normalized_landmarks:
        cv2.circle(frame, (int(lm.x * width), int(lm.y * height)), 3, color, -1, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description="Stage 4 live pinch-classifier/event-layer debug tool.")
    parser.add_argument("--camera-index", type=int, default=0, help="cv2.VideoCapture device index (default 0)")
    args = parser.parse_args()

    model = classifier.load(WEIGHTS_PATH)
    representation = model["representation"]
    print(f"[LiveGestureDebug] Loaded model: representation={representation!r}, architecture={model['architecture']!r}")

    detector = build_detector()

    # Same DSHOW backend as RecordSession.py/VisionPipeline.py -- the default
    # MSMF backend can hang for a long time on open, especially after a
    # prior run didn't release the device cleanly.
    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). Is another program using the camera?")

    hand_states = {handedness: GestureHistory() for handedness in TRACKED_HANDS}
    window_name = "Live gesture debug (Stage 4)"
    start_time = time.time()

    print("[LiveGestureDebug] Running -- press 'q' or close the window to stop.")
    print("[LiveGestureDebug] Onset/offset events are logged below as they fire; per-frame confidence is overlaid on the video.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            now = time.time() - start_time
            timestamp_ms = int(now * 1000)  # real elapsed time, not an assumed-fps increment -- also satisfies VIDEO mode's monotonic-timestamp requirement
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = detector.detect_for_video(mp_image, timestamp_ms)

            height, width = frame.shape[:2]

            for idx in range(len(result.hand_landmarks)):
                handedness = result.handedness[idx][0].category_name
                if handedness not in hand_states:
                    continue

                color = (255, 120, 0) if handedness == "Left" else (0, 0, 255)
                _draw_hand_points(frame, result.hand_landmarks[idx], width, height, color)

                landmarks = features.to_dict_landmarks(result.hand_world_landmarks[idx])
                state = hand_states[handedness]

                conf = predict_confidence(model, representation, handedness, state, now, landmarks)
                state.push(now, landmarks)

                line_y = 30 if handedness == "Left" else 60
                if conf is None:
                    cv2.putText(
                        frame, f"{handedness}: warming up...",
                        (10, line_y), cv2.FONT_HERSHEY_DUPLEX, 0.7, (200, 200, 200), 2, cv2.LINE_AA,
                    )
                    continue

                ratio = features.pinch_ratio(landmarks)
                new_state, onset_event, offset_event = state.tracker.update(conf, ratio)
                if onset_event:
                    print(f"[LiveGestureDebug] {handedness}: ONSET  (confidence={conf:.2f}, pinch_ratio={ratio:.2f})")
                if offset_event:
                    print(f"[LiveGestureDebug] {handedness}: OFFSET (confidence={conf:.2f}, pinch_ratio={ratio:.2f})")

                text_color = (0, 200, 0) if new_state == "apex" else (0, 165, 255)
                cv2.putText(
                    frame, f"{handedness}: conf={conf:.2f} ratio={ratio:.2f} state={new_state}",
                    (10, line_y), cv2.FONT_HERSHEY_DUPLEX, 0.7, text_color, 2, cv2.LINE_AA,
                )

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[LiveGestureDebug] Stopped, camera released.")


if __name__ == "__main__":
    main()
