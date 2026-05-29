"""Tunable configuration. All magic numbers live here so behaviour can be tuned
without touching logic. Self-contained. See spec sections 5, 6, 7."""
from core.contracts import FingerId

# --- Camera ---
CAMERA_INDEX = 0
CAPTURE_WIDTH = 640   # lower = less CPU for inference; None to use device default
CAPTURE_HEIGHT = 480

# --- MediaPipe HandLandmarker ---
MODEL_PATH = "models/hand_landmarker.task"   # resolved relative to the app folder
NUM_HANDS = 2
MIN_HAND_DETECTION_CONFIDENCE = 0.5
MIN_HAND_PRESENCE_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# --- Strike detection (spec sections 6/7; TO CALIBRATE for the table/camera) ---
STRIKE_AXIS = "y"              # "y" | "x" | "z" — image axis pointing toward the table
APPROACH_SIGN = +1             # +1 if "toward the table" means the axis value INCREASES,
                               #   -1 if it decreases. Flip this if taps never register
                               #   (you're approaching in the other direction).

# Kinematics — smoothing & velocity windows. The detector counts these in FRAMES,
# but a fixed frame count means a different real-time span at different frame rates
# (e.g. 3 frames = 100 ms @30 FPS but 200 ms @15 FPS, which over-smooths fast taps).
# So we specify them in TIME (ms) and let the app measure the real FPS at startup and
# convert to frame counts. NOTE: MediaPipe does NOT smooth landmark coordinates, so
# this is the ONLY smoothing in the chain — it does not compound with the pipeline.
KINEMATICS_AUTO_FROM_FPS = True  # measure FPS at launch and derive the frame windows below
MEASURE_FPS_SECONDS = 1.5        # how long to measure the camera FPS at startup
POS_SMOOTHING_MS = 100.0         # moving-average window (real time). ~100 ms is a good start;
                                 #   lower if fast taps get smoothed away, raise to reject noise.
VELOCITY_DELTA_MS = 33.0         # derivative baseline (real time) between the two smoothed samples.
# Used directly when KINEMATICS_AUTO_FROM_FPS is False, OR as the fallback if the FPS
# measurement fails:
POS_SMOOTHING_FRAMES = 3         # moving-average frames applied to the fingertip position
VELOCITY_DELTA_FRAMES = 1        # gap (frames) between the two smoothed samples for the velocity

# Strike = a fast approach that suddenly decelerates at the table. We fire on the
# deceleration (NOT on the velocity reversal) so the hit lands before the finger
# leaves the table. Requires velocity >= V_high during the descent, then < V_low.
# Speeds are in PIXELS PER SECOND (real wall-clock, FPS-independent — main.py feeds
# the detector real timestamps). At ~30 FPS, 180 px/s ~= 6 px/frame.
STRIKE_SPEED_THRESHOLD = 180.0 # V_high: min downward speed (px/sec) of the approach.
                               #   The main float to tune: raise = less sensitive.
DECEL_SPEED_THRESHOLD = 60.0   # V_low: 'almost zero' speed (px/sec) that marks the impact.
                               #   Must be < STRIKE_SPEED_THRESHOLD. Raise to fire a touch earlier.
GAP_RESET_MS = 100             # if a finger is unseen this long, drop its motion history AND
                               #   disarm it on re-acquisition (no phantom strike on re-entry)
# Deferred noise-elimination knobs (removed for now — reinstate later, spec §16):
#   MIN_FAST_FRAMES (require N consecutive >= V_high frames) and REFRACTORY_MS
#   (per-finger debounce). The arm-consume rule currently handles debounce; the
#   existing gates (arm-rise / high->low velocity / contact vicinity) handle noise.

# --- Contact gate + arming (needs calibration below; spec 6/7) ---
CONTACT_GATE_ENABLED = True    # False => pure kinematic detection (no table-height gating)
CONTACT_BAND_PX = 25.0         # min-depth tolerance: the tip must reach within this many px of
                               #   the calibrated table height to count (deeper is fine). Lower
                               #   = stricter about hitting the table.

# --- Contact calibration (fixed-width mode; SWEEP mode is future work — spec §7) ---
CALIBRATION_ENABLED = True
CALIBRATION_COUNTDOWN_SECONDS = 3.0  # time to place fingers before capture starts
CALIBRATION_CAPTURE_SECONDS = 1.5    # PLACEHOLDER timing — fine-tune later (spec §7).
                                     #   Keyboard is NOT used; capture is purely on this timer
                                     #   so the user can keep both hands on the table.

# --- Arm-clearance dry-run (measure the lift needed to (re)arm a hit; spec §7) ---
# Phase 2 of calibration: the user taps a few times with one index finger; we
# measure the tap amplitude (raised peak -> table) and set the arm clearance to a
# fraction of it (so a slightly smaller lift still re-arms -> fewer false negatives).
ARM_CALIBRATION_ENABLED = True
ARM_CALIBRATION_FRACTION = 0.667     # use 2/3 of the measured tap amplitude
ARM_DRYRUN_COUNTDOWN_SECONDS = 3.0
ARM_DRYRUN_SECONDS = 4.0             # PLACEHOLDER timing — fine-tune later
ARM_CLEARANCE_PX = 35.0              # fallback: used if the dry-run is disabled or yields no
                                     #   data. The tip must rise this far above the table to
                                     #   (re)arm a hit. Keep > CONTACT_BAND_PX.

# --- Debug visualization (spec sections 9; turn off for max frame rate) ---
DRAW_FULL_SKELETON = True      # draw EVERY hand landmark + bone (not just fingertips)
DRAW_LANDMARK_LABELS = False   # overlay the MediaPipe landmark index next to each point
DRAW_FPS = True                # overlay the measured (real wall-clock) loop FPS, top-right

# --- Finger -> sound mapping (debug logs the name; audio plays a sample later) ---
FINGER_SOUNDS = {
    FingerId.LEFT_THUMB:   "kick",
    FingerId.LEFT_INDEX:   "snare",
    FingerId.LEFT_MIDDLE:  "hat_closed",
    FingerId.LEFT_RING:    "tom_low",
    FingerId.LEFT_PINKY:   "tom_high",
    FingerId.RIGHT_THUMB:  "kick_2",
    FingerId.RIGHT_INDEX:  "snare_2",
    FingerId.RIGHT_MIDDLE: "hat_open",
    FingerId.RIGHT_RING:   "crash",
    FingerId.RIGHT_PINKY:  "ride",
}
