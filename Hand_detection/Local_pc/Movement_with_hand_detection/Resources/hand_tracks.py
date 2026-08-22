"""Per-PHYSICAL-HAND state, keyed by DR-1 track id instead of by handedness slot.

WHY THIS EXISTS — 4.1's migration was half done, and the halves fought
----------------------------------------------------------------------
4.1 moved **cube ownership** onto the stable DR-1 track id. It left every other
per-hand thing keyed by the handedness SLOT:

    _last_known_thumb_outward   _thumb_outward_snap_allowed   _palm_facing_trackers
    _hand_state_trackers        _hand_orientation_filters     _hand_rotation_states
    _resync_blend_left          _last_hand_reliability_alpha

So when two hands cross and their labels swap, a hand **inherits the other hand's
history**: its palm/back reading, its D2 coast, its orientation filter, and its
snap permission. Measured on `2026-08-22_163014_optionA_frozen_cube_check`:
**4 snaps by a thumb-outward hand that GAME_RULES rule 3 forbids** — the
back-of-hand hand landed in a slot the palm hand had armed. ⚠ That is the T3
defect again, in different state; fixing ownership alone could not fix it.

⭐ **AND THE COMPENSATING MACHINERY WAS THE SYMPTOM.** `_owner_hand_of_cube`,
`_owner_absent_since` and the degrade window existed only to bridge "ownership is
track-keyed but its coast is slot-keyed". Once a track owns its OWN tracking
state, that bridge is unnecessary: the coast travels with the hand automatically.
**Finishing the migration removes code rather than adding more.**

WHAT IS SHARED HERE, AND WHAT IS NOT
-------------------------------------
Shared: the slot<->track RESOLUTION — the part that must never diverge between
production and the debug tool. Not shared: what the per-hand state *contains*,
which each tool supplies through `factory`. That keeps this module free of
pygame/mediapipe/filter dependencies so it stays portable (U3) and testable.

⚠ Pre-existing and NOT addressed here: `HandOrientationFilter` and
`_predictive_filter_step` are still COPIES in both tools (N6 violation predating
4.1). Recorded so it is not mistaken for something this module fixed.

THE ONE SUBTLETY: a slot with no published id
----------------------------------------------
DR-1 does not always publish an id (a detection that started no track, or a frame
it could not resolve). Rather than fall back to the slot — which is the very bug
being fixed — the slot REMEMBERS its last track for `SLOT_MEMORY_MS`.

⭐ That window is MEASURED, not chosen: over the recordings taken after the DR-1
frame-edge fix, every id-gap seen while a hand was still in view was **<= 130 ms
(n=32)**. 250 ms covers 100% with ~2x margin and caps a wrong-hand association at
~6 frames. ⚠ Do NOT size it off the pre-fix sessions (p90 642 ms, max 1604 ms):
those are the out-of-frame `None` defect, now fixed, and sizing off them would
license half a second of wrong-hand state.

Stdlib only, numpy-free, CLOCK-FREE (`now_ms` is injected) — the port contract,
same as `hand_state.py` / `palm_geometry.py`.
Golden vectors: `analysis/verify_hand_tracks.py`.
"""

# How long a slot keeps pointing at its last track while no id is published.
SLOT_MEMORY_MS = 250.0

# How long a track's state survives after the track was last seen. Longer than
# SLOT_MEMORY_MS on purpose: a hand that leaves and returns within a beat should
# find its own filter and palm/back reading, not a cold start.
TRACK_TTL_MS = 1500.0

NO_TRACK = -1


class TrackRegistry:
    """Maps handedness slots to stable track ids, and track ids to state.

    `factory()` builds one fresh per-hand state object; this module never looks
    inside it.
    """

    def __init__(self, factory, slot_memory_ms=SLOT_MEMORY_MS, track_ttl_ms=TRACK_TTL_MS):
        self._factory = factory
        self.slot_memory_ms = slot_memory_ms
        self.track_ttl_ms = track_ttl_ms
        self._states = {}          # track id -> state object
        self._last_seen = {}       # track id -> now_ms
        self._slot_track = {}      # slot -> track id last published there
        self._slot_at = {}         # slot -> when that id was last published
        # diagnostics
        self.remembered_frames = 0
        self.evicted = 0

    # --- resolution ---------------------------------------------------------
    def resolve(self, slot_ids, now_ms):
        """slot -> effective track id (or NO_TRACK).

        `slot_ids` is this frame's wire values, e.g. {"Left": 3, "Right": -1}.
        A slot with no published id keeps its previous track for
        `slot_memory_ms`, then gives up.
        """
        out = {}
        for slot, tid in slot_ids.items():
            if tid is not None and tid >= 0:
                self._slot_track[slot] = tid
                self._slot_at[slot] = now_ms
                self._last_seen[tid] = now_ms
                out[slot] = tid
                continue
            prev = self._slot_track.get(slot)
            at = self._slot_at.get(slot)
            if prev is not None and at is not None and now_ms - at < self.slot_memory_ms:
                self.remembered_frames += 1
                out[slot] = prev
            else:
                self._slot_track.pop(slot, None)
                self._slot_at.pop(slot, None)
                out[slot] = NO_TRACK
        return out

    # --- state --------------------------------------------------------------
    def state(self, track_id, seed=None):
        """Get-or-create the state for a track. None for NO_TRACK.

        `seed` is an optional zero-arg callable used INSTEAD of the default
        factory when this track is first seen.

        ⚠ It exists for a real reason, found by `verify_d1_wiring.py`: a caller
        may have injected configured objects (a `HandStateTracker` with a custom
        bridge window, say) into its own per-slot dicts before the first frame.
        Handing a brand-new track a DEFAULT bundle silently discarded that
        configuration -- D2's coast reverted to 0 ms and cubes released on the
        first missed frame. Seeding lets a new track ADOPT whatever is already in
        the slot it appeared in.
        """
        if track_id is None or track_id < 0:
            return None
        st = self._states.get(track_id)
        if st is None:
            st = (seed or self._factory)()
            self._states[track_id] = st
        return st

    def known(self, track_id):
        """True if this track currently has state. ⚠ Does NOT create it —
        use this when asking 'is this owner still around?', so merely asking
        cannot resurrect a dead track."""
        return track_id in self._states

    def seen_ms_ago(self, track_id, now_ms):
        at = self._last_seen.get(track_id)
        return None if at is None else now_ms - at

    def evict(self, now_ms):
        """Drop state for tracks not seen within the TTL. Returns the ids dropped.

        ⚠ Track ids are monotonic and never reused, so this is about memory and
        about answering 'is that owner gone for good?', never about stale state
        being mistaken for a new hand.
        """
        dead = [t for t, at in self._last_seen.items()
                if now_ms - at >= self.track_ttl_ms]
        for t in dead:
            self._states.pop(t, None)
            self._last_seen.pop(t, None)
            self.evicted += 1
        return dead

    def live_ids(self):
        return set(self._states)

    def reset(self):
        self._states.clear()
        self._last_seen.clear()
        self._slot_track.clear()
        self._slot_at.clear()
