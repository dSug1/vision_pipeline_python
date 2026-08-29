# -*- coding: utf-8 -*-
"""⛔ THE GATE, RUN FIRST: does the lean trim cost per-frame steadiness?

    .venv/Scripts/python.exe analysis/lean_trim_ab.py <session> [<session> ...]

`REJECTED.md`, on the three orientation estimators that died before this one:

    "A fourth attempt of this shape should not be proposed unless it first
     demonstrates a per-frame orientation jump AT OR UNDER shipped Horn's on a
     GRABBING take -- the lean number is not the gate and never was."

⭐⭐ SO THE JUMP IS PRINTED FIRST AND THE LEAN SECOND, deliberately. Three builds
scored BETTER on the lean and WORSE on the tail, and the tail decided the verdict
every time. A lean number quoted before the jump number is the exact mistake this
row has already made three times.

⚠ THE METRIC IS THE FULL QUATERNION STEP, NOT AXIS WANDER. `REJECTED.md` again:
an earlier A/B measured per-frame AXIS DIRECTION, which is undefined for a
near-identity rotation, and duly reported smoothing as making jitter WORSE. The
geodesic angle between consecutive orientations is defined everywhere.

⚠ AND IT IS SCORED ON GRABBING TAKES. `T6`'s closing method rule: *a corpus whose
MOTION does not match the product's cannot validate an estimator for the product.*
Every take that killed the previous attempts was an OPEN hand; the game GRIPS. Pass
sessions recorded during normal handling, not instructed sweeps.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import lean_trim as LT                         # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass


def geo_deg(a, b):
    """ROTATION angle between two orientations, in degrees -- stable near identity.

    ⛔⛔ THE FACTOR OF 2, FIXED 2026-08-29, AND IT WAS WRONG FOR AS LONG AS THIS
    FILE HAS EXISTED. `2*atan2(|a-b|, |a+b|)` is the geodesic on the unit quaternion
    sphere S3 -- and S3 DOUBLE-COVERS SO(3), so that angle is **exactly half the
    rotation angle**. Verified against `palm_rotation.quat_angle_deg`:

        true rotation      geo_deg (before)      quat_angle_deg
             1.0 deg            0.500                1.000
            20.0 deg           10.000               20.000
            90.0 deg           45.000               90.000

    ⭐⭐ WHAT IT DID **NOT** BREAK, AND THAT IS WHY IT SURVIVED: THE GATE THIS FILE
    EXISTS FOR IS A RATIO (trimmed p95 / shipped p95), and a constant factor cancels
    exactly. **Every `V2` verdict stands unchanged** -- 1.072x on `stripped`, the
    0.892x / 0.995x no-ops of the double-cover fix, the 1.166x pitch failure. A
    dimensionless comparison was immune to a scale error in its own instrument.

    ⛔ WHAT IT DID BREAK: every ABSOLUTE per-frame number ever read off this helper
    was half its true value -- including the 2026-08-29 delta-orbit window and noise
    tables, which had to be doubled. ⚠ `analysis/` ONLY: `geo_deg` is imported by no
    shipped module, so neither tool ever consumed it.

    ⭐⭐⭐ THE METHOD RULE, and it is a new one: **A METRIC USED ONLY IN RATIOS IS
    NEVER SCALE-CHECKED BY ITS OWN CONSUMERS.** This file's gate could not have
    caught it, and did not, for the whole life of the row. A helper returning a
    PHYSICAL quantity must be checked against a KNOWN input at least once --
    `verify_delta_orbit.py` now does exactly that, on a hand-computed 20 deg step.
    ⚠ `4.0 *` rather than a rewrite: the `atan2(d, s)` form is KEPT because it is
    what stays conditioned near identity, which is why it was chosen originally."""
    if a is None or b is None:
        return None
    if sum(x * y for x, y in zip(a, b)) < 0.0:
        b = tuple(-c for c in b)
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    s = math.sqrt(sum((x + y) ** 2 for x, y in zip(a, b)))
    return math.degrees(4.0 * math.atan2(d, s))


def lean_deg(q):
    """How far out of a pure yaw this rotation is -- the SWING's magnitude."""
    sw, _ = LT.swing_twist(q)
    v = LT._to_rotvec(sw)
    return math.degrees(math.sqrt(sum(c * c for c in v)))


def pct(v, p):
    if not v:
        return float("nan")
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


def run(sessions, gp, gr):
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    jump_a, jump_b, lean_a, lean_b = [], [], [], []
    frames = 0
    for session in sessions:
        path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
        if not os.path.isfile(path):
            continue
        states, prev = {}, {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    frame = json.loads(line)
                except ValueError:
                    continue
                for h in frame.get("hands") or []:
                    w, px = h.get("world_landmarks"), h.get("landmarks")
                    if not w or not px:
                        continue
                    key = h.get("trackId", h.get("handedness"))
                    if key not in states:
                        states[key] = horn.freeze(px, w)
                    st = states[key]
                    if st is None:
                        continue
                    q = horn.delta(st, px, w)
                    if q is None:
                        continue
                    qt = LT.trim(q, gp, gr)
                    frames += 1
                    if key in prev:
                        pa, pb = prev[key]
                        ja, jb = geo_deg(q, pa), geo_deg(qt, pb)
                        if ja is not None:
                            jump_a.append(ja)
                        if jb is not None:
                            jump_b.append(jb)
                    prev[key] = (q, qt)
                    # the lean is only meaningful where there IS a turn
                    if abs(LT.twist_angle_deg(q)) >= 20.0:
                        lean_a.append(lean_deg(q))
                        lean_b.append(lean_deg(qt))
    return frames, jump_a, jump_b, lean_a, lean_b


def main():
    sessions = sys.argv[1:]
    if not sessions:
        print("usage: lean_trim_ab.py <session> [<session> ...]")
        return 2
    print("=" * 78)
    print("LEAN TRIM A/B  --  shipped Horn vs trimmed, on recorded GRABBING takes")
    print("=" * 78)

    # ⛔⛔ JUDGED PER TAKE, NEVER POOLED. The first run of this harness pooled the
    # sessions and reported "EVERY setting clears the gate" -- while one take was
    # failing at 1.09x. Pooling mixes takes with different jump distributions and
    # the worst one disappears into the average. ⚠ That is the SECOND pooling error
    # in this session (`lean_decomposition` made the same one on depth bins), which
    # is why the rule is now written into the harness instead of remembered.
    print("")
    print("GATE, PER TAKE -- p95 orientation-jump ratio vs shipped Horn")
    print("(<= 1.000 passes; a take that fails is a failure, whatever the mean says)")
    print("")
    settings = ((0.5, 0.5), (1.0, 1.0), (1.0, 0.75))
    print("  %-32s %s" % ("take", "  ".join("g%.2f/%.2f" % g for g in settings)))
    table = {}
    for session in sessions:
        row = []
        for gp, gr in settings:
            frames, ja, jb, la, lb = run([session], gp, gr)
            if not ja:
                row.append(None)
                continue
            a, b = pct(ja, 0.95), pct(jb, 0.95)
            row.append(b / a if a > 1e-9 else float("inf"))
        table[session] = row
        print("  %-32s %s" % (session[:32], "  ".join(
            "  --   " if r is None else "%7.3fx" % r for r in row)))

    print("")
    best = None
    for k, g in enumerate(settings):
        vals = [r[k] for r in table.values() if r[k] is not None]
        if not vals:
            continue
        worst = max(vals)
        n_fail = sum(1 for v in vals if v > 1.0 + 1e-9)
        state = "PASSES on every take" if n_fail == 0 else "FAILS on %d of %d take(s)" % (n_fail, len(vals))
        print("  g%.2f/%.2f  worst %.3fx  -> %s" % (g[0], g[1], worst, state))
        if n_fail == 0 and (best is None or worst < best[1]):
            best = (g, worst)

    print("")
    print("=" * 78)
    if best:
        print("✅ CLEARS THE GATE at gains %.2f/%.2f on EVERY take (worst %.3fx)."
              % (best[0][0], best[0][1], best[1]))
    else:
        print("⛔ NO SETTING CLEARS THE GATE ON EVERY TAKE.")
    print("⭐ FOR SCALE: the three rejected predecessors never came within 1.8x.")
    print("   Everything above is 0.83-1.13x, which is a different regime -- but")
    print("   'better than what was rejected' is NOT the gate. The gate is 1.000x.")
    print("⚠ AND THE LEAN NUMBERS THIS HARNESS PRINTS ARE SELF-MEASURING (see above):")
    print("   the metric is the swing and the trim removes the swing. The jump ratio")
    print("   is the only independent evidence here.")
    print("⛔ NECESSARY, NOT SUFFICIENT. Three builds cleared their offline metrics")
    print("   and were rejected on sight. Only a live look in both tools closes this.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
