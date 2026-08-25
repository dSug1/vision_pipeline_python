<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 1-9
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
# Hand-Tracking Object Manipulation Game — the ORIGINAL build handoff (historical)

> ⚠ **NOT the entry point — read `README.md` first.** This is the founding
> document: the goal, the hard constraints, the prior-art scan and the original
> architecture sketch. Those parts are still authoritative.
> ⛔ **§11's suggested build order is HISTORICAL** — `PART_ONE.md` §3.1 is the
> single build queue and supersedes it. §3's repo layout is a target shape that
> the real tree only partly follows; trust the tree and `README.md` §2.

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 63-238
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 363-503
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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

<!-- VERBATIM-END -->
<!-- PROVENANCE — machine-extracted, NOT edited.
     source : Claude/Specification.md lines 624-666
     commit : 3d44c9a
     when   : 2026-08-25 documentation reorganisation
     Every byte between the VERBATIM markers below is exactly as it was.
     The map of the new folder layout is Claude/README.md.
-->
<!-- VERBATIM-BEGIN -->
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

<!-- VERBATIM-END -->
