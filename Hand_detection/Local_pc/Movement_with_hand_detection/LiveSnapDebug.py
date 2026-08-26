import argparse
import json
from datetime import datetime
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Combined single-window debug tool for the new snap/translate gesture set
# (Claude/GESTURE_PIPELINE_SPEC.md §13). Overlays semi-transparent 3D cubes
# directly on the live camera + hand-landmarks feed (one window instead of
# the production split's two -- webcam preview + separate pygame cube
# window) so gesture behavior can be visually verified against the real
# hand position/landmarks in the same frame. Originally meant to be
# deleted once the gesture set was built and verified; kept in active use
# past that point per direct request (2026-08-01) -- it's easier to debug
# with video+landmarks+cube visible together than via production's split
# windows -- to be removed only once final production no longer needs
# this level of visibility. NOT part of the production client/server
# pipeline (`Resources/HandsTriggeredActions.py`/`Resources/CubeWindow.py`,
# which stay independent of this file and of each other's rendering
# choice, same "deliberately independent debug tool" pattern as
# `LiveGestureDebug.py` used for pinch).
#
# Deliberately duplicates (not imports) HandsTriggeredActions.py's small
# snap/translate logic rather than sharing it -- that module's `cube_window`
# is a module-level pygame CubeWindow instantiated at import time (opens a
# real pygame window as a side effect), which this single-OpenCV-window
# tool must not trigger. Keep the two logic copies in sync by hand if the
# snap/translate design changes; this file is temporary and small enough
# that a shared-abstraction refactor isn't worth it before it's deleted.

# Shared perception module -- the SAME track-level hand identity (DR-1) the
# production server uses, imported rather than copied so the debug tool cannot
# drift out of tune with production (owner instruction 2026-08-02). It is pure
# stdlib with no cv2/mediapipe/window side effects, so importing it here is safe
# and pulls in nothing else from the server package.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "Python_Server_MediaPipe_vision_pipeline", "Resources"))
import hand_identity  # noqa: E402  (path set immediately above)
import capture_policy  # noqa: E402  (same directory; shared with production, N6)
from Resources import palm_rotation as _PRot
from Resources import palm_depth as _PDepth  # noqa: E402  (4.1/M9, read-only)
from Resources import session_paths  # noqa: E402  (tag sanitising, shared with production)
from Resources import capture_drive  # noqa: E402  (drive wake/retry, shared with production)
from Resources import fingertips  # noqa: E402  (F1 step 2, shared with production)
from Resources import tip_trim  # noqa: E402  (F1 step 4, shared with production)
from Resources import one_euro  # noqa: E402  (F1 step 1, the jitter filter)

# ⭐⭐ WHAT PRODUCTION ACTUALLY RUNS, since 2026-08-17.
# `Resources/HandsTriggeredActions.py` now drives cube orientation with Horn
# least-squares over the FIVE PALM LANDMARKS. Any tool here that claims to show
# "production behaviour" must pass this explicitly.
#
# ⚠⚠ AND `rotation=None` DELIBERATELY STILL MEANS GRAM-SCHMIDT. Do NOT make this
# the default of `update_hands`: `LiveBlockPredictionDebug` rows 1-2,
# `analysis/b4_anchor_rotation_ab.py` and `analysis/b7_live_ab.py` all rely on
# the no-argument call being the OLD estimator to hold rotation constant. Change
# the default and every one of those A/Bs silently starts comparing a thing
# against itself -- the §16.14 failure mode, from the other direction.
PRODUCTION_ROTATION = _PRot.Horn(_PRot.PALM_LANDMARKS, "ref")

# ⭐⭐ THE INPUT SYSTEM (2026-08-25) -- the same package production imports, so the
# two tools emit the SAME actions from the same facts (N6). It is a read-only
# OBSERVER: no cube is snapped, moved or released by it, and the HUD line it
# feeds (`handinput …`) is the only thing on screen that comes from it.
# `handinput/README.md` has the design; `analysis/verify_handinput.py` guards it.
try:
    import handinput as _HI
    from handinput.sources import live as _hi_live
    from handinput import trace as _hi_trace
    _hand_input = _HI.HandInput()
    _hand_input.trace_sink = _hi_trace.sink("LiveSnapDebug (DEBUG)")
except Exception as _e:                      # pragma: no cover -- defensive by design
    print("[handinput] disabled (%s)" % _e)
    _hand_input = None
    _hi_live = None


def _publish_hand_input(state, hand_data_by_hand, pose_out, now_ms):
    """Hand this frame to `handinput`. ⚠ Mirrors production's function of the same
    name exactly -- same fields, same order, same sources -- because two tools that
    build the same struct differently is how §13.6.1 happened. ⛔ Errors disable the
    observer; they never interrupt the tool."""
    global _hand_input
    if _hand_input is None:
        return
    try:
        obs = []
        for handedness in TRACKED_HANDS:
            data = hand_data_by_hand.get(handedness)
            pose = pose_out.get(handedness, {})
            _hd = (data or {}).get("hand_depth")
            obs.append(_hi_live.observe(
                slot=handedness,
                tracking=state.hand_state_trackers[handedness],
                palm_facing=_palm_facing_trackers[handedness],
                present=data is not None,
                track_id=_hand_track_ids.get(handedness, -1),
                position_px=pose.get("position_px"),
                depth_m=_hd[0] if _hd else None,
                depth_valid=bool(_hd[1]) if _hd else False,
                orientation=pose.get("orientation"),
                thumb_outward=state.last_known_thumb_outward[handedness],
                edge_on=(palm_geometry.edge_on_measure(data["pixel_landmarks"])
                         if data else None),
                landmarks_px=(data or {}).get("pixel_landmarks"),
                world_landmarks=(data or {}).get("world_landmarks"),
            ))
        _hand_input.update(_hi_live.frame(now_ms, obs))
    except Exception as e:                   # pragma: no cover -- defensive by design
        print("[handinput] update failed, disabling: %s" % e)
        _hand_input = None

# --------------------------------------------------------------------------
# THE SMOOTHING SLIDER -- the only live knob this tool carries
# --------------------------------------------------------------------------
# ⛔⛔ T6d (the anisotropic normal rebuild and its four sliders) WAS REMOVED FROM
# THIS TOOL on 2026-08-24 (owner: *"remove the anisotropic fit : I will not use
# it"*). It was measured over four live sessions and never shipped; production
# never ran it. The estimator itself still exists in `Resources/palm_rotation.py`
# (`AnisoParams`, `rebuild_terms`, `RebuiltNormalHorn`) because `analysis/
# t5i_zscale_sweep.py` and `t5j_roll_axis.py` drive it and because the T6 line's
# measurements are the record of a rejected arm -- but NOTHING LIVE reads it.
# The whole account is `Claude/HANDOFF_T6_ORIENTATION_FROM_2D.md`.
#
# ⭐ WHAT REPLACED IT AS THE THING TO TUNE: the rotation smoothing. It is the only
# filter left in the rotation path (the predictive orientation filter was removed
# the same day as dead code) and it is therefore the whole of the felt lag.
SLIDER_WIN = "Rotation smoothing + F1 fingertips"

# ⭐ Measured on `2026-08-24_205729_t6d_ab_ghost`, every arm fed identical input,
# lag read by shift-aligning against an unsmoothed replay of the same take:
#     tau 149 ms -> 128 ms lag, cube step p95 11.44 deg   (== the shipped 0.35)
#     tau  80 ms ->  64 ms lag, p95 12.76
#     tau  60 ms ->   0 ms lag, p95 13.09
#     tau  40 ms ->   0 ms lag, p95 13.93
#     tau  20 ms ->   0 ms lag, p95 14.64
#     tau   0 ms ->   0 ms lag, p95 15.17   (no smoothing at all)
# ⚠ "step p95" includes GENUINE hand motion, so it overstates jitter in absolute
# terms. It is a fair RELATIVE comparison because every arm replays the identical
# take; do not quote it as an absolute jitter figure.
# ⛔⛔ THE SLIDER IS CONTINUOUS IN MILLISECONDS, AND THE DISCRETE LADDER THAT CAME
# BEFORE IT WAS A REAL DEFECT. It was an INDEX into a tuple of choices -- but
# OpenCV draws a trackbar's own integer POSITION beside its name, so a control
# labelled "SMOOTH ms" displayed "3" while applying 20 ms. The owner read the take
# off it as "3 ms". ⭐ A slider whose displayed number is not the applied value is
# worse than an unlabelled one, because it invites a confident wrong reading. Now
# the trackbar's number IS tau in ms, and it can be trusted from a screenshot.
# ⚠ 150 is the top because 149 ms == the shipped per-frame 0.35 at a 64 ms frame
# time, so today's behaviour stays reachable and this stays an A/B.
SLERP_TAU_MAX_MS = 150

# ⭐⭐ F1's KNOBS, added 2026-08-26 -- the owner asked for "a threshold with a
# slider to set the filter value" and this is that, in a form that does not lie.
#
# ⛔⛔ EVERY SLIDER'S DISPLAYED INTEGER **IS** THE APPLIED VALUE IN ITS STATED
# UNIT. That is the rule the discrete ladder broke above, and it cost a take: the
# owner read "3 ms" off a control that was applying 20 ms. So the fingertip filter
# is exposed as a TIME CONSTANT IN MILLISECONDS -- the same unit as SMOOTH ms and
# the one the owner already reasons in -- rather than as the 1€ filter's cutoff
# frequency, which has no natural integer scale. The conversion is exact:
#
#       tau = 1 / (2*pi*fc)      <=>      fc = 1 / (2*pi*tau)
#
# ⚠ The two `x1000` / `%` labels carry their scale IN THE NAME for the same
# reason: `beta` is ~0.02 and a gain is a fraction, and neither is integer-natural.
JITTER_TAU_MAX_MS = 400
TRIM_GAIN_MAX_PCT = 100
TRIM_MAX_DEG_MAX = 30

SLIDERS = (
    # ⛔ 0 = NO smoothing: the cube goes exactly where Horn says, every frame.
    ("SMOOTH ms", SLERP_TAU_MAX_MS, 20, lambda n: float(n)),
    # ⛔ 0 = the fingertip filter OFF, and off is BIT-EXACT (the input value is
    # returned unchanged), so this position is genuinely today-without-F1's-filter
    # rather than an approximation of it.
    # ⛔⛔ PARKED 2026-08-26, owner: "jitter and speed ... removed at their
    # minimums ... don't delete the code, just park those three". Both are now
    # fixed at ZERO -- the 1-euro filter's own off state, which is BIT-EXACT
    # passthrough rather than an approximation. Reason: the census puts the tip
    # noise floor at 1.5 mm median, so there was little for the filter to remove,
    # and the owner found its lag "unbearable" at any useful setting.
    # ⭐ To revisit, put these two lines back in the tuple and restore the
    # 5-value unpack in `_read_sliders`; nothing else was removed.
    #   ("JITTER tau ms", JITTER_TAU_MAX_MS, 133, lambda n: float(n)),
    #   ("SPEED b x1000", 200, 20, lambda n: n / 1000.0),
    # ⚠ DRIVES ONLY THE ARM THAT HAS THE TRIM ON. In the three-window rig panels
    # 1 and 2 pin their gain to 0.0 explicitly, so sweeping this moves panel 3 and
    # leaves the controls alone -- which is what keeps the rig one-variable.
    #
    # ⛔⛔ IT STARTS AT 0, MATCHING PRODUCTION, AND `--f1-rig` RAISES IT.
    # Starting it at 100 made the ordinary single-arm debug tool run the trim
    # while production ran without it -- i.e. the two tools would differ in normal
    # use, which is the exact divergence `U6` keeps `parity_replay` around to
    # prevent. The rig is where the trim is meant to be ON, so the rig turns it on.
    ("TRIM gain %", TRIM_GAIN_MAX_PCT, 0, lambda n: n / 100.0),
    # ⭐⭐ THE GRAB RADIUS, owner 2026-08-26: "slider x the narrower axis of the
    # cube's projected footprint, slider between 0 and 1". Shown as a PERCENT
    # because the panel's rule is that the displayed integer IS the applied value
    # in its stated unit, and a trackbar cannot show 0.50.
    # ⚠ 0% means NOTHING CAN BE GRABBED -- deliberately reachable, because a
    # slider whose useful range is hidden behind a floor teaches the wrong thing
    # about where the limit is.
    # ⭐ Starts at the shipped 50%. Measured on 50 real grabs: 50% -> 42% of them
    # still occur, 60% -> 54%, 75% -> 72%, 100% -> 80%.
    # ⚠ The start value here is a PLACEHOLDER, exactly as "SMOOTH ms"'s is: this
    # table is built before `hand_state` is imported, so the real value is pushed
    # onto the trackbar in `_create_sliders`. A literal that drifts from the
    # constant would show the operator a number the pipeline is not using.
    # ⚠ RANGE IS 0..300, not 0..100. At 100 max the owner could not get BACK to a
    # working value once 33% turned out to be unusable -- a slider that cannot
    # reach the previous behaviour is a trap, not a control.
    ("GRAB radius %", 300, 100, lambda n: n / 100.0),
    # ⭐⭐ A1's fade budget, owner 2026-08-26: "make a slider for these xx ms,
    # between 0 and 1000 ms". Milliseconds OF HAND MOVEMENT, not of wall clock —
    # a hand held still does not spend it.
    # ⚠ 0 ms is the TELEPORT, and it is reachable on purpose: it is the design the
    # acceptance gate rejected at 118.4 px in one frame, so the slider's own left
    # end shows what that felt like.
    ("FADE ms moving", 1000, 300, lambda n: float(n)),
    # ⭐⭐ How much of the HAND's own step the cube may spend closing the gap, per
    # frame. Owner 2026-08-26: "a multiple of the hand movement cap, with a slider
    # between 0.05 and 1". Shown as a percent so the displayed integer IS the
    # applied value, the rule every slider on this panel follows.
    # ⚠ 0 is reachable and means the cube NEVER re-centres — informative rather
    # than hidden. The owner's stated floor, 0.05, is position 5.
    ("WALK % of hand", 100, 25, lambda n: n / 100.0),
    # ⭐⭐ THE AXIAL HALF OF THE GRAB GATE, owner 2026-08-26: "currently, the margin
    # is too wide". In CENTIMETRES so the displayed integer is the applied value.
    # ⚠ It is deliberately SEPARATE from the in-plane radius and always has been:
    # x,y are MEASURED in pixels while depth is ESTIMATED, and `T6` measured the
    # four palm spans disagreeing about that estimate by 13-22% at a single square
    # pose. `GRAB_Z_TOLERANCE_M`'s own comment says it is sized to swallow that so
    # the gate stays REACHABLE.
    # ⛔ MEASURED BEFORE TIGHTENING: on the two takes recorded before the depth
    # ratchet was fixed, |hand depth - cube depth| at grab ran a MEDIAN 12.3 cm
    # (p95 14.6), i.e. pressed against today's 15. Most of that was the ratchet --
    # cubes pinned at the 0.30 m floor while the hand sat at 0.42 -- so it should
    # be far smaller now. This slider is how we find out, live.
    ("GRAB z margin cm", 30, 15, lambda n: n / 100.0),
    # ⛔ PARKED 2026-08-26 alongside the two above -- the owner retired it after
    # revisiting an earlier preference for a raised clamp.
    #   ("TRIM max deg", TRIM_MAX_DEG_MAX, 10, lambda n: float(n)),
)

# ⭐ OWNER'S CHOICE, 2026-08-24, settled live: **20 ms**. Reached by sweeping the
# whole range (down to 0, up through 149 = today, back), and returned to twice.
# ⚠ Imported HERE rather than relying on the later `from Resources import
# hand_state`: this block sits above it, and N6 matters more than import order.
from Resources import hand_state as _HS_const  # noqa: E402
SLERP_TAU_MS = _HS_const.ROTATION_SLERP_TAU_MS

# ⭐ F1's live values, mirrored here so `--no-sliders` still runs. Seeded from the
# module defaults rather than repeated as literals (N6: a tuning constant lives in
# ONE module), and converted into the ms the slider speaks.
# ⛔ ITS SLIDER IS PARKED (see `SLIDERS`), so this is now a fixed value rather than
# a live knob. ⚠ NOT parked at zero: zero failed the acceptance gate -- see
# `fingertips.GRIP_FILTER_ENABLED` for the 120.4 px measurement.
JITTER_TAU_MS = 1000.0 / (2.0 * math.pi * one_euro.MIN_CUTOFF_HZ)
JITTER_BETA = one_euro.BETA




# Palm chirality geometry -- SHARED with production's HandsTriggeredActions.py
# (queue item 1.2). Same reasoning as hand_identity above: imported, never copied.
# `Resources` is a package alongside this file; importing this ONE module does not
# pull in HandsTriggeredActions/CubeWindow, so no pygame window is opened.
from Resources import owner_remap
from Resources import object_extent  # noqa: E402
from Resources import palm_geometry  # noqa: E402
from Resources import hand_state  # noqa: E402
from Resources import hand_tracks  # noqa: E402  (4.1 migration, shared with production)  (queue D1 -- state lives on CubeState)

HAND_LANDMARKER_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "Python_Server_MediaPipe_vision_pipeline", "Resources", "hand_landmarker.task",
)

# MediaPipe's built-in Closed_Fist/Open_Palm Gesture Recognizer was tried
# here (2026-08-01) and reverted: live-tested unreliable across hand
# positions/orientations (many missed fist closures) — it's evidently
# tuned to a narrow set of canonical poses, not usable for this project's
# purpose. GESTURE_PIPELINE_SPEC.md §13.2 already flagged this exact risk
# ("still subject to Stage 4 discipline... don't trust a claim without
# checking it") and this is that check failing. `gesture_recognizer.task`
# is kept on disk (not deleted) for a possible later use of its Thumb_Up
# class; fist/open-palm detection needs a different approach (custom
# geometric heuristic or trained classifier) — not yet decided, see
# GESTURE_PIPELINE_SPEC.md §13.4.

# Recording root for --record. Deliberately the SAME root
# RecordPerceptionSequence.py writes to, so analysis/t5*.py locate these
# sessions with the same CAPTURE_ROOT constant and need no new path.
# Owner rule (memory): recordings live on E:, never --local.
RECORD_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer"

TRACKED_HANDS = ("Left", "Right")

# ⭐ N6 PARITY with production's `HandsTriggeredActions._owner_key` (4.1 / T3).
# Ownership keys on the STABLE DR-1 track id, not the handedness label, because
# the label flips and 113 of 205 measured spurious releases were that flip
# orphaning a held cube. ⚠ Falls back to the label when no id backs the hand,
# exactly as production does -- a cube must never become unreleasable.
# ⚠ Production reads the id off the wire; here DR-1 runs in-process, so it is
# read straight off the shared tracker. Same value, same semantics.
# ⛔ REVERTED 2026-08-22 by owner instruction. Mirrors production's
# `HandsTriggeredActions.TRACK_OWNERSHIP` -- see the long comment there for why.
# OFF = ownership and per-hand state key on the handedness SLOT, as before 4.1.
TRACK_OWNERSHIP = False

_hand_track_ids = {h: -1 for h in TRACKED_HANDS}
# Must equal production's HandsTriggeredActions.OWNER_ABSENT_RELEASE_MS (N6).
# ⭐ OPTION A, mirroring production exactly (N6). Ownership DEGRADES rather than
# breaking: while the owning track is missing the cube keeps being driven by the
# hand in its remembered slot, and past the window it is RELEASED -- so there is
# no owned-but-frozen state left, which is what the owner kept hitting.
# Window is MEASURED: every post-DR-1-fix id-gap seen with a hand still in view
# was <= 130 ms (n=32); 250 ms covers 100% with ~2x margin and caps a wrong-hand
# follow at ~6 frames. Must equal production's constants (guarded by
# analysis/verify_track_ownership.py).
OWNER_DEGRADE_MS = 250.0
OWNER_ABSENT_RELEASE_MS = OWNER_DEGRADE_MS


class _HandBundle:
    """One physical hand's state, mirroring production's `_HandBundle`."""

    # ⚠ NO `palm_facing` HERE. DR-2 is UPSTREAM of the arms and its tracker is
    # deliberately SHARED between them (see the rig comment): giving each arm its
    # own would introduce a second difference between panels and destroy the
    # one-variable property the whole rig depends on. Upstream per-hand state is
    # bound once per frame by `_bind_upstream_track_state`, not here.
    __slots__ = ("tracking", "orientation_filter", "rotation_state",
                 "last_known_thumb_outward",
                 "resync_blend_left", "reliability_alpha")

    def __init__(self):
        self.tracking = None
        self.orientation_filter = None
        self.rotation_state = None
        self.last_known_thumb_outward = False
        self.resync_blend_left = 0
        self.reliability_alpha = 1.0


def _new_bundle_for(state, slot):
    """FRESH state for a newly-seen track: CONFIG only, never STATE.
    Mirrors production's `_new_bundle_for` -- see its comment for the two live
    failures the previous seed-from-slot version caused (a returning hand
    inheriting the old hand's snap permission, and two tracks aliasing ONE
    HandStateTracker, which froze every cube)."""
    b = _HandBundle()
    template = state.hand_state_trackers.get(slot)
    window = getattr(template, "bridge_window_ms", state.bridge_window_ms)
    b.tracking = hand_state.HandStateTracker(bridge_window_ms=window)
    b.rotation_state = None
    b.last_known_thumb_outward = False
    b.resync_blend_left = 0
    b.reliability_alpha = 1.0
    return b


def _bind_track_state(state, now_ms):
    """Point this arm's per-hand dicts at the state of the track now in each slot."""
    if not TRACK_OWNERSHIP:
        return {}

    if state.track_registry is None:
        state.track_registry = hand_tracks.TrackRegistry(_HandBundle)
    slots = state.track_registry.resolve(dict(_hand_track_ids), now_ms)
    bound = {}
    for slot, tid in slots.items():
        b = state.track_registry.state(tid, seed=lambda st=state, s=slot: _new_bundle_for(st, s))
        if b is None:
            # No identity -> leave the dicts alone (legacy behaviour), exactly as
            # production does. Substituting a default bundle here would discard
            # any injected configuration.
            continue
        bound[slot] = b
        state.hand_state_trackers[slot] = b.tracking
        state.hand_rotation_states[slot] = b.rotation_state
        state.last_known_thumb_outward[slot] = b.last_known_thumb_outward
        state.resync_blend_left[slot] = b.resync_blend_left
        state.last_hand_reliability_alpha[slot] = b.reliability_alpha
    return bound


def _writeback_track_state(state, bound, now_ms):
    if not TRACK_OWNERSHIP:
        return

    for slot, b in bound.items():
        b.rotation_state = state.hand_rotation_states[slot]
        b.last_known_thumb_outward = state.last_known_thumb_outward[slot]
        b.resync_blend_left = state.resync_blend_left[slot]
        b.reliability_alpha = state.last_hand_reliability_alpha[slot]
    state.track_registry.evict(now_ms)


def _cube_for_hand(state, handedness, now_ms):
    """The cube this hand drives this frame, degraded path included. See
    production's `_cube_for_hand`; kept behaviourally identical."""
    direct = state.cube_owned_by(_owner_key(handedness, state))
    if direct is not None or not TRACK_OWNERSHIP:
        return direct
    live = {t for t in _hand_track_ids.values() if t >= 0}
    for name, cube in state.cubes.items():
        if not isinstance(cube.owner, int) or cube.owner in live:
            continue
        if state.owner_hand_of_cube.get(name) != handedness:
            continue
        first = state.owner_absent_since.get(name)
        if first is not None and now_ms - first < OWNER_DEGRADE_MS:
            return name
    return None
# ⚠ THE SESSION-VALIDITY COUNTER. The 4.1/T3 rig tests nothing unless a RELABEL
# actually happens -- the same trap as the D2 rig's `brid` staying at 0. This
# counts frames where a track id appeared under a DIFFERENT handedness slot than
# it did last frame, which is precisely the event that used to orphan a cube.
_prev_slot_of_track = {}
arms_first_panel = [None]
_coast_rig = [False]          # set from --coast-ab so titles can name the window
_relabel_events = [0]


# ⭐ 4.1 M9: a READ-ONLY live view of the depth estimator. It drives nothing --
# wiring the ratio into cube Z is 4.2 and needs 3D snap gating with it. This
# exists so the estimator can be SEEN responding before anything depends on it.
# ⚠ Deliberately NOT reset on release: the baseline follows the hand track, so a
# reading persists across a drop, which is what makes drift visible.
_depth_trackers = {h: _PDepth.DepthRatioTracker() for h in TRACKED_HANDS}
_depth_readout = {h: None for h in TRACKED_HANDS}


def _update_depth(hand_data_by_hand):
    for hand in TRACKED_HANDS:
        d = hand_data_by_hand.get(hand)
        trk = _depth_trackers[hand]
        if d is None:
            trk.reset()
            _depth_readout[hand] = None
            continue
        ratio, valid = trk.update(d["pixel_landmarks"])
        _depth_readout[hand] = (ratio, valid)


# ⭐⭐ 4.2 -- THE ABSOLUTE HAND DEPTH THE 3D SNAP GATE READS.
#
# UPSTREAM and SHARED across arms, exactly like `_palm_facing_trackers`: it has
# no grab dependency, so one estimator serves every panel and the arms' only
# difference stays their own configuration. ⚠ AND IT MUST BE UPDATED ONCE PER
# FRAME, NOT ONCE PER ARM -- `update_hands` runs per arm, so advancing a
# hysteretic tracker in there would step its band three times per frame in a
# three-arm rig. That is why this writes the answer INTO `hand_data_by_hand`
# (like `thumb_outward`) instead of being computed inside `update_hands`.
#
# ⚠ A caller that never calls this leaves `hand_depth` absent, and `update_hands`
# then runs the PRE-4.2 2D gate. That is deliberate: eight harnesses drive
# `update_hands` and none of them know about depth. `analysis/parity_replay.py`
# is the one that MUST call it -- production computes depth internally, so a
# parity harness that skips this compares a 3D gate against a 2D one and
# manufactures a divergence. Third time that rule has been written down.
_snap_depth_trackers = {h: _PDepth.HandDepthTracker() for h in TRACKED_HANDS}


# This frame's pixel landmarks per hand, for the HUD's SQUARE readout only.
_last_pixel_landmarks = {}


def _update_snap_depth(hand_data_by_hand, frame_size):
    """Stamp each detected hand's `(depth_m, valid)` onto its data dict."""
    for hand in TRACKED_HANDS:
        d = hand_data_by_hand.get(hand)
        if d is None:
            _snap_depth_trackers[hand].reset()
            _last_pixel_landmarks.pop(hand, None)
            continue
        _last_pixel_landmarks[hand] = d["pixel_landmarks"]
        d["hand_depth"] = _snap_depth_trackers[hand].update(
            d["pixel_landmarks"], frame_size)


# ⭐ UPSTREAM per-hand state: shared by every arm, so it is bound ONCE per frame,
# before the arms run. Today that is DR-2's PalmFacingTracker. Keeping it out of
# the per-arm bundle is what preserves the rig's one-variable property.
class _UpstreamBundle:
    __slots__ = ("palm_facing", "grip_tracker")

    def __init__(self):
        self.palm_facing = palm_geometry.PalmFacingTracker()
        # ⭐ F1 step 2. Upstream for the same reason DR-2 is: no grab dependency,
        # and every arm must see the same grip point or the rig gains a second
        # variable. A NEW track gets a fresh one -- a returning hand must not
        # inherit the previous hand's filter history.
        self.grip_tracker = fingertips.GripTracker()


_upstream_registry = hand_tracks.TrackRegistry(_UpstreamBundle)
_upstream_bound = {}


def _bind_upstream_track_state(now_ms):
    """Point the shared DR-2 trackers at the track now in each slot."""
    if not TRACK_OWNERSHIP:
        return

    global _upstream_bound
    _upstream_bound = {}
    slots = _upstream_registry.resolve(dict(_hand_track_ids), now_ms)
    for slot, tid in slots.items():
        def _seed(s=slot):
            # FRESH tracker: sharing the slot's object would alias DR-2 state
            # between two different physical hands.
            return _UpstreamBundle()
        b = _upstream_registry.state(tid, seed=_seed)
        if b is None:
            continue                      # no identity -> leave it alone
        _upstream_bound[slot] = b
        _palm_facing_trackers[slot] = b.palm_facing
        _grip_trackers[slot] = b.grip_tracker
    _upstream_registry.evict(now_ms)


def _count_relabels():
    for hand, tid in _hand_track_ids.items():
        if tid < 0:
            continue
        prev = _prev_slot_of_track.get(tid)
        if prev is not None and prev != hand:
            _relabel_events[0] += 1
        _prev_slot_of_track[tid] = hand


def _owner_key(handedness, state=None):
    if not TRACK_OWNERSHIP:
        return handedness

    """The ownership key for this hand THIS FRAME.

    `state` selects the arm's mode; None means the shipped behaviour. An arm in
    "label" mode reproduces the PRE-4.1 keying exactly, which is what makes the
    A/B honest -- the control is the old code path, not an approximation.
    """
    if state is not None and getattr(state, "ownership", "track") == "label":
        return handedness
    tid = _hand_track_ids.get(handedness, -1)
    return tid if tid >= 0 else handedness


# One tracker for the whole session, mirroring production's module-level one.
_hand_identity_tracker = hand_identity.HandIdentityTracker()

# DR-2 palm-facing freeze, per hand -- mirrors production's `_palm_facing_trackers`
# in HandsTriggeredActions.py (queue item 2.2). Same shared class, so the debug tool
# and the game apply an identical edge-on policy.
_palm_facing_trackers = {h: palm_geometry.PalmFacingTracker() for h in ("Left", "Right")}

# ⭐ F1 step 2: the filtered fingertip grip point, per hand. ⚠ UPSTREAM AND
# SHARED ACROSS ARMS, like `_palm_facing_trackers` and unlike the per-arm depth
# ratio trackers: it has no grab dependency, so giving each arm its own would
# add a second difference between panels and destroy the rig's one-variable
# property. Mirrors production's `_grip_trackers`.
_grip_trackers = {h: fingertips.GripTracker() for h in ("Left", "Right")}

# D1/D2/D3 tracking state (queue Phase D, spec §2.1/§2.2) lives on CubeState, NOT
# here -- see the `bridge_window_ms` block there. It has to be per-arm so the
# three-arm comparison below can run three configurations off one camera.
# ⚠ Production keeps its copies at module level in `HandsTriggeredActions`; it
# runs one arm and needs no split. The VALUES must stay in step (§13.6.1) even
# though the storage does not: `hand_state.BRIDGE_WINDOW_MS` is the shared
# constant both read, which is what keeps them honest.
#
# ⚠ One field is deliberately NOT mirrored: production records DR-2's
# `orientation_valid` on the quality block, this tool does not, because it
# computes DR-2 in the capture loop BEFORE `update_hands` runs and nothing here
# consumes the bit. That is a gap in a field no rule reads, not in behaviour.

# D3 resync blend, mirroring production's `_resync_blend_left` /
# `RESYNC_BLEND_FRAMES`. Same value, same meaning; 0 disables it, which is the
# live A/B's no-blend arm.
RESYNC_BLEND_FRAMES = 3

# ⭐⭐ THE D2/D3 COMPARISON RIG, THREE ARMS SIDE BY SIDE (`--arms 3`).
#
#   off    window 0, no blend   = production before D2. THE CONTROL.
#   on     window 150, no blend = D2 alone: the drop is gone, the pop is not
#   blend  window 150, blend 3  = D2 + D3
#
# ✅ DECIDED LIVE 2026-08-21: the owner ran the three arms, chose BLEND -- "3 -
# BLEND is definitely better" -- and WAIVED the blind test. So `blend` is what
# production runs and what this tool now runs by DEFAULT (`--arms 1`), because a
# debug tool that does not mirror production is the divergence N6/§13.6.1 exists
# to prevent. The rig stays behind `--arms 3` for the next time an arm needs
# comparing; it is no longer the default view.
#
# ⭐ Each arm keeps its OWN cubes and its own Phase D state, but all three are
# driven by ONE camera frame, ONE detection and ONE identity resolution -- so the
# ONLY thing that differs between the panels is the bridging. That one-variable
# property is what made B4's six-arm session readable and is not negotiable here:
# if a second difference ever creeps in, a visible difference stops having one
# cause. (`_palm_facing_trackers` is deliberately shared -- DR-2 is UPSTREAM of
# these arms, so giving each arm its own would introduce exactly such a second
# difference.)
#
# ⚠ This is a SIGHTED test and it can only answer "does this feel right / did
# anything regress". A PREFERENCE between arms needs the balanced
# `--blind-series` machinery -- §16.17 measured an unbalanced sighted comparison
# manufacturing a convincing 5-1 that collapsed to 4-2 (p = 0.34) once balanced.
# Do not report a winner from this screen.
BRIDGE_MODES = ("off", "on", "blend")
BRIDGE_ARM_COLOURS = {"off": (128, 128, 128), "on": (0, 200, 255), "blend": (0, 255, 128)}


def _make_arm(mode, width, height, ownership="track", coast_ms=None,
              use_tips=None, trim_gain=None):
    """One arm of a comparison: its own cubes, trackers, window and counters.

    `coast_ms` overrides D2's bridge window for this arm only -- the U5 coast rig
    (queue item U5) needs several windows side by side on ONE camera."""
    if coast_ms is not None:
        window = float(coast_ms)
    else:
        window = 0.0 if mode == "off" else hand_state.BRIDGE_WINDOW_MS
    return CubeState(
        window_size=(width, height),
        bridge_window_ms=window,
        resync_blend_frames=RESYNC_BLEND_FRAMES if mode == "blend" else 0,
        arm_label=mode,
        ownership=ownership,
        use_tips=use_tips,
        trim_gain=trim_gain,
    )


def _arm_title(state):
    # ⭐ F1 rig panels name the STEP, not the bridge mode -- all three are "blend",
    # so without this the three windows are indistinguishable. Same complaint the
    # ownership and T6d rigs each had to fix.
    if state.use_tips is not None or state.trim_gain is not None:
        _tips = bool(state.use_tips)
        # ⚠ None means "follow the live global", NOT zero. Reading it as zero
        # would title panel 3 "STEP 2" while it was running the trim -- a panel
        # whose label contradicts what it is doing is the T6d/ownership-rig
        # complaint all over again.
        _gain = tip_trim.TRIM_GAIN if state.trim_gain is None else state.trim_gain
        if not _tips and _gain == 0.0:
            return "1. STEP 0 -- palm anchor, no trim   [SHIPPED / CONTROL]"
        if _tips and _gain == 0.0:
            return "2. STEP 2 -- FINGERTIP barycentre drives snap + translation"
        return ("3. STEP 4 -- step 2 + FINGERTIP TRIM  "
                "[gain %.2f, max %.0f deg]" % (_gain, tip_trim.TRIM_MAX_DEG))
    return {
        "off": "1. OFF -- pre-D2 control (release on frame 1)",
        "on": f"2. ON -- D2 bridge {state.bridge_window_ms:.0f} ms, NO blend",
        "blend": f"3. BLEND -- D2 {state.bridge_window_ms:.0f} ms + D3 "
                 f"{state.resync_blend_frames}-frame resync  [SHIPPED]",
    }.get(state.arm_label, state.arm_label) + (
        f"   [COAST {state.bridge_window_ms:.0f} ms"
        + ("  <-- SHIPPED]" if abs(state.bridge_window_ms - hand_state.BRIDGE_WINDOW_MS) < 1e-6
           else "]")
        if _coast_rig[0] else "") + (
        "   [OWNERSHIP: LABEL -- pre-4.1 control]" if state.ownership == "label"
        else "   [OWNERSHIP: TRACK ID]" if state.ownership == "track" else "") + (
        # ⭐ T6d: when an arm carries its OWN estimator, NAME it on the panel. Both
        # A/B arms are "blend"+"track", so without this the two windows are
        # indistinguishable -- the exact complaint the ownership rig's naming
        # comment already records, and the U5 rig's recorder key already paid for.
        ("   [ROTATION: %s]" % getattr(state.rotation, "name", "?"))
        if getattr(state, "rotation", None) is not None else "")


COAST_MS_ARMS = (150.0, 300.0, 450.0)


def _make_slerp_ab_arms(width, height):
    """The LAG rig: identical estimators, smoothing the ONLY difference.

    ⭐ Panel 1 keeps the shipped fixed-per-frame 0.35 and panel 2 runs the
    time-based constant, so this isolates exactly the thing being judged.
    ⚠ Both arms get their OWN plain `Horn`: one estimator object shared between
    them would share its frozen grab reference, and panel 2 would then be
    measuring panel 1's grab.
    """
    before = _make_arm("blend", width, height)
    before.rotation = _PRot.Horn(_PRot.PALM_LANDMARKS, "ref")
    before.slerp_mode = "frame"
    after = _make_arm("blend", width, height)
    after.rotation = _PRot.Horn(_PRot.PALM_LANDMARKS, "ref")
    after.slerp_mode = "time"
    return [before, after]


# ⭐⭐ F1's THREE-WINDOW RIG. One camera, one detection, one identity resolution,
# one shared grip filter -- the panels differ ONLY in which F1 step is switched on,
# which is what makes a difference between them attributable.
#
#   1  STEP 0  baseline   palm centre drives snap+translation, no fingertip trim.
#                         ⭐ This is the SHIPPED pipeline and it is the control.
#   2  STEP 2  grip       the fingertip BARYCENTRE drives snap + translation.
#   3  STEP 4  grip+trim  step 2, plus the fingertip ROTATION trim.
#
# ⚠ Panel 3 differs from panel 2 by the TRIM ALONE, and panel 2 from panel 1 by
# the GRIP POINT alone -- so each pair isolates one step. Reading 3 against 1
# answers "is F1 better than today"; reading 3 against 2 answers "does the trim
# earn its place", which `T6d` shows is a separate question with a different answer.
def _make_f1_rig(width, height):
    return [
        _make_arm("blend", width, height, use_tips=False, trim_gain=0.0),
        _make_arm("blend", width, height, use_tips=True, trim_gain=0.0),
        # ⚠ `trim_gain=None` means "follow the module global", which is what the
        # TRIM sliders drive -- so sweeping them moves THIS panel and leaves the
        # two controls above pinned at 0.0. That is what keeps the rig
        # one-variable while still being tunable live.
        _make_arm("blend", width, height, use_tips=True, trim_gain=None),
    ]


def _arm_layout(n, width, height, ownership_ab=False, coast_ab=False,
                slerp_ab=False, f1_rig=False):
    """The comparison rig, or None for the ordinary single-arm view."""
    if f1_rig:
        return _make_f1_rig(width, height)
    if slerp_ab:
        return _make_slerp_ab_arms(width, height)
    if coast_ab:
        # ⭐ QUEUE ITEM U5's RECORDING TEST. Three coast windows, everything else
        # identical, one camera and one detection -- so a difference between
        # panels has exactly one cause.
        # 150 ms is what SHIPS; 300/450 are the candidates. Measured motivation:
        # hand-crossing gaps run 402 ms median / 2130 ms p90, and 70% exceed 150.
        # ⚠ Judge on BOTH directions at once: `rel` should FALL as the window
        # grows (fewer cubes dropped through an occlusion) while the cube must not
        # start following the WRONG hand or staying stuck to a released one --
        # a longer hold widens N8's stealing window. A rig that only counts drops
        # will happily recommend an infinite coast.
        return [_make_arm("blend", width, height, coast_ms=ms) for ms in COAST_MS_ARMS]
    if ownership_ab:
        # ⭐ 4.1/T3 rig: SAME bridge config on both panels, ownership the ONLY
        # difference. Left = the old label keying, right = the shipped track id.
        # ⚠ Judge it on `rel`: a relabel while holding a cube drops it on the
        # LABEL panel and must NOT drop it on the TRACK panel.
        return [_make_arm("blend", width, height, "label"),
                _make_arm("blend", width, height, "track")]
    if n == 3:
        return [_make_arm(m, width, height) for m in BRIDGE_MODES]
    return None

WRIST = 0
INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 5, 9, 13, 17
HAND_POSITION_LANDMARKS = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

# Translation-pivot fix (§14.1/§14.1.1, 2026-08-01, later conversation) --
# distance-weighted live landmark tracking, verified offline against 7 real
# hold intervals (AnalyzeTranslationPivot.py) before being wired in here:
# no-pop exact, jitter comparable to today's zero-offset mechanism,
# translation now measurably scales with real rotation. One known,
# deliberately DEFERRED limitation: swings toward the palm under yaw
# specifically (pure 2D weighting can't distinguish yaw foreshortening from
# real repositioning -- likely shares root cause with the not-yet-built
# Z-axis translation gesture, §14.3) -- accepted for now, revisit alongside
# a proposed future startup Z-axis calibration step.
THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP = 4, 8, 12, 16, 20
TRANSLATION_CANDIDATE_LANDMARKS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP,
                                    INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
# Floor under the inverse-distance denominator -- prevents divide-by-zero
# and caps how sharply weight can concentrate onto a single landmark.
# Matches AnalyzeTranslationPivot.py's verified value; re-tune together
# with that script if this ever needs adjusting, don't drift the two apart.
TRANSLATION_EPSILON_PX = 5.0

# Cube sizes match production's CubeWindow.py exactly (2026-08-01, direct
# request: large cube's every dimension is 2x the small cube's) -- keeping
# this debug tool's visual an accurate stand-in for what production shows,
# per its own "kept in logic-sync with the production module" discipline.
CUBE_SIZE_SMALL = 40
CUBE_SIZE_LARGE = CUBE_SIZE_SMALL * 2
# ⛔ IMPORTED, NEVER COPIED (`CONSTRAINTS` §4 / N6). This was a SECOND copy of a
# tuning constant until 2026-08-26 -- both tools happened to read 1.5, so the
# duplication was invisible right up until the moment one of them was tuned.
# ⭐ Now there is one definition and the debug tool cannot drift from production
# on the grab radius, whatever it is set to.
GRAB_RADIUS_MULTIPLIER = _HS_const.GRAB_RADIUS_MULTIPLIER

# ⭐ A1's fade budget, in ms OF HAND MOVEMENT. Slider-driven here; `fingertips`
# holds the shipped default and production reads that one.
GRIP_ALIGN_MOVING_MS = fingertips.GRIP_ALIGN_MOVING_MS
GRIP_ALIGN_MASK_RATIO = fingertips.GRIP_ALIGN_MASK_RATIO
GRAB_Z_TOLERANCE_M = _PDepth.GRAB_Z_TOLERANCE_M
CUBE_ALPHA = 0.55  # transparency of the cube overlay, so the video stays visible underneath
SNAP_BORDER_COLOR = (255, 255, 255)
SNAP_BORDER_WIDTH = 3
CUBE_EDGE_COLOR = (20, 20, 20)  # normal (unsnapped) face-outline color, BGR

HAND_POINT_COLOR = {"Left": (255, 120, 0), "Right": (0, 0, 255)}

IDENTITY_QUATERNION: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # (w, x, y, z)

# Rotation while snapped (GESTURE_PIPELINE_SPEC.md §13.3, PART_ONE.md §2/§7.5,
# HANDOFF_SNAP_ROTATE_RELEASE.md §2) — built here first because this debug
# tool already runs HandLandmarker in-process and gets `hand_world_landmarks`
# for free, letting rotation be live-verified before touching the wire
# protocol (which doesn't send world landmarks yet, see PART_ONE.md §4).
# CONFIRMED 2026-08-01: rotation is UNGATED (active for any snapped hand,
# regardless of pose) — Open_Palm detection has no working implementation
# (§13.5), and gating was an inference, not a hard requirement; the user
# chose the pragmatic path of building/verifying rotation independently and
# adding a gate later once open-palm detection exists.
ROTATION_SLERP_FACTOR = 0.35  # tune by feel once live, same discipline as GRAB_RADIUS_MULTIPLIER
# Raised from 0.25 to 0.35 (2026-08-01, direct request) for more responsive
# feel -- an exponential-smoothing filter's settling time constant (frames
# to close 1-1/e of any gap) is 1/(-ln(1-factor)); 0.25 -> ~3.48 frames,
# 0.35 -> ~2.32 frames, a reduction of almost exactly one third.
# Real 3D cube rendering (2026-08-01, direct request — replaces the axis
# gizmo now that rotation is confirmed working end-to-end; ported from the
# production CubeWindow.py, same design and same fixed-camera-distance
# perspective projection -- see CubeWindow.py's CUBE_PERSPECTIVE_DISTANCE_
# RATIO comment for the live-found morphing bug this avoids (a naive
# per-vertex scale relative to the cube's own half-size goes negative for
# cube corners at some rotations; a fixed virtual camera distance,
# comfortably larger than the cube's half-diagonal, never does).
CUBE_PERSPECTIVE_DISTANCE_RATIO = 3.0  # virtual camera distance = cube.size * this


def _darken(color: Tuple[int, int, int], factor: float = 0.45) -> Tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in color)


@dataclass(frozen=True)
class MeshFace:
    """One planar face: local vertex indices (ANY polygon size -- 3 for a
    triangle, 4 for a quad, so this scales to a real imported mesh later),
    its own local outward normal, and its own color -- mirrors production
    CubeWindow.py's identical class (mesh-generic rendering, 2026-08-01,
    direct request: the cube is a placeholder for future imported 3D
    objects, see GESTURE_PIPELINE_SPEC.md §13.8)."""
    vertex_indices: Tuple[int, ...]
    normal: Tuple[float, float, float]
    color: Tuple[int, int, int]


@dataclass(frozen=True)
class Mesh:
    """Generic local-space geometry (unit scale, multiplied by the owning
    cube's own size at draw time) -- mirrors production CubeWindow.py's
    identical class. `_make_cube_mesh` below is the one cube-specific
    construction function; `_draw_cube_3d` operates on ANY Mesh."""
    vertices: Tuple[Tuple[float, float, float], ...]
    faces: Tuple[MeshFace, ...]


# ⭐ Hoisted to a module constant so the slider panel can report the grab
# footprint without building a mesh, and so there is ONE vertex list in this file
# rather than one per caller.
_CUBE_MESH_VERTS = (
    (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
    (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
)


def _make_cube_mesh(color_x, color_y, color_z) -> Mesh:
    vertices = _CUBE_MESH_VERTS
    face_specs = (
        ((1, 2, 6, 5), (1.0, 0.0, 0.0), color_x),
        ((0, 3, 7, 4), (-1.0, 0.0, 0.0), _darken(color_x)),
        ((3, 2, 6, 7), (0.0, 1.0, 0.0), color_y),
        ((0, 1, 5, 4), (0.0, -1.0, 0.0), _darken(color_y)),
        ((4, 5, 6, 7), (0.0, 0.0, 1.0), color_z),
        ((0, 1, 2, 3), (0.0, 0.0, -1.0), _darken(color_z)),
    )
    faces = tuple(MeshFace(vertex_indices=vi, normal=n, color=c) for vi, n, c in face_specs)
    return Mesh(vertices=vertices, faces=faces)


# Colors are BGR (cv2 convention here, vs. CubeWindow.py's RGB/pygame) --
# same colors as production, channel order swapped.
FACE_COLOR_YELLOW = (0, 221, 255)
FACE_COLOR_VIOLET = (224, 90, 170)
FACE_COLOR_TURQUOISE = (208, 224, 64)
FACE_COLOR_GREEN = (60, 200, 60)
FACE_COLOR_RED = (60, 60, 220)
FACE_COLOR_BLUE = (230, 130, 60)

# Orientation noise filtering (2026-08-01) -- history of attempts, kept for
# context on why this landed here, not because earlier attempts are still
# used:
#
# Attempt 1 (removed): reject a frame if its target was far from the CUBE's
# current (slerped) orientation. Created a self-reinforcing trap (a lagging
# reference falls further behind on every rejection) -- many CONSECUTIVE
# frames rejected during otherwise-smooth pitch rotation.
#
# Attempt 2 (removed): compare each frame's raw reading only to the
# previous raw reading (never a lagged value), substitute the last known-
# good raw on a flagged frame (`RAW_ORIENTATION_GLITCH_DEG = 60`, a
# physically-justified per-frame bound). Fixed the stuck-trap problem, but
# still a binary accept/reject: a flagged frame contributed literally
# nothing (the cube froze), and live testing at the exact pitch crossing
# showed the classic pattern this produces -- freeze, then one or two
# CATASTROPHIC back-to-back jumps once a frame finally got accepted again
# (observed: 141 degrees then 124 degrees in consecutive frames), then a
# snap back. Root cause of the residual noise itself (not this filter's
# design): geometric analysis + two further tests (a thumb-based vector
# pair, literature-motivated since the thumb is the one MediaPipe landmark
# not coplanar with the palm; and a PCA/centroid fit averaging all 4
# non-thumb MCPs) both failed to improve conditioning at the exact
# degenerate frames -- proving the residual is a SYSTEMATIC, CORRELATED
# distortion of the whole knuckle-row reconstruction at that viewing angle
# (all landmarks degrade together), not independent per-landmark noise, so
# no in-frame landmark choice can fix it. Full account:
# GESTURE_PIPELINE_SPEC.md §13.7.
#
# Attempt 3 (current): a predictive, reliability-weighted filter --
# literature-grounded (Ernst & Banks 2002 reliability-weighted/Bayesian
# sensory cue integration; Wolpert/Friston forward-model and predictive-
# coding work; EKF/UKF is documented standard practice for monocular hand
# pose specifically under depth ambiguity) and empirically verified against
# recorded data before implementing (same discipline as everything else in
# this file): maintain a short estimate of the hand's recent angular
# velocity from accepted frames (`HandOrientationFilter.omega`), predict
# each frame's expected orientation by extrapolating it forward one step,
# and blend the raw reading with that prediction weighted by
# `_reliability_alpha(conditioning_norm)` -- a continuous ramp, not a hard
# cutoff, so a frame is never fully discarded OR fully trusted based on a
# threshold alone. During a fully degenerate run the filter "coasts" at the
# last known angular velocity (dead reckoning) instead of freezing; during
# healthy frames it tracks the raw signal with zero added lag (alpha=1).
# Verified on the same recorded pitch-crossing data used to diagnose the
# problem: eliminated >30deg jumps entirely (4%->0%) and >60deg jumps
# entirely (3%->0%) in the back-toward-camera pose, mean jump 11.4->7.8
# degrees, with no change to the already-good palm-toward-camera pose
# (mean 5.2 degrees both). Replaces BOTH earlier mechanisms -- there is no
# longer a separate raw-jump filter or geometric-substitution gate, this is
# the sole noise-handling mechanism.
CONDITIONING_ALPHA_LOW = 0.015   # at/below this conditioning_norm, alpha=0 (fully trust the prediction)
CONDITIONING_ALPHA_HIGH = 0.06   # at/above this conditioning_norm, alpha=1 (fully trust the raw reading)


def _reliability_alpha(conditioning_norm: float) -> float:
    """Linear ramp from 0 (fully degenerate -> trust the prediction) to 1
    (comfortably well-conditioned -> trust the raw reading), the continuous
    generalization of the old hard GEOMETRIC_DEGENERACY_NORM cutoff --
    mirrors Ernst & Banks' inverse-variance-weighted sensory cue
    integration (a degraded cue is down-weighted smoothly, not discarded
    outright at an arbitrary threshold)."""
    if conditioning_norm <= CONDITIONING_ALPHA_LOW:
        return 0.0
    if conditioning_norm >= CONDITIONING_ALPHA_HIGH:
        return 1.0
    return (conditioning_norm - CONDITIONING_ALPHA_LOW) / (CONDITIONING_ALPHA_HIGH - CONDITIONING_ALPHA_LOW)


@dataclass
class Cube:
    mesh: Mesh
    size: int
    position: Tuple[float, float]  # top-left corner, pixel coordinates
    owner: Optional[str] = None
    orientation: Tuple[float, float, float, float] = IDENTITY_QUATERNION
    # Relative-rotation baseline, captured at the instant of grab (see
    # update_hands' docstring) -- direct request 2026-08-01: a cube must
    # keep its OWN orientation at grab time, not snap to the hand's
    # orientation; it should only rotate by however much the hand rotates
    # AFTER the grab. `grab_hand_orientation` is the hand's quaternion at
    # that instant, `grab_cube_orientation` is the cube's own orientation
    # at that instant (unchanged) -- both None while unowned.
    grab_hand_orientation: Optional[Tuple[float, float, float, float]] = None
    grab_cube_orientation: Optional[Tuple[float, float, float, float]] = None
    # Translation-pivot fix (§14.1/§14.1.1) -- distance-weighted live
    # landmark tracking, the translation counterpart of the rotation
    # baseline pair above. `grab_landmark_weights` (frozen at grab, never
    # recomputed) maps each candidate landmark index to its normalized
    # inverse-distance-from-the-object weight; `grab_residual_offset` is
    # the small constant added every frame so the grab frame itself is
    # exactly continuous (no pop) -- see _compute_grab_weights' docstring.
    grab_landmark_weights: Optional[Dict[int, float]] = None
    grab_residual_offset: Optional[Tuple[float, float]] = None
    # ⭐ F1 step 2, mirroring production's Cube.
    grab_grip_offset: Optional[Tuple[float, float]] = None
    # ⭐ A1's fade budget, in milliseconds OF HAND MOVEMENT still to be spent.
    grab_grip_fade_ms: Optional[float] = None
    # ⭐ A1-in-Z: how far the object's depth ANCHOR still has to travel to reach
    # the hand's. Walked to zero on the same progress as the in-plane offset, so
    # the grab is continuous in depth instead of switching in one frame.
    grab_depth_offset_m: Optional[float] = None
    grab_hand_depth_m: Optional[float] = None
    # B4 alternative anchor (Resources/palm_anchor.py): the frozen metric offset
    # in the PALM's own frame. Used instead of the two fields above when
    # update_hands is given an `anchor`; None for §14.1's incumbent path.
    grab_anchor_state: Optional[object] = None
    # ⭐⭐ 4.2 -- Z-AXIS TRANSLATION, mirroring production's `CubeWindow.Cube`
    # field for field (N6). `size` is the extent AT THE REFERENCE DEPTH,
    # `depth_m` is where the object actually is, and `grab_depth_m` is the Z
    # baseline frozen at the grab so the grab frame is continuous in Z as well.
    depth_m: float = palm_geometry.REFERENCE_DEPTH_M
    grab_depth_m: Optional[float] = None


# ⛔⛔ `HandOrientationFilter` WAS REMOVED HERE (owner, 2026-08-24). Archived whole
# in `Resources/_archived_predictive_orientation_filter.py`, together with the
# measurement that retired it: Horn replaced its output whenever it succeeded, and
# Horn returned None on **0 of 9091 hand-frames** across four recordings -- so the
# filter reached the cube on none of them. ⚠ `_reliability_alpha` STAYS (a
# conditioning measure, and the operator-facing `reliability` readout).
# ⭐ N6: production dropped it in the same commit, in the same place.

@dataclass
class CubeState:
    window_size: Tuple[int, int]
    cubes: Dict[str, Cube] = field(default_factory=dict)
    # Thumb-outward snap rule state (§13.6) — see update_hands' docstring.
    last_known_thumb_outward: Dict[str, bool] = field(default_factory=lambda: {h: False for h in TRACKED_HANDS})
    # ⭐ Palm CONDITIONING (0-1) per hand, for the on-screen diagnostic
    # (`_draw_hand`) — 1.0 = the palm's two vectors are well separated and the
    # frame's orientation is trustworthy, 0.0 = they are nearly parallel and it is
    # not. ⚠ It no longer WEIGHTS anything: the predictive filter it used to feed
    # was removed 2026-08-24 (see the note where the class used to live). It is
    # kept because it tells the operator when a degenerate palm is the reason the
    # cube is misbehaving, which nothing else on screen says.
    last_hand_reliability_alpha: Dict[str, float] = field(default_factory=lambda: {h: 1.0 for h in TRACKED_HANDS})
    # §16.15: per-hand state for an optional least-squares rotation estimator.
    # Reset on tracking loss -- never fit against a dead track.
    hand_rotation_states: Dict[str, object] = field(default_factory=lambda: {h: None for h in TRACKED_HANDS})
    # ⭐ D1/D2/D3 (queue Phase D). These live on CubeState rather than at module
    # level SO THAT SEVERAL ARMS CAN RUN AT ONCE off one camera: `--arms 3` gives
    # each arm its own trackers, its own coast window and its own blend, driven
    # by ONE detection and ONE identity resolution. That is what makes the
    # three-way comparison one-variable -- the same discipline as B4's six-arm
    # session, where each row was a single change on the row above.
    # ⚠ Production keeps ITS copies at module level in `HandsTriggeredActions`;
    # it runs exactly one arm, so it needs no such split. The VALUES must stay in
    # step (§13.6.1) even though the storage differs.
    bridge_window_ms: float = hand_state.BRIDGE_WINDOW_MS
    resync_blend_frames: int = 3
    arm_label: str = "blend"
    # ⭐⭐ F1 PER-ARM CONFIG -- what makes a three-window rig possible on ONE
    # camera. Defaults mirror the module globals, so an arm that does not set them
    # behaves exactly as production does.
    #   use_tips  : step 2 -- fingertip barycentre drives snap + translation
    #   trim_gain : step 4 -- fingertip ROTATION trim (0.0 = shipped Horn)
    # ⚠ The GRIP TRACKER stays shared and upstream: every arm sees the same
    # filtered barycentre and only differs in whether it USES it. Giving each arm
    # its own filter would add a second variable and break the rig.
    use_tips: bool = None
    trim_gain: float = None
    tip_trims: Dict[str, object] = field(
        default_factory=lambda: {h: tip_trim.TipTrim() for h in TRACKED_HANDS})
    # ⭐ 4.1/T3 A/B: "track" keys ownership on the stable DR-1 id (what shipped),
    # "label" reproduces the OLD handedness keying so the two can be compared
    # live on ONE camera and ONE detection -- the only difference between the
    # panels is this field. Same one-variable discipline as the D2/D3 arms.
    ownership: str = "track"
    # ⭐ T6d A/B: THIS ARM's rotation estimator, overriding the one
    # `update_hands_all` is called with. `None` = use the caller's, which is what
    # every existing rig and harness does, so their behaviour is untouched.
    # ⚠ It has to live PER ARM, not per call, because the whole point of the rig is
    # two estimators on ONE camera and ONE detection -- a per-call estimator can
    # only ever compare a panel against itself.
    rotation: object = None
    # ⭐⭐ THE LAG A/B (owner, 2026-08-24: *"the cube is lagging the hand and this
    # feels very uncomfortable"*). "frame" = today's FIXED PER-FRAME factor; "time"
    # = a real exponential with a time constant in MILLISECONDS.
    #
    # ⛔⛔ WHY THE PER-FRAME FORM IS A DEFECT AND NOT A STYLE CHOICE. `0.35` per frame
    # is a settling time of 2.32 FRAMES, so the feel is whatever the camera is doing:
    # measured 111 ms at 48.0 ms/frame (good light) and 149 ms at 64.0 ms/frame
    # (poor light) -- **the same code feels 34% laggier in a darker room**, because
    # the webcam drops its rate under auto-exposure. On a phone, where frame rates
    # vary far more, that is first-order.
    # ⭐ `tau_ms` is the SAME quantity the owner can actually reason about: "how long
    # the cube takes to catch up". At a steady 64 ms frame time, tau = 149 ms
    # reproduces today's 0.35 EXACTLY, which is what makes the A/B honest.
    slerp_mode: str = "frame"
    slerp_tau_ms: float = 149.0
    # Previous frame's clock for this arm, for the dt the time-based form needs.
    last_frame_ms: Optional[float] = None
    # ⭐ Previous frame's grip point per hand — A1's fade needs a SPEED, and the
    # speed has to come from the same point the object is following.
    last_grip_px: Dict[str, Optional[Tuple[float, float]]] = field(
        default_factory=lambda: {h: None for h in TRACKED_HANDS})
    # Cube name -> the handedness slot whose tracker governs it. See production's
    # `_owner_hand_of_cube`: release must follow the owning TRACK across a
    # relabel, and must keep the last known hand while the track is absent so
    # D2's coast still applies. Per-arm, so the arms cannot contaminate.
    owner_hand_of_cube: Dict[str, str] = field(default_factory=dict)
    # ⚠ N6 PARITY, added 2026-08-22 after the owner hit the strand in the DEBUG
    # tool at 300 and 450 ms: production had `OWNER_ABSENT_RELEASE_MS` and this
    # tool did NOT, so the safety net existed on only one side -- the exact
    # divergence class N6 exists to prevent, created while fixing a divergence.
    # Per-arm, because each arm owns its own cubes and its own timers.
    owner_absent_since: Dict[str, float] = field(default_factory=dict)
    # ⭐ T3 NARROW REMAP (2026-08-22): cube name -> the DR-1 TRACK id that holds
    # it, captured at the snap. Ownership itself stays a SLOT NAME, so nothing
    # else changes; this only lets the owner slot FOLLOW its track when DR-1
    # swaps the two hands between slots. Without it the cube follows the LABEL to
    # the other physical hand with no release, no snap and no rule-3 check --
    # the recorded back-of-hand steal (`2026-08-22_184440_n8_back_steal_b`, f478).
    # ⚠ Per-arm, like every other cube field, so the arms cannot contaminate.
    holder_track: Dict[str, int] = field(default_factory=dict)
    hand_state_trackers: Dict[str, object] = field(default_factory=dict)
    # ⭐ Finishing 4.1's migration, mirroring production (N6). Per-hand state is
    # rebound each frame to whichever TRACK is in that slot, so a relabel carries
    # a hand's own palm/back reading, coast, filter and snap permission with it
    # instead of handing them to the other hand. Per ARM, because each arm owns
    # its own cubes and its own history.
    track_registry: object = None
    resync_blend_left: Dict[str, int] = field(default_factory=lambda: {h: 0 for h in TRACKED_HANDS})
    # ⭐ 4.2: the RATIO estimator that drives a held object's depth. PER ARM,
    # because its baseline is captured at THAT arm's grab and the arms grab at
    # different moments -- sharing one would baseline every arm against
    # whichever grabbed first. ⚠ The ABSOLUTE estimator behind the snap gate is
    # NOT here: it has no grab dependency, so it is upstream and shared, exactly
    # like `_palm_facing_trackers`. Keeping the arms' only difference their own
    # configuration is what makes the rig one-variable.
    depth_ratio_trackers: Dict[str, object] = field(
        default_factory=lambda: {h: _PDepth.DepthRatioTracker() for h in TRACKED_HANDS})
    # Per-arm live counters for the on-screen comparison.
    stats: Dict[str, int] = field(
        default_factory=lambda: {"bridged_frames": 0, "saves": 0, "releases": 0})

    def __post_init__(self):
        if not self.hand_state_trackers:
            self.hand_state_trackers = {
                h: hand_state.HandStateTracker(bridge_window_ms=self.bridge_window_ms)
                for h in TRACKED_HANDS
            }
        if not self.cubes:
            self.cubes = {
                "large": Cube(
                    mesh=_make_cube_mesh(FACE_COLOR_YELLOW, FACE_COLOR_VIOLET, FACE_COLOR_TURQUOISE),
                    size=CUBE_SIZE_LARGE,
                    position=self._centered_position(CUBE_SIZE_LARGE),
                ),
                "small": Cube(
                    mesh=_make_cube_mesh(FACE_COLOR_GREEN, FACE_COLOR_RED, FACE_COLOR_BLUE),
                    size=CUBE_SIZE_SMALL,
                    position=self._centered_position(CUBE_SIZE_SMALL),
                ),
            }

    def _centered_position(self, size: int) -> Tuple[float, float]:
        return ((self.window_size[0] - size) / 2, (self.window_size[1] - size) / 2)

    def projected_size(self, name: str) -> float:
        """The named object's on-screen extent at its CURRENT depth (4.2).
        Mirrors `CubeWindow.projected_size` (N6)."""
        return self.projected_size_of(self.cubes[name])

    def projected_size_of(self, cube: Cube) -> float:
        """⚠ Every consumer of an object's screen extent must use THIS, not
        `cube.size`: the grab radius, the centre, the clamp and the renderer."""
        return palm_geometry.projected_size_px(cube.size, cube.depth_m)

    def cube_center(self, name: str) -> Tuple[float, float]:
        # ⚠ 4.2: the PROJECTED extent, not `cube.size` -- `position` is the
        # top-left of what is actually drawn.
        cube = self.cubes[name]
        size = self.projected_size_of(cube)
        return (cube.position[0] + size / 2, cube.position[1] + size / 2)

    def unowned_cube_names(self):
        return [name for name, cube in self.cubes.items() if cube.owner is None]

    def cube_owned_by(self, owner_key) -> Optional[str]:
        for name, cube in self.cubes.items():
            if cube.owner == owner_key:
                return name
        return None

    def snap_cube(self, name: str, owner_key, holder_track=None) -> None:
        self.cubes[name].owner = owner_key
        # T3: remember WHICH HAND took it, so the owner slot can follow that hand
        # across a relabel. `None`/-1 means no identity this frame -- store
        # nothing rather than a sentinel, so `remap_owner` simply no-ops.
        if holder_track is not None and holder_track >= 0:
            self.holder_track[name] = holder_track
        else:
            self.holder_track.pop(name, None)

    def release_cube(self, name: str) -> None:
        cube = self.cubes[name]
        cube.owner = None
        self.holder_track.pop(name, None)
        cube.grab_hand_orientation = None
        cube.grab_cube_orientation = None
        cube.grab_landmark_weights = None
        cube.grab_residual_offset = None
        cube.grab_grip_offset = None
        cube.grab_grip_fade_ms = None
        cube.grab_depth_offset_m = None
        cube.grab_hand_depth_m = None
        cube.grab_anchor_state = None
        cube.grab_depth_m = None    # 4.2: depth freezes in place, like position

    def set_target_center(self, name: str, center: Tuple[float, float]) -> None:
        """⭐⭐ U9 (N6, mirrors `CubeWindow.set_target_center`): confine the object
        to the PLAY AREA, not to the window. The hand-side margin cannot enforce
        this -- translation is grab-relative, so the object keeps its own offset
        from the hand and creeps outward on every grab-push-drop cycle. Trigger
        vs invariant.

        ⭐⭐ 4.2: the play area is now a WORLD-SPACE VOLUME (owner, 2026-08-23) --
        at the object's depth, the frustum's lateral extent inset by the 42.5 mm
        world margin. The on-screen boundary MOVES with depth; that is intended.

        ⚠ Takes the CENTRE, and depth must already be set for this frame: the
        projected extent depends on depth, and `position` is derived from the
        centre with it."""
        cube = self.cubes[name]
        cx, cy = palm_geometry.clamp_to_play_volume(
            center[0], center[1], cube.depth_m, cube.size, self.window_size)
        size = self.projected_size_of(cube)
        cube.position = (cx - size / 2.0, cy - size / 2.0)


def _is_thumb_outward(pixel_landmarks, handedness: str) -> bool:
    """True when the hand is oriented with the thumb outward (back of hand
    facing the camera) -- GESTURE_PIPELINE_SPEC.md §13.6.

    **Delegates to Resources/palm_geometry.py, SHARED with production's
    HandsTriggeredActions.py** (queue item 1.2, 2026-08-03). This file used to
    carry its own copy of the formula, hand-synced with production's -- the same
    duplication that produced the production-only inversion of 2026-08-01
    (§13.6.1), and the same pattern already fixed for the identity tracker (N6).
    Do NOT reinline the maths here; the whole point is one source."""
    return palm_geometry.is_thumb_outward(pixel_landmarks, handedness)


def _edge_on_measure(pixel_landmarks) -> float:
    """0..1, how far the palm is from edge-on (M5a, queue item 1.2). Mirrors
    production's `_edge_on_measure`. Not yet gating anything -- DR-2 (item 2.2)
    is what will consume it."""
    return palm_geometry.edge_on_measure(pixel_landmarks)


def _hand_position(pixel_landmarks) -> Tuple[float, float]:
    """⭐ Delegates to `palm_geometry.palm_center_px` since 2026-08-25 -- the same
    five landmarks and the same mean this held inline, now defined once and shared
    with production (`analysis/verify_handinput.py` §5 asserts the equality). The
    move `_is_thumb_outward` above already made, for the same reason: a geometric
    convention that exists twice is one that eventually differs."""
    return palm_geometry.palm_center_px(pixel_landmarks)


def _weighted_position(weights: Dict[int, float], pixel_landmarks) -> Tuple[float, float]:
    """Distance-weighted combination of candidate landmarks' CURRENT pixel
    positions (§14.1's translation-pivot fix, chosen mechanism). Used both
    to compute the grab-time weights' own no-pop residual and to track
    position live every frame after -- same formula, different landmark
    positions."""
    x = sum(w * pixel_landmarks[i][0] for i, w in weights.items())
    y = sum(w * pixel_landmarks[i][1] for i, w in weights.items())
    return (x, y)


def _compute_grab_weights(object_pos_at_grab: Tuple[float, float], pixel_landmarks) -> Dict[int, float]:
    """Freezes distance-weighted candidate-landmark weights at the moment
    of grab (§14.1.1's chosen, offline-verified mechanism): each candidate
    (5 fingertips + 4 non-thumb MCPs) is weighted by normalized inverse
    distance from the object's own position at that instant -- the
    literal, computable version of "the phalanges are locked once the
    object is grabbed." Never recomputed during the hold; the caller also
    needs a `grab_residual_offset` (object_pos_at_grab minus this
    function's own weighted combination at grab) added every frame after,
    since inverse-distance weighting doesn't interpolate exactly through
    the query point -- see AnalyzeTranslationPivot.py's identical
    construction, verified offline (0.0000px no-pop error, 7/7 real hold
    intervals) before being ported here."""
    raw = {i: 1.0 / (math.hypot(object_pos_at_grab[0] - pixel_landmarks[i][0],
                                 object_pos_at_grab[1] - pixel_landmarks[i][1]) + TRANSLATION_EPSILON_PX)
           for i in TRANSLATION_CANDIDATE_LANDMARKS}
    total = sum(raw.values())
    return {i: w / total for i, w in raw.items()}


# ⚠ `_top_left_for_center` was removed in 4.2 (N6: production dropped it too).
# It converted with the NOMINAL size, which stops being the on-screen extent the
# moment depth is driven. `CubeState.set_target_center` owns the conversion now,
# with the projected extent, in one place.


# --- Rotation: orthonormal-frame -> quaternion -> slerp ---------------------
# PART_ONE.md §2: "Track hand orientation as a quaternion built from an
# orthonormal frame (Gram-Schmidt on wrist->index_MCP and wrist->pinky_MCP
# from world_landmarks), and slerp the cube's quaternion toward it each
# frame. Never decompose into separate roll/pitch/yaw Euler angles at any
# point -- gimbal lock is a property of that decomposition, not of the
# underlying rotation itself." Hand-rolled rather than via scipy: scipy is
# only incidentally present in this venv (a transitive dep of mediapipe's
# `jax`, not a declared requirement -- see requirements.txt), not something
# to build a core mechanic on without adding it as a real dependency.

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]  # (w, x, y, z)


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
    """Gram-Schmidt orthonormal frame from a hand's world landmarks.

    REVISED 2026-08-01 (data-driven, see the memory/handoff for the full
    analysis): the original construction (e1 along wrist->index_MCP, e2 the
    wrist->pinky_MCP direction orthogonalized against e1) uses two vectors
    that both point from the wrist toward opposite ends of the SAME
    knuckle row -- only moderately non-parallel even in a neutral pose.
    A PITCH rotation (about the screen's horizontal axis) sweeps exactly
    that knuckle-row axis edge-on to the camera at the crossing, driving
    the two vectors' 3D reconstruction toward collinearity right when the
    hand is edge-on -- normalizing then divides by a near-zero
    orthogonalized component, amplifying ordinary landmark noise into wild
    swings. A YAW rotation (about the vertical axis) instead foreshortens
    the wrist->fingertip axis, which the OLD construction never used at
    all -- explaining exactly the pitch-bad/yaw-fine asymmetry observed
    live and confirmed by recording (r=-0.52 correlation between this
    function's orthogonalized-vector norm and the per-frame rotation
    jump, 16x mean-jump difference between the most- and least-degenerate
    quartiles of frames).

    New pair: e1 along index_MCP->pinky_MCP (the knuckle-row "width" axis,
    taken directly rather than via the wrist -- larger magnitude, one less
    wrist-noise term), e2 the wrist->middle_MCP "length" axis orthogonalized
    against e1. These two are much closer to genuinely orthogonal in a
    normal pose, giving far more margin before any single rotation axis
    drives them toward collinearity (verified: worst-case orthogonalized
    norm across a full pitch-crossing recording improved from 0.0008 to
    0.0025, and specifically AT the three observed crossings from
    0.011-0.025 up to 0.033-0.049 -- roughly 2-4x better exactly where it
    mattered). Some rotation axis can likely still degrade any 2-vector
    choice, but not pitch specifically, at least not this badly.

    Chirality is preserved on purpose (verified against real recordings:
    211/211 frames, palm-normal dot product with the OLD construction's
    palm-normal averaged 0.991, i.e. essentially the same up-vector, not
    flipped) -- e1 is deliberately index_MCP->pinky_MCP, not the reverse;
    swapping that order would invert the rotation SENSE (clockwise hand
    twist would rotate the cube counterclockwise), which would have broken
    yaw/roll, not just left pitch unfixed. Do not swap it without
    re-verifying chirality the same way.

    Returns the rotation matrix as its three orthonormal column vectors
    (e1, e2, e3) -- this IS the target hand-orientation, converted to a
    quaternion by _matrix_to_quaternion below -- plus the pre-normalization
    norm of the orthogonalized e2 vector, a direct numerical-conditioning
    signal (small = e1/e2 nearly collinear = this frame is close to the
    known degenerate zone) fed into the predictive filter's reliability
    weighting (`_reliability_alpha`, see "Attempt 3" above
    CONDITIONING_ALPHA_LOW) in update_hands."""
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
    """Rotation-matrix -> quaternion via Shepperd's method (branch on the
    largest of trace/diagonal terms) -- numerically stable everywhere,
    unlike the naive sqrt(1+trace) formula which loses precision as
    trace -> -1 (a 180 degree rotation, well within reach of a hand twisting
    in front of a camera). `cols` = (e1, e2, e3) column vectors, i.e.
    m[row][col] = cols[col][row]."""
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
    """Hamilton product q1*q2 -- composing q1 then q2 in world/global frame
    is the product q2*q1 (matching rotation-matrix composition order); used
    below as `q2 * conjugate(q1)` to get the world-frame rotation that
    takes orientation q1 to orientation q2."""
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
    """Returns (orientation quaternion, conditioning_norm) -- the latter is
    _orthonormal_frame's raw numerical-conditioning signal, fed into the
    predictive filter's reliability weighting in update_hands (see
    "Attempt 3" above CONDITIONING_ALPHA_LOW)."""
    e1, e2, e3, conditioning_norm = _orthonormal_frame(
        world_landmarks[WRIST], world_landmarks[INDEX_MCP], world_landmarks[PINKY_MCP], world_landmarks[MIDDLE_MCP]
    )
    return _matrix_to_quaternion((e1, e2, e3)), conditioning_norm


def _quat_slerp(q0: Quat, q1: Quat, t: float) -> Quat:
    """Shortest-path spherical interpolation: q and -q represent the same
    rotation, so negate q1 first if the dot product is negative (otherwise
    interpolation can take the long way around, a classic quaternion-slerp
    bug). Falls back to normalized linear interpolation when q0/q1 are
    nearly identical, where slerp's own formula divides by a near-zero
    sin(theta0)."""
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


def _quat_rotate_vector(q: Quat, v: Vec3) -> Vec3:
    """Rotate a 3-vector by quaternion q (w,x,y,z): v' = v + 2w(qv x v) +
    2(qv x (qv x v)), the standard closed form for q * (0,v) * q^-1 that
    avoids materializing full quaternion multiplication for a single
    vector."""
    w, x, y, z = q
    qv = (x, y, z)
    uv = _vec_cross(qv, v)
    uuv = _vec_cross(qv, uv)
    return (v[0] + 2.0 * (w * uv[0] + uuv[0]), v[1] + 2.0 * (w * uv[1] + uuv[1]), v[2] + 2.0 * (w * uv[2] + uuv[2]))


def _make_continuous(q: Quat, reference: Quat) -> Quat:
    """Flip q's sign if needed so it's on the same hemisphere as reference
    (quaternion double-cover: q and -q are the same rotation) -- must be
    resolved before any quaternion ARITHMETIC (multiply/subtract), unlike
    _quat_slerp which already handles this internally for its own use."""
    d = q[0] * reference[0] + q[1] * reference[1] + q[2] * reference[2] + q[3] * reference[3]
    return tuple(-c for c in q) if d < 0 else q


def _try_snap(state: CubeState, handedness: str, hand_pos: Tuple[float, float],
              hand_depth_m=None, exclude=frozenset()) -> Optional[str]:
    """Grab radius scales to EACH candidate cube's OWN size (2026-08-01,
    matching production's CubeWindow.py fix) -- a single shared radius
    stopped making sense once the two cubes have different sizes.

    ⭐⭐ 4.2, mirroring production's `_try_snap` (N6): the check is 3D. Lateral
    stays the PROJECTED grab radius (so X/Y feel is unchanged and now scales
    with depth); axial uses its own, much looser `GRAB_Z_TOLERANCE_M`, because
    the hand depth carries a constant per-user scale bias a spherical check
    would make un-grabbable. `hand_depth_m is None` -> the pre-4.2 2D check."""
    best_name, best_dist = None, None
    for name in state.unowned_cube_names():
        if name in exclude:
            continue
        cube = state.cubes[name]
        # ⭐ Mirrors production exactly, through the ONE shared implementation
        # (`Resources/object_extent.py`) -- the grab region is the one thing the
        # two renderers must never disagree about.
        grab_radius = object_extent.grab_extent(
            state.projected_size_of(cube), cube.orientation,
            cube.mesh.vertices, CUBE_PERSPECTIVE_DISTANCE_RATIO,
        ) * GRAB_RADIUS_MULTIPLIER
        cx, cy = state.cube_center(name)
        dist = math.hypot(hand_pos[0] - cx, hand_pos[1] - cy)
        if dist > grab_radius:
            continue
        if hand_depth_m is not None and \
                abs(hand_depth_m - cube.depth_m) > _PDepth.GRAB_Z_TOLERANCE_M:
            continue
        if best_dist is None or dist <= best_dist:
            best_name, best_dist = name, dist
    if best_name is not None:
        state.snap_cube(best_name, _owner_key(handedness, state),
                        holder_track=_hand_track_ids.get(handedness, -1))
    return best_name


def update_hands_all(arms, hand_data_by_hand, now_ms=None, **kw):
    """Advance every arm by one frame from ONE observation.

    ⭐ The single timestamp read lives here, not in the loop over arms: three
    separate clock reads would give the arms slightly different gap lengths, and
    a comparison whose arms disagree about how long the gap was is not a
    comparison. `analysis/verify_three_arm_bridge.py` drives this same function,
    so the test and the tool cannot diverge."""
    if now_ms is None:
        now_ms = time.perf_counter() * 1000.0
    for i, arm in enumerate(arms):
        # ⭐ T6d: an arm may carry its OWN rotation estimator (the shipped-Horn vs
        # smoothing rig). Absent one, every arm gets the caller's, which
        # is exactly what the D2/D3, U5 and ownership rigs already do.
        per_arm = getattr(arm, "rotation", None)
        # ⭐ handinput: only the FIRST arm feeds the input system. An A/B rig runs
        # the same hand through several policies, and publishing all of them would
        # emit contradictory events for one physical hand -- the arms disagree on
        # purpose. Arm 0 is the one whose panel is the shipped behaviour.
        pose_out = {} if i == 0 else None
        update_hands(arm, hand_data_by_hand, now_ms=now_ms, pose_out=pose_out,
                     **({**kw, "rotation": per_arm} if per_arm is not None else kw))
        if pose_out is not None:
            _publish_hand_input(arms[0], hand_data_by_hand, pose_out, now_ms)


def _draw_bridge_hud(frame, state, height):
    """Per-arm overlay: which arm this panel is, and what it has done so far.

    ⚠ `rel` (releases) is the number being judged: in the OFF panel it is the
    familiar rate of cubes dropping for no visible reason, and it should be lower
    in the other two. `brid` is how often the coast was used at all -- ⭐ IF IT
    STAYS NEAR ZERO THE SESSION NEVER PROVOKED A DROPOUT and nothing has been
    tested, whatever the panels look like.

    ⚠ The counters are NOT the verdict. Three cubes released at different moments
    is a thing you WATCH; the numbers are there so the session leaves a trace
    behind, not so the biggest number wins."""
    colour = BRIDGE_ARM_COLOURS.get(state.arm_label, (128, 128, 128))
    cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), colour, 2)
    cv2.putText(frame, _arm_title(state), (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)
    held = sum(1 for c in state.cubes.values() if c.owner is not None)
    # 4.1/M9 read-only depth readout, on the first panel only (one estimator).
    if state is arms_first_panel[0]:
        parts = []
        for h in TRACKED_HANDS:
            rd = _depth_readout.get(h)
            if rd is not None:
                parts.append(f"{h[0]} {rd[0]:.2f}{'' if rd[1] else '*'}")
            # ⭐ 4.2: the ABSOLUTE depth the snap gate compares against, in cm,
            # beside each object's own depth. ⚠ THIS LINE IS THE INSTRUMENT FOR
            # THE ONE FAILURE MODE THAT WOULD OTHERWISE LOOK LIKE A DEAD BUILD:
            # the hand depth is scaled by NOMINAL anatomy, so a user whose hands
            # are far off the median reads a constant offset from the object's
            # depth and nothing can be picked up. Seeing "hand 55 / obj 40" says
            # that immediately; a cube that just refuses to be grabbed does not.
            sd = _snap_depth_trackers[h].depth_m
            if sd is not None:
                parts.append(f"{h[0]}z {sd * 100:.0f}cm")
            # ⭐⭐ SQUARE = how square the palm is to the camera (`edge_on_measure`:
            # 0 = edge-on, 1 = knuckle row square to the lens).
            #
            # ⭐ THE REASON IT IS ON THE HUD: it is **INVARIANT UNDER PURE ROLL**.
            # Roll is an in-image-plane rotation, so both palm vectors turn together
            # -- their lengths and the angle between them do not change, and neither
            # does this number. It drops ONLY when yaw or pitch leaks in. So for a
            # roll take the operator can simply hold it high and steady, instead of
            # trying to judge "am I still perpendicular to the camera?" by feel --
            # which the owner reported as too hard to do on 2026-08-23, discarding a
            # take over it.
            # ⚠ It is a LIVE OPERATOR AID, not a gate: nothing acts on it here.
            lm = _last_pixel_landmarks.get(h)
            if lm is not None:
                parts.append(f"{h[0]}sq {palm_geometry.edge_on_measure(lm):.2f}")
        parts += [f"{n[:1]}obj {c.depth_m * 100:.0f}cm"
                  for n, c in state.cubes.items()]
        if parts:
            # ⚠ y = height-36, NOT height-12: the counters line below draws at
            # height-14 AFTER this one, in a larger brighter font, and painted
            # straight over it -- the readout was rendered every frame and
            # invisible in every one. Reported by the owner as "there was no such
            # depth line". Keep these two rows apart.
            cv2.putText(frame, "depth " + "  ".join(parts) + "   (*=held)",
                        (10, height - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(frame,
                f"rel {state.stats['releases']}   saves {state.stats['saves']}"
                f"   brid {state.stats['bridged_frames']}   held {held}"
                f"   relabels {_relabel_events[0]}",
                (10, height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)
    # ⭐ handinput: the ACTION layer's own state, so it is visible live rather than
    # only in a trace file. Per hand: the `tracked` phase, RDY when `grab_ready` is
    # performing, ROT when a rotation reference is frozen. ⚠ It reports the input
    # system's view; the cube is still driven by the logic above, so a disagreement
    # between this line and the cube is a real finding, not a display bug.
    if _hand_input is not None:
        cv2.putText(frame, _hand_input.summary() + f"   ev {_hand_input.event_count}",
                    (10, height - 58), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (140, 255, 140), 1, cv2.LINE_AA)


def _create_sliders():
    """The smoothing trackbar, in its own window.

    ⭐ The trackbar's integer IS tau in milliseconds. That is deliberate and it
    was learned the hard way: an earlier version made it an INDEX into a ladder of
    choices, and OpenCV drew that index beside the name "SMOOTH ms" -- so the panel
    read "3" while applying 20 ms, and the take was reported as "3 ms is good".
    A slider whose displayed number is not the applied value is worse than an
    unlabelled one, because it invites a confident wrong reading.
    """
    cv2.namedWindow(SLIDER_WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(SLIDER_WIN, 520, 400)
    for name, maxv, start, _ in SLIDERS:
        cv2.createTrackbar(name, SLIDER_WIN, start, maxv, lambda _v: None)


def _tau_ms_to_cutoff_hz(tau_ms):
    """tau (ms) -> the 1€ filter's cutoff (Hz). Exact inverse of 1/(2*pi*fc)."""
    return 1.0 / (2.0 * math.pi * (tau_ms / 1000.0))


def _read_sliders() -> None:
    """Copy every trackbar into the value it controls.

    ⚠ Swallows the window-gone error rather than letting it end a live take: the
    owner may close the panel mid-session, and the last value is the right thing
    to carry on with. ⛔ Reads ALL sliders or none -- a partial read would leave
    the tool in a state no slider position describes.
    """
    global SLERP_TAU_MS, JITTER_TAU_MS, JITTER_BETA, GRAB_RADIUS_MULTIPLIER
    global GRIP_ALIGN_MOVING_MS, GRIP_ALIGN_MASK_RATIO, GRAB_Z_TOLERANCE_M
    try:
        vals = [spec[3](cv2.getTrackbarPos(spec[0], SLIDER_WIN)) for spec in SLIDERS]
    except cv2.error:
        return
    # ⚠ THREE sliders now -- three others are parked (see `SLIDERS`). The parked
    # values are NOT re-read here; they keep their module defaults.
    (SLERP_TAU_MS, _gain, GRAB_RADIUS_MULTIPLIER, GRIP_ALIGN_MOVING_MS,
     GRIP_ALIGN_MASK_RATIO, GRAB_Z_TOLERANCE_M) = vals
    # ⚠ The SHARED module global, like TRIM gain above: `decay_grip_offset` reads
    # it internally, and the two tools cannot run at once (one camera, DSHOW is
    # exclusive), so there is no window in which they could disagree.
    fingertips.GRIP_ALIGN_MASK_RATIO = GRIP_ALIGN_MASK_RATIO
    # ⚠ Same reasoning: both tools read this attribute at call time, and they can
    # never run at once, so driving the shared module is safe and keeps ONE value.
    _PDepth.GRAB_Z_TOLERANCE_M = GRAB_Z_TOLERANCE_M

    # ⭐ The fingertip filter is SHARED across arms by design, so configuring it
    # here configures every panel at once -- which is correct: the arms differ in
    # whether they USE the grip point, never in how it is filtered.
    _enabled = JITTER_TAU_MS > 0.0
    for _t in _grip_trackers.values():
        if _enabled:
            _t.configure(min_cutoff_hz=_tau_ms_to_cutoff_hz(JITTER_TAU_MS),
                         beta=JITTER_BETA, enabled=True)
        else:
            # ⚠ Disable WITHOUT touching the cutoff: there is no meaningful
            # cutoff at tau = 0, and writing a placeholder would be a trap for
            # whoever later flips the flag without re-reading this.
            _t.configure(enabled=False)

    # ⚠ The module GLOBAL, not a per-arm value: arms that pin their gain (the rig
    # controls, at 0.0) are unaffected, and arms that leave it None follow this.
    tip_trim.TRIM_GAIN = _gain

    # ⚠ `GRAB_RADIUS_MULTIPLIER` above rebinds THIS MODULE's name only, and that is
    # deliberate: `hand_state` keeps the shipped value, so sweeping the slider
    # tunes the debug tool without silently editing the constant production reads.
    # ⛔ Which also means a value settled here has to be written into
    # `hand_state.GRAB_RADIUS_MULTIPLIER` to survive the session -- the same
    # discipline tau went through.



def settled_values() -> dict:
    """Every live-tuned value, with the unit its slider speaks. ⭐ ONE PLACE.

    ⛔⛔ THIS EXISTS BECAUSE THE VALUES WERE ONCE UNRECOVERABLE. On 2026-08-26 the
    owner tuned six sliders to a setting they liked and asked to keep it -- and the
    numbers lived only in a running process's trackbars. `tau_changes` had captured
    the smoothing slider since `L1` and nothing had captured the other five, so a
    session's worth of tuning could be lost by closing a window.
    ⭐ Written into every take's `meta.json` AND printed on exit, so a setting the
    owner likes survives the session that produced it.
    """
    return {
        "slerp_tau_ms": SLERP_TAU_MS,
        "trim_gain": tip_trim.TRIM_GAIN,
        "trim_max_deg": tip_trim.TRIM_MAX_DEG,
        "grab_radius_x_footprint": GRAB_RADIUS_MULTIPLIER,
        "grip_align_moving_ms": GRIP_ALIGN_MOVING_MS,
        "grip_align_mask_ratio": GRIP_ALIGN_MASK_RATIO,
        "grab_z_margin_m": GRAB_Z_TOLERANCE_M,
        "jitter_tau_ms": JITTER_TAU_MS,
        "jitter_beta": JITTER_BETA,
    }


def print_settled_values(prefix="[LiveSnapDebug]"):
    """Print the tuned values in a form that can be pasted back into the code."""
    print(f"{prefix} ---- SLIDER VALUES AT EXIT ----")
    for k, v in settled_values().items():
        print(f"{prefix}   {k:<26} = {v!r}")
    print(f"{prefix} -------------------------------")


def _draw_slider_panel(open_: bool):
    """The panel's own canvas: the value in the unit the owner reasons about."""
    if not open_ or cv2.getWindowProperty(SLIDER_WIN, cv2.WND_PROP_VISIBLE) < 1:
        return
    canvas = np.zeros((380, 520, 3), dtype=np.uint8)
    cv2.putText(canvas, f"smoothing tau = {SLERP_TAU_MS:.0f} ms", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 255, 255), 2, cv2.LINE_AA)
    note = ("no smoothing -- the cube goes exactly where Horn says"
            if SLERP_TAU_MS <= 0 else
            "TODAY's behaviour (== the shipped per-frame 0.35)"
            if SLERP_TAU_MS >= 149 else
            "below one frame (64 ms): the lag is gone, this trades jitter only")
    cv2.putText(canvas, note, (10, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (170, 170, 170), 1, cv2.LINE_AA)
    cv2.putText(canvas, "0 = none    20 = owner's setting    149 = today",
                (10, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1, cv2.LINE_AA)

    # ⭐ F1's block. Every line prints the APPLIED value, and the fingertip filter
    # prints its cutoff too -- the slider speaks ms because that is the unit the
    # owner reasons in, but the algorithm's own parameter is the Hz, and a take
    # should be readable off a screenshot in both.
    cv2.line(canvas, (10, 90), (510, 90), (60, 60, 60), 1)
    if JITTER_TAU_MS <= 0:
        jl = "fingertip filter OFF  (bit-exact: the raw barycentre)"
        jc = (120, 120, 255)
    else:
        jl = (f"fingertip jitter: tau {JITTER_TAU_MS:.0f} ms "
              f"(fc {_tau_ms_to_cutoff_hz(JITTER_TAU_MS):.2f} Hz)  "
              f"beta {JITTER_BETA:.3f}")
        jc = (120, 255, 200)
    cv2.putText(canvas, jl, (10, 116), cv2.FONT_HERSHEY_SIMPLEX, 0.52, jc, 1,
                cv2.LINE_AA)
    cv2.putText(canvas, "lower tau = twitchier but no lag;  higher = calmer at rest",
                (10, 138), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)

    if tip_trim.TRIM_GAIN <= 0:
        tl = "fingertip TRIM OFF  (rotation is shipped Horn, exactly)"
        tc = (120, 120, 255)
    else:
        tl = (f"fingertip trim: gain {tip_trim.TRIM_GAIN:.2f}  "
              f"max {tip_trim.TRIM_MAX_DEG:.0f} deg")
        tc = (120, 255, 200)
    cv2.putText(canvas, tl, (10, 172), cv2.FONT_HERSHEY_SIMPLEX, 0.52, tc, 1,
                cv2.LINE_AA)
    cv2.putText(canvas, "census: real finger motion is ~16 deg median over 0.5 s,",
                (10, 194), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)
    cv2.putText(canvas, "so a max far above ~15 stops being a TRIM and starts",
                (10, 214), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)
    cv2.putText(canvas, "following the fingers -- which is the A10-dead arm.",
                (10, 234), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)

    # ⭐ THE GRAB RADIUS, printed in BOTH units: the fraction the slider sets, and
    # the pixels it comes to on a face-on large cube at the resting depth -- which
    # is the number the operator is actually aiming inside of.
    cv2.line(canvas, (10, 252), (510, 252), (60, 60, 60), 1)
    _face_on = object_extent.grab_extent(
        palm_geometry.projected_size_px(CUBE_SIZE_LARGE,
                                        palm_geometry.REFERENCE_DEPTH_M),
        (1.0, 0.0, 0.0, 0.0), _CUBE_MESH_VERTS, CUBE_PERSPECTIVE_DISTANCE_RATIO)
    if GRAB_RADIUS_MULTIPLIER <= 0:
        gl = "GRAB radius 0%  --  NOTHING can be picked up"
        gc = (120, 120, 255)
    else:
        gl = (f"grab radius: {GRAB_RADIUS_MULTIPLIER:.2f} x footprint "
              f"= {GRAB_RADIUS_MULTIPLIER * _face_on:.0f} px face-on")
        gc = (120, 255, 200)
    cv2.putText(canvas, gl, (10, 278), cv2.FONT_HERSHEY_SIMPLEX, 0.52, gc, 1,
                cv2.LINE_AA)
    cv2.putText(canvas, "of 50 real grabs: 50% -> 42% still occur, 75% -> 72%,",
                (10, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)
    cv2.putText(canvas, "100% -> 80%.  Smaller radius = smaller slide at grab.",
                (10, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)
    _zl = (f"grab z margin: {GRAB_Z_TOLERANCE_M * 100:.0f} cm"
           f"    walk: {GRIP_ALIGN_MASK_RATIO:.2f} x hand step")
    cv2.putText(canvas, _zl, (10, 348), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                (120, 255, 200) if GRAB_Z_TOLERANCE_M > 0 else (120, 120, 255),
                1, cv2.LINE_AA)
    cv2.putText(canvas, "depth is ESTIMATED, not measured: T6 put the four palm",
                (10, 368), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1,
                cv2.LINE_AA)
    try:
        cv2.imshow(SLIDER_WIN, canvas)
    except cv2.error:
        pass


# ⚠ A HITCH MUST NOT BECOME A POP. dt is clamped before it reaches the exponential:
# after a dropout, a coast or a stalled frame, `now_ms` can jump by hundreds of ms,
# and an unclamped dt drives the factor to 1.0 -- i.e. the cube teleports onto the
# hand on the first frame back. That is precisely what D3's resync blend exists to
# prevent, and letting the smoothing undo it would re-open a defect the owner has
# already accepted a fix for. Three frame-times of catch-up is plenty.
_SLERP_MAX_DT_MS = _HS_const.ROTATION_SLERP_MAX_DT_MS


def _slerp_factor_for(state: CubeState, now_ms) -> float:
    """This frame's blend factor for `state` -- fixed per-frame, or time-based.

    ⭐ `mode == "frame"` returns the module constant untouched, so every existing
    caller, harness and the whole production mirror keep today's behaviour exactly.
    """
    if getattr(state, "slerp_mode", "frame") != "time" or now_ms is None:
        return ROTATION_SLERP_FACTOR
    prev = state.last_frame_ms
    tau = max(1.0, state.slerp_tau_ms)
    if prev is None:
        return ROTATION_SLERP_FACTOR      # no dt yet: today's value, never a guess
    dt = min(max(0.0, now_ms - prev), _SLERP_MAX_DT_MS)
    return 1.0 - math.exp(-dt / tau)


def _draw_ab_divergence(frame, before: CubeState, after: CubeState, height):
    """How far apart the two estimators' cubes are, in degrees, live.

    ⭐ THE NUMBER MATTERS BECAUSE THE EYE'S THRESHOLD IS HIGH. The recorded A/B
    take puts the median panel-to-panel difference at 4.83 deg -- real, systematic,
    and below what anyone can see on a small cube. Printing it means "no visible
    difference" and "no difference" stop being the same observation, which is the
    distinction this project has had to re-learn from the other direction four
    times (a harness reporting CLEAN on a take the owner had just watched fail).
    """
    parts = []
    for name, a in after.cubes.items():
        b = before.cubes.get(name)
        if b is None or (a.owner is None and b.owner is None):
            continue
        d = abs(sum(x * y for x, y in zip(a.orientation, b.orientation)))
        parts.append("%s %.1f deg" % (name[:1],
                     2.0 * math.degrees(math.acos(max(-1.0, min(1.0, d))))))
    if parts:
        cv2.putText(frame, "cage(BEFORE) vs solid(AFTER):  " + "   ".join(parts),
                    (10, height - 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 220, 255), 1, cv2.LINE_AA)


def update_hands(state: CubeState, hand_data_by_hand, snap_blocked=frozenset(),
                 anchor=None, rotation=None, now_ms=None, pose_out=None) -> None:
    """hand_data_by_hand: {handedness: {"pixel_landmarks": [...],
    "world_landmarks": [...], "thumb_outward": bool} or None (not detected
    this frame)}.

    `snap_blocked`: handednesses that may take NO NEW SNAP this frame. Empty by
    default, so nothing here changes for existing callers. It exists for **S3,
    binding** (GESTURE_PIPELINE_SPEC.md §16.2 rule 5): when a predictive gate is
    withholding judgement on a hand, the grab/release state machine must HOLD
    rather than decide on inferred data. Only the *decision* freezes -- a cube
    already held keeps being translated and rotated, and a release on tracking
    loss is unaffected, because tracking loss is measured and never predicted.
    `LiveBlockPredictionDebug.py` is the caller that uses it.

    `anchor`: an optional `Resources/palm_anchor.PalmAnchor` (queue item B4).
    None -- the default -- keeps §14.1's incumbent 9-landmark distance-weighted
    anchor exactly as it was, so nothing changes for existing callers. When
    supplied, the held object rides the PALM BLOCK instead: a metric offset
    frozen in the palm's own 3D frame, rotated by the palm frame each frame and
    projected. ⚠ The two paths are kept strictly separate and never mixed -- a
    degenerate palm REFUSES the grab rather than silently falling back to the
    other anchor, because a fallback would contaminate the A/B this exists for
    (§16.5's methodological lesson).

    Two passes, not one combined per-hand pass — bug found live
    (2026-08-01): releasing and re-snapping in the same per-hand pass let a
    cube instantly jump to the other hand the instant one hand lost
    tracking, if the other hand was already within grab radius. Fix:
    release everyone who needs releasing first, across both hands, then
    snap/translate/rotate, excluding cubes released this same frame from
    this frame's snap pass — kept in sync with the same fix in
    Resources/HandsTriggeredActions.py.

    Closed-fist release/snap-blocking (§13.3/§13.4) is NOT implemented
    here — reverted along with the Gesture Recognizer integration, see the
    module header note above. Only tracking-loss release is active for now.

    Thumb-outward snap rule (§13.6, direct request, 2026-08-01): don't snap
    while the hand is thumb-outward (back of hand facing camera) UNLESS the
    hand was already thumb-outward at the moment its currently-held cube
    was last released, AND it hasn't shown thumb-inward since.

    ⛔⛔ THAT RULE WAS REMOVED ON 2026-08-25 (owner, queue F1): an object may be
    grabbed at any palm facing, including on re-entry into the frame window. The
    armed/disarmed exception state (`thumb_outward_snap_allowed`) was deleted with
    it. `last_known_thumb_outward` survives as an OBSERVATION only — it is on the
    HUD and published as `palm_facing`, and it gates nothing.

    Rotation (2026-08-01, confirmed UNGATED — see the ROTATION_SLERP_FACTOR
    comment above) is RELATIVE, not absolute — direct request 2026-08-01,
    superseding an earlier absolute-follow attempt: a cube must keep its
    OWN orientation at the instant of grab (no pop/snap to match whatever
    twist the hand happens to be at), and should only rotate by however
    much the hand's orientation CHANGES after that. Mechanism: on grab,
    record the hand's orientation quaternion (`grab_hand_orientation`) and
    the cube's own current orientation (`grab_cube_orientation`) as a
    baseline pair on the Cube itself. Every frame while held, compute the
    world-frame delta the hand has rotated since grab (`hand_now *
    inverse(grab_hand_orientation)`) and apply that same delta on top of
    `grab_cube_orientation` to get this frame's target — on the grab frame
    itself the delta is identity by construction, so the target equals the
    cube's current orientation exactly (no pop); slerp still eases toward
    it each frame afterward for jitter smoothing, not to bridge a gap.

    ⛔ THE PREDICTIVE, RELIABILITY-WEIGHTED FILTER THAT USED TO SIT HERE WAS
    REMOVED ON 2026-08-24 (owner). It ran between the raw reading and the
    grab-delta math, blending a constant-angular-velocity extrapolation with the
    raw frame. ⭐ It had become dead code: Horn's fit replaced its output whenever
    it succeeded, measured on **9091 of 9091 hand-frames**. Archived with its full
    rationale in `Resources/_archived_predictive_orientation_filter.py`.
    ⭐⭐ CONSEQUENCE WORTH KNOWING: the slerp onto the cube is now the ONLY smoothing
    in the rotation path, so its time constant IS the felt lag. It superseded two
    earlier binary-filter attempts (see the module-level comment above
    CONDITIONING_ALPHA_LOW for the full history of why) and is verified
    against recorded data to eliminate the large (>30/>60 degree)
    per-frame jumps at the pitch crossing without changing already-healthy
    frames at all (alpha=1 there, zero added lag)."""
    # D1, mirroring production's identical pass: resolve tracking state for both
    # hands before either pass acts on it. `now_ms` is injected so `hand_state`
    # stays clock-free (`analysis/verify_hand_state.py`).
    if now_ms is None:
        now_ms = time.perf_counter() * 1000.0

    # ⚠⚠ BIND BEFORE THE TRACKERS ARE UPDATED, NEVER AFTER. Binding afterwards
    # swaps in the track's own tracker only AFTER this frame's detection has been
    # applied to the previous one, leaving a STALE `TRACKING` state on a slot
    # whose `data` is None -- which crashed the tool live at
    # `thumb_outward = data["thumb_outward"]`. Production binds first; this is
    # the same order.
    _bound = _bind_track_state(state, now_ms)

    for handedness in TRACKED_HANDS:
        data = hand_data_by_hand[handedness]
        t = state.hand_state_trackers[handedness]
        t.update(data is not None, now_ms)
        if t.tracking_state == hand_state.BRIDGING:
            state.stats["bridged_frames"] += 1
        if t.reacquired_after_ms > 0.0 and state.cube_owned_by(_owner_key(handedness, state)) is not None:
            state.stats["saves"] += 1

    released_this_frame = set()

    # ⛔⛔ THE HOLE THE GOVERNING-HAND FIX DOES NOT CLOSE, and the owner hit it
    # live: the governing map tracks a SLOT, and a slot can be refilled by a
    # DIFFERENT hand. Cube owned by track 3 in the Left slot; track 3 ends during
    # a crossing; another hand takes Left; `hand_state_trackers['Left']` sees a
    # DETECTED hand, so `holds_track` is True and release never fires. The cube
    # stays owned by a dead id: grabbed-looking, driven by nothing, un-regrabbable.
    # ⚠ A LONGER COAST MAKES THIS WORSE, NOT BETTER -- which is why the owner saw
    # it at 300 and 450 ms.
    # Same constant and semantics as production's `OWNER_ABSENT_RELEASE_MS`.
    # ⭐⭐ T3 NARROW REMAP -- runs FIRST, before anything reads `cube.owner`.
    #
    # DR-1 swaps two tracks between slots constantly. Ownership is a slot NAME, so
    # without this the cube silently changes PHYSICAL HAND at that instant: no
    # release, no snap, and rule 3 never consulted -- which is exactly why every
    # ordinary back-of-hand grab is blocked and the recorded steal was not
    # (`2026-08-22_184440_n8_back_steal_b`, f478: t7 and t8 swap, owner stays
    # "Right", the cube passes to the BACK hand).
    #
    # ⚠ This is NOT 4.1's migration: ownership REMAINS a slot name, nothing else
    # moves off the slot, and an ABSENT track is a no-op here (the coast/release
    # path below still owns that case). See `Resources/owner_remap.py`.
    for _n, _c in state.cubes.items():
        if _c.owner is None:
            state.holder_track.pop(_n, None)   # N6: same guard as production
            continue
        _new_owner = owner_remap.remap_owner(
            _c.owner, state.holder_track.get(_n), _hand_track_ids)
        if _new_owner != _c.owner:
            state.stats["owner_remaps"] = state.stats.get("owner_remaps", 0) + 1
            _c.owner = _new_owner

    _live_ids = {t for t in _hand_track_ids.values() if t >= 0}
    for _n, _c in list(state.cubes.items()):
        _o = _c.owner
        if _o is None or not isinstance(_o, int) or _o in _live_ids:
            state.owner_absent_since.pop(_n, None)
            continue
        _first = state.owner_absent_since.setdefault(_n, now_ms)
        if now_ms - _first >= OWNER_ABSENT_RELEASE_MS:
            state.stats["releases"] += 1
            state.release_cube(_n)
            state.owner_absent_since.pop(_n, None)
            state.owner_hand_of_cube.pop(_n, None)
            released_this_frame.add(_n)

    # ⛔ Mirrors production's stranded-cube fix (2026-08-22). Driving release from
    # `cube_owned_by(_owner_key(...))` strands a cube forever once its track
    # ends: the key degrades to the label, the int-keyed cube is never found, and
    # it stays owned-but-dead -- drawn as grabbed, moving with nothing, and
    # un-regrabbable. Drive it from the CUBES instead.
    _id_to_hand = {t: h for h, t in _hand_track_ids.items() if t >= 0}
    for _n, _c in state.cubes.items():
        if _c.owner is None:
            state.owner_hand_of_cube.pop(_n, None)
        elif isinstance(_c.owner, int):
            _h = _id_to_hand.get(_c.owner)
            if _h is not None:
                state.owner_hand_of_cube[_n] = _h
        else:
            state.owner_hand_of_cube[_n] = _c.owner

    for owned, cube in list(state.cubes.items()):
        if cube.owner is None:
            continue
        handedness = state.owner_hand_of_cube.get(owned)
        if handedness is None:
            state.stats["releases"] += 1
            state.release_cube(owned)
            released_this_frame.add(owned)
            continue
        if not state.hand_state_trackers[handedness].holds_track:  # tracking lost
            state.stats["releases"] += 1
            state.release_cube(owned)
            released_this_frame.add(owned)

    for handedness in TRACKED_HANDS:
        data = hand_data_by_hand[handedness]
        if state.hand_state_trackers[handedness].tracking_state != hand_state.TRACKING:
            # ⚠ Resets gated on the track being properly gone, not on one missed
            # frame -- see the long note on production's copy of this branch.
            # Under D2's open window these no longer coincide, and clearing here
            # would discard exactly what the bridge coasts on.
            if state.hand_state_trackers[handedness].tracking_state == hand_state.SUSTAINED_LOST:
                state.hand_rotation_states[handedness] = None                         # §16.15: never fit against a dead track
                # ⛔⛔ MISSING UNTIL 2026-08-22 -- production always did this and
                # this tool never did. Owner, live: "when the palm exits and comes
                # back with back, the back hand still grabs the cube for a short
                # while... this does not happen in production."
                #
                # DR-2 FREEZES the palm/back sign while edge-on. Without this
                # reset the sign frozen BEFORE the hand left survived its death,
                # so a hand returning back-of-hand -- briefly edge-on, nothing
                # measurable -- was judged with the OLD hand's "palm" reading,
                # `thumb_outward` came back False, and GAME_RULES rule 3's gate
                # let it snap. Production cleared it, so production never showed
                # the defect. A one-line divergence, live-visible.
                _palm_facing_trackers[handedness].reset()
                state.resync_blend_left[handedness] = 0                               # D3: a dead track carries no pending blend
            continue
        if data is None:
            # ⚠ Defensive: "TRACKING implies data is not None" held only while the
            # tracker was pinned to the slot. Now that it follows the TRACK, keep
            # this explicit rather than relying on the two staying in step.
            continue
        if state.hand_state_trackers[handedness].reacquired_after_ms > 0.0:
            # D2/D3, mirroring production exactly: never extrapolate across a gap
            # the filter did not observe (B8), and arm the resync blend -- only
            # for a hand that is actually holding, or it would stay armed until
            # the next grab and blend one that never bridged.
            if _cube_for_hand(state, handedness, now_ms) is not None:
                state.resync_blend_left[handedness] = state.resync_blend_frames
        thumb_outward = data["thumb_outward"]
        state.last_known_thumb_outward[handedness] = thumb_outward

        # ⭐⭐ F1 STEP 2 -- two positions, mirroring production exactly (see its
        # comment). `palm_pos` stays the palm and is what `handinput` publishes as
        # `palm_pose`; `hand_pos` is the filtered fingertip GRIP point and drives
        # snap proximity and translation.
        palm_pos = _hand_position(data["pixel_landmarks"])
        # ⭐ The grip point is computed ONCE per frame from the SHARED tracker, and
        # each arm then chooses whether to use it -- so the filter history is
        # identical across panels and the only difference is the choice itself.
        _use_tips = (fingertips.USE_TIP_BARYCENTER if state.use_tips is None
                     else state.use_tips)
        # ⛔⛔ THE FLAG MUST GO *INTO* `grip_position_px`, NOT BE APPLIED AFTER IT.
        # Until 2026-08-26 it was applied after: the call read the module global
        # (False) and returned the palm centre, so `_grip` and `palm_pos` were the
        # SAME POINT and the line below chose between two identical values. The
        # rig's panels 1 and 2 were bit-identical in position for the whole of the
        # owner's first live take -- 0.00 px over 6025 owned-cube samples.
        _grip = fingertips.grip_position_px(
            _grip_trackers[handedness], data["pixel_landmarks"], now_ms,
            use_tips=_use_tips)
        hand_pos = _grip if _use_tips else palm_pos
        _prev_grip_px = state.last_grip_px.get(handedness)
        state.last_grip_px[handedness] = hand_pos
        raw_quat, conditioning_norm = _hand_orientation_quaternion(data["world_landmarks"])
        state.last_hand_reliability_alpha[handedness] = _reliability_alpha(conditioning_norm)
        # ⭐ RAW straight through -- Horn replaces it below on every frame it
        # succeeds (measured 9091/9091), so this is the fallback path only, and raw
        # is the honest fallback (B8: every velocity fit lost to holding the last
        # value). N6: production does exactly this, in the same place.
        hand_quat_now = raw_quat
        if rotation is not None:
            # §16.15: the orientation DELTA comes from a least-squares fit over
            # the palm constellation. Its own frozen reference is per hand, so a
            # cube grabbed later still measures from the same track.
            rs = state.hand_rotation_states[handedness]
            if rs is None:
                rs = rotation.freeze(data["pixel_landmarks"], data["world_landmarks"])
                state.hand_rotation_states[handedness] = rs
            if rs is not None:
                _d = rotation.delta(rs, data["pixel_landmarks"], data["world_landmarks"])
                if _d is not None:
                    hand_quat_now = _d

        # ⭐ 4.2: this frame's absolute hand depth, stamped upstream by
        # `_update_snap_depth` so one estimator serves every arm. ABSENT means a
        # caller that predates 4.2 -> pre-4.2 2D gating, deliberately.
        _hdepth = data.get("hand_depth")
        _hand_depth_m = _hdepth[0] if _hdepth else None
        _hand_depth_valid = bool(_hdepth[1]) if _hdepth else None

        # ⭐ handinput: capture the pose this arm produced, before it reaches a
        # cube. ⚠ `pose_out` is None for every arm but the first -- see
        # `update_hands_all`, which explains why an A/B must not publish twice.
        if pose_out is not None:
            pose_out[handedness] = {"position_px": palm_pos,
                                    "orientation": hand_quat_now}

        owned = _cube_for_hand(state, handedness, now_ms)
        if owned is None:
            # ⛔⛔ RULE 3's BACK-OF-HAND SNAP BLOCK REMOVED 2026-08-25 (owner,
            # queue F1) -- an object may be claimed at any palm facing, including
            # on re-entry. Kept in step with production; `parity_replay` proves it.
            can_snap = handedness not in snap_blocked   # S3, see docstring
            # ⭐⭐ 4.2 DECISION 1 (owner, 2026-08-23), mirroring production: NO
            # SNAPPING WHILE DEPTH IS FROZEN. A frozen depth is a held value, not
            # a measurement, and the gate below is 3D now. `None` = no depth
            # supplied by this caller at all, which is the pre-4.2 path and must
            # NOT refuse.
            if _hand_depth_valid is not None and _PDepth.SNAP_REQUIRES_VALID_DEPTH:
                can_snap = can_snap and _hand_depth_valid
            # ⭐⭐ U8, mirroring production exactly (N6): rule 3 may not act on a
            # PROVISIONAL chirality. A newly entered hand's thumb has not cleared
            # the frame edge, so its palm/back answer can be confidently wrong --
            # measured at f664 of `2026-08-22_190955_t3_remap_production_test`.
            # See `HandsTriggeredActions` for the three cheaper remedies that were
            # measured and rejected.
            can_snap = can_snap and _palm_facing_trackers[handedness].chirality_confirmed
            # ⚠ A FREE HAND CARRIES NO DEPTH BASELINE (N6: production drops it in
            # exactly the same place, and for the same reason -- releases happen
            # at several sites and a forgotten one would leave the next grab
            # baselined against a span measured before the object was picked up).
            state.depth_ratio_trackers[handedness].reset()
            state.tip_trims[handedness].reset()
            if can_snap:
                owned = _try_snap(state, handedness, hand_pos,
                                  hand_depth_m=_hand_depth_m,
                                  exclude=released_this_frame)
                if owned is not None:
                    cube = state.cubes[owned]
                    # 4.2: freeze the Z baseline pair with the others, so the
                    # grab frame is continuous in Z too (ratio 1.0 at grab).
                    # ⭐ A1-in-Z: anchor to the HAND's measured depth so the grab
                    # cannot ratchet the object into the near wall (see
                    # `fingertips.GRIP_ALIGN_DEPTH_AT_GRAB` for the measurement).
                    # ⛔ NO JUMP. The first version set `cube.depth_m` to the
                    # hand's depth right here, and the object visibly stepped in Z
                    # at the instant of the grab (owner, 2026-08-26). The anchor is
                    # now WALKED there, on the same progress as the in-plane offset.
                    cube.grab_depth_m = cube.depth_m
                    if (fingertips.GRIP_ALIGN_DEPTH_AT_GRAB and _use_tips
                            and _hand_depth_m is not None):
                        cube.grab_hand_depth_m = _hand_depth_m
                        cube.grab_depth_offset_m = cube.depth_m - _hand_depth_m
                    else:
                        cube.grab_hand_depth_m = None
                        cube.grab_depth_offset_m = None
                    state.depth_ratio_trackers[handedness].freeze(data["pixel_landmarks"])
                    cube.grab_hand_orientation = hand_quat_now
                    cube.grab_cube_orientation = cube.orientation
                    # ⭐ F1 step 4, mirroring production: the trim's reference is
                    # the GRAB, so R_trim(grab) = I and there is no pop.
                    if hand_quat_now is not None:
                        state.tip_trims[handedness].freeze(
                            data["world_landmarks"], hand_quat_now)
                    # Object position at the instant of grab -- captured
                    # from the cube's own pre-existing center, BEFORE this
                    # frame's translation update below touches it, so this
                    # is genuinely "wherever the cube visually was," not
                    # the hand anchor (§14.1's whole point: today's
                    # zero-offset design discarded this; the redesign
                    # preserves it, same no-pop principle as the
                    # orientation baseline just above).
                    object_pos_at_grab = state.cube_center(owned)
                    if anchor is not None:
                        # B4: freeze a metric offset in the palm's own frame.
                        # No residual-offset term is needed -- that existed only
                        # because inverse-distance weighting does not
                        # interpolate through the query point; this is exact.
                        cube.grab_anchor_state = anchor.freeze(
                            object_pos_at_grab, data["pixel_landmarks"],
                            data["world_landmarks"])
                        if cube.grab_anchor_state is None:
                            # Degenerate palm this frame -- refuse the grab
                            # rather than fall back to a different anchor, which
                            # would silently contaminate an A/B.
                            state.release_cube(owned)
                            owned = None
                    else:
                        cube.grab_landmark_weights = _compute_grab_weights(object_pos_at_grab, data["pixel_landmarks"])
                        weighted_at_grab = _weighted_position(cube.grab_landmark_weights, data["pixel_landmarks"])
                        cube.grab_residual_offset = (
                            object_pos_at_grab[0] - weighted_at_grab[0],
                            object_pos_at_grab[1] - weighted_at_grab[1],
                        )
                        # ⭐ F1 step 2, mirroring production: the same no-pop
                        # construction against the grip point.
                        # ⭐⭐ A1: zero offset means the cube's centre IS the
                        # fingertip barycentre, in x and y, for the whole hold.
                        # ⭐ A1 keeps this offset -- the grab stays continuous --
                        # and fades it to zero during the hold, so the cube ends
                        # up ON the barycentre without popping onto it.
                        cube.grab_grip_offset = (
                            object_pos_at_grab[0] - hand_pos[0],
                            object_pos_at_grab[1] - hand_pos[1],
                        )
                        cube.grab_grip_fade_ms = GRIP_ALIGN_MOVING_MS
        if owned is not None:
            cube = state.cubes[owned]
            # ⭐⭐ 4.2 -- Z FIRST, before the X/Y target is applied: the clamp and
            # the top-left both depend on the projected extent, which depends on
            # depth. ⚠ `valid` False means the ratio is HELD, not measured, so
            # depth holds too -- B8 measured every velocity fit losing to "hold
            # the last value", so there is nothing to extrapolate with.
            if cube.grab_depth_m is not None:
                _ratio, _ratio_valid = state.depth_ratio_trackers[handedness].update(
                    data["pixel_landmarks"])
                if _ratio_valid and _ratio > 1e-6:
                    # ⭐ The anchor walks from the object's own depth at grab
                    # towards the hand's. At grab the offset is the whole gap, so
                    # this is exactly today's value and nothing moves; as the walk
                    # retires it the anchor becomes the hand's depth.
                    _anchor = cube.grab_depth_m
                    if (cube.grab_hand_depth_m is not None
                            and cube.grab_depth_offset_m is not None):
                        _anchor = cube.grab_hand_depth_m + cube.grab_depth_offset_m
                    cube.depth_m = palm_geometry.clamp_depth(_anchor / _ratio)
            if anchor is not None:
                new_center = anchor.apply(cube.grab_anchor_state,
                                          data["pixel_landmarks"],
                                          data["world_landmarks"])
            else:
                # ⭐⭐ F1 STEP 2 -- the object follows the fingertip barycentre.
                # Identical to production; `parity_replay` is what keeps it so.
                # ⛔ SECOND HALF OF THE SAME DEFECT: this tested the module
                # global too, so even a correct grip point would have been
                # ignored here. It follows the ARM's flag now; `state.use_tips`
                # is None for every non-rig caller, which resolves to the global
                # and leaves production and the single-arm view untouched.
                if _use_tips and cube.grab_grip_offset is not None:
                    # ⭐⭐ A1's fade. `state.last_frame_ms` is still the PREVIOUS
                    # frame here -- it is advanced after the slerp, further down --
                    # so this is the same dt the rotation channel uses.
                    _dt = (None if (now_ms is None or state.last_frame_ms is None)
                           else now_ms - state.last_frame_ms)
                    # ⭐⭐ The fade is spent in HAND MOVEMENT, not wall time, so a
                    # cube never slides on its own while the hand is still.
                    _prev_px = _prev_grip_px
                    _hand_step = (None if _prev_px is None else
                                  math.hypot(hand_pos[0] - _prev_px[0],
                                             hand_pos[1] - _prev_px[1]))
                    (cube.grab_grip_offset, cube.grab_depth_offset_m,
                     cube.grab_grip_fade_ms) = fingertips.decay_grip_offset(
                        cube.grab_grip_offset, cube.grab_depth_offset_m,
                        cube.grab_grip_fade_ms, _dt, _hand_step)
                    new_center = (
                        hand_pos[0] + cube.grab_grip_offset[0],
                        hand_pos[1] + cube.grab_grip_offset[1],
                    )
                else:
                    weighted_now = _weighted_position(
                        cube.grab_landmark_weights, data["pixel_landmarks"])
                    new_center = (
                        weighted_now[0] + cube.grab_residual_offset[0],
                        weighted_now[1] + cube.grab_residual_offset[1],
                    )
            if new_center is not None and state.resync_blend_left[handedness] > 0:
                # D3, mirroring production: walk back to the hand over a few
                # frames instead of teleporting on the first frame after a bridge.
                t = 1.0 / state.resync_blend_left[handedness]
                have = state.cube_center(owned)
                new_center = (have[0] + (new_center[0] - have[0]) * t,
                              have[1] + (new_center[1] - have[1]) * t)
                state.resync_blend_left[handedness] -= 1
            if new_center is not None:      # None = degenerate palm: HOLD, never jump
                # 4.2: the CENTRE is what the play volume clamps; `position` is
                # derived from it with the projected extent, so an object moving
                # in Z grows about its own centre, not its corner.
                state.set_target_center(owned, new_center)
            # ⭐⭐ F1 STEP 4 -- the fingertip trim, per arm. Identical maths to
            # production; `parity_replay` is what keeps them identical.
            _gain = tip_trim.TRIM_GAIN if state.trim_gain is None else state.trim_gain
            _trim_q = state.tip_trims[handedness].update(
                data["world_landmarks"], hand_quat_now,
                tip_trim.palm_span_m(data["world_landmarks"]), now_ms, gain=_gain)
            _q_eff = (hand_quat_now if _trim_q is tip_trim.IDENTITY
                      else _quat_multiply(hand_quat_now, _trim_q))
            delta = _quat_multiply(_q_eff, _quat_conjugate(cube.grab_hand_orientation))
            target_quat = _quat_multiply(delta, cube.grab_cube_orientation)
            # Slerp was temporarily disabled 2026-08-01 to isolate and
            # diagnose the back-toward-camera noise from any smoothing
            # artifact (confirmed: the chaos was a faithful reflection of
            # the raw signal, not a slerp artifact). Root-caused and fixed
            # since (see _orthonormal_frame's docstring + GEOMETRIC_
            # DEGENERACY_NORM above: better-conditioned vector pair +
            # geometric confidence gate) -- data-confirmed improvement
            # (back-pose >30deg-jump frames dropped ~4-5x, >60deg ~2-3x
            # across matched recordings), re-enabled.
            cube.orientation = _quat_slerp(cube.orientation, target_quat,
                                           _slerp_factor_for(state, now_ms))

    # ⚠ AFTER the slerp, never before it: `_slerp_factor_for` needs the PREVIOUS
    # frame's clock to form dt, and stamping it earlier would make dt zero and the
    # blend factor zero -- i.e. a cube that never moves at all.
    state.last_frame_ms = now_ms
    # ⚠ WRITE BACK LAST, after every mutation this frame. Without it the whole
    # rebinding is a no-op that silently resets each hand every frame.
    _writeback_track_state(state, _bound, now_ms)


def _draw_hand(frame, normalized_landmarks, handedness, thumb_outward, reliability_alpha, width, height):
    hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
    for lm in normalized_landmarks:
        hand_landmarks_proto.landmark.append(landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z))
    solutions.drawing_utils.draw_landmarks(
        frame, hand_landmarks_proto, solutions.hands.HAND_CONNECTIONS,
        solutions.drawing_styles.get_default_hand_landmarks_style(),
        solutions.drawing_styles.get_default_hand_connections_style(),
    )
    xs = [lm.x for lm in normalized_landmarks]
    ys = [lm.y for lm in normalized_landmarks]
    text_x, text_y = int(min(xs) * width), int(min(ys) * height) - 10
    # ⚠ OBSERVATION ONLY since 2026-08-25 -- palm facing no longer gates the snap
    # (queue F1), so this must not read as "BLOCKED"/"allowed" any more. It is kept
    # on the HUD because it is still the operator's window onto chirality.
    if thumb_outward:
        label, color = "thumb-outward", (0, 200, 200)
    else:
        label, color = "thumb-inward", (0, 200, 200)
    # Display the ANATOMICAL hand (owner report 2026-08-22). DISPLAY ONLY --
    # `handedness` keeps its pipeline convention everywhere else in this file.
    _shown = hand_identity.anatomical_name(handedness)
    cv2.putText(frame, f"{_shown}: {label}", (text_x, max(text_y, 20)),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 2, cv2.LINE_AA)
    # Predictive-filter reliability diagnostic (see "Attempt 3" above
    # CONDITIONING_ALPHA_LOW) -- a per-hand signal, drawn here rather than
    # on the cube since it's about the hand's own reading, independent of
    # whether it currently holds anything. alpha=1.0 (not drawn) means the
    # filter is fully trusting the raw reading; lower values mean it's
    # increasingly coasting on the predicted/extrapolated orientation.
    if reliability_alpha < 0.999:
        color = (0, 140, 255) if reliability_alpha > 0.0 else (0, 0, 255)
        cv2.putText(frame, f"{_shown}: reliability {reliability_alpha:.2f}", (text_x, max(text_y, 20) + 24),
                    cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 2, cv2.LINE_AA)


def _draw_cube_3d(overlay, cube: Cube, screen_center: Tuple[float, float]):
    """Real rotating 3D object (2026-08-01, replaces the old flat-rect +
    axis-gizmo placeholder) -- ported from production CubeWindow.py's
    `_draw_object_3d`, same fixed-camera-distance perspective projection
    (see CubeWindow.py's CUBE_PERSPECTIVE_DISTANCE_RATIO comment for the
    live-found morphing bug this specifically avoids), same backface-cull +
    painter's-algorithm depth sort, just drawn with cv2 primitives onto the
    (not-yet-blended) `overlay` canvas instead of pygame ones -- the
    alpha-blend with the real video frame happens once for both cubes
    together in the caller, same as the old flat-rect version did.

    Entirely generic over `cube.mesh` (see Mesh/MeshFace's docstrings) --
    no cube-specific geometry here, mirroring production's identical
    design (mesh-generic rendering, direct request 2026-08-01: the cube is
    a placeholder for future imported 3D objects)."""
    # ⭐ 4.2 (N6, mirrors production's `_draw_object_3d`): the object's REAL size
    # is fixed; its PROJECTION is what depth changes. The virtual camera distance
    # tracks the projected extent so the object's own foreshortening is unchanged
    # by where it sits in Z -- otherwise pushing it away would also flatten it.
    size = palm_geometry.projected_size_px(cube.size, cube.depth_m)
    half = size / 2.0
    camera_distance = size * CUBE_PERSPECTIVE_DISTANCE_RATIO
    cx, cy = screen_center

    projected = []
    for v in cube.mesh.vertices:
        local = (v[0] * half, v[1] * half, v[2] * half)
        rx, ry, rz = _quat_rotate_vector(cube.orientation, local)
        scale = camera_distance / (camera_distance + rz)
        projected.append(((cx + rx * scale, cy + ry * scale), rz))

    visible_faces = []
    for face in cube.mesh.faces:
        rn = _quat_rotate_vector(cube.orientation, face.normal)
        if rn[2] >= 0:
            continue  # facing away from the viewer -- culled
        avg_z = sum(projected[i][1] for i in face.vertex_indices) / len(face.vertex_indices)
        pts = [projected[i][0] for i in face.vertex_indices]
        visible_faces.append((avg_z, face.color, pts))
    visible_faces.sort(key=lambda f: f[0], reverse=True)  # farthest first, nearest last/on top

    for _avg_z, color, pts in visible_faces:
        int_pts = np.array([[int(x), int(y)] for x, y in pts], dtype=np.int32)
        cv2.fillConvexPoly(overlay, int_pts, color)
        cv2.polylines(overlay, [int_pts], True, CUBE_EDGE_COLOR, 1, cv2.LINE_AA)


def _draw_cubes(frame, state: CubeState):
    """Draws both 3D cubes onto a copy of the frame, alpha-blends once (per
    direction: 'the overlay has to have some transparency'), then draws a
    bright snap-highlight outline on the now-blended frame for whichever
    cube(s) are held -- kept opaque/on top so the highlight itself stays
    crisp rather than also being alpha-blended."""
    overlay = frame.copy()
    for cube in state.cubes.values():
        # 4.2: the PROJECTED extent, everywhere. `position` is the top-left of
        # what is drawn, so using `size` here would offset the centre at any
        # depth other than the reference one.
        size = state.projected_size_of(cube)
        screen_center = (cube.position[0] + size / 2, cube.position[1] + size / 2)
        _draw_cube_3d(overlay, cube, screen_center)
    cv2.addWeighted(overlay, CUBE_ALPHA, frame, 1 - CUBE_ALPHA, 0, frame)
    # ⚠ RESTORED 2026-08-25: this loop was removed as COLLATERAL by `febd3fa`,
    # the commit that stripped T6d's A/B rig out of this tool. It sat directly
    # under the ghost-wireframe block that commit was meant to delete, and went
    # with it -- leaving the docstring above describing code that no longer
    # existed and SNAP_BORDER_* defined but never read. Found by the owner in a
    # live look, not by any harness: production's CubeWindow.py kept its
    # equivalent (edge_color/edge_width), so the two tools had silently diverged
    # on what a HELD object looks like. U6's parity guard does not cover drawing.
    for cube in state.cubes.values():
        if cube.owner is not None:
            size = int(round(state.projected_size_of(cube)))
            x, y = int(cube.position[0]), int(cube.position[1])
            cv2.rectangle(frame, (x, y), (x + size, y + size), SNAP_BORDER_COLOR, SNAP_BORDER_WIDTH)


def build_detector():
    base_options = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options, num_hands=2, running_mode=vision.RunningMode.VIDEO,
    )
    return vision.HandLandmarker.create_from_options(options)


def main():
    # ⚠ `--smooth-ms` ASSIGNS this below, which without the declaration makes it a
    # LOCAL for the whole function -- every later read then raises UnboundLocalError
    # before a single frame is captured. Cost three launches to find, because it is
    # invisible to import, to py_compile and to a static name check.
    global SLERP_TAU_MS
    parser = argparse.ArgumentParser(description="Combined snap/translate debug view (video + landmarks + cube overlay).")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--bridge", choices=BRIDGE_MODES, default="blend",
                        help="which D2/D3 arm to run. Default 'blend' = what "
                             "production runs. Ignored when --arms 3.")
    parser.add_argument("--arms", type=int, default=1, choices=(1, 3),
                        help="1 (default) = mirror production, one window. "
                             "3 = the D2/D3 bridging comparison rig, all three "
                             "arms side by side off one camera.")
    parser.add_argument("--f1-rig", dest="f1_rig", action="store_true",
                        # ⚠ ASCII ONLY IN HELP TEXT: argparse prints to the
                        # console, and a cp1252 terminal raises UnicodeEncodeError
                        # on a star -- `--help` died outright until this was
                        # stripped. The comments in this file may use symbols; the
                        # HELP STRINGS may not.
                        help="F1's THREE-WINDOW RIG on one camera: panel 1 = "
                             "STEP 0 (shipped palm anchor, the control), panel 2 = "
                             "STEP 2 (fingertip barycentre drives snap and "
                             "translation), panel 3 = STEP 4 (step 2 plus the "
                             "fingertip rotation trim). Panels differ by ONE step "
                             "each, so a difference is attributable.")
    parser.add_argument("--scale", type=float, default=0.62,
                        help="per-panel display scale for --arms 3")
    parser.add_argument("--gap", type=int, default=8, help="pixels between panels")
    # --- opt-in recording (added 2026-08-22, spec 14.3.4) -------------------
    # The owner asked to SEE the cube while a yaw take is recorded. The
    # perception recorder shows no cube; this tool shows the cube but recorded
    # nothing. Rather than build a third tool, recording is bolted on here,
    # OFF by default, so the live view and the capture are the same run.
    # N17's lesson is applied: tCapture is a REAL monotonic clock, never a
    # synthesised cadence, and --note exists so the operator's intent is stored.
    parser.add_argument("--coast-ab", action="store_true",
                        help="U5 rig: three panels at 150/300/450 ms of D2 coast, "
                             "identical in every other respect")
    parser.add_argument("--ownership-ab", action="store_true",
                        help="4.1/T3 rig: two panels, LABEL keying vs TRACK-ID "
                             "keying, identical in every other respect")
    parser.add_argument("--record", action="store_true",
                        help="also write raw_landmarks.jsonl + per-frame cube state")
    parser.add_argument("--note", type=str, default="",
                        help="free-text note stored in meta.json (use with --record)")
    parser.add_argument("--known-hand", choices=("left", "right"), default=None,
                        help="GROUND TRUTH: the physical hand the operator will "
                             "use for the WHOLE take. Stored in meta.json so an "
                             "analysis can check the pipeline's label against it "
                             "instead of inferring. Same idea as the corpus's "
                             "known_left_back / known_right_back sequences.")
    parser.add_argument("--tag", type=str, default="live_cube_yaw",
                        help="session folder suffix (use with --record)")
    parser.add_argument("--duration", type=float, default=None,
                        help="auto-stop after N seconds (use with --record)")
    parser.add_argument("--slerp-ab", action="store_true",
                        help="LAG rig: two panels, SAME Horn estimator, differing "
                             "only in smoothing -- 1 = today's fixed per-frame "
                             "0.35, 2 = the time-based constant on the SMOOTH ms "
                             "slider. One camera and one detection feed both, so a "
                             "difference between the panels has exactly one cause.")
    parser.add_argument("--no-sliders", dest="sliders", action="store_false",
                        help="do not open the smoothing slider panel. The smoothing "
                             "is then locked to whatever --smooth-ms sets.")
    parser.add_argument("--smooth-ms", type=float, default=None,
                        help="start the smoothing at this time constant in ms "
                             "instead of the default 20 (the owner's live-settled "
                             "value). Range 0..150; 149 == today's shipped feel.")
    args = parser.parse_args()

    # ⚠ VALIDATED BEFORE THE CAMERA IS OPENED. A bad value must fail in the first
    # second, not after the operator has held a pose for a minute -- the same
    # preflight rule the record path already follows below.
    if args.smooth_ms is not None:
        # ⚠ Refused rather than clamped: with the slider open, a value it cannot
        # represent is silently overwritten on the first frame, so the run would
        # use a number the operator never chose -- and meta.json would record THAT.
        if not 0 <= args.smooth_ms <= SLERP_TAU_MAX_MS:
            raise SystemExit(
                f"[LiveSnapDebug] --smooth-ms {args.smooth_ms} is outside "
                f"[0, {SLERP_TAU_MAX_MS}].")
        SLERP_TAU_MS = args.smooth_ms

    detector = build_detector()
    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). Is another program using the camera?")

    ret, frame, _ = capture_policy.read_frame(cap)   # retries a cold-start stall
    if not ret:
        raise RuntimeError("Could not read an initial frame from the webcam.")
    height, width = frame.shape[:2]
    arms = (_arm_layout(args.arms, width, height, args.ownership_ab, args.coast_ab,
                        args.slerp_ab, args.f1_rig)
            or [_make_arm(args.bridge, width, height)])
    # ⭐⭐ THE UNIT CHANGE (owner, 2026-08-24: *"change the unit first"*). Every LIVE
    # arm smooths on a time constant in milliseconds instead of a fixed per-frame
    # factor, so the feel no longer moves with the camera's frame rate.
    # ⚠ `CubeState` still DEFAULTS to "frame": the analysis harnesses are
    # regressions against shipped behaviour and must not silently change units
    # underneath themselves. Only the live tool opts in, here, explicitly.
    # ⛔ EXCEPT panel 1 of `--slerp-ab`, which is deliberately left on the old form
    # -- it is the control.
    for _i, _a in enumerate(arms):
        if not (args.slerp_ab and _i == 0):
            _a.slerp_mode = "time"
    arms_first_panel[0] = arms[0]
    _coast_rig[0] = bool(args.coast_ab)
    state = arms[0]        # the single-arm path's state, and arm 1 of a rig

    # One window per arm, laid out left-to-right, same approach as the six-arm
    # tool (`LiveBlockPredictionDebug`). Separate windows rather than one wide
    # canvas so the owner can move, resize or hide a panel mid-session.
    disp_w, disp_h = int(width * args.scale), int(height * args.scale)
    windows = []
    multi = len(arms) > 1
    rig = "D2/D3" if len(arms) == 3 else ""
    for i, arm in enumerate(arms):
        if multi and args.coast_ab:
            name = ("%d. COAST %.0f ms%s" %
                    (i + 1, arm.bridge_window_ms,
                     "  (SHIPPED)" if abs(arm.bridge_window_ms - hand_state.BRIDGE_WINDOW_MS) < 1e-6
                     else "  (candidate)"))
        elif multi and args.slerp_ab:
            name = ("%d. BEFORE -- per-frame 0.35 (today's lag)" % (i + 1) if i == 0
                    else "%d. AFTER -- time-based smoothing (SMOOTH ms slider)" % (i + 1))
        elif multi and args.ownership_ab:
            # Name the panels by the VARIABLE under test, not "arm 1 / arm 2":
            # both arms share a bridge config here, so the arm label alone left
            # the two windows indistinguishable on the taskbar.
            name = ("%d. OWNERSHIP = HANDEDNESS LABEL  (OLD -- cube should DROP)" % (i + 1)
                    if arm.ownership == "label" else
                    "%d. OWNERSHIP = TRACK ID  (NEW -- cube should HOLD)" % (i + 1))
        elif multi:
            name = f"{rig} arm {i + 1}: {arm.arm_label.upper()}"
        else:
            name = "Snap/translate debug (video + landmarks + cube overlay)"
        windows.append(name)
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        if multi:
            cv2.resizeWindow(name, disp_w, disp_h)
            cv2.moveWindow(name, i * (disp_w + args.gap), 0)
    window_name = windows[0]

    # ⭐ A SEPARATE window, so no video panel's layout moves and the owner can drag
    # it onto a second screen while turning their hand.
    if args.sliders:
        _create_sliders()
        cv2.setTrackbarPos(SLIDERS[0][0], SLIDER_WIN, int(round(SLERP_TAU_MS)))
        # ⭐ The applied value, not the table's placeholder.
        cv2.setTrackbarPos("GRAB radius %", SLIDER_WIN,
                           int(round(GRAB_RADIUS_MULTIPLIER * 100)))
        cv2.setTrackbarPos("FADE ms moving", SLIDER_WIN,
                           int(round(GRIP_ALIGN_MOVING_MS)))
        cv2.setTrackbarPos("WALK % of hand", SLIDER_WIN,
                           int(round(GRIP_ALIGN_MASK_RATIO * 100)))
        cv2.setTrackbarPos("GRAB z margin cm", SLIDER_WIN,
                           int(round(GRAB_Z_TOLERANCE_M * 100)))
        if args.f1_rig:
            # ⭐ The rig exists to show the trim, so it starts with the trim ON --
            # while the ordinary single-arm view stays at production's 0.
            cv2.setTrackbarPos("TRIM gain %", SLIDER_WIN, TRIM_GAIN_MAX_PCT)

    timestamp_ms = 0
    print("[LiveSnapDebug] Running -- press 'q' or close a window to stop.")
    print(f"[LiveSnapDebug] smoothing tau starts at {SLERP_TAU_MS:.0f} ms "
          f"(149 = today's behaviour, 0 = none). Slider window: '{SLIDER_WIN}'.")
    if multi:
        for i, arm in enumerate(arms):
            print(f"[LiveSnapDebug]   window {i + 1}: {_arm_title(arm)}")
        print("[LiveSnapDebug] !! Every arm runs off ONE detection and ONE identity")
        print("[LiveSnapDebug]   resolution, so a difference between panels has")
        print("[LiveSnapDebug]   exactly one cause.")
        print("[LiveSnapDebug] !! To test anything you must PROVOKE dropouts:")
        print("[LiveSnapDebug]   grab a cube, then move fast, sweep out past the")
        print("[LiveSnapDebug]   frame edge and back. If 'brid' stays 0, nothing")
        print("[LiveSnapDebug]   was tested.")
    else:
        print(f"[LiveSnapDebug] single arm: {_arm_title(state)}")

    # PREFLIGHT the capture root BEFORE a single frame, never after the
    # operator's effort -- RecordPerceptionSequence.py learned this the hard way
    # on 2026-08-02 when a completed take was discarded at save time.
    session_dir, records, t0 = None, [], time.perf_counter()
    # ⭐⭐ T6d: THE PARAMETER LOG IS THE POINT OF RECORDING THIS SESSION, not a
    # footnote. The sliders move DURING the take, so a single meta.json value would
    # describe only its last few seconds; every change is stamped with the frame and
    # the capture clock so a harness can cut the recording into per-setting
    # segments. ⭐ And this take is the corpus's missing measurement: a yaw sweep
    # only exercises psi~0 and a pitch sweep only psi~90, so `b` and `c` are
    # currently fitted from two endpoints and unconstrained in between. Live hand
    # exploration is what visits the psi no recording does.
    _tau_changes, _tau_last = [], None
    if args.record:
        # ⚠ SANITISED (audit 2026-08-25), mirroring production's recorder exactly:
        # the tag is interpolated into a PATH, so an unchecked one can write the
        # session outside the capture root. `Resources/session_paths.py` holds the
        # one definition -- imported by both recorders, never copied (N6).
        _tag, _tag_changed = session_paths.check_tag(args.tag, "session")
        if _tag_changed:
            print(f"[LiveSnapDebug] --tag was not filename-safe; using '{_tag}'")
        args.tag = _tag
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        session_dir = os.path.join(RECORD_ROOT, "sessions", f"{stamp}_{args.tag}")
        # ⛔ Wake the drive before the preflight, or the preflight refuses a take
        # merely because E: is asleep. Same one copy production uses (N6) --
        # `Resources/capture_drive.py`. ⚠ The operator waking it beforehand is not
        # enough: it sleeps again during whatever ran before.
        capture_drive.ensure_awake(os.path.join(RECORD_ROOT, "sessions"))
        try:
            os.makedirs(session_dir, exist_ok=True)
            probe = os.path.join(session_dir, ".writable")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
        except OSError as e:
            cap.release()
            raise SystemExit(
                f"[LiveSnapDebug] Capture root is not writable, refusing to record.\n"
                f"                path : {session_dir}\n"
                f"                error: {e}\n"
                f"                The drive did not come back after "
                f"{capture_drive.ATTEMPTS} wake attempts -- check the cable or "
                f"enclosure.\n"
                f"                ⛔ Do NOT fall back to a local path; "
                f"recordings belong on E:.")
        print(f"[LiveSnapDebug] RECORDING -> {session_dir}")
        if args.duration:
            print(f"[LiveSnapDebug] auto-stop after {args.duration:.0f}s")

    try:
        while True:
            # ⭐ A transient stall no longer ends the session (audit 2026-08-25),
            # and on a RECORDED take that used to cost the whole session. Shared
            # policy with production -- `capture_policy.py`, N6, same constants.
            ret, frame, _retries = capture_policy.read_frame(cap)
            if not ret:
                print(capture_policy.give_up_message("LiveSnapDebug"))
                break
            if _retries:
                print(f"[LiveSnapDebug] camera recovered after {_retries} failed read(s)")
            t_capture_ms = (time.perf_counter() - t0) * 1000.0   # REAL clock (N17)
            frame = cv2.flip(frame, 1)  # mirror, matching the production pipeline's invert_x

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = detector.detect_for_video(mp_image, timestamp_ms)
            timestamp_ms += 33

            hand_data_by_hand = {h: None for h in TRACKED_HANDS}
            normalized_by_hand = {}
            # Collect into a LIST first, not a dict keyed by handedness: MediaPipe
            # can return BOTH detections with the SAME label (measured: 25 frames
            # across the recorded sessions), and a dict silently overwrites one of
            # them -- the exact defect that hid Object Jump Correction in the old
            # recorder. The shared tracker below assigns the real identities.
            detections = []
            for idx in range(len(result.hand_landmarks)):
                handedness = result.handedness[idx][0].category_name
                if handedness not in TRACKED_HANDS:
                    continue
                normalized = result.hand_landmarks[idx]
                pixel_landmarks = [(lm.x * width, lm.y * height) for lm in normalized]
                # world_landmarks: metric, hand-relative 3D (meters), no
                # pixel remapping needed. No x-mirroring needed either here
                # (unlike the production pipeline's pixel remap_keypoints
                # invert_x): the frame fed to the detector above was already
                # cv2.flip-mirrored before detection, so MediaPipe's own
                # output -- pixel AND world -- is already mirror-consistent
                # with what's displayed. The production port (not yet done)
                # runs detection on the UN-mirrored frame and mirrors pixel
                # coordinates afterward instead, so world_landmarks will
                # need an explicit x-negation there -- verify live when that
                # port happens, don't assume the same code is correct as-is.
                world_landmarks = [(lm.x, lm.y, lm.z) for lm in result.hand_world_landmarks[idx]]
                detections.append({
                    "raw_handedness": handedness,
                    "score": float(result.handedness[idx][0].score),
                    "pixel_landmarks": pixel_landmarks,
                    "world_landmarks": world_landmarks,
                    "normalized": normalized,
                })

            # DR-1: resolve track-level identity by POSITION before anything
            # keys off handedness. Identical code path to production.
            observations = [
                (hand_identity.palm_centroid(d["pixel_landmarks"]),
                 d["raw_handedness"], d["score"],
                 hand_identity.palm_width(d["pixel_landmarks"]))
                for d in detections
            ]
            if detections and all(o[0] is not None for o in observations):
                # N7: same measured-frame-rate timestamp production supplies.
                # Kept in step deliberately -- a debug tool running different
                # dwells from production is the divergence class N6 was created
                # to end.
                labels = _hand_identity_tracker.update(
                    observations, now_ms=time.perf_counter() * 1000.0)
            else:
                labels = [d["raw_handedness"] for d in detections]

            # ⭐ 4.1/T3: publish this frame's stable ids before anything resolves
            # ownership. Mirrors the server sending "hand_tracks" BEFORE "hands".
            for h in TRACKED_HANDS:
                _hand_track_ids[h] = -1
            _ids = getattr(_hand_identity_tracker, "last_track_ids", [])
            for _i, _lab in enumerate(labels):
                if _lab in _hand_track_ids and _i < len(_ids):
                    _hand_track_ids[_lab] = _ids[_i]

            _count_relabels()
            # ⭐ ONE clock read for the whole frame, reused below by U8's
            # confirmation window. Reading it per hand would be a second (and
            # third) sample of the same instant -- and the owner's constraint on
            # U8 was explicitly that it must not sample per frame to work out a
            # rate. It does not: it never estimates fps at all, it just subtracts.
            _frame_ms = time.perf_counter() * 1000.0
            _bind_upstream_track_state(_frame_ms)

            for d, label in zip(detections, labels):
                # thumb_outward is chirality-sensitive, so it must be computed
                # from the RESOLVED label, not MediaPipe's raw one.
                # DR-2 (queue item 2.2): freeze the palm/back sign while edge-on,
                # exactly as production does -- same shared tracker class, same
                # per-hand state. Mirrored here because the debug tool must stay in
                # tune with production (owner instruction, 2026-08-02).
                # ⭐ U7: the WORLD landmarks drive the chirality correction now,
                # not the label -- same shared tracker, same single edit as
                # production. See `Claude/HANDEDNESS_LABEL_DEFECT.md`.
                _dr2_outward, _dr2_valid = _palm_facing_trackers[label].update(
                    d["pixel_landmarks"], label, d["world_landmarks"],
                    track_id=_hand_track_ids.get(label, -1), now_ms=_frame_ms
                )
                hand_data_by_hand[label] = {
                    "pixel_landmarks": d["pixel_landmarks"],
                    "world_landmarks": d["world_landmarks"],
                    "thumb_outward": _dr2_outward,
                    # carried so the recorder can store them -- see its comment
                    "score": d["score"],
                    "raw_handedness": d["raw_handedness"],
                }
                normalized_by_hand[label] = d["normalized"]

            # ⚠ AFTER the fill loop above, never before it. `hand_data_by_hand`
            # starts as {hand: None} and is populated by that loop; calling
            # _update_depth earlier read an all-None dict every frame, so every
            # readout was None, `parts` was empty and the HUD line was never
            # drawn. That is why the owner reported "I still can't see the depth"
            # even after the y-position was fixed -- two independent bugs on the
            # same line of output, and the first one masked the second.
            _update_depth(hand_data_by_hand)
            # ⭐ 4.2: the ABSOLUTE hand depth the 3D snap gate reads. ONCE per
            # frame, before the arms, for the same reason DR-2 is resolved here:
            # it is a property of the hand, not of an arm's cubes, and stepping
            # its hysteresis once per arm would advance it three times a frame.
            _update_snap_depth(hand_data_by_hand, (width, height))

            # ⭐ T6d: read the sliders, then derive this frame's rebuild terms per
            # hand -- BEFORE the arms run, so the HUD, the recorder and the
            # estimator all describe the same frame under the same parameters.
            if args.sliders:
                _read_sliders()
            # ⭐ One global, pushed onto every arm running the time-based form, so
            # the slider and the maths cannot disagree about which tau ran.
            for _a in arms:
                if _a.slerp_mode == "time":
                    _a.slerp_tau_ms = SLERP_TAU_MS
            # ⛔ THE SETTING MUST BE ON THE RECORD, PER FRAME. The first lag take
            # recorded 1191 frames with NO record of which smoothing it ran, so it
            # could not be attributed to a setting at all -- and the whole reason
            # this log exists is that the knob moves DURING the take.
            if SLERP_TAU_MS != _tau_last:
                _tau_changes.append({"frame": len(records) if args.record else -1,
                                     "t_capture_ms": round(t_capture_ms, 2),
                                     "slerp_tau_ms": SLERP_TAU_MS})
                _tau_last = SLERP_TAU_MS

            # ⭐ ONE update per arm, all fed the SAME `hand_data_by_hand`. The
            # arms differ only in their own Phase D configuration, so a
            # divergence between panels has exactly one cause.
            # ⚠ In the lag rig each arm carries its OWN Horn (see
            # `_make_slerp_ab_arms`) and overrides this; a single shared estimator
            # would share its frozen reference between the panels.
            update_hands_all(arms, hand_data_by_hand, rotation=PRODUCTION_ROTATION)

            if args.record:
                # Schema is DELIBERATELY identical to RecordPerceptionSequence.py's
                # raw_landmarks.jsonl, so every existing analysis/t5*.py harness
                # reads this file unchanged. "cubes" is additive -- those readers
                # only touch "hands" -- and carries what they could never see
                # before: the orientation actually applied to the cube.
                rec_hands = []
                for handedness in TRACKED_HANDS:
                    d = hand_data_by_hand.get(handedness)
                    if d is None:
                        continue
                    rec_hands.append({
                        "handedness": handedness,
                        "landmarks": [[round(x, 2), round(y, 2)] for x, y in d["pixel_landmarks"]],
                        "world_landmarks": [[round(x, 5), round(y, 5), round(z, 5)]
                                            for x, y, z in d["world_landmarks"]],
                        "thumb_outward": bool(d["thumb_outward"]),
                        # ⚠ MediaPipe's own handedness confidence, and the RAW
                        # label before DR-1 overrode it. Missing until 2026-08-22,
                        # and its absence blocked a diagnosis: when a hand
                        # re-enters showing its BACK, the label is least reliable
                        # (spec §0.4 -- flips at ~0.66 against a 0.95-0.99
                        # baseline), and `is_thumb_outward` INVERTS under a wrong
                        # label, so a back-of-hand hand computes as "palm" and
                        # rule 3's gate lets it snap. Without the score there is
                        # no way to corroborate that from a recording.
                        "score": round(float(d.get("score", 0.0)), 4),
                        "raw_handedness": d.get("raw_handedness"),
                        # 4.1/T3: store the STABLE id so a replay can read it
                        # instead of reconstructing it. The first A/B session had
                        # to re-derive ids by re-running DR-1 -- sound, since it
                        # is deterministic, but stored is strictly better evidence.
                        "trackId": int(_hand_track_ids.get(handedness, -1)),
                        # ⭐ 4.2 / schema 3 (N6, matching production's
                        # `_record_flush`): the depth the snap gate actually
                        # used, and whether it was MEASURED or held. Without
                        # `depth_valid` a snap refused by DECISION 1 is
                        # indistinguishable from a hand that was near nothing --
                        # and DECISION 1 is the constant flagged for re-tuning,
                        # so that distinction is the whole point of the field.
                        "hand_depth_m": (None if d.get("hand_depth") is None
                                         or d["hand_depth"][0] is None
                                         else round(d["hand_depth"][0], 4)),
                        "depth_valid": bool(d.get("hand_depth")
                                            and d["hand_depth"][1]),
                    })
                records.append({
                    "tCapture": round(t_capture_ms, 2),
                    "hands": rec_hands,
                    # ⚠ PER ARM, not arms[0]. Storing only the first arm made a
                    # multi-arm recording unable to answer questions about the
                    # other panels -- and in the ownership rig arms[0] is the
                    # LABEL control, so the SHIPPED arm's cubes were the ones
                    # missing. Found while trying to verify the stranded-cube fix
                    # from a recording and discovering the data was not there.
                    # ⚠⚠ THE KEY MUST BE UNIQUE PER ARM, AND IT MUST INCLUDE THE
                    # ARM INDEX. This has now failed TWICE and each time silently
                    # discarded the data the session was recorded to produce:
                    #   1. it stored only arms[0] -- in the ownership rig that is
                    #      the LABEL control, so the SHIPPED arm was missing;
                    #   2. it keyed on arm_label+ownership -- in the U5 coast rig
                    #      all three arms are "blend"+"track", so they COLLIDED
                    #      and only the last (450 ms) survived.
                    # Leading with the index makes a collision impossible whatever
                    # the arms differ by; the rest is there to be readable.
                    "cubes": {
                        (f"{i}:{arm.arm_label}"
                         f":{getattr(arm, 'ownership', '?')}"
                         f":{arm.bridge_window_ms:.0f}ms"): {
                            # ⭐ POSITION + SIZE recorded 2026-08-23. Without them
                            # the play-area invariant (U9) can only be checked by
                            # REPLAYING a take, i.e. by re-deriving what the tool
                            # already knew -- and a re-derivation is a second
                            # implementation that can silently disagree. `size` is
                            # here too so a harness can test the whole object's
                            # extent, not just its top-left corner.
                            # ⭐ 4.2 / schema 3: `depth_m` and `projected_size`.
                            # `size` stays the NOMINAL extent so nothing that
                            # reads it changes meaning; `projected_size` is what
                            # was actually drawn and what the play-area
                            # invariant is expressed in now that both the margin
                            # and the extent move with depth.
                            name: {"owner": c.owner,
                                   "position": [round(v, 2) for v in c.position],
                                   "size": c.size,
                                   "depth_m": round(c.depth_m, 4),
                                   "projected_size": round(arm.projected_size_of(c), 2),
                                   "orientation": [round(v, 6) for v in c.orientation]}
                            for name, c in arm.cubes.items()
                        }
                        for i, arm in enumerate(arms)
                    },
                    # ⚠ PER FRAME, not once in meta.json. The sliders move during
                    # the take, so a frame that does not carry its own parameters
                    # cannot be attributed to a setting.

                    # ⚠ PER FRAME: the smoothing is on a slider and moves DURING
                    # the take, so a frame that does not carry its own value cannot
                    # be attributed to a setting.
                    "slerp_tau_ms": SLERP_TAU_MS,
                    "slerp_mode": [a.slerp_mode for a in arms],
                })

            for i, arm in enumerate(arms):
                panel = frame if len(arms) == 1 else frame.copy()
                for handedness, normalized in normalized_by_hand.items():
                    data = hand_data_by_hand[handedness]
                    _draw_hand(
                        panel, normalized, handedness, data["thumb_outward"],
                        arm.last_hand_reliability_alpha[handedness], width, height,
                    )
                # ⭐ In the A/B rig, panel 2 also carries panel 1's cube as a
                # wireframe. Positions are bit-identical between the arms, so any
                # visible gap between cage and solid IS the estimator difference.
                _draw_cubes(panel, arm)
                _draw_bridge_hud(panel, arm, height)
                if args.slerp_ab and i == 1:
                    _draw_ab_divergence(panel, arms[0], arm, height)
                # ⭐ T6d: the readout belongs on the panel the sliders DRIVE. In the
                # A/B rig that is panel 2; in the single-arm view it is the only
                # panel. Putting it on the control panel would invite reading
                # panel 1's cube against panel 2's numbers.
                cv2.imshow(windows[i], panel)
            _draw_slider_panel(args.sliders)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if any(cv2.getWindowProperty(n, cv2.WND_PROP_VISIBLE) < 1 for n in windows):
                break
            if args.duration and (time.perf_counter() - t0) >= args.duration:
                print("[LiveSnapDebug] duration reached")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[LiveSnapDebug] Stopped, camera released.")
        if session_dir is not None:
            elapsed = time.perf_counter() - t0
            fps = len(records) / elapsed if elapsed > 0 else 0.0
            with open(os.path.join(session_dir, "raw_landmarks.jsonl"), "w",
                      encoding="utf-8") as fh:
                for r in records:
                    fh.write(json.dumps(r) + "\n")
            with open(os.path.join(session_dir, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    # ⭐ Matches production's marker (N6). 2 = cubes are
                    # snapshotted AFTER the frame's logic and carry position +
                    # size. The debug tool always had the "after" alignment;
                    # production did not until 2026-08-23, and the mismatch
                    # produced phantom violations in a harness that paired
                    # hands[i] with cubes[i].
                    # ⭐ 3 (4.2) = depth is on the wire: per cube `depth_m` and
                    # `projected_size`, per hand `hand_depth_m` / `depth_valid`.
                    # ⚠ REQUIRED to check the play area on a schema-3 take: the
                    # margin and the object's extent both move with depth, so a
                    # harness assuming 60 px and a fixed size reads it wrong.
                    "recorder_schema": 3,
                    "sequence": args.tag,
                    "source": "LiveSnapDebug.py --record (cube visible live)",
                    "note": args.note,
                    "frames": len(records),
                    "duration_s": round(elapsed, 2),
                    "measured_fps": round(fps, 2),
                    "bridge": args.bridge,
                    # ⚠ THE ARMS THAT RAN, not the `--arms` flag. A rig builds its
                    # own panel count (the T6d A/B builds two while `--arms`
                    # defaults to 1), so the flag was recording "1" for a two-panel
                    # take -- and `cubes` is keyed by arm INDEX, so a reader
                    # trusting this number would stop at panel 1 and never see the
                    # arm the session existed to test. Same class as the two
                    # collisions the `cubes` key comment already records.
                    "arms": len(arms),
                    "arms_flag": args.arms,
                    "rig": ("slerp_ab" if args.slerp_ab else
                            "ownership_ab" if args.ownership_ab else
                            "coast_ab" if args.coast_ab else
                            "three_arm" if args.arms == 3 else "single"),
                    # ⭐ Which estimator each panel ran, by index -- the one fact a
                    # T6d A/B take cannot be read without.
                    "arm_rotation": [getattr(getattr(a, "rotation", None), "name",
                                             "horn_palm_ref") for a in arms],
                    # ⭐ Ground truth. Without it a recording cannot answer "was
                    # the label right?", because the label is the thing under
                    # suspicion -- and the corpus has no images (N14) to fall
                    # back on. Declared by the operator, not inferred.
                    "known_hand": args.known_hand,
                    # ⭐⭐ `tau_changes` is the take's INDEX: every smoothing change
                    # with the frame it happened on, so the recording can be cut
                    # into per-setting segments. A knob that moves during a take and
                    # is recorded only once describes just its last few seconds.
                    "slerp_tau_ms_final": SLERP_TAU_MS,
                    "slerp_tau_max_ms": SLERP_TAU_MAX_MS,
                    "tau_changes": _tau_changes,
                    "slerp_mode": [a.slerp_mode for a in arms],
                    # ⭐ Every tuned value, so a take is self-describing and a
                    # setting the owner liked can be recovered from the recording.
                    "settled_values": settled_values(),
                }, fh, indent=2)
            with_hand = sum(1 for r in records if r["hands"])
            print(f"[LiveSnapDebug] Saved {len(records)} frames "
                  f"({fps:.2f} fps measured) to {session_dir}")
            print(f"[LiveSnapDebug] frames with >=1 hand: {with_hand}/{len(records)}")
            print_settled_values()


if __name__ == "__main__":
    main()
