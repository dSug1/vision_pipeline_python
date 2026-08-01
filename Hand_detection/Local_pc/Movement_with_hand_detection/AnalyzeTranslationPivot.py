import glob
import json
import math
import os

# For the rotation-coupling check (added 2026-08-01, same conversation,
# direct request after the first analysis pass): reuses LiveSnapDebug.py's
# own quaternion machinery (already live-verified for rotation, §13.7)
# rather than re-deriving it -- import-safe, no camera/window opened on
# import (confirmed by RecordRotationDebug.py's own precedent).
import LiveSnapDebug as debug_tool

# Offline verification for the §14.1 distance-weighted-live-landmark
# translation mechanism (GESTURE_PIPELINE_SPEC.md §14.1,
# HANDOFF_SNAP_ROTATE_RELEASE.md §2.1), built 2026-08-01 per this
# project's standing discipline: verify against recorded data BEFORE
# wiring a new mechanism into LiveSnapDebug.py/HandsTriggeredActions.py,
# same as every prior gesture in this pipeline.
#
# Loads recordings made by RecordTranslationPivotDebug.py, finds each real
# grab event (a cube's `owner` transitioning from None to a handedness --
# produced by LiveSnapDebug.py's actual, already-live-verified snap logic,
# not simulated), and for each resulting hold interval:
#   1. Freezes distance-weighted candidate-landmark weights at the grab
#      frame, using the REAL recorded cube center at that frame as the
#      object's grab-time position (ground truth -- see
#      RecordTranslationPivotDebug.py's _cubes_record docstring for why
#      this is valid ground truth under today's zero-offset design).
#   2. Replays the new mechanism frame-by-frame using the SAME frozen
#      weights against each frame's LIVE candidate-landmark positions.
#   3. Checks: exact no-pop at the grab frame, frame-to-frame jitter of
#      the new mechanism's output, and weight-concentration (does a small
#      object's weights collapse onto one or two noisy fingertip
#      landmarks, the risk flagged in §14.1).
#
# Does NOT modify or wire anything into LiveSnapDebug.py -- verification
# only, per the project's build-then-verify-then-ship discipline.

# Matches RecordTranslationPivotDebug.py's save location (external-drive
# corpus dir, direct request 2026-08-01).
RECORDINGS_DIR = r"E:\Python\Recordings for vision_pipeline\Position_during_rotation"

# Candidate phalange-adjacent landmarks (§14.1's "Concrete redesign,
# chosen mechanism" step 1) -- standard MediaPipe Hand Landmarker indices.
# 5 fingertips + the same 4 non-thumb MCPs today's `_hand_position`
# already uses. Extend with PIP/DIP only if this pass shows the fingertip
# + MCP set is too coarse -- not assumed necessary up front.
WRIST = 0
THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP = 4, 8, 12, 16, 20
INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 5, 9, 13, 17
CANDIDATE_LANDMARKS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP,
                        INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
# Same 5 points as today's `_hand_position` -- used below as the "palm
# centroid" reference for the yaw/foreshortening diagnostic.
PALM_LANDMARKS = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
FINGERTIP_LANDMARKS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]

# Floor under the inverse-distance denominator -- prevents divide-by-zero
# and caps how sharply weight can concentrate onto a single landmark.
# Starting value, to be tuned against what this pass actually measures
# (§14.1's "known risk to verify, not assume"), not picked blindly.
EPSILON_PX = 5.0

TRACKED_HANDS = ("Left", "Right")


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _centroid(landmarks, indices):
    xs = [landmarks[i][0] for i in indices]
    ys = [landmarks[i][1] for i in indices]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _weighted_position(weights, landmarks_now):
    x = sum(w * landmarks_now[i][0] for i, w in weights.items())
    y = sum(w * landmarks_now[i][1] for i, w in weights.items())
    return (x, y)


def _compute_grab_weights(object_pos_at_grab, landmarks_at_grab):
    raw = {i: 1.0 / (_dist(object_pos_at_grab, landmarks_at_grab[i]) + EPSILON_PX) for i in CANDIDATE_LANDMARKS}
    total = sum(raw.values())
    return {i: w / total for i, w in raw.items()}


def _participation_ratio(weights):
    # Effective number of landmarks actually contributing (1 = fully
    # concentrated on one landmark, len(CANDIDATE_LANDMARKS) = perfectly
    # even spread) -- inverse Simpson index, standard concentration metric.
    return 1.0 / sum(w * w for w in weights.values())


def _rotation_angle_deg(q_now, q_prev):
    """Frame-to-frame rotation angle (degrees) between two RAW hand
    orientation quaternions -- standard quaternion-to-angle formula,
    `abs(w)` handles the double-cover sign ambiguity (q and -q represent
    the same rotation). Uses the same `_hand_orientation_quaternion` this
    project already live-verified for rotation (§13.7), not a new
    derivation."""
    delta = debug_tool._quat_multiply(q_now, debug_tool._quat_conjugate(q_prev))
    w = max(-1.0, min(1.0, abs(delta[0])))
    return math.degrees(2 * math.acos(w))


def _pearson_correlation(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 1e-9 or var_y <= 1e-9:
        return None
    return cov / math.sqrt(var_x * var_y)


def _tercile_split(rotation_angles, jitter_deltas):
    """Mean new-mechanism jitter in the lowest-rotation third of frame
    transitions vs. the highest-rotation third -- the direct check for
    "does translation now scale with real rotation instead of being
    erratic": low-rotation frames should show LOW jitter (near-zero
    movement when the hand basically isn't rotating), high-rotation
    frames should show proportionally MORE. Not just a correlation
    coefficient, which can be misleading with outliers."""
    n = len(rotation_angles)
    if n < 6:  # need enough transitions for terciles to mean anything
        return None, None
    order = sorted(range(n), key=lambda i: rotation_angles[i])
    third = n // 3
    low_idx = order[:third]
    high_idx = order[-third:]
    low_mean = sum(jitter_deltas[i] for i in low_idx) / len(low_idx)
    high_mean = sum(jitter_deltas[i] for i in high_idx) / len(high_idx)
    return low_mean, high_mean


def _yaw_palm_bias_diagnostic(new_positions, palm_centroids, fingertip_centroids, knuckle_widths):
    """Checks the specific problem reported live (2026-08-01, after the
    first two analysis passes): "at one point, the center of the cube
    sits inside the palm... when the hand is facing left or right,
    orthogonal to the camera view" -- i.e. under YAW (turning the hand
    sideways to the camera), not pitch/roll (reported OK).

    `knuckle_width` (pixel distance INDEX_MCP<->PINKY_MCP) foreshortens
    specifically under yaw -- the knuckle row turns edge-on to the camera
    -- so a shrinking width-at-grab ratio is used as the yaw/sideways
    indicator (cheap, already-available proxy; doesn't need 3D pose
    classification). `bias_toward_palm` is signed: positive means the
    computed position sits closer to the palm centroid (today's OLD
    anchor) than to the fingertip centroid, negative means the reverse.
    If the reported problem is real, bias_toward_palm should INCREASE
    (swing toward the palm) as the knuckle row foreshortens (ratio drops)
    -- i.e. a NEGATIVE correlation between ratio and bias."""
    if len(new_positions) < 6 or knuckle_widths[0] < 1e-6:
        return None
    baseline_width = knuckle_widths[0]
    ratios = [w / baseline_width for w in knuckle_widths]
    biases = []
    for pos, palm_c, tip_c in zip(new_positions, palm_centroids, fingertip_centroids):
        d_palm = _dist(pos, palm_c)
        d_tip = _dist(pos, tip_c)
        denom = d_palm + d_tip
        biases.append((d_tip - d_palm) / denom if denom > 1e-6 else 0.0)

    corr = _pearson_correlation(ratios, biases)

    n = len(ratios)
    order = sorted(range(n), key=lambda i: ratios[i])  # ascending: most-foreshortened first
    third = n // 3
    if third < 2:
        return {"correlation": corr, "foreshortened_bias": None, "frontal_bias": None}
    foreshortened_idx = order[:third]   # smallest ratio = most sideways/yawed
    frontal_idx = order[-third:]        # largest ratio = most front-facing
    foreshortened_bias = sum(biases[i] for i in foreshortened_idx) / len(foreshortened_idx)
    frontal_bias = sum(biases[i] for i in frontal_idx) / len(frontal_idx)
    return {"correlation": corr, "foreshortened_bias": foreshortened_bias, "frontal_bias": frontal_bias,
            "min_ratio": min(ratios)}


def _find_hold_intervals(frames, handedness):
    """Yields (start_idx, end_idx_exclusive, held_cube) for each contiguous
    span where this hand holds a cube AND is detected AND that cube's
    recorded owner matches -- i.e. a real grab-to-release (or
    grab-to-tracking-loss, or grab-to-recording-end) interval."""
    start_idx = None
    held_cube = None
    for idx, frame in enumerate(frames):
        hand = frame["hands"].get(handedness, {"detected": False})
        current_cube = hand.get("held_cube") if hand.get("detected") else None
        if current_cube != held_cube:
            if held_cube is not None:
                yield (start_idx, idx, held_cube)
            if current_cube is not None:
                start_idx = idx
            held_cube = current_cube
    if held_cube is not None:
        yield (start_idx, len(frames), held_cube)


def _analyze_interval(frames, handedness, start_idx, end_idx, held_cube, source_label):
    grab_frame = frames[start_idx]
    object_pos_at_grab = tuple(grab_frame["cubes"][held_cube]["center"])
    cube_size = grab_frame["cubes"][held_cube]["size"]
    landmarks_at_grab = frames[start_idx]["hands"][handedness]["pixel_landmarks"]

    weights = _compute_grab_weights(object_pos_at_grab, landmarks_at_grab)
    weighted_at_grab = _weighted_position(weights, landmarks_at_grab)
    residual = (object_pos_at_grab[0] - weighted_at_grab[0], object_pos_at_grab[1] - weighted_at_grab[1])
    no_pop_error_px = _dist(
        (weighted_at_grab[0] + residual[0], weighted_at_grab[1] + residual[1]),
        object_pos_at_grab,
    )

    new_positions = []
    old_positions = []
    raw_quats = []
    palm_centroids = []
    fingertip_centroids = []
    knuckle_widths = []
    for idx in range(start_idx, end_idx):
        hand = frames[idx]["hands"].get(handedness)
        if hand is None or not hand.get("detected"):
            break
        landmarks_now = hand["pixel_landmarks"]
        weighted_now = _weighted_position(weights, landmarks_now)
        new_positions.append((weighted_now[0] + residual[0], weighted_now[1] + residual[1]))
        old_positions.append(tuple(frames[idx]["cubes"][held_cube]["center"]))
        raw_quat, _conditioning = debug_tool._hand_orientation_quaternion(hand["world_landmarks"])
        raw_quats.append(raw_quat)
        palm_centroids.append(_centroid(landmarks_now, PALM_LANDMARKS))
        fingertip_centroids.append(_centroid(landmarks_now, FINGERTIP_LANDMARKS))
        knuckle_widths.append(_dist(landmarks_now[INDEX_MCP], landmarks_now[PINKY_MCP]))

    def _jitter_deltas(positions):
        return [_dist(positions[i], positions[i - 1]) for i in range(1, len(positions))]

    new_deltas = _jitter_deltas(new_positions)
    old_deltas = _jitter_deltas(old_positions)
    rotation_deltas = [_rotation_angle_deg(raw_quats[i], raw_quats[i - 1]) for i in range(1, len(raw_quats))]

    def _mean_max(deltas):
        return (sum(deltas) / len(deltas), max(deltas)) if deltas else (0.0, 0.0)

    new_mean_jitter, new_max_jitter = _mean_max(new_deltas)
    old_mean_jitter, old_max_jitter = _mean_max(old_deltas)
    participation = _participation_ratio(weights)

    corr_new = _pearson_correlation(rotation_deltas, new_deltas)
    corr_old = _pearson_correlation(rotation_deltas, old_deltas)
    low_rot_jitter, high_rot_jitter = _tercile_split(rotation_deltas, new_deltas)
    old_low_rot_jitter, old_high_rot_jitter = _tercile_split(rotation_deltas, old_deltas)

    print(
        f"  [{source_label}] hand={handedness} cube={held_cube} (size={cube_size}) "
        f"frames={end_idx - start_idx}"
    )
    print(f"    no-pop error: {no_pop_error_px:.4f}px (should be ~0.0)")
    print(f"    weight participation ratio: {participation:.2f} / {len(CANDIDATE_LANDMARKS)} candidates "
          f"(1.0 = fully concentrated on one landmark)")
    print(f"    new-mechanism jitter: mean={new_mean_jitter:.2f}px max={new_max_jitter:.2f}px")
    print(f"    old (today's) jitter: mean={old_mean_jitter:.2f}px max={old_max_jitter:.2f}px")
    corr_new_str = f"{corr_new:.2f}" if corr_new is not None else "n/a"
    corr_old_str = f"{corr_old:.2f}" if corr_old is not None else "n/a"
    print(f"    jitter-vs-rotation correlation: new={corr_new_str} old={corr_old_str} "
          f"(higher = translation tracks real rotation, not erratic)")
    if low_rot_jitter is not None:
        new_ratio = high_rot_jitter / low_rot_jitter if low_rot_jitter > 1e-6 else float("inf")
        print(f"    new-mechanism jitter by rotation tercile: "
              f"low-rotation frames={low_rot_jitter:.2f}px, high-rotation frames={high_rot_jitter:.2f}px "
              f"(ratio {new_ratio:.2f}x)")
    if old_low_rot_jitter is not None:
        old_ratio = old_high_rot_jitter / old_low_rot_jitter if old_low_rot_jitter > 1e-6 else float("inf")
        print(f"    old (today's) jitter by rotation tercile: "
              f"low-rotation frames={old_low_rot_jitter:.2f}px, high-rotation frames={old_high_rot_jitter:.2f}px "
              f"(ratio {old_ratio:.2f}x)")

    yaw_diag = _yaw_palm_bias_diagnostic(new_positions, palm_centroids, fingertip_centroids, knuckle_widths)
    if yaw_diag is not None:
        corr_str = f"{yaw_diag['correlation']:.2f}" if yaw_diag["correlation"] is not None else "n/a"
        print(f"    yaw/foreshortening check: knuckle-width min ratio={yaw_diag.get('min_ratio', float('nan')):.2f} "
              f"(1.0=frontal, lower=more sideways), ratio-vs-palm-bias correlation={corr_str} "
              f"(negative = swings toward palm as hand turns sideways, matches the reported problem)")
        if yaw_diag["foreshortened_bias"] is not None:
            print(f"    palm-bias when most sideways={yaw_diag['foreshortened_bias']:+.2f} "
                  f"vs. most frontal={yaw_diag['frontal_bias']:+.2f} "
                  f"(-1=fully at fingertips, +1=fully at palm, 0=balanced)")

    return {
        "cube": held_cube,
        "cube_size": cube_size,
        "no_pop_error_px": no_pop_error_px,
        "participation_ratio": participation,
        "new_mean_jitter": new_mean_jitter,
        "new_max_jitter": new_max_jitter,
        "old_mean_jitter": old_mean_jitter,
        "old_max_jitter": old_max_jitter,
        "corr_new": corr_new,
        "corr_old": corr_old,
        "low_rot_jitter": low_rot_jitter,
        "high_rot_jitter": high_rot_jitter,
        "old_low_rot_jitter": old_low_rot_jitter,
        "old_high_rot_jitter": old_high_rot_jitter,
        "yaw_diag": yaw_diag,
        "frames": end_idx - start_idx,
    }


def main() -> None:
    paths = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.json")))
    if not paths:
        print(f"[AnalyzeTranslationPivot] No recordings found in {RECORDINGS_DIR}. "
              f"Run record_translation_pivot_debug.bat first.")
        return

    all_results = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        frames = data["frames"]
        label = data.get("label", os.path.basename(path))
        print(f"\n{os.path.basename(path)} (label={label}, {len(frames)} frames):")

        found_any = False
        for handedness in TRACKED_HANDS:
            for start_idx, end_idx, held_cube in _find_hold_intervals(frames, handedness):
                if end_idx - start_idx < 3:
                    continue  # too short to say anything meaningful about jitter
                found_any = True
                result = _analyze_interval(frames, handedness, start_idx, end_idx, held_cube, label)
                all_results.append(result)
        if not found_any:
            print("  (no hold interval of >= 3 frames found in this recording)")

    if not all_results:
        print("\n[AnalyzeTranslationPivot] No analyzable hold intervals across all recordings.")
        return

    print("\n=== Summary, grouped by cube size ===")
    for size_label in sorted({r["cube"] for r in all_results}):
        group = [r for r in all_results if r["cube"] == size_label]
        mean_participation = sum(r["participation_ratio"] for r in group) / len(group)
        mean_new_jitter = sum(r["new_mean_jitter"] for r in group) / len(group)
        max_no_pop = max(r["no_pop_error_px"] for r in group)
        print(
            f"  {size_label}: {len(group)} interval(s), "
            f"mean participation ratio={mean_participation:.2f}, "
            f"mean new-mechanism jitter={mean_new_jitter:.2f}px, "
            f"worst no-pop error={max_no_pop:.4f}px"
        )

    print("\n=== Rotation-coupling check (does translation now scale with real rotation?) ===")
    corr_new_vals = [r["corr_new"] for r in all_results if r["corr_new"] is not None]
    corr_old_vals = [r["corr_old"] for r in all_results if r["corr_old"] is not None]
    low_vals = [r["low_rot_jitter"] for r in all_results if r["low_rot_jitter"] is not None]
    high_vals = [r["high_rot_jitter"] for r in all_results if r["high_rot_jitter"] is not None]
    if corr_new_vals:
        print(f"  mean jitter-vs-rotation correlation: new={sum(corr_new_vals)/len(corr_new_vals):.2f} "
              f"old={sum(corr_old_vals)/len(corr_old_vals) if corr_old_vals else float('nan'):.2f} "
              f"(across {len(corr_new_vals)} intervals)")
    old_low_vals = [r["old_low_rot_jitter"] for r in all_results if r["old_low_rot_jitter"] is not None]
    old_high_vals = [r["old_high_rot_jitter"] for r in all_results if r["old_high_rot_jitter"] is not None]
    if low_vals:
        new_low_mean, new_high_mean = sum(low_vals) / len(low_vals), sum(high_vals) / len(high_vals)
        print(f"  new-mechanism jitter, low-rotation frames: {new_low_mean:.2f}px "
              f"vs. high-rotation frames: {new_high_mean:.2f}px "
              f"(ratio {new_high_mean / new_low_mean:.2f}x)")
    if old_low_vals:
        old_low_mean, old_high_mean = sum(old_low_vals) / len(old_low_vals), sum(old_high_vals) / len(old_high_vals)
        print(f"  old (today's) jitter, low-rotation frames: {old_low_mean:.2f}px "
              f"vs. high-rotation frames: {old_high_mean:.2f}px "
              f"(ratio {old_high_mean / old_low_mean:.2f}x)")

    print("\n=== Yaw/foreshortening check (does the cube sink toward the palm when the hand turns sideways?) ===")
    yaw_diags = [r["yaw_diag"] for r in all_results if r["yaw_diag"] is not None]
    corr_vals = [d["correlation"] for d in yaw_diags if d.get("correlation") is not None]
    fore_vals = [d["foreshortened_bias"] for d in yaw_diags if d.get("foreshortened_bias") is not None]
    front_vals = [d["frontal_bias"] for d in yaw_diags if d.get("frontal_bias") is not None]
    if corr_vals:
        print(f"  mean ratio-vs-palm-bias correlation: {sum(corr_vals)/len(corr_vals):.2f} "
              f"(across {len(corr_vals)} intervals; negative = confirms the reported swing-toward-palm)")
    if fore_vals:
        print(f"  mean palm-bias, most-sideways frames: {sum(fore_vals)/len(fore_vals):+.2f} "
              f"vs. most-frontal frames: {sum(front_vals)/len(front_vals):+.2f}")
        print(f"  worst single-frame min knuckle-width ratio seen: "
              f"{min(d.get('min_ratio', 1.0) for d in yaw_diags):.2f}")


if __name__ == "__main__":
    main()
