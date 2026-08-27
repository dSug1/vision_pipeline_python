# -*- coding: utf-8 -*-
"""⭐⭐⭐ IS MEDIAPIPE'S `z` DEPTH-FLIPPED WHEN THE PALM FACES THE CAMERA?

Owner, 2026-08-27: the fingertips of a closing palm-forward hand read +1.07 cm
BEHIND the hand's origin when they must be in FRONT. *"Why does that happen in palm
and not in back? Is it something we can reliably rectify? Would it help the yaw
rotation?"*

⭐ THE HYPOTHESIS. Recovering 3-D from one image carries a **depth-reversal
ambiguity**: a shape and its mirror THROUGH THE IMAGE PLANE project identically
under weak perspective. A flat hand is nearly planar, so "palm toward camera,
fingers curling toward me" and "back toward camera, fingers curling away" look
almost the same in 2-D. \u26a0 If the model has a BIAS toward one branch, it will be
right on one side of the hand and systematically wrong on the other.

────────────────────────────────────────────────────────────────────────────────
\u2b50\u2b50 THE TEST NEEDS NO GROUND TRUTH, WHICH IS WHY IT IS WORTH RUNNING

A hand cannot change chirality. A right hand is a right hand whether you show its
palm or its back. \u2b50 But the SIGNED VOLUME of the 3-D landmarks -- which is what
`geometric_chirality` reads -- **flips sign under a depth reversal**.

So: compute the geometric chirality per frame, split the frames by the 2-D palm/back
cue, and ask whether the answer CHANGES with the side of the hand shown. It must
not. Any flip is the estimator reversing depth, and the take supplies its own
control because the operator's hand is the same hand throughout.

\u26d4 `signed_palm_area` (2-D, pixels) does the splitting and shares no expression
with `signed_palm_volume` (3-D, world z) \u2014 `B4`.

⚠ THIS MAY BE THE SAME DEFECT AS `U7`. The handedness label was measured
**confidently wrong 10.8%** of the time. A depth flip inverts the geometric
chirality, which is exactly what a wrong handedness looks like from the inside. If
the two line up, one cause explains both \u2014 and the yaw lean as well, because Horn
consumes that same `z`.

    .venv/Scripts/python.exe analysis/z_depth_flip.py [session ...]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry as PG                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
DEFAULTS = ("2026-08-27_185142_perlandmark",
            "2026-08-27_181733_pose_rig",
            "2026-08-22_134553_yaw_sweep_constant_depth")

PALM = (0, 5, 9, 13, 17)


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def load(session):
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        return None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            h = (r.get("hands") or [])
            if len(h) != 1:
                continue
            hh = h[0]
            if hh.get("landmarks") and hh.get("world_landmarks"):
                out.append((hh["landmarks"], hh["world_landmarks"], hh.get("handedness")))
    return out


def report(session):
    frames = load(session)
    if not frames:
        print("\n  [%s] not found" % session)
        return None

    # per side: how the 3D signed volume comes out, and how flat the hand reads
    side_sign = {"palm": {"L": 0, "R": 0}, "back": {"L": 0, "R": 0}}
    side_eo = {"palm": [], "back": []}
    labels = {"palm": {}, "back": {}}

    for px, wl, lab in frames:
        if len(wl) < 21:
            continue
        sa = PG.signed_palm_area(px)
        if sa is None or abs(sa) < 1e-9:
            continue
        side = "palm" if sa > 0 else "back"
        ch = PG.geometric_chirality(wl)
        if ch is None:
            continue
        side_sign[side]["L" if ch == "Left" else "R"] += 1
        side_eo[side].append(PG.edge_on_measure(px))
        if lab:
            labels[side][lab] = labels[side].get(lab, 0) + 1

    n_p = sum(side_sign["palm"].values())
    n_b = sum(side_sign["back"].values())
    if n_p < 20 or n_b < 20:
        print("\n  [%s] only palm=%d back=%d -- needs both sides" % (session, n_p, n_b))
        return None

    p_left = side_sign["palm"]["L"] / float(n_p)
    b_left = side_sign["back"]["L"] / float(n_b)

    print("\n  [%s]" % session)
    print("    %-6s %6s | geometric chirality says | MediaPipe label says"
          % ("side", "frames"))
    for side, n, frac in (("palm", n_p, p_left), ("back", n_b, b_left)):
        lab = labels[side]
        labstr = " / ".join("%s %d%%" % (k, round(100.0 * v / max(1, sum(lab.values()))))
                            for k, v in sorted(lab.items())) or "-"
        print("    %-6s %6d | Left %3d%%  Right %3d%%     | %s"
              % (side, n, round(100 * frac), round(100 * (1 - frac)), labstr))
    print("    face-on-ness (edge_on_measure): palm %.2f   back %.2f"
          % (med(side_eo["palm"]), med(side_eo["back"])))
    return p_left, b_left, n_p, n_b


def main():
    sessions = sys.argv[1:] or list(DEFAULTS)
    w = 88
    print("=" * w)
    print("  IS THE WORLD `z` DEPTH-FLIPPED ON ONE SIDE OF THE HAND?")
    print("=" * w)
    print("  A hand cannot change chirality. The SIGNED VOLUME of its 3D landmarks")
    print("  flips sign under a depth reversal -- so if the geometric chirality")
    print("  disagrees with itself between palm-facing and back-facing frames of the")
    print("  SAME hand, the estimator reversed depth on one of them.")

    rows = []
    for s in sessions:
        r = report(s)
        if r:
            rows.append((s, r))

    print()
    print("=" * w)
    print("  VERDICT")
    print("=" * w)
    if not rows:
        print("  no usable session")
        return 1
    flips = []
    for s, (p_left, b_left, n_p, n_b) in rows:
        # "flip" = the two sides give OPPOSITE majority answers
        disagree = (p_left > 0.5) != (b_left > 0.5)
        strength = abs(p_left - b_left)
        flips.append(disagree)
        print("    %-42s palm %3d%% Left vs back %3d%% Left   %s"
              % (s[:42], round(100 * p_left), round(100 * b_left),
                 "\u26d4 OPPOSITE" if disagree else "consistent"))
    print()
    if all(flips):
        print("  \u26d4\u26d4 CONFIRMED: the geometric chirality INVERTS with the side of the")
        print("     hand shown, in every session tested. One hand cannot be both, so")
        print("     the world `z` is DEPTH-REVERSED on one side.")
        print("  \u2b50 It is DETECTABLE without ground truth -- that is what this harness")
        print("     just did -- so it is in principle correctable: negate the")
        print("     out-of-plane component on the offending side.")
        print("  \u26a0 Whether correcting it helps YAW is a separate measurement and must")
        print("     not be assumed: `T6` has four rejected fixes that all looked sound.")
    elif any(flips):
        print("  \u26a0 MIXED. Some sessions invert and some do not, so a blanket sign")
        print("     correction would be wrong. Look at the per-session rows above")
        print("     before building anything.")
    else:
        print("  \u2705 NO INVERSION. The chirality is consistent across both sides, so")
        print("     the fingertip-sign finding is NOT a whole-hand depth reversal.")
        print("     \u2b50 That is a real result: it rules out the simplest explanation and")
        print("     points at a LOCAL error (the fingers) rather than a global flip.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
