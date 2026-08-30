# -*- coding: utf-8 -*-
"""⭐⭐⭐ `RB5` STEP 1 — THE ONE MEASUREMENT THAT SETS BOTH THE WINDOW AND THE GAIN.

    .venv/Scripts/python.exe analysis/rb5_window_calibration.py [<take-dir> ...]

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md` §8sexies.

The owner specified `RB5`'s control law in **REAL** hand degrees (2026-08-30):

    pitch +15..+50   yaw 0..+60   roll -45..+45     ->   -90..+90 deg of cube

⛔⛔ AND NOTHING IN THE CODE READS REAL DEGREES. Two different readings stand between
the owner's numbers and the build, and they are compressed against the real angle by
different, non-constant amounts:

    (2) the POSE GATE  -- palm-normal swing + the new roll axis  -> sets the WINDOW
    (3) HORN's DELTA   -- what is actually integrated onto the object -> sets the GAIN

So `180/35 = 5.14` is the gain in REAL degrees and is WRONG applied to a compressed
delta. This harness measures both maps against DECLARED holds and prints the
constants to paste into `Resources/hand_pose_window.py` and the control law.

────────────────────────────────────────────────────────────────────────────────
⭐ WHY A DECLARED-ANGLE TAKE, AND NOT A DERIVED TRUTH

The stepped takes label each hold with the angle the operator was ASKED to hold
(`hold_0` ... `hold_90`). That label IS the ground truth, so this harness needs no
depth-free truth proxy at all -- which matters, because the palm-length proxy the
earlier window work used is **non-monotone over the first three holds** and folded
declared 0 / 15 / 30 into one bucket (`SPEC_DELTA_ORBIT` §8bis, the owner's
correction). A declared label cannot fold.

⚠ The declaration is what the operator was asked for, not a protractor. Treat the
slope as an image of reality good to a few degrees, which is all a soft gate needs.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE TAKE MUST BE UN-MIRRORED, AND THE CORPUS HAS NO SUCH TAKE TODAY.

Every `hold_0..hold_90` take in the corpus was recorded with
`detection_on_mirrored_frame: true`; every UN-mirrored take of 2026-08-29 declares a
DIRECTION (`hold_yaw_pos`) and not an ANGLE. `1.7.42` detects on the un-mirrored
frame, and ⛔ post-hoc un-mirroring is a REJECTED operation -- MediaPipe is measured
**not mirror-equivariant** (7.7-10 mm, 12-20 deg, `REJECTED.md` 2026-08-22), so the
readings from a mirrored take are not a proxy for what this stack will produce.

⭐ This harness therefore RUNS on a mirrored take -- it is a useful instrument check
and shows the shape -- but it marks every number **NON-BINDING** and refuses to emit
a constants block. `CALIBRATED` in `hand_pose_window` stays False until an
un-mirrored take exists.

⚠ METHOD: the pose reading and the orientation are taken FROM their modules; the
declared bookkeeping, the medians and the fit are this harness's own, so it can
still FAIL on the module. It re-implements nothing it checks.

Stdlib only. Reads the corpus, writes nothing.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The Windows console is cp1252; the whole `analysis/` folder does this.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_frame                      # noqa: E402
from Resources import hand_orientation                # noqa: E402
from Resources import hand_pose_window as HPW         # noqa: E402

CORPUS = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# ⭐ One take per axis. The 123147 roll attempt recorded ZERO hands and is excluded
# by name rather than silently by the loader -- a take that produced nothing is a
# fact about the session, not a gap to paper over.
DEFAULT_TAKES = (
    "2026-08-29_122958_window_yaw_grip",
    "2026-08-29_123058_window_pitch_grip",
    "2026-08-29_123725_window_roll_grip",
)

AXIS_INDEX = {"pitch": 0, "yaw": 1, "roll": 2}


def axis_of(sequence):
    for name in AXIS_INDEX:
        if name in (sequence or ""):
            return name
    return None


def pct(values, q):
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    i = q * (len(s) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def load(take_dir):
    meta_path = os.path.join(take_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    frames = []
    with open(os.path.join(take_dir, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            frames.append(json.loads(line))
    return meta, frames


def declared_of(step):
    """`hold_45` -> 45.0, `hold_m45` / `hold_-45` -> -45.0. `None` otherwise.

    ⚠ The `m` spelling exists because a step label rides into a filename-ish field
    and a bare minus has bitten shell tooling here before; both are accepted so a
    recorder change cannot silently drop half a roll take."""
    if not isinstance(step, str) or not step.startswith("hold_"):
        return None
    tail = step[5:]
    if tail[:1] == "m":
        tail = "-" + tail[1:]
    try:
        return float(tail)
    except ValueError:
        return None


def interp(xs, ys, x):
    """Piecewise-linear read of the MEASURED curve at `x`. `(value, extrapolated)`.

    ⭐⭐ DELIBERATELY NOT A GLOBAL STRAIGHT LINE. The dry run showed PITCH is
    strongly non-linear in the declared angle -- the pose reading runs
    -14.3, -1.7, +1.4, +7.4, +16.7, +31.3, +60.1 over declared 0..90, which
    accelerates by a factor of ~5 across the sweep. A single fitted line through
    that mis-places the window edge by more than the fade width, and the edge is
    the whole point. ⚠ The fitted slope is still PRINTED, as a diagnostic of how
    non-linear the axis is -- never as the thing the constants come from."""
    if not xs:
        return (float("nan"), True)
    if x <= xs[0]:
        if len(xs) < 2 or x == xs[0]:
            return (ys[0], x != xs[0])
        t = (x - xs[0]) / (xs[1] - xs[0])
        return (ys[0] + t * (ys[1] - ys[0]), True)
    if x >= xs[-1]:
        if len(xs) < 2 or x == xs[-1]:
            return (ys[-1], x != xs[-1])
        t = (x - xs[-2]) / (xs[-1] - xs[-2])
        return (ys[-2] + t * (ys[-1] - ys[-2]), True)
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return (ys[i] + t * (ys[i + 1] - ys[i]), False)
    return (ys[-1], True)


def fit_line(xs, ys):
    """Least squares `y = a + b x`. Returns `(a, b)` or `None` if degenerate."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-12:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    b = sxy / sxx
    return (my - b * mx, b)


def measure(take_dir):
    meta, frames = load(take_dir)
    axis = axis_of(meta.get("sequence"))
    if axis is None:
        print("  ⛔ cannot tell which axis %r is about -- skipped" % meta.get("sequence"))
        return None
    ai = AXIS_INDEX[axis]
    mirrored = bool(meta.get("detection_on_mirrored_frame"))
    # ⛔⛔ THE MOUNT COMES FROM THE TAKE. The first version let every reading fall
    # through to the process-wide `hand_frame.MOUNT` (env `HAND_MOUNT`), so a
    # `head_worn` take -- or a stale env var in the shell -- would have produced
    # constants for a viewpoint off by `Ry180`, silently.
    mount = meta.get("declared_mount") or hand_frame.FACING_USER

    print("\n%s" % os.path.basename(take_dir))
    print("  axis=%-5s  frames=%-5d  fps=%-6s  mirrored=%s  mount=%s"
          % (axis, len(frames), meta.get("measured_fps"), mirrored, mount))
    if not meta.get("declared_mount"):
        print("  ⚠ the take declares no mount -- assuming %s. Takes recorded before"
              % mount)
        print("    2026-08-29 predate the flag; a wrong guess here is an Ry180 error.")
    if mount != hand_frame.MOUNT:
        print("  ⚠ the take's mount differs from the process default (%s) -- the"
              % hand_frame.MOUNT)
        print("    take wins, as it must, but check HAND_MOUNT is not set by mistake.")
    if mirrored:
        print("  ⛔⛔ MIRRORED CAPTURE -- every number below is NON-BINDING (see header).")
    if (meta.get("measured_fps") or 0) < 20.0:
        print("  ⚠ under the 20 fps floor: fine for angles, useless for rates.")

    # ── the reference: the first usable frame of `hold_0` ─────────────────────
    ref = None
    for fr in frames:
        if declared_of(fr.get("step")) != 0.0:
            continue
        hands = fr.get("hands") or []
        if len(hands) != 1:
            continue
        ref = hand_orientation.freeze(hands[0].get("world_landmarks"), mount=mount)
        if ref is not None:
            break
    if ref is None:
        print("  ⛔ no usable `hold_0` frame -- cannot reference the sweep")
        return None

    buckets = {}
    refused = 0
    for fr in frames:
        declared = declared_of(fr.get("step"))
        if declared is None:
            continue
        hands = fr.get("hands") or []
        if len(hands) != 1:
            continue
        wl = hands[0].get("world_landmarks")
        pose = HPW.pose_angles(wl, mount=mount)
        dq = hand_orientation.delta(ref, wl, mount=mount)
        if pose is None or dq is None:
            refused += 1
            continue
        horn = hand_orientation.rotvec_deg(dq)
        b = buckets.setdefault(declared, {"pose": [], "horn": [], "total": []})
        b["pose"].append(pose[ai])
        b["horn"].append(horn[ai])
        b["total"].append(hand_orientation.angle_deg(dq))

    if not buckets:
        print("  ⛔ no usable hold frames")
        return None

    print("  declared |   n | POSE GATE deg (p50, p5..p95) | HORN %-5s deg (p50) | HORN total"
          % axis)
    xs, pose_ys, horn_ys = [], [], []
    for declared in sorted(buckets):
        b = buckets[declared]
        n = len(b["pose"])
        p50 = pct(b["pose"], 0.50)
        h50 = pct(b["horn"], 0.50)
        t50 = pct(b["total"], 0.50)
        thin = "  ⚠THIN" if n < 15 else ""
        print("    %6.0f | %3d | %8.2f  (%7.2f ..%7.2f) | %14.2f | %9.2f%s"
              % (declared, n, p50, pct(b["pose"], 0.05), pct(b["pose"], 0.95),
                 h50, t50, thin))
        xs.append(declared)
        pose_ys.append(p50)
        horn_ys.append(h50)
    if refused:
        print("  ⚠ %d hold frame(s) refused by the pose reading or the fit" % refused)

    pose_fit = fit_line(xs, pose_ys)
    horn_fit = fit_line(xs, horn_ys)
    if pose_fit is not None:
        print("  POSE  global fit = %+7.2f %+6.3f x declared   ⚠ DIAGNOSTIC ONLY"
              % pose_fit)
    if horn_fit is not None:
        print("  HORN  global fit = %+7.2f %+6.3f x declared   ⚠ DIAGNOSTIC ONLY"
              % horn_fit)

    lo_real, hi_real = HPW.OWNER_WINDOW_REAL_DEG[axis]
    pose_lo, ex1 = interp(xs, pose_ys, lo_real)
    pose_hi, ex2 = interp(xs, pose_ys, hi_real)
    horn_lo, ex3 = interp(xs, horn_ys, lo_real)
    horn_hi, ex4 = interp(xs, horn_ys, hi_real)
    extrapolated = ex1 or ex2 or ex3 or ex4

    horn_span = abs(horn_hi - horn_lo)
    gain = (HPW.OWNER_CUBE_SPAN_DEG / horn_span) if horn_span > 1e-6 else float("inf")

    print("  owner window %+.0f..%+.0f real  ->  %+.2f..%+.2f in POSE units%s"
          % (lo_real, hi_real, min(pose_lo, pose_hi), max(pose_lo, pose_hi),
             "   ⛔ EXTRAPOLATED" if extrapolated else ""))
    if extrapolated:
        print("     ⛔ the take does not BRACKET the owner's window -- record holds at")
        print("        or outside %+.0f and %+.0f, or this edge is a guess."
              % (lo_real, hi_real))
    print("  HORN spans %.2f deg across that window  ->  GAIN = 180 / %.2f = %.3f"
          % (horn_span, horn_span, gain))
    nominal = HPW.OWNER_CUBE_SPAN_DEG / (hi_real - lo_real)
    print("  ⚠ the NOMINAL gain (real degrees) would be %.3f -- a factor %.2f out"
          % (nominal, (gain / nominal) if nominal else float("nan")))

    # ⭐⭐ LOCAL vs GLOBAL slope: how much the axis is NOT a straight line. This is
    # the number behind spec §8sexies-b's warning that a CONSTANT gain can match the
    # full-window sweep or feel uniform locally, but not both.
    local = (horn_hi - horn_lo) / (hi_real - lo_real) if hi_real != lo_real else 0.0
    if horn_fit is not None and abs(horn_fit[1]) > 1e-6:
        print("  ⚠ local slope in-window %+.3f vs global %+.3f -- non-linearity %.2fx"
              % (local, horn_fit[1], abs(local / horn_fit[1])))

    return {
        "axis": axis, "mirrored": mirrored, "mount": mount,
        "pose_window": (min(pose_lo, pose_hi), max(pose_lo, pose_hi)),
        "gain": gain, "pose_fit": pose_fit, "horn_fit": horn_fit,
        "extrapolated": extrapolated,
        "take": os.path.basename(take_dir),
    }


def objections(results, by):
    """Every reason this run must NOT emit a constants block. Empty == safe to paste.

    ⛔⛔ THE GUARD IS THE POINT OF THE PASTE BLOCK. The first version printed
    `CALIBRATED = True` unconditionally -- so a run that measured two axes out of
    three, or read an edge by EXTRAPOLATION, still emitted a block that flips the
    guard while a PLACEHOLDER window survived underneath, and
    `verify_hand_pose_window` §7 would then pass, because the flag says calibrated
    and the constants look like numbers. **A half-calibrated build is worse than an
    uncalibrated one**: the flag is the only thing telling the next session whether
    to trust the window.

    ⭐ A pure function of the results, so the guard can be exercised without a
    camera -- which matters, because the mirrored branch used to return first and
    the other three had never once been run.
    """
    out = []
    if any(r["mirrored"] for r in results):
        out.append("⛔⛔ MIRRORED CAPTURE -- `1.7.42` detects UN-mirrored, and post-hoc\n"
                   "   un-mirroring is a REJECTED operation (MediaPipe is not\n"
                   "   mirror-equivariant: 7.7-10 mm, 12-20 deg). Re-record with\n"
                   "   `--no-mirror --mount facing_user`, in a room bright enough for 20+ fps.")
    missing = [a for a in ("pitch", "yaw", "roll") if a not in by]
    if missing:
        out.append("⛔⛔ NOT MEASURED: %s -- no take for that axis." % ", ".join(missing))
    guessed = sorted(r["axis"] for r in results if r["extrapolated"])
    if guessed:
        out.append("⛔⛔ EXTRAPOLATED, not measured: %s -- the take does not BRACKET\n"
                   "   the owner's window on that axis. Record holds at or outside BOTH edges."
                   % ", ".join(guessed))
    mounts = sorted({r["mount"] for r in results})
    if len(mounts) > 1:
        out.append("⛔⛔ MIXED MOUNTS across the takes (%s) -- one calibration cannot\n"
                   "   describe two viewpoints." % ", ".join(mounts))
    if out:
        out.append("   NO CONSTANTS BLOCK IS EMITTED.")
    return out


def main(argv):
    takes = argv[1:] or [os.path.join(CORPUS, t) for t in DEFAULT_TAKES]
    print("RB5 STEP 1 -- window + gain calibration")
    print("mount=%s  CAPTURE_MIRRORED=%s  pose_window.CALIBRATED=%s"
          % (hand_frame.MOUNT, hand_frame.CAPTURE_MIRRORED, HPW.CALIBRATED))

    results = []
    for t in takes:
        if not os.path.isdir(t):
            print("\n⛔ missing take: %s" % t)
            continue
        r = measure(t)
        if r:
            results.append(r)

    if not results:
        print("\n⛔ nothing measured")
        return 1

    print("\n" + "=" * 78)
    by = {r["axis"]: r for r in results}
    blockers = objections(results, by)
    if blockers:
        # ⭐ EVERY objection is printed, not just the first. A run that is both
        # mirrored AND missing an axis has two things to fix, and surfacing them one
        # per run costs one recording session each.
        for line in blockers:
            print(line)
        print("=" * 78)
        return 2

    print("PASTE INTO Resources/hand_pose_window.py")
    print("=" * 78)
    for axis in ("pitch", "yaw", "roll"):
        r = by[axis]
        print("WINDOW_%s_DEG = (%.1f, %.1f)" % (axis.upper(), r["pose_window"][0],
                                                r["pose_window"][1]))
    print("CALIBRATED = True")
    print("CALIBRATION_SOURCE = %r" % ", ".join(sorted(r["take"] for r in results)))
    print("\n# and PASTE INTO Resources/hand_control.py:")
    print("GAIN = (%.3f, %.3f, %.3f)   # pitch, yaw, roll"
          % (by["pitch"]["gain"], by["yaw"]["gain"], by["roll"]["gain"]))
    print("CALIBRATED = True")
    print("CALIBRATION_SOURCE = %r" % ", ".join(sorted(r["take"] for r in results)))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
