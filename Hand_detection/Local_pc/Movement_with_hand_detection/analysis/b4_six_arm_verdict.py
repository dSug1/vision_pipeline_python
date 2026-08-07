"""⭐ THE VERDICT SCRIPT — score all six live arms and name the best.

Run this on takes recorded by `debug_prediction.bat` with `--arms 6`. It scores
what the operator actually saw, because all six cube tracks were computed LIVE
from the same frames and are stored in the take. **No replay is involved**, so
none of the replay confounds apply (§16.14's harness had two of them).

    1  §14.1 anchor, shipped rotation     2  + B7 gate     <- production today
    3  ARM B anchor, shipped rotation     4  + B7 gate     <- anchor changed
    5  ARM B + HORN rotation              6  + B7 gate     <- rotation changed

⚠⚠ BINDING RULES, each already paid for once in this project:
  * REPORT PER TAKE, NEVER POOLED. Pitch-sink and yaw-sink have OPPOSITE SIGNS
    and cancel when mixed — §16.4 scored a benign 0.138 pooled while the isolated
    axes were 0.822 and 0.323 (§16.5).
  * THE AXIS COMES FROM THE TAKE NAME, NOT FROM THE DATA. `edge_on_measure`
    drops under BOTH yaw and pitch, so no metric can recover it. An invented
    `e1.z` classifier read frame DEGENERACY as yaw and cost a needless retake.
  * ⭐ SINK IS THE DEFECT THE OWNER REPORTED; JITTER IS NOT (§16.5). A row that
    wins on jitter and loses on sink has not won.
  * CLASSIFY, DO NOT COUNT. Every number here is split by take and by band.

    .venv/Scripts/python.exe analysis/b4_six_arm_verdict.py [--root DIR]
"""
import argparse
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import b7_live_ab as A
from Resources import hand_blocks as HB
from Resources import palm_geometry as PG
from Resources import palm_rotation as PR

STILL_PALM = 0.5
DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"

ARMS = [
    ("cubes_raw",          "1  §14.1                (production)"),
    ("cubes_gated",        "2  §14.1 + B7"),
    ("cubes_anchor",       "3  ARM B"),
    ("cubes_anchor_gated", "4  ARM B + B7"),
    ("cubes_horn",         "5  ARM B + HORN"),
    ("cubes_horn_gated",   "6  ARM B + HORN + B7"),
]


def Q(v, p):
    return sorted(v)[int(p * (len(v) - 1))] if v else float("nan")


def corr(a, b):
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else float("nan")


def score(recs, key):
    """Position and orientation behaviour of ONE arm, straight from the take."""
    pos, pos_still, ori, ori_still = [], [], [], []
    sink_d, sink_e, held = [], [], 0
    prev_p, prev_q, prev_palm = {}, {}, None
    for r in recs:
        if key not in r:
            continue
        hs = r.get("hands") or []
        palm = eo = wid = None
        if hs:
            px = [tuple(p) for p in hs[0]["landmarks"]]
            palm = HB.palm_position(px)
            eo = PG.edge_on_measure(px)
            wid = HB.palm_scale(px)
        still = (palm and prev_palm and math.dist(palm, prev_palm) < STILL_PALM)
        any_held = False
        for n, c in r[key].items():
            if c["owner"] is not None:
                any_held = True
                if n in prev_p:
                    d = math.dist(c["pos"], prev_p[n])
                    pos.append(d)
                    if still:
                        pos_still.append(d)
                if n in prev_q:
                    a = PR.quat_angle_deg(tuple(prev_q[n]), tuple(c["quat"]))
                    if a is not None:
                        ori.append(a)
                        if still:
                            ori_still.append(a)
                if palm and wid and eo is not None:
                    cc = (c["pos"][0] + 40, c["pos"][1] + 40)   # approx centre
                    sink_d.append(math.dist(cc, palm) / wid)
                    sink_e.append(eo)
            prev_p[n] = c["pos"]
            prev_q[n] = c["quat"]
        held += 1 if any_held else 0
        prev_palm = palm
    return {"pos": pos, "pos_still": pos_still, "ori": ori, "ori_still": ori_still,
            "sink": corr(sink_d, sink_e), "held": held}


def main():
    ap = argparse.ArgumentParser(description="Score all six live arms, per take.")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--only", default=None, help="substring filter on take name")
    args = ap.parse_args()

    takes = [d for d in sorted(glob.glob(os.path.join(args.root, "*")))
             if os.path.exists(os.path.join(d, "meta.json"))]
    if args.only:
        takes = [d for d in takes if args.only in d]

    print("=" * 100)
    print("SIX-ARM VERDICT — measured LIVE, not replayed")
    print("=" * 100)

    wins = {lab: 0 for _k, lab in ARMS}
    any6 = False
    for d in takes:
        meta, recs = A.load(d)
        if not recs or "cubes_horn" not in recs[0]:
            continue                      # not a 6-arm take
        any6 = True
        name = meta.get("sequence", os.path.basename(d))
        print(f"\n  --- {name}   {meta.get('actual_span_s')}s   {len(recs)} frames   "
              f"{meta.get('measured_fps')} fps ---")
        print(f"      {'arm':<38}{'POS p95':>9}{'POS max':>9}{'still':>8}"
              f"{'ORI p95':>9}{'ORI max':>9}{'still':>8}{'SINK':>9}")
        rows = []
        for key, lab in ARMS:
            s = score(recs, key)
            if not s["pos"]:
                continue
            rows.append((lab, s))
            print(f"      {lab:<38}{Q(s['pos'],.95):>9.2f}{max(s['pos']):>9.2f}"
                  f"{(max(s['pos_still']) if s['pos_still'] else float('nan')):>8.2f}"
                  f"{Q(s['ori'],.95):>9.2f}{max(s['ori']):>9.2f}"
                  f"{(max(s['ori_still']) if s['ori_still'] else float('nan')):>8.2f}"
                  f"{s['sink']:>9.3f}")
        # ⭐ the take-level winner: SINK first (the reported defect), jitter as
        # the tie-break. Never the other way round (§16.5).
        ok = [(abs(s["sink"]), Q(s["pos"], .95), lab) for lab, s in rows
              if s["sink"] == s["sink"]]
        if ok:
            ok.sort()
            print(f"      -> lowest |sink|: {ok[0][2]}   (|r| = {ok[0][0]:.3f}, "
                  f"pos p95 {ok[0][1]:.2f})")
            wins[ok[0][2]] += 1

    if not any6:
        print("\n  ⚠ No 6-arm takes found. Record with:")
        print("      debug_prediction.bat --arms 6 --sequence <name>")
        return

    print("\n" + "=" * 100)
    print("TAKES WON, by lowest |sink| (the defect the owner reported)")
    print("=" * 100)
    for lab, n in sorted(wins.items(), key=lambda kv: -kv[1]):
        print(f"  {lab:<40}{n}")
    print("\n  ⚠ A winner here is NOT a decision. Read the per-take tables: the")
    print("    pitch and back-of-hand takes are the ones the owner cares about,")
    print("    and jitter is a real cost that this ranking deliberately subordinates.")
    print("=" * 100)


if __name__ == "__main__":
    main()
