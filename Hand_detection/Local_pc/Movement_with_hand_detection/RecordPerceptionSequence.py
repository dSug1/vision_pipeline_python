"""Raw-capture recorder for the perception layer (merged queue items 0.1 / 0.2b).

Records the scripted test sequences defined in PERCEPTION_LAYER_SPEC.md §7.2 to
the session layout defined in M0, so every perception module can be A/B tested
offline on identical input.

DELIBERATELY PURE L0/L1 CAPTURE. Unlike `RecordTranslationPivotDebug.py` -- which
imports `LiveSnapDebug.py` on purpose, so that recorded cube state is real ground
truth for the translation work -- this recorder imports NO gesture logic at all.
It writes only what MediaPipe produced, plus timing. Everything derived
(edge-on measure, palm normal, bone lengths, sign) is recomputed at analysis
time, so a config change never requires re-recording. That is the spec's
boundary discipline (L0-L6 must not depend on gesture logic) applied to the
tooling itself.

Two consequences worth knowing:
  * `tCapture` is a real monotonic timestamp taken at frame read, NOT the
    synthesised 33 ms cadence the older recorders assume.
  * There is no cube, no snap, no window overlay -- only the camera preview and
    the sequence prompt. Nothing to grab.

Usage:  record_perception_sequence.bat <sequence> [duration_s] [camera_index]
        python RecordPerceptionSequence.py --sequence static_hold
"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer"
# Fallback when the external drive is unavailable (it dropped out repeatedly on
# 2026-08-02: reads and writes both failing intermittently between operations,
# WinError 21). Sessions are self-contained folders of plain JSONL + meta.json,
# so a local capture can simply be moved to CAPTURE_ROOT later -- nothing in the
# analysis path depends on which root a session came from.
LOCAL_CAPTURE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perception_recordings")
HAND_LANDMARKER_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "Python_Server_MediaPipe_vision_pipeline", "Resources", "hand_landmarker.task",
)

COUNTDOWN_S = 3.0

# PERCEPTION_LAYER_SPEC.md §7.2. (default_duration_s, on-screen prompt, what it unblocks)
SEQUENCES = {
    "static_hold": (
        12.0,
        "HOLD BOTH HANDS STILL - one pose, do not move at all",
        "resting jitter, palm-normal jitter, bone CV (3 M0 metrics that CANNOT "
        "come from the existing grab-and-rotate recordings)",
    ),
    "non_crossing": (
        30.0,
        "Move hands freely BUT NEVER turn palm-to-back - palms stay to camera",
        "chirality flip rate: any sign flip here is definitionally spurious, "
        "which is what decides EDGE_ON_THRESHOLD",
    ),
    "pitch_sweep_slow": (
        30.0,
        "SLOW pitch sweep: rotate one hand palm->back->palm, ~3s per sweep",
        "crossing survival, orientation continuity, DR-2 entry/exit behaviour",
    ),
    "pitch_sweep_fast": (
        20.0,
        "FAST pitch sweep: same rotation, ~0.5s per sweep",
        "crossing survival under motion blur; angular-velocity carry-through",
    ),
    "palm_back": (
        40.0,
        "Rotate palm<->back repeatedly, at 4 DIFFERENT speeds",
        "chirality flip rate, hysteresis behaviour",
    ),
    "occlusion": (
        30.0,
        "Occlude: hand behind object, out/in of frame, finger over finger",
        "coast behaviour, reacquisition time, accidental-unsnap safety",
    ),
    # Two deliberately SEPARATE conditions. The original single "pass hands close
    # together" prompt was ambiguous (2026-08-02, operator feedback: unclear
    # whether the hands should occlude or merely pass near each other) -- and they
    # are different hypotheses, so they must not be mixed in one recording:
    #   overlap  -> one hand visually hides part of the other; MediaPipe loses the
    #               appearance cues (knuckles, creases) that its handedness
    #               classifier depends on. Strongest candidate for the identity
    #               mixup behind Object Jump Correction (§14.1.4): in the recorded
    #               event, one hand was undetected for several frames and then
    #               reappeared exactly where the other had been.
    #   near-miss -> hands come close in the image but never overlap. If the mixup
    #               reproduces here TOO, occlusion is not the mechanism and the
    #               cause is proximity/association alone -- a materially different
    #               fix. This is the control condition.
    "two_hand_overlap": (
        30.0,
        "CROSS hands so they OVERLAP - pass one IN FRONT of the other, briefly "
        "hiding it - then swap sides. Repeat.",
        "Object Jump Correction - the hand-identity-mixup repro condition "
        "(occlusion hypothesis)",
    ),
    "two_hand_near_miss": (
        30.0,
        "Pass hands CLOSE but NEVER touching or overlapping - keep a visible gap "
        "- then swap sides. Repeat.",
        "Object Jump Correction CONTROL: if the mixup happens here too, occlusion "
        "is not the mechanism",
    ),
    "depth_sweep": (
        30.0,
        "Push one hand slowly toward the camera and pull it back, repeatedly",
        "depth monotonicity, foreshortening-correction correctness",
    ),
    "known_right_palm": (
        8.0,
        "RIGHT hand only, PALM to camera, held steady - ground truth clip",
        "the M5d `K` fixture test (item 1.1) - ground truth is the LABEL itself",
    ),
    "known_right_back": (
        8.0,
        "RIGHT hand only, BACK of hand to camera, held steady - ground truth",
        "the M5d `K` fixture test (item 1.1)",
    ),
    "known_left_palm": (
        8.0,
        "LEFT hand only, PALM to camera, held steady - ground truth clip",
        "the M5d `K` fixture test (item 1.1)",
    ),
    "known_left_back": (
        8.0,
        "LEFT hand only, BACK of hand to camera, held steady - ground truth",
        "the M5d `K` fixture test (item 1.1)",
    ),
}


def _window_open(name):
    return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) >= 1


def main():
    parser = argparse.ArgumentParser(description="Record a scripted perception-layer test sequence.")
    parser.add_argument("--sequence", required=True, choices=sorted(SEQUENCES),
                        help="which §7.2 sequence to record")
    parser.add_argument("--duration", type=float, default=None, help="override the default duration")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--note", type=str, default="", help="free-text note stored in meta.json")
    parser.add_argument("--local", action="store_true",
                        help="record to the LOCAL capture root instead of the external drive "
                             "(use when E: is unavailable; move the session folder later)")
    parser.add_argument("--capture-root", type=str, default=None,
                        help="explicit capture root, overriding both defaults")
    args = parser.parse_args()

    capture_root = args.capture_root or (LOCAL_CAPTURE_ROOT if args.local else CAPTURE_ROOT)

    default_duration, prompt, unblocks = SEQUENCES[args.sequence]
    duration = args.duration if args.duration is not None else default_duration

    # PREFLIGHT: create and write-test the session directory BEFORE capturing a
    # single frame. Learned the hard way 2026-08-02 -- the capture root is on an
    # external drive, and when it was unavailable the original ordering failed at
    # SAVE time, discarding a completed 12s take. Fail before the operator's
    # effort, never after it.
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session_dir = os.path.join(capture_root, "sessions", f"{stamp}_{args.sequence}")
    try:
        os.makedirs(session_dir, exist_ok=True)
        probe = os.path.join(session_dir, ".writable")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as e:
        raise SystemExit(
            f"[perception] Capture root is not writable, refusing to record.\n"
            f"             path : {session_dir}\n"
            f"             error: {e}\n"
            f"             If this is the external drive, re-run with --local to "
            f"capture locally\n"
            f"             and move the session folder across later."
        )

    base_options = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options, num_hands=2, running_mode=vision.RunningMode.VIDEO
    )
    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). "
                           f"Is another program using the camera?")
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read an initial frame from the webcam.")
    height, width = frame.shape[:2]

    window_name = f"Perception capture - {args.sequence}"
    records = []

    print(f"[perception] sequence : {args.sequence}")
    print(f"[perception] duration : {duration:.1f}s (after a {COUNTDOWN_S:.0f}s countdown)")
    print(f"[perception] DO THIS  : {prompt}")
    print(f"[perception] unblocks : {unblocks}")

    t0 = time.perf_counter()
    try:
        # --- countdown ---
        countdown_start = time.perf_counter()
        aborted = False
        while True:
            ret, frame = cap.read()
            if not ret:
                aborted = True
                break
            frame = cv2.flip(frame, 1)  # mirrored preview, matching the debug tools
            remaining = COUNTDOWN_S - (time.perf_counter() - countdown_start)
            if remaining <= 0:
                break
            cv2.putText(frame, f"Get ready... {remaining:.1f}s", (10, 30),
                        cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 200, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, prompt, (10, 65),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow(window_name, frame)
            cv2.waitKey(1)
            if not _window_open(window_name):
                aborted = True
                break

        # --- capture ---
        if not aborted:
            record_start = time.perf_counter()
            while True:
                elapsed = time.perf_counter() - record_start
                if elapsed >= duration:
                    break

                ret, frame = cap.read()
                t_capture_ms = (time.perf_counter() - t0) * 1000.0  # real monotonic clock
                if not ret:
                    break
                frame = cv2.flip(frame, 1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = detector.detect_for_video(mp_image, int(t_capture_ms))

                hands = []
                for idx in range(len(result.hand_landmarks)):
                    hands.append({
                        "handedness": result.handedness[idx][0].category_name,
                        "score": round(float(result.handedness[idx][0].score), 5),
                        # pixel coords in the MIRRORED preview frame (detection ran on it)
                        "landmarks": [[round(lm.x * width, 2), round(lm.y * height, 2)]
                                      for lm in result.hand_landmarks[idx]],
                        "world_landmarks": [[round(lm.x, 5), round(lm.y, 5), round(lm.z, 5)]
                                            for lm in result.hand_world_landmarks[idx]],
                    })
                records.append({"tCapture": round(t_capture_ms, 2), "hands": hands})

                # minimal overlay: no landmark drawing, to keep this tool free of
                # any dependency on the gesture/visualiser layer
                cv2.putText(frame, f"REC {duration - elapsed:4.1f}s  frames:{len(records)}  hands:{len(hands)}",
                            (10, 30), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, prompt, (10, 62),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow(window_name, frame)
                cv2.waitKey(1)
                if not _window_open(window_name):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not records:
        print("[perception] No frames captured, nothing saved.")
        try:
            os.rmdir(session_dir)  # don't leave an empty session behind
        except OSError:
            pass
        return

    jsonl_path = os.path.join(session_dir, "raw_landmarks.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    span_s = (records[-1]["tCapture"] - records[0]["tCapture"]) / 1000.0
    meta = {
        "sequence": args.sequence,
        "prompt": prompt,
        "unblocks": unblocks,
        "note": args.note,
        "requested_duration_s": duration,
        "actual_span_s": round(span_s, 3),
        "frames": len(records),
        "measured_fps": round(len(records) / span_s, 2) if span_s > 0 else None,
        "resolution": [width, height],
        "camera_index": args.camera_index,
        "mediapipe_version": getattr(mp, "__version__", "unknown"),
        "model": os.path.basename(HAND_LANDMARKER_MODEL_PATH),
        "mirrored_preview": True,
        "detection_on_mirrored_frame": True,
        "recorded_at": stamp,
        "config_hash": hashlib.sha256(
            f"{args.sequence}|{width}x{height}|{getattr(mp, '__version__', '?')}".encode()
        ).hexdigest()[:12],
    }
    with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    detected = sum(1 for r in records if r["hands"])
    print(f"[perception] Saved {len(records)} frames ({meta['measured_fps']} fps measured) to")
    print(f"             {session_dir}")
    print(f"[perception] frames with >=1 hand detected: {detected}/{len(records)}")


if __name__ == "__main__":
    main()
