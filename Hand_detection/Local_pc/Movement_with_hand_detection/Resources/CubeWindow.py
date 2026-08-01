import math
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
DEFAULT_CUBE_SIZE = 40

# Snap/hover highlight (Claude/GESTURE_PIPELINE_SPEC.md §13.3, 2026-08-01):
# a snapped cube gets a bright border so snap/release state is visible live
# without needing a separate troubleshooting technique (the old depth-proxy
# color effect was for exactly this kind of "is it working" visual check on
# translation; this replaces that need directly for snap state).
SNAP_BORDER_COLOR = (255, 255, 255)
SNAP_BORDER_WIDTH = 4

# Rotation-while-snapped orientation gizmo (2026-08-01, ported from the
# confirmed-working LiveSnapDebug.py `_draw_orientation_gizmo`/
# `_project_local_point` — see GESTURE_PIPELINE_SPEC.md §13.7 for the full
# rotation design/history). A 3-axis RGB gizmo (X=red, Y=green, Z=blue-ish)
# rotated by the cube's orientation quaternion, weak-perspective projected
# -- the visual stand-in this cube previously had no way to show
# orientation at all. Colors here are RGB (pygame convention), not BGR
# (cv2, LiveSnapDebug.py's convention) -- values converted accordingly.
GIZMO_AXIS_LENGTH_RATIO = 0.9  # relative to cube.size
GIZMO_PERSPECTIVE_K = 0.6  # cosmetic weak-perspective foreshortening only, tune by feel
GIZMO_AXIS_COLORS = {"x": (255, 0, 0), "y": (0, 255, 0), "z": (0, 160, 255)}
GIZMO_ORIGIN_COLOR = (255, 255, 255)


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
    """One on-screen square ('cube'), snappable to either hand. See
    Hand_detection/Claude/GESTURE_PIPELINE_SPEC.md §13 for the current
    gesture design (proximity snap, open-palm rotate, closed-fist release)
    that grew out of Part One's original grab/release/translate/depth/
    rotate matrix (`PART_ONE.md` §3) after pinch was archived 2026-08-01.
    `owner` is None (idle) or a handedness string ("Left"/"Right") —
    either hand can snap either cube, no fixed pairing."""
    color: Tuple[int, int, int]
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
    """A local window with two 'cubes', snappable to either tracked hand.
    Part One's extension (Hand_detection/Claude/PART_ONE.md) of Part Zero's
    single-cube CubeWindow (Hand_detection/Claude/PART_ZERO.md), now driven
    by the proximity-snap/open-palm-rotate/closed-fist-release gesture set
    (`GESTURE_PIPELINE_SPEC.md` §13) rather than the archived pinch design.
    This class only holds/renders cube state and exposes ownership
    primitives — snap-radius decisions and hand-pose gating live in
    `HandsTriggeredActions.py`, which is the per-frame gesture logic."""

    def __init__(self, window_size: Tuple[int, int] = DEFAULT_WINDOW_SIZE, cube_size: int = DEFAULT_CUBE_SIZE):
        pygame.init()
        self.window_size = window_size
        self.cube_size = cube_size
        self.screen = pygame.display.set_mode(window_size)
        pygame.display.set_caption("Part One - two cubes, one per hand")
        self.clock = pygame.time.Clock()
        self.cubes: Dict[str, Cube] = {
            "blue": Cube(color=(0, 200, 255), size=cube_size, position=self._centered_position()),
            "red": Cube(color=(220, 60, 60), size=cube_size, position=self._centered_position()),
        }
        self.closed = False

    def _centered_position(self) -> Tuple[float, float]:
        return (
            (self.window_size[0] - self.cube_size) / 2,
            (self.window_size[1] - self.cube_size) / 2,
        )

    def resize(self, window_size: Tuple[int, int]) -> None:
        """Re-size the window to the webcam's actual frame resolution, once
        it's known (see the "meta" packet handling in PythonApp_Main.py).
        Re-centers both cubes since their old positions may no longer be
        valid against the new bounds."""
        if window_size == self.window_size:
            return
        self.window_size = window_size
        self.screen = pygame.display.set_mode(window_size)
        for cube in self.cubes.values():
            cube.position = self._centered_position()

    def set_target_position(self, cube_name: str, position: Tuple[float, float]) -> None:
        """Clamp and store the next position for the named cube ("blue" or
        "red"). Mirrors CursorController.set_target_position_async's
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
        cube = self.cubes[cube_name]
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

    def _draw_orientation_gizmo(self, cube: Cube) -> None:
        """3-axis RGB gizmo showing the cube's current orientation
        quaternion — ported from LiveSnapDebug.py's confirmed-working
        `_draw_orientation_gizmo`/`_project_local_point` (§13.7). Always
        drawn (not just while snapped), so a released cube's frozen
        orientation stays visible, matching position's own freeze-in-place
        semantics."""
        cx, cy = self.cube_center_from(cube)
        axis_length = cube.size * GIZMO_AXIS_LENGTH_RATIO

        def project(local_point):
            rx, ry, rz = _quat_rotate_vector(cube.orientation, local_point)
            scale = 1.0 / (1.0 + GIZMO_PERSPECTIVE_K * (rz / axis_length)) if axis_length else 1.0
            return (int(cx + rx * scale), int(cy + ry * scale))

        origin = project((0.0, 0.0, 0.0))
        for axis, color in (
            ((axis_length, 0.0, 0.0), GIZMO_AXIS_COLORS["x"]),
            ((0.0, axis_length, 0.0), GIZMO_AXIS_COLORS["y"]),
            ((0.0, 0.0, axis_length), GIZMO_AXIS_COLORS["z"]),
        ):
            tip = project(axis)
            pygame.draw.line(self.screen, color, origin, tip, 3)
        pygame.draw.circle(self.screen, GIZMO_ORIGIN_COLOR, origin, 4)

    def cube_center_from(self, cube: Cube) -> Tuple[float, float]:
        """Same as cube_center(name) but takes the Cube object directly,
        for callers that already have it (avoids a redundant dict lookup)."""
        return (cube.position[0] + cube.size / 2, cube.position[1] + cube.size / 2)

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
            cube_rect = pygame.Rect(int(cube.position[0]), int(cube.position[1]), cube.size, cube.size)
            pygame.draw.rect(self.screen, cube.color, cube_rect)
            if cube.owner is not None:
                pygame.draw.rect(self.screen, SNAP_BORDER_COLOR, cube_rect, SNAP_BORDER_WIDTH)
            self._draw_orientation_gizmo(cube)
        pygame.display.flip()
        self.clock.tick(60)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            pygame.quit()
