"""The PUSH adapter -- how a running tool hands this frame to the input system.

⭐⭐ WHY THE TOOLS PUSH INSTEAD OF THE PACKAGE PULLING. Production and the debug
tool each compute the palm centre, the depth, the orientation, the palm/back cue
and the tracking state in their per-hand pass. If this package recomputed them it
would be a THIRD implementation of the pipeline, and this project's most expensive
recurring failure is a second implementation quietly disagreeing with the real one
-- four harnesses reported CLEAN on takes the owner had just watched fail. So the
input system reports **what ran**.

⭐ AND THE MAPPING LIVES HERE, NOT IN THE TOOLS. `observe()` takes the tracker
OBJECTS the tools already hold and reads the fields off them, so the "which
attribute means what" knowledge exists once. A copy of that mapping in each tool
is exactly the drift N6 forbids -- and the two tools have already shipped one
divergence of precisely that shape (§13.6.1).
"""
from ..contract import HandFrame, HandObservation, SUSTAINED_LOST


def observe(slot,
            tracking=None,
            palm_facing=None,
            present=False,
            track_id=-1,
            position_px=None,
            depth_m=None,
            depth_valid=False,
            orientation=None,
            thumb_outward=False,
            edge_on=None,
            landmarks_px=None,
            world_landmarks=None):
    """Build one `HandObservation`.

    `tracking`    -- the hand's `hand_state.HandStateTracker` (optional)
    `palm_facing` -- the hand's `palm_geometry.PalmFacingTracker` (optional)

    ⚠ Both are read, never mutated and never advanced: the tools call
    `update()` on them in their own pass, and a second `update()` here would
    double-count a frame. This function only LOOKS.
    """
    tracking_state = SUSTAINED_LOST
    frames_since = 0
    reacquired = 0.0
    orientation_valid = False
    if tracking is not None:
        tracking_state = tracking.tracking_state
        frames_since = int(getattr(tracking, "frames_since_measurement", 0) or 0)
        reacquired = float(getattr(tracking, "reacquired_after_ms", 0.0) or 0.0)
        orientation_valid = bool(getattr(tracking, "orientation_valid", False))

    chirality_confirmed = False
    if palm_facing is not None:
        chirality_confirmed = bool(getattr(palm_facing, "chirality_confirmed", False))
        # ⚠ DR-2's validity bit is authoritative on the FACING tracker when the
        # host has one; `HandStateTracker.orientation_valid` is a copy landed by
        # `set_orientation_valid()` and is False whenever the hand is not
        # TRACKING. Prefer the tracker that produces it.
        orientation_valid = bool(getattr(palm_facing, "orientation_valid",
                                         orientation_valid))

    return HandObservation(
        slot=slot,
        present=bool(present),
        tracking_state=tracking_state,
        track_id=int(track_id if track_id is not None else -1),
        frames_since_measurement=frames_since,
        reacquired_after_ms=reacquired,
        position_px=tuple(position_px) if position_px is not None else None,
        depth_m=depth_m,
        depth_valid=bool(depth_valid),
        orientation=tuple(orientation) if orientation is not None else None,
        thumb_outward=bool(thumb_outward),
        chirality_confirmed=chirality_confirmed,
        orientation_valid=orientation_valid,
        edge_on=edge_on,
        landmarks_px=landmarks_px,
        world_landmarks=world_landmarks,
    )


def frame(time_ms, observations, frame_size=None):
    """Wrap this frame's observations. ⚠ `time_ms` comes from the HOST's capture
    clock -- the same one the trackers are driven from -- so a replay harness
    running faster than real time produces identical events (N7)."""
    return HandFrame(time_ms=float(time_ms),
                     hands=list(observations),
                     frame_size=tuple(frame_size) if frame_size else None)
