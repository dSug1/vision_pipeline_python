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
    print("")
    print("--- 4. !! THE FALLBACK: edge-on alone no longer freezes depth ---")
    print("      Owner: a depth measure cannot be frozen because the hand is on the")
    print("      edge; a second-order fallback must bridge. Measured over 206")
    print("      edge-on frames: the 0-5 diagonal (1.01x) and palm length (0.94x)")
    print("      SURVIVE while the width collapses (0.63x). The gate is PER-SPAN now.")
    t4 = PD.DepthRatioTracker(rate_limit=10.0)
    t4.freeze(hand(scale=1.0))
    r, ok = t4.update(hand(scale=1.0, half_width=0.4))   # knuckle row edge-on
    check("edge-on with a surviving span still MEASURES", ok, True)
    check("and reports ~1.0 from that span", round(r, 2), 1.0)
    check("the band was still recorded as entered", t4.band_entries, 1)

    print("")
    print("--- 5. it holds ONLY when every span has collapsed ---")
    print("      MIN_SPAN_FRACTION 0.50 sits just BELOW the measured reach envelope")
    print("      minimum (0.53), so real arm movement stays measurable and only")
    print("      sub-envelope collapse holds.")
    t5 = PD.DepthRatioTracker(rate_limit=10.0)
    t5.freeze(hand(scale=1.0))
    t5.update(hand(scale=0.9))
    held = t5.ratio
    r, ok = t5.update(hand(scale=0.2))
    check("all spans collapsed -> holds", ok, False)
    check("and the ratio does not move", r, held, 0.0)
    t5b = PD.DepthRatioTracker(rate_limit=10.0)
    t5b.freeze(hand(scale=1.0))
    r, ok = t5b.update(hand(scale=0.6))
    check("a genuine 0.6x retreat is still measured", ok, True)


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

    # ======================================================================
    print("\n" + "=" * 78)
    print("Golden vectors -- palm_depth.HandDepthTracker (4.2's 3D snap gate)")
    print("=" * 78)
    FR = (640, 480)

    print("\n--- 10. absolute depth from nominal anatomy ---")
    # ⚠ The point of these vectors is NOT that the metre value is TRUE -- it
    # cannot be, absolute scale is unobservable from one uncalibrated camera and
    # this substitutes anthropometric medians for the missing baseline. It is
    # that the value is the RIGHT FUNCTION of the image: proportional to 1/span,
    # selected from the least-foreshortened span, and bounded by the play volume.
    h = PD.HandDepthTracker()
    d1, v1 = h.update(hand(scale=1.0), FR)
    check("a face-on hand measures (not holds)", v1, True)
    check("...and lands inside the play volume",
          PD.PG.PLAY_DEPTH_MIN_M <= d1 <= PD.PG.PLAY_DEPTH_MAX_M, True)

    # ⭐ THE INVARIANCE THAT MATTERS: doubling every span halves the depth, and
    # halving them doubles it -- a pinhole camera's 1/Z law. Anything else here
    # would mean the estimator is not measuring distance at all.
    h2 = PD.HandDepthTracker()
    near, _ = h2.update(hand(scale=2.0), FR)
    h3 = PD.HandDepthTracker()
    far, _ = h3.update(hand(scale=0.5), FR)
    check("twice the apparent size -> half the depth", near, d1 / 2.0, 1e-6)
    check("half the apparent size -> twice the depth", far, min(d1 * 2.0, PD.PG.PLAY_DEPTH_MAX_M), 1e-6)

    print("\n--- 11. the least-foreshortened span wins ---")
    # Narrowing the knuckle row foreshortens the WIDTH span only. Depth must not
    # move with it: the surviving spans still measure the same distance. This is
    # the ratio form's `max()` seen from the other side (a shrunken span inflates
    # `f*S/span`, so the SMALLEST per-span depth is the least corrupted one).
    h4 = PD.HandDepthTracker()
    d_square, _ = h4.update(hand(scale=1.0, half_width=30.0), FR)
    h5 = PD.HandDepthTracker()
    d_narrow, _ = h5.update(hand(scale=1.0, half_width=18.0), FR)
    check("a 40% narrower knuckle row moves depth by <5%",
          abs(d_narrow - d_square) / d_square < 0.05, True)

    print("\n--- 12. S10: the band HOLDS, and says so ---")
    # ⭐ 4.2 DECISION 1 rests entirely on this bit: a snap is REFUSED while
    # `valid` is False. If the tracker ever reported True through the band, the
    # decision would silently stop applying and nothing would look wrong.
    h6 = PD.HandDepthTracker()
    good, _ = h6.update(hand(scale=1.0), FR)
    d_edge, v_edge = h6.update(hand(scale=1.0, half_width=0.05), FR)
    check("edge-on reports INVALID rather than a number it cannot measure", v_edge, False)
    check("...and HOLDS the last measured depth", d_edge, good, 1e-12)
    check("...and counts the frozen frame", h6.frames_frozen, 1)
    # Hysteresis: one good frame is not enough to leave the band (EXIT_DWELL).
    check("one recovered frame does not leave the band",
          h6.update(hand(scale=1.0), FR)[1], False)
    for _ in range(PD.EXIT_DWELL_FRAMES):
        last = h6.update(hand(scale=1.0), FR)
    check("a sustained recovery run does", last[1], True)

    print("\n--- 13. degradations never fabricate a value ---")
    h7 = PD.HandDepthTracker()
    check("a short landmark list holds and reports invalid",
          h7.update([(0, 0)] * 5, FR), (None, False))
    check("no frame size -> no focal -> no depth",
          h7.update(hand(), None), (None, False))
    h8 = PD.HandDepthTracker()
    h8.update(hand(), FR)
    h8.reset()
    check("reset drops the held depth (it belonged to that hand)", h8.depth_m, None)

    print("\n--- 14. the tolerance is reachable for a non-median hand ---")
    # ⚠⚠ THE FAILURE MODE THIS EXISTS TO CATCH: the depth is scaled by NOMINAL
    # anatomy, so a user 20% off the median reads a CONSTANT offset. If
    # GRAB_Z_TOLERANCE_M were ever tightened below that offset, nothing could be
    # picked up -- and it would look like a broken build, not a bad constant.
    h9 = PD.HandDepthTracker()
    median, _ = h9.update(hand(scale=1.0), FR)
    h10 = PD.HandDepthTracker()
    small_hand, _ = h10.update(hand(scale=0.8), FR)     # 20% smaller than nominal
    check("a 20% smaller hand still lands inside GRAB_Z_TOLERANCE_M",
          abs(small_hand - median) <= PD.GRAB_Z_TOLERANCE_M, True)
    check("the policy constants live here, not in either tool",
          (PD.SNAP_REQUIRES_VALID_DEPTH, round(PD.GRAB_Z_TOLERANCE_M, 3)), (True, 0.15))

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
