import pygame
from dataclasses import dataclass
from typing import Dict, Tuple

# The vision server sends each hand's landmarks as mirrored webcam-frame pixel
# coordinates (see VisionPipeline.py's remap_keypoints call, invert_x=True).
# This default is only a placeholder shown before the server's real
# resolution arrives — VisionPipeline.py reads the webcam's actual frame size
# and sends it once as a "meta" packet (see PythonApp_Main.py's dispatch for
# datatype == "meta"), which calls resize() below to match it.
DEFAULT_WINDOW_SIZE: Tuple[int, int] = (640, 480)
DEFAULT_CUBE_SIZE = 40


@dataclass
class Cube:
    """One on-screen square ('cube') driven by one hand. See
    Hand_detection/Claude/PART_ONE.md for the full gesture matrix this will
    grow into (grab/release, translation, depth-as-scale/color, rotation) —
    step 1 only tracks a target position, unconditionally, the same way Part
    Zero's single cube did."""
    color: Tuple[int, int, int]
    size: int
    position: Tuple[float, float] = (0.0, 0.0)


class CubeWindow:
    """A local window with one 'cube' per tracked hand, each driven live by
    that hand's index-fingertip position. Part One's extension
    (Hand_detection/Claude/PART_ONE.md) of Part Zero's single-cube
    CubeWindow (Hand_detection/Claude/PART_ZERO.md) to two independent
    hands/cubes."""

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
        pygame.display.flip()
        self.clock.tick(60)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            pygame.quit()
