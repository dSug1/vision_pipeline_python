import sys
import os
from .CubeWindow import CubeWindow

# Part Zero (see Claude/PART_ZERO.md): retargeted from moving the OS cursor
# (CursorController, still in CursorController.py but no longer used here) to
# moving a cube in a local window. The signal itself — left-index-fingertip
# (x, y) — and the point it enters at (left_index_tip) are unchanged; only
# what happens with the signal changed.
cube_window = CubeWindow()

def left_index_tip(x: float, y: float) -> None:
    position = (x, y)  # Vector2-like tuple
    cube_window.set_target_position(position)
    cube_window.pump_and_draw()

