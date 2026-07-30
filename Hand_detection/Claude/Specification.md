# Hand-Tracking Object Manipulation Game — Build Handoff

## 0. Goal & constraints (read first)

Build a browser-based 3D "game" where hand movements captured by webcam manipulate
3D objects, using MediaPipe hand landmarks as input.

Hard constraints from the owner:
- **No Unity. No OpenCV.** Everything client-facing ends up in the browser (WebGL / Three.js).
- **No physics engine** for v1 — direct kinematic manipulation of objects (position/rotation
  driven straight from hand transform), not force/collision simulation.
- **3D assets authored in Blender**, exported to whatever format WebGL/Three.js consumes
  natively (glTF/GLB — see §8).
- **Camera access rights must be explicitly managed** in the browser (permissions UX,
  not just `getUserMedia()` fire-and-forget) — see §9.
- **Cybersecurity requirements apply throughout**: browsing/research, dependency selection,
  coding practices, and cloud deployment — see §10. This is a standing requirement, not a
  final checklist item — apply it at each part below, starting with Part Zero.
- **Four-part development path (important — design for this explicitly):**
  - **Part Zero (now, on PC):** take the *existing* Python MediaPipe pipeline, which
    currently moves the PC mouse cursor from detected finger position, and retarget it:
    instead of moving the OS cursor, open a simple local window (e.g. Pygame or a minimal
    OpenGL/matplotlib window — whatever's fastest to stand up) containing one cube, and
    move that cube using the same finger-position signal that used to drive the cursor.
    This is a minimal, deliberately low-effort milestone — its only purpose is to prove
    "landmark → 2D/3D object position" works end to end before any other complexity is
    added.
  - **Part Zero-bis (now, port to browser):** port *that same minimal loop* — hand
    detection + cube-follows-finger — to JavaScript/WASM, running 100% in-browser
    (MediaPipe Tasks Vision JS + a trivial Three.js scene with one cube). This is a
    deliberate early dry run of the Python→browser port, done on the *simplest possible*
    pipeline, specifically to surface porting problems (camera permissions, MediaPipe JS
    API differences, coordinate system differences, performance) while the logic being
    ported is still trivial — not after Pipeline A has grown complex. Treat Part Zero-bis
    as the risk-reduction step for the eventual Phase 2 port in §5.
  - **Part One (later, stays on PC):** develop Pipeline A proper (pattern/gesture
    recognition beyond a single cursor point) using the existing Python MediaPipe pipeline
    as the data source. This part does **not** move to the browser yet — it stays a PC-side
    R&D effort, informed by what Part Zero-bis already taught about portability.
  - **Phase 2 (later, production):** once Pipeline A's gesture logic is validated on PC,
    port it to JavaScript/WASM and run 100% in-browser — this port should now be
    low-risk, since Part Zero-bis already validated the porting mechanics on a simpler
    case.
  - **Design implication:** Pipeline A's gesture-recognition logic must be written so its
    *core algorithm* (feature extraction + classification/threshold logic) is portable
    between Python (numpy) and JS with minimal re-architecture — i.e., keep it as pure
    functions over a landmark-array data structure, not entangled with Python-only
    libraries (no pandas, no sklearn Pipeline objects if avoidable — prefer plain numpy /
    a tiny hand-rolled MLP so the trained weights can be exported as flat arrays and
    re-implemented as a forward-pass in JS, or exported to ONNX/TF.js if a real NN is used).
    Apply this same discipline even in Part Zero, small as it is — it's the first proof
    point for the pattern.

---

## 1. Prior art — close matches found on the web (use as reference, review before reuse)

Several public projects already implement close variants of this exact stack (MediaPipe
hands + Three.js, all client-side, static hosting, no backend). Worth cloning and reading
before scaffolding Part Zero-bis and Pipeline B — they validate the architecture choices
in this handoff and can save time on the fiddly bits (camera permission UX, gesture-to-
transform mapping, runtime glTF loading). **Review each per §10's security requirements
before reusing any code** — read before integrating, don't copy-paste unread.

**Closest match — directly relevant to Pipeline B:**
- **3D Model Playground** (stereoDrift, Hugging Face Space + GitHub
  `collidingScopes/3d-model-playground`): pinch-to-manipulate a 3D model in real time,
  built with Three.js + MediaPipe hand tracking, entirely client-side, static hosting (no
  build step, no backend — served via a plain local HTTP server for dev). Supports
  drag/drop import of GLB/GLTF models at runtime via `GLTFLoader`, and switches
  interaction mode (drag/rotate/scale/animate) via voice command layered on top of the
  gesture control. This is the single closest match to your Pipeline B goal — same stack,
  same "pinch to grab, no physics" interaction model, same static-hosting deployment
  target. **Read this one closely for**: the camera-permission gate implementation, the
  pinch-detection → object-transform mapping, and the runtime GLTFLoader usage pattern —
  all three map directly onto §5, §8, and §9 of this handoff.
- **threejs-handtracking-101** (`collidingScopes/threejs-handtracking-101`, same author,
  simpler/earlier project): pinch-to-resize a single 3D sphere, live demo at
  `collidingscopes.github.io/threejs-handtracking-101`. A stripped-down precursor to the
  project above — smaller surface area, good minimal reference specifically for **Part
  Zero-bis** (§5) since it's close to the "one shape, one gesture" scope Part Zero-bis
  targets, before Pipeline A/B complexity is added.

**Adjacent — different interaction model, same stack, worth knowing about:**
- **3D Connect-4** (React Three Fiber + Vite + MediaPipe hand-gesture control + Minimax
  AI): shows the stack used for an actual game with real game logic and win conditions,
  not just a manipulation demo — useful if the project grows toward a rules-based game
  rather than free-form object manipulation.
- **three-mediapipe-rig** (`bandinopla/three-mediapipe-rig`): binds MediaPipe landmarks to
  a Three.js skeletal rig (maps landmarks to bones for body/hands/face). Not directly
  needed for kinematic cube/object manipulation, but relevant if a later iteration wants a
  visible tracked hand model rendered in-scene rather than using landmarks purely as an
  input signal.
- **webxr-handtracking-playground** (`beemsoft/webxr-handtracking-playground`): same
  MediaPipe-hands-in-Three.js idea, but prefers the browser's native WebXR hand tracking
  when available and falls back to MediaPipe otherwise — a possible future direction if
  WebXR/VR headset support is ever wanted, out of scope for now.

**Takeaway for this handoff:** the architecture in §2–§3 (Three.js + MediaPipe Tasks
Vision JS, no backend, static hosting) isn't speculative — it's what's already running in
production for a near-identical use case (stereoDrift's Space). Where this handoff's
design choices and the prior art agree, treat that as validation; where they diverge
(e.g. this project's no-physics constraint, the Part Zero/Zero-bis dry-run staging, the
Python-pipeline starting point), the prior art doesn't need to be followed — it's a
reference, not a spec.

---

## 2. High-level architecture

**Note to Claude Code: adapt this to the actual current repo, don't impose it wholesale.**
Before restructuring anything, inspect the existing Python MediaPipe cursor-control
pipeline's current folder layout, module names, and how it currently reads landmarks and
drives the cursor. Preserve its structure where reasonable and integrate the new pieces
below into it (e.g. as new sibling modules/folders) rather than forcing a rewrite into the
layout sketched in §3. The layout in §3 is a target shape for the *new* pieces (Part Zero
outputs, Pipeline A, Pipeline B) — treat the existing cursor-control code as the starting
point for Part Zero, not something to discard.

```
PART ZERO / ZERO-BIS         PART ONE (dev/train on PC)          PHASE 2 (production, all-browser)
(on PC → then browser)       ─────────────────────────           ──────────────────────────────
Webcam                       Webcam                               Webcam
  │                            │                                    │
  ▼                            ▼                                    ▼
Existing Python              Python + MediaPipe (existing         MediaPipe Tasks Vision JS
MediaPipe pipeline            pipeline, extended)                   (HandLandmarker, client-side
(currently: cursor)            │  → JSON landmarks per frame          WASM/GPU)
  │                            ▼                                    │  → landmarks per frame
  ▼ (Part Zero: retarget    Pipeline A prototype (Python/numpy)      │  (in-memory, no JSON file,
    to move a cube in a       │  gesture/pattern recognition          │  no network hop)
    local window instead      │  (rule-based + optional lightweight  ▼
    of the OS cursor)         │   MLP/LSTM, trained offline)        Pipeline A (ported to JS)
  ▼                           ▼                                      │  same feature extraction
  Local window, 1 cube      Offline validation only —                │  + classifier, validated
                             NOT connected to a live game            ▼  in Part Zero-bis
  ▼ (Part Zero-bis: port                                            Pipeline B (Three.js scene)
    this same minimal                                                object transforms driven by
    loop to browser)                                                 recognized gestures/pose,
  ▼                                                                   no server round-trip
  MediaPipe Tasks Vision JS
  + Three.js, 1 cube
  (browser, dry-run port)
```

Key decisions:
- **Part Zero and Part Zero-bis are a deliberately small, fast dry run.** One cube, one
  positional signal, no gesture classification yet. Their entire purpose is to de-risk the
  Python→browser port mechanics early, cheaply, before Pipeline A exists.
- **Part One has no game and doesn't move to the browser.** It's pure gesture-recognition
  R&D against recorded/live Python-pipeline JSON, informed by Part Zero-bis's findings.
  Don't build a Python↔browser bridge (no WebSocket server) for Part One — that would be
  throwaway infrastructure since Phase 2 eliminates Python entirely. Time is better spent
  making Pipeline A's core logic trivially portable, the same way Part Zero-bis proved out.

---

## 3. Repo layout (target shape for new pieces — adapt to existing repo, see §2)

```
/hand-game
  /part-zero/                 # Part Zero + Zero-bis: minimal port dry-run
    /pc/                       # retargeted existing pipeline: cube instead of cursor
      cube_window.py            # local window (Pygame/OpenGL/etc.) + 1 cube driven by
                                 # the existing pipeline's finger-position signal
      README.md                 # what changed vs. the original cursor-control script
    /web/                       # ported version: same minimal loop, in-browser
      index.html
      package.json
      /src
        main.js                 # bootstrap, permission flow, render loop
        camera.js                # getUserMedia + permission UX (§8) — same module used
                                  # later by /web in §3's Phase-2 layout; write it once here
        handTracker.js           # wraps @mediapipe/tasks-vision HandLandmarker
        cubeScene.js             # trivial Three.js scene, 1 cube, position driven by
                                  # fingertip landmark — the JS mirror of cube_window.py
      NOTES.md                   # record porting friction found here (coordinate system
                                  # differences, permission quirks, perf) — feed forward
                                  # into Phase 2 port later

  /pipeline-a-dev/            # Part One: Python gesture-recognition R&D (extends the
                               # existing pipeline; throwaway/reference for the JS port)
    capture_to_json.py        # wraps existing MediaPipe python pipeline, writes per-frame JSON
    landmarks_schema.md        # documents the JSON shape (see §6)
    features.py                # pure functions: landmarks -> normalized features
    rules.py                   # rule-based static gesture classifiers (pinch, fist, open, point)
    temporal.py                # sliding-window buffer + dynamic gesture classifier
    train_classifier.py        # optional: trains lightweight MLP/LSTM, exports weights as JSON/ONNX
    recordings/                 # sample JSON sessions for testing (gitignored if large)
    tests/
      test_features.py
      test_rules.py

  /web/                        # Phase 2: production, all-browser
    index.html
    package.json
    vite.config.js             # or similar bundler config
    /src
      main.js                  # app bootstrap, permission flow, render loop
      camera.js                 # getUserMedia + permission UX (§8) — reuse/evolve from
                                  # /part-zero/web/src/camera.js
      handTracker.js            # wraps @mediapipe/tasks-vision HandLandmarker
      /pipelineA
        features.js             # PORTED from features.py — same math, same function names
        rules.js                 # PORTED from rules.py
        temporal.js              # PORTED from temporal.py
        classifier.js            # loads exported weights, runs forward pass (if NN used)
      /pipelineB
        scene.js                 # Three.js scene setup, camera, lights
        assetLoader.js           # GLTFLoader wrapper
        objectController.js      # maps recognized gestures -> object transforms
      /gestures
        gestureConfig.js         # SINGLE SOURCE OF TRUTH: gesture names, thresholds,
                                  # mapped to game actions (grab, rotate, release, etc.)
                                  # ENGINE-AGNOSTIC (see §7.4) — plain data, no Three.js/
                                  # MediaPipe imports; consumed by pipelineA and pipelineB
                                  # but owned by neither
    /assets
      /models                    # .glb files exported from Blender (see §8)
    /public

  /docs
    SECURITY.md                 # §9, expanded into a living checklist
    ARCHITECTURE.md              # this file, or a trimmed version, kept in-repo

  .gitignore
  README.md
```

---

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

## 7. Pipeline A — gesture/pattern recognition

### 7.1 Two source options — use both, layered

1. **Primary: custom rule-based + lightweight learned classifier over MediaPipe's raw
   landmarks.** This is the recommended default and what most prior art converges on:
   - **Static poses** (open hand, fist, pinch, point, thumbs-up, "grab"): pure geometric
     rules on normalized landmarks — finger-extension test (tip vs. PIP joint position
     relative to MCP), inter-fingertip distances for pinch detection, palm-normal
     orientation from wrist + MCP points. No training data needed. Implement first —
     covers most of what a manipulation game needs (grab = pinch or fist, release = open,
     point = index-only extended).
   - **Dynamic/temporal gestures** (swipe, throw, rotate-twist, "closing" transition):
     maintain a sliding window (~20–30 frames) of normalized landmark sequences and
     classify with a small model — MLP if a single-frame feature vector (e.g. velocity of
     key points) suffices, otherwise a small LSTM/GRU or 1D-CNN over the window. Keep this
     model deliberately small (few thousand params) — it needs to run in real time in a
     browser WASM/JS context in Phase 2, not a full sign-language-scale network.
   - Train offline in Python in Part One (`train_classifier.py`) on recorded sessions, then
     export weights in a portable form: either (a) flat JSON arrays of weights/biases for
     a hand-rolled forward pass reimplemented in JS (simplest, fully auditable, no extra
     runtime dependency), or (b) ONNX → onnxruntime-web / TensorFlow.js if the model is
     nontrivial enough to want a real inference runtime. Default to (a) unless the model
     grows past a simple MLP — keeps Phase 2 dependency surface smaller (see §10).

2. **Secondary/reference: MediaPipe's own Gesture Recognizer task.** It ships a pretrained
   gesture classification head on top of the hand landmarker and *can* be fine-tuned on
   custom gesture datasets via MediaPipe Model Maker. Since the game's target gestures
   differ from MediaPipe's built-in set (Thumbs_Up, Victory, etc.), don't rely on the
   built-in categories directly — either (a) use Model Maker to fine-tune a custom gesture
   head on your own recorded examples (least code to write, but adds a Model Maker
   training dependency and a black-box classification head vs. full control), or (b) skip
   the Gesture Recognizer task entirely and only use HandLandmarker + your own classifier
   from option 1 (full control, fully portable, no black box). **Recommendation: start
   with option 1 only.** Revisit MediaPipe's fine-tunable recognizer only if hand-rolled
   rules+small-model prove insufficient for the specific dynamic gestures the game needs.

### 7.2 Concrete gesture set to implement first (adjust to game design)

Keep this list in `gestureConfig.js` / a Python equivalent as the single source of truth
consumed by both Pipeline A (what to detect) and Pipeline B (what action it triggers) —
see §7.4 for the rules that keep this file portable rather than tangled into either side.

| Gesture | Type | Detection approach | Game action |
|---|---|---|---|
| Open hand | static | finger-extension rule (all 4 fingers extended) | release object |
| Fist / pinch | static | finger-flexion rule or thumb-index distance < threshold | grab object |
| Point (index only) | static | index extended, others flexed | pointer/cursor mode |
| Hand translation | continuous | wrist (or palm centroid) world_landmark position, smoothed | move grabbed object |
| Wrist rotation/twist | continuous | palm normal vector from landmark geometry | rotate grabbed object |
| Swipe | dynamic | velocity spike + direction over sliding window | fling/dismiss object |

### 7.3 Testing strategy

- `tests/test_features.py` and `tests/test_rules.py`: unit tests against **synthetic
  landmark fixtures** (hand-authored JSON for "clearly open hand", "clearly fist", etc.) —
  don't require a live webcam to run CI.
  - Store fixtures in `recordings/` as short recorded JSON sessions captured with the
    existing Python pipeline for real-world validation, but keep unit tests on synthetic
    fixtures so they're deterministic and fast.
- When porting `features.py` → `features.js`, add a **parity test**: run the same fixture
  JSON through both implementations and assert numerically equal outputs. This is the
  actual guarantee that Phase 2 preserves Phase 1 behavior — treat it as required, not
  optional, before considering the port done.

### 7.4 `gestureConfig.js` must stay engine-agnostic — enforce this from the start

This file (and its Python-side equivalent, e.g. `gesture_config.py` / a shared
`gesture_config.json`) is the one artifact in this project explicitly designed to outlive
any single engine choice — it's what a future Spectacles/SIK rebuild (§12) would start
from, and what keeps Pipeline A and Pipeline B decoupled from each other today. Treat the
following as hard rules, not style preferences:

- **Plain data only — no imports from Three.js, MediaPipe, or any rendering/detection
  library.** The file should be expressible as pure JSON (or a JS/Python object literal
  that trivially serializes to JSON) — gesture names, thresholds, detection-approach
  labels, and the game-action string each gesture maps to. If a value can't survive a
  round-trip through `JSON.stringify`/`json.dumps`, it doesn't belong in this file.
- **No functions, no class instances, no engine-specific types** (no `THREE.Vector3`
  defaults, no MediaPipe enum references) — thresholds are plain numbers, positions/axes
  are plain `{x, y, z}` objects if needed, not library-specific vector types.
- **Consumed, not owned, by both pipelines.** `pipelineA/rules.js` and
  `pipelineA/temporal.js` read thresholds from it to decide *what gesture occurred*;
  `pipelineB/objectController.js` reads the action mapping to decide *what to do about
  it*. Neither pipeline should write to it at runtime, and neither should extend it with
  engine-specific fields — if Pipeline B needs Three.js-specific tuning (e.g. an easing
  curve for a particular action), that belongs in `objectController.js` itself, keyed off
  the action name from `gestureConfig.js`, not added into the config file.
- **One file, two runtimes.** Since Part One's Python pipeline and Phase 2's JS pipeline
  both need the same gesture definitions, prefer maintaining this as a single JSON file
  loaded by both (Python via `json.load`, JS via `import`/`fetch`) over hand-syncing two
  separate language-native files — this also makes the §7.3 parity tests stronger, since
  both implementations are provably reading the identical spec rather than two files that
  could silently drift apart.
- **Review this file specifically whenever adding a gesture** — if adding a new gesture
  requires touching anything outside `gestureConfig.js` plus the relevant detection
  function body, check whether engine-specific detail leaked into the config by mistake.

### 7.5 Part One's concrete first-pass design (rotation, grab arbitration, gimbal lock)

Recorded here so it's available at the spec level when the gesture set is next enriched;
full detail and the enrichable gesture matrix live in `Claude/PART_ONE.md` — read that
file before adding a new gesture, don't just work from this summary. **For how any gesture
classifier actually gets built (recording, training, live validation) read
`Claude/GESTURE_PIPELINE_SPEC.md` first** — a hand-tuned-threshold pinch classifier was
built and then abandoned (structural rotation ambiguity a threshold couldn't fix, see
`PART_ONE.md` §6–§8 for the evidence); that spec is what replaced it and applies to every
gesture, not just pinch.

- **Live PC prototype, not offline-only.** Part One's first concrete build is a live,
  visually-tuned two-hand/two-cube manipulation prototype extending Part Zero's
  `CubeWindow.py` directly, not the offline-JSON-only R&D sketched in §2/§7 above — grab
  thresholds, rotation feel, and the depth-proxy mapping all need tuning against a live
  webcam feed to be validated at all, the same reasoning that made Part Zero-bis's
  coordinate mapping a live-verification exercise rather than a docs-only assumption.
- **Grab arbitration is the one cross-hand exception to "gestures are per-hand."** Either
  hand may grab either object (no fixed hand→object pairing), so a small shared registry
  (`{object: holding_hand | None}`) is needed: on a pinch rising-edge, claim the nearest
  *unowned* object within grab radius, skipping objects already owned by the other hand.
  Every other signal (pinch, translation, rotation, depth proxy) stays a pure per-hand
  computation with no cross-hand data — this is deliberately the minimum "combined" logic
  needed, not a general two-hand gesture-fusion system.
- **Rotation must be quaternion-based — never decompose to Euler angles.** Build hand
  orientation each frame as a quaternion from an orthonormal frame (Gram-Schmidt on
  `wrist→index_MCP` and `wrist→pinky_MCP` from `world_landmarks`), and slerp the object's
  quaternion toward it. Gimbal lock is a property of roll/pitch/yaw decomposition, not of
  the underlying rotation — so no per-axis Euler math at any point, including for
  smoothing (smooth the composed quaternion uniformly, not per-axis). Expect rotation
  about the axis orthogonal to the camera plane (twisting the wrist while facing the
  camera — a clean 2D rotation in image-space landmarks) to be reliable, and rotation
  about axes in the camera plane (tilting toward/away from the camera — pitch/yaw, which
  shows up mainly in `world_landmarks`' noisier `z` component) to be noisier — this is an
  inherent monocular-tracking limitation, not something to "fix," just to smooth harder
  against and verify empirically.
- **Depth proxy uses apparent hand size, not raw MediaPipe `z`.** Hand span in
  normalized/pixel image coordinates relative to a calibration baseline captured at grab
  time, mapped to object scale + color gradient only (no Z-axis translation yet,
  deliberately deferred) — active only while grabbed, not as a hover preview.

---

## 8. Pipeline B — Three.js scene + Blender asset pipeline

**Reference before building from scratch**: `stereoDrift/3d-model-playground` (see §1) is
the closest public match to this whole pipeline — same stack, same "pinch to grab, no
physics" model, same static-hosting target, and it already handles runtime GLTFLoader
usage for user-supplied models. Read its `game.js` for the gesture-detection-to-transform
logic and its camera-permission handling before implementing §8.3 and §9 from scratch —
subject to the review-before-reuse practice in §10.

### 8.1 Stack

- **Three.js** (WebGL). Use a bundler (Vite recommended — fast dev server, easy to later
  containerize the static build for hosting).
- No physics library for v1 (explicitly out of scope) — object manipulation is direct:
  recognized gesture + hand world-position → object transform (position/quaternion) each
  frame, with simple smoothing/lerp for stability, no collision/rigid-body simulation.

### 8.2 Blender → WebGL asset path

- **Export format: glTF 2.0 (`.glb`, binary/single-file preferred over `.gltf` + separate
  textures for simpler asset management).** This is the native, first-class format for
  Three.js — Blender has a built-in glTF exporter (File → Export → glTF 2.0), no plugins
  needed, and Three.js consumes it via `GLTFLoader` with no conversion step.
- Workflow: author/rig objects in Blender → `File → Export → glTF 2.0 (.glb)` → drop into
  `/web/assets/models/` → load via `GLTFLoader` in `assetLoader.js`.
- Keep exported models low-poly / optimized for real-time web rendering (this is a live
  webcam-driven interaction loop, not an offline render — frame budget matters). Consider
  `gltf-transform` or Blender's built-in export compression (Draco) if models get heavy.
- **If any assets originate as Mecabricks `.zmbx` files**: `.zmbx` is not natively
  WebGL-loadable. Path: export from Mecabricks (File → Export → "Blender Add-on") into
  Blender, then re-export from Blender as glTF following the same path above. (A
  third-party zmbx→glTF converter tool also exists if bypassing the Blender round-trip is
  preferred — vet it per §10 before using, since it's an unofficial small utility.)

### 8.3 Gesture → object manipulation mapping

- `objectController.js` subscribes to Pipeline A's recognized-gesture stream (in-process
  JS calls in Phase 2, not network messages) and updates Three.js object
  `position`/`quaternion` directly.
- Design for **one hand actively "holding" at most one object at a time** initially
  (simplest state machine: idle → hover → grabbed → released), extend to two-hand/
  two-object later if needed.
- `3d-model-playground`'s pinch-to-drag/rotate/scale mapping (see §1) is a working
  reference for this exact state machine — its "mode switch" concept (drag vs. rotate vs.
  scale, there triggered by voice command) also maps onto this project's `gestureConfig.js`
  single-source-of-truth idea if multiple manipulation modes are wanted later.

---

## 9. Camera permission handling (browser)

Required, not optional — build this as a real UX flow, not a bare `getUserMedia()` call:

- Explicit **"Enable camera" button/gate** before any `getUserMedia()` call — don't
  auto-prompt on page load (bad UX, and looks like a dark pattern to users/browsers).
- Handle and surface all rejection paths distinctly: user denies permission, no camera
  device present, camera in use by another application, browser blocks due to non-HTTPS
  context (getUserMedia requires a secure context — HTTPS or localhost, plan hosting
  around this from day one, see §10).
- Provide a visible way to know the camera is active (a live preview thumbnail or a clear
  "camera active" indicator) — don't run hand tracking on a hidden/invisible video element
  without the user being able to see that their camera is on.
- Stop all `MediaStreamTrack`s (`track.stop()`) on page unload/navigation and expose an
  explicit in-UI "disable camera" control — don't rely solely on the tab closing.
- No frame or landmark data leaves the browser in Phase 2 (all-in-browser design already
  guarantees this) — state that explicitly in a short in-app privacy note near the camera
  permission prompt, since "does my webcam feed get sent anywhere" is the natural user
  question for this kind of app.

---

## 10. Cybersecurity requirements (apply at every phase, not just at the end)

**When researching/borrowing from state-of-the-art (web, GitHub, HuggingFace, etc.):**
- Before pulling in any third-party code sample, snippet, or library found via search:
  check repo provenance (stars/activity/maintainer are weak signals but check them),
  license compatibility, and read the actual code for anything unexpected (obfuscated
  code, unexplained network calls, eval/exec patterns) before integrating — don't
  copy-paste unread code into the project, especially anything touching camera/media
  streams or anything that will run in Phase 2's browser context with camera access.
- Treat MediaPipe's own official packages (`@mediapipe/tasks-vision` on npm,
  `mediapipe` on PyPI) and Three.js as the trusted core dependencies; treat small
  one-off utility repos (e.g. a random zmbx→glTF converter) as lower-trust — review before
  use, prefer running such conversion tools offline/locally rather than as a live
  dependency, and don't give them any credentials or network access they don't need.

**When coding:**
- Pin dependency versions (package-lock.json / requirements with hashes) — don't use
  floating `latest`/`^`/`*` version ranges for anything that ends up in the production
  bundle, to avoid unreviewed supply-chain updates landing silently.
- Run `npm audit` (or equivalent) and Python dependency vulnerability scanning
  (e.g. `pip-audit`) as a routine step before each milestone, not just once at the end.
- No secrets, API keys, or credentials committed to the repo at any point — this project
  as designed needs none (no server-side API keys in the all-browser Phase 2 design), so
  treat any future addition that *would* need one as a design decision to flag, not a
  default to reach for.
- Validate/sanitize anything loaded dynamically (glTF assets, any future user-uploaded
  content) — Three.js's GLTFLoader parses attacker-controllable file structures if asset
  upload is ever added, so keep asset sources restricted to files you've authored/vetted
  (bundled with the app) unless a user-upload feature is explicitly designed with
  validation.

**When porting to cloud (Phase 2 hosting):**
- Phase 2's all-browser design means production hosting is **static file hosting only** —
  no server-side compute, no database, no user data collected or stored server-side (the
  camera stream and landmarks never leave the browser). This is a meaningful security
  simplification — preserve it; don't casually add a backend later without re-evaluating
  the threat model.
- **Serve over HTTPS only** — required both for `getUserMedia()` (secure-context
  requirement) and generally non-negotiable for anything handling camera permissions.
- Set a reasonable Content-Security-Policy (restrict script-src to self + the specific
  CDN origin used for MediaPipe's WASM/model assets if loaded from CDN, or better: bundle
  the WASM/model files with the app build and serve from the same origin, removing the
  external CDN dependency and its associated trust/availability risk entirely — prefer
  this for production over the jsdelivr CDN pattern shown in MediaPipe's quickstart docs).
- If a static host with a public bucket/CDN (Netlify/Vercel/S3+CloudFront/etc.) is used,
  ensure no directory listing is exposed and only intended build output is public.

---

## 11. Suggested build order (milestones for Claude Code)

**Do Part Zero and Part Zero-bis first, in full, before starting Part One.** They're small
by design — the payoff is finding porting problems while there's almost nothing to debug.

1. **Inspect the existing repo** (per §2) — understand current pipeline structure, module
   names, and the exact finger-position-to-cursor code path before changing anything.
2. **Part Zero** (§4): retarget the existing cursor-control pipeline to move a cube in a
   local PC window instead of the OS cursor. Confirm it runs live against the webcam.
3. **Skim the prior art** (§1) before writing browser code — specifically
   `threejs-handtracking-101` and `3d-model-playground` — to see working camera-permission
   and gesture-detection patterns before reinventing them in Part Zero-bis.
4. **Part Zero-bis** (§5): port that same minimal loop to the browser —
   `@mediapipe/tasks-vision` HandLandmarker + a one-cube Three.js scene, with real camera-
   permission UX (§9) built now rather than deferred. Write `NOTES.md` documenting any
   coordinate/mirroring/perf/permission differences found versus the Python version.
5. **Repo scaffold** for the rest of the project, matching §3's target shape for the new
   pieces, integrated into the existing repo per §2.
6. **Pipeline A, Part One, static gestures only**: `features.py` (normalization) +
   `rules.py` (open/fist/pinch/point) + synthetic-fixture unit tests. Validate against a
   few recorded sessions from the existing Python MediaPipe pipeline.
7. **Pipeline A, Part One, dynamic gestures**: sliding-window buffer + swipe detection
   (start rule-based on velocity; only add a learned model if rules prove insufficient).
8. **Pipeline B skeleton**: Vite + Three.js scene, a single placeholder glTF cube/sphere,
   orbit-controls camera for dev sanity-check — no hand input yet. (Can share setup with
   Part Zero-bis's Three.js scene rather than starting fresh.)
9. **Blender asset path**: export one real test asset from Blender as `.glb`, load it via
   `GLTFLoader`, confirm it renders correctly.
10. **Phase 2 hand tracking**: integrate `@mediapipe/tasks-vision` HandLandmarker in-browser
    for the full pipeline (beyond Part Zero-bis's single cube), reusing the camera/permission
    module built in Part Zero-bis. Render landmark skeleton overlay for debugging.
11. **Port Pipeline A to JS**, run the parity tests from §7.3 against Part One's fixtures —
    this port should now be routine, since Part Zero-bis already resolved the general
    porting issues (coordinate systems, mirroring, perf) on the simpler case.
12. **Wire Pipeline A (JS) → Pipeline B**: gesture events drive object grab/move/rotate/
    release per §8.3. `3d-model-playground`'s mode-switch pattern (§1) is a useful
    reference here if multiple manipulation modes are wanted.
13. **Security pass** per §10 before any cloud deployment: dependency audit, CSP, bundle
    MediaPipe assets same-origin, confirm HTTPS-only hosting config.
14. **Deploy** static build to chosen static host.

---

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

## 13. Open decisions to make during implementation (flag back to owner, don't assume)

- Exact gesture set beyond the starter list in §7.2 (game-design dependent).
- One-hand vs. two-hand interaction model.
- Whether any dynamic gesture actually needs a learned model, or whether rules suffice
  (resolve empirically in Part One before writing any training code).
- Final static hosting provider for Phase 2 deployment.
- Which local-window library to use for Part Zero's cube (Pygame vs. alternatives) —
  depends on what's already available in the existing pipeline's environment.
