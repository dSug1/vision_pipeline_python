# CursorController.py

# Initial screen dimensions (can be updated via callback)
_screenWidth = 1920.0
_screenHeight = 1080.0
_pointerSize = (20.0, 20.0)  # width, height

CursorTargetPosition = (0.0, 0.0)

def SetCursorTargetPositionAsync(position: tuple) -> None:
    x, y = position

    clampedX = max(0.0, min(x, _screenWidth - _pointerSize[0]))
    clampedY = max(0.0, min(y, _screenHeight - _pointerSize[1]))

    global CursorTargetPosition
    CursorTargetPosition = (clampedX, clampedY)

    print(f"[CursorController] Cursor target set to: X={clampedX}, Y={clampedY}")

# Simulated DisplayInfo structure
class DisplayInfo:
    def __init__(self, width: float, height: float, density: float = 1.0):
        self.Width = width
        self.Height = height
        self.Density = density  # Optional, for DIP conversion

def UpdateScreenDimensions(info: DisplayInfo) -> None:
    global _screenWidth, _screenHeight
    # If you want to convert to DIPs, uncomment the division
    _screenWidth = info.Width  # / info.Density
    _screenHeight = info.Height  # / info.Density

    print(f"[CursorController] Screen dimensions updated: {_screenWidth}x{_screenHeight}")

def OnMainDisplayInfoChanged(sender: object, e: DisplayInfo) -> None:
    UpdateScreenDimensions(e)


def UpdateCursorPositioninUI() -> None:
    print("[Main] Cursor position updated in UI")
    # Trigger UI refresh or animation