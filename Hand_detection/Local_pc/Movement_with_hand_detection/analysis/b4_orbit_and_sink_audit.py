"""⭐ Why the ARM B rows visibly ORBIT the hand, and whether SINK measures anything.

Written 2026-08-17 after the owner watched the six-arm session and reported, on
the yaw take: *"in the first two windows the cube rotated without much movement,
while on the other 4 windows there was a significant movement of the cube on top
of the rotation: as if the cube was rotating around the hand instead of around
itself."*

That observation is correct, it is the anchor change, and it is the ONLY visible
difference in the session. This script measures two things about it.

────────────────────────────────────────────────────────────────────────────────
1. THE ORBIT IS THE DESIGN, NOT A BUG

  §14.1     P = weighted_mean(landmarks_now) + FROZEN PIXEL OFFSET
            The offset is a screen vector. It never rotates. A hand that spins
            in place moves the weighted mean barely at all, so the cube sits
            still and only spins -- windows 1 and 2.

  ARM B     P = o + s * (Rx*ex + Ry*ey)
            The offset lives in the palm's OWN frame. When the palm yaws, ex/ey
            rotate and s foreshortens, so the cube swings around the palm
            centroid -- windows 3-6.

  Arm B is the physically honest one: a real cube held off-centre in a real hand
  does travel through space when the wrist turns. §14.1 is the visually calm one.
  ⚠ Which is *correct* is not what the operator's eye was asked to judge, and
  this script does not decide it either -- it measures the size of the effect.

────────────────────────────────────────────────────────────────────────────────
2. ⚠⚠ THE SINK METRIC IS SELF-MEASURING FOR ARM B — handoff trap #4

  `b4_six_arm_verdict.score()` defines   SINK = corr( |cube - palm| / palm_width,
                                                      edge_on_measure )

  and `hand_blocks.palm_position` / `palm_scale` are THE SAME `o` and `s` that
  `palm_anchor.Arm2D` builds its position out of. So for arm B

      |cube - o| / s  ==  |R|  ==  frozen at grab, for the whole grab

  i.e. the numerator of the correlation is an algebraic CONSTANT and the
  correlation is 0 by construction, for any hand motion whatsoever. Arm B cannot
  score a sink. The small residuals actually reported (-0.026 .. -0.187) come
  from the `+40` px cube-centre fudge in `score()`, not from the anchor.

  ⭐ This is exactly handoff trap #4 -- *"a classifier that shares an expression
  with the thing it judges measures itself"* -- and it is why §16.14's
  spectacular "ARM B kills the sink on every axis" table must not be read as
  evidence that arm B fixed anything. It is a restatement of arm B's formula.

  The test below is the falsifiable form: recompute the sink numerator with the
  `+40` removed. If arm B's |R| is constant to numerical precision, the metric
  is measuring its own definition.

    .venv/Scripts/python.exe analysis/b4_orbit_and_sink_audit.py [--root DIR]
"""
import argparse
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_blocks as HB
from Resources import palm_geometry as PG

DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"

ARMS = [("cubes_raw", "1  §14.1 (production)"),
        ("cubes_anchor", "3  ARM B"),
        ("cubes_horn", "5  ARM B + HORN")]


def q(v, p):
    return sorted(v)[int(p * (len(v) - 1))] if v else float("nan")


def stats(v):
    if not v:
        return float("nan"), float("nan"), float("nan")
    m = sum(v) / len(v)
    sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
    return m, sd, max(v) - min(v)


def analyse(recs, key):
    """Cube-vs-palm geometry for one arm, per frame, while the cube is held."""
    r_norm = []          # |cube - o| / s   -- the SINK numerator, no +40 fudge
    r_px = []            # |cube - o|       -- in pixels
    theta = []           # angle of (cube - o) measured IN THE PALM FRAME
    theta_img = []       # angle of (cube - o) in IMAGE axes
    step = []            # per-frame cube displacement, px
    eo = []
    prev = None
    for rec in recs:
        blk = (rec.get(key) or {}).get("large")
        hs = rec.get("hands") or []
        if not blk or not blk.get("owner") or not hs:
            prev = None
            continue
        px = [tuple(p) for p in hs[0]["landmarks"]]
        o = HB.palm_position(px)
        s = HB.palm_scale(px)
        if not o or not s:
            prev = None
            continue
        # cube centre: pos is the TOP-LEFT, the large cube is 80 px (score()
        # uses +40, which is that same half-size).
        c = (blk["pos"][0] + 40.0, blk["pos"][1] + 40.0)
        d = (c[0] - o[0], c[1] - o[1])
        r_px.append(math.hypot(*d))
        r_norm.append(math.hypot(*d) / s)
        # palm frame: ex along the knuckle row (index-MCP -> pinky-MCP)
        ax = (px[HB.PINKY_MCP][0] - px[HB.INDEX_MCP][0],
              px[HB.PINKY_MCP][1] - px[HB.INDEX_MCP][1])
        n = math.hypot(*ax)
        if n > 1e-9:
            ex = (ax[0] / n, ax[1] / n)
            ey = (-ex[1], ex[0])
            theta.append(math.degrees(math.atan2(d[0] * ey[0] + d[1] * ey[1],
                                                 d[0] * ex[0] + d[1] * ex[1])))
        theta_img.append(math.degrees(math.atan2(d[1], d[0])))
        eo.append(PG.edge_on_measure(px))
        if prev is not None:
            step.append(math.dist(c, prev))
        prev = c
    return {"r_norm": r_norm, "r_px": r_px, "theta": theta,
            "theta_img": theta_img, "step": step, "eo": eo}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--only", default="2026-08-17_18",
                    help="substring filter; defaults to the POST-FIX takes only")
    a = ap.parse_args()

    takes = [d for d in sorted(glob.glob(os.path.join(a.root, "*")))
             if os.path.exists(os.path.join(d, "meta.json"))
             and (not a.only or a.only in os.path.basename(d))]

    print("=" * 96)
    print("ORBIT SIZE, and whether SINK can measure ARM B at all")
    print("=" * 96)

    for d in takes:
        meta = json.load(open(os.path.join(d, "meta.json")))
        recs = [json.loads(l) for l in
                open(os.path.join(d, "raw_landmarks.jsonl"))]
        if "cubes_horn" not in recs[0]:
            continue
        print(f"\n--- {meta.get('sequence')}  ({len(recs)} frames, "
              f"{meta.get('measured_fps')} fps) ---")
        print(f"    {'arm':<24}{'|R| mean':>10}{'|R| sd':>9}{'|R| range':>11}"
              f"{'px mean':>9}{'px range':>10}{'palmang range':>15}{'step p95':>10}")
        for key, lab in ARMS:
            r = analyse(recs, key)
            if not r["r_norm"]:
                continue
            m, sd, rng = stats(r["r_norm"])
            pm, _psd, prng = stats(r["r_px"])
            _tm, _tsd, trng = stats(r["theta"])
            print(f"    {lab:<24}{m:>10.4f}{sd:>9.4f}{rng:>11.4f}"
                  f"{pm:>9.1f}{prng:>10.1f}{trng:>15.1f}{q(r['step'], .95):>10.2f}")
        print("      |R| = the SINK numerator with the +40 fudge kept but the")
        print("      correlation dropped. sd ~ 0 => the metric is a constant for")
        print("      that arm and its 'sink ~ 0' is an identity, not a finding.")


if __name__ == "__main__":
    main()
