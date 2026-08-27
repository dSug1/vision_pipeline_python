"""⭐⭐ T6 — THE COMPOSITION, FITTED INSTEAD OF ASSUMED.

The owner's architecture freezes a matrix at grab and measures everything relative
to it. Validated 2026-08-27 — but the step that makes it work,

    sigma_abs(b) = sigma_rel(b | a0) * sigma_abs(a0)

is the ORTHOGRAPHIC `cos` model, which is the very assumption the regression exists
to avoid. It came back in through the composition.

⭐ THIS FILE REMOVES IT. Generalise the product to

    u = sigma_rel^alpha * sigma_0^beta          then    angle = f(u)

with `alpha`, `beta` and the monotone curve `f` all FITTED from the takes. The
multiplicative model is the special case `alpha = beta = 1`, so the data is free to
keep it or move away from it, and we find out which.

⭐ It stays 1-D in the end: for a fixed grab pose `u` is monotone in `sigma_rel`, so
the inverse is single-valued and the map remains BIJECTIVE.

────────────────────────────────────────────────────────────────────────────────
WHAT IS SCORED

Every ordered pair of holds within a take is one sample: freeze at `a0`, observe
`b`. The quantity the cube actually needs is the RELATIVE rotation `|b - a0|` --
its orientation is grab-relative, so the absolute error at grab cancels.

    LEAVE ONE TAKE OUT -- fit on two depths, predict the third.

⚠ The labels are the operator's declared angles, measured irreproducible at the 30
degree holds. ⛔ So this is COMPARATIVE against Horn on identical labels, never an
accuracy claim. The independent-truth check is `t5j`/`t5h` and it comes next.

    .venv/Scripts/python.exe analysis/t6_composition_fit.py [--axis yaw|pitch]
"""
import argparse
import importlib.util
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_rotation as PR                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

_spec = importlib.util.spec_from_file_location(
    "rf", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "t6_regression_fit.py"))
rf = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, ["t6_regression_fit"]
_spec.loader.exec_module(rf)
sys.argv = _argv

IDENT = (1.0, 0.0, 0.0, 0.0)

# ⛔ PALM ONLY. The finger-inclusive feature is 2.4x steadier on the OPEN-hand
# takes and up to 60x WORSE on a gripping hand (0.013-0.458 vs 0.004-0.070 per
# frame). The game grips; the orientation channel takes the palm.
PALM = (0, 5, 9, 13, 17)


def sigma(canon, frames):
    vals = []
    for lm, _wl in frames:
        r = rf.affine_svd(canon, [[lm[i][0], lm[i][1]] for i in PALM])
        if r:
            vals.append(r[0])
    return rf.med(vals)


def samples(holds):
    """(a0, b, sigma_rel, sigma_0) for every ordered pair of holds."""
    sq = holds[0.0][len(holds[0.0]) // 2][0]
    csq = [[sq[i][0], sq[i][1]] for i in PALM]
    s_abs = {a: sigma(csq, holds[a]) for a in holds}
    # ⛔ ONE BRANCH ONLY. The first version paired every hold with every other,
    # 0..180 -- so the monotone curve was asked to represent the FOLD, which it
    # cannot, and the grid search "fixed" that by running the exponents to the edge
    # (alpha 1.8-2.0, beta 0.4) and scored 59 deg against Horn's 13. The fold has
    # bitten this project four times now; it does not stop being true here.
    # ⭐ Pairs are taken within the palm-facing branch, which is where the
    # show-stopper lives and where a grab realistically happens.
    front = [a for a in sorted(holds) if a <= 90.0]
    out = []
    for a0 in front:
        ref = holds[a0][len(holds[a0]) // 2][0]
        canon = [[ref[i][0], ref[i][1]] for i in PALM]
        for b in front:
            if b == a0:
                continue
            out.append((a0, b, sigma(canon, holds[b]), s_abs[a0]))
    return out


def build(train, alpha, beta):
    pairs = []
    for _a0, b, sr, s0 in train:
        if sr <= 0 or s0 <= 0:
            continue
        pairs.append(((sr ** alpha) * (s0 ** beta), b))
    return rf.fit_monotone(pairs) if len(pairs) >= 3 else None


def score(f, data, alpha, beta):
    errs = []
    for a0, b, sr, s0 in data:
        if sr <= 0 or s0 <= 0:
            continue
        u = (sr ** alpha) * (s0 ** beta)
        errs.append(abs(abs(f(u) - a0) - abs(b - a0)))
    return sum(errs) / len(errs) if errs else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--axis", default="yaw", choices=("yaw", "pitch"))
    a = ap.parse_args()
    takes = rf.load(a.axis)
    if len(takes) < 3:
        print("need three depths; found %d" % len(takes))
        return 1
    S = {t: samples(h) for t, h in takes.items()}
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")

    w = 84
    print("=" * w)
    print("  T6 -- THE COMPOSITION, FITTED  (axis: %s)" % a.axis)
    print("=" * w)
    print("  u = sigma_rel^alpha * sigma_0^beta   ->   angle = f(u), f monotone")
    print("  alpha = beta = 1 IS the multiplicative model, so it is in the search.")
    print("  palm landmarks only -- the finger feature does not survive a grip.")
    print()

    grid = [x / 10.0 for x in range(4, 21, 2)]
    rows = []
    for held in sorted(S):
        train = [s for t, ss in S.items() if t != held for s in ss]
        best = None
        for al in grid:
            for be in grid:
                f = build(train, al, be)
                if f is None:
                    continue
                e = score(f, train, al, be)
                if best is None or e < best[0]:
                    best = (e, al, be, f)
        _e, al, be, f = best
        model = score(f, S[held], al, be)

        # Horn on the same pairs, scored identically
        errs = []
        for a0, b, _sr, _s0 in S[held]:
            ref = takes[held][a0][len(takes[held][a0]) // 2]
            st = horn.freeze(ref[0], ref[1])
            hs = []
            for lm, wl in takes[held][b]:
                dq = horn.delta(st, lm, wl)
                if dq is not None:
                    hs.append(PR.quat_angle_deg(IDENT, dq))
            if hs:
                errs.append(abs(rf.med(hs) - abs(b - a0)))
        hv = sum(errs) / len(errs) if errs else float("nan")
        rows.append((held, al, be, model, hv))
        print("  predict %-4s : alpha %.1f  beta %.1f   MODEL %5.1f°   HORN %5.1f°   %s"
              % (held, al, be, model, hv, "model" if model < hv else "HORN"))

    mm = sum(r[3] for r in rows) / len(rows)
    hm = sum(r[4] for r in rows) / len(rows)
    print()
    print("  MEAN                              MODEL %5.1f°   HORN %5.1f°   %s"
          % (mm, hm, "MODEL BETTER" if mm < hm else "HORN BETTER"))

    # what the data says about the assumption itself
    als = [r[1] for r in rows]
    bes = [r[2] for r in rows]
    print()
    print("  ⭐ WHAT THE DATA SAYS ABOUT THE MULTIPLICATIVE ASSUMPTION")
    print("     fitted alpha: %s      beta: %s"
          % ("/".join("%.1f" % v for v in als), "/".join("%.1f" % v for v in bes)))
    if all(abs(v - 1.0) < 0.25 for v in als + bes):
        print("     ⇒ the data KEEPS alpha=beta=1: the multiplicative composition")
        print("       was not a smuggled assumption after all, it is what the")
        print("       takes support. ⭐ The assumption is now MEASURED, not assumed.")
    else:
        print("     ⇒ the data MOVES AWAY from alpha=beta=1, so the orthographic")
        print("       product was costing accuracy. The fitted exponents are the")
        print("       correction, and they are empirical rather than derived.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
