# -*- coding: utf-8 -*-
"""⭐⭐ `RB5` STEP 5 — DRIFT: what the object collects while the hand is STILL.

    .venv/Scripts/python.exe analysis/rb5_drift.py <take-dir> [<take-dir> ...]

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md` §8sexies.

⛔⛔ WHY THIS IS THE MEASUREMENT THAT DECIDES `RB6`. In absolute mode a bad frame is
a bad frame and the next good one recovers. `RB5` INTEGRATES, so **every frame's
error is added to the object permanently**. On the pre-rebuild stack that came to
**43 / 35 / 48 deg per minute** (yaw / pitch / roll) with the hand held still --
and the drift control that hid it (`FREEZE 1` / `RELEASE 60 deg/s`) was STRIPPED by
this branch.

⚠ Those numbers were measured on the OLD frame handling and **do not carry**
(`METHOD`: a constant borrowed from another row's derivation inherits its question).
This harness measures the NEW stack's own.

⭐ AND IT REPORTS AT TWO GAINS, BECAUSE THE GAIN MULTIPLIES THE DRIFT. Gain does not
improve signal-to-noise -- it scales both. At the owner's nominal gains the old
stack's drift would become 129 / 180 / 96 deg/min: a full turn every 20-40 seconds.

────────────────────────────────────────────────────────────────────────────────
⚠ THE TWO NUMBERS, AND WHY BOTH ARE PRINTED

  * **NET** -- where the object actually ENDED UP. This is what a player sees, and
    it is the number comparable to 43/35/48.
  * **PATH** -- the sum of every increment's magnitude. Always larger, because a
    random walk doubles back on itself. ⭐ A large PATH with a small NET means the
    object is JITTERING rather than sliding, which is a different complaint with a
    different fix -- and reporting only NET would hide it.

⛔⛔ AND THE COVERAGE LINE IS NOT OPTIONAL. If the still hand sits OUTSIDE its
window, the gate closes and the drift is trivially zero -- a number that says
nothing about the build. The fraction of frames actually DRIVEN is printed on every
row, and a run under 50% is called out. `METHOD`: print the aggregation, not just
the value.

⚠ Frame rate matters here in a way it did not for the window: this measures a RATE.
Every take of 2026-08-29 ran 8.5-20 fps, under the 20 fps floor, which is fine for
angles and useless for rates.

Stdlib only. Reads the corpus, writes nothing.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_control as HC              # noqa: E402
from Resources import hand_orientation as HO          # noqa: E402
from Resources import hand_pose_window as HPW         # noqa: E402

UNITY = (1.0, 1.0, 1.0)


def load(take_dir):
    with open(os.path.join(take_dir, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    frames = []
    with open(os.path.join(take_dir, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return meta, frames


def is_hold(step):
    """A frame the operator was told to hold STILL. Everything else is motion.

    ⭐ On a take with no `step` field at all -- a plain `static_hold` -- every frame
    is a hold by construction, which is why `None` counts."""
    return step is None or (isinstance(step, str) and step.startswith("hold"))


def run_take(take_dir, gain, label):
    meta, frames = load(take_dir)
    mount = meta.get("declared_mount") or "facing_user"
    ctrl = HC.ObjectRotationControl()
    path = 0.0

    # ⛔⛔ THE CLOCK COUNTS **HOLD TIME ONLY**. The first version measured
    # first-hold to last-hold and divided by that, which silently included every
    # MOVE interval -- and drift only accrues on holds. On the `RB5` sweeps (3 s
    # hold / 2 s move) that under-reports the rate by ~40%, and this rate is the
    # number compared against 43/35/48 to decide whether `RB6` is needed. A drift
    # figure that is 40% low is exactly how a build talks itself out of a fix.
    held_ms = 0.0
    prev_t = None

    for fr in frames:
        t = fr.get("tCapture")
        if not is_hold(fr.get("step")):
            # ⛔ A MOVE frame is not drift, it is the operator. Feeding it in would
            # measure how much the hand moved -- the same trap `delta_orbit_window`
            # records for its dropped signal/noise ratio.
            ctrl.reset()
            prev_t = None
            continue
        hands = fr.get("hands") or []
        if len(hands) != 1:
            # ⛔ NOT `continue`. The live build sees a frame with no usable hand and
            # REFUSES it, dropping the reference; skipping it here would let one
            # increment span the dropout and integrate the re-acquisition jump --
            # so the harness would be measuring a law the product does not run.
            # Feeding `None` exercises the module's own refusal path (`METHOD`: take
            # the thing under test FROM the module).
            ctrl.update(None, gain=gain)
            prev_t = None
            continue
        if t is not None and prev_t is not None:
            held_ms += (t - prev_t)
        prev_t = t
        before = ctrl.orientation
        after = ctrl.update(hands[0].get("world_landmarks"), mount=mount, gain=gain)
        # The increment actually APPLIED, recovered from the two orientations rather
        # than recomputed -- `METHOD`: a harness must not re-implement the thing it
        # checks. `inc = after (x) before^-1`, and for a unit quaternion the
        # conjugate IS the inverse.
        before_inv = (before[0], -before[1], -before[2], -before[3])
        inc = HO.compose(before_inv, after)
        path += HO.angle_deg(inc) if inc else 0.0

    span_s = held_ms / 1000.0
    net = HO.rotvec_deg(ctrl.orientation)
    total = HO.angle_deg(ctrl.orientation)
    driven = ctrl.frames_driven
    denom = max(1, ctrl.frames_driven + ctrl.frames_gated + ctrl.frames_refused)
    cover = 100.0 * driven / denom
    per_min = (60.0 / span_s) if span_s > 1.0 else 0.0

    print("  %-8s NET %+7.1f /%+7.1f /%+7.1f deg  (|%6.1f|)   PATH %8.1f deg   [%.1f s HELD]"
          % (label, net[0], net[1], net[2], total, path, span_s))
    if per_min:
        print("           per MINUTE: pitch %+6.1f  yaw %+6.1f  roll %+6.1f   |net| %6.1f  path %8.1f"
              % (net[0] * per_min, net[1] * per_min, net[2] * per_min,
                 total * per_min, path * per_min))
    else:
        print("           ⚠ no usable timestamps -- cannot express this as a RATE")
    print("           driven %d / %d frames (%.0f%%), gated %d, refused %d"
          % (driven, denom, cover, ctrl.frames_gated, ctrl.frames_refused))
    if cover < 50.0:
        print("           ⛔⛔ UNDER 50%% DRIVEN -- the still hand sits mostly OUTSIDE")
        print("              its window, so this drift number says little about the build.")
    return {"span_s": span_s, "cover": cover, "net": total * per_min if per_min else None}


def main(argv):
    takes = argv[1:]
    if not takes:
        print(__doc__.strip().splitlines()[2])
        print("\n⛔ give one or more take directories.")
        return 2

    print("RB5 STEP 5 -- drift with the hand STILL")
    print("GAIN=%s  CALIBRATED=%s  window CALIBRATED=%s"
          % (HC.GAIN, HC.CALIBRATED, HPW.CALIBRATED))
    if not HPW.CALIBRATED:
        print("⚠ the WINDOW is uncalibrated, so which frames are gated is provisional;")
        print("  re-run this after pasting the calibration constants.")
    print("⚠ baseline to beat, OLD stack: 43 / 35 / 48 deg per minute (yaw/pitch/roll)")

    for t in takes:
        if not os.path.isdir(t):
            print("\n⛔ missing take: %s" % t)
            continue
        meta, _ = load(t)
        fps = meta.get("measured_fps") or 0.0
        print("\n%s" % os.path.basename(t))
        print("  fps=%-6s  mirrored=%s  frames=%s"
              % (fps, meta.get("detection_on_mirrored_frame"), meta.get("frames")))
        if meta.get("detection_on_mirrored_frame"):
            print("  ⛔⛔ MIRRORED CAPTURE -- NON-BINDING for `1.7.42` (see rb5_window_calibration).")
        if fps < 20.0:
            print("  ⛔ UNDER THE 20 fps FLOOR -- this measures a RATE, so the number is soft.")
        run_take(t, UNITY, "gain 1")
        run_take(t, HC.GAIN, "shipped")
    print("\n⭐ NET is what a player sees; PATH is jitter. A large PATH with a small NET")
    print("  is a different complaint -- and a different fix -- from a slide.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
