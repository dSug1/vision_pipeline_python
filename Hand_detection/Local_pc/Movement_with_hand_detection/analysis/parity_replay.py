"""Replays ONE recording through BOTH implementations and reports the first divergence.

WHY THIS EXISTS
----------------
Owner, repeatedly and correctly: *"I don't face the same issue in the production."*
Every time that has been said this session it has been a real, findable divergence
(§13.6.1's chirality inversion, the mirror route, the missing DR-2 reset). Each was
hunted BY HAND, one at a time, by reading two files side by side. That does not
scale and it has already missed several.

⭐ This drives production's `on_hands_frame` and the debug tool's `update_hands`
from the SAME recorded frames and compares what each believes, per frame:

    cube ownership          who holds what
    thumb_outward           the palm/back reading rule 3 gates on
    snap permission         `thumb_outward_snap_allowed`
    tracking state          holds_track / SUSTAINED_LOST

The FIRST frame where they disagree is the divergence, named and located. No
guessing, no reading two files hoping to spot it.

⚠ It compares BEHAVIOUR, not source. Two implementations can look different and
behave identically (that is fine) or look identical and behave differently (that
is the dangerous case, and only this catches it).

Run from the parent directory:
    .venv/Scripts/python.exe analysis/parity_replay.py <session>
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

from Resources import HandsTriggeredActions as P   # noqa: E402
import LiveSnapDebug as D                          # noqa: E402

HANDS = ("Left", "Right")


def load(session):
    rows = []
    with open(os.path.join(CAPTURE, session, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    if len(sys.argv) < 2:
        print("usage: parity_replay.py <session>")
        return 2
    session = sys.argv[1]
    if not os.path.isdir(os.path.join(CAPTURE, session)):
        print(f"no such session: {session}")
        return 1
    rows = load(session)

    # production drives a real CubeWindow; the debug tool drives its own arm.
    arm = D._make_arm("blend", 640, 480)
    # ⛔⛔ THE SIXTH TIME THE SYMMETRY RULE HAS BITTEN, and the cause of the
    # 2026-08-26 "41 divergences".
    #
    # Production's rotation blend is time-based UNCONDITIONALLY:
    # `_rotation_slerp_factor` returns `1 - exp(-dt/tau)` with tau = 20 ms. The
    # debug tool's arm DEFAULTS to `slerp_mode = "frame"` (the legacy fixed 0.35)
    # and the live tool switches every arm to "time" at startup -- but this harness
    # never did.
    #
    # ⚠ So it compared a 0.918-per-frame blend against a 0.35-per-frame one at
    # 20 fps. Both converge on the same target, so the difference showed only as a
    # TRANSIENT after each rotation change: 3.08 deg at the first grab, decaying
    # over the following frames. Invisible until this harness began comparing
    # orientation on the same day, and it then flipped an OWNERSHIP decision once
    # the grab radius started depending on the object's projected footprint.
    #
    # ⭐ THREE separate harness asymmetries produced one "divergence": no rotation
    # module, no slerp mode, and no orientation comparison to reveal either.
    arm.slerp_mode = "time"
    # ⛔⛔ AND ITS TIME CONSTANT, WHICH IS THE ACTUAL CAUSE. `CubeState` defaults
    # `slerp_tau_ms = 149.0` -- the legacy value, deliberately kept as the dataclass
    # default -- and the live tool overwrites it with `SLERP_TAU_MS` (the owner's
    # 20 ms, settled in `L1`) on every arm at startup. This harness set neither.
    #
    # ⭐ PROVED, not guessed: with the slerp calls instrumented, the two tools'
    # orientation TARGETS were bit-identical (0.0000 deg) on every frame. Only the
    # blend factor differed -- production 0.955, debug 0.341 -- i.e. tau = 20 ms
    # against tau ~120 ms. The cubes were converging on the same answer at
    # different speeds, which is why the "divergence" was a transient that decayed
    # after every rotation change instead of a persistent offset.
    arm.slerp_tau_ms = D.SLERP_TAU_MS
    D.arms_first_panel[0] = arm
    P.configure_source_resolution(640, 480)

    print("=" * 82)
    print("PARITY REPLAY -- same frames into both implementations")
    print("=" * 82)
    print(f"  session: {session}   frames: {len(rows)}\n")

    diffs = []
    for i, r in enumerate(rows):
        hs = r.get("hands") or []
        by = {h["handedness"]: h for h in hs}
        t = r.get("tCapture", i * 40.0)

        # --- production
        left = by.get("Left", {}).get("landmarks") or [(0.0, 0.0)] * 21
        right = by.get("Right", {}).get("landmarks") or [(0.0, 0.0)] * 21
        lw = by.get("Left", {}).get("world_landmarks") or [(0.0, 0.0, 0.0)] * 21
        rw = by.get("Right", {}).get("world_landmarks") or [(0.0, 0.0, 0.0)] * 21
        # ⭐ Feed production the TRACK IDS too, exactly as the live wire does via
        # the `hand_tracks` packet. ⚠ THIS CAUGHT ITS OWN BUG A SECOND TIME: when
        # the palm-facing tracker became track-aware, omitting this made production
        # see -1 forever (so it never reset) while the debug side reset normally --
        # a divergence that existed ONLY in the harness. Whenever either tool gains
        # an input, BOTH sides of this harness must gain it.
        P.on_hand_tracks_frame(by.get("Left", {}).get("trackId", -1),
                               by.get("Right", {}).get("trackId", -1))
        P.on_hands_world_frame(lw, rw)
        P.on_hands_frame(left, right, now_ms=t)

        # --- debug tool
        # ⚠ RECOMPUTE DR-2 here exactly as the live debug tool does, in its main
        # loop, before update_hands. An earlier version of this harness fed the
        # RECORDED thumb_outward instead and reported 8 "divergences" that were
        # purely that asymmetry -- production recomputes, the harness replayed.
        # A parity harness that is not itself symmetric manufactures divergences.
        # ...and the debug tool reads its track ids from a MODULE GLOBAL, which
        # the live tool fills from DR-1 in its main loop. Set it here for the same
        # reason as production's call above: `update_hands` uses it for the T3
        # remap and to stamp `holder_track` at a snap.
        for h in HANDS:
            D._hand_track_ids[h] = (by.get(h) or {}).get("trackId", -1)

        data = {}
        for h in HANDS:
            src = by.get(h)
            if src is None:
                data[h] = None
                continue
            # ⭐ U7: pass world landmarks, exactly as `LiveSnapDebug.py` does at
            # its real call site. ⚠ THIS LINE CAUGHT ITS OWN CLASS OF BUG the day
            # U7 landed: production feeds world landmarks via
            # `on_hands_world_frame` above, so leaving this call at two arguments
            # made the harness report a divergence that existed only in the
            # harness. The symmetry rule in the comment above applies to the
            # ARGUMENTS as well as to the recompute.
            # ⚠ `now_ms=t` for the same symmetry reason as the two arguments
            # above: production gets the frame time via `on_hands_frame(now_ms=t)`,
            # so omitting it here would put the two sides on different clocks and
            # manufacture a divergence. Third time this rule has bitten.
            dr2, _valid = D._palm_facing_trackers[h].update(
                src["landmarks"], h, src["world_landmarks"],
                track_id=src.get("trackId", -1), now_ms=t)
            data[h] = {
                "pixel_landmarks": src["landmarks"],
                "world_landmarks": src["world_landmarks"],
                "thumb_outward": dr2,
                "score": src.get("score", 0.97),
                "raw_handedness": src.get("raw_handedness", h),
            }
        # ⭐ 4.2, and this is the SAME RULE for the FOURTH time: whenever either
        # tool gains an input, BOTH sides of this harness must gain it.
        # Production computes its hand depth inside `on_hands_frame`; the debug
        # tool has it stamped upstream by `_update_snap_depth` (once per frame,
        # because `update_hands` runs per arm). Omitting this line would compare
        # production's 3D snap gate against a 2D one and report a divergence
        # that exists only here.
        D._update_snap_depth(data, (640, 480))
        # ⛔⛔ `rotation=` — THE FIFTH TIME THE SYMMETRY RULE HAS BITTEN, and the
        # worst, because it was invisible for as long as this harness did not
        # compare orientation. Production always fits Horn over the palm; the debug
        # tool only does so when `update_hands` is HANDED a rotation module, and
        # this harness never handed it one. So the debug arm's rotation reference
        # was never frozen (`hand_rotation_states` stayed None) and its cubes were
        # driven by the Gram-Schmidt fallback while production's used Horn.
        #
        # ⚠ It surfaced as a 3.0 deg orientation gap at frame 51 that later flipped
        # an OWNERSHIP decision, once the grab radius started depending on the
        # object's projected footprint. Both symptoms were the harness, not the
        # pipelines. ⭐ `PRODUCTION_ROTATION` is exactly what the live tool passes.
        D.update_hands(arm, data, rotation=D.PRODUCTION_ROTATION, now_ms=t)

        # --- compare
        for h in HANDS:
            # ⛔ `snap_allowed` was compared here until 2026-08-25. Rule 3's
            # back-of-hand snap block was removed (owner, queue F1) and the
            # armed/disarmed state deleted from BOTH tools, so there is nothing
            # left to compare. ⚠ `thumb_outward` itself is still compared below:
            # it remains a real observation in both, and the two must still agree
            # on it even though neither acts on it any more.
            pl = P._last_known_thumb_outward[h]
            dl = arm.last_known_thumb_outward[h]
            if pl != dl:
                diffs.append((i, h, "last_thumb_outward", pl, dl))
        # ⭐⭐ POSITION PARITY -- added 2026-08-26 with `F1` step 2, because until
        # then this harness compared OWNERSHIP and the palm/back reading but never
        # WHERE THE OBJECT ACTUALLY IS. Step 2 moved translation onto the fingertip
        # barycentre in both tools, which is exactly the kind of change that can
        # agree about who holds a cube while disagreeing about where it is drawn.
        # ⚠ Measured EXACT on first run -- 0.0000 px over 3026 samples across two
        # takes -- so the tolerance is zero deliberately. If this ever needs
        # loosening, that is a finding, not a maintenance task.
        for _n, _c in P.cube_window.cubes.items():
            if _n in arm.cubes:
                _d = math.dist(_c.position, arm.cubes[_n].position)
                if _d > 0.0:
                    diffs.append((i, _n, "position", tuple(_c.position),
                                  tuple(arm.cubes[_n].position)))
        # ⭐⭐ ORIENTATION PARITY -- added 2026-08-26, and it found a divergence the
        # DAY it was added. This harness had compared ownership, the palm/back
        # reading and (since step 2) POSITION, but never HOW THE OBJECT IS TURNED.
        #
        # ⛔ It was found the expensive way. Making the grab radius depend on the
        # object's projected FOOTPRINT made the radius orientation-dependent, and a
        # divergence that had been silent since frame 51 of this very take surfaced
        # as an OWNERSHIP disagreement 326 frames later. The two tools had been
        # rotating cubes differently the whole time and nothing was watching.
        # ⭐ The lesson `U6` keeps restating: a quantity no harness compares is a
        # quantity the two pipelines are free to disagree about.
        for _n, _c in P.cube_window.cubes.items():
            if _n not in arm.cubes:
                continue
            _pq, _dq = _c.orientation, arm.cubes[_n].orientation
            # ⛔ COMPARE THE COMPONENTS, NOT THE ANGLE. `2*acos(dot)` is singular at
            # dot = 1: a quaternion whose norm is one ULP off unity yields ~1e-6 deg
            # out of arithmetic alone, so an angle threshold cannot distinguish
            # "identical" from "very slightly different" no matter how it is tuned.
            # ⭐ Exact equality is the honest test and it is achievable -- these are
            # the same operations on the same inputs. The angle is computed only to
            # REPORT a difference, never to detect one.
            if tuple(_pq) != tuple(_dq):
                _dot = abs(sum(a * b for a, b in zip(_pq, _dq)))
                _ang = 2.0 * math.degrees(math.acos(max(-1.0, min(1.0, _dot))))
                diffs.append((i, _n, "orientation_deg", round(_ang, 6), ""))

        pown = {n: c.owner for n, c in P.cube_window.cubes.items()}
        down = {n: c.owner for n, c in arm.cubes.items()}
        if set(pown) == set(down):
            for n in pown:
                if (pown[n] is None) != (down[n] is None):
                    diffs.append((i, n, "ownership", pown[n], down[n]))
        if diffs and len(diffs) > 40:
            break

    if not diffs:
        print("  NO DIVERGENCE -- the two implementations agreed on every frame.")
        print("  (Then the owner's production/debug difference is NOT in this logic:")
        print("   look upstream, at how each obtains landmarks and identity.)")
        return 0

    print(f"  {len(diffs)} DIVERGENCE(S). First 15:\n")
    print(f"  {'frame':>6s} {'what':22s} {'production':>14s} {'debug':>14s}")
    print("  " + "-" * 62)
    for i, what, key, pv, dv in diffs[:15]:
        print(f"  {i:6d} {str(what)+'/'+key:22s} {str(pv):>14s} {str(dv):>14s}")
    first = diffs[0]
    print(f"\n  * FIRST DIVERGENCE at frame {first[0]}: {first[1]}/{first[2]}"
          f"  production={first[3]!r} debug={first[4]!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
