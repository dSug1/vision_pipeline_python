"""T5i -- does DOWN-WEIGHTING MediaPipe's world z fix the rotation-axis tilt?

⭐⭐ THE LEAD (spec §14.3.4.8, 2026-08-23). On a clean yaw take the fitted axis
tilt scales monotonically with how much the Horn fit trusts world z: multiplying
world z by `k` gives 13.0 deg of tilt at k=1.0 (what ships) and 3.7 deg at k=0.4 --
which would cut the object's VISIBLE LEAN from 23.4 deg to 6.6 deg. It is the
first lever ever found that moves this defect.

⛔⛔ AND THE OBVIOUS WAY IT DIES: **z is what makes PITCH observable at all.** Under
pitch the knuckle row stays put and the hand rotates INTO the screen, so a fit that
ignores depth has almost nothing left to measure. If `k` fixes yaw by destroying
pitch, it is not a fix -- it is moving the defect. **That is what this harness
exists to find out, and a negative result here closes the lead for good.**

⚠ THE TWO AXES NEED DIFFERENT GROUND TRUTH, both z-free (the B4 rule -- a metric
must not share an expression with what it is judging):
  * YAW   foreshortens palm WIDTH  (5<->17), leaves length alone
  * PITCH foreshortens palm LENGTH (0<->9),  leaves width alone
⚠ Both fold at 90 deg (`acos` comes back down), which has produced nonsense gains
of 3.57 and 2.41 in two separate sessions. Both are unwrapped here with DR-2's
palm-facing sign, which is the documented requirement (§14.3.4.2).

Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5i_zscale_sweep.py
"""

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Resources"))
import palm_rotation as PR          # noqa: E402
import palm_geometry as PG          # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 5, 9, 17
MIN_ANGLE_DEG = 40.0                 # the axis noise floor, with headroom
K_SWEEP = (1.00, 0.85, 0.60, 0.40, 0.20, 0.00)

# ⛔⛔ THE EXPECTED AXIS FOR PITCH IS **NOT** A FIXED HORIZONTAL, and assuming it
# was produced 45.7 deg on one pitch take against 17.7 deg on another -- both
# absurd next to the 5.0 deg that §14.3.4 documents. **Pitch rotates about the
# KNUCKLE ROW**, which is horizontal only if the hand happens to be held upright,
# and hand posture differs between takes. So the expectation is MEASURED from the
# reference frame's own anatomy (index_MCP -> pinky_MCP, in the image plane).
# ⭐ This is the same correction §14.3.4.1 applied to yaw when it checked the
# fitted axis against the hand's long axis instead of assuming screen-vertical.
#
# ⚠ YAW keeps the fixed WORLD VERTICAL, deliberately: that is the owner's stated
# requirement in their own words -- "rotation of the hand on the vertical world
# axis = equal rotation of the cube in the vertical 2d screen axis" -- and the
# hand was measured near-upright (+4.7 deg) on that take, so anatomy and world
# agree there anyway.
#
# session substring -> (axis name, expected axis or "knuckle-row", span)
TAKES = [
    ("2026-08-22_134553_yaw_sweep",   "YAW",   (0.0, 1.0, 0.0), "width"),
    ("2026-08-04_054702_pitch_sweep", "PITCH", "knuckles", "length"),
    ("2026-08-02_191816_pitch_sweep", "PITCH", "knuckles", "length"),
    ("2026-08-04_054109_known_right_back", "PITCH", "knuckles", "length"),
    ("2026-08-03_165518_palm_back",   "PITCH", "knuckles", "length"),
]


def pct(xs, p):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def axis_angle(q):
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    ang = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, math.degrees(ang)
    return (x / s, y / s, z / s), math.degrees(ang)


def _resolution(session):
    """⚠ PnP needs the CAPTURE resolution -- a wrong focal lands on exactly the
    out-of-plane component T6 exists to fix, so read it, never assume it."""
    try:
        with open(os.path.join(CAPTURE, session, "meta.json"), encoding="utf-8") as fh:
            r = json.load(fh).get("resolution")
        if r and len(r) == 2 and r[0] and r[1]:
            return (int(r[0]), int(r[1]))
    except (OSError, ValueError, TypeError):
        pass
    return (640, 480)


def load(key):
    m = [d for d in sorted(os.listdir(CAPTURE)) if key in d]
    if not m:
        return None, []
    p = os.path.join(CAPTURE, m[-1], "raw_landmarks.jsonl")
    if not os.path.isfile(p):
        return m[-1], []
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    out = []
    for r in rows:
        hs = r.get("hands") or []
        if len(hs) != 1:
            continue
        h = hs[0]
        px, wl = h.get("landmarks"), h.get("world_landmarks")
        if px and wl and len(px) >= 21 and len(wl) >= 21:
            out.append((px, wl, h.get("handedness", "Right")))
    return m[-1], out


def span(px, kind):
    if kind == "width":
        return math.hypot(px[INDEX_MCP][0] - px[PINKY_MCP][0],
                          px[INDEX_MCP][1] - px[PINKY_MCP][1])
    return math.hypot(px[WRIST][0] - px[MIDDLE_MCP][0],
                      px[WRIST][1] - px[MIDDLE_MCP][1])


def ground_truth(frames, kind):
    """Z-free rotation magnitude from foreshortening, UNWRAPPED past edge-on."""
    ref = max(range(len(frames)), key=lambda i: span(frames[i][0], kind))
    s0 = span(frames[ref][0], kind)
    sign0 = PG.is_thumb_outward(frames[ref][0], frames[ref][2])
    truth = []
    for px, _wl, hd in frames:
        a = math.degrees(math.acos(max(-1.0, min(1.0, span(px, kind) / s0))))
        if PG.is_thumb_outward(px, hd) != sign0:
            a = 180.0 - a               # past edge-on: acos folds, unwrap it
        truth.append(a)
    return ref, truth


def main():
    print("=" * 86)
    print("T5i -- z-scale sweep: does trusting world z LESS fix the axis tilt?")
    print("=" * 86)
    print(f"  frames below {MIN_ANGLE_DEG:.0f} deg of rotation are excluded (axis noise floor)")
    print("  k = 1.00 is what SHIPS today.")

    for key, axis_name, expected, kind in TAKES:
        name, frames = load(key)
        if not frames:
            print(f"\n  -- {key}: no single-hand frames, skipped")
            continue
        seq = [(px, wl) for px, wl, _h in frames]
        ref, truth = ground_truth(frames, kind)
        exp = expected
        if exp == "knuckles":
            px0 = frames[ref][0]
            dx = px0[PINKY_MCP][0] - px0[INDEX_MCP][0]
            dy = px0[PINKY_MCP][1] - px0[INDEX_MCP][1]
            n = math.hypot(dx, dy) or 1.0
            exp = (dx / n, dy / n, 0.0)

        print(f"\n  {axis_name}  {name}   ({len(seq)} frames, true rotation reaches "
              f"{max(truth):.0f} deg)")
        print(f"    {'arm':>5s}  {'MEAN-axis':>9s}  {'MEDIAN/fr':>9s}  {'gain':>7s}  {'n':>5s}")
        print("    " + "-" * 48)
        # ⭐ T6's arm is scored by the SAME code as the k sweep, deliberately.
        # Trap #3 (two harnesses aggregating differently under one name) reported
        # pitch as "45-55 deg, broken" once; a separate A/B script would risk it
        # again, so `planar_pnp` is just another row here.
        arms = [(f"{k:5.2f}", PR.Horn(PR.PALM_LANDMARKS, "ref"), k) for k in K_SWEEP]
        res = _resolution(name)
        arms.append(("  PnP", PR.PlanarPnP(frame_size=res), None))
        # ⭐⭐ T6b: Horn UNCHANGED, fed geometrically gated world z. Keeps the
        # five-point averaging that makes Horn stable, removes only the bias.
        arms.append((" GATE", PR.GatedHorn(), None))
        # ⭐⭐ T6c: Horn UNCHANGED, fed a palm normal rebuilt from the two halves
        # measured to be reliable -- bearing+sign from MediaPipe, MAGNITUDE from
        # depth-free foreshortening.
        arms.append((" REBLD", PR.RebuiltNormalHorn(), None))
        # ⭐⭐ THE 6-POINT ARMS. A PLANAR model is degenerate for depth-from-2D by
        # construction; THUMB_CMC sits off that plane and breaks it. Its OFF-PLANE
        # depth is the one quantity face-on 2D cannot reveal, so it is SWEPT rather
        # than assumed -- if the result is flat across the sweep, the thumb is not
        # doing the work and the idea is dead; if it peaks, that peak is a measured
        # constant and a candidate for the owner's per-user harvest.
        # ⭐⭐ THE CONDITIONING-AWARE REFERENCE. T6 froze its reference at the MOST
        # FACE-ON frame -- trap #2's rule, correct for Horn and exactly backwards for
        # a planar PnP, whose degeneracy IS face-on. This arm migrates to a
        # better-conditioned reference as soon as the hand offers one.
        arms.append(("PnPRR", PR.PlanarPnP(frame_size=res, reref=True), None))
        arms.append(("T60RR", PR.PlanarPnP(frame_size=res, with_thumb=True,
                                           thumb_z_m=0.060, reref=True), None))
        for label, est, k in arms:
            if k is None:
                s2 = seq          # ⭐ PnP never reads world z; nothing to scale
            else:
                s2 = [(px, [(x, y, z * k) for x, y, z in wl]) for px, wl in seq]
            horn = est
            st = horn.freeze(*s2[ref])
            if st is None:
                print(f"    {label}  REFUSED -- degenerate reference")
                continue
            # ⚠⚠ TWO DIFFERENT QUESTIONS, AND CONFLATING THEM COST A FALSE ALARM.
            # `t5_rotation_axis_fidelity.py` averages the per-frame axes FIRST and
            # reports how far that MEAN axis sits from the expected one -- which is
            # where the documented "pitch 5.0 deg" comes from. This harness's other
            # column is the MEDIAN PER-FRAME deviation, which also carries the
            # frame-to-frame SCATTER. Both are legitimate; they are not the same
            # number, and reading one against the other reported pitch as 45-55 deg
            # "broken" when the mean axis is fine.
            #   MEAN  = is the axis pointing the right way on average?  (bias)
            #   MED   = how far off is a TYPICAL frame?                 (bias+scatter)
            devs, gains, axes = [], [], []
            for i, (px, wl) in enumerate(s2):
                d = horn.delta(st, px, wl)
                if d is None:
                    continue
                ax, ang = axis_angle(d)
                if ax is None:
                    continue
                # deviation from the EXPECTED axis, sign-folded
                dot = abs(ax[0] * exp[0] + ax[1] * exp[1] + ax[2] * exp[2])
                if ang >= MIN_ANGLE_DEG:
                    devs.append(math.degrees(math.acos(max(-1.0, min(1.0, dot)))))
                    a = ax
                    if axes and sum(p * q for p, q in zip(a, axes[0])) < 0.0:
                        a = (-a[0], -a[1], -a[2])   # fold onto one hemisphere
                    axes.append(a)
                if 40.0 <= truth[i] <= 140.0:
                    gains.append(ang / truth[i])
            mdev = float("nan")
            if axes:
                mx = sum(a[0] for a in axes) / len(axes)
                my = sum(a[1] for a in axes) / len(axes)
                mz = sum(a[2] for a in axes) / len(axes)
                n = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
                mdot = abs((mx * exp[0] + my * exp[1] + mz * exp[2]) / n)
                mdev = math.degrees(math.acos(max(-1.0, min(1.0, mdot))))
            print(f"    {label}  {mdev:9.1f}  {pct(devs,50):9.1f}  "
                  f"{pct(gains,50):7.2f}  {len(devs):5d}")

    print()
    print("  MEAN-axis = bias only (comparable to t5_rotation_axis_fidelity's numbers).")
    print("  MEDIAN/fr = bias + per-frame scatter, i.e. what a single frame looks like.")
    print("  k helps only if YAW improves WITHOUT PITCH degrading, gain staying near 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
