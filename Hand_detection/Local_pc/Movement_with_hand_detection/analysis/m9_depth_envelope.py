"""M9 / 4.1 -- THE A10 TEST for `Resources/palm_depth.py`, plus the envelope
measurement that decided the no-calibration-step question.

A10 (binding): a module must show a measured improvement on identical recorded
input, or be reverted. For a depth estimator the requirement is two-sided and
one half is useless without the other:

    RESPONSIVE  on `depth_sweep`, where the hand really does move toward and
                away from the camera, the ratio MUST move.
    STABLE      on the rotation takes (yaw / pitch), where the hand rotates in
                place at constant distance, the ratio MUST NOT move. Any motion
                there is FALSE DEPTH -- the cube would drift toward or away from
                the camera purely because the operator turned their wrist.

⚠ A single-sided test is gameable in both directions: an estimator that returns a
constant scores perfectly on STABLE, and one that returns raw span scores
perfectly on RESPONSIVE. Both are reported, always, together.

Also reports the ENVELOPE -- the ratio range an ordinary push/pull reaches --
because that is what decides whether the game needs a min/max depth calibration
step. Run from the parent directory:

    .venv/Scripts/python.exe analysis/m9_depth_envelope.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_depth as PD         # noqa: E402
import palm_geometry as PG      # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

RESPONSIVE = [("2026-08-03_172504_depth_sweep", "depth_sweep -- hand really moves")]
STABLE = [
    ("2026-08-22_134553_yaw_sweep_constant_depth", "YAW in place (clean take)", "yaw"),
    ("2026-08-04_164647_yaw_sweep_constant_depth", "YAW in place (contaminated)", "yaw"),
    ("2026-08-04_054702_pitch_sweep_slow",         "PITCH in place", "pitch"),
    ("2026-08-03_171314_palm_back_s2_slow",        "PITCH palm->back [RIGHT]", "pitch"),
]


def load(session):
    out = []
    path = os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            hands = (json.loads(line).get("hands") or [])
            if not hands:
                continue
            px = hands[0].get("landmarks")
            if px and len(px) == 21:
                out.append(px)
    return out


def pct(v, p):
    s = sorted(v)
    return s[max(0, min(len(s) - 1, int(len(s) * p)))]


def run(session):
    frames = load(session)
    if not frames:
        return None
    trk = PD.DepthRatioTracker()
    # Baseline on the first frame that is not edge-on -- what a real grab does.
    ratios, valid_n = [], 0
    for px in frames:
        r, ok = trk.update(px)
        ratios.append(r)
        valid_n += 1 if ok else 0
    if not ratios:
        return None
    lo, hi, mid = pct(ratios, 0.02), pct(ratios, 0.98), pct(ratios, 0.5)
    # spread of the ratio = how much depth the estimator thinks happened
    return {
        "n": len(ratios), "lo": lo, "hi": hi, "mid": mid,
        "span": hi / lo if lo > 1e-6 else float("inf"),
        "valid_pct": 100.0 * valid_n / len(ratios),
        "frozen": trk.frames_frozen, "bands": trk.band_entries,
        "rate_limited": trk.rate_limited,
    }


def drift_floor(session, axis):
    """The IRREDUCIBLE floor: how much the hand GENUINELY changed distance.

    A span perpendicular to the rotation axis foreshortens; a span PARALLEL to it
    cannot. So on a yaw take the LENGTH span (0<->9, parallel to the vertical
    rotation axis) varies only when the hand really moved -- operator drift, which
    no estimator can or should remove. Measured 1.40x on the clean yaw take, so
    most of what looks like estimator error there is the operator's own arm.
    """
    frames = load(session)
    a, b = (0, 9) if axis == "yaw" else (5, 17)
    v = [math.hypot(p[a][0] - p[b][0], p[a][1] - p[b][1]) for p in frames]
    if not v:
        return float("nan")
    lo, hi = pct(v, 0.02), pct(v, 0.98)
    return hi / lo if lo > 1e-6 else float("inf")


def raw_span_control(session):
    """The naive estimator: palm WIDTH alone, no freeze, no rate limit.
    This is the thing 4.1 has to beat on the STABLE takes."""
    frames = load(session)
    base = None
    vals = []
    for px in frames:
        w = math.hypot(px[5][0] - px[17][0], px[5][1] - px[17][1])
        if base is None and w > 1e-6:
            base = w
        if base:
            vals.append(w / base)
    if not vals:
        return None
    lo, hi = pct(vals, 0.02), pct(vals, 0.98)
    return hi / lo if lo > 1e-6 else float("inf")


def main():
    print("=" * 78)
    print("M9 / 4.1  A10 TEST -- responsive where depth changes, flat where it does not")
    print("=" * 78)
    print("  'span' = p98/p2 of the reported ratio. HIGH is right for depth_sweep,")
    print("  LOW is right for rotation-in-place (there, span-1 IS the false depth).")
    print("  'width-only' is the naive control 4.1 must beat on the stable takes.\n")

    print(f"  {'take':42s} {'span':>7s} {'width-only':>11s} {'valid%':>7s} {'froz':>5s}")
    print("  " + "-" * 76)

    print("  RESPONSIVE -- want a LARGE span")
    for s, label in RESPONSIVE:
        if not os.path.isdir(os.path.join(CAPTURE_ROOT, s)):
            print(f"  {label:42s}   (missing)")
            continue
        r = run(s)
        c = raw_span_control(s)
        print(f"  {label:42s} {r['span']:6.2f}x {c:10.2f}x {r['valid_pct']:6.1f}% {r['frozen']:5d}")
        print(f"    -> ratio {r['lo']:.2f} .. {r['hi']:.2f} about {r['mid']:.2f}"
              f"   ENVELOPE an ordinary push/pull reaches")

    print("\n  STABLE -- want a span near 1.00; anything above it is FALSE DEPTH")
    worst = 0.0
    for s, label, axis in STABLE:
        if not os.path.isdir(os.path.join(CAPTURE_ROOT, s)):
            print(f"  {label:42s}   (missing)")
            continue
        r = run(s)
        c = raw_span_control(s)
        fl = drift_floor(s, axis)
        excess = r["span"] / fl if fl > 1e-6 else float("inf")
        worst = max(worst, r["span"])
        globals()["_worst_excess"] = max(globals().get("_worst_excess", 0.0), excess)
        print(f"  {label:42s} {r['span']:6.2f}x {c:10.2f}x {r['valid_pct']:6.1f}% {r['frozen']:5d}")
        print(f"    -> drift floor {fl:.2f}x  =>  estimator's OWN error {excess:.2f}x")

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"  worst raw span on a rotation take : {worst:.2f}x")
    print(f"  worst span ABOVE the drift floor   : {globals().get('_worst_excess', 0.0):.2f}x"
          f"   <- the honest number")
    print("  WARNING: do NOT quote the raw stable span alone. On the clean yaw take")
    print("  1.40x of it is the operator's arm genuinely moving distance, which no")
    print("  estimator can remove.")
    print("  A10 passes only if the responsive span is clearly larger than the")
    print("  worst stable span -- i.e. real depth is separable from wrist rotation.")


if __name__ == "__main__":
    main()
