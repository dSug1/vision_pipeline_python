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
- **Rotation while snapped: PORTED TO PRODUCTION (2026-08-01), NOT YET
  LIVE-TESTED end-to-end.** Confirmed UNGATED (not gated on `Open_Palm`).
  Relative-to-grab (not absolute), hand-rolled quaternion math, the
  predictive/reliability-weighted orientation filter (replacing the two
  earlier binary filter attempts) — all ported verbatim from the
  debug-tool-verified `LiveSnapDebug.py` into `HandsTriggeredActions.py`/
  `CubeWindow.py`, and the wire protocol extended (`hands_world` packet,
  `VisionPipeline.py`→`Server.py`→`PythonApp_Main.py`). Offline-verified
  end-to-end with synthetic data (snap, no-pop-at-grab, and rotation
  tracking a moving target with EXACTLY the theoretically-predicted
  steady-state slerp lag — 0.000° error against theory) — but **never run
  against a real camera yet**. Full account: `GESTURE_PIPELINE_SPEC.md`
  §13.7. **One specific unverified item**: the world-landmark mirroring/
  x-negation convention in `utils_for_remapping_coordinates_and_output_
  formatting.py`'s `remap_world_keypoints` (`invert_x=True` default) was
  never live-confirmed — `LiveSnapDebug.py` never needed this (it runs
  detection on an already-mirrored frame), so this is genuinely new,
  untested code. If rotation feels mirrored/inverted on any axis once
  tested live, check this first. **Known open TODO (unchanged)**: rotation
  quality is still reportedly poor with the BACK of the hand facing the
  camera — the SAME pitch-crossing pose already diagnosed and fixed, just
  not eliminated. Three geometric fixes and one temporal/predictive filter
  have all been tried; §13.7's last paragraph has what to check before a
  fifth attempt.
- **Release via closed fist: not started**, blocked on finding a working
  fist-detection approach (candidates logged in §13.5: a geometric
  heuristic on `features.py`'s finger-curl functions, or a custom-trained
  classifier via the Stage 1-3 pipeline).

## 2. Immediate next action: live-test the production rotation port

Everything is built and offline-verified — see `GESTURE_PIPELINE_SPEC.md`
§13.7 for the full design (relative-to-grab quaternion math, the
predictive filter, the better-conditioned landmark pair) and its remaining
known issue (rotation quality still imperfect with the back of the hand
facing the camera, not fully eliminated). **Never decompose into separate
roll/pitch/yaw Euler angles at any point** — gimbal lock is a property of
that decomposition, not of the rotation itself (checked against
literature, `GESTURE_PIPELINE_SPEC.md` §13.2 point 3).

**What's left is purely live verification, not more building**:
1. Run the full production pipeline (`PythonApp_Main.py`, which launches
   both server and client via `Resources/Launcher_for_Server_and_Client.py`)
   against the real webcam and confirm rotation works end-to-end through
   the actual wire protocol — this has never been tested with a real
   camera, only offline with synthetic landmark data.
2. **Specifically check the world-landmark mirroring/x-negation
   convention** (see §1's note above) — if any rotation axis feels
   mirrored/inverted compared to how it felt in `LiveSnapDebug.py`, that's
   the first place to look; flip `remap_world_keypoints`'s `invert_x`
   default and re-test, don't guess blindly.
3. Confirm the orientation gizmo (`CubeWindow.py`'s
   `_draw_orientation_gizmo`, ported from `LiveSnapDebug.py`) renders
   correctly in the actual pygame window, not just in the isolated
   synthetic test used to verify it during the port.

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
