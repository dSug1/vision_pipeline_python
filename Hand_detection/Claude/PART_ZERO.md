# Part Zero — what it does and what changed

Implements §4 of `Specification.md`: the smallest possible change that proves
"finger position → object position" instead of "finger position → OS cursor
position", using the *existing* pipeline unmodified except for the last step.

Code lives in `Hand_detection/Local_pc/` — a sibling of this `Claude/`
folder and of `Web/`. (Both folders were later renamed from
`Part_Zero_local_pc`/`Part_Zero_Bis_Web` once Part One started building
directly on top of Part Zero's code rather than in a separate folder — see
`PART_ONE.md` §1.) This doc used to live inside
`Part_Zero_local_pc/Movement_with_hand_detection/`; it (and `Specification.md`
and `PART_ZERO_BIS.md`) were pulled up to `Hand_detection/Claude/` so one
`Claude/` folder documents both the PC pipeline and its browser port,
instead of the docs living inside just one of the two things they describe.

## What Part Zero actually is

The existing pipeline is two processes talking over a local TCP socket, both
under `Local_pc/`:

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

All paths below are relative to `Local_pc/Movement_with_hand_detection/`
unless stated otherwise.

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
- **New:** a `"meta"` packet, sent once by the server right after the webcam
  opens (`../Python_Server_MediaPipe_vision_pipeline/VisionPipeline.py` reads
  one frame up front, reports its real `frame.shape` width/height via the new
  `SendMetaPacket` in that folder's `Resources/Server.py`) — lets the client
  size the cube window to the webcam's *actual* capture resolution instead of
  guessing. `PythonApp_Main.py` dispatches `datatype == "meta"` to
  `HandsTriggeredActions.configure_source_resolution(width, height)`, which
  calls the new `CubeWindow.resize(...)`.
- **Unchanged:** MediaPipe detection itself, the rest of the socket protocol,
  `Client.py`, `CursorController.py` (left in place, simply no longer
  imported — nothing else referenced it).

## How to run it

Same as before: `Local_pc/Movement_with_hand_detection/launch.bat`
(creates/reuses `.venv`, installs `requirements.txt`, runs
`PythonApp_Main.py`, which spawns the server + client). A cyan square should
now track your left hand's index fingertip in its own window instead of
moving your mouse. `stop.bat` kills the server and client processes by
matching `VisionPipeline.py` / `Client.py` / `PythonApp_Main.py` in their
command lines.

## Known caveats / assumptions (carried over from the original pipeline)

- The server sends **mirrored webcam-frame pixel coordinates**, not
  normalized `[0,1]` coordinates — `remap_keypoints(..., invert_x=True)` in
  `VisionPipeline.py`. The cube window now sizes itself to the webcam's real
  resolution via the `"meta"` packet (see above) rather than assuming a fixed
  size, so this maps 1:1 with no rescaling needed regardless of your camera's
  actual capture resolution. `CubeWindow`'s `DEFAULT_WINDOW_SIZE` (640×480) is
  only the placeholder shown for the brief moment before the meta packet
  arrives.
- No smoothing changes, no multi-hand logic, no gesture recognition — none of
  that is in scope here, by design (§4).

## Next step

Part Zero-bis (§5): port this same minimal loop — hand detection + cube
follows fingertip — to the browser (MediaPipe Tasks Vision JS +
Three.js), as the early dry run for the eventual full browser port. Done —
see `PART_ZERO_BIS.md` (same folder) and `Hand_detection/Web/`.
It's live on GitHub Pages — see `PART_ZERO_BIS.md` for the URL and how
deploys are triggered.

Then Part One (§7): back on PC, real gesture recognition built directly on
top of this folder's code (`Local_pc/`) — see `PART_ONE.md` for the design
and gesture matrix.
