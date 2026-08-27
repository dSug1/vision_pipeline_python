# -*- coding: utf-8 -*-
"""Golden vectors for `Resources/palm_slant.py` (T6 / Strategy A).

⭐ Written in the SAME change as the module, not after — `CONSTRAINTS` §3. This
file is the artifact a JS/Swift/Kotlin port must reproduce: no numpy, no pygame,
no camera, no recordings, no clock.

⭐⭐ The property tests below are the ones that matter, because they are the claims
the module makes about itself:

  * scale invariance  — the camera distance cancels, so `T6`'s unreliable tape
    measure (caveat zero) cannot reach this estimator;
  * ROLL invariance   — the property that makes slant/tilt worth having at all;
  * ORTHOGONALITY     — yaw compresses at 90°, pitch at 0°, as the geometry
    requires and as the six takes measured;
  * the AUTHORITY FADE is zero at the measured noise floor — a port that drops it
    ships ~20° of invented tilt.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_palm_slant.py
Exit code 0 = all pass.
"""
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_slant as PS         # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):        # pragma: no cover
    pass

FAILURES = []


def check(name, got, want, tol=1e-9):
    if want is None or isinstance(want, bool) or isinstance(want, int):
        good = got == want
    else:
        good = got is not None and abs(got - want) <= tol
    print("  [%s] %-58s got %r" % ("PASS" if good else "FAIL", name, got))
    if not good:
        FAILURES.append("%s: got %r, want %r" % (name, got, want))


def ok(name, cond, detail=""):
    print("  [%s] %-58s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


# A canonical palm quad + wrist, in pixels, roughly the real proportions.
CANON = [(0.0, 0.0), (-34.0, -62.0), (-4.0, -70.0), (24.0, -66.0), (46.0, -50.0)]


def apply(M, pts, tx=0.0, ty=0.0):
    return [(M[0][0] * x + M[0][1] * y + tx, M[1][0] * x + M[1][1] * y + ty)
            for x, y in pts]


def rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((c, -s), (s, c))


def mul(A, B):
    return tuple(tuple(sum(A[r][k] * B[k][c] for k in range(2)) for c in range(2))
                 for r in range(2))


def hand(pts):
    """Scatter a 5-point palm into a full 21-landmark array.

    [!] The tracker takes MediaPipe's whole hand and picks the palm out by index;
    `affine_svd` takes the picked points directly. Handing the tracker a bare
    5-point list is what the first run of this file did, and it correctly refused
    every frame -- the API asymmetry is real and this is where it gets documented.
    """
    out = [(0.0, 0.0)] * 21
    for i, k in enumerate(PS.PALM_LANDMARKS):
        out[k] = pts[i]
    return out


def main():
    print("=" * 78)
    print("Golden vectors -- palm_slant  (T6 Strategy A: slant/tilt from 2D)")
    print("=" * 78)

    print("\n--- 1. the invariances (what makes this estimator worth having) ---")
    r = PS.affine_svd(CANON, CANON)
    check("identity map -> sigma 1", r[0], 1.0, 1e-9)

    r = PS.affine_svd(CANON, apply(((3.0, 0.0), (0.0, 3.0)), CANON, 500.0, -120.0))
    check("3x scale + translation -> sigma 1 (distance cancels)", r[0], 1.0, 1e-9)

    for d in (17.0, 45.0, 103.0):
        r = PS.affine_svd(CANON, apply(rot(d), CANON))
        check("pure roll %5.1f deg -> sigma 1" % d, r[0], 1.0, 1e-9)

    print("\n--- 2. compression: magnitude and direction ---")
    # Squash x by half: a YAW-like foreshortening.
    ry = PS.affine_svd(CANON, apply(((0.5, 0.0), (0.0, 1.0)), CANON))
    check("squash x 0.5 -> sigma 0.5", ry[0], 0.5, 1e-9)
    check("squash x     -> tilt 90 deg", ry[1], 90.0, 1e-7)

    # Squash y by half: a PITCH-like foreshortening.
    rp = PS.affine_svd(CANON, apply(((1.0, 0.0), (0.0, 0.5)), CANON))
    check("squash y 0.5 -> sigma 0.5", rp[0], 0.5, 1e-9)
    check("squash y     -> tilt 0 deg (mod 180: 180 IS 0)",
          PS.tilt_delta(rp[1], 0.0), 0.0, 1e-7)
    ok("[*] yaw and pitch are ORTHOGONAL in tilt",
       abs(PS.tilt_delta(ry[1], rp[1]) - 90.0) < 1e-6,
       "yaw %.2f vs pitch %.2f" % (ry[1], rp[1]))

    print("\n--- 3. ROLL INVARIANCE OF THE TILT (the load-bearing property) ---")
    # Squash first, then roll the whole hand in the image plane. The compression is
    # the same physical foreshortening, so both readings must be unchanged.
    for d in (30.0, 75.0, 140.0):
        rr = PS.affine_svd(CANON, apply(mul(rot(d), ((0.5, 0.0), (0.0, 1.0))), CANON))
        ok("roll %5.1f deg after squash: sigma AND tilt unchanged" % d,
           abs(rr[0] - ry[0]) < 1e-9 and PS.tilt_delta(rr[1], ry[1]) < 1e-6,
           "sigma %.6f tilt %.3f" % rr)

    print("\n--- 4. the trim earns its keep ---")
    dst = apply(((0.5, 0.0), (0.0, 1.0)), CANON)
    dst[3] = (dst[3][0] + 40.0, dst[3][1] - 35.0)        # one landmark flies off
    rt = PS.affine_svd(CANON, dst, trim=PS.TRIM_FRACTION)
    ru = PS.affine_svd(CANON, dst, trim=0.0)
    ok("trimmed fit survives one bad landmark", abs(rt[0] - 0.5) < abs(ru[0] - 0.5),
       "trimmed %.4f vs untrimmed %.4f (truth 0.5)" % (rt[0], ru[0]))
    check("TRIM_MIN_KEEP matches the fitting harness", PS.TRIM_MIN_KEEP, 4)

    print("\n--- 5. degeneracies return None, they do not guess ---")
    check("collinear canonical -> None",
          PS.affine_svd([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)], CANON), None)
    check("mismatched lengths -> None", PS.affine_svd(CANON, CANON[:3]), None)
    check("too few points -> None", PS.affine_svd(CANON[:2], CANON[:2]), None)

    print("\n--- 6. THE AUTHORITY FADE (a port that drops this ships 20 deg of noise) ---")
    check("SLANT_NOISE_FLOOR is the measured 0.94", PS.SLANT_NOISE_FLOOR, 0.94, 1e-12)
    check("authority at the noise floor is ZERO", PS.authority(0.94), 0.0, 1e-12)
    check("authority above the floor is ZERO", PS.authority(0.99), 0.0, 1e-12)
    check("authority at sigma 1 (square palm) is ZERO", PS.authority(1.0), 0.0, 1e-12)
    check("authority at SLANT_FULL is ONE", PS.authority(0.80), 1.0, 1e-12)
    check("authority well past full is ONE", PS.authority(0.20), 1.0, 1e-12)
    check("authority midway is 0.5 (smoothstep)", PS.authority(0.87), 0.5, 1e-12)
    check("authority(None) is ZERO", PS.authority(None), 0.0, 1e-12)
    check("authority(nan) is ZERO", PS.authority(float("nan")), 0.0, 1e-12)
    seq = [PS.authority(x / 100.0) for x in range(75, 101)]
    ok("authority is monotone non-increasing in sigma",
       all(seq[i] >= seq[i + 1] - 1e-12 for i in range(len(seq) - 1)))

    print("\n--- 7. invert(): monotone table in, single value out ---")
    TABLE = [(1.00, 0.0), (0.86, 30.0), (0.53, 60.0), (0.24, 90.0)]
    check("invert at a table knot", PS.invert(TABLE, 0.53), 60.0, 1e-12)
    check("invert interpolates between knots", PS.invert(TABLE, 0.695), 45.0, 1e-9)
    check("invert CLAMPS above the table", PS.invert(TABLE, 1.30), 0.0, 1e-12)
    check("invert CLAMPS below the table", PS.invert(TABLE, 0.01), 90.0, 1e-12)
    check("invert accepts an unsorted table", PS.invert(list(reversed(TABLE)), 0.53), 60.0, 1e-12)
    check("invert(empty) is None", PS.invert([], 0.5), None)
    check("invert(nan) is None", PS.invert(TABLE, float("nan")), None)
    vals = [PS.invert(TABLE, x / 200.0) for x in range(48, 201)]
    ok("invert is monotone (the map stays BIJECTIVE)",
       all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1)))

    print("\n--- 8. SlantTracker: freeze at grab, hold on trouble ---")
    t = PS.SlantTracker()
    H0 = hand(CANON)
    ok("not frozen -> authority 0", t.update(H0)[2] == 0.0 and not t.frozen)
    ok("freeze takes the canonical", t.freeze(H0) and t.frozen)
    s, _tl, au = t.update(H0)
    check("frozen then unmoved -> sigma 1", s, 1.0, 1e-9)
    check("frozen then unmoved -> authority 0 (says NOTHING)", au, 0.0, 1e-12)

    s, tl, au = t.update(hand(apply(((0.5, 0.0), (0.0, 1.0)), CANON)))
    check("turned hand -> sigma 0.5", s, 0.5, 1e-9)
    check("turned hand -> full authority", au, 1.0, 1e-12)
    check("turned hand -> tilt 90", tl, 90.0, 1e-7)

    s2, tl2, au2 = t.update(None)
    ok("[!] unusable frame HOLDS, it does not snap to identity",
       s2 == s and tl2 == tl and au2 == 0.0 and t.frames_refused == 1,
       "held sigma %.4f, refused %d" % (s2, t.frames_refused))
    s3, _t3, au3 = t.update([(1.0, 1.0)] * 21)     # all coincident -> degenerate fit
    ok("degenerate frame HOLDS too", s3 == s and au3 == 0.0 and t.frames_refused == 2)

    ok("freeze refuses a short landmark list", not PS.SlantTracker().freeze([(0.0, 0.0)] * 5))
    t.reset()
    ok("reset drops the canonical with the grab", not t.frozen and t.last_tilt is None)

    print("\n--- 9. the port contract (CONSTRAINTS section 2) ---")
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "Resources", "palm_slant.py"), encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("import numpy", "import time", "time.", "perf_counter", "datetime", "random"):
        ok("no %-16s (clock-free, numpy-free)" % bad, bad not in body)

    print("\n--- 10. golden digest -- a port must reproduce these EXACTLY ---")
    for name, M in (("yaw-like  x*0.62", ((0.62, 0.0), (0.0, 1.0))),
                    ("pitch-like y*0.62", ((1.0, 0.0), (0.0, 0.62))),
                    ("oblique: squash along 41 deg",
                     mul(rot(41.0), mul(((0.62, 0.0), (0.0, 1.0)), rot(-41.0))))):
        sg, tt = PS.affine_svd(CANON, apply(M, CANON))
        print("  %-20s sigma %.9f   tilt %.6f   authority %.9f"
              % (name, sg, tt, PS.authority(sg)))

    print("\n" + "=" * 78)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
