# Project Handoff

_Last updated: 2026-05-29. Read this to resume work in a new conversation._

---

## 0. START HERE — immediate next step

The **Virtual Drums** app runs end-to-end (camera → hand landmarks → per-finger
"strike" → debug flash + console print). User chose **detection logic/calibration
first**, then audio.

**Done (2026-05-29): strike detection is an arm/contact state machine that fires on
DECELERATION** (`core/strike_detector.py` + `core/calibrator.py`). A hit requires:
- **ARM** — the fingertip first rose above the table by the arm clearance, then came
  down. Rejects derivative noise AND is the **masked-finger guard** (an occluded
  thumb that reappears near the table starts disarmed → no phantom hit). Arm is
  consumed per hit; small lifts re-arm it so rolls work. Clearance is measured by a
  launch dry-run (2/3 of the index tap amplitude), fallback `ARM_CLEARANCE_PX`.
- **FAST APPROACH** — velocity reached ≥ `STRIKE_SPEED_THRESHOLD` (V_high) during the
  descent. (Replaced the old peak-speed gate, redundant once we gate on speed.)
- **DECELERATION = impact** — fires the frame velocity drops below
  `DECEL_SPEED_THRESHOLD` (V_low, "almost zero"). **Does NOT wait for velocity
  reversal** → fires ~1 frame earlier, while the tip is still on the table (verified).
- **CONTACT (min-depth)** — deepest point reached at least table-deep (within
  `CONTACT_BAND_PX` of the calibrated zero; deeper is fine).
- **No debounce** — the arm-consume rule replaces it (a micro-bounce can't re-fire
  without re-arming). `MIN_FAST_FRAMES` + `REFRACTORY_MS` were removed as **deferred
  noise work** (spec §16); reinstate if the kinematic-only fallback is used.
Velocity: `POS_SMOOTHING_FRAMES` moving average → derivative over
`VELOCITY_DELTA_FRAMES` (latency ≈ their sum). Confirmed MediaPipe does NOT pre-smooth
landmarks, so no double-smoothing. **Two-phase launch calibration** (timer-based, no
keyboard): (1) rest all 10 fingertips → per-finger contact zero; (2) tap with one
index finger → arm clearance. Verified with synthetic sequences (table tap → 1,
no-rebound stop → 1, mid-air → 0, never-armed → 0, masked reappearance → 0,
fires-on-decel-not-reversal). **Not yet run on the live camera.**

Next work, in order:

1. **Run live & calibrate** (tune `config.py`). See §10. Calibration timings
   (1.5 s / 4 s) are PLACEHOLDERS; `sweep` band mode is future work (spec §7). A live
   **FPS overlay** (top-right, `DRAW_FPS`) shows the real loop rate.
2. **Finalize the finger→drum mapping** (`FINGER_SOUNDS` in the same file).
3. **Add real audio** (implement `AudioSoundEngine`; pick a license-free library).

---

## 1. What this project is

A real-time webcam computer-vision pipeline (Google MediaPipe) that detects hand
landmarks and maps them to actions. Two things live here now:

- **Active app: "Virtual Drums — Finger Tracking"** (`Virtual_drums_fingers_tracking/`).
  Camera laid on a table; fingers tap the table like drums; each finger triggers a
  different drum sound. The current build detects taps and shows a debug flash +
  prints the drum name (no audio yet).
- **Original system (RETIRED, parked in `_not_used/`):** a server–client "mouse
  cursor" controller. Superseded; kept runnable for reference.

## 2. Big-picture goal & key decisions

- **Goal:** eventually ship as a **cross-platform app (iOS, Android, Windows).**
  This drives all architecture choices. (Persisted in memory — see §7.)
- **Decision (2026-05-29):** Build the **desktop prototype now in Python + cv2 +
  MediaPipe** for speed. The Python code is **disposable for mobile** (Python does
  not run on iOS, and `mediapipe`/`opencv-python` have no mobile wheels). Mobile
  will be a **later rebuild** reusing the **design + model files, not the code**.
- **Therefore keep the design clean & portable:** producer→consumer separation,
  a stable landmark data contract, touch-friendly UX, reusable `.task`/`.tflite`
  models. Desktop-only pieces (`cv2.VideoCapture`, OpenCV window, Win32 APIs) stay
  isolated behind interfaces.
- **No Unity** (ruled out: overhead + license fees).
- **Mobile framework NOT yet chosen.** Research (in `docs/mobile-deployment-research.md`)
  found: only **LiteRT (TFLite)** and **ONNX Runtime** natively span iOS+Android+
  Windows; ML Kit and Apple Vision lack Windows; no turnkey single-codebase
  MediaPipe-vision SDK exists. Decision deferred until mobile work begins.

## 3. Current repo structure

```
vision_pipeline_python/
├── handoff.md                         ← this file
├── Virtual_drums_fingers_tracking/    ← ACTIVE app (self-contained, own .venv)
│   ├── main.py                        # composition root + run loop
│   ├── config.py                      # ALL tunables (strike thresholds, finger→sound map)
│   ├── launch.bat                     # builds local .venv (first run), then runs (CRLF!)
│   ├── requirements.txt               # mediapipe==0.10.14, opencv-contrib-python, numpy
│   ├── core/                          # PORTABLE, no cv2/mediapipe:
│   │   ├── contracts.py               #   data contract: FingerId, Landmark, LandmarkFrame, StrikeEvent
│   │   ├── events.py                  #   in-process EventBus (pub/sub)
│   │   ├── finger_tracker.py          #   LandmarkFrame → per-finger strike points
│   │   └── strike_detector.py         #   velocity-sign-inversion strike algorithm (FIRST PASS)
│   ├── vision/                        # DESKTOP-ONLY producer, behind interfaces:
│   │   ├── camera_source.py           #   ICameraSource + OpenCvCameraSource (CAP_DSHOW)
│   │   └── hand_landmarker.py         #   ILandmarkSource + MediaPipeHandLandmarker (hands only, VIDEO mode)
│   ├── output/                        # consumers:
│   │   ├── sound_engine.py            #   ISoundEngine + LoggingSoundEngine (debug) + AudioSoundEngine (TODO)
│   │   └── visualizer.py              #   OpenCV window + green fingertip dots + red strike flash
│   ├── models/hand_landmarker.task    # bundled model (copied in — folder is independent)
│   └── spec/Virtual_drums_specification.md   ← FULL design spec for this app
├── docs/
│   ├── General_specification.md       # the ORIGINAL server-client design
│   └── mobile-deployment-research.md  # 2-round cited research on mobile deployment
└── _not_used/                         ← parked, runnable later
    ├── MauiApp_Launcher/              # C# .NET MAUI client (dormant)
    ├── MouseCursorApp/                # original entry + client + cursor logic (+ its own launch.bat/requirements.txt)
    └── Python_Server_MediaPipe_vision_pipeline/  # original shared vision server
```

## 4. The Virtual Drums app — how it works & how to run

**Architecture:** single process, **in-process EventBus** (no socket, no
subprocess — this is why the original "single-client server" limitation does not
exist here). Flow:
`camera → MediaPipeHandLandmarker → LandmarkFrame (bus) → FingerTracker →
StrikeDetector → StrikeEvent (bus) → LoggingSoundEngine + Visualizer`.

**Run it:** double-click `Virtual_drums_fingers_tracking\launch.bat`
(local `.venv` is already built, so it starts immediately). **Two timer-based
calibration phases run first** (don't touch the keyboard): (1) rest all 10 fingertips
flat on the table; (2) tap a few times with one index finger (sizes the arm
clearance). Then play begins. Quit with **`q`** or by closing the window. The window
shows the **full hand skeleton** (all 21 landmarks, color-coded per finger) and a
real-FPS readout top-right; a strike flashes that fingertip red + larger and prints
e.g. `[drum] left_index -> snare`. (Closing the window during calibration skips it →
detector runs kinematic-only.)

**Key tunables — `Virtual_drums_fingers_tracking/config.py`:**
- `STRIKE_AXIS` = `"y"` (image axis "toward the table"; options `y`/`x`/`z`)
- `APPROACH_SIGN` = `+1` (flip to `-1` if taps NEVER register — you're approaching
  in the decreasing-axis direction; first thing to try if nothing fires)
- `POS_SMOOTHING_MS` = `100` / `VELOCITY_DELTA_MS` = `33` (kinematics windows in REAL
  time; app measures FPS at launch and converts to frames, so 15/30/60 FPS all get a
  consistent span. `KINEMATICS_AUTO_FROM_FPS=True`; `*_FRAMES` are the fallback)
- `STRIKE_SPEED_THRESHOLD` = `180.0` (V_high: min approach speed, **px/sec** — raise
  if trigger-happy, lower if real taps get missed)
- `DECEL_SPEED_THRESHOLD` = `60.0` (V_low: "almost zero" speed, px/sec, that = impact;
  fires here, not on reversal. Must be < V_high)
- `GAP_RESET_MS` = `100` (drop+disarm a finger if unseen this long)
- _(removed, deferred noise work: `MIN_FAST_FRAMES`, `REFRACTORY_MS` — spec §16)_
- `CONTACT_GATE_ENABLED` = `True` (False → pure kinematic, no calibration needed)
- `CONTACT_BAND_PX` = `25.0` (min-depth tolerance below the calibrated table height)
- `ARM_CALIBRATION_ENABLED` = `True`, `ARM_CALIBRATION_FRACTION` = `0.667` (arm
  clearance = 2/3 × measured index-tap amplitude), `ARM_CLEARANCE_PX` = `35.0`
  (fallback if dry-run skipped; keep > band)
- `CALIBRATION_CAPTURE_SECONDS` = `1.5` / `ARM_DRYRUN_SECONDS` = `4.0` (PLACEHOLDERS),
  countdowns `3.0` each
- `DRAW_FPS` = `True` (live real-FPS overlay, top-right)
- `FINGER_SOUNDS` = the finger→drum-name map (10 fingers). Labels are placeholders
  (kick/snare/hat_closed/hat_open/tom_low/tom_high/crash/ride + kick_2/snare_2).
  No audio yet — these are just printed.

**Strike algorithm (spec §6, in `strike_detector.py`):** per-finger arm/contact
state machine — see the bullets in §0 (ARM → FAST APPROACH → DECELERATION → CONTACT
min-depth). Calibration (`core/calibrator.py`) supplies the per-finger contact zero;
without it the detector falls back to kinematic-only. NOTE: `main.py` now uses a
real wall-clock (`MonotonicMsClock`), so velocity is **px/second** and the speed
thresholds are **FPS-independent**. The app also **measures FPS at launch** (~1.5 s)
and converts the ms-based smoothing/velocity windows to frame counts, so they hold a
consistent real-time span at 15/30/60 FPS (prints `[fps] measured ... -> smoothing=N
frames`). The real timestamp gap also drives `GAP_RESET_MS` re-acquisition detection.
(If FPS *fluctuates* mid-run, a time-windowed EMA smoother is the next step — spec §6.)

## 5. What is validated / works
- ✅ Full loop runs; 10 fingers detected and distinguished; strikes fire.
- ✅ **§16 #1 (was highest risk) CLEARED:** tracking works with only the last 2-3
  phalanges visible (palm out of frame) AND re-acquires after a hand leaves and
  re-enters the frame.
- ✅ Folder is **independent**: no imports/links to other folders; own
  `requirements.txt`; own local `.venv`; model copied in. Can be copied elsewhere
  and run standalone.
- ✅ All `.bat` files are CRLF (a `.gitattributes` rule enforces `*.bat eol=crlf`).

## 6. Important context & gotchas
- **MediaPipe pinned to `0.10.14`** repo-wide. Newer (0.10.30+) dropped the legacy
  `mediapipe.solutions`/`framework` modules. NOTE: the Virtual Drums app does NOT
  use those (drawing is plain OpenCV), so it *could* use newer MediaPipe — pinned
  only for reproducibility.
- **`.bat` files MUST be CRLF** — LF makes `cmd.exe` flash-and-vanish on multi-line
  blocks. Enforced via `.gitattributes`. If you create new `.bat`, keep CRLF.
- **Per-folder venvs:** each app builds its own local `.venv` (independence). Don't
  copy a `.venv` between machines — recreate from `requirements.txt` (launch.bat
  does this). The old repo-root `.venv` was deleted.
- **`cv2.VideoCapture` uses `CAP_DSHOW`** (DirectShow) on Windows — the default
  MSMF backend hangs on open. Camera released via `try/finally`.
- **Folder-rename lock on Windows:** moving a whole tracked directory with
  `git mv` sometimes fails with "Permission denied"; the workaround is to `git mv`
  files individually (used several times in this project).
- Platform: Windows 11, system **Python 3.11.9**.

## 7. Persistent memory (auto-loaded each session)
Memory dir: `.../memory/` for this project. Key file:
**`target-cross-platform-app-deployment.md`** — the cross-platform goal, the
Python-prototype-now/mobile-rebuild-later decision, the no-Unity constraint, and
the deployment research summary. It loads automatically, so a new conversation
already has this context.

## 8. Running the parked original system (if ever needed)
`_not_used/MouseCursorApp/launch.bat` — self-contained: builds its own local
`.venv` from `_not_used/MouseCursorApp/requirements.txt` and starts the
server+client (server is the sibling `_not_used/Python_Server_MediaPipe_vision_pipeline/`).
Stop with `q`/window-close, or `_not_used/MouseCursorApp/stop.bat`. Design doc:
`docs/General_specification.md`.

## 9. Git state
**Nothing is committed yet** — all the work above is in the working tree
(many `git mv` renames, deletions, and new files staged). Consider committing
before/while continuing. Branch: `1.5.0-`. Main branch: `main`.

## 10. Suggested first actions in the new conversation
1. Confirm: calibrate detection first, or add sound first?
2. If calibrating: run the app, report whether strikes are accurate vs
   trigger-happy, and we tune `config.py` (`STRIKE_SPEED_THRESHOLD`,
   `REFRACTORY_MS`, `STRIKE_AXIS`, `SMOOTHING_WINDOW`).
3. If sound: choose a license-free audio library (candidates: `pygame.mixer`,
   `simpleaudio`, `sounddevice`, `playsound`), then implement `AudioSoundEngine`
   in `output/sound_engine.py` and add per-finger sample files.
