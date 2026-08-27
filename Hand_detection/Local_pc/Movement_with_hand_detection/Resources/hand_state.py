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
# ✅ SET BY THE OWNER 2026-08-27 after six live sessions: 4500 / 80.
# ⚠ This is no longer "off by default" -- production damps too. The
# acceptance gate stands: 0 still reproduces the old behaviour bit-exactly.
ROTATION_STEADY_EXTRA_MS = 4500.0

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
ROTATION_STEADY_RELEASE_DEG_S = 80.0

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
# ⛔⛔ THE ENVELOPE'S DECAY RATE IS NOW ITS OWN NUMBER, IN deg/s PER SECOND.
# It used to be "one whole RELEASE threshold per ENVELOPE_MS", which quietly COUPLED
# the release slider to two opposing effects: raising it lifted the bar (more
# damping) AND sped up the decay (less damping). Owner, 2026-08-27: *"I did not see
# much effect for the release when I varied it"* -- that cancellation is why.
# ⭐ Decoupled, the RELEASE slider now does exactly one thing.
# ⭐⭐ AND IT IS FAST, WHICH IS THE WHOLE FIX. Owner, 2026-08-27: *"I felt the
# 600 ms did not dampen as much as previously"* -- correct, and the cause was NOT
# the attack. A held-still hand's raw target exceeds 160 deg/s on 5.4% of frames
# from jitter alone, and at the original 640 each of those spikes released the
# damping for ~350 ms. Measured duty cycle: full damping only 80.3% of the time.
#
# ⭐ A real turn RE-ATTACKS EVERY FRAME, so it stays released no matter how fast
# this decays; only an ISOLATED spike decays away. Making the release last about one
# frame therefore costs the onset nothing and buys back all the damping:
#
#     decay    full damping   released   onset following
#      640         80.3%        12.5%         96%
#     3000         88.1%         6.1%         97%
#     6000         88.6%         5.7%         97%   <- shipped
#   no envelope at all           88.6%/5.6%    (onset 81%)
#
# ⛔ i.e. the damping is now indistinguishable from having no envelope, while the
# onset keeps the envelope's full benefit. ⚠ Raising it further changes nothing --
# 12000 measures identically, so this is the knee, not a maximum.
ROTATION_STEADY_DECAY_DEG_S2 = 6000.0

# (the old ROTATION_STEADY_ENVELOPE_MS is gone: the decay rate above replaced it,
# and a constant nothing reads is a constant that drifts from the truth.)


def steady_speed_envelope(previous_env, speed_deg_s, dt_ms):
    """Fast-attack, fast-release envelope of the raw target's angular speed.

    ⛔⛔ A WINDOWED (multi-frame) SPEED WAS TRIED HERE AND IS THE WRONG ANSWER.
    It rejects the noise beautifully -- median speed 23 -> 9 deg/s -- and it
    DESTROYS the thing the envelope exists for: onset following collapsed from 96%
    to 10%, because averaging the first fast frame with two quiet ones puts it back
    under the threshold. ⭐ At the very first frame of a turn there is genuinely no
    information separating it from a noise spike; only the NEXT frame can tell.
    Every dual-threshold variant was measured too and none recovered it, because the
    noise (p95 163 deg/s) overlaps the onset speeds (>121 deg/s).
    ⚠ So the attack stays instant and per-frame, and the noise is dealt with by
    making the RELEASE fast instead -- see `ROTATION_STEADY_DECAY_DEG_S2`.

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
    if dt_ms is None or dt_ms <= 0.0:
        return previous_env
    # linear release at its OWN rate, independent of the release threshold
    step = ROTATION_STEADY_DECAY_DEG_S2 * (float(dt_ms) / 1000.0)
    fell = previous_env - step
    return sp if fell < sp else fell


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
# ✅ SETTLED BY THE OWNER 2026-08-27: 4500 / 80 / 1 / 0.60, after eight live
# sessions. ⚠ 1 frame, not 2: the two-frame trigger was rejected for making the
# rotation jerky, and the coherence gate below is what makes one frame enough.
ROTATION_STEADY_FREEZE_FRAMES = 1      # 0 = off (smooth ramp); N = freeze, N-frame trigger


# ⭐⭐⭐ PER-LANDMARK DIRECTIONAL COHERENCE -- the owner's mechanism, 2026-08-27:
# *"at each landmark level, the trigger threshold is N consecutive frames where the
# landmark position changes in the same direction: that should eliminate noise where
# landmarks goes one direction the next frame and comes back the frame after"*.
#
# ⭐ IT SUCCEEDS WHERE A SPEED THRESHOLD CANNOT, and the reason is measurable: the
# noise and a real turn OVERLAP in magnitude (noise p95 163 deg/s against onsets
# above 121), so no speed alone separates them. They do NOT overlap in DIRECTION.
# Measured on `2026-08-27_224751_freeze`, fraction of moving landmarks whose step
# agrees in direction with their previous step:
#
#       hand STILL     0.35 median
#       hand TURNING   0.90 median
#
# ⛔ BUT COHERENCE ALONE IS NOT ENOUGH, and this is the part worth keeping: on its
# own it calls 19-38% of still frames "moving", because a SLOW COHERENT DRIFT is
# perfectly coherent and simply is not fast. Direction rejects jitter; magnitude
# rejects drift; the trigger needs both.
#
# ⭐⭐ WHAT IT BUYS: with coherence gating alongside the speed test, ONE frame is
# enough -- which is the point, because the owner rejected the two-frame trigger for
# making the rotation jerky:
#
#     rule                                  releases when STILL   when TURNING
#     speed>=80,  N=2  (rejected: jerky)           1.3%              85.1%
#     speed>=80 AND coherence>=0.6, N=1            1.6%              97.7%
#
# i.e. the same noise rejection with no second frame, and far more of the real
# turning caught.
COHERENCE_MIN_PX = 0.75        # below this a landmark has no meaningful direction
COHERENCE_FRACTION = 0.60      # 0 = gate OFF. ✅ 0.60 settled by the owner.


def landmark_coherence(points, prev_points, prev_deltas, min_px=COHERENCE_MIN_PX):
    """(fraction_agreeing, deltas) -- how much of the hand is moving ONE WAY.

    ⭐ A landmark counts only if it moved at least `min_px`: a point that barely
    moved has a direction made of rounding, and counting it would add coin flips to
    the average. ⚠ Compared as SQUARED magnitudes so this module still needs no
    `math` import (`verify_hand_state` asserts it imports nothing).

    ⚠ Returns the deltas so the caller can pass them back next frame; this module
    holds no state of its own.
    """
    if not points or not prev_points or len(points) != len(prev_points):
        return None, None
    deltas = []
    for i in range(len(points)):
        deltas.append((points[i][0] - prev_points[i][0],
                       points[i][1] - prev_points[i][1]))
    if not prev_deltas or len(prev_deltas) != len(deltas):
        return None, deltas
    thr = float(min_px) * float(min_px)
    moving = agree = 0
    for i in range(len(deltas)):
        dx, dy = deltas[i]
        if dx * dx + dy * dy < thr:
            continue
        moving += 1
        if dx * prev_deltas[i][0] + dy * prev_deltas[i][1] > 0.0:
            agree += 1
    return (agree / float(moving) if moving else 0.0), deltas


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
                       trigger_frames=None, hold_fraction=ROTATION_STEADY_HOLD_FRACTION,
                       coherence=None):
    """Advance the freeze state machine. Returns `(frozen, run)`.

    FROZEN  -> needs `trigger_frames` CONSECUTIVE frames at or above the release
               speed to let go. One fast frame is not enough; that is the point.
    MOVING  -> refreezes as soon as the speed drops below the HOLD level, which is
               lower than the release level, so the two thresholds hysterese and the
               state cannot chatter on a speed hovering at the boundary.

    ⚠ `speed_deg_s` is the RAW target's speed, never the smoothed output -- the
    same rule `steady_tau_ms` states, and for the same reason.
    """
    n = int(ROTATION_STEADY_FREEZE_FRAMES if trigger_frames is None else trigger_frames)
    if n <= 0:
        return False, 0                      # mode off: never frozen
    hi = float(ROTATION_STEADY_RELEASE_DEG_S if release_deg_s is None else release_deg_s)
    lo = hi * max(0.0, min(1.0, float(hold_fraction)))
    if speed_deg_s is None or speed_deg_s != speed_deg_s:
        return frozen, 0                     # unknown speed changes nothing
    sp = max(0.0, float(speed_deg_s))
    # ⭐ BOTH tests must pass to release: fast ENOUGH and moving ONE WAY. Direction
    # rejects the jitter that magnitude cannot; magnitude rejects the slow coherent
    # drift that direction cannot.
    # ⚠ `COHERENCE_FRACTION = 0` disables the direction half, leaving exactly the
    # speed-only behaviour -- so the gate can be turned off without a second branch.
    ok = sp >= hi
    if ok and COHERENCE_FRACTION > 0.0 and coherence is not None:
        ok = coherence >= COHERENCE_FRACTION
    if frozen:
        run = run + 1 if ok else 0
        return (False, 0) if run >= n else (True, run)
    return (True, 0) if sp < lo else (False, 0)


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
