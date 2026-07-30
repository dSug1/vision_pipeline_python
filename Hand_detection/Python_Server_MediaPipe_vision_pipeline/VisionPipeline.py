import cv2
import argparse

from Resources.inference import load_models, run_inference_on_frame
from Resources.Server import Start_socket_server as StartServer
from Resources.Server import SendPacket as SendPacketThroughSocket
from Resources.Server import SendMetaPacket as SendMetaPacketThroughSocket
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

# Load models. Dependencies (mediapipe, opencv) are managed via requirements.txt
# and the project's .venv — no runtime pip install.
face_detector, hand_detector = load_models()

# Start webcam.
# Use the DirectShow backend (CAP_DSHOW) explicitly: the default MSMF backend on
# Windows can hang for a very long time on open — especially if a previous run
# was killed without releasing the device.
WINDOW_NAME = "Hands & Face Detection"
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam (index 0). Is another program using the camera?")

# Read one frame up front purely to learn the webcam's actual capture
# resolution (cap.get(CAP_PROP_FRAME_WIDTH/HEIGHT) can report 0 or a stale
# value before the first frame is pulled, especially on CAP_DSHOW) and tell
# the client, so it can size its consumer to the real resolution instead of
# guessing (see Claude/PART_ZERO.md).
ret, frame = cap.read()
if not ret:
    raise RuntimeError("Could not read an initial frame from the webcam.")
height, width = frame.shape[:2]
try:
    SendMetaPacketThroughSocket(width, height, connection)
except (BrokenPipeError, ConnectionResetError, OSError) as e:
    print(f"[Main] Socket connection lost while sending meta packet: {e}")
    connection_alive = False

# Run inference and write keypoints coordinates in json files
timestamp_ms = 0

try:
  while connection_alive:
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


    # Send the in-memory coordinates straight over the socket (no disk round-trip).
    try:
        SendPacketThroughSocket(flat_face_coords, flat_hands_coords, connection)
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"[Main] Socket connection lost: {e}")
        connection_alive = False
        break

    timestamp_ms += 33  # ~30 FPS

    ret, frame = cap.read()
    if not ret:
        break
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
