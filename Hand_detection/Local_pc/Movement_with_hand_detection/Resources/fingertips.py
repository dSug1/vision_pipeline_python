"""⭐⭐ THE FINGERTIP GRIP POINT — `F1` step 2. The barycentre of the five tips.

> **Owner, 2026-08-25:** *"the cube's transform follows the transform of the
> barycenter of the fingertips"* · *"the condition for the cube being grabbed: the
> barycenter is close to the cube (same as previous, except that instead of the
> palm we use the fingertips barycenter)"* · *"if the fingertips move while the
> cube is grabbed, the cube's transform follow the transform of the barycenter."*

Spec: `Claude/10_HAND_TRACKING/spec/F1_FINGERTIP_TRANSFORM_SPEC.md` §4, §5.1.

────────────────────────────────────────────────────────────────────────────────
⭐ WHY A BARYCENTRE IS A SAFE THING TO BUILD ON, WHERE A TIP IS NOT

The Model Card says the fingertips are the landmarks the model estimates WORST,
and `analysis/f1_tip_census.py` measured their noise floor at a **1.5 mm median /
4.7 mm p95** per tip (on frames where the palm itself barely moved). ⭐ Averaging
five of them cuts uncorrelated noise by ~sqrt(5), and the 1€ filter below takes
the rest. Averaging is also what makes Horn's five-point palm stable -- the same
argument, applied to the other end of the hand.

────────────────────────────────────────────────────────────────────────────────
⚠⚠ THE MEASURED HAZARD, RECORDED BEFORE THE LIVE TAKE RATHER THAN AFTER

The barycentre MOVES WHEN THE FINGERS MOVE, which is the point -- and also the
risk. With the palm held still, `f1_tip_census.py` measured the tip barycentre
drifting a **median 1 cm and a p95 of 6 cm within half a second**, purely from
re-gripping. At the `g_pos = 1` this module implements -- the owner's request
taken literally -- that is the object translating by those amounts while the hand
is not going anywhere.

⭐ That may well be RIGHT: a real held object does move when you reposition your
fingers on it. Only the live take can say whether the amount matches the intent.
⛔ **The remedy, if it is wrong, is NOT to filter harder** -- that trades the
wander for lag and keeps both. It is the palm-frame clamp in spec §4.3
(`u_drift`), which needs the palm frame that `F1` step 4 builds, and which is why
the clamp is deliberately NOT in this step.

────────────────────────────────────────────────────────────────────────────────
⛔ `USE_TIP_BARYCENTER = False` MUST BE TODAY'S BEHAVIOUR, EXACTLY

Every `F1` step lands behind a switch whose OFF state is provably the shipped
pipeline (`T6d`'s method: measured byte-identical on 975/975 frames, which is what
made that build revert-free when the owner rejected it). Callers ask
`grip_position_px()` for the point to use and get the palm centre back when the
flag is off -- the same object today's code would have used, not a recomputation
of it.

⚠ NOT PUBLISHED AS `palm_pose`. `handinput`'s `palm_pose` action means the PALM
and keeps meaning the palm; this grip point is a separate quantity used for snap
proximity and translation. Silently redefining a shipped action's meaning would
break every consumer without changing a single signature.
"""
import math

from . import one_euro
from . import palm_geometry

# MediaPipe fingertip landmark ids: thumb, index, middle, ring, pinky.
TIPS = (4, 8, 12, 16, 20)

# ⛔⛔ THE STEP-2 SWITCH, AND IT IS **OFF** UNTIL THE LIVE TAKE SAYS OTHERWISE.
#
# False => `grip_position_px` returns the palm centre, so this module cannot affect
# anything and the game runs exactly as it did before `F1`.
#
# ⚠ It was briefly True on 2026-08-26, which meant PRODUCTION was shipping the
# fingertip barycentre for snap and translation **while it was still unconfirmed**
# -- the owner's last production sign-off predates step 2 entirely. A change the
# owner has not seen must not be live in the game they are using to judge it: it
# makes the rig's control panel and the actual game disagree, and it is exactly
# how an unnoticed regression gets attributed to something else.
#
# ⭐ THE RIG IS UNAFFECTED. `--f1-rig`'s panels pass `use_tips` EXPLICITLY
# (False, True, True), and an explicit value always wins over this global -- so
# the three-window comparison still works with this off, and the ordinary
# single-arm debug view now matches production again.
# ⭐⭐ SWITCHED ON IN PRODUCTION 2026-08-26, owner's instruction, after four
# rig sessions. ⚠ Shipped with the `A10` non-regression bar and §10.1's
# trim-resolution metric still OUTSTANDING; the owner chose the LIVE LOOK as the
# gate, knowing that jitter p95 25.41 is the metric that killed the 9-point fit.
# ⚠ The docstring above still describes the OFF state as today's behaviour --
# that remains true and is what `verify_f1_grip_offstate` pins; it is simply no
# longer the state the game runs in.
USE_TIP_BARYCENTER = True

# ⚠ ONE COPY, imported by both tools (`CONSTRAINTS` §4 / N6). A tuning constant
# that exists twice is how the two pipelines drift.
# ⛔⛔ THE OWNER ASKED FOR THIS PARKED AT ITS MINIMUM ON 2026-08-26 AND THE
# ACCEPTANCE GATE REFUSED IT -- kept ON, with the measurement, pending their call.
#
# Minimum means zero, and zero is the 1-euro filter's bit-exact OFF state. Set
# there, `analysis/verify_f1_grip_offstate.py` FAILS its third check:
#     worst single-frame step   OFF (palm) 76.0 px   ON (tips, unfiltered) 120.4 px
# against 50.9 px with the filter at its default. So the filter is not decoration:
# it is what keeps the fingertip grip point from stepping FURTHER in one frame
# than the palm path it is meant to improve on.
#
# ⚠ AND IT CORRECTS SOMETHING I SAID WHILE RECOMMENDING THE PARK: "the census puts
# the noise floor at 1.5 mm, so there is little to remove". That 1.5 mm is the
# QUIET-FRAME floor. Raw frame-to-frame tip motion is p95 **21-31 mm** -- the very
# distinction the census flagged as its own trap, and I read the wrong side of it.
#
# ⭐ The owner's reason for wanting it low (lag) is real and unaddressed; a small
# non-zero tau is the likely answer, not zero. Left at the default until they choose.
GRIP_FILTER_ENABLED = True

# ⭐⭐ A1 (owner, 2026-08-26): "cube center is locked in x and y axis onto the x
# and y positions of the barycenter of the fingertips."
#
# ⛔ WHAT IT REPLACES, AND WHY. The grab used to store `object_pos - hand_pos` and
# carry that pixel offset for the whole hold. MEASURED on the owner's float take
# (`2026-08-26_190912_f1_rig`, 3498 held frames): the cube sat a median **115.6 px**
# from the fingertip barycentre -- p90 142, max 181 -- and the offset did NOT grow
# with rotation (115 px square-on, 115 px edge-on). It is a constant displacement
# captured at the instant of the grab, and it is wider than the cube itself.
#
# ⭐ So the object was never IN the hand; it rode beside it. Zeroing the offset is
# what makes "the object follows the fingertips" literally true.
# ⚠ THE COST, stated because it is a real behaviour change: a deliberately
# off-centre grab no longer holds its offset -- take a cube by its corner and it
# re-centres on your fingertips. The owner accepted this: at 115 px there was no
# meaningful "grab it where you touch it" left to preserve.
GRIP_ALIGN_AT_GRAB = True

# ⛔⛔ AND IT IS A FADE, NOT A TELEPORT -- because the teleport FAILED THE GATE.
#
# Zeroing the offset at the instant of the grab made the object jump onto the
# fingertips in one frame. `analysis/verify_f1_grip_offstate.py` caught it
# immediately: worst single-frame step went 50.9 px -> 120.7 px, i.e. ON now moved
# FURTHER in one frame than the palm path it replaces (76.0 px). That check exists
# to stop exactly this.
#
# ⭐ So the offset is captured as it always was -- the grab stays continuous, no
# pop -- and then DECAYS to zero with a time constant. The object ends up centred
# on the fingertips, which is what `A1` asked for, and gets there smoothly.
# ⭐ The owner anticipated this in their own wording: *"it costs an initial
# repositioning"*. This is that repositioning, spread over `GRIP_ALIGN_TAU_MS`.
#
# ⛔⛔ AND IT ADVANCES ONLY WHILE THE HAND IS MOVING — owner, 2026-08-26:
# *"instead of immediately reposition, make the slerp over the first xx ms of a
# hand movement (and the slerp freezes if the hand stops moving during these
# first xx ms). That will mask the repositioning slerp within a hand movement
# instead of a cube movement which is not triggered by any hand movement."*
#
# ⭐⭐ THE INSIGHT IS PERCEPTUAL AND IT IS RIGHT. A cube sliding while the hand is
# still reads as the software doing something wrong. The SAME slide during a hand
# movement is not seen at all — it is attributed to the hand. So the correction is
# spent where it is invisible, and never spent where it would be conspicuous.
#
# Two constants, and both were MEASURED rather than chosen:
#
#   * `GRIP_ALIGN_MOVING_MS` — the budget, in milliseconds OF MOVEMENT. Wall time
#     does not advance it; a hand held still pauses the fade indefinitely and it
#     resumes exactly where it stopped.
#   * `GRIP_ALIGN_MOVING_PX_S` — the speed above which the hand counts as moving.
#     ⭐ From the four post-fix rig takes, 14656 frames: the barycentre's own speed
#     is p5 7.6 / p25 24.3 / p50 56.3 / p75 132.8 px/s. A 40 px/s line sits between
#     the 25th and 50th percentile and counts 60.7% of frames as moving — i.e.
#     comfortably above a held hand's residual tremble, comfortably below any
#     deliberate motion.
#
# ⚠ AN EARLIER DESIGN, kept because it explains the shape of this one: a plain
# rate cap in px/s. It passed the gate and settled predictably, but it spent the
# correction on WALL time, so a cube grabbed and then held still would visibly
# creep on its own. That is exactly the artefact the owner named.
# ⛔ And before THAT, two designs the gate rejected outright — a teleport
# (118.4 px in one frame) and an exponential fade (118.4 px, because an exponential
# takes its biggest bite on the first frame). Both are recorded at
# `GRIP_ALIGN_AT_GRAB` above.
# ⭐ 300 ms — settled by the owner on the rig slider, 2026-08-26.
GRIP_ALIGN_MOVING_MS = 300.0
GRIP_ALIGN_MOVING_PX_S = 40.0

# ⛔⛔ AND THE STEP IS CAPPED BY HOW FAR THE HAND ACTUALLY MOVED — the correction
# that made the first version wrong.
#
# **Owner, 2026-08-26:** *"It's like running to catch a train, but if the train
# stops, you also stop running."*
#
# ⚠ A moving-TIME budget alone does not deliver that. Consider a hand creeping at
# 45 px/s -- just over the "moving" line -- for the whole 250 ms: it travels 11 px
# while the cube retires its entire 50 px offset. The cube has then moved nearly
# five times as far as the hand, which is precisely the un-masked, self-propelled
# motion the whole design exists to hide. The gate on movement was binary when it
# needed to be PROPORTIONAL.
#
# ⭐ So each frame the cube may close at most `GRIP_ALIGN_MASK_RATIO` times the
# distance the HAND moved in that same frame. The cube can therefore never travel
# more than about twice the hand's own step, which reads as "keeping up" rather
# than as "moving by itself". At 1.0 the catch-up is at most the hand's own step.
#
# ⚠ CONSEQUENCE, and it is the intended one: `GRIP_ALIGN_MOVING_MS` becomes a
# FLOOR on the duration, not a promise. A hand that barely moves takes longer than
# the budget, and a hand that stops never finishes -- which is the train stopping.
# ⭐ 0.25 since 2026-08-26 — the owner: *"the current cap is too high and the cube
# reposition movement is still too fast"*. At 1.0 the cube was allowed to close a
# full hand-step per frame, so it kept pace with the hand and the correction was
# still legible as motion. A quarter of the hand's step disappears into it.
# ⚠ Below ~1.0 the MASK is what binds, not the time budget, so
# `GRIP_ALIGN_MOVING_MS` stops being the duration and becomes only a floor -- the
# walk then takes as long as the hand's own travel dictates. That is the intent.
GRIP_ALIGN_MASK_RATIO = 0.25

# ⚠ A hitch must not become a pop: dt is clamped before it is spent, exactly as
# `hand_state.ROTATION_SLERP_MAX_DT_MS` does for the rotation channel.
GRIP_ALIGN_MAX_DT_MS = 200.0


def decay_grip_offset(offset, depth_offset_m, remaining_ms, dt_ms, hand_step_px):
    """Walk a grab offset toward zero, in step with the HAND. ⭐ ONE COPY (N6).

    Returns `(offset, depth_offset_m, remaining_ms)`.

    ⭐⭐ THE DEPTH OFFSET WALKS ON THE SAME PROGRESS as the in-plane one, and it is
    here rather than in a second function on purpose: the object must arrive in the
    hand in all three axes AT ONCE. Two independent walks would land x/y first and
    then slide the object in depth on its own -- which is the very artefact this
    mechanism exists to prevent, reintroduced through the back door.

    Two limits apply to every frame, and the SMALLER wins:
      * the time budget -- the share of the remaining span this frame's `dt` buys
        out of `remaining_ms`, so the whole thing is walked in that much MOVING
        time;
      * the mask -- at most `GRIP_ALIGN_MASK_RATIO` times how far the hand itself
        moved this frame, so the object can never out-run the hand carrying it.

    ⚠ The mask is measured on the IN-PLANE step only. A depth correction is seen as
    a change of SIZE, and there is no honest pixel measure of "how much the hand
    moved in depth" -- the estimator that would supply it is the one being
    corrected. Tying both to the visible motion is the conservative choice.

    ⚠ Every early return leaves ALL THREE values untouched -- a frozen walk is
    frozen, not slowly leaking.
    """
    if offset is None or not GRIP_ALIGN_AT_GRAB:
        return offset, depth_offset_m, remaining_ms
    if remaining_ms is None or remaining_ms <= 0.0:
        return (0.0, 0.0), 0.0, 0.0
    if dt_ms is None or dt_ms <= 0.0 or hand_step_px is None:
        return offset, depth_offset_m, remaining_ms

    # ⛔ The train has stopped: so do we. Not a slow leak -- a full stop.
    speed = hand_step_px / (dt_ms / 1000.0)
    if speed < GRIP_ALIGN_MOVING_PX_S:
        return offset, depth_offset_m, remaining_ms

    dz = 0.0 if depth_offset_m is None else depth_offset_m
    d = math.hypot(offset[0], offset[1])
    dt = min(dt_ms, GRIP_ALIGN_MAX_DT_MS, remaining_ms)
    by_time_frac = dt / remaining_ms
    # ⚠ With no in-plane offset left there is nothing for the mask to bound, so the
    # time budget alone governs -- otherwise a dead-centre grab would freeze its
    # depth correction forever.
    by_mask_frac = (GRIP_ALIGN_MASK_RATIO * hand_step_px / d) if d > 1e-6 else by_time_frac
    frac = min(by_time_frac, by_mask_frac, 1.0)
    if frac >= 1.0:
        return (0.0, 0.0), 0.0, 0.0

    k = 1.0 - frac
    # ⚠ Only the time the walk ACTUALLY used is charged. When the mask is the
    # binding limit the budget is spent more slowly, which is what makes the
    # duration a floor rather than a deadline.
    spent = dt * (frac / by_time_frac) if by_time_frac > 1e-9 else dt
    return ((offset[0] * k, offset[1] * k), dz * k,
            max(0.0, remaining_ms - spent))

# ⭐⭐ THE SAME ALIGNMENT, IN Z -- and it fixes a RATCHET, not just an offset.
#
# ⛔ `cube.grab_depth_m = cube.depth_m` meant the object's depth was never once
# anchored to the hand. It started at whatever the cube was spawned with and from
# then on only ever evolved MULTIPLICATIVELY (`grab_depth / ratio`), carrying its
# own error into the next grab, and the next.
#
# ⛔⛔ MEASURED, same take: the hand was **never** nearer than the play volume's
# 0.30 m floor -- 0.0% of 3033 frames, p5 = 0.333 m -- while the CUBE sat pinned
# AT that floor for **57.4%** of the held frames. The object had been ratcheted
# into the near wall and stayed there, rendered at its maximum size, while the
# hand holding it was comfortably mid-volume. That is most of "it floats far away
# from the hand".
#
# ⭐ Anchoring the depth to the HAND's own measurement at grab removes the ratchet
# at its source: every grab re-seats the object where the hand actually is.
# ⚠ It imports the absolute estimator's per-user scale bias into the object's
# placement ONCE per grab. That is deliberate and bounded -- `palm_depth`'s
# standing warning is about feeding absolute metres into the Z-translation
# MAPPING, which still runs on the ratio form and is untouched here.
# ⚠ Falls back to the old behaviour whenever the hand's depth is not valid (the
# S10 band), because a held depth is not a measurement.
GRIP_ALIGN_DEPTH_AT_GRAB = True


def tip_barycenter_px(landmarks):
    """Mean of the five fingertips in pixels, or None if any is missing.

    ⚠ ALL FIVE OR NONE. A barycentre that silently changes its denominator jumps:
    averaging four tips instead of five moves the point by up to a fifth of a
    finger's reach, and nothing downstream could tell that from real motion. This
    is the same class of defect as the adaptive edge margin, which failed live
    because its input collapsed 45% in one frame.
    """
    if landmarks is None or len(landmarks) <= TIPS[-1]:
        return None
    x = y = 0.0
    for i in TIPS:
        p = landmarks[i]
        if p is None or len(p) < 2:
            return None
        x += p[0]
        y += p[1]
    return (x / len(TIPS), y / len(TIPS))


def tip_barycenter_world(world_landmarks):
    """Mean of the five fingertips in metres, or None. Used by the analysis
    harnesses and by step 4's palm-frame trim; not by the pixel path below."""
    if world_landmarks is None or len(world_landmarks) <= TIPS[-1]:
        return None
    x = y = z = 0.0
    for i in TIPS:
        p = world_landmarks[i]
        if p is None or len(p) < 3:
            return None
        x += p[0]
        y += p[1]
        z += p[2]
    n = float(len(TIPS))
    return (x / n, y / n, z / n)


class GripTracker:
    """Per-hand filtered grip point, in pixels.

    ⚠ ONE PER HAND, and `reset()` on a NEW TRACK -- never on a relabel. The `4.1`
    postmortem's lesson: a hand that leaves and returns is a new track and must
    inherit nothing, while the same hand under a swapped label must keep its
    state. `_bind_track_state` already carries per-hand objects that way.
    """

    __slots__ = ("_fx", "_fy", "_last")

    def __init__(self):
        self._fx = one_euro.OneEuroFilter(enabled=GRIP_FILTER_ENABLED)
        self._fy = one_euro.OneEuroFilter(enabled=GRIP_FILTER_ENABLED)
        self._last = None

    def configure(self, min_cutoff_hz=None, beta=None, enabled=None):
        for f in (self._fx, self._fy):
            if min_cutoff_hz is not None:
                f.min_cutoff_hz = min_cutoff_hz
            if beta is not None:
                f.beta = beta
            if enabled is not None:
                f.enabled = enabled

    def reset(self):
        self._fx.reset()
        self._fy.reset()
        self._last = None

    def update(self, landmarks, now_ms):
        """The filtered tip barycentre, or None when the tips are not all present.

        ⚠ A missing tip HOLDS the last good point rather than producing a partial
        barycentre -- `B8` measured that holding beats every fit, and `D2`'s coast
        makes the same choice for the hand as a whole. Returns None only when
        there has never been a good point to hold.
        """
        raw = tip_barycenter_px(landmarks)
        if raw is None:
            return self._last
        self._last = (self._fx.filter(raw[0], now_ms),
                      self._fy.filter(raw[1], now_ms))
        return self._last

    @property
    def last(self):
        return self._last


# ⭐⭐ THE AXIAL HALF OF THE GRIP POINT (owner, 2026-08-27).
#
# ⛔⛔ THE DEFECT IT FIXES, and the owner found it by looking rather than by
# measuring: *"in the palm and 80 degrees yaw tilted hand, the fingertips are all in
# front of the cube except the thumb: this cannot be, since the cube should follow
# the barycenter of the fingertips."*
#
# They were right, and it was an inconsistency in OUR logic, not in MediaPipe:
#
#     cube x,y  =  the FINGERTIP barycentre   (`grip_position_px`, F1 step 2)
#     cube z    =  a PALM-derived depth       (`palm_depth`, spans 0-5-9-13-17)
#
# The object sat at the fingertips laterally and at the PALM's depth axially. Grip
# palm-forward and the fingers wrap TOWARD the camera -- measured 3.6 cm nearer than
# the hand's own origin -- so every tip lands in front of the cube. Turn the hand
# over and the same fingers are 3.7 cm FARTHER, so they all land behind it and the
# occlusion looks right. Same code, opposite appearance.
#
# ⭐ This returns the offset that makes the two halves agree.
TIP_DEPTH_OFFSET = True


def tip_depth_offset_m(world_landmarks):
    """How far the fingertip barycentre sits in FRONT of the hand's own origin, in
    metres. Negative = nearer the camera. `None` when it cannot be computed.

    ⚠ MediaPipe's world `z` is per-landmark and relative to the hand's origin, so
    this is a RELATIVE offset and carries no absolute depth of its own. It is added
    to whatever absolute depth the caller already trusts (`palm_depth`), which keeps
    the two concerns separate and keeps this function free of any calibration.

    ⛔ It uses the SAME `TIPS` the barycentre uses, thumb included. Dropping the
    thumb here while `grip_position_px` keeps it would reintroduce exactly the
    inconsistency this exists to remove.
    """
    if not TIP_DEPTH_OFFSET or not world_landmarks:
        return None
    if len(world_landmarks) <= max(TIPS):
        return None
    zs = []
    for t in TIPS:
        w = world_landmarks[t]
        if w is None or len(w) < 3 or w[2] != w[2]:
            return None
        zs.append(float(w[2]))
    return sum(zs) / len(zs)


def grip_depth_m(hand_depth_m, world_landmarks):
    """The GRIP POINT's absolute depth: the hand's depth plus the tip offset.

    ⭐ This is what an object held in the fingers should converge to, and it is
    what `cube.grab_hand_depth_m` now anchors on.
    ⚠ Falls back to `hand_depth_m` unchanged whenever the offset is unavailable --
    i.e. exactly today's behaviour, never a guess.
    """
    if hand_depth_m is None:
        return None
    off = tip_depth_offset_m(world_landmarks)
    return hand_depth_m if off is None else hand_depth_m + off


def grip_position_px(tracker, landmarks, now_ms, use_tips=None):
    """⭐ THE ONE ENTRY POINT both tools call. Palm centre when the step is off.

    ⛔ When the step is off this returns exactly what the shipped pipeline used --
    `palm_geometry.palm_center_px(landmarks)` -- so the off state is the old
    behaviour rather than an approximation of it.

    ⛔⛔ `use_tips` EXISTS BECAUSE ITS ABSENCE SILENTLY VOIDED A LIVE TAKE
    (2026-08-26). The three-window rig passes `use_tips` explicitly per panel
    (False / True / True), and the docstring above this function used to claim
    "an explicit value always wins over this global". **It did not.** This
    function read the module global and returned the palm centre for EVERY panel,
    so the caller's choice was between two identical values -- and the owner
    judged a rig in which panels 1 and 2 were **bit-identical in position**
    (measured: 0.00 px across 6025 owned-cube samples).

    ⭐ `None` means "follow the module global", so production is untouched and
    every existing call site keeps its exact behaviour. Only a caller that passes
    the flag explicitly -- i.e. the rig -- can now override it.
    """
    enabled = USE_TIP_BARYCENTER if use_tips is None else bool(use_tips)
    if not enabled:
        return palm_geometry.palm_center_px(landmarks)
    got = tracker.update(landmarks, now_ms)
    # ⚠ Fall back to the palm rather than to nothing: a hand whose tips are not
    # all visible must still be able to hold and move an object. Losing a fingertip
    # is not losing the hand.
    return got if got is not None else palm_geometry.palm_center_px(landmarks)
