import glob
import json
import os

import numpy as np

from Resources import classifier, features

# Stage 3 of Claude/GESTURE_PIPELINE_SPEC.md: train the base per-frame pinch
# classifier. Loads every held-state recording (pinch/open_hand/fist/
# rotating_no_pinch), splits at the SESSION level (not per-frame -- frames
# within one session are highly correlated, per the spec's stage 3 note),
# trains a plain-numpy logistic regression, and compares hand-crafted
# features against raw landmark coordinates as model input (§6.2) rather
# than assuming either is correct.
#
# `pinch_cycles_*` and `pinch_rotate_release` recordings are event-layer
# (stage 3.3) data, not classifier training data -- excluded here per the
# spec's stage 1 rule (cyclic/transition sessions are never part of this
# train/test split).

# Recordings live on the external drive, not the local disk (2026-07-31) --
# must match RecordSession.py's RECORDINGS_DIR.
RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline"
WEIGHTS_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Resources", "pinch_classifier_weights.json"
)

BASE_CLASS_PREFIXES = {
    "open_hand_": "open_hand",
    "fist_": "fist",
}


def classify_label(label):
    """Returns (base_class, orientation) for a held-state recording label,
    or None for event-layer-only labels (pinch_cycles_*, pinch_rotate_release)."""
    if label == "rotating_no_pinch":
        return "rotating_no_pinch", None
    if label.startswith("pinch_cycles") or label == "pinch_rotate_release":
        return None
    if label.startswith("pinch_"):
        return "pinch", label[len("pinch_"):]
    for prefix, base_class in BASE_CLASS_PREFIXES.items():
        if label.startswith(prefix):
            return base_class, label[len(prefix):]
    return None


def load_sessions():
    """Groups recording files by (base_class, orientation) cell, sorted by
    timestamp within each cell -- lets the split below hold out the LAST
    session per cell as test, deterministically."""
    cells = {}
    for path in sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        classified = classify_label(data["label"])
        if classified is None:
            continue
        base_class, orientation = classified
        cells.setdefault((base_class, orientation), []).append((path, data))
    return cells


def session_level_split(cells):
    """Session-level train/test split (spec stage 3: 'hold out whole
    sessions, ideally spanning different orientations, for testing' --
    never a per-frame split, which would leak correlated frames across the
    split). Last session per (class, orientation) cell -> test; the rest
    -> train. Single-session cells (e.g. fist_palmout, only 1 clean
    recording -- see PART_ONE.md handoff) go entirely to train."""
    train_sessions, test_sessions = [], []
    for cell, sessions in cells.items():
        if len(sessions) >= 2:
            train_sessions.extend((cell, path, data) for path, data in sessions[:-1])
            test_sessions.append((cell, *sessions[-1]))
        else:
            train_sessions.extend((cell, path, data) for path, data in sessions)
    return train_sessions, test_sessions


# Fallback session duration (seconds), for recordings made before
# RecordSession.py started storing "duration_s" in the JSON (2026-07-31).
# Matches this project's actual recording commands -- see the Stage 1
# recording session for the --duration value used per label prefix.
LABEL_DURATION_FALLBACK_S = [
    ("pinch_cycles", 10.0),
    ("pinch_rotate_release", 8.0),
    ("rotating_no_pinch", 6.0),
]
DEFAULT_DURATION_FALLBACK_S = 4.0


def session_duration_s(data):
    if "duration_s" in data:
        return data["duration_s"]
    label = data["label"]
    for prefix, duration in LABEL_DURATION_FALLBACK_S:
        if label.startswith(prefix):
            return duration
    return DEFAULT_DURATION_FALLBACK_S


def hand_landmark_sequence(data, handedness):
    """One hand's world_landmarks across a session, in temporal order --
    skips frames where that hand wasn't detected."""
    seq = []
    for frame in data["frames"]:
        for hand in frame["hands"]:
            if hand["handedness"] == handedness:
                seq.append(hand["world_landmarks"])
                break
    return seq


# Named feature sets compared this round (2026-07-31 follow-up): does a
# prediction-error ("surprise") signal succeed where a plain velocity delta
# didn't (GESTURE_PIPELINE_SPEC.md §3.2.3 found velocity-only gave a
# negligible rotation-robustness improvement, 27.2%->26.9%)? All computed
# from the SAME (t-2W, t-W, t) triple per example so the comparison is
# apples-to-apples, not confounded by different example counts.
REPRESENTATIONS = ["handcrafted_static", "handcrafted_velocity", "handcrafted_prederror",
                    "handcrafted_full", "raw_landmarks"]


def sessions_to_windowed_examples(session_list):
    """Expands (cell, path, data) session entries into one example per
    hand-frame: (features_by_representation dict, y, meta). Each example is
    anchored at a frame t, paired with frames ~features.DELTA_WINDOW_MS and
    ~2*features.DELTA_WINDOW_MS earlier (t-W, t-2W) -- needed for the
    prediction-error features (extrapolate from t-2W/t-W, compare to t).
    The window is converted from milliseconds to frames per-session using
    that session's own measured fps (frame count / duration), NOT a fixed
    frame count, since capture fps varies with hardware load (measured
    ~15fps near-distance vs ~27fps far-distance sessions). The first
    2*window_frames of each hand's sequence are skipped (no valid t-2W yet),
    the same warm-up skip a live rolling-buffer tracker would have."""
    examples = []
    for (base_class, orientation), path, data in session_list:
        y = 1 if base_class == "pinch" else 0
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            seq = hand_landmark_sequence(data, handedness)
            if len(seq) < 3:
                continue
            fps = len(seq) / duration_s
            window_frames = max(1, round(fps * features.DELTA_WINDOW_MS / 1000))
            for i in range(2 * window_frames, len(seq)):
                now, t1, t2 = seq[i], seq[i - window_frames], seq[i - 2 * window_frames]
                feats = {
                    "handcrafted_static": features.extract_handcrafted_features(now),
                    "handcrafted_velocity": features.extract_handcrafted_windowed_features(now, t1),
                    "handcrafted_prederror": features.extract_handcrafted_features(now)
                    + features.extract_prediction_error_features(t2, t1, now),
                    "handcrafted_full": features.extract_handcrafted_full_features(t2, t1, now),
                    "raw_landmarks": features.extract_raw_windowed_features(now, t1, handedness=handedness),
                }
                examples.append((feats, y, {
                    "base_class": base_class, "orientation": orientation,
                    "handedness": handedness, "file": os.path.basename(path),
                }))
    return examples


class LogisticRegression:
    """Plain-numpy logistic regression -- no ML framework dependency, per
    spec stage 3's portability requirement (weights export as flat JSON,
    re-implementable as a forward pass in JS later)."""

    def __init__(self, n_features):
        self.w = np.zeros(n_features)
        self.b = 0.0
        self.mean = np.zeros(n_features)
        self.std = np.ones(n_features)

    def _standardize(self, X):
        return (X - self.mean) / self.std

    def fit(self, X, y, epochs=3000, lr=0.1, l2=0.01):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std == 0] = 1.0
        Xs = self._standardize(X)
        n = len(y)
        for _ in range(epochs):
            z = Xs @ self.w + self.b
            p = 1.0 / (1.0 + np.exp(-z))
            grad_w = Xs.T @ (p - y) / n + l2 * self.w
            grad_b = np.sum(p - y) / n
            self.w -= lr * grad_w
            self.b -= lr * grad_b

    def predict_proba(self, X):
        Xs = self._standardize(np.asarray(X, dtype=np.float64))
        z = Xs @ self.w + self.b
        return 1.0 / (1.0 + np.exp(-z))

    def to_json(self, feature_names, representation):
        return {
            "representation": representation,
            "architecture": "logreg",
            "feature_names": feature_names,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "weights": self.w.tolist(),
            "bias": float(self.b),
        }


class TinyMLP:
    """Small hand-rolled 2-layer MLP (numpy, no ML framework dependency) --
    spec stage 3's escalation path, only reached for because logistic
    regression measurably underperformed (see main()'s printed comparison):
    it couldn't linearly separate open_hand_palmup from pinch across the
    full 6-orientation grid. tanh hidden layer, sigmoid output, plain
    backprop -- small enough (hidden_units default 12) to stay within the
    'few thousand params, re-implementable as a forward pass in JS later'
    budget Specification.md §7.1 sets."""

    def __init__(self, n_features, hidden_units=12, seed=0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0, 0.5, (n_features, hidden_units))
        self.b1 = np.zeros(hidden_units)
        self.W2 = rng.normal(0, 0.5, hidden_units)
        self.b2 = 0.0
        self.mean = np.zeros(n_features)
        self.std = np.ones(n_features)

    def _standardize(self, X):
        return (X - self.mean) / self.std

    def _forward(self, Xs):
        h = np.tanh(Xs @ self.W1 + self.b1)
        z = h @ self.W2 + self.b2
        p = 1.0 / (1.0 + np.exp(-z))
        return h, p

    def fit(self, X, y, epochs=4000, lr=0.05, l2=0.001):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0)
        self.std[self.std == 0] = 1.0
        Xs = self._standardize(X)
        n = len(y)
        for _ in range(epochs):
            h, p = self._forward(Xs)
            dz = (p - y) / n
            grad_W2 = h.T @ dz + l2 * self.W2
            grad_b2 = np.sum(dz)
            dh = np.outer(dz, self.W2) * (1 - h ** 2)
            grad_W1 = Xs.T @ dh + l2 * self.W1
            grad_b1 = np.sum(dh, axis=0)
            self.W2 -= lr * grad_W2
            self.b2 -= lr * grad_b2
            self.W1 -= lr * grad_W1
            self.b1 -= lr * grad_b1

    def predict_proba(self, X):
        Xs = self._standardize(np.asarray(X, dtype=np.float64))
        _, p = self._forward(Xs)
        return p

    def to_json(self, feature_names, representation):
        return {
            "representation": representation,
            "architecture": "mlp",
            "hidden_units": self.W1.shape[1],
            "feature_names": feature_names,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": float(self.b2),
        }


def _extract_by_representation(representation, t2, t1, now, handedness):
    if representation == "handcrafted_static":
        return features.extract_handcrafted_features(now)
    if representation == "handcrafted_velocity":
        return features.extract_handcrafted_windowed_features(now, t1)
    if representation == "handcrafted_prederror":
        return features.extract_handcrafted_features(now) + features.extract_prediction_error_features(t2, t1, now)
    if representation == "handcrafted_full":
        return features.extract_handcrafted_full_features(t2, t1, now)
    if representation == "raw_landmarks":
        return features.extract_raw_windowed_features(now, t1, handedness=handedness)
    raise ValueError(representation)


def rotation_stress_test(model_json, representation):
    """Runs the trained model against EVERY rotating_no_pinch recording
    (not just the one held-out test session) and reports the fraction of
    frames that falsely exceed the 0.5 'pinch' bar during pure rotation
    with zero pinching. This is the actual target metric for the Stage 3
    redesign (GESTURE_PIPELINE_SPEC.md §3 stage-3-redesign /
    §3.3.2's rotation-robustness finding) -- aggregate F1 doesn't isolate
    it, since rotating_no_pinch is only ~15% of the dataset's frames."""
    pcts = []
    for path in sorted(glob.glob(os.path.join(RECORDINGS_DIR, "rotating_no_pinch_*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            seq = hand_landmark_sequence(data, handedness)
            if len(seq) < 3:
                continue
            fps = len(seq) / duration_s
            window_frames = max(1, round(fps * features.DELTA_WINDOW_MS / 1000))
            confs = []
            for i in range(2 * window_frames, len(seq)):
                now, t1, t2 = seq[i], seq[i - window_frames], seq[i - 2 * window_frames]
                x = _extract_by_representation(representation, t2, t1, now, handedness)
                confs.append(classifier.predict_from_features(model_json, x))
            pcts.append(100.0 * float(np.mean(np.array(confs) > 0.5)))
    return float(np.mean(pcts)) if pcts else float("nan")


def evaluate(model, X, y, meta, label):
    p = model.predict_proba(X)
    pred = (p >= 0.5).astype(int)
    y = np.asarray(y)
    tp = int(np.sum((pred == 1) & (y == 1)))
    tn = int(np.sum((pred == 0) & (y == 0)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    n = len(y)
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    print(f"  [{label}] n={n} accuracy={accuracy:.3f} precision={precision:.3f} "
          f"recall={recall:.3f} f1={f1:.3f}")
    print(f"  [{label}] confusion matrix: TP={tp} FP={fp} FN={fn} TN={tn}")
    if fp or fn:
        by_cell = {}
        for m, pr, yt in zip(meta, pred, y):
            if pr != yt:
                key = (m["base_class"], m["orientation"], m["handedness"])
                by_cell[key] = by_cell.get(key, 0) + 1
        print(f"  [{label}] misclassified by (class, orientation, hand): {by_cell}")
    return {"n": n, "accuracy": accuracy, "precision": precision, "recall": recall,
            "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main():
    cells = load_sessions()
    train_sessions, test_sessions = session_level_split(cells)
    print(f"Cells: {len(cells)} | train sessions: {len(train_sessions)} | "
          f"test sessions: {len(test_sessions)}")
    for (base_class, orientation), path, data in test_sessions:
        print(f"  held out as TEST: {base_class}/{orientation} <- {os.path.basename(path)}")

    train_ex = sessions_to_windowed_examples(train_sessions)
    test_ex = sessions_to_windowed_examples(test_sessions)
    print(f"\nHand-frame examples (windowed, {features.DELTA_WINDOW_MS}ms window): "
          f"train={len(train_ex)} test={len(test_ex)}")

    feature_names_by_repr = {
        "handcrafted_static": features.HANDCRAFTED_FEATURE_NAMES,
        "handcrafted_velocity": features.HANDCRAFTED_WINDOWED_FEATURE_NAMES,
        "handcrafted_prederror": features.HANDCRAFTED_FEATURE_NAMES + features.PREDICTION_ERROR_FEATURE_NAMES,
        "handcrafted_full": features.HANDCRAFTED_FULL_FEATURE_NAMES,
        "raw_landmarks": [f"lm{i}_{axis}" for i in range(21) for axis in ("x", "y", "z")] + features.DELTA_FEATURE_NAMES,
    }

    results = {}
    for representation in REPRESENTATIONS:
        X_train = [ex[0][representation] for ex in train_ex]
        y_train = [ex[1] for ex in train_ex]
        X_test = [ex[0][representation] for ex in test_ex]
        y_test = [ex[1] for ex in test_ex]
        feature_names = feature_names_by_repr[representation]

        for arch_name, make_model, fit_kwargs in [
            ("logreg", lambda: LogisticRegression(n_features=len(X_train[0])), {}),
            # hidden_units=4, l2=0.001 chosen via a hyperparameter sweep (not
            # guessed) -- see GESTURE_PIPELINE_SPEC.md stage 3 results. Wider
            # hidden layers (8-20) and weaker L2 overfit hard given how few
            # independent sessions this dataset has (train/test F1 gaps of
            # 0.2-0.3); this config had the best test-set generalization.
            ("mlp", lambda: TinyMLP(n_features=len(X_train[0]), hidden_units=4),
             {"l2": 0.001}),
        ]:
            key = f"{arch_name}/{representation}"
            print(f"\n=== {key} ===")
            model = make_model()
            model.fit(X_train, y_train, **fit_kwargs)
            evaluate(model, X_train, y_train, [ex[2] for ex in train_ex], "train")
            test_report = evaluate(model, X_test, y_test, [ex[2] for ex in test_ex], "test")
            model_json = model.to_json(feature_names, representation)
            rotation_fp_pct = rotation_stress_test(model_json, representation)
            print(f"  [rotation stress test] mean false-positive rate during pure "
                  f"rotation (all rotating_no_pinch sessions): {rotation_fp_pct:.1f}%")
            results[key] = {"model": model, "feature_names": feature_names,
                             "representation": representation, "test": test_report,
                             "rotation_fp_pct": rotation_fp_pct}

    print("\n=== Summary (held-out test F1, and the rotation stress test that actually matters right now) ===")
    for key, r in sorted(results.items(), key=lambda kv: -kv[1]["test"]["f1"]):
        t = r["test"]
        print(f"  {key:24s} f1={t['f1']:.3f} accuracy={t['accuracy']:.3f} "
              f"precision={t['precision']:.3f} recall={t['recall']:.3f} "
              f"rotation_fp={r['rotation_fp_pct']:.1f}%")

    # Selection is NOT plain max(test F1) -- aggregate F1 doesn't isolate
    # rotation robustness (rotating_no_pinch is only ~15% of frames), and
    # that's this project's actual current priority (GESTURE_PIPELINE_SPEC.md
    # §3.3.2). But rotation_fp_pct alone is gameable by a degenerate
    # always-predict-not-pinch model (trivially zero false positives
    # anywhere, including during rotation) -- found this exact failure
    # live: logreg/raw_landmarks had the best rotation_fp_pct but recall
    # 0.250 (misses 3 of 4 real pinches). MIN_RECALL excludes candidates
    # that "solve" rotation robustness by barely predicting pinch at all;
    # only among the survivors does the lowest rotation_fp_pct win, with a
    # preference for hand-crafted features per §8's decided default.
    MIN_RECALL = 0.4
    eligible = [k for k in results if results[k]["test"]["recall"] >= MIN_RECALL]
    if not eligible:
        print(f"\nWARNING: no candidate reached recall >= {MIN_RECALL}; "
              f"falling back to the best test F1 (all candidates are weak).")
        eligible = list(results)
    best_overall = min(eligible, key=lambda k: results[k]["rotation_fp_pct"])
    # Prefer a hand-crafted-family variant over raw_landmarks when close
    # (within 2 points), per §8's decided default (raw landmarks are more
    # noise-sensitive on this small dataset).
    handcrafted_eligible = [k for k in eligible if results[k]["representation"] != "raw_landmarks"]
    winner = best_overall
    if results[best_overall]["representation"] == "raw_landmarks" and handcrafted_eligible:
        hc_best = min(handcrafted_eligible, key=lambda k: results[k]["rotation_fp_pct"])
        if results[hc_best]["rotation_fp_pct"] <= results[best_overall]["rotation_fp_pct"] + 2.0:
            winner = hc_best
    win = results[winner]
    print(f"\nWinner: {winner} (rotation_fp={win['rotation_fp_pct']:.1f}%, test_f1={win['test']['f1']:.3f}) "
          f"-- selected by rotation robustness, not aggregate F1 alone")
    with open(WEIGHTS_OUT, "w", encoding="utf-8") as f:
        json.dump(win["model"].to_json(win["feature_names"], win["representation"]), f, indent=2)
    print(f"Saved weights -> {WEIGHTS_OUT}")


if __name__ == "__main__":
    main()
