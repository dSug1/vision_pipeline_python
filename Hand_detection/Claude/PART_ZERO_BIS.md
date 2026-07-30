# Part Zero-bis — what it does and what changed

Implements §5 of `Specification.md`: port Part Zero's minimal loop — hand
detection + cube follows fingertip — to the browser, once, early, on the
simplest possible pipeline, so porting problems (coordinate systems,
mirroring, camera resolution, permissions, perf) surface now instead of
after Pipeline A/B get complex.

Code lives in `Hand_detection/Part_Zero_Bis_Web/` — a sibling of this
`Claude/` folder and of `Part_Zero_local_pc/` (which holds the Python
pipeline: `Movement_with_hand_detection/` and
`Python_Server_MediaPipe_vision_pipeline/`), not inside either. It's a
standalone Vite/npm project (JS, not Python), so it gets its own top-level
folder rather than being squeezed into the Python pipeline's structure. See
that folder's `README.md` for how to run it and `NOTES.md` for the
Python↔browser comparison findings §5 asks for.

## What Part Zero-bis actually is

Part Zero (`PART_ZERO.md`) is two Python processes — a MediaPipe server and
a Pygame client — talking over a local socket. Part Zero-bis collapses that
into a single browser page, since there's no separate "server process" once
detection runs client-side:

- **`src/camera.js`** — the one `getUserMedia()` call in the app. Gated
  behind an explicit "Enable camera" button (Specification.md §9), with
  distinct handling for each rejection path (denied, no device, in use,
  insecure context, unsupported browser), a visible active-camera indicator,
  an explicit "Disable camera" button, and `track.stop()` on page unload.
  This is new relative to Part Zero — the Python version has no consent step
  at all, since `cv2.VideoCapture` talks straight to the OS driver.
- **`src/handTracker.js`** — wraps `@mediapipe/tasks-vision`'s
  `HandLandmarker` in `VIDEO` mode, using the **same `hand_landmarker.task`
  model file** the Python server uses (copied in via
  `scripts/copy-mediapipe-assets.mjs`, not re-downloaded from anywhere) —
  the JS analog of `Resources/inference.py`.
- **`src/cubeScene.js`** — a trivial Three.js scene: one cube, fixed camera,
  no orbit controls, no physics — the JS analog of Part Zero's
  `CubeWindow.py`.
- **`src/main.js`** — bootstraps all three: starts loading the hand model
  immediately on page load (doesn't touch the camera, so it isn't gated),
  and once both the model is ready and the camera is enabled, runs a
  `requestAnimationFrame` loop that detects the left hand's index fingertip
  (landmark 8, same index as the Python side) each frame and moves the cube.

## What's different from Part Zero, and why

- **No server/client split, no socket.** Detection and rendering both run
  in the same page — there's nothing to send landmark data *to*, so the
  `"hands"`/`"meta"` packet protocol Part Zero uses doesn't apply here. (It
  will resurface conceptually in Phase 2's Pipeline A/B split, just as
  in-process JS calls instead of a network protocol — see Specification.md
  §2's Phase 2 diagram.)
- **Mirroring is explicit and client-side.** Part Zero's server mirrors X
  server-side (`remap_keypoints(..., invert_x=True)`) before ever sending
  coordinates. Here, `HandLandmarker` returns normalized `[0,1]`
  coordinates as-is, and `main.js` mirrors X (`1 - x`) itself before mapping
  to Three.js world space — see `NOTES.md` for why this needs an empirical
  check, not just a docs-based assumption, before it's trusted.
- **Camera resolution is read, not assumed or hardcoded.** Same principle
  Part Zero was fixed to use (§4/`PART_ZERO.md`'s `"meta"` packet): here,
  `camera.js`'s `getTrackResolution()` reads `track.getSettings()` after
  `getUserMedia()` resolves. Logged for comparison in `NOTES.md`; not used
  to resize anything, because positions are mapped through normalized
  `[0,1]` space on both ends here — there's no raw-pixel window to size, the
  way Part Zero's Pygame window needed sizing.
- **MediaPipe assets are bundled same-origin**, not loaded from MediaPipe's
  quickstart CDN — `scripts/copy-mediapipe-assets.mjs` copies the wasm
  runtime out of `node_modules` and the model file out of the Python
  pipeline's own `Resources/` folder into `public/` at install time
  (Specification.md §10).

## How to run it locally

See `Hand_detection/Part_Zero_Bis_Web/README.md`. Short version: `npm
install && npm run dev` in that folder, then open the printed local URL and
click "Enable camera."

## Deployed on GitHub Pages

Live at `https://dsug1.github.io/vision_pipeline_python/`. Deployed by
`.github/workflows/deploy-part-zero-bis.yml` (repo root, not under
`Hand_detection/` — GitHub Actions requires workflows there).

- **Trigger:** push to *any* branch that touches
  `Hand_detection/Part_Zero_Bis_Web/**` (also runnable manually from the
  Actions tab — `workflow_dispatch`). Not restricted to `main`: this repo's
  workflow is a chain of version-numbered branches that never get merged
  into `main`, so whatever branch you push last is what ends up live —
  there's no separate "production branch" gate.
- **Build:** `npm ci` then `npm run build -- --base=/vision_pipeline_python/`
  — the `--base` matters because GitHub project-pages serve at
  `https://<user>.github.io/<repo>/`, not domain root; `src/handTracker.js`
  reads `import.meta.env.BASE_URL` (rather than hardcoding `/`) specifically
  so its same-origin asset paths (`mediapipe/wasm`, `models/hand_landmarker.task`)
  still resolve correctly under that sub-path.
- **One-time setup already done:** repo Settings → Pages → Source: "GitHub
  Actions."

## What's not yet empirically verified

Everything in `NOTES.md`'s table marked **TO VERIFY** — chiefly, whether the
mirrored-X mapping and MediaPipe JS's "Left"/"Right" handedness labels
actually produce the same hand-moves-right → cube-moves-right behavior as
the Python window, side by side, on a live camera. That requires a human
running both at once; this was built and reasoned through from documented
MediaPipe/browser behavior, not confirmed against hardware from here.

## Next step

Part One (§7): back on PC, build real gesture recognition (`features.py`,
`rules.py`) against the existing Python pipeline — informed by whatever
`NOTES.md` turns up here, but not blocked on it. Not started yet.
