import argparse
import math
import os
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
GRAB_RADIUS_MULTIPLIER = 1.5
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


def _make_cube_mesh(color_x, color_y, color_z) -> Mesh:
    vertices = (
        (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
    )
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


@dataclass
class HandOrientationFilter:
    """Per-hand predictive/reliability-weighted orientation filter state
    (see the "Attempt 3" comment above `CONDITIONING_ALPHA_LOW`, further
    down this file). A property of the HAND's own signal, not of whichever
    cube it holds (if any), so it lives on CubeState rather than on Cube.
    `last_fused` is the filter's own running orientation estimate (this
    frame's output, next frame's prediction base); `omega` is the most
    recently observed per-frame rotation delta among accepted/fused frames
    (the constant-angular-velocity model's state). Reset to a fresh
    instance whenever the hand isn't detected (see update_hands), so
    reacquiring tracking after a gap never predicts from a stale
    reference. Uses raw tuples, not the `Quat` alias, because this class is
    defined before that alias exists further down the file (same reason
    `Cube.orientation` above does the same)."""
    last_fused: Optional[Tuple[float, float, float, float]] = None
    omega: Tuple[float, float, float, float] = IDENTITY_QUATERNION


@dataclass
class CubeState:
    window_size: Tuple[int, int]
    cubes: Dict[str, Cube] = field(default_factory=dict)
    # Thumb-outward snap rule state (§13.6) — see update_hands' docstring.
    last_known_thumb_outward: Dict[str, bool] = field(default_factory=lambda: {h: False for h in TRACKED_HANDS})
    thumb_outward_snap_allowed: Dict[str, bool] = field(default_factory=lambda: {h: False for h in TRACKED_HANDS})
    # Predictive/reliability-weighted orientation filter (see "Attempt 3"
    # above CONDITIONING_ALPHA_LOW) — a property of the HAND's own signal,
    # not of whichever cube it holds, so it lives here rather than on Cube.
    # Reset to a fresh HandOrientationFilter() whenever the hand isn't
    # detected (see update_hands), so reacquiring tracking after a gap
    # never predicts from a stale reference.
    hand_orientation_filters: Dict[str, HandOrientationFilter] = field(
        default_factory=lambda: {h: HandOrientationFilter() for h in TRACKED_HANDS}
    )
    # Reliability weight (0-1) the filter used most recently for each hand,
    # exposed purely for the on-screen diagnostic (_draw_hand) — 1.0 means
    # fully trusting the raw reading, 0.0 means fully coasting on the
    # predicted/extrapolated orientation.
    last_hand_reliability_alpha: Dict[str, float] = field(default_factory=lambda: {h: 1.0 for h in TRACKED_HANDS})

    def __post_init__(self):
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

    def cube_center(self, name: str) -> Tuple[float, float]:
        cube = self.cubes[name]
        return (cube.position[0] + cube.size / 2, cube.position[1] + cube.size / 2)

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
        cube.grab_landmark_weights = None
        cube.grab_residual_offset = None

    def set_target_position(self, name: str, top_left: Tuple[float, float]) -> None:
        cube = self.cubes[name]
        x, y = top_left
        clamped_x = max(0.0, min(x, self.window_size[0] - cube.size))
        clamped_y = max(0.0, min(y, self.window_size[1] - cube.size))
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


def _top_left_for_center(center: Tuple[float, float], size: int) -> Tuple[float, float]:
    return (center[0] - size / 2, center[1] - size / 2)


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


def _predictive_filter_step(filt: HandOrientationFilter, raw_quat: Quat, conditioning_norm: float) -> Quat:
    """Advances `filt` by one frame and returns the fused orientation to
    use as `hand_quat_now`. See the "Attempt 3" comment above
    CONDITIONING_ALPHA_LOW for the full design rationale; verified against
    recorded data before being wired in here (GESTURE_PIPELINE_SPEC.md
    §13.7)."""
    if filt.last_fused is None:
        # First sighting since the last reset -- nothing to predict from yet.
        filt.last_fused = raw_quat
        return raw_quat
    raw_quat = _make_continuous(raw_quat, filt.last_fused)
    predicted = _make_continuous(_quat_multiply(filt.omega, filt.last_fused), filt.last_fused)
    alpha = _reliability_alpha(conditioning_norm)
    fused = _quat_slerp(predicted, raw_quat, alpha)
    filt.omega = _quat_multiply(fused, _quat_conjugate(filt.last_fused))
    filt.last_fused = fused
    return fused


def _try_snap(state: CubeState, handedness: str, hand_pos: Tuple[float, float], exclude=frozenset()) -> Optional[str]:
    """Grab radius scales to EACH candidate cube's OWN size (2026-08-01,
    matching production's CubeWindow.py fix) -- a single shared radius
    stopped making sense once the two cubes have different sizes."""
    best_name, best_dist = None, None
    for name in state.unowned_cube_names():
        if name in exclude:
            continue
        grab_radius = state.cubes[name].size * GRAB_RADIUS_MULTIPLIER
        cx, cy = state.cube_center(name)
        dist = math.hypot(hand_pos[0] - cx, hand_pos[1] - cy)
        if dist <= grab_radius and (best_dist is None or dist <= best_dist):
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

    Predictive, reliability-weighted orientation filtering (see "Attempt 3"
    above CONDITIONING_ALPHA_LOW, 2026-08-01): each hand's raw orientation
    reading is passed through `_predictive_filter_step` (per-hand state in
    `state.hand_orientation_filters`) BEFORE being fed into the grab-delta
    math above. That filter maintains a running angular-velocity estimate
    and blends the raw reading with a one-step extrapolation of it,
    weighted by `_reliability_alpha(conditioning_norm)` — never a hard
    accept/reject, always a continuous blend. This replaced two earlier
    binary-filter attempts (see the module-level comment above
    CONDITIONING_ALPHA_LOW for the full history of why) and is verified
    against recorded data to eliminate the large (>30/>60 degree)
    per-frame jumps at the pitch crossing without changing already-healthy
    frames at all (alpha=1 there, zero added lag)."""
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
            state.hand_orientation_filters[handedness] = HandOrientationFilter()  # avoid predicting from a stale reference on reacquire
            continue
        thumb_outward = data["thumb_outward"]
        state.last_known_thumb_outward[handedness] = thumb_outward
        if not thumb_outward:
            state.thumb_outward_snap_allowed[handedness] = False

        hand_pos = _hand_position(data["pixel_landmarks"])
        raw_quat, conditioning_norm = _hand_orientation_quaternion(data["world_landmarks"])
        state.last_hand_reliability_alpha[handedness] = _reliability_alpha(conditioning_norm)
        hand_quat_now = _predictive_filter_step(
            state.hand_orientation_filters[handedness], raw_quat, conditioning_norm
        )

        owned = state.cube_owned_by(handedness)
        if owned is None:
            can_snap = (not thumb_outward) or state.thumb_outward_snap_allowed[handedness]
            if can_snap:
                owned = _try_snap(state, handedness, hand_pos, exclude=released_this_frame)
                if owned is not None:
                    cube = state.cubes[owned]
                    cube.grab_hand_orientation = hand_quat_now
                    cube.grab_cube_orientation = cube.orientation
                    # Object position at the instant of grab -- captured
                    # from the cube's own pre-existing center, BEFORE this
                    # frame's translation update below touches it, so this
                    # is genuinely "wherever the cube visually was," not
                    # the hand anchor (§14.1's whole point: today's
                    # zero-offset design discarded this; the redesign
                    # preserves it, same no-pop principle as the
                    # orientation baseline just above).
                    object_pos_at_grab = state.cube_center(owned)
                    cube.grab_landmark_weights = _compute_grab_weights(object_pos_at_grab, data["pixel_landmarks"])
                    weighted_at_grab = _weighted_position(cube.grab_landmark_weights, data["pixel_landmarks"])
                    cube.grab_residual_offset = (
                        object_pos_at_grab[0] - weighted_at_grab[0],
                        object_pos_at_grab[1] - weighted_at_grab[1],
                    )
        if owned is not None:
            cube = state.cubes[owned]
            weighted_now = _weighted_position(cube.grab_landmark_weights, data["pixel_landmarks"])
            new_center = (
                weighted_now[0] + cube.grab_residual_offset[0],
                weighted_now[1] + cube.grab_residual_offset[1],
            )
            state.set_target_position(owned, _top_left_for_center(new_center, cube.size))
            delta = _quat_multiply(hand_quat_now, _quat_conjugate(cube.grab_hand_orientation))
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
            cube.orientation = _quat_slerp(cube.orientation, target_quat, ROTATION_SLERP_FACTOR)


def _draw_hand(frame, normalized_landmarks, handedness, thumb_outward, snap_allowed, reliability_alpha, width, height):
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
    # Predictive-filter reliability diagnostic (see "Attempt 3" above
    # CONDITIONING_ALPHA_LOW) -- a per-hand signal, drawn here rather than
    # on the cube since it's about the hand's own reading, independent of
    # whether it currently holds anything. alpha=1.0 (not drawn) means the
    # filter is fully trusting the raw reading; lower values mean it's
    # increasingly coasting on the predicted/extrapolated orientation.
    if reliability_alpha < 0.999:
        color = (0, 140, 255) if reliability_alpha > 0.0 else (0, 0, 255)
        cv2.putText(frame, f"{handedness}: reliability {reliability_alpha:.2f}", (text_x, max(text_y, 20) + 24),
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
    half = cube.size / 2.0
    camera_distance = cube.size * CUBE_PERSPECTIVE_DISTANCE_RATIO
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
        screen_center = (cube.position[0] + cube.size / 2, cube.position[1] + cube.size / 2)
        _draw_cube_3d(overlay, cube, screen_center)
    cv2.addWeighted(overlay, CUBE_ALPHA, frame, 1 - CUBE_ALPHA, 0, frame)
    for cube in state.cubes.values():
        if cube.owner is not None:
            x, y = int(cube.position[0]), int(cube.position[1])
            cv2.rectangle(frame, (x, y), (x + cube.size, y + cube.size), SNAP_BORDER_COLOR, SNAP_BORDER_WIDTH)


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
                    state.last_hand_reliability_alpha[handedness], width, height,
                )

            _draw_cubes(frame, state)

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
