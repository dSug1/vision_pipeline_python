import subprocess
import sys
import os
from typing import List, Tuple

from Resources.HandsTriggeredActions import (
    on_hands_frame, on_hands_world_frame, on_hand_tracks_frame,
    configure_source_resolution,
)

# "hands" packets carry both hands' full 21-point landmark lists, flattened
# as [left_x0, left_y0, ..., left_x20, left_y20, right_x0, right_y0, ...,
# right_x20, right_y20] — see VisionPipeline.py's remap_keypoints calls for
# "Left" then "Right". A hand not detected this frame arrives as 21 (0, 0)
# placeholder points rather than being omitted (see
# utils_for_remapping_coordinates_and_output_formatting.py's expected_count
# fallback), so the array length is always the same regardless of how many
# hands are actually visible.
LANDMARKS_PER_HAND = 21
VALUES_PER_HAND = LANDMARKS_PER_HAND * 2  # (x, y) per landmark
VALUES_PER_HANDS_PACKET = VALUES_PER_HAND * 2  # left hand + right hand

# "hands_world" packets: same per-hand/per-landmark layout, but (x, y, z)
# metric hand-relative coordinates instead of (x, y) pixel coordinates --
# added for rotation-while-snapped (Claude/GESTURE_PIPELINE_SPEC.md §13.7).
# Sent BEFORE "hands" each frame (see Server.py's SendHandsWorldPacket),
# so on_hands_world_frame's stored values are already current by the time
# on_hands_frame runs for that same frame.
VALUES_PER_HAND_WORLD = LANDMARKS_PER_HAND * 3  # (x, y, z) per landmark
VALUES_PER_HANDS_WORLD_PACKET = VALUES_PER_HAND_WORLD * 2  # left hand + right hand


def _to_landmark_pairs(values: List[float]) -> List[Tuple[float, float]]:
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


def _to_landmark_triples(values: List[float]) -> List[Tuple[float, float, float]]:
    return [(values[i], values[i + 1], values[i + 2]) for i in range(0, len(values), 3)]


def receive_float_array(datatype: str, array: List[float]) -> None:
    # Debug-style printout of received data
    #print(f"[MainPage] Received {datatype} data with [{', '.join(map(str, array))}]")

    if datatype == "meta":
        if len(array) < 2 or array[0] <= 0 or array[1] <= 0:
            print(f"[MainPage] Warning: invalid 'meta' resolution {array}.")
        else:
            configure_source_resolution(int(array[0]), int(array[1]))

    elif datatype == "face":
        # TODO: Add logic for face movement
        pass

    elif datatype == "hand_tracks":
        # Stable DR-1 track ids, [Left, Right], -1 = slot empty (queue 4.1/T3).
        # Sent BEFORE this frame's "hands" packet, so ownership resolution below
        # already has the current identities.
        if len(array) < 2:
            print(f"[MainPage] Warning: 'hand_tracks' array too short ({len(array)}, expected 2).")
        else:
            on_hand_tracks_frame(int(array[0]), int(array[1]))

    elif datatype == "hands_world":
        if len(array) < VALUES_PER_HANDS_WORLD_PACKET:
            print(f"[MainPage] Warning: 'hands_world' array too short ({len(array)} values, expected {VALUES_PER_HANDS_WORLD_PACKET}).")
        else:
            left_world = _to_landmark_triples(array[:VALUES_PER_HAND_WORLD])
            right_world = _to_landmark_triples(array[VALUES_PER_HAND_WORLD:VALUES_PER_HANDS_WORLD_PACKET])
            on_hands_world_frame(left_world, right_world)

    elif datatype == "hands":
        if len(array) < VALUES_PER_HANDS_PACKET:
            print(f"[MainPage] Warning: 'hands' array too short ({len(array)} values, expected {VALUES_PER_HANDS_PACKET}).")
        else:
            left_landmarks = _to_landmark_pairs(array[:VALUES_PER_HAND])
            right_landmarks = _to_landmark_pairs(array[VALUES_PER_HAND:VALUES_PER_HANDS_PACKET])
            on_hands_frame(left_landmarks, right_landmarks)

    else:
        print(f"[MainPage] Unknown type: {datatype}")


def main() -> None:
    # Resolve the launcher path relative to this file (cwd-independent)
    _dir = os.path.dirname(os.path.abspath(__file__))
    launcher_path = os.path.join(_dir, "Resources", "Launcher_for_Server_and_Client.py")

    launcher_command = [sys.executable, launcher_path]
    print(f"[Main.py] Starting Launcher_for_Server_and_Client.py")
    subprocess.Popen(launcher_command)


# Only launch the pipeline when run directly. When Client.py imports this module
# to reuse receive_float_array(), the launch logic must NOT run again.
if __name__ == "__main__":
    main()
