"""`HandState` -- the CLIENT-SIDE SUBSET of the perception contract (queue D1).

Implements `PERCEPTION_LAYER_SPEC.md` §2's `HandState.quality` block, restricted
to the fields that can be produced on the client from the EXISTING wire data.
§2.1 is the single schema of record; §2.2 is the owner decision that scopes this
first implementation. Read both before adding a field here.

WHAT THIS IS FOR -- and it is one measured number, not a design preference:
a hand that is not detected arrives as 21 (0, 0) placeholder points, and
`HandsTriggeredActions` releases the held cube on the FIRST such frame. Queue D0
(`analysis/d0_dropout_census.py`) measured what that costs: **98 spurious cube
releases over 40,307 held frames**, one per ~24 s of holding, median gap 89 ms.
This module is the state machine those 98 drops will be fixed through.

    TRACKING        a fresh detection this frame
    BRIDGING        no detection, but still inside the coast window
    SUSTAINED_LOST  the coast window is exhausted; the track is gone

⚠⚠ D1 SHIPS WITH `BRIDGE_WINDOW_MS = 0.0`, AND THAT IS DELIBERATE. With a zero
window `BRIDGING` is unreachable, so every consumer sees exactly the two states
it saw before this module existed and **production behaviour is identical**. D1
lands the contract; **queue D2 raises the window and adds the hold-and-decay** --
that is the change that removes the drops, and it is the change that has to be
measured. Anyone who "helpfully" raises the constant here has shipped D2 without
D2's A/B. `analysis/verify_hand_state.py` §2 fails if the default stops being 0.

⚠ MILLISECONDS, NOT FRAMES -- and this pipeline is the reason. Measured frame
rate is 14-24 fps and ENVIRONMENT-DEPENDENT (spec §0.7), so the document that
prompted Phase D assumes 30-60 fps and its 150 ms is 2-3 frames here, not 5-9.
The coast window is a real elapsed duration, which is exactly the case N1 says
belongs in ms; the frame COUNT is reported alongside because the contract names
it, but nothing decides on it. (Contrast `palm_geometry`'s exit dwell, which
stays in frames because a consecutive-confirmation debounce is not a duration.)

`now_ms` is INJECTED, never read here: this module must stay deterministic and
side-effect free for the port and for golden vectors. Production passes
`time.perf_counter() * 1000.0`, the same clock DR-1's tracker already gets.

FIELD MAPPING to the contract (the spec is language-neutral / camelCase; this is
Python, so the names are snake_case and the identities are what must match):

    tracking_state            -> quality.trackingState
    frames_since_measurement  -> quality.framesSinceMeasurement
    ms_since_measurement      -> derived; the quantity D2 actually thresholds
    orientation_valid         -> quality.orientationValid
    reacquired_after_ms       -> derived; queue D3 (resync blend) needs the gap
                                 length AFTER the counter has been reset, and it
                                 cannot recover it otherwise

⛔ NOT here, on purpose: `occlusionLevel` and `motionBlur` (nothing on the client
measures them -- a fabricated field is worse than an absent one), and every
`palm.*` metric field. Those need the full v2 wire migration, which is a separate
decision paired with 4.1/M9. **Until then this struct is not serialised.**

PORT CONTRACT: stdlib only, no numpy, no side effects, deterministic -- the same
contract as `palm_geometry.py` / `hand_blocks.py` / `hand_identity.py`. Golden
vectors before the port exists (U3).
"""

# The three values of `quality.trackingState` (spec §2, added 2026-08-21).
TRACKING = "TRACKING"
BRIDGING = "BRIDGING"
SUSTAINED_LOST = "SUSTAINED_LOST"

# ⭐⭐ ROTATION SMOOTHING -- OWNER-SETTLED LIVE ON 2026-08-24 AT **20 ms**.
#
# ⚠⚠ IT LIVES HERE BECAUSE IT IS SHARED, AND N6 IS EXPLICIT: a module both tools
# need is IMPORTED, never copied. `LiveSnapDebug.py` cannot import
# `HandsTriggeredActions` (that module opens a pygame window at import time), so a
# constant defined in production would have had to be duplicated in the debug tool
# -- and a duplicated TUNING constant is precisely how the two drift. `hand_state`
# is already imported by both, and already hosts `BRIDGE_WINDOW_MS` for the same
# reason.
#
# The blend is `factor = 1 - exp(-dt / tau)`, so the cube's settling time is `tau`
# in real milliseconds whatever the frame rate. ⛔ It REPLACES a fixed per-frame
# 0.35, whose settling was 2.32 FRAMES and therefore moved with the camera:
# measured 111 ms at 48.0 ms/frame and 149 ms at 64.0 ms/frame, i.e. 34% laggier
# in a darker room. Full measurements and the tuning history are in
# `HandsTriggeredActions.ROTATION_SLERP_TAU_MS`'s comment.
ROTATION_SLERP_TAU_MS = 20.0

# ⚠ A HITCH MUST NOT BECOME A POP: dt is clamped before the exponential, or a cube
# teleports onto the hand on the first frame after a dropout -- undoing D3's
# resync blend, a fix the owner has already accepted.
ROTATION_SLERP_MAX_DT_MS = 200.0

# ⭐ D2, 2026-08-21: 150 ms, chosen from `analysis/d2_bridge_ab.py`, which
# classifies every held-cube dropout rather than counting the ones removed.
#
#   * it covers the MEASURED median true-dropout gap of 128 ms -- 2-3 frames at
#     this pipeline's 14-24 fps, NOT the 5-9 the source document's 30-60 fps
#     assumption implies. The constant is derived here, never copied;
#   * of 83 true dropouts it saves 39 and costs 19 resume pops. Going to 300 ms
#     buys 9 more saves for 2 more pops and barely moves the ratio (0.49 -> 0.44)
#     while TRIPLING the worst added hang;
#   * ⚠ and the hang is the real ceiling, not the ratio. A window is a cube
#     visibly hanging in the air before it drops. At 150 ms that is under the
#     threshold of a felt game rule; at 500-1000 ms it becomes one -- which is
#     queue D4 / M10.7, DEFERRED by the owner with an explicit instruction not to
#     re-propose it as a side effect of another item. **Do not raise this
#     constant into D4's territory without D4's decision.**
#
# ⚠ Raise it in step with `LiveSnapDebug.py`, which imports this same module --
# it does, automatically, and that is the point of the shared constant.
BRIDGE_WINDOW_MS = 150.0


class HandStateTracker:
    """Per-hand tracking state. One instance per tracked hand, like
    `PalmFacingTracker`; `update()` once per received frame per hand.

    Stateful and read by attribute, matching the other per-hand trackers in
    `Resources/`. `update()` also returns the new `tracking_state` so the common
    call reads as one line.
    """

    def __init__(self, bridge_window_ms=BRIDGE_WINDOW_MS):
        self.bridge_window_ms = bridge_window_ms
        self.reset()

    def reset(self):
        """Back to never-having-seen-this-hand. Called on a hard track end, the
        same places `PalmFacingTracker.reset()` is called."""
        self.tracking_state = SUSTAINED_LOST
        self.frames_since_measurement = 0
        self.ms_since_measurement = None   # None = no measurement has EVER landed
        self.orientation_valid = False
        self.reacquired_after_ms = 0.0
        self._last_measurement_ms = None

    def update(self, detected, now_ms):
        """Advance one frame. `detected` is the caller's existing detection test
        (production: `_is_detected`, i.e. the placeholder-landmark check); this
        module deliberately does NOT reimplement it, so there is one definition
        of "detected" on the client."""
        if detected:
            gap = self._elapsed(now_ms)
            # A gap only counts as a reacquisition if we were actually coasting;
            # a continuous track reports 0.0 every frame.
            self.reacquired_after_ms = gap if self.tracking_state != TRACKING and gap is not None else 0.0
            self.tracking_state = TRACKING
            self.frames_since_measurement = 0
            self.ms_since_measurement = 0.0
            self._last_measurement_ms = now_ms
            return self.tracking_state

        elapsed = self._elapsed(now_ms)
        self.frames_since_measurement += 1
        self.ms_since_measurement = elapsed
        self.reacquired_after_ms = 0.0
        # ⚠ A stale `True` must not survive a dropout: with no measurement there
        # is no orientation to call valid, and a consumer that branches on this
        # would coast on a bit measured before the hand vanished.
        self.orientation_valid = False
        if self.bridge_window_ms > 0.0 and elapsed is not None and elapsed <= self.bridge_window_ms:
            self.tracking_state = BRIDGING
        else:
            self.tracking_state = SUSTAINED_LOST
        return self.tracking_state

    def set_orientation_valid(self, valid):
        """Land DR-2's `orientation_valid` on THIS frame's quality block.

        Separate from `update()` because of ordering, not taste: tracking state
        must be known before the per-hand pass runs, and DR-2's validity bit is
        produced inside that pass. `HandsTriggeredActions` has computed this bit
        since 2.2 shipped and discarded it, with a comment naming this contract
        as where it belongs; this is that landing. Ignored unless TRACKING."""
        if self.tracking_state == TRACKING:
            self.orientation_valid = bool(valid)

    @property
    def holds_track(self):
        """True while a consumer should still consider this hand present --
        i.e. TRACKING or BRIDGING. ⭐ THIS IS THE RELEASE TEST: a cube is
        released when this goes False, never on the raw detection bit."""
        return self.tracking_state != SUSTAINED_LOST

    def _elapsed(self, now_ms):
        """Milliseconds since the last accepted measurement, or None if none has
        ever landed (which reads as 'infinitely stale' at every call site).
        Clamped at 0: a clock that steps backwards must not manufacture a
        negative gap that looks like a fresh measurement."""
        if self._last_measurement_ms is None:
            return None
        return max(0.0, now_ms - self._last_measurement_ms)
