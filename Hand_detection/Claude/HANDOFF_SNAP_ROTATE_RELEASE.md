# Handoff — snap/rotate/release gesture set, current state and next steps

Written 2026-08-01, for starting a **new** Claude Code conversation. Read
this first. The three other living documents for this work, in order of
how detailed they are:

1. **`Claude/GAME_RULES.md`** — plain-language inventory of confirmed game
   rules, no implementation detail. Read this to know *what the game does
   today*.
2. **`Claude/PART_ONE.md` §3** — the gesture/signal matrix (build order,
   status per row). Read this to know *what's built vs. not, in one
   table*.
3. **`Claude/GESTURE_PIPELINE_SPEC.md` §13** (all subsections, through
   §13.6) — full design rationale, state-of-the-art checks, and build
   history. Read this to know *why* things are the way they are.

This handoff file is only an orientation pointer plus a prioritized
action list — don't duplicate the above, link to them.

**Repo state**: check `git status` before assuming anything — this
session's work (the whole snap/rotate/release pivot, all of Phase A, the
Gesture Recognizer detour and revert, the thumb-outward rule) has not
been committed as of this handoff.

## 1. Where the project stands

**Pinch is archived** (not deleted — code/corpus/weights kept, reusable
later). Full account: `GESTURE_PIPELINE_SPEC.md` §13.1,
`HANDOFF_GESTURE_CLASSIFIER.md` (now itself archived/historical).

**Current gesture set: proximity snap, open-palm rotate (not yet built),
closed-fist release (not yet built).** Status, in build order:

- **Hand position, proximity snap, translation, tracking-loss release,
  thumb-outward snap restriction: all built and live-verified.**
  `Resources/HandsTriggeredActions.py` (production) +
  `LiveSnapDebug.py`/`debug_snap.bat` (temporary combined debug view — one
  OpenCV window with video + hand landmarks + a semi-transparent cube
  overlay, kept in logic-sync with the production module by hand). Exact
  rules: `GAME_RULES.md` rules 1-3.
- **A same-frame release/re-snap ordering bug** was found live and fixed
  (a cube could instantly "jump" to the other hand the instant one hand
  lost tracking nearby) — see `on_hands_frame`'s docstring in
  `HandsTriggeredActions.py` for the fix if touching that logic again.
- **MediaPipe's built-in Gesture Recognizer (`Open_Palm`/`Closed_Fist`)
  was tried and reverted** — live-tested unreliable across hand
  positions/orientations for `Closed_Fist` specifically (many missed
  fist closures; `Open_Palm` was never separately confirmed bad or good,
  the whole integration was reverted together). `gesture_recognizer.task`
  is kept on disk (`Local_pc/Python_Server_MediaPipe_vision_pipeline/
  Resources/`) for a possible later `Thumb_Up` use, unrelated to this.
  Full account: `GESTURE_PIPELINE_SPEC.md` §13.5.
- **Rotation while snapped: not started.** This is the next build target
  — see §2 below.
- **Release via closed fist: not started**, blocked on finding a working
  fist-detection approach (candidates logged in §13.5: a geometric
  heuristic on `features.py`'s finger-curl functions, or a custom-trained
  classifier via the Stage 1-3 pipeline).

## 2. Immediate next action: rotation while snapped

**Design already decided** (`PART_ONE.md` §2, carried over unchanged from
the archived pinch plan, re-confirmed applicable in
`GESTURE_PIPELINE_SPEC.md` §13.3): track hand orientation as a quaternion
built from an orthonormal frame (Gram-Schmidt on `wrist(0)→index_MCP(5)`
and `wrist(0)→pinky_MCP(17)` from `world_landmarks`), and slerp the
cube's quaternion toward it each frame, while snapped. **Never decompose
into separate roll/pitch/yaw Euler angles at any point** — gimbal lock is
a property of that decomposition, not of the rotation itself (checked
against literature, `GESTURE_PIPELINE_SPEC.md` §13.2 point 3).

**Three concrete pieces of work, in order**:

1. **Wire-protocol extension — `world_landmarks` are not currently sent
   over the live socket.** This is the same "known wire-protocol gap"
   flagged in `PART_ONE.md` §4 since before the pinch work even started.
   The production pipeline (`VisionPipeline.py` → `Server.py` →
   `Client.py` → `PythonApp_Main.py` → `HandsTriggeredActions.py`)
   currently only extracts and sends 2D pixel landmarks
   (`Resources/hands_visualizer.py`'s `draw_landmarks_on_image` only
   reads `detection_result.hand_landmarks`, never
   `detection_result.hand_world_landmarks` — confirmed present on the
   same `HandLandmarkerResult` object this session, see
   `RecordSession.py`'s `_landmark_list(result.hand_world_landmarks[idx])`
   for the exact extraction pattern already used elsewhere). Needs:
   extract world landmarks server-side, add a new packet type (e.g.
   `"hands_world"`, 21×3×2 = 126 floats) sent alongside `"hands"` each
   frame (send it *before* `"hands"` in the per-frame send order, so by
   the time `on_hands_frame`'s per-frame logic runs, that frame's world
   landmarks are already available — packets are dispatched sequentially
   as they arrive, see `Client.py`'s `receive_keypoints_data`), and a
   client-side handler that stores the latest world landmarks per hand
   for `HandsTriggeredActions.py` to read.
2. **Quaternion computation + slerp**, gated appropriately (see the open
   question below), applied to the snapped cube's orientation each frame.
3. **Rendering**: `CubeWindow.py`'s cube is currently a flat, solid-color
   `pygame.Rect` — **it has no visual way to show orientation at all**.
   This needs to change before rotation can be live-verified (the whole
   point of every gesture this project ships) — e.g. a marker line/dot
   on one face, or a small isometric/wireframe cube projected in 2D.
   Decide and build this as part of the same pass, not as an afterthought
   — you cannot verify "does rotation work" without it.

**Open question, needs the user's direction before or during this
build**: should rotation be gated on the hand being `Open_Palm`
(§13.3/§13.4's original design intent), or built ungated first (rotation
active whenever an object is snapped, regardless of hand pose) since
`Open_Palm` detection has no working implementation right now (§13.5)?
Building ungated first is probably the pragmatic path — it lets rotation
itself be built and verified independently of the still-unresolved
fist/open-palm detection problem, with the gate added later once that's
solved. Confirm with the user rather than assuming.

## 3. Environment notes

- Python env: `Local_pc/Movement_with_hand_detection/.venv` — shared by
  the client (`PythonApp_Main.py`), the server
  (`VisionPipeline.py`, launched via the same `sys.executable`), and all
  debug tools (`LiveSnapDebug.py`, `debug_snap.bat`; the archived
  `LiveGestureDebug.py`/`debug.bat` for pinch).
- Model files: `Local_pc/Python_Server_MediaPipe_vision_pipeline/
  Resources/hand_landmarker.task` (in active use) and
  `gesture_recognizer.task` (downloaded 2026-08-01, kept on disk, not
  currently used by any code path — see §1).
- **Live pipeline processes hold the webcam device** — if a debug/launch
  session's window isn't explicitly closed, the process keeps running and
  the *next* attempt to open the camera fails with "Could not open webcam
  ... Is another program using the camera?". Check
  `Get-Process python` and stop stale ones before relaunching if this
  happens (hit this exact issue twice this session).
- `debug_snap.bat`/`LiveSnapDebug.py` is **temporary** (per direction) —
  delete once the gesture set is built and verified enough that the
  combined single-window debug view is no longer needed; it duplicates
  (not imports) `HandsTriggeredActions.py`'s snap/translate/orientation
  logic by design (see the file's own header comment for why), so any
  production logic change needs to be mirrored there too until it's
  deleted.

## 4. Standing discipline (carried over from the pinch work, still applies)

- **Live-verify before trusting any claim, including your own geometric
  assumptions.** This session's two concrete examples: MediaPipe's
  built-in `Closed_Fist` classifier looked correct in isolation but
  failed across real hand positions; the thumb-outward sign convention
  was calibrated live (raw value + tentative label shown on screen,
  operator confirmed the mapping) *before* being wired into gating logic,
  specifically to not repeat the first mistake. Apply the same pattern to
  the rotation quaternion once built — visually verify the sign/axis
  conventions against real rotation before trusting the feel.
- **No heuristic pile-up** — if a value needs tuning (grab radius,
  rotation slerp factor, etc.), tune it live and record the reasoning,
  don't guess-and-forget.
- **Same-frame ordering matters** in per-hand stateful loops — the
  release/re-snap jump bug this session is the concrete example; think
  through what state a second hand's pass can observe from the first
  hand's pass in the same frame before assuming independence.
- **Keep `GAME_RULES.md` updated** every time a new rule is confirmed and
  built — it's the one place meant to answer "what does the game do
  today" without reading code or design prose.
- The full, generalized lessons-learned list from the pinch arc (still
  broadly applicable) lives in `HANDOFF_GESTURE_CLASSIFIER.md` §0 /
  `GESTURE_PIPELINE_SPEC.md` §12.7 — worth a skim if this build hits a
  wall that feels familiar.
