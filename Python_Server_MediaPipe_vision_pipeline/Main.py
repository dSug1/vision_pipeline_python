import sys
import os
import json
import subprocess
import importlib.util


# Ensure mediapipe is installed
def ensure_mediapipe():
    package_name = "mediapipe"
    if importlib.util.find_spec(package_name) is None:
        print(f"{package_name} not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
    else:
        print(f"{package_name} is already installed.")

ensure_mediapipe()

# Ensure OpenCV is installed
def ensure_opencv():
    package_import_name = "cv2"
    package_pip_name = "opencv-python"
    if importlib.util.find_spec(package_import_name) is None:
        print(f"{package_import_name} not found. Installing {package_pip_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_pip_name])
    else:
        print(f"{package_import_name} is already installed.")

ensure_opencv()

import cv2
import time

from inference import load_models, run_inference_on_frame
from Server import Start_socket_server as StartServer
from Server import SendPacket as SendPacketThroughSocket


# Load models
face_detector, hand_detector = load_models()

# Start webcam
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam.")

# Start socket server
connection, address, server = StartServer('127.0.0.1', 5050)
connection_alive = True

# Run inference and write keypoints coordinates in json files
timestamp_ms = 0

while True:
    ret, frame = cap.read()
    if not ret or not connection_alive:
        break

    annotatedImage, facekeypointsCoordinates, allHandsLandmarksCoordinatesArray = run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms)
    
    cv2.imshow("Hands & Face Detection", annotatedImage)

    if cv2.waitKey(1) & 0xFF == ord('q'):   #add the condition "& if the connection breaks"
        break

    # Serialize facekeypoints_coords and write to a JSON file
    # Flatten face keypoints into [x1, y1, x2, y2, ...]
    flat_face_coords = []

    for point_index, point in enumerate(facekeypointsCoordinates):
        if isinstance(point, dict):
            try:
                x = int(float(point.get("x", 0)))
                y = int(float(point.get("y", 0)))
                flat_face_coords.extend([x, y])
            except (ValueError, TypeError):
                flat_face_coords.extend([0, 0])
        else:
            print(f"[Warning] Unexpected face point format at index {point_index}: {point}")
            flat_face_coords.extend([0, 0])



    # Serialize and write to JSON
    facekeypointsCoordinates_output_path = os.path.join(os.path.dirname(__file__), "facekeypointsCoordinates.json")
    with open(facekeypointsCoordinates_output_path, "w") as f:
        json.dump(flat_face_coords, f, indent=2)

    #print(f"[Main] Saved flattened face keypoints to {facekeypointsCoordinates_output_path}")


    # Serialize handslandmarks and write to a JSON file
    def zero_landmarks_flat():
        return [0] * 42 * 2  # 42 per hand × 2 hands

    def flatten_landmarks(landmarks):
        flat = []
        for lm in landmarks:
            if isinstance(lm, dict):
                try:
                    x = int(float(lm.get("x_px", 0)))
                    y = int(float(lm.get("y_px", 0)))
                    flat.extend([x, y])
                except (ValueError, TypeError):
                    flat.extend([0, 0])
            else:
                flat.extend([0, 0])
        return flat

    left_hand = next((hand for hand in allHandsLandmarksCoordinatesArray if hand.get("handedness") == "Left"), None)
    right_hand = next((hand for hand in allHandsLandmarksCoordinatesArray if hand.get("handedness") == "Right"), None)

    left_landmarks = left_hand.get("landmarks", []) if left_hand else []
    right_landmarks = right_hand.get("landmarks", []) if right_hand else []

    left_valid = len(left_landmarks) == 21
    right_valid = len(right_landmarks) == 21

    left_output = flatten_landmarks(left_landmarks) if left_valid else [0] * 42
    right_output = flatten_landmarks(right_landmarks) if right_valid else [0] * 42

    flat_hands_coords = left_output + right_output

    # Serialize and write to JSON
    handskeypointsCoordinates_output_path = os.path.join(os.path.dirname(__file__), "handskeypointsCoordinates.json")
    with open(handskeypointsCoordinates_output_path, "w") as f:
        json.dump(flat_hands_coords, f, indent=2)

    #print(f"[Main] Saved flattened hands keypoints to {handskeypointsCoordinates_output_path}")



    try:
        SendPacketThroughSocket("facekeypointsCoordinates.json", "handskeypointsCoordinates.json", connection)
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"[Main] Socket connection lost: {e}")
        connection_alive = False
        break

    timestamp_ms += 33  # ~30 FPS

cap.release()
cv2.destroyAllWindows()
connection.close()
server.close()
print("[Socket Server] Connection closed.")
