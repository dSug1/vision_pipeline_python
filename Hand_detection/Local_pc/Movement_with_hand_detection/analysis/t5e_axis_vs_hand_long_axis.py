"""T5e -- is the tilted yaw axis the ESTIMATOR's bias, or the HAND's own anatomy?

Owner requirement (2026-08-22): "rotation of the hand on the vertical world axis
= equal rotation of the cube in the vertical 2d screen axis". Observed instead: a
mix of screen x and y.

THE COMPETING EXPLANATIONS
---------------------------
  (1) ESTIMATOR BIAS -- the fit systematically mis-orients the axis. Fixing it is
      a correctness change.

  (2) FAITHFUL TRACKING OF A TILTED HAND -- turning a palm edge-on is forearm
      pronation/supination, whose axis runs along the FOREARM, i.e. roughly the
      hand's own LONG axis (wrist -> middle MCP). If the hand is held tilted in
      the image, that axis is tilted from screen-vertical by the same amount, and
      the cube is correctly following the hand. Then the owner's requirement is a
      deliberate REMAPPING, not a bug fix.

These make a sharp, separable prediction:

      (1) the fitted axis sits near screen-vertical plus noise, uncorrelated
          with how the hand happens to be held
      (2) the fitted axis TRACKS the hand's long axis, tilt for tilt

So this measures the in-screen tilt of BOTH and correlates them. The hand's long
axis comes from 2D PIXEL landmarks only -- it never passes through world z, so it
does not share an expression with the quantity it is auditing (the B4 rule).

Reported in the SCREEN PLANE (the owner's frame): the angle of a direction
measured from screen-vertical (+y down), positive toward +x (screen right).

Stdlib only. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5e_axis_vs_hand_long_axis.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_rotation as PR      # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

TAKES = [
    ("2026-08-22_134553_yaw_sweep_constant_depth", "YAW (clean, 2026-08-22)"),
    ("2026-08-04_164647_yaw_sweep_constant_depth", "YAW (contaminated, 2026-08-04)"),
    ("2026-08-04_054702_pitch_sweep_slow",         "PITCH (control)"),
]

MIN_ANGLE = 40.0     # well clear of t5b's small-angle noise floor


def rows(session):
    out = []
    with open(os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            hands = (json.loads(line).get("hands") or [])
            if not hands:
                continue
            h = hands[0]
            px, wl = h.get("landmarks"), h.get("world_landmarks")
            if not px or not wl or len(px) != 21 or len(wl) != 21:
                continue
            out.append((px, wl))
    return out


def screen_tilt(dx, dy):
    """Angle of direction (dx,dy) from the screen VERTICAL axis, in degrees,
    folded to [-90, 90] so a direction and its opposite read the same."""
    a = math.degrees(math.atan2(dx, dy))
    while a > 90.0:
        a -= 180.0
    while a < -90.0:
        a += 180.0
    return a


def axis_of(q):
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, 0.0
    return (x / s, y / s, z / s), math.degrees(2.0 * math.acos(w))


def median(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def main():
    print("=" * 78)
    print("T5e  IS THE TILT THE ESTIMATOR'S, OR THE HAND'S OWN LONG AXIS?")
    print("=" * 78)
    print("  angles are measured IN THE SCREEN PLANE, from screen-VERTICAL,")
    print("  positive toward screen-right. 0 = perfectly vertical.\n")

    for session, label in TAKES:
        data = rows(session)
        if not data:
            print(f"[{label}] no frames\n")
            continue
        horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
        state = horn.freeze(data[0][0], data[0][1])
        fit_tilts, hand_tilts, pairs = [], [], []

        for px, wl in data[1:]:
            # the hand's own long axis, from PIXELS only
            hand_tilts.append(screen_tilt(px[9][0] - px[0][0], px[9][1] - px[0][1]))
            q = horn.delta(state, px, wl)
            if q is None:
                continue
            ax, ang = axis_of(q)
            if ax is None or ang < MIN_ANGLE:
                continue
            ft = screen_tilt(ax[0], ax[1])
            fit_tilts.append(ft)
            pairs.append((hand_tilts[-1], ft))

        print(f"[{label}]  {session}")
        print(f"  hand's own long axis, tilt from screen-vertical : median {median(hand_tilts):+6.1f} deg"
              f"   (n={len(hand_tilts)})")
        if not fit_tilts:
            print("  no frames past the angle floor\n")
            continue
        print(f"  FITTED rotation axis, tilt from screen-vertical : median {median(fit_tilts):+6.1f} deg"
              f"   (n={len(fit_tilts)})")

        # Correlate: does the fitted axis follow the hand as the hand's tilt varies?
        hs = [p[0] for p in pairs]
        fs = [p[1] for p in pairs]
        mh, mf = sum(hs) / len(hs), sum(fs) / len(fs)
        sh = math.sqrt(sum((h - mh) ** 2 for h in hs))
        sf = math.sqrt(sum((f - mf) ** 2 for f in fs))
        if sh > 1e-9 and sf > 1e-9:
            r = sum((h - mh) * (f - mf) for h, f in pairs) / (sh * sf)
            print(f"  correlation(hand tilt, fitted-axis tilt)       : r = {r:+.3f}")
        gap = median(fit_tilts) - median(hand_tilts)
        print(f"  fitted-axis tilt MINUS hand long-axis tilt      : {gap:+6.1f} deg")
        if abs(median(fit_tilts)) > 10.0 and abs(gap) < abs(median(fit_tilts)) * 0.6:
            print("  -> the fitted axis sits NEAR THE HAND'S OWN AXIS, not near vertical:")
            print("     explanation (2), FAITHFUL TRACKING of a tilted hand.")
        else:
            print("  -> the fitted axis does NOT follow the hand's long axis:")
            print("     explanation (1), ESTIMATOR BIAS.")
        print()

    print("=" * 78)
    print("WHY THIS DECIDES THE FIX")
    print("=" * 78)
    print("  If (2): the estimator is correct and the owner's requirement is a")
    print("  deliberate re-expression -- the cube should follow WORLD axes, not the")
    print("  hand's anatomical one. That is a mapping change, and it is well-posed.")
    print("  If (1): find and fix the bias first; a remap would only paper over it.")


if __name__ == "__main__":
    main()
