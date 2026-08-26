"""⭐⭐ §10.1 — THE TRIM-RESOLUTION TAKE. The metric `F1` needs and did not have.

Every metric the project owns measures GROSS sweep fidelity: yaw axis, lean,
pitch, roll, jitter over big hand rotations. `F1` exists to buy FINE alignment —
nudging a held object into place with the fingers while the wrist stays put.
⛔ So `F1` can pass every existing number and still deliver nothing it was built
for. This records the take that tells them apart.

────────────────────────────────────────────────────────────────────────────────
WHAT IT CAPTURES, AND WHY IT IS NOT CIRCULAR

Two marked states per declared angle:

    REFERENCE   fingers neutral, wrist still
    TARGET      fingers rotated by the angle YOU DECLARED, wrist still

⭐ The ground truth is the operator's DECLARATION, made before the take — never
the estimator being scored. That is `B4`'s binding rule (*"an anchor metric must
not share an expression with the anchor"*), the same discipline `U7`'s acceptance
take and the ratio-table protocol both follow.

⛔ THE WRIST-STILL GATE IS THE WHOLE POINT. If the palm turns, the gross channel
has done the work and the fine channel is untested. A frame counts only while the
palm's own rotation since the state began stays under `--palm-tol-deg` and its
centre has moved under `--palm-tol-px`. Frames that fail are still RECORDED but
flagged, so a take that could not hold the wrist is visible rather than silently
thinned — the same choice the ratio protocol made.

⚠ The object's response is NOT recorded here, deliberately. Landmarks are, and
`analysis/f1_trim_resolution.py` replays them through the SHIPPED pipeline to get
the cube's rotation. Recording the cube would freeze one build's answer into the
take; replaying lets the same take score every future build.

────────────────────────────────────────────────────────────────────────────────
    .venv/Scripts/python.exe tools/RecordTrimResolution.py --hand right
        [--angles 10 20 40] [--hold-frames 30] [--tag ...] [--note ...]
"""
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

try:                                    # the console here is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_APP_ROOT, "Resources"))
import palm_geometry as PG          # noqa: E402  (imported, never copied -- N6)
import palm_rotation as PR          # noqa: E402  (the SHIPPED Horn fit)
import session_paths                # noqa: E402

HAND_LANDMARKER_MODEL_PATH = os.path.join(
    _APP_ROOT, "..", "Python_Server_MediaPipe_vision_pipeline", "Resources",
    "hand_landmarker.task")
CAPTURE_ROOT = (r"E:\Python\Recordings for vision_pipeline"
                r"\Recordings_perception_layer\sessions")

# ⭐ Both derived, not chosen. The palm's own rotation must stay well below the
# smallest declared finger angle or the two channels are not separable; 5 deg is
# half of the smallest angle this take asks for. The translation figure is the
# barycentre's measured p50 frame-to-frame speed (56 px/s) over ~0.5 s.
DEFAULT_PALM_TOL_DEG = 5.0
DEFAULT_PALM_TOL_PX = 25.0


def palm_centre_px(lms):
    pts = [lms[i] for i in PR.PALM_LANDMARKS]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hand", required=True, choices=("left", "right"),
                    help="DECLARED, never inferred -- the label is 10.8%% wrong")
    ap.add_argument("--angles", type=float, nargs="+", default=[10.0, 20.0, 40.0],
                    help="declared FINGER-ONLY rotations, degrees (default 10 20 40)")
    ap.add_argument("--hold-frames", type=int, default=30)
    ap.add_argument("--palm-tol-deg", type=float, default=DEFAULT_PALM_TOL_DEG)
    ap.add_argument("--palm-tol-px", type=float, default=DEFAULT_PALM_TOL_PX)
    ap.add_argument("--camera-index", type=int, default=0)
    ap.add_argument("--tag", type=str, default="")
    ap.add_argument("--note", type=str, default="")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[trimres] Camera not available. Is the debug tool or production running?")
        return 1
    ok, probe = cap.read()
    if not ok:
        print("[trimres] Camera opened but the first read failed.")
        cap.release()
        return 1
    height, width = probe.shape[:2]

    base = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    detector = vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(base_options=base, num_hands=1,
                                     running_mode=vision.RunningMode.VIDEO))
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")

    suffix = session_paths.safe_tag(args.tag, fallback="") if args.tag else ""
    name = "trim_resolution_%s%s" % (args.hand, ("_" + suffix) if suffix else "")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    outdir = os.path.join(CAPTURE_ROOT, "%s_%s" % (stamp, name))

    win = "F1 §10.1 trim resolution -- %s hand" % args.hand
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)

    print("[trimres] hand    : %s (DECLARED)" % args.hand)
    print("[trimres] angles  : %s deg  (finger-only, wrist STILL)" % args.angles)
    print("[trimres] gate    : palm rotation < %.1f deg and centre < %.0f px"
          % (args.palm_tol_deg, args.palm_tol_px))
    print("[trimres] SPACE = start/stop a state   R = redo this state   ESC/Q = abort")
    print()
    print("  FOR EACH ANGLE, TWO STATES:")
    print("    1. REFERENCE -- hold a cube as if gripping it, fingers NEUTRAL.")
    print("    2. TARGET    -- rotate the OBJECT with your FINGERS by the declared")
    print("                    angle. Your WRIST MUST NOT TURN. Only the fingers.")
    print()

    records, states = [], []
    t0 = time.perf_counter()
    aborted = False

    try:
        for ai, ang in enumerate(args.angles):
            for phase in ("reference", "target"):
                collected, arming = 0, True
                ref_state, worst_deg, worst_px = None, 0.0, 0.0
                ref_centre = None
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        print("[trimres] camera read failed")
                        aborted = True
                        break
                    frame = cv2.flip(frame, 1)
                    t_ms = (time.perf_counter() - t0) * 1000.0
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    res = detector.detect_for_video(
                        mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(t_ms))

                    hands, palm_deg, palm_px, still = [], None, None, False
                    for idx in range(len(res.hand_landmarks)):
                        hands.append({
                            "handedness": res.handedness[idx][0].category_name,
                            "score": round(float(res.handedness[idx][0].score), 5),
                            "landmarks": [[round(lm.x * width, 2), round(lm.y * height, 2)]
                                          for lm in res.hand_landmarks[idx]],
                            "world_landmarks": [[round(lm.x, 5), round(lm.y, 5), round(lm.z, 5)]
                                                for lm in res.hand_world_landmarks[idx]],
                        })
                    if len(hands) == 1:
                        lms, wl = hands[0]["landmarks"], hands[0]["world_landmarks"]
                        c = palm_centre_px(lms)
                        if not arming:
                            if ref_state is None:
                                ref_state = horn.freeze(lms, wl)
                                ref_centre = c
                            if ref_state is not None:
                                d = horn.delta(ref_state, lms, wl)
                                palm_deg = (0.0 if d is None else
                                            PR.quat_angle_deg((1.0, 0.0, 0.0, 0.0), d))
                            palm_px = math.hypot(c[0] - ref_centre[0], c[1] - ref_centre[1])
                            still = (palm_deg is not None
                                     and palm_deg <= args.palm_tol_deg
                                     and palm_px <= args.palm_tol_px)

                    if not arming and len(hands) == 1:
                        records.append({
                            "tCapture": round(t_ms, 2),
                            "hands": hands,
                            "angle_index": ai,
                            "declared_deg": ang,
                            "phase": phase,
                            "palm_rot_deg": None if palm_deg is None else round(palm_deg, 3),
                            "palm_move_px": None if palm_px is None else round(palm_px, 2),
                            "wrist_still": bool(still),
                        })
                        if still:
                            collected += 1
                        worst_deg = max(worst_deg, palm_deg or 0.0)
                        worst_px = max(worst_px, palm_px or 0.0)

                    # ---- overlay
                    colour = (0, 220, 0) if still else (0, 120, 255)
                    cv2.putText(frame, "%s  %.0f deg" % (phase.upper(), ang), (12, 34),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2, cv2.LINE_AA)
                    msg = ("SPACE to start" if arming else
                           "RECORDING %d/%d wrist-still frames" % (collected, args.hold_frames))
                    cv2.putText(frame, msg, (12, 66), cv2.FONT_HERSHEY_SIMPLEX,
                                0.62, (255, 255, 255), 1, cv2.LINE_AA)
                    if palm_deg is not None:
                        cv2.putText(frame, "palm %.1f deg / %.0f px  (limit %.0f / %.0f)"
                                    % (palm_deg, palm_px or 0.0,
                                       args.palm_tol_deg, args.palm_tol_px),
                                    (12, 96), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                    colour, 1, cv2.LINE_AA)
                    if phase == "target":
                        cv2.putText(frame, "FINGERS ONLY -- do not turn the wrist",
                                    (12, height - 18), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.6, (0, 200, 255), 1, cv2.LINE_AA)
                    cv2.imshow(win, frame)

                    k = cv2.waitKey(1) & 0xFF
                    if k in (27, ord('q')):
                        aborted = True
                        break
                    if k == ord(' '):
                        if arming:
                            arming = False
                        else:
                            break
                    if k == ord('r'):
                        records = [r for r in records
                                   if not (r["angle_index"] == ai and r["phase"] == phase)]
                        collected, arming, ref_state, ref_centre = 0, True, None, None
                        worst_deg = worst_px = 0.0
                        print("[trimres] redo %s %.0f deg" % (phase, ang))
                    if (not arming) and collected >= args.hold_frames:
                        break

                if aborted:
                    break
                states.append({"angle_index": ai, "declared_deg": ang, "phase": phase,
                               "still_frames": collected,
                               "worst_palm_rot_deg": round(worst_deg, 3),
                               "worst_palm_move_px": round(worst_px, 2)})
                print("[trimres] %-9s %5.0f deg -> %d still frames "
                      "(worst palm %.1f deg / %.0f px)"
                      % (phase, ang, collected, worst_deg, worst_px))
            if aborted:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not records:
        print("[trimres] nothing recorded.")
        return 1

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "raw_landmarks.jsonl"), "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "recorder_schema": 3,
            "sequence": name,
            "source": "tools/RecordTrimResolution.py",
            "purpose": ("F1 §10.1 trim resolution. Ground truth is the OPERATOR'S "
                        "DECLARED finger-only rotation, with the wrist held still."),
            "known_hand": args.hand,
            "declared_angles_deg": args.angles,
            "hold_frames": args.hold_frames,
            "palm_tol_deg": args.palm_tol_deg,
            "palm_tol_px": args.palm_tol_px,
            "states": states,
            "frames": len(records),
            "frame_size": [width, height],
            "aborted": bool(aborted),
            "note": args.note,
        }, fh, indent=2)
    print("[trimres] wrote %d frames to %s" % (len(records), outdir))
    if aborted:
        print("[trimres] ⚠ ABORTED -- the take is incomplete and marked so in meta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
