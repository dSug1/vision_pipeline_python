import atexit
import json
import math
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .CubeWindow import CubeWindow
# Palm chirality geometry, SHARED with LiveSnapDebug.py so the sign convention
# cannot drift between them again (§13.6.1). Pure stdlib, no side effects.
from . import owner_remap
from . import palm_geometry
from . import palm_rotation
from . import hand_state
from . import hand_tracks

# Gesture design: Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13
# (proximity snap, open-palm rotate, closed-fist release) — replaces the
# archived pinch-grab design (`PART_ONE.md`'s original §2/§3, kept for
# historical reference). This module owns the per-frame gesture logic;
# `CubeWindow.py` only holds/renders cube state and exposes ownership
# primitives (snap_cube/release_cube/cube_owned_by/unowned_cube_names).
cube_window = CubeWindow()

INDEX_TIP = 8  # MediaPipe's 21-point hand landmark index for the index fingertip

TRACKED_HANDS = ("Left", "Right")

# Hand position (§13.3): palm-center approximation, the centroid of the
# wrist and the four non-thumb MCP joints. More stable than the wrist alone
# (offset from the actual palm) or any single MCP (asymmetric) — this is
# what "hand position" means everywhere below (snap proximity, translation
# target), replacing the archived design's "pinch midpoint".
WRIST = 0
INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 5, 9, 13, 17
HAND_POSITION_LANDMARKS = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

# Translation-pivot fix (§14.1/§14.1.1, 2026-08-01) -- distance-weighted
# live landmark tracking, ported from LiveSnapDebug.py after live
# verification there. Replaces the old zero-offset design (cube center
# forced to exactly equal HAND_POSITION_LANDMARKS' centroid every frame,
# with no grab-time offset) -- see `_compute_grab_weights`'s docstring for
# the mechanism and GESTURE_PIPELINE_SPEC.md §14.1 for the full account,
# including a known, deliberately DEFERRED limitation (the computed point
# swings toward the palm under yaw specifically -- §14.1.1).
THUMB_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP = 4, 12, 16, 20
TRANSLATION_CANDIDATE_LANDMARKS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP,
                                    INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
# Matches LiveSnapDebug.py's verified value -- re-tune together if this
# ever needs adjusting, don't let the two drift apart.
TRANSLATION_EPSILON_PX = 5.0

# Grab radius (open item, `PART_ONE.md` §5 — "likely scaled to cube size",
# still unresolved/tunable): distance from a cube's CENTER, in the same
# pixel units as hand position, within which an unowned cube can be
# snapped. 1.5x cube size as a starting point — verify by feel live and
# adjust here, this is exactly the kind of value the project's own
# discipline says needs live tuning, not a guess kept forever.
GRAB_RADIUS_MULTIPLIER = 1.5

# TODO (§13.4 open question, pending Phase B's Open_Palm/Closed_Fist
# detection): snap should probably be blocked while the hand is
# closed-fist, so a fist passing near an object doesn't accidentally grab it.
# Not yet implemented — proximity is the only condition checked below
# until fist detection exists to gate it.

# Thumb-outward snap rule state (§13.6, direct request, 2026-08-01) — see
# on_hands_frame's docstring for the full rule. `_last_known_thumb_outward`
# persists the most recent reading through frames where a hand isn't
# detected (so a tracking-loss release still has an orientation to
# record); `_thumb_outward_snap_allowed` is the armed/disarmed exception.
_last_known_thumb_outward: Dict[str, bool] = {h: False for h in TRACKED_HANDS}
_thumb_outward_snap_allowed: Dict[str, bool] = {h: False for h in TRACKED_HANDS}

# DR-2 (queue item 2.2, spec M5e): freeze the palm/back sign while the palm is too
# close to edge-on for it to be trustworthy. Per-hand, and SHARED with
# LiveSnapDebug.py via palm_geometry so the two cannot diverge.
#
# What this protects, concretely: the rule-3 line below disarms the snap exception
# on a single thumb-inward reading (`if not thumb_outward: ... = False`). Near
# edge-on the raw sign chatters at up to 765 flips per 1000 frames (spec §0.2), so
# ONE spurious flip mid-crossing silently revokes the exception. Freezing through
# the band removes that.
#
# Measured before shipping (A10): improved 2 of 10 ground-truth streams, worsened
# NONE, and did nothing at all on both chirality controls. See spec §0.11.
_palm_facing_trackers: Dict[str, palm_geometry.PalmFacingTracker] = {
    h: palm_geometry.PalmFacingTracker() for h in TRACKED_HANDS
}

# ⭐ D1 (2026-08-21): the client-side `HandState.quality` subset --
# `Resources/hand_state.py`, spec §2.1/§2.2. Per hand, and SHARED with
# LiveSnapDebug.py for the same reason DR-2 is (§13.6.1: this module carries a
# deliberate duplicate of the snap/translate logic, and the two diverging has
# already shipped one bug).
#
# ⚠⚠ THIS CHANGES NO BEHAVIOUR TODAY, BY CONSTRUCTION. `BRIDGE_WINDOW_MS` is
# 0.0, so `BRIDGING` is unreachable and `holds_track` is False on exactly the
# frames `_is_detected` was False on before. What it buys is that the release
# decision and the filter resets below now read a tracking STATE rather than a
# raw detection bit, so queue D2 -- hold-and-decay bridging, the row that
# removes D0's measured 98 spurious cube drops -- is a change to one constant
# plus the coasting pose, not a re-plumbing of this function.
_hand_state_trackers: Dict[str, hand_state.HandStateTracker] = {
    h: hand_state.HandStateTracker() for h in TRACKED_HANDS
}

# ⭐ D3 (2026-08-21): RESYNC BLEND. Brought forward to ship WITH D2 rather than
# after it, on D2's own evidence -- `analysis/d2_bridge_ab.py` measured the cube's
# resume displacement at a median 0.59 palm widths, p90 1.95, max 4.99, and
# classified 19 of 58 bridged dropouts as POPs (a resume that moves the cube more
# than a palm width). A bridge with no blend does not remove a defect; it TRADES a
# drop for a jump, and the jump is the §14.1.4 teleport this project has spent
# real effort on. Blending is what makes the trade a win.
#
# Position only. Orientation already converges through `ROTATION_SLERP_FACTOR`'s
# slerp and needs no second mechanism -- adding one would be the rule-stacking the
# owner has asked against.
#
# ⚠ SET TO 0 TO DISABLE, which is what the live A/B's no-blend arm does. The
# blend must justify itself in front of the owner's eye like everything else.
RESYNC_BLEND_FRAMES = 3
_resync_blend_left: Dict[str, int] = {h: 0 for h in TRACKED_HANDS}

# ⛔⛔ T3 WAS BUILT HERE AND REVERTED 2026-08-22. DO NOT REBUILD IT AT THIS LAYER.
#
# The defect is real and measured: cube ownership is keyed to the handedness
# LABEL, and **113 of 205 spurious releases are the owner's own hand reappearing
# under the other label** (`analysis/d2_bridge_ab.py`). A client-side fix was
# built, wired, and live-tested, and it worked -- 5 transfers in one minute.
#
# ⚠ IT WAS ALSO WRONG, AND THE REASON IS STRUCTURAL, NOT A TUNING MISS. It
# recognised "the same hand" by POSITION, and two hands in the same place are
# indistinguishable by position -- which is exactly what OCCLUSION is. Live, it
# handed a held cube to the operator's OTHER PHYSICAL HAND. Measured after the
# fact: 38 of its 49 corpus "saves" occur with a second hand seen within the
# preceding second, i.e. almost the entire benefit sits in the regime where the
# mechanism cannot be trusted, and the safe remainder is 11 of 236 (4.7%).
#
# ⭐ THE FIX BELONGS ONE LAYER DOWN: `HandState` v2 carries a TRACK identity, so
# ownership keys on the track and the whole question disappears. That migration
# is scheduled with 4.1/M9 (spec §2.2). Reconstructing a track id from positions
# on the client is guessing at something the protocol is about to state.
# Full account: `PART_ONE.md`'s T3 row; measurement kept and re-runnable in
# `analysis/t3_relabel_threshold.py`.


def _is_detected(landmarks: List[Tuple[float, float]]) -> bool:
    """A hand not detected this frame arrives as 21 (0, 0) placeholder
    points (see remap_keypoints's expected_count fallback in
    utils_for_remapping_coordinates_and_output_formatting.py) — checking the
    index tip alone mirrors the pre-Part-One check on array[16]/[17]."""
    x, y = landmarks[INDEX_TIP]
    return x != 0 or y != 0


def _hand_position(landmarks: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Palm-center point (see HAND_POSITION_LANDMARKS above), in the same
    mirrored webcam-frame pixel coordinates as the raw landmarks. Still
    used for the snap/grab-radius proximity check (unchanged) -- no longer
    used to drive translation once a cube is held, see
    `_compute_grab_weights`/`_weighted_position` below."""
    xs = [landmarks[i][0] for i in HAND_POSITION_LANDMARKS]
    ys = [landmarks[i][1] for i in HAND_POSITION_LANDMARKS]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _weighted_position(weights: Dict[int, float], landmarks: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Distance-weighted combination of candidate landmarks' CURRENT pixel
    positions (§14.1's translation-pivot fix). Used both to compute the
    grab-time weights' own no-pop residual and to track position live every
    frame after -- same formula, different landmark positions each time."""
    x = sum(w * landmarks[i][0] for i, w in weights.items())
    y = sum(w * landmarks[i][1] for i, w in weights.items())
    return (x, y)


def _compute_grab_weights(object_pos_at_grab: Tuple[float, float], landmarks: List[Tuple[float, float]]) -> Dict[int, float]:
    """Freezes distance-weighted candidate-landmark weights at the moment
    of grab (§14.1.1's chosen, live-verified mechanism): each candidate (5
    fingertips + 4 non-thumb MCPs) is weighted by normalized inverse
    distance from the object's own position at that instant -- the
    literal, computable version of "the phalanges are locked once the
    object is grabbed." Never recomputed during the hold; the caller also
    adds a `grab_residual_offset` (object_pos_at_grab minus this function's
    own weighted combination at grab) every frame after, since
    inverse-distance weighting doesn't interpolate exactly through the
    query point. Ported verbatim from LiveSnapDebug.py after live
    verification there -- do not re-derive independently if this needs
    touching again, keep the two in sync."""
    raw = {i: 1.0 / (math.hypot(object_pos_at_grab[0] - landmarks[i][0],
                                 object_pos_at_grab[1] - landmarks[i][1]) + TRANSLATION_EPSILON_PX)
           for i in TRANSLATION_CANDIDATE_LANDMARKS}
    total = sum(raw.values())
    return {i: w / total for i, w in raw.items()}


def _is_thumb_outward(landmarks: List[Tuple[float, float]], handedness: str) -> bool:
    """True when the hand is oriented with the thumb outward (back of hand
    facing the camera) — GESTURE_PIPELINE_SPEC.md §13.6.

    **Delegates to `Resources/palm_geometry.py`, which is SHARED with
    `LiveSnapDebug.py`** (queue item 1.2, 2026-08-03). This function previously
    carried its own copy of the formula, hand-synced with the debug tool's copy —
    which is exactly how the convention drifted into the production-only inversion
    of 2026-08-01 (§13.6.1). Same fix already applied to the identity tracker (N6).
    Do NOT reinline the maths here."""
    return palm_geometry.is_thumb_outward(landmarks, handedness)


def _edge_on_measure(landmarks: List[Tuple[float, float]]) -> float:
    """0..1, how far the palm is from edge-on — the magnitude `_is_thumb_outward`
    used to discard (M5a, queue item 1.2). 0 = edge-on, where the palm/back sign is
    a coin flip; 1 = knuckle row square to the camera.

    Not yet consumed by any gesture rule: DR-2 (item 2.2) is what will gate on it.
    Exposed now because it is the observability signal M4/M6 need, and because
    recovering it costs one division."""
    return palm_geometry.edge_on_measure(landmarks)


def _top_left_for_center(center: Tuple[float, float], size: int) -> Tuple[float, float]:
    """CubeWindow.set_target_position takes a cube's top-left corner (how
    Cube.position/pygame.Rect represent it), but hand position should drive
    the cube's CENTER, not its corner — convert once here rather than at
    every call site."""
    return (center[0] - size / 2, center[1] - size / 2)


# ⭐⭐ OWNERSHIP KEYS ON THE STABLE TRACK ID, NOT THE HANDEDNESS LABEL
# (queue 4.1 / T3, 2026-08-22). The label is not an identity: it flips, and
# **113 of 205 measured spurious cube releases** were exactly that flip
# orphaning a held cube -- larger than true dropouts (83).
#
# ⛔ A client-side repair for this was built, live-tested and REVERTED
# (`git show d4972b5`): it inferred "same hand" from POSITION, and two hands in
# the same place are indistinguishable by position -- which is what OCCLUSION
# is. Live, it handed a held cube to the operator's other physical hand. The
# generalisable lesson recorded then was "prefer waiting for the layer that
# knows"; this IS that layer.
#
# ⚠ THE FALLBACK IS NOT OPTIONAL. If the wire carries no id (-1 -- an older
# server, or a frame where DR-1 could not resolve identity) ownership degrades
# to the old label key rather than breaking. A cube must never become
# unreleasable because an id went missing.
# ⛔⛔ REVERTED 2026-08-22 BY OWNER INSTRUCTION ("it is still full of bugs. Revert.")
#
# `TRACK_OWNERSHIP` switches the WHOLE 4.1 identity migration -- cube ownership
# keyed on the DR-1 track id, and per-hand state following the track -- on or off
# in one place. It is OFF: ownership and per-hand state key on the handedness
# SLOT, exactly as they did before 4.1.
#
# WHY, stated straight: the migration was live-tested five times and the owner hit
# a defect every time -- a stranded cube, a recurrence at 300/450 ms, a forbidden
# back-of-hand grab, a crash, then a returning hand inheriting permission and
# every cube freezing. Each fix was correct about the cause it named and each left
# another hole. ⚠ At the end my instruments reported the session CLEAN (0 rule-3
# violations across 21 relabels, no frozen cube) while the owner was still seeing
# bugs -- so the measurements were not capturing what actually breaks. **A green
# instrument I cannot trust is a reason to stop, not to continue.**
#
# WHAT COMES BACK WITH IT: T3's defect, measured at 113 of 205 spurious releases
# -- a held cube is orphaned when the handedness label flips. ⭐ That is a DROP,
# which the operator can simply re-grab. The migration traded it for FREEZES and
# rule violations, which are worse. Reverting is the better failure.
#
# WHAT IS KEPT, because it is independent and good: `palm_depth.py` (4.1's
# estimator, drives nothing), the DR-1 frame-edge fix, production recording, the
# wire's `hand_tracks` packet (sent, simply unused here), and every harness.
#
# ⭐ TO RE-ENABLE FOR A FUTURE ATTEMPT: set this True. Nothing was deleted. Read
# `PERCEPTION_LAYER_SPEC.md` §2.2.x first -- every defect above is written up
# there with its measurement.
TRACK_OWNERSHIP = False

_hand_track_ids: Dict[str, int] = {h: -1 for h in TRACKED_HANDS}

# ⭐ T3 NARROW REMAP (2026-08-22): cube name -> the DR-1 TRACK id holding it,
# captured at the snap. Ownership itself stays a SLOT NAME, so every consumer is
# untouched; this only lets the owner slot FOLLOW its track when DR-1 swaps the
# two hands between slots. Without it the cube changes PHYSICAL HAND with no
# release, no snap and no rule-3 check -- the recorded back-of-hand steal
# (`2026-08-22_184440_n8_back_steal_b`, f478), and the spurious relabel-releases
# that are 113 of 205 measured drops (T3).
# ⚠ NOT 4.1's migration: the key type does not change and nothing else moves off
# the slot. Mirrors `LiveSnapDebug.CubeState.holder_track` (N6).
_cube_holder_track: Dict[str, int] = {}


def on_hand_tracks_frame(left_id: int, right_id: int) -> None:
    """Store this frame's stable DR-1 track ids. Called from the "hand_tracks"
    packet, which the server sends BEFORE the same frame's "hands" packet."""
    _hand_track_ids["Left"] = int(left_id)
    _hand_track_ids["Right"] = int(right_id)


# ⛔⛔ THE STRANDED-CUBE BUG, AND WHY RELEASE CANNOT USE `_owner_key` (2026-08-22)
#
# Owner report, live: "the cube was indicated as grabbed but did not move at all
# and the free hand could not grab it again."
#
# Root cause, introduced BY the track-id migration itself. The release pass used
# to read `cube_owned_by(_owner_key(handedness))`. When a hand's track ENDS,
# `_hand_track_ids[handedness]` goes to -1, so `_owner_key` degrades to the LABEL
# -- but the cube is owned by an int TRACK ID, so the lookup misses, `continue`
# runs, and the release never fires. Track ids are monotonic and never reused, so
# that cube stays owned by a dead id forever: still drawn with the snap border
# (owner is not None), driven by nothing, and excluded from
# `unowned_cube_names()` so it can never be re-grabbed. All three reported
# symptoms, exactly.
#
# ⚠ The fallback made it worse, not better: it fires precisely when the id is
# missing, which is precisely when we need to find the cube owned by that now
# absent id. Under the OLD label keying this was unreachable.
#
# ⭐ THE FIX: drive release from the CUBES, not from the current frame's owner
# key, and govern each held cube by the tracker of whichever slot its owning
# TRACK is in right now (`_owner_hand_of_cube`, refreshed every frame).
#   - relabel  -> the track moves slot, the governing hand follows it, cube HELD
#   - dropout  -> the track is absent, the LAST governing hand's tracker coasts
#                 (D2's 150 ms) and only then releases -- Phase D preserved
#   - track end-> same path, so the cube is released instead of stranded
_owner_hand_of_cube: Dict[str, str] = {}

# ⛔⛔ SECOND STRAND CAUSE, found on the FIRST recorded PRODUCTION run
# (2026-08-22, `2026-08-22_154426_production_4_1`): cubes stayed owned by an
# absent track for runs of 40 frames (~1.6 s), repeatedly.
#
# ⚠ IT IS NOT "the track ended" -- the hands were still DETECTED. Their track ids
# went to -1 while landmarks kept arriving:
#     f1997  hands=[('Left', 3), ('Right', 2)]  owner=3
#     f1999  hands=[('Left',-1), ('Right',-1)]  owner=3   <- stranded
#
# ⭐ ROOT CAUSE, server-side: `_normalized_to_pixel_coordinates` returns None for
# any landmark outside [0,1] -- i.e. a hand PARTIALLY OUT OF FRAME. One None makes
# `palm_centroid` None, which fails `all(o[0] is not None ...)`, which skips DR-1
# ENTIRELY for that frame, so NO hand gets a trackId and the wire carries -1 for
# both slots. Moving a hand near the frame edge is enough.
#
# The cube is then owned by an int that matches no live key, while its governing
# slot still holds a DETECTED hand -- so `holds_track` is True and the release
# above never fires. Un-driveable and un-regrabbable: the owner's exact report.
#
# ⚠ THIS IS A SAFETY NET, NOT THE ROOT FIX. The root fix is server-side (DR-1
# should survive a partially-out-of-frame hand, e.g. centroid over the VALID
# landmarks) and is a change to measured identity behaviour, so it is the owner's
# call -- see the queue. This bounds the damage meanwhile: a cube may never be
# stranded FOREVER.
#
# ⚠ The threshold is deliberately LONGER than D2's 150 ms coast, so this cannot
# fight Phase D: it only fires well after the bridge has already given up.
# ⭐⭐ OPTION A (owner decision 2026-08-22): ownership DEGRADES, it never breaks.
#
# The defect this replaces: a cube owned by an int track id became UNDRIVEABLE on
# any frame where that id was not published -- frozen, still showing the snap
# border, and excluded from `unowned_cube_names()`. The owner hit it repeatedly:
# "the cubes get ungrabbed but is still marked as grab and no hand can grab it."
# Three layers were added on top of that design (governing hand, absent timer,
# safety net) and EACH had a hole. The fault was the design, not the patches.
#
# Now: while the owning track is missing, the cube keeps being driven by the hand
# in its remembered slot, so it never freezes. Past the window it is RELEASED, so
# it never sticks either. There is no owned-but-frozen state left to fall into.
#
# ⭐ THE WINDOW IS MEASURED, NOT CHOSEN. Pooled over the recordings taken AFTER
# the DR-1 frame-edge fix, every id-gap that occurred while a hand was still in
# view was <= 130 ms (n=32). 250 ms covers 100% with ~2x margin while capping a
# wrong-hand follow at ~6 frames. ⚠ The pre-fix sessions show p90 642 / max 1604
# ms -- do NOT size this off those, they are the out-of-frame None bug that is
# now fixed, and sizing off them would license a half-second of wrong-hand drag.
OWNER_DEGRADE_MS = 250.0
# Kept equal on purpose: the moment we stop driving a cube is the moment we let
# it go. A gap between the two is exactly the frozen-but-owned window this fix
# exists to delete.
OWNER_ABSENT_RELEASE_MS = OWNER_DEGRADE_MS
_owner_absent_since: Dict[str, float] = {}


def _release_stranded_cubes(now_ms: float) -> set:
    """Release any cube whose owning TRACK has been unrepresented too long."""
    live = {tid for tid in _hand_track_ids.values() if tid >= 0}
    released = set()
    for name, cube in list(cube_window.cubes.items()):
        owner = cube.owner
        if owner is None or not isinstance(owner, int):
            _owner_absent_since.pop(name, None)
            continue
        if owner in live:
            _owner_absent_since.pop(name, None)
            continue
        first = _owner_absent_since.setdefault(name, now_ms)
        if now_ms - first >= OWNER_ABSENT_RELEASE_MS:   # == OWNER_DEGRADE_MS
            cube_window.release_cube(name)
            _owner_absent_since.pop(name, None)
            _owner_hand_of_cube.pop(name, None)
            released.add(name)
    return released


def _refresh_cube_owner_hands() -> None:
    """Follow each held cube's owning TRACK to whichever slot holds it now.

    ⚠ Only updates when the track IS visible. When it is not, the last known
    governing hand is deliberately KEPT, because that hand's tracker is what
    implements D2's coast -- clearing it here would release on the first missed
    frame and undo Phase D."""
    id_to_hand = {tid: h for h, tid in _hand_track_ids.items() if tid >= 0}
    for name, cube in cube_window.cubes.items():
        if cube.owner is None:
            _owner_hand_of_cube.pop(name, None)
        elif isinstance(cube.owner, int):
            hand = id_to_hand.get(cube.owner)
            if hand is not None:
                _owner_hand_of_cube[name] = hand
        else:
            _owner_hand_of_cube[name] = cube.owner      # label-fallback owner


def _cube_for_hand(handedness: str, now_ms: float):
    """The cube this hand should drive THIS FRAME, degraded path included.

    1. Normally: the cube whose owner key matches this hand.
    2. DEGRADED: a cube whose owning TRACK is missing this frame, whose remembered
       governing slot is this hand, and whose absence is still inside
       `OWNER_DEGRADE_MS`. It keeps moving with the hand instead of freezing.

    ⚠ Returns None past the window -- the release pass then lets the cube go. A
    cube must never be both owned and undriveable.
    """
    direct = cube_window.cube_owned_by(_owner_key(handedness))
    if direct is not None or not TRACK_OWNERSHIP:
        return direct               # pre-4.1: no degraded path, keys never vanish
    live = {tid for tid in _hand_track_ids.values() if tid >= 0}
    for name, cube in cube_window.cubes.items():
        if not isinstance(cube.owner, int) or cube.owner in live:
            continue
        if _owner_hand_of_cube.get(name) != handedness:
            continue
        first = _owner_absent_since.get(name)
        if first is not None and now_ms - first < OWNER_DEGRADE_MS:
            return name
    return None


def _owner_key(handedness: str):
    if not TRACK_OWNERSHIP:
        return handedness           # pre-4.1: ownership keys on the label

    """The value cube ownership is keyed on for this hand THIS FRAME.

    Returns the stable track id when one is available, else the handedness
    string. ⚠ Never persist the result: it is re-resolved every frame, and that
    is the whole point -- the same physical hand keeps its key across a relabel.
    """
    tid = _hand_track_ids.get(handedness, -1)
    return tid if tid >= 0 else handedness


def _try_snap(handedness: str, hand_pos: Tuple[float, float], exclude=frozenset()) -> Optional[str]:
    """Claims the nearest unowned cube within GRAB_RADIUS of hand_pos, if
    any (skipping names in `exclude` — see on_hands_frame's same-frame
    release/snap ordering note). Returns the claimed cube's name, or None.
    Hands are processed in a fixed order by the caller (Left then Right),
    so two hands can never claim the same cube in the same frame — the
    second hand's check runs after the first's claim is already recorded
    (`PART_ONE.md` §5's same-frame tie-break open item, resolved by
    construction this way).

    Grab radius is scaled to EACH candidate cube's OWN size (2026-08-01,
    now that the two cubes are different sizes — `PART_ONE.md` §5's
    long-open "grab radius likely scaled to object size" item), not a
    single shared value — otherwise the small cube would keep the same
    (comparatively huge) grab radius as the large one."""
    best_name, best_dist = None, None
    for name in cube_window.unowned_cube_names():
        if name in exclude:
            continue
        cube = cube_window.cubes[name]
        grab_radius = cube.size * GRAB_RADIUS_MULTIPLIER
        cx, cy = cube_window.cube_center(name)
        dist = math.hypot(hand_pos[0] - cx, hand_pos[1] - cy)
        if dist <= grab_radius and (best_dist is None or dist <= best_dist):
            best_name, best_dist = name, dist
    if best_name is not None:
        cube_window.snap_cube(best_name, _owner_key(handedness))
        # T3: remember WHICH HAND took it. -1 means no identity this frame --
        # store nothing rather than a sentinel, so the remap simply no-ops.
        _tid = _hand_track_ids.get(handedness, -1)
        if _tid >= 0:
            _cube_holder_track[best_name] = _tid
        else:
            _cube_holder_track.pop(best_name, None)
    return best_name


# --- Rotation: orthonormal-frame -> quaternion -> predictive filter -> slerp
# Ported from LiveSnapDebug.py (2026-08-01) after live-verification there —
# see that file's module-level comments (above CONDITIONING_ALPHA_LOW and
# in _orthonormal_frame's docstring) for the full design history/rationale;
# kept verbatim here rather than re-derived, to not risk reintroducing bugs
# already found and fixed once (two live-caught filter bugs, a chirality
# regression risk, etc.). GESTURE_PIPELINE_SPEC.md §13.7 has the complete
# account, including the still-OPEN TODO: rotation quality remains
# imperfect with the back of the hand facing the camera (reduced, not
# eliminated, by the predictive filter below).
IDENTITY_QUATERNION: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # (w, x, y, z)

# Rotation is UNGATED (confirmed 2026-08-01) — active for any snapped hand
# regardless of pose; Open_Palm detection has no working implementation
# (§13.5), gating can be added later.
ROTATION_SLERP_FACTOR = 0.35  # tune by feel; time-constant math in LiveSnapDebug.py's comment

# Geometric confidence signal thresholds for the predictive filter's
# reliability weighting (see _reliability_alpha) — data-derived in
# LiveSnapDebug.py, see GESTURE_PIPELINE_SPEC.md §13.7 for the full numbers.
CONDITIONING_ALPHA_LOW = 0.015
CONDITIONING_ALPHA_HIGH = 0.06

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]  # (w, x, y, z)


def _reliability_alpha(conditioning_norm: float) -> float:
    """Linear ramp from 0 (fully degenerate -> trust the prediction) to 1
    (well-conditioned -> trust the raw reading) — Ernst & Banks-style
    reliability-weighted cue blending, not a hard accept/reject cutoff."""
    if conditioning_norm <= CONDITIONING_ALPHA_LOW:
        return 0.0
    if conditioning_norm >= CONDITIONING_ALPHA_HIGH:
        return 1.0
    return (conditioning_norm - CONDITIONING_ALPHA_LOW) / (CONDITIONING_ALPHA_HIGH - CONDITIONING_ALPHA_LOW)


def _vec_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _vec_scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _vec_normalize(v: Vec3) -> Vec3:
    n = math.sqrt(_vec_dot(v, v))
    if n < 1e-9:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _orthonormal_frame(wrist: Vec3, index_mcp: Vec3, pinky_mcp: Vec3, middle_mcp: Vec3) -> Tuple[Vec3, Vec3, Vec3, float]:
    """Gram-Schmidt orthonormal frame from a hand's world landmarks: e1
    along index_MCP->pinky_MCP (knuckle-row width axis), e2 the
    wrist->middle_MCP length axis orthogonalized against e1, e3 = e1 x e2.
    Better-conditioned pair than the original wrist-anchored one (fixes a
    pitch-crossing collinearity bug) — see LiveSnapDebug.py's identical
    function for the full data-driven derivation and the chirality-
    preservation verification (do not swap e1's vector order without
    re-verifying chirality the same way, or yaw/roll will invert).
    Returns (e1, e2, e3, conditioning_norm) — the last is the
    pre-normalization length of the orthogonalized e2, fed into
    _reliability_alpha."""
    e1 = _vec_normalize(_vec_sub(pinky_mcp, index_mcp))
    v2 = _vec_sub(middle_mcp, wrist)
    v2_orth = _vec_sub(v2, _vec_scale(e1, _vec_dot(v2, e1)))
    conditioning_norm = math.sqrt(_vec_dot(v2_orth, v2_orth))
    e2 = _vec_normalize(v2_orth)
    e3 = _vec_cross(e1, e2)
    return (e1, e2, e3, conditioning_norm)


def _quat_normalize(q: Quat) -> Quat:
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n < 1e-9:
        return IDENTITY_QUATERNION
    return (w / n, x / n, y / n, z / n)


def _matrix_to_quaternion(cols: Tuple[Vec3, Vec3, Vec3]) -> Quat:
    """Rotation-matrix -> quaternion via Shepperd's method (numerically
    stable across all rotation angles, unlike the naive sqrt(1+trace)
    formula). `cols` = (e1, e2, e3) column vectors."""
    e1, e2, e3 = cols
    m00, m10, m20 = e1
    m01, m11, m21 = e2
    m02, m12, m22 = e3
    trace = m00 + m11 + m22
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        w, x, y, z = 0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        w, x, y, z = (m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        w, x, y, z = (m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        w, x, y, z = (m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s
    return _quat_normalize((w, x, y, z))


def _quat_multiply(q1: Quat, q2: Quat) -> Quat:
    """Hamilton product q1*q2 -- used below as `q2 * conjugate(q1)` to get
    the world-frame rotation that takes orientation q1 to orientation q2."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


def _quat_conjugate(q: Quat) -> Quat:
    """Inverse of a unit quaternion (conjugate == inverse when normalized)."""
    w, x, y, z = q
    return (w, -x, -y, -z)


def _hand_orientation_quaternion(world_landmarks: List[Vec3]) -> Tuple[Quat, float]:
    """Returns (orientation quaternion, conditioning_norm)."""
    e1, e2, e3, conditioning_norm = _orthonormal_frame(
        world_landmarks[WRIST], world_landmarks[INDEX_MCP], world_landmarks[PINKY_MCP], world_landmarks[MIDDLE_MCP]
    )
    return _matrix_to_quaternion((e1, e2, e3)), conditioning_norm


def _quat_slerp(q0: Quat, q1: Quat, t: float) -> Quat:
    """Shortest-path spherical interpolation (negates q1 if the dot product
    is negative -- quaternion double-cover). Falls back to normalized
    linear interpolation when q0/q1 are nearly identical."""
    d = q0[0] * q1[0] + q0[1] * q1[1] + q0[2] * q1[2] + q0[3] * q1[3]
    if d < 0:
        q1 = (-q1[0], -q1[1], -q1[2], -q1[3])
        d = -d
    d = max(-1.0, min(1.0, d))
    if d > 0.9995:
        lerped = tuple(a + t * (b - a) for a, b in zip(q0, q1))
        return _quat_normalize(lerped)
    theta0 = math.acos(d)
    theta = theta0 * t
    q2 = _quat_normalize(tuple(b - a * d for a, b in zip(q0, q1)))
    sin_theta, cos_theta = math.sin(theta), math.cos(theta)
    return tuple(a * cos_theta + b * sin_theta for a, b in zip(q0, q2))


def _make_continuous(q: Quat, reference: Quat) -> Quat:
    """Flip q's sign if needed so it's on the same hemisphere as reference
    (quaternion double-cover) -- must be resolved before quaternion
    ARITHMETIC (multiply/subtract), unlike _quat_slerp which handles this
    internally for its own use."""
    d = q[0] * reference[0] + q[1] * reference[1] + q[2] * reference[2] + q[3] * reference[3]
    return tuple(-c for c in q) if d < 0 else q


class HandOrientationFilter:
    """Per-hand predictive/reliability-weighted orientation filter state.
    `last_fused` is the filter's own running orientation estimate (this
    frame's output, next frame's prediction base); `omega` is the most
    recently observed per-frame rotation delta among accepted/fused frames
    (constant-angular-velocity model). Reset to a fresh instance whenever
    the hand isn't detected, so reacquiring tracking after a gap never
    predicts from a stale reference."""

    def __init__(self):
        self.last_fused: Optional[Quat] = None
        self.omega: Quat = IDENTITY_QUATERNION


def _predictive_filter_step(filt: "HandOrientationFilter", raw_quat: Quat, conditioning_norm: float) -> Quat:
    """Advances `filt` by one frame and returns the fused orientation to
    use as this frame's hand orientation. See GESTURE_PIPELINE_SPEC.md
    §13.7 for the full design rationale and live-test results (a real but
    incomplete improvement — TODO remains open for the back-of-hand pose)."""
    if filt.last_fused is None:
        filt.last_fused = raw_quat
        return raw_quat
    raw_quat = _make_continuous(raw_quat, filt.last_fused)
    predicted = _make_continuous(_quat_multiply(filt.omega, filt.last_fused), filt.last_fused)
    alpha = _reliability_alpha(conditioning_norm)
    fused = _quat_slerp(predicted, raw_quat, alpha)
    filt.omega = _quat_multiply(fused, _quat_conjugate(filt.last_fused))
    filt.last_fused = fused
    return fused


# Per-hand predictive-filter state and the latest world_landmarks received
# via the "hands_world" wire packet (sent BEFORE "hands" each frame, see
# Server.py's SendHandsWorldPacket — so by the time on_hands_frame runs for
# a given frame, that same frame's world landmarks are already stored
# here). None until the first "hands_world" packet arrives after connect.
_hand_orientation_filters: Dict[str, HandOrientationFilter] = {h: HandOrientationFilter() for h in TRACKED_HANDS}
_last_hand_reliability_alpha: Dict[str, float] = {h: 1.0 for h in TRACKED_HANDS}
_latest_world_landmarks: Dict[str, Optional[List[Vec3]]] = {h: None for h in TRACKED_HANDS}

# ⭐ B4 / §16.15, ported to production 2026-08-17 (owner decision). Horn
# least-squares orientation over the FIVE PALM LANDMARKS ONLY.
#
# ⚠⚠ SHIPPED ON DESIGN GROUNDS, NOT ON MEASURED BENEFIT -- state that honestly
# to anyone who reads this later. The balanced blind A/B (6 rounds, takes
# `hvg_r1..r6`) scored horn-palm 4 / shipped 2, p = 0.34, and p95 was 3-3. It is
# NOT measurably better than the Gram-Schmidt frame it replaces; it is not worse
# either, and a least-squares fit over 5 points cannot degenerate the way a
# 3-vector frame can. An EARLIER unbalanced series suggested 5-1 in its favour;
# that was an artifact of a free random draw and is withdrawn.
#
# ⚠ PALM_LANDMARKS, never PALM_AND_TIPS. The fingertip variant fits finger
# motion as hand rotation and scored orientation p95 9.85 -> 27.79 in free play.
# The takes that "validated" it forbade finger movement, which is what hid it.
#
# ⭐ And what it does NOT fix: the ~60 deg orientation jumps are reproduced by
# BOTH estimators to within 1 deg on the same frames, so they live in the
# landmarks, not here. No rotation estimator will remove them -- that is the
# landmark layer's problem (queue T1/T2, items 1.5/1.6/1.7, 5.4).
_hand_rotation = palm_rotation.Horn(palm_rotation.PALM_LANDMARKS, "ref")
_hand_rotation_states: Dict[str, Optional[dict]] = {h: None for h in TRACKED_HANDS}


# ══════════════════════════════════════════════════════════════════════════════
# FINISHING 4.1's MIGRATION: per-hand state follows the TRACK, not the slot
# ══════════════════════════════════════════════════════════════════════════════
# 4.1 moved cube OWNERSHIP onto the track id and left everything above keyed by
# the handedness SLOT. So when two hands cross and the labels swap, a hand
# INHERITS the other's history -- palm/back reading, D2 coast, orientation
# filter, and snap permission. Measured on
# `2026-08-22_163014_optionA_frozen_cube_check`: **4 snaps by a thumb-outward
# hand that GAME_RULES rule 3 forbids**, because the back-of-hand hand landed in
# a slot the palm hand had armed.
#
# ⭐ HOW THIS IS DONE, AND WHY NOT A FULL RE-KEY. The gesture logic below reads
# `[handedness]` in ~40 places. Rewriting all of it would be the largest edit of
# the session, on the day several smaller ones shipped bugs. Instead the dicts
# are RE-BOUND each frame to the state of whichever track is in that slot now,
# and mutated scalars are written back at the end. The logic is untouched; the
# state travels with the hand. Same property, far smaller blast radius.
#
# ⚠ Objects (trackers, filters) are shared BY REFERENCE, so their internal
# mutation lands automatically. Only SCALARS -- and any object the logic
# REPLACES rather than mutates, notably the orientation filter on reset -- need
# writing back. Missing one would silently lose that hand's state each frame.
class _HandBundle:
    """Everything the gesture layer knows about ONE physical hand."""

    __slots__ = ("palm_facing", "tracking", "orientation_filter", "rotation_state",
                 "last_known_thumb_outward", "thumb_outward_snap_allowed",
                 "resync_blend_left", "reliability_alpha")

    def __init__(self):
        self.palm_facing = palm_geometry.PalmFacingTracker()
        self.tracking = hand_state.HandStateTracker()
        self.orientation_filter = HandOrientationFilter()
        self.rotation_state = None
        self.last_known_thumb_outward = False
        self.thumb_outward_snap_allowed = False
        self.resync_blend_left = 0
        self.reliability_alpha = 1.0


_track_registry = hand_tracks.TrackRegistry(_HandBundle)
_bound_bundles: Dict[str, _HandBundle] = {}


def _new_bundle_for(slot: str) -> "_HandBundle":
    """A FRESH bundle for a newly-seen track, carrying CONFIG but never STATE.

    ⛔⛔ THIS DISTINCTION IS THE WHOLE BUG, AND I GOT IT WRONG ONCE ALREADY.
    An earlier version seeded a new track from the slot's CURRENT dict entries.
    That was written to let a harness's injected tracker be adopted, and it
    passed `verify_d1_wiring` -- while re-creating the exact inheritance defect
    this migration exists to remove. Reported live by the owner:

      "the hand exited as palm and came back as back and still could grab the
       cube. Then all the cubes frozed."

    Two failures, one cause:
      1. A hand that leaves and returns is a NEW track. Seeding from the slot
         handed it the previous hand's `thumb_outward_snap_allowed`, so a
         back-of-hand hand could snap -- GAME_RULES rule 3 forbids that.
      2. Worse, the seed copied the tracker OBJECT BY REFERENCE, so two distinct
         tracks mutated ONE `HandStateTracker`. `holds_track` then answered for
         the wrong hand, release never fired, and every cube froze.

    ⭐ So: fresh objects always; copy only CONFIGURATION (the bridge window a
    harness or arm may have set). Never copy a flag, a filter, or a tracker.
    """
    b = _HandBundle()
    b.palm_facing = palm_geometry.PalmFacingTracker()
    template = _hand_state_trackers.get(slot)
    window = getattr(template, "bridge_window_ms", hand_state.BRIDGE_WINDOW_MS)
    b.tracking = hand_state.HandStateTracker(bridge_window_ms=window)
    b.orientation_filter = HandOrientationFilter()
    b.rotation_state = None
    b.last_known_thumb_outward = False
    b.thumb_outward_snap_allowed = False
    b.resync_blend_left = 0
    b.reliability_alpha = 1.0
    return b


def _bind_track_state(now_ms: float) -> None:
    """Point the per-hand dicts at the state of the track now in each slot."""
    if not TRACK_OWNERSHIP:
        return                      # pre-4.1: per-hand state stays slot-keyed

    slots = _track_registry.resolve(dict(_hand_track_ids), now_ms)
    for slot, tid in slots.items():
        # ⚠ A NEW track ADOPTS whatever is currently in its slot rather than
        # getting a default bundle. Harnesses (and D2's own verification) inject
        # configured trackers into these dicts before the first frame; a default
        # bundle silently discarded that and reverted the coast to 0 ms.
        bundle = _track_registry.state(tid, seed=lambda s=slot: _new_bundle_for(s))
        if bundle is None:
            # ⭐ NO TRACK -> LEAVE THE DICTS EXACTLY AS THEY ARE. With no identity
            # there is nothing better to bind, and the per-slot values are the
            # legacy behaviour, which is correct in that case.
            # ⚠ This also keeps the change strictly ADDITIVE: a caller that never
            # publishes track ids (every pre-4.1 harness, and `verify_d1_wiring`,
            # which injects configured trackers into these dicts) behaves exactly
            # as before. An earlier version substituted a default "orphan" bundle
            # here and silently discarded that injection -- D2's coast reverted to
            # 0 ms and cubes released on the first missed frame.
            _bound_bundles.pop(slot, None)
            continue
        _bound_bundles[slot] = bundle
        _palm_facing_trackers[slot] = bundle.palm_facing
        _hand_state_trackers[slot] = bundle.tracking
        _hand_orientation_filters[slot] = bundle.orientation_filter
        _hand_rotation_states[slot] = bundle.rotation_state
        _last_known_thumb_outward[slot] = bundle.last_known_thumb_outward
        _thumb_outward_snap_allowed[slot] = bundle.thumb_outward_snap_allowed
        _resync_blend_left[slot] = bundle.resync_blend_left
        _last_hand_reliability_alpha[slot] = bundle.reliability_alpha


def _writeback_track_state(now_ms: float) -> None:
    """Persist this frame's mutations onto the track they belong to."""
    if not TRACK_OWNERSHIP:
        return

    for slot, bundle in _bound_bundles.items():
        bundle.orientation_filter = _hand_orientation_filters[slot]
        bundle.rotation_state = _hand_rotation_states[slot]
        bundle.last_known_thumb_outward = _last_known_thumb_outward[slot]
        bundle.thumb_outward_snap_allowed = _thumb_outward_snap_allowed[slot]
        bundle.resync_blend_left = _resync_blend_left[slot]
        bundle.reliability_alpha = _last_hand_reliability_alpha[slot]
    _track_registry.evict(now_ms)


# ---------------------------------------------------------------------------
# OPTIONAL SESSION RECORDING (2026-08-22) — production had none, and that was a
# real gap: every debug session could be measured afterwards while production
# could only be described. The stranded-cube bug took three exchanges to pin
# down for exactly that reason.
#
# ⭐ The schema is DELIBERATELY IDENTICAL to `LiveSnapDebug.py --record`, so every
# existing harness (`analysis/t5*`, `t3_ownership_live_ab.py`,
# `t3_stranded_cube_check.py`) reads a production take with no changes.
#
# ⚠ Enabled by ENVIRONMENT VARIABLE, not a CLI flag: production is launched
# PythonApp_Main -> Launcher -> Client, so a flag would need plumbing through
# three processes while an env var is inherited by all of them for free.
#     VISION_RECORD=1                 turn it on
#     VISION_RECORD_TAG=<name>        session folder suffix
#     VISION_RECORD_NOTE=<text>       stored in meta.json
#
# ⚠ Frames are appended AS THEY ARRIVE, not buffered until exit. Production has
# no clean shutdown path here, and a buffered take would be lost whenever the
# window is closed with the X button -- which is how these sessions usually end.
_RECORD_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer"
_rec = {"fh": None, "dir": None, "n": 0, "t0": None, "hands": 0}


def _record_open():
    if _rec["fh"] is not None or os.environ.get("VISION_RECORD") != "1":
        return
    tag = os.environ.get("VISION_RECORD_TAG", "production")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    d = os.path.join(_RECORD_ROOT, "sessions", f"{stamp}_{tag}")
    try:
        os.makedirs(d, exist_ok=True)
        fh = open(os.path.join(d, "raw_landmarks.jsonl"), "w", encoding="utf-8")
    except OSError as e:
        print(f"[record] cannot record, continuing WITHOUT it: {e}")
        os.environ["VISION_RECORD"] = "0"      # do not retry every frame
        return
    _rec.update(fh=fh, dir=d, t0=time.perf_counter())
    print(f"[record] RECORDING -> {d}")
    atexit.register(_record_close)


def _record_close():
    if _rec["fh"] is None:
        return
    try:
        # A row may still be held from the final frame (see `_record_flush`).
        # Dropping it would silently truncate the session by one frame -- exactly
        # the sort of quiet instrument error this recorder exists to eliminate.
        _record_flush()
        _rec["fh"].close()
        elapsed = time.perf_counter() - (_rec["t0"] or time.perf_counter())
        with open(os.path.join(_rec["dir"], "meta.json"), "w", encoding="utf-8") as m:
            json.dump({"sequence": os.environ.get("VISION_RECORD_TAG", "production"),
                       # ⭐ 2 = cubes snapshotted AFTER the frame's logic, matching
                       # the debug recorder, and carrying position + size. ABSENT
                       # (or 1) means the OLD alignment: cubes were captured
                       # before the logic, so a harness pairing hands[i] with
                       # cubes[i] is off by one frame. Check this before comparing
                       # takes across 2026-08-23.
                       "recorder_schema": 2,
                       "source": "HandsTriggeredActions (PRODUCTION, over the socket)",
                       "note": os.environ.get("VISION_RECORD_NOTE", ""),
                       "frames": _rec["n"], "duration_s": round(elapsed, 2),
                       "measured_fps": round(_rec["n"] / elapsed, 2) if elapsed else 0.0,
                       "frames_with_hand": _rec["hands"]}, m, indent=2)
        print(f"[record] saved {_rec['n']} frames ({_rec['hands']} with a hand) "
              f"to {_rec['dir']}")
    except Exception as e:
        print(f"[record] error while closing: {e}")
    finally:
        _rec["fh"] = None


def _record_frame(hands):
    """One line per frame, same shape as the debug recorder's."""
    if _rec["fh"] is None:
        return
    rec_hands = []
    for handedness, landmarks in hands:
        if not _is_detected(landmarks):
            continue
        world = _latest_world_landmarks.get(handedness) or []
        rec_hands.append({
            "handedness": handedness,
            "trackId": int(_hand_track_ids.get(handedness, -1)),
            "landmarks": [[round(x, 2), round(y, 2)] for x, y in landmarks],
            "world_landmarks": [[round(a, 5), round(b, 5), round(c, 5)]
                                for a, b, c in world],
        })
    row = {
        "tCapture": round((time.perf_counter() - _rec["t0"]) * 1000.0, 2),
        "hands": rec_hands,
    }
    # ⭐⭐ HELD, NOT WRITTEN YET. Both the palm/back cue and the cube state this
    # frame produces are computed BELOW, so writing here would record the PREVIOUS
    # frame's answers. `_record_flush()` writes the row at the end of the frame.
    _rec["pending"] = row


def _record_flush():
    """Write the row held by `_record_frame`, now that this frame's cue exists.

    ⭐ WHY THIS EXISTS (owner instruction, 2026-08-22): production recorded no
    `thumb_outward`, so diagnosing a production session meant RECOMPUTING the cue
    -- and a recomputation is a second implementation that can silently disagree
    with the real one. It did, immediately: the first pass over the recorded
    production steal recomputed with a slot-keyed tracker while production was
    running track-aware, and reported the session CLEAN when the owner had just
    watched the defect happen. Record what ran; never re-derive it."""
    if _rec["fh"] is None or _rec.get("pending") is None:
        return
    row = _rec.pop("pending")
    # ⭐⭐ CUBES SNAPSHOT TAKEN HERE -- AFTER this frame's logic, matching the debug
    # recorder (2026-08-23). Until now production captured them BEFORE, so a snap
    # or release during frame i first appeared in frame i+1's row while `hands`
    # came from frame i. ⚠ That one-frame skew is invisible and it fooled a
    # harness the same day: pairing hands[i] with cubes[i] reported 11 phantom
    # "cube held beyond the margin" violations in production that vanished once
    # the rows were realigned. Two recorders with different frame semantics are a
    # trap for every future analysis, so they now agree.
    # ⚠ Takes recorded before 2026-08-23 lack `recorder_schema` in meta.json and
    # carry the OLD alignment -- see `_record_close`.
    # ⭐ POSITION + SIZE are new here too: without them the play-area invariant
    # (U9) could only be checked by replaying a take, i.e. by re-deriving what the
    # tool already knew.
    row["cubes"] = {"production": {
        name: {"owner": c.owner,
               "position": [round(v, 2) for v in c.position],
               "size": c.size,
               "orientation": [round(v, 6) for v in c.orientation]}
        for name, c in cube_window.cubes.items()}}
    for h in row["hands"]:
        slot = h["handedness"]
        tracker = _palm_facing_trackers[slot]
        h["thumb_outward"] = bool(_last_known_thumb_outward[slot])
        # The U8 gate's own state, so a replay can separate "rule 3 refused
        # because the hand was back" from "rule 3 refused because the chirality
        # was still provisional" -- two very different behaviours that look
        # identical from the outside.
        h["chirality_confirmed"] = bool(tracker.chirality_confirmed)
        h["orientation_valid"] = bool(tracker.orientation_valid)
        h["snap_allowed"] = bool(_thumb_outward_snap_allowed[slot])
    _rec["fh"].write(json.dumps(row) + "\n")
    _rec["n"] += 1
    if row["hands"]:
        _rec["hands"] += 1
    if _rec["n"] % 50 == 0:
        _rec["fh"].flush()


def on_hands_world_frame(left_world: List[Tuple[float, float, float]], right_world: List[Tuple[float, float, float]]) -> None:
    """Called once per received "hands_world" packet, storing each hand's
    latest metric world landmarks for on_hands_frame (below) to read when
    the same frame's "hands" packet arrives next. See PythonApp_Main.py's
    dispatch for datatype == "hands_world"."""
    _latest_world_landmarks["Left"] = left_world
    _latest_world_landmarks["Right"] = right_world


def on_hands_frame(left_landmarks: List[Tuple[float, float]], right_landmarks: List[Tuple[float, float]],
                   now_ms: Optional[float] = None) -> None:
    """Called once per received "hands" packet with both hands' full
    21-point landmark lists (mirrored webcam-frame pixel coordinates).

    `now_ms` is optional and exists so a replay harness can drive the D1
    tracking state from a recording's own `tCapture` instead of wall-clock
    time; production leaves it None and gets `time.perf_counter()`.

    Two passes, not one combined per-hand pass — bug found live
    (2026-08-01): releasing and re-snapping in the same per-hand pass let a
    cube instantly "jump" to the other hand the instant the first hand lost
    tracking, whenever the other hand happened to already be within grab
    radius (its snap-check ran immediately after and saw the just-released
    cube as fair game). Fix: release everyone who needs releasing FIRST,
    across both hands, then snap/translate/rotate — and any cube released
    this frame is excluded from THIS frame's snap pass, so the earliest a
    cube can be re-claimed is next frame, never the same tick as its release.

    Thumb-outward snap rule (§13.6, direct request, 2026-08-01): don't snap
    while the hand is thumb-outward (back of hand facing camera) UNLESS the
    hand was already thumb-outward at the moment its currently-held cube
    was last released, AND it hasn't shown thumb-inward since. See the
    module-level `_last_known_thumb_outward`/`_thumb_outward_snap_allowed`
    comment for what each bit of state tracks.

    Rotation (2026-08-01, ported from LiveSnapDebug.py after live
    verification there — GESTURE_PIPELINE_SPEC.md §13.7 has the full
    account): RELATIVE to the hand's orientation at grab time (a cube
    keeps its own orientation at grab, then rotates by however much the
    hand's orientation changes afterward — no pop), fed through a
    predictive/reliability-weighted filter (per-hand `HandOrientationFilter`
    in `_hand_orientation_filters`) before the relative-delta math, then
    slerped into the cube's displayed orientation. The filter runs for
    EVERY detected hand every frame, regardless of whether it currently
    holds a cube (matching LiveSnapDebug.py exactly) -- this keeps its
    angular-velocity estimate warm, so a grab that happens to land right
    before a noisy stretch still has a useful prediction to fall back on,
    rather than starting cold. Skipped for a hand this frame if its world
    landmarks haven't arrived yet (only expected very briefly after
    connecting, since "hands_world" is sent every frame)."""
    hands = (("Left", left_landmarks), ("Right", right_landmarks))

    # Optional session recording (VISION_RECORD=1). Opened lazily on the first
    # frame so a run without it pays nothing. Recorded BEFORE this frame's
    # gesture logic, so the row shows the state the logic was about to act on.
    _record_open()
    _record_frame(hands)

    # D1: resolve every hand's tracking state FIRST, before any pass acts on it,
    # so the release pass and the per-hand pass below cannot disagree about
    # whether a hand is present this frame. `time.perf_counter() * 1000.0` is
    # the same clock DR-1's identity tracker is already driven from (N7);
    # `hand_state` never reads a clock itself, so it stays deterministic and
    # golden-vector testable (`analysis/verify_hand_state.py`).
    if now_ms is None:
        now_ms = time.perf_counter() * 1000.0

    # ⭐ BIND FIRST, before anything reads per-hand state. Each slot is pointed at
    # the state of the track currently in it, so a relabel carries the hand's own
    # palm/back reading, coast, filter and snap permission with it instead of
    # handing them to the other hand.
    _bind_track_state(now_ms)

    for handedness, landmarks in hands:
        _hand_state_trackers[handedness].update(_is_detected(landmarks), now_ms)

    # ⭐⭐ T3 NARROW REMAP -- runs BEFORE anything reads `cube.owner`.
    #
    # DR-1 swaps two tracks between slots constantly. Ownership is a slot NAME, so
    # without this the cube silently changes PHYSICAL HAND at that instant: no
    # release, no snap, and rule 3 never consulted -- which is why every ordinary
    # back-of-hand grab is blocked and the recorded steal was not. It also removes
    # the spurious relabel-RELEASE (measured: the cube dropped and was re-grabbed
    # one frame later, with only ONE hand on screen).
    #
    # ⚠ NOT 4.1's migration: ownership REMAINS a slot name, nothing else moves off
    # the slot, and an ABSENT track is a no-op here -- `_release_stranded_cubes`
    # below still owns that case. See `Resources/owner_remap.py`.
    for _name, _cube in cube_window.cubes.items():
        if _cube.owner is None:
            # Clear the holder here rather than at each release SITE: production
            # releases from several places (tracking loss, strand, arbitration),
            # and a forgotten site would leave a stale holder that could re-point
            # a LATER grab of the same cube at the wrong hand.
            _cube_holder_track.pop(_name, None)
            continue
        _remapped = owner_remap.remap_owner(
            _cube.owner, _cube_holder_track.get(_name), _hand_track_ids)
        if _remapped != _cube.owner:
            _cube.owner = _remapped

    released_this_frame = set()
    # Bound the strand FIRST, so a cube owned by a track the wire has stopped
    # representing cannot survive indefinitely (see OWNER_ABSENT_RELEASE_MS).
    released_this_frame |= _release_stranded_cubes(now_ms)
    _refresh_cube_owner_hands()
    for owned_cube, cube in list(cube_window.cubes.items()):
        if cube.owner is None:
            continue
        handedness = _owner_hand_of_cube.get(owned_cube)
        if handedness is None:
            # Owned, but its track has never been seen in any slot -- nothing can
            # govern it, so releasing is the only way it does not strand.
            cube_window.release_cube(owned_cube)
            released_this_frame.add(owned_cube)
            continue
        if not _hand_state_trackers[handedness].holds_track:
            # Tracking lost: release (freeze in place), matching
            # PART_ONE.md §2's existing release-conditions semantics ("or
            # loss of hand tracking... cube frozen in place, ownership
            # cleared").
            #
            # ⭐ D1: `holds_track` is False exactly when `_is_detected` was
            # False, because the bridge window ships at 0. D2 opens that window
            # and this line becomes "release only once the coast is exhausted"
            # with no edit -- which is the whole point of landing the contract
            # first. ⚠ D4 (a GRACE PERIOD before release) is a SEPARATE and
            # currently GATED decision -- it is queue 4.3's M10.7 under another
            # name, deferred by the owner. Do not smuggle it in here.
            cube_window.release_cube(owned_cube)
            released_this_frame.add(owned_cube)
            _thumb_outward_snap_allowed[handedness] = _last_known_thumb_outward[handedness]

    for handedness, landmarks in hands:
        tracking = _hand_state_trackers[handedness]
        if tracking.tracking_state != hand_state.TRACKING:
            # No landmarks this frame, so nothing below can be computed either
            # way. But the STATE RESETS are gated on the track being properly
            # gone, not merely on this frame being a miss:
            #
            # ⚠⚠ D2 DEPENDS ON THIS DISTINCTION AND IT IS THE EASY THING TO GET
            # WRONG. Bridging means "hold the last good pose across a short
            # gap"; wiping the orientation filter, the Horn reference
            # constellation and DR-2's frozen sign on the first missed frame
            # would throw away precisely the state a bridge has to coast on, and
            # the bridge would then resume from a cold start -- a visible pop
            # instead of the drop it replaced. With today's 0 ms window these
            # two conditions coincide exactly, so this is a no-op now and
            # load-bearing the moment the window opens.
            if tracking.tracking_state == hand_state.SUSTAINED_LOST:
                _hand_orientation_filters[handedness] = HandOrientationFilter()  # avoid predicting from a stale reference on reacquire
                _hand_rotation_states[handedness] = None                         # §16.15: never fit against a dead track
                # Same reasoning for DR-2's frozen sign: a value held from before the
                # hand vanished is stale, and the hand may reappear in a different
                # orientation. `_last_known_thumb_outward` deliberately survives this
                # (rule 3 needs an orientation to record at a tracking-loss release);
                # the FROZEN value must not.
                _palm_facing_trackers[handedness].reset()
                _resync_blend_left[handedness] = 0   # D3: a dead track carries no pending blend
            continue
        # DR-2: measured when well-conditioned, frozen while edge-on.
        # `orientation_valid` is False while frozen. ⭐ D1: that contract HAS now
        # landed, so the bit is no longer discarded -- it is recorded on this
        # frame's quality block as `HandState.quality.orientationValid`. Still
        # read by no RULE (that stays a separate, deliberate decision), but it is
        # now available to one rather than being recomputed later from scratch.
        # ⭐ U7: hand the tracker this frame's WORLD landmarks so the chirality
        # correction comes from geometry, not from MediaPipe's handedness label
        # (measured wrong 10.8% of the time, at 0.94 confidence -- see
        # `Claude/HANDEDNESS_LABEL_DEFECT.md`). Read from the SAME slot as this
        # frame's pixel landmarks: "hands_world" is sent immediately BEFORE
        # "hands" every frame, so the two are same-frame consistent by
        # construction. `None` before the first packet arrives -> the tracker
        # falls back to the label, i.e. exactly the old behaviour.
        thumb_outward, _orientation_valid = _palm_facing_trackers[handedness].update(
            landmarks, handedness, _latest_world_landmarks[handedness],
            track_id=_hand_track_ids.get(handedness, -1), now_ms=now_ms
        )
        tracking.set_orientation_valid(_orientation_valid)
        _last_known_thumb_outward[handedness] = thumb_outward
        if not thumb_outward:
            _thumb_outward_snap_allowed[handedness] = False

        hand_pos = _hand_position(landmarks)

        if tracking.reacquired_after_ms > 0.0:
            # ⭐ D2: this frame ends a bridge. Two things happen exactly here.
            #
            # (a) DO NOT EXTRAPOLATE ACROSS A GAP THE FILTER DID NOT OBSERVE.
            #     `omega` is one frame's rotation delta measured BEFORE the hand
            #     vanished, and the predictive step would apply it as though it
            #     were still current. B8 measured every velocity fit losing to
            #     "hold the last value" at every horizon, orientation included,
            #     so the honest resume is a pure hold: zero omega, let the
            #     reliability blend walk back to the measurement.
            # (b) D3's resync blend is armed (see RESYNC_BLEND_FRAMES) -- but
            #     ONLY if this hand is actually holding something. The blend is
            #     consumed by the translation update below, which runs only for a
            #     held cube, so arming it on an empty hand would leave it armed
            #     until the NEXT grab and then blend a grab that never bridged.
            _hand_orientation_filters[handedness].omega = IDENTITY_QUATERNION
            if _cube_for_hand(handedness, now_ms) is not None:
                _resync_blend_left[handedness] = RESYNC_BLEND_FRAMES

        hand_quat_now = None
        world_landmarks = _latest_world_landmarks[handedness]
        if world_landmarks is not None:
            raw_quat, conditioning_norm = _hand_orientation_quaternion(world_landmarks)
            _last_hand_reliability_alpha[handedness] = _reliability_alpha(conditioning_norm)
            hand_quat_now = _predictive_filter_step(
                _hand_orientation_filters[handedness], raw_quat, conditioning_norm
            )
            # §16.15. The filter step above still RUNS -- it keeps its own
            # angular-velocity state warm -- but Horn's fit replaces its output
            # when it succeeds. That is exactly what LiveBlockPredictionDebug
            # measured; do not "simplify" it into an either/or.
            #
            # The reference constellation is frozen ONCE PER HAND TRACK, not per
            # grab, so a cube grabbed later still measures against the same
            # reference. `grab_hand_orientation` below captures whatever this
            # returns at the grab instant, so the cube's delta still starts at
            # identity and there is no pop.
            rs = _hand_rotation_states[handedness]
            if rs is None:
                rs = _hand_rotation.freeze(landmarks, world_landmarks)
                _hand_rotation_states[handedness] = rs
            if rs is not None:
                _d = _hand_rotation.delta(rs, landmarks, world_landmarks)
                if _d is not None:          # None = degenerate fit: keep the filtered value
                    hand_quat_now = _d

        owned_cube = _cube_for_hand(handedness, now_ms)
        if owned_cube is None:
            # ⭐⭐ U8: rule 3 may not act on a PROVISIONAL chirality.
            #
            # `thumb_outward` is computed FROM the chirality, so while a newly
            # entered hand's chirality is unconfirmed the palm/back answer can be
            # confidently WRONG -- not noisy, wrong, because the thumb has not yet
            # cleared the frame edge and MediaPipe hallucinates one. Measured: a
            # back-of-hand hand read as PALM and took a cube rule 3 forbids
            # (`2026-08-22_190955_t3_remap_production_test`, f664, track age 5).
            #
            # ⚠ SUPPRESS, DO NOT GUESS -- the DR-2 pattern. Three cheaper remedies
            # were measured and all failed: conditioning-gating (the bad frames
            # were ABOVE median thickness), falling back to the label (the label
            # is WORSE at entry: 76.8% vs geometry's 89.7%), and temporal voting
            # (the wrong value was stable for 5 consecutive frames).
            #
            # Cost: ~22% of snaps delayed by ~380 ms. Delayed, not refused.
            _chirality_ok = _palm_facing_trackers[handedness].chirality_confirmed
            can_snap = ((not thumb_outward) or _thumb_outward_snap_allowed[handedness]) \
                and _chirality_ok
            if can_snap:
                owned_cube = _try_snap(handedness, hand_pos, exclude=released_this_frame)
                if owned_cube is not None:
                    cube = cube_window.cubes[owned_cube]
                    if hand_quat_now is not None:
                        cube.grab_hand_orientation = hand_quat_now
                        cube.grab_cube_orientation = cube.orientation
                    # Translation-pivot fix (§14.1/§14.1.1): capture the
                    # object's position from its own PRE-EXISTING center --
                    # BEFORE this frame's translation update below touches
                    # it -- so this is genuinely "wherever the cube
                    # visually was," not the hand anchor (today's old
                    # zero-offset design discarded this; no-pop guarantee,
                    # same principle as the orientation baseline above).
                    object_pos_at_grab = cube_window.cube_center(owned_cube)
                    cube.grab_landmark_weights = _compute_grab_weights(object_pos_at_grab, landmarks)
                    weighted_at_grab = _weighted_position(cube.grab_landmark_weights, landmarks)
                    cube.grab_residual_offset = (
                        object_pos_at_grab[0] - weighted_at_grab[0],
                        object_pos_at_grab[1] - weighted_at_grab[1],
                    )
        if owned_cube is not None:
            cube = cube_window.cubes[owned_cube]
            weighted_now = _weighted_position(cube.grab_landmark_weights, landmarks)
            new_center = (
                weighted_now[0] + cube.grab_residual_offset[0],
                weighted_now[1] + cube.grab_residual_offset[1],
            )
            if _resync_blend_left[handedness] > 0:
                # D3: walk the cube back to the hand over a few frames instead of
                # teleporting it there on the first frame after a bridge. `t`
                # rises as the blend runs down (1/3, 1/2, 1 for a 3-frame blend),
                # so the last step lands exactly on the measurement -- no residual
                # offset, and no dependence on how long the blend was.
                t = 1.0 / _resync_blend_left[handedness]
                have = cube_window.cube_center(owned_cube)
                new_center = (have[0] + (new_center[0] - have[0]) * t,
                              have[1] + (new_center[1] - have[1]) * t)
                _resync_blend_left[handedness] -= 1
            cube_window.set_target_position(owned_cube, _top_left_for_center(new_center, cube.size))
            if hand_quat_now is not None:
                cube = cube_window.cubes[owned_cube]
                if cube.grab_hand_orientation is None:
                    # Missed the grab-frame capture above (world landmarks
                    # weren't available yet at that instant) -- capture now
                    # so the delta still starts at identity, no pop.
                    cube.grab_hand_orientation = hand_quat_now
                    cube.grab_cube_orientation = cube.orientation
                delta = _quat_multiply(hand_quat_now, _quat_conjugate(cube.grab_hand_orientation))
                target_quat = _quat_multiply(delta, cube.grab_cube_orientation)
                cube.orientation = _quat_slerp(cube.orientation, target_quat, ROTATION_SLERP_FACTOR)

    # ⚠ WRITE BACK LAST, after every mutation this frame. Skipping it would make
    # the whole rebinding a no-op that silently reset each hand every frame.
    _writeback_track_state(now_ms)

    # ⭐ Now that this frame's palm/back cue and U8 gate state exist, write the
    # recording row held since the top of the frame. See `_record_flush`.
    _record_flush()

    cube_window.pump_and_draw()


def configure_source_resolution(width: int, height: int) -> None:
    """Called once, as soon as the server's "meta" packet arrives, to size
    the cube window to the webcam's actual frame resolution instead of the
    placeholder default it opens with."""
    cube_window.resize((width, height))
