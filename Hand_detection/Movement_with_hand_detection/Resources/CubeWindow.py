import pygame
from typing import Tuple

# The vision server sends the left-index-fingertip position as mirrored
# webcam-frame pixel coordinates (see VisionPipeline.py's remap_keypoints call,
# invert_x=True). No explicit capture resolution is set there, so the webcam's
# default applies (commonly 640x480). Match that here 1:1 (no rescaling) so the
# cube's range of motion roughly fills the window; nudge these constants if the
# cube doesn't reach the edges on this PC's actual camera resolution.
DEFAULT_WINDOW_SIZE: Tuple[int, int] = (640, 480)
DEFAULT_CUBE_SIZE = 40


class CubeWindow:
    """A local window with a single square ('cube') whose position is driven
    live by an external position signal — the Part Zero replacement for
    CursorController's OS-cursor move. See Claude/PART_ZERO.md."""

    def __init__(self, window_size: Tuple[int, int] = DEFAULT_WINDOW_SIZE, cube_size: int = DEFAULT_CUBE_SIZE):
        pygame.init()
        self.window_size = window_size
        self.cube_size = cube_size
        self.screen = pygame.display.set_mode(window_size)
        pygame.display.set_caption("Part Zero - cube follows left index fingertip")
        self.clock = pygame.time.Clock()
        self.cube_position: Tuple[float, float] = (
            (window_size[0] - cube_size) / 2,
            (window_size[1] - cube_size) / 2,
        )
        self.closed = False

    def set_target_position(self, position: Tuple[float, float]) -> None:
        """Clamp and store the next cube position. Mirrors
        CursorController.set_target_position_async's clamping, just against
        the window bounds instead of the screen bounds."""
        x, y = position
        clamped_x = max(0.0, min(x, self.window_size[0] - self.cube_size))
        clamped_y = max(0.0, min(y, self.window_size[1] - self.cube_size))
        self.cube_position = (clamped_x, clamped_y)

    def pump_and_draw(self) -> None:
        """Process window events and redraw. Called once per received hands
        packet (~30fps from the server), mirroring how
        update_cursor_position_in_ui used to be called once per packet."""
        if self.closed:
            return

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.closed = True

        if self.closed:
            pygame.quit()
            return

        self.screen.fill((30, 30, 30))
        cube_rect = pygame.Rect(int(self.cube_position[0]), int(self.cube_position[1]), self.cube_size, self.cube_size)
        pygame.draw.rect(self.screen, (0, 200, 255), cube_rect)
        pygame.display.flip()
        self.clock.tick(60)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            pygame.quit()
