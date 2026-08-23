"""U9/4.2 -- READ THE PLAY-AREA INVARIANT STRAIGHT OUT OF A RECORDING.

⭐⭐ NO REPLAY, NO RE-DERIVATION. Every frame's object position, extent and depth
are in the file because the tools wrote what they actually used (recorder schema
2 added position+size, schema 3 added depth_m+projected_size). This harness only
compares them against the boundary. That is the whole point: a re-derivation is a
second implementation of the rule, and on 2026-08-23 a re-derivation reported
**11 phantom violations** that vanished once the recorded rows were read as they
stood.

⚠⚠ AND THE INVARIANT MOVED IN 4.2. It is no longer "inside the window inset by
60 px". The play area is a WORLD-SPACE VOLUME (owner, 2026-08-23), so BOTH the
margin and the object's extent project differently at different depths:

    schema 3 -> margin = focal * 42.5 mm / depth, extent = projected_size
    schema 2 -> margin = EDGE_MARGIN_PX (60), extent = size      [the old rule]

A harness that assumed 60 px and a fixed size would silently pass a schema-3 take
that was actually violating, and fail a legitimate one. The schema stamp is read,
never guessed.

Run from the parent directory (no argument = every session):
    .venv/Scripts/python.exe analysis/verify_play_volume_from_recording.py
    .venv/Scripts/python.exe analysis/verify_play_volume_from_recording.py <substring>
Exit code 0 = the invariant held on every cube-frame of every session checked.
⚠ "no session carried cube rows" exits 1, not 0. A harness that tested nothing
must never report a pass -- that is how the D2 rig looked green for a session it
had never exercised.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Resources"))
import palm_geometry as PG          # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
FRAME = (640, 480)

# ⛔⛔ THIS TOLERANCE IS NOT A FUDGE, AND LEAVING IT OUT COST A FALSE ALARM.
#
# On the first schema-3 PRODUCTION take (`2026-08-23_194406_4_2_zaxis_production_
# check`) this harness reported **361 violations** on a session the owner had just
# watched work correctly. ⭐ The instrument was wrong, again, and this time
# because it ignored the precision of its own input:
#
#     position        rounded to 2 dp by the recorder  -> +/- 0.005 px
#     projected_size  rounded to 2 dp                  -> +/- 0.005 px
#     depth_m         rounded to 4 dp -> margin error  -> ~0.006 px at 0.5 m
#                                                        ------------------
#     worst observed edge error                           0.0115 px
#
# An object pinned EXACTLY on the boundary (which is the correct, intended
# outcome — U9's own evidence quotes "0.0 px slack") therefore rounds a hundredth
# of a pixel outside. 0.05 px is ~4x the observed worst case and still 20x tighter
# than one pixel, and a real escape moves an object by whole pixels.
#
# ⚠ THE GENERAL RULE: a harness must compare at the precision its INPUT carries,
# not at the precision its arithmetic can produce. Tighten this only by making the
# recorder write more digits — never by asserting below what was recorded.
ROUNDING_TOLERANCE_PX = 0.05


def check_session(name):
    """(cube_frames, violations, worst_slack, schema). worst_slack < 0 = outside."""
    d = os.path.join(CAPTURE, name)
    path = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.isfile(path):
        return None

    schema = 1
    meta = os.path.join(d, "meta.json")
    if os.path.isfile(meta):
        try:
            schema = int(json.load(open(meta, encoding="utf-8"))
                         .get("recorder_schema", 1))
        except (ValueError, OSError):
            schema = 1

    focal = PG.focal_px(FRAME)
    n, viol, worst, worst_at = 0, [], None, None
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cubes = row.get("cubes") or {}
            for arm, objs in cubes.items():
                if not isinstance(objs, dict):
                    continue
                for oname, o in objs.items():
                    # ⚠ Older takes wrote a bare owner (or null) per object
                    # rather than a dict. Skipping is right -- those rows carry
                    # no position, so there is nothing to check -- but it must
                    # not be counted as a checked frame either, or the summary
                    # would report a pass over frames it never looked at.
                    if not isinstance(o, dict):
                        continue
                    pos = o.get("position")
                    if pos is None:
                        continue        # schema 1: nothing to check, not a pass
                    # ⭐ RECORDED, not recomputed. `projected_size` is what was
                    # drawn; `size` is only its extent at the resting depth.
                    extent = o.get("projected_size", o.get("size"))
                    depth = o.get("depth_m")
                    if depth is not None and schema >= 3:
                        margin = focal * PG.PLAY_AREA_MARGIN_M / PG.clamp_depth(depth)
                    else:
                        margin = PG.EDGE_MARGIN_PX
                    n += 1
                    # Slack on the tightest of the four edges. Negative = the
                    # object is outside the play area on that edge.
                    slack = min(pos[0] - margin,
                                pos[1] - margin,
                                FRAME[0] - margin - (pos[0] + extent),
                                FRAME[1] - margin - (pos[1] + extent))
                    if worst is None or slack < worst:
                        worst, worst_at = slack, (i, arm, oname)
                    if slack < -ROUNDING_TOLERANCE_PX:
                        viol.append((i, arm, oname, round(slack, 2)))
    return n, viol, worst, worst_at, schema


def report(name):
    r = check_session(name)
    if r is None:
        print(f"  no raw_landmarks.jsonl in {name}")
        return None
    n, viol, worst, worst_at, schema = r
    if n == 0:
        # ⚠ NOT a pass. A session with no cube rows tests nothing -- the same
        # trap as the D2 rig's `brid` staying at 0, and it must say so.
        print(f"  [ -- ] {name}  (schema {schema}: NO cube rows -- nothing tested)")
        return None
    tag = "PASS" if not viol else "FAIL"
    print(f"  [{tag}] {name}")
    print(f"         schema {schema}   cube-frames {n}   violations {len(viol)}"
          f"   closest approach {worst:+.3f} px"
          + (f" (frame {worst_at[0]}, {worst_at[2]})" if worst_at else ""))
    for v in viol[:5]:
        print(f"           frame {v[0]:5d}  {v[1]}/{v[2]}  outside by {-v[3]:.1f} px")
    return not viol


def main():
    if not os.path.isdir(CAPTURE):
        print("capture root not reachable -- run wake_e_drive.py first")
        return 2
    # ⚠ No argument = check EVERY session, not a usage error: this file is named
    # `verify_*` and the project sweeps that glob with no arguments. A usage exit
    # there reads as a failing suite.
    args = sys.argv[1:] or ["--all"]
    sessions = (sorted(os.listdir(CAPTURE)) if args[0] == "--all"
                else [s for s in sorted(os.listdir(CAPTURE)) if args[0] in s])

    print("=" * 84)
    print("PLAY-AREA INVARIANT, READ FROM THE RECORDING (U9 / 4.2)")
    print("=" * 84)
    results = [report(s) for s in sessions]
    tested = [r for r in results if r is not None]

    print()
    if not tested:
        print("NOTHING TESTED -- no session carried cube rows. This is not a pass.")
        return 1
    if all(tested):
        print(f"INVARIANT HELD on every cube-frame of {len(tested)} session(s).")
        return 0
    print(f"VIOLATED in {sum(1 for r in tested if not r)} of {len(tested)} session(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
