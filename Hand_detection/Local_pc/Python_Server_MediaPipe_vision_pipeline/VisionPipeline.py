import cv2
import argparse

from Resources import capture_policy
from Resources.inference import load_models, run_inference_on_frame
from Resources.Server import Start_socket_server as StartServer
from Resources.Server import SendPacket as SendPacketThroughSocket
from Resources.Server import SendMetaPacket as SendMetaPacketThroughSocket
from Resources.Server import SendHandsWorldPacket as SendHandsWorldPacketThroughSocket
from Resources.Server import SendHandTracksPacket as SendHandTracksPacketThroughSocket
from Resources.utils_for_remapping_coordinates_and_output_formatting import (
    remap_keypoints,
    remap_world_keypoints,
    extract_hand_track_id,
    extract_hand_by_type,
    extract_hand_world_by_type
)


# Parse arguments
parser = argparse.ArgumentParser(description="Run vision inference and socket server.")
parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
parser.add_argument("--port", type=int, default=5050, help="Server port")
# ⛔ See `Resources/Server.py`: this socket carries live hand and face landmarks,
# and the build's privacy position depends on that stream staying on the machine.
# Binding off-loopback is refused unless this is passed DELIBERATELY.
parser.add_argument("--allow-remote", action="store_true",
                    help="Permit a non-loopback --host. This TRANSMITS landmarks; "
                         "read Server.py's header before using it.")
# ⚠ The face detector runs every frame and NOTHING consumes its output (the
# client's dispatch is `elif datatype == "face": pass`). Default ON preserves
# today's behaviour; `--face off` stops loading the model, computing it and
# putting it on the wire. Full reasoning: `Resources/inference.load_models`.
parser.add_argument("--face", choices=("on", "off"), default="on",
                    help="Run the (currently unconsumed) face detector. Default on.")
args = parser.parse_args()
FACE_ENABLED = args.face == "on"


# Start socket server
connection, address, server = StartServer(args.host, args.port, args.allow_remote)
connection_alive = True

# Load models. Dependencies (mediapipe, opencv) are managed via requirements.txt
# and the project's .venv — no runtime pip install.
face_detector, hand_detector = load_models(with_face=FACE_ENABLED)
if not FACE_ENABLED:
    print("[Main] face detection OFF -- no face model, no face packet.")

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
# guessing (see Hand_detection/Claude/PART_ZERO.md).
ret, frame, _ = capture_policy.read_frame(cap)   # retries a cold-start stall
if not ret:
    raise RuntimeError("Could not read an initial frame from the webcam.")
# MIRROR BEFORE DETECTION (2026-08-22, spec 14.3.4.3). This frame is NOT just a
# size probe: the loop below consumes it before reading the next one, so it
# reaches inference and must be mirrored like every other frame.
frame = cv2.flip(frame, 1)
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
    # invert_x=False: the FRAME was mirrored before detection (spec 14.3.4.3), so
    # these coordinates are already in the mirrored/selfie frame. Mirroring again
    # would put face keypoints back into the un-mirrored frame -- the exact
    # double-flip class M5d warns about (an EVEN number of flips still "works",
    # an odd number inverts).
    flat_face_coords = remap_keypoints(
        facekeypointsCoordinates,
        width,
        height,
        expected_count=6,
        invert_x=False,
    )

    # Process hands landmarks: 21 keypoints per hand × 2 = 42 values per hand
    left_landmarks = extract_hand_by_type(allHandsLandmarksCoordinatesArray, "Left")
    right_landmarks = extract_hand_by_type(allHandsLandmarksCoordinatesArray, "Right")
    flat_hands_coords = (
        remap_keypoints(left_landmarks, width, height, x_key="x_px", y_key="y_px",
                        expected_count=21, invert_x=False) +
        remap_keypoints(right_landmarks, width, height, x_key="x_px", y_key="y_px",
                        expected_count=21, invert_x=False)
    )

    # World landmarks (metric, hand-relative 3D) -- added for rotation-while-
    # snapped (Claude/GESTURE_PIPELINE_SPEC.md §13.7). 21 x/y/z per hand x 2
    # hands = 126 floats.
    left_world_landmarks = extract_hand_world_by_type(allHandsLandmarksCoordinatesArray, "Left")
    right_world_landmarks = extract_hand_world_by_type(allHandsLandmarksCoordinatesArray, "Right")
    flat_hands_world_coords = (
        remap_world_keypoints(left_world_landmarks, expected_count=21, invert_x=False) +
        remap_world_keypoints(right_world_landmarks, expected_count=21, invert_x=False)
    )

    # Stable DR-1 track ids for the two slots (4.1 / T3). Two ints, same slot
    # order as every other hands packet: [Left, Right]. -1 = slot empty.
    hand_track_ids = [
        extract_hand_track_id(allHandsLandmarksCoordinatesArray, "Left"),
        extract_hand_track_id(allHandsLandmarksCoordinatesArray, "Right"),
    ]

    # Send the in-memory coordinates straight over the socket (no disk round-trip).
    try:
        # hands_world sent BEFORE hands -- see SendHandsWorldPacket's
        # docstring for why the order matters.
        SendHandTracksPacketThroughSocket(hand_track_ids, connection)
        SendHandsWorldPacketThroughSocket(flat_hands_world_coords, connection)
        SendPacketThroughSocket(flat_face_coords, flat_hands_coords, connection,
                                send_face=FACE_ENABLED)
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        print(f"[Main] Socket connection lost: {e}")
        connection_alive = False
        break

    timestamp_ms += 33  # ~30 FPS

    # ⭐ A transient stall no longer ends the session (audit 2026-08-25). Shared
    # policy with the debug tool -- `Resources/capture_policy.py`, N6.
    ret, frame, _retries = capture_policy.read_frame(cap)
    if not ret:
        print(capture_policy.give_up_message("Main"))
        break
    if _retries:
        print(f"[Main] camera recovered after {_retries} failed read(s)")
    frame = cv2.flip(frame, 1)   # mirror BEFORE detection -- spec 14.3.4.3
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
