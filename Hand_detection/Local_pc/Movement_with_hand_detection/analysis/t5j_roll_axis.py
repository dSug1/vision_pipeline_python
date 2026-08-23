"""T5j -- ROLL: the axis that had never been recorded (spec §14.3.4.2's standing gap).

⭐⭐ WHY ROLL IS THE CONTROL EVERYTHING ELSE NEEDED. Roll is rotation about the
CAMERA axis, so it happens entirely in the image plane: the palm stays facing the
lens and the knuckle row simply turns. **Its ground truth needs no depth at all** --
it is the in-image angle of the knuckle row, read straight off the pixels.

So roll separates two things that yaw and pitch cannot:
  * if roll is ACCURATE, the fit and the frame conventions are sound, and the
    yaw/pitch errors really are the DEPTH data (which is what §14.3.4.9 concluded
    by a different route);
  * if roll is ALSO wrong, something more basic is wrong and the depth diagnosis
    is incomplete.

⚠ ROLL'S CLEANLINESS GATE IS THE OPPOSITE OF YAW'S. Under a pure roll NOTHING
foreshortens -- palm width AND length both stay put, because the palm never leaves
the plane it started in. So **both collapse ratios should stay HIGH (near 1.0)**,
and `edge_on_measure` should stay FLAT. Any dip means yaw or pitch leaked in.
⭐ That invariance is also why `edge_on_measure` was put on the debug HUD as a live
operator aid for this take: the owner discarded a first attempt because holding the
palm perpendicular to the camera by feel is too hard, and a steady number is
something a person can actually hold.

⚠ The in-plane angle WRAPS at +/-180 (it does not FOLD like `acos` does -- a
different failure). It is unwrapped continuously here.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5j_roll_axis.py <session> [skip_head_s]
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
MIN_ANGLE_DEG = 30.0
VIEW_AXIS = (0.0, 0.0, 1.0)         # roll turns about the camera/depth axis


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


def main():
    if len(sys.argv) < 2:
        print("usage: t5j_roll_axis.py <session substring> [skip_head_s]")
        return 2
    head_s = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    m = [d for d in sorted(os.listdir(CAPTURE)) if sys.argv[1] in d]
    if not m:
        print("no session matching", sys.argv[1])
        return 1
    session = m[-1]
    rows = [json.loads(l) for l in
            open(os.path.join(CAPTURE, session, "raw_landmarks.jsonl"), encoding="utf-8")
            if l.strip()]
    frames = []
    for r in rows:
        if r.get("tCapture", 0.0) < head_s * 1000.0:
            continue
        hs = r.get("hands") or []
        if len(hs) != 1:
            continue
        h = hs[0]
        px, wl = h.get("landmarks"), h.get("world_landmarks")
        if px and wl and len(px) >= 21 and len(wl) >= 21:
            frames.append((px, wl))
    if not frames:
        print("no single-hand frames in the window")
        return 1

    print("=" * 84)
    print("T5j -- ROLL AXIS (the never-before-recorded axis)")
    print("=" * 84)
    print(f"  session : {session}")
    print(f"  frames  : {len(frames)} single-hand, first {head_s:.0f} s dropped")

    # ---- cleanliness: under a PURE roll nothing foreshortens.
    ws = [math.hypot(px[INDEX_MCP][0] - px[PINKY_MCP][0],
                     px[INDEX_MCP][1] - px[PINKY_MCP][1]) for px, _ in frames]
    ls = [math.hypot(px[WRIST][0] - px[MIDDLE_MCP][0],
                     px[WRIST][1] - px[MIDDLE_MCP][1]) for px, _ in frames]
    eo = [PG.edge_on_measure(px) for px, _ in frames]
    wc, lc = pct(ws, 5) / pct(ws, 95), pct(ls, 5) / pct(ls, 95)
    print()
    print("  1. CLEANLINESS -- for ROLL, both spans must stay HIGH (nothing foreshortens)")
    print(f"     palm WIDTH  collapse : {wc:.3f}")
    print(f"     palm LENGTH collapse : {lc:.3f}")
    print(f"     squareness (edge_on) : p5 {pct(eo,5):.2f}  median {pct(eo,50):.2f}  p95 {pct(eo,95):.2f}")
    ok = wc > 0.70 and lc > 0.70
    print(f"     -> {'CLEAN roll' if ok else 'CONTAMINATED -- yaw/pitch leaked in'}")

    # ---- ground truth: the in-image knuckle-row angle, unwrapped. NO DEPTH USED.
    ref = max(range(len(frames)), key=lambda i: eo[i])   # squarest frame
    def knuckle_angle(px):
        return math.degrees(math.atan2(px[PINKY_MCP][1] - px[INDEX_MCP][1],
                                       px[PINKY_MCP][0] - px[INDEX_MCP][0]))
    a0 = knuckle_angle(frames[ref][0])
    truth = []
    for px, _ in frames:
        d = knuckle_angle(px) - a0
        while d > 180.0:
            d -= 360.0
        while d < -180.0:
            d += 360.0
        truth.append(abs(d))
    print(f"\n     reference = squarest frame (edge_on {eo[ref]:.2f})")
    print(f"     true roll reaches {max(truth):.0f} deg, median {pct(truth,50):.0f} deg")

    # ---- the fit
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    st = horn.freeze(*frames[ref])
    if st is None:
        print("\n  degenerate reference -- REFUSED")
        return 1
    devs, gains, axes = [], [], []
    for i, (px, wl) in enumerate(frames):
        d = horn.delta(st, px, wl)
        if d is None:
            continue
        ax, ang = axis_angle(d)
        if ax is None:
            continue
        if ang >= MIN_ANGLE_DEG:
            dot = abs(sum(a * b for a, b in zip(ax, VIEW_AXIS)))
            devs.append(math.degrees(math.acos(max(-1.0, min(1.0, dot)))))
            a = ax
            if axes and sum(p * q for p, q in zip(a, axes[0])) < 0.0:
                a = (-a[0], -a[1], -a[2])
            axes.append(a)
        if truth[i] >= 30.0:
            gains.append(ang / truth[i])

    print()
    print("  2. THE FIT vs the depth-free ground truth")
    if not devs:
        print("     ! nothing above the noise floor -- the roll never got large enough")
        return 1
    mx = sum(a[0] for a in axes) / len(axes)
    my = sum(a[1] for a in axes) / len(axes)
    mz = sum(a[2] for a in axes) / len(axes)
    n = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
    mdev = math.degrees(math.acos(max(-1.0, min(1.0,
                        abs((mx * VIEW_AXIS[0] + my * VIEW_AXIS[1] + mz * VIEW_AXIS[2]) / n)))))
    print(f"     axis off the VIEW axis -- MEAN   : {mdev:5.1f} deg   (bias)")
    print(f"     axis off the VIEW axis -- MEDIAN : {pct(devs,50):5.1f} deg   (bias + scatter, n={len(devs)})")
    print(f"     gain (fitted / true)             : {pct(gains,50):5.2f}   (n={len(gains)})")
    print()
    print("     compare: YAW 14.5 mean / 13.0 median, gain 1.13")
    print("              PITCH 5.5 mean / 20.2 median, gain 0.74   (validated take)")
    print()
    print("  * ROLL NEEDS NO DEPTH. If it is accurate here while yaw is not, the fit")
    print("    and the frame conventions are sound and the defect is the DEPTH data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
