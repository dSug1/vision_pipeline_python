import subprocess
import sys
import os
from typing import List, Tuple

from Resources.HandsTriggeredActions import on_hands_frame, configure_source_resolution

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


def _to_landmark_pairs(values: List[float]) -> List[Tuple[float, float]]:
    return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]


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
