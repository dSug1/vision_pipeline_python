"""4.2 -- WHERE DOES THE OPERATOR'S HAND ACTUALLY SIT? (and can an object be reached?)

⚠⚠ WHY THIS EXISTS, AND IT IS NOT A NICE-TO-HAVE. 4.2's snap gate is 3D: a hand
may only claim an object whose depth is within `palm_depth.GRAB_Z_TOLERANCE_M` of
its own. An object starts at `palm_geometry.REFERENCE_DEPTH_M`. **If the operator
habitually works further away than that by more than the tolerance, NOTHING CAN
EVER BE PICKED UP** -- and the symptom would be a build that looks completely
broken, not a mis-sized constant. That is a failure worth ten minutes of
measurement rather than a plausible-sounding guess.

⚠ U9's derivation is the reason to be suspicious: it read the corpus's **p99**
palm width (127 px) as 0.37 m and concluded "40 cm IS the closest the operator
actually works". p99 is the CLOSEST APPROACH. The TYPICAL distance is further,
and it is the typical distance an object must be initialised at.

⭐ Measured with the SHIPPED estimator (`palm_depth.HandDepthTracker.measure`),
not a re-derivation -- so this reports what the gate will actually see, not what
a second implementation of it would.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/m9_working_distance.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Resources"))
import palm_depth as PD             # noqa: E402
import palm_geometry as PG          # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
FRAME = (640, 480)


def pct(xs, p):
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def main():
    if not os.path.isdir(CAPTURE):
        print("capture root not reachable -- run wake_e_drive.py first")
        return 2
    focal = PG.focal_px(FRAME)
    trk = PD.HandDepthTracker()

    sessions = sorted(os.listdir(CAPTURE))
    if len(sys.argv) > 1:
        sessions = [s for s in sessions if sys.argv[1] in s]

    # ⭐ DECISION 1's COST, measured. The owner's own condition for ever
    # re-tuning "no snapping while depth is frozen" was: *measure how often the
    # freeze actually coincides with a grab attempt first.* This is the
    # denominator for that -- the fraction of hand-frames on which the tracker
    # is HOLDING rather than measuring, i.e. on which a snap would be refused.
    seen_frames, frozen_frames = 0, 0

    per_session, pooled = [], []
    for s in sessions:
        path = os.path.join(CAPTURE, s, "raw_landmarks.jsonl")
        if not os.path.isfile(path):
            continue
        depths = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                for h in row.get("hands") or []:
                    lm = h.get("landmarks")
                    if not lm:
                        continue
                    seen_frames += 1
                    # ⚠ Only frames the gate would TRUST. Measuring through the
                    # edge-on band would pull the distribution outward with
                    # values the shipped code refuses to publish -- i.e. it would
                    # answer a question nothing asks.
                    if PG.edge_on_measure(lm) < PG.EDGE_ON_THRESHOLD:
                        frozen_frames += 1
                        continue
                    d = trk.measure(lm, focal)
                    if d is not None:
                        depths.append(d)
        if depths:
            depths.sort()
            per_session.append((s, len(depths), pct(depths, 50)))
            pooled += depths

    if not pooled:
        print("no usable frames")
        return 1
    pooled.sort()

    print("=" * 84)
    print("4.2 -- MEASURED WORKING DISTANCE (shipped estimator, nominal anatomy)")
    print("=" * 84)
    print(f"  sessions: {len(per_session)}   trusted hand-frames: {len(pooled)}")
    print(f"  focal: {focal:.1f} px at {PG.CAMERA_HFOV_DEG:.0f} deg on {FRAME[0]}x{FRAME[1]}")
    print()
    print(f"  {'p1':>7s} {'p5':>7s} {'p25':>7s} {'MEDIAN':>7s} {'p75':>7s} {'p95':>7s} {'p99':>7s}")
    print("  " + "-" * 55)
    print("  " + " ".join(f"{pct(pooled, p):7.3f}" for p in (1, 5, 25, 50, 75, 95, 99)))
    print()
    print("  per session (median m):")
    for s, n, m in per_session:
        print(f"    {m:6.3f}   n={n:6d}   {s}")

    med = pct(pooled, 50)
    print()
    print("  -> REACHABILITY of an object initialised at REFERENCE_DEPTH_M "
          f"({PG.REFERENCE_DEPTH_M:.2f} m),")
    print(f"     with GRAB_Z_TOLERANCE_M = {PD.GRAB_Z_TOLERANCE_M:.2f} m:")
    reach = sum(1 for d in pooled
                if abs(d - PG.REFERENCE_DEPTH_M) <= PD.GRAB_Z_TOLERANCE_M)
    print(f"       {reach}/{len(pooled)} = {100.0 * reach / len(pooled):.1f}% of "
          "trusted frames could pass the axial gate")
    print(f"     ...and if an object started at the MEASURED median ({med:.3f} m):")
    reach2 = sum(1 for d in pooled if abs(d - med) <= PD.GRAB_Z_TOLERANCE_M)
    print(f"       {reach2}/{len(pooled)} = {100.0 * reach2 / len(pooled):.1f}%")

    print()
    print("  -> COST OF DECISION 1 (no snapping while depth is frozen):")
    print(f"       {frozen_frames}/{seen_frames} = "
          f"{100.0 * frozen_frames / max(seen_frames, 1):.1f}% of hand-frames are "
          "inside the edge-on band")
    print("     ! THAT IS THE CEILING, NOT THE COST. It counts every frame, not")
    print("     frames where a hand was ALSO within grab radius of a free object.")
    print("     A hand edge-on to the camera is rarely a hand reaching to pick")
    print("     something up. Narrow it with a real take before re-tuning the")
    print("     decision -- the recorder writes `depth_valid` per hand for exactly")
    print("     that, so it is a query against a session, not a new session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
