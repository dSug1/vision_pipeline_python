# vision_pipeline_python/server.py

import sys
import subprocess
import importlib.util
import socket
import threading
import cv2
import time

# 🛠 Ensure mediapipe is installed
def ensure_mediapipe():
    package_name = "mediapipe"
    if importlib.util.find_spec(package_name) is None:
        print(f"[Setup] {package_name} not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
    else:
        print(f"[Setup] {package_name} is already installed.")

ensure_mediapipe()

# 📦 Import your pipeline
try:
    from MediaPipe_vision_pipeline import load_models, run_inference_on_frame
except Exception as e:
    print(f"[Import Error] {e}")
    sys.exit(1)
    
# 🌐 Socket config
HOST = '127.0.0.1'
PORT = 65432

# 🧠 Load models once
face_detector, hand_detector = load_models()

def handle_client(conn, addr):
    print(f"[Server] Connected by {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            message = data.decode('utf-8').strip()
            print(f"[Server] Received: {message}")

            if message == "run_inference":
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    conn.sendall(b"error: webcam not available")
                    return

                ret, frame = cap.read()
                cap.release()

                if not ret:
                    conn.sendall(b"error: frame capture failed")
                    return

                timestamp_ms = int(time.time() * 1000)
                print("[Debug] Reached block0")
                annotated = run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms)

                print("[Debug] Reached block1")
                cv2.imshow("Hands & Face Detection", annotated)
                print("[Debug] Reached block2")
                cv2.waitKey(1)

                conn.sendall(b"inference complete")
                print("[Debug] Reached block3")


            elif message == "shutdown":
                conn.sendall(b"shutting down")
                break

            else:
                conn.sendall(b"error: unknown command")

    except Exception as e:
        print(f"[Server] Error: {e}")
        conn.sendall(f"error: {str(e)}".encode('utf-8'))

    finally:
        conn.close()
        print(f"[Server] Connection closed")

def start_server():
    print(f"[Server] Starting on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()


if __name__ == "__main__":
    start_server()




