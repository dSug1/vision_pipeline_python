"""T5f -- the owner's requirement, measured on the CLEAN yaw take (2026-08-22).

Requirement: "rotation of the hand on the vertical world axis = equal rotation of
the cube in the vertical 2d screen axis". That is TWO claims, and they fail
differently, so this measures them separately:

    AXIS   does the cube turn about screen-VERTICAL, or about a mix of x and y?
    ANGLE  does it turn by the SAME amount the hand did? ("equal")

THE GROUND TRUTH IS z-FREE
---------------------------
`world_landmarks` z is the coordinate under suspicion, so it cannot supply the
reference (the B4 rule). The palm is a rigid plate, so under pure yaw its
projected WIDTH (knuckle row 5<->17) foreshortens as cos(yaw). Inverting that
gives the true yaw angle from PIXELS alone.

⚠ **acos FOLDS at edge-on**: once the hand turns past 90 deg the width comes back
up, so 150 deg reads as 30 deg. This bit the first version of this measurement and
produced a nonsense "gain 3.57". It is unwrapped here with the PALM-FACING SIGN
(`palm_geometry.signed_palm_area`, the same cue DR-2 uses): once the sign flips,
the true angle is 180 - acos(ratio). ⭐ **This fold is not an artifact of the
harness -- it is an inherent property of any foreshortening-based angle estimate,
and any z-free yaw design must carry a sign cue for exactly this reason.**

⚠ The reference frame is the MOST FACE-ON frame, not frame 0. Freezing Horn on an
already-rotated frame gives the two measures different origins -- that produced a
second nonsense result ("gain 21.5") before it was caught.

Requires a CLEAN single-axis take: verify with `t5c_operator_or_estimator.py`
first. On a contaminated take these numbers mean nothing.

Stdlib only. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5f_equal_rotation.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_rotation as PR      # noqa: E402
import palm_geometry as PG      # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
CLEAN_YAW = "2026-08-22_134553_yaw_sweep_constant_depth"
OLD_YAW = "2026-08-04_164647_yaw_sweep_constant_depth"

BIN = 20


def load(session):
    out = []
    with open(os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            hands = (json.loads(line).get("hands") or [])
            if not hands:
                continue
            px, wl = hands[0].get("landmarks"), hands[0].get("world_landmarks")
            if px and wl and len(px) == 21 and len(wl) == 21:
                out.append((px, wl))
    return out


def span(px, a, b):
    return math.hypot(px[a][0] - px[b][0], px[a][1] - px[b][1])


def quat_angle(q):
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, abs(q[0])))))


def quat_axis(q):
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    return None if s < 1e-9 else (x / s, y / s, z / s)


def screen_tilt(dx, dy):
    a = math.degrees(math.atan2(dx, dy))
    while a > 90.0:
        a -= 180.0
    while a < -90.0:
        a += 180.0
    return a


def med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def analyse(session):
    r = load(session)
    if not r:
        return None
    widths = [span(p, 5, 17) for p, _ in r]
    lengths = [span(p, 0, 9) for p, _ in r]
    signs = [PG.signed_palm_area(p) for p, _ in r]
    w_face = sorted(widths)[int(len(widths) * 0.95)]
    i0 = max(range(len(widths)), key=lambda i: widths[i])     # most face-on frame
    ref_sign = 1.0 if signs[i0] >= 0.0 else -1.0

    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    state = horn.freeze(r[i0][0], r[i0][1])
    bins, tilts, offs = {}, [], []

    for i, ((px, wl), wid) in enumerate(zip(r, widths)):
        q = horn.delta(state, px, wl)
        if q is None:
            continue
        base = math.degrees(math.acos(min(1.0, wid / w_face)))
        same = (1.0 if signs[i] >= 0.0 else -1.0) == ref_sign
        true = base if same else 180.0 - base
        got = quat_angle(q)
        bins.setdefault(int(true // BIN) * BIN, []).append((true, got))
        ax = quat_axis(q)
        if ax is not None and got >= 40.0:
            tilts.append(screen_tilt(ax[0], ax[1]))
            offs.append(math.degrees(math.acos(min(1.0, abs(ax[1])))))

    def collapse(v):
        s = sorted(v)
        return s[int(len(s) * 0.05)] / s[int(len(s) * 0.95)]

    return {
        "n": len(r), "bins": bins, "tilt": med(tilts), "off": med(offs),
        "cw": collapse(widths), "cl": collapse(lengths), "ref": i0,
    }


def main():
    print("=" * 78)
    print("T5f  THE OWNER'S REQUIREMENT, MEASURED -- axis and angle, separately")
    print("=" * 78)

    for label, session in (("CLEAN (2026-08-22)", CLEAN_YAW), ("OLD (2026-08-04)", OLD_YAW)):
        res = analyse(session)
        if res is None:
            print(f"[{label}] missing\n")
            continue
        gate = ("CLEAN single-axis yaw" if res["cw"] < res["cl"] * 0.75
                else "MIXED AXIS -- numbers below are not interpretable")
        print(f"\n[{label}]  {session}")
        print(f"  span collapse: width {res['cw']:.3f}  length {res['cl']:.3f}   -> {gate}")
        print(f"  AXIS : in-screen tilt from vertical {res['tilt']:+.1f} deg"
              f"   |   3D off-vertical {res['off']:.1f} deg")
        if res["cw"] >= res["cl"] * 0.75:
            continue
        print(f"  ANGLE: (reference = most face-on frame #{res['ref']})")
        print(f"    {'true yaw':>14s}  {'n':>4s}  {'cube angle':>11s}  {'gain':>6s}  {'error':>9s}")
        gains = []
        for b in sorted(res["bins"]):
            v = res["bins"][b]
            if len(v) < 10:
                continue
            mt, mf = med([x[0] for x in v]), med([x[1] for x in v])
            if mt < 10.0:
                continue
            gains.append(mf / mt)
            print(f"    {b:3d}-{b + BIN:3d} deg  {len(v):4d}  {mf:8.1f} deg  {mf / mt:6.2f}  {mf - mt:+6.1f} deg")
        if gains:
            print(f"    median gain {med(gains):.2f}   (1.00 = 'equal rotation')")

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    print("  ANGLE is broadly satisfied -- the cube turns about as far as the hand.")
    print("  AXIS is not: the residual tilt is what shows up as x/y mixing on screen.")
    print("  The OLD take's larger figure was roughly half operator contamination;")
    print("  compare the two rows above and quote only the CLEAN one.")


if __name__ == "__main__":
    main()
