"""What the input system IS -- the explicit file list, and the boundary it keeps.

⭐⭐ THIS FILE EXISTS BECAUSE THE ESTIMATOR MODULES WERE DELIBERATELY NOT MOVED.
`Resources/` holds two different things side by side: the portable estimator layer
(this list) and the game (CubeWindow, HandsTriggeredActions, Client). Moving the
first into `handinput/core/` was considered and rejected -- ~15 harnesses import
those modules BARE off `sys.path`, and dozens of paths in `Claude/*.md` name their
current location, so a move would break working code and the project's own memory
to gain nothing measurable today.

⭐ So the boundary is enforced as a PROPERTY rather than a folder, which is
stronger anyway: `analysis/verify_handinput.py` asserts that every module below,
plus `handinput` itself, imports nothing but the standard library and each other.
A future violation fails a suite; it does not merely look untidy.

⚠ THE CLOSURE IS REAL AND WAS CHECKED, NOT ASSUMED (2026-08-25): the only
non-local import anywhere in this list is `math`. `hand_state`, `hand_tracks` and
`owner_remap` import nothing at all.

⚠ AMENDED 2026-08-28: `camera_mount` joined the list and brings `os` with it, for
ONE line -- an optional `CAMERA_MOUNT` environment override read once at import.
A port replaces that line with its own config read; nothing else in the package
touches `os`. The claim above otherwise stands.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_HERE)                       # Movement_with_hand_detection
_SERVER = os.path.join(os.path.dirname(BASE),
                       "Python_Server_MediaPipe_vision_pipeline", "Resources")

# --- the portable core, in dependency order ---------------------------------
# ⚠ ONLY the LIVE path. `block_predictor`, `confirmation_gate`, `frame_gate`,
# `hand_skeleton`, `hand_anatomy`, `hand_model`, `features`, `classifier` and
# `palm_anchor` are parked or archived research (Phase B, the archived pinch
# work) and are NOT part of the input system -- shipping them would be shipping
# code no build runs.
MODULES = (
    # ⭐⭐ WHERE THE CAMERA IS RELATIVE TO THE USER'S EYES (2026-08-28). It is FIRST
    # because `palm_geometry` derives its chirality bit from it, and it is IN the
    # package rather than beside it because the port is the entire reason it
    # exists: a head-worn camera on vision glasses shares the user's viewpoint and
    # needs none of the corrections a facing webcam needs. An input system that
    # could not say which way the camera points would push that decision onto
    # every host that embeds it.
    ("camera_mount", os.path.join(BASE, "Resources", "camera_mount.py")),
    ("palm_geometry", os.path.join(BASE, "Resources", "palm_geometry.py")),
    ("palm_depth", os.path.join(BASE, "Resources", "palm_depth.py")),
    ("hand_blocks", os.path.join(BASE, "Resources", "hand_blocks.py")),
    ("planar_pnp", os.path.join(BASE, "Resources", "planar_pnp.py")),
    ("palm_rotation", os.path.join(BASE, "Resources", "palm_rotation.py")),
    ("hand_state", os.path.join(BASE, "Resources", "hand_state.py")),
    ("hand_tracks", os.path.join(BASE, "Resources", "hand_tracks.py")),
    ("owner_remap", os.path.join(BASE, "Resources", "owner_remap.py")),
    # ⭐ DR-1 lives on the SERVER side and is imported by both tools via sys.path
    # (N6). Track identity is input, not game logic, so it belongs in the package.
    ("hand_identity", os.path.join(_SERVER, "hand_identity.py")),
)

# --- what the boundary forbids ----------------------------------------------
# ⛔ An import of any of these from inside the package or the modules above means
# the input system has grown a dependency on THIS game or on a heavy runtime, and
# is no longer droppable into another one.
FORBIDDEN_IMPORTS = (
    "CubeWindow", "HandsTriggeredActions", "Client", "PythonApp_Main",
    "LiveSnapDebug", "CursorController", "Launcher_for_Server_and_Client",
    "pygame", "cv2", "mediapipe", "numpy", "scipy",
)

# Standard-library modules the core is allowed to use. ⚠ Kept SHORT on purpose:
# every entry is something a JS/Swift/Kotlin port has to find an equivalent for.
ALLOWED_STDLIB = (
    "math", "json", "os", "sys", "copy", "time", "dataclasses", "typing",
    "collections", "itertools", "argparse", "shutil",
)


def module_paths():
    return [p for _, p in MODULES]


def missing():
    """Any manifest entry that is not on disk -- a rename would otherwise turn
    the boundary test into a test of nothing."""
    return [p for p in module_paths() if not os.path.isfile(p)]
