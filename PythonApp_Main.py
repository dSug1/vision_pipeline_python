import subprocess
import sys
import os
import time

from PythonApp.Resources import Launcher_for_Server_and_Client
from PythonApp.Resources import Client

# Resolve paths relative to the folder
_dir = os.path.dirname(os.path.abspath(__file__))
launcher_path = os.path.join("PythonApp", "Resources", "Launcher_for_Server_and_Client.py")

# Launch Launcher.py
launcher_command = [
    sys.executable,
    launcher_path
]
print(f"[Main.py] Starting Launcher_for_Server_and_Client.py")
subprocess.Popen(launcher_command)

time.sleep(3)

from typing import List
from PythonApp.Resources.HandsTriggeredActions import left_index_tip

def receive_float_array(datatype: str, array: List[float]) -> None:
    # Debug-style printout of received data
    #print(f"[MainPage] Received {datatype} data with [{', '.join(map(str, array))}]")

    if datatype == "face":
        # TODO: Add logic for face movement
        pass

    elif datatype == "hands":
        if len(array) >= 18 and (array[16] != 0 or array[17] != 0):
            indexfingerpositionX = array[16]
            indexfingerpositionY = array[17]
            left_index_tip(indexfingerpositionX, indexfingerpositionY)
        else:
            print(f"[MainPage] Warning: 'hands' array missing or zeroed index finger tip.")

    else:
        print(f"[MainPage] Unknown type: {datatype}")





