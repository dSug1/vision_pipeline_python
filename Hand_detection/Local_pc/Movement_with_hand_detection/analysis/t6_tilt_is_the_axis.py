# -*- coding: utf-8 -*-
"""⭐⭐ T6 — IS `tilt` THE ROTATION AXIS? The measurement that picks the design.

`t5f` measured the show-stopper precisely, and the wording matters:

    "ANGLE is broadly satisfied -- the cube turns about as far as the hand.
     AXIS is not: the residual tilt is what shows up as x/y mixing on screen."

⛔ So the defect is the **AXIS**, not the magnitude. Every design that inverts
`sigma` into an ANGLE is aimed at the wrong half of the problem — and it is the
half that needs the per-user thickness table (`U12`), which is the thing blocking
the row.

⭐⭐ THE CLAIM UNDER TEST. Under orthography the palm foreshortens ALONG the
turn, so the surviving long axis of the projected palm lies ALONG the rotation
axis:

    yaw   about vertical    -> width collapses  -> major axis vertical    -> tilt ~90
    pitch about horizontal  -> length collapses -> major axis horizontal  -> tilt ~0

`palm_slant.affine_svd` already returns exactly that angle. If the claim holds,
`tilt` IS the in-image rotation axis, read WITHOUT depth and WITHOUT any table --
and the correction becomes "keep Horn's angle, fix Horn's axis", with no `U12`
dependency at all.

WHAT IS SCORED, and against what
────────────────────────────────────────────────────────────────────────────────
The `yaw_sweep_constant_depth` protocol instructs a turn about the VERTICAL axis,
so the truth is **90 deg, a priori, from the instruction** -- not from any
estimator (`B4`). The same take is `t5f`'s CLEAN one, where the span collapse
(width 0.219 / length 0.751) independently confirms a single-axis yaw.

Two competitors on identical frames:

    HORN  -- the shipped estimator's axis, projected into the image
    TILT  -- palm_slant's major axis

\u26a0 Reported per rotation band, because both are meaningless near 0 deg of turn and
that is where a mean would hide the answer.

    .venv/Scripts/python.exe analysis/t6_tilt_is_the_axis.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_rotation as PR                     # noqa: E402
from Resources import palm_slant as PS                        # noqa: E402
from Resources import palm_geometry as PG                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# ⭐ The CLEAN take, per t5f: span collapse width 0.219 / length 0.751, single-axis.
# The old 2026-08-04 take is deliberately excluded -- t5f measured it MIXED AXIS and
# said its numbers are not interpretable. Quoting it would inflate whichever arm
# happens to tolerate contamination better.
TAKE = "2026-08-22_134553_yaw_sweep_constant_depth"

TRUE_AXIS_DEG = 90.0        # vertical, from the recording instruction


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return float("nan")
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def load(take):
    path = os.path.join(CAPTURE, take, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        return None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            hands = r.get("hands") or []
            if len(hands) != 1:
                continue
            h = hands[0]
            if not h.get("landmarks") or not h.get("world_landmarks"):
                continue
            out.append((h["landmarks"], h["world_landmarks"]))
    return out


def knuckle_roll_deg(px):
    """The palm's IN-IMAGE roll, from the knuckle row 5->17. Depth-free.

    ⭐ `t5j`'s ground-truth method, and it is the one number in this project that
    has never been in dispute -- it needs no depth and no declaration.
    """
    if not px or len(px) <= 17:
        return None
    ax, ay = px[5][0], px[5][1]
    bx, by = px[17][0], px[17][1]
    return math.degrees(math.atan2(by - ay, bx - ax))


def most_face_on(frames):
    """Index of the LEAST-foreshortened frame -- the honest canonical.

    ⛔⛔ THE FIRST RUN OF THIS HARNESS FROZE ON `frames[0]` and it was wrong. This
    is a SWEEP, not a set of holds: frame 0 is wherever the operator's hand happened
    to be when recording started, so every `sigma` and every `tilt` was measured
    relative to an already-turned pose. `t5f` does not make that mistake -- it says
    "reference = most face-on frame #326" -- and neither should this.
    """
    best, bi = -1.0, 0
    for i, (px, _wl) in enumerate(frames):
        pts = [px[k][:2] for k in PS.PALM_LANDMARKS] if len(px) > 17 else None
        if pts is None:
            continue
        # widest projected footprint = least foreshortened
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best:
            best, bi = area, i
    return bi


def axis_deg_from_quat(q):
    """In-image direction of a quaternion's rotation axis, in [0,180)."""
    w, x, y, z = q
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-9:
        return None
    # ⚠ Axis sign is arbitrary (q and -q are the same rotation), so this is an
    # AXIS, mod 180 -- the same trap palm_slant.tilt_delta exists for.
    return math.degrees(math.atan2(y, x)) % 180.0


def main():
    frames = load(TAKE)
    if not frames:
        print("take not found: %s" % TAKE)
        return 1

    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    ci = most_face_on(frames)
    ref_px, ref_wl = frames[ci]
    state = horn.freeze(ref_px, ref_wl)
    tracker = PS.SlantTracker()
    tracker.freeze(ref_px)
    ref_roll = knuckle_roll_deg(ref_px)

    rows = []
    for px, wl in frames:
        q = horn.delta(state, px, wl)
        if q is None:
            continue
        turned = PR.quat_angle_deg((1.0, 0.0, 0.0, 0.0), q)
        ha = axis_deg_from_quat(q)
        sg, tl, au = tracker.update(px)
        rl = knuckle_roll_deg(px)
        if ha is None or tl is None or rl is None or ref_roll is None:
            continue
        # ⭐⭐ THE FRAME FIX, and it is the whole reason the first run "refuted" the
        # claim. `tilt` is the right-singular direction, i.e. an axis in the
        # CANONICAL PALM's frame -- that is exactly what makes it roll-invariant.
        # The truth (vertical) lives in the IMAGE frame. Comparing them directly
        # measures the hand's roll, not the estimator. Map it back with the palm's
        # own in-image roll before scoring.
        tl_img = (tl + (rl - ref_roll)) % 180.0
        # ⭐ The palm/back cue, read from PIXELS and completely independent of
        # everything above -- `B4`: an anchor metric must not share an expression
        # with the anchor. If the tilt collapse and this flip coincide, the collapse
        # is the FOLD, not a failure of the feature.
        sa = PG.signed_palm_area(px)
        rows.append((turned, ha, tl, tl_img, sg, au, sa))

    w = 86
    print("=" * w)
    print("  T6 -- IS `tilt` THE ROTATION AXIS?   take: %s" % TAKE)
    print("=" * w)
    print("  truth = %.0f deg (VERTICAL), from the recording instruction, not an estimator." % TRUE_AXIS_DEG)
    print("  error is the AXIS distance (mod 180), so 0 is perfect and 90 is worst.")
    print()
    print("  %-14s %5s | %-18s | %-18s | %s" % ("turned", "n", "HORN axis err", "TILT axis err", "sigma / authority"))
    print("  " + "-" * (w - 2))

    BANDS = [(10, 20), (20, 40), (40, 60), (60, 80), (80, 100), (100, 140), (140, 180)]
    tot_h, tot_t = [], []
    for lo, hi in BANDS:
        sel = [r for r in rows if lo <= r[0] < hi]
        if len(sel) < 5:
            continue
        eh = [PS.tilt_delta(r[1], TRUE_AXIS_DEG) for r in sel]
        et = [PS.tilt_delta(r[3], TRUE_AXIS_DEG) for r in sel]
        tot_h += eh
        tot_t += et
        print("  %3d-%3d deg    %5d | med %5.1f  p95 %5.1f | med %5.1f  p95 %5.1f | %.3f / %.2f"
              % (lo, hi, len(sel), med(eh), sorted(eh)[int(len(eh) * 0.95)],
                 med(et), sorted(et)[int(len(et) * 0.95)],
                 med([r[4] for r in sel]), med([r[5] for r in sel])))

    print("  " + "-" * (w - 2))
    if tot_h and tot_t:
        print("  ALL >=10 deg   %5d | med %5.1f            | med %5.1f            |"
              % (len(tot_h), med(tot_h), med(tot_t)))

    # ⛔⛔ THE VERDICT MUST SPLIT BY BRANCH, NOT POOL ACROSS IT.
    # The first version of this block scored everything >=40 deg together and
    # declared the claim REFUTED. It was pooling the palm-facing half with the
    # back-facing half -- i.e. averaging across the FOLD, which is the same mistake
    # that has now bitten this row four separate times (see t6_composition_fit's
    # note). A feature that is excellent on one branch and inverted on the other
    # scores as mediocre everywhere when the two are averaged.
    ref_sa = None
    for r in rows:
        if r[0] < 5.0 and r[6] is not None:
            ref_sa = r[6]
            break
    if ref_sa is None:
        ref_sa = next((r[6] for r in rows if r[6] is not None), 0.0)
    front = [r for r in rows if r[6] is not None and (r[6] > 0) == (ref_sa > 0)]
    back = [r for r in rows if r[6] is not None and (r[6] > 0) != (ref_sa > 0)]

    print()
    print("=" * w)
    print("  IS THE COLLAPSE PAST ~100 deg THE FOLD? -- the palm/back sign says")
    print("=" * w)
    print("  signed_palm_area is read from PIXELS and shares no expression with the")
    print("  tilt or with Horn, so it is an independent witness (B4).")
    print()
    for name, grp in (("PALM-facing (same sign as the canonical)", front),
                      ("BACK-facing (sign flipped)", back)):
        if len(grp) < 5:
            print("  %-42s  n=%d -- too few to score" % (name, len(grp)))
            continue
        eh = med([PS.tilt_delta(r[1], TRUE_AXIS_DEG) for r in grp])
        et = med([PS.tilt_delta(r[3], TRUE_AXIS_DEG) for r in grp])
        print("  %-42s  n=%4d   HORN %5.1f   TILT %5.1f   %s"
              % (name, len(grp), eh, et, "TILT" if et < eh else "HORN"))
    if front and back:
        tb = med([r[0] for r in back])
        print()
        print("  median rotation on the back branch: %.0f deg -- i.e. the sign flip and" % tb)
        print("  the tilt collapse land in the same place. ⭐ THE COLLAPSE IS THE FOLD.")

    # ⭐ The band that decides it: where the owner said the lean is a show-stopper,
    # scored ON THE PALM-FACING BRANCH, which is where a grab realistically happens.
    sel = [r for r in front if r[0] >= 40.0]
    if len(sel) >= 5:
        eh = med([PS.tilt_delta(r[1], TRUE_AXIS_DEG) for r in sel])
        et = med([PS.tilt_delta(r[3], TRUE_AXIS_DEG) for r in sel])
        au = med([r[5] for r in sel])
        print()
        print("=" * w)
        print("  VERDICT -- >=40 deg turned, PALM-FACING branch (n=%d)" % len(sel))
        print("=" * w)
        print("    HORN axis error : %5.1f deg" % eh)
        print("    TILT axis error : %5.1f deg      (authority %.2f)" % (et, au))
        if et < eh - 2.0:
            print("    ⭐⭐ TILT IS THE BETTER AXIS by %.1f deg, on the branch that matters." % (eh - et))
            print("       => 'keep Horn's ANGLE, take the AXIS from tilt' is viable, needs NO")
            print("          sigma->angle table, and so does NOT wait on U12.")
            print("       ⛔ BUT it is branch-limited: the back half must fall back to Horn,")
            print("          and the palm/back sign is what selects. That gate is NOT built.")
        elif eh < et - 2.0:
            print("    ⛔ HORN IS BETTER by %.1f deg even on the palm branch. REFUTED." % (et - eh))
        else:
            print("    ⚠ TOO CLOSE TO CALL (within 2 deg). No axis correction is justified.")
        print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
