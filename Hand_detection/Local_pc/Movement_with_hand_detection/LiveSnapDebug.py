import argparse
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Combined single-window debug tool for the new snap/translate gesture set
# (Claude/GESTURE_PIPELINE_SPEC.md §13). TEMPORARY, per direction: overlays
# semi-transparent cubes directly on the live camera + hand-landmarks feed
# (one window instead of the production split's two -- webcam preview +
# separate pygame cube window) so snap/translate can be visually verified
# against the real hand position in the same frame. Meant to be deleted
# once the gesture set is built and verified; NOT part of the production
# client/server pipeline (`Resources/HandsTriggeredActions.py`/
# `Resources/CubeWindow.py`, which stay independent of this file and of
# each other's rendering choice, same "deliberately independent debug
# tool" pattern as `LiveGestureDebug.py` used for pinch).
#
# Deliberately duplicates (not imports) HandsTriggeredActions.py's small
# snap/translate logic rather than sharing it -- that module's `cube_window`
# is a module-level pygame CubeWindow instantiated at import time (opens a
# real pygame window as a side effect), which this single-OpenCV-window
# tool must not trigger. Keep the two logic copies in sync by hand if the
# snap/translate design changes; this file is temporary and small enough
# that a shared-abstraction refactor isn't worth it before it's deleted.

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

TRACKED_HANDS = ("Left", "Right")

WRIST = 0
INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 5, 9, 13, 17
HAND_POSITION_LANDMARKS = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

CUBE_SIZE = 60
GRAB_RADIUS_MULTIPLIER = 1.5
CUBE_ALPHA = 0.55  # transparency of the cube overlay, so the video stays visible underneath
SNAP_BORDER_COLOR = (255, 255, 255)
SNAP_BORDER_WIDTH = 4

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
ROTATION_SLERP_FACTOR = 0.25  # tune by feel once live, same discipline as GRAB_RADIUS_MULTIPLIER
GIZMO_AXIS_LENGTH = CUBE_SIZE * 0.9
GIZMO_PERSPECTIVE_K = 0.6  # cosmetic weak-perspective foreshortening only, tune by feel
GIZMO_AXIS_COLORS = {"x": (0, 0, 255), "y": (0, 255, 0), "z": (255, 160, 0)}  # BGR: X=red, Y=green, Z=blue-ish

# Raw-signal glitch detection (2026-08-01, revised after live testing found
# the first attempt below over-triggered):
#
# Attempt 1 (removed): reject a frame outright if its target orientation was
# far from the CUBE's current (slerped) orientation, freezing the cube for
# that frame. Live result: many CONSECUTIVE frames got rejected during
# otherwise-smooth pitch rotation (rotating about the screen's horizontal
# axis -- crossing from palm-toward-camera to back-of-hand-toward-camera).
# Root cause, on inspection: comparing against the cube's orientation is
# comparing against a LAGGING reference (slerp itself lags by design, and
# each rejection freezes it further) -- once one frame tripped the
# threshold, the cube fell further behind, making the NEXT frame's gap look
# even bigger against that same stale reference. A self-reinforcing trap,
# not a threshold-tuning problem.
#
# Separately: `_orthonormal_frame`/`_matrix_to_quaternion` are continuous
# functions of (wrist, index_MCP, pinky_MCP) wherever the frame isn't
# geometrically degenerate, and quaternion double-cover is already handled
# (see _quat_angle_deg's abs(dot)) -- so a genuine large single-frame jump
# in the RAW hand-orientation reading can only come from MediaPipe's own
# `hand_world_landmarks` output itself jumping between frames, not from a
# bug in this file's math. The likely cause: a monocular depth-estimation
# flip at the ambiguous edge-on viewing angle (documented failure mode for
# learned 3D reconstruction under depth ambiguity) -- PART_ONE.md §2's own
# predicted risk ("world_landmarks' z... the least reliable of the three
# coordinates monocularly... expect this to be noisier") landing here.
#
# Attempt 2 (current): compare each frame's RAW reading only to the
# PREVIOUS RAW reading (`CubeState.last_raw_hand_orientation`, always
# advanced every detected frame, substituted rather than frozen on a
# flagged frame) -- never to a lagged/frozen value, so there is no
# reference to fall behind and no accumulating trap. A real hand cannot
# rotate this far in one ~33ms frame regardless of intent (even a fast
# flick is well under this per-frame bound at 30fps), so a jump this size
# is still a physically-justified glitch signal, not a guess -- but now one
# that self-heals within a single frame instead of compounding.
RAW_ORIENTATION_GLITCH_DEG = 60.0


@dataclass
class Cube:
    color: Tuple[int, int, int]
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


@dataclass
class CubeState:
    window_size: Tuple[int, int]
    cubes: Dict[str, Cube] = field(default_factory=dict)
    # Thumb-outward snap rule state (§13.6) — see update_hands' docstring.
    last_known_thumb_outward: Dict[str, bool] = field(default_factory=lambda: {h: False for h in TRACKED_HANDS})
    thumb_outward_snap_allowed: Dict[str, bool] = field(default_factory=lambda: {h: False for h in TRACKED_HANDS})
    # Raw-signal glitch filter state (RAW_ORIENTATION_GLITCH_DEG above) — a
    # property of the HAND's own orientation signal, not of whichever cube
    # (if any) it's holding, so it lives here rather than on Cube. Reset to
    # None whenever the hand isn't detected (see update_hands), so
    # reacquiring tracking after a gap never compares against a stale value.
    last_raw_hand_orientation: Dict[str, Optional[Tuple[float, float, float, float]]] = field(
        default_factory=lambda: {h: None for h in TRACKED_HANDS}
    )
    last_hand_glitch_flagged: Dict[str, bool] = field(default_factory=lambda: {h: False for h in TRACKED_HANDS})

    def __post_init__(self):
        if not self.cubes:
            center = self._centered_position()
            self.cubes = {
                "blue": Cube(color=(255, 200, 0), position=center),
                "red": Cube(color=(60, 60, 220), position=center),
            }

    def _centered_position(self) -> Tuple[float, float]:
        return ((self.window_size[0] - CUBE_SIZE) / 2, (self.window_size[1] - CUBE_SIZE) / 2)

    def cube_center(self, name: str) -> Tuple[float, float]:
        cube = self.cubes[name]
        return (cube.position[0] + CUBE_SIZE / 2, cube.position[1] + CUBE_SIZE / 2)

    def unowned_cube_names(self):
        return [name for name, cube in self.cubes.items() if cube.owner is None]

    def cube_owned_by(self, handedness: str) -> Optional[str]:
        for name, cube in self.cubes.items():
            if cube.owner == handedness:
                return name
        return None

    def snap_cube(self, name: str, handedness: str) -> None:
        self.cubes[name].owner = handedness

    def release_cube(self, name: str) -> None:
        cube = self.cubes[name]
        cube.owner = None
        cube.grab_hand_orientation = None
        cube.grab_cube_orientation = None

    def set_target_position(self, name: str, top_left: Tuple[float, float]) -> None:
        cube = self.cubes[name]
        x, y = top_left
        clamped_x = max(0.0, min(x, self.window_size[0] - CUBE_SIZE))
        clamped_y = max(0.0, min(y, self.window_size[1] - CUBE_SIZE))
        cube.position = (clamped_x, clamped_y)


def _is_thumb_outward(pixel_landmarks, handedness: str) -> bool:
    """True when the hand is oriented with the thumb outward (back of hand
    facing the camera) -- GESTURE_PIPELINE_SPEC.md §13.6. Sign of the 2D
    cross product of (index_MCP-wrist) x (pinky_MCP-wrist) in mirrored
    webcam-frame pixel coordinates, mirrored again per handedness for a
    physically consistent sign across both hands. CALIBRATED LIVE
    2026-08-01: positive (mirrored-for-Left) = thumb-outward, confirmed by
    the operator showing palm/back of hand for both hands via this file's
    on-screen facing-sign display before this threshold was set (same
    live-verify-before-trusting discipline that caught the Closed_Fist
    problem)."""
    wrist = pixel_landmarks[WRIST]
    idx_mcp = pixel_landmarks[INDEX_MCP]
    pinky_mcp = pixel_landmarks[PINKY_MCP]
    v1 = (idx_mcp[0] - wrist[0], idx_mcp[1] - wrist[1])
    v2 = (pinky_mcp[0] - wrist[0], pinky_mcp[1] - wrist[1])
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    if handedness == "Left":
        cross = -cross
    return cross > 0


def _hand_position(pixel_landmarks) -> Tuple[float, float]:
    xs = [pixel_landmarks[i][0] for i in HAND_POSITION_LANDMARKS]
    ys = [pixel_landmarks[i][1] for i in HAND_POSITION_LANDMARKS]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _top_left_for_center(center: Tuple[float, float]) -> Tuple[float, float]:
    return (center[0] - CUBE_SIZE / 2, center[1] - CUBE_SIZE / 2)


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


def _orthonormal_frame(wrist: Vec3, index_mcp: Vec3, pinky_mcp: Vec3) -> Tuple[Vec3, Vec3, Vec3]:
    """Gram-Schmidt orthonormal frame from a hand's world landmarks: e1
    along wrist->index_MCP, e2 the wrist->pinky_MCP direction orthogonalized
    against e1, e3 = e1 x e2 completing a right-handed frame. Returns the
    rotation matrix as its three orthonormal column vectors (e1, e2, e3) --
    this IS the target hand-orientation, converted to a quaternion by
    _matrix_to_quaternion below."""
    e1 = _vec_normalize(_vec_sub(index_mcp, wrist))
    v2 = _vec_sub(pinky_mcp, wrist)
    v2_orth = _vec_sub(v2, _vec_scale(e1, _vec_dot(v2, e1)))
    e2 = _vec_normalize(v2_orth)
    e3 = _vec_cross(e1, e2)
    return (e1, e2, e3)


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


def _quat_angle_deg(q0: Quat, q1: Quat) -> float:
    """Angle in degrees between two orientations. Uses abs(dot) so q and -q
    (the same rotation, quaternion double-cover) read as 0 degrees apart,
    not 180 -- otherwise every other frame's arbitrary sign choice out of
    _matrix_to_quaternion could look like a huge spurious jump on its own."""
    d = abs(q0[0] * q1[0] + q0[1] * q1[1] + q0[2] * q1[2] + q0[3] * q1[3])
    d = max(-1.0, min(1.0, d))
    return math.degrees(2.0 * math.acos(d))


def _hand_orientation_quaternion(world_landmarks: List[Vec3]) -> Quat:
    cols = _orthonormal_frame(world_landmarks[WRIST], world_landmarks[INDEX_MCP], world_landmarks[PINKY_MCP])
    return _matrix_to_quaternion(cols)


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


def _try_snap(state: CubeState, handedness: str, hand_pos: Tuple[float, float], exclude=frozenset()) -> Optional[str]:
    grab_radius = CUBE_SIZE * GRAB_RADIUS_MULTIPLIER
    best_name, best_dist = None, grab_radius
    for name in state.unowned_cube_names():
        if name in exclude:
            continue
        cx, cy = state.cube_center(name)
        dist = math.hypot(hand_pos[0] - cx, hand_pos[1] - cy)
        if dist <= best_dist:
            best_name, best_dist = name, dist
    if best_name is not None:
        state.snap_cube(best_name, handedness)
    return best_name


def update_hands(state: CubeState, hand_data_by_hand) -> None:
    """hand_data_by_hand: {handedness: {"pixel_landmarks": [...],
    "world_landmarks": [...], "thumb_outward": bool} or None (not detected
    this frame)}.

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
    was last released, AND it hasn't shown thumb-inward since. Two bits of
    per-hand state track this: `last_known_thumb_outward` (the most recent
    reading while the hand WAS detected — persists through frames where
    it's lost, so a tracking-loss release still has an orientation to
    record) and `thumb_outward_snap_allowed` (the armed/disarmed exception
    itself — armed on release with whatever orientation held at that
    moment, disarmed the instant the hand is seen thumb-inward).

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

    Raw-signal glitch filtering (see RAW_ORIENTATION_GLITCH_DEG above): each
    hand's freshly computed orientation is compared only to ITS OWN previous
    raw reading (`last_raw_hand_orientation`, per-hand, always advanced —
    substituted, never frozen, on a flagged frame) before being fed into the
    grab-delta/slerp math above. This is deliberately independent of
    whether the hand currently holds a cube, and of the cube's own
    (lagging, by design) slerped orientation — comparing against a lagging
    reference is what made the previous version of this filter get stuck
    rejecting many consecutive frames."""
    released_this_frame = set()
    for handedness in TRACKED_HANDS:
        data = hand_data_by_hand[handedness]
        owned = state.cube_owned_by(handedness)
        if owned is None:
            continue
        if data is None:  # tracking lost
            state.release_cube(owned)
            released_this_frame.add(owned)
            state.thumb_outward_snap_allowed[handedness] = state.last_known_thumb_outward[handedness]

    for handedness in TRACKED_HANDS:
        data = hand_data_by_hand[handedness]
        if data is None:
            state.last_raw_hand_orientation[handedness] = None  # avoid comparing against a stale reading on reacquire
            continue
        thumb_outward = data["thumb_outward"]
        state.last_known_thumb_outward[handedness] = thumb_outward
        if not thumb_outward:
            state.thumb_outward_snap_allowed[handedness] = False

        hand_pos = _hand_position(data["pixel_landmarks"])
        raw_quat = _hand_orientation_quaternion(data["world_landmarks"])
        last_raw = state.last_raw_hand_orientation[handedness]
        is_glitch = last_raw is not None and _quat_angle_deg(raw_quat, last_raw) > RAW_ORIENTATION_GLITCH_DEG
        hand_quat_now = last_raw if is_glitch else raw_quat
        # The comparison reference MUST always become this frame's TRUE raw
        # reading, regardless of the accept/reject decision -- not
        # `hand_quat_now` (a bug found live 2026-08-01: that assigns back
        # the OLD value on a flagged frame, so the reference never advances,
        # and every later frame -- even a perfectly clean, stable one -- was
        # still being compared against a stale pre-transition value forever.
        # That reproduced the exact stuck-trap failure this filter exists to
        # avoid, one level down, and is what caused "prolonged" glitch
        # flagging instead of a single flagged frame whenever the hand
        # settled into a genuinely different but stable pose.
        state.last_raw_hand_orientation[handedness] = raw_quat
        state.last_hand_glitch_flagged[handedness] = is_glitch

        owned = state.cube_owned_by(handedness)
        if owned is None:
            can_snap = (not thumb_outward) or state.thumb_outward_snap_allowed[handedness]
            if can_snap:
                owned = _try_snap(state, handedness, hand_pos, exclude=released_this_frame)
                if owned is not None:
                    cube = state.cubes[owned]
                    cube.grab_hand_orientation = hand_quat_now
                    cube.grab_cube_orientation = cube.orientation
        if owned is not None:
            state.set_target_position(owned, _top_left_for_center(hand_pos))
            cube = state.cubes[owned]
            delta = _quat_multiply(hand_quat_now, _quat_conjugate(cube.grab_hand_orientation))
            target_quat = _quat_multiply(delta, cube.grab_cube_orientation)
            cube.orientation = _quat_slerp(cube.orientation, target_quat, ROTATION_SLERP_FACTOR)


def _draw_hand(frame, normalized_landmarks, handedness, thumb_outward, snap_allowed, glitch_flagged, width, height):
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
    if thumb_outward:
        label, color = (f"thumb-outward ({'allowed' if snap_allowed else 'BLOCKED'})",
                         (0, 200, 0) if snap_allowed else (0, 0, 255))
    else:
        label, color = "thumb-inward", (0, 200, 200)
    cv2.putText(frame, f"{handedness}: {label}", (text_x, max(text_y, 20)),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 2, cv2.LINE_AA)
    # Raw-orientation glitch diagnostic (RAW_ORIENTATION_GLITCH_DEG,
    # update_hands' docstring) -- a per-hand signal, drawn here rather than
    # on the cube since it's about the hand's own reading, independent of
    # whether it currently holds anything. Should show as brief, ISOLATED
    # flashes if this is really a rare depth-flip artifact; if it's instead
    # near-continuous during the pitch transition, that points to sustained
    # jitter rather than a one-frame flip -- watch for which live.
    if glitch_flagged:
        cv2.putText(frame, f"{handedness}: ORIENTATION GLITCH", (text_x, max(text_y, 20) + 24),
                    cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)


def _draw_cubes(frame, state: CubeState):
    """Alpha-blended overlay so the video underneath stays visible (per
    direction: 'the overlay has to have some transparency')."""
    overlay = frame.copy()
    for cube in state.cubes.values():
        x, y = int(cube.position[0]), int(cube.position[1])
        cv2.rectangle(overlay, (x, y), (x + CUBE_SIZE, y + CUBE_SIZE), cube.color, -1)
    cv2.addWeighted(overlay, CUBE_ALPHA, frame, 1 - CUBE_ALPHA, 0, frame)
    for cube in state.cubes.values():
        if cube.owner is not None:
            x, y = int(cube.position[0]), int(cube.position[1])
            cv2.rectangle(frame, (x, y), (x + CUBE_SIZE, y + CUBE_SIZE), SNAP_BORDER_COLOR, SNAP_BORDER_WIDTH)


def _project_local_point(local_point: Vec3, quat: Quat, screen_center: Tuple[float, float]) -> Tuple[int, int]:
    """Rotate a cube-local point by its orientation quaternion and project
    it onto the 2D overlay: orthographic in x/y, plus a small cosmetic
    weak-perspective foreshortening term (scale by 1/(1+k*z)) purely so
    rotation toward/away from the camera reads as a size change too, not
    just angle -- this scale factor has no bearing on the rotation's
    correctness, only its legibility, and is safe to retune by feel."""
    rx, ry, rz = _quat_rotate_vector(quat, local_point)
    scale = 1.0 / (1.0 + GIZMO_PERSPECTIVE_K * (rz / GIZMO_AXIS_LENGTH)) if GIZMO_AXIS_LENGTH else 1.0
    return (int(screen_center[0] + rx * scale), int(screen_center[1] + ry * scale))


def _draw_orientation_gizmo(frame, cube: Cube, screen_center: Tuple[float, float]):
    """Draws a 3-axis RGB gizmo (X=red, Y=green, Z=blue-ish) at the cube's
    screen center, rotated by its orientation quaternion -- the visual
    stand-in CubeWindow.py's flat solid square never had for "which way is
    this object facing" (HANDOFF_SNAP_ROTATE_RELEASE.md §2 point 3). Always
    drawn (not just while snapped) so a released cube's frozen orientation
    stays visible, matching position's own freeze-in-place semantics."""
    origin = _project_local_point((0.0, 0.0, 0.0), cube.orientation, screen_center)
    for axis, color in (
        ((GIZMO_AXIS_LENGTH, 0.0, 0.0), GIZMO_AXIS_COLORS["x"]),
        ((0.0, GIZMO_AXIS_LENGTH, 0.0), GIZMO_AXIS_COLORS["y"]),
        ((0.0, 0.0, GIZMO_AXIS_LENGTH), GIZMO_AXIS_COLORS["z"]),
    ):
        tip = _project_local_point(axis, cube.orientation, screen_center)
        cv2.line(frame, origin, tip, color, 3, cv2.LINE_AA)
    cv2.circle(frame, origin, 4, (255, 255, 255), -1)


def build_detector():
    base_options = python.BaseOptions(model_asset_path=HAND_LANDMARKER_MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options, num_hands=2, running_mode=vision.RunningMode.VIDEO,
    )
    return vision.HandLandmarker.create_from_options(options)


def main():
    parser = argparse.ArgumentParser(description="Combined snap/translate debug view (video + landmarks + cube overlay).")
    parser.add_argument("--camera-index", type=int, default=0)
    args = parser.parse_args()

    detector = build_detector()
    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). Is another program using the camera?")

    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read an initial frame from the webcam.")
    height, width = frame.shape[:2]
    state = CubeState(window_size=(width, height))

    window_name = "Snap/translate debug (video + landmarks + cube overlay)"
    timestamp_ms = 0
    print("[LiveSnapDebug] Running -- press 'q' or close the window to stop.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)  # mirror, matching the production pipeline's invert_x

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = detector.detect_for_video(mp_image, timestamp_ms)
            timestamp_ms += 33

            hand_data_by_hand = {h: None for h in TRACKED_HANDS}
            normalized_by_hand = {}
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
                hand_data_by_hand[handedness] = {
                    "pixel_landmarks": pixel_landmarks,
                    "world_landmarks": world_landmarks,
                    "thumb_outward": _is_thumb_outward(pixel_landmarks, handedness),
                }
                normalized_by_hand[handedness] = normalized

            update_hands(state, hand_data_by_hand)

            for handedness, normalized in normalized_by_hand.items():
                data = hand_data_by_hand[handedness]
                _draw_hand(
                    frame, normalized, handedness, data["thumb_outward"],
                    state.thumb_outward_snap_allowed[handedness],
                    state.last_hand_glitch_flagged[handedness], width, height,
                )

            _draw_cubes(frame, state)
            for name, cube in state.cubes.items():
                _draw_orientation_gizmo(frame, cube, state.cube_center(name))

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[LiveSnapDebug] Stopped, camera released.")


if __name__ == "__main__":
    main()
