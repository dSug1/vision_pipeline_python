import cv2
import argparse
import sys
import os
import json
import subprocess
import importlib.util
import time

from Resources.inference import load_models, run_inference_on_frame
from Resources.Server import Start_socket_server as StartServer
from Resources.Server import SendPacket as SendPacketThroughSocket
from Resources.utils_for_remapping_coordinates_and_output_formatting import (
    remap_keypoints,
    extract_hand_by_type
)


# Parse arguments
parser = argparse.ArgumentParser(description="Run vision inference and socket server.")
parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
parser.add_argument("--port", type=int, default=5050, help="Server port")
args = parser.parse_args()


# Start socket server
connection, address, server = StartServer(args.host, args.port)
connection_alive = True

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

# Start webcam.
# Use the DirectShow backend (CAP_DSHOW) explicitly: the default MSMF backend on
# Windows can hang for a very long time on open — especially if a previous run
# was killed without releasing the device.
WINDOW_NAME = "Hands & Face Detection"
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam (index 0). Is another program using the camera?")


# Run inference and write keypoints coordinates in json files
timestamp_ms = 0

try:
  while True:
    ret, frame = cap.read()
    if not ret or not connection_alive:
        break

    height, width = frame.shape[:2]

    annotatedImage, facekeypointsCoordinates, allHandsLandmarksCoordinatesArray = run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms)

    #show in display
    cv2.imshow(WINDOW_NAME, annotatedImage)

    # Stop on 'q' OR when the preview window is closed with the X button.
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
        break

    # Process face keypoints: 6 keypoints × 2 = 12 values
    flat_face_coords = remap_keypoints(
        facekeypointsCoordinates,
        width,
        height,
        expected_count=6
    )

    # Process hands landmarks: 21 keypoints per hand × 2 = 42 values per hand
    left_landmarks = extract_hand_by_type(allHandsLandmarksCoordinatesArray, "Left")
    right_landmarks = extract_hand_by_type(allHandsLandmarksCoordinatesArray, "Right")
    flat_hands_coords = (
        remap_keypoints(left_landmarks, width, height, x_key="x_px", y_key="y_px", expected_count=21) +
        remap_keypoints(right_landmarks, width, height, x_key="x_px", y_key="y_px", expected_count=21)
    )


    # Save to JSON
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "Resources", "facekeypointsCoordinates.json"), "w") as f:
        json.dump(flat_face_coords, f, indent=2)

    with open(os.path.join(base_dir, "Resources", "handskeypointsCoordinates.json"), "w") as f:
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
finally:
    # Always release the camera and sockets, even on exception / interrupt,
    # so the device is never left in a stuck state for the next run.
    cap.release()
    cv2.destroyAllWindows()
    try:
        connection.close()
    except Exception:
        pass
    try:
        server.close()
    except Exception:
        pass
    print("[Socket Server] Connection closed.")
