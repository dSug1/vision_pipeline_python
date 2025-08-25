import subprocess
import sys
import os
import time

from Resources import Launcher


# Resolve paths relative to the folder
_dir = os.path.dirname(os.path.abspath(__file__))
launcher_path = os.path.join("Resources", "Launcher.py")

# Launch Launcher.py
launcher_command = [
    sys.executable,
    launcher_path
]
print(f"[Main.py] Starting Launcher.py")
subprocess.Popen(launcher_command)

time.sleep(3)
