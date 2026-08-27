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
#     cube ORIENTATION   4.30 deg/frame median, p95 15.40   <- THE JITTER
#     cube size (depth)  1.25 px median, p95 6.57 (8% of an 80 px cube)
#
# ⛔ So position is NOT the problem -- damping it would only lag translation. The
# shimmer is ORIENTATION, 4.3 deg every frame at 15 fps, and it is already smoothed
# at tau = 20 ms.
#
# ⭐ RAISING tau IS NOT THE ANSWER, and `L1` is why: a fixed time constant lags
# genuine motion exactly as much as it damps jitter, and the owner rejected that
# trade once already (*"the cube is lagging the hand and this feels very
# uncomfortable"*). This makes tau ADAPTIVE instead -- the 1-euro idea applied to
# the slerp already shipped:
#
#     barely turning  ->  tau rises      -> the shimmer is held still
#     really turning  ->  tau collapses  -> today's responsiveness, unchanged
#
# ⛔ `extra_ms = 0` IS TODAY'S BEHAVIOUR, BIT-EXACT. The slider's left end is
# production.
ROTATION_STEADY_EXTRA_MS = 0.0

# ⛔⛔ THE RELEASE IS A HARD-EDGED RAMP, NOT A HYPERBOLA (owner, 2026-08-27:
# *"we need a more abrupt cut-off because I don't want any quaternion slerp as soon
# as I start a hand rotation"*).
#
# The first shape was `extra / (1 + speed/knee)`, which never fully lets go: at
# 600 ms of extra and a brisk 300 deg/s it still left ~120 ms of tau, and that is
# the "lengthy slerp" felt at the START of a turn. ⭐ Now the extra damping is
# ramped to EXACTLY ZERO by `RELEASE_DEG_S`, so above that speed the cube is on
# today's tau and nothing else.
#
# ⚠ THE FLOOR IS SET BY THE NOISE, and it is why this cannot simply be tiny:
# a HELD-STILL hand's raw target already moves 2.53 deg/frame -- about 38 deg/s at
# 15 fps. A release threshold under that would be tripped by the very jitter the
# damper exists to remove, and the damping would flicker on and off.
ROTATION_STEADY_RELEASE_DEG_S = 90.0

# Below this fraction of the release speed the damping is at FULL strength. The gap
# between the two is the whole width of the ramp -- narrow, on purpose.
ROTATION_STEADY_HOLD_FRACTION = 0.45

# ⭐⭐ THE SPEED ENVELOPE: INSTANT ATTACK, SLOW RELEASE. This is what makes the
# cut-off feel immediate rather than merely sharp.
#
# ⛔ A turn STARTS at zero speed. Any threshold on the instantaneous speed is
# therefore still fully damped for the first frame or two of a deliberate rotation
# -- exactly the onset lag being complained about. So the envelope jumps to any new
# maximum AT ONCE and only falls back gradually: one fast frame releases the damper,
# and it re-engages only after the hand has genuinely settled.
#
# ⭐ How long the envelope takes to fall by one whole RELEASE threshold. A LINEAR
# release, not an exponential one, and that is deliberate twice over:
#   ✅ it keeps this module's "imports NOTHING" property, which
#      `verify_hand_state.py` asserts as a port-contract check and which an `exp`
#      would have quietly cost (it did: the first version failed that vector);
#   ⭐ and a fixed rate gives a PREDICTABLE hold time, which is what an envelope
#      follower wants -- an exponential tail lingers unevenly depending on how fast
#      the turn was.
# ⚠ Still TIME-based, never per-frame (`L1`): the step is rate x dt.
ROTATION_STEADY_ENVELOPE_MS = 250.0


def steady_speed_envelope(previous_env, speed_deg_s, dt_ms,
                          tau_ms=ROTATION_STEADY_ENVELOPE_MS):
    """Fast-attack, slow-release envelope of the raw target's angular speed.

    ⚠ `previous_env` None starts the envelope AT the speed, not at zero -- starting
    low would apply full damping to a hand that is already moving.
    """
    if speed_deg_s is None or speed_deg_s != speed_deg_s:
        return previous_env
    sp = max(0.0, float(speed_deg_s))
    if previous_env is None:
        return sp
    if sp >= previous_env:
        return sp                                  # instant attack
    if dt_ms is None or dt_ms <= 0.0 or tau_ms <= 0.0:
        return previous_env
    # linear release: one whole RELEASE threshold per `tau_ms` of elapsed time
    step = ROTATION_STEADY_RELEASE_DEG_S * (float(dt_ms) / float(tau_ms))
    fell = previous_env - step
    return sp if fell < sp else fell


def steady_tau_ms(base_tau_ms, speed_deg_s,
                  extra_ms=None, release_deg_s=None,
                  hold_fraction=ROTATION_STEADY_HOLD_FRACTION):
    """The effective smoothing time constant for this frame.

    ⛔⛔ `speed_deg_s` MUST BE MEASURED FROM THE RAW TARGET, never from the
    smoothed output. Measuring the output makes it self-referential: damping lowers
    the apparent speed, which raises the damping, which lowers it further -- and the
    cube locks solid and never moves again. This is the one way to get this function
    badly wrong, so it is stated here rather than left to the caller to notice.

    ⚠ An unknown speed is treated as FAST (no extra damping). Unknown must not
    mean "hold still", or a dropout would freeze the object.
    """
    base = max(1.0, float(base_tau_ms))
    extra = ROTATION_STEADY_EXTRA_MS if extra_ms is None else float(extra_ms)
    if extra <= 0.0 or speed_deg_s is None or speed_deg_s != speed_deg_s:
        return base
    hi = float(ROTATION_STEADY_RELEASE_DEG_S if release_deg_s is None else release_deg_s)
    if hi <= 0.0:
        return base
    lo = hi * max(0.0, min(1.0, float(hold_fraction)))
    sp = max(0.0, float(speed_deg_s))
    if sp >= hi:
        return base                       # ⭐ fully released: today's tau, exactly
    if sp <= lo:
        return base + extra               # fully held
    t = (sp - lo) / (hi - lo)
    return base + extra * (1.0 - t * t * (3.0 - 2.0 * t))

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

# ⛔⛔ OPEN DEFECT, FOUND 2026-08-26 BY RAISING THIS VALUE: at 1.0 the two
# pipelines DISAGREE about whether a grab happens. `analysis/parity_replay.py` on
# `2026-08-24_220415_prod_tau20` reports 41 divergences, the first being ownership
# at frame 377 (production claims the large cube, the debug tool does not); at 0.33
# it reports NONE.
#
# ⚠ It is NOT the `F1` path: both switches are off in that replay, so the grip
# point, the trim and the depth walk are all inert. A wider radius simply brings
# more cubes into contention and surfaces a difference that a narrow radius hid.
# ⭐ Which is precisely what `U6` keeps `parity_replay` for -- the guard worked.
#
# ⛔ NOT diagnosed yet. Narrowed to: with both flags off the two tools compute the
# same centre and the same hand position, so the difference has to be in
# `projected_size_of` -> `cube.depth_m`, i.e. the two depth-ratio trackers drifting
# apart over the take. Investigate before this value ships.

# ⚠ A HITCH MUST NOT BECOME A POP: dt is clamped before the exponential, or a cube
# teleports onto the hand on the first frame after a dropout -- undoing D3's
# resync blend, a fix the owner has already accepted.
ROTATION_SLERP_MAX_DT_MS = 200.0


# ⭐⭐ THE FRAME INTERVAL, COMPUTED ONCE AND SHARED. Owner, 2026-08-27: *"the dt
# will probably also be used somewhere else in the game later on"* -- so it lands
# as a named, reusable quantity rather than being re-derived at each call site.
#
# ⛔ WHY IT LIVES HERE AND NOT IN THE ESTIMATORS. The estimator layer is
# CLOCK-FREE BY CONTRACT (`CONSTRAINTS` §2): it is transliterated to JS/Swift/
# Kotlin, and a wall-clock read is the first thing that does not port. So no
# estimator may ask what time it is -- the CALLER, which already owns the frame
# loop and its timestamps, computes the interval and passes it down as a plain
# number. That keeps every estimator deterministic under replay, which is what
# `analysis/parity_replay.py` and every golden-vector suite depend on.
#
# ⚠ THE CLAMP IS THE POINT, NOT A DETAIL. After a dropout, a coast or a stalled
# frame the raw interval can be hundreds of milliseconds, and every consumer of dt
# scales something by it -- a blend factor, a rate limit, a fade. Unclamped, one
# hitch becomes one large visible jump, which is precisely the pop `D2`/`D3` exist
# to prevent. Clamping here means no consumer has to remember to.
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
