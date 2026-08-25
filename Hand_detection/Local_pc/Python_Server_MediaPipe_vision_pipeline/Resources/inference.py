import cv2
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from Resources.facevisualizer import visualize, extract_facekeypoint_coordinates
from Resources.hands_visualizer import draw_landmarks_on_image


def load_models(with_face=True):
    """⚠⚠ `with_face` EXISTS BECAUSE OF AN AUDIT FINDING (2026-08-25), and the
    default preserves today's behaviour rather than acting on it.

    **The face detector runs on every frame, its keypoints are serialised and sent
    over the socket, and the client throws them away** —
    `PythonApp_Main.receive_float_array` has `elif datatype == "face": pass`. It is
    a leftover of Part Zero's cursor-control experiment; `CursorController.py` is
    likewise defined and imported by nothing.

    Three reasons it is worth switching off, and one reason it was not switched
    off here:
      * ⭐ **PRIVACY SURFACE.** Since the audience was decided as ALL PUBLIC
        INCLUDING YOUTH (2026-08-23), COPPA/GDPR-K are live and "what biometric
        processing does this app perform" is a disclosure question with a
        different answer depending on whether a FACE detector runs. Running one
        for no consumer is the worst version of that trade.
      * ⚠ **IT IS ALSO A DEBUG/PRODUCTION DIVERGENCE**: `LiveSnapDebug.py` has no
        face detector at all, so the two pipelines differ in what they load, what
        they compute per frame, and what the preview shows.
      * a whole model inference per frame, for nothing. ⚠ Do NOT expect a frame
        rate win: the capture rate was measured **camera-bound, not
        compute-bound** (64.1 vs 64.0 ms with and without a hand in view).
      * ⛔ **BUT TURNING IT OFF IS A VISIBLE CHANGE** — the preview loses the face
        overlay and the `face` wire packet stops — so it is the owner's call, not
        an audit's. Default ON = nothing changes; `--face off` when decided.
    """
    # Get absolute path to the model relative to inference.py
    model_dir = os.path.dirname(os.path.abspath(__file__))

    # Load face model
    face_detector = None
    if with_face:
        face_model_path = os.path.join(model_dir, "facedetector.tflite")
        face_base = python.BaseOptions(model_asset_path=face_model_path)
        face_options = vision.FaceDetectorOptions(base_options=face_base)
        face_detector = vision.FaceDetector.create_from_options(face_options)

    # Load hand model in VIDEO mode
    hand_model_path = os.path.join(model_dir, "hand_landmarker.task")
    hand_base = python.BaseOptions(model_asset_path=hand_model_path)
    hand_options = vision.HandLandmarkerOptions(
        base_options=hand_base,
        num_hands=2,
        running_mode=vision.RunningMode.VIDEO
    )
    hand_detector = vision.HandLandmarker.create_from_options(hand_options)

    return face_detector, hand_detector

def run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms):
    """⚠ `face_detector` may be None (`load_models(with_face=False)`), in which
    case no face model runs, no face keypoints are produced, and the preview shows
    the hand overlay alone -- at full brightness rather than blended 50/50 with a
    second copy of the frame."""
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    #hands results
    hand_result = hand_detector.detect_for_video(mp_image, timestamp_ms)
    frame_with_hands, allhandslandmarkscoordinatesarray = draw_landmarks_on_image(frame.shape,rgb_frame, hand_result)
    hands_bgr = cv2.cvtColor(frame_with_hands, cv2.COLOR_RGB2BGR)

    if face_detector is None:
        return hands_bgr, [], allhandslandmarkscoordinatesarray

    #face results
    face_result = face_detector.detect(mp_image)
    frame_with_faces = visualize(frame, face_result)
    facekeypoint_coords = extract_facekeypoint_coordinates(face_result, frame.shape)

    combined = cv2.addWeighted(frame_with_faces, 0.5, hands_bgr, 0.5, 0)
    return combined, facekeypoint_coords, allhandslandmarkscoordinatesarray

