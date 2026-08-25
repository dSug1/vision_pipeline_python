"""Record the ON-AXIS, PAUSED, DECLARED-ANGLE takes the 2D-ratio table needs.

⭐⭐ WHY THIS IS ITS OWN TOOL AND NOT A NEW `RecordPerceptionSequence` SEQUENCE.
That recorder captures a CONTINUOUS sweep for a fixed duration. This protocol is
the opposite in every respect that matters: the operator PAUSES at angles they
DECLARE, each hold is its own labelled segment, and a frame only counts if the
palm is on the optical axis. Different protocol, different tool. ⚠ The shared
pieces are imported, never copied (N6): `session_paths` for the tag, and
`palm_geometry` for the focal length and the palm landmark set.

--------------------------------------------------------------------------------
THE POINT OF THE ON-AXIS CONSTRAINT -- and it is first-order, not a nicety
--------------------------------------------------------------------------------
The table maps `2D landmark distance ratios -> true palm angle`. Those ratios are
set by the angle between the palm and the VIEWING RAY, not the optical axis. A
hand `r` pixels from the principal point is seen along a ray tilted by

    alpha = atan(r / focal_px)

At 640x480 and CAMERA_HFOV_DEG = 60, focal_px = 554.3, so:

      25 px ->  2.6 deg      150 px -> 15.1 deg
      50 px ->  5.2 deg      200 px -> 19.8 deg
     100 px -> 10.2 deg      250 px -> 24.3 deg

⭐ A palm is ~94 px wide at 0.5 m, so **one palm width off centre is already
~10 deg** -- 40% of a 25 deg table step. A reference table built off-axis has that
error baked in and can never be recovered, because `alpha` is not stored.

⛔ So the REFERENCE must be captured on-axis. At runtime the hand is wherever the
player puts it, and the same relation supplies the compensation, which is
beautifully simple in the decoupled (x-ratio / y-ratio) formulation:

    yaw_true   ~= yaw_from_table   - atan(x_offset_px / focal_px)
    pitch_true ~= pitch_from_table - atan(y_offset_px / focal_px)

Every frame here therefore stores its own offset and alpha, so the harness can
verify that relation instead of assuming it.

--------------------------------------------------------------------------------
WHAT IT WRITES
--------------------------------------------------------------------------------
`raw_landmarks.jsonl` in EXACTLY the corpus schema (`tCapture`, `hands[]` with
`handedness`, `score`, `landmarks`, `world_landmarks`), so every existing
`analysis/` harness reads it unchanged -- plus per-frame `declared_deg`,
`position_index`, `palm_offset_px`, `alpha_deg` and `on_axis`.

⚠ Frames are recorded whether or not they are on-axis, with the flag set. Nothing
is silently dropped: a take that could not hold the axis should be VISIBLE in the
data, not absent from it.

⭐⭐ IF THE OPERATOR MEASURES THE REAL DISTANCE, PASS IT: `--declared-depth-m`.
It is optional for the ratio table (ratios are scale-free), but it is the ONLY
declared depth ground truth in the corpus -- so these six takes would also, for
free, measure the absolute depth estimator's per-user scale bias, which today is
absorbed by a deliberately generous GRAB_Z_TOLERANCE_M = 0.15 m and is exactly
what U12 exists to collapse.

Run from the app root:
    .venv/Scripts/python.exe tools/RecordRatioCalibration.py --axis yaw --hand right
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ⚠ This file lives in tools/, so the app root is one level up.
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_APP_ROOT, "Resources"))
import palm_geometry as PG          # noqa: E402  (imported, never copied -- N6)
import palm_depth as PD              # noqa: E402  (NOMINAL_SPAN_M -- one source)
import session_paths                # noqa: E402

HAND_LANDMARKER_MODEL_PATH = os.path.join(
    _APP_ROOT, "..", "Python_Server_MediaPipe_vision_pipeline", "Resources",
    "hand_landmarker.task")

CAPTURE_ROOT = (r"E:\Python\Recordings for vision_pipeline"
                r"\Recordings_perception_layer\sessions")

PALM_LANDMARKS = (0, 5, 9, 13, 17)     # wrist + the four MCPs

# ⭐ TOLERANCE, DERIVED NOT CHOSEN. 25 px at focal 554.3 is alpha = 2.6 deg, which
# is ~10% of a 25 deg table step -- small enough that the reference is not
# meaningfully contaminated by it. 50 px (5.2 deg) is the amber band.
DEFAULT_TOL_PX = 25
AMBER_TOL_PX = 50

PROMPTS = {
    "yaw": ("Hand VERTICAL. Rotate about the VERTICAL axis, like turning a page.",
            "0 deg = palm square to the camera. 180 deg = back of the hand square."),
    "pitch": ("Hand VERTICAL. Rotate about the HORIZONTAL axis, tipping toward/away.",
              "0 deg = palm square to the camera. 180 deg = back of the hand square."),
}


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[len(xs) // 2], 4) if xs else None


def palm_centre_px(landmarks):
    pts = [landmarks[i] for i in PALM_LANDMARKS]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def depth_estimate_m(landmarks, focal):
    """Rough absolute depth, MIN over the four rigid palm spans.

    ⭐ MIN, not mean or max, and the reason is the whole point of this protocol:
    foreshortening only ever SHORTENS a projected span, and a shorter span implies
    a LARGER apparent depth. So the least-foreshortened span is the one giving the
    SMALLEST depth, and taking the min is what makes this survive a take that
    deliberately rotates the palm 180 deg. Same trick `palm_depth` uses.

    ⚠ It is an ESTIMATE, for confirming that the three takes really sat at
    different depths -- not a calibrated measurement. It inherits the assumed
    60 deg HFOV and anthropometric medians, so it carries a per-user scale bias.
    """
    best = None
    for (a, b), metres in PD.NOMINAL_SPAN_M.items():
        pa, pb = landmarks[a], landmarks[b]
        span_px = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        if span_px <= 1e-6:
            continue
        d = focal * metres / span_px
        if best is None or d < best:
            best = d
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--axis", required=True, choices=("yaw", "pitch"))
    ap.add_argument("--hand", required=True, choices=("left", "right"),
                    help="the PHYSICAL hand, declared before recording (ground truth)")
    ap.add_argument("--positions", type=int, default=8,
                    help="declared hold positions, inclusive of both ends (default 8)")
    ap.add_argument("--span", type=float, default=180.0,
                    help="total rotation covered, degrees (default 180)")
    ap.add_argument("--hold-frames", type=int, default=40,
                    help="ON-AXIS frames required per position (default 40, ~2 s)")
    ap.add_argument("--tolerance-px", type=float, default=DEFAULT_TOL_PX)
    ap.add_argument("--camera-index", type=int, default=0)
    ap.add_argument("--tag", type=str, default="",
                    help="suffix appended to the session name")
    ap.add_argument("--declared-depth-m", type=float, default=None,
                    help="MEASURED palm-to-lens distance in metres, declared "
                         "BEFORE recording. Optional for the ratio table (ratios "
                         "are scale-free) but valuable: it is the only DECLARED "
                         "depth ground truth in the corpus, so it also measures "
                         "the absolute estimator's per-user scale bias (U12).")
    ap.add_argument("--note", type=str, default="")
    args = ap.parse_args()

    n = args.positions
    angles = [round(args.span * i / (n - 1), 2) for i in range(n)] if n > 1 else [0.0]

    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[calib] Camera not available. Is the debug tool or production running?")
        return 1
    ok, probe = cap.read()
    if not ok:
        print("[calib] Camera opened but the first read failed.")
        cap.release()
        return 1
    height, width = probe.shape[:2]
    cx, cy = width / 2.0, height / 2.0
    focal = PG.focal_px((width, height))

    base = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    detector = vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(base_options=base, num_hands=1,
                                     running_mode=vision.RunningMode.VIDEO))

    suffix = session_paths.safe_tag(args.tag, fallback="") if args.tag else ""
    name = "ratio_calib_%s_%s%s" % (args.axis, args.hand,
                                    ("_" + suffix) if suffix else "")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    outdir = os.path.join(CAPTURE_ROOT, "%s_%s" % (stamp, name))

    win = "ratio calibration -- %s, %s hand" % (args.axis, args.hand)
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)

    print("[calib] axis      : %s     hand: %s (DECLARED)" % (args.axis, args.hand))
    print("[calib] positions : %s" % angles)
    print("[calib] focal     : %.1f px   tolerance %.0f px = %.1f deg"
          % (focal, args.tolerance_px, math.degrees(math.atan(args.tolerance_px / focal))))
    print("[calib] SPACE = start/stop a hold   R = redo   N = skip   ESC/Q = abort")

    records, per_pos = [], []
    t_ms, t0 = 0.0, time.perf_counter()
    aborted = False

    try:
        for pi, ang in enumerate(angles):
            collected, arming, started_at = 0, True, None
            off_hist, depth_hist = [], []
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("[calib] camera read failed")
                    aborted = True
                    break
                frame = cv2.flip(frame, 1)          # mirrored, as every other tool
                t_ms = (time.perf_counter() - t0) * 1000.0
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = detector.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(t_ms))

                hands, off, alpha, on_axis, depth = [], None, None, False, None
                for idx in range(len(res.hand_landmarks)):
                    lms = [[round(lm.x * width, 2), round(lm.y * height, 2)]
                           for lm in res.hand_landmarks[idx]]
                    hands.append({
                        "handedness": res.handedness[idx][0].category_name,
                        "score": round(float(res.handedness[idx][0].score), 5),
                        "landmarks": lms,
                        "world_landmarks": [[round(lm.x, 5), round(lm.y, 5), round(lm.z, 5)]
                                            for lm in res.hand_world_landmarks[idx]],
                    })
                if len(hands) == 1:
                    px, py = palm_centre_px(hands[0]["landmarks"])
                    off = math.hypot(px - cx, py - cy)
                    alpha = math.degrees(math.atan(off / focal))
                    on_axis = off <= args.tolerance_px
                    depth = depth_estimate_m(hands[0]["landmarks"], focal)

                # ---- capture ------------------------------------------------
                if not arming and len(hands) == 1:
                    records.append({
                        "tCapture": round(t_ms, 2),
                        "hands": hands,
                        "axis": args.axis,
                        "position_index": pi,
                        "declared_deg": ang,
                        "palm_offset_px": round(off, 2),
                        "alpha_deg": round(alpha, 3),
                        "on_axis": bool(on_axis),
                        "depth_est_m": round(depth, 4) if depth else None,
                    })
                    if on_axis:
                        collected += 1
                        off_hist.append(off)
                        if depth:
                            depth_hist.append(depth)

                # ---- HUD ----------------------------------------------------
                colour = ((0, 200, 0) if on_axis else
                          (0, 200, 255) if (off is not None and off <= AMBER_TOL_PX) else
                          (0, 0, 255))
                cv2.circle(frame, (int(cx), int(cy)), int(args.tolerance_px), colour, 2)
                cv2.drawMarker(frame, (int(cx), int(cy)), (255, 255, 255),
                               cv2.MARKER_CROSS, 18, 1)
                if off is not None:
                    px, py = palm_centre_px(hands[0]["landmarks"])
                    cv2.circle(frame, (int(px), int(py)), 5, colour, -1)
                    cv2.line(frame, (int(cx), int(cy)), (int(px), int(py)), colour, 1)
                    if depth:
                        cv2.putText(frame, "depth ~%.2f m" % depth, (width - 190, height - 40),
                                    cv2.FONT_HERSHEY_DUPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
                    cv2.putText(frame, "off %4.0f px = %4.1f deg" % (off, alpha),
                                (10, height - 40), cv2.FONT_HERSHEY_DUPLEX, 0.6,
                                colour, 1, cv2.LINE_AA)
                else:
                    cv2.putText(frame, "no single hand", (10, height - 40),
                                cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 1, cv2.LINE_AA)

                head = "%d/%d  HOLD AT %.0f deg" % (pi + 1, len(angles), ang)
                cv2.putText(frame, head, (10, 28), cv2.FONT_HERSHEY_DUPLEX, 0.8,
                            (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, PROMPTS[args.axis][0], (10, 54),
                            cv2.FONT_HERSHEY_DUPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
                cv2.putText(frame, PROMPTS[args.axis][1], (10, 74),
                            cv2.FONT_HERSHEY_DUPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
                state = ("SPACE to start the hold" if arming else
                         "RECORDING  %d/%d on-axis frames" % (collected, args.hold_frames))
                cv2.putText(frame, state, (10, height - 14), cv2.FONT_HERSHEY_DUPLEX,
                            0.6, (0, 0, 255) if not arming else (255, 255, 255),
                            1, cv2.LINE_AA)
                cv2.imshow(win, frame)

                k = cv2.waitKey(1) & 0xFF
                if k in (27, ord('q')):
                    aborted = True
                    break
                if k == ord(' '):
                    arming = not arming
                    if not arming:
                        started_at = len(records)
                if k == ord('r'):                      # redo: drop this position
                    if started_at is not None:
                        del records[started_at:]
                    collected, arming, started_at = 0, True, None
                    off_hist, depth_hist = [], []
                if k == ord('n'):
                    break
                if (not arming) and collected >= args.hold_frames:
                    break

            if aborted:
                break
            off_hist.sort()
            depth_hist.sort()
            med_d = depth_hist[len(depth_hist) // 2] if depth_hist else None
            per_pos.append({
                "position_index": pi,
                "declared_deg": ang,
                "on_axis_frames": collected,
                "median_offset_px": round(off_hist[len(off_hist) // 2], 2) if off_hist else None,
                "median_depth_est_m": round(med_d, 4) if med_d else None,
            })
            print("[calib]   %6.1f deg -> %d on-axis frames%s"
                  % (ang, collected, ("   depth ~%.2f m" % med_d) if med_d else ""))
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if aborted and not records:
        print("[calib] aborted, nothing written.")
        return 1
    if not records:
        print("[calib] no frames captured, nothing written.")
        return 1

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "raw_landmarks.jsonl"), "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")

    on_axis_total = sum(1 for r in records if r["on_axis"])
    meta = {
        "sequence": name,
        "source": "tools/RecordRatioCalibration.py",
        "purpose": ("ON-AXIS paused reference for the 2D-ratio orientation table. "
                    "Ground truth is the OPERATOR'S DECLARED angle at each hold."),
        "axis": args.axis,
        "known_hand": args.hand,
        "declared_angles_deg": angles,
        "positions": per_pos,
        "frames": len(records),
        "frames_on_axis": on_axis_total,
        "median_depth_est_m": _median([r["depth_est_m"] for r in records
                                       if r["on_axis"] and r.get("depth_est_m")]),
        "declared_depth_m": args.declared_depth_m,
        "tolerance_px": args.tolerance_px,
        "tolerance_deg": round(math.degrees(math.atan(args.tolerance_px / focal)), 3),
        "focal_px": round(focal, 2),
        "frame_size": [width, height],
        "camera_hfov_deg_assumed": PG.CAMERA_HFOV_DEG,
        "mirrored": True,
        "aborted": aborted,
        "mediapipe_version": getattr(mp, "__version__", "unknown"),
        "note": args.note,
        "offaxis_compensation": (
            "Ratios are set by the angle to the VIEWING RAY, not the optical axis. "
            "alpha = atan(offset_px / focal_px). This take is on-axis by "
            "construction so the table is uncontaminated; at runtime compensate "
            "with yaw_true ~= yaw_table - atan(x_off/focal) and "
            "pitch_true ~= pitch_table - atan(y_off/focal). Every frame stores its "
            "own offset and alpha so that relation can be VERIFIED, not assumed."),
    }
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)

    est = meta["median_depth_est_m"]
    if args.declared_depth_m and est:
        ratio = est / args.declared_depth_m
        print("[calib] depth  declared %.3f m   estimated %.3f m   ratio %.3f"
              % (args.declared_depth_m, est, ratio))
        print("[calib]        ⭐ that ratio IS the absolute estimator's scale bias "
              "at this depth (U12).")
    print("[calib] wrote %d frames (%d on-axis) to" % (len(records), on_axis_total))
    print("        %s" % outdir)
    if aborted:
        print("[calib] \u26a0 ABORTED partway -- meta.aborted is true. Treat as incomplete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
