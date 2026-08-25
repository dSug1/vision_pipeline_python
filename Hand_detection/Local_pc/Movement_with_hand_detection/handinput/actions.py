"""Actions, phases, contexts and callbacks -- the Unity-shaped surface.

⭐ THE SHAPE IS BORROWED ON PURPOSE, because the owner asked for it and because
it is the interface every game programmer already knows: an **action** is a named
thing the player can do; it moves through **phases**; a consumer subscribes to
`started` / `performed` / `canceled` and receives a **context** describing what
happened. Unity's own phase set is Disabled / Waiting / Started / Performed /
Canceled, and those are the five below.

⚠⚠ THE ONE PLACE THIS DEVIATES FROM UNITY, AND IT IS FORCED BY THE SENSOR.
Unity actions are driven by DEVICE EVENTS -- a key goes down, and that is a fact.
A camera supplies a *belief* that can be missing, stale or unreliable, so every
context carries `quality` and every action's liveness is gated on it. ⭐ A hand
that has vanished does not silently hold its last value: its actions are
CANCELED, which is the same instant the game releases a held object
(`hand_state.holds_track`). Consumers therefore get one consistent story.

────────────────────────────────────────────────────────────────────────────────
PHASE SEMANTICS -- pinned here, golden-vectored in `analysis/verify_handinput.py`
────────────────────────────────────────────────────────────────────────────────
BUTTON action (`tracked`, `grab_ready`)
    rising edge   -> `started`, then `performed` (same frame, as Unity does for
                     a simple press)
    while held    -> nothing. A button does not re-fire every frame.
    falling edge  -> `canceled`
VALUE action (`palm_pose`, `palm_facing`, `rotation_delta`)
    first live    -> `started`, then `performed`
    each live     -> `performed` (the value is refreshed every frame it exists)
    goes away     -> `canceled`, and `read_value()` returns None

⭐ WHY VALUE ACTIONS FIRE EVERY FRAME RATHER THAN ON CHANGE. A change test needs
an epsilon per field, and an epsilon is a tuning constant that would live in two
languages and drift. Every-frame is also what a game wants: it is reading a pose,
not waiting for a keypress. The cost is a busier trace, which is a recording
concern and is bounded there, not here.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import quat
from .config import DEFAULT_CONFIG, merged_config
from .contract import (
    HandFrame,
    HandObservation,
    TRACKING,
    hand_state as _hand_state_dict,
)

# --- phases (Unity's five) --------------------------------------------------
DISABLED = "Disabled"
WAITING = "Waiting"
STARTED = "Started"
PERFORMED = "Performed"
CANCELED = "Canceled"


class Event:
    """A multicast callback list with `+=` / `-=`, mimicking a C# event.

    ⚠ Exceptions in a subscriber are NOT swallowed. A consumer that throws
    inside a callback would otherwise take down the frame silently in one tool
    and not the other; letting it raise means it is found on the first run.
    """

    __slots__ = ("_handlers",)

    def __init__(self):
        self._handlers: List[Callable[["ActionContext"], None]] = []

    def __iadd__(self, handler):
        if handler not in self._handlers:
            self._handlers.append(handler)
        return self

    def __isub__(self, handler):
        if handler in self._handlers:
            self._handlers.remove(handler)
        return self

    def __len__(self):
        return len(self._handlers)

    def invoke(self, ctx: "ActionContext") -> None:
        for h in list(self._handlers):
            h(ctx)


@dataclass(frozen=True)
class ActionContext:
    """What a callback is told. Deliberately flat and serialisable.

    `control` is a stable BINDING PATH in Unity's style (`hand/Left/palm`), so a
    consumer can log or route by string without knowing this package's types.
    """

    action: str
    phase: str
    hand: str
    track_id: int
    value: Any
    time_ms: float
    control: str
    quality: Dict[str, Any]

    def read_value(self):
        """Unity spells it `ReadValue<T>()`; the value is already typed here."""
        return self.value

    def as_dict(self) -> Dict[str, Any]:
        """For traces and cross-language conformance. ⚠ Values are normalised to
        lists/scalars -- a tuple and a list are the same thing once serialised,
        and a port must not have to guess which one was meant."""
        return {
            "action": self.action,
            "phase": self.phase,
            "hand": self.hand,
            "trackId": self.track_id,
            "value": _plain(self.value),
            "tCapture": self.time_ms,
            "control": self.control,
            "quality": dict(self.quality),
        }


# --- typed values -----------------------------------------------------------
@dataclass(frozen=True)
class PalmPose:
    """Where the hand is. ⚠ Mixed units, deliberately and visibly: the pipeline
    positions objects in PIXELS (a frame-relative signal is what placing
    something on screen needs, `PART_ONE.md` §1) and measures depth in METRES
    (4.2). Naming the field `position_px` is how that stays impossible to
    misread."""

    position_px: Optional[Tuple[float, float]]
    depth_m: Optional[float]
    depth_valid: bool
    orientation: Optional[Tuple[float, float, float, float]]


@dataclass(frozen=True)
class PalmFacing:
    """The palm/back cue and how much to trust it.

    ⛔ `thumb_outward` is a BOOL, not a signed cosine -- see `contract.py`'s table.
    ⚠ `confirmed` False means U8's provisional window: the cue exists but a
    newly-entered hand's thumb has not cleared the frame edge, so the answer can
    be confidently WRONG. Suppress, do not guess."""

    thumb_outward: bool
    confirmed: bool
    orientation_valid: bool
    edge_on: Optional[float]


def _plain(v):
    if isinstance(v, (PalmPose, PalmFacing)):
        return {k: _plain(getattr(v, k)) for k in v.__dataclass_fields__}
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    return v


# --- actions ----------------------------------------------------------------
class Action:
    """Base: per-hand phase bookkeeping plus the three events.

    ⚠ Phase is PER HAND. One action object serves both slots, exactly as one
    Unity action serves several bindings, and a hand appearing does not disturb
    the other's phase.
    """

    kind = "value"

    def __init__(self, name: str, control_suffix: str = "palm"):
        self.name = name
        self.control_suffix = control_suffix
        self.enabled = True
        self.started = Event()
        self.performed = Event()
        self.canceled = Event()
        self._phase: Dict[str, str] = {}
        self._value: Dict[str, Any] = {}

    # -- consumer-facing polling --------------------------------------------
    def phase(self, hand: str) -> str:
        if not self.enabled:
            return DISABLED
        return self._phase.get(hand, WAITING)

    def read_value(self, hand: str):
        """The latest value, or None once the action has been canceled. ⭐ The
        polling half of the API: Unity offers both, and a render loop usually
        wants to poll rather than cache what a callback handed it."""
        return self._value.get(hand)

    # -- to be provided by each action --------------------------------------
    def evaluate(self, obs: HandObservation, cfg) -> Tuple[bool, Any]:
        """Return `(live, value)` for this hand this frame."""
        raise NotImplementedError

    # -- the shared state machine -------------------------------------------
    def step(self, obs: HandObservation, frame: HandFrame, cfg, sink) -> None:
        if not self.enabled:
            return
        hand = obs.slot
        prev = self._phase.get(hand, WAITING)
        try:
            live, value = self.evaluate(obs, cfg)
        except Exception:                       # an evaluator must never kill the frame
            live, value = False, None
        quality = _quality(obs)

        if live:
            self._value[hand] = value
            if prev in (WAITING, CANCELED):
                self._phase[hand] = STARTED
                self._emit(self.started, STARTED, obs, frame, value, quality, sink)
                self._phase[hand] = PERFORMED
                self._emit(self.performed, PERFORMED, obs, frame, value, quality, sink)
            elif self.kind == "value":
                self._phase[hand] = PERFORMED
                self._emit(self.performed, PERFORMED, obs, frame, value, quality, sink)
            # a BUTTON held down emits nothing -- see the module docstring
        else:
            if prev in (STARTED, PERFORMED):
                # ⚠ The value is cleared BEFORE the callback, so a subscriber that
                # polls `read_value()` from inside `canceled` cannot read a value
                # the action no longer has.
                last = self._value.pop(hand, None)
                self._phase[hand] = CANCELED
                self._emit(self.canceled, CANCELED, obs, frame, last, quality, sink)
            self._phase[hand] = WAITING
            self._value.pop(hand, None)

    def _emit(self, event, phase, obs, frame, value, quality, sink):
        ctx = ActionContext(
            action=self.name, phase=phase, hand=obs.slot, track_id=obs.track_id,
            value=value, time_ms=frame.time_ms,
            control="hand/%s/%s" % (obs.slot, self.control_suffix),
            quality=quality,
        )
        if sink is not None:
            sink(ctx)
        event.invoke(ctx)


def _quality(obs: HandObservation) -> Dict[str, Any]:
    return {
        "trackingState": obs.tracking_state,
        "orientationValid": bool(obs.orientation_valid),
        "depthValid": bool(obs.depth_valid),
        "chiralityConfirmed": bool(obs.chirality_confirmed),
        "framesSinceMeasurement": int(obs.frames_since_measurement),
    }


class TrackedAction(Action):
    """Is this hand there? ⭐ Live while `holds_track`, i.e. TRACKING **or**
    BRIDGING -- so a 150 ms detection gap does NOT cancel it, matching the rule
    the game already releases objects on (`GAME_RULES.md` rule 2). A consumer
    that wants raw detection reads `quality.trackingState`."""

    kind = "button"

    def __init__(self):
        Action.__init__(self, "tracked", "tracked")

    def evaluate(self, obs, cfg):
        return obs.holds_track, True


class PalmPoseAction(Action):
    def __init__(self):
        Action.__init__(self, "palm_pose", "palm")

    def evaluate(self, obs, cfg):
        # ⚠ TRACKING, not holds_track: during a bridge there is no measurement,
        # and publishing the last pose as though it were current is precisely
        # the extrapolation B8 measured losing to "hold the last value". The
        # action stays live (`tracked`), the POSE simply stops updating.
        live = obs.tracking_state == TRACKING and obs.position_px is not None
        return live, PalmPose(obs.position_px, obs.depth_m,
                              bool(obs.depth_valid), obs.orientation)


class PalmFacingAction(Action):
    def __init__(self):
        Action.__init__(self, "palm_facing", "palmFacing")

    def evaluate(self, obs, cfg):
        live = obs.tracking_state == TRACKING
        return live, PalmFacing(bool(obs.thumb_outward),
                                bool(obs.chirality_confirmed),
                                bool(obs.orientation_valid), obs.edge_on)


class GrabReadyAction(Action):
    """⭐⭐ ELIGIBILITY, NOT A GRAB -- the hand-side half of `GAME_RULES.md` rule 3.

    True when this hand *may* take an object if one is in range. It answers
    nothing about WHAT, because "what" needs the scene and this package does not
    have one (see `__init__.py`). The interaction tier, or the game, ANDs this
    with proximity.

    The three conditions are the three the game already applies, in one place:
      * palm/back -- refuse while thumb-outward, unless rule 3's exception is
        ARMED (`snap_allowed`, armed at a thumb-outward release);
      * U8 -- refuse while the chirality is PROVISIONAL. Measured: a back-of-hand
        hand read as palm and took a cube rule 3 forbids;
      * 4.2 DECISION 1 -- refuse while depth is FROZEN rather than measured.
        ⚠ `depth_m is None` means the host supplies no depth at all (pre-4.2
        callers, and any host without a depth estimator) -- that must NOT refuse,
        or the action would be permanently false there.
    """

    kind = "button"

    def __init__(self):
        Action.__init__(self, "grab_ready", "grabReady")

    def evaluate(self, obs, cfg):
        if obs.tracking_state != TRACKING:
            return False, False
        ok = (not obs.thumb_outward) or obs.snap_allowed
        ok = ok and obs.chirality_confirmed
        if cfg["grab_ready"]["require_valid_depth"] and obs.depth_m is not None:
            ok = ok and obs.depth_valid
        return bool(ok), True


class RotationDeltaAction(Action):
    """How far this hand has turned since a reference the CONSUMER froze.

    ⭐ This is the piece a game needs to rotate a held object, expressed without
    any knowledge of the object: call `set_reference(hand)` when you grab,
    `clear_reference(hand)` when you let go, and read a quaternion delta every
    frame in between. On the reference frame itself the delta is identity by
    construction -- the same no-pop guarantee the cube already gets (§14.1).

    ⚠ The reference is cleared automatically when the hand's track is lost.
    Keeping it would measure against a pose belonging to a hand that no longer
    exists -- §16.15's rule ("never fit against a dead track") applied one layer
    up.
    """

    def __init__(self):
        Action.__init__(self, "rotation_delta", "rotation")
        self._reference: Dict[str, Tuple[float, float, float, float]] = {}

    def set_reference(self, hand: str, orientation=None) -> None:
        """Freeze the zero point. With `orientation=None` the next observed
        orientation for that hand is used, so a caller does not have to have the
        quaternion to hand at the moment it grabs."""
        self._reference[hand] = orientation if orientation is not None else "pending"

    def clear_reference(self, hand: str) -> None:
        self._reference.pop(hand, None)

    def has_reference(self, hand: str) -> bool:
        return hand in self._reference

    def evaluate(self, obs, cfg):
        if obs.tracking_state != TRACKING or obs.orientation is None:
            if not obs.holds_track:
                self._reference.pop(obs.slot, None)
            return False, None
        ref = self._reference.get(obs.slot)
        if ref is None:
            return False, None
        if ref == "pending":
            ref = tuple(obs.orientation)
            self._reference[obs.slot] = ref
        return True, quat.delta(tuple(obs.orientation), ref)


# --- the map ----------------------------------------------------------------
class HandInput:
    """The device + its action map. One instance per host.

    ⚠ NOT a singleton and NOT global state: the debug tool runs several
    independent arms, and a module-level instance would let one arm's events
    describe another's hands.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = merged_config(config)
        self.actions: Dict[str, Action] = {}
        for a in (TrackedAction(), PalmPoseAction(), PalmFacingAction(),
                  GrabReadyAction(), RotationDeltaAction()):
            a.enabled = bool(self.config["actions"].get(a.name, True))
            self.actions[a.name] = a
        self.trace_sink: Optional[Callable[[ActionContext], None]] = None
        self.frame_count = 0
        self.event_count = 0
        self._states: Dict[str, Dict] = {}
        self._last_time_ms: Optional[float] = None

    # -- the pump ------------------------------------------------------------
    def update(self, frame: HandFrame) -> None:
        """Advance one frame and dispatch. ⚠ THE HOST CALLS THIS; this module
        never runs a loop, never draws, never sleeps and never reads a clock."""
        self._last_time_ms = frame.time_ms
        self.frame_count += 1
        sink = self._sink
        for obs in frame.hands:
            self._states[obs.slot] = _hand_state_dict(
                obs, frame.time_ms,
                include_landmarks=self.config["include_landmarks"])
            for action in self.actions.values():
                action.step(obs, frame, self.config, sink)

    def _sink(self, ctx: ActionContext) -> None:
        self.event_count += 1
        if self.trace_sink is not None:
            self.trace_sink(ctx)

    # -- polling -------------------------------------------------------------
    def state(self, hand: str) -> Optional[Dict]:
        """The latest `HandState` v2 dict for one hand."""
        return self._states.get(hand)

    def value(self, action: str, hand: str):
        a = self.actions.get(action)
        return None if a is None else a.read_value(hand)

    def phase(self, action: str, hand: str) -> str:
        a = self.actions.get(action)
        return DISABLED if a is None else a.phase(hand)

    # -- convenience the rotation consumer needs -----------------------------
    def set_rotation_reference(self, hand: str, orientation=None) -> None:
        self.actions["rotation_delta"].set_reference(hand, orientation)

    def clear_rotation_reference(self, hand: str) -> None:
        self.actions["rotation_delta"].clear_reference(hand)

    def summary(self) -> str:
        """One line for a HUD. ⭐ Shows the PHASE per hand, which is what makes
        the action layer visible live rather than only in a trace file."""
        bits = []
        for hand in ("Left", "Right"):
            tr = self.phase("tracked", hand)
            if tr in (WAITING, DISABLED):
                continue
            gr = "RDY" if self.phase("grab_ready", hand) == PERFORMED else "---"
            rot = "ROT" if self.actions["rotation_delta"].has_reference(hand) else "   "
            bits.append("%s:%s %s %s" % (hand[0], tr[:4].upper(), gr, rot))
        return "handinput " + (" | ".join(bits) if bits else "(no hand)")


__all__ = [
    "HandInput", "Action", "ActionContext", "Event",
    "PalmPose", "PalmFacing", "DEFAULT_CONFIG",
    "DISABLED", "WAITING", "STARTED", "PERFORMED", "CANCELED",
]
