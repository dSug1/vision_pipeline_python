"""Detects the STRANDED-CUBE defect in a recorded session (4.1 / T3, 2026-08-22).

THE DEFECT
-----------
Owner, live: *"the cube was indicated as grabbed but did not move at all and the
free hand could not grab it again."*

Introduced BY the track-id migration. Release read
`cube_owned_by(_owner_key(handedness))`; when a hand's track ENDS the key
degrades to the handedness LABEL, so an int-keyed cube was never found, `continue`
ran, and the cube stayed owned by a track id that -- ids being monotonic and never
reused -- can never appear again. It renders with the snap border (owner is not
None), follows nothing, and is excluded from `unowned_cube_names()` forever.

WHAT IS MEASURED
-----------------
A STRAND = consecutive frames on which a cube is owned by an INT track id that is
present in NO hand slot. A few such frames are legitimate -- that is exactly D2's
150 ms coast (~4 frames at 25 fps) holding the cube across a brief dropout. A run
far beyond the coast is the bug: nothing will ever reclaim or release it.

⚠ Only INT owners can strand. A string owner is the pre-4.1 label fallback, which
any hand entering that slot re-acquires, so it is reported separately and is not a
strand.

⚠ **Needs a recording whose `cubes` block is stored PER ARM** (takes from
2026-08-22 session 4 onward). Earlier takes stored only `arms[0]`, which in the
ownership rig is the LABEL control -- so the shipped arm's cubes are simply absent
and this script will say so rather than guess.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/t3_stranded_cube_check.py <session>
"""

import json
import os
import sys

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

COAST_FRAMES = 6        # D2's 150 ms at ~25 fps, plus a frame of slack
STRAND_FRAMES = 30      # > ~1.2 s owned by an absent track = not a coast


def load(session):
    rows = []
    with open(os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    session = sys.argv[1]
    if not os.path.isdir(os.path.join(CAPTURE_ROOT, session)):
        print(f"No such session: {session}")
        return 1
    rows = load(session)

    sample = next((r for r in rows if r.get("cubes")), None)
    if sample is None:
        print("This recording stores no cube state at all.")
        return 1
    per_arm = all(isinstance(v, dict) and v and
                  all(isinstance(x, dict) and "owner" in x for x in v.values())
                  for v in sample["cubes"].values())

    print("=" * 78)
    print("STRANDED-CUBE CHECK -- a cube owned by a track that is not present")
    print("=" * 78)
    print(f"  session : {session}   frames: {len(rows)}")
    if not per_arm:
        print()
        print("  !! THIS RECORDING STORES ONLY ONE ARM'S CUBES (pre-2026-08-22-session-4).")
        print("  In the ownership rig arms[0] is the LABEL control, so the SHIPPED")
        print("  arm's cubes are not in the file. This session CANNOT answer the")
        print("  stranding question -- re-record with the current recorder.")
        arms = {"(single, arm 0)": sample["cubes"]}
    else:
        arms = {k: v for k, v in sample["cubes"].items()}
        print(f"  arms    : {', '.join(arms)}")
    print()

    worst = {}
    for arm_key in arms:
        runs, cur = {}, {}
        for r in rows:
            cubes = r.get("cubes") or {}
            block = cubes.get(arm_key, cubes) if per_arm else cubes
            live = {int(h["trackId"]) for h in (r.get("hands") or [])
                    if h.get("trackId") is not None and int(h["trackId"]) >= 0}
            for name, c in (block or {}).items():
                if not isinstance(c, dict):
                    continue
                owner = c.get("owner")
                stranded = isinstance(owner, int) and owner not in live
                if stranded:
                    cur[name] = cur.get(name, 0) + 1
                    runs[name] = max(runs.get(name, 0), cur[name])
                else:
                    cur[name] = 0
        worst[arm_key] = runs

    for arm_key, runs in worst.items():
        print(f"  [{arm_key}]")
        if not runs:
            print("     no cube was ever owned by an absent track  -> no strand")
            continue
        for name, longest in sorted(runs.items()):
            verdict = ("OK (within D2's coast)" if longest <= COAST_FRAMES else
                       "suspicious" if longest < STRAND_FRAMES else
                       "!! STRANDED -- the bug is present")
            print(f"     cube {name:8s} longest run owned-by-absent-track: "
                  f"{longest:4d} frames   {verdict}")
    print()
    print("  A run within the coast is D2 working. A long run is the defect:")
    print("  nothing will reclaim or release that cube for the rest of the session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
