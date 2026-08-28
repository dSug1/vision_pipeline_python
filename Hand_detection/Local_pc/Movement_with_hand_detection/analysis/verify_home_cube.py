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
    ok("centre is the world origin (frame centre)",
       abs(cx - W / 2.0) < 0.5 and abs(cy - H / 2.0) < 0.5, "(%.1f, %.1f)" % (cx, cy))

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
