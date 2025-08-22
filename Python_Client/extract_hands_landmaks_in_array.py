import json
import os

def extract_landmark_array(json_path="./received_hands_data.json"):
    def zero_landmarks():
        return [{"x_px": 0, "y_px": 0} for _ in range(21)]

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        if not data or not isinstance(data, list):
            return zero_landmarks() * 2  # 42 zeroed entries

        # Extract hands
        left_hand = next((hand for hand in data if hand.get("handedness") == "Left"), None)
        right_hand = next((hand for hand in data if hand.get("handedness") == "Right"), None)

        # Validate and extract landmarks
        left_landmarks = left_hand.get("landmarks", []) if left_hand else []
        right_landmarks = right_hand.get("landmarks", []) if right_hand else []

        left_valid = len(left_landmarks) == 21
        right_valid = len(right_landmarks) == 21

        left_output = [{"x_px": lm["x_px"], "y_px": lm["y_px"]} for lm in left_landmarks] if left_valid else zero_landmarks()
        right_output = [{"x_px": lm["x_px"], "y_px": lm["y_px"]} for lm in right_landmarks] if right_valid else zero_landmarks()

        return left_output + right_output

    except (json.JSONDecodeError, FileNotFoundError, TypeError) as e:
        print(f"Error reading or parsing file: {e}")
        return zero_landmarks() * 2

# Example usage
if __name__ == "__main__":
    result = extract_landmark_array()
    print(result)
