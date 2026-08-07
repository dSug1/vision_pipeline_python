"""B4 -- the anchor + rotation A/B, on the seven purpose-built takes.

⭐ THE FIRST TIME THIS PROJECT HAS TAKES THAT CONTAIN THE CONDITIONS ITS ANCHOR
CLAIMS ARE ABOUT. §16.4 measured the sink on takes with no sustained yaw and no
pitch crossing and produced a confident, wrong, three-decimal answer that §16.5
had to overturn. The 2026-08-06/07 set was recorded specifically to close that:

    finger_flex_hold        palm still, fingers moving      -> the §16.10 defect
    wrist_rotate_still_palm centroid pinned, wrist turning  -> rotation estimator
    yaw_hold_cube           sustained yaw, edge-on sweep    -> SINK, yaw axis
    pitch_crossing_cube     pitch through horizontal (x2)   -> SINK, pitch axis
    depth_sweep_cube        2.97x depth range               -> is scale needed
    back_of_hand_hold       40% back-of-hand                -> where §0.18 fails

⚠⚠ BINDING RULES, each already paid for once:
  * REPORT PER TAKE, NEVER POOLED. Pitch-sink and yaw-sink have OPPOSITE SIGNS
    and cancel when mixed -- that is how §16.4 scored a benign 0.138 while the
    isolated axes were 0.822 and 0.323 (§16.5).
  * ⚠ THE AXIS COMES FROM THE OPERATOR'S PROTOCOL, NOT FROM THE DATA.
    `edge_on_measure` drops under BOTH yaw and pitch, so no metric can recover
    which axis a take contains. An `e1.z`-based classifier was tried and is
    WORSE than useless: it reads the palm frame DEGENERATING at edge-on as
    "yaw", and pitch is what drives the hand edge-on -- so it labelled a pure
    pitch take as yaw-dominant and cost a needless retake. The take name is
    ground truth.
  * CHIRALITY FIRST. No rotation variant is reported until it has passed
    `verify_palm_rotation.py` §4 -- §13.6.1 shipped a silent handedness
    inversion once.
  * ⚠ CONFOUND TO CARRY: takes 1, 2, 4 and 6 have arc spans 0.20-0.64, so the
    fingers moved during them. The palm+tips variants are therefore partly
    confounded THERE -- their extra points are the ones that moved. Takes 5
    (0.01-0.02) and 3 (0.12) are the clean references for that comparison, and
    every table below marks which is which.

    .venv/Scripts/python.exe analysis/b4_anchor_rotation_ab.py [--root DIR]
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
import LiveSnapDebug as LSD
from Resources import hand_blocks as HB
from Resources import palm_geometry as PG
from Resources import palm_anchor as PAnc
from Resources import palm_rotation as PR

STILL_PALM = 0.5            # px/frame -- "the palm did not move this frame"
DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"

# take name -> (label, axis the OPERATOR performed, fingers-still?)
TAKES = [
    ("finger_flex_hold",        "1  finger_flex",   "none",  False),
    ("wrist_rotate_still_palm", "2  wrist_rotate",  "all",   False),
    ("yaw_hold_cube",           "3  yaw_hold",      "YAW",   True),
    ("075823_pitch_crossing",   "4a pitch (1st)",   "PITCH", False),
    ("080343_pitch_crossing",   "4b pitch (clean)", "PITCH", False),
    ("depth_sweep_cube",        "5  depth_sweep",   "depth", True),
    ("back_of_hand_hold",       "6  back_of_hand",  "none",  False),
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


def find(root, tag):
    c = [d for d in sorted(glob.glob(os.path.join(root, "*"))) if tag in d]
    return c[-1] if c else None


# --------------------------------------------------------------------------
# 1. ROTATION STABILITY -- degrees per frame while the PALM IS STILL
# --------------------------------------------------------------------------
def rotation_stability(recs, window=None):
    """A still palm should give a still orientation. Whatever a variant reports
    here is pure estimator error, since the hand did not move."""
    out = {e.name: [] for e in PR.estimators()}
    out["gram_schmidt_filtered"] = []
    ests = {e.name: (e, None) for e in PR.estimators()}
    filt = LSD.HandOrientationFilter()
    lo, hi = window if window else (float("-inf"), float("inf"))
    prev_pos = prev_fq = None
    for r in recs:
        inside = lo <= r["tCapture"] <= hi
        for h in (r.get("hands") or [])[:1]:
            px = [tuple(p) for p in h["landmarks"]]
            w = [tuple(v) for v in h["world_landmarks"]]
            pos = HB.palm_position(px)
            still = (prev_pos is not None and pos is not None
                     and math.dist(pos, prev_pos) < STILL_PALM)
            for name, (e, st) in list(ests.items()):
                if st is None:
                    st = e.freeze(px, w)
                    ests[name] = (e, st)
                    continue
                d = e.step(st, px, w)
                if inside and still and d is not None:
                    out[name].append(d)
            rq, cond = LSD._hand_orientation_quaternion(w)
            fq = LSD._predictive_filter_step(filt, rq, cond)
            if inside and still and prev_fq is not None:
                d = PR.quat_angle_deg(prev_fq, fq)
                if d is not None:
                    out["gram_schmidt_filtered"].append(d)
            prev_fq = fq
            prev_pos = pos
    return out


# --------------------------------------------------------------------------
# 2. CUBE-LEVEL A/B -- translation anchor x rotation estimator
# --------------------------------------------------------------------------
class Anchor141:
    """The incumbent, with an optional fingertip-weight scale (§16.12)."""

    def __init__(self, tip_w=1.0):
        self.tip_w = tip_w
        self.name = "14.1" if tip_w == 1.0 else f"14.1 tip x{tip_w:g}"

    def freeze(self, obj, px, world):
        raw = LSD._compute_grab_weights(obj, px)
        tips = {4, 8, 12, 16, 20}
        adj = {i: (v * self.tip_w if i in tips else v) for i, v in raw.items()}
        tot = sum(adj.values())
        if tot < 1e-9:
            return None
        w = {i: v / tot for i, v in adj.items()}
        wp = LSD._weighted_position(w, px)
        return {"w": w, "R": (obj[0] - wp[0], obj[1] - wp[1])}

    def apply(self, st, px, world):
        if st is None:
            return None
        p = LSD._weighted_position(st["w"], px)
        return (p[0] + st["R"][0], p[1] + st["R"][1])


class PalmCentroidAnchor:
    """Palm centroid for translation + a SELECTABLE rotation estimator.

    ⭐ This is the combination the owner proposed. §16.11 measured the palm
    centroid as the BETTER translation term (still-frame p50 0.321 vs §14.1's
    0.432) while the whole anchor still lost -- because the rotation term,
    multiplied by the lever arm, dominated everything. If a better rotation
    estimator collapses that term, this is where it shows up.
    """

    def __init__(self, rot, use_scale=True):
        self.rot = rot
        self.use_scale = use_scale
        self.name = f"palm+{rot.name}" + ("" if use_scale else " (k frozen)")

    def freeze(self, obj, px, world):
        o = PAnc.palm_origin_px(px)
        k = PAnc.weak_perspective_scale(px, world)
        rs = self.rot.freeze(px, world)
        if o is None or not k or rs is None:
            return None
        return {"o": o, "k": k, "d": (obj[0] - o[0], obj[1] - o[1]), "rs": rs}

    def apply(self, st, px, world):
        if st is None:
            return None
        o = PAnc.palm_origin_px(px)
        if o is None:
            return None
        q = self.rot.delta(st["rs"], px, world)
        if q is None:
            return None
        k = PAnc.weak_perspective_scale(px, world) if self.use_scale else st["k"]
        if not k:
            k = st["k"]
        s = k / st["k"]
        dx, dy = st["d"]
        # rotate the frozen pixel offset by the measured rotation, projected:
        # the image-plane part of R * (dx, dy, 0), then scaled for depth.
        w_, x_, y_, z_ = q
        m00 = 1 - 2 * (y_ * y_ + z_ * z_)
        m01 = 2 * (x_ * y_ - w_ * z_)
        m10 = 2 * (x_ * y_ + w_ * z_)
        m11 = 1 - 2 * (x_ * x_ + z_ * z_)
        return (o[0] + s * (m00 * dx + m01 * dy),
                o[1] + s * (m10 * dx + m11 * dy))


def cube_ab(recs, anchor, window=None):
    """⚠ REPLAY THE FULL TAKE, MEASURE ONLY INSIDE `window`.

    The trim exists to exclude the operator's grab approach -- but a replay NEEDS
    that approach, because every arm starts with its cubes reset to the centre of
    the window and has to re-acquire the grab from scratch. Feeding it trimmed
    records means the hand never comes within grab radius, nothing is ever held,
    and every metric comes back NaN (measured: exactly that, first run).

    So: full records in, metrics gated by timestamp.
    """
    lo, hi = window if window else (float("-inf"), float("inf"))
    state = LSD.CubeState(window_size=(640, 480))
    steps, still, sink_d, sink_e = [], [], [], []
    prev, prev_palm = {}, None
    for r in recs:
        data = {h: None for h in LSD.TRACKED_HANDS}
        for h in r.get("hands") or []:
            data[h["label"]] = {
                "pixel_landmarks": [tuple(p) for p in h["landmarks"]],
                "world_landmarks": [tuple(v) for v in h["world_landmarks"]],
                "thumb_outward": h["thumb_outward"]}
        LSD.update_hands(state, data, anchor=anchor)
        inside = lo <= r["tCapture"] <= hi
        hs = r.get("hands") or []
        palm = eo = wid = None
        if hs:
            px = [tuple(p) for p in hs[0]["landmarks"]]
            palm, eo, wid = HB.palm_position(px), PG.edge_on_measure(px), HB.palm_scale(px)
        for n, c in state.cubes.items():
            if inside and n in prev and c.owner is not None:
                d = math.dist(c.position, prev[n])
                steps.append(d)
                if palm and prev_palm and math.dist(palm, prev_palm) < STILL_PALM:
                    still.append(d)
            if inside and c.owner is not None and palm and wid and eo is not None:
                cc = (c.position[0] + c.size / 2, c.position[1] + c.size / 2)
                sink_d.append(math.dist(cc, palm) / wid)
                sink_e.append(eo)
            prev[n] = c.position
        prev_palm = palm
    return {"steps": steps, "still": still, "sink": corr(sink_d, sink_e),
            "n_sink": len(sink_d)}


def main():
    ap = argparse.ArgumentParser(description="B4 anchor + rotation A/B, per take.")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    found = [(t, lab, ax, fs, find(args.root, t)) for t, lab, ax, fs in TAKES]
    missing = [lab for _t, lab, _a, _f, d in found if d is None]
    found = [f for f in found if f[4]]
    print("=" * 92)
    print("B4 -- ANCHOR x ROTATION, per take")
    print("=" * 92)
    if missing:
        print(f"⚠ takes not found: {', '.join(missing)}")

    # ---------------- PART 1: rotation stability ----------------
    print("\n" + "=" * 92)
    print("PART 1 -- ROTATION STABILITY: deg/frame while the PALM IS STILL")
    print("  A still palm should give a still orientation. This is pure estimator error.")
    print("=" * 92)
    names = [e.name for e in PR.estimators()] + ["gram_schmidt_filtered"]
    order = ["gram_schmidt", "gram_schmidt_filtered", "horn_palm_ref",
             "horn_palm_ff", "horn_palmtips_ref", "horn_palmtips_ff"]
    print(f"  {'take':<20}{'n':>5}" + "".join(f"{n[:17]:>18}" for n in order))
    print(f"  {'':<20}{'':>5}" + "".join(f"{'p95 / max':>18}" for _ in order))
    for tag, lab, axis, fstill, d in found:
        rawmeta, raw = A.load(d, trim=False)
        tr = rawmeta.get("analysis_trim") or {}
        t0, t1 = raw[0]["tCapture"], raw[-1]["tCapture"]
        win = (t0 + float(tr.get("head_s", 0)) * 1000.0,
               t1 - float(tr.get("tail_s", 0)) * 1000.0)
        st = rotation_stability(raw, window=win)
        n = len(st.get("gram_schmidt", []))
        row = f"  {lab:<20}{n:>5}"
        for nm in order:
            v = st.get(nm, [])
            row += f"{Q(v,.95):>8.1f}/{(max(v) if v else 0):>8.1f}" if v else f"{'-':>18}"
        print(row + ("" if fstill else "   ⚠ fingers moved"))

    # ---------------- PART 2: cube-level A/B ----------------
    print("\n" + "=" * 92)
    print("PART 2 -- CUBE BEHAVIOUR, per take.  ⚠ SINK IS READ PER TAKE, NEVER POOLED")
    print("=" * 92)
    anchors = [Anchor141(1.0), Anchor141(0.35),
               PalmCentroidAnchor(PR.GramSchmidt()),
               PalmCentroidAnchor(PR.Horn(PR.PALM_LANDMARKS, "ref")),
               PalmCentroidAnchor(PR.Horn(PR.PALM_AND_TIPS, "ref")),
               PalmCentroidAnchor(PR.Horn(PR.PALM_AND_TIPS, "ff"))]
    if args.quick:
        anchors = anchors[:4]
    for tag, lab, axis, fstill, d in found:
        meta, recs = A.load(d)                      # trimmed: header only
        # ⚠ The REPLAY needs the untrimmed take. Every arm resets its cubes to
        # the window centre and must re-acquire the grab from scratch, and the
        # grab approach is precisely what the head trim removes -- feed it
        # trimmed records and nothing is ever held (measured: all-NaN).
        # Metrics are then gated to the documented window by timestamp.
        rawmeta, raw = A.load(d, trim=False)
        tr = rawmeta.get("analysis_trim") or {}
        t0, t1 = raw[0]["tCapture"], raw[-1]["tCapture"]
        win = (t0 + float(tr.get("head_s", 0)) * 1000.0,
               t1 - float(tr.get("tail_s", 0)) * 1000.0)
        print(f"\n  --- {lab}   axis={axis}   {meta['actual_span_s']}s   "
              f"{len(recs)} frames" + ("" if fstill else "   ⚠ fingers moved") + " ---")
        print(f"      {'anchor':<26}{'p50':>8}{'p95':>8}{'max':>9}{'stillMax':>10}"
              f"{'SINK |r|':>10}")
        assert raw is not None and rawmeta.get("sequence") in d, (
            "stale replay data: `raw` must belong to THIS take. A previous "
            "version leaked Part 1's last-iteration `raw`/`win` into Part 2 and "
            "printed seven IDENTICAL rows for seven different takes.")
        for a in anchors:
            res = cube_ab(raw, None if a.name == "14.1" else a, window=win)
            s = res["steps"]
            print(f"      {a.name:<26}{Q(s,.5):>8.2f}{Q(s,.95):>8.2f}"
                  f"{(max(s) if s else 0):>9.2f}"
                  f"{(max(res['still']) if res['still'] else float('nan')):>10.2f}"
                  f"{res['sink']:>10.3f}")

    print("\n" + "=" * 92)
    print("READING IT")
    print("=" * 92)
    print("  PART 1  the estimator comparison, independent of any cube.")
    print("          ⚠ horn_*_ref and horn_*_ff are IDENTICAL here BY DESIGN:")
    print("            step() always measures frame-to-frame stability, so the")
    print("            ref/ff distinction cannot show up until PART 2, where a")
    print("            ff variant's drift accumulates over the length of a hold.")
    print("  SINK    corr(|cube - palm| / palm width, edge_on). 0 = the offset does")
    print("          not depend on how the hand is turned. ⚠ Compare it ONLY within")
    print("          a take: yaw and pitch sinks have opposite signs (§16.5).")
    print("  ⚠ Rows marked 'fingers moved' partly confound the palmtips variants.")
    print("=" * 92)


if __name__ == "__main__":
    main()
