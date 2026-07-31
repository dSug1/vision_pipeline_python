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

# Windowed/derivative features (Stage 3 redesign, 2026-07-31): static
# per-frame classification of pinch is fundamentally ambiguous against
# incidental rotation-induced poses -- confirmed both by this project's own
# measured evidence (base classifier hit 0.9 confidence during pure
# rotation, GESTURE_PIPELINE_SPEC.md §3.3.2) and by gesture-recognition
# literature (clockwise/counterclockwise circular motion shares
# intermediate static poses; only temporal order disambiguates) and
# biological-motion-perception literature (humans use motion cues, not
# static snapshots, for exactly this kind of intention judgment). These 2
# features give the classifier that temporal signal directly, instead of
# only a per-frame snapshot. Window = 300ms, chosen from
# analyze_transition_window.py's measured onset/offset transition-duration
# distribution (median 667-967ms depending on distance, p25 220-440ms) --
# short enough to trigger before a slow transition fully completes, long
# enough to carry real signal above frame-to-frame noise.
DELTA_FEATURE_NAMES = ["delta_pinch_ratio", "delta_curl_worst_deg"]
HANDCRAFTED_WINDOWED_FEATURE_NAMES = HANDCRAFTED_FEATURE_NAMES + DELTA_FEATURE_NAMES
DELTA_WINDOW_MS = 300


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


def curl_worst_deg(landmarks):
    return max(middle_curl_deg(landmarks), ring_curl_deg(landmarks), pinky_curl_deg(landmarks))


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


def extract_delta_features(current_landmarks, past_landmarks):
    """2 windowed/derivative features -- how much pinch_ratio and
    curl_worst changed between two landmark snapshots (typically
    ~DELTA_WINDOW_MS apart). Pure function over two landmark snapshots, not
    three -- the caller (training pipeline or a live rolling buffer) owns
    picking which past frame to compare against and how many real
    milliseconds apart it is; this function doesn't need to know."""
    return [
        pinch_ratio(current_landmarks) - pinch_ratio(past_landmarks),
        curl_worst_deg(current_landmarks) - curl_worst_deg(past_landmarks),
    ]


def extract_handcrafted_windowed_features(current_landmarks, past_landmarks):
    """7 hand-crafted features + 2 delta features -> 9 values, in
    HANDCRAFTED_WINDOWED_FEATURE_NAMES order."""
    return extract_handcrafted_features(current_landmarks) + extract_delta_features(
        current_landmarks, past_landmarks
    )


def extract_raw_windowed_features(current_landmarks, past_landmarks, handedness=None):
    """63 raw landmark values + 2 delta features -> 65 values."""
    return extract_raw_features(current_landmarks, handedness) + extract_delta_features(
        current_landmarks, past_landmarks
    )


PREDICTION_ERROR_FEATURE_NAMES = ["prederr_pinch_ratio", "prederr_curl_worst_deg"]
HANDCRAFTED_FULL_FEATURE_NAMES = (
    HANDCRAFTED_FEATURE_NAMES + DELTA_FEATURE_NAMES + PREDICTION_ERROR_FEATURE_NAMES
)


def extract_prediction_error_features(landmarks_t2, landmarks_t1, landmarks_now):
    """2 prediction-error ("surprise") features -- Stage 3 redesign,
    2026-07-31 follow-up after the plain velocity-delta features (above)
    failed to fix the rotation/pinch confusion (GESTURE_PIPELINE_SPEC.md
    §3.2.3). Different mechanism, not just a bigger window: a simple
    constant-velocity extrapolation from two past snapshots (t2, t1,
    equally spaced) predicts where pinch_ratio/curl_worst "should" be now
    if the hand keeps doing whatever it was already doing; the signed
    residual (actual - predicted) is the feature. Directly modeled on
    forward-model/efference-copy accounts of biological motion perception
    and predictive-coding anomaly detection (PredNet and related video
    next-frame-prediction work): smooth, continuous motion (e.g. ambient
    rotation) is well predicted by its own recent trajectory -> low
    residual; a genuine voluntary action (a pinch closing) breaks from
    whatever trajectory preceded it -> high residual, precisely at onset.
    This is a second-order ("did the *trend* change") signal, distinct
    from extract_delta_features' first-order ("did the *value* change")
    signal -- smooth rotation can still have nonzero velocity, but should
    have close to zero prediction error since it's the same velocity
    continuing."""
    predicted_ratio = 2 * pinch_ratio(landmarks_t1) - pinch_ratio(landmarks_t2)
    predicted_curl = 2 * curl_worst_deg(landmarks_t1) - curl_worst_deg(landmarks_t2)
    return [
        pinch_ratio(landmarks_now) - predicted_ratio,
        curl_worst_deg(landmarks_now) - predicted_curl,
    ]


def extract_handcrafted_full_features(landmarks_t2, landmarks_t1, landmarks_now):
    """7 static + 2 velocity-delta + 2 prediction-error -> 11 values, in
    HANDCRAFTED_FULL_FEATURE_NAMES order."""
    return (
        extract_handcrafted_features(landmarks_now)
        + extract_delta_features(landmarks_now, landmarks_t1)
        + extract_prediction_error_features(landmarks_t2, landmarks_t1, landmarks_now)
    )


# Fused representation (2026-07-31, GESTURE_PIPELINE_SPEC.md §3.2.7):
# neither pure raw landmarks nor pure 7-dim hand-crafted features have won
# on every axis this project cares about -- raw landmarks keep recall up as
# the rotating_no_pinch corpus grows (§3.2.6 found the 7-dim hand-crafted
# representation's recall collapses, static or windowed alike, while raw
# landmarks did not), but hand-crafted features generalize better across
# camera distance (§3.2.1's near/far re-run). Concatenating both into one
# input vector -- rather than picking one -- has direct literature
# precedent in pose/sign-language recognition: models built from "a flat
# vector representation of pose concatenated with the 2D angle and length
# of every limb" are a documented, standard pattern, not a novel idea. This
# is a model *input representation* choice, explicitly not covered by §2's
# "no heuristic pile-up" rule (§6.2 already carves this out: choosing input
# representation by literature + held-out validation is normal ML
# practice, unlike patching a trained model's output).


def extract_raw_plus_handcrafted_features(landmarks, handedness=None):
    """63 raw landmark values + 7 hand-crafted features -> 70 values.
    Deliberately static (no delta/prediction-error terms) -- isolates the
    spatial-fusion question from the temporal-window question §3.2.3/§3.2.6
    already investigated separately and found inconclusive-to-negative, so
    this experiment doesn't reintroduce that confound."""
    return extract_raw_features(landmarks, handedness) + extract_handcrafted_features(landmarks)


RAW_PLUS_HANDCRAFTED_FEATURE_NAMES = (
    [f"lm{i}_{axis}" for i in range(21) for axis in ("x", "y", "z")] + HANDCRAFTED_FEATURE_NAMES
)


# Finger-articulation features (2026-07-31, GESTURE_PIPELINE_SPEC.md
# §3.3.3): none of this project's features so far explicitly measure
# whether fingers move TOGETHER (rigid whole-hand motion -- rotation) or
# INDEPENDENTLY (one finger articulating relative to the rest -- a genuine
# pinch). Two independent literatures converge on this being the right
# signal: computer-vision rigid-vs-articulated motion segmentation (points
# on a rigid body share one low-dimensional motion pattern; independently
# moving parts deviate from it) and hand biomechanics postural-synergy
# research (finger joints move together during grasping in patterns
# distinguishable from whole-hand/wrist movement via correlation analysis,
# with wrist-hand coordination measurably lower than within-hand
# coordination). The 5 MCP knuckles (already this project's `hand_size_ref`
# anchor) are used as a proxy for the hand's RIGID motion -- they move
# together under any whole-hand translation/rotation, since the palm itself
# doesn't independently deform. Each fingertip's displacement is then
# measured RELATIVE to that rigid reference: near zero if the finger is
# just along for the ride (rotation), large if it's independently
# articulating (a real pinch/curl) -- directly operationalizing "common
# fate" instead of assuming it.
MCP_JOINTS = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
FINGERTIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_ARTICULATION_FEATURE_NAMES = ["thumb_index_articulation", "other_fingers_articulation"]


def extract_finger_articulation_features(landmarks_past, landmarks_now):
    """2 features: how much the thumb+index tips move relative to the
    hand's rigid (MCP-based) motion, and how much the other three fingers
    do. A genuine pinch onset should show HIGH thumb_index_articulation
    (independent closing motion) and LOW other_fingers_articulation
    (those fingers stay relatively still, just riding along with whatever
    rigid motion exists). Pure rotation should show both LOW -- every
    fingertip's motion is explained by the same rigid reference, since nothing
    is independently articulating."""
    size_ref = hand_size_ref(landmarks_now)
    if size_ref == 0:
        size_ref = 1.0
    mcp_displacements = [_vec(landmarks_past[j], landmarks_now[j]) for j in MCP_JOINTS]
    rigid = tuple(sum(d[axis] for d in mcp_displacements) / len(mcp_displacements) for axis in range(3))
    residuals = []
    for tip in FINGERTIPS:
        d = _vec(landmarks_past[tip], landmarks_now[tip])
        relative_to_rigid = (d[0] - rigid[0], d[1] - rigid[1], d[2] - rigid[2])
        residuals.append(_norm(relative_to_rigid) / size_ref)
    thumb_index_articulation = (residuals[0] + residuals[1]) / 2
    other_fingers_articulation = (residuals[2] + residuals[3] + residuals[4]) / 3
    return [thumb_index_articulation, other_fingers_articulation]


RAW_PLUS_HANDCRAFTED_PLUS_ARTICULATION_FEATURE_NAMES = (
    RAW_PLUS_HANDCRAFTED_FEATURE_NAMES + FINGER_ARTICULATION_FEATURE_NAMES
)


def extract_raw_plus_handcrafted_plus_articulation_features(landmarks_past, landmarks_now, handedness=None):
    """70-dim raw_plus_handcrafted (static, at `now`) + 2 finger-
    articulation features (need both `now` and `past`) -> 72 values."""
    return (
        extract_raw_plus_handcrafted_features(landmarks_now, handedness)
        + extract_finger_articulation_features(landmarks_past, landmarks_now)
    )
