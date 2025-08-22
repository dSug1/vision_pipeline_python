import cv2
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
import numpy as np
from facevisualizer import _normalized_to_pixel_coordinates as _normalized_to_px_coords

MARGIN = 10  # pixels
FONT_SIZE = 1
FONT_THICKNESS = 1
HANDEDNESS_TEXT_COLOR = (88, 205, 54) # vibrant green

def draw_landmarks_on_image(frame_image_shape, rgb_image, detection_result):
  hand_landmarks_list = detection_result.hand_landmarks
  handedness_list = detection_result.handedness
  annotated_image = np.copy(rgb_image)
  height, width = frame_image_shape[:2]
  all_hands_coords = []
  landmarkscoordinatesArray = []




  # Loop through the detected hands to visualize.
  for idx in range(len(hand_landmarks_list)):
    hand_landmarks = hand_landmarks_list[idx]
    handedness = handedness_list[idx]

    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()     # Prepare protobuf for drawing
    handslandmarks_coords = []  # This will store the extracted coordinates

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

    # Draw handedness (left or right hand) on the image.
    cv2.putText(annotated_image, f"{handedness[0].category_name}",
                (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX,
                FONT_SIZE, HANDEDNESS_TEXT_COLOR, FONT_THICKNESS, cv2.LINE_AA)

    # Append to full list
    all_hands_coords.append({
            "handedness": handedness[0].category_name,
            "landmarks": handslandmarks_coords
        })

  return annotated_image, all_hands_coords
