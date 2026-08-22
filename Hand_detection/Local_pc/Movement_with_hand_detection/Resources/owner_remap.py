"""T3 NARROW REMAP -- keep a held cube with the HAND, across a slot relabel.

SHARED by production and the debug tool (N6: shared, never copied). Pure stdlib,
no numpy/pygame, so it is portable by transliteration (U3) and importable by both
without side effects.

--------------------------------------------------------------------------------
THE DEFECT THIS FIXES, MEASURED
--------------------------------------------------------------------------------
Owner, 2026-08-22, live: *"I can steal a cube which is grabbed by a palm by
occluding the hand with the other hand in the back position: the back position
steals and grabs the cube even though grabbing in back position should not be
allowed"*. Recorded deliberately as `2026-08-22_184440_n8_back_steal_b`.

⛔ IT IS NOT A RULE-3 HOLE, and that mis-diagnosis cost a build. Rule 3's gate is
never reached. Cube `large`:

    f407  snapped by slot Left  = track t7 (palm)   <- legitimate
    f453  released
    f471  re-snapped by slot Right = STILL t7       <- a slot rename, not a hand change
    f478  t7 and t8 SWAP SLOTS. owner is the string "Right", so the cube
          passes to t8 -- the BACK-of-hand hand -- with NO release, NO snap
          and NO rule-3 check.

⭐ That is why every ORDINARY back-of-hand grab is correctly blocked and this one
is not: ownership is keyed on the handedness label, which is not an identity, so
DR-1 swapping two tracks between slots hands the cube over for free. This is T3.

--------------------------------------------------------------------------------
⭐⭐ WHY THIS IS NOT 4.1's MIGRATION, WHICH WAS REVERTED
--------------------------------------------------------------------------------
`POSTMORTEM_4_1_IDENTITY_MIGRATION.md` reverted keying ownership on the track id.
Its verdict was NOT that the premise was wrong -- it was that a PARTIAL migration
seams the system: ownership moved onto integer ids while eight other per-hand
fields stayed on slots, and the bridges over that seam (`_owner_key`'s degrade,
`_owner_absent_since`) became the defects.

This module does something deliberately smaller:

  * **Ownership stays a SLOT NAME.** Every existing consumer -- release, drive,
    `unowned_cube_names`, the renderer -- is untouched and still sees a slot.
  * **Nothing else moves.** Per-hand state stays slot-keyed exactly as today, so
    ownership and per-hand state remain CONSISTENT rather than seamed: the cube's
    owner slot is the slot its holding track is in, which is the slot whose
    per-hand state belongs to that track.
  * The only new state is one int per held cube: which track holds it.

So there is no key-type change, no fallback that fires exactly when it is needed
(post-mortem §3.1), and no new-track seeding (§3.5). It is independently
revertible with one flag.

⚠ WHAT IT DOES NOT FIX, so neither is mistaken for a regression:
  * a hand can still STEAL a cube palm-first -- snap is pure proximity (N8 -> B5);
  * the underlying relabel churn stays (T3's cause is upstream, in DR-1);
  * a cube whose holding track ends is handled by the EXISTING coast/release path,
    not here.
"""

# A/B switch. False restores the exact pre-remap behaviour, so the two can be
# compared on a recording rather than argued about (post-mortem rule 6).
OWNER_FOLLOWS_TRACK = True


def slot_of_track(track_ids, tid):
    """Which slot currently holds `tid`, or None if no slot does.

    `track_ids` is {slot: track id}, the same mapping both tools already keep.
    A negative id means "no identity this frame" and never matches -- DR-1
    publishes -1 in exactly that case, and treating -1 as a real id would make
    two unidentified hands look like the same hand."""
    if tid is None or tid < 0:
        return None
    for slot, t in track_ids.items():
        if t == tid and t >= 0:
            return slot
    return None


def remap_owner(current_owner, holder_track, track_ids):
    """-> the slot that should own the cube now.

    Returns `current_owner` unchanged unless the holding TRACK has moved to a
    different slot, in which case the ownership follows it.

    ⚠ Returns `current_owner` when the track is ABSENT rather than releasing or
    clearing. Absence is the existing coast/release path's business, and the 4.1
    post-mortem's worst defect (§3.1) was a fallback that fired precisely when the
    id was missing -- which is exactly when the caller still needed the cube to be
    findable. This function never makes a cube harder to find than it already was."""
    if not OWNER_FOLLOWS_TRACK:
        return current_owner
    if current_owner is None or holder_track is None:
        return current_owner
    slot = slot_of_track(track_ids, holder_track)
    if slot is None:
        return current_owner
    return slot


def remap_all(owners, holder_tracks, track_ids):
    """Batch form: {cube: owner} -> {cube: owner}, applying `remap_owner` to each.

    Convenience so each tool's per-frame loop is one call and the two cannot
    drift in how they iterate."""
    out = {}
    for name, owner in owners.items():
        out[name] = remap_owner(owner, holder_tracks.get(name), track_ids)
    return out
