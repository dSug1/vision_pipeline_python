# THE ORIGINAL PORT PLAN — verbatim

> **reference · Part Zero, Part Zero-bis, the landmark data contract, Snap Spectacles**
> **SOURCE** · `Specification.md` §4, §5, §6, §12 — extracted verbatim, not edited

⭐ §6's **shared landmark data contract** is the ancestor of `HandState` v2 and
is still the right frame for the port. §12 (Snap Spectacles) is design-for-later
only, not in scope.

---

<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 239-362
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 4. Part Zero — retarget cursor pipeline to move a cube on PC

**Goal:** smallest possible change to the existing pipeline that proves "finger position →
object position" instead of "finger position → OS cursor position."

- Start from the existing script that currently drives the PC cursor. Identify the exact
  point where it computes a finger-position signal (likely a single 2D point, e.g. index
  fingertip landmark, possibly smoothed) and where it currently calls into the OS
  (`pyautogui`/`ctypes`/etc. to move the cursor) — isolate that signal as a clean function
  output rather than something buried inside the cursor-moving call.
- Replace only the "move cursor" step with "move a cube in a local window":
  - Open a simple local window (Pygame is the lowest-friction choice for a single moving
    shape; a minimal OpenGL or even a matplotlib animation window is acceptable if
    Pygame's not already a dependency) alongside the existing webcam capture loop.
  - Draw one cube (2D square standing in for a cube is fine at this stage if a real 3D
    render isn't already trivial with what's on hand — the point is the control loop, not
    the visual fidelity) and update its position each frame from the same finger-position
    signal that used to drive the cursor.
  - Keep the webcam feed and MediaPipe detection code untouched — only the "what do we do
    with the coordinate" step changes.
- No gesture recognition, no multi-hand logic, no smoothing changes beyond what already
  exists — Part Zero is intentionally trivial. Resist the temptation to add polish here;
  extra scope belongs in Part One (§7), not here.
- **Deliverable:** a single script (or minimal change to the existing one) that opens a
  window, shows a cube, and moves it live as the hand moves in front of the webcam.

---

## 5. Part Zero-bis — port the minimal loop to the browser

**Goal:** do the Python→JS/WASM port once, early, on the simplest possible pipeline, so
porting problems are found and solved now — not later, once Pipeline A is complex.

- Build a minimal standalone web page: `@mediapipe/tasks-vision` `HandLandmarker` running
  in `VIDEO` mode against the browser's webcam feed, plus a trivial Three.js scene with a
  single cube whose position is updated each frame from the detected fingertip landmark —
  the direct JS analog of Part Zero's `cube_window.py`.
- **Reference before building from scratch**: `collidingScopes/threejs-handtracking-101`
  (see §1) is a close scope match — one shape, pinch-driven interaction, Three.js +
  MediaPipe, no backend. Read its camera-permission handling and its detection-loop
  structure (`requestAnimationFrame` + `detectForVideo`) before writing this from
  scratch — it can shortcut a lot of the "how do these two libraries actually fit
  together in a browser" groundwork, subject to the usual review-before-reuse (§10).
- Explicitly compare against Part Zero's Python behavior while building this:
  - **Coordinate systems**: MediaPipe Python and MediaPipe Tasks Vision JS both use the
    same 21-point landmark model and the same normalized `[0,1]` image-space convention,
    but confirm this empirically (log/print both side by side) rather than assuming —
    also confirm which axis conventions Three.js expects for the cube's position and
    whether any flip/rescale is needed going from normalized landmark space to Three.js
    world space.
  - **Mirroring**: webcam feeds are often displayed mirrored; confirm whether "hand moves
    right → cube moves right" holds the same way in both the Python window and the browser
    version, and fix any inversion consistently.
  - **Camera resolution**: don't assume a fixed capture resolution. Part Zero's Python
    version originally hardcoded a 640×480 window before being fixed to have the server
    read the webcam's actual `frame.shape` and send it once to the client as a `"meta"`
    packet, which the client uses to size the cube window correctly (see
    `Claude/PART_ZERO.md`). Do the browser-side equivalent: read the active video track's
    real resolution — `track.getSettings().width`/`.height` (from the `MediaStreamTrack`
    obtained via `getUserMedia`), or the `<video>` element's `videoWidth`/`videoHeight`
    once its `loadedmetadata` event fires — and use that when mapping the fingertip
    landmark to the Three.js cube's position, rather than hardcoding an assumed
    resolution. Note this in `NOTES.md` either way (confirmed same behavior, or had to
    fix an assumption) since it's a concrete parity point with the Python side.
  - **Latency/perf**: sanity-check that `detectForVideo` in a `requestAnimationFrame` loop
    keeps up in real time; note the delegate setting used (`GPU` vs `CPU`) and any
    frame-rate difference versus the Python pipeline.
  - **Camera permission flow**: this is the first point in the whole project where a
    browser actually asks for camera access — implement the real permission UX from §9
    here already (explicit enable button, rejection handling, visible "camera active"
    indicator), don't defer it to Phase 2. Getting it right on the trivial cube case means
    Phase 2 reuses working code instead of debugging permissions and gesture logic at once.
- **Record findings in `/part-zero/web/NOTES.md`**: anything that had to be adjusted
  between the Python and JS versions (coordinate flips, scaling constants, permission
  quirks, performance ceilings). This document is the whole point of Part Zero-bis — it's
  what makes the eventual Phase 2 port (§11) low-risk instead of a fresh unknown.
- **Deliverable:** a local web page (served via any simple local dev server — Vite is fine
  to introduce here already, since §3's Phase 2 `/web` layout will want it anyway) that
  asks for camera permission, then shows a cube moving live with the hand, matching Part
  Zero's Python behavior.
- **Do not** build Pipeline A or Pipeline B logic here — this stays scoped to one cube,
  one point, proving the port mechanics only.

---

## 6. Shared landmark data contract (Part One → Phase 2 portability)

Define this once, keep it identical in Python and JS, so Pipeline A code ports 1:1.

```jsonc
// One "frame" — matches MediaPipe's own landmark structure closely on purpose
{
  "timestamp_ms": 1234567.0,
  "hands": [
    {
      "handedness": "Right",        // as reported by MediaPipe (mirror-aware)
      "score": 0.98,
      "landmarks": [                 // 21 points, NORMALIZED image coords [0,1]
        {"x": 0.51, "y": 0.62, "z": -0.03}, // 0 = wrist
        ...                                  // ... up to 20 = pinky tip
      ],
      "world_landmarks": [           // 21 points, METRIC 3D coords (meters, hand-relative)
        {"x": 0.01, "y": -0.02, "z": 0.001},
        ...
      ]
    }
  ]
}
```

Notes:
- Use **world_landmarks** (metric, depth-aware) for Pipeline B object manipulation —
  they're scale/perspective invariant, which normalized image-space landmarks are not.
- Use **normalized landmarks** (or world_landmarks, test both) for Pipeline A gesture
  recognition — normalize further by subtracting the wrist landmark and scaling by a
  hand-size reference distance (e.g. wrist→middle-finger-MCP) before feature extraction.
  This normalization step is what the literature consistently flags as the single biggest
  accuracy lever — do this before anything else in `features.py`/`features.js`.
- Landmark index order (0=wrist, 4=thumb tip, 8=index tip, 12=middle tip, 16=ring tip,
  20=pinky tip, etc.) follows MediaPipe's standard 21-point hand model — identical in
  Python `mediapipe` and JS `@mediapipe/tasks-vision`, so no remapping needed between phases.

---

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 667-719
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
## 12. Future direction: Snap Spectacles port (not in scope now — design-for-later only)

**Not a build target for this project as currently scoped.** No code in Part Zero through
Phase 2 should be written to accommodate this — it's captured here so gesture-vocabulary
and asset decisions made now don't accidentally make a later port harder than it needs to
be. Revisit only after Phase 2 is deployed and working.

### 12.1 What this would actually be

Snap's AR glasses (Spectacles) run their own OS with **native hand tracking as a hardware
feature**, exposed in Lens Studio via the **Spectacles Interaction Kit (SIK)**. SIK's hand
data is conceptually close to what this project already produces: named landmark access
(e.g. index fingertip position), pinch-down events, and an `Interactable` component system
for driving scene-object manipulation from hand input — i.e., a SIK-based Lens is doing the
same job as this project's Pipeline A → Pipeline B pipeline, just on Snap's own SDK and
runtime instead of MediaPipe + Three.js.

**This would not be a code port — it would be a rebuild in a different engine.** Lens
Studio uses its own scripting environment, not JavaScript/Three.js, so none of Pipeline A's
or Pipeline B's *code* carries over. What transfers is the **design**, not the
implementation:
- The gesture vocabulary and thresholds (open/fist/pinch/point, translation, rotation —
  §7.2's table) — as a specification to re-implement against SIK's `HandInputData` /
  `HandInteractor` APIs, not as portable code.
- The Blender-authored `.glb` assets (§8.2) — glTF is a standard interchange format; the
  same Blender exports used for the Three.js scene should import into Lens Studio with
  little to no rework.
- The manipulation state machine (idle → hover → grabbed → released, §8.3) — the same
  logical design, re-expressed against SIK's `Interactable` component model.

### 12.2 Why not now

- Spectacles 5th gen is currently a developer-kit device distributed through Snap's
  Spectacles Developer Program to approved studios/developers, not a broadly available
  consumer product — a general "consumer" audience isn't reachable on this hardware yet.
  Revisit this section once that changes (Snap has signaled a consumer version, branded
  "Specs," is coming) rather than building for it speculatively now.
- Camera Kit for Web (Snap's SDK for embedding a Lens into a third-party web page) is a
  *different* thing from Spectacles hardware access — it lets a Lens run inside a webpage
  via the browser's own camera, but does not get this project's Three.js scene running on
  Spectacles. It's only relevant if a future goal is layering a Snapchat-style AR filter
  onto the web version of this project, not as a path to the glasses.

### 12.3 The one thing worth doing now, for free

`gestureConfig.js` is already required to stay engine-agnostic as a hard rule — see §7.4
for the concrete constraints (plain data only, no Three.js/MediaPipe imports, single
JSON spec shared by both runtimes). This costs nothing extra today and is exactly the
artifact a future SIK rebuild would start from — enforcing it now is what makes that
option cheap later rather than a rewrite.

---

<!-- VERBATIM-END -->
