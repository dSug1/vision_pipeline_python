import sys
import os
from .CursorController import CursorController

# Instantiate the controller (consider singleton or shared instance if needed)
controller = CursorController()

def left_index_tip(x: float, y: float) -> None:
    position = (x, y)  # Vector2-like tuple
    controller.set_target_position_async(position)
    controller.update_cursor_position_in_ui()

