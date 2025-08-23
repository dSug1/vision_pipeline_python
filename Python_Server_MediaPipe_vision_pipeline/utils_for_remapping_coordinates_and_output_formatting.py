def remap_point(x, y, frame_width, frame_height, invert_x, center_origin, flip_y):
    """
    Remaps a single (x, y) point from image-space to a centered coordinate system.
    - invert_x: if True, flips X horizontally
    - center_origin: if True, origin is moved to image center
    - flip_y: if True, Y axis is flipped (so upward motion increases Y)
    """
    if invert_x:
        x = frame_width - x
    if center_origin:
        x -= frame_width // 2
        y -= frame_height // 2
    if flip_y:
        y *= -1
    return x, y


def remap_keypoints(points, frame_width, frame_height, x_key="x", y_key="y", expected_count=None,
                    invert_x=True, center_origin=False, flip_y=False):
    """
    Remaps a list of keypoints (dicts with x/y) to the new coordinate system.
    Returns a flattened list: [x1, y1, x2, y2, ...]
    If expected_count is set and doesn't match, returns fallback zeros.
    """
    # set invert_x=True, center_origin=True, flip_y=True if you want to have the keypoints origins to be at the center of the display with negative and positive variance around this origin
    if expected_count is not None and (not points or len(points) != expected_count):
        return [0] * expected_count * 2

    remapped = []
    for i, pt in enumerate(points):
        if isinstance(pt, dict):
            try:
                x = int(float(pt.get(x_key, 0)))
                y = int(float(pt.get(y_key, 0)))
                x, y = remap_point(x, y, frame_width, frame_height, invert_x, center_origin, flip_y)
                remapped.extend([x, y])
            except (ValueError, TypeError):
                remapped.extend([0, 0])
        else:
            remapped.extend([0, 0])
    return remapped

def extract_hand_by_type(hands_array, handedness):
    hand = next((h for h in hands_array if h.get("handedness") == handedness), None)
    return hand.get("landmarks", []) if hand else []