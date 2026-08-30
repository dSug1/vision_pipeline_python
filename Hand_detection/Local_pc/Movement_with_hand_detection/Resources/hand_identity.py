# -*- coding: utf-8 -*-
"""⭐⭐ `RB4` — WHICH HAND IS THIS? Identity from chirality, held through degeneracy.

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`.
Branch `1.7.42-`.

────────────────────────────────────────────────────────────────────────────────
⭐⭐⭐ WHY THIS IS FOUR SCREENS AND NOT A TRACKER

The old pipeline identified hands with DR-1 TRACK IDS and a slot<->track
resolution layer (`hand_tracks.py`, and `4.1`). ⛔ `4.1` was **built, patched five
times, and REVERTED by the owner**. The machinery around it -- `_owner_hand_of_cube`,
`_owner_absent_since`, the degrade window -- existed only to bridge "ownership is
track-keyed but its coast is slot-keyed".

⭐ `1.7.42` does not need any of it, because `RB2` made **CHIRALITY RELIABLE**:
the palm determinant read the declared hand on **788/788** frames, independent of
facing. A left hand and a right hand are *distinguishable by their own geometry*,
frame by frame, with no history, no association step and nothing to drift.

⚠ MEASURED, and the separation is not marginal:

    palm-side |det|   p5 3.19e-05   median 5.06e-05        <- confident
    back-of-hand      p95 2.57e-07  median 4.77e-08        <- degenerate

**Two orders of magnitude with nothing in between**, so `CONFIDENT_DET` is placed
from data rather than taste.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ AND THE ONE THING THAT MUST NOT HAPPEN: A FLIP

`RB2` measured that the determinant COLLAPSES on a back-of-hand view -- three takes,
sign agreement wandering 57.6 / 88.7 / 58.3%, which is the sign of ~zero. ⛔ If
identity simply read the determinant every frame, a hand turning its back would
**flip identity mid-gesture**, inherit the other hand's state, and produce exactly
the class of defect `T3` and `U8` cost this project weeks of.

⭐ So identity is **HELD** through low confidence: a hand keeps the last identity it
was confident about, and a flip requires the determinant to be confident AND
disagree. That is `U9`'s lesson -- *a trigger cannot enforce an invariant* -- applied
to a label rather than to a gesture.

────────────────────────────────────────────────────────────────────────────────
⚠ WHAT THIS DELIBERATELY DOES NOT SOLVE

* **Two hands of the SAME chirality** (two people, or one hand seen twice). Identity
  collapses to one key and the second hand is refused rather than silently merged.
  ⛔ The game is single-player with two hands; when that stops being true this
  module needs a real association step, and it should be REPLACED, not patched.
* **Re-entry after a long absence.** A hand that leaves and returns is simply
  identified again from its own geometry -- there is no continuity to lose, which is
  the advantage of a per-frame cue over a tracker.

PORT CONTRACT (`CONSTRAINTS` §2): stdlib only, no numpy, CLOCK-FREE -- `now_ms` is
passed in, like `hand_state` and `mate_connector`.
"""
from . import hand_frame

LEFT = "left"
RIGHT = "right"

# ⛔ FROM THE MEASURED DISTRIBUTION, not from taste. Palm-side p5 is 3.19e-05 and
# degenerate back-of-hand p95 is 2.57e-07; this sits an order of magnitude below the
# usable floor and an order above the noise, in a gap with no data in it.
# ⚠ It is an ABSOLUTE threshold on a quantity with units (metres cubed), so a port
# that changes the landmark scale must re-derive it. Stated because a scale-free
# version was tried and is worse: normalising by the palm size divides by a length
# that is ITSELF collapsing in exactly the degenerate case this guards.
CONFIDENT_DET = 3.0e-06

# ⚠ How long a held identity survives without a confident reading. Sized from the
# `RB2` back-of-hand takes: a palm can face away for a long time in normal play, and
# a hand that re-enters is re-identified from geometry anyway -- so this is generous
# on purpose. Forgetting too eagerly is what a tracker does badly; forgetting late
# costs nothing here.
HOLD_MS = 2000.0


class Identity(object):
    """Per-hand identity, keyed by geometry and held through degeneracy.

    ⚠ ONE INSTANCE PER STREAM, not per hand: it has to see both hands in a frame to
    refuse a same-chirality collision, which is the one failure it can detect.
    """

    def __init__(self):
        self._last = {}        # key -> (last confident now_ms)
        # ⛔⛔ SINGLE-HAND ONLY. `_held` is read only when exactly one hand is in
        # frame; see `classify`. It used to be read for ANY count, keyed on the
        # detection's INDEX -- and MediaPipe does not guarantee that ordering, as the
        # comment in `classify` said even while the code depended on it. Two
        # simultaneously-degenerate hands returned in swapped order each inherited the
        # OTHER's identity: the exact flip this module exists to prevent, and
        # invisible to the same-chirality check below because the two keys stay
        # distinct. Found by review 2026-08-30, before this module was ever wired.
        self._held = []

    def reset(self):
        self._last.clear()
        self._held = []

    def classify(self, world_landmarks_list, now_ms, mount=None):
        """Identify every hand in ONE frame. Returns a list of keys, index-aligned
        with the input, each `LEFT`, `RIGHT` or `None` (refused).

        ⛔ WHOLE-FRAME, NOT PER-HAND, and that is the point: two hands claiming the
        same chirality is only visible when both are in view. A per-hand call would
        have to guess, and guessing is what produced the state-inheritance defects.
        """
        n = len(world_landmarks_list)
        if len(self._held) != n:
            # ⚠ The detector's ordering is not stable between frames. A change in
            # count re-identifies everyone from geometry, which is cheap and honest.
            # ⛔ Resetting on a COUNT change is NOT sufficient on its own -- the count
            # can stay at 2 while the ORDER swaps -- which is why `_held` is now read
            # only when `n == 1`.
            self._held = [None] * n

        raw, conf = [], []
        for wl in world_landmarks_list:
            u = hand_frame.to_user_frame(wl, mount=mount)
            det = hand_frame.signed_palm_volume(u)
            if det is None:
                raw.append(None)
                conf.append(0.0)
                continue
            raw.append(RIGHT if hand_frame.is_right_hand(u) else LEFT)
            conf.append(abs(det))

        out = []
        for i in range(n):
            if conf[i] >= CONFIDENT_DET:
                out.append(raw[i])
                self._last[raw[i]] = now_ms
            elif n == 1:
                # ⭐ DEGENERATE, and the ONLY hand in frame: hold what this detection
                # was last confidently called. A flip requires CONFIDENCE and
                # disagreement, never noise.
                # ⭐ With `n == 1` there is exactly one slot, so "this detection" is
                # unambiguous and the index cannot mean a different hand than it did
                # last frame. That is the ONLY case where holding by index is sound.
                held = self._held[0] if self._held else None
                if held is not None and (now_ms - self._last.get(held, -1e18)) <= HOLD_MS:
                    out.append(held)
                else:
                    out.append(None)
            else:
                # ⛔⛔ TWO OR MORE HANDS: DO NOT HOLD BY INDEX. Resolved below by
                # ELIMINATION, or refused. See the note on `_held`.
                out.append(None)

        # ⭐⭐ ELIMINATION -- IDENTITY FOR AN UNCERTAIN HAND WITHOUT ANY HISTORY.
        # With exactly two hands in view and one of them confidently named, the other
        # is the remaining chirality: that is a COUNTING argument, not a temporal one,
        # so it needs no `_held`, no index stability and no clock. It is strictly
        # stronger than the hold it replaces -- a hold can be stale, and this cannot.
        # ⚠ It rests on the module's stated assumption (ONE player, two hands of
        # opposite chirality); two same-chirality hands are refused below and, per the
        # header, are the case that requires REPLACING this module rather than
        # patching it.
        if n == 2:
            unknown = [i for i in range(n) if out[i] is None]
            claimed = {out[i] for i in range(n) if out[i] is not None}
            if len(unknown) == 1:
                free = [k for k in (LEFT, RIGHT) if k not in claimed]
                if len(free) == 1:
                    out[unknown[0]] = free[0]

        # ⛔ A SAME-CHIRALITY COLLISION IS REFUSED, NOT MERGED. Two hands reported as
        # the same hand would share per-hand state, which is the `T3` / `U8` defect
        # class exactly. The LESS confident one loses its identity and the caller
        # must treat `None` as "no identity this frame" -- not as a hand to drop.
        for key in (LEFT, RIGHT):
            idx = [i for i in range(n) if out[i] == key]
            if len(idx) > 1:
                keep = max(idx, key=lambda i: conf[i])
                for i in idx:
                    if i != keep:
                        out[i] = None

        self._held = list(out)
        return out
