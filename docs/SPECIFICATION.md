# Vision Pipeline — Technical Specification

## 1. Overview

`vision_pipeline_python` is a real-time, webcam-driven computer-vision pipeline
that detects **face** and **hand** keypoints with Google MediaPipe and streams
the resulting coordinates over a local TCP socket. A client consumes that stream
and turns hand keypoints into OS-level actions (e.g. moving the mouse cursor).

The system is designed to be launched standalone (`PythonApp_Main.py`) or driven
from a companion **.NET MAUI** application (`MauiApp_Launcher`) that spawns the
Python process.

### High-level goal
Let a user control the desktop cursor (and, in future, other actions) with hand
gestures captured from a standard webcam.

---

## 2. Components

The repository is split into three top-level units plus a MAUI launcher app.

| Component | Path | Role |
|-----------|------|------|
| **Entry point** | `PythonApp_Main.py` | Boots the launcher, defines the data callback `receive_float_array`. |
| **Launcher** | `PythonApp/Resources/Launcher_for_Server_and_Client.py` | Spawns the vision server and the client as subprocesses. |
| **Vision server** | `Python_Server_MediaPipe_vision_pipeline/` | Webcam capture, MediaPipe inference, socket server. |
| **Client / action layer** | `PythonApp/Resources/` | Receives packets, dispatches to cursor/action handlers. |
| **MAUI launcher** | `MauiApp_Launcher/` | Cross-platform .NET app that can launch the Python pipeline. |

---

## 3. Module Reference

### 3.1 `PythonApp_Main.py` (entry point)
- Launches `Launcher_for_Server_and_Client.py` as a subprocess.
- Sleeps ~3s to let the server/client come up.
- Defines `receive_float_array(datatype, array)`:
  - `datatype == "face"` → currently a no-op (TODO: face-driven movement).
  - `datatype == "hands"` → reads the **left index-finger tip** (array indices
    16, 17) and calls `left_index_tip(x, y)`.
  - Unknown types are logged.

### 3.2 `Launcher_for_Server_and_Client.py`
- Parses `--host` (default `127.0.0.1`) and `--port` (default `5050`).
- Spawns `Python_Server_MediaPipe_vision_pipeline/VisionPipeline.py` with the
  host/port args.
- Waits 1s, then spawns `Client.py` with the same args.

### 3.3 `VisionPipeline.py` (vision server main loop)
- Parses `--host` / `--port`.
- Starts the TCP socket server and blocks until a client connects.
- Ensures `mediapipe` and `opencv-python` are installed (auto-`pip install`).
- Loads the face + hand models, opens webcam (`cv2.VideoCapture(0)`).
- Per-frame loop (~30 FPS, `timestamp_ms += 33`):
  1. Run inference → annotated image + face coords + hand landmarks.
  2. Show preview window (`q` to quit).
  3. Remap/flatten face keypoints (6 pts → 12 floats).
  4. Remap/flatten left+right hand landmarks (21 pts each → 42 floats per hand,
     84 total).
  5. Write `facekeypointsCoordinates.json` and `handskeypointsCoordinates.json`.
  6. Send both over the socket.
- Cleans up webcam, windows, and socket on exit / connection loss.

### 3.4 `inference.py`
- `load_models()` → loads `facedetector.tflite` (FaceDetector) and
  `hand_landmarker.task` (HandLandmarker, VIDEO mode, up to 2 hands).
- `run_inference_on_frame(frame, face_detector, hand_detector, timestamp_ms)` →
  runs both detectors, draws overlays, returns
  `(combined_image, face_coords, all_hands_landmarks)`.

### 3.5 `Server.py`
- `Start_socket_server(host, port)` → bind/listen/accept, returns
  `(conn, addr, server)`. Uses `SO_REUSEADDR`.
- `Load_keypoints_json(name)` → loads a JSON file relative to the module.
- `SendPacket(face_file, hands_file, conn)` → sends two newline-delimited JSON
  packets: `{"type": "face", "data": [...]}` and `{"type": "hands", "data": [...]}`.

### 3.6 `utils_for_remapping_coordinates_and_output_formatting.py`
- `remap_point(...)` → optionally inverts X, centers origin, flips Y.
- `remap_keypoints(...)` → maps a list of `{x,y}` dicts to a flat
  `[x1,y1,x2,y2,...]` list; returns zeros if count mismatches `expected_count`.
  Default `invert_x=True` (mirror), `center_origin=False`, `flip_y=False`.
- `extract_hand_by_type(hands, "Left"|"Right")` → returns that hand's landmarks.

### 3.7 `Client.py`
- Connects to the server, creates `Received_data_json_files/`.
- Appends the project root to `sys.path` and imports `receive_float_array`
  from `PythonApp_Main`.
- `receive_keypoints_data()` loop:
  - Reads socket in 4096-byte chunks, splits on `\n`.
  - For each packet: parse JSON, write `received_<type>_data.json`, read it back,
    validate it's a non-empty list, then call `receive_float_array(type, array)`.

### 3.8 `HandsTriggeredActions.py` & `CursorController.py`
- `left_index_tip(x, y)` → sets the cursor target and updates UI position.
- `CursorController`:
  - Screen defaults `1920×1080`, pointer `20×20`.
  - `set_target_position_async` clamps the target to the screen bounds.
  - `update_cursor_position_in_ui` calls `ctypes.windll.user32.SetCursorPos`
    (**Windows-only**).
  - `update_screen_dimensions` / `on_main_display_info_changed` handle display
    changes (DIP-aware, orientation-aware).

---

## 4. Data Flow

```
Webcam ─▶ VisionPipeline.py ─▶ MediaPipe inference (face + hands)
                │
                ├─▶ remap/flatten ─▶ *.json files
                │
                └─▶ Socket server (TCP 127.0.0.1:5050)
                        │  newline-delimited JSON packets
                        ▼
                    Client.py ──▶ received_<type>_data.json
                        │
                        └─▶ receive_float_array(type, array)
                                │
                                ├─ "face"  → (TODO)
                                └─ "hands" → left_index_tip(x, y)
                                                │
                                                └─▶ CursorController → SetCursorPos
```

### Packet format (over socket)
Each packet is a single JSON object followed by `"\n"`:
```json
{"type": "face",  "data": [x1, y1, ... x6, y6]}        // 12 floats
{"type": "hands", "data": [ ...left 42..., ...right 42... ]}  // 84 floats
```

### Hands array layout (84 floats)
- Indices `0..41`  → left hand: 21 landmarks × (x, y).
- Indices `42..83` → right hand: 21 landmarks × (x, y).
- `PythonApp_Main` reads index **16, 17** = left-hand landmark #8 (index-finger
  tip) for cursor control.

---

## 5. Configuration

| Setting | Default | Where |
|---------|---------|-------|
| Host | `127.0.0.1` | `--host` arg (all entry points) |
| Port | `5050` | `--port` arg |
| Frame rate | ~30 FPS | `timestamp_ms += 33` in `VisionPipeline.py` |
| Camera index | `0` | `cv2.VideoCapture(0)` |
| Max hands | `2` | `inference.load_models` |
| Screen size | `1920×1080` | `CursorController` |

---

## 6. Dependencies & Requirements

- **Python 3** with `pip`.
- `opencv-python` (`cv2`) and `mediapipe` — auto-installed by `VisionPipeline.py`
  if missing, but a virtual environment is recommended (see `README_Installs.txt`).
- **Windows** is required for cursor control (`ctypes.windll.user32.SetCursorPos`).
- Model assets shipped in the repo:
  `facedetector.tflite`, `hand_landmarker.task`.

### Setup (one-time)
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Running
Double-click **`launch.bat`**, or from a terminal:
```powershell
# Easiest — uses the venv automatically:
.\launch.bat

# Or manually with the venv interpreter:
.\.venv\Scripts\python.exe PythonApp_Main.py
```
Press **`q`** in the camera preview window to stop. Because every process is
spawned with `sys.executable`, launching with the venv interpreter means the
server and client subprocesses inherit the same environment automatically.

---

## 7. .NET MAUI Launcher

`MauiApp_Launcher` is a cross-platform .NET MAUI app intended to launch the
Python pipeline via `System.Diagnostics.Process`, passing `--host`/`--port`.
See `TO DO - README_launch of Mainpy from DOTNET MAUI app.txt` for the launch
snippet. It also contains C# equivalents of the client / cursor / action logic
(`Client.cs`, `CursorControls.cs`, `HandsTriggeredActionscs.cs`).

---

## 8. Known Limitations & TODOs

- **Windows-only** cursor control (`user32.SetCursorPos`).
- Face data is received but **not yet acted on** (`receive_float_array` "face"
  branch is a no-op).
- Only the **left index-finger tip** drives the cursor; other landmarks/gestures
  are unused.
- JSON keypoints are written to disk every frame, then re-read — a potential I/O
  bottleneck that could be replaced by passing in-memory data.
- Hardcoded `1920×1080` screen size in `CursorController` (no auto-detect).
- Hardcoded ~30 FPS timestamp increment regardless of actual capture rate.
- No graceful reconnect if the socket drops; the pipeline exits.
- Auto-`pip install` at runtime mixes concerns; prefer an explicit requirements
  file / managed environment.
