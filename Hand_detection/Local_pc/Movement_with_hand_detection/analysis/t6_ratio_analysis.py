"""⭐⭐ T6 — THE RATIO-TABLE ANALYSIS, and the DEPTH ARM that rides on the same data.

Answers protocol §4.1 (is the yaw/pitch decoupling real?) and §8.1–8.2 (what does
rotation do to the shipped depth anchor, and is the climb the ESTIMATOR or the ARM?)
over the six on-axis calibration takes recorded 2026-08-26.

Spec: `Claude/10_HAND_TRACKING/spec/RATIO_TABLE_CALIBRATION_PROTOCOL.md` §4 and §8.
Dossier: `Claude/00_CORE/queue_notes/T6.md` — ⛔ read CAVEAT ZERO there first.

────────────────────────────────────────────────────────────────────────────────
⛔ CAVEAT ZERO, AND EXACTLY HOW FAR IT REACHES

The declared distances were set with a tape at the START of a take and then held
by eye through seven poses; the owner reports the hand very likely drifted. So:

  ⛔ NOTHING here is indexed on the true standing distance. Not one number.
  ⭐ EVERY depth quantity is normalised WITHIN a take to that take's own 0° hold,
    which is scale-free -- it asks "how much did the reading MOVE while the hand
    only turned", a question the true distance never enters.
  ⭐ The ratio quantities are scale-free by construction (a length over a length).

────────────────────────────────────────────────────────────────────────────────
WHAT IT MEASURES, AND WHAT EACH NUMBER DECIDES

  §4.1  CROSS-TALK. Each scale-free ratio's response across the 7 declared holds,
        on the YAW takes vs the PITCH takes.
        ⇒ if a ratio moves under one axis and not the other, two independent 1-D
          tables are enough. If every ratio moves under both, the table must be
          2-D -- which the protocol anticipates and which is a real answer, not a
          failure.

        ⚠ THE DEGENERACY TO EXPECT, stated up front so a null is not read as a
        bug: under ORTHOGRAPHIC projection a rigid planar palm scales by cos(yaw)
        horizontally and cos(pitch) vertically, so the quad's shape yields ONE
        scale-free number and `Rwl = w/l` carries `cos(yaw)/cos(pitch)` -- pooled,
        by geometry. Anything that separates the axes must come from a cue
        orthography does not have: PERSPECTIVE (`Rdiag`) or the palm's own
        OUT-OF-PLANE shape (`Rbow`, the measured 10.6 mm knuckle-row bow).
        ⭐ That is precisely why those two are in the vector.

  §8.1  THE DEPTH BIAS CURVE. The SHIPPED relative anchor (`palm_depth.
        DepthRatioTracker`, frozen at the 0° hold) driven through the sweep. The
        hand is at a fixed distance, so a perfect anchor reads 1.000 at every
        hold; whatever it actually reads is FALSE DEPTH FROM ROTATION ALONE.
        ⇒ `palm_depth.py` admits "~9% false depth during rotation" from a CV over
          an UNLABELLED take. These takes carry a DECLARED angle, so the scalar
          becomes a CURVE -- and a curve can be inverted, a scalar cannot.

  §8.2  IS IT THE ESTIMATOR OR THE ARM?
        ⛔⛔ THE 180° RETURN TEST WAS TRIED FIRST AND IT DOES NOT WORK. It assumed
        palm-on and back-on project the SAME spans, so a return to 1.00 would mean
        the hand had not moved. ⚠ The spans refute that premise: at the 180° hold
        three of the four sit at 0.83-0.92 while one reads 0.94-1.08. `max4`
        reports that one, so "it returned" only ever meant "one span returned",
        which a ~12% retreat produces just as readily. The column is still printed,
        with its verdict, because the shape is informative -- but it is NOT a drift
        bound and the "<=7%, ~3.5 cm" first read off it is RETRACTED.

        ⭐⭐ §8.2b IS THE TEST THAT WORKS, and it needs a single frame. At the
        square 0° hold, ask what depth each of the four spans implies ON ITS OWN.
        They see the same hand at the same instant, so the arm cannot enter --
        and they disagree by 13-22%. That disagreement becomes a STEP in the
        absolute estimator every time `min` switches which span wins.

  ⭐ A PREDICTION THIS RUN TESTS, written before seeing the output: the shipped
    tracker should be HOLDING rather than measuring near 90° on the YAW takes
    (edge_on 0.13–0.28 there) and measuring throughout on the PITCH takes
    (edge_on 0.94–1.00 -- `edge_on_measure` is blind to pitch, T6 side finding).
    If so, the false depth is not symmetric between the two axes and pitch
    carries the whole of it.

  ⛔ RESULT 2026-08-26: RIGHT ABOUT THE ASYMMETRY, WRONG ABOUT WHICH ESTIMATOR.
    The RELATIVE tracker never holds -- `held% = 0` at every hold of all six
    takes, including the 90° yaw hold where `edge_on` bottoms out at 0.12. S10's
    freeze, which the prediction was read off, has been REPLACED there by a
    PER-SPAN gate: edge-on no longer freezes anything on its own, it only removes
    the spans edge-on actually destroyed, and a survivor above `MIN_SPAN_FRACTION`
    was always available.
    ⭐ The predicted asymmetry is real, but it belongs to the ABSOLUTE tracker,
    where the S10 band IS still the gate: `aheld% = 100%` at the 90° YAW hold of
    the far take (15.0% of that take's frames), against 1.1% on its PITCH pair and
    0% on the other four takes.
    ⚠ CORRECTED: an earlier version of this note said "0% at every PITCH hold".
    That is wrong -- the far pitch take refuses on 8% of its 120° hold, the tail of
    an exit-hysteresis dwell. The asymmetry is 15.0% vs 1.1%, not 15% vs nothing.
    ⭐ It still means a hand turned like a page can leave the snap gate with no
    depth at all, while the same turn about the other axis leaves it with a WRONG
    one and no indication.

────────────────────────────────────────────────────────────────────────────────
METHOD NOTES — read before trusting a number

  * ⭐ The depth curve uses the SHIPPED `DepthRatioTracker`, frozen and stepped,
    not a re-derivation of it. "A recomputation is a second implementation that
    can silently disagree with the real one" (METHOD.md). The un-rate-limited
    `max4` is reported BESIDE it so the rate limiter's contribution is visible,
    never instead of it.
  * Only `on_axis` frames with exactly one hand are used -- the takes are
    on-axis by construction, but the flag is honoured rather than assumed.
  * ⚠ Only the HOLDS are recorded (7 x 40 frames); the rotation between them is
    not. So consecutive frames JUMP between poses, and the tracker's 12%/frame
    rate limit needs time to converge. Per-hold values are taken over the LAST
    `SETTLE_TAIL` frames of each hold for that reason, and the settling is
    reported so the choice can be checked.
  * The handedness LABEL is ignored entirely (it is 10.8% wrong, and every
    quantity here is a distance or a ratio of distances, so chirality never
    enters).
  * ⚠ Take 2 stores `declared_depth_m: null`; the owner supplied 0.35 m on
    2026-08-26. It is used ONLY to label the depth pair, never in a computation.
  * ⚠ An earlier take 1 (`164023`) carries the superseded 25.71° grid. The rule
    here is "the LAST take of each (axis, tag) pair wins"; anything dropped is
    PRINTED, never silently.

    .venv/Scripts/python.exe analysis/t6_ratio_analysis.py [--root DIR] [--json OUT]
"""
import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry as PG                    # noqa: E402
from Resources import palm_depth as PD                       # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                            # pragma: no cover
    pass

DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline"

WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 0, 5, 9, 13, 17

# Frames at the END of each 40-frame hold used for that hold's value. The
# tracker's rate limit is 12%/frame, so ~20 frames covers any jump the sweep can
# produce; the report prints how much the value still moves over that tail.
SETTLE_TAIL = 20

# ⚠ Owner-supplied 2026-08-26, NOT recorded by the tool. Labels the depth pair.
DECLARED_DEPTH_OVERRIDE = {"2026-08-26_164611_ratio_calib_pitch_right_dA": 0.35}


# ---------------------------------------------------------------- small helpers
def _median(xs):
    xs = sorted(x for x in xs if x is not None and x == x)
    if not xs:
        return float("nan")
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _fmt(v, nd=3):
    return "  n/a" if v != v else ("%.*f" % (nd, v))


# ------------------------------------------------------------- the ratio vector
# ⭐ Every one of these is a LENGTH OVER A LENGTH, so the standing distance
# cancels exactly. That is the whole reason caveat zero cannot reach them.
def ratios(lm):
    """The scale-free 2D shape descriptors, or None if the landmarks are unusable."""
    if not lm or len(lm) < 18:
        return None
    w = _dist(lm[INDEX_MCP], lm[PINKY_MCP])         # knuckle row, full 2D length
    l = _dist(lm[WRIST], lm[MIDDLE_MCP])            # palm length, full 2D length
    if w <= 1e-6 or l <= 1e-6:
        return None

    d_idx = _dist(lm[WRIST], lm[INDEX_MCP])         # the two palm diagonals
    d_pky = _dist(lm[WRIST], lm[PINKY_MCP])

    # bow: perpendicular offset of the middle MCP from the knuckle row, over the
    # row's own length. The row bows 10.6 mm OUT OF PLANE, so this is one of only
    # two cues that survive the orthographic degeneracy.
    ax, ay = lm[INDEX_MCP][0], lm[INDEX_MCP][1]
    bx, by = lm[PINKY_MCP][0], lm[PINKY_MCP][1]
    cx, cy = lm[MIDDLE_MCP][0], lm[MIDDLE_MCP][1]
    cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    # roll-SENSITIVE component version, kept deliberately: comparing it with the
    # roll-invariant Rwl says whether the operator's hand was rolled in the takes.
    wx = abs(lm[INDEX_MCP][0] - lm[PINKY_MCP][0])
    ly = abs(lm[WRIST][1] - lm[MIDDLE_MCP][1])

    return {
        "Rwl":   w / l,                             # roll-invariant primary
        "Rxy":   (wx / ly) if ly > 1e-6 else float("nan"),   # roll-sensitive twin
        "Rdiag": d_idx / d_pky,                     # perspective asymmetry
        "Rbow":  cross / (w * w),                   # out-of-plane shape, SIGNED
        "Rarea": abs(cross) / (w * l),              # quad compactness
    }


RATIO_KEYS = ("Rwl", "Rxy", "Rdiag", "Rbow", "Rarea")


# ------------------------------------------------------------------ take loading
def load_take(meta_path):
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    sess = os.path.basename(os.path.dirname(meta_path))
    jl = os.path.join(os.path.dirname(meta_path), "raw_landmarks.jsonl")
    if not os.path.exists(jl):
        return None

    frames = []
    with open(jl, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            hands = r.get("hands") or []
            if len(hands) != 1 or not r.get("on_axis"):
                continue
            lm = hands[0].get("landmarks")
            if not lm or len(lm) < 18:
                continue
            frames.append({
                "pos": r.get("position_index"),
                "deg": r.get("declared_deg"),
                "alpha": r.get("alpha_deg"),
                "offset": r.get("palm_offset_px"),
                "lm": lm,
            })
    if not frames:
        return None

    return {
        "session": sess,
        "axis": meta.get("axis"),
        "tag": sess.rsplit("_", 1)[-1],
        "declared_depth_m": (meta.get("declared_depth_m")
                             or DECLARED_DEPTH_OVERRIDE.get(sess)),
        "declared_depth_is_recalled": (meta.get("declared_depth_m") is None
                                       and sess in DECLARED_DEPTH_OVERRIDE),
        "frame_size": meta.get("frame_size") or [640, 480],
        "angles": meta.get("declared_angles_deg") or [],
        "frames": frames,
    }


def discover(root):
    """Every ratio-calibration take, latest-per-(axis, tag) winning. Drops PRINTED."""
    metas = sorted(glob.glob(os.path.join(root, "**", "sessions",
                                          "*ratio_calib*", "meta.json"),
                             recursive=True))
    takes = [t for t in (load_take(m) for m in metas) if t]
    best, dropped = {}, []
    for t in sorted(takes, key=lambda x: x["session"]):
        key = (t["axis"], t["tag"])
        if key in best:
            dropped.append((best[key]["session"], t["session"]))
        best[key] = t
    order = {"dA": 0, "dB": 1, "dC": 2}
    return (sorted(best.values(),
                   key=lambda t: (order.get(t["tag"], 9), t["axis"])), dropped)


# ------------------------------------------------------------------- measurement
def per_hold(take):
    """Per declared hold: ratio medians, edge_on, and both depth readings.

    ⭐ The shipped `DepthRatioTracker` is FROZEN at the 0° hold and then stepped
    through every frame in order, so the number reported is the one the pipeline
    would actually have produced -- not a second implementation of it.
    """
    fs = take["frame_size"]
    focal = PG.focal_px(fs)
    tracker = PD.DepthRatioTracker()
    # ⛔ CORRECTED 2026-08-26: the absolute column was first computed by
    # re-implementing min-over-spans here -- the exact second implementation this
    # file cites METHOD.md against two paragraphs above. `HandDepthTracker` also
    # REFUSES inside the edge-on band (unlike the ratio tracker, the S10 band IS
    # its gate), so a hand-rolled version silently published readings the pipeline
    # would never have used. It is now stepped, like the ratio tracker.
    absolute = PD.HandDepthTracker()

    holds = {}
    for f in take["frames"]:
        holds.setdefault(f["pos"], []).append(f)
    positions = sorted(holds)

    # baseline spans: the 0° hold's medians, for the un-rate-limited max4 twin
    base_frames = holds[positions[0]]
    base_spans = [_median([PD.palm_spans(f["lm"])[i] for f in base_frames])
                  for i in range(len(PD.PALM_SPANS))]

    # freeze the shipped tracker on the 0° hold, mid-way through it
    tracker.freeze(base_frames[len(base_frames) // 2]["lm"])

    out = []
    for p in positions:
        fr = holds[p]
        ship_seq, raw4, absd, eos, rats, alphas = [], [], [], [], [], []
        held = 0
        abs_held = 0
        abs_band = 0
        for f in fr:
            lm = f["lm"]
            ratio, valid = tracker.update(lm)
            ship_seq.append(ratio)
            if not valid:
                held += 1
            # ⛔ the two reasons `HandDepthTracker` returns invalid are DIFFERENT
            # failures and were conflated in the first version: the S10 band (the
            # palm collapsed, a deliberate refusal) vs `measure()` returning None
            # (landmarks unusable). Ask the class which one it was.
            a_m, a_valid = absolute.update(lm, fs)
            if a_valid and a_m:
                absd.append(a_m)
            else:
                abs_held += 1
                if absolute.in_band:
                    abs_band += 1
            spans = PD.palm_spans(lm)
            if spans:
                norm = [s / b for s, b in zip(spans, base_spans) if b > 1e-6]
                if norm:
                    raw4.append(max(norm))
            eos.append(PG.edge_on_measure(lm))
            rr = ratios(lm)
            if rr:
                rats.append(rr)
            if f["alpha"] is not None:
                alphas.append(abs(f["alpha"]))

        tail = [v for v in ship_seq[-SETTLE_TAIL:] if v is not None]
        out.append({
            "pos": p,
            "deg": fr[0]["deg"],
            "n": len(fr),
            "ship": _median(tail),
            "ship_tail_swing": (max(tail) - min(tail)) if tail else float("nan"),
            "held_frac": held / float(len(fr)),
            "abs_held_frac": abs_held / float(len(fr)),
            "abs_band_frac": abs_band / float(len(fr)),
            # ⚠ is the settled tail still CONVERGING (monotone) or just noisy?
            # |last - first| ~ the tail's full range means the rate limiter had
            # not finished, and the per-hold value is then an underestimate.
            "tail_drift": (abs(tail[-1] - tail[0]) if len(tail) > 1 else float("nan")),
            "raw4": _median(raw4[-SETTLE_TAIL:]),
            "abs_m": _median(absd),
            "edge_on": _median(eos),
            "alpha": _median(alphas),
            "ratios": {k: _median([r[k] for r in rats]) for k in RATIO_KEYS},
        })
    return out


SPAN_NAMES = ("w5-17", "l0-9", "d0-5", "d0-17")


def _span_depths_at_square(take):
    """Depth implied by EACH span on its own, at the square 0° hold, in metres.

    ⭐ Drift-free by construction: all four read the same frames, so the arm
    cannot move between one span and another. Their disagreement is purely
    `NOMINAL_SPAN_M` against this operator's hand.
    """
    holds = {}
    for f in take["frames"]:
        holds.setdefault(f["pos"], []).append(f)
    if not holds:
        return None
    lms = [f["lm"] for f in holds[sorted(holds)[0]]]
    focal = PG.focal_px(take["frame_size"])
    out = []
    for i, pair in enumerate(PD.PALM_SPANS):
        vals = []
        for lm in lms:
            sp = PD.palm_spans(lm)
            if sp and sp[i] > 1e-6:
                vals.append(focal * PD.NOMINAL_SPAN_M[pair] / sp[i])
        out.append(_median(vals))
    return out if all(v == v for v in out) else None


def _selection_trace(take):
    """Which span index each estimator selects at each hold: (relative, absolute).

    `rel` maximises `px/px_at_0°` (least foreshortened relative to its own
    baseline); `abs` minimises `f*S_nominal/px`, i.e. maximises `px/S_nominal`.
    """
    holds = {}
    for f in take["frames"]:
        holds.setdefault(f["pos"], []).append(f)
    positions = sorted(holds)
    focal = PG.focal_px(take["frame_size"])

    def spans_at(p):
        return [_median([PD.palm_spans(f["lm"])[i] for f in holds[p]])
                for i in range(len(PD.PALM_SPANS))]

    base = spans_at(positions[0])
    rel_sel, abs_sel = [], []
    for p in positions:
        sp = spans_at(p)
        rel_sel.append(max(range(len(sp)), key=lambda i: sp[i] / base[i]))
        abs_sel.append(min(range(len(sp)),
                           key=lambda i: focal * PD.NOMINAL_SPAN_M[PD.PALM_SPANS[i]] / sp[i]))
    return rel_sel, abs_sel


# ----------------------------------------------------------------------- report
# ⛔⛔ A METRIC THAT WAS TRIED FIRST AND IS WRONG — kept as a comment because the
# failure is instructive and someone will otherwise re-derive it.
#
#     response = (max - min) / |median across the holds|
#
# It is degenerate on exactly this data, in two separate ways:
#   1. `Rwl = w/l` DIVIDES BY A SPAN THAT GOES TO ZERO. At the 90° PITCH hold the
#      palm length projects to almost nothing, so Rwl explodes and the "response"
#      measures the singularity, not the shape. It read 2.880 on pitch-dB.
#   2. `Rbow` is SIGNED and CROSSES ZERO through a sweep, so |median| can sit near
#      zero and the quotient blows up regardless of how little the bow moved.
# ⚠ It also produced a confident-looking verdict ("YES x3.7") for a ratio that in
# fact moves hugely under BOTH axes. A separation test must compare EXCURSIONS,
# not the ratio of two large numbers.
#
# ⭐ What replaces it: work in LOG space for the strictly-positive ratios (a
# reciprocal is then just a sign flip, and the 90° singularity becomes a large
# finite number instead of an infinity), LINEAR for the signed ones, and measure
# the excursion over the 0°->90° QUARTER only. Past 90° a cosine folds back, so a
# full-sweep range confuses "moved a lot" with "came back".
LOG_RATIOS = ("Rwl", "Rxy", "Rdiag")


def _excursion(by_deg, key):
    """Signed 0°->90° excursion, in log space for positive ratios.

    ⭐ This is the quantity a 1-D table needs: how far the ratio TRAVELS as the
    hand turns a quarter turn. A ratio that separates the axes travels under one
    and stays put under the other.
    """
    lo = by_deg.get(0.0, {}).get("ratios", {}).get(key)
    hi = by_deg.get(90.0, {}).get("ratios", {}).get(key)
    if lo is None or hi is None or lo != lo or hi != hi:
        return float("nan")
    if key in LOG_RATIOS:
        if lo <= 1e-9 or hi <= 1e-9:
            return float("nan")
        return math.log(hi / lo)
    return hi - lo


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--json", default=None, help="also write the raw table here")
    a = ap.parse_args()

    takes, dropped = discover(a.root)
    if not takes:
        print("no ratio_calib takes under %s" % a.root)
        return 1

    w = 96
    print("=" * w)
    print("  T6 RATIO-TABLE ANALYSIS — protocol §4.1 (cross-talk) and §8.1–8.2 (depth)")
    print("  ⛔ caveat zero: every depth number below is normalised to its OWN take's")
    print("     0° hold. The true standing distance is used NOWHERE.")
    print("=" * w)
    for old, new in dropped:
        print("  ⚠ superseded, not analysed: %s  (replaced by %s)" % (old, new))

    tables = {}
    print()
    print("  %-46s %-6s %-8s %6s %7s" % ("take", "axis", "depth", "holds", "frames"))
    for t in takes:
        rows = per_hold(t)
        tables[t["session"]] = rows
        dd = t["declared_depth_m"]
        lbl = ("%.2f m%s" % (dd, "*" if t["declared_depth_is_recalled"] else "")
               if dd else "n/a")
        print("  %-46s %-6s %-8s %6d %7d"
              % (t["session"][:46], t["axis"], lbl, len(rows), len(t["frames"])))
    print("  * = owner-recalled, not recorded by the tool")

    # ---------------------------------------------------------------- §4.2
    print()
    print("-" * w)
    print("  §4.2  THE TABLE ITSELF — median ratio vector per declared hold")
    print("-" * w)
    print("  ⭐ This IS the table the protocol asks for. Everything after it is read")
    print("    off these rows, so they are printed rather than summarised away.")
    for k in RATIO_KEYS:
        print()
        print("  %-6s %-40s %s" % (k, "take", "".join("%8.0f°" % d
                                                      for d in (0, 30, 60, 90, 120, 150, 180))))
        for t in takes:
            rows = tables[t["session"]]
            by_deg = {h["deg"]: h for h in rows}
            cells = "".join("%9s" % _fmt(by_deg.get(float(d), {}).get("ratios", {}).get(k), 3)
                            for d in (0, 30, 60, 90, 120, 150, 180))
            print("  %-6s %-40s %s" % ("", "%-5s %s" % (t["axis"], t["tag"]), cells))

    # ---------------------------------------------------------------- §4.1
    print()
    print("-" * w)
    print("  §4.1  CROSS-TALK — does a ratio move under ONE axis and stay put under")
    print("        the other? Signed 0°→90° excursion (log space where positive).")
    print("-" * w)
    print("  %-8s %26s %26s %6s %-13s" % ("ratio", "YAW takes (dA/dB/dC)",
                                          "PITCH takes (dA/dB/dC)", "|mag|", "SIGN"))
    for k in RATIO_KEYS:
        cells = {"yaw": [], "pitch": []}
        for t in takes:
            by_deg = {h["deg"]: h for h in tables[t["session"]]}
            cells[t["axis"]].append(_excursion(by_deg, k))
        y = " ".join("%+8.3f" % v for v in cells["yaw"])
        p = " ".join("%+8.3f" % v for v in cells["pitch"])
        # |excursion under the weaker axis| / |excursion under the stronger one|.
        # 0 = one axis moves it and the other does not. 1 = MAGNITUDE cannot tell
        # the two apart -- which orthography says is the expected answer.
        my = abs(_median([abs(v) for v in cells["yaw"]]))
        mp = abs(_median([abs(v) for v in cells["pitch"]]))
        if my != my or mp != mp or max(my, mp) < 1e-9:
            mag = "n/a"
        else:
            mag = "%.2f" % (min(my, mp) / max(my, mp))
        # ⭐ THE QUESTION MAGNITUDE MISSES: does the excursion's SIGN separate them?
        sy = set(v > 0 for v in cells["yaw"] if v == v)
        sp = set(v > 0 for v in cells["pitch"] if v == v)
        if len(sy) == 1 and len(sp) == 1 and sy != sp:
            sign = "SPLITS 3/3"
        elif len(sy) == 1 and len(sp) == 1:
            sign = "same sign"
        else:
            sign = "inconsistent"
        print("  %-8s %26s %26s %6s %-13s" % (k, y, p, mag, sign))
    print()
    print("  ⭐ Rwl/Rxy are EXPECTED to move under both — orthography makes them")
    print("    carry cos(yaw)/cos(pitch), which is pooled by geometry, not by a bug.")
    print("  ⭐ Rdiag (perspective) and Rbow (the 10.6 mm out-of-plane bow) are the")
    print("    only two cues that CAN break that degeneracy. Read their rows first.")
    print("  ⚠ Rwl vs Rxy: a large gap means the hand was ROLLED during the takes,")
    print("    because Rwl is roll-invariant and Rxy is not.")
    print("  ⛔ '|mag|' near 1.00 means MAGNITUDE cannot tell the axes apart — which")
    print("    is what orthography predicts, not a defect in the ratio.")
    print("  ⭐⭐ 'SPLITS 3/3' means the excursion's SIGN does what its magnitude could")
    print("    not: one axis drives the ratio DOWN, the other UP, with no overlap over")
    print("    the six takes. ⚠ It is only a discriminator while the rotation is about")
    print("    ONE axis at a time — a mixed pose puts cos(yaw)/cos(pitch) back into a")
    print("    single equation with two unknowns, and the table must then be 2-D.")

    # ---------------------------------------------------------------- §8.1
    print()
    print("-" * w)
    print("  §8.1  FALSE DEPTH FROM ROTATION ALONE — shipped anchor, hand at a fixed")
    print("        distance, normalised to each take's own 0° hold. Perfect = 1.000")
    print("-" * w)
    for t in takes:
        rows = tables[t["session"]]
        print()
        print("  %s   [%s, depth %s]"
              % (t["session"], t["axis"],
                 ("%.2f m" % t["declared_depth_m"]) if t["declared_depth_m"] else "n/a"))
        print("      %-10s %9s %9s %9s %9s %7s %7s %8s"
              % ("declared", "SHIPPED", "raw max4", "abs m", "abs/0°",
                 "held%", "aheld%", "edge_on"))
        a0 = rows[0]["abs_m"]
        for h in rows:
            rel_abs = (h["abs_m"] / a0) if (a0 and a0 == a0) else float("nan")
            print("      %7.0f°   %9s %9s %9s %9s %6.0f%% %6.0f%% %8s"
                  % (h["deg"], _fmt(h["ship"]), _fmt(h["raw4"]),
                     _fmt(h["abs_m"]), _fmt(rel_abs),
                     100.0 * h["held_frac"], 100.0 * h["abs_held_frac"],
                     _fmt(h["edge_on"], 2)))
        peak = max(abs(h["ship"] - 1.0) for h in rows if h["ship"] == h["ship"])
        peak4 = max(abs(h["raw4"] - 1.0) for h in rows if h["raw4"] == h["raw4"])
        # ⛔ the ABSOLUTE estimator's worst excursion was EYEBALLED off this table
        # in the first pass, and misread by a factor of two. It is computed now:
        # "a number that is not printed is an assertion, not a finding".
        abs_dev = [abs(h["abs_m"] / a0 - 1.0) for h in rows
                   if a0 and h["abs_m"] == h["abs_m"]]
        peaka = max(abs_dev) if abs_dev else float("nan")
        swing = max(h["ship_tail_swing"] for h in rows)
        drift = max(h["tail_drift"] for h in rows if h["tail_drift"] == h["tail_drift"])
        band = sum(h["abs_band_frac"] for h in rows) / len(rows)
        unus = sum(h["abs_held_frac"] - h["abs_band_frac"] for h in rows) / len(rows)
        print("      ⇒ worst false depth:  RELATIVE shipped %+.1f%% (raw max4 %+.1f%%)"
              "   ABSOLUTE %+.1f%%" % (100.0 * peak, 100.0 * peak4, 100.0 * peaka))
        print("      ⇒ absolute refused on %.1f%% of frames for the S10 BAND, %.1f%%"
              " for unusable landmarks" % (100.0 * band, 100.0 * unus))
        print("      ⇒ settled tail: range %.4f, end-to-end drift %.4f"
              "  (drift << range = converged, just noisy)" % (swing, drift))

    # ---------------------------------------------------------------- §8.2
    print()
    print("-" * w)
    print("  §8.2  IS THE CLIMB THE ESTIMATOR OR THE ARM?")
    print("-" * w)
    print("  FORESHORTENING: symmetric about 90°, RETURNS at 180°, and SUPERPOSES")
    print("  across takes once each is normalised to its own 0°.")
    print("  DRIFT: monotone, take-specific, indifferent to 90°.")
    print()
    print("  ⭐⭐ AND A THIRD SIGNATURE THAT NEEDS NEITHER — the SELECTION statistic.")
    print("  ⛔ CORRECTED 2026-08-26: the first version of this column used the RATIO")
    print("  `(abs/0°) / max4` and called it distance-free. IT IS THE OPPOSITE. Under")
    print("  a pure retreat by factor k every span scales by k, so `max4` = k while")
    print("  `abs/0°` = 1/k — they move in OPPOSITE directions, and the ratio goes as")
    print("  1/k², AMPLIFYING the drift it was meant to cancel. A 10% retreat alone")
    print("  fabricates 1.23 there. The quantity that cancels is the PRODUCT:")
    print()
    print("      sel = max4 × (abs/0°)     = 1.000 exactly under any pure distance")
    print("                                  change, and >= 1 always (proof: the max")
    print("                                  of a product <= the product of the maxes)")
    print()
    print("  ⭐ So `sel` measures ONE thing: how far apart the two estimators' span")
    print("  SELECTIONS drift under foreshortening. The arm cannot enter it.")
    print()
    print("  %-40s %9s %9s %8s %8s %8s"
          % ("take", "180°/0°", "sym err", "min at", "worst", "verdict"))
    for t in takes:
        rows = tables[t["session"]]
        by_deg = {h["deg"]: h for h in rows}
        v0 = by_deg.get(0.0, {}).get("raw4")
        v180 = by_deg.get(180.0, {}).get("raw4")
        ret = (v180 / v0) if (v0 and v180 and v0 == v0) else float("nan")
        # distance-free SELECTION statistic: max4 x (abs/0°). See the header above.
        a0 = rows[0]["abs_m"]
        am = float("nan")
        for h in rows:
            if a0 and h["abs_m"] == h["abs_m"] and h["raw4"] == h["raw4"]:
                q = (h["abs_m"] / a0) * h["raw4"]
                if am != am or abs(q - 1.0) > abs(am - 1.0):
                    am = q
        # symmetry: |f(90-d) - f(90+d)| over the mirrored pairs
        errs = []
        for d in (30.0, 60.0):
            lo, hi = by_deg.get(90.0 - d), by_deg.get(90.0 + d)
            if lo and hi and lo["raw4"] == lo["raw4"] and hi["raw4"] == hi["raw4"]:
                errs.append(abs(lo["raw4"] - hi["raw4"]))
        sym = _median(errs) if errs else float("nan")
        cand = [h for h in rows if h["raw4"] == h["raw4"]]
        pk = min(cand, key=lambda h: h["raw4"]) if cand else None
        pkdeg = pk["deg"] if pk else float("nan")
        if ret != ret:
            verdict = "n/a"
        elif abs(ret - 1.0) <= 0.08:
            verdict = "returns"
        else:
            verdict = "ARM"
        print("  %-40s %9s %9s %7.0f° %8s %8s"
              % (t["session"][:40], _fmt(ret), _fmt(sym), pkdeg, _fmt(am), verdict))
    print()
    print("  ⛔⛔ '180°/0°' WAS READ AS A DRIFT BOUND ON 2026-08-26. THAT IS RETRACTED.")
    print("    The reading assumed palm-on and back-on project the SAME spans, so a")
    print("    return to 1.00 would mean the hand had not moved. ⚠ The spans refute the")
    print("    premise: at the 180° hold THREE of the four sit at 0.83–0.92 while one")
    print("    reads 0.94–1.08 (spread 0.09–0.25). `max4` reports that one. So a return")
    print("    means 'at least one span came back', which a ~12% retreat would produce")
    print("    just as readily. ⛔ These takes cannot bound the drift, and the earlier")
    print("    '<=7%, ~3.5 cm' does not stand. §8.2b below needs no such premise.")
    print("  ⚠ 'min at' is the hold whose anchor read SMALLEST, i.e. farthest away.")
    print("  ⭐⭐ 'worst' is `sel` — 1.00 would mean the two estimators select the same")
    print("    span throughout. It is >= 1 by construction, so its DIRECTION carries no")
    print("    information; only its SIZE does, and the arm cannot contribute to it.")

    # ---------------------------------------------------------------- §8.2b
    print()
    print("-" * w)
    print("  §8.2b  WHY THE ABSOLUTE ESTIMATOR MOVES — and it is not foreshortening")
    print("-" * w)
    print("  ⭐⭐ THE CLEANEST EVIDENCE IN THIS FILE, because it needs ONE FRAME: at the")
    print("  SQUARE 0° hold, what depth does each of the four spans imply ON ITS OWN?")
    print("  They all see the same hand at the same instant, so they must agree. Any")
    print("  disagreement is `NOMINAL_SPAN_M` vs THIS user, and it is drift-free by")
    print("  construction — the arm cannot move between a frame and itself.")
    print()
    print("  %-30s %s %9s" % ("take", "".join("%9s" % n for n in SPAN_NAMES), "spread"))
    for t in takes:
        z = _span_depths_at_square(t)
        if not z:
            continue
        print("  %-30s %s %8.1f%%"
              % (t["session"][16:46], "".join("%9.3f" % v for v in z),
                 100.0 * (max(z) - min(z)) / min(z)))
    print()
    print("  ⇒ `min` over these IS the absolute estimator. When rotation changes which")
    print("    span wins, the output STEPS by that disagreement — no foreshortening")
    print("    required. The relative form is immune: each span is normalised to its")
    print("    OWN 0° baseline, which absorbs the per-span nominal error exactly.")
    print()
    print("  WHICH SPAN EACH ESTIMATOR SELECTS, hold by hold:")
    for t in takes:
        rel_sel, abs_sel = _selection_trace(t)
        print("  %-30s rel %s" % (t["session"][16:46],
                                  " ".join("%-6s" % SPAN_NAMES[i] for i in rel_sel)))
        print("  %-30s abs %s" % ("", " ".join("%-6s" % SPAN_NAMES[i] for i in abs_sel)))
    print()
    print("  ⚠ Read this per AXIS, not as one rule. On the YAW takes `abs` sits on the")
    print("    same span through almost the whole sweep while `rel` moves through four")
    print("    of them. On the PITCH takes it is the reverse — `rel` holds the knuckle")
    print("    width, which pitch does not foreshorten, and `abs` is the one that")
    print("    wanders. ⭐ In both cases it is `rel` that tracks WHICH SPAN THE POSE")
    print("    LEFT INTACT, which is the property a depth anchor needs.")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({t["session"]: tables[t["session"]] for t in takes},
                      fh, indent=1)
        print("\n  raw table -> %s" % a.json)
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
