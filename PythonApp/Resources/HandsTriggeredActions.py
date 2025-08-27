from .CursorController import SetCursorTargetPositionAsync, UpdateCursorPositioninUI
import sys
import os


def LeftIndexTip(x: float, y: float) -> None:
    position = (x, y)  # Vector2-like tuple
    SetCursorTargetPositionAsync(position)
    UpdateCursorPositioninUI()
