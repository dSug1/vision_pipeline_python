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
    
def SendPacket(facecoordsfilename, handscoordsfilename, throughconnection):
    try:
        #send face keypoints coordinates
        facekeypoints_data = Load_keypoints_json(facecoordsfilename)
        serialized = json.dumps({"type": "face", "data":facekeypoints_data})+ "\n"  # Add delimiter
        throughconnection.sendall(serialized.encode('utf-8'))
        #print("[Socket Server] Face data sent successfully.")

        #send hands landmarks coordinates
        hands_data = Load_keypoints_json(handscoordsfilename)
        hands_serialized = json.dumps({"type": "hands", "data": hands_data}) + "\n"
        throughconnection.sendall(hands_serialized.encode('utf-8'))
        #print("[Socket Server] Hand keypoints sent successfully.")
    except Exception as e:
        print(f"[Socket Server] Error: {e}")
        raise  # <-- This is critical: re-raise the exception


