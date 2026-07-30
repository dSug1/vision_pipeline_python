# Virtual Drums — Finger Tracking (new desktop app)

**Status:** new desktop application — scaffolded; logic to be filled in & calibrated.
Replaces the retired server–client `MouseCursorApp`.

**This folder is self-contained** — it has no imports, links, or dependencies on
any other folder in the repo. Copy it anywhere and run `launch.bat` (it creates a
local `.venv` from `requirements.txt`). Full spec: [`spec/Virtual_drums_specification.md`](spec/Virtual_drums_specification.md).

## Intent

A Windows desktop app that tracks finger positions from the webcam and triggers
**virtual drum hits** (a different sound per finger).

## Run
```
launch.bat        # first run creates a local .venv and installs deps, then starts the app
```
Press `q` or close the window to stop.

## Architecture (decided)

Built as a **single process** with **in-process messaging** (event / callback /
queue) and a clean **producer → consumer** boundary — **no TCP socket, no second
process**:

- **Producer:** camera capture + MediaPipe landmark detection → emits landmark events.
- **Consumer(s):** drum-trigger logic (and any future consumers) subscribe in-process.

This removes the original design's single-client server limitation entirely:
multiple consumers simply subscribe to the in-process landmark stream.

## Design principles (so the design ports to mobile later)

The Python code here is a desktop prototype and will **not** port to mobile, but
the **design** should. Keep portable:

- a stable, documented **landmark data contract**;
- **producer ↔ consumer separation** behind interfaces;
- **touch-friendly UX** (no assumption of a desktop OS cursor);
- reusable **`.task` / `.tflite` model files**.

The camera-capture layer (`cv2.VideoCapture`) and the MediaPipe wrapper are
isolated behind interfaces (`ICameraSource`, `ILandmarkSource`) so they can be
swapped for mobile (CameraX/AVFoundation, native MediaPipe Tasks SDK).

> Full design and open questions: [`spec/Virtual_drums_specification.md`](spec/Virtual_drums_specification.md).
