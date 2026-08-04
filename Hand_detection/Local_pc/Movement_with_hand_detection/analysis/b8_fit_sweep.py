"""B8 -- optimise the quadratic. Judged on PREDICTION ERROR, not gate behaviour.

`BUILD_PREDICTION_GATE.md` 2. A SEPARATE LEVER from B7 and not to be conflated
with it: B8 improves how accurately the next value is predicted; B7 decides when
to trust the measurement. Optimising weights alone would improve jitter and leave
B3'''s reversal ratio roughly intact -- that was already measured.

WHAT IS SWEPT
    weighting   uniform | exp(half-life 2/3/5 frames) | linear ramp
                ⚠ the shipped fit is UNWEIGHTED -- the most obviously wrong part,
                since a 7-frame window counts a 290 ms-old sample as heavily as
                the newest one
    window      5, 7, 9, 11      ⚠ must be >= order+2 or s^2 -- which IS the
                                 distribution -- is meaningless
    order       1 (velocity) | 2 (+acceleration)

NOT swept here, deliberately: `ACCEL_UNCERTAINTY` widens sigma and does not move
the prediction by one pixel, so it cannot show up in a prediction-error table. It
belongs to the gate sweep (`b7_eval.py`), where B3'' already measured it scaling
rejections down without changing the reversal ratio.

⚠ S1, MANDATORY, AND THE REASON THIS SCRIPT EXISTS: a fitted predictor must beat
BOTH the zero-velocity and the constant-velocity baseline AT EVERY HORIZON.
Published predictors have repeatedly lost to those and been shipped anyway. A
config that loses to "hold the last value" is not an improvement, whatever it
does to the gate.

Errors are measured OPEN LOOP on raw streams -- fit over past RAW frames, predict
h ahead, compare against the raw truth. No gate is involved, so no rejection can
cascade into the statistic (the bug 6 failure mode: a closed-loop rejection rate
was read as a motion-model error and reached the spec).

    .venv/Scripts/python.exe analysis/b8_fit_sweep.py [--stride N]
"""
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

import b3_full_eval as B3E
from Resources import block_predictor as BP

HORIZONS = (1, 2, 4, 6)
FAMILY = {"pos_x": "position px", "pos_y": "position px", "scale": "scale px",
          "arc0": "arc (unitless)", "arc1": "arc (unitless)",
          "arc2": "arc (unitless)", "arc3": "arc (unitless)"}

# ⚠ STRATIFY BY SPEED, or the answer is decided by the still-hand majority.
# "Hold the last value" is unbeatable on a stationary hand and hopeless on a
# moving one; a pooled median hides which regime produced the win, and the gate
# only ever coasts on a hand that was MOVING. Bins are in units of the channel's
# own derived noise floor, so they mean the same thing on pixels and on arcs.
SPEED_BINS = (("still <1 floor", 0.0, 1.0),
              ("slow 1-3", 1.0, 3.0),
              ("fast >3", 3.0, float("inf")))

# (label, window, order, weighting, half_life)
CONFIGS = [
    ("BASELINE hold (v=0)", None, None, None, None),
    ("BASELINE const-vel", None, None, None, None),
    ("B3'' w7 o2 uniform", 7, 2, None, 0.0),
    ("w7 o1 uniform", 7, 1, None, 0.0),
    ("w7 o2 exp hl2", 7, 2, "exp", 2.0),
    ("w7 o2 exp hl3", 7, 2, "exp", 3.0),
    ("w7 o2 exp hl5", 7, 2, "exp", 5.0),
    ("w7 o2 linear", 7, 2, "linear", 0.0),
    ("w7 o1 exp hl2", 7, 1, "exp", 2.0),
    ("w7 o1 exp hl3", 7, 1, "exp", 3.0),
    ("w7 o1 linear", 7, 1, "linear", 0.0),
    ("w5 o1 exp hl3", 5, 1, "exp", 3.0),
    ("w9 o1 exp hl3", 9, 1, "exp", 3.0),
    ("w11 o1 exp hl3", 11, 1, "exp", 3.0),
    ("w5 o2 exp hl3", 5, 2, "exp", 3.0),
    ("w9 o2 exp hl3", 9, 2, "exp", 3.0),
    ("w11 o2 exp hl3", 11, 2, "exp", 3.0),
]


def pctl(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def main():
    stride = 1
    if "--stride" in sys.argv:
        stride = int(sys.argv[sys.argv.index("--stride") + 1])

    print("=" * 78)
    print("B8 -- fit sweep, OPEN-LOOP prediction error on raw streams")
    print("=" * 78)
    streams = list(B3E.sessions())
    print(f"streams: {len(streams)} (audit_jump_provenance build_v2 semantics)")

    # err[label][family][h] = list of |measured - predicted|
    err = {c[0]: {f: {h: [] for h in HORIZONS} for f in set(FAMILY.values())}
           for c in CONFIGS}
    # serr[label][speed bin][h] = the same, stratified, pooled in FLOOR units
    serr = {c[0]: {b[0]: {h: [] for h in HORIZONS} for b in SPEED_BINS}
            for c in CONFIGS}
    qerr = {"BASELINE hold (v=0)": {h: [] for h in HORIZONS},
            "BASELINE const-vel": {h: [] for h in HORIZONS},
            "B3'' log-map fit": {h: [] for h in HORIZONS}}
    maxw = max(c[1] for c in CONFIGS if c[1])

    for _name, seq in streams:
        for ch, fam in FAMILY.items():
            vals = [BP.BlockPredictor._scalars(st).get(ch) for st in seq]
            floor = BP.FLOOR.get(ch, 1.0)
            for k in range(maxw, len(vals) - max(HORIZONS), stride):
                past = vals[k - maxw:k]
                if any(p is None for p in past):
                    continue
                truth = {h: vals[k + h - 1] for h in HORIZONS}
                if any(t is None for t in truth.values()):
                    continue
                speed = abs(past[-1] - past[-2]) / floor
                sbin = next(b[0] for b in SPEED_BINS if b[1] <= speed < b[2])
                for label, win, order, wt, hl in CONFIGS:
                    if win is None:
                        if "hold" in label:
                            pred = {h: past[-1] for h in HORIZONS}
                        else:
                            v = past[-1] - past[-2]
                            pred = {h: past[-1] + v * h for h in HORIZONS}
                    else:
                        st = BP.fit_channel(past[-win:], order=order,
                                            weighting=wt, half_life=hl)
                        if st is None:
                            continue
                        pred = {h: st.predict(h) for h in HORIZONS}
                    for h in HORIZONS:
                        e = abs(truth[h] - pred[h])
                        err[label][fam][h].append(e)
                        serr[label][sbin][h].append(e / floor)

        quats = [st.get("quaternion") for st in seq]
        for k in range(maxw, len(quats) - max(HORIZONS), stride):
            past = quats[k - maxw:k]
            if any(q is None for q in past):
                continue
            truth = {h: quats[k + h - 1] for h in HORIZONS}
            if any(t is None for t in truth.values()):
                continue
            qst = BP.fit_quat(past[-7:])
            step = BP._qlog(BP._qmul(past[-1], BP._qconj(past[-2])))
            for h in HORIZONS:
                qerr["BASELINE hold (v=0)"][h].append(
                    BP._qangle(past[-1], truth[h]))
                cv = BP._qmul(BP._qexp(tuple(s * h for s in step)), past[-1])
                qerr["BASELINE const-vel"][h].append(BP._qangle(cv, truth[h]))
                if qst is not None:
                    qerr["B3'' log-map fit"][h].append(
                        BP._qangle(qst.predict(h), truth[h]))

    for fam in sorted(set(FAMILY.values())):
        print("\n" + "=" * 78)
        print(f"{fam}   -- median |error| (p95 in brackets), by horizon")
        print("=" * 78)
        head = f"  {'config':<22}"
        for h in HORIZONS:
            head += f"{'h=' + str(h):>18}"
        print(head)
        base = {}
        for label, _w, _o, _wt, _hl in CONFIGS:
            row = f"  {label:<22}"
            for h in HORIZONS:
                e = err[label][fam][h]
                row += f"{pctl(e,50):>9.4f}[{pctl(e,95):>7.3f}]"
                if label.startswith("BASELINE"):
                    base.setdefault(h, []).append(pctl(e, 50))
            print(row)
        print("  " + "-" * 74)
        best = min((sum(pctl(err[c[0]][fam][h], 50) / min(base[h])
                        for h in HORIZONS), c[0])
                   for c in CONFIGS if not c[0].startswith("BASELINE"))
        print(f"  S1 CHECK -- must beat BOTH baselines at EVERY horizon:")
        for label, w, _o, _wt, _hl in CONFIGS:
            if w is None:
                continue
            wins = [pctl(err[label][fam][h], 50) < min(base[h]) for h in HORIZONS]
            if all(wins):
                print(f"    PASS  {label}")
        fails = [c[0] for c in CONFIGS if c[1] and
                 not all(pctl(err[c[0]][fam][h], 50) < min(base[h])
                         for h in HORIZONS)]
        if fails:
            print(f"    FAIL  {', '.join(fails)}")
        print(f"  best by summed normalised median error: {best[1]}")

    print("\n" + "=" * 78)
    print("⭐ STRATIFIED BY SPEED -- median |error| in units of the channel floor")
    print("   (all scalar channels pooled; the pooled table above is decided by")
    print("    the still-hand majority, and the gate only coasts on a MOVING hand)")
    print("=" * 78)
    for bname, _lo, _hi in SPEED_BINS:
        n = len(serr[CONFIGS[0][0]][bname][1])
        print(f"\n  {bname}   n={n}")
        head = f"    {'config':<22}"
        for h in HORIZONS:
            head += f"{'h=' + str(h):>10}"
        print(head)
        for label, _w, _o, _wt, _hl in CONFIGS:
            row = f"    {label:<22}"
            for h in HORIZONS:
                row += f"{pctl(serr[label][bname][h], 50):>10.3f}"
            print(row)

    print("\n" + "=" * 78)
    print("orientation (deg) -- median |error| (p95 in brackets)")
    print("=" * 78)
    head = f"  {'config':<22}"
    for h in HORIZONS:
        head += f"{'h=' + str(h):>18}"
    print(head)
    for label, d in qerr.items():
        row = f"  {label:<22}"
        for h in HORIZONS:
            e = [x for x in d[h] if x is not None]
            row += f"{pctl(e,50):>9.4f}[{pctl(e,95):>7.3f}]"
        print(row)
    print("=" * 78)


if __name__ == "__main__":
    main()
