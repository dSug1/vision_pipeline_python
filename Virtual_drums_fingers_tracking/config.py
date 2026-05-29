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
SMOOTHING_WINDOW = 3           # frames of moving-average smoothing before differentiating
STRIKE_SPEED_THRESHOLD = 8.0   # min approach speed (px/frame for x/y) to count as a strike
REFRACTORY_MS = 120            # min time between two strikes of the same finger

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
