# -*- coding: utf-8 -*-
"""⭐⭐⭐ THE DELTA-ORBIT WINDOW -- where is the hand's own MOTION clean?

    .venv/Scripts/python.exe analysis/delta_orbit_window.py

Owner, 2026-08-29, for branch `1.7.41-Hand-delta-orbit`: *"for yaw and for pitch,
there is an optimal range of hand position degrees which can be used reliably ...
If the hand is inside this degrees range, the delta increment provides input with
the rate gain. If the hand is outside this degrees range, the rate gain smoothly
and quickly decays to zero."*

⛔⛔ THIS ASKS A DIFFERENT QUESTION FROM `rotation_accuracy_bands.py`, AND THE
DIFFERENCE IS WHY THAT HARNESS GAVE THE WRONG ANSWER ABOUT PITCH. It bins by HOW FAR
THE HAND HAS TURNED and scores the ABSOLUTE pose -- correct for a build whose cube
COPIES the hand. A delta-orbit build INTEGRATES INCREMENTS, so what matters is
whether the FRAME-TO-FRAME CHANGE is signal or noise **as a function of where the
hand currently is**. That is the window.

⭐⭐⭐ WHAT IT OVERTURNED TWICE. FIRST, THE POOLING: `rotation_accuracy_bands`
reported pitch wobbling **±29.3 deg at p95 while the hand is still**, and on that
number I told the owner pitch was unusable for this design. That figure is POOLED
ACROSS ALL POSES, and it is almost entirely the **120-180 deg** bin -- the hand
turned PAST EDGE-ON, back of hand to camera, which is the documented `T1` /
MediaPipe issue #5156 landmark collapse. **In the working region (0-30 deg) pitch's
noise is 1.35-2.05 deg p95** -- the same order as roll's 1.61 and yaw's. Confirmed
on BOTH pitch takes.

⚠ **A POOLED STATISTIC ANSWERED A QUESTION ABOUT A REGION, AND IT ANSWERED IT
WRONG.** The owner's premise -- that there is a usable window -- was right, and the
harness that said otherwise was aggregating over the very thing being asked about.

THE METRIC, and why it needs no ground truth:
  * the per-frame delta `dq = q(t) . q(t-1)^-1` is exactly what the new build would
    integrate;
  * split frames by whether the hand is HOLDING (the depth-free truth moves
    < 1 deg/frame) or MOVING;
  * **a hold's delta is PURE ERROR** -- the hand is still, so whatever the pipeline
    reports is what the cube would wrongly integrate. That is the number a window
    must be drawn around.
⚠ p95, not median: rate control integrates the tail.

⛔ WHAT THIS HARNESS DELIBERATELY DOES NOT REPORT. A first version also printed a
signal/noise ratio, using the moving frames as "signal". **It was dropped**: these
takes are SLOW SWEEPS, so the moving-frame delta measures how fast the operator
happened to move -- a property of the take, not of the pipeline. Same trap
`ROTATION_ACCEPTANCE_AND_TRAPS` §7 trap 5 records for width collapse ("measures
SWEEP SIZE, not cleanliness"). The noise column stands alone; what signal the user
supplies is the rate curve's business, not the window's.

✅✅ SUPERSEDED BY THE 2026-08-29 GRIP TAKES, AND THE OLD TEXT IS KEPT BECAUSE THE
GAP IT DESCRIBES IS WHY THEY WERE RECORDED: *"the YAW window CANNOT be placed from
this corpus -- its holds sit at 120-180 deg (n=140) with only 11-12 frames near
face-on."* Three stepped, GRIPPING takes now cover all three axes with ~75 declared
hold frames per angle, and the result is flat:

    p95 noise a STILL hand injects, by declared hold, gripping
      YAW    1.09 - 2.56 deg   (pooled 1.45)
      PITCH  1.09 - 4.77 deg   (pooled 3.14)
      ROLL   1.35 - 2.55 deg   (pooled 1.86)

⚠ THESE DOUBLED ON 2026-08-29, AFTER THE FIRST RUN. `lean_trim_ab.geo_deg`, which
this file imports, returned the geodesic on the quaternion sphere S3 -- half the
ROTATION angle, because S3 double-covers SO(3). Fixed at the source; every number
here is the corrected one. ⭐ The SHAPE is unchanged, and so is every conclusion
drawn from it: a constant factor cannot move a comparison.

⭐⭐ **THERE IS NO WINDOW INSIDE THE RANGE TESTED** -- all three axes are clean and
flat, and GRIPPING is what bought it: the open-hand takes read yaw 7.7-7.8 and
pitch up to 19-27 over the same kind of poses (also corrected). `T6`'s rule paying out a third
time.

⛔⛔ **THE EDGE IS STILL NOT LOCATED, AND THAT IS THE REMAINING GAP.** The grip
takes reached ~57 deg (yaw) and ~75 deg (pitch) of MEASURED pose; the region where
the old corpus collapsed is 120-180 deg, past edge-on. **Nothing here says where the
rate gain must decay** -- only that it need not decay early. A wide-range take
(deferred by the owner, 2026-08-29) is what closes it.

⚠ SAMPLE SIZES ARE PRINTED. A bin marked THIN has under 15 hold frames, where a p95
is barely more than the maximum.

⚠ Past ~120 deg the depth-free truth itself leans on `is_thumb_outward` to unwrap the
`acos` fold -- the chirality bit that is least trustworthy exactly there. ⭐ That
doubt argues the same way the numbers do: outside the window, trust nothing.

⛔⛔ SECOND, AND IT CAME FROM THE OWNER: **THE PITCH TRUTH WAS THE WRONG AXIS.**
*"in my game, the angle is between the fingertips and the basis of the palm"*. That
is not a relabelling -- the palm length is NON-MONOTONE over the first three holds
(1.000 -> 1.023 -> 1.022), so `acos` folded declared 0 / 15 / 30 into one 8-14 deg
bucket. The fingertip axis is monotone throughout and reaches 0.265 (~75 deg) where
the palm reads 0.523 (~58 deg) for the same declared 90. `span(kind="tip_length")`
carries it, and `F1` already uses the same fingertip barycentre for the grip point.
⚠ **YAW is NOT fixed by that axis** -- for yaw the fingertip axis IS the rotation
axis and carries almost no signal (1.000 -> 1.023 in length). Yaw's own compression
has a separate cause: on a GRIPPING (cupped) hand the knuckle row has real depth
extent, so its projected width never collapses and large yaw is under-reported.

⛔ WHAT THE SHIPPED ROTATION PATH ACTUALLY IS, because the window must describe the
signal the build integrates: `Horn(PALM_LANDMARKS)` (x) `lean_trim`. **`tip_trim`
contributes IDENTITY to rotation -- `TRIM_GAIN = 0.0`** -- so the fingertips drive
the object's POSITION and not its rotation. ⭐ `lean_trim` (`V2`) costs **+10% on
the yaw delta noise** (0.72 -> 0.80 deg p95) and exactly nothing on pitch and roll,
where it is correctly silent after the 2026-08-29 double-cover fix.

Stdlib only. Reads the corpus, writes nothing.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Resources"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Resources import palm_rotation as PR                      # noqa: E402
from rotation_accuracy_bands import load, ground_truth, pct          # noqa: E402
from rotation_accuracy_bands import TAKES as LEGACY_TAKES           # noqa: E402
from lean_trim_ab import geo_deg                               # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                           # pragma: no cover
    pass

# ⭐⭐ THE WINDOW TAKES, recorded 2026-08-29 FOR THIS QUESTION. Stepped (so the
# holds are DECLARED, not inferred from a threshold on a noisy truth) and recorded
# with a GRIPPING hand -- `T6`'s closing rule, which cost that row twice: a corpus
# whose MOTION does not match the product's cannot validate an estimator for it.
# Every earlier take in this project's rotation work was an OPEN hand.
#
# ⚠ THE FIRST ROLL ATTEMPT FAILED AND IS DELIBERATELY NOT DELETED:
# `2026-08-29_123147_window_roll_grip` recorded 985 frames with a hand in **0** of
# them -- the take never launched (owner). It is kept on `E:` because a failed take
# is evidence about the protocol, but nothing may be read from it. ✅ Re-recorded
# the same session as `_123725`, which is the one listed below.
TAKES = (
    ("2026-08-29_122958_window_yaw_grip",   "YAW-grip",   (0.0, 1.0, 0.0), "width",  0.0),
    # ⭐⭐ `tip_length`, NOT `length`: the owner's own axis (fingertips to the
    # palm base), which is monotone where the palm length is not. See
    # `rotation_accuracy_bands.span()` for the measured comparison.
    ("2026-08-29_123058_window_pitch_grip", "PITCH-grip", "knuckles",  "tip_length", 0.0),
    ("2026-08-29_123725_window_roll_grip",  "ROLL-grip",  (0.0, 0.0, 1.0), "roll",   0.0),
    # ⚠ The legacy takes are KEPT alongside, never replaced: they are open-hand
    # sweeps measured on a different day and camera placement, so they cannot be
    # compared absolutely -- but if the new gripping takes disagree with them about
    # the SHAPE of the window, that disagreement is the finding.
) + tuple(LEGACY_TAKES)

# ⚠ Stated, not tuned: a frame counts as a HOLD when the depth-free truth moves less
# than this between frames. The truth is depth-free, so the split cannot be
# contaminated by the world-z defect the whole project is working around.
HOLD_STEP_DEG = 1.0
THIN = 15

BINS = ((0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 60),
        (60, 75), (75, 90), (90, 120), (120, 180))


def main():
    print("=" * 78)
    print("DELTA-ORBIT WINDOW -- what a STILL hand injects, by WHERE IT IS")
    print("=" * 78)
    print("  Every degree below would be integrated by a delta-orbit build and never")
    print("  given back. The window is where that number is small.")
    print(f"  HOLD = the depth-free truth moving < {HOLD_STEP_DEG:.0f} deg/frame.")

    for key, axis, expected, kind, head in TAKES:
        session, frames = load(key, head)
        if not frames:
            continue
        ref, truth = ground_truth(frames, kind)
        horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
        st = horn.freeze(frames[ref][0], frames[ref][1])
        if st is None:
            continue
        seq = []
        declared = 0
        for i, (px, wl, _h, step) in enumerate(frames):
            q = horn.delta(st, px, wl)
            if q is not None:
                seq.append((truth[i], q, step))
                if step:
                    declared += 1
        # ⭐⭐ DECLARED BEATS INFERRED, WHEREVER IT EXISTS. A stepped take stamps
        # `hold_*` / `move_*` on every frame, so the hold/move split is what the
        # operator was ASKED for rather than a threshold on a depth-free truth that
        # is ill-conditioned near face-on and leans on the chirality bit past 120.
        # ⚠ Falls back silently for the 400+ takes that predate the stamp -- and
        # says which mode it used, because a harness that quietly changes its own
        # definition between takes is exactly the drift `METHOD` warns about.
        use_declared = declared >= 0.5 * len(seq) and declared > 0
        print(f"\n  {axis}  {session}")
        print("    hold/move split: " + ("DECLARED (%d/%d frames stamped)"
                                         % (declared, len(seq)) if use_declared
              else "inferred (<%.0f deg/frame of truth) -- take carries no step labels"
                   % HOLD_STEP_DEG))

        # ⭐⭐⭐ BIN BY THE DECLARED STEP WHEN THERE IS ONE, NEVER BY THE MEASURED
        # TRUTH -- and this is not a preference, the measured truth CANNOT do the
        # job. On the 2026-08-29 takes, declared vs measured comes out:
        #
        #     declared    0    15    30    45    60    75    90
        #     yaw       8.1  23.2  35.5  44.0  48.8  53.7  56.9   monotone, compressive
        #     pitch    14.5   8.0   8.1  16.3  28.4  36.7  59.6   ⛔ NOT MONOTONE
        #
        # ⛔ Pitch's first three declared angles all read 8-14 deg: `acos` of a
        # foreshortening ratio has infinite slope at 1, so near face-on the truth
        # cannot separate 0 from 30. Binning the noise by that would smear three
        # different poses into one bucket and then report the result as a window.
        # ⭐ The declared label has no such failure -- it is what the operator was
        # asked for, and it is monotone by construction.
        #
        # ⚠⚠ THE DECLARED LABEL IS BALLPARK, AND THE OWNER SAID SO (2026-08-29):
        # *"yaw was from 0 to around 80 degrees (instead of 90). Also, the 10 degrees
        # increment were ballpark, not very accurate."* So the labels below are
        # ORDINAL, not metric: they place the window's SHAPE and its edge, and no
        # number here should be quoted as "the noise at exactly N degrees".
        # ⭐ For a window whose fade is ~15 deg wide that is enough, and it is the
        # honest resolution of a person placing their own hand by eye.
        if use_declared:
            holds = {}
            for i in range(1, len(seq)):
                t0, q0, s0 = seq[i - 1]
                t1, q1, s1 = seq[i]
                if not (s1 and s1.startswith("hold") and s0 == s1):
                    continue
                d = geo_deg(q1, q0)
                if d is not None:
                    holds.setdefault(s1, []).append((d, t1))
            print(f"    {'declared':>10s} {'n':>5s} {'med':>7s} {'p95':>8s} "
                  f"{'max':>8s}   {'(measured)':>10s}")
            print("    " + "-" * 58)
            pooled = []
            for label in sorted(holds, key=lambda s: int(s.split("_")[1])):
                v = [d for d, _t in holds[label]]
                tt = [t for _d, t in holds[label]]
                pooled.extend(v)
                flag = "  <-- THIN" if len(v) < THIN else ""
                print(f"    {label.split('_')[1] + '°':>10s} {len(v):5d} "
                      f"{pct(v, 50):6.2f}° {pct(v, 95):7.2f}° {max(v):7.2f}°"
                      f"   {pct(tt, 50):9.1f}°{flag}")
            if pooled:
                print(f"    POOLED: n={len(pooled)}  med {pct(pooled,50):.2f}°  "
                      f"p95 {pct(pooled,95):.2f}°  max {max(pooled):.2f}°")
            continue

        print(f"    {'hand at':>10s} {'n':>5s} {'med':>7s} {'p95':>8s} {'max':>8s}")
        print("    " + "-" * 44)
        pooled = []
        for lo, hi in BINS:
            noise = []
            for i in range(1, len(seq)):
                t0, q0, s0 = seq[i - 1]
                t1, q1, s1 = seq[i]
                if not (lo <= t1 < hi):
                    continue
                if use_declared:
                    # ⛔ BOTH frames must sit inside the SAME hold. A pair that
                    # straddles a step boundary contains the operator starting to
                    # move, and counting that as noise is the one way a declared
                    # split could score WORSE than the inferred one it replaces.
                    if not (s1 and s1.startswith("hold") and s0 == s1):
                        continue
                elif abs(t1 - t0) >= HOLD_STEP_DEG:
                    continue
                d = geo_deg(q1, q0)
                if d is not None:
                    noise.append(d)
                    pooled.append(d)
            if not noise:
                continue
            flag = "  <-- THIN" if len(noise) < THIN else ""
            print(f"    {lo:4.0f}-{hi:3.0f}° {len(noise):5d} {pct(noise, 50):6.2f}° "
                  f"{pct(noise, 95):7.2f}° {max(noise):7.2f}°{flag}")
        if pooled:
            # ⭐ Printed LAST and deliberately: this is the number that misled, and
            # seeing it beside the bins is the whole lesson of this file.
            print(f"    POOLED over all poses: n={len(pooled)}  "
                  f"med {pct(pooled, 50):.2f}°  p95 {pct(pooled, 95):.2f}°  "
                  f"max {max(pooled):.2f}°")

    print()
    print("  ⚠ The POOLED row is the one that said 'pitch is unusable'. Read the BINS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
