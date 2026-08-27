# -*- coding: utf-8 -*-
"""⭐⭐ T6 — EMIT THE FITTED sigma->angle TABLES as a data artifact.

The owner's HALF 1: the six open-hand takes give the regression. This writes those
fits out as `Resources/palm_slant_table.py` so a live estimator can read them.

⛔⛔ WHY THIS IS A SEPARATE FILE AND NOT A CONSTANT IN THE MODULE. The curve encodes
the OPERATOR'S HAND THICKNESS -- it is why sigma bottoms at 0.07-0.30 instead of 0 --
so it is a per-user artifact (`U12`). Freezing one hand's curve into a shared module
would ship a hidden calibration to every future user. The estimator takes the table
as data; this file is where that data comes from, and it is regenerable.

FOUR CURVES, and the reasons for each split:

  yaw / pitch     the hand is thicker one way than the other: at a declared 90 the
                  yaw hold reads sigma 0.238 and the pitch hold 0.341. One curve
                  cannot serve both, and `tilt` is what says which is in play.
  front / back    front 60 deg reads 0.513 and back 60 deg reads 0.633, so the hand
                  is measurably NOT front-back symmetric. ⭐ The two branches SHARE
                  the 90 deg knot -- the mend the owner asked for. Splitting there
                  exclusively left the back branch extrapolating and clamping at
                  30.0 deg every time.

TWO FEATURE SETS, and this is a live question rather than a formality:

  palm     landmarks (0,5,9,13,17). Steady under a GRIP (0.004-0.070 per frame).
  fingers  every landmark but the thumb. 2.4x steadier on an OPEN hand -- which is
           what these takes are -- and up to 60x WORSE on a gripping one
           (0.013-0.458). ⚠ The game grips. Both are emitted so the live rig can
           settle it with a hand instead of an argument.

    .venv/Scripts/python.exe analysis/t6_emit_table.py
"""
import importlib.util
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("rf", os.path.join(_here, "t6_regression_fit.py"))
rf = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, ["t6_regression_fit"]
_spec.loader.exec_module(rf)
sys.argv = _argv

PALM = (0, 5, 9, 13, 17)
FINGERS = rf.FEATURE_IDS
OUT = os.path.join(_here, "..", "Resources", "palm_slant_table.py")


def sigma_for(holds, ids):
    """(declared, sigma) per hold, sigma measured from the take's own 0 deg hold."""
    ref = holds[0.0][len(holds[0.0]) // 2][0]
    canon = [[ref[i][0], ref[i][1]] for i in ids]
    out = []
    for ang in sorted(holds):
        ss = []
        for lm, _wl in holds[ang]:
            r = rf.affine_svd(canon, [[lm[i][0], lm[i][1]] for i in ids])
            if r:
                ss.append(r[0])
        if ss:
            out.append((ang, rf.med(ss)))
    return out


def knots(pairs, rising=True):
    """Monotone piecewise-linear knots, in FALLING sigma.

    ⛔⛔ `rising` IS NOT A STYLE FLAG. The first version of this file hard-coded
    the FRONT branch's direction -- as sigma falls, the angle rises -- and applied it
    to the back branch too. On the back branch sigma RISES with angle (90 deg is the
    minimum, 180 deg reads 0.911), so forcing "angle must rise as sigma falls"
    dragged every back knot up to 180 and the emitted table read `180..180`: the
    whole back half, silently flattened into one value.

    ⚠ It printed that in the emit log and was only caught by reading it. A table
    that says 180 everywhere is not a bad fit, it is no fit at all.
    """
    pts = sorted(pairs, key=lambda p: -p[0])
    xs, ys = [], []
    for x, y in pts:
        if xs and x >= xs[-1]:
            continue
        if ys:
            if rising and y <= ys[-1]:
                y = ys[-1] + 1e-6
            elif not rising and y >= ys[-1]:
                y = ys[-1] - 1e-6
        xs.append(x)
        ys.append(y)
    return list(zip(xs, ys))


def build(ids):
    out = {}
    for axis in ("yaw", "pitch"):
        takes = rf.load(axis)
        if len(takes) < 1:
            print("  !! no takes for %s" % axis)
            continue
        feats = [f for _t, h in takes.items() for f in sigma_for(h, ids)]
        # ⭐ The 90 deg samples belong to BOTH branches -- the shared knot.
        front = [(s, a) for a, s in feats if a <= 90.0]
        back = [(s, a) for a, s in feats if a >= 90.0]
        # ⭐ front: sigma falls as the hand turns away from face-on, so the angle
        # RISES. back: sigma is at its minimum at 90 and climbs again toward 180,
        # so along falling sigma the angle FALLS. Two directions, one table format.
        out[axis] = {"front": knots(front, True), "back": knots(back, False)}
        # the two constructions must agree, or the shipped table is not the fit
        f = rf.fit_monotone(front)
        for x, y in out[axis]["front"]:
            assert abs(f(x) - y) < 1e-6, "knots disagree with fit_monotone"
    return out


def main():
    print("=" * 84)
    print("  T6 -- EMITTING THE FITTED TABLES (the owner's HALF 1)")
    print("=" * 84)
    sets = {}
    for name, ids in (("palm", PALM), ("fingers", FINGERS)):
        print("\n  feature set: %s (%d landmarks)" % (name, len(ids)))
        sets[name] = build(ids)
        for axis, br in sets[name].items():
            for side, ks in br.items():
                print("    %-5s %-5s : %d knots   sigma %.3f..%.3f  ->  %.0f..%.0f deg"
                      % (axis, side, len(ks), ks[0][0], ks[-1][0], ks[0][1], ks[-1][1]))

    body = ['# -*- coding: utf-8 -*-',
            '"""GENERATED by `analysis/t6_emit_table.py` -- do not hand-edit.',
            '',
            '⛔⛔ THIS IS ONE PERSON\'S HAND. The curve encodes HAND THICKNESS (it is why',
            'sigma bottoms near 0.1 instead of 0), so it is a per-user artifact and `U12`',
            'owns the question of where a second user\'s comes from. It is data, deliberately',
            'kept out of `palm_slant.py` so no shared module carries a hidden calibration.',
            '',
            'sigma -> declared angle, monotone piecewise-linear, knots in FALLING sigma.',
            'FRONT and BACK share the 90 deg knot. `yaw` and `pitch` differ because the hand',
            'is thicker one way than the other; `tilt` says which is in play.',
            '"""']
    for name in ("palm", "fingers"):
        body.append("")
        body.append("TABLE_%s = {" % name.upper())
        for axis in ("yaw", "pitch"):
            body.append('    "%s": {' % axis)
            for side in ("front", "back"):
                ks = sets[name].get(axis, {}).get(side, [])
                body.append('        "%s": [' % side)
                for x, y in ks:
                    body.append("            (%.6f, %.4f)," % (x, y))
                body.append("        ],")
            body.append("    },")
        body.append("}")
    body.append("")
    body.append("TABLES = {\"palm\": TABLE_PALM, \"fingers\": TABLE_FINGERS}")
    body.append("")
    io.open(os.path.normpath(OUT), "w", encoding="utf-8").write("\n".join(body))
    print("\n  wrote %s" % os.path.normpath(OUT))
    print("=" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
