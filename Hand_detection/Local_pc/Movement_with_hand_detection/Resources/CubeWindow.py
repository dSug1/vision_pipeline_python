import pygame
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

# Real 3D cube rendering (2026-08-01, direct request — replaces the earlier
# flat pygame.Rect + orientation-gizmo placeholder now that rotation is
# confirmed working end-to-end, see GESTURE_PIPELINE_SPEC.md §13.7). Each
# cube's orientation quaternion rotates 8 local vertices, perspective-
# projects them, and 6 faces (colored in 3 opposite-pair color families,
# one darker than the other per pair) are backface-culled and painter's-
# algorithm sorted (farthest drawn first, nearest last/on top).
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
# camera at a FIXED distance (CUBE_PERSPECTIVE_DISTANCE_RATIO * cube.size,
# comfortably larger than the cube's own half-diagonal) using the standard
# pinhole-camera divide `scale = camera_distance / (camera_distance + rz)`.
# This is a real, physically-correct perspective transform of a rigid
# body -- it cannot morph a cube, only foreshorten it correctly, and the
# denominator is verified (numerically swept across full rotations on 7
# different axes, both cube sizes) to never drop below ~0.71x
# camera_distance, nowhere near the zero-crossing that caused the bug.
CUBE_PERSPECTIVE_DISTANCE_RATIO = 3.0  # virtual camera distance = cube.size * this

CUBE_VERTICES: Tuple[Tuple[float, float, float], ...] = (
    (-1.0, -1.0, -1.0),  # 0
    (1.0, -1.0, -1.0),   # 1
    (1.0, 1.0, -1.0),    # 2
    (-1.0, 1.0, -1.0),   # 3
    (-1.0, -1.0, 1.0),   # 4
    (1.0, -1.0, 1.0),    # 5
    (1.0, 1.0, 1.0),     # 6
    (-1.0, 1.0, 1.0),    # 7
)

# Each face: outward local normal (used for backface culling after rotation)
# and its 4 vertex indices (winding doesn't matter, only used for a filled
# polygon + outline, not lit/shaded).
CUBE_FACES: Tuple[Dict, ...] = (
    {"key": "+x", "normal": (1.0, 0.0, 0.0), "verts": (1, 2, 6, 5)},
    {"key": "-x", "normal": (-1.0, 0.0, 0.0), "verts": (0, 3, 7, 4)},
    {"key": "+y", "normal": (0.0, 1.0, 0.0), "verts": (3, 2, 6, 7)},
    {"key": "-y", "normal": (0.0, -1.0, 0.0), "verts": (0, 1, 5, 4)},
    {"key": "+z", "normal": (0.0, 0.0, 1.0), "verts": (4, 5, 6, 7)},
    {"key": "-z", "normal": (0.0, 0.0, -1.0), "verts": (0, 1, 2, 3)},
)


def _darken(color: Tuple[int, int, int], factor: float = 0.45) -> Tuple[int, int, int]:
    """The opposite face of each color pair is a darker shade of the same
    color, computed rather than hand-picked, so the pairing is guaranteed
    consistent (direct request 2026-08-01)."""
    return tuple(max(0, int(c * factor)) for c in color)


def _face_colors(color_x: Tuple[int, int, int], color_y: Tuple[int, int, int], color_z: Tuple[int, int, int]) -> Dict[str, Tuple[int, int, int]]:
    """Assigns one color family per local axis (three opposite face pairs),
    the lighter shade on the + side, darker on the - side. Which physical
    axis gets which color is arbitrary -- only the pairing (same color
    family on opposite faces, one darker) was the actual request."""
    return {
        "+x": color_x, "-x": _darken(color_x),
        "+y": color_y, "-y": _darken(color_y),
        "+z": color_z, "-z": _darken(color_z),
    }


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
    """One on-screen 3D cube, snappable to either hand. See
    Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13 for the current
    gesture design (proximity snap, open-palm rotate, closed-fist release)
    that grew out of Part One's original grab/release/translate/depth/
    rotate matrix (`PART_ONE.md` §3) after pinch was archived 2026-08-01.
    `owner` is None (idle) or a handedness string ("Left"/"Right") —
    either hand can snap either cube, no fixed pairing. `face_colors` maps
    each of the 6 CUBE_FACES keys ("+x".."-z") to an RGB color (2026-08-01,
    direct request: one color family per opposite face pair, one side
    darker than the other -- see _face_colors)."""
    face_colors: Dict[str, Tuple[int, int, int]]
    size: int
    position: Tuple[float, float] = (0.0, 0.0)
    owner: Optional[str] = None
    # Rotation-while-snapped state (§13.7) — orientation is a quaternion
    # (w,x,y,z), relative-to-grab baseline pair captured at the instant of
    # grab so the cube keeps its OWN orientation at that moment rather than
    # popping to match the hand's (both None while unowned). See
    # HandsTriggeredActions.py's on_hands_frame docstring for the full
    # mechanism -- kept in sync with LiveSnapDebug.py's identical Cube
    # fields, live-verified there first.
    orientation: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    grab_hand_orientation: Optional[Tuple[float, float, float, float]] = None
    grab_cube_orientation: Optional[Tuple[float, float, float, float]] = None


class CubeWindow:
    """A local window with two 3D cubes, snappable to either tracked hand.
    Part One's extension (Hand_detection/Claude/PART_ONE.md) of Part Zero's
    single-cube CubeWindow (Hand_detection/Claude/PART_ZERO.md), now driven
    by the proximity-snap/open-palm-rotate/closed-fist-release gesture set
    (`GESTURE_PIPELINE_SPEC.md` §13) rather than the archived pinch design.
    This class only holds/renders cube state and exposes ownership
    primitives — snap-radius decisions and hand-pose gating live in
    `HandsTriggeredActions.py`, which is the per-frame gesture logic.

    Cube identifiers are "large" and "small" (renamed 2026-08-01 from the
    old "blue"/"red" — those names stopped describing anything once each
    cube got three face colors and different sizes; "large"/"small" is
    what actually distinguishes them now, per direct request: the large
    cube's every dimension is 2x the small cube's)."""

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
                face_colors=_face_colors(FACE_COLOR_YELLOW, FACE_COLOR_VIOLET, FACE_COLOR_TURQUOISE),
                size=large_size,
                position=self._centered_position(large_size),
            ),
            "small": Cube(
                face_colors=_face_colors(FACE_COLOR_GREEN, FACE_COLOR_RED, FACE_COLOR_BLUE),
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
        clamped_x = max(0.0, min(x, self.window_size[0] - cube.size))
        clamped_y = max(0.0, min(y, self.window_size[1] - cube.size))
        cube.position = (clamped_x, clamped_y)

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

    def cube_owned_by(self, handedness: str):
        """The name of the cube currently snapped to `handedness`
        ("Left"/"Right"), or None if that hand holds nothing. Either hand
        can hold at most one cube at a time (sticky grab, one cube per
        hand) — enforced by construction here since snap only ever assigns
        an unowned cube."""
        for name, cube in self.cubes.items():
            if cube.owner == handedness:
                return name
        return None

    def snap_cube(self, cube_name: str, handedness: str) -> None:
        """Claim an unowned cube for `handedness`. Caller (`HandsTriggeredActions.py`)
        is responsible for the proximity/arbitration check — this just
        performs the assignment."""
        self.cubes[cube_name].owner = handedness

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

    def _draw_cube_3d(self, cube: Cube) -> None:
        """Rotates the 8 local vertices by the cube's orientation
        quaternion, perspective-projects them around the cube's screen
        center using a fixed virtual camera distance (see
        CUBE_PERSPECTIVE_DISTANCE_RATIO's comment for why -- a naive
        per-vertex scale relative to the cube's own half-size broke down
        for cube corners and made the cube visibly morph), backface-culls
        (a face is drawn only if its rotated normal points toward the
        viewer, negative Z per the established projection convention), and
        paints the remaining faces farthest-to-nearest (painter's
        algorithm) so nearer faces correctly cover farther ones. Edges are
        highlighted when the cube is snapped, same visual role the old
        flat-rect border played."""
        cx, cy = self.cube_center_from(cube)
        half = cube.size / 2.0
        camera_distance = cube.size * CUBE_PERSPECTIVE_DISTANCE_RATIO

        projected = []  # (screen_xy, rotated_z) per local vertex, in CUBE_VERTICES order
        for v in CUBE_VERTICES:
            local = (v[0] * half, v[1] * half, v[2] * half)
            rx, ry, rz = _quat_rotate_vector(cube.orientation, local)
            scale = camera_distance / (camera_distance + rz)
            projected.append(((cx + rx * scale, cy + ry * scale), rz))

        visible_faces = []
        for face in CUBE_FACES:
            rn = _quat_rotate_vector(cube.orientation, face["normal"])
            if rn[2] >= 0:
                continue  # facing away from the viewer -- culled
            verts = face["verts"]
            avg_z = sum(projected[i][1] for i in verts) / len(verts)
            pts = [projected[i][0] for i in verts]
            visible_faces.append((avg_z, face["key"], pts))

        visible_faces.sort(key=lambda f: f[0], reverse=True)  # farthest (largest z) first, nearest last/on top

        edge_color = SNAP_BORDER_COLOR if cube.owner is not None else CUBE_EDGE_COLOR
        edge_width = SNAP_BORDER_WIDTH if cube.owner is not None else 1
        for _avg_z, key, pts in visible_faces:
            int_pts = [(int(x), int(y)) for x, y in pts]
            pygame.draw.polygon(self.screen, cube.face_colors[key], int_pts)
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
            self._draw_cube_3d(cube)
        pygame.display.flip()
        self.clock.tick(60)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            pygame.quit()
