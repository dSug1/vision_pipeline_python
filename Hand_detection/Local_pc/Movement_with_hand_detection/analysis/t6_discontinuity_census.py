# -*- coding: utf-8 -*-
"""⛔⛔ T6 — WHY THE AXIS CORRECTION FEELS DISCONTINUOUS. The owner's verdict, sourced.

Owner, 2026-08-27, on `--slant-rig` take 2: *"the feel is very bad. there is no
consistency in the rotation axis, discontinuities everywhere"*.

⛔ THE MEASUREMENT THAT SHIPPED IT WAS THE WRONG ONE. `t6_axis_correction_ab.py`
scored per-frame axis WANDER on the instructed SWEEPS -- a hand turning smoothly
through a single axis, which is the one motion that cannot expose a gate chattering.
It read 19.8 -> 19.6 p95 and I called that "no jitter cost". On a real GRAB it is
not the same question, and the corpus never contained one: every `T6` take is an
OPEN hand, and the game grips. That gap was named out loud before the wiring and
then not closed.

⭐ THIS FILE ATTRIBUTES THE FELT DEFECT TO A MECHANISM, on the owner's own frames.
Four suspects, all of them things I built:

  1. BRANCH GATE      hard switch on the palm/back sign. Correction goes 100% -> 0%
                      in ONE frame. Near palm-edge-on that sign chatters.
  2. EDGE-ON GATE     hard switch on `edge_on_measure < 0.15`. Same step, and the
                      measure is noisiest exactly at its own threshold.
  3. TILT NOISE       \u00a71.3(a) of the strategy spec WARNED that the tilt DIRECTION is
                      undefined as sigma -> 1. The authority fade damps how much of
                      it is used; it does nothing about the target ANGLE jumping.
  4. GRIP DEFORMATION the canonical is frozen on an OPEN hand at grab. Closing the
                      fingers moves the palm quad for reasons that are not rotation.

    .venv/Scripts/python.exe analysis/t6_discontinuity_census.py [session]
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry as PG                     # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402
from Resources import palm_slant as PS                        # noqa: E402
from Resources import palm_slant_axis as SA                   # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
DEFAULT = "2026-08-27_174418_slant_rig"
GAIN = 0.75                       # what the take actually ran, per its meta.json


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else float("nan")


def med(xs):
    return pct(xs, 0.5)


def load(session):
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
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
                out.append(None)               # a gap is data: it breaks continuity
                continue
            h = hands[0]
            if h.get("landmarks") and h.get("world_landmarks"):
                out.append((h["landmarks"], h["world_landmarks"]))
            else:
                out.append(None)
    return out


def axis_deg(q):
    if q is None or math.hypot(q[1], q[2]) < 1e-9:
        return None
    return math.degrees(math.atan2(q[2], q[1])) % 180.0


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    frames = load(session)
    if not frames:
        print("session not found: %s" % session)
        return 1

    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    est = SA.SlantAxisHorn(gain=GAIN)

    # \u26a0 A real session is many grabs. Re-freeze whenever the hand comes back, which
    # is what the game does -- scoring one endless grab would flatter both arms by
    # hiding every re-acquisition.
    st_h = st_e = None
    prev_h = prev_e = None
    jump_h, jump_e = [], []
    gate_steps, branch_flips, edge_flips = [], 0, 0
    prev_gate = None
    sig_step, tilt_step = [], []
    prev_sig = prev_tilt = None
    grabs = 0

    for fr in frames:
        if fr is None:
            st_h = st_e = None
            prev_h = prev_e = prev_sig = prev_tilt = prev_gate = None
            continue
        px, wl = fr
        if st_h is None:
            st_h, st_e = horn.freeze(px, wl), est.freeze(px, wl)
            grabs += 1
            continue
        qh, qe = horn.delta(st_h, px, wl), est.delta(st_e, px, wl)
        ah, ae = axis_deg(qh), axis_deg(qe)

        # which gate, if any, is suppressing the correction THIS frame
        sa = PG.signed_palm_area(px)
        eo = PG.edge_on_measure(px)
        on_branch = not (st_e and st_e.get("sign0") is not None and sa is not None
                         and (sa > 0.0) != st_e["sign0"])
        gate = "branch" if not on_branch else ("edge" if eo < SA.EDGE_FADE_ZERO else "on")
        if prev_gate is not None and gate != prev_gate:
            if "branch" in (gate, prev_gate):
                branch_flips += 1
            if "edge" in (gate, prev_gate):
                edge_flips += 1
            if ah is not None and ae is not None:
                # \u2b50 THE STEP THE HAND FEELS: how far the corrected axis sits from the
                # uncorrected one at the instant the gate toggles. The correction is
                # switched on or off WHOLE, so this is the size of the jolt.
                gate_steps.append(PS.tilt_delta(ae, ah))
        prev_gate = gate

        if ah is not None and prev_h is not None:
            jump_h.append(PS.tilt_delta(ah, prev_h))
        if ae is not None and prev_e is not None:
            jump_e.append(PS.tilt_delta(ae, prev_e))
        prev_h, prev_e = ah, ae

        tr = st_e.get("slant") if st_e else None
        sg = tr.last_sigma if tr else None
        tl = tr.last_tilt if tr else None
        if prev_sig is not None and sg is not None:
            sig_step.append(abs(sg - prev_sig))
        if prev_tilt is not None and tl is not None:
            tilt_step.append(PS.tilt_delta(tl, prev_tilt))
        prev_sig, prev_tilt = sg, tl

    w = 88
    print("=" * w)
    print("  T6 -- DISCONTINUITY CENSUS   %s" % session)
    print("=" * w)
    print("  frames %d   grab segments %d   correction gain %.2f" % (len(frames), grabs, GAIN))
    print()
    print("  \u2b50 PER-FRAME AXIS JUMP -- what 'no consistency' measures")
    print("     %-26s med %5.2f   p95 %6.2f   max %6.2f deg"
          % ("HORN (what ships)", med(jump_h), pct(jump_h, 0.95), pct(jump_h, 1.0)))
    print("     %-26s med %5.2f   p95 %6.2f   max %6.2f deg"
          % ("SLANT-AXIS (panel 2)", med(jump_e), pct(jump_e, 0.95), pct(jump_e, 1.0)))
    if jump_h and jump_e:
        r95 = pct(jump_e, 0.95) / pct(jump_h, 0.95) if pct(jump_h, 0.95) > 1e-9 else float("inf")
        print("     \u2192 the correction multiplies the p95 frame-to-frame jump by %.2fx" % r95)
    print()
    print("  \u26d4 SUSPECT 1+2 -- THE HARD GATES")
    print("     branch-gate toggles : %4d      edge-gate toggles : %4d" % (branch_flips, edge_flips))
    if gate_steps:
        print("     jolt when a gate toggles: med %.1f  p95 %.1f  max %.1f deg"
              % (med(gate_steps), pct(gate_steps, 0.95), pct(gate_steps, 1.0)))
        print("     \u2192 each toggle switches the correction on or off WHOLE, so that")
        print("       is the size of the step the hand feels, %d times in this take."
              % (branch_flips + edge_flips))
    print()
    print("  \u26d4 SUSPECT 3+4 -- THE SIGNAL ITSELF, frame to frame")
    print("     sigma step : med %.4f  p95 %.4f      (a steady hand should be ~0)"
          % (med(sig_step), pct(sig_step, 0.95)))
    print("     TILT step  : med %5.2f  p95 %6.2f deg   \u2190 the steered target"
          % (med(tilt_step), pct(tilt_step, 0.95)))
    print("     \u2192 the authority fade damps HOW MUCH of the tilt is used. It does")
    print("       nothing about the tilt ANGLE itself moving, and the strategy spec")
    print("       \u00a71.3(a) warned the direction is undefined as sigma \u2192 1.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
