# Models

**`hand_landmarker.task`** — the MediaPipe Hand Landmarker bundle (palm detector
+ 21-point hand-landmark model).

This file is **bundled inside the app** (copied, not linked) so the folder is
self-contained and portable: copy `Virtual_drums_fingers_tracking/` anywhere and
the model travels with it. It is loaded by `vision/hand_landmarker.py` via the
path in `config.py` (`MODEL_PATH`), resolved relative to the app folder.

The same `.task` file is the **portable asset** that the native MediaPipe Tasks
SDK loads on Android/iOS in a future mobile rebuild.
