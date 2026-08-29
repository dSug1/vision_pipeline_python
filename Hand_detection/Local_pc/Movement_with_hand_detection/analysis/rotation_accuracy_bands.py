# -*- coding: utf-8 -*-
"""⭐⭐ WHERE IS ROTATION MOST ACCURATE? Per axis, BINNED BY TURN SIZE, with V2 ON.

    .venv/Scripts/python.exe analysis/rotation_accuracy_bands.py

Owner, 2026-08-29: *"I want the accuracies on yaw, roll and pitch after we have
shipped v2. I want to find the ranges for each where the rotation accuracy is the
best."*

⛔⛔ WHY THIS FILE HAD TO EXIST. The lean-vs-turn table everyone quotes
(6.8 / 12.3 / 21.9 / 26.8 deg at 20 / 40 / 60 / 60-90 deg of turn) is the
**pre-V2 baseline**. `V2` shipped on 2026-08-28 and NOBODY REGENERATED IT. Scaling
those numbers by (1 - gain) is arithmetic, not measurement, and `METHOD` rule 1 is
"measure or revert". So this measures it.

────────────────────────────────────────────────────────────────────────────────
⭐ WHAT IS REUSED RATHER THAN RE-DERIVED (`N6`, and `METHOD`'s instrument rule)

* the FIT is `palm_rotation.Horn(PALM_LANDMARKS, "ref")` -- what ships;
* the TRIM is `lean_trim.trim()` at the shipped gains, READ FROM THE MODULE, never
  repeated as literals here. A/B is the same frame through the same estimator with
  only the trim differing;
* the ERROR is `lean_trim.swing_deg(q, axis=<this take's expected axis>)` -- the
  SHIPPED module's own function, not a local copy (trap #3: two harnesses
  aggregating differently under one name once reported pitch as "45-55 deg,
  broken" when the mean axis was 5.5 deg);

⛔⛔ AND THE INSTRUMENT MISTAKE THIS FILE MADE FIRST, KEPT AS THE WARNING. Its first
run reported the LEAN -- `swing_deg` about the VERTICAL, which is the shipping
gate's definition -- for all three axes. That is right for yaw and MEANINGLESS for
the other two: "how far from a pure YAW is it" applied to a pitch take just returns
the pitch itself, so roll scored 99.8 deg of "error" at a 90-120 deg roll and pitch
86.6 deg. Both were the gesture, reported as its own defect. ⭐ The fix is to judge
each axis against ITS OWN expected axis -- `swing_deg(q, axis=exp)` -- which for
yaw reduces to exactly the documented lean and reproduces 26.8 deg, and for the
other two finally means "how far off a PURE pitch / PURE roll".
* the GROUND TRUTH is each axis's own z-free construction, exactly as
  `t5i_zscale_sweep.py` (yaw/pitch) and `t5j_roll_axis.py` (roll) build it.

⛔ GROUND TRUTH IS DEPTH-FREE ON ALL THREE AXES, WHICH IS THE WHOLE POINT. The
defect under investigation IS MediaPipe's world z, so a truth that touched z would
share an expression with the thing being judged (`B4`). Yaw foreshortens palm
WIDTH, pitch foreshortens palm LENGTH, and roll foreshortens NOTHING -- its truth
is the in-image knuckle-row angle, read straight off the pixels.

────────────────────────────────────────────────────────────────────────────────
⚠⚠ THE FIVE TRAPS THIS FILE IS BUILT AROUND, all of them hit for real before

1. THE `acos` FOLD -- any foreshortening angle folds past edge-on (140 reads as
   40). It has produced bogus gains of 3.57, 2.41 and 21.5 in three sessions.
   Unwrapped here with DR-2's palm-facing sign. Roll WRAPS instead of folding and
   is unwrapped continuously.
2. THE REFERENCE FRAME IS THE MOST FACE-ON, NEVER THE FIRST -- using frame 0 moved
   a measured axis by 12 deg.
3. THE AXIS NOISE FLOOR -- below ~30 deg of rotation the axis is barely determined;
   a CLEAN pitch take reads 44-63 deg off its own axis there. Bins below the floor
   are printed with a `!` and their axis column must not be read as accuracy.
   ⭐ The LEAN and the GAIN are defined at every magnitude, which is why they carry
   the answer and the axis column is context.
4. STATE THE AGGREGATION -- MEAN-axis is bias only; MEDIAN-per-frame is bias +
   scatter. Both are printed, labelled.
5. CROSS-TAKE ABSOLUTE NUMBERS ARE NOT COMPARABLE -- the camera moved between
   recordings. Compare bins WITHIN a take; compare axes only by shape.

⚠ AND ONE THAT IS NOT A TRAP BUT A PREDICTION WORTH FALSIFYING: `V2` is gated on
YAW DOMINANCE (correct nothing at/below 0.35, correct in full at/above 0.65), so on
a PITCH or ROLL take it should do NOTHING AT ALL. The `auth` column reports the
mean authority per bin, so "pitch is unchanged" is measured here rather than
asserted from reading the source.

⛔⛔ THE `B4` WARNING, AND IT BINDS THIS TABLE AS HARD AS IT BINDS THE GATE:
**THE `OFF-AXIS off -> ON` COLUMNS ARE SELF-MEASURING ON THE YAW TAKE.** The metric
is the swing about the vertical; `V2` multiplies exactly that swing by (1 - gain).
So "27.3 -> 9.3" is not a discovery, it is 0.34x applied to a measured number, and
`METHOD` rule 2 says a metric built from the thing it judges measures nothing.

⭐ WHAT IS ACTUALLY INDEPENDENT HERE, and it is the part worth reading:
  * the per-frame JUMP ratio -- the trim could have bought its lean with tail
    steadiness, which is how three predecessors died. On yaw it does not;
  * the GAIN ABOUT EACH TAKE'S OWN AXIS (`AXgain-` / `AXgain+`). ⛔⛔ AND THE FIRST
    VERSION OF THIS LINE WAS WRONG, WHICH IS WHY IT IS SPELLED OUT: it claimed the
    gain is "untouched by construction, the twist is left exact". That holds ONLY
    about `V2`'s OWN twist axis, the vertical -- where it is confirmed exactly
    (`AXgain-` == `AXgain+` to every decimal, all 8 yaw bands). A PITCH is entirely
    SWING in that decomposition, so nothing protects it: wherever the dominance
    gate lets the trim fire on pitch, the trim SHRINKS THE GESTURE (measured:
    0.18 -> 0.13 in the 40-50 deg band). The owner asked exactly this and was
    right;
  * the AUTHORITY distribution -- whether the trim fires where it was meant to. It
    is the only column that can surprise you, and on the pitch take it does;
  * the SHAPE across bands -- the trim scales uniformly, so the RANKING of bands is
    the underlying geometry and survives the self-measurement objection.

Stdlib only. Reads the corpus, writes nothing.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Resources"))

from Resources import lean_trim as LT                          # noqa: E402
from Resources import palm_rotation as PR                      # noqa: E402
from Resources import palm_geometry as PG                      # noqa: E402
# ⭐ IMPORTED, NOT COPIED: one definition of per-frame steadiness for the shipping
# gate and for this. The ERROR metric comes straight from `lean_trim` below.
from lean_trim_ab import geo_deg                               # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 5, 9, 17

# ⚠ The floor is stated, not tuned: trap #3. Bins whose centre is under it are
# flagged so the axis column is never read as an accuracy there.
AXIS_FLOOR_DEG = 30.0

# ⚠ Bin EDGES are chosen to reproduce the documented table's rows (20 / 40 / 60 /
# 60-90) so the new numbers can be read straight against the old ones. Changing
# them to something prettier would break exactly that comparison.
BANDS = ((5, 10), (10, 20), (20, 30), (30, 40), (40, 50),
         (50, 60), (60, 75), (75, 90), (90, 120))

#            key substring                       axis    expected axis   truth
TAKES = (
    ("2026-08-22_134553_yaw_sweep",   "YAW",   (0.0, 1.0, 0.0), "width",  0.0),
    ("2026-08-02_191816_pitch_sweep", "PITCH", "knuckles",      "length", 0.0),
    # ⭐ THE SECOND PITCH TAKE, deliberately kept: the hold-wobble finding below
    # is strong enough that one take must not carry it. ⚠ `t5i` records this
    # take's mean-axis as 30.0° against the other's 5.5° and calls the gap
    # UNEXPLAINED -- so it is the weaker take, and it is here as corroboration
    # of a defect, never as the primary evidence for one.
    ("2026-08-04_054702_pitch_sweep", "PITCH2", "knuckles",     "length", 0.0),
    ("2026-08-23_211528_roll_card",   "ROLL",  (0.0, 0.0, 1.0), "roll",   4.0),
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                           # pragma: no cover
    pass


def pct(xs, p):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def axis_angle(q):
    """Unit axis and angle in degrees, or (None, angle) when degenerate."""
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    ang = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, math.degrees(ang)
    return (x / s, y / s, z / s), math.degrees(ang)


def load(key, head_s):
    m = [d for d in sorted(os.listdir(CAPTURE)) if key in d]
    if not m:
        return None, []
    session = m[-1]
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.isfile(path):
        return session, []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("tCapture", 0.0) < head_s * 1000.0:
                continue          # ⚠ roll take: the first 4 s are the operator
            hs = r.get("hands") or []
            if len(hs) != 1:
                continue          # one hand only -- no ownership question here
            h = hs[0]
            px, wl = h.get("landmarks"), h.get("world_landmarks")
            if px and wl and len(px) >= 21 and len(wl) >= 21:
                out.append((px, wl, h.get("handedness", "Right")))
    return session, out


def span(px, kind):
    if kind == "width":
        return math.hypot(px[INDEX_MCP][0] - px[PINKY_MCP][0],
                          px[INDEX_MCP][1] - px[PINKY_MCP][1])
    return math.hypot(px[WRIST][0] - px[MIDDLE_MCP][0],
                      px[WRIST][1] - px[MIDDLE_MCP][1])


def knuckle_angle(px):
    return math.degrees(math.atan2(px[PINKY_MCP][1] - px[INDEX_MCP][1],
                                   px[PINKY_MCP][0] - px[INDEX_MCP][0]))


def ground_truth(frames, kind):
    """Depth-free rotation magnitude. Yaw/pitch: foreshortening, unwrapped past
    edge-on with DR-2's sign. Roll: the in-image knuckle angle, unwrapped."""
    if kind == "roll":
        # ⭐ reference = the SQUAREST frame, which is roll's own analogue of
        # "most face-on" (t5j). Under a pure roll nothing foreshortens, so the
        # squareness is flat and the choice is stable.
        eo = [PG.edge_on_measure(px) for px, _w, _h in frames]
        ref = max(range(len(frames)), key=lambda i: (eo[i] if eo[i] is not None else -1))
        a0 = knuckle_angle(frames[ref][0])
        truth = []
        for px, _w, _h in frames:
            d = knuckle_angle(px) - a0
            while d > 180.0:
                d -= 360.0
            while d < -180.0:
                d += 360.0
            truth.append(abs(d))
        return ref, truth

    ref = max(range(len(frames)), key=lambda i: span(frames[i][0], kind))
    s0 = span(frames[ref][0], kind)
    sign0 = PG.is_thumb_outward(frames[ref][0], frames[ref][2])
    truth = []
    for px, _w, hd in frames:
        a = math.degrees(math.acos(max(-1.0, min(1.0, span(px, kind) / (s0 or 1.0)))))
        if PG.is_thumb_outward(px, hd) != sign0:
            a = 180.0 - a          # trap #1: past edge-on, acos folds -- unwrap
        truth.append(a)
    return ref, truth


def run_take(key, axis_name, expected, kind, head_s):
    session, frames = load(key, head_s)
    if not frames:
        print(f"\n  -- {key}: no usable frames, SKIPPED")
        return
    ref, truth = ground_truth(frames, kind)

    exp = expected
    if exp == "knuckles":
        # ⛔ Pitch rotates about the KNUCKLE ROW, which is horizontal only if the
        # hand happens to be upright. Assuming a fixed horizontal produced 45.7 deg
        # on one pitch take against 17.7 on another -- both absurd next to 5.0.
        px0 = frames[ref][0]
        dx = px0[PINKY_MCP][0] - px0[INDEX_MCP][0]
        dy = px0[PINKY_MCP][1] - px0[INDEX_MCP][1]
        n = math.hypot(dx, dy) or 1.0
        exp = (dx / n, dy / n, 0.0)

    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    st = horn.freeze(frames[ref][0], frames[ref][1])
    if st is None:
        print(f"\n  -- {session}: degenerate reference frame, SKIPPED")
        return

    # ⚠ Paired BY INDEX with the truth array, in one pass: a second pass that
    # re-fits would be a second implementation, and `delta()` returning None on a
    # degenerate frame would silently shift the pairing by one.
    paired = []                    # (true_deg, q_trim_OFF, q_trim_ON)
    for i, (px, wl, _hd) in enumerate(frames):
        q = horn.delta(st, px, wl)
        if q is None:
            continue
        paired.append((truth[i], q, LT.trim(q)))   # gains default to the SHIPPED ones

    print(f"\n  {axis_name}   {session}")
    print(f"    {len(paired)} frames · reference = "
          f"{'squarest' if kind == 'roll' else 'most face-on'} (#{ref})"
          f" · true rotation reaches {max(truth):.0f}°")
    print(f"    {'turn band':>11s} {'n':>5s} {'AXgain-':>6s} {'AXgain+':>6s} "
          f"{'tot-':>6s} {'OFFAX-':>9s} {'OFFAX+':>6s} "
          f"{'axis/fr':>8s} {'nax':>4s} {'auth':>5s}")
    print("    " + f"{'':>17s}(- = trim OFF, + = trim ON)")
    print("    " + "-" * 80)

    for lo, hi in BANDS:
        sel = [r for r in paired if lo <= r[0] < hi]
        if len(sel) < 8:           # too few frames to median honestly
            continue
        gains, gains_off, off_a, off_b, axdev, auths, axes = [], [], [], [], [], [], []
        tw_on, tw_off = [], []
        for tdeg, q, qt in sel:
            ax, ang = axis_angle(qt)
            _ax0, ang0 = axis_angle(q)
            if tdeg > 1e-6:
                gains.append(ang / tdeg)
                # ⭐⭐ THE GAIN WITH THE TRIM OFF, SO THE PAIR ANSWERS "DOES V2 CHANGE
                # THE TURN AMOUNT?" -- which for YAW is supposed to be NO by
                # construction (the twist is left exact), and for PITCH is not
                # protected by anything: a pitch IS swing about the vertical, so
                # wherever the dominance gate leaks, V2 SHRINKS THE GESTURE.
                gains_off.append(ang0 / tdeg)
                # ⭐⭐⭐ THE GAIN THAT ACTUALLY MEANS "DID IT TURN THE RIGHT AMOUNT
                # ABOUT THE AXIS THE OPERATOR TURNED ABOUT". The total-angle gain
                # above CONFLATES the wanted turn with the spurious lean, so `V2`
                # removing lean reads there as a LOWER gain -- which is error being
                # removed, not signal. Projecting onto the take's OWN expected axis
                # separates them, and it is the only form in which the question
                # "does the trim change the turn amount?" has a defined answer.
                # ⛔ For YAW that axis IS `V2`'s twist axis, so the trim cannot
                # touch it and the two columns must come out IDENTICAL -- which
                # makes this a live check of the trim's central claim, not a
                # description of it. For PITCH nothing protects it.
                tw_on.append(abs(LT.twist_angle_deg(qt, axis=exp)) / tdeg)
                tw_off.append(abs(LT.twist_angle_deg(q, axis=exp)) / tdeg)
            # ⭐⭐ EACH AXIS JUDGED AGAINST ITS OWN EXPECTED AXIS. For yaw `exp` is
            # the world vertical, so this IS the documented lean and reproduces it.
            off_a.append(LT.swing_deg(q, axis=exp))
            off_b.append(LT.swing_deg(qt, axis=exp))
            auths.append(LT.authority(q))
            # ⛔ THE FLOOR BELONGS ON THE **FITTED** ANGLE, NOT THE TRUE ONE. It is
            # the fitted quaternion's axis whose direction is undefined near
            # identity; gating on the true angle let frames with a 12° fit into a
            # "40-50°" bin and inflated its axis column to 74°.
            if ax is not None and ang >= AXIS_FLOOR_DEG:
                dot = abs(sum(a * e for a, e in zip(ax, exp)))
                axdev.append(math.degrees(math.acos(max(-1.0, min(1.0, dot)))))
                a = ax
                if axes and sum(p * q2 for p, q2 in zip(a, axes[0])) < 0.0:
                    a = (-a[0], -a[1], -a[2])
                axes.append(a)
        flag = "!" if (lo + hi) / 2.0 < AXIS_FLOOR_DEG else " "
        print(f"    {lo:4.0f}-{hi:3.0f}°{flag} {len(sel):5d} "
              f"{pct(tw_off, 50):6.2f} {pct(tw_on, 50):6.2f} "
              f"{pct(gains_off, 50):6.2f} "
              f"{pct(off_a, 50):8.1f}° {pct(off_b, 50):5.1f}° "
              f"{pct(axdev, 50):7.1f}° {len(axdev):4d} "
              f"{sum(auths) / len(auths):5.2f}")

    # ---- the MEAN-axis (bias-only) number, for continuity with the documented
    # table, computed over the frames ABOVE the noise floor only.
    big = [r for r in paired if r[0] >= 40.0]
    if big:
        axes = []
        for _t, _q, qt in big:
            ax, ang = axis_angle(qt)
            if ax is None or ang < AXIS_FLOOR_DEG:
                continue
            if axes and sum(p * q2 for p, q2 in zip(ax, axes[0])) < 0.0:
                ax = (-ax[0], -ax[1], -ax[2])
            axes.append(ax)
        if axes:
            mx = sum(a[0] for a in axes) / len(axes)
            my = sum(a[1] for a in axes) / len(axes)
            mz = sum(a[2] for a in axes) / len(axes)
            n = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
            mdot = abs((mx * exp[0] + my * exp[1] + mz * exp[2]) / n)
            print(f"    MEAN-axis over the {len(axes)} frames past 40° of true "
                  f"rotation (bias only): {math.degrees(math.acos(max(-1.0, min(1.0, mdot)))):.1f}°")

    # ---- ⭐⭐ HOW OFTEN DOES V2 FIRE ON THIS AXIS AT ALL? The trim is supposed to
    # act on TURNS and leave pitch/roll gestures alone (dominance gate, 0.35/0.65).
    # Printing the DISTRIBUTION rather than the per-bin mean is what makes a LEAK
    # visible: a mean of 0.30 is one frame in three at full authority just as much
    # as it is every frame at a third, and those are different defects.
    auths = [LT.authority(q) for _t, q, _qt in paired]
    if auths:
        n0 = sum(1 for a in auths if a <= 0.01)
        nf = sum(1 for a in auths if a >= 0.99)
        npart = len(auths) - n0 - nf
        print(f"    V2 authority: {100.0*n0/len(auths):5.1f}% silent · "
              f"{100.0*npart/len(auths):5.1f}% partial · "
              f"{100.0*nf/len(auths):5.1f}% full")

    # ---- per-frame steadiness, the gate that killed three predecessors
    ja, jb = [], []
    for i in range(1, len(paired)):
        a = geo_deg(paired[i][1], paired[i - 1][1])
        b = geo_deg(paired[i][2], paired[i - 1][2])
        if a is not None:
            ja.append(a)
        if b is not None:
            jb.append(b)
    if ja:
        print(f"    per-frame JUMP  median {pct(ja,50):.2f}° -> {pct(jb,50):.2f}°   "
              f"p95 {pct(ja,95):.2f}° -> {pct(jb,95):.2f}°   (trim off -> ON)")

    resolvability(axis_name, paired)


def resolvability(axis_name, paired):
    """⭐⭐ IS THERE A MINIMUM TURN BELOW WHICH THE ROTATION IS NOT RELIABLE?

    Owner, 2026-08-29. ⛔ The documented "~30 deg axis noise floor" does NOT answer
    it: that floor is about the AXIS DIRECTION being undefined near identity, which
    is a statement about a DIAGNOSTIC column, not about whether the product can
    tell a 15 deg turn from a 20 deg one.

    ⭐ The product-level question is SIGNAL vs NOISE:
      * SIGNAL = the median FITTED angle in a band, and how far apart consecutive
        bands sit -- can the pipeline separate this band from its neighbour at all;
      * NOISE  = the per-frame orientation JUMP on the same take. That is the
        pipeline's own frame-to-frame wobble, in the same unit, measured on the
        same frames. No ground truth needed, so the foreshortening truth's
        ill-conditioning near face-on cannot contaminate it.

    A band is RESOLVED when its fitted angle stands clear of the frame-to-frame
    wobble. `snr` is median-fitted / p95-wobble-DURING-HOLDS: at 1.0 a pose of that
    size is the same size as the pipeline's worst single-frame wobble while the
    hand is STILL, so it cannot be held apart from its neighbour. Take ~2 as the
    floor.

    ⚠ Reported per take, never across -- the wobble is the take's own.
    ⛔ THIS IS A DIFFERENT FLOOR FROM THE GAIN'S, AND CONFLATING THEM IS THE ERROR
    THIS FUNCTION EXISTS TO PREVENT. A band can be RESOLVED (the pose is
    distinguishable from noise) and still MIS-SCALED (the fitted angle is only half
    the true one). Yaw is exactly that between 10 and 40 deg: snr 4-10, gain ~0.5.
    "Reliable" has to say WHICH of the two is meant."""
    # ⛔⛔ TWO DIFFERENT WOBBLES, AND USING THE WRONG ONE OVERSTATES THE FLOOR.
    # A take-wide p95 jump is dominated by the FAST SWEEP between holds -- motion
    # the operator asked for, not error. The number that decides "can I HOLD a
    # pose at this angle" is the wobble while the hand is nearly still, so the
    # frames are split by how fast the TRUTH is moving and both are reported.
    # ⚠ The split is on the truth's frame-to-frame step, which is depth-free.
    HOLD_STEP_DEG = 1.0
    jumps, hold_jumps = [], []
    for i in range(1, len(paired)):
        g = geo_deg(paired[i][1], paired[i - 1][1])
        if g is None:
            continue
        jumps.append(g)
        if abs(paired[i][0] - paired[i - 1][0]) < HOLD_STEP_DEG:
            hold_jumps.append(g)
    if not jumps:
        return
    j50, j95 = pct(jumps, 50), pct(jumps, 95)
    h95 = pct(hold_jumps, 95) if len(hold_jumps) >= 20 else float("nan")
    print()
    print("    RESOLVABILITY -- fitted signal against this take's own wobble")
    print(f"      wobble, WHOLE take : median {j50:.2f}° · p95 {j95:.2f}°")
    print(f"      wobble, HOLDS only : p95 {h95:.2f}°   "
          f"({len(hold_jumps)} frames with the truth moving <{HOLD_STEP_DEG:.0f}°/frame)")
    if h95 == h95:                       # not NaN
        j95 = h95                        # the floor that decides a HOLD
    print(f"      {'true band':>11s} {'fitted p10':>10s} {'p50':>6s} {'p90':>6s} "
          f"{'spread':>7s} {'snr':>5s}")
    print("      " + "-" * 52)
    for lo, hi in BANDS:
        sel = [r for r in paired if lo <= r[0] < hi]
        if len(sel) < 8:
            continue
        fit = []
        for _t, q, _qt in sel:
            _ax, ang = axis_angle(q)
            fit.append(ang)
        f10, f50, f90 = pct(fit, 10), pct(fit, 50), pct(fit, 90)
        snr = f50 / j95 if j95 > 1e-9 else float("nan")
        mark = "  <-- at/below the wobble" if snr < 1.0 else ""
        print(f"      {lo:4.0f}-{hi:3.0f}° {f10:9.1f}° {f50:5.1f}° {f90:5.1f}° "
              f"{f90 - f10:6.1f}° {snr:5.1f}{mark}")


def main():
    print("=" * 78)
    print("ROTATION ACCURACY BY TURN SIZE -- the POST-V2 table, all three axes")
    print("=" * 78)
    print(f"  shipped trim gains: pitch {LT.GAIN_PITCH:.2f} / roll {LT.GAIN_ROLL:.2f}"
          f"   (read from lean_trim, not repeated here)")
    print(f"  dominance gate: nothing at/below {LT.DOMINANCE_LO:.2f}, "
          f"full at/above {LT.DOMINANCE_HI:.2f}; floor {LT.MIN_TOTAL_DEG:.0f}° total")
    print()
    print("  OFF-AXIS = how far out of a PURE rotation about THIS take's own axis")
    print("             (lean_trim.swing_deg against the expected axis). For YAW")
    print("             this IS the documented 'lean'. off -> ON = trim off -> ON.")
    print("  gain     = fitted angle / true angle. 1.00 is exact; >1 over-turns.")
    print("  axis/fr  = MEDIAN PER-FRAME deviation from the expected axis")
    print("             (bias + scatter), over the `nax` frames whose FITTED angle")
    print("             clears the 30° noise floor. ! = the band's centre is under")
    print("             the floor, so few frames qualify and it is thin evidence.")
    print("  ⚠ gain    = binned BY the truth, and the foreshortening truth is")
    print("             ill-conditioned near face-on (acos of a ratio near 1), which")
    print("             biases the low bands' truth HIGH and their gain LOW. Read")
    print("             the gain from the bands past 40° only.")
    print("  auth     = mean V2 authority. 0.00 = the trim is doing NOTHING here.")
    print()
    print("  ⚠ Compare bins WITHIN a take. Absolute numbers are NOT comparable")
    print("    across takes -- the camera moved between recordings.")

    for key, axis_name, expected, kind, head_s in TAKES:
        run_take(key, axis_name, expected, kind, head_s)

    print()
    print("  MEAN-axis = bias only. axis/fr = bias + per-frame scatter. Not the")
    print("  same number, and reading one against the other once reported pitch")
    print("  as \"45-55°, broken\" when the mean axis was 5.5°.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
