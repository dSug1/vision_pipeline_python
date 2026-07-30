import socket
import json


def Start_socket_server(serverhost, serverport):
    serVer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serVer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #This allows the socket to reuse the address if it was recently closed
    serVer.bind((serverhost, serverport))
    serVer.listen()
    print(f"[Socket Server] Listening on {serverhost}:{serverport}...")

    conn, addr = serVer.accept()
    print(f"[Socket Server] Connection established with {addr}")

    return conn, addr, serVer

def SendMetaPacket(frame_width, frame_height, throughconnection):
    """Sent once at startup so the client knows the webcam's actual capture
    resolution instead of having to guess/hardcode one (e.g. Part Zero's
    CubeWindow sizing itself off this instead of assuming 640x480)."""
    try:
        serialized = json.dumps({"type": "meta", "data": [frame_width, frame_height]}) + "\n"
        throughconnection.sendall(serialized.encode('utf-8'))
    except Exception as e:
        print(f"[Socket Server] Error: {e}")
        raise  # re-raise so the caller can mark the connection dead


def SendPacket(face_data, hands_data, throughconnection):
    """Serialize the face and hands coordinate arrays and send them as two
    newline-delimited JSON packets over the socket. `\n` is the packet
    delimiter; compact json.dumps guarantees no embedded newlines."""
    try:
        serialized = json.dumps({"type": "face", "data": face_data}) + "\n"
        throughconnection.sendall(serialized.encode('utf-8'))

        hands_serialized = json.dumps({"type": "hands", "data": hands_data}) + "\n"
        throughconnection.sendall(hands_serialized.encode('utf-8'))
    except Exception as e:
        print(f"[Socket Server] Error: {e}")
        raise  # re-raise so the caller can mark the connection dead


