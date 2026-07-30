from typing import List, Tuple
from .CubeWindow import CubeWindow

# Part One (see Hand_detection/Claude/PART_ONE.md): extends Part Zero's
# single-cube retarget (Hand_detection/Claude/PART_ZERO.md) to two
# independently tracked hands, each driving its own cube. Step 1
# (scaffolding, matrix order #1) only wires both hands' index fingertips to
# their own cube, unconditionally — no pinch/grab/rotate/depth logic yet,
# that's layered on in later steps per PART_ONE.md's build order.
cube_window = CubeWindow()

INDEX_TIP = 8  # MediaPipe's 21-point hand landmark index for the index fingertip


def _is_detected(landmarks: List[Tuple[float, float]]) -> bool:
    """A hand not detected this frame arrives as 21 (0, 0) placeholder
    points (see remap_keypoints's expected_count fallback in
    utils_for_remapping_coordinates_and_output_formatting.py) — checking the
    index tip alone mirrors the pre-Part-One check on array[16]/[17]."""
    x, y = landmarks[INDEX_TIP]
    return x != 0 or y != 0


def on_hands_frame(left_landmarks: List[Tuple[float, float]], right_landmarks: List[Tuple[float, float]]) -> None:
    """Called once per received "hands" packet with both hands' full
    21-point landmark lists (mirrored webcam-frame pixel coordinates). Each
    hand's full landmark set is passed through — not just the index tip —
    so later steps (pinch detection needs landmark 4, the depth proxy needs
    a wrist/knuckle span, ...) don't require another wire-protocol touch.
    Left hand drives the blue cube, right hand drives the red cube — purely
    as this step's wiring; step 3's grab arbitration will make cube
    ownership dynamic (either hand can grab either cube) rather than fixed
    like this."""
    if _is_detected(left_landmarks):
        cube_window.set_target_position("blue", left_landmarks[INDEX_TIP])
    if _is_detected(right_landmarks):
        cube_window.set_target_position("red", right_landmarks[INDEX_TIP])
    cube_window.pump_and_draw()


def configure_source_resolution(width: int, height: int) -> None:
    """Called once, as soon as the server's "meta" packet arrives, to size
    the cube window to the webcam's actual frame resolution instead of the
    placeholder default it opens with."""
    cube_window.resize((width, height))
