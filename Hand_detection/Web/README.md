# Web

Browser port of Part Zero's cube-follows-fingertip loop. See
`Hand_detection/Claude/PART_ZERO_BIS.md` for what this is and why, and
`NOTES.md` in this folder for Python↔browser porting findings. (Folder
renamed from `Part_Zero_Bis_Web` to `Web` once it became the ongoing browser
pipeline rather than a Part-Zero-bis-specific artifact — see
`Hand_detection/Claude/PART_ONE.md` §1.)

This folder lives directly under `Hand_detection/`, as a sibling of
`Local_pc/` (which holds the Python pipeline —
`Movement_with_hand_detection/` and `Python_Server_MediaPipe_vision_pipeline/`)
— not inside it, since this is a standalone JS/npm project.

## Run it

```
npm install     # also copies MediaPipe's wasm + the shared hand_landmarker.task
                 # into public/ (postinstall) — see scripts/copy-mediapipe-assets.mjs
npm run dev      # starts Vite's local dev server (http://localhost:5173 by default)
```

Open the printed local URL, click **Enable camera**, allow access, then move
your left hand in front of the camera — the cyan cube should track your
index fingertip. The debug panel under the canvas shows raw/mirrored
coordinates for comparing against the Python version (see `NOTES.md`).

```
npm run build    # production build to dist/
npm run preview  # serve the production build locally
```

## Structure

```
index.html              permission-gated UI: enable/disable camera buttons,
                          camera preview + active indicator, cube canvas,
                          debug readout
src/
  camera.js              the only getUserMedia() call in the app — permission
                          UX, per-reason rejection handling, resolution
                          detection, stop-on-unload (Specification.md §9)
  handTracker.js          HandLandmarker wrapper (VIDEO mode, same-origin
                          assets, same hand_landmarker.task as the Python side)
  cubeScene.js             trivial Three.js scene, one cube, fixed camera
  main.js                  wires it together: button gate -> detection loop
                          -> cube render
public/
  mediapipe/wasm/          copied from node_modules/@mediapipe/tasks-vision/wasm
  models/hand_landmarker.task
                            copied from ../Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/
scripts/
  copy-mediapipe-assets.mjs  the copy step above (runs on `npm install` via postinstall)
NOTES.md                     Python vs. browser porting findings (§5's deliverable)
```

`public/mediapipe/` and `public/models/` are gitignored — they're generated,
not source; re-run `npm install` (or `npm run copy-mediapipe-assets`) to
regenerate them after a fresh checkout.

## Why bundle MediaPipe's wasm/model files instead of using their CDN?

Specification.md §10: prefer same-origin assets over MediaPipe's quickstart
CDN pattern, to remove that external dependency's trust/availability risk
entirely. The model file is also already vetted — it's the exact file the
Python pipeline uses (`Hand_detection/Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/hand_landmarker.task`),
not a separately-sourced copy.
