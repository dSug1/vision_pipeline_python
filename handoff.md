# Project Handoff

_Last updated: 2026-05-29. Read this to resume work in a new conversation._

---

## 0. START HERE — immediate next step

The **Virtual Drums** app runs end-to-end (camera → hand landmarks → per-finger
"strike" → debug flash + console print). User chose **detection logic/calibration
first**, then audio.

**Done (2026-05-29): reworked the strike-detection logic** (`core/strike_detector.py`).
The first pass had three real bugs, now fixed:
1. It only checked the *single previous frame's* velocity, so hard taps whose
   deceleration spanned 2–3 frames were **missed**. Now it tracks the **peak
   approach speed** over the whole descent and fires on reversal if the peak beat
   the threshold (matches spec §6.4).
2. **No history reset on re-acquisition** → a phantom strike fired the instant a
   hand re-entered the frame (differentiating across the absence gap). Now a
   `GAP_RESET_MS` guard drops stale motion history when a finger reappears.
3. Smoothing was folded into the derivative oddly; now it's a clean moving-average
   position → 1-frame velocity.
Verified with synthetic sequences (real tap → 1 hit, jitter → 0, re-acquisition →
0, double-tap → 2, direction-sign flip works). **Not yet run on the live camera.**

Next work, in order:

1. **Run live & calibrate** the new logic (tune `config.py`). See §10.
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
(local `.venv` is already built, so it starts immediately). Quit with **`q`** or
by closing the window. You'll see green fingertip dots; a strike flashes that
fingertip red + larger and prints e.g. `[drum] left_index -> snare`.

**Key tunables — `Virtual_drums_fingers_tracking/config.py`:**
- `STRIKE_AXIS` = `"y"` (image axis "toward the table"; options `y`/`x`/`z`)
- `APPROACH_SIGN` = `+1` (flip to `-1` if taps NEVER register — you're approaching
  in the decreasing-axis direction; this is the first thing to try if nothing fires)
- `STRIKE_SPEED_THRESHOLD` = `6.0` (min **peak** approach speed, px/frame, to count
  as a strike — raise if trigger-happy, lower if real taps get missed)
- `REFRACTORY_MS` = `120` (debounce per finger — raise to kill double-fires)
- `SMOOTHING_WINDOW` = `3` (frames smoothed before differentiating)
- `GAP_RESET_MS` = `100` (drop a finger's motion history if unseen this long)
- `FINGER_SOUNDS` = the finger→drum-name map (10 fingers). Labels are placeholders
  (kick/snare/hat_closed/hat_open/tom_low/tom_high/crash/ride + kick_2/snare_2).
  No audio yet — these are just printed.

**Strike algorithm (spec §6, in `strike_detector.py`):** moving-average smooth the
fingertip's strike-axis position → 1-frame velocity (sign-normalized so +ve =
toward table) → while descending, accumulate the **peak approach speed** → on
velocity sign inversion (stop/rebound at impact), fire if peak ≥
`STRIKE_SPEED_THRESHOLD`, debounced by `REFRACTORY_MS`. Stale history is dropped
after a `GAP_RESET_MS` absence so re-entering hands don't fake a strike. NOTE:
`main.py` uses a synthetic 33 ms/frame clock, so "velocity" is effectively
**px/frame**, not px/ms.

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
