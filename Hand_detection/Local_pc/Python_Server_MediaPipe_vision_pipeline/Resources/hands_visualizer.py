import cv2
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
import numpy as np
from .facevisualizer import _normalized_to_pixel_coordinates as _normalized_to_px_coords

MARGIN = 10  # pixels
FONT_SIZE = 1
FONT_THICKNESS = 1
HANDEDNESS_TEXT_COLOR = (88, 205, 54) # vibrant green

# Mirror-consistent handedness (2026-08-01, direct request -- root-caused
# from a live bug report, not guessed). VisionPipeline.py runs MediaPipe
# detection on the RAW, un-mirrored camera frame (no cv2.flip anywhere in
# that file), but the pixel/world landmark COORDINATES get mirrored
# afterward for display consistency (utils_for_remapping_coordinates_
# and_output_formatting.py's remap_keypoints/remap_world_keypoints,
# invert_x=True). MediaPipe's own Left/Right classification assumes an
# already-mirrored ("selfie") input by convention -- fed an UN-mirrored
# frame, it reports the TRUE anatomical hand, the OPPOSITE of what the
# mirrored display shows. Left uncorrected, this silently broke any
# chirality-sensitive consumer of the handedness label: confirmed live,
# HandsTriggeredActions.py's `_is_thumb_outward` (`if handedness ==
# "Left": cross = -cross`) computed the wrong sign, inverting the
# thumb-outward/inward snap restriction in production -- opposite of the
# already-correct debug tool (LiveSnapDebug.py flips the frame BEFORE
# detection, so its handedness needs no such correction). Fixed at this
# single source, not by patching each chirality-sensitive consumer
# separately -- everything downstream (both the "hands" and "hands_world"
# packets, both keyed off this same field) inherits the fix consistently.
_MIRRORED_HANDEDNESS = {"Left": "Right", "Right": "Left"}


def _mirror_handedness(category_name):
    return _MIRRORED_HANDEDNESS.get(category_name, category_name)

def draw_landmarks_on_image(frame_image_shape, rgb_image, detection_result):
  hand_landmarks_list = detection_result.hand_landmarks
  # world_landmarks: metric, hand-relative 3D coordinates (meters), parallel
  # array to hand_landmarks -- needed for rotation-while-snapped
  # (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13.7), not previously
  # extracted here since only 2D pixel landmarks were needed before.
  hand_world_landmarks_list = detection_result.hand_world_landmarks
  handedness_list = detection_result.handedness
  annotated_image = np.copy(rgb_image)
  height, width = frame_image_shape[:2]
  all_hands_coords = []
  landmarkscoordinatesArray = []




  # Loop through the detected hands to visualize.
  for idx in range(len(hand_landmarks_list)):
    hand_landmarks = hand_landmarks_list[idx]
    hand_world_landmarks = hand_world_landmarks_list[idx]
    handedness = handedness_list[idx]
    mirrored_handedness = _mirror_handedness(handedness[0].category_name)

    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()     # Prepare protobuf for drawing
    handslandmarks_coords = []  # This will store the extracted coordinates
    # Metric hand-relative 3D coords (meters), no pixel remapping -- raw
    # x/y/z as MediaPipe returns them (mirroring/remap_keypoints only
    # applies to the pixel-space landmarks above).
    handsworldlandmarks_coords = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in hand_world_landmarks]

    for landmark in hand_landmarks:
        # Add to protobuf for drawing
        hand_landmarks_proto.landmark.append(
            landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z)
        )

        # Extract coordinates into a dictionary
        # Convert normalized coordinates to pixel coordinates
        pixel_coords = _normalized_to_px_coords(
            landmark.x, landmark.y, width, height
        )

        # Extract coordinates into a dictionary
        handslandmarks_coords.append({
            "x_px": pixel_coords[0] if pixel_coords else None,
            "y_px": pixel_coords[1] if pixel_coords else None
        })

    solutions.drawing_utils.draw_landmarks(
      annotated_image,
      hand_landmarks_proto,
      solutions.hands.HAND_CONNECTIONS,
      solutions.drawing_styles.get_default_hand_landmarks_style(),
      solutions.drawing_styles.get_default_hand_connections_style())

    # Get the top left corner of the detected hand's bounding box.
    height, width, _ = annotated_image.shape
    x_coordinates = [landmark.x for landmark in hand_landmarks]
    y_coordinates = [landmark.y for landmark in hand_landmarks]
    text_x = int(min(x_coordinates) * width)
    text_y = int(min(y_coordinates) * height) - MARGIN

    # Draw handedness (left or right hand) on the image -- the MIRRORED
    # label, so this on-screen debug text matches what a human sees of
    # their own mirrored reflection, not MediaPipe's raw (un-mirrored)
    # classification.
    cv2.putText(annotated_image, f"{mirrored_handedness}",
                (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX,
                FONT_SIZE, HANDEDNESS_TEXT_COLOR, FONT_THICKNESS, cv2.LINE_AA)

    # Append to full list
    all_hands_coords.append({
            "handedness": mirrored_handedness,
            "landmarks": handslandmarks_coords,
            "world_landmarks": handsworldlandmarks_coords
        })

  return annotated_image, all_hands_coords
