"""Golden vectors for `Resources/tip_trim.py` — `F1` step 4's fingertip trim.

⛔ THE FIRST CHECK IS THE ACCEPTANCE GATE: `gain = 0` must return the IDENTITY
OBJECT, so the shipped rotation expression is reached byte-for-byte and the whole
step is revert-free. `T6d` proved its arms identical on 975/975 frames, which is
why its rejection after four live sessions cost nothing.

⭐ The rest pin the properties the design's safety rests on, each of which is a
claim made in the module header and therefore worth testing rather than trusting:

  * WHOLE-HAND ROTATION CANNOT REACH THE TRIM. Rotate a rigid hand arbitrarily and
    the trim must stay identity -- that is the entire reason this is not `B4`'s
    `PALM_AND_TIPS`, which is A10-dead twice.
  * The clamp bounds the ANGLE, and the axis survives it.
  * Conditioning FADES, never switches -- a hard gate is itself a rotation step.
  * A collinear or clustered tip cloud loses authority.
  * Every unusable frame HOLDS the last trim rather than snapping to identity.

    .venv/Scripts/python.exe analysis/verify_tip_trim.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import tip_trim                                  # noqa: E402
from Resources import palm_rotation                             # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

_fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<60} {detail}")
    if not ok:
        _fails.append(name)


def quat_axis_angle(axis, deg):
    n = math.sqrt(sum(a * a for a in axis)) or 1.0
    a = [x / n for x in axis]
    h = math.radians(deg) * 0.5
    s = math.sin(h)
    return (math.cos(h), a[0] * s, a[1] * s, a[2] * s)


def rot(q, v):
    return tip_trim._rotate(q, v)


# ⚠⚠ THE FIXTURE'S PROPORTIONS ARE NOT DECORATIVE -- they decide whether the test
# exercises the trim at all. The first version gave all five tips the SAME reach,
# which put them nearly on a straight line: `spread` read **0.172**, just under
# `SPREAD_FLOOR`, so the conditioning fade correctly zeroed the trim and two checks
# failed for a reason that had nothing to do with the code. ⭐ Real fingers differ
# in length, and `analysis/f1_tip_census.py` measures a real-hand `spread` MEDIAN
# of **0.483** (p1 0.172 -- i.e. the flat version was at the 1st percentile of
# reality). These reaches reproduce the measured range.
FINGER_REACH = (0.055, 0.100, 0.105, 0.098, 0.082)      # thumb, index .. pinky


def make_hand(spread_m=0.09, curl=0.0, q=None):
    """A synthetic 21-landmark world hand. `curl` rotates the TIPS only, about
    the palm's own y axis, which is exactly the articulation the trim must see."""
    lm = [(0.0, 0.0, 0.0)] * 21
    half = spread_m / 2.0
    palm = {0: (0.0, -0.04, 0.0), 5: (-half, 0.0, 0.0), 9: (-half / 3.0, 0.01, 0.0),
            13: (half / 3.0, 0.01, 0.0), 17: (half, 0.0, 0.0)}
    tips = {}
    for k, i in enumerate(tip_trim.TIPS):
        x = -half + (2.0 * half) * (k / 4.0)
        base = (x, FINGER_REACH[k], -0.02 if k == 0 else 0.0)   # thumb off-plane
        if curl:
            c = quat_axis_angle((0.0, 1.0, 0.0), curl)
            base = rot(c, base)
        tips[i] = base
    out = list(lm)
    for i, p in list(palm.items()) + list(tips.items()):
        out[i] = p
    if q is not None:
        out = [rot(q, p) for p in out]
    return out


IDQ = tip_trim.IDENTITY


def section_gate():
    print("\n§1  ⛔ THE GATE — gain 0 is the shipped pipeline, exactly")
    t = tip_trim.TipTrim()
    h = make_hand()
    t.freeze(h, IDQ)
    got = t.update(make_hand(curl=25.0), IDQ, 0.09, 100.0, gain=0.0)
    check("gain 0 returns the IDENTITY OBJECT (not a rebuilt one)",
          got is tip_trim.IDENTITY)
    check("module default TRIM_GAIN is 0.0 -- it lands OFF",
          tip_trim.TRIM_GAIN == 0.0, str(tip_trim.TRIM_GAIN))
    t2 = tip_trim.TipTrim()
    check("an unfrozen trim is identity even at full gain",
          t2.update(h, IDQ, 0.09, 0.0, gain=1.0) is tip_trim.IDENTITY)


def section_rigid():
    print("\n§2  ⭐⭐ WHOLE-HAND ROTATION CANNOT REACH THE TRIM")
    print("      This is why the design is not B4's PALM_AND_TIPS. If it fails,")
    print("      the step is the arm that is already A10-dead twice.")
    t = tip_trim.TipTrim()
    base = make_hand()
    t.freeze(base, IDQ)
    worst = 0.0
    for deg in (5, 20, 45, 90, 140):
        for axis in ((0, 1, 0), (1, 0, 0), (0, 0, 1), (1, 1, 0)):
            q = quat_axis_angle(axis, deg)
            # The hand is RIGID and merely rotated; `q_palm` reports that rotation.
            got = t.update(make_hand(q=q), q, 0.09, 0.0, gain=1.0)
            worst = max(worst, palm_rotation.quat_angle_deg(IDQ, got))
    check("a rigidly rotated hand produces NO trim, on any axis",
          worst < 0.5, f"worst trim {worst:.4f} deg over 20 poses")


def section_articulation():
    print("\n§3  ARTICULATION DOES reach it, and is bounded")
    t = tip_trim.TipTrim()
    t.freeze(make_hand(), IDQ)
    got = t.update(make_hand(curl=20.0), IDQ, 0.09, 0.0, gain=1.0)
    deg = palm_rotation.quat_angle_deg(IDQ, got)
    check("curling the fingers DOES produce a trim", deg > 0.5, f"{deg:.2f} deg")

    t = tip_trim.TipTrim()
    t.freeze(make_hand(), IDQ)
    big = t.update(make_hand(curl=80.0), IDQ, 0.09, 0.0, gain=1.0)
    dbig = palm_rotation.quat_angle_deg(IDQ, big)
    check("...and is CLAMPED to TRIM_MAX_DEG",
          dbig <= tip_trim.TRIM_MAX_DEG + 1e-6,
          f"{dbig:.2f} deg vs cap {tip_trim.TRIM_MAX_DEG:.0f}")

    # ⚠ MEASURE PROPORTIONALITY BELOW THE CLAMP. A 20 deg curl saturates at both
    # gains -- both arms read exactly TRIM_MAX_DEG and the check "passes" while
    # measuring the cap rather than the gain. 8 deg keeps both arms in the linear
    # region, which is the only place proportionality is a claim at all.
    SMALL = 8.0
    t = tip_trim.TipTrim()
    t.freeze(make_hand(), IDQ)
    half = t.update(make_hand(curl=SMALL), IDQ, 0.09, 0.0, gain=0.5)
    t = tip_trim.TipTrim()
    t.freeze(make_hand(), IDQ)
    full = t.update(make_hand(curl=SMALL), IDQ, 0.09, 0.0, gain=1.0)
    dh = palm_rotation.quat_angle_deg(IDQ, half)
    df = palm_rotation.quat_angle_deg(IDQ, full)
    check("gain scales the ANGLE proportionally (below the clamp)",
          df < tip_trim.TRIM_MAX_DEG - 0.01 and abs(dh * 2.0 - df) < 1e-6,
          f"gain .5 -> {dh:.3f}, gain 1 -> {df:.3f} deg")


def section_conditioning():
    print("\n§4  ⭐ 'TO THE EXTENT THEY ARE ROBUST ENOUGH' — the fade")
    for x, want in ((0.0, 0.0), (tip_trim.SPREAD_FLOOR - 0.01, 0.0),
                    (tip_trim.SPREAD_FULL + 0.1, 1.0)):
        got = tip_trim._smoothstep(x, tip_trim.SPREAD_FLOOR, tip_trim.SPREAD_FULL)
        check(f"smoothstep({x:.2f}) -> {want:.0f}", abs(got - want) < 1e-9, f"{got:.4f}")
    mid = tip_trim._smoothstep((tip_trim.SPREAD_FLOOR + tip_trim.SPREAD_FULL) / 2,
                               tip_trim.SPREAD_FLOOR, tip_trim.SPREAD_FULL)
    check("...and is CONTINUOUS in between (a hard gate is a rotation step)",
          0.4 < mid < 0.6, f"{mid:.4f}")

    # A collinear cloud: every tip on one line.
    lm = list(make_hand())
    for k, i in enumerate(tip_trim.TIPS):
        lm[i] = (-0.045 + 0.0225 * k, 0.10, 0.0)
    pts = tip_trim.tips_in_palm_frame(lm, IDQ)
    spread, scale = tip_trim.conditioning(pts, 0.09)
    check("a COLLINEAR tip cloud reads spread ~ 0",
          spread < tip_trim.SPREAD_FLOOR, f"spread {spread:.4f}")
    ok_pts = tip_trim.tips_in_palm_frame(make_hand(), IDQ)
    ok_spread, _ = tip_trim.conditioning(ok_pts, 0.09)
    check("...while an ORDINARY hand is comfortably above the floor",
          ok_spread > tip_trim.SPREAD_FULL, f"spread {ok_spread:.4f}")

    # A fist: every tip in one place.
    lm = list(make_hand())
    for i in tip_trim.TIPS:
        lm[i] = (0.001, 0.002, 0.001)
    pts = tip_trim.tips_in_palm_frame(lm, IDQ)
    _sp, sc = tip_trim.conditioning(pts, 0.09)
    check("a FIST reads scale ~ 0", sc < tip_trim.SCALE_FLOOR, f"scale {sc:.4f}")

    t = tip_trim.TipTrim()
    t.freeze(make_hand(), IDQ)
    t.update(make_hand(curl=15.0), IDQ, 0.09, 0.0, gain=1.0)
    held = t._last_q
    got = t.update(lm, IDQ, 0.09, 40.0, gain=1.0)
    check("an unusable frame HOLDS the last trim, it does not snap to identity",
          got is held and got is not tip_trim.IDENTITY)


def section_edges():
    print("\n§5  EDGES")
    t = tip_trim.TipTrim()
    check("freeze() refuses a hand with no world landmarks", t.freeze(None, IDQ) is False)
    check("...and update() is identity while unfrozen",
          t.update(make_hand(), IDQ, 0.09, 0.0, gain=1.0) is tip_trim.IDENTITY)

    t = tip_trim.TipTrim()
    t.freeze(make_hand(), IDQ)
    t.update(make_hand(curl=10.0), IDQ, 0.09, 0.0, gain=1.0)
    t.reset()
    check("reset() clears the reference (a released cube leaves no trim)",
          t.frozen is False and
          t.update(make_hand(curl=60.0), IDQ, 0.09, 0.0, gain=1.0) is tip_trim.IDENTITY)

    check("palm_span_m measures the PALM quad, in metres",
          abs(tip_trim.palm_span_m(make_hand(spread_m=0.09)) - 0.09) < 1e-9,
          f"{tip_trim.palm_span_m(make_hand(spread_m=0.09)):.5f} m")
    check("palm_span_m degrades to 0.0, which fades the trim OUT",
          tip_trim.palm_span_m(None) == 0.0)


def main():
    print("=" * 82)
    print("TIP TRIM -- golden vectors (F1 step 4)")
    print("=" * 82)
    section_gate()
    section_rigid()
    section_articulation()
    section_conditioning()
    section_edges()
    print("=" * 82)
    if _fails:
        print(f"{len(_fails)} CHECK(S) FAILED")
        for n in _fails:
            print(f"   - {n}")
        return 1
    print("ALL CHECKS PASSED -- articulation only, bounded, faded, and off at gain 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
