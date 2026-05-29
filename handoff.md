# Project Handoff

_Last updated: 2026-05-29. Read this to resume work in a new conversation._

---

## 0. START HERE — immediate next step

The **Virtual Drums** app runs end-to-end and is **validated LIVE** (2026-05-29):
camera → hand landmarks → per-finger "strike" → debug flash + console print. Last run
calibrated **10/10 fingers (both hands)** and fired mapped drums across the whole kit
(`right_ring→crash`, `left_thumb→kick`, …). **No audio yet** — `LoggingSoundEngine`
prints the drum name; the next step is real sound.

**➡ NEXT STEP: implement real audio** (`AudioSoundEngine` in
`output/sound_engine.py`) — pick a license-free library (candidates `pygame.mixer`,
`simpleaudio`, `sounddevice`, `playsound`), add per-finger sample files, and swap it
in for `LoggingSoundEngine` in `main.py`. Detection is tuned and working; sound is the
remaining gap. (Optionally first finalize the `FINGER_SOUNDS` map in `config.py`.)

### Detection algorithm (tuned & working — `core/strike_detector.py` + `core/calibrator.py`)
A per-finger **arm/contact state machine** that fires on **DECELERATION**. A hit needs:
- **ARM** — the fingertip first rose above the table by the arm clearance (checked on
  the **raw, un-smoothed** position, so a quick 1-frame lift isn't averaged away —
  spec §6.6), then came down. Rejects noise AND is the **masked-finger guard**
  (occluded finger reappearing near the table starts disarmed). Consumed per hit;
  small lifts re-arm so rolls work.
- **FAST APPROACH** — velocity reached ≥ `STRIKE_SPEED_THRESHOLD` (V_high).
- **DECELERATION = impact** — fires when velocity drops below `DECEL_SPEED_THRESHOLD`
  (V_low); does NOT wait for reversal, so the hit lands while the tip is still down.
- **CONTACT (min-depth)** — deepest point reached at least table-deep (within
  `CONTACT_BAND_PX` of the calibrated zero; deeper is fine).
- **No debounce** — the arm-consume rule replaces it (`MIN_FAST_FRAMES` +
  `REFRACTORY_MS` removed as deferred noise work, spec §16).

**Velocity is real-time px/second** (FPS-independent): `main.py` feeds a real
`MonotonicMsClock`. Smoothing/velocity windows are set in **ms** (`POS_SMOOTHING_MS`,
`VELOCITY_DELTA_MS`) and converted to frame counts using the **FPS measured at launch**
(~1.5 s warmup) — so a fixed real-time span holds at any frame rate. MediaPipe does NOT
pre-smooth landmarks (verified), so ours is the only smoothing.

**Two-phase launch calibration** (timer-based, no keyboard):
1. Rest all 10 fingertips on the table → per-finger **contact zero** (median).
2. Tap the **weakest finger** (`ARM_DRYRUN_FINGER="ring"`) → **arm clearance** =
   `ARM_CALIBRATION_FRACTION` (0.6) × **average swing amplitude** (zig-zag turning
   points with `ARM_SWING_MIN_PROMINENCE_PX`; outlier-robust, not max-min). Sizing it
   to the weakest finger lets every stronger finger clear the arm line.

### Tuned values (validated live at ~15 FPS — in `config.py`)
`STRIKE_SPEED_THRESHOLD=130` px/s · `DECEL_SPEED_THRESHOLD=60` · `CONTACT_BAND_PX=25` ·
`ARM_DRYRUN_FINGER="ring"` · `ARM_CALIBRATION_FRACTION=0.6` · `ARM_SWING_MIN_PROMINENCE_PX=6`
· `POS_SMOOTHING_MS=100` · `VELOCITY_DELTA_MS=33`. Result: ring 4–5/5 incl. soft taps,
no false/double fires, zero crosstalk to neighbors.

### Debug CSV logger — KEEP for production calibration
`DEBUG_LOG_ENABLED` (now **False** for normal use). When True, writes `debug_log.csv`
(per-frame detector internals + `#` header with fps/calibration). This is the tool we
used to tune the thresholds and is **intended for the production app's calibration UI** —
do not remove. Analyze with the scripts pattern used this session (parse, skip `#`,
find FIRE/impact events, check velocities vs thresholds).

### Known limitations / deferred (spec §16)
- **Calibrate BOTH hands** on the table — an uncalibrated finger runs kinematic-only
  (no gates) and false-fires on any motion (we chose calibration discipline over a
  code guard).
- **Per-finger arm clearance** would be more robust than the current global value
  (median-of-swings is an easy upgrade).
- **Fast hand exit / teleport glitch** (landmark jumps as a hand leaves frame) can
  fake a hit — deemed a debug-procedure artifact, intentionally NOT fixed.
- Calibration timings (1.5 s / 4 s) are PLACEHOLDERS; `sweep` band mode is future
  work; an EMA (time-windowed) smoother is the upgrade if FPS fluctuates mid-run.

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
│   │   ├── strike_detector.py         #   arm/contact state machine, fires on DECELERATION (tuned)
│   │   └── calibrator.py              #   contact-zero (median) + arm-clearance (avg swing) calibration
│   ├── vision/                        # DESKTOP-ONLY producer, behind interfaces:
│   │   ├── camera_source.py           #   ICameraSource + OpenCvCameraSource (CAP_DSHOW)
│   │   └── hand_landmarker.py         #   ILandmarkSource + MediaPipeHandLandmarker (hands only, VIDEO mode)
│   ├── output/                        # consumers:
│   │   ├── sound_engine.py            #   ISoundEngine + LoggingSoundEngine (debug) + AudioSoundEngine (TODO ← NEXT)
│   │   ├── visualizer.py              #   OpenCV window + full 21-pt skeleton + red strike flash + FPS
│   │   └── debug_logger.py            #   CSV logger for calibration/finetuning (gated by DEBUG_LOG_ENABLED)
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
flat on the table (BOTH hands, or only the hand you want active); (2) tap a few times
with your **ring** finger (the weakest — sizes the arm clearance to fit all fingers).
Then play begins. Quit with **`q`** or by closing the window. The window
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
- `STRIKE_SPEED_THRESHOLD` = `130.0` (V_high: min approach speed, **px/sec** — raise
  if trigger-happy, lower if real taps get missed. Tuned 130 for slow ring taps)
- `DECEL_SPEED_THRESHOLD` = `60.0` (V_low: "almost zero" speed, px/sec, that = impact;
  fires here, not on reversal. Must be < V_high)
- `GAP_RESET_MS` = `100` (drop+disarm a finger if unseen this long)
- _(removed, deferred noise work: `MIN_FAST_FRAMES`, `REFRACTORY_MS` — spec §16)_
- `CONTACT_GATE_ENABLED` = `True` (False → pure kinematic, no calibration needed)
- `CONTACT_BAND_PX` = `25.0` (min-depth tolerance below the calibrated table height)
- `ARM_CALIBRATION_ENABLED` = `True`, `ARM_DRYRUN_FINGER` = `"ring"` (weakest),
  `ARM_CALIBRATION_FRACTION` = `0.6` (clearance = 0.6 × avg ring swing),
  `ARM_SWING_MIN_PROMINENCE_PX` = `6.0` (min travel to count a swing),
  `ARM_CLEARANCE_PX` = `35.0` (fallback if dry-run skipped; keep > band)
- `CALIBRATION_CAPTURE_SECONDS` = `1.5` / `ARM_DRYRUN_SECONDS` = `4.0` (PLACEHOLDERS),
  countdowns `3.0` each
- `DRAW_FPS` = `True` (live real-FPS overlay, top-right)
- `DEBUG_LOG_ENABLED` = `False` for normal use — flip to `True` for a calibration/
  finetuning session, then back. `DEBUG_LOG_HANDS` = both hands. CSV cols: ts, raw_y,
  smoothed_y, velocity_pxps, depth, armed, was_fast, deepest_y, contact_zero_y,
  arm_line_y, event, fired, strike_speed; `#`-header has fps + calibration values.
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
- ✅ **Detection tuned & validated LIVE (2026-05-29):** index 5/5; ring (weakest)
  4–5/5 incl. soft taps; no false fires, no double-fires, zero crosstalk to neighbor
  fingers; fires on deceleration (low latency); full 10-finger kit triggered mapped
  drums in a normal run. Tuning was driven by the CSV debug logger.
- ✅ **FPS-adaptive & real-time:** velocity in px/s (FPS-independent); smoothing
  windows derived from measured FPS at launch (works at the user's ~15 FPS).
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
Branch: **`1.7.4-done-finger-hit-detection`**. Main branch: `main`. Some work is
committed (latest: `modified the FPS`); the detection-tuning + debug-logger changes
from this session are **uncommitted in the working tree** (~9 changed files). Consider
committing this calibration milestone before starting audio.

## 10. Suggested first actions in the new conversation
1. **Implement real audio** — the one remaining gap (see §0 "NEXT STEP"):
   `AudioSoundEngine` + per-finger samples + swap into `main.py`.
2. (Old, now done) ~~calibrate detection vs add sound first?~~ — detection is tuned &
   validated live. If you instead need to re-tune feel, flip `DEBUG_LOG_ENABLED=True`,
   run, and analyze `debug_log.csv` (see §0 "Debug CSV logger").
3. For audio: choose a license-free library (candidates: `pygame.mixer`,
   `simpleaudio`, `sounddevice`, `playsound`), implement `AudioSoundEngine` in
   `output/sound_engine.py`, add per-finger sample files, and wire it in `main.py`.
   Requirements: low-latency one-shot playback, overlapping voices (rolls), permissive
   license, cross-platform-friendly design (spec §8). `strike_speed` (px/s) is on the
   `StrikeEvent` and can drive velocity-sensitive volume later.
