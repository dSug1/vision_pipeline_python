import glob
import json
import os

import numpy as np

from Resources import classifier, features
from train_pinch_classifier import (
    RECORDINGS_DIR, LogisticRegression, TinyMLP, evaluate,
    hand_landmark_sequence, load_sessions, session_duration_s,
    session_level_split,
)

# GESTURE_PIPELINE_SPEC.md §3.2.4 built prediction-error features
# (features.extract_prediction_error_features) at a single fixed window --
# 300ms, features.DELTA_WINDOW_MS -- but that number came from
# analyze_transition_window.py's measurement of real onset/offset
# TRANSITION timing (median 667-967ms, p25 220-440ms). That's a different
# question from "which window makes the prediction-error features best
# separate genuine pinch from rotation-induced false positives" -- 300ms
# was never actually validated against classifier performance, just assumed
# to transfer. This sweeps window size directly against the same two
# metrics train_pinch_classifier.py already selects on (held-out test
# recall/F1, and the rotation stress test), across the window-dependent
# representations, so the isolation is measured, not guessed.
#
# Re-run 2026-07-31 against the pencil-grip corpus (GESTURE_PIPELINE_SPEC.md
# §12) -- extended to include raw_plus_handcrafted_plus_articulation, the
# CURRENT winning representation (§3.2.10/§3.3.3), which the original sweep
# (built against the old corpus, before the articulation feature existed)
# never covered. That representation's articulation feature is exactly as
# window-dependent as the older handcrafted variants (extract_finger_
# articulation_features(past, now) needs the same window_frames), so
# DELTA_WINDOW_MS is a live assumption for the actual shipped model, not
# just a historical artifact for superseded representations.
#
# Not run automatically as part of every retrain (unlike
# train_pinch_classifier.py) -- this is a one-off tuning pass, same
# category as analyze_transition_window.py.

WINDOW_SIZES_MS = [100, 150, 200, 300, 450, 600, 900, 1200]
WINDOW_DEPENDENT_REPRESENTATIONS = [
    "handcrafted_velocity", "handcrafted_prederror", "handcrafted_full",
    "raw_plus_handcrafted_plus_articulation",
]
MIN_RECALL = 0.4

FEATURE_NAMES = {
    "handcrafted_velocity": features.HANDCRAFTED_WINDOWED_FEATURE_NAMES,
    "handcrafted_prederror": features.HANDCRAFTED_FEATURE_NAMES + features.PREDICTION_ERROR_FEATURE_NAMES,
    "handcrafted_full": features.HANDCRAFTED_FULL_FEATURE_NAMES,
    "raw_plus_handcrafted_plus_articulation": features.RAW_PLUS_HANDCRAFTED_PLUS_ARTICULATION_FEATURE_NAMES,
}

# hidden_units per representation for the "mlp" architecture below -- the
# handcrafted family stays at 4 (unchanged, low-dimensional input, never
# implicated in the §3.2.9 stale-hyperparameter finding). 72-dim
# raw_plus_handcrafted_plus_articulation uses 24, matching the value
# train_pinch_classifier.py's own sweep found correct for that input size --
# using the old default of 4 here would confound the window-size comparison
# with a known-undersized model for this representation.
MLP_HIDDEN_UNITS = {
    "handcrafted_velocity": 4, "handcrafted_prederror": 4, "handcrafted_full": 4,
    "raw_plus_handcrafted_plus_articulation": 24,
}


def _features_for(representation, t2, t1, now, handedness=None):
    if representation == "handcrafted_velocity":
        return features.extract_handcrafted_windowed_features(now, t1)
    if representation == "handcrafted_prederror":
        return features.extract_handcrafted_features(now) + features.extract_prediction_error_features(t2, t1, now)
    if representation == "handcrafted_full":
        return features.extract_handcrafted_full_features(t2, t1, now)
    if representation == "raw_plus_handcrafted_plus_articulation":
        return features.extract_raw_plus_handcrafted_plus_articulation_features(t1, now, handedness=handedness)
    raise ValueError(representation)


def build_examples(session_list, window_ms):
    """Same anchoring scheme as train_pinch_classifier.sessions_to_windowed_examples
    (t-2W, t-W, now; per-session fps-derived window_frames), but parameterized
    by window_ms instead of the fixed features.DELTA_WINDOW_MS."""
    examples = []
    for (base_class, orientation), path, data in session_list:
        y = 1 if base_class == "pinch" else 0
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            seq = hand_landmark_sequence(data, handedness)
            if len(seq) < 3:
                continue
            fps = len(seq) / duration_s
            window_frames = max(1, round(fps * window_ms / 1000))
            for i in range(2 * window_frames, len(seq)):
                now, t1, t2 = seq[i], seq[i - window_frames], seq[i - 2 * window_frames]
                feats = {rep: _features_for(rep, t2, t1, now, handedness) for rep in WINDOW_DEPENDENT_REPRESENTATIONS}
                examples.append((feats, y, {
                    "base_class": base_class, "orientation": orientation,
                    "handedness": handedness, "file": os.path.basename(path),
                }))
    return examples


def rotation_stress_test_window(model_json, representation, window_ms):
    pcts = []
    for path in sorted(glob.glob(os.path.join(RECORDINGS_DIR, "rotating_no_pinch_*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("protocol") != "held_state":
            raise ValueError(f"{path}: expected protocol='held_state', got {data.get('protocol')!r}")
        duration_s = session_duration_s(data)
        for handedness in ("Left", "Right"):
            seq = hand_landmark_sequence(data, handedness)
            if len(seq) < 3:
                continue
            fps = len(seq) / duration_s
            window_frames = max(1, round(fps * window_ms / 1000))
            confs = []
            for i in range(2 * window_frames, len(seq)):
                now, t1, t2 = seq[i], seq[i - window_frames], seq[i - 2 * window_frames]
                x = _features_for(representation, t2, t1, now, handedness)
                confs.append(classifier.predict_from_features(model_json, x))
            pcts.append(100.0 * float(np.mean(np.array(confs) > 0.5)))
    return float(np.mean(pcts)) if pcts else float("nan")


def main():
    cells = load_sessions()
    train_sessions, test_sessions = session_level_split(cells)

    results = []
    for window_ms in WINDOW_SIZES_MS:
        train_ex = build_examples(train_sessions, window_ms)
        test_ex = build_examples(test_sessions, window_ms)
        print(f"\n--- window={window_ms}ms: train={len(train_ex)} test={len(test_ex)} examples ---")

        for representation in WINDOW_DEPENDENT_REPRESENTATIONS:
            X_train = [ex[0][representation] for ex in train_ex]
            y_train = [ex[1] for ex in train_ex]
            X_test = [ex[0][representation] for ex in test_ex]
            y_test = [ex[1] for ex in test_ex]
            feature_names = FEATURE_NAMES[representation]

            hidden_units = MLP_HIDDEN_UNITS[representation]
            for arch_name, make_model, fit_kwargs in [
                ("logreg", lambda: LogisticRegression(n_features=len(X_train[0])), {}),
                ("mlp", lambda hu=hidden_units: TinyMLP(n_features=len(X_train[0]), hidden_units=hu), {"l2": 0.001}),
            ]:
                model = make_model()
                model.fit(X_train, y_train, **fit_kwargs)
                test_report = evaluate(
                    model, X_test, y_test, [ex[2] for ex in test_ex],
                    f"{window_ms}ms/{arch_name}/{representation}/test",
                )
                model_json = model.to_json(feature_names, representation)
                rotation_fp = rotation_stress_test_window(model_json, representation, window_ms)
                print(f"  [rotation stress test] {window_ms}ms/{arch_name}/{representation}: "
                      f"{rotation_fp:.1f}% false-positive during pure rotation")
                results.append({
                    "window_ms": window_ms, "arch": arch_name, "representation": representation,
                    "f1": test_report["f1"], "recall": test_report["recall"],
                    "precision": test_report["precision"], "rotation_fp": rotation_fp,
                })

    print("\n=== Window sweep summary, ALL results by rotation_fp ===")
    for r in sorted(results, key=lambda r: r["rotation_fp"]):
        eligible = "eligible" if r["recall"] >= MIN_RECALL else "recall<0.4"
        print(f"  window={r['window_ms']:4d}ms {r['arch']:7s} {r['representation']:20s} "
              f"f1={r['f1']:.3f} recall={r['recall']:.3f} precision={r['precision']:.3f} "
              f"rotation_fp={r['rotation_fp']:5.1f}%  [{eligible}]")

    eligible_results = [r for r in results if r["recall"] >= MIN_RECALL]
    print(f"\n=== Best per representation (recall >= {MIN_RECALL}, else best test F1 among all) ===")
    for representation in WINDOW_DEPENDENT_REPRESENTATIONS:
        candidates = [r for r in eligible_results if r["representation"] == representation]
        if not candidates:
            candidates = [r for r in results if r["representation"] == representation]
            print(f"  {representation}: NO candidate reached recall >= {MIN_RECALL}; showing best F1 instead")
        best = min(candidates, key=lambda r: r["rotation_fp"])
        print(f"  {representation:20s} best window={best['window_ms']}ms ({best['arch']}) "
              f"rotation_fp={best['rotation_fp']:.1f}% f1={best['f1']:.3f} recall={best['recall']:.3f}")


if __name__ == "__main__":
    main()
