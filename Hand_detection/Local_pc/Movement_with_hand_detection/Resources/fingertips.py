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
USE_TIP_BARYCENTER = False

# ⚠ ONE COPY, imported by both tools (`CONSTRAINTS` §4 / N6). A tuning constant
# that exists twice is how the two pipelines drift.
GRIP_FILTER_ENABLED = True


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


def grip_position_px(tracker, landmarks, now_ms):
    """⭐ THE ONE ENTRY POINT both tools call. Palm centre when the step is off.

    ⛔ When `USE_TIP_BARYCENTER` is False this returns exactly what the shipped
    pipeline used -- `palm_geometry.palm_center_px(landmarks)` -- so the off state
    is the old behaviour rather than an approximation of it.
    """
    if not USE_TIP_BARYCENTER:
        return palm_geometry.palm_center_px(landmarks)
    got = tracker.update(landmarks, now_ms)
    # ⚠ Fall back to the palm rather than to nothing: a hand whose tips are not
    # all visible must still be able to hold and move an object. Losing a fingertip
    # is not losing the hand.
    return got if got is not None else palm_geometry.palm_center_px(landmarks)
