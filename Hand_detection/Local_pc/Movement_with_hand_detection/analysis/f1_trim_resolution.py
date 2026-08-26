"""⭐⭐ §10.1 — TRIM RESOLUTION. Does `F1`'s fine channel actually resolve anything?

The `A10` bar measures GROSS sweep fidelity: yaw axis, lean, pitch, roll, jitter
over big hand rotations. `F1` was built to buy FINE alignment. ⛔ So it can pass
every one of those and still deliver nothing it exists for. This is the metric
that separates them, and it was the last outstanding acceptance gate.

Take: `tools/RecordTrimResolution.py` — per declared angle, a REFERENCE state
(fingers neutral) and a TARGET state (fingers rotated by the angle the operator
DECLARED beforehand), both with the wrist held still.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE OWNER'S CAVEAT, AND WHY THE METRIC IS BUILT AROUND IT

**Owner, 2026-08-26:** *"the angles are approximative, and the palm anyway rotates
slightly as it is impossible to rotate the fingers without slightly rotating the
palm."*

⚠ Both halves are real, and a naive metric would be destroyed by the second one.
If the object turns 8° when the fingers move, the PALM having turned 2° means the
gross channel already supplied a quarter of it — and a "fine channel gain" that
silently includes the palm's own contribution measures the wrong thing.

⭐ THE ANSWER IS A SAME-TAKE A/B, NOT A CORRECTION. The identical frames are
replayed twice, with `TRIM_GAIN` at 1.0 and at 0.0:

    OFF  the object follows the palm exactly -- shipped Horn, today's pipeline
    ON   the object follows the palm PLUS the fingertip trim

    FINE CHANNEL  =  ON − OFF

The palm's motion is present in both and cancels **by construction**. Whatever
survives the subtraction is the trim's own contribution and nothing else — so the
caveat cannot reach it. ⭐ The declared angle stays approximate, which is why the
gain is reported as a ratio to it and read as an order of magnitude, never to
three decimals.

⚠ The rotation the operator performed was about the ROLL axis (palm vertical and
facing the camera, no finger yaw or pitch), so this take scores the roll channel.
Yaw and pitch of the fingers are a separate take.

────────────────────────────────────────────────────────────────────────────────
WHAT EACH NUMBER DECIDES

  GAIN      fine-channel rotation / declared angle. ⇒ near 0 means the trim is
            decoration; near 1 means the object follows the fingers.
  JITTER    p95 frame-to-frame object rotation while a state is HELD, ON vs OFF.
            ⇒ what the trim costs in stillness, which is the axis on which the
              9-point fit was killed (`A10`'s jitter p95 25.41).
  RESOLUTION amplitude / jitter. ⇒ the number of distinguishable steps the fine
            channel actually offers. Below ~1 the correction is buried in its own
            noise and cannot be aimed.

⚠ The composition below reproduces production's two-line expression
(`HandsTriggeredActions` ~L1797: `q_eff = hand · trim`, then
`delta = q_eff · conj(q_eff_at_grab)`). The COMPONENTS are the shipped ones --
`palm_rotation.Horn` and `tip_trim.TipTrim` -- so only the two-line composition is
restated here, deliberately and visibly.

    .venv/Scripts/python.exe analysis/f1_trim_resolution.py [session]
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_rotation as PR                     # noqa: E402
from Resources import tip_trim                                # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                             # pragma: no cover
    pass

CAPTURE = (r"E:\Python\Recordings for vision_pipeline"
           r"\Recordings_perception_layer\sessions")
IDENT = (1.0, 0.0, 0.0, 0.0)


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def qang(a, b):
    d = abs(sum(x * y for x, y in zip(a, b)))
    return 2.0 * math.degrees(math.acos(max(-1.0, min(1.0, d))))


def axis_of(q):
    w, x, y, z = q if q[0] >= 0 else tuple(-c for c in q)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    return None if s < 1e-9 else (x / s, y / s, z / s)


def pct(xs, p):
    xs = sorted(xs)
    return xs[int(p * (len(xs) - 1))] if xs else float("nan")


def latest_session():
    c = sorted(d for d in os.listdir(CAPTURE) if "trim_resolution" in d)
    return c[-1] if c else None


def run(session):
    root = os.path.join(CAPTURE, session)
    meta = json.load(open(os.path.join(root, "meta.json"), encoding="utf-8"))
    rows = []
    with open(os.path.join(root, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    by = {}
    for r in rows:
        if not r.get("wrist_still"):
            continue                       # the gate the take was recorded under
        hs = r.get("hands") or []
        if len(hs) != 1:
            continue
        by.setdefault((r["angle_index"], r["phase"]), []).append(r)

    w = 88
    print("=" * w)
    print("  §10.1  TRIM RESOLUTION -- does F1's fine channel resolve anything?")
    print("=" * w)
    print("  take   : %s" % session)
    print("  hand   : %s (declared)   angles: %s deg (declared, APPROXIMATE)"
          % (meta.get("known_hand"), meta.get("declared_angles_deg")))
    print("  ⭐ fine channel = (trim ON) − (trim OFF) on the SAME frames, so the")
    print("     palm's own motion cancels by construction and the owner's caveat")
    print("     -- 'the palm rotates slightly' -- cannot reach the result.")
    print("  ⚠ rotation performed about the ROLL axis; yaw/pitch are another take.")
    print()

    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    print("  %-8s %10s %10s %10s %9s %9s %9s"
          % ("declared", "PALM", "obj OFF", "obj ON", "FINE", "gain", "resol"))
    print("  " + "-" * (w - 4))

    summary = []
    for ai, ang in enumerate(meta.get("declared_angles_deg", [])):
        ref, tgt = by.get((ai, "reference")), by.get((ai, "target"))
        if not ref or not tgt:
            print("  %-8.0f  (missing state)" % ang)
            continue

        # ⭐ The reference is frozen on the REFERENCE state, exactly as a grab
        # freezes it, and both arms share that one freeze -- so ON and OFF differ
        # in the trim and in nothing else.
        r0 = ref[len(ref) // 2]
        lm0, wl0 = r0["hands"][0]["landmarks"], r0["hands"][0]["world_landmarks"]
        rs = horn.freeze(lm0, wl0)
        if rs is None:
            print("  %-8.0f  (no palm fit at the reference)" % ang)
            continue

        def q_eff_seq(frames, gain):
            trim = tip_trim.TipTrim()
            trim.freeze(wl0, IDENT)
            out = []
            for fr in frames:
                lm = fr["hands"][0]["landmarks"]
                wl = fr["hands"][0]["world_landmarks"]
                d = horn.delta(rs, lm, wl)
                hq = IDENT if d is None else d
                tq = trim.update(wl, hq, tip_trim.palm_span_m(wl),
                                 fr["tCapture"], gain=gain)
                out.append(hq if tq is tip_trim.IDENTITY else qmul(hq, tq))
            return out

        ref_off, tgt_off = q_eff_seq(ref, 0.0), q_eff_seq(tgt, 0.0)
        ref_on, tgt_on = q_eff_seq(ref, 1.0), q_eff_seq(tgt, 1.0)

        def med_q(seq):
            # the element closest to all the others -- a median in rotation space
            return min(seq, key=lambda q: sum(qang(q, o) for o in seq))

        # object rotation from REFERENCE to TARGET, each arm against its OWN base
        off_rot = qang(med_q(ref_off), med_q(tgt_off))
        on_rot = qang(med_q(ref_on), med_q(tgt_on))
        # ⭐ the fine channel: the trim's own contribution at the target pose
        fine_q = qmul(med_q(tgt_on), qconj(med_q(tgt_off)))
        fine = qang(IDENT, fine_q)

        def jitter(seq):
            return pct([qang(seq[i - 1], seq[i]) for i in range(1, len(seq))], 0.95)

        j_off = max(jitter(ref_off), jitter(tgt_off))
        j_on = max(jitter(ref_on), jitter(tgt_on))
        resol = fine / j_on if j_on > 1e-9 else float("nan")

        print("  %-8.0f %9.2f° %9.2f° %9.2f° %8.2f° %9.2f %9.2f"
              % (ang, off_rot, off_rot, on_rot, fine, fine / ang if ang else float("nan"),
                 resol))
        summary.append({"declared": ang, "palm": off_rot, "on": on_rot, "fine": fine,
                        "gain": fine / ang if ang else float("nan"),
                        "j_off": j_off, "j_on": j_on, "resol": resol,
                        "axis": axis_of(fine_q)})

    if not summary:
        print("\n  nothing measurable in this take.")
        return 1

    print()
    print("  JITTER while HELD (p95 frame-to-frame object rotation)")
    print("  %-8s %14s %14s %12s" % ("declared", "trim OFF", "trim ON", "cost"))
    for s in summary:
        print("  %-8.0f %13.3f° %13.3f° %11.3f°"
              % (s["declared"], s["j_off"], s["j_on"], s["j_on"] - s["j_off"]))

    print()
    print("  FINE-CHANNEL AXIS (the operator rotated about ROLL)")
    for s in summary:
        a = s["axis"]
        print("  %-8.0f %s" % (s["declared"],
                               "degenerate" if a is None else
                               "x %+.2f  y %+.2f  z %+.2f" % a))

    print()
    print("=" * w)
    gains = [s["gain"] for s in summary if s["gain"] == s["gain"]]
    res = [s["resol"] for s in summary if s["resol"] == s["resol"]]
    cost = [s["j_on"] - s["j_off"] for s in summary]
    print("  VERDICT")
    print("    fine-channel gain     : %.2f – %.2f  (of the declared angle)"
          % (min(gains), max(gains)))
    print("    usable resolution     : %.1f – %.1f  (amplitude / its own jitter)"
          % (min(res), max(res)))
    print("    jitter cost of ON     : %+.3f° – %+.3f° p95" % (min(cost), max(cost)))
    print()
    # ⛔⛔ THE CHECK THIS FILE WAS MISSING ON ITS FIRST RUN, AND THE ONE THAT
    # MATTERS MOST. "Resolution" is not amplitude-over-noise if the amplitude is a
    # CONSTANT: a channel pinned at its clamp contributes the same rotation however
    # far the fingers move, so it cannot be AIMED, only switched on. Amplitude vs
    # jitter would score that as excellent, which is exactly backwards.
    fines = [s["fine"] for s in summary]
    spread = max(fines) - min(fines)
    at_clamp = (abs(sum(fines) / len(fines) - tip_trim.TRIM_MAX_DEG) < 0.5
                and spread < 0.5)
    if at_clamp:
        print("    ⛔⛔ THE FINE CHANNEL IS SATURATED AT ITS CLAMP.")
        print("       It contributed %.2f°, %.2f°, %.2f° for declared %s° --"
              % (fines[0], fines[1] if len(fines) > 1 else float('nan'),
                 fines[2] if len(fines) > 2 else float('nan'),
                 "/".join("%.0f" % s["declared"] for s in summary)))
        print("       the SAME rotation regardless of how far the fingers moved,")
        print("       and equal to `tip_trim.TRIM_MAX_DEG` = %.1f°."
              % tip_trim.TRIM_MAX_DEG)
        print("       ⇒ It is a fixed OFFSET, not a proportional fine control. The")
        print("         apparent 'gain' of %.2f at the smallest angle is arithmetic:"
              % max(gains))
        print("         the declared angle happened to equal the clamp.")
        print("       ⇒ `RESOLUTION` above is therefore MEANINGLESS as controllability.")
    elif max(gains) < 0.05:
        print("    ⛔ THE FINE CHANNEL IS DECORATION. The trim moves the object by")
        print("       under 5% of the declared finger rotation.")
    elif max(res) < 1.0:
        print("    ⛔ THE CORRECTION IS BURIED IN ITS OWN NOISE -- amplitude below")
        print("       the jitter it introduces, so it cannot be aimed.")
    else:
        print("    ✅ The fine channel moves the object measurably and above its own")
        print("       noise floor. ⚠ The declared angles are approximate: read the")
        print("       gain as an order of magnitude, not to two decimals.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else latest_session()
    if not s:
        print("no trim_resolution take found")
        sys.exit(1)
    sys.exit(run(s))
