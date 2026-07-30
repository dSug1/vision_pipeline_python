import math

# Pure feature-extraction functions over a single hand's world_landmarks
# (Claude/GESTURE_PIPELINE_SPEC.md stage 3). Rebuilt fresh, not resurrected
# from the deleted rule-based GestureRules.py (PART_ONE.md §6-8) -- the math
# below (hand-size-normalized ratios, PIP-joint curl angles) is the same
# state-of-the-art-checked approach, but these functions are only ever
# consumed as model input features now, never as hand-picked thresholds
# themselves.
#
# Landmark shape expected everywhere: a list of 21 {"x", "y", "z"} dicts
# (MediaPipe's standard hand model, Specification.md §6). Call
# to_dict_landmarks() first if converting from MediaPipe's live result
# objects (.x/.y/.z attributes, not dict keys) -- see PART_ONE.md §7.1's
# "Integration bug found and fixed" note for why this conversion is a
# required call-site step, not optional.

WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

HANDCRAFTED_FEATURE_NAMES = [
    "pinch_ratio",
    "thumb_curl_deg",
    "index_curl_deg",
    "middle_curl_deg",
    "ring_curl_deg",
    "pinky_curl_deg",
    "curl_worst_deg",
]


def to_dict_landmarks(mp_landmarks):
    """Convert MediaPipe's live landmark objects (.x/.y/.z attributes) to
    this module's {"x", "y", "z"} dict shape. Recorded JSON is already in
    that shape and does not need this."""
    return [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in mp_landmarks]


def _vec(a, b):
    return (b["x"] - a["x"], b["y"] - a["y"], b["z"] - a["z"])


def _norm(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def distance(a, b):
    return _norm(_vec(a, b))


def angle_between_deg(v1, v2):
    """Angle between two 3D vectors, in degrees. 0 = parallel (straight
    finger segment), 180 = folded back onto itself (fully curled)."""
    n1, n2 = _norm(v1), _norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
    cos_angle = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos_angle))


def hand_size_ref(landmarks):
    """Wrist-to-middle-MCP distance -- the hand-size normalization
    reference used throughout (Specification.md §6, PART_ONE.md §6's
    'ratio-normalize by a hand-size reference' finding)."""
    return distance(landmarks[WRIST], landmarks[MIDDLE_MCP])


def pinch_ratio(landmarks, size_ref=None):
    size_ref = size_ref or hand_size_ref(landmarks)
    if size_ref == 0:
        return float("inf")
    return distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / size_ref


def _finger_curl_deg(landmarks, mcp, pip, tip):
    v1 = _vec(landmarks[mcp], landmarks[pip])
    v2 = _vec(landmarks[pip], landmarks[tip])
    return angle_between_deg(v1, v2)


def thumb_curl_deg(landmarks):
    return _finger_curl_deg(landmarks, THUMB_MCP, THUMB_IP, THUMB_TIP)


def index_curl_deg(landmarks):
    return _finger_curl_deg(landmarks, INDEX_MCP, INDEX_PIP, INDEX_TIP)


def middle_curl_deg(landmarks):
    return _finger_curl_deg(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP)


def ring_curl_deg(landmarks):
    return _finger_curl_deg(landmarks, RING_MCP, RING_PIP, RING_TIP)


def pinky_curl_deg(landmarks):
    return _finger_curl_deg(landmarks, PINKY_MCP, PINKY_PIP, PINKY_TIP)


def extract_handcrafted_features(landmarks):
    """7 hand-crafted features -> list, in HANDCRAFTED_FEATURE_NAMES order.
    One of the two input representations stage 3 compares (§6.2)."""
    size_ref = hand_size_ref(landmarks)
    middle, ring, pinky = (
        middle_curl_deg(landmarks),
        ring_curl_deg(landmarks),
        pinky_curl_deg(landmarks),
    )
    return [
        pinch_ratio(landmarks, size_ref),
        thumb_curl_deg(landmarks),
        index_curl_deg(landmarks),
        middle,
        ring,
        pinky,
        max(middle, ring, pinky),
    ]


def extract_raw_features(landmarks, handedness=None):
    """Raw landmark coordinates, wrist-relative and hand-size-normalized
    (63 values: 21 landmarks x,y,z) -- the other input representation
    stage 3 compares (§6.2), matching MediaPipe's own gesture-embedding
    model's input shape (a flat per-hand vector), just hand-size-normalized
    instead of image-size-normalized since this project works from metric
    world_landmarks, not MediaPipe's own image-normalized landmarks.

    `handedness` ("Left"/"Right"/None) mirrors the X axis for one hand so
    both hands present the same canonical geometry -- left and right hands
    performing the identical gesture are mirror images of each other in
    raw coordinates (most visibly for the palm_in/palm_out orientations,
    which are defined as mirror opposites between hands), and unlike the
    hand-crafted features above (distances/angles, already
    handedness-invariant by construction), raw coordinates need this
    correction explicitly or the model sees two different shapes for one
    gesture. Canonicalized to "Right"; Left hands get X negated."""
    size_ref = hand_size_ref(landmarks)
    if size_ref == 0:
        size_ref = 1.0
    wrist = landmarks[WRIST]
    x_sign = -1.0 if handedness == "Left" else 1.0
    out = []
    for lm in landmarks:
        out.append(x_sign * (lm["x"] - wrist["x"]) / size_ref)
        out.append((lm["y"] - wrist["y"]) / size_ref)
        out.append((lm["z"] - wrist["z"]) / size_ref)
    return out
