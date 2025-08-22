import socket
import json
import os


def Start_socket_server(serverhost, serverport):
    serVer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serVer.bind((serverhost, serverport))
    serVer.listen()
    print(f"[Socket Server] Listening on {serverhost}:{serverport}...")

    conn, addr = serVer.accept()
    print(f"[Socket Server] Connection established with {addr}")

    return conn, addr, serVer

def Load_keypoints_json(nameOfFile):
    path = os.path.join(os.path.dirname(__file__), nameOfFile)
    with open(path, "r") as f:
        return json.load(f)
    
def SendPacket(filename, throughconnection):
    try:
        keypoints_data = Load_keypoints_json(filename)
        serialized = json.dumps(keypoints_data)
        throughconnection.sendall(serialized.encode('utf-8'))
        print("[Socket Server] Data sent successfully.")
    except Exception as e:
        print(f"[Socket Server] Error: {e}")



