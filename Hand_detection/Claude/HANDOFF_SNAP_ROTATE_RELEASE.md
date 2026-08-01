# Handoff — snap/rotate/release gesture set, current state and next steps

Refreshed 2026-08-01, for starting a **new** Claude Code conversation.
Read this first. The three other living documents for this work, in
order of how detailed they are:

1. **`Claude/GAME_RULES.md`** — plain-language inventory of confirmed game
   rules, no implementation detail. Read this to know *what the game does
   today*.
2. **`Claude/PART_ONE.md` §3** — the gesture/signal matrix (build order,
   status per row). Read this to know *what's built vs. not, in one
   table*.
3. **`Claude/GESTURE_PIPELINE_SPEC.md` §13-§14** — full design rationale,
   state-of-the-art checks, and build history (§13, all subsections
   through §13.8), plus the two next build targets proposed 2026-08-01
   (§14). Read this to know *why* things are the way they are, and *what's
   next*.

This handoff file is only an orientation pointer plus a prioritized
action list — don't duplicate the above, link to them.

**Repo state**: check `git status` before assuming anything — this
work has not been committed as of this handoff.

## 1. Where the project stands

**Pinch is archived** (not deleted — code/corpus/weights kept, reusable
later). Full account: `GESTURE_PIPELINE_SPEC.md` §13.1,
`HANDOFF_GESTURE_CLASSIFIER.md` (now itself archived/historical).

**Current gesture set: proximity snap, translation, rotation — all built,
ported to production, and CONFIRMED WORKING LIVE against a real camera.**
Closed-fist/open-hand release still not built. Status, in build order:

- **Hand position, proximity snap, translation, tracking-loss release,
  thumb-outward snap restriction: all built and live-verified.**
  `Resources/HandsTriggeredActions.py` (production) +
  `LiveSnapDebug.py`/`debug_snap.bat` (combined debug view — one OpenCV
  window with video + hand landmarks + a semi-transparent 3D-cube
  overlay, kept in logic-sync with the production module by hand — **kept
  in active use past its original "temporary" framing, per direct
  request**, since it's easier to debug with video+landmarks+object
  visible together than via production's split windows; remove only once
  final production no longer needs this level of visibility). Exact
  rules: `GAME_RULES.md` rules 1-3.
- **A same-frame release/re-snap ordering bug** was found live and fixed
  (a cube could instantly "jump" to the other hand the instant one hand
  lost tracking nearby) — see `on_hands_frame`'s docstring in
  `HandsTriggeredActions.py` for the fix if touching that logic again.
- **MediaPipe's built-in Gesture Recognizer (`Open_Palm`/`Closed_Fist`)
  was tried and reverted** — live-tested unreliable across hand
  positions/orientations for `Closed_Fist` specifically (many missed
  fist closures). `gesture_recognizer.task` is kept on disk
  (`Local_pc/Python_Server_MediaPipe_vision_pipeline/Resources/`) for a
  possible later `Thumb_Up` use, unrelated to this. Full account:
  `GESTURE_PIPELINE_SPEC.md` §13.5.
- **Rotation while snapped: BUILT, PORTED TO PRODUCTION, AND CONFIRMED
  WORKING LIVE (2026-08-01).** Confirmed UNGATED (not gated on
  `Open_Palm`). Relative-to-grab (not absolute — a cube keeps its own
  orientation at grab, only rotates by however much the hand rotates
  afterward), hand-rolled quaternion math, the predictive/reliability-
  weighted orientation filter. Wire protocol extended (`hands_world`
  packet, `VisionPipeline.py`→`Server.py`→`PythonApp_Main.py`). User
  confirmed "it is working" against the real camera — the previously-
  unverified world-landmark mirroring convention needed no fix. Full
  account: `GESTURE_PIPELINE_SPEC.md` §13.7.
  - **Known open TODO**: rotation quality is still imperfect with the
    BACK of the hand facing the camera. Four attempts total (three
    geometric landmark-selection fixes, one temporal/predictive filter)
    have each helped without fully resolving it — increasingly looks like
    a genuine floor of a single-monocular-camera setup, not a software fix
    away. §13.7's last paragraph has what to check before a fifth attempt
    (tuning `CONDITIONING_ALPHA_LOW`/`HIGH`, widening the angular-velocity
    averaging window) before reaching for a fundamentally different
    approach.
  - **Known open TODO (new, proposed 2026-08-01, not yet started)**: the
    object translates somewhat when the hand only rotates in place — it
    shouldn't. Root cause and candidate fixes: §14.1 below.
- **Real 3D object rendering: BUILT and CONFIRMED WORKING LIVE
  (2026-08-01)**, once rotation was confirmed. Replaced the flat-square +
  axis-gizmo placeholder with actual rotating 3D shapes — 2 objects,
  **large** (yellow/violet/turquoise faces, one side of each opposite
  pair a darker shade) and **small** (green/red/blue), large exactly 2x
  small in every dimension. Grab radius now scales per-object size (an
  old open item, resolved as a side effect).
  - **A morphing bug was found live and fixed same day**: the first
    version's per-vertex projection scale could go negative for cube
    corners at certain rotations, flipping vertices to the wrong side.
    Fixed with a proper, bounded perspective projection (verified safe
    across a full rotation sweep). Full account: `GESTURE_PIPELINE_SPEC.md`
    §13.7's morphing-bug note.
  - **Refactored the same day to be mesh-generic** (direct request: "the
    cube should act as a placeholder for 3d complex objects which will be
    imported later on"): geometry (`Mesh`/`MeshFace`) is now fully
    decoupled from the rendering pipeline (`CubeWindow._draw_object_3d`),
    which operates on ANY mesh's vertices/faces/colors with zero
    cube-specific logic. Verified by swapping in a completely different
    mesh (a tetrahedron) at runtime with no code changes. A real 3D-file
    import (OBJ/glTF) is NOT built yet — that's a separate, scoped future
    step (loader + maybe a faster depth-sort for many-triangle meshes),
    not blocking anything currently planned. Full account:
    `GESTURE_PIPELINE_SPEC.md` §13.8.
- **Release via closed fist: not started**, blocked on finding a working
  fist-detection approach (candidates logged in §13.5).
- **New candidate release trigger, proposed 2026-08-01, not yet started**:
  unsnap by quickly fully opening the hand. Design + a proposed
  recording/discrimination plan: §14.2 below. Not yet confirmed whether
  this replaces or complements the closed-fist plan above — ask the user
  if it's ambiguous when picking this up.

## 2. Immediate next actions — two build targets, proposed 2026-08-01

Both are NEW, NOT YET STARTED, and were specifically deferred to a fresh
conversation (this handoff) rather than built the same session. Full
design detail for both is in `GESTURE_PIPELINE_SPEC.md` §14 (§14.1 and
§14.2) — this section only summarizes; read the spec section before
starting either.

### 2.1 Fix: object shouldn't translate when the hand only rotates

**Problem**: the tracked hand-position anchor (centroid of wrist + 4
non-thumb MCPs) isn't exactly at the hand's true rotational pivot, so
rotating the wrist in place still traces a small arc in image space —
this is a geometric consequence of the anchor point's location, not
tracking noise, and would happen even with perfect landmark data.

**Candidates to test** (§14.1 has full detail, don't skip it): (1) the
user's own suggestion — a centroid over a wider set of landmarks
approximating "the middle of the volume enclosed by the fingers and
palm"; (2) anchor on the wrist landmark alone (closer to the true
anatomical pivot); (3) a weighted/offset centroid between the two.
**Verify empirically before committing to one** — record a hand rotating
in place at a few real positions, log all candidate anchor points' pixel
positions per frame, measure which one drifts least. Don't guess by feel;
this project's standing discipline is recorded-data verification first
(see §4 below and literally every prior build step in §13).

### 2.2 New candidate: unsnap by quickly fully opening the hand

**Design**: while holding an object, rapidly and fully opening the hand
(fingers extending fast) unsnaps it — **provided the wrist/hand base
doesn't translate much at the same time**. That qualifier exists
specifically to distinguish this from a **different, NOT YET BUILT**
future gesture: moving the whole hand toward/away from the camera to
control depth/Z-axis translation, where fingers AND wrist would scale
together in the image, unlike this release gesture where only the
fingers change quickly while the wrist stays comparatively stable.

**Proposed data-collection plan** (direct request): record 6 sessions of
the target gesture (grab, then quickly fully open the hand) and 6 of the
confound to rule out (moving the whole hand toward/away from the camera,
no release intent) — across a few different hand positions/distances so
whatever signal is found generalizes. Reuse/extend `RecordRotationDebug.py`'s
recording harness (same schema: full landmark data, pixel + world, both
hands, per frame). Offline, compare candidate discriminating signals
(rate of finger-extension/curl-angle change vs. rate of overall hand-scale
change) across all 12 recordings before designing any threshold — full
detail and reasoning in §14.2.

**Not yet decided**: whether this supersedes the closed-fist release plan
or the two are meant to coexist as alternative triggers. Ask the user
rather than assuming either way.

## 3. Environment notes

- Python env: `Local_pc/Movement_with_hand_detection/.venv` — shared by
  the client (`PythonApp_Main.py`), the server (`VisionPipeline.py`,
  launched via the same `sys.executable`), and all debug tools
  (`LiveSnapDebug.py`, `debug_snap.bat`, `RecordRotationDebug.py`,
  `record_rotation_debug.bat`; the archived `LiveGestureDebug.py`/
  `debug.bat` for pinch).
- Model files: `Local_pc/Python_Server_MediaPipe_vision_pipeline/
  Resources/hand_landmarker.task` (in active use) and
  `gesture_recognizer.task` (downloaded 2026-08-01, kept on disk, not
  currently used by any code path — see §1).
- **Live pipeline processes hold the webcam device** — if a debug/launch
  session's window isn't explicitly closed, the process keeps running and
  the *next* attempt to open the camera fails with "Could not open webcam
  ... Is another program using the camera?". Check `Get-Process python`
  and stop stale ones before relaunching if this happens.
- `debug_snap.bat`/`LiveSnapDebug.py` duplicates (not imports)
  `HandsTriggeredActions.py`'s/`CubeWindow.py`'s snap/translate/orientation/
  rendering logic by design (see the file's own header comment for why —
  its `cube_window` is a module-level object that opens a real pygame
  window as an import side effect, which this single-OpenCV-window tool
  must not trigger). **Any production logic OR rendering change needs to
  be mirrored there too** — this was true throughout the 2026-08-01
  session (rotation, the mesh-generic refactor, the morphing-bug fix all
  had to be applied in both places) and still applies going forward.

## 4. Standing discipline (carried over, still applies)

- **Live-verify before trusting any claim, including your own geometric
  assumptions** — the whole 2026-08-01 session is full of concrete
  examples: MediaPipe's built-in `Closed_Fist` classifier looked correct
  in isolation but failed across real hand positions; the thumb-outward
  sign convention was calibrated live before being trusted; the rotation
  quaternion's world-landmark mirroring convention was flagged as
  unverified and then confirmed fine only once actually tested against a
  real camera; the cube-morphing bug was only found by watching it live,
  not by inspection. Apply the same pattern to both new build targets in
  §2 — test against recorded data before committing to a fix, same as
  every prior step.
- **No heuristic pile-up** — if a value needs tuning (grab radius,
  rotation slerp factor, `CONDITIONING_ALPHA_LOW/HIGH`, etc.), tune it
  live and record the reasoning, don't guess-and-forget.
- **Same-frame ordering matters** in per-hand stateful loops — the
  release/re-snap jump bug is the concrete example; think through what
  state a second hand's pass can observe from the first hand's pass in
  the same frame before assuming independence.
- **Keep `GAME_RULES.md` updated** every time a new rule is confirmed and
  built — it's the one place meant to answer "what does the game do
  today" without reading code or design prose.
- **Recorded-data-first empiricism, not guessing** — this is now a deeply
  established pattern in this project (the entire pitch-crossing rotation
  investigation, the thumb/PCA landmark tests, the predictive-filter
  verification, the morphing-bug fix all followed it): when a design
  decision is unclear, build a small recorder, capture real data, analyze
  it offline, THEN decide. Both new build targets in §2 are explicitly
  designed to be approached this way — don't skip straight to an
  implementation guess for either.
- The full, generalized lessons-learned list from the pinch arc (still
  broadly applicable) lives in `HANDOFF_GESTURE_CLASSIFIER.md` §0 /
  `GESTURE_PIPELINE_SPEC.md` §12.7 — worth a skim if this build hits a
  wall that feels familiar.
