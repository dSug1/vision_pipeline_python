import math
from typing import Dict, List, Optional, Tuple
from .CubeWindow import CubeWindow

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

# Grab radius (open item, `PART_ONE.md` §5 — "likely scaled to cube size",
# still unresolved/tunable): distance from a cube's CENTER, in the same
# pixel units as hand position, within which an unowned cube can be
# snapped. 1.5x cube size as a starting point — verify by feel live and
# adjust here, this is exactly the kind of value the project's own
# discipline says needs live tuning, not a guess kept forever.
GRAB_RADIUS_MULTIPLIER = 1.5

# TODO (§13.4 open question, pending Phase B's Open_Palm/Closed_Fist
# detection): snap should probably be blocked while the hand is
# closed-fist, so a fist passing near a cube doesn't accidentally grab it.
# Not yet implemented — proximity is the only condition checked below
# until fist detection exists to gate it.

# Thumb-outward snap rule state (§13.6, direct request, 2026-08-01) — see
# on_hands_frame's docstring for the full rule. `_last_known_thumb_outward`
# persists the most recent reading through frames where a hand isn't
# detected (so a tracking-loss release still has an orientation to
# record); `_thumb_outward_snap_allowed` is the armed/disarmed exception.
_last_known_thumb_outward: Dict[str, bool] = {h: False for h in TRACKED_HANDS}
_thumb_outward_snap_allowed: Dict[str, bool] = {h: False for h in TRACKED_HANDS}


def _is_detected(landmarks: List[Tuple[float, float]]) -> bool:
    """A hand not detected this frame arrives as 21 (0, 0) placeholder
    points (see remap_keypoints's expected_count fallback in
    utils_for_remapping_coordinates_and_output_formatting.py) — checking the
    index tip alone mirrors the pre-Part-One check on array[16]/[17]."""
    x, y = landmarks[INDEX_TIP]
    return x != 0 or y != 0


def _hand_position(landmarks: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Palm-center point (see HAND_POSITION_LANDMARKS above), in the same
    mirrored webcam-frame pixel coordinates as the raw landmarks."""
    xs = [landmarks[i][0] for i in HAND_POSITION_LANDMARKS]
    ys = [landmarks[i][1] for i in HAND_POSITION_LANDMARKS]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _is_thumb_outward(landmarks: List[Tuple[float, float]], handedness: str) -> bool:
    """True when the hand is oriented with the thumb outward (back of hand
    facing the camera) — GESTURE_PIPELINE_SPEC.md §13.6. Sign of the 2D
    cross product of (index_MCP-wrist) x (pinky_MCP-wrist) in mirrored
    webcam-frame pixel coordinates, mirrored again per handedness for a
    physically consistent sign across both hands. Calibrated live
    2026-08-01 in LiveSnapDebug.py (kept in sync here) — positive
    (mirrored-for-Left) = thumb-outward, confirmed by the operator showing
    palm/back of hand for both hands against an on-screen sign display
    before this threshold was trusted."""
    wrist = landmarks[WRIST]
    idx_mcp = landmarks[INDEX_MCP]
    pinky_mcp = landmarks[PINKY_MCP]
    v1 = (idx_mcp[0] - wrist[0], idx_mcp[1] - wrist[1])
    v2 = (pinky_mcp[0] - wrist[0], pinky_mcp[1] - wrist[1])
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    if handedness == "Left":
        cross = -cross
    return cross > 0


def _top_left_for_center(center: Tuple[float, float], size: int) -> Tuple[float, float]:
    """CubeWindow.set_target_position takes a cube's top-left corner (how
    Cube.position/pygame.Rect represent it), but hand position should drive
    the cube's CENTER, not its corner — convert once here rather than at
    every call site."""
    return (center[0] - size / 2, center[1] - size / 2)


def _try_snap(handedness: str, hand_pos: Tuple[float, float], exclude=frozenset()) -> Optional[str]:
    """Claims the nearest unowned cube within GRAB_RADIUS of hand_pos, if
    any (skipping names in `exclude` — see on_hands_frame's same-frame
    release/snap ordering note). Returns the claimed cube's name, or None.
    Hands are processed in a fixed order by the caller (Left then Right),
    so two hands can never claim the same cube in the same frame — the
    second hand's check runs after the first's claim is already recorded
    (`PART_ONE.md` §5's same-frame tie-break open item, resolved by
    construction this way)."""
    grab_radius = cube_window.cube_size * GRAB_RADIUS_MULTIPLIER
    best_name, best_dist = None, grab_radius
    for name in cube_window.unowned_cube_names():
        if name in exclude:
            continue
        cx, cy = cube_window.cube_center(name)
        dist = math.hypot(hand_pos[0] - cx, hand_pos[1] - cy)
        if dist <= best_dist:
            best_name, best_dist = name, dist
    if best_name is not None:
        cube_window.snap_cube(best_name, handedness)
    return best_name


def on_hands_frame(left_landmarks: List[Tuple[float, float]], right_landmarks: List[Tuple[float, float]]) -> None:
    """Called once per received "hands" packet with both hands' full
    21-point landmark lists (mirrored webcam-frame pixel coordinates).

    Two passes, not one combined per-hand pass — bug found live
    (2026-08-01): releasing and re-snapping in the same per-hand pass let a
    cube instantly "jump" to the other hand the instant the first hand lost
    tracking, whenever the other hand happened to already be within grab
    radius (its snap-check ran immediately after and saw the just-released
    cube as fair game). Fix: release everyone who needs releasing FIRST,
    across both hands, then snap/translate — and any cube released this
    frame is excluded from THIS frame's snap pass, so the earliest a cube
    can be re-claimed is next frame, never the same tick as its release.

    Thumb-outward snap rule (§13.6, direct request, 2026-08-01): don't snap
    while the hand is thumb-outward (back of hand facing camera) UNLESS the
    hand was already thumb-outward at the moment its currently-held cube
    was last released, AND it hasn't shown thumb-inward since. See the
    module-level `_last_known_thumb_outward`/`_thumb_outward_snap_allowed`
    comment for what each bit of state tracks."""
    hands = (("Left", left_landmarks), ("Right", right_landmarks))

    released_this_frame = set()
    for handedness, landmarks in hands:
        owned_cube = cube_window.cube_owned_by(handedness)
        if owned_cube is None:
            continue
        if not _is_detected(landmarks):
            # Tracking lost: release (freeze in place), matching
            # PART_ONE.md §2's existing release-conditions semantics ("or
            # loss of hand tracking... cube frozen in place, ownership
            # cleared").
            cube_window.release_cube(owned_cube)
            released_this_frame.add(owned_cube)
            _thumb_outward_snap_allowed[handedness] = _last_known_thumb_outward[handedness]

    for handedness, landmarks in hands:
        if not _is_detected(landmarks):
            continue
        thumb_outward = _is_thumb_outward(landmarks, handedness)
        _last_known_thumb_outward[handedness] = thumb_outward
        if not thumb_outward:
            _thumb_outward_snap_allowed[handedness] = False

        hand_pos = _hand_position(landmarks)
        owned_cube = cube_window.cube_owned_by(handedness)
        if owned_cube is None:
            can_snap = (not thumb_outward) or _thumb_outward_snap_allowed[handedness]
            if can_snap:
                owned_cube = _try_snap(handedness, hand_pos, exclude=released_this_frame)
        if owned_cube is not None:
            cube_window.set_target_position(owned_cube, _top_left_for_center(hand_pos, cube_window.cube_size))

    cube_window.pump_and_draw()


def configure_source_resolution(width: int, height: int) -> None:
    """Called once, as soon as the server's "meta" packet arrives, to size
    the cube window to the webcam's actual frame resolution instead of the
    placeholder default it opens with."""
    cube_window.resize((width, height))
