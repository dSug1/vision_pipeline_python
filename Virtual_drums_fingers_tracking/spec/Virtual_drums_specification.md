# Virtual Drums — Finger Tracking — Specification

**App folder:** `Virtual_drums_fingers_tracking/`
**Status:** new desktop application (Windows), to be built. Supersedes the
original `MouseCursorApp` (which is retired).
**Relationship to the original design:** the repo's `docs/General_specification.md`
describes the **original server–client** design. This app keeps the same
*conceptual* pipeline (camera → MediaPipe hand landmarks → action) but drops the
socket/multi-process model in favour of a **single process with in-process
messaging**, per the project's clean-architecture / mobile-portability goal.

---

## 1. Purpose & concept

A desktop app that turns a webcam into a **finger drum kit**. The camera is laid
on a table; the user's fingers are in front of it, and the camera sees only the
**last two or three phalanges** of the fingers of both hands. When a finger taps
the table, the app detects the "strike" and emits a **drum sound** — **a
different sound per finger** (up to 10).

- **Strike detection** is purely kinematic: track each fingertip's motion, take
  the time-derivative (velocity), and fire a strike on the **velocity sign
  inversion** (the finger decelerates and rebounds at impact), gated by a
  velocity threshold (noise rejection) and a refractory period (debounce).
- **Sound** is produced by a license-free audio library (chosen later). Until
  then, **debug mode** flashes a **light signal** per finger in the app window.
- **One window** shows the live camera view with hand + finger landmarks drawn.

### Camera & ergonomics
- Camera flat on the table, fingers approaching the table surface in its field of
  view; only finger tips / distal phalanges are visible (no palm, often no wrist).
- The "strike axis" is the image-space direction corresponding to *toward the
  table*. It is **configurable / calibratable** (default: vertical image axis),
  because it depends on how the camera is laid down. See §7.

---

## 2. Architecture

**Single process. No sockets. No subprocesses.** A `producer → consumer` design
connected by an **in-process event bus** (callbacks / observer / thread-safe
queue). Multiple consumers may subscribe — which is why the original
**single-client server limitation simply does not exist here**.

```
┌──────────────────────────── Virtual Drums (one process) ─────────────────────────────┐
│                                                                                       │
│  PRODUCER (vision)                          CORE (portable domain logic)              │
│  ┌───────────────┐   frames   ┌───────────────┐  LandmarkFrame  ┌──────────────────┐ │
│  │ CameraSource  │──────────▶ │ HandLandmarker │───── event ───▶ │  FingerTracker   │ │
│  │ (cv2, desktop)│            │ (MediaPipe)    │                 │  + StrikeDetector│ │
│  └───────────────┘            └───────────────┘                 └────────┬─────────┘ │
│         ▲ ICameraSource              ▲ ILandmarkSource          StrikeEvent│           │
│         │                                                                  ▼           │
│                                   EVENT BUS (in-process pub/sub)  ┌──────────────────┐ │
│                                                                   │  Consumers:      │ │
│                                                                   │  • SoundEngine   │ │
│                                                                   │  • Visualizer    │ │
│                                                                   │    (window)      │ │
│                                                                   └──────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

**Module boundaries are interfaces** (`ICameraSource`, `ILandmarkSource`,
`ISoundEngine`, an event-bus contract). These are the **mobile-portability
seams**: the desktop implementations (OpenCV camera, OpenCV window, MediaPipe
Python) are swappable without touching `core/`.

### Portability classification
| Layer | Ports to mobile? | Notes |
|---|---|---|
| `core/` (events, contracts, finger tracking, strike detection) | ✅ **Design + logic port** | Pure, framework-free; reimplement 1:1 in the mobile language |
| Data contracts (`LandmarkFrame`, `StrikeEvent`, finger IDs) | ✅ **Port as-is** | The stable contract a mobile rebuild targets |
| Model file (`hand_landmarker.task`) | ✅ **Reuse the file** | Same bundle on Android/iOS native SDKs |
| `CameraSource` (cv2.VideoCapture) | ❌ Desktop-only | Swap for CameraX/AVFoundation behind `ICameraSource` |
| `HandLandmarker` (MediaPipe **Python**) | ❌ Desktop-only | Swap for MediaPipe **Tasks SDK** behind `ILandmarkSource` |
| `Visualizer` (OpenCV window) | ❌ Desktop-only | Swap for native UI |

---

## 3. Module breakdown & interfaces

### 3.1 `core/` — portable domain logic (no OpenCV / MediaPipe imports)
- **`events.py`** — a minimal thread-safe **EventBus** (publish/subscribe by event
  type) plus event dataclasses. Decouples producer from consumers.
- **`contracts.py`** — the data contract (see §4): `Handedness`, `FingerId`,
  `Landmark`, `HandLandmarks`, `LandmarkFrame`, `StrikeEvent`.
- **`finger_tracker.py`** — consumes `LandmarkFrame`, extracts the strike point
  per finger (fingertip landmark, optionally averaged with the DIP joint for
  stability), and maintains a short per-finger position/time history.
- **`strike_detector.py`** — the kinematic strike algorithm (§6). Emits
  `StrikeEvent`s onto the bus.

### 3.2 `vision/` — the producer (desktop implementations behind interfaces)
- **`ICameraSource`** → `read() -> (ok, frame)`, `release()`. Impl
  **`OpenCvCameraSource`** using `cv2.VideoCapture(0, cv2.CAP_DSHOW)` — DirectShow
  backend (reliable on Windows) + clean `try/finally` release. Self-contained.
- **`ILandmarkSource`** → given a frame + timestamp, returns/raises
  `LandmarkFrame`. Impl **`MediaPipeHandLandmarker`** wrapping the MediaPipe
  HandLandmarker Task (hands only — §5).

### 3.3 `output/` — consumers
- **`ISoundEngine`** → `play(finger_id: FingerId)`. Implementations:
  - **`LoggingSoundEngine`** (debug, default first): subscribes to `StrikeEvent`
    and prints the strike — no audio dependency.
  - **`AudioSoundEngine`** (later): plays a per-finger sample via a license-free
    library (TBD — §8).
- **`Visualizer`** — renders one window: camera frame + finger landmarks + the
  **debug light flash** (it also subscribes to `StrikeEvent`). OpenCV `imshow` for
  the prototype (lightest). Handles quit via `q` / window close.

### 3.4 `main.py` — composition root
Wires the graph, owns the run loop: capture frame → detect landmarks → publish
`LandmarkFrame` → (FingerTracker/StrikeDetector publish `StrikeEvent`) →
consumers react → Visualizer draws. **Launching the app launches the whole
vision pipeline** (it is all one process).

---

## 4. Data contracts (stable, portable)

```text
Handedness = "Left" | "Right"

FingerId (10):  LEFT_THUMB, LEFT_INDEX, LEFT_MIDDLE, LEFT_RING, LEFT_PINKY,
                RIGHT_THUMB, RIGHT_INDEX, RIGHT_MIDDLE, RIGHT_RING, RIGHT_PINKY

Landmark      = { x, y, z (normalized 0..1, z relative), x_px, y_px (pixels) }
HandLandmarks = { handedness, landmarks: Landmark[21] }      # MediaPipe 21-point hand
LandmarkFrame = { timestamp_ms, frame_w, frame_h, hands: HandLandmarks[] }   # 0..2 hands

StrikeEvent   = { finger_id, handedness, timestamp_ms, strike_speed, position(x_px,y_px) }
```

**MediaPipe 21-landmark indices** (per hand) — strike points are the **TIP**s,
last phalanx joints are the **DIP/IP**s:

| Finger | TIP | DIP/IP (last joint) |
|---|---|---|
| Thumb  | 4  | 3 (IP) |
| Index  | 8  | 7  |
| Middle | 12 | 11 |
| Ring   | 16 | 15 |
| Pinky  | 20 | 19 |

> The camera sees the last 2–3 phalanges, so TIP (4/8/12/16/20) and DIP (3/7/11/15/19)
> are the reliably-visible landmarks; palm/wrist landmarks (0–2, 5, 9, 13, 17) may
> be out of frame. We **only consume the finger landmarks**; the rest are ignored.

**Finger → sound mapping** is a configurable table (default: 10 distinct samples).
Defined in config, not hard-coded, so it is easily reassigned.

---

## 5. MediaPipe configuration — and the "no palm" question

**Use the Hand Landmarker only — do NOT load the Face Detector** (the original
pipeline loaded both; dropping face is the single biggest CPU saving). The loading
logic is reimplemented self-contained in `vision/hand_landmarker.py` (hands only).

**On removing palm detection:** in the MediaPipe **HandLandmarker Task**, the
**palm detector is an internal bootstrap stage and cannot be independently
disabled** — it locates the hand and produces the ROI that the 21-point landmark
model runs on. However:
- In **`RunningMode.VIDEO`** (or `LIVE_STREAM`) the Task **tracks** hands across
  frames and only re-runs the palm detector **when tracking is lost**, so its cost
  is **amortized**, not paid every frame. This already achieves most of the
  "skip the palm work" benefit.
- We **ignore** the palm/wrist landmarks downstream — only finger landmarks feed
  the drum logic. So "just the hands, not the palm" is satisfied at the *usage*
  level even though the detector stage remains.

⚠️ **Risk to validate (§16):** with only phalanges visible (palm out of frame),
re-acquisition via the palm detector after tracking loss may be unreliable. The
user has confirmed the full pipeline works; we must confirm it still re-acquires
robustly. Mitigation knobs: lower `min_hand_detection_confidence`, keep hands in
frame, tune `min_tracking_confidence`.

**Recommended options:**
- `num_hands = 2`
- `running_mode = VIDEO` (monotonic timestamp per frame; reuse the `timestamp_ms += dt` pattern)
- `min_hand_detection_confidence`, `min_hand_presence_confidence`,
  `min_tracking_confidence` — start at defaults, tune for the table setup
- Consider the **lite** hand-landmark model bundle if accuracy permits (lower CPU)
- Model file **bundled in this app** at `models/hand_landmarker.task` (copied, not linked)

---

## 6. Strike-detection algorithm

For each finger, track its strike-axis coordinate `p(t)` over time (default: the
fingertip's pixel **y**, the table-ward axis — configurable, see §7). The detector
is a small **per-finger arm/contact state machine** combining kinematic and
positional conditions; each rejects a different false positive so one real tap = one
hit. Implemented in `core/strike_detector.py`.

**Kinematic core**
1. **Smooth** `p(t)` with a moving average to suppress landmark jitter. The window
   is specified in **real time** (`POS_SMOOTHING_MS`); at launch the app **measures
   the actual FPS** (`MonotonicMsClock` over a ~1.5 s warmup — `CAP_PROP_FPS` is
   unreliable on DirectShow) and converts it to a frame count, so the smoothing spans
   a consistent duration whether the camera runs at 15, 30, or 60 FPS. (E.g. 100 ms →
   2 frames @15 FPS, 3 @30 FPS.) Falls back to `POS_SMOOTHING_FRAMES` if measurement
   fails or `KINEMATICS_AUTO_FROM_FPS` is off.
2. **Velocity** (1st derivative) computed between two smoothed samples
   `VELOCITY_DELTA_FRAMES` apart, **divided by the real elapsed wall-clock time**
   between them → **px/second**, then sign-normalized via `APPROACH_SIGN` so **+ve =
   toward the table**. Because it is normalized by real time, the speed thresholds
   (V_high/V_low) are **FPS-independent** — they don't shift when the frame rate
   varies (`main.py` feeds a real `MonotonicMsClock`, not a synthetic frame clock).
   These two frame counts are independent, tunable knobs: detection latency ≈
   `(POS_SMOOTHING_FRAMES + VELOCITY_DELTA_FRAMES)` frames (smoothing 2–3, delta 1
   is the sweet spot at ~30 FPS). NOTE: MediaPipe does **not** smooth landmark
   coordinates (verified — no such option in the Tasks API), so this is the *only*
   smoothing in the chain; it does not compound with the detection pipeline.
   *Note:* the smoothing/velocity windows are derived from real-time (ms) values via
   the measured FPS (step 1), so their real-time span holds across frame rates. This
   assumes a roughly **stable** FPS; if the camera's FPS *fluctuates* mid-run (common
   under changing light at ~15 FPS), the startup-measured conversion is fixed — a
   fully time-windowed (EMA) smoother would be the next step. Still, very low FPS
   inherently limits temporal resolution (a tap is only ~2-3 frames at 15 FPS).
3. **Fast approach:** the toward-table velocity must reach **≥ `STRIKE_SPEED_THRESHOLD`
   (V_high)** during the descent. This is the speed gate. The max velocity of the
   burst is reported as `strike_speed` (free; reusable later for velocity-sensitive
   volume) but is **not** itself a gate.
4. **Deceleration = impact:** the hit fires on the frame velocity drops **below
   `DECEL_SPEED_THRESHOLD` (V_low, "almost zero")** right after the fast approach —
   the finger slammed to a stop *at* the table. We deliberately **do not wait for
   the velocity to reverse** (go negative): by then the finger has already left the
   table, which is pure latency. Firing on the deceleration lands the hit ~1 frame
   earlier, while the tip is still on the surface. (This is why peak-speed tracking
   was removed: the speed gate in step 3 already enforces "the approach was fast",
   so a separate remembered max was redundant.)

> **No refractory/debounce.** The arm is **consumed** on each hit (step 6) and the
> finger must rise back above the arm line to re-arm, so a micro-bounce at the table
> cannot re-fire — the arm-consume rule *is* the debounce. (Caveat: with the contact
> gate disabled [kinematic-only fallback] there is no arm gate, hence no debounce —
> see §16. A consecutive-fast-frames noise gate was also removed; both are deferred.)

**Positional conditions** (active once the finger is calibrated, §7; otherwise the
detector falls back to kinematic-only)
6. **ARM (high-position threshold):** a hit can only fire if the fingertip first
   **rose above the table by the arm clearance** (above the contact zero) and then
   came down. This (a) rejects derivative noise — a resting/jittering finger never
   crossed the line — and (b) is the **masked-finger guard**: a finger that was
   occluded (e.g. the thumb) and reappears near the table starts **disarmed** and
   cannot fire until it is lifted. Small lifts re-arm it, so fast rolls still work.
   The arm is **consumed** on each hit; the finger must clear the line again to
   re-arm. The clearance is **measured at launch** by the index-finger dry-run (§7)
   — `ARM_CALIBRATION_FRACTION` (0.4) of the real tap amplitude — falling back to
   `ARM_CLEARANCE_PX` if the dry-run is skipped.
   > The arm check uses the **raw (un-smoothed)** position, unlike velocity/contact
   > which use the smoothed signal. Reason (found in live tuning, 15 FPS): a quick
   > shallow lift is only 1 frame, and the moving average blends it with neighbours,
   > hiding the rise — so a real fast tap was rejected as "not armed". Arming only
   > *enables* a hit (the fire still needs speed + reaching the table), so using the
   > raw position is safe and catches brief lifts. Tuned on real data: arm-on-raw +
   > `ARM_CALIBRATION_FRACTION=0.4` gives 5/5 hits with no false/double fires.
7. **CONTACT (min-depth):** the deepest point reached must be **at least table-deep**
   — within `CONTACT_BAND_PX` of the calibrated contact zero (deeper is fine). This
   rejects mid-air taps that decelerate above the table. (Min-depth chosen over a
   symmetric band so hard taps that overshoot the surface are not lost.)

On a valid strike, publish `StrikeEvent(finger_id, …, strike_speed)`.

**Tunable parameters (to calibrate — §16):** `POS_SMOOTHING_FRAMES`,
`VELOCITY_DELTA_FRAMES`, `STRIKE_SPEED_THRESHOLD` (V_high), `DECEL_SPEED_THRESHOLD`
(V_low), `GAP_RESET_MS`, `STRIKE_AXIS`, `APPROACH_SIGN`, `CONTACT_GATE_ENABLED`,
`CONTACT_BAND_PX`, `ARM_CALIBRATION_FRACTION` / `ARM_CLEARANCE_PX`. All live in
config, not code. *(Deferred noise knobs `MIN_FAST_FRAMES` and `REFRACTORY_MS` were
removed for now — see §16.)*

> Re-acquisition: if a finger is unseen for `GAP_RESET_MS` its motion history is
> dropped **and it is disarmed**, so we never differentiate across the absence gap
> and a re-entering hand cannot fake a strike.
> Optional refinements (future): corroborate with the 2nd derivative (acceleration
> spike); use landmark `z` (depth) if the camera geometry makes depth the cleaner
> strike axis.

---

## 7. Strike axis & calibration

### Strike axis
Because the camera is *laid on the table*, "toward the table" may map to image
**y**, image **x**, or **z** depending on placement. Provided as config: the
`STRIKE_AXIS` flag (default `y`) and an `APPROACH_SIGN` (+1/−1) for which direction
along that axis is "toward the table". *(Future: auto-pick the axis with the largest
oscillation amplitude over a few taps.)*

### Contact calibration (launch-time, two phases)
At launch the app calibrates the positional gates (§6.6–6.7) in two timed phases
(`core/calibrator.py` + `run_calibration` in `main.py`). Both run purely on a
**timer** — *the keyboard is not used during capture* — so the user can keep hands
on the table. Closing the window aborts → kinematic-only.

**Phase 1 — contact zero (per finger).**
1. A countdown banner asks the user to **rest all 10 fingertips flat on the table**.
2. Capture for `CALIBRATION_CAPTURE_SECONDS`.
3. The contact zero per finger is the **median** of its samples (robust to stray
   frames); fingers with too few samples are left **ungated** (kinematic-only).

**Phase 2 — arm-clearance dry-run (the WEAKEST finger).**
1. A banner asks the user to **tap a few times with the `ARM_DRYRUN_FINGER`** —
   default the **ring** finger. Calibrate with the *weakest* finger on purpose: its
   lift is the smallest, so a clearance sized to it lets every *stronger* finger
   (which lifts more) clear the arm line too. (Calibrating with the strong index set
   the bar too high — the ring couldn't reach it; found in live tuning 2026-05-29.)
2. Capture for `ARM_DRYRUN_SECONDS`; measure that finger's **average swing
   amplitude**: a zig-zag detector finds alternating turning points (press valleys /
   lift peaks) that reverse by at least `ARM_SWING_MIN_PROMINENCE_PX` (rejects
   landmark jitter ~3-5 px), and the peak-to-valley travels are **averaged**. This is
   outlier-robust — one stray high lift is a single swing among many, not the whole
   value (unlike max-min). Tap the dry-run the way you'll actually play.
3. Arm clearance = `ARM_CALIBRATION_FRACTION` (0.6) × average swing. One global
   clearance (px), applied to all fingers; falls back to `ARM_CLEARANCE_PX` if no
   clean swings are captured. The fraction + the raw-position arm check (§6.6) keep
   it forgiving. *(Per-finger arm clearance would be the fully robust fix — §16.)*

> ⚠️ **PLACEHOLDER TIMING — fine-tune later.** `CALIBRATION_CAPTURE_SECONDS = 1.5`,
> `ARM_DRYRUN_SECONDS = 4.0`, and the 3 s countdowns are first guesses. The global
> (non-per-finger) arm clearance and the 2/3 fraction are also first cuts. Revisit
> once tested live.

**Width modes for the contact band:**
- **`fixed` (current):** the band half-width is the config float `CONTACT_BAND_PX`
  around the captured zero. Fast to tune for debugging.
- **`sweep` (FUTURE — not yet implemented):** during calibration the user keeps
  fingers on the table and slides hands **nearer/farther** from the camera; the app
  records the per-finger **range** of contact positions (perspective makes "touching"
  span a range of pixels) and sizes the band automatically. To be added; tracked in
  §16.

---

## 8. Sound output
- **Debug-first:** the **Visualizer** flashes a per-finger colored marker in the
  window on each strike (it subscribes to `StrikeEvent`), and a debug
  `LoggingSoundEngine` prints each strike — validating detection with **zero audio
  dependency**.
- **Audio (later):** a **license-free** library (TBD). Requirements: low-latency
  one-shot sample playback, overlapping voices (fast rolls), permissive license,
  cross-platform-friendly (so the *design* ports). Candidates to evaluate when we
  get there: `pygame.mixer`, `simpleaudio`, `sounddevice`, `playsound` — decision
  deferred. Per-finger samples live as asset files; mapping is config-driven (§4).

---

## 9. UI / window
- **One OpenCV window** showing the live (BGR) camera frame with finger landmarks
  drawn (implemented self-contained in `output/visualizer.py` with plain OpenCV —
  **no dependency on MediaPipe's legacy `solutions`/`framework` modules**).
- Overlay debug **light signals** (per-finger markers that flash on strike).
- Quit on `q` or window-close (reuse the hardened shutdown, §10).
- Keep drawing **cheap** (only finger landmarks + small markers) to protect the
  frame rate (§11).

---

## 10. Self-contained implementation (independent folder)

> **This folder is fully independent.** It does **not** import from, link to, or
> depend on `MouseCursorApp/` or `Python_Server_MediaPipe_vision_pipeline/`. The
> ideas below were *reimplemented internally* (and the model file copied in), so
> the whole `Virtual_drums_fingers_tracking/` folder can be copied elsewhere and
> run on its own (`launch.bat` builds a local `.venv` from the local
> `requirements.txt`).

Concepts adapted from the original app, **reimplemented here**:
- Webcam capture with **`cv2.CAP_DSHOW`** + clean `try/finally` release + `q`/
  window-close shutdown → `vision/camera_source.py` + `main.py`.
- HandLandmarker loading & per-frame inference (hands only) → `vision/hand_landmarker.py`.
- Landmark→pixel conversion → `vision/hand_landmarker.py` (in the `LandmarkFrame` build).
- Landmark drawing → `output/visualizer.py` (plain OpenCV, no legacy `solutions`).
- The **producer→consumer** pattern (originally socket dispatch) → the in-process
  **EventBus** + interfaces (`ICameraSource`, `ILandmarkSource`, `ISoundEngine`).

**Drop entirely (the "lighter" part):**
- ❌ Face detector + `facevisualizer` + the BGR/RGB blend (`addWeighted`).
- ❌ TCP **socket** server/client, the **launcher**, **subprocess** spawning.
- ❌ All **disk JSON** I/O (already removed in MouseCursorApp; here it never exists).
- ❌ Win32 `SetCursorPos` cursor control.

---

## 11. Performance & CPU/GPU optimization (explicit requirement)
- **Hands-only** inference (no face model loaded) — biggest single win.
- **VIDEO mode + tracking** so the palm detector runs rarely (§5).
- **`num_hands = 2`** (no more than needed).
- Consider the **lite** hand model; consider **GPU/XNNPACK delegate** where
  available (Windows = CPU/XNNPACK by default).
- **Downscale** the capture frame before inference if accuracy allows (less
  pre-processing); cap capture resolution/FPS to what's needed.
- **In-memory only** — no JSON, no sockets, no disk (zero I/O per frame).
- **Minimal drawing** — only finger landmarks + strike markers.
- **Threading:** capture+inference on a worker; UI on the main thread; sound on
  its own thread/callback so audio never blocks inference. The event bus
  decouples these cleanly.
- Process only the **finger** landmarks downstream; ignore palm/wrist points.

---

## 12. Proposed folder structure
```
Virtual_drums_fingers_tracking/
├── README.md
├── main.py                     # composition root + run loop (launches the pipeline)
├── launch.bat                  # creates a LOCAL .venv, runs main.py
├── requirements.txt            # self-contained deps
├── config.py                   # thresholds, strike axis, finger→sound map
├── core/                       # PORTABLE — no cv2/mediapipe imports
│   ├── __init__.py
│   ├── events.py               # EventBus + event types
│   ├── contracts.py            # Handedness, FingerId, Landmark, LandmarkFrame, StrikeEvent
│   ├── finger_tracker.py
│   └── strike_detector.py
├── vision/                     # PRODUCER (desktop impls behind interfaces)
│   ├── __init__.py
│   ├── camera_source.py        # ICameraSource + OpenCvCameraSource   [DESKTOP-ONLY]
│   └── hand_landmarker.py      # ILandmarkSource + MediaPipeHandLandmarker
├── output/                     # CONSUMERS
│   ├── __init__.py
│   ├── sound_engine.py         # ISoundEngine + LoggingSoundEngine (+ AudioSoundEngine later)
│   └── visualizer.py           # OpenCV window + strike flashes        [DESKTOP-ONLY]
└── models/
    └── hand_landmarker.task    # bundled model (portable asset, copied in)
```

---

## 13. Launch
- **`launch.bat`** (in this folder): `cd`s to **this folder**, creates a **local
  `.venv`** from the local `requirements.txt` on first run, then runs `main.py`.
  No dependency on the repo-root venv — the folder is self-contained.
- Launching the app **is** launching the vision pipeline — one process, no
  separate server to start.
- Stop with `q` or by closing the window (clean camera release via `try/finally`).

---

## 14. Dependencies (self-contained)
- The folder declares its own [`requirements.txt`](../requirements.txt) and uses
  its own **local `.venv`** (created by `launch.bat`): `mediapipe==0.10.14`
  (pinned), `opencv-contrib-python`, `numpy`.
- This app does **not** use MediaPipe's legacy `solutions`/`framework` modules
  (drawing is plain OpenCV), so it is **not** bound to the old pin for that reason
  — kept pinned only for reproducibility.
- **Audio library:** TBD (license-free) — added to `requirements.txt` when chosen.

---

## 15. Mobile-portability notes
The seams that must stay clean (so a future mobile rebuild reuses the *design*):
`core/` is framework-free and ports 1:1; the data contracts (§4) are the API a
mobile app reimplements; the model file is reused as-is; `ICameraSource`,
`ILandmarkSource`, and `ISoundEngine` isolate every desktop-only dependency
(`cv2`, MediaPipe-Python, OpenCV window) so they can be swapped for CameraX/
AVFoundation, the native MediaPipe Tasks SDK, and native audio/UI.

---

## 16. Open questions / to calibrate / risks
1. ✅ **RESOLVED (2026-05-29) — Palm-detector re-acquisition with only phalanges
   visible.** Validated live: hand/finger tracking works when only the last 2-3
   phalanges are in frame (palm out of view), **and** re-acquires cleanly after a
   hand leaves and re-enters the frame. *(This was the highest risk — now cleared.)*
2. **Strike axis & thresholds** (`STRIKE_SPEED_THRESHOLD`, `REFRACTORY_MS`,
   `POS_SMOOTHING_FRAMES`, `VELOCITY_DELTA_FRAMES`, `CONTACT_BAND_PX`,
   `ARM_CLEARANCE_PX`) — must be empirically calibrated live for the table/camera.
2a. **Calibration timing** (`CALIBRATION_CAPTURE_SECONDS = 1.5`, 3 s countdown) is a
   PLACEHOLDER — fine-tune after live testing (§7).
2b. **Sweep calibration mode** (auto-size the contact band by moving hands near/far)
   is FUTURE WORK — only `fixed` width mode exists today (§7).
2c. **Noise-elimination layer (DEFERRED).** Two guards were intentionally removed to
   keep the logic lean, to be revisited once the core is tuned live:
   • `MIN_FAST_FRAMES` — require N consecutive ≥ V_high frames before a hit (rejects
     single-frame velocity spikes).
   • `REFRACTORY_MS` — per-finger debounce. Currently redundant because the
     arm-consume rule prevents re-fire until the finger re-arms; **but** in the
     kinematic-only fallback (contact gate disabled) there is then **no debounce** —
     reinstate if that mode is used. The current gates (arm-rise, high→low velocity
     transition, contact vicinity) are relied on for noise rejection meanwhile.
3. **`y` vs `z`** as the strike axis — evaluate which is cleaner for this geometry.
4. **Lite vs full** hand model — accuracy vs CPU trade-off for this close-up,
   partial-hand view.
5. **Audio library** choice and latency (must keep tap→sound latency low).
6. **Thumb** ergonomics — thumbs may strike differently than fingers; may need a
   per-finger axis/threshold.
7. **10-finger separation** — reliably distinguishing adjacent fingers when only
   tips are visible and hands are close together.
