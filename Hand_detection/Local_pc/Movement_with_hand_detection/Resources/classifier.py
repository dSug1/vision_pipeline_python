import json

import numpy as np

from Resources import features

# Loads the trained pinch base classifier (Claude/GESTURE_PIPELINE_SPEC.md
# stage 3, weights from train_pinch_classifier.py) and runs its forward
# pass. Kept separate from features.py (pure feature extraction) and from
# train_pinch_classifier.py (training only) so the event layer (stage 3.3)
# and the live debug tool (stage 4) can both load a trained model without
# pulling in numpy-heavy training code.


def load(weights_path):
    with open(weights_path, encoding="utf-8") as f:
        return json.load(f)


def _forward(model, x):
    x = np.asarray(x, dtype=np.float64)
    mean = np.asarray(model["mean"])
    std = np.asarray(model["std"])
    xs = (x - mean) / std
    if model["architecture"] == "mlp":
        h = np.tanh(xs @ np.asarray(model["W1"]) + np.asarray(model["b1"]))
        z = h @ np.asarray(model["W2"]) + model["b2"]
    else:
        z = xs @ np.asarray(model["weights"]) + model["bias"]
    return 1.0 / (1.0 + np.exp(-z))


def predict_from_features(model, feature_vector):
    return float(_forward(model, feature_vector))


def predict_from_landmarks(model, landmarks, handedness=None):
    """landmarks: world_landmarks, this module's {"x","y","z"} dict shape
    (features.to_dict_landmarks() first if converting from a live
    MediaPipe result)."""
    if model["representation"] == "handcrafted":
        x = features.extract_handcrafted_features(landmarks)
    else:
        x = features.extract_raw_features(landmarks, handedness=handedness)
    return predict_from_features(model, x)
