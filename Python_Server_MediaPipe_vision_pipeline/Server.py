import socket
import json
import os

def load_keypoints_json(filename="facekeypointsCoordinates.json"):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r") as f:
        return json.load(f)

def start_socket_server(serverhost, serverport):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((serverhost, serverport))
    server.listen()
    print(f"[Socket Server] Listening on {serverhost}:{serverport}...")

    conn, addr = server.accept()
    print(f"[Socket Server] Connection established with {addr}")

    try:
        keypoints_data = load_keypoints_json()
        serialized = json.dumps(keypoints_data)
        conn.sendall(serialized.encode('utf-8'))
        print("[Socket Server] Data sent successfully.")
    except Exception as e:
        print(f"[Socket Server] Error: {e}")
    finally:
        conn.close()
        server.close()
        print("[Socket Server] Connection closed.")


