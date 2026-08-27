# -*- coding: utf-8 -*-
"""⭐⭐ WHY DOES THE OCCLUSION LOOK BETTER ON THE BACK OF THE HAND THAN THE PALM?

Owner, 2026-08-27, watching the per-landmark occlusion live. The occlusion geometry
is side-agnostic -- `depth_order` never asks which face of the hand it is looking at
-- so if the two sides behave differently, the difference is in the INPUT, i.e. in
MediaPipe's per-landmark `z`. This measures that, on the owner's own take.

WHAT IS COMPARED, and the split is independent of everything being measured
────────────────────────────────────────────────────────────────────────────────
Frames are split by `palm_geometry.signed_palm_area`, a 2-D cue computed from PIXEL
landmarks. It shares no expression with the world `z` under test (`B4`).

    SPREAD      max-min world z across the 21 landmarks, per frame.
                How much depth STRUCTURE MediaPipe is reporting at all. A hand is
                ~4-8 cm deep, so a spread far below that is a flattened hand and
                every joint will sort at nearly the same depth.

    JITTER      frame-to-frame change of each landmark's z. This is what makes a
                joint flicker in and out of a cube while the hand is still.

    SIGN FLIPS  how often the fingertip-vs-wrist z ORDER reverses between frames.
                A real hand does not turn inside out; every flip is the estimator
                changing its mind about which way the hand faces.

\u26a0 All three are reported in METRES and as a fraction of the hand's own depth, so
"noisy" is measured against something physical rather than asserted.

    .venv/Scripts/python.exe analysis/occlusion_palm_vs_back.py [session]
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
DEFAULT = "2026-08-27_185142_perlandmark"

TIPS = (4, 8, 12, 16, 20)
WRIST = 0


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else float("nan")


def med(xs):
    return pct(xs, 0.5)


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
                out.append(None)
                continue
            hh = h[0]
            if hh.get("landmarks") and hh.get("world_landmarks"):
                out.append((hh["landmarks"], hh["world_landmarks"]))
            else:
                out.append(None)
    return out


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    frames = load(session)
    if not frames:
        print("session not found: %s" % session)
        return 1

    stats = {"palm": {"spread": [], "jitter": [], "flips": 0, "n": 0},
             "back": {"spread": [], "jitter": [], "flips": 0, "n": 0}}
    prev_w = prev_side = prev_sign = None

    for fr in frames:
        if fr is None:
            prev_w = prev_side = prev_sign = None
            continue
        px, wl = fr
        if len(wl) < 21:
            continue
        sa = PG.signed_palm_area(px)
        if sa is None:
            continue
        side = "palm" if sa > 0 else "back"
        zs = [w[2] for w in wl if w is not None and len(w) > 2]
        if len(zs) < 21:
            continue
        st = stats[side]
        st["n"] += 1
        st["spread"].append(max(zs) - min(zs))

        # tip-vs-wrist ordering: does the hand keep facing the same way?
        sign = 1.0 if (sum(zs[t] for t in TIPS) / len(TIPS)) >= zs[WRIST] else -1.0
        if prev_side == side and prev_sign is not None and sign != prev_sign:
            st["flips"] += 1
        prev_sign, prev_side = sign, side

        if prev_w is not None and len(prev_w) >= 21:
            st["jitter"].extend(abs(zs[i] - prev_w[i]) for i in range(21))
        prev_w = zs

    w = 84
    print("=" * w)
    print("  WHY THE OCCLUSION DIFFERS BY HAND SIDE   %s" % session)
    print("=" * w)
    print("  split by `signed_palm_area` -- a 2D cue, independent of the world z (B4)")
    print()
    print("  %-8s %7s | %-24s | %-24s | %s"
          % ("side", "frames", "z SPREAD (m)", "z JITTER per frame (m)", "sign flips"))
    print("  " + "-" * (w - 4))
    for side in ("palm", "back"):
        st = stats[side]
        if st["n"] < 10:
            print("  %-8s %7d | too few frames to score" % (side, st["n"]))
            continue
        print("  %-8s %7d | med %.4f  p95 %.4f | med %.4f  p95 %.4f | %4d (%.1f%%)"
              % (side, st["n"], med(st["spread"]), pct(st["spread"], 0.95),
                 med(st["jitter"]), pct(st["jitter"], 0.95),
                 st["flips"], 100.0 * st["flips"] / max(1, st["n"])))
    print("  " + "-" * (w - 4))

    p, b = stats["palm"], stats["back"]
    if p["n"] >= 10 and b["n"] >= 10:
        print()
        print("=" * w)
        print("  WHAT IT MEANS FOR THE OCCLUSION")
        print("=" * w)
        js, bs = med(p["jitter"]), med(b["jitter"])
        ss, sb = med(p["spread"]), med(b["spread"])
        print("    jitter  palm %.4f m  vs  back %.4f m   -> palm is %.2fx %s"
              % (js, bs, (js / bs if bs > 1e-9 else float("inf")),
                 "NOISIER" if js > bs else "steadier"))
        print("    spread  palm %.4f m  vs  back %.4f m   -> palm reports %.2fx the depth structure"
              % (ss, bs and sb, (ss / sb if sb > 1e-9 else float("inf"))))
        print("    flips   palm %.1f%%  vs  back %.1f%%"
              % (100.0 * p["flips"] / max(1, p["n"]), 100.0 * b["flips"] / max(1, b["n"])))
        print()
        print("  \u2b50 A joint sorts against the cube on `hand_depth + world_z`. Jitter in")
        print("     `world_z` moves a joint across the cube's depth and back, which is")
        print("     exactly the flicker; a small SPREAD flattens the hand so every joint")
        print("     sorts together and the per-landmark effect disappears.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
