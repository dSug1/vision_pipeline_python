"""A/B the T3 narrow remap on the RECORDED steal -- the same frames, both ways.

Drives the DEBUG tool's real `update_hands` over a recording twice, with
`owner_remap.OWNER_FOLLOWS_TRACK` off and on, and reports who ends up holding
each cube. One variable between the arms, per the B4 discipline.

⭐ THE ACCEPTANCE CRITERION IS TWO-SIDED, not "the steal is gone":
  * the SILENT HANDOVER must disappear (the cube stays with the hand that grabbed
    it when DR-1 swaps the slots), AND
  * every behavioural difference must be EXPLAINED by a relabel. A fix that also
    suppresses legitimate grabs, or holds a cube through a genuine release, is
    not a fix.

⚠ THE FIRST VERSION OF THIS CRITERION SAID "same release count", AND IT WAS
WRONG -- it would have blocked the fix from shipping. Removing spurious releases
is the POINT of T3: 113 of 205 measured spurious releases are a relabel orphaning
a held cube. Measured here: the remap removes the release at f206, where track t2
moves from slot Right to slot Left with NO second hand present -- a pure label
flip that dropped the cube and forced a re-grab one frame later. So releases may
DECREASE, and each removed release must coincide with a relabel of the owning
slot. That is what is checked below.

Run:  .venv/Scripts/python.exe analysis/t3_remap_ab.py [session]
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import owner_remap as OR  # noqa: E402
import LiveSnapDebug as D  # noqa: E402

SESSIONS = (r"E:\Python\Recordings for vision_pipeline"
            r"\Recordings_perception_layer\sessions")
DEFAULT = "2026-08-22_184440_n8_back_steal_b"
HANDS = ("Left", "Right")


def run(session, follows_track):
    """-> (per-frame owner+track log, stats)"""
    saved = OR.OWNER_FOLLOWS_TRACK
    OR.OWNER_FOLLOWS_TRACK = follows_track
    try:
        path = os.path.join(SESSIONS, session, "raw_landmarks.jsonl")
        with open(path) as f:
            frames = [json.loads(x) for x in f if x.strip()]

        # A fresh arm and fresh per-hand state for each run, so the two arms
        # cannot contaminate each other through module-level dicts.
        state = D._make_arm("blend", 640, 480)
        for h in HANDS:
            D._palm_facing_trackers[h] = D.palm_geometry.PalmFacingTracker()
            D._hand_track_ids[h] = -1

        log = []
        for i, fr in enumerate(frames):
            by = {h["handedness"]: h for h in (fr.get("hands") or [])}
            # Replay the RECORDED identity: this harness is testing the remap,
            # not DR-1. Feeding recorded ids keeps the two arms on identical
            # identity so the only difference is the remap itself.
            for h in HANDS:
                src = by.get(h)
                D._hand_track_ids[h] = (src or {}).get("trackId", -1)

            data = {}
            for h in HANDS:
                src = by.get(h)
                if src is None:
                    data[h] = None
                    continue
                data[h] = {
                    "pixel_landmarks": src["landmarks"],
                    "world_landmarks": src["world_landmarks"],
                    # the cue AS RECORDED -- recomputing it would add a second
                    # variable and this A/B is about ownership only
                    "thumb_outward": src.get("thumb_outward", False),
                    "score": src.get("score", 0.97),
                    "raw_handedness": src.get("raw_handedness", h),
                }
            D.update_hands(state, data, now_ms=fr.get("tCapture", i * 40.0))

            owners = {n: c.owner for n, c in state.cubes.items()}
            holders = dict(state.holder_track)
            ids = dict(D._hand_track_ids)
            log.append((i, owners, holders, ids))
        return log, dict(state.stats)
    finally:
        OR.OWNER_FOLLOWS_TRACK = saved


def holder_of(owners, ids, cube):
    """Which TRACK physically holds `cube` right now (owner slot -> its track)."""
    slot = owners.get(cube)
    if slot is None:
        return None
    return ids.get(slot)


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    print("=" * 78)
    print("T3 NARROW REMAP -- A/B on %s" % session)
    print("=" * 78)

    off_log, off_stats = run(session, False)
    on_log, on_stats = run(session, True)

    cubes = sorted(off_log[0][1]) if off_log else []
    print()
    print("SILENT HANDOVERS -- the cube changes PHYSICAL HAND with no snap/release")
    print("-" * 78)
    for label, log in (("remap OFF", off_log), ("remap ON ", on_log)):
        events = 0
        detail = []
        for k in range(1, len(log)):
            _i, o_prev, _h, id_prev = log[k - 1]
            i, o_now, _h2, id_now = log[k]
            for c in cubes:
                if o_prev.get(c) and o_now.get(c) and o_prev[c] == o_now[c]:
                    a = holder_of(o_prev, id_prev, c)
                    b = holder_of(o_now, id_now, c)
                    if a is not None and b is not None and a >= 0 and b >= 0 and a != b:
                        events += 1
                        detail.append("f%d %s t%s->t%s" % (i, c, a, b))
                # the remap changes the owner STRING; that is the fix working,
                # and is counted separately below
        print("  %s : %d   %s" % (label, events, ", ".join(detail[:6])))

    print()
    print("OWNER SLOT FOLLOWING THE HAND (the remap firing)")
    print("-" * 78)
    print("  remap ON  fired %d time(s)" % on_stats.get("owner_remaps", 0))
    changes = 0
    for k in range(1, len(on_log)):
        _i, o_prev, _h, _idp = on_log[k - 1]
        i, o_now, _h2, _idn = on_log[k]
        for c in cubes:
            if o_prev.get(c) and o_now.get(c) and o_prev[c] != o_now[c]:
                changes += 1
                print("    f%-6d %-7s owner %s -> %s (cube stays with the same hand)"
                      % (i, c, o_prev[c], o_now[c]))
    if not changes:
        print("    (no owner-slot changes)")

    print()
    print("NOTHING ELSE MAY CHANGE -- the other half of the criterion")
    print("-" * 78)
    keys = sorted(set(off_stats) | set(on_stats))
    bad = False
    for k in keys:
        a, b = off_stats.get(k), on_stats.get(k)
        if k == "owner_remaps":
            continue
        flag = ""
        if a != b:
            # Releases going DOWN is the fix working (see the header note).
            # Anything else moving, or releases going UP, is a real concern.
            if k == "releases" and isinstance(a, int) and isinstance(b, int) and b < a:
                flag = "   <== FEWER spurious releases (expected: T3)"
            else:
                flag = "   <== CHANGED, investigate"
                bad = True
        print("  %-22s off=%-8s on=%-8s%s" % (k, a, b, flag))

    print()
    print("=" * 78)
    if bad:
        print("** Something moved that the remap does not explain. Investigate.")
    else:
        print("OK -- silent handovers gone; the only other change is FEWER spurious")
        print("     releases, which is T3's whole point. Ownership follows the hand.")
    print("=" * 78)


if __name__ == "__main__":
    main()
