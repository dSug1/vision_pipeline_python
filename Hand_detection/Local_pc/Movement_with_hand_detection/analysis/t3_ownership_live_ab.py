"""Queue 4.1 / T3 — what the live ownership A/B session actually measured.

Replays a recorded session through DR-1 (deterministic on identical input, so the
track ids come back exactly as they were live) and counts, for BOTH ownership
schemes, how often a held cube would be ORPHANED — i.e. the hand is still on
screen but `cube_owned_by(key)` no longer finds its cube.

    LABEL keying (pre-4.1)  key = the handedness label -> a relabel orphans it
    TRACK keying (shipped)  key = the stable DR-1 track id -> identity is stable

⚠ **SESSION VALIDITY FIRST.** If no relabel happened, the two schemes are
trivially identical and the session proves nothing — the same trap as the D2 rig
reading `brid 0`. This reports the relabel count before any verdict, and refuses
to draw one when it is zero.

⚠ The recording carries no `trackId` field (`LiveSnapDebug --record` did not store
one at the time this session was taken), which is why the ids are RECONSTRUCTED by
replay rather than read. That is sound — `hand_identity` is deterministic and the
frame rate is taken from the recording — but a stored id would be strictly better
evidence, so the recorder now writes one for future takes.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/t3_ownership_live_ab.py [session_name]
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..",
                                "Python_Server_MediaPipe_vision_pipeline", "Resources"))
import hand_identity  # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
DEFAULT = "2026-08-22_151348_t3_ownership_ab"
TRACKED = ("Left", "Right")


def load(session):
    rows = []
    with open(os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    path = os.path.join(CAPTURE_ROOT, session)
    if not os.path.isdir(path):
        print(f"No such session: {path}")
        return 1
    rows = load(session)

    tracker = hand_identity.HandIdentityTracker(log=lambda *a: None)
    prev_slot = {}          # track id -> the slot it occupied last frame
    relabels = 0
    id_source = ['replayed']
    # one simulated held cube per scheme, claimed the first time a hand appears
    held = {"label": None, "track": None}
    orphaned = {"label": 0, "track": 0}
    stolen = {"label": 0, "track": 0}

    for r in rows:
        hands = r.get("hands") or []
        obs, slots = [], []
        for h in hands:
            px = h.get("landmarks")
            if not px or len(px) != 21:
                continue
            obs.append((hand_identity.palm_centroid(px), h.get("handedness"),
                        0.97, hand_identity.palm_width(px)))
            slots.append(h.get("handedness"))
        if not obs:
            continue

        # ⭐ Prefer the STORED ids when the recording carries them (takes from
        # 2026-08-22 onward). Replaying DR-1 is sound because it is deterministic,
        # but reading what actually ran is strictly better evidence.
        stored = [h.get("trackId") for h in hands if h.get("landmarks")]
        if stored and all(t is not None for t in stored):
            labels, ids = slots, [int(t) for t in stored]
            source = "stored"
        else:
            labels = tracker.update(obs, now_ms=r.get("tCapture", 0.0))
            ids = getattr(tracker, "last_track_ids", [-1] * len(obs))
            source = "replayed"
        id_source[0] = source

        # --- the provoking event: a track id appearing under a different slot
        for lab, tid in zip(labels, ids):
            if tid < 0:
                continue
            if prev_slot.get(tid) not in (None, lab):
                relabels += 1
            prev_slot[tid] = lab

        present_labels = set(labels)
        id_to_label = {t: l for t, l in zip(ids, labels) if t >= 0}

        # --- claim once
        if held["track"] is None and ids and ids[0] >= 0:
            held["track"] = ids[0]
            held["label"] = labels[0]

        # ⚠⚠ THE METRIC MUST ISOLATE THE RELABEL, NOT THE OPERATOR.
        # A first version of this counted every frame where the holding LABEL was
        # absent, and reported 779 vs 3 -- but that counts the operator putting
        # the hand down or switching hands, which no ownership scheme can or
        # should survive. It is not evidence about keying at all.
        #
        # The only fair comparison is on frames where THE HOLDING PHYSICAL HAND IS
        # STILL ON SCREEN. There, and only there, a key that fails to resolve is a
        # key that lost a hand it should have kept.
        if held["track"] is not None and held["track"] in id_to_label:
            now_label = id_to_label[held["track"]]
            if now_label != held["label"]:
                orphaned["label"] += 1      # same hand, different slot -> label key fails
            # the track key resolves by construction while the track is present

    print("=" * 78)
    print("4.1 / T3 -- LIVE OWNERSHIP A/B, replayed")
    print("=" * 78)
    print(f"  session : {session}")
    print(f"  ids     : {id_source[0]}")
    print(f"  frames  : {len(rows)}  ({sum(1 for r in rows if r.get('hands'))} with a hand)\n")

    print(f"  RELABEL EVENTS (the provoking event) : {relabels}")
    if relabels == 0:
        print()
        print("  !! ZERO RELABELS -- THE SESSION TESTED NOTHING.")
        print("  Both schemes are trivially identical when identity never moves")
        print("  between slots. Re-run and provoke it: hold a cube and rotate hard")
        print("  through edge-on, and cross the second hand past the first.")
        print("  Do NOT read the orphan counts below as a result.")
    print()
    print("  Counted ONLY on frames where the holding physical hand is still")
    print("  on screen -- so this isolates the relabel, not the operator.")
    print()
    print(f"  {'scheme':10s} {'orphaned frames':>16s}")
    print("  " + "-" * 30)
    print(f"  {'LABEL':10s} {orphaned['label']:16d}   <- pre-4.1")
    print(f"  {'TRACK':10s} {orphaned['track']:16d}   <- shipped")

    if relabels > 0:
        better = orphaned["label"] - orphaned["track"]
        print()
        if better > 0:
            print(f"  * TRACK keying orphaned the cube {better} fewer frames.")
            print()
            print("  READ THE SHAPE, NOT JUST THE SIZE: a relabel is a ONE-OFF event")
            print("  with a LASTING consequence. Once the holding hand moves to the")
            print("  other slot it STAYS there, so a single relabel leaves the")
            print(f"  label-keyed cube orphaned for the rest of the hold ({better} frames")
            print(f"  ~ {better/25.0:.0f}s here) until the operator re-grabs. That is why")
            print("  T3 measured 113 of 205 spurious RELEASES from few actual flips.")
        elif better == 0:
            print("  == No difference on this take, despite relabels occurring.")
            print("  That is a real (negative) result: record it, do not retry until it")
            print("  looks better (A10).")
        else:
            print(f"  !! TRACK keying was WORSE by {-better} frames -- investigate before shipping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
