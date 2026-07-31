import os
import re

from Resources import classifier
from train_pinch_classifier import (
    LogisticRegression, TinyMLP, evaluate, load_sessions, rotation_stress_test,
    session_level_split, sessions_to_windowed_examples,
)

# Learning-curve ablation (2026-07-31, GESTURE_PIPELINE_SPEC.md §3.2.8):
# does adding a full new distance-set of recordings (matching the near/far
# protocol) keep improving the classifier, or are we hitting diminishing
# returns? Answered by training on 1 set (near), 1+2 sets (near+far), and
# 1+2+3 sets (near+far+new), all evaluated against the SAME fixed held-out
# test split -- a genuine learning curve (fixed test set, growing train
# set), not three separate before/after snapshots with their own splits.
#
# rotating_no_pinch is NOT gated by "set" here -- it's a separate axis
# (negative-class coverage growth, already tracked independently via §9's
# data loop) and is deliberately held CONSTANT (the full current pool,
# minus whichever session the global split holds out as test) across all
# three training pools, so this ablation isolates ONE variable: does
# held-state (pinch/open_hand/fist) distance diversity help, independent of
# rotation-negative-class growth.
#
# Distance-set membership isn't recorded in any label or JSON field -- it's
# only inferable from recording timestamp (near = 2026-07-30, far =
# 2026-07-31 07:14-07:27, new = 2026-07-31 10:15+), confirmed by manually
# inspecting the corpus's timestamp clusters before writing this script.

TS_RE = re.compile(r"_(\d{8})_(\d{6})\.json$")


def session_set(path):
    """Returns 1/2/3 for a held-state (pinch/open_hand/fist) recording
    based on its capture timestamp, or None if it doesn't belong to any of
    the three distance sets (shouldn't happen for non-rotating cells in the
    current corpus, but fail loudly rather than silently mis-bucket)."""
    m = TS_RE.search(os.path.basename(path))
    date, time = m.group(1), m.group(2)
    if date == "20260730":
        return 1
    if date == "20260731" and time < "080000":
        return 2
    if date == "20260731" and time >= "100000":
        return 3
    return None


def main():
    cells = load_sessions()
    train_sessions, test_sessions = session_level_split(cells)
    test_paths = {path for _, path, _ in test_sessions}

    rotating_train = [(cell, path, data) for cell, path, data in train_sessions
                       if cell[0] == "rotating_no_pinch"]
    held_state_train = [(cell, path, data) for cell, path, data in train_sessions
                         if cell[0] != "rotating_no_pinch"]

    unassigned = [path for _, path, _ in held_state_train if session_set(path) is None]
    if unassigned:
        raise RuntimeError(f"{len(unassigned)} held-state training sessions didn't match "
                            f"any of the 3 known distance-set timestamp windows: {unassigned}")

    print(f"Fixed test split: {len(test_sessions)} sessions (unchanged across all 3 runs)")
    print(f"Rotating pool (constant across all 3 runs): {len(rotating_train)} sessions")
    for n in (1, 2, 3):
        count = sum(1 for _, path, _ in held_state_train if session_set(path) <= n)
        print(f"  cumulative through set {n}: {count} held-state sessions")

    test_ex = sessions_to_windowed_examples(test_sessions)
    X_test = [ex[0]["raw_plus_handcrafted"] for ex in test_ex]
    y_test = [ex[1] for ex in test_ex]
    test_meta = [ex[2] for ex in test_ex]

    print(f"\nTest examples (fixed, all runs): {len(test_ex)}")

    results = []
    for n in (1, 2, 3):
        pool = [(cell, path, data) for cell, path, data in held_state_train if session_set(path) <= n] \
            + rotating_train
        n_sessions = len(pool)
        train_ex = sessions_to_windowed_examples(pool)
        X_train = [ex[0]["raw_plus_handcrafted"] for ex in train_ex]
        y_train = [ex[1] for ex in train_ex]

        print(f"\n=== Sets 1..{n} ({n_sessions} sessions, {len(train_ex)} train examples) ===")
        model = TinyMLP(n_features=len(X_train[0]), hidden_units=4)
        model.fit(X_train, y_train, l2=0.001)
        evaluate(model, X_train, y_train, [ex[2] for ex in train_ex], "train")
        test_report = evaluate(model, X_test, y_test, test_meta, "test (fixed)")
        model_json = model.to_json(None, "raw_plus_handcrafted")
        rotation_fp = rotation_stress_test(model_json, "raw_plus_handcrafted")
        print(f"  [rotation stress test] {rotation_fp:.1f}% false-positive during pure rotation")
        results.append({"sets": n, "sessions": n_sessions, "train_examples": len(train_ex),
                         "f1": test_report["f1"], "recall": test_report["recall"],
                         "precision": test_report["precision"], "rotation_fp": rotation_fp})

    print("\n=== Learning curve: sets included -> metrics (all on the SAME fixed test split) ===")
    print(f"  {'sets':6s} {'sessions':8s} {'train_ex':9s} {'F1':6s} {'recall':7s} {'precision':10s} {'rotation_fp':11s}")
    for r in results:
        print(f"  {r['sets']:<6d} {r['sessions']:<8d} {r['train_examples']:<9d} "
              f"{r['f1']:<6.3f} {r['recall']:<7.3f} {r['precision']:<10.3f} {r['rotation_fp']:<11.1f}")

    print("\nDeltas between successive rounds:")
    for a, b in zip(results, results[1:]):
        print(f"  sets {a['sets']}->{b['sets']}: F1 {a['f1']:+.3f}->{b['f1']:+.3f} "
              f"(delta {b['f1']-a['f1']:+.3f}), recall delta {b['recall']-a['recall']:+.3f}, "
              f"rotation_fp delta {b['rotation_fp']-a['rotation_fp']:+.1f}")


if __name__ == "__main__":
    main()
