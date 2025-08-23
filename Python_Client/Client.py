from pathlib import Path
import os
import socket
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, default="127.0.0.1")
parser.add_argument("--port", type=int, default=5050)
args = parser.parse_args()

# Connect to server
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((args.host, args.port))
print(f"[Client] Connected to {args.host}:{args.port}")

# Example: send a start command
#client.sendall(b'{"action": "start"}')


script_dir = Path(__file__).resolve().parent
output_dir = script_dir / "Received_data_json_files"
output_dir.mkdir(exist_ok=True)


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
