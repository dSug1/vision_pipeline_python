"""U5 -- pick D2's coast window from a RECORDING, not by feel (owner instruction).

Reads a `--coast-ab` session (three panels at 150 / 300 / 450 ms, identical in
every other respect, one camera and one detection) and reports, per arm:

    RELEASES    how often a held cube was let go. Should FALL as the window grows
                -- that is the whole point: an occlusion shorter than the coast no
                longer drops the cube.
    HELD-FRAMES how long cubes were held in total. Should RISE.
    STRANDED    longest run owned by a track present in NO slot. Must stay near
                the coast; a long run means the cube stuck to something dead.

⚠⚠ **A RIG THAT ONLY COUNTS DROPS WILL RECOMMEND AN INFINITE COAST.** Fewer
releases is not automatically better: a longer hold keeps a cube attached to a
hand that is no longer there, which is exactly N8 (a cube stolen by an occluding
hand) and also means a cube the operator really released stays stuck. Both
directions are printed together, always, and the verdict names the trade rather
than picking a winner on releases alone.

⚠ Why this exists: hand-crossing gaps measured 402 ms median / 2130 ms p90 on
`2026-08-22_154426_production_4_1`, with **70% beyond the shipped 150 ms**, so the
cube is dropped and re-snapped -- the jump the owner reported.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/u5_coast_ab.py <session>
"""
import json
import os
import sys

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"


def main():
    if len(sys.argv) < 2:
        print("usage: u5_coast_ab.py <session>")
        return 2
    session = sys.argv[1]
    path = os.path.join(CAPTURE_ROOT, session)
    if not os.path.isdir(path):
        print(f"No such session: {session}")
        return 1
    rows = [json.loads(l) for l in
            open(os.path.join(path, "raw_landmarks.jsonl"), encoding="utf-8") if l.strip()]
    sample = next((r for r in rows if r.get("cubes")), None)
    if not sample:
        print("no cube state recorded")
        return 1
    arms = list(sample["cubes"])
    print("=" * 78)
    print("U5 COAST A/B -- releases vs how long a dead owner is held")
    print("=" * 78)
    print(f"  session: {session}   frames: {len(rows)}")
    print(f"  arms   : {arms}")
    if len(arms) < 2:
        print("\n  !! ONLY ONE ARM STORED -- this session cannot compare anything.")
        print("  (An earlier recorder keyed arms by label+ownership, which COLLIDES")
        print("   when the arms differ only by coast. Re-record with the current one.)")
        return 1
    print()
    print(f"  {'arm':26s} {'releases':>9s} {'held frames':>12s} {'longest dead-owner run':>23s}")
    print("  " + "-" * 74)
    for a in arms:
        rel = held = 0
        prev = {}
        run = {}
        worst = 0
        for r in rows:
            live = {int(h["trackId"]) for h in (r.get("hands") or [])
                    if int(h.get("trackId", -1)) >= 0}
            for name, c in (r["cubes"].get(a) or {}).items():
                o = c.get("owner")
                if prev.get(name) is not None and o is None:
                    rel += 1
                prev[name] = o
                if o is not None:
                    held += 1
                dead = isinstance(o, int) and o not in live
                run[name] = run.get(name, 0) + 1 if dead else 0
                worst = max(worst, run[name])
        print(f"  {a:26s} {rel:9d} {held:12d} {worst:19d} fr")
    print()
    print("  READ BOTH COLUMNS TOGETHER. Releases falling is the intended effect.")
    print("  Held-frames rising far faster than releases fall, or a growing")
    print("  dead-owner run, means the cube is staying attached to a hand that is")
    print("  not there -- N8's stealing window, and cubes that will not let go.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
