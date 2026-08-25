import subprocess
import sys
import argparse
import os
import time

# Parse launcher arguments
parser = argparse.ArgumentParser(description="Launcher for Python_Server_MediaPipe_vision_pipeline/VisionPipeline.py and Client.py")
parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
parser.add_argument("--port", type=int, default=5050, help="Server port")
# ⛔ Forwarded to BOTH children so the loopback refusal cannot be half-applied --
# a server that permits remote while the client refuses it (or the reverse) would
# read as "the pipeline is broken" instead of "this is not allowed". See
# `Python_Server_MediaPipe_vision_pipeline/Resources/Server.py`.
parser.add_argument("--allow-remote", action="store_true",
                    help="Permit a non-loopback --host. This TRANSMITS landmarks.")
args = parser.parse_args()
_remote_flag = ["--allow-remote"] if args.allow_remote else []

# Resolve paths relative to the parent folder
script_dir = os.path.dirname(os.path.abspath(__file__))
grandparent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
main_path = os.path.join(grandparent_dir, "Python_Server_MediaPipe_vision_pipeline", "VisionPipeline.py")
client_path = os.path.join(script_dir, "Client.py")

# Launch Main.py
main_command = [
    sys.executable,
    main_path,
    "--host", args.host,
    "--port", str(args.port)
] + _remote_flag
print(f"[Launcher] Starting VisionPipeline.py on {args.host}:{args.port}")
subprocess.Popen(main_command)

# Optional delay to ensure server starts before client connects
time.sleep(1)

# Launch Client.py
client_command = [
    sys.executable,
    client_path,
    "--host", args.host,
    "--port", str(args.port)
] + _remote_flag
print(f"[Launcher] Starting Client.py on {args.host}:{args.port}")
subprocess.Popen(client_command)
