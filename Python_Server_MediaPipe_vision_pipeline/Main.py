import cv2
import sys
import os
import json
import subprocess
import importlib.util
import time

from inference import load_models, run_inference_on_frame
from Server import Start_socket_server as StartServer
from Server import SendPacket as SendPacketThroughSocket
from utils_for_output_data_formatting import (
    flatten_face_keypoints,
    flatten_hand_keypoints,
    extract_hand_by_type
)


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
    
    #show in display
    cv2.imshow("Hands & Face Detection", annotatedImage)

    if cv2.waitKey(1) & 0xFF == ord('q'):   
        break

    # Process Face Keypoints
    flat_face_coords = flatten_face_keypoints(facekeypointsCoordinates)

    # Process Hand Keypoints
    left_landmarks = extract_hand_by_type(allHandsLandmarksCoordinatesArray, "Left")
    right_landmarks = extract_hand_by_type(allHandsLandmarksCoordinatesArray, "Right")

    flat_hands_coords = (
        flatten_hand_keypoints(left_landmarks) +
        flatten_hand_keypoints(right_landmarks)
    )


    # Save to JSON
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "facekeypointsCoordinates.json"), "w") as f:
        json.dump(flat_face_coords, f, indent=2)

    with open(os.path.join(base_dir, "handskeypointsCoordinates.json"), "w") as f:
        json.dump(flat_hands_coords, f, indent=2)

    #print(f"[Main] Saved flattened hands keypoints to {handskeypointsCoordinates_output_path}")


    # Send via Socket
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
