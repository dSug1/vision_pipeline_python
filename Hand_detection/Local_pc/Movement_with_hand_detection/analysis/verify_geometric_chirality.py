"""Golden vectors for U7's geometric chirality -- `Resources/palm_geometry.py`.

WHY THESE EXIST BEFORE THE PORT DOES (binding rule 6, U3 precedent): a module
designated for the web/mobile port gets golden vectors BEFORE the port is
written, not after. That is not ceremony -- the first run of the FrameRateEstimator
vectors caught a real banker's-rounding divergence between Python and JavaScript
that nothing in normal testing would have surfaced.

⚠ These are UNIT vectors, hand-constructed so the expected answer is known from
geometry rather than from a recording. The corpus measurement lives in
`u7_geometric_chirality.py`; this file guards the ARITHMETIC and the STATE
MACHINE, which is what a port has to reproduce exactly.

Run:  .venv/Scripts/python.exe analysis/verify_geometric_chirality.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import palm_geometry as PG  # noqa: E402

FAILS = []


def check(name, got, want):
    ok = (got == want)
    if not ok:
        FAILS.append("%s: got %r, want %r" % (name, got, want))
    print("  [%s] %-58s %r" % ("PASS" if ok else "FAIL", name, got))


def close(name, got, want, tol=1e-9):
    ok = abs(got - want) <= tol
    if not ok:
        FAILS.append("%s: got %r, want %r (tol %g)" % (name, got, want, tol))
    print("  [%s] %-58s %.9f" % ("PASS" if ok else "FAIL", name, got))


def hand(thumb_z, scale=1.0):
    """A minimal synthetic hand in WORLD coordinates.

    wrist at the origin; index_MCP along +x; pinky_MCP along +y (so the palm quad
    lies in the z=0 plane); the thumb lifted off that plane by `thumb_z`. The SIGN
    of thumb_z is therefore the chirality, and the expected answer is readable
    straight off the construction rather than from a fixture."""
    pts = [(0.0, 0.0, 0.0)] * 21
    pts[PG.WRIST] = (0.0, 0.0, 0.0)
    pts[PG.INDEX_MCP] = (0.08 * scale, 0.0, 0.0)
    pts[PG.PINKY_MCP] = (0.0, 0.08 * scale, 0.0)
    pts[PG.THUMB_CMC] = (0.02 * scale, 0.02 * scale, thumb_z)
    return pts


def main():
    print(__doc__.strip().splitlines()[0])
    print()

    # -- 1. the volume itself ------------------------------------------------
    print("1. signed_palm_volume -- sign is chirality, magnitude is scale^3")
    # det[(0.08,0,0), (0,0.08,0), (0.02,0.02,z)] = 0.08*0.08*z = 0.0064*z
    close("V for thumb_z=+0.01", PG.signed_palm_volume(hand(+0.01)), 0.0064 * 0.01)
    close("V for thumb_z=-0.01", PG.signed_palm_volume(hand(-0.01)), -0.0064 * 0.01)
    close("V is exactly zero when the thumb is IN the palm plane",
          PG.signed_palm_volume(hand(0.0)), 0.0)
    # Scaling EVERY coordinate by k scales a 3x3 determinant by k^3. A port that
    # normalises coordinates will diverge here, which is the point of the check.
    # ⚠ Note `hand(z, scale)` scales x/y only, so the k^3 hand is built by scaling
    # the finished point list -- getting this wrong is how the first draft of this
    # vector "failed" against correct code.
    scaled = [(2.0 * x, 2.0 * y, 2.0 * z) for (x, y, z) in hand(0.01)]
    close("V scales as k^3 (k=2)", PG.signed_palm_volume(scaled),
          8.0 * PG.signed_palm_volume(hand(0.01)))

    # -- 2. rotation invariance ----------------------------------------------
    print()
    print("2. ROTATION INVARIANCE -- the property the whole approach rests on")

    def rot_z(pts, c, s):
        return [(x * c - y * s, x * s + y * c, z) for (x, y, z) in pts]

    def rot_x(pts, c, s):
        return [(x, y * c - z * s, y * s + z * c) for (x, y, z) in pts]

    base = hand(+0.01)
    v0 = PG.signed_palm_volume(base)
    # 90 deg about z, then 90 deg about x -- exact integers, no trig error
    close("V unchanged by a 90 deg z-rotation",
          PG.signed_palm_volume(rot_z(base, 0.0, 1.0)), v0)
    close("V unchanged by a 90 deg x-rotation",
          PG.signed_palm_volume(rot_x(base, 0.0, 1.0)), v0)
    close("V unchanged by both, composed",
          PG.signed_palm_volume(rot_x(rot_z(base, 0.0, 1.0), 0.0, 1.0)), v0)
    # ...and translation
    close("V unchanged by translation",
          PG.signed_palm_volume([(x + 0.5, y - 0.3, z + 7.0) for (x, y, z) in base]), v0)

    # -- 3. reflection flips it ----------------------------------------------
    print()
    print("3. REFLECTION -- the ONLY thing that may flip the sign")
    close("mirroring x negates V",
          PG.signed_palm_volume([(-x, y, z) for (x, y, z) in base]), -v0)
    close("mirroring z negates V",
          PG.signed_palm_volume([(x, y, -z) for (x, y, z) in base]), -v0)

    # -- 4. the label mapping ------------------------------------------------
    print()
    print("4. geometric_chirality -- the fitted bit: V<0 == apparent Left")
    check("V<0 -> 'Left'", PG.geometric_chirality(hand(-0.01)), "Left")
    check("V>0 -> 'Right'", PG.geometric_chirality(hand(+0.01)), "Right")
    check("V==0 -> None (caller holds rather than guesses)",
          PG.geometric_chirality(hand(0.0)), None)

    # -- 5. conditioning -----------------------------------------------------
    print()
    print("5. palm_plane_thickness -- diagnostic, NOT a gate (measured null)")
    # |V| / |cross(a,b)| = (0.0064*z) / 0.0064 = z
    close("thickness == the thumb's height above the palm plane",
          PG.palm_plane_thickness(hand(0.0123)), 0.0123)
    close("thickness is unsigned", PG.palm_plane_thickness(hand(-0.0123)), 0.0123)
    close("degenerate palm quad -> 0.0, not a divide-by-zero",
          PG.palm_plane_thickness([(0.0, 0.0, 0.0)] * 21), 0.0)

    # -- 6. the resolver's state machine -------------------------------------
    print()
    print("6. ChiralityResolver -- debounce %d, the part a port gets wrong"
          % PG.CHIRALITY_DEBOUNCE_FRAMES)
    L, R = hand(-0.01), hand(+0.01)

    r = PG.ChiralityResolver()
    check("first sighting is adopted immediately", r.update(L, "Right"), "Left")
    check("...and it OVERRIDES a disagreeing label", r.held, "Left")

    r = PG.ChiralityResolver()
    r.update(L, "Left")
    check("a single disagreeing frame is absorbed", r.update(R, "Left"), "Left")
    check("two disagreeing frames are still absorbed", r.update(R, "Left"), "Left")
    check("the THIRD flips it (debounce=3)", r.update(R, "Left"), "Right")

    r = PG.ChiralityResolver()
    r.update(L, "Left")
    r.update(R, "Left")
    r.update(R, "Left")
    check("an agreeing frame RESETS the run", r.update(L, "Left"), "Left")
    check("...so the next two do not flip it", r.update(R, "Left"), "Left")
    check("...nor the one after that", r.update(R, "Left"), "Left")

    r = PG.ChiralityResolver()
    r.update(L, "Left")
    r.reset()
    check("reset drops the held value (a returning hand inherits NOTHING)",
          r.held, None)
    check("...so the next sighting is adopted fresh", r.update(R, "Left"), "Right")

    r = PG.ChiralityResolver()
    check("no world landmarks -> the label, unchanged", r.update(None, "Right"), "Right")
    check("empty world landmarks -> the label, unchanged", r.update([], "Left"), "Left")
    check("...and nothing was held from those frames", r.held, None)

    r = PG.ChiralityResolver()
    check("degenerate V and nothing held -> falls back to the label",
          r.update(hand(0.0), "Right"), "Right")
    r.update(L, "Left")
    check("degenerate V WITH a held value -> holds, ignores the label",
          r.update(hand(0.0), "Right"), "Left")

    # -- 7. the A/B switch really restores the old behaviour ------------------
    print()
    print("7. GEOMETRIC_CHIRALITY=False must be bit-identical to pre-U7")
    saved = PG.GEOMETRIC_CHIRALITY
    try:
        PG.GEOMETRIC_CHIRALITY = False
        r = PG.ChiralityResolver()
        check("flag off -> the label passes straight through",
              r.update(L, "Right"), "Right")
        check("flag off -> nothing is held", r.held, None)
    finally:
        PG.GEOMETRIC_CHIRALITY = saved

    # -- 8. end to end through PalmFacingTracker -----------------------------
    print()
    print("8. PalmFacingTracker -- the choke point BOTH tools call")
    # A well-conditioned 2D palm, so DR-2 does not freeze and we see the cue.
    px = [(0.0, 0.0)] * 21
    px[PG.WRIST] = (100.0, 300.0)
    px[PG.INDEX_MCP] = (60.0, 200.0)
    px[PG.PINKY_MCP] = (160.0, 210.0)

    t = PG.PalmFacingTracker()
    without = t.update(px, "Right")[0]
    t2 = PG.PalmFacingTracker()
    with_world = t2.update(px, "Right", L)[0]
    check("omitting world_landmarks reproduces the label-driven answer",
          without, PG.is_thumb_outward(px, "Right"))
    check("supplying them uses the GEOMETRIC chirality instead",
          with_world, PG.is_thumb_outward(px, "Left"))
    check("...and those two answers actually differ (the vector is meaningful)",
          without != with_world, True)
    t2.reset()
    check("tracker.reset() clears the resolver too", t2.chirality.held, None)

    # -- 9. a DIFFERENT hand in the slot inherits nothing -------------------
    print()
    print("9. TRACK-AWARE RESET -- post-mortem rule 2, measured live 2026-08-22")
    # The recorded defect: track t9 moved into a slot holding t5's chirality and
    # its back-of-hand read as PALM for two frames -- long enough to grab a cube
    # rule 3 should have refused. Session 2026-08-22_185958, frame 1050.
    t = PG.PalmFacingTracker()
    a = t.update(px, "Right", L, track_id=5)[0]      # hand t5 establishes state
    b = t.update(px, "Right", R, track_id=9)[0]      # a DIFFERENT hand arrives
    check("a new track in the slot resets the held chirality",
          t.chirality.held, PG.geometric_chirality(R))
    check("...so its own geometry decides, not the previous hand's", b,
          PG.is_thumb_outward(px, PG.geometric_chirality(R)))
    check("...and that differs from the inherited answer", a != b, True)
    check("the reset is counted", t.track_changes, 1)

    t = PG.PalmFacingTracker()
    t.update(px, "Right", L, track_id=5)
    t.update(px, "Right", L, track_id=5)
    check("the SAME track does not reset", t.track_changes, 0)

    # -1 is "no identity this frame": it must neither reset nor be adopted as an
    # id, or every unidentified frame would throw away good state.
    t = PG.PalmFacingTracker()
    t.update(px, "Right", L, track_id=5)
    t.update(px, "Right", L, track_id=-1)
    check("-1 (no identity) does not reset", t.track_changes, 0)
    t.update(px, "Right", L, track_id=5)
    check("...and the track is still remembered as 5", t.track_changes, 0)

    t = PG.PalmFacingTracker()
    t.update(px, "Right", L)
    check("omitting track_id never resets (unmigrated caller)", t.track_changes, 0)

    # -- 10. U8: rule 3 may not act on a PROVISIONAL chirality ---------------
    print()
    print("10. U8 CONFIRMATION GATE -- confirm frames = %d"
          % PG.CHIRALITY_CONFIRM_FRAMES)
    r = PG.ChiralityResolver()
    check("nothing seen yet -> confirmed (the LABEL is driving, not geometry)",
          r.confirmed, True)
    r.update(L, "Left")
    check("one geometric frame -> PROVISIONAL", r.confirmed, False)
    for _ in range(PG.CHIRALITY_CONFIRM_FRAMES - 2):
        r.update(L, "Left")
    check("...still provisional one frame short", r.confirmed, False)
    r.update(L, "Left")
    check("...confirmed on the %dth agreeing observation"
          % PG.CHIRALITY_CONFIRM_FRAMES, r.confirmed, True)

    # THE RECORDED FAILURE: the count alone was satisfied ON the grab frame while
    # the held value was still wrong. A disagreeing observation must un-confirm.
    check("a DISAGREEING observation makes it provisional again",
          (r.update(R, "Left"), r.confirmed)[1], False)
    check("...and the held value has NOT flipped yet (debounce still running)",
          r.held, "Left")
    check("agreement restores confirmation",
          (r.update(L, "Left"), r.confirmed)[1], True)

    r = PG.ChiralityResolver()
    for _ in range(PG.CHIRALITY_CONFIRM_FRAMES):
        r.update(L, "Left")
    r.reset()
    check("reset makes it provisional again (a new hand is unconfirmed)",
          r.confirmed, True)          # held is None -> the label drives, so True
    r.update(R, "Left")
    check("...and once geometry speaks again it is provisional", r.confirmed, False)

    # A caller that supplies no world landmarks must be UNCHANGED, never blocked.
    r = PG.ChiralityResolver()
    for _ in range(10):
        r.update(None, "Left")
    check("no world landmarks -> never blocked (unmigrated caller unchanged)",
          r.confirmed, True)

    saved = PG.GEOMETRIC_CHIRALITY
    try:
        PG.GEOMETRIC_CHIRALITY = False
        r = PG.ChiralityResolver()
        r.update(L, "Left")
        check("flag off -> gate is open (pre-U7 behaviour)", r.confirmed, True)
    finally:
        PG.GEOMETRIC_CHIRALITY = saved

    # -- 11. U8 in MILLISECONDS: correct at any capture rate ----------------
    print()
    print("11. U8 WINDOW AS A DURATION (%.0f ms) -- rate-independent"
          % PG.CHIRALITY_CONFIRM_MS)
    MS = PG.CHIRALITY_CONFIRM_MS

    def run_at(fps, frames):
        """Feed `frames` agreeing observations at `fps`; -> confirmed?"""
        rr = PG.ChiralityResolver()
        step = 1000.0 / fps
        for k in range(frames):
            rr.update(L, "Left", now_ms=k * step)
        return rr.confirmed

    # The SAME wall-clock window must be enforced whatever the rate. At 15 fps
    # that is ~5 frames; at 30 fps ~10. A frame constant could not do both.
    slow_needed = int(MS / (1000.0 / 15.0)) + 1
    fast_needed = int(MS / (1000.0 / 30.0)) + 1
    check("15 fps: one frame short of %.0f ms -> provisional" % MS,
          run_at(15.0, slow_needed), False)
    check("15 fps: %.0f ms elapsed -> confirmed" % MS,
          run_at(15.0, slow_needed + 1), True)
    check("30 fps: the same FRAME count is NOT yet enough (half the time)",
          run_at(30.0, slow_needed + 1), False)
    check("30 fps: %.0f ms elapsed -> confirmed" % MS,
          run_at(30.0, fast_needed + 1), True)
    check("...and that needs about twice the frames, as it should",
          fast_needed > slow_needed, True)

    # The observation floor still binds, however long the wall clock says.
    rr = PG.ChiralityResolver()
    rr.update(L, "Left", now_ms=0.0)
    rr.update(L, "Left", now_ms=100000.0)
    check("a long gap with too FEW observations stays provisional",
          rr.confirmed, False)
    check("...the floor is %d observations" % PG.CHIRALITY_CONFIRM_MIN_FRAMES,
          (rr.update(L, "Left", now_ms=100001.0), rr.confirmed)[1], True)

    # A caller that passes no timestamp must still work -- frame-count fallback.
    rr = PG.ChiralityResolver()
    for _ in range(PG.CHIRALITY_CONFIRM_FRAMES - 1):
        rr.update(L, "Left")
    check("no timestamps -> frame fallback, still provisional", rr.confirmed, False)
    rr.update(L, "Left")
    check("no timestamps -> confirmed at %d frames" % PG.CHIRALITY_CONFIRM_FRAMES,
          rr.confirmed, True)

    rr = PG.ChiralityResolver()
    for k in range(PG.CHIRALITY_CONFIRM_FRAMES + 4):
        rr.update(L, "Left", now_ms=k * (1000.0 / 18.0))
    rr.reset()
    check("reset clears the clock too (a new hand starts its own window)",
          rr._first_ms, None)

    print()
    t = PG.PalmFacingTracker()
    check("tracker exposes the gate", t.chirality_confirmed, True)
    t.update(px, "Right", L, track_id=1)
    check("...and it goes provisional with the resolver",
          t.chirality_confirmed, False)

    print()
    if FAILS:
        print("=" * 70)
        print("FAILED (%d):" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        print("=" * 70)
        return 1
    print("=" * 70)
    print("ALL GOLDEN VECTORS PASS -- this is the artifact a port must reproduce.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
