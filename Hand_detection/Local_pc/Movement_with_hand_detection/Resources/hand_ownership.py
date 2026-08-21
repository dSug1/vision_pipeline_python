"""Keep a held cube with the HAND, not with the handedness LABEL (queue T3).

THE DEFECT, MEASURED. `analysis/d2_bridge_ab.py` classified every spurious cube
release across 36 takes: of 205, only 83 were true detection dropouts. **113 were
the owner's own hand reappearing under the OTHER handedness label.** Ownership is
keyed by that label (`cube_owned_by("Right")`), so a relabel orphans a held cube
-- and it does so whether DR-1 got it WRONG or got it RIGHT, because a correction
is a relabel too. That made it the single largest cause of cubes dropping for no
reason a player can see, larger than dropouts.

⭐ WHAT THE CLIENT ACTUALLY SEES, and why this needs no protocol change. DR-1
runs server-side, so a relabel arrives as: the owner's slot goes empty, and the
other slot fills with the same physical hand. That is recognisable by POSITION --
the same criterion DR-1 itself resolves identity with -- from data already on the
wire. Same scoping decision as D1 (spec §2.2): client-side subset, no socket
migration. The full v2 wire protocol would carry a track id and make this
unnecessary; until then, this is the honest local reconstruction.

THE THRESHOLD IS MEASURED, NOT CHOSEN (`analysis/t3_relabel_threshold.py`):

    transfer candidates, displacement in palm widths, 57 events
      min 0.01   median 0.11   p90 0.88
      <= 0.25 pw : 70.2%      <= 0.75 pw : 89.5%
      <= 0.50 pw : 86.0%      <= 1.00 pw : 91.2%

⭐ The cluster is essentially finished by 0.5 palm widths -- a hand that "moved"
0.11 palm widths between two consecutive frames IS the same hand, and that tight
cluster is itself the evidence for the relabel reading. Between 0.5 and 1.0 lie
just 3 of 57 events. So the threshold sits at the knee, NOT where it would catch
the most events: past the cluster you are no longer repairing relabels, you are
handing cubes to hands that are somewhere else.

⚠⚠ THE GUARD IS NOT OPTIONAL AND IT IS WHY THIS IS SAFE. A transfer only happens
if the other slot was EMPTY at the moment the owner hand vanished. If a hand was
already tracked there, this is two real hands, and moving a cube between them is
theft, not repair -- exactly the N8 cube-stealing failure, which this row must not
manufacture a new route to. The measurement shows that guard blocking 84 events,
more than it allows: those stay dropped, deliberately.

⚠ SCOPE, stated so it is not mistaken for a full fix: this repairs the
SINGLE-HAND relabel. It does not repair a two-hand SWAP (both hands present,
labels exchanged) -- there the owner's slot never empties, so nothing here fires,
and the cube silently follows the wrong physical hand. That is the §0.4 duplicate
-label case and it remains open.

PORT CONTRACT: stdlib only, no numpy, no side effects, deterministic -- the same
contract as `palm_geometry.py` / `hand_state.py`. Golden vectors before the port
(U3): `analysis/verify_hand_ownership.py`.
"""

# The other handedness. Ownership only ever moves between these two slots.
OTHER_HAND = {"Left": "Right", "Right": "Left"}

# ⭐ Measured, see the module docstring. Palm widths, so it is scale-free and
# survives the hand being nearer or further from the camera -- a pixel threshold
# would mean different things at different depths.
# ⚠ Raising this does not save more cubes; it starts giving them away.
TRANSFER_PALM_WIDTHS = 0.5


def should_transfer(last_seen_centre, last_seen_palm_width, other_centre,
                    other_slot_was_busy, threshold=TRANSFER_PALM_WIDTHS):
    """Should a cube held by a hand that just vanished follow the hand now
    appearing in the OTHER slot?

        last_seen_centre      palm centre (px) the LAST frame the owner was seen
        last_seen_palm_width  palm width (px) at that same frame -- the scale
        other_centre          palm centre (px) of the hand now in the other slot
        other_slot_was_busy   was the other slot ALREADY tracking a hand at the
                              moment the owner vanished? If so: never transfer.

    Returns True only for a hand close enough to be the same physical hand.
    Every missing or degenerate input answers False -- a transfer is an
    affirmative claim about identity, so absence of evidence must never read as
    evidence.
    """
    if other_slot_was_busy:
        return False
    if last_seen_centre is None or other_centre is None:
        return False
    if not last_seen_palm_width or last_seen_palm_width <= 0.0:
        return False
    if threshold <= 0.0:
        return False
    dx = other_centre[0] - last_seen_centre[0]
    dy = other_centre[1] - last_seen_centre[1]
    # math.hypot avoided so the module stays import-free (port contract); the
    # squared comparison is also exact where hypot would round.
    return (dx * dx + dy * dy) <= (threshold * last_seen_palm_width) ** 2


class LastSeen:
    """Per-hand memory of where a hand was the last time it was tracked, and
    whether the other slot was occupied at that instant.

    ⚠ `other_busy` MUST be recorded at the last-seen frame, not read at transfer
    time. By the time the transfer is considered, the other slot is occupied BY
    DEFINITION -- that is what triggers the check -- so reading it then would
    make the guard always true and silently disable it.
    """

    __slots__ = ("centre", "palm_width", "other_busy")

    def __init__(self):
        self.centre = None
        self.palm_width = None
        self.other_busy = False

    def record(self, centre, palm_width, other_busy):
        self.centre = centre
        self.palm_width = palm_width
        self.other_busy = bool(other_busy)

    def clear(self):
        self.centre = None
        self.palm_width = None
        self.other_busy = False
