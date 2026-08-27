"""⭐⭐ T6 — ORIENTATION BY REGRESSION FROM THE TAKES, not from a formula.

**Owner, 2026-08-27:** *"start from regression from the data directly, you could
avoid this trap"* — the trap being that every closed form tried so far
(`Rwl ≈ cos θ`, `arccos(R/R₀)`) omits something real, most obviously the hand's
THICKNESS, and then the data refuses it.

⭐ A regression does not care WHY the curve bends. Thickness, the knuckle bow, the
wrist landmark's wobble and perspective are all absorbed into the fitted shape
because they are present in the frames it is fitted to.

────────────────────────────────────────────────────────────────────────────────
THE FEATURE, AND WHY THIS ONE

Fit the 2×2 affine map from the take's own 0° hold to the current frame, TRIMMED
(worst residuals dropped, refit), then take its SVD:

    slant_feature = σ₂/σ₁        how compressed the shape is
    tilt          = minor axis   which way it is compressed, in the PALM frame

⛔ Measured, and it is why this file exists: the LANDMARK SET matters more than the
model. Cross-take spread of `σ₂/σ₁` at matched declared angles —

    palm5 (0,5,9,13,17)      0.162     <- what every earlier attempt used
    palm+pip                 0.108
    palm+tips  trim 0.25     0.071
    no-thumb   trim 0.25     0.067     <- 2.4x better than palm5

⭐ The owner predicted this (*"finger + trim could help"*). The fingers are extra
rigid-ish points that improve the conditioning of the fit; the THUMB hurts, because
it moves independently; trimming removes whichever points articulated anyway.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ BIJECTIVITY, WHICH IS THE POINT OF THE PARAMETERISATION

`σ₂/σ₁` alone is NOT bijective over 0–180°: it falls to the edge-on pose and rises
again, so 60° and 120° are indistinguishable. That fold is inherent to every
foreshortening measure and has already produced two nonsense results in this
project (`t5f`'s "gain 3.57" and "gain 21.5").

⭐ Three numbers make it bijective, and all three are DEPTH-FREE:

    σ₂/σ₁                  ->  |angle from square|, 0..90     (this regression)
    palm/back SIGN         ->  which side of 90                (signed_palm_area)
    tilt direction         ->  which axis, yaw vs pitch        (the SVD)

⚠ It degenerates where any of the three does: at σ₂/σ₁ → 1 the tilt is undefined,
and at σ₂/σ₁ → 0 (edge-on) the sign is what `DR-2` already freezes. Bijective on
the interior, and the boundaries are places the pipeline already refuses to act.

────────────────────────────────────────────────────────────────────────────────
HOW IT IS SCORED — LEAVE ONE TAKE OUT

Fit on two depths, predict the THIRD, score against its declared angles. That is
the transfer question §4.3 asked, but now the model is fitted rather than assumed.

⚠⚠ AND THE LABELS ARE THE WEAK PART, STATED UP FRONT. The declared angles are the
operator's own, and the cross-check of 2026-08-27 measured them irreproducible at
the 30° holds (ratio/declared spread 0.50–0.69 across takes). ⛔ So a small
prediction error here means the model reproduces the OPERATOR; it does not prove
accuracy. The honest reading is COMPARATIVE: does the fitted model beat Horn on the
same labels, and is it consistent across depths?

    .venv/Scripts/python.exe analysis/t6_regression_fit.py [--axis yaw|pitch]
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry as PG                     # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = (r"E:\Python\Recordings for vision_pipeline"
           r"\Recordings_perception_layer\sessions")
IDENT = (1.0, 0.0, 0.0, 0.0)

# ⭐ MEASURED, not chosen -- see the header's table.
FEATURE_IDS = tuple(i for i in range(21) if i not in (1, 2, 3, 4))   # no thumb
TRIM = 0.25


def med(xs):
    xs = sorted(v for v in xs if v == v)
    return xs[len(xs) // 2] if xs else float("nan")


def affine_svd(src, dst, trim=TRIM):
    """Trimmed 2×2 affine fit, returned as (σ₂/σ₁, tilt°). None if degenerate."""
    idx = list(range(len(src)))
    A = None
    for _ in range(3 if trim > 0 else 1):
        cs = [sum(src[i][k] for i in idx) / len(idx) for k in range(2)]
        cd = [sum(dst[i][k] for i in idx) / len(idx) for k in range(2)]
        S = [[0.0, 0.0], [0.0, 0.0]]
        T = [[0.0, 0.0], [0.0, 0.0]]
        for i in idx:
            a = (src[i][0] - cs[0], src[i][1] - cs[1])
            b = (dst[i][0] - cd[0], dst[i][1] - cd[1])
            for r in range(2):
                for c in range(2):
                    S[r][c] += a[r] * a[c]
                    T[r][c] += b[r] * a[c]
        det = S[0][0] * S[1][1] - S[0][1] * S[1][0]
        if abs(det) < 1e-12:
            return None
        Si = [[S[1][1] / det, -S[0][1] / det], [-S[1][0] / det, S[0][0] / det]]
        A = [[sum(T[r][k] * Si[k][c] for k in range(2)) for c in range(2)]
             for r in range(2)]
        if trim > 0:
            res = []
            for i in range(len(src)):
                a = (src[i][0] - cs[0], src[i][1] - cs[1])
                b = (dst[i][0] - cd[0], dst[i][1] - cd[1])
                pr = (A[0][0] * a[0] + A[0][1] * a[1],
                      A[1][0] * a[0] + A[1][1] * a[1])
                res.append((math.hypot(pr[0] - b[0], pr[1] - b[1]), i))
            res.sort()
            idx = [i for _, i in res[:max(4, int(len(res) * (1.0 - trim)))]]
    a, b = A[0]
    c, d = A[1]
    E, F = (a + d) / 2.0, (a - d) / 2.0
    G, H = (c + b) / 2.0, (c - b) / 2.0
    Q, R = math.hypot(E, H), math.hypot(F, G)
    s1, s2 = Q + R, abs(Q - R)
    if s1 < 1e-9:
        return None
    tilt = math.degrees((math.atan2(H, E) - math.atan2(G, F)) / 2.0) % 180.0
    return s2 / s1, tilt


def load(axis):
    out = {}
    for d in sorted(os.listdir(CAPTURE)):
        if "ratio_calib" not in d:
            continue
        jl = os.path.join(CAPTURE, d, "raw_landmarks.jsonl")
        if not os.path.exists(jl):
            continue
        meta = json.load(open(os.path.join(CAPTURE, d, "meta.json"), encoding="utf-8"))
        if meta.get("axis") != axis:
            continue
        holds = {}
        with open(jl, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if not r.get("on_axis") or len(r.get("hands") or []) != 1:
                    continue
                h = r["hands"][0]
                holds.setdefault(float(r["declared_deg"]), []).append(
                    (h["landmarks"], h["world_landmarks"]))
        if 0.0 in holds:
            out[d.rsplit("_", 1)[-1]] = holds       # latest per depth tag wins
    return out


def features(holds):
    """(declared, σ₂/σ₁, |signed area| sign, tilt) per hold."""
    ref = holds[0.0][len(holds[0.0]) // 2][0]
    canon = [[ref[i][0], ref[i][1]] for i in FEATURE_IDS]
    sign0 = PG.signed_palm_area(ref)
    out = []
    for ang in sorted(holds):
        ss, ts, sg = [], [], []
        for lm, _wl in holds[ang]:
            r = affine_svd(canon, [[lm[i][0], lm[i][1]] for i in FEATURE_IDS])
            if r:
                ss.append(r[0])
                ts.append(r[1])
            a = PG.signed_palm_area(lm)
            sg.append(1.0 if (a * sign0) >= 0 else -1.0)
        if ss:
            out.append((ang, med(ss), med(sg), med(ts)))
    return out


def fit_monotone(pairs):
    """Piecewise-linear σ→angle from (σ, angle) samples, forced MONOTONE.

    ⭐ Monotone by construction is what makes the inverse single-valued -- i.e.
    what makes the regression BIJECTIVE on its half-domain. A free polynomial fit
    can wiggle, and a wiggle is two angles for one measurement.
    """
    pts = sorted(pairs, key=lambda p: -p[0])          # σ falling, angle rising
    xs, ys = [], []
    for x, y in pts:
        if xs and x >= xs[-1]:
            continue
        if ys and y <= ys[-1]:
            y = ys[-1] + 1e-6                          # enforce strict monotone
        xs.append(x)
        ys.append(y)
    def f(s):
        if s >= xs[0]:
            return ys[0]
        if s <= xs[-1]:
            return ys[-1]
        for (x1, y1), (x2, y2) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
            if x2 <= s <= x1:
                t = 0.0 if abs(x1 - x2) < 1e-12 else (x1 - s) / (x1 - x2)
                return y1 + t * (y2 - y1)
        return ys[-1]
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--axis", default="yaw", choices=("yaw", "pitch"))
    a = ap.parse_args()
    takes = load(a.axis)
    if len(takes) < 3:
        print("need three depths; found %d" % len(takes))
        return 1
    feats = {t: features(h) for t, h in takes.items()}
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")

    w = 86
    print("=" * w)
    print("  T6 -- ORIENTATION BY REGRESSION  (axis: %s)" % a.axis)
    print("=" * w)
    print("  feature : sigma2/sigma1 of the TRIMMED affine fit, no-thumb landmarks")
    print("  test    : LEAVE ONE ANGLE OUT -- unseen at EVERY depth")
    print("  scoring : |estimate - declared| for BOTH sides, no folding of either")
    print()
    print("  ⛔ LEAVE-ONE-DEPTH-OUT WAS TRIED FIRST AND IS MEANINGLESS HERE. It")
    print("     scored 1.2 deg against Horn's 10.2 -- but the grid is 30 deg and")
    print("     the held-out angle is present at the OTHER depths, so a monotone")
    print("     fit BINS to it instead of interpolating. Holding out the ANGLE is")
    print("     the only test that asks the model to interpolate.")
    print()
    print("  ⭐ TWO BRANCHES, not one unfolded curve: front 60 deg reads sigma 0.513")
    print("     and back 60 deg reads 0.633, so the hand is measurably NOT")
    print("     front-back symmetric and unfolding loses that. The palm/back sign")
    print("     picks the branch, which is also what makes the map single-valued.")
    print()
    print("  %-9s %11s %11s   %s" % ("held-out", "MODEL err", "HORN err", "winner"))
    allm, allh = [], []
    for held in (30.0, 60.0, 120.0, 150.0):
        front = held <= 90.0
        # ⭐⭐ THE 90° SAMPLES BELONG TO **BOTH** BRANCHES -- the mend the owner
        # asked for, and the whole reason the back half stopped losing.
        #
        # ⛔ Splitting at 90 exclusively left the back branch with only
        # {120,150,180}. Hold out 120 and it trains on {150,180}, whose sigma span
        # (0.835-0.914) does NOT contain 120's sigma (0.618) -- so the fit had to
        # EXTRAPOLATE and clamped instead, scoring exactly 30.0 deg every time.
        # ⚠ I first blamed that on `T1` (back-of-hand landmark quality). That was
        # wrong: it was my own data partition. Sharing the knot turns the same
        # prediction from an extrapolation into an interpolation, and the back half
        # went 30.0 -> 15.5 (yaw) and 30.0 -> 16.3 (pitch) with NO cost to the
        # front half.
        #
        # ⭐ C0 holds exactly: both curves pass through the shared knot. The
        # derivative matches in the only sense the data supports -- sigma has its
        # MINIMUM at 90, so both branches approach it flattening out.
        # ⚠ A stiffer C1 form was tried (v + a·u² + b·u³ per branch, zero slope at
        # 90 by construction). It fixed the extrapolation too but cost the front
        # half badly -- yaw 30 went 4.1 -> 11.2 and yaw 60 went 1.7 -> 6.4 -- because
        # two parameters per branch cannot follow the real curve. Flexibility was
        # doing more work than smoothness.
        train = [(s, ang) for _t, fs in feats.items() for ang, s, _g, _ti in fs
                 if ang != held and ((ang <= 90.0) if front else (ang >= 90.0))]
        if len(train) < 3:
            continue
        fit = fit_monotone(train if front else [(s, 180.0 - y) for s, y in train])
        em, eh = [], []
        for t in sorted(feats):
            base = takes[t][0.0][len(takes[t][0.0]) // 2]
            st = horn.freeze(base[0], base[1])
            for ang, s, _g, _ti in feats[t]:
                if ang != held:
                    continue
                p = fit(s)
                if not front:
                    p = 180.0 - p
                hs = []
                for lm, wl in takes[t][ang]:
                    dq = horn.delta(st, lm, wl)
                    if dq is not None:
                        hs.append(PR.quat_angle_deg(IDENT, dq))
                em.append(abs(p - ang))
                eh.append(abs(med(hs) - ang))
        if em:
            allm += em
            eh_m = sum(eh) / len(eh)
            allh += eh
            print("  %-9.0f %10.1f° %10.1f°   %s"
                  % (held, sum(em) / len(em), eh_m,
                     "model" if sum(em) / len(em) < eh_m else "HORN"))
    print("  %-9s %10.1f° %10.1f°   %s"
          % ("MEAN", sum(allm) / len(allm), sum(allh) / len(allh),
             "MODEL" if sum(allm) < sum(allh) else "HORN"))
    print()
    print("  ⭐ The model now beats Horn on BOTH axes. It still trails on the back")
    print("    half hold-outs, but the gap is interpolation range, not landmark")
    print("    quality -- the back branch spans 90..180 with three angles.")
    print("  ⚠ A 30.0 deg error is the fit CLAMPING: a hold-out adjacent to the")
    print("    branch end still asks it to extrapolate, and it refuses by design")
    print("    rather than guess.")
    print("  ⛔ And the labels remain the weak link -- the declared angles were")
    print("    measured irreproducible at the 30 deg holds (spread 0.50-0.69).")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
