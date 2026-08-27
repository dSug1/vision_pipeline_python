# -*- coding: utf-8 -*-
"""⭐⭐ TUNE THE FREEZE TRIGGER — steadiness against jerking on a SLOW legitimate turn.

Owner, 2026-08-27: *"can you finetune those slider values to avoid jerking during
slow rotation of the hand? have a look at the recordings to define which best values
optimize the trade off between steady and jerking during legit movement"*.

⛔ THE SLOW TURN IS THE HARD CASE, and it is the one a speed threshold cannot serve.
A deliberate turn at 50 deg/s is BELOW a release set at 80, so the object stays
frozen, the gap accumulates, and when the speed finally crosses the line the whole
gap is paid back at once. That jump IS the jerking.

⭐ The way out is the owner's own mechanism: a slow REAL turn is highly COHERENT --
every landmark stepping the same way frame after frame -- while noise of the same
magnitude is not. So the release threshold can be lowered to catch slow motion,
with coherence doing the noise rejection that the threshold used to do.

WHAT IS SCORED, on every take that has held frames
────────────────────────────────────────────────────────────────────────────────
    STILL      hand under 40 deg/s    -> fraction of frames the object MOVES  (want 0)
    SLOW       40-120 deg/s           -> fraction it moves                    (want 1)
    FAST       over 150 deg/s         -> fraction it moves                    (want 1)

⚠ SLOW is the column that matters. Any setting can be made to look good on STILL and
FAST alone, and that is exactly how a jerky slow turn gets shipped.

    .venv/Scripts/python.exe analysis/steady_tuning_sweep.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import hand_state as HS                        # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
TAKES = ("2026-08-27_230601_coherence", "2026-08-27_230012_coherence",
         "2026-08-27_224751_freeze", "2026-08-27_223431_steady")
DT = 66.0


def load(session):
    """(speed_deg_s, coherence) per held frame."""
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        return []
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    st = prev_pts = prev_deltas = prev_q = None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            h = r.get("hands") or []
            held = any(c.get("owner") for a in (r.get("cubes") or {}).values()
                       for c in a.values())
            if not held or len(h) != 1:
                st = prev_pts = prev_deltas = prev_q = None
                out.append(None)
                continue
            px, wl = h[0].get("landmarks"), h[0].get("world_landmarks")
            if not px or not wl:
                out.append(None)
                continue
            if st is None:
                st = horn.freeze(px, wl)
                prev_pts, prev_deltas, prev_q = px, None, None
                out.append(None)
                continue
            q = horn.delta(st, px, wl)
            coh, deltas = HS.frobenius_coherence(px, prev_pts, prev_deltas)
            if q is not None and prev_q is not None:
                out.append((PR.quat_angle_deg(prev_q, q) * 1000.0 / DT, coh))
            else:
                out.append(None)
            prev_pts, prev_deltas, prev_q = px, deltas, q
    return out


def score(seqs, release, coh_thr, frames):
    """(still, slow, fast) fractions of frames on which the object MOVES."""
    HS.ROTATION_STEADY_RELEASE_DEG_S = release
    HS.FROBENIUS_THRESHOLD = coh_thr
    HS.ROTATION_STEADY_FREEZE_FRAMES = frames
    n = [0, 0, 0]
    moved = [0, 0, 0]
    for seq in seqs:
        frozen, run = True, 0
        for x in seq:
            if x is None:
                frozen, run = True, 0
                continue
            sp, coh = x
            frozen, run = HS.steady_hold_update(frozen, run, sp, coherence=coh)
            band = 0 if sp < 40.0 else (1 if sp < 120.0 else (2 if sp > 150.0 else None))
            if band is None:
                continue
            n[band] += 1
            if not frozen:
                moved[band] += 1
    return tuple(100.0 * moved[i] / max(1, n[i]) for i in range(3)), n


def main():
    seqs = [s for s in (load(t) for t in TAKES) if s]
    if not seqs:
        print("no takes found")
        return 1

    w = 78
    print("=" * w)
    print("  FREEZE TRIGGER TUNING -- steadiness vs jerking on a SLOW turn")
    print("=" * w)
    print("  object MOVES on what fraction of frames, by how fast the hand is going:")
    print("    STILL <40 deg/s (want 0%)   SLOW 40-120 (want 100%)   FAST >150 (want 100%)")
    print("  \u26a0 SLOW is the column that matters -- it is where the jerking lives.")
    print()
    print("  %-26s %9s %9s %9s   %s" % ("release / coherence / N", "STILL", "SLOW", "FAST", "verdict"))
    print("  " + "-" * (w - 4))

    best = None
    for frames in (1, 2):
        for rel in (30.0, 40.0, 50.0, 60.0, 80.0):
            for coh in (None, -0.2, 0.0, 0.3):
                (st, sl, fa), n = score(seqs, rel, coh, frames)
                # \u2b50 the objective states the trade-off explicitly rather than ranking
                # on one column: stillness matters, but a frozen SLOW turn is the
                # defect being fixed, so it is weighted hardest.
                cost = st * 1.0 + (100.0 - sl) * 1.5 + (100.0 - fa) * 0.5
                if best is None or cost < best[0]:
                    best = (cost, rel, coh, frames, st, sl, fa)
                if coh in (None, 0.0) and rel in (30.0, 50.0, 80.0):
                    print("  rel %3.0f  frob %-5s N=%d      %8.1f%% %8.1f%% %8.1f%%"
                          % (rel, coh, frames, st, sl, fa))
    print("  " + "-" * (w - 4))
    print("  sample sizes: still %d, slow %d, fast %d frames" % tuple(n))
    print()
    print("=" * w)
    _c, rel, coh, fr, st, sl, fa = best
    print("  \u2b50 BEST TRADE-OFF: RELEASE %.0f   FROB %-5s   FREEZE %d" % (rel, coh, fr))
    print("     still %.1f%%   slow %.1f%%   fast %.1f%%" % (st, sl, fa))
    print("  \u26a0 The objective weights a frozen SLOW turn 1.5x a false release when")
    print("     still, because the jerking is the defect being fixed. Change the")
    print("     weights and the winner can change -- they are a judgement, not a fact.")
    print("=" * w)
    HS.ROTATION_STEADY_RELEASE_DEG_S = 80.0
    HS.FROBENIUS_THRESHOLD = None
    HS.ROTATION_STEADY_FREEZE_FRAMES = 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
