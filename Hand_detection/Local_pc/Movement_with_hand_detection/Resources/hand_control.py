# -*- coding: utf-8 -*-
"""⭐⭐⭐ `RB5` — THE CONTROL LAW. The delta, gated, scaled, integrated. Nothing else.

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md` §8sexies.
Branch `1.7.42-`.

    delta   = between(previous palm pose, this one)      <- Horn, in the user frame
    v       = rotvec_deg(delta)                          <- (pitch, yaw, roll), degrees
    scaled  = (GAIN[i] * weight[i] * v[i] for i in 0..2)
    object <- from_rotvec_deg(scaled) (x) object         <- left-multiply, world frame

⛔ WHAT THIS DELIBERATELY IS NOT. No smoothing, no filter, no predictive term, no
lean trim, no fingertip trim, no rate curve, no deadzone, no per-axis SIGN. `1.7.42`
strips those and rebuilds each ONLY when a measurement asks (spec §6). The 2026-08-29
stack was locally reasonable at every layer and a REFLECTION as a whole.

⭐⭐ AND IT IS CLOCK-FREE, WHICH IS A CONSEQUENCE OF THE OWNER'S DECISION, NOT AN
ACCIDENT. *"Do not build two different gains based on velocity of hand rotation."*
With no velocity term there is no `dt`, so nothing here can drift with the frame
rate -- and the frame rate in this project is camera-bound and moves with the room
lighting (`L1`: 111 ms in good light, 149 ms in poor).

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE ONE THING THAT MAKES A CLUTCH A CATAPULT

A gated frame and a REFUSED frame are NOT the same, and treating them alike is how
an integrating build injects a rotation nobody performed:

  * **GATED** -- the pose reads fine, it is simply outside the owner's window.
    The increment is zero AND **the reference still advances**. That is the clutch:
    lift the mouse, move it, put it down. ⛔ If the reference did not advance, the
    first in-window frame after a long excursion would deliver the WHOLE excursion
    in one increment -- a catapult, permanently integrated.

    ⛔⛔ AND THE GATE READS **BOTH ENDS OF THE DELTA**, NOT JUST THE ARRIVAL POSE.
    A first version weighted each increment by the pose it ARRIVED at, and the
    golden vectors caught it immediately: a hand that rolls out of its window and
    comes back delivers the whole return leg, because the frame it lands on is
    in-window. Weighting by the DEPARTURE pose alone has the mirror defect on the
    way out. ⭐ So the effective weight is the **per-axis MIN of the two ends** --
    an increment that touches the outside is attenuated by the outside. `min` and
    not a product, so a wholly in-window increment stays at exactly 1.0.

  * **REFUSED** -- the landmarks or the pose reading are degenerate, so there is no
    trustworthy pose at all. ⚠ PAST EDGE-ON is NOT this case: the reading is fine,
    it is the POSE that is untrustworthy, so it is GATED (hard, every axis) and the
    reference still advances. That keeps the clutch across an excursion through
    edge-on instead of tearing it. The increment is zero and **the reference is DROPPED**.
    The next usable frame re-seeds and produces nothing. ⚠ That deliberately LOSES
    whatever real motion happened across the gap: a rotation measured across an
    unobserved interval is not measured, and in rate mode an invented one is kept
    forever. `SPEC_DELTA_ORBIT` §8bis: *"an integrating build must refuse what it
    cannot vouch for."*

⭐ `reset()` exists for the same reason and `F1` paid for the lesson: **every
per-hand estimator must die with its track** -- three were missing that reset, and a
stale reference across a re-acquisition is exactly a catapult.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE GAINS ARE NOT CALIBRATED YET, AND `CALIBRATED` IS THE GUARD.

The values below are the owner's NOMINAL gains -- `180 / (real-degree window span)`.
They are known to be WRONG applied to Horn's delta, which is compressed against the
real angle: the 2026-08-30 dry run measured them **1.7-3.1x out**. The real numbers
come from `analysis/rb5_window_calibration.py` on an UN-MIRRORED declared-angle take.
⚠ A build that ships with `CALIBRATED = False` is shipping the wrong gain.

PORT CONTRACT (`CONSTRAINTS` §2): stdlib only, no numpy, CLOCK-FREE.
"""
import math

from . import hand_orientation
from . import hand_pose_window as HPW

IDENTITY = hand_orientation.IDENTITY

# (pitch, yaw, roll) -- cube degrees per degree of HORN's reported delta.
# ⛔ PLACEHOLDERS: the owner's nominal `180 / real-window-span`. See the header.
GAIN = (5.143, 3.000, 2.000)

CALIBRATED = False
CALIBRATION_SOURCE = None

# ⚠ A single frame may not rotate the object further than this. It is NOT a rate
# curve and NOT a deadzone -- it is a guard against one corrupt frame being
# integrated permanently, which is the failure mode absolute control does not have.
# ⭐ Deliberately far above anything real: the measured per-frame delta is 0.3-2.4 deg
# and the largest gain here is ~5x, so ordinary motion never reaches it. It exists
# for the landmark-collapse frame, not for noise.
MAX_STEP_DEG = 45.0


# ⭐ IMPORTED, NEVER COPIED (`N6`). The log/exp pair and the quaternion product all
# live in `hand_orientation`; a second copy here is how two modules come to disagree
# about the same arithmetic, which this project has paid for more than once.
from_rotvec_deg = hand_orientation.from_rotvec_deg


def scaled_delta(delta_quat, weights, gain=None):
    """The increment the object actually receives. `IDENTITY` when fully gated.

    ⭐⭐ SCALED IN ROTATION-VECTOR SPACE, NEVER IN EULER ANGLES (`M6a`, queue `1.3`).
    The log map's three components are independent only for SMALL rotations, and a
    per-frame delta is 0.3-2.4 deg measured -- exact enough for an increment and
    hopeless for an absolute pose.
    ⛔ AND IT SCALES, IT NEVER REJECTS. A magnitude deadzone was MEASURED WORSE
    (43 -> 72 deg/min): the noise is a random walk whose small steps largely cancel,
    and rejecting them throws the cancellation away while keeping the excursions."""
    if delta_quat is None:
        return IDENTITY
    g = GAIN if gain is None else gain
    v = hand_orientation.rotvec_deg(delta_quat)
    out = [g[i] * weights[i] * v[i] for i in range(3)]
    mag = math.sqrt(sum(c * c for c in out))
    if mag > MAX_STEP_DEG:
        k = MAX_STEP_DEG / mag
        out = [c * k for c in out]
    return from_rotvec_deg(out)


def _normalise(q):
    """⚠ Renormalise EVERY frame. An integrator multiplies thousands of quaternions
    together and float error accumulates in the NORM, which shows up as the object
    slowly shearing rather than as an obviously wrong rotation."""
    n = math.sqrt(sum(c * c for c in q))
    if n < 1e-12:
        return IDENTITY
    q = tuple(c / n for c in q)
    return q if q[0] >= 0.0 else tuple(-c for c in q)


class ObjectRotationControl:
    """Carries the object's orientation and the previous hand pose. One per HAND.

    ⚠ One per hand, and it must be destroyed with the hand's identity -- see the
    header on `reset()`. `RB4` names hands from chirality and REFUSES a hand it
    cannot name; a refused hand must not drive an instance that belonged to another."""

    def __init__(self, orientation=IDENTITY):
        self._orientation = _normalise(orientation)
        self._ref = None
        # ⛔ The DEPARTURE pose's weights. Half of the both-ends rule; see the header.
        self._ref_w = None
        # ⭐ Counters, not logs: they make the gated/refused distinction VISIBLE in a
        # harness and on screen. A silent gate is indistinguishable from a dead one,
        # and this project has shipped an inverted build past an "end-to-end
        # confirmed" claim before.
        self.frames_driven = 0
        self.frames_gated = 0
        self.frames_refused = 0

    @property
    def orientation(self):
        return self._orientation

    def reset(self, orientation=None):
        """Drop the reference. ⛔ Call this when the hand's identity dies."""
        self._ref = None
        self._ref_w = None
        if orientation is not None:
            self._orientation = _normalise(orientation)

    def update(self, world_landmarks, mount=None, gain=None):
        """Advance one frame. Returns the object's new orientation.

        ⛔ THE ORDER HERE IS THE WHOLE MODULE. Read the pose FIRST: a refused pose
        must drop the reference, and a gated pose must advance it."""
        # ⭐ ONE pass. The first version called `weights` and `pose_angles`
        # separately, so every frame walked 21 landmarks through `to_user_frame`
        # twice over for an answer it already had.
        angles, pose_w, _facing = HPW.read(world_landmarks, mount=mount)
        readable = angles is not None
        state = hand_orientation.freeze(world_landmarks, mount=mount)

        if not readable or state is None:
            # REFUSED -- no trustworthy pose. Drop the reference so no increment
            # ever spans the gap.
            self._ref = None
            self._ref_w = None
            self.frames_refused += 1
            return self._orientation

        if self._ref is None:
            # First usable frame: a reference and nothing else. There is no
            # "previous" to take a delta from, and inventing one is a catapult.
            self._ref = state
            self._ref_w = pose_w
            self.frames_gated += 1
            return self._orientation

        delta = hand_orientation.delta(self._ref, world_landmarks, mount=mount)
        # ⛔⛔ BOTH ENDS. The increment is weighted by the per-axis MINIMUM of the
        # pose it left and the pose it arrived at -- see the header. Computed BEFORE
        # the reference advances, because it needs the departure pose.
        eff_w = tuple(min(self._ref_w[i], pose_w[i]) for i in range(3))

        # ⭐ THE REFERENCE ADVANCES WHATEVER THE GATE SAYS. This is the clutch.
        self._ref = state
        self._ref_w = pose_w

        if delta is None:
            self.frames_refused += 1
            return self._orientation

        inc = scaled_delta(delta, eff_w, gain=gain)
        # ⚠ "Driven" means the OBJECT MOVED, not merely that the gate was open. A
        # counter that says otherwise makes a silent gate look like a working one,
        # and this project has shipped an inverted build past an "end-to-end
        # confirmed" claim before.
        if inc == IDENTITY or hand_orientation.angle_deg(inc) < 1e-9:
            self.frames_gated += 1
            return self._orientation

        # ⚠ `compose(first, second)` applies `first` THEN `second`, i.e. it
        # left-multiplies `second` -- so this is `inc (x) orientation`, the
        # world-frame composition the design calls for.
        self._orientation = _normalise(hand_orientation.compose(self._orientation, inc))
        self.frames_driven += 1
        return self._orientation
