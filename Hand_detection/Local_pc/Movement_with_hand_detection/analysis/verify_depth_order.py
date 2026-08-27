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

    print("\n--- 6. per-landmark and per-segment occlusion ---")
    SQ = [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
    ok("convex_hull of a square is 4 points", len(DO.convex_hull(SQ)) == 4)
    ok("an interior point does not enter the hull",
       len(DO.convex_hull(SQ + [(20.0, 20.0)])) == 4)
    ok("point_in_convex: inside", DO.point_in_convex(SQ, 20.0, 20.0))
    ok("point_in_convex: outside", not DO.point_in_convex(SQ, 5.0, 20.0))
    ok("point_in_convex: a degenerate poly is never inside",
       not DO.point_in_convex([(0.0, 0.0), (1.0, 1.0)], 0.5, 0.5))
    ok("hull winding does not matter",
       DO.point_in_convex(list(reversed(SQ)), 20.0, 20.0))

    occ = [(SQ, 0.50)]
    ok("a NEARER landmark shows through the occluder",
       DO.point_visible(20.0, 20.0, 0.30, occ))
    ok("a FARTHER landmark is hidden", not DO.point_visible(20.0, 20.0, 0.90, occ))
    ok("outside the polygon it is visible at any depth",
       DO.point_visible(5.0, 20.0, 0.90, occ))
    ok("an unknown landmark depth is hidden", not DO.point_visible(20.0, 20.0, None, occ))
    ok("no occluders -> always visible", DO.point_visible(20.0, 20.0, 9.0, []))

    print("\n--- 6b. a bone CROSSING the cube is split, not dropped ---")
    runs = DO.segment_runs((0.0, 20.0), 0.20, (40.0, 20.0), 0.80, occ)
    ok("a crossing bone yields a visible run", len(runs) >= 1, "%d run(s)" % len(runs))
    # ⛔ THE FIRST VERSION OF THIS CHECK ASSERTED THE WRONG THING and failed a
    # correct implementation: it expected the last run to stop short of x=40, but the
    # square only spans x=10..30, so beyond x=30 the bone LEAVES the occluder and is
    # rightly visible again. The property that actually matters is the HOLE in the
    # middle, where the bone is both inside the square and behind it.
    ok("the visible part starts at the NEAR end", abs(runs[0][0][0]) < 1e-9,
       "starts at x=%.2f" % runs[0][0][0])
    ok("the bone is cut into TWO runs with a gap between them", len(runs) == 2,
       "runs %r" % (runs,))
    gap = (runs[0][1][0], runs[1][0][0]) if len(runs) == 2 else (0.0, 0.0)
    ok("the gap is where it is INSIDE the square AND behind it",
       gap[0] >= 19.0 and gap[1] <= 31.0 and gap[1] > gap[0],
       "hidden from x=%.2f to x=%.2f" % gap)
    ok("it is visible again after leaving the square",
       abs(runs[-1][1][0] - 40.0) < 1e-9)
    ok("a wholly-in-front bone is ONE run over its whole length",
       DO.segment_runs((0.0, 20.0), 0.1, (40.0, 20.0), 0.1, occ)
       == [((0.0, 20.0), (40.0, 20.0))])
    ok("a wholly-behind bone crossing the square is broken in TWO",
       len(DO.segment_runs((0.0, 20.0), 0.9, (40.0, 20.0), 0.9, occ)) == 2)
    ok("a bone entirely clear of the square is untouched",
       DO.segment_runs((0.0, 50.0), 0.9, (40.0, 50.0), 0.9, occ)
       == [((0.0, 50.0), (40.0, 50.0))])
    ok("no occluders -> one run, no subdivision cost",
       DO.segment_runs((0.0, 0.0), 1.0, (5.0, 5.0), 2.0, []) == [((0.0, 0.0), (5.0, 5.0))])

    print("\n--- 6c. landmark_depths: built from the hand depth, never guessed ---")
    w = [(0.0, 0.0, -0.03), (0.0, 0.0, 0.02), (0.0, 0.0, 0.0)]
    got = DO.landmark_depths(w, 0.50)
    ok("depth = hand depth + world z",
       all(abs(a - b) < 1e-9 for a, b in zip(got, [0.47, 0.52, 0.50])), "%r" % (got,))
    ok("unknown hand depth -> one None PER LANDMARK, not a bare None",
       DO.landmark_depths(w, None) == [None, None, None])
    ok("empty input -> empty list", DO.landmark_depths([], 0.5) == [])
    ok("a malformed landmark falls back to the hand depth",
       DO.landmark_depths([(0.0, 0.0)], 0.5) == [0.5])

    print("\n--- 7. the port contract (CONSTRAINTS section 2) ---")
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
