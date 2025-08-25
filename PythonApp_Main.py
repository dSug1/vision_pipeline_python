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


def receive_float_array(datatype: str, array: List[float]) -> None:
    print(f"[Client] Sent {datatype} float array to MainPage: {array}.")
