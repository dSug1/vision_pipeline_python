import pygame

from . import palm_geometry
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# The vision server sends each hand's landmarks as mirrored webcam-frame pixel
# coordinates (see VisionPipeline.py's remap_keypoints call, invert_x=True).
# This default is only a placeholder shown before the server's real
# resolution arrives — VisionPipeline.py reads the webcam's actual frame size
# and sends it once as a "meta" packet (see PythonApp_Main.py's dispatch for
# datatype == "meta"), which calls resize() below to match it.
DEFAULT_WINDOW_SIZE: Tuple[int, int] = (640, 480)
DEFAULT_CUBE_SIZE = 40  # the SMALL cube's edge length; the LARGE cube is 2x this (direct request, 2026-08-01)

# Snap/hover highlight (Claude/GESTURE_PIPELINE_SPEC.md §13.3, 2026-08-01):
# a snapped cube gets bright edges so snap/release state is visible live
# without needing a separate troubleshooting technique.
SNAP_BORDER_COLOR = (255, 255, 255)
SNAP_BORDER_WIDTH = 3
CUBE_EDGE_COLOR = (20, 20, 20)  # normal (unsnapped) face-outline color

# Real 3D rendering (2026-08-01, direct request — replaces the earlier flat
# pygame.Rect + orientation-gizmo placeholder now that rotation is confirmed
# working end-to-end, see GESTURE_PIPELINE_SPEC.md §13.7). An object's
# orientation quaternion rotates its Mesh's local vertices, perspective-
# projects them, and its faces (each carrying its own color + local normal)
# are backface-culled and painter's-algorithm sorted (farthest drawn first,
# nearest last/on top).
#
# BUG FOUND LIVE (2026-08-01) and fixed: the first version scaled each
# vertex by 1/(1+K*rz/half) -- a formula only ever safe for a single point
# at distance <= half from the origin (true of the axis-gizmo's endpoints,
# which this was copied from), NOT for cube corners, whose distance from
# the origin is half*sqrt(3) (the body diagonal). At some rotations a
# corner's |rz| exceeds half/K, making the denominator go NEGATIVE --
# verified numerically (worst case -0.039 with the original K=0.6): the
# scale flips sign and the vertex jumps to the opposite side of the cube,
# which is exactly the reported "vertices moving so faces morph and the
# cube doesn't stay a cube."
#
# Fixed with a proper, bounded perspective projection instead: a virtual
# camera at a FIXED distance (CUBE_PERSPECTIVE_DISTANCE_RATIO * object.size,
# comfortably larger than the object's own half-diagonal) using the standard
# pinhole-camera divide `scale = camera_distance / (camera_distance + rz)`.
# This is a real, physically-correct perspective transform of a rigid
# body -- it cannot morph a rigid mesh, only foreshorten it correctly, and
# the denominator is verified (numerically swept across full rotations on
# 7+ different axes, both cube sizes) to never drop below ~0.71x
# camera_distance, nowhere near the zero-crossing that caused the bug.
CUBE_PERSPECTIVE_DISTANCE_RATIO = 3.0  # virtual camera distance = object.size * this


def _darken(color: Tuple[int, int, int], factor: float = 0.45) -> Tuple[int, int, int]:
    """The opposite face of each color pair is a darker shade of the same
    color, computed rather than hand-picked, so the pairing is guaranteed
    consistent (direct request 2026-08-01)."""
    return tuple(max(0, int(c * factor)) for c in color)


@dataclass(frozen=True)
class MeshFace:
    """One planar face of a Mesh: which local vertex indices form it (ANY
    polygon size -- 3 for a triangle, 4 for a quad, etc. -- so this scales
    directly to a real imported mesh later, which will typically be all
    triangles), its own LOCAL outward normal (for backface culling after
    rotation), and its own color. Storing color per-face directly (rather
    than the cube's original "+x"/"-x"/etc. axis-keyed lookup) is what
    makes this representation object-agnostic -- an imported mesh's faces
    will carry their own real per-face colors/materials the same way."""
    vertex_indices: Tuple[int, ...]
    normal: Tuple[float, float, float]
    color: Tuple[int, int, int]


@dataclass(frozen=True)
class Mesh:
    """Generic 3D geometry: local-space vertices (unit scale, roughly
    -1..1 per axis -- multiplied by the owning object's own `size` at draw
    time) and faces. This is the piece meant to be swapped out later for a
    real imported 3D object's geometry (Claude/GESTURE_PIPELINE_SPEC.md
    §13.8) -- everything downstream in CubeWindow.CubeWindow._draw_object_3d
    (rotation, perspective projection, backface culling, depth sorting,
    drawing) operates on ANY Mesh identically, with zero cube-specific
    logic. `_make_cube_mesh` below is the ONE cube-specific construction
    function in this file -- a future "import a 3D object" step only needs
    an equivalent factory that builds a Mesh from the imported file, no
    changes anywhere else."""
    vertices: Tuple[Tuple[float, float, float], ...]
    faces: Tuple[MeshFace, ...]


def _make_cube_mesh(color_x: Tuple[int, int, int], color_y: Tuple[int, int, int], color_z: Tuple[int, int, int]) -> Mesh:
    """Builds the placeholder cube Mesh: 8 vertices, 6 quad faces (one
    color family per opposite pair, the - side a computed darker shade of
    the + side, direct request 2026-08-01 -- see _darken). Which physical
    axis gets which color is arbitrary, only the pairing was the actual
    request."""
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


# Large cube: yellow / violet / turquoise (direct request 2026-08-01).
FACE_COLOR_YELLOW = (255, 221, 0)
FACE_COLOR_VIOLET = (170, 90, 224)
FACE_COLOR_TURQUOISE = (64, 224, 208)

# Small cube: green / red / blue (direct request 2026-08-01).
FACE_COLOR_GREEN = (60, 200, 60)
FACE_COLOR_RED = (220, 60, 60)
FACE_COLOR_BLUE = (60, 130, 230)


def _quat_rotate_vector(q: Tuple[float, float, float, float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Rotate a 3-vector by quaternion q (w,x,y,z) -- standard closed form
    for q * (0,v) * q^-1. Duplicated (not imported) from
    HandsTriggeredActions.py's identical function: that module imports
    THIS one (CubeWindow), so importing the other way would be circular;
    a single small vector-rotation formula is cheap enough to keep in sync
    by hand, same "deliberately independent" precedent as LiveSnapDebug.py's
    header comment."""
    w, x, y, z = q
    qv = (x, y, z)
    uv = (qv[1] * v[2] - qv[2] * v[1], qv[2] * v[0] - qv[0] * v[2], qv[0] * v[1] - qv[1] * v[0])
    uuv = (qv[1] * uv[2] - qv[2] * uv[1], qv[2] * uv[0] - qv[0] * uv[2], qv[0] * uv[1] - qv[1] * uv[0])
    return (v[0] + 2.0 * (w * uv[0] + uuv[0]), v[1] + 2.0 * (w * uv[1] + uuv[1]), v[2] + 2.0 * (w * uv[2] + uuv[2]))


@dataclass
class Cube:
    """One on-screen 3D object, snappable to either hand. Named `Cube` for
    historical/current reasons (every object today IS cube-shaped) but its
    geometry lives entirely in `mesh` (a generic `Mesh`, see that class's
    docstring) -- this is deliberately a PLACEHOLDER for future imported 3D
    objects (direct request 2026-08-01, `GESTURE_PIPELINE_SPEC.md` §13.8):
    swapping in a real imported object later means constructing a different
    `Mesh` and assigning it here, no changes to any rendering/projection
    code. See Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13 for the
    gesture design (proximity snap, open-palm rotate, closed-fist release)
    that grew out of Part One's original grab/release/translate/depth/
    rotate matrix (`PART_ONE.md` §3) after pinch was archived 2026-08-01.
    `owner` is None (idle) or an OWNER KEY — either hand can snap either
    object, no fixed pairing.

    ⭐ **The owner key is the stable DR-1 TRACK ID (an int) since 2026-08-22**
    (queue 4.1 / T3), not a handedness string. The label is not an identity: it
    flips, and 113 of 205 measured spurious releases were that flip orphaning a
    held cube. ⚠ It falls back to the handedness string when no id is available
    (-1 on the wire), so this field is deliberately typed loosely — it is
    whatever `HandsTriggeredActions._owner_key()` returned. **Compare it, never
    parse it**: nothing may assume it is a hand name."""
    mesh: Mesh
    size: int
    position: Tuple[float, float] = (0.0, 0.0)
    owner: Optional[object] = None   # owner key: track id (int), or a handedness str
    # Rotation-while-snapped state (§13.7) — orientation is a quaternion
    # (w,x,y,z), relative-to-grab baseline pair captured at the instant of
    # grab so the object keeps its OWN orientation at that moment rather
    # than popping to match the hand's (both None while unowned). See
    # HandsTriggeredActions.py's on_hands_frame docstring for the full
    # mechanism -- kept in sync with LiveSnapDebug.py's identical Cube
    # fields, live-verified there first.
    orientation: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    grab_hand_orientation: Optional[Tuple[float, float, float, float]] = None
    grab_cube_orientation: Optional[Tuple[float, float, float, float]] = None
    # Translation-pivot fix (§14.1/§14.1.1) -- distance-weighted live
    # landmark tracking, ported from LiveSnapDebug.py after live
    # verification there (2026-08-01). Translation counterpart of the
    # rotation baseline pair above: `grab_landmark_weights` (frozen at
    # grab, never recomputed) maps each candidate landmark index to its
    # normalized inverse-distance-from-the-object weight;
    # `grab_residual_offset` is the small constant added every frame so
    # the grab frame itself is exactly continuous (no pop) -- see
    # HandsTriggeredActions.py's `_compute_grab_weights` docstring.
    grab_landmark_weights: Optional[Dict[int, float]] = None
    grab_residual_offset: Optional[Tuple[float, float]] = None


class CubeWindow:
    """A local window with two 3D objects (cube-shaped placeholders for
    now), snappable to either tracked hand. Part One's extension
    (Hand_detection/Claude/PART_ONE.md) of Part Zero's single-cube
    CubeWindow (Hand_detection/Claude/PART_ZERO.md), now driven by the
    proximity-snap/open-palm-rotate/closed-fist-release gesture set
    (`GESTURE_PIPELINE_SPEC.md` §13) rather than the archived pinch design.
    This class only holds/renders object state and exposes ownership
    primitives — snap-radius decisions and hand-pose gating live in
    `HandsTriggeredActions.py`, which is the per-frame gesture logic.

    Object identifiers are "large" and "small" (renamed 2026-08-01 from the
    old "blue"/"red" — those names stopped describing anything once each
    object got three face colors and different sizes; "large"/"small" is
    what actually distinguishes them now, per direct request: the large
    object's every dimension is 2x the small object's)."""

    def __init__(self, window_size: Tuple[int, int] = DEFAULT_WINDOW_SIZE, cube_size: int = DEFAULT_CUBE_SIZE):
        pygame.init()
        self.window_size = window_size
        self.screen = pygame.display.set_mode(window_size)
        pygame.display.set_caption("Part One - two cubes, one per hand")
        self.clock = pygame.time.Clock()
        large_size = cube_size * 2
        small_size = cube_size
        self.cubes: Dict[str, Cube] = {
            "large": Cube(
                mesh=_make_cube_mesh(FACE_COLOR_YELLOW, FACE_COLOR_VIOLET, FACE_COLOR_TURQUOISE),
                size=large_size,
                position=self._centered_position(large_size),
            ),
            "small": Cube(
                mesh=_make_cube_mesh(FACE_COLOR_GREEN, FACE_COLOR_RED, FACE_COLOR_BLUE),
                size=small_size,
                position=self._centered_position(small_size),
            ),
        }
        self.closed = False

    def _centered_position(self, size: int) -> Tuple[float, float]:
        return (
            (self.window_size[0] - size) / 2,
            (self.window_size[1] - size) / 2,
        )

    def resize(self, window_size: Tuple[int, int]) -> None:
        """Re-size the window to the webcam's actual frame resolution, once
        it's known (see the "meta" packet handling in PythonApp_Main.py).
        Re-centers both cubes since their old positions may no longer be
        valid against the new bounds. Each cube uses ITS OWN size to
        center now that the two cubes differ in size."""
        if window_size == self.window_size:
            return
        self.window_size = window_size
        self.screen = pygame.display.set_mode(window_size)
        for cube in self.cubes.values():
            cube.position = self._centered_position(cube.size)

    def set_target_position(self, cube_name: str, position: Tuple[float, float]) -> None:
        """Clamp and store the next position for the named cube ("large" or
        "small"). Mirrors CursorController.set_target_position_async's
        clamping, just against the window bounds instead of the screen
        bounds."""
        cube = self.cubes[cube_name]
        x, y = position
        # ⭐⭐ U9: clamp to the PLAY AREA (the window inset by the edge margin),
        # not to the window itself. Owner, 2026-08-23: the cube could be pushed
        # step by step to the very edge of the display. ⚠ The hand-side margin
        # cannot prevent that -- translation is grab-relative, so the cube keeps
        # its own offset from the hand and creeps further out on every
        # grab-push-drop cycle. This is the invariant; that is the trigger.
        cube.position = palm_geometry.clamp_to_play_area(
            x, y, cube.size, self.window_size)

    def cube_center(self, cube_name: str) -> Tuple[float, float]:
        """Center point of the named cube, for proximity/grab-radius checks
        against a hand position (which is itself a single point, not a
        rect) — comparing against the cube's center rather than its
        top-left corner (`position`) is the geometrically correct proximity
        check."""
        return self.cube_center_from(self.cubes[cube_name])

    def cube_center_from(self, cube: Cube) -> Tuple[float, float]:
        """Same as cube_center(name) but takes the Cube object directly,
        for callers that already have it (avoids a redundant dict lookup)."""
        return (cube.position[0] + cube.size / 2, cube.position[1] + cube.size / 2)

    def unowned_cube_names(self):
        """Names of cubes with no current owner — candidates for a new
        snap."""
        return [name for name, cube in self.cubes.items() if cube.owner is None]

    def cube_owned_by(self, owner_key):
        """The name of the cube currently snapped to `owner_key`
        (a stable track id, or a handedness string as fallback -- see
        `Cube.owner`), or None if that hand holds nothing. Either hand
        can hold at most one cube at a time (sticky grab, one cube per
        hand) — enforced by construction here since snap only ever assigns
        an unowned cube."""
        for name, cube in self.cubes.items():
            if cube.owner == owner_key:
                return name
        return None

    def snap_cube(self, cube_name: str, owner_key) -> None:
        """Claim an unowned cube for `owner_key`. Caller
        (`HandsTriggeredActions.py`) is responsible for the proximity/
        arbitration check — this just performs the assignment.

        ⚠ `owner_key` is whatever `_owner_key()` returned: a stable track id, or
        a handedness string as the fallback. Do not assume a hand name."""
        self.cubes[cube_name].owner = owner_key

    def release_cube(self, cube_name: str) -> None:
        """Clear ownership; the cube stays exactly where it is (frozen in
        place), matching the sticky-grab release semantics `PART_ONE.md`
        §2 already specified for pinch. Orientation freezes too (not
        reset) -- only the grab baseline is cleared, so a future re-grab
        captures a fresh one instead of reusing a stale pair."""
        cube = self.cubes[cube_name]
        cube.owner = None
        cube.grab_hand_orientation = None
        cube.grab_cube_orientation = None
        cube.grab_landmark_weights = None
        cube.grab_residual_offset = None

    def _draw_object_3d(self, obj: Cube) -> None:
        """Rotates `obj.mesh`'s local vertices by the object's orientation
        quaternion, perspective-projects them around the object's screen
        center using a fixed virtual camera distance (see
        CUBE_PERSPECTIVE_DISTANCE_RATIO's comment for why -- a naive
        per-vertex scale relative to the object's own half-size broke down
        for cube corners and made the cube visibly morph), backface-culls
        (a face is drawn only if its rotated normal points toward the
        viewer, negative Z per the established projection convention), and
        paints the remaining faces farthest-to-nearest (painter's
        algorithm) so nearer faces correctly cover farther ones. Edges are
        highlighted when the object is snapped, same visual role the old
        flat-rect border played.

        Entirely generic over `obj.mesh` -- no cube-specific logic here at
        all (see Mesh/MeshFace's docstrings); this is what makes swapping
        in a real imported 3D object later a matter of building a
        different Mesh, not touching this method."""
        cx, cy = self.cube_center_from(obj)
        half = obj.size / 2.0
        camera_distance = obj.size * CUBE_PERSPECTIVE_DISTANCE_RATIO

        projected = []  # (screen_xy, rotated_z) per local vertex, in obj.mesh.vertices order
        for v in obj.mesh.vertices:
            local = (v[0] * half, v[1] * half, v[2] * half)
            rx, ry, rz = _quat_rotate_vector(obj.orientation, local)
            scale = camera_distance / (camera_distance + rz)
            projected.append(((cx + rx * scale, cy + ry * scale), rz))

        visible_faces = []
        for face in obj.mesh.faces:
            rn = _quat_rotate_vector(obj.orientation, face.normal)
            if rn[2] >= 0:
                continue  # facing away from the viewer -- culled
            avg_z = sum(projected[i][1] for i in face.vertex_indices) / len(face.vertex_indices)
            pts = [projected[i][0] for i in face.vertex_indices]
            visible_faces.append((avg_z, face.color, pts))

        visible_faces.sort(key=lambda f: f[0], reverse=True)  # farthest (largest z) first, nearest last/on top

        edge_color = SNAP_BORDER_COLOR if obj.owner is not None else CUBE_EDGE_COLOR
        edge_width = SNAP_BORDER_WIDTH if obj.owner is not None else 1
        for _avg_z, color, pts in visible_faces:
            int_pts = [(int(x), int(y)) for x, y in pts]
            pygame.draw.polygon(self.screen, color, int_pts)
            pygame.draw.polygon(self.screen, edge_color, int_pts, edge_width)

    def pump_and_draw(self) -> None:
        """Process window events and redraw both cubes. Called once per
        received "hands" packet (~30fps from the server), after both cubes'
        positions have been updated for the frame — not once per hand, so
        the event pump and frame clock only run once per packet."""
        if self.closed:
            return

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.closed = True

        if self.closed:
            pygame.quit()
            return

        self.screen.fill((30, 30, 30))
        for cube in self.cubes.values():
            self._draw_object_3d(cube)
        pygame.display.flip()
        self.clock.tick(60)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            pygame.quit()
