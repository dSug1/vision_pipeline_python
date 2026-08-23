"""T5g -- the CUBE's rotation axis, read from what the renderer actually used.

⭐⭐ WHY THIS IS DIFFERENT FROM `t5_rotation_axis_fidelity.py` / `t5f_equal_rotation.py`.
Those RE-DERIVE the estimator's rotation from the recorded landmarks. This one reads
the cube's own orientation quaternion, which both recorders have written since
`recorder_schema: 2`. ⚠ A re-derivation is a second implementation that can silently
disagree with the real one, and on 2026-08-23 that cost four reverted builds. The
owner's complaint is about THE CUBE ON SCREEN, so the cube's own orientation is the
right quantity to measure -- not a reconstruction of it.

WHAT IT ANSWERS
---------------
Spec §14.3.4.2 left exactly one question open: the yaw axis is tilted **13.0°** off
vertical, every code-side cause has been eliminated (mirror, frame convention,
constellation degeneracy, hand anatomy, the Horn fit itself), and the remaining
candidates are **MediaPipe's world-z error** and **residual operator wobble** -- a
freehand "pure" yaw can plausibly carry ~10° on its own.

⭐ THE TAKE THIS IS WRITTEN FOR removes the wobble candidate by CONTROL rather than
by argument: the operator holds a flat card clamped at the BASE of the index and
middle fingers -- i.e. on the rigid palm plate the Horn fit actually uses
(landmarks 0, 5, 9, 13, 17) -- with its plane parallel to the palm and its long
edge VERTICAL. Under a pure yaw a vertical card stays vertical, so any lean is
visible to the operator AS IT HAPPENS and can be corrected in the moment.

⚠ THE CARD IS NOT IN THE FILE. Recordings store landmarks, never pixels (N14). The
card is an operator-control device and a live visual reference; the cleanliness
gate below is what tells us, from the data, whether the control worked.

⚠ THE NOISE FLOOR IS BINDING (§14.3.4.2). Below ~30° of rotation the axis is barely
determined -- a *clean* pitch take reads 44-63° off its own axis there. Frames below
`MIN_ANGLE_DEG` are excluded from every axis statistic, and the threshold is printed
so no number can be quoted without it.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5g_cube_axis_from_recording.py <session> [skip_head_s] [skip_tail_s]
"""

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Resources"))
import palm_geometry as PG          # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# Below this the axis is not determined -- see §14.3.4.2's noise floor.
MIN_ANGLE_DEG = 30.0

WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 5, 9, 17


def pct(xs, p):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def axis_angle(q):
    """(unit axis, angle_deg) of a quaternion, canonicalised to a positive angle."""
    w, x, y, z = q
    if w < 0.0:                       # same rotation, positive angle
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    ang = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, math.degrees(ang)
    return (x / s, y / s, z / s), math.degrees(ang)


def main():
    if len(sys.argv) < 2:
        print("usage: t5g_cube_axis_from_recording.py <session substring> [skip_head_s] [skip_tail_s]")
        return 2
    key = sys.argv[1]
    head_s = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    tail_s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

    matches = [d for d in sorted(os.listdir(CAPTURE)) if key in d]
    if not matches:
        print("no session matching", key)
        return 1
    session = matches[-1]
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not rows:
        print("empty session")
        return 1

    t_end = rows[-1].get("tCapture", 0.0)
    lo, hi = head_s * 1000.0, t_end - tail_s * 1000.0
    kept = [r for r in rows if lo <= r.get("tCapture", 0.0) <= hi]

    print("=" * 84)
    print("T5g -- CUBE ROTATION AXIS, FROM THE RECORDED ORIENTATION")
    print("=" * 84)
    print(f"  session : {session}")
    print(f"  frames  : {len(rows)} total, {len(kept)} kept "
          f"(trimmed {head_s:.0f} s head / {tail_s:.0f} s tail, "
          f"operator: 'I was not really on position then')")
    print(f"  window  : {lo/1000.0:.1f} s .. {hi/1000.0:.1f} s of {t_end/1000.0:.1f} s")

    # ---- 1. CLEANLINESS GATE (2D pixels only -- never touches world z, so it does
    #         not share an expression with what it is auditing: the B4 rule).
    #         A rigid plate foreshortens the dimension PERPENDICULAR to its axis.
    #         A clean YAW collapses palm WIDTH and leaves palm LENGTH alone.
    widths, lengths = [], []
    for r in kept:
        for h in r.get("hands") or []:
            lm = h.get("landmarks")
            if not lm or len(lm) < 18:
                continue
            widths.append(math.hypot(lm[INDEX_MCP][0] - lm[PINKY_MCP][0],
                                     lm[INDEX_MCP][1] - lm[PINKY_MCP][1]))
            lengths.append(math.hypot(lm[WRIST][0] - lm[MIDDLE_MCP][0],
                                      lm[WRIST][1] - lm[MIDDLE_MCP][1]))
    if not widths:
        print("\n  no hand frames in the window -- nothing to measure")
        return 1
    wc = pct(widths, 5) / pct(widths, 95)
    lc = pct(lengths, 5) / pct(lengths, 95)
    print()
    print("  1. CLEANLINESS GATE -- was this actually a single-axis yaw?")
    print(f"     palm WIDTH  collapse p5/p95 : {wc:.3f}   (want LOW -- yaw foreshortens width)")
    print(f"     palm LENGTH collapse p5/p95 : {lc:.3f}   (want HIGH -- yaw leaves length alone)")
    # ⛔⛔ READ THE TWO NUMBERS SEPARATELY -- THEY MEAN DIFFERENT THINGS, and an
    # earlier version of this gate conflated them and called a clean-but-SHORT
    # sweep "pitch contaminated". That was wrong, and it is the same class of
    # error as every other instrument mistake this project has logged.
    #
    #   WIDTH collapse  measures HOW FAR the hand turned, not how cleanly.
    #     A pure yaw of A degrees collapses width to ~cos(A) BY CONSTRUCTION:
    #     50 deg -> 0.64, 70 deg -> 0.34, past 90 deg -> ~0.
    #     So a high number means a SMALL SWEEP, not a dirty one.
    #   LENGTH collapse measures CONTAMINATION, and it is sweep-independent.
    #     A pure yaw leaves palm length alone at any magnitude, so ~1.0 is clean
    #     and anything well below it is pitch mixed in.
    sweep_deg = math.degrees(math.acos(max(-1.0, min(1.0, wc))))
    pitch_deg = math.degrees(math.acos(max(-1.0, min(1.0, lc))))
    print(f"     -> implied YAW sweep from face-on : ~{sweep_deg:.0f} deg  (from width)")
    print(f"     -> implied PITCH contamination    : ~{pitch_deg:.0f} deg  (from length)")
    print("     reference: 2026-08-22 clean 0.219 / 0.751 ; 2026-08-04 mixed 0.629 / 0.670")
    print(f"     -> CLEANLINESS: {'GOOD' if lc >= 0.75 else 'CONTAMINATED'} "
          f"(length {lc:.3f} vs the clean take's 0.751)")
    print(f"     -> SWEEP SIZE : {'ADEQUATE' if wc <= 0.45 else 'TOO SMALL'} "
          f"(width {wc:.3f}; the clean take reached 0.219 by going past edge-on)")

    # ---- 2. THE CUBE'S OWN AXIS, from the recorded quaternion.
    # Reference = the cube's orientation on the first frame it is held in the
    # window. Every later orientation is expressed relative to it, which is
    # exactly the delta the hand applied.
    # ⛔⛔ THE REFERENCE MUST BE THE MOST FACE-ON FRAME, NEVER THE FIRST ONE.
    # §14.3.4.2 records this trap explicitly: a previous pass "produced 'gain 21.5'
    # by freezing the estimator's reference on an already-rotated frame rather than
    # the most face-on one". The first frame of a trimmed window is arbitrary --
    # the operator can be mid-sweep -- and referencing it rotates every measured
    # axis by however far off face-on that frame happened to be.
    # Face-on = maximum palm WIDTH: yaw foreshortens width, so the widest frame is
    # the squarest one. 2D pixels only, so it shares no expression with the
    # quaternion it is selecting a reference for (the B4 rule).
    best_t, best_w = None, -1.0
    for r in kept:
        for h in r.get("hands") or []:
            lm = h.get("landmarks")
            if not lm or len(lm) < 18:
                continue
            w = math.hypot(lm[INDEX_MCP][0] - lm[PINKY_MCP][0],
                           lm[INDEX_MCP][1] - lm[PINKY_MCP][1])
            if w > best_w:
                best_w, best_t = w, r.get("tCapture", 0.0)

    per_cube = {}
    for r in kept:
        cubes = r.get("cubes") or {}
        for arm, objs in cubes.items():
            if not isinstance(objs, dict):
                continue
            for name, o in objs.items():
                if not isinstance(o, dict) or o.get("owner") is None:
                    continue
                q = tuple(o.get("orientation") or ())
                if len(q) != 4:
                    continue
                per_cube.setdefault(name, []).append((r.get("tCapture", 0.0), q,
                                                      o.get("depth_m")))

    if not per_cube:
        print("\n  NO HELD CUBE in the window -- nothing was grabbed, so nothing is tested.")
        return 1

    for name, seq in sorted(per_cube.items(), key=lambda kv: -len(kv[1])):
        # the held frame closest in time to the most face-on frame
        ref = min(seq, key=lambda e: abs(e[0] - best_t)) if best_t is not None else seq[0]
        q0 = ref[1]
        tilts_screen, tilts_3d, angles = [], [], []
        for _t, q, _d in seq:
            d = qmul(q, qconj(q0))
            axis, ang = axis_angle(d)
            if axis is None or ang < MIN_ANGLE_DEG:
                continue
            ax, ay, az = axis
            if ay < 0.0:                      # vertical is +/-y; fold to one side
                ax, ay, az = -ax, -ay, -az
            angles.append(ang)
            # in-screen tilt from vertical: the x/y components only
            tilts_screen.append(math.degrees(math.atan2(abs(ax), abs(ay))))
            # full 3D deviation from the vertical axis
            tilts_3d.append(math.degrees(math.acos(max(-1.0, min(1.0, ay)))))

        print()
        print(f"  2. CUBE '{name}' -- {len(seq)} held frames, "
              f"{len(angles)} above the {MIN_ANGLE_DEG:.0f} deg noise floor")
        print(f"     reference frame       : t={ref[0]/1000.0:.1f} s, the most FACE-ON "
              f"in the window (widest palm), not the first")
        if not angles:
            print("     ! NOTHING above the noise floor -- the rotation never got large")
            print("       enough for the axis to be determined. Not a pass, not a fail.")
            continue
        print(f"     rotation reached      : median {pct(angles,50):5.1f} deg, max {max(angles):5.1f} deg")
        print(f"     AXIS tilt in-screen   : median {pct(tilts_screen,50):5.1f} deg   "
              f"(p25 {pct(tilts_screen,25):.1f}, p75 {pct(tilts_screen,75):.1f})")
        print(f"     AXIS off-vertical 3D  : median {pct(tilts_3d,50):5.1f} deg   "
              f"(p25 {pct(tilts_3d,25):.1f}, p75 {pct(tilts_3d,75):.1f})")
        print("     reference: the 2026-08-22 clean take measured +12.3 in-screen / 13.0 3D")

        # ⭐⭐ AXIS vs ROTATION MAGNITUDE -- the only honest way to read this.
        # §14.3.4.2, binding: "Never quote an axis deviation without the rotation
        # magnitude it was measured at." Below ~30 deg the axis is barely
        # determined at all -- a CLEAN pitch take reads 44-63 deg off its own axis
        # there. So a large tilt at small rotation is the noise floor, not a
        # defect, and only the trend as rotation grows is informative.
        print("     axis vs rotation magnitude (the noise floor dominates the left):")
        print("        rotation band    n     axis off-vertical (median)")
        bands = [(30, 40), (40, 50), (50, 60), (60, 90)]
        for a, b in bands:
            sel = [t for t, ang in zip(tilts_3d, angles) if a <= ang < b]
            if sel:
                print(f"        {a:3d}-{b:3d} deg  {len(sel):5d}     {pct(sel,50):5.1f} deg")
            else:
                print(f"        {a:3d}-{b:3d} deg  {0:5d}     --  (never reached)")
        print("        reference: the 2026-08-22 clean take read 13.0 deg AT LARGE ROTATION")

        # ⭐⭐ IS THE DEPTH DRIFT CAUSED BY THE ROTATION? This is the A10 property
        # `palm_depth` was built for: a depth anchor must stay CONSTANT while the
        # hand merely rotates. A rotation-only take is the direct test, and the
        # cube's own recorded depth is the honest quantity -- not a re-derivation.
        # If median depth climbs with rotation magnitude, foreshortening is leaking
        # into depth and the object visibly swims while only being turned. If it is
        # flat, the drift is the operator's hand genuinely moving.
        paired = []
        for (_t, q, d) in seq:
            if d is None:
                continue
            dq = qmul(q, qconj(q0))
            _ax, ang = axis_angle(dq)
            paired.append((ang, d))
        if paired:
            print("     depth vs rotation magnitude (want FLAT -- rotation must not move Z):")
            for a, b in [(0, 15), (15, 30), (30, 45), (45, 90)]:
                sel = [d for ang, d in paired if a <= ang < b]
                if sel:
                    print(f"        {a:3d}-{b:3d} deg  {len(sel):5d}     median depth {pct(sel,50):.3f} m")
            flat = [d for ang, d in paired if ang < 15]
            turned = [d for ang, d in paired if ang >= 45]
            if flat and turned:
                drift = pct(turned, 50) - pct(flat, 50)
                print(f"        -> shift from near-face-on to most-turned: {drift:+.3f} m")
                print("           (a large POSITIVE shift = foreshortening read as 'further away')")

        depths = [d for _t, _q, d in seq if d is not None]
        if depths:
            print(f"     DEPTH while rotating  : {min(depths):.3f} .. {max(depths):.3f} m "
                  f"(span {max(depths)-min(depths):.3f})")
            print("       ! This is a ROTATION take -- the hand held its distance, so a large")
            print("         span here is 4.2's depth estimator being fooled by foreshortening,")
            print("         which is exactly what the max4 anchor and S10 exist to prevent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
