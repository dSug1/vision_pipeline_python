import socket
import json
import os


def Start_socket_server(serverhost, serverport):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((serverhost, serverport))
    server.listen()
    print(f"[Socket Server] Listening on {serverhost}:{serverport}...")

    conn, addr = server.accept()
    print(f"[Socket Server] Connection established with {addr}")

    return conn, addr

def Load_keypoints_json(filename="facekeypointsCoordinates.json"):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r") as f:
        return json.load(f)
    
def SendPacket(throughconnection, throughserver):
    try:
        keypoints_data = Load_keypoints_json()
        serialized = json.dumps(keypoints_data)
        throughconnection.sendall(serialized.encode('utf-8'))
        print("[Socket Server] Data sent successfully.")
    except Exception as e:
        print(f"[Socket Server] Error: {e}")
    finally:
        throughconnection.close()
        throughserver.close()
        print("[Socket Server] Connection closed.")


