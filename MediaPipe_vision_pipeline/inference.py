import cv2
import os
import json
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from facevisualizer import visualize
from facevisualizer import extract_keypoint_coordinates
from hands_visualizer import draw_landmarks_on_image


def load_models():
    # Load face model


    #model_path = os.path.join(os.path.dirname(__file__), "facedetector.tflite")
    #face_base = python.BaseOptions(model_asset_path=model_path)
    face_base = python.BaseOptions("facedetector.tflite")
    face_options = vision.FaceDetectorOptions(base_options=face_base)
    face_detector = vision.FaceDetector.create_from_options(face_options)

    # Load hand model in VIDEO mode


    #hand_model_path = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
    #hand_base = python.BaseOptions(model_asset_path=hand_model_path)
    hand_base = python.BaseOptions("hand_landmarker.task")
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
    keypoint_coords = extract_keypoint_coordinates(face_result, frame.shape)
    # Serialize keypoints_coords and write to JSON file
    serialized_coords = json.dumps(keypoint_coords, indent=2)
    output_path = os.path.join(os.path.dirname(__file__), "facekeypoints.json")
    with open(output_path, "w") as f:
        f.write(serialized_coords)




    #hands results
    hand_result = hand_detector.detect_for_video(mp_image, timestamp_ms)
    frame_with_hands = draw_landmarks_on_image(rgb_frame, hand_result)

    combined = cv2.addWeighted(frame_with_faces, 0.5,
                               cv2.cvtColor(frame_with_hands, cv2.COLOR_RGB2BGR), 0.5, 0)
    return combined

