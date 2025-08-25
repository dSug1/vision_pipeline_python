import cv2
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from Resources.facevisualizer import visualize, extract_facekeypoint_coordinates
from Resources.hands_visualizer import draw_landmarks_on_image


def load_models():


    # Get absolute path to the model relative to inference.py
    model_dir = os.path.dirname(os.path.abspath(__file__))

    # Load face model
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
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    #face results
    face_result = face_detector.detect(mp_image)
    frame_with_faces = visualize(frame, face_result)
    facekeypoint_coords = extract_facekeypoint_coordinates(face_result, frame.shape)

    #hands results
    hand_result = hand_detector.detect_for_video(mp_image, timestamp_ms)
    frame_with_hands, allhandslandmarkscoordinatesarray = draw_landmarks_on_image(frame.shape,rgb_frame, hand_result)

    combined = cv2.addWeighted(frame_with_faces, 0.5,
                               cv2.cvtColor(frame_with_hands, cv2.COLOR_RGB2BGR), 0.5, 0)
    return combined, facekeypoint_coords, allhandslandmarkscoordinatesarray

