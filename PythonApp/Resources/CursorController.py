import ctypes
from typing import Tuple, Optional

class DisplayInfo:
    def __init__(self, width: float, height: float, density: float = 1.0, orientation: Optional[str] = None):
        self.width = width
        self.height = height
        self.density = density  # Optional: for DIP conversion
        self.orientation = orientation  # e.g., "portrait", "landscape"

class CursorController:
    def __init__(self):
        self.screen_width = 1920.0
        self.screen_height = 1080.0
        self.pointer_size = (20.0, 20.0)  # width, height
        self.cursor_target_position = (0.0, 0.0)
        self.last_orientation = None

    def set_target_position_async(self, position: Tuple[float, float]) -> None:
        x, y = position
        clamped_x = max(0.0, min(x, self.screen_width - self.pointer_size[0]))
        clamped_y = max(0.0, min(y, self.screen_height - self.pointer_size[1]))
        self.cursor_target_position = (clamped_x, clamped_y)
        print(f"[CursorController] Cursor target set to: X={clamped_x}, Y={clamped_y}")

    def update_cursor_position_in_ui(self) -> None:
        x, y = self.cursor_target_position
        try:
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
            print(f"[Main] Cursor moved to UI position: X={x}, Y={y}")
        except Exception as e:
            print(f"[Main] Failed to move cursor: {e}")

    def update_screen_dimensions(self, info: DisplayInfo, use_dips: bool = False) -> None:
        new_width = info.width / info.density if use_dips else info.width
        new_height = info.height / info.density if use_dips else info.height

        orientation_changed = info.orientation and info.orientation != self.last_orientation
        dimensions_changed = (new_width != self.screen_width) or (new_height != self.screen_height)

        if dimensions_changed or orientation_changed:
            self.screen_width = new_width
            self.screen_height = new_height
            self.last_orientation = info.orientation
            print(f"[CursorController] Screen dimensions updated: {self.screen_width}x{self.screen_height} (Orientation: {info.orientation})")
        else:
            print("[CursorController] DisplayInfo unchanged. No update applied.")

    def on_main_display_info_changed(self, sender: object, info: DisplayInfo) -> None:
        self.update_screen_dimensions(info)


