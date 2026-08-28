# -*- coding: utf-8 -*-
"""Golden vectors for the debug tool's SPACE key — ungrab and home the cube.

    .venv/Scripts/python.exe analysis/verify_home_cube.py

Owner, 2026-08-28: *"when a cube is grabbed and I hit space on debug, ungrab the
cube and reset the transform of the grabbed cube to position vector null and
quaternion identity. This will help me have a fixed reference to start each of the
movements."*

⭐ IT IS AN INSTRUMENT, SO IT IS TESTED LIKE ONE. Every rotation in this pipeline
is grab-relative, so a trial that starts wherever the last one ended is not
comparable to the one before it. If this reset is subtly wrong -- an orientation
that is not quite identity, a centre that drifts with depth -- then every eye-level
judgement made with it inherits the error, silently. That is worse than no tool.

⛔ THE ORDER-OF-OPERATIONS CHECK IS THE LOAD-BEARING ONE. `set_target_center`
derives `position` from the PROJECTED extent, which depends on depth
(`CONSTRAINTS` §7). Setting the centre before the depth leaves the cube off-centre
by the size difference — so the test homes from a NON-reference depth, which is the
only way that mistake shows up.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

FAILURES = []


def ok(name, cond, detail=""):
    print("  [%s] %-56s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        FAILURES.append(name)


def main():
    print("=" * 78)
    print("GOLDEN VECTORS — SPACE homes the held cube")
    print("=" * 78)
    import LiveSnapDebug as L
    from Resources import palm_geometry as PG
    from Resources import object_assembly as OA
    from Resources.CubeWindow import DEFAULT_CUBE_SIZE as CW_SIZE

    W, H = 1280, 720

    def fresh(depth, pos, orient, owner="Left"):
        st = L.CubeState(window_size=(W, H))
        st.cubes["left"] = L.Cube(mesh=None, size=120, position=pos)
        c = st.cubes["left"]
        c.owner = owner
        c.orientation = orient
        c.depth_m = depth
        c.grab_hand_orientation = (1.0, 0.0, 0.0, 0.0)
        c.grab_cube_orientation = orient
        c.grab_depth_m = depth
        c.grab_grip_offset = (5.0, 5.0)
        c.grab_hand_depth_m = depth
        return st, c

    def centre_of(st, c):
        s = st.projected_size_of(c)
        return c.position[0] + s / 2.0, c.position[1] + s / 2.0

    print("\n1. THE TRANSFORM IS RESET")
    st, c = fresh(0.31, (900.0, 40.0), (0.7071, 0.0, 0.7071, 0.0))
    st.home_held_cubes()
    ok("orientation is EXACTLY identity", c.orientation == L.IDENTITY_QUATERNION,
       str(c.orientation))
    ok("depth is the reference depth", c.depth_m == PG.REFERENCE_DEPTH_M,
       "%.3f m" % c.depth_m)
    cx, cy = centre_of(st, c)
    # ⚠⚠ THIS ASSERTION CHANGED ON 2026-08-28, AND IT IS NOT A SILENCED FAILURE.
    # It used to read "the frame centre", and it failed the moment objects were
    # given SEPARATE home slots (`AS1`). ⛔ The old behaviour was the defect: both
    # cubes homing to the middle put them INSIDE each other, which is what made an
    # ordinary drag mate on frame 12 and take the cube out of the player's hand --
    # reported live as *"I can't get the cube to move on the z axis"*.
    # ⭐ The PROPERTY under test is unchanged and is the one that matters: homing
    # sends the object to a DETERMINISTIC, KNOWN place. That place is now its own
    # slot in the row, which is what `home_center` returns.
    # ⛔ `V1` recorded the opposite mistake as a method rule -- a harness reporting a
    # real defect was explained away with a guard. This is the other case: the
    # SPECIFICATION moved, so the vector moves with it, and says so.
    hx, hy = st.home_center("left")
    # ⚠ The contract is "your own slot, CONFINED TO THE PLAY AREA" — homing goes
    # through `set_target_center`, so the clamp applies here as everywhere else.
    # ⭐ It bites in this fixture and not in the product: the fixture adds a THIRD
    # cube, and at `HOME_SEPARATION_M` the outermost of three slots falls outside
    # the play area on a 1280-wide frame. With the two objects that actually ship,
    # no clamping happens — which section 1b asserts directly.
    ex, ey = PG.clamp_to_play_volume(hx, hy, c.depth_m, c.size, st.window_size)
    ok("centre is this object's OWN home slot (not the frame centre)",
       abs(cx - ex) < 0.5 and abs(cy - ey) < 0.5,
       "(%.1f, %.1f) vs home (%.1f, %.1f)" % (cx, cy, ex, ey))
    ok("...and that slot is deterministic, so a trial always starts identically",
       st.home_center("left") == (hx, hy))

    print("\n1b. ⛔⛔ THE OBJECTS' REAL SIZES MUST CLEAR THEIR OWN PREVIEW REACH")
    # ⭐⭐ THIS READS THE SHIPPED OBJECTS, NOT A FIXTURE, AND THAT IS THE POINT.
    # `verify_object_assembly.py` builds its own cubes, so it cannot notice when the
    # PRODUCT's sizes move underneath it — which is exactly the trap that let a
    # `+X`-only connector set ship unreachable. When the owner made both cubes the
    # same size (2026-08-28) the home separation silently stopped clearing the
    # preview reach; this is the check that refuses to let that pass quietly again.
    # ⚠⚠ CHECKED AT SEVERAL RESOLUTIONS, AND THE NARROW ONE IS THE HARD CASE.
    # `size` is a PIXEL count at the reference depth, so an object's REAL size is
    # `size * REFERENCE_DEPTH / focal(width)` — and focal scales with width. The
    # same 80 px cube is 72 mm on a 640-wide camera and 36 mm on a 1280-wide one.
    # A check at one resolution therefore proves nothing about the other, and the
    # NARROW camera is where the home separation is tightest.
    for _W, _H in ((640, 480), (1280, 720), (1920, 1080)):
        st_r = L.CubeState(window_size=(_W, _H))
        halves_r = sorted(OA.half_extent_m(c.size, (_W, _H)) for c in st_r.cubes.values())
        meeting = halves_r[-2:]                 # the two that would actually meet
        reach = sum(h * OA.MC.MATE_RADIUS_FRACTION for h in meeting)
        gap = OA.HOME_SEPARATION_M - sum(meeting)
        ok("home gap clears the PREVIEW reach at %dx%d" % (_W, _H),
           gap > reach * OA.PREVIEW_RADIUS_FACTOR,
           "%.1f mm gap vs %.1f mm preview"
           % (gap * 1000.0, reach * OA.PREVIEW_RADIUS_FACTOR * 1000.0))
    st2 = L.CubeState(window_size=(W, H))
    halves = sorted(OA.half_extent_m(c.size, (W, H)) for c in st2.cubes.values())
    homes = [st2.home_center(n) for n in st2.cubes]
    ok("every object gets its OWN home slot", len(set(homes)) == len(homes),
       str(["%.0f" % h[0] for h in homes]))
    f = PG.focal_px((W, H))
    inset = (PG.PLAY_AREA_MARGIN_M + max(halves)) * f / PG.REFERENCE_DEPTH_M
    ok("...and every slot is inside the play area at the reference depth",
       all(inset <= h[0] <= W - inset for h in homes),
       "%s in %.0f..%.0f" % (["%.0f" % h[0] for h in homes], inset, W - inset))
    ok("⚠ N6: the debug tool and production carry the SAME object size",
       {c.size for c in st2.cubes.values()} == {CW_SIZE},
       "debug %s vs production %d" % (sorted({c.size for c in st2.cubes.values()}), CW_SIZE))

    print("\n2. ⛔ THE CUBE IS RELEASED, AND EVERY GRAB BASELINE IS CLEARED")
    ok("owner is None", c.owner is None)
    for f in ("grab_hand_orientation", "grab_cube_orientation", "grab_depth_m",
              "grab_grip_offset", "grab_hand_depth_m", "grab_landmark_weights",
              "grab_residual_offset", "grab_depth_offset_m", "grab_anchor_state"):
        ok("%-24s cleared" % f, getattr(c, f) is None)

    print("\n3. ⛔ ORDER OF OPERATIONS — depth BEFORE centre (CONSTRAINTS §7)")
    # Homing from a far depth and a near depth must land on the SAME centre. If
    # the centre were computed before the depth, the projected size would differ
    # and the two would disagree.
    centres = []
    for d in (0.31, 0.50, 0.80):
        st2, c2 = fresh(d, (10.0, 10.0), (0.5, 0.5, 0.5, 0.5))
        st2.home_held_cubes()
        centres.append(centre_of(st2, c2))
    ok("same centre from every start depth",
       max(abs(a[0] - centres[0][0]) + abs(a[1] - centres[0][1]) for a in centres) < 1e-6,
       " ".join("(%.1f,%.1f)" % p for p in centres))

    print("\n4. ⚠ IT TOUCHES ONLY WHAT IS HELD")
    st3 = L.CubeState(window_size=(W, H))
    st3.cubes["left"] = L.Cube(mesh=None, size=120, position=(900.0, 40.0))
    st3.cubes["right"] = L.Cube(mesh=None, size=120, position=(100.0, 600.0))
    st3.cubes["left"].owner = "Left"
    st3.cubes["right"].orientation = (0.7071, 0.7071, 0.0, 0.0)
    before = st3.cubes["right"].position
    homed = st3.home_held_cubes()
    ok("only the held cube is homed", homed == ["left"], str(homed))
    ok("the unheld cube is untouched",
       st3.cubes["right"].position == before
       and st3.cubes["right"].orientation == (0.7071, 0.7071, 0.0, 0.0))
    ok("homing with nothing held is a no-op", st3.home_held_cubes() == [])

    print("\n5. ⭐ IDEMPOTENT — homing twice is homing once")
    st4, c4 = fresh(0.31, (900.0, 40.0), (0.7071, 0.0, 0.7071, 0.0))
    st4.home_held_cubes()
    snap = (c4.orientation, c4.depth_m, c4.position)
    c4.owner = "Left"                      # re-grab, change nothing else
    st4.home_held_cubes()
    ok("second home changes nothing",
       (c4.orientation, c4.depth_m, c4.position) == snap)

    print("\n6. ⛔ PRODUCTION HAS NO SUCH KEY")
    import io
    prod = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "Resources", "CubeWindow.py"),
                   encoding="utf-8-sig").read()
    ok("`home_cube` is debug-only", "def home_cube" not in prod,
       "a game that teleports its object on a keypress is a different game")

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
