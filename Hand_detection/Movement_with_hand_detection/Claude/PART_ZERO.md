# Part Zero — what it does and what changed

Implements §4 of `Specification.md`: the smallest possible change that proves
"finger position → object position" instead of "finger position → OS cursor
position", using the *existing* pipeline unmodified except for the last step.

## What Part Zero actually is

The existing pipeline is two processes talking over a local TCP socket:

- **Server** (`Python_Server_MediaPipe_vision_pipeline/VisionPipeline.py`) — opens
  the webcam, runs MediaPipe hand/face detection every frame, streams landmark
  coordinates as JSON over the socket.
- **Client** (`Movement_with_hand_detection/Resources/Client.py`) — receives each
  packet and calls `PythonApp_Main.receive_float_array(datatype, array)`, which
  for `"hands"` packets pulls out indices 16/17 — the left hand's index
  fingertip (x, y) — and calls `HandsTriggeredActions.left_index_tip(x, y)`.

Before Part Zero, `left_index_tip` fed that (x, y) into `CursorController`,
which clamped it to the screen and called `ctypes.windll.user32.SetCursorPos`
— i.e. it moved the real OS mouse cursor.

**Part Zero replaces only that last step.** `left_index_tip(x, y)` is exactly
the "clean function output" §4 asks for — the isolation was already there, it
just fed the OS cursor. So the retarget was: keep the function, swap what it
calls.

## What changed

- **New:** `Resources/CubeWindow.py` — a small Pygame window with one square
  ("cube" — a flat square stand-in, per §4's explicit allowance) whose
  position is set via `set_target_position(x, y)` (clamped to the window,
  mirroring `CursorController`'s clamping logic) and redrawn via
  `pump_and_draw()`.
- **Changed:** `Resources/HandsTriggeredActions.py` — `left_index_tip` now
  calls `cube_window.set_target_position(...)` +
  `cube_window.pump_and_draw()` instead of `controller.set_target_position_async(...)`
  + `controller.update_cursor_position_in_ui()`.
- **Changed:** `requirements.txt` — added `pygame==2.6.1` (pinned, per §10).
- **Unchanged:** webcam capture, MediaPipe detection, socket protocol,
  `Client.py`, `PythonApp_Main.py`, `CursorController.py` (left in place,
  simply no longer imported — nothing else referenced it).

## How to run it

Same as before: `launch.bat` (creates/reuses `.venv`, installs
`requirements.txt`, runs `PythonApp_Main.py`, which spawns the server +
client). A cyan square should now track your left hand's index fingertip in
its own window instead of moving your mouse. `stop.bat` kills the server
process by matching `VisionPipeline.py` in its command line.

## Known caveats / assumptions (carried over from the original pipeline)

- The server sends **mirrored webcam-frame pixel coordinates**, not
  normalized `[0,1]` coordinates — `remap_keypoints(..., invert_x=True)` in
  `VisionPipeline.py`. `CubeWindow` assumes those pixels are roughly in a
  640×480 range (`VisionPipeline.py` never calls `cap.set()`, so whatever your
  webcam's default resolution is applies) and maps them 1:1 into a 640×480
  window with no rescaling. If your camera's default resolution differs, the
  cube's range of motion inside the window will feel off — adjust
  `DEFAULT_WINDOW_SIZE` in `CubeWindow.py` to match, or (future work) have the
  server include actual frame width/height in the packet so the client can
  scale properly instead of assuming.
- No smoothing changes, no multi-hand logic, no gesture recognition — none of
  that is in scope here, by design (§4).

## Next step

Part Zero-bis (§5): port this same minimal loop — hand detection + cube
follows fingertip — to the browser (MediaPipe Tasks Vision JS +
Three.js), as the early dry run for the eventual full browser port. Not
started yet.
