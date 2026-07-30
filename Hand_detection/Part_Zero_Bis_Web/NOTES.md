# Part Zero-bis — porting notes (Python → browser)

Per Specification.md §5, this records what had to be adjusted going from Part
Zero's Python/Pygame version to this browser/Three.js version. Items marked
**TO VERIFY** were reasoned from documented MediaPipe/browser behavior while
writing the code, not confirmed against a live camera — do that first, then
fill in the "confirmed" column below.

| Item | Python (Part Zero) | Browser (Part Zero-bis) | Status |
|---|---|---|---|
| Landmark model | `mediapipe` 0.10.14, `hand_landmarker.task`, VIDEO mode | `@mediapipe/tasks-vision` 1.0.0, **same `hand_landmarker.task` file** (copied via `scripts/copy-mediapipe-assets.mjs`), VIDEO mode | Same model file, same 21-point index order — no remapping needed (per Specification.md §6) |
| Coordinate convention | Pixel coords, `invert_x=True` mirror applied server-side before sending | Normalized `[0,1]` image-space landmarks from `HandLandmarker`, mirrored client-side (`1 - x`) before mapping to Three.js world space | **TO VERIFY**: confirm mirrored X actually makes "hand moves right → cube moves right" match the Python window, by running both side by side |
| Handedness → "Left" | `extract_hand_by_type(..., "Left")` on MediaPipe's own handedness label | `extractHandByType(result, "Left")`, same label source | **TO VERIFY**: confirm MediaPipe JS's "Left"/"Right" labels agree with the Python `mediapipe` package's labels for the same physical hand in front of the same camera — comment in `handTracker.js` states the assumption (handedness is reported from the subject's perspective, mirror-aware) but this needs an empirical check, not just doc-reading |
| Camera resolution | Server reads real `frame.shape` once, sends a `"meta"` packet, client resizes the window to match (`Claude/PART_ZERO.md`) | `camera.js`'s `getTrackResolution()` reads `track.getSettings().width/height` after `getUserMedia()` resolves; logged to console, not yet used to resize anything (there's nothing to resize — the Three.js canvas is CSS-sized, not pixel-mapped 1:1 like the Pygame window was) | Done — logged for comparison; no rescaling needed since positions are mapped through normalized `[0,1]` space either way, unlike Part Zero's raw-pixel approach |
| Latency/perf | ~30 FPS, paced by the server's `timestamp_ms += 33` and the socket packet rate | `requestAnimationFrame` + `detectForVideo`, uncapped (browser's own vsync pacing), `delegate: "GPU"` | **TO VERIFY**: note actual FPS achieved and whether GPU delegate is actually active on this machine (falls back to CPU silently if not) — log `performance.now()` deltas between frames |
| Camera permission flow | None — Python opens the camera directly via `cv2.VideoCapture`, no consent step | Explicit "Enable camera" button gate, per-reason rejection handling (`camera.js`'s `REJECTION_MESSAGES`), visible active indicator (`#camera-indicator`), explicit "Disable camera" button, `track.stop()` on `beforeunload` | Done — this is a net-new capability versus Part Zero, not a port; see Specification.md §9 |
| Model loading vs. camera gate | N/A (single process, no separate "model loading" step) | `createHandLandmarker()` starts on page load, in parallel with waiting for the user to click "Enable camera" — cuts perceived wait, and doesn't touch the camera itself so it doesn't need to be gated | Design decision, not a parity concern |

## How to fill in the TO VERIFY rows

1. Run the Python pipeline (`Movement_with_hand_detection/launch.bat`) and this
   page (`npm run dev` in this folder) side by side.
2. Move your left hand right/left/up/down in front of the camera in both at
   once. Confirm the cube moves the same direction in both windows.
3. Watch the `#debug-readout` panel on the web page (handedness, raw and
   mirrored X) while doing this — it's there specifically to make this
   comparison possible without opening devtools.
4. Update this table's Status column with what was actually observed instead
   of the design-time assumption.
