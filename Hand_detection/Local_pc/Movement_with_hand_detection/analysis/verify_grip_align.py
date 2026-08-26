"""GOLDEN VECTORS for `A1`'s grip re-alignment — the walk that hides in a movement.

> **Owner, 2026-08-26:** *"It's like running to catch a train, but if the train
> stops, you also stop running."*

`CONSTRAINTS` §3: the fixture lands with the logic, not after. Each check below is
a property the design would be WRONG without, and three of them are things the two
earlier versions of this code actually got wrong.

    .venv/Scripts/python.exe analysis/verify_grip_align.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import fingertips as FT                         # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # pragma: no cover
    pass

_fails = []

# ⛔ PIN the tunables these vectors reason about. They are slider-driven in the
# rig, and a fixture that inherits a live value asserts something different every
# time the owner moves a slider -- which is not a fixture.
FT.GRIP_ALIGN_MASK_RATIO = 1.0
FT.GRIP_ALIGN_MOVING_PX_S = 40.0


def check(name, ok, detail=""):
    print("  [%s] %-56s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        _fails.append(name)


def walk(hand_step, dt=50.0, offset=(50.0, 0.0), budget=250.0, frames=60):
    """Run the walk and return (remaining_px, frames_used, worst_cube_step_px)."""
    off, rem = offset, budget
    prev = math.hypot(*offset)
    worst = 0.0
    used = 0
    for _ in range(frames):
        off, _dz, rem = FT.decay_grip_offset(off, 0.0, rem, dt, hand_step)
        d = math.hypot(*off)
        worst = max(worst, prev - d)
        prev = d
        used += 1
        if d <= 1e-9:
            break
    return math.hypot(*off), used, worst


print("=" * 80)
print("A1 grip re-alignment — the walk")
print("=" * 80)

# ⛔ THE ONE THAT DEFINES THE FEATURE. A cube that drifts while the hand is still
# reads as the software misbehaving; it is the whole reason this is not a plain
# time fade.
left, _, worst = walk(0.0)
check("hand STILL -> the cube does not move AT ALL", left == 50.0 and worst == 0.0,
      "%.1f px still owed" % left)

# ⛔ The first implementation failed exactly here: a moving-TIME budget let the
# cube retire 50 px while a creeping hand travelled 11.
_, frames, worst = walk(2.0)
check("hand CREEPING -> the cube never out-walks the hand", worst <= 2.0 + 1e-9,
      "cube %.2f px/frame vs hand 2.00" % worst)
check("...and the budget becomes a FLOOR, not a deadline", frames > 5,
      "%d frames (%.0f ms) against a 250 ms budget" % (frames, frames * 50.0))

# with real motion the time budget is what binds, and it binds exactly
left, frames, _ = walk(10.0)
check("hand MOVING -> the span is walked in the budgeted moving time",
      left <= 1e-9 and frames == 5, "%d frames x 50 ms = %.0f ms" % (frames, frames * 50.0))

left, frames, _ = walk(30.0)
check("...and a FASTER hand does not finish sooner than the budget",
      frames == 5, "%d frames" % frames)

# the train stopping mid-run must PAUSE, not reset and not leak
off, rem = (50.0, 0.0), 250.0
off, _dz, rem = FT.decay_grip_offset(off, 0.0, rem, 50.0, 10.0)
mid, mid_rem = math.hypot(*off), rem
for _ in range(20):
    off, _dz, rem = FT.decay_grip_offset(off, 0.0, rem, 50.0, 0.0)
check("a stop mid-walk FREEZES it (no leak, no reset)",
      abs(math.hypot(*off) - mid) < 1e-12 and abs(rem - mid_rem) < 1e-12,
      "%.4f px held over 20 still frames" % math.hypot(*off))
off, _dz, rem = FT.decay_grip_offset(off, 0.0, rem, 50.0, 10.0)
check("...and it RESUMES where it stopped", math.hypot(*off) < mid - 1.0,
      "%.1f -> %.1f px" % (mid, math.hypot(*off)))

# ⚠ the slider's left end is the teleport the acceptance gate rejected; it must be
# reachable and it must mean exactly that
off, _dz, rem = FT.decay_grip_offset((50.0, 0.0), 0.0, 0.0, 50.0, 10.0)
check("a ZERO budget is the teleport (the slider's own left end)",
      off == (0.0, 0.0) and rem == 0.0)

# degenerate inputs must hold the offset, never fabricate motion
for name, args in (("no dt", ((50.0, 0.0), 0.0, 250.0, None, 10.0)),
                   ("no hand step", ((50.0, 0.0), 0.0, 250.0, 50.0, None)),
                   ("backwards clock", ((50.0, 0.0), 0.0, 250.0, -5.0, 10.0))):
    o, _dz, r = FT.decay_grip_offset(*args)
    check("%-14s -> holds, does not move the cube" % name,
          o == (50.0, 0.0) and r == 250.0)

check("an absent offset is passed through untouched",
      FT.decay_grip_offset(None, 0.0, 250.0, 50.0, 10.0) == (None, 0.0, 250.0))

# ⭐⭐ the depth offset must ride the SAME progress -- landing x/y first and then
# sliding the object in Z on its own is the artefact this whole design prevents.
o, dz, r = FT.decay_grip_offset((50.0, 0.0), 0.10, 300.0, 50.0, 10.0)
check("the DEPTH offset walks in lockstep with the in-plane one",
      abs(dz / 0.10 - math.hypot(*o) / 50.0) < 1e-12,
      "z %.1f%% vs xy %.1f%% retired" % (100 * (1 - dz / 0.10),
                                         100 * (1 - math.hypot(*o) / 50.0)))
o, dz, r = FT.decay_grip_offset((0.0, 0.0), 0.10, 300.0, 50.0, 10.0)
check("...and a DEAD-CENTRE grab still retires its depth", dz < 0.10,
      "%.4f m left of 0.10" % dz)

print("=" * 80)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — the cube runs only while the train is moving.")
