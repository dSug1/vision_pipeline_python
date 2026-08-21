"""Golden vectors for `Resources/hand_ownership.py` (queue T3).

⭐ THE LOAD-BEARING TEST IS §3, THE GUARD. A transfer moves a held cube from one
hand to the other, so the failure mode of this module is not "a cube drops" -- it
is **a cube is taken from the hand holding it and given to a different hand**,
which is N8 cube-stealing arriving through a new door. The guard (never transfer
when the other slot already held a tracked hand) is the only thing standing
between this row and that, and the measurement shows it blocking 84 of 141
candidates -- more than it allows.

§2 pins the measured threshold. It is 0.5 palm widths because the candidate
displacement cluster ends there (median 0.11, 86% inside 0.5, only 3 of 57
between 0.5 and 1.0) -- not because 0.5 catches a satisfying number of events.

⚠ Do not edit the expectations to match a port. The port is wrong, not this.

    .venv/Scripts/python.exe analysis/verify_hand_ownership.py
"""
import io
import os
import sys
import tokenize

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def executable_source(path):
    """A module's code with every string literal and comment removed.

    ⚠ Written with `tokenize` rather than by slicing off the leading docstring,
    because the first version of this check did the latter and promptly failed on
    the phrase "transfer time." inside a CLASS docstring. A port-contract scan
    that trips over its own prose teaches the reader to ignore it."""
    with open(path, encoding="utf-8") as fh:
        toks = list(tokenize.generate_tokens(fh.readline))
    return " ".join(t.string for t in toks
                    if t.type not in (tokenize.STRING, tokenize.COMMENT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_ownership as HO

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


WIDTH = 100.0          # palm width in px, so 0.5 palm widths == 50 px
HERE = (300.0, 200.0)


def at(dx, dy=0.0):
    return (HERE[0] + dx, HERE[1] + dy)


print("=" * 78)
print("GOLDEN VECTORS -- Resources/hand_ownership.py (T3)")
print("=" * 78)

print("\n1. THE BASIC CLAIM -- a hand that barely moved is the same hand")
check("0 px away transfers", HO.should_transfer(HERE, WIDTH, at(0), False))
check("11 px (the measured MEDIAN, 0.11 pw) transfers",
      HO.should_transfer(HERE, WIDTH, at(11.0), False))
check("far away does not", HO.should_transfer(HERE, WIDTH, at(400.0), False) is False)

print("\n2. THE MEASURED THRESHOLD -- 0.5 palm widths, and it is a boundary")
check("shipped threshold is 0.5 palm widths", HO.TRANSFER_PALM_WIDTHS == 0.5,
      repr(HO.TRANSFER_PALM_WIDTHS))
check("exactly 0.5 pw transfers (boundary inclusive)",
      HO.should_transfer(HERE, WIDTH, at(50.0), False))
check("just past it does not", HO.should_transfer(HERE, WIDTH, at(50.001), False) is False)
check("distance is EUCLIDEAN, not per-axis",
      HO.should_transfer(HERE, WIDTH, at(40.0, 30.0), False)          # 50 px exactly
      and HO.should_transfer(HERE, WIDTH, at(40.0, 31.0), False) is False)
# Scale-free: the same physical displacement at a different distance from the
# camera must give the same answer. A pixel threshold would not.
check("⭐ scale-free -- half the palm width, half the pixels, same verdict",
      HO.should_transfer(HERE, 50.0, at(25.0), False)
      and HO.should_transfer(HERE, 50.0, at(25.001), False) is False)

print("\n3. ⭐ THE GUARD -- a busy other slot NEVER transfers")
check("busy slot blocks even a perfect positional match",
      HO.should_transfer(HERE, WIDTH, at(0.0), True) is False)
check("busy slot blocks at the median displacement too",
      HO.should_transfer(HERE, WIDTH, at(11.0), True) is False)
print("     ⚠ Two real hands. Moving a cube between them is theft, not repair --")
print("       it would be N8 cube-stealing arriving through a new door.")

print("\n4. ABSENCE OF EVIDENCE IS NOT EVIDENCE -- every degenerate input is False")
check("no last-seen centre", HO.should_transfer(None, WIDTH, at(0), False) is False)
check("no other centre", HO.should_transfer(HERE, WIDTH, None, False) is False)
check("no palm width", HO.should_transfer(HERE, None, at(0), False) is False)
check("zero palm width", HO.should_transfer(HERE, 0.0, at(0), False) is False)
check("negative palm width", HO.should_transfer(HERE, -100.0, at(0), False) is False)
check("zero threshold disables transfers entirely",
      HO.should_transfer(HERE, WIDTH, at(0), False, threshold=0.0) is False)

print("\n5. LastSeen -- and the ordering trap the guard depends on")
s = HO.LastSeen()
check("starts empty", s.centre is None and s.palm_width is None and s.other_busy is False)
s.record(HERE, WIDTH, True)
check("records", s.centre == HERE and s.palm_width == WIDTH and s.other_busy is True)
check("  other_busy is coerced to bool", isinstance(s.other_busy, bool))
s.record(HERE, WIDTH, 0)
check("  falsy other_busy becomes False", s.other_busy is False)
s.clear()
check("clear() empties it", s.centre is None and s.other_busy is False)
print("     ⚠ `other_busy` must be recorded when the hand was LAST SEEN, never")
print("       read at transfer time: by then the other slot is occupied by")
print("       definition, so a late read makes the guard always true and")
print("       silently disables it.")

print("\n6. OTHER_HAND is an involution")
check("Left <-> Right", HO.OTHER_HAND["Left"] == "Right" and HO.OTHER_HAND["Right"] == "Left")
check("applying it twice is identity",
      all(HO.OTHER_HAND[HO.OTHER_HAND[h]] == h for h in ("Left", "Right")))

print("\n7. PORT CONTRACT -- stdlib only, no side effects")
code = executable_source(os.path.join(BASE, "Resources", "hand_ownership.py"))
check("imports nothing", "import " not in code)
for banned in ("math.", "numpy", "random", "time."):
    check(f"no `{banned}`", banned not in code)

print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
