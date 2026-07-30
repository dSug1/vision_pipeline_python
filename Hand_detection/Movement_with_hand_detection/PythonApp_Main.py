import subprocess
import sys
import os
from typing import List

from Resources.HandsTriggeredActions import left_index_tip, configure_source_resolution


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
        if len(array) < 18:
            print(f"[MainPage] Warning: 'hands' array too short ({len(array)} values).")
        elif array[16] != 0 or array[17] != 0:
            indexfingerpositionX = array[16]
            indexfingerpositionY = array[17]
            left_index_tip(indexfingerpositionX, indexfingerpositionY)
        # else: left-hand index fingertip not detected this frame (normal) — no log spam

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
