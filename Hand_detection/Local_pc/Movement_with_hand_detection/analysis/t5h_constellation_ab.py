"""T5h -- THE A/B THAT HAS BEEN OPEN SINCE 2026-08-22: 5-point palm vs 9-point palm+tips.

⛔⛔ WHY THIS IS AN A/B AND NOT A SWITCH TO FLIP. The 9-point constellation
(palm + the four fingertips) beat production's 5-point palm-only on AXIS fidelity
in every take ever measured -- pitch 8.1->3.9, palm_back R 22.4->6.4, L 36.9->19.0,
yaw 28.3->24.9. ⚠ But production ships palm-only DELIBERATELY, because tips scored
orientation p95 **9.85 -> 27.79 WORSE** in free play. Those two results measure
different things: that was JITTER, this is AXIS. **Neither number alone decides it.**

⭐ SO THIS SCRIPT MEASURES BOTH, ON THE SAME FRAMES, WITH ONE VARIABLE.
`analysis/README.md`'s standing rule (A10): a module ships only on a measured
improvement, and a null result is recorded rather than shipped hopefully.

⚠ THE TWO METRICS NEED DIFFERENT TAKES, and using one take for both is how this
question stayed open:
  * AXIS   is only determined at LARGE rotation -> a clean, wide yaw sweep.
    Below ~30 deg even a clean pitch take reads 44-63 deg off its own axis
    (spec §14.3.4.2, binding).
  * JITTER is about ordinary handling -> a free_manipulation take.
So pass one of each, and read each metric only off the take that can measure it.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5h_constellation_ab.py <yaw_session> [free_session]
"""

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Resources"))
import palm_rotation as PR          # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

MIN_ANGLE_DEG = 30.0                # the axis noise floor (§14.3.4.2)
INDEX_MCP, PINKY_MCP = 5, 17

ARMS = [("palm  (5pt, SHIPS)", PR.PALM_LANDMARKS),
        ("palm+tips (9pt)   ", PR.PALM_AND_TIPS)]


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
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    ang = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, math.degrees(ang)
    return (x / s, y / s, z / s), math.degrees(ang)


def load(key):
    m = [d for d in sorted(os.listdir(CAPTURE)) if key in d]
    if not m:
        return None, []
    s = m[-1]
    p = os.path.join(CAPTURE, s, "raw_landmarks.jsonl")
    if not os.path.isfile(p):
        return s, []
    return s, [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def hands_of(rows):
    """[(px, world)] for the single dominant hand, in frame order."""
    out = []
    for r in rows:
        hs = r.get("hands") or []
        if len(hs) != 1:
            continue            # two-handed frames: identity is a separate question
        h = hs[0]
        px, wl = h.get("landmarks"), h.get("world_landmarks")
        if px and wl and len(px) >= 21 and len(wl) >= 21:
            out.append((px, wl))
    return out


def run_arm(seq, indices, ref_i):
    """Freeze at `ref_i` (the most face-on frame) and return per-frame deltas."""
    horn = PR.Horn(indices, "ref")
    st = horn.freeze(seq[ref_i][0], seq[ref_i][1])
    if st is None:
        return None
    out = []
    for px, wl in seq:
        d = horn.delta(st, px, wl)
        out.append(d)
    return out


def axis_report(name, seq, ref_i):
    print(f"\n  AXIS -- {name}")
    print(f"    {'arm':22s} {'n>floor':>8s} {'median tilt':>12s} {'at 60-90deg':>12s}")
    print("    " + "-" * 58)
    results = {}
    for label, idx in ARMS:
        deltas = run_arm(seq, idx, ref_i)
        if deltas is None:
            print(f"    {label:22s}  degenerate reference -- REFUSED")
            continue
        tilts, big = [], []
        for d in deltas:
            if d is None:
                continue
            ax, ang = axis_angle(d)
            if ax is None or ang < MIN_ANGLE_DEG:
                continue
            x, y, z = ax
            if y < 0.0:
                y = -y
            t = math.degrees(math.acos(max(-1.0, min(1.0, y))))
            tilts.append(t)
            if ang >= 60.0:
                big.append(t)
        results[label] = (tilts, big)
        print(f"    {label:22s} {len(tilts):8d} {pct(tilts,50):11.1f} "
              f"{(pct(big,50) if big else float('nan')):11.1f} deg")
    return results


def jitter_report(name, seq, ref_i):
    """Frame-to-frame angular change of the fitted orientation. LOWER is better."""
    print(f"\n  JITTER -- {name}")
    print(f"    {'arm':22s} {'n':>8s} {'median':>10s} {'p95':>10s}")
    print("    " + "-" * 54)
    for label, idx in ARMS:
        deltas = run_arm(seq, idx, ref_i)
        if deltas is None:
            print(f"    {label:22s}  degenerate reference -- REFUSED")
            continue
        steps = []
        prev = None
        for d in deltas:
            if d is None:
                prev = None
                continue
            if prev is not None:
                _a, ang = axis_angle(qmul(d, qconj(prev)))
                steps.append(ang)
            prev = d
        if steps:
            print(f"    {label:22s} {len(steps):8d} {pct(steps,50):9.2f} {pct(steps,95):9.2f}")


def most_face_on(seq):
    """Widest palm = squarest to the camera. 2D pixels only (the B4 rule)."""
    best_i, best_w = 0, -1.0
    for i, (px, _wl) in enumerate(seq):
        w = math.hypot(px[INDEX_MCP][0] - px[PINKY_MCP][0],
                       px[INDEX_MCP][1] - px[PINKY_MCP][1])
        if w > best_w:
            best_i, best_w = i, w
    return best_i


def main():
    if len(sys.argv) < 2:
        print("usage: t5h_constellation_ab.py <yaw_session> [free_session]")
        return 2

    print("=" * 78)
    print("T5h -- CONSTELLATION A/B: 5-point palm (ships) vs 9-point palm+tips")
    print("=" * 78)
    print(f"  axis noise floor: rotations below {MIN_ANGLE_DEG:.0f} deg excluded")

    name, rows = load(sys.argv[1])
    seq = hands_of(rows)
    if not seq:
        print(f"\n  no single-hand frames in {name}")
        return 1
    print(f"\n  AXIS take  : {name}  ({len(seq)} single-hand frames)")
    axis_report(name, seq, most_face_on(seq))
    # ⚠ Jitter is ALSO printed for the yaw take, but read it off the free take:
    # a deliberate sweep is not ordinary handling, and the historical 9.85->27.79
    # regression was measured in free play.
    jitter_report(name + "  (! a SWEEP, not ordinary handling)", seq, most_face_on(seq))

    if len(sys.argv) > 2:
        name2, rows2 = load(sys.argv[2])
        seq2 = hands_of(rows2)
        if seq2:
            print(f"\n  JITTER take: {name2}  ({len(seq2)} single-hand frames)")
            jitter_report(name2, seq2, most_face_on(seq2))
        else:
            print(f"\n  no single-hand frames in {name2} -- jitter not measured")
    else:
        print("\n  ⚠ NO FREE-PLAY TAKE GIVEN -- the COST side of this trade is unmeasured.")
        print("    Pass a free_manipulation session as the second argument.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
