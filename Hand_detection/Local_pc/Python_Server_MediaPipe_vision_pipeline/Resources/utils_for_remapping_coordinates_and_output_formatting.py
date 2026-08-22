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
                    invert_x=False, center_origin=False, flip_y=False):
    """
    Remaps a list of keypoints (dicts with x/y) to the new coordinate system.
    Returns a flattened list: [x1, y1, x2, y2, ...]
    If expected_count is set and doesn't match, returns fallback zeros.

    ⚠ `invert_x` DEFAULTS TO FALSE SINCE 2026-08-22 (spec 14.3.4.3). It used to
    default to True, because the pipeline detected on the RAW frame and mirrored
    coordinates afterward. `VisionPipeline.py` now mirrors the FRAME before
    detection, so coordinates arrive already mirrored and must NOT be mirrored
    again. Turning this back on re-introduces a double flip -- the M5d
    even/odd-flip trap that produced §13.6.1.
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


def extract_hand_world_by_type(hands_array, handedness):
    """Same lookup as extract_hand_by_type, but for the "world_landmarks"
    key (metric, hand-relative 3D coords) added for rotation-while-snapped
    (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13.7)."""
    hand = next((h for h in hands_array if h.get("handedness") == handedness), None)
    return hand.get("world_landmarks", []) if hand else []


def remap_world_keypoints(points, expected_count=None, invert_x=False):
    """Flattens a list of world-landmark dicts (x/y/z, metric hand-relative
    coordinates, NOT pixel coordinates) into [x1, y1, z1, x2, y2, z2, ...].
    Unlike remap_keypoints, values are kept as floats (no int cast --
    metric units are sub-pixel-scale) and there's no center_origin/flip_y
    option, since world_landmarks are already hand-relative, not
    image-relative.

    ⛔⛔ `invert_x` NOW DEFAULTS TO FALSE, AND THE OLD RATIONALE WAS FALSIFIED
    (2026-08-22, spec 14.3.4.3). It previously defaulted to True and read:
    "negate x to stay mirror-consistent with the pixel landmarks ... This has NOT
    been live-verified yet ... don't assume this is correct as-is."

    ⭐ It was verified, and it was wrong. Negating x after the fact equals
    mirroring the frame before detection ONLY if MediaPipe is mirror-equivariant.
    `analysis/t6_mirror_route_ab.py` measured both routes on the SAME frames:
    they disagree by **7.7-10 mm** of world landmark and **12-20° of fitted
    rotation** -- 3-4x the palm's own 2.76 mm rigidity, and NOT tracking drift
    (a stateless IMAGE-mode control makes it larger). Production and the debug
    tool were therefore different pipelines, which is what the owner saw as
    "the behavior in the production was not the same".

    `VisionPipeline.py` now mirrors the FRAME before detection, exactly as the
    debug tool and recorders always have, so world landmarks arrive already
    mirrored. ⚠ Re-enabling this flag would mirror them a second time."""
    if expected_count is not None and (not points or len(points) != expected_count):
        return [0.0] * expected_count * 3

    remapped = []
    for pt in points:
        if isinstance(pt, dict):
            try:
                x = float(pt.get("x", 0))
                y = float(pt.get("y", 0))
                z = float(pt.get("z", 0))
                if invert_x:
                    x = -x
                remapped.extend([x, y, z])
            except (ValueError, TypeError):
                remapped.extend([0.0, 0.0, 0.0])
        else:
            remapped.extend([0.0, 0.0, 0.0])
    return remapped