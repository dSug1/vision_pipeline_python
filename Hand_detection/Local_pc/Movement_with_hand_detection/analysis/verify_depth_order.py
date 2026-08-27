# -*- coding: utf-8 -*-
"""Golden vectors for `Resources/depth_order.py` — the game's one occlusion rule.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_depth_order.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import depth_order as DO                       # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []


def ok(name, cond, detail=""):
    print("  [%s] %-58s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


def main():
    print("=" * 78)
    print("Golden vectors -- depth_order")
    print("=" * 78)

    print("\n--- 1. farthest first, and SMALLER METRES IS NEARER ---")
    ok("plain ordering", DO.order([(0.5, "near"), (2.0, "far"), (1.0, "mid")])
       == ["far", "mid", "near"])
    ok("a single item is returned as-is", DO.order([(0.5, "x")]) == ["x"])
    ok("an empty list is empty", DO.order([]) == [])

    print("\n--- 2. ⛔ UNKNOWN DEPTH SORTS FARTHEST (it may not claim to be in front) ---")
    ok("None goes to the back", DO.order([(0.5, "known"), (None, "unknown")])
       == ["unknown", "known"])
    ok("NaN goes to the back too",
       DO.order([(0.5, "known"), (float("nan"), "nan")]) == ["nan", "known"])
    ok("two unknowns keep the caller's order",
       DO.order([(None, "a"), (None, "b")]) == ["a", "b"])
    ok("unknown sorts behind even a very distant known object",
       DO.order([(1000.0, "far"), (None, "unknown")]) == ["unknown", "far"])

    print("\n--- 3. ⚠ STABILITY -- equal depths must not swap (that flickers) ---")
    same = [(0.5, "a"), (0.5, "b"), (0.5, "c")]
    ok("equal depths keep the supplied order", DO.order(same) == ["a", "b", "c"])
    ok("stable across repeated calls",
       all(DO.order(same) == ["a", "b", "c"] for _ in range(50)))
    ok("stable when equal depths are interleaved with others",
       DO.order([(0.5, "a"), (2.0, "far"), (0.5, "b")]) == ["far", "a", "b"])

    print("\n--- 4. occludes(): the same rule, stated for a direct caller ---")
    ok("nearer occludes farther", DO.occludes(0.4, 0.9))
    ok("farther does not occlude nearer", not DO.occludes(0.9, 0.4))
    ok("equal depths do not occlude", not DO.occludes(0.5, 0.5))
    ok("an unknown occludes nothing", not DO.occludes(None, 0.5))
    ok("...but a known DOES occlude an unknown", DO.occludes(0.5, None))
    ok("NaN behaves as unknown", not DO.occludes(float("nan"), 0.5))

    print("\n--- 5. it agrees with itself ---")
    # ⭐ The two entry points must never disagree: if `occludes(a, b)` is true then
    # `order` must place b before a. A renderer mixing both would tear otherwise.
    cases = [(0.2, 0.7), (1.5, 0.3), (None, 0.4), (0.4, None), (0.5, 0.5)]
    good = True
    for a, b in cases:
        seq = DO.order([(a, "A"), (b, "B")])
        if DO.occludes(a, b) and seq.index("A") < seq.index("B"):
            good = False
    ok("occludes() and order() never contradict", good)

    print("\n--- 6. the port contract (CONSTRAINTS section 2) ---")
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "Resources", "depth_order.py"), encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for bad in ("import numpy", "import time", "time.", "perf_counter", "datetime", "random"):
        ok("no %-16s (clock-free, numpy-free)" % bad, bad not in body)

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
