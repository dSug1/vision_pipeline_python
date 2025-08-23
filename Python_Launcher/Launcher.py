import subprocess
import sys
import argparse
import os
import time

# Parse launcher arguments
parser = argparse.ArgumentParser(description="Launcher for Main.py and Client.py")
parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
parser.add_argument("--port", type=int, default=5050, help="Server port")
args = parser.parse_args()

# Resolve paths relative to the parent folder
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
main_path = os.path.join(parent_dir, "Python_Server_MediaPipe_vision_pipeline", "Main.py")
client_path = os.path.join(parent_dir, "Python_Client", "Client.py")

# Launch Main.py
main_command = [
    sys.executable,
    main_path,
    "--host", args.host,
    "--port", str(args.port)
]
print(f"[Launcher] Starting Main.py on {args.host}:{args.port}")
subprocess.Popen(main_command)

# Optional delay to ensure server starts before client connects
time.sleep(5)

# Launch Client.py
client_command = [
    sys.executable,
    client_path,
    "--host", args.host,
    "--port", str(args.port)
]
print(f"[Launcher] Starting Client.py on {args.host}:{args.port}")
subprocess.Popen(client_command)
