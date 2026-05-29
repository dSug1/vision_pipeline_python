from pathlib import Path
import os
import sys
import socket
import json
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, default="127.0.0.1")
parser.add_argument("--port", type=int, default=5050)
args = parser.parse_args()

# Connect to server. The server process needs a few seconds to import MediaPipe
# before it starts listening, so retry instead of failing on the first refusal.
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_CONNECT_TIMEOUT = 30  # seconds
connected = False
for _attempt in range(_CONNECT_TIMEOUT * 2):  # try every 0.5s
    try:
        client.connect((args.host, args.port))
        connected = True
        break
    except (ConnectionRefusedError, OSError):
        time.sleep(0.5)

if not connected:
    print(f"[Client] Could not connect to {args.host}:{args.port} within {_CONNECT_TIMEOUT}s. Is the server running?")
    sys.exit(1)

print(f"[Client] Connected to {args.host}:{args.port}")

# Example: send a start command
#client.sendall(b'{"action": "start"}')


script_dir = Path(__file__).resolve().parent
output_dir = script_dir / "Received_data_json_files"
output_dir.mkdir(exist_ok=True)

# Add the application directory (one level above Resources/) to the path so we
# can import the entry module that defines the dispatch callback.
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(app_dir)

# Now import the module
from PythonApp_Main import receive_float_array


def receive_keypoints_data():
    try:
        buffer = ""
        while True:
            chunk = client.recv(4096).decode('utf-8')
            if not chunk:
                print("[Client] Connection closed by server.")
                break
            buffer += chunk

            while '\n' in buffer:
                packet, buffer = buffer.split('\n', 1)
                try:
                    data = json.loads(packet)
                    #print("[Client] Received data:", data)

                    data_type = data.get("type", "unknown")
                    output_file = output_dir / f"received_{data_type}_data.json"

                    with open(output_file, 'w') as f:
                        json.dump(data["data"], f, indent=4)

                    # Read back the just-written JSON
                    try:
                        with open(output_file, 'r') as f:
                            json_content = f.read()
                            float_array = json.loads(json_content)

                            # Validate and dispatch
                            if isinstance(float_array, list) and float_array:
                                receive_float_array(data_type, float_array)
                            else:
                                print(f"[Client] Warning: Received null or empty float array for type '{data_type}'. Skipping MainPage dispatch.")
                    except Exception as e:
                        print(f"[Client] Error reading or dispatching float array: {e}")

                   
                except json.JSONDecodeError as e:
                    print(f"[Client] JSON decode error: {e}")
                except Exception as e:
                    print(f"[Client] Error processing packet: {e}")

    except Exception as e:
        print(f"[Client] Connection error: {e}")
    finally:
        client.close()
        print("[Client] Socket closed.")

receive_keypoints_data()

#Want help building a unified client that routes packets to different Blender handlers based on type? I can sketch that out next.
