import json
import os

def extract_face_array(json_file_path):
    def zero_face_flat(n=6):
        return [0] * n * 2  # n keypoints × 2 coordinates

    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)

        if not data or not isinstance(data, list):
            return zero_face_flat()

        flat_array = []
        for point in data:
            try:
                x = int(float(point.get("x", 0)))
                y = int(float(point.get("y", 0)))
                flat_array.extend([x, y])
            except (ValueError, TypeError):
                flat_array.extend([0, 0])

        return flat_array

    except (json.JSONDecodeError, FileNotFoundError, TypeError) as e:
        print(f"Error reading or parsing file: {e}")
        return zero_face_flat()

