
def flatten_face_keypoints(face_points, expected_count=6):
    if not face_points or len(face_points) != expected_count:
        return [0] * expected_count * 2

    flat = []
    for i, point in enumerate(face_points):
        if isinstance(point, dict):
            try:
                x = int(float(point.get("x", 0)))
                y = int(float(point.get("y", 0)))
                flat.extend([x, y])
            except (ValueError, TypeError):
                flat.extend([0, 0])
        else:
            print(f"[Warning] Unexpected face point format at index {i}: {point}")
            flat.extend([0, 0])
    return flat


def flatten_hand_keypoints(hand_landmarks, expected_count=21):
    if not hand_landmarks or len(hand_landmarks) != expected_count:
        return [0] * expected_count * 2

    flat = []
    for lm in hand_landmarks:
        if isinstance(lm, dict):
            try:
                x = int(float(lm.get("x_px", 0)))
                y = int(float(lm.get("y_px", 0)))
                flat.extend([x, y])
            except (ValueError, TypeError):
                flat.extend([0, 0])
        else:
            flat.extend([0, 0])
    return flat


def extract_hand_by_type(hands_array, handedness):
    hand = next((h for h in hands_array if h.get("handedness") == handedness), None)
    return hand.get("landmarks", []) if hand else []

