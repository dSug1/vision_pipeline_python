import sys
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

import cv2
import time

from .inference import load_models, run_inference_on_frame

# Load models
face_detector, hand_detector = load_models()

# Start webcam
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam.")

timestamp_ms = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    annotated = run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms)
    cv2.imshow("Hands & Face Detection", annotated)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    timestamp_ms += 33  # ~30 FPS

cap.release()
cv2.destroyAllWindows()
