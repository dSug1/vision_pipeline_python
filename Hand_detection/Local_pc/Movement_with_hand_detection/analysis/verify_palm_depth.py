"""Golden vectors for `Resources/palm_depth.py` (M9 / queue item 4.1).

⭐ Written BEFORE the web/mobile port exists, not after — the U3 discipline. The
precedent is not ceremony: the very first run of `verify_frame_rate_estimator.py`
caught a real bug (Python's banker's rounding vs JavaScript's `Math.round`), and
nothing in normal testing would have surfaced it.

This file is the artifact a port must reproduce. It is dependency-free (no numpy,
no pygame, no camera, no recordings) so it can be transliterated to JS/Swift/
Kotlin and run there against the same expected numbers.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_palm_depth.py
Exit code 0 = all pass.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_depth as PD         # noqa: E402

FAILURES = []


def check(name, got, want, tol=1e-9):
    ok = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:58s} got {got!r}")
    if not ok:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def hand(scale=1.0, half_width=30.0):
    """A synthetic 21-point hand, face-on, centred on the wrist.

    `half_width` shrinks the knuckle row toward the wrist axis, which is what
    turning the palm edge-on does in projection: at 0 the palm quad is collapsed
    and `edge_on_measure` is 0.
    """
    pts = [(0.0, 0.0)] * 21
    pts[0] = (0.0, 0.0)                              # wrist
    pts[5] = (-half_width * scale, -60.0 * scale)    # index MCP
    pts[9] = (0.0, -70.0 * scale)                    # middle MCP
    pts[17] = (half_width * scale, -60.0 * scale)    # pinky MCP
    return pts


def main():
    print("=" * 78)
    print("Golden vectors -- palm_depth.DepthRatioTracker (M9 / 4.1)")
    print("=" * 78)

    print("\n--- 1. spans and baseline ---")
    s = PD.palm_spans(hand())
    check("palm_spans returns 4 rigid spans", len(s), 4)
    check("width span 5<->17 at scale 1", s[0], 60.0, 1e-9)
    check("palm_spans rejects a short landmark list", PD.palm_spans([(0, 0)] * 5), None)

    t = PD.DepthRatioTracker()
    check("freeze on a face-on hand succeeds", t.freeze(hand()), True)
    check("ratio is exactly 1.0 at the baseline", t.ratio, 1.0, 0.0)
    check("depth_valid True once baselined", t.depth_valid, True)

    print("\n--- 2. !! freeze REFUSES an edge-on baseline ---")
    print("      (a collapsed span as denominator would inflate every later ratio)")
    t2 = PD.DepthRatioTracker()
    check("edge-on freeze is refused", t2.freeze(hand(half_width=0.4)), False)
    check("no baseline was taken", t2.baseline, None)
    check("depth_valid False with no baseline", t2.depth_valid, False)

    print("\n--- 3. the ratio tracks scale, rate limit permitting ---")
    t3 = PD.DepthRatioTracker(rate_limit=10.0)      # effectively unlimited
    t3.freeze(hand(scale=1.0))
    r, ok = t3.update(hand(scale=1.5))
    check("hand 1.5x larger -> ratio 1.5 (nearer)", r, 1.5, 1e-9)
    check("valid while well-conditioned", ok, True)
    r, ok = t3.update(hand(scale=0.5))
    check("hand 0.5x -> ratio 0.5 (further)", r, 0.5, 1e-9)

    print("\n--- 4. !! S10: the ratio FREEZES inside the edge-on band ---")
    t4 = PD.DepthRatioTracker(rate_limit=10.0)
    t4.freeze(hand(scale=1.0))
    t4.update(hand(scale=1.2))
    held = t4.ratio
    r, ok = t4.update(hand(scale=3.0, half_width=0.4))   # huge scale BUT edge-on
    check("edge-on frame does NOT move the ratio", r, held, 0.0)
    check("valid is False while held", ok, False)
    check("depth_valid False inside the band", t4.depth_valid, False)
    check("band entry counted", t4.band_entries, 1)

    print("\n--- 5. leaving the band needs a SUSTAINED run, not one good frame ---")
    r, ok = t4.update(hand(scale=1.0))       # 1st good frame
    check("one good frame does not release the freeze", ok, False)
    r, ok = t4.update(hand(scale=1.0))       # 2nd
    check("two good frames still held", ok, False)
    r, ok = t4.update(hand(scale=1.0))       # 3rd == EXIT_DWELL_FRAMES
    check("third consecutive good frame resumes measuring", ok, True)

    print("\n--- 6. rate limit caps a per-frame excursion ---")
    t6 = PD.DepthRatioTracker(rate_limit=0.10)
    t6.freeze(hand(scale=1.0))
    r, _ = t6.update(hand(scale=2.0))
    check("a 2.0x jump is capped to +10%", r, 1.1, 1e-9)
    check("rate limiting was counted", t6.rate_limited, 1)

    print("\n--- 7. clamping keeps one bad frame from throwing the cube away ---")
    t7 = PD.DepthRatioTracker(rate_limit=10.0)
    t7.freeze(hand(scale=1.0))
    r, _ = t7.update(hand(scale=99.0))
    check("ratio clamped to MAX_RATIO", r, PD.MAX_RATIO, 1e-9)

    print("\n--- 8. reset drops the baseline (never fit against a dead track) ---")
    t8 = PD.DepthRatioTracker()
    t8.freeze(hand())
    t8.reset()
    check("baseline cleared on reset", t8.baseline, None)
    check("ratio returns to 1.0", t8.ratio, 1.0, 0.0)

    print("\n--- 9. determinism: same input, same output, no clock ---")
    a = PD.DepthRatioTracker(rate_limit=10.0)
    b = PD.DepthRatioTracker(rate_limit=10.0)
    a.freeze(hand()), b.freeze(hand())
    seq = [1.1, 1.3, 0.9, 1.0, 1.4]
    ra = [a.update(hand(scale=k))[0] for k in seq]
    rb = [b.update(hand(scale=k))[0] for k in seq]
    check("two instances agree exactly", ra == rb, True)
    check("no wall-clock is read (update takes no timestamp)",
          PD.DepthRatioTracker.update.__code__.co_argcount, 2)

    print("\n" + "=" * 78)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print("  -", f)
        print("=" * 78)
        return 1
    print("ALL CHECKS PASSED -- safe to port by transliteration.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
