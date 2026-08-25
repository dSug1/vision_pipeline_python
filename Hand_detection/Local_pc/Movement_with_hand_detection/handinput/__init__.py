"""`handinput` -- the hand-tracking INPUT SYSTEM, as a pluggable module.

⭐ WHAT THIS IS. A Unity-Input-System-shaped surface over this project's hand
pipeline: **actions** with **phases** (`started` / `performed` / `canceled`),
**callbacks carrying a context**, a **polling** API alongside them, and a
**language-neutral state contract** (`HandState` v2, `PERCEPTION_LAYER_SPEC.md`
§2). A game -- this one, a Unity game, a browser build, a lens -- consumes those
events and never touches a landmark.

⛔⛔ WHAT THIS IS NOT, AND THE DISTINCTION IS THE WHOLE ARCHITECTURE. Unity splits
**Input System** (devices -> actions -> callbacks, knows nothing about your scene)
from **XR Interaction Toolkit** (grab, hold, arbitration, which does). This package
is the FIRST of those two. It answers *"is this hand tracked, where is it, which
way is it facing, is it eligible to grab?"* -- it never answers *"grab WHAT"*,
because that needs scene knowledge and would weld the module to one game.

  ⭐ Snap proximity, arbitration between hands, sticky grab, owner-follows-track,
    grab-relative translation/rotation/depth and the play volume all stay in
    `Resources/HandsTriggeredActions.py` (production) and `LiveSnapDebug.py`
    (debug) for now. Extracting them into a `handinput.interaction` tier is a
    LATER, separately-decided step; nothing here presumes it, and nothing here
    has to change when it happens. That is why `grab_ready` is an ELIGIBILITY
    action and not a `grab` action.

⚠⚠ TODAY THIS LAYER DERIVES NOTHING -- IT ADAPTS, AND THAT IS DELIBERATE.
Both tools already compute every quantity below in their per-hand pass. This
package receives those values (`sources.live.observe(...)`) rather than
recomputing them from landmarks. ⭐ The reason is this project's most expensive
recurring lesson: **a recomputation is a second implementation that can silently
disagree with the real one**, and four harnesses reported CLEAN on takes the owner
had just watched fail because of exactly that. So the input system reports what
RAN. A future self-sufficient mode (calling the estimators itself, for a host that
has only landmarks) fills the same `HandObservation` struct -- the contract, the
state machine and the event surface do not move.

⭐ THE PORTABLE CORE IS NOT IN THIS FOLDER, AND `manifest.py` SAYS WHERE IT IS.
The estimator modules (`palm_geometry`, `palm_depth`, `palm_rotation`, ...) were
deliberately NOT moved: ~15 harnesses import them bare off `sys.path`, and dozens
of documented paths in `Claude/*.md` name their current location -- moving them
would break working code and the project's own memory to gain nothing measurable.
Instead the boundary is enforced as a PROPERTY, mechanically:

    .venv/Scripts/python.exe analysis/verify_handinput.py

asserts that this package plus every module in `manifest.MODULES` imports nothing
from the game (no `CubeWindow`, no `HandsTriggeredActions`, no pygame/cv2/
mediapipe/numpy). ⭐ And when you actually want the folder, one command writes a
standalone copy with its conformance data:

    .venv/Scripts/python.exe handinput/export_package.py <target-dir>

Usage:

    from handinput import HandInput
    from handinput.sources import live

    hi = HandInput()
    hi.actions["grab_ready"].started += lambda ctx: print("ready", ctx.hand)
    hi.actions["palm_pose"].performed += on_pose

    hi.update(live.frame(time_ms, [live.observe(...), ...], frame_size))

⚠ THE HOST PUMPS; THIS MODULE NEVER DRAWS AND NEVER READS A CLOCK. Every time
value arrives on the frame (N7's rule: a module that samples the clock itself
looks right in production and is meaningless in replay).

Contract version: `contract.SCHEMA`. Package version: `__version__`.
"""

from .contract import (                                   # noqa: F401
    SCHEMA,
    HandFrame,
    HandObservation,
    hand_state,
    TRACKING,
    BRIDGING,
    SUSTAINED_LOST,
)
from .actions import (                                    # noqa: F401
    HandInput,
    ActionContext,
    Event,
    DISABLED,
    WAITING,
    STARTED,
    PERFORMED,
    CANCELED,
    PalmPose,
    PalmFacing,
)

__version__ = "1.0.0"

__all__ = [
    "HandInput", "ActionContext", "Event",
    "HandFrame", "HandObservation", "hand_state",
    "PalmPose", "PalmFacing",
    "SCHEMA", "__version__",
    "DISABLED", "WAITING", "STARTED", "PERFORMED", "CANCELED",
    "TRACKING", "BRIDGING", "SUSTAINED_LOST",
]
