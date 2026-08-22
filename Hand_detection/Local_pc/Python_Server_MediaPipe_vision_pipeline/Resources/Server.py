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


def SendHandsWorldPacket(hands_world_data, throughconnection):
    """Sent BEFORE each frame's "hands" packet (see SendPacket below) --
    metric, hand-relative 3D landmarks (21 x/y/z per hand x 2 hands = 126
    floats), added for rotation-while-snapped
    (Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13.7). Packets are
    dispatched sequentially in arrival order (Client.py's
    receive_keypoints_data), so sending this first guarantees the frame's
    world landmarks are already stored by the time the same frame's
    "hands" packet triggers on_hands_frame's per-frame gesture logic."""
    try:
        serialized = json.dumps({"type": "hands_world", "data": hands_world_data}) + "\n"
        throughconnection.sendall(serialized.encode('utf-8'))
    except Exception as e:
        print(f"[Socket Server] Error: {e}")
        raise  # re-raise so the caller can mark the connection dead


def SendHandTracksPacket(track_ids, throughconnection):
    """Stable DR-1 track ids for the two hand slots -- [Left, Right], -1 if the
    slot is empty this frame. Added 2026-08-22 for queue 4.1 / T3.

    ⭐ WHY THIS EXISTS: cube ownership used to key on the handedness LABEL, which
    is not an identity -- it flips, and 113 of 205 measured spurious cube
    releases were exactly that flip orphaning a held cube. A client-side repair
    was built and REVERTED (it had to infer "same hand" from position, and two
    hands in the same place are indistinguishable by position -- that is what
    occlusion IS). Carrying the track identity the server already computes makes
    the whole question disappear.

    ⚠ Sent BEFORE the frame's "hands" packet, same reasoning as
    SendHandsWorldPacket: packets dispatch in arrival order, so the ids must
    already be stored when the same frame's "hands" packet drives the gesture
    logic.
    """
    try:
        serialized = json.dumps({"type": "hand_tracks", "data": track_ids}) + "\n"
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


