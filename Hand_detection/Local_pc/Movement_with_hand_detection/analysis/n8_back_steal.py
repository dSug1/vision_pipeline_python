"""N8 + rule 3 -- can a BACK-of-hand hand STEAL a cube by occluding the holder?

OWNER REPORT (2026-08-22, live): *"in the debug mode, I can steal a cube which is
grabbed by a palm by occluding the hand with the other hand in the back position:
the back position steals and grabs the cube even though grabbing in back position
should not be allowed"* -- and *"this does not happen in production"*.

--------------------------------------------------------------------------------
WHAT THIS MEASURES, AND WHY IT IS NOT CIRCULAR
--------------------------------------------------------------------------------
The event detected here is an OWNERSHIP TRANSFER, which is a RECORDED FACT: cube
`c` is owned by slot A, then by slot B. That is read from the recording, not
inferred. Only then does it ask what the palm/back cue was for the ACQUIRING hand.

⚠ THE RECORDERS ARE ASYMMETRIC, and it matters here: debug sessions store
`thumb_outward` per hand; production sessions do NOT (they store handedness,
landmarks, world_landmarks, trackId). So for production the cue is RECOMPUTED with
the shipped `PalmFacingTracker` -- the same class both tools call. Every row says
which source it used, and `--validate` cross-checks the recomputation against
debug's recorded values so the production numbers are not trusted blind.

⛔ DO NOT read a zero for production as "it does not happen in production" until
the sessions are shown to CONTAIN the manoeuvre. One camera means the two tools
never run together, so any such comparison is across separate sessions of a
possibly intermittent defect -- which has meant SAMPLING once and a real
divergence three times on this project. Coverage is printed for exactly that
reason.

Run:  .venv/Scripts/python.exe analysis/n8_back_steal.py [--validate]
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import palm_geometry as PG  # noqa: E402

SESSIONS = (r"E:\Python\Recordings for vision_pipeline"
            r"\Recordings_perception_layer\sessions")

# A transfer still counts as a steal if the cube spends up to this many frames
# unowned in between -- release-then-resnap is the very mechanism N8 describes.
GAP_FRAMES = 30
# Slot absent this long -> the track is considered ended, so the recomputed
# tracker resets (mirroring production's SUSTAINED_LOST reset).
ABSENT_RESET = 8


def load(session):
    path = os.path.join(SESSIONS, session, "raw_landmarks.jsonl")
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip()]


def recompute_outward(frames):
    """thumb_outward per (frame, slot), using the SHIPPED tracker."""
    trackers, missing, out = {}, {}, {}
    for i, fr in enumerate(frames):
        seen = set()
        for h in (fr.get("hands") or []):
            slot = h["handedness"]
            seen.add(slot)
            missing[slot] = 0
            if slot not in trackers:
                trackers[slot] = PG.PalmFacingTracker()
            to, _v = trackers[slot].update(
                h["landmarks"], slot, h.get("world_landmarks"))
            out[(i, slot)] = to
        for slot in list(trackers):
            if slot not in seen:
                missing[slot] = missing.get(slot, 0) + 1
                if missing[slot] > ABSENT_RESET:
                    trackers[slot].reset()
    return out


def silent_handovers(frames):
    """⭐⭐ THE ACTUAL DEFECT (found 2026-08-22 from the deliberate steal take).

    A cube keeps its owner SLOT while the TRACK sitting in that slot changes.
    No release, no snap, no rule-3 check -- the cube simply changes PHYSICAL HAND.
    That is why rule 3 blocks every ordinary back-of-hand grab and still lets this
    one through: the gate is never reached.

    ⚠ THIS IS T3, not a rule-3 hole. Cube ownership is keyed on the handedness
    label, which is not an identity; DR-1 swapping two tracks between slots
    therefore hands the cube to the other hand for free.

    ⚠⚠ AND IT IS WHY THIS FILE'S `transfers` COUNT MUST NOT BE READ AS IDENTITY.
    An earlier version of this harness called a slot change (`Left` -> `Right`) a
    transfer between hands. It is not: the same track moves between slots
    constantly. Counting slots as hands is the exact confusion under diagnosis --
    it produced '0 back-steals' on a take the owner had just watched one in."""
    events = []
    prev_owners, prev_tracks = {}, {}
    for i, fr in enumerate(frames):
        tracks = {h["handedness"]: h.get("trackId")
                  for h in (fr.get("hands") or [])}
        outward = {h["handedness"]: h.get("thumb_outward")
                   for h in (fr.get("hands") or [])}
        owners = frame_owners(fr)
        for key, owner in owners.items():
            if not owner or prev_owners.get(key) != owner:
                continue
            was, now = prev_tracks.get(owner), tracks.get(owner)
            if was is None or now is None or was < 0 or now < 0 or was == now:
                continue
            events.append(dict(frame=i, cube=key[1], slot=owner,
                               from_track=was, to_track=now,
                               receiver_back=outward.get(owner)))
        prev_owners, prev_tracks = owners, tracks
    return events


def frame_owners(fr):
    """{(arm, cube): owner} for ONE frame, normalising the TWO recorded schemas.

    ⚠ The corpus contains both, and mixing them up silently mis-reads ownership:
      * per-arm  {"<arm>": {"large": {"owner": ...}, ...}}   (multi-arm rigs)
      * flat     {"large": {"owner": ...}, "small": {...}}   (single-arm takes)
    A flat record is recognised by its VALUES carrying "owner" directly."""
    out = {}
    cubes = fr.get("cubes") or {}
    if not isinstance(cubes, dict):
        return out
    for key, val in cubes.items():
        if not isinstance(val, dict):
            continue
        if "owner" in val:                       # flat schema
            out[("-", key)] = val.get("owner")
        else:                                    # per-arm schema
            for name, c in val.items():
                if isinstance(c, dict):
                    out[(key, name)] = c.get("owner")
    return out


def owners_by_frame(frames):
    """{(arm, cube): [owner per frame]}"""
    per_frame = [frame_owners(fr) for fr in frames]
    keys = set()
    for d in per_frame:
        keys |= set(d)
    return {k: [d.get(k) for d in per_frame] for k in keys}


def analyse(session, validate=False):
    frames = load(session)
    with open(os.path.join(SESSIONS, session, "meta.json")) as f:
        meta = json.load(f)
    recorded = {}
    for i, fr in enumerate(frames):
        for h in (fr.get("hands") or []):
            if "thumb_outward" in h:
                recorded[(i, h["handedness"])] = h["thumb_outward"]
    recomputed = recompute_outward(frames)
    source = "recorded" if recorded else "RECOMPUTED"
    cue = recorded if recorded else recomputed

    agree = disagree = 0
    if recorded and validate:
        for k, v in recorded.items():
            if k in recomputed:
                if recomputed[k] == v:
                    agree += 1
                else:
                    disagree += 1

    series = owners_by_frame(frames)
    transfers, steals_back, snaps_back = [], [], []
    for (arm, name), seq in series.items():
        last_owner, last_idx = None, None
        for i, o in enumerate(seq):
            prev = seq[i - 1] if i else None
            if o and not prev:                      # an acquisition
                to = cue.get((i, o))
                if last_owner is not None and o != last_owner \
                        and last_idx is not None and (i - last_idx) <= GAP_FRAMES:
                    transfers.append((i, name, last_owner, o, to))
                    if to is True:
                        steals_back.append((i, name, last_owner, o))
                elif to is True:
                    snaps_back.append((i, name, o))
            if o:
                last_owner, last_idx = o, i
            elif prev:
                last_idx = i

    # coverage: does this session even CONTAIN the manoeuvre?
    two_hand = sum(1 for fr in frames if len(fr.get("hands") or []) == 2)
    held = sum(1 for _k, seq in series.items() for o in seq if o)
    back_frames = sum(1 for v in cue.values() if v is True)

    return dict(session=session, meta=meta, source=source, frames=len(frames),
                two_hand=two_hand, held=held, back_frames=back_frames,
                transfers=transfers, steals_back=steals_back,
                snaps_back=snaps_back, agree=agree, disagree=disagree,
                silent=silent_handovers(frames))


def main():
    validate = "--validate" in sys.argv
    sessions = []
    for s in sorted(os.listdir(SESSIONS)):
        p = os.path.join(SESSIONS, s, "raw_landmarks.jsonl")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for line in f:
                if line.strip() and json.loads(line).get("cubes"):
                    sessions.append(s)
                    break

    print("=" * 100)
    print("N8 + rule 3 -- BACK-of-hand STEALS. Transfer = a recorded fact;")
    print("               the palm/back cue is recorded (debug) or recomputed (production).")
    print("=" * 100)
    print()
    hdr = ("  %-44s %-11s %6s %6s %7s %7s %7s"
           % ("session", "cue", "2hand", "held", "xfers", "STEALS", "backsnp"))
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    prod_steals = debug_steals = 0
    rows = []
    for s in sessions:
        r = analyse(s, validate)
        rows.append(r)
        is_prod = "production" in (r["meta"].get("sequence") or s)
        n_steal = len(r["steals_back"])
        if is_prod:
            prod_steals += n_steal
        else:
            debug_steals += n_steal
        print("  %-44s %-11s %6d %6d %7d %7s %7d"
              % (s[:44], r["source"], r["two_hand"], r["held"],
                 len(r["transfers"]),
                 ("**%d**" % n_steal) if n_steal else "0",
                 len(r["snaps_back"])))
    print("  " + "-" * (len(hdr) - 2))
    print("  DEBUG-recorded sessions: %d back-steals | PRODUCTION-recorded: %d"
          % (debug_steals, prod_steals))

    if validate:
        a = sum(r["agree"] for r in rows)
        d = sum(r["disagree"] for r in rows)
        print()
        print("  VALIDATION of the recomputation against debug's RECORDED cue:")
        print("    %d agree, %d disagree (%.3f%%)"
              % (a, d, 100.0 * d / (a + d) if (a + d) else 0.0))
        print("    -> this is what licenses reading the RECOMPUTED production rows.")

    print()
    print("-" * 100)
    print("*** SILENT HANDOVERS -- the cube changes PHYSICAL HAND with no snap and")
    print("*** no rule-3 check, because ownership is keyed on the SLOT, not identity.")
    print("*** This is T3. It is why rule 3 blocks ordinary back grabs and misses these.")
    print("-" * 100)
    any_silent = False
    for r in rows:
        for e in r["silent"]:
            any_silent = True
            print("  %-44s f%-6d %-7s slot %-6s t%s -> t%s   receiver BACK=%s%s"
                  % (r["session"][:44], e["frame"], e["cube"], e["slot"],
                     e["from_track"], e["to_track"], e["receiver_back"],
                     "   <== RULE 3 VIOLATED" if e["receiver_back"] is True else ""))
    if not any_silent:
        print("  none in any session carrying track ids")

    print()
    print("-" * 100)
    print("DETAIL -- every back-of-hand acquisition (rule 3 says these must not happen)")
    print("-" * 100)
    for r in rows:
        if not r["steals_back"] and not r["snaps_back"]:
            continue
        print("  %s  [%s cue]" % (r["session"], r["source"]))
        for (i, name, frm, to) in r["steals_back"]:
            print("    frame %-6d %-7s STOLEN from %-6s by %-6s -- acquirer was BACK"
                  % (i, name, frm, to))
        for (i, name, who) in r["snaps_back"][:8]:
            print("    frame %-6d %-7s snapped by %-6s while BACK (not a steal)"
                  % (i, name, who))
        if len(r["snaps_back"]) > 8:
            print("    ... and %d more back-snaps" % (len(r["snaps_back"]) - 8))

    print()
    print("=" * 100)
    print("COVERAGE -- read this BEFORE concluding anything from a zero.")
    print("A session with no two-hand frames or no held cube cannot show the defect.")
    print("=" * 100)
    for r in rows:
        flag = ""
        if r["two_hand"] == 0 or r["held"] == 0 or r["back_frames"] == 0:
            flag = "   <-- CANNOT show it"
        print("  %-44s 2hand=%-6d held=%-6d back-frames=%-6d%s"
              % (r["session"][:44], r["two_hand"], r["held"], r["back_frames"], flag))


if __name__ == "__main__":
    main()
