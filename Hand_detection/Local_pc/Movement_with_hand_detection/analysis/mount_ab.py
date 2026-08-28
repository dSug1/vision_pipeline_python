# -*- coding: utf-8 -*-
"""⭐⭐ THE CAMERA-MOUNT A/B, ON A REAL RECORDING — does the switch take EFFECT?

    .venv/Scripts/python.exe analysis/mount_ab.py <session> [<session> ...]

⛔⛔ WHY THIS EXISTS, AND WHY IT IS NOT OPTIONAL. `F1`'s TAKE 1 WAS VOID: two
module-global gates left two A/B panels **bit-identical (0.00 px)**, because the
switch had been verified where it was SET rather than where it took EFFECT. The
golden vectors in `verify_camera_mount.py` prove the MATHS; they cannot prove the
wiring. This replays recorded hands through the SHIPPED estimator and reports what
actually changes.

⭐ It needs NO CAMERA and NO live session — it reads `raw_landmarks.jsonl` from the
corpus, so it can be run before the owner ever looks at the screen.

────────────────────────────────────────────────────────────────────────────────
WHAT IT REPORTS, AND WHAT WOULD FALSIFY THE DESIGN

1. **Per-axis rotation.** The hand's own orientation is decomposed about the three
   camera axes. The claim is `yaw REVERSES, pitch REVERSES, roll DOES NOT`.
   ⛔ Roll changing sign, or yaw not changing, refutes the whole diagnosis.

2. **The angle is preserved exactly.** A viewpoint change may not make the hand
   turn further. ⛔ Any drift here means the conjugation is not a rotation.

3. **Z-translation direction.** For the recorded palm-span ratios, which way the
   held object's depth moves. The claim is that `facing_user` inverts it and
   leaves the units alone (still metres from the camera, still positive).

⚠ This measures DIRECTION, not quality. It cannot tell you the new feel is better
-- only the owner's eyes can, in both tools (`METHOD.md`). It exists to rule out
the one failure this project has actually suffered: a switch that changes nothing.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import camera_mount as CM                      # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass


def axis_angles_deg(q):
    """Signed rotation about each camera axis, from the quaternion's vector part.

    ⚠ Deliberately NOT Euler angles: `M6a` forbids Euler in the estimation path,
    and a decomposition is not needed here -- the vector part of a unit quaternion
    is `sin(theta/2) * axis`, so its components carry exactly the per-axis SIGN
    and relative magnitude this harness is asking about."""
    w, x, y, z = q
    s = 2.0 * math.degrees(math.atan2(math.sqrt(x * x + y * y + z * z), abs(w)))
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return 0.0, 0.0, 0.0, 0.0
    sgn = 1.0 if w >= 0.0 else -1.0
    return (sgn * x / n * s, sgn * y / n * s, sgn * z / n * s, s)


def run(session):
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.isfile(path):
        print("  no raw_landmarks.jsonl for %s" % session)
        return None

    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    states, rows = {}, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                frame = json.loads(line)
            except ValueError:
                continue
            for h in frame.get("hands") or []:
                w = h.get("world_landmarks")
                px = h.get("landmarks")
                if not w or not px:
                    continue
                key = h.get("trackId", h.get("handedness"))
                if key not in states:
                    states[key] = horn.freeze(px, w)
                st = states[key]
                if st is None:
                    continue
                q = horn.delta(st, px, w)
                if q is None:
                    continue
                rows.append((CM.user_view_quat(q, CM.LEGACY),
                             CM.user_view_quat(q, CM.FACING_USER)))
    if not rows:
        print("  %-34s no fittable hand frames" % session)
        return None

    # --- 1 & 2: rotation ---------------------------------------------------
    flip = {"pitch(x)": [0, 0], "yaw(y)": [0, 0], "roll(z)": [0, 0]}
    worst_angle = 0.0
    for qa, qb in rows:
        ax, ay, az, sa = axis_angles_deg(qa)
        bx, by, bz, sb = axis_angles_deg(qb)
        worst_angle = max(worst_angle, abs(sa - sb))
        for name, a, b in (("pitch(x)", ax, bx), ("yaw(y)", ay, by), ("roll(z)", az, bz)):
            if abs(a) < 1.0:          # below 1 deg the sign is noise, not motion
                continue
            flip[name][1] += 1
            if a * b < 0:
                flip[name][0] += 1

    print("  %s   (%d fitted frames)" % (session, len(rows)))
    for name in ("yaw(y)", "pitch(x)", "roll(z)"):
        n, tot = flip[name]
        pct = 100.0 * n / tot if tot else float("nan")
        want = "REVERSE" if name != "roll(z)" else "hold"
        good = (pct > 99.0) if name != "roll(z)" else (pct < 1.0)
        print("      %-9s sign reversed on %6.2f%% of %5d frames >1deg   want %-7s  %s"
              % (name, pct, tot, want, "OK" if good else "<<< UNEXPECTED"))
    print("      total rotation ANGLE preserved to %.3e deg (must be ~0)" % worst_angle)
    return worst_angle


def depth_direction():
    print("\n  Z-TRANSLATION DIRECTION (recorded ratios, grab anchor 0.50 m)")
    print("      %-8s %-12s %-12s %s" % ("ratio", "legacy", "facing_user", "meaning"))
    for r, meaning in ((1.40, "hand nearer the camera = AWAY from a facing user"),
                       (0.70, "hand further from the camera = TOWARD that user"),
                       (1.00, "the grab frame itself -- must not move")):
        a = CM.depth_from_ratio(0.50, r, CM.LEGACY)
        b = CM.depth_from_ratio(0.50, r, CM.FACING_USER)
        print("      %-8.2f %-12.4f %-12.4f %s" % (r, a, b, meaning))
    print("      \u26a0 both columns are METRES FROM THE CAMERA and stay positive --")
    print("        only the DIRECTION the hand drives them changes.")


def main():
    sessions = sys.argv[1:]
    if not sessions:
        print(__doc__.strip().splitlines()[2])
        return 2
    print("=" * 78)
    print("CAMERA-MOUNT A/B  --  legacy vs facing_user, on recorded hands")
    print("=" * 78)
    worst = 0.0
    for s in sessions:
        w = run(s)
        if w is not None:
            worst = max(worst, w)
    depth_direction()
    print("\n" + "=" * 78)
    ok = worst < 1e-6
    print("ANGLE PRESERVED across every session (worst %.3e deg)" % worst if ok
          else "*** ANGLE NOT PRESERVED (worst %.3e deg) -- not a rotation ***" % worst)
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
