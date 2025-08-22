import json
import os

def extract_landmark_array(json_file_path):
    def zero_landmarks_flat():
        return [0] * 42 * 2  # 42 landmarks × 2 coordinates

    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)

        if not data or not isinstance(data, list):
            return zero_landmarks_flat()

        # Extract hands
        left_hand = next((hand for hand in data if hand.get("handedness") == "Left"), None)
        right_hand = next((hand for hand in data if hand.get("handedness") == "Right"), None)

        # Validate and extract landmarks
        left_landmarks = left_hand.get("landmarks", []) if left_hand else []
        right_landmarks = right_hand.get("landmarks", []) if right_hand else []

        left_valid = len(left_landmarks) == 21
        right_valid = len(right_landmarks) == 21

        def flatten_landmarks(landmarks):
            flat = []
            for lm in landmarks:
                try:
                    x = int(float(lm.get("x_px", 0)))
                    y = int(float(lm.get("y_px", 0)))
                    flat.extend([x, y])
                except (ValueError, TypeError):
                    flat.extend([0, 0])
            return flat

        left_output = flatten_landmarks(left_landmarks) if left_valid else [0] * 42
        right_output = flatten_landmarks(right_landmarks) if right_valid else [0] * 42

        return left_output + right_output

    except (json.JSONDecodeError, FileNotFoundError, TypeError) as e:
        print(f"Error reading or parsing file: {e}")
        return zero_landmarks_flat()
