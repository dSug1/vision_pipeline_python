"""⛔⛔ `F1` STEP 2's ACCEPTANCE GATE — the switch OFF must be TODAY's pipeline.

Every `F1` step lands behind a flag whose OFF state is provably the shipped
behaviour, so the whole build is revert-free by a number rather than by an
argument. `T6d` established the method — every arm sat behind a toggle measured
byte-identical to shipped Horn on 975/975 frames — and it is what made that build
cost nothing when the owner rejected it after four live sessions.

⭐⭐ THE REFERENCE IS NOT A SECOND IMPLEMENTATION, IT IS THE RECORDING ITSELF.
A take recorded before step 2 carries, per frame, the cube positions the OLD code
actually produced. Replaying that take through the CURRENT code with
`fingertips.USE_TIP_BARYCENTER = False` must reproduce them exactly. That closes
the loop against what shipped, not against a fresh derivation of what shipped —
which is the distinction that made four harnesses report CLEAN on takes the owner
had just watched fail.

⚠ It also checks the flag ON actually CHANGES something. A gate that passes in
both positions is not testing the switch, it is testing nothing — and this project
has shipped an inverted convention while passing an "end-to-end confirmed" claim.

    .venv/Scripts/python.exe analysis/verify_f1_grip_offstate.py [session]
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_depth                             # noqa: E402
from Resources import object_extent                          # noqa: E402
from Resources import fingertips                               # noqa: E402
from Resources import HandsTriggeredActions as P               # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
# ⛔⛔ IT MUST BE A **PRODUCTION** TAKE, recorded BEFORE step 2. Two things this
# harness got wrong on its first run, both worth keeping:
#   1. A DEBUG-tool take was used, and replayed through PRODUCTION. The two are
#      separate implementations kept in step by `parity_replay` on gesture logic
#      and OWNERSHIP -- not on the exact pixel the cube is drawn at. Comparing one
#      tool's recording against the other's replay measured that gap, not step 2.
#   2. The two passes shared cube state, so pass 2 began wherever pass 1 left the
#      cubes and EVERY frame differed. The giveaway was `moved == compared`
#      exactly: even frames with nothing held "changed".
DEFAULT_SESSION = "2026-08-24_220415_prod_tau20"
HANDS = ("Left", "Right")

_fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<58} {detail}")
    if not ok:
        _fails.append(name)


def load(session):
    d = os.path.join(CAPTURE, session)
    path = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.isfile(path):
        return None
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def recorded_cubes(row):
    """The cube block the RECORDER wrote for this frame, whatever its shape."""
    c = row.get("cubes") or {}
    if not isinstance(c, dict) or not c:
        return {}
    vals = list(c.values())
    if vals and all(isinstance(v, dict) and v and
                    all(isinstance(x, dict) for x in v.values()) for v in vals):
        return vals[0]                      # per-arm: the shipped arm is first
    return c


# ⛔⛔ THE GRAB RADIUS THE REFERENCE TAKE WAS RECORDED UNDER, AND WHY IT IS PINNED.
#
# This gate's reference is a RECORDING, so it is a net over the WHOLE pipeline:
# change any gameplay constant and the replay stops reproducing the take. That is
# usually the point. But the subject this file NAMES is the `F1` switch, and on
# 2026-08-26 the owner tightened `GRAB_RADIUS_MULTIPLIER` from 1.5 to 0.5 -- a
# deliberate behaviour change, which made check 1 fail at 288 px for a reason that
# has nothing to do with the switch.
#
# ⭐ So the radius is PINNED here to the value in force when the take was made.
# The gate then isolates the variable it claims to test, instead of reporting a
# switch failure that is really a constant change.
#
# ⛔ WHAT THIS COSTS, STATED PLAINLY: this gate can no longer notice a change to
# the grab radius. That is now covered only by the constant's own definition in
# `hand_state.py` and by a live take -- a tightened radius CANNOT be validated
# against recordings made under the old one, because the grabs it removes are
# exactly the ones the recording contains.
# ⚠⚠ THREE THINGS ARE NOW PINNED HERE (grab radius, grab rule, depth rate limit).
# Each is defensible on its own -- every one is a deliberate behaviour change made
# after this take was recorded -- but together they mean this file tests the `F1`
# SWITCH and increasingly little else. ⛔ It is not a general regression net any
# more, and should not be read as one. The general net is `parity_replay` plus the
# golden-vector suites; if a fourth pin is ever needed, re-baseline against a NEW
# recording instead of adding it.
RECORDING_ERA_GRAB_RADIUS = 1.5


def _recording_era_grab_extent(size_px, orientation, vertices, perspective_ratio):
    """The grab rule EXACTLY as it stood when the reference take was recorded.

    ⛔ Pinning the multiplier back to 1.5 is not enough, because the rule's FORM
    changed too: it used to multiply the object's NOMINAL projected edge, and now
    it multiplies the narrower axis of the projected FOOTPRINT (~1.2x larger,
    orientation-dependent). Restoring only the number still moved the grab region
    and check 1 still failed, at 158 px.

    ⭐ So the harness restores the whole expression. The F1 switch is then the only
    thing that differs between the recording and the replay, which is what this
    file exists to measure.
    """
    return size_px


def replay(rows, use_tips):
    """Drive production over the take and return its per-frame cube centres."""
    prev = fingertips.USE_TIP_BARYCENTER
    prev_radius = P.GRAB_RADIUS_MULTIPLIER
    fingertips.USE_TIP_BARYCENTER = use_tips
    P.GRAB_RADIUS_MULTIPLIER = RECORDING_ERA_GRAB_RADIUS
    prev_extent = object_extent.grab_extent
    object_extent.grab_extent = _recording_era_grab_extent
    # ⛔ AND THE RECORDING-ERA RATE LIMIT. The depth ratio's cap became PER SECOND
    # on 2026-08-27 (`palm_depth.RATE_LIMIT_PER_S`), driven by a caller-supplied
    # interval. At the take's real ~19.92 fps the intervals are not exactly 50 ms,
    # so the cap now tracks elapsed time rather than frame count -- which is the
    # entire point of the change, and which moved this replay by 7.5 px.
    # ⭐ Dropping the interval restores the per-FRAME cap the take was recorded
    # under, so the F1 switch is again the only variable this file measures.
    prev_ratio_update = palm_depth.DepthRatioTracker.update
    palm_depth.DepthRatioTracker.update = (
        lambda self, landmarks, dt_ms=None: prev_ratio_update(self, landmarks, None))
    P.configure_source_resolution(640, 480)
    # ⛔ A WHOLLY FRESH WORLD, not a released one. `release_cube` clears the grab
    # baseline but leaves the cube WHERE IT ENDED, so a second pass would start
    # from the first pass's final layout and every frame would differ.
    P.cube_window.__class__.__init__(P.cube_window, (640, 480))
    for h in HANDS:
        P._grip_trackers[h].reset()
        P._depth_ratio_trackers[h].reset()
        P._palm_facing_trackers[h].reset()
        P._hand_state_trackers[h].__init__()

    out = []
    try:
        for r in rows:
            t = r["tCapture"]
            by = {h["handedness"]: h for h in (r.get("hands") or [])}
            for h in HANDS:
                P._hand_track_ids[h] = (by.get(h) or {}).get("trackId", -1)
            P.on_hand_tracks_frame(P._hand_track_ids.get("Left", -1),
                                   P._hand_track_ids.get("Right", -1))
            # ⚠ ABSENT HAND = the placeholder the live wire sends, NOT None.
            # `_is_detected` reads a landmark to decide presence, so None crashes
            # it -- and `parity_replay` feeds the same placeholders for the same
            # reason. A harness that shapes its input differently from the wire
            # tests a pipeline that does not exist.
            left = (by.get("Left") or {}).get("landmarks") or [(0.0, 0.0)] * 21
            right = (by.get("Right") or {}).get("landmarks") or [(0.0, 0.0)] * 21
            lw = (by.get("Left") or {}).get("world_landmarks") or [(0.0, 0.0, 0.0)] * 21
            rw = (by.get("Right") or {}).get("world_landmarks") or [(0.0, 0.0, 0.0)] * 21
            P.on_hands_world_frame(lw, rw)
            P.on_hands_frame(left, right, now_ms=t)
            out.append({n: tuple(c.position)
                        for n, c in P.cube_window.cubes.items()})
    finally:
        fingertips.USE_TIP_BARYCENTER = prev
        P.GRAB_RADIUS_MULTIPLIER = prev_radius
        object_extent.grab_extent = prev_extent
        palm_depth.DepthRatioTracker.update = prev_ratio_update
    return out


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SESSION
    print("=" * 82)
    print("F1 STEP 2 -- the OFF state must be today's pipeline")
    print("=" * 82)

    rows = load(session)
    if rows is None:
        print(f"  SKIPPED -- no such take: {session}")
        print("  (wake the capture drive; recordings live on E:, never --local)")
        return 0
    print(f"  take: {session}   frames: {len(rows)}")

    off = replay(rows, use_tips=False)
    on = replay(rows, use_tips=True)

    # --- 1. OFF vs the recording's own cube positions -----------------------
    worst, compared = 0.0, 0
    for r, got in zip(rows, off):
        want = recorded_cubes(r)
        for name, cube in want.items():
            pos = cube.get("position")
            if pos is None or name not in got:
                continue
            compared += 1
            worst = max(worst, math.dist(pos, got[name]))
    # ⛔ THE TOLERANCE IS THE RECORDER'S OWN ROUNDING, and nothing else.
    # `_record_flush` writes `round(v, 2)` per axis, so a faithful replay can differ
    # from the file by at most sqrt(2) * 0.005 = 0.00708 px. ⚠ This is NOT a
    # "close enough" fudge: anything above it is a real behaviour change, and the
    # measured 0.0068 sits just under the bound, which is what a pure rounding
    # residual looks like. Loosening this number would be how a regression hides.
    ROUNDING_PX = math.sqrt(2.0) * 0.005
    check("OFF reproduces the RECORDED cube positions",
          compared > 0 and worst <= ROUNDING_PX,
          f"{compared} comparisons, worst {worst:.6f} px "
          f"(recorder rounding bound {ROUNDING_PX:.6f})")

    # --- 2. ON must actually differ ----------------------------------------
    moved, biggest = 0, 0.0
    for a, b in zip(off, on):
        for name in a:
            if name in b:
                d = math.dist(a[name], b[name])
                if d > 1e-9:
                    moved += 1
                biggest = max(biggest, d)
    check("ON changes the object's position (the switch is live)",
          moved > 0, f"{moved} frames differ, largest {biggest:.1f} px")

    # --- 3. no NEW teleports ----------------------------------------------
    # ⚠ The first version of this check compared OFF and ON positions directly and
    # called a 224 px gap a "teleport". It is not: once snap proximity moves to the
    # fingertips a grab can happen at a different FRAME, after which the two
    # trajectories are simply different runs -- comparing them measures divergence,
    # not smoothness. What actually matters is whether the object JUMPS between
    # consecutive frames, so measure that, within each pass.
    def worst_step(passes):
        w = 0.0
        for a, b in zip(passes, passes[1:]):
            for name in a:
                if name in b:
                    w = max(w, math.dist(a[name], b[name]))
        return w

    s_off, s_on = worst_step(off), worst_step(on)
    check("ON introduces no larger frame-to-frame jump than OFF",
          s_on <= max(s_off * 1.5, s_off + 10.0),
          f"worst single-frame step: OFF {s_off:.1f} px, ON {s_on:.1f} px")

    print("=" * 82)
    if _fails:
        print(f"{len(_fails)} CHECK(S) FAILED")
        return 1
    print("ALL CHECKS PASSED -- step 2 is revert-free by measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
