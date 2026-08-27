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

# ⭐⭐ THE STEADY DAMPER (owner, 2026-08-27: *"there is a bit of jitter of the
# cube"*). Measured on `2026-08-27_195429_solid` while a cube was held:
#
#     grip point moves   3.50 px/frame median      <- the input
#     cube POSITION      3.39 px/frame median      <- tracks it to 0.1 px
#     cube ORIENTATION   4.30 deg/frame median     <- THE JITTER
#
# ⛔ So position was never the problem: the cube follows the grip point to within a
# tenth of a pixel, and damping it would only lag translation. The shimmer is
# ORIENTATION, 4.3 deg every frame at 15 fps.
#
# ⛔⛔ WHAT THIS IS *NOT*, AND THE HISTORY IS WORTH ONE PARAGRAPH BECAUSE EACH
# STEP WAS BUILT, MEASURED AND REJECTED. A fixed longer tau was rejected by `L1`
# (it lags real motion as much as it damps jitter). An ADAPTIVE tau with a
# fast-attack speed envelope was built next and rejected by the owner -- *"damping
# is not stillness"*: even at 4500 ms the blend factor is 0.015, so the cube still
# creeps 1.5% of the gap every frame and wanders over a long hold. Both are gone;
# what survives is a HARD FREEZE.
#
# ⭐ The object does not move AT ALL below the threshold -- blend factor exactly
# 0.0, still by construction rather than by being slow -- and moves at the shipped
# `ROTATION_SLERP_TAU_MS` above it. There is no middle.

# ⭐⭐⭐ FREEZE MODE (owner, 2026-08-27): *"I want absolutely no movement when the
# cube should be steady, and immediate release when the hands move (maybe with a
# couple of frames trigger)"*.
#
# ⛔ DAMPING IS NOT STILLNESS. Even at 4500 ms the blend factor is 0.015, so the
# cube still creeps 1.5% of the gap every frame -- small, but never zero, and over a
# long hold it wanders. Freeze mode makes the blend factor EXACTLY 0.0 below the
# threshold: the object does not move at all, by construction rather than by being
# slow.
#
# ⭐ THE TRIGGER IS WHAT MAKES IT SAFE, and it is why the owner's "couple of
# frames" is the right instinct: a single frame above the threshold is the shape of
# a NOISE SPIKE (measured: the raw target exceeds 160 deg/s on 5.4% of frames with
# the hand still), while a real turn is above it for many frames in a row. Requiring
# N consecutive frames rejects the spikes outright -- which the earlier
# instant-attack envelope could not do -- at a cost of exactly N-1 frames of onset.
#
# ⚠ THE COST, stated plainly: while frozen the cube ignores slow drift, so if the
# hand creeps below the threshold the gap accumulates and is paid back as a JUMP on
# release. That is inherent to "absolutely no movement" and is the reason this is a
# mode rather than the default.
# ✅ SETTLED BY THE OWNER 2026-08-27: RELEASE 60 / FREEZE 1 / COHERENCE 0, after nine live
# sessions. ⚠ 1 frame, not 2: the two-frame trigger was rejected for making the
# rotation jerky, and the coherence gate below is what makes one frame enough.
# ⭐⭐ THE GRAB RADIUS LIVES HERE FOR THE SAME REASON tau DOES, and it had the same
# problem: it was defined TWICE, once in each tool, both reading 1.5 -- so the
# duplication stayed invisible until the moment one of them was tuned.
#
# Distance from a cube's CENTRE, in units of that cube's projected extent, within
# which an unowned cube can be snapped.
#
# ⭐ 0.5 since 2026-08-26, owner: *"the barycenter must be away less than half of
# the maximum dimension shown by the cube to the camera"*. The rationale, the
# measured cost (only 22% of 50 real grabs survive the tightening) and the reason
# it is an IN-PLANE test only are recorded at the reference in
# `HandsTriggeredActions.GRAB_RADIUS_MULTIPLIER`.
# ⛔⛔ 0.33 MADE THE GAME UNGRABBABLE, AND THE REASON IS A COMPOUNDING MISTAKE.
#
# The owner picked 0.33 on the rig slider and it felt right AT THE TIME. What was
# not noticed -- by me -- is that the fraction was chosen while every cube was
# still INFLATED by the depth ratchet: cubes were pinned at the 0.30 m floor and
# rendering at 133 px instead of the ~80 px they take at the resting depth. So
# 0.33 then meant 0.33 x 160 = 53 px, and 0.33 now means 0.33 x 96 = 32 px for the
# large cube and 16 px for the small one.
#
# ⚠ Fixing the ratchet and tightening the multiplier in the same session multiplied
# together: the grab region collapsed about 4x, and the owner reported "I can't
# grab any more". ⛔ THE LESSON: a fraction settled live is only valid against the
# quantity it was settled against. Re-measure a tuned fraction after ANY change to
# what it multiplies.
#
# ⭐ 1.0 = "the barycentre must fall inside the object's projected outline", which
# is a rule that means the same thing at every size and depth. At the resting depth
# that is 96 px (large) / 48 px (small), comparable to the 120/60 the old rule gave.
# The owner re-tunes from here with the slider, which now reaches past 100%.
GRAB_RADIUS_MULTIPLIER = 1.0

# ⚠ A HITCH MUST NOT BECOME A POP: dt is clamped before the exponential, or a cube
# teleports onto the hand on the first frame after a dropout -- undoing D3's
# resync blend, a fix the owner has already accepted.
ROTATION_SLERP_MAX_DT_MS = 200.0

# ⛔⛔ THE RELEASE THRESHOLD IS THE ONLY REAL DIAL, and that was measured against
# the alternatives rather than assumed. Speed-only beats every variant at every
# stillness level; see `analysis/steady_tuning_sweep.py`. On 6038 frames of natural
# use:
#
#     RELEASE   moves when STILL   follows a SLOW turn
#        50           10.2%              87.2%
#        60            6.0%              77.6%     <- settled by the owner
#        70            3.3%              70.3%
#        80            1.4%              62.0%
#
# ⚠ THE UNITS ARE SHARED WITH TRANSLATION ON PURPOSE -- deg/s for rotation, px/s
# for the grip point -- because the two distributions nearly coincide while a cube
# is held (p50 27 vs 26, p75 64 vs 53). If the camera or working distance changes,
# the pixel figures move and the degree ones do not, and this needs RE-MEASURING
# rather than re-deriving.
ROTATION_STEADY_RELEASE_DEG_S = 60.0

# ⭐ Hysteresis: it releases at RELEASE and refreezes at this fraction of it, so a
# speed hovering at the boundary cannot chatter between the two states.
ROTATION_STEADY_HOLD_FRACTION = 0.45

ROTATION_STEADY_FREEZE_FRAMES = 1      # 0 = off (smooth ramp); N = freeze, N-frame trigger


# ⛔⛔ A DIRECTIONAL-COHERENCE GATE WAS BUILT TWICE AND REMOVED TWICE. Do not
# rebuild it without new evidence. Both forms are recorded in
# `analysis/global_coherence.py`, which still runs:
#
#     measure                        still     slow turn    separation
#     per-landmark sign vote         0.353       0.810         0.98
#     Frobenius correlation         -0.260      +0.538         1.01
#     dominant-direction energy      0.762       0.818         0.33
#     rigid residual (Kabsch fit)    0.831       0.856         0.12
#
# ⭐ The Frobenius form is a genuinely good MEASURE -- a still hand reads NEGATIVE
# because consecutive noise steps anti-correlate, so zero is a principled threshold.
# ⛔ It is a bad TRIGGER, and that is a property of the question rather than of the
# implementation: coherence says the hand is moving SOMEHOW, and the freeze needs to
# know HOW MUCH. A drifting still hand is coherent; a hand pausing mid-turn is not.
# Measured on 6038 frames of natural use, it cost 7-11 points of slow-turn following
# for about 1 point of stillness, at every setting.

# ⭐⭐ TRANSLATION USES THE SAME RULE AND THE SAME NUMBERS (owner, 2026-08-27:
# *"can you implement the same for translation (same values as the sliders for
# translation, to avoid growing the number of sliders)"*).
#
# ⭐ IT IS NOT A COINCIDENCE THAT ONE THRESHOLD SERVES BOTH, it was measured. The
# grip point's speed in PIXELS/S and the hand's rotation speed in DEGREES/S have
# nearly the same distribution while a cube is held:
#
#             p50      p75      p90
#   rotation   27       64      177   deg/s
#   grip       26       53      117   px/s
#
# So `RELEASE = 80` freezes below 36 in either unit, and covers 81.8% of the frames
# where the hand is rotationally still. ⚠ If the camera resolution or the working
# distance changes the pixel figures move and the rotation ones do not -- at which
# point this shared threshold needs re-measuring, not re-deriving.
#
# ⛔ `steady_hold_update` is deliberately UNIT-AGNOSTIC: it compares a speed to a
# threshold and counts frames. Feeding it px/s instead of deg/s is the whole port.
# The COHERENCE input is literally the same number for both -- the hand either is
# or is not moving one way, and that fact does not belong to one channel.
TRANSLATION_STEADY = True


def steady_hold_update(frozen, run, speed_deg_s, release_deg_s=None,
                       trigger_frames=None, hold_fraction=ROTATION_STEADY_HOLD_FRACTION):
    """Advance the freeze state machine. Returns `(frozen, run)`.

    FROZEN  -> needs `trigger_frames` CONSECUTIVE frames at or above the release
               speed to let go. One fast frame is not enough; that is the point.
    MOVING  -> refreezes as soon as the speed drops below the HOLD level, which is
               lower than the release level, so the two thresholds hysterese and the
               state cannot chatter on a speed hovering at the boundary.

    ⚠ `speed_deg_s` is the RAW target's speed, never the smoothed output -- the
    output is self-referential and the cube would lock solid.
    """
    n = int(ROTATION_STEADY_FREEZE_FRAMES if trigger_frames is None else trigger_frames)
    if n <= 0:
        return False, 0                      # mode off: never frozen
    hi = float(ROTATION_STEADY_RELEASE_DEG_S if release_deg_s is None else release_deg_s)
    lo = hi * max(0.0, min(1.0, float(hold_fraction)))
    if speed_deg_s is None or speed_deg_s != speed_deg_s:
        return frozen, 0                     # unknown speed changes nothing
    sp = max(0.0, float(speed_deg_s))
    ok = sp >= hi
    if frozen:
        run = run + 1 if ok else 0
        return (False, 0) if run >= n else (True, run)
    return (True, 0) if sp < lo else (False, 0)


def frame_dt_ms(now_ms, last_ms, max_dt_ms=ROTATION_SLERP_MAX_DT_MS):
    """Milliseconds since the previous frame, clamped. None when unknowable.

    `None` means "there is no usable interval yet" -- the first frame, or a
    caller with no clock. Every consumer must treat it as "do not advance",
    never as zero and never as a guess.
    """
    if now_ms is None or last_ms is None:
        return None
    return min(max(0.0, now_ms - last_ms), max_dt_ms)

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
