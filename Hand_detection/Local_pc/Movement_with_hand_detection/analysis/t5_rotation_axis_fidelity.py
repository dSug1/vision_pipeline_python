"""T5 -- DOES A SINGLE-AXIS HAND ROTATION PRODUCE A SINGLE-AXIS CUBE ROTATION?

Owner observation (2026-08-22): "when I rotate my hand on the yaw axis, the cube
seems to rotate on an axis which is not the world z axis", with pitch and roll
believed (but not verified) correct.

WHAT IS MEASURED, AND WHY IT IS NOT CIRCULAR
--------------------------------------------
Production makes the cube's rotation EQUAL to the hand's fitted rotation:

    delta       = hand_quat_now * conj(grab_hand_orientation)     # world frame
    target_quat = delta * grab_cube_orientation                   # left-multiply

so whatever axis the estimator reports IS the axis the cube turns about. There is
no frame conversion between the two (`HandsTriggeredActions.py` ~L711). Therefore
measuring the fitted axis measures the cube's axis exactly.

The recording protocol supplies the ground truth WITHOUT using the estimator:
`RecordPerceptionSequence.py` instructs a `yaw_sweep_constant_depth` operator to
rotate "about the VERTICAL axis ... like turning a doorknob", and a
`pitch_sweep_*` operator to "tip the fingers TOWARD then AWAY ... the axis runs
left-right across the knuckles". So the expected axis is known a priori:

    yaw   -> the VERTICAL image axis        (world Y here)
    pitch -> the HORIZONTAL image axis      (world X here)
    roll  -> the camera/depth axis          (world Z here)  [NO TAKE EXISTS]

FRAME CONVENTION (established, not assumed)
--------------------------------------------
`RecordPerceptionSequence.py` cv2.flip()s the frame BEFORE detection (L465/L497),
exactly as `LiveSnapDebug.py` does (L1236) and equivalent to what the production
server reproduces with `remap_world_keypoints(invert_x=True)`. So the corpus
world landmarks are in the SAME mirrored frame production feeds the cube, and
these numbers transfer to production directly.

    world X = image right (on the mirrored/selfie display)
    world Y = image DOWN            <- the VERTICAL axis, so yaw belongs here
    world Z = depth (MediaPipe hand-relative metric z)

    NOTE the renderer shares this convention: CubeWindow._draw_object_3d maps
    screen_x = cx + rx*scale, screen_y = cy + ry*scale (pygame y is DOWN).
    So "vertical" is Y in BOTH frames. An owner using a z-up world convention
    (Blender-style) would call this same axis "z"; the axis LINE is what matters
    and this script reports all three components, so either reading is served.

AXIS SIGN
----------
A sweep rotates one way then back, so the per-frame axis direction flips with the
sweep. We care about the axis LINE, not its direction, so each frame's axis is
folded onto a common hemisphere (negate if it opposes the running reference)
before averaging. Angle magnitude is reported separately and unfolded.

Stdlib only. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5_rotation_axis_fidelity.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_rotation as PR  # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# take-tag -> (expected axis index, human label)
EXPECTED = {
    "yaw_sweep_constant_depth": (1, "VERTICAL / world Y"),   # NB two takes: 2026-08-04 is CONTAMINATED (t5c), 2026-08-22 is CLEAN
    "pitch_sweep_slow":         (0, "HORIZONTAL / world X"),
    "pitch_sweep_fast":         (0, "HORIZONTAL / world X"),
    "palm_back_s2_slow":        (0, "HORIZONTAL / world X"),
    "palm_back_s3_medium":      (0, "HORIZONTAL / world X"),
}
AXIS_NAME = ("X (horizontal)", "Y (vertical)", "Z (depth)")

MIN_ANGLE_DEG = 20.0   # only frames actually rotating carry axis information


def load(session_dir):
    path = os.path.join(session_dir, "raw_landmarks.jsonl")
    frames = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def quat_to_axis_angle(q):
    """Returns (axis unit vector, angle in degrees, in [0,180])."""
    w, x, y, z = q
    if w < 0.0:                       # canonical hemisphere -> angle in [0,180]
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    ang = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return (0.0, 0.0, 0.0), 0.0
    return (x / s, y / s, z / s), math.degrees(ang)


def angle_between(a, b):
    d = sum(ai * bi for ai, bi in zip(a, b))
    d = max(-1.0, min(1.0, d))
    return math.degrees(math.acos(abs(d)))     # abs -> axis LINE, ignore direction


def analyse(session_dir, tag, invert_x=False, hand_filter=None):
    frames = load(session_dir)
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    state = None
    axes, angles = [], []
    ref_dir = None

    for fr in frames:
        hands = fr.get("hands") or []
        if not hands:
            continue
        h = hands[0] if hand_filter is None else next(
            (x for x in hands if x.get("handedness") == hand_filter), None)
        if h is None:
            continue
        wl = h.get("world_landmarks")
        if not wl or len(wl) != 21:
            continue
        if invert_x:
            wl = [[-p[0], p[1], p[2]] for p in wl]
        px = h.get("landmarks")

        if state is None:
            state = horn.freeze(px, wl)
            continue
        q = horn.delta(state, px, wl)
        if q is None:
            continue
        axis, ang = quat_to_axis_angle(q)
        if ang < MIN_ANGLE_DEG:
            continue
        if ref_dir is None:
            ref_dir = axis
        if sum(a * b for a, b in zip(axis, ref_dir)) < 0.0:   # fold onto one hemisphere
            axis = (-axis[0], -axis[1], -axis[2])
        axes.append(axis)
        angles.append(ang)

    if not axes:
        return None

    mean = [sum(a[i] for a in axes) / len(axes) for i in range(3)]
    n = math.sqrt(sum(c * c for c in mean)) or 1.0
    mean = tuple(c / n for c in mean)

    spread = sorted(angle_between(a, mean) for a in axes)
    dev = [angle_between(mean, tuple(1.0 if i == k else 0.0 for i in range(3))) for k in range(3)]
    nearest = min(range(3), key=lambda k: dev[k])

    return {
        "tag": tag, "n": len(axes), "mean_axis": mean, "dev": dev, "nearest": nearest,
        "spread_p50": spread[len(spread) // 2], "spread_p95": spread[int(len(spread) * 0.95)],
        "max_angle": max(angles),
    }


def report(res, expected_idx, expected_label):
    mx, my, mz = res["mean_axis"]
    print(f"  frames used (>{MIN_ANGLE_DEG:.0f} deg rotated): {res['n']}   max rotation {res['max_angle']:.1f} deg")
    print(f"  mean fitted axis            : X {mx:+.3f}   Y {my:+.3f}   Z {mz:+.3f}")
    print(f"  deviation from each world axis: X {res['dev'][0]:5.1f}   Y {res['dev'][1]:5.1f}   Z {res['dev'][2]:5.1f}  (deg)")
    print(f"  per-frame axis wander vs mean : p50 {res['spread_p50']:.1f}   p95 {res['spread_p95']:.1f} deg")
    err = res["dev"][expected_idx]
    verdict = "OK" if err < 15.0 else ("TILTED" if err < 50.0 else "WRONG AXIS")
    print(f"  EXPECTED {expected_label}: off by {err:.1f} deg   -> {verdict}")
    if res["nearest"] != expected_idx:
        print(f"  !! the fitted axis is CLOSEST TO {AXIS_NAME[res['nearest']]}, not the expected axis")
    return err


def main():
    sessions = sorted(os.listdir(CAPTURE_ROOT))
    print("=" * 78)
    print("T5  ROTATION-AXIS FIDELITY -- does a single-axis hand rotation")
    print("    produce a single-axis cube rotation?")
    print("=" * 78)
    print(f"corpus : {CAPTURE_ROOT}")
    print("frame  : X=image right, Y=image DOWN (vertical), Z=depth; mirrored/selfie")
    print("estimator: palm_rotation.Horn(PALM_LANDMARKS, 'ref') -- exactly production's\n")

    summary = []
    for tag, (idx, label) in EXPECTED.items():
        matches = [s for s in sessions if s.endswith(tag)]
        if not matches:
            print(f"[{tag}] NO TAKE IN CORPUS -- skipped\n")
            continue
        for s in matches:
            print(f"[{tag}]  {s}")
            res = analyse(os.path.join(CAPTURE_ROOT, s), tag)
            if res is None:
                print("  no usable frames\n")
                continue
            err = report(res, idx, label)
            summary.append((tag, s, err, res["nearest"], idx))
            print()

    print("=" * 78)
    print("MIRROR CONTROL -- same yaw take with the x-axis negated.")
    print("A pure mirror can only REVERSE an axis (M R M^-1 = R(-Mn, theta)),")
    print("never TILT one. If the tilt survives this flip, the mirror is not the cause.")
    print("=" * 78)
    yaw = [s for s in sessions if s.endswith("yaw_sweep_constant_depth")]
    for s in yaw:
        for inv in (False, True):
            res = analyse(os.path.join(CAPTURE_ROOT, s), "yaw", invert_x=inv)
            if res:
                mx, my, mz = res["mean_axis"]
                print(f"  invert_x={str(inv):5s} -> axis X {mx:+.3f} Y {my:+.3f} Z {mz:+.3f}"
                      f"   off-vertical {res['dev'][1]:5.1f} deg")

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for tag, s, err, near, idx in summary:
        flag = "" if near == idx else f"   <-- lands on {AXIS_NAME[near]}"
        print(f"  {tag:28s} off-expected-axis {err:5.1f} deg{flag}")
    print("\n  ROLL: no take exists in the corpus -- rotation in the image plane was")
    print("  never recorded, so roll CANNOT be settled from existing data.")


if __name__ == "__main__":
    main()
