# Part Zero-bis — porting notes (Python → browser)

Per Specification.md §5, this records what had to be adjusted going from Part
Zero's Python/Pygame version to this browser/Three.js version.

**Verified (2026-07-30):** ran the Python pipeline and the deployed web page
side by side per the steps below. Confirmed working — hand movement, cube
range of motion, mirroring direction, and handedness all match between the
two, and tracking is responsive in practice. All items below are resolved;
none are still design-time assumptions.

| Item | Python (Part Zero) | Browser (Part Zero-bis) | Status |
|---|---|---|---|
| Landmark model | `mediapipe` 0.10.14, `hand_landmarker.task`, VIDEO mode | `@mediapipe/tasks-vision` 1.0.0, **same `hand_landmarker.task` file** (copied via `scripts/copy-mediapipe-assets.mjs`), VIDEO mode | Same model file, same 21-point index order — no remapping needed (per Specification.md §6) |
| Coordinate convention | Pixel coords, `invert_x=True` mirror applied server-side before sending | Normalized `[0,1]` image-space landmarks from `HandLandmarker`, mirrored client-side (`1 - x`) before mapping to Three.js world space | **Confirmed.** Bug found and fixed along the way: `cubeScene.js` originally mapped normalized coords to a hardcoded `RANGE_X = 2.0, RANGE_Y = 1.5`, which didn't match the camera's actual visible area at the cube's depth (~±3.7 × ±2.8 for the default FOV/distance/aspect) — so the cube stopped well short of the window edges even when the fingertip reached the camera frame's edges, unlike Part Zero's Pygame window which fills its whole width/height. Fixed by deriving the range from the camera's actual FOV/distance/aspect (`_getVisibleHalfExtents()`) instead of a guessed constant. Mirroring **direction** confirmed live — hand moves right → cube moves right, matching the Python window. |
| Handedness → "Left" | `extract_hand_by_type(..., "Left")` on MediaPipe's own handedness label | `extractHandByType(result, "Left")`, same label source | **Confirmed** — MediaPipe JS's "Left"/"Right" labels agree with the Python `mediapipe` package's labels for the same physical hand in front of the same camera; the mirror-aware assumption in `handTracker.js`'s comment holds in practice. |
| Camera resolution | Server reads real `frame.shape` once, sends a `"meta"` packet, client resizes the window to match (`Hand_detection/Claude/PART_ZERO.md`) | `camera.js`'s `getTrackResolution()` reads `track.getSettings().width/height` after `getUserMedia()` resolves; shown in the status line and logged to console, not used to resize anything (there's nothing to resize — the Three.js canvas is CSS-sized, not pixel-mapped 1:1 like the Pygame window was) | Done — no rescaling needed since positions are mapped through normalized `[0,1]` space either way, unlike Part Zero's raw-pixel approach |
| Latency/perf | ~30 FPS, paced by the server's `timestamp_ms += 33` and the socket packet rate | `requestAnimationFrame` + `detectForVideo`, uncapped (browser's own vsync pacing), `delegate: "GPU"` | **Confirmed** — tracking is responsive and real-time in practice, no perceptible lag versus the Python window. (Exact FPS/GPU-vs-CPU delegate not logged numerically; revisit with `performance.now()` deltas only if perf issues show up later.) |
| Camera permission flow | None — Python opens the camera directly via `cv2.VideoCapture`, no consent step | Explicit "Enable camera" button gate, per-reason rejection handling (`camera.js`'s `REJECTION_MESSAGES`), visible active indicator (`#camera-indicator`), explicit "Disable camera" button, `track.stop()` on `beforeunload` | Done — this is a net-new capability versus Part Zero, not a port; see Specification.md §9 |
| Model loading vs. camera gate | N/A (single process, no separate "model loading" step) | `createHandLandmarker()` starts on page load, in parallel with waiting for the user to click "Enable camera" — cuts perceived wait, and doesn't touch the camera itself so it doesn't need to be gated | Design decision, not a parity concern |

## How this was verified

1. Ran the Python pipeline (`Hand_detection/Local_pc/Movement_with_hand_detection/launch.bat`)
   and the deployed web page (`https://dsug1.github.io/vision_pipeline_python/`)
   side by side.
2. Moved a hand right/left/up/down in front of the camera in both at once —
   the cube moved the same direction and reached the window edges the same
   way in both.
3. Used the `#debug-readout` panel on the web page (handedness, raw and
   mirrored X) to cross-check against the Python window without opening
   devtools.

Part Zero-bis's §5 deliverable (this file, with real findings instead of
design-time predictions) is complete.
