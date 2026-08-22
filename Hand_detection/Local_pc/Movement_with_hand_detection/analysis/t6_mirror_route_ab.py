"""T6 -- DEBUG vs PRODUCTION: are the two mirroring routes actually equivalent?

Owner, 2026-08-22: "in this debug configuration the vertical axis rotation looks
ok ... it seemed to me the behavior in the production was not the same".

WHAT IS AND IS NOT SHARED (audited 2026-08-22, read before assuming a cause)
----------------------------------------------------------------------------
Identical in both: the estimator (`palm_rotation.Horn(PALM_LANDMARKS,'ref')`),
the delta math (`delta = q_now * conj(q_grab)`, left-multiplied), the slerp
(0.35), AND DR-1 -- the server runs `hand_identity` and OVERRIDES MediaPipe's
handedness with the resolved track label (`hands_visualizer.py`), exactly as
`LiveSnapDebug.py` does. Pixel and world landmarks are extracted with the SAME
label key, so they cannot be cross-assigned.

EXACTLY ONE THING DIFFERS -- how the mirror is applied:

    DEBUG       cv2.flip the frame BEFORE detection; world landmarks used as-is
    PRODUCTION  detect on the RAW frame; world landmarks x-NEGATED afterward
                (`remap_world_keypoints(invert_x=True)`)

Those are equivalent **only if MediaPipe is mirror-equivariant**, i.e. only if

    W_mirrored_input  ==  diag(-1,1,1) . W_raw_input

⚠ BOTH files flag this as never verified, in almost the same words:
  - `remap_world_keypoints`: "This has NOT been live-verified yet ... confirm the
    rotation's sign/axis feel live once this wire-protocol extension is actually
    in use, don't assume this is correct as-is."
  - `LiveSnapDebug.py`: "the production port ... will need an explicit
    x-negation there -- verify live when that port happens".

This script is that verification. It runs BOTH routes on the SAME camera frame,
through TWO detectors, and reports:

  1. GEOMETRY  per-landmark RMS between W_A and M.W_B -- the direct equivariance
     test, in millimetres. Zero (up to detector noise) means the routes agree.
  2. CONSEQUENCE  the rotation each route yields from a common reference: the
     angle BETWEEN the two rotations, and each route's axis. This is what the
     cube would actually do.

⭐ Note a pure mirror can only REVERSE an axis, never tilt one
(M R M^-1 = R(-Mn, theta)) -- established in spec 14.3.4. So if the two routes
disagree by a TILT rather than a sign, the cause is NOT the mirror algebra but
MediaPipe answering differently on a mirrored image.

Needs the camera. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t6_mirror_route_ab.py [--duration 30]
"""

import argparse
import math
import os
import sys
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_rotation as PR      # noqa: E402

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                     "Python_Server_MediaPipe_vision_pipeline", "Resources",
                     "hand_landmarker.task")


def make_detector(image_mode=False):
    """VIDEO mode is what BOTH real systems run, so it is the ecologically valid
    comparison. But each detector then carries its OWN temporal tracking state,
    which is a confound: some of the disagreement could be the two trackers
    drifting apart rather than a genuine mirror asymmetry. IMAGE mode is
    stateless and isolates pure equivariance. Run both."""
    mode = vision.RunningMode.IMAGE if image_mode else vision.RunningMode.VIDEO
    opts = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=MODEL),
        num_hands=1, running_mode=mode)
    return vision.HandLandmarker.create_from_options(opts)


def world_of(result):
    if not result.hand_world_landmarks:
        return None
    return [(lm.x, lm.y, lm.z) for lm in result.hand_world_landmarks[0]]


def pixels_of(result, w, h):
    if not result.hand_landmarks:
        return None
    return [(lm.x * w, lm.y * h) for lm in result.hand_landmarks[0]]


def axis_angle(q):
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, 0.0
    return (x / s, y / s, z / s), math.degrees(2.0 * math.acos(w))


def q_between(qa, qb):
    """Angle between two rotations, in degrees."""
    d = abs(sum(a * b for a, b in zip(qa, qb)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


def med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--camera-index", type=int, default=0)
    ap.add_argument("--image-mode", action="store_true",
                    help="stateless IMAGE mode: removes the tracking-state confound")
    args = ap.parse_args()

    det_a = make_detector(args.image_mode)               # A = debug route
    det_b = make_detector(args.image_mode)               # B = production route
    if args.image_mode:
        print("[t6] IMAGE mode: stateless, isolates equivariance from tracking drift")
    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise SystemExit("Could not open the webcam.")
    ok, probe = cap.read()
    if not ok:
        raise SystemExit("Could not read from the webcam.")
    h, w = probe.shape[:2]

    horn_a = PR.Horn(PR.PALM_LANDMARKS, "ref")
    horn_b = PR.Horn(PR.PALM_LANDMARKS, "ref")
    st_a = st_b = None
    rms_mm, betweens, ax_a, ax_b = [], [], [], []
    ts = 0
    t0 = time.perf_counter()
    win = "T6  debug route vs production route  (press q to stop)"

    print("=" * 76)
    print("T6  MIRROR-ROUTE A/B -- both routes, same frames, two detectors")
    print("=" * 76)
    print("  A = DEBUG      : flip the frame, then detect")
    print("  B = PRODUCTION : detect, then negate world x")
    print("  Rotate your hand in YAW (palm edge-on, like a page) while this runs.\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            mirrored = cv2.flip(frame, 1)

            img_a = mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB))
            img_b = mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if args.image_mode:
                ra, rb = det_a.detect(img_a), det_b.detect(img_b)
            else:
                ra = det_a.detect_for_video(img_a, ts)
                rb = det_b.detect_for_video(img_b, ts)
            ts += 33

            wa, wb = world_of(ra), world_of(rb)
            pa, pb = pixels_of(ra, w, h), pixels_of(rb, w, h)
            if wa and wb:
                wb_m = [(-x, y, z) for x, y, z in wb]        # production's invert_x
                # 1. GEOMETRY: do the two routes describe the same hand?
                d2 = sum((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2
                         for (ax, ay, az), (bx, by, bz) in zip(wa, wb_m))
                rms_mm.append(math.sqrt(d2 / len(wa)) * 1000.0)

                # 2. CONSEQUENCE: the rotation each route produces
                if st_a is None:
                    st_a, st_b = horn_a.freeze(pa, wa), horn_b.freeze(pb, wb_m)
                else:
                    qa = horn_a.delta(st_a, pa, wa)
                    qb = horn_b.delta(st_b, pb, wb_m)
                    if qa and qb:
                        aa, na = axis_angle(qa)
                        ab, nb = axis_angle(qb)
                        if aa and ab and na > 25.0 and nb > 25.0:
                            betweens.append(q_between(qa, qb))
                            ax_a.append(aa)
                            ax_b.append(ab)

            hud = mirrored.copy()
            cv2.putText(hud, f"frames {len(rms_mm)}  rotating {len(betweens)}"
                             f"  RMS {med(rms_mm) if rms_mm else 0:.1f} mm",
                        (10, 30), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 220, 255), 2)
            cv2.putText(hud, "YAW: palm edge-on, like turning a page",
                        (10, 62), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)
            cv2.imshow(win, hud)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break
            if time.perf_counter() - t0 >= args.duration:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    print("\n" + "=" * 76)
    print("RESULT")
    print("=" * 76)
    if not rms_mm:
        print("  No frames with a hand in both routes -- nothing measured.")
        return
    r = sorted(rms_mm)
    print(f"  1. GEOMETRY  W_debug vs mirrored W_production, per-landmark RMS")
    print(f"       p50 {r[len(r)//2]:6.2f} mm    p95 {r[int(len(r)*0.95)]:6.2f} mm"
          f"    max {r[-1]:6.2f} mm    (n={len(r)})")
    print(f"     reference: MediaPipe's own documented world-landmark error is"
          f" 13-15 mm (spec 1.4),")
    print(f"     and the palm is rigid to 2.76 mm (spec 0.2).")
    if not betweens:
        print("\n  2. No frames rotated past 25 deg in both routes -- rotate more next run.")
        return
    b = sorted(betweens)
    print(f"\n  2. CONSEQUENCE  angle between the two routes' rotations")
    print(f"       p50 {b[len(b)//2]:6.2f} deg   p95 {b[int(len(b)*0.95)]:6.2f} deg"
          f"   max {b[-1]:6.2f} deg   (n={len(b)})")

    def mean_axis(v):
        m = [sum(a[i] for a in v) / len(v) for i in range(3)]
        n = math.sqrt(sum(c * c for c in m)) or 1.0
        return tuple(c / n for c in m)

    ma, mb = mean_axis(ax_a), mean_axis(ax_b)
    print(f"       mean axis A (debug)      X {ma[0]:+.3f}  Y {ma[1]:+.3f}  Z {ma[2]:+.3f}")
    print(f"       mean axis B (production) X {mb[0]:+.3f}  Y {mb[1]:+.3f}  Z {mb[2]:+.3f}")
    print("\n  READING IT: a few mm / a few deg is detector noise and the routes agree")
    print("  -- then the production difference is NOT the mirror and lies elsewhere.")
    print("  A large disagreement means MediaPipe is NOT mirror-equivariant, and")
    print("  production's invert_x shortcut is not a valid substitute for flipping")
    print("  the frame before detection.")


if __name__ == "__main__":
    main()
