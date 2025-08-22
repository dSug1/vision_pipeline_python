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

# Run inference and write keypoints coordinates in json files
timestamp_ms = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    annotatedImage, facekeypointsCoordinates, allHandsLandmarksCoordinatesArray = run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms)
    
    cv2.imshow("Hands & Face Detection", annotatedImage)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    # Serialize facekeypoints_coords and write to a JSON file
    handskeypoints_serialized_coords = json.dumps(allHandsLandmarksCoordinatesArray, indent=2)
    handskeypointsCoordinates_output_path = os.path.join(os.path.dirname(__file__), "handskeypointsCoordinates.json")
    with open(handskeypointsCoordinates_output_path, "w") as f:
        f.write(handskeypoints_serialized_coords)

    # Serialize handslandmarks and write to a JSON file
    facekeypoints_serialized_coords = json.dumps(facekeypointsCoordinates, indent=2)
    facekeypointsCoordinates_output_path = os.path.join(os.path.dirname(__file__), "facekeypointsCoordinates.json")
    with open(facekeypointsCoordinates_output_path, "w") as f:
        f.write(facekeypoints_serialized_coords)

    SendPacketThroughSocket("facekeypointsCoordinates.json", connection)

    timestamp_ms += 33  # ~30 FPS

cap.release()
cv2.destroyAllWindows()
connection.close()
server.close()
print("[Socket Server] Connection closed.")
