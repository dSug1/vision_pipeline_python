# -*- coding: utf-8 -*-
"""⭐⭐ DELTA-ORBIT (`DO1`/`DO2`/`DO3`) — the object's rotation as an INTEGRAL.

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_DELTA_ORBIT.md`.
Branch `1.7.41-Hand-delta-orbit`, owner 2026-08-29.

⚠ POSITION IS NOT IN SCOPE. The object keeps following the hand exactly as `F1`
shipped it. This module changes ROTATION only.

────────────────────────────────────────────────────────────────────────────────
WHAT CHANGES: A CONTROL LAW, NOT PLUMBING

Today the object's rotation is already a delta -- but measured from the GRAB:

    delta       = q_eff(t) . q_eff(grab)^-1        <- absolute, w.r.t. the grab
    target      = delta . cube_at_grab

`DO` replaces the SOURCE of that delta with a per-frame increment:

    d(t)        = q_eff(t) . q_eff(t-1)^-1         <- an increment
    cube       <- scale(d(t), gain) . cube

⭐ That is position control -> RATE control, the same distinction as mouse-absolute
vs mouse-look, and everything below follows from it.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE CONSEQUENCE THAT DECIDES THE DESIGN: ERROR INTEGRATES

In absolute mode a bad frame is a bad frame and the next good frame recovers. Here
every frame's error is added to the object PERMANENTLY.

⭐ MEASURED on the 2026-08-29 gripping takes, integrating across declared holds --
the hand is STILL, so every degree is error the object keeps:

    YAW 43 deg/min    PITCH 35 deg/min    ROLL 48 deg/min

⚠ These three are NOT affected by the `geo_deg` halving found the same day: the
drift probe composed quaternions and read the angle with `2*acos(|w|)`, which was
correct. The noise/signal tables below WERE halved and are the corrected values.

⛔⛔ AND A MAGNITUDE DEADZONE MAKES IT WORSE, WHICH IS THE OPPOSITE OF THE OBVIOUS
FIX AND WAS MEASURED THREE TIMES:

    deadzone      none     0.5 deg/frame     1.0 deg/frame
    YAW        43/min        58/min            72/min

⭐⭐ WHY: the noise is a RANDOM WALK whose small steps largely CANCEL. A deadzone
rejects the small steps, throws the cancellation away, and keeps only the large
excursions. **THE CURVE MUST SCALE, NEVER REJECT.** Scaling is safe because it
scales both directions equally.
⚠ This is the one line of the owner's Unity reference that must NOT be copied:
`if (appliedDelta.sqrMagnitude < 0.0001f) return;` is a reject.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ THE DRIFT CONTROL IS THE SHIPPED `FREEZE`, AND NOTHING ELSE CAN DO IT

`RELEASE 60 deg/s` + `FREEZE 1` (shipped with `R1`, live-accepted) gates on HAND
SPEED. During the measured holds the hand moved 14-24 deg/s, comfortably below it,
so the freeze suppresses the whole of the drift above.

⛔⛔ NO OTHER MECHANISM CAN, BECAUSE NOISE AND SLOW SIGNAL ARE THE SAME SIZE:

    declared HOLD (noise)   vs   declared MOVE (signal),  deg/frame p50 / p95
    YAW    0.62 / 1.45           0.66 / 1.50
    PITCH  0.98 / 3.14           1.16 / 3.22
    ROLL   0.71 / 1.86           1.00 / 2.78

⭐⭐⭐ THERE IS NO KNEE THAT PASSES THE SIGNAL AND BLOCKS THE NOISE. Above ~80 deg/s
you are clear of the noise; below ~50 deg/s you are inside it, and nothing
downstream recovers what is not in the signal.

⚠ SO THE RATE CURVE IS NOT A NOISE DISCRIMINATOR. An earlier draft of this design
claimed it was; the table above is what retracted that. **Two jobs, two mechanisms:
the FREEZE handles noise, the curve handles feel.**
⭐ It costs less than it sounds: for fine control you do not move slower, you use a
lower gain. Precision is CD gain, not creeping -- which is how a mouse has always
worked.

────────────────────────────────────────────────────────────────────────────────
⛔ NO EULER (`M6a`, queue `1.3`)

The Unity reference works in `desiredAngles.x/.y` and `Quaternion.Euler`. Porting
that reintroduces gimbal lock and breaks a constraint currently satisfied.
⭐ The translation is the ROTATION VECTOR (log map), and it is well-conditioned HERE
for a reason that does not hold for absolute pose: its three components are
independent only for SMALL rotations, and a per-frame delta is 0.3-2.4 deg.

────────────────────────────────────────────────────────────────────────────────
PORT CONTRACT (`CONSTRAINTS` §2): stdlib only, no numpy, and CLOCK-FREE --
`now_ms` and `dt_ms` are passed in, exactly like `hand_state` and `mate_connector`.
"""
import math

# ⭐⭐⭐ EVERY ONE OF THESE IS A SLIDER, AND THAT IS AN OWNER DECISION, NOT a default
# waiting to be replaced (2026-08-29): *"build sliders instead of fixing arbitrary
# values so I can finetune the ranges later on during debug."*
#
# ⛔ NO VALUE HERE IS DERIVED. Only `KNEE_DEG_S` carries a measured constraint, and
# it is ONE-SIDED -- see below. The two gains are FEEL, and this project settles
# feel live: `V2`'s 0.66 took 19 homed trials, `L1`'s tau a full sweep.
#
# ⭐ `L1`'s rule: a tuning constant lives in ONE module. The debug tool's sliders
# write THESE names; production reads them and has no sliders. That is what keeps
# `parity_replay` meaningful.

# ⭐⭐⭐ DELTA-ORBIT IS THE BUILD, NOT AN OPTION ON TOP OF THE OLD ONE.
#
# Owner, 2026-08-29, rejecting a first draft that defaulted to the legacy path:
# *"I do not want to have a mix of hand follow and integral of hand motion. I want
# pure integral of hand motion since the beginning with no interference of what we
# previously built."*
#
# ⚠ THE FIRST DRAFT WAS NOT ACTUALLY A MIX -- `ORBIT_GAIN` was a hard switch, and
# no frame ever had both paths contributing. But it defaulted to the OLD path, so
# the build only became itself when a slider was moved, and it carried a THIRD
# gain multiplying the two `RATE` ones. Both are gone.
#
# ⭐ THE SHAPE IS `V1`'s, WHICH THE OWNER ALREADY ACCEPTED FOR EXACTLY THIS
# SITUATION: the new behaviour is the DEFAULT and the only one the product runs;
# the old one survives ONLY as a named diagnostic baseline, because `A10` requires
# that the pre-change build stay reachable bit-for-bit and `parity_replay` needs
# something to compare against. `CAMERA_MOUNT=legacy` is the precedent.
#
# ⛔ `legacy` IS NOT A DEPLOYMENT. It reproduces the 1.7.40 absolute path -- the
# object's rotation COPIES the hand's, referenced to the grab -- and exists so a
# measurement can be repeated, never so the game can ship with it.
ORBIT = "orbit"
LEGACY = "legacy"
MODES = (ORBIT, LEGACY)

# ⚠ The only non-pure line in the module, and it runs exactly once, at import --
# the same contract `camera_mount` states. A port replaces it with its own config
# read.
import os as _os
_ENV = _os.environ.get("DELTA_ORBIT", "").strip().lower()
MODE = _ENV if _ENV in MODES else ORBIT

# Cube-per-hand for ORDINARY motion -- the precision setting. < 1 means the object
# turns LESS than the hand, which is what assembly-style alignment argues for.
RATE_LO = 0.50
# Cube-per-hand for FAST strokes -- travel, and the clutch.
# ⭐ THE RATIO hi/lo IS THE CLUTCH STRENGTH: a fast stroke out at `hi` and a slow
# return at `lo` leave net rotation behind. That is how anyone crosses a screen
# without lifting the mouse, and it is why no separate clutch gesture is needed.
RATE_HI = 1.50
# ⛔ THE ONE CONSTANT WITH A MEASURED CONSTRAINT, and it is one-sided:
# **above ~80 deg/s the hand is clear of the noise band; below ~50 deg/s it is
# inside it.** Putting the knee low does not buy fine control -- it opens the gate
# to jitter that is the same size as the signal there.
# ⚠ 90, not 60: the first draft said 60, from numbers a HALVED helper produced
# (`lean_trim_ab.geo_deg` returned the S3 geodesic, which is half the rotation
# angle -- found and fixed 2026-08-29 by `verify_delta_orbit` §4). 60 sat BELOW
# the corrected noise band, i.e. on the wrong side of the one constraint this
# constant has.
KNEE_DEG_S = 90.0
# How sharply the curve turns. 1.0 = a straight ramp between lo and hi.
# ⚠ Higher is twitchier and clutches harder; this is feel, hence a slider.
CURVE_SHAPE = 1.0

# ⛔ `DO3` -- THE WINDOW, AND IT IS A HARD GATE, NEVER A FADE.
# Past edge-on the palm/back chirality sign flips. In ABSOLUTE mode that is a
# visible glitch that recovers next frame; **in RATE mode it is a ~180 deg
# increment integrated PERMANENTLY.** A fade would admit a fraction of it.
# ⭐ The threshold is `palm_geometry.EDGE_ON_THRESHOLD`; it is NOT repeated here --
# the caller passes the measure in, so there is exactly one owner of that number.
#
# ⚠ The INSIDE of the window needs no fade: on the 2026-08-29 gripping takes the
# noise is FLAT across everything tested (yaw 1.09-2.56, pitch 1.09-4.77, roll
# 1.35-2.55 deg p95). ⛔ The OUTER edge has never been located -- the takes reached
# only ~57 deg (yaw) / ~75 deg (pitch) of measured pose, and the region where the
# old corpus collapses is 120-180. `DO4` is that gap.

# ⭐⭐⭐ `DO3` v2 -- THE PER-AXIS POSE WINDOW (owner, 2026-08-29, on the first
# live run). The v1 gate used `palm_geometry.edge_on_measure` alone and the owner
# found it does not work:
#
#   *"in yaw rotation, when the hand is almost edge facing the camera, it shall not
#    contribute to any input ... I can still rotate the cube around yaw when hand is
#    edge-on and even further palm facing the camera."*
#
# ⛔⛔ THE CAUSE: `edge_on_measure` IS SYMMETRIC. It measures knuckle-row
# SQUARENESS -- ~1.0 palm-on, ~0.15 edge-on, and **~1.0 again with the BACK of the
# hand showing**. So a threshold on it kills a thin band at edge-on and then
# RE-OPENS COMPLETELY past it. It cannot tell "palm toward me" from "back toward
# me", which is also the most likely source of the owner's second report, that the
# cube's PITCH sometimes runs opposite the hand's.
#
# ⭐ THE REPLACEMENT: THE PALM NORMAL, SPLIT PER AXIS.
#     yaw_pose   = atan2(nx, |nz|)     horizontal swing of the normal
#     pitch_pose = atan2(ny, |nz|)     vertical swing
#     sign(nz)                          palm toward the camera, or away
# The sign is what v1 lacked, and it makes the past-edge-on region a HARD ZERO
# instead of a re-opened gate.
#
# ⭐ MEASURED on the 2026-08-29 gripping takes, per declared hold:
#     YAW take,   declared 0 -> ~80 deg : yaw_pose  -12 -> -60 deg, MONOTONE
#     PITCH take, declared 0 -> ~90 deg : pitch_pose -14 -> +60 deg, MONOTONE
#                                         and yaw_pose stays -14 -> -10 (clean split)
#
# ⚠⚠ AND ITS HONEST LIMIT, MEASURED THE SAME WAY: on the ROLL take the normal's
# yaw reading wanders **27 deg** while the hand only rolls -- and a roll cannot move
# the palm normal at all, because the normal IS the roll axis. That is MediaPipe's
# world-`z` error leaking in. **So this is good enough for a SOFT GATE with a
# ~15 deg fade, and not good enough for anything finer.** Do not build a
# measurement on it.
#
# ⛔ The thresholds are in NORMAL-SWING degrees, which read COMPRESSED against the
# hand's real angle (the owner's ~80 deg of yaw reads ~60 here) -- the same
# compression every depth-derived reading in this project shows. They are sliders,
# so the owner tunes the felt edge rather than trusting the mapping.
WINDOW_YAW_DEG = 60.0        # ~ the owner's "0 to 80 degrees" of hand yaw
WINDOW_PITCH_DEG = 45.0      # ~ the owner's "0 to 60 or 70 degrees" of hand pitch
# "a smooth and rapid decay to zero" (owner). ⚠ NOT a hard cliff: a step would put
# a discontinuity in the middle of a gesture, and `F1`'s own trim died on §10.1 for
# being non-monotone in the declared angle.
WINDOW_FADE_DEG = 15.0

# ⭐⭐⭐ PER-AXIS SIGN OF THE CONTROL MAPPING (owner, 2026-08-29, after the live
# A/B: *"yaw and roll are right: the cube follows the hand's rotation direction.
# pitch is mirrored. I think we just need to introduce a quaternion multiplication
# to revert the pitch if camera is facing the user."*)
#
# ⛔⛔ AND IT CANNOT LIVE IN `camera_mount`, WHICH IS WHY IT IS HERE. A viewpoint
# change is a CONJUGATION, and a conjugation reverses **exactly two** axes -- that
# is `camera_mount`'s own recorded finding, the one that made its search finite,
# because `det(Q)` cannot be +1 and -1 at once. All three conjugations are already
# tabulated there and NONE gives "pitch reversed, yaw and roll as-is". The owner's
# report is therefore not reachable by any mount setting.
#
# ⭐ RATE CONTROL IS WHAT MAKES IT LEGAL. `step` already scales the increment's
# per-axis components (that is the pose window); a sign is the same operation with
# a gain of -1 instead of a gain in [0,1]. It is a CONTROL MAPPING, not a change of
# coordinates, so the determinant argument does not bind it.
#
# ⚠⚠ WHAT IT COSTS, STATED SO IT IS CHOSEN KNOWINGLY: the object no longer
# RIGIDLY follows the hand. Pure pitch is exactly right; a COMPOUND motion (yaw and
# pitch together, about a diagonal axis) turns the object about the MIRRORED
# diagonal. Increments are small so nothing is discontinuous and the integral stays
# a valid rotation -- but it is a reflection of the correspondence, not a rotation
# of it, and diagonal turns are where it would be felt.
# ⚠ It exists ONLY in rate mode. The same trick is not well defined on `legacy`'s
# accumulated absolute rotation, so `DELTA_ORBIT=legacy` keeps the old behaviour.
#
# ⛔ NOT tied to `CAMERA_MOUNT` in code, deliberately. The owner said *"if camera
# is facing the user"*, and that is the mount this game runs -- but the mount is
# already a setting, and making one setting silently rewrite another is how the
# 2026-08-28 hybrid (mirror from one mounting, depth from the other) happened. This
# is its own switch, and a port that finds a different sign changes it here.
AXIS_SIGN = (-1.0, 1.0, 1.0)     # (pitch, yaw, roll)

IDENTITY = (1.0, 0.0, 0.0, 0.0)


def _qmul(p, q):
    w1, x1, y1, z1 = p
    w2, x2, y2, z2 = q
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def _qnorm(q):
    n = math.sqrt(sum(c * c for c in q))
    if n < 1e-12:
        return IDENTITY
    return tuple(c / n for c in q)


def _to_rotvec(q):
    """Quaternion -> rotation vector (axis * angle, radians), SHORTEST ARC.

    ⛔⛔ THE `w < 0` CANONICALISATION IS LOAD-BEARING AND IT IS NOT DEFENSIVE
    CODING. `q` and `-q` are the SAME rotation, and `horn_rotation` returns
    whichever sign its largest-eigenvalue eigenvector carries. On 2026-08-29 this
    exact omission in `lean_trim.twist_angle_deg` made a 15 deg turn read as
    -345 deg and drove `authority` to 1.0 on gestures that must receive none.
    ⭐⭐ HERE IT WOULD BE WORSE: a delta read the long way round is a ~360 deg
    increment INTEGRATED PERMANENTLY, where the absolute build merely glitched for
    one frame. `analysis/verify_delta_orbit.py` feeds negated quaternions for this
    reason."""
    w, x, y, z = _qnorm(q)
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    ang = 2.0 * math.atan2(n, w)
    return (x / n * ang, y / n * ang, z / n * ang)


def _from_rotvec(v):
    ang = math.sqrt(sum(c * c for c in v))
    if ang < 1e-12:
        return IDENTITY
    s = math.sin(ang / 2.0) / ang
    return (math.cos(ang / 2.0), v[0] * s, v[1] * s, v[2] * s)


def delta_of(q_now, q_prev):
    """The per-frame increment: what the hand did SINCE THE LAST FRAME.

    ⚠ Right-multiplied by the inverse of the previous pose, so the result is in the
    same frame the object's own rotation lives in -- composing it on the left of the
    object's rotation then means "turn the object by what the hand just did"."""
    if q_now is None or q_prev is None:
        return IDENTITY
    return _qnorm(_qmul(q_now, _qconj(q_prev)))


def speed_deg_s(delta, dt_ms):
    """Angular speed implied by this increment. ⚠ TIME-BASED, never per-frame:
    `L1` replaced a per-frame 0.35 with a time constant precisely because the feel
    of a per-frame number moves with the room lighting (which moves the frame rate).
    A rate curve keyed on deg/FRAME would drift the same way."""
    if dt_ms is None or dt_ms <= 0.0:
        return 0.0
    v = _to_rotvec(delta)
    return math.degrees(math.sqrt(sum(c * c for c in v))) * 1000.0 / dt_ms


def rate_gain(speed, lo=None, hi=None, knee=None, shape=None):
    """The CD-gain curve: how much object-rotation per unit of hand-rotation.

    ⛔ IT IS NOT A NOISE GATE. It never returns 0, and it must not: noise and slow
    deliberate motion are the SAME SIZE (see the header), so a curve that rejected
    the noise would reject the signal with it -- and rejecting increments breaks the
    random walk's own cancellation, which measured WORSE than doing nothing.
    ⭐ Its job is feel. The FREEZE is what stops a still hand from driving anything.
    """
    lo = RATE_LO if lo is None else lo
    hi = RATE_HI if hi is None else hi
    knee = KNEE_DEG_S if knee is None else knee
    shape = CURVE_SHAPE if shape is None else shape
    if knee <= 0.0:
        return hi
    t = speed / knee
    if t <= 0.0:
        return lo
    if t >= 1.0:
        return hi
    # ⚠ A plain power ramp, deliberately: it is monotone in the speed, continuous at
    # both ends, and has ONE shape parameter. `F1`'s own trim died on §10.1 for
    # being NON-MONOTONE in the declared angle, and that is the property being
    # protected here.
    return lo + (hi - lo) * (t ** shape)


def palm_normal(world_landmarks):
    """Unit palm normal in the CAMERA frame, from the world landmarks.

    ⚠ The same construction `signed_palm_area` uses in 2-D, kept in 3-D:
    `cross(index_MCP -> pinky_MCP, wrist -> middle_MCP)`. Returns `None` when the
    landmarks are degenerate, and the caller must treat that as "no window
    information" rather than as an open gate."""
    try:
        w = world_landmarks[0]
        i, m, p = world_landmarks[5], world_landmarks[9], world_landmarks[17]
    except (IndexError, TypeError):
        return None
    a1 = (p[0] - i[0], p[1] - i[1], p[2] - i[2])
    b1 = (m[0] - w[0], m[1] - w[1], m[2] - w[2])
    n = (a1[1] * b1[2] - a1[2] * b1[1],
         a1[2] * b1[0] - a1[0] * b1[2],
         a1[0] * b1[1] - a1[1] * b1[0])
    mag = math.sqrt(sum(c * c for c in n))
    if mag < 1e-9:
        return None
    return (n[0] / mag, n[1] / mag, n[2] / mag)


def _fade(value, full, fade):
    """1 inside `full`, 0 beyond `full + fade`, smooth between."""
    if fade <= 0.0:
        return 1.0 if value <= full else 0.0
    t = (value - full) / fade
    if t <= 0.0:
        return 1.0
    if t >= 1.0:
        return 0.0
    # ⭐ smoothstep, so the weight leaves 1 and reaches 0 with zero SLOPE. A linear
    # ramp is continuous but kinks at both ends, and a kink mid-gesture is felt.
    return 1.0 - (t * t * (3.0 - 2.0 * t))


def pose_window(normal, palm_facing, yaw_deg=None, pitch_deg=None,
                fade_deg=None):
    """Per-axis weights from the hand's POSE: `(w_pitch, w_yaw, w_roll)`.

    ⛔⛔ PAST EDGE-ON IS A HARD ZERO ON EVERY AXIS. With the BACK of the hand
    toward the camera the landmarks collapse (`T1`, MediaPipe #5156) and the
    chirality bit is degenerate. In the absolute build that was a visible glitch
    that recovered; here an increment taken there is integrated permanently.

    ⛔⛔ `palm_facing` IS PASSED IN, AND DERIVING IT FROM `nz` WAS A REAL DEFECT
    (2026-08-29). A first version tested `nz * facing_sign <= 0` with a single
    constant sign. **The palm normal is CHIRALITY-ODD** -- `cross(index_MCP ->
    pinky_MCP, wrist -> middle_MCP)` points out of the PALM for one hand and out of
    the BACK for the other -- so one constant cannot serve both. Measured on
    `2026-08-27_195429_solid`, on frames where the PALM faces the camera:

        RIGHT hand   nz > 0 in  98.1%     (nz is POSITIVE)   n=321
        LEFT  hand   nz > 0 in   0.2%     (nz is NEGATIVE)   n=1183

    ⛔ So the whole LEFT hand returned `(0, 0, 0)` on every frame and could not
    rotate anything at all. The owner found it in one run.

    ⛔⛔ AND THE FIX FOR THAT INTRODUCED A WORSE ONE, THE SAME DAY: `palm_facing`
    was fed straight from `last_known_thumb_outward`, and **`is_thumb_outward`
    returns True when the hand shows its BACK** (`palm_geometry`, calibrated
    2026-08-01 against 788/788 known-facing frames). The polarity was inverted, so
    the gate opened only while the palm was HIDDEN -- **no rotation at all, on
    either hand**, which is how the owner reported it. The caller must pass
    `not thumb_outward`.
    ⭐⭐ BOTH DEFECTS WERE THE SAME MISTAKE: a boolean whose meaning was assumed
    from its name instead of read from its definition -- once for the normal's
    sign, once for the cue's polarity. `verify_delta_orbit` §6b now pins the
    polarity against `palm_geometry.is_thumb_outward` itself, so neither can
    return quietly.
    ⚠ `palm_geometry`'s own comment states this outright -- *"that normal points
    out of the BACK for one chirality and out of the PALM for the other"* -- and it
    was read during this build and not applied.

    ⭐ THE FIX IS NOT A SECOND SIGN CONSTANT. The caller passes the pipeline's OWN
    palm/back cue (`last_known_thumb_outward`), which is chirality-aware, hysteresis
    -tracked, and already recorded per frame. `METHOD`: **record and reuse what ran;
    never re-derive it** -- a recomputation is a second implementation that can
    silently disagree, and it did here.

    ⭐ THE ANGLES BELOW ARE CHIRALITY-SAFE without any of that: negating the normal
    flips `nx` and `nz` together, and `abs()` of the resulting angle is unchanged.
    Only the palm-vs-back question ever needed the hand's identity.

    ⭐ ROLL IS NEVER GATED. Measured flat at every pose on both the gripping roll
    take (1.35-2.55 deg p95) and the 2026-08-23 card take -- roll is the axis that
    never touches world `z`, so it has no bad region to exclude.
    """
    yd = WINDOW_YAW_DEG if yaw_deg is None else yaw_deg
    pd = WINDOW_PITCH_DEG if pitch_deg is None else pitch_deg
    fd = WINDOW_FADE_DEG if fade_deg is None else fade_deg
    if normal is None:
        # ⛔ No pose information is NOT an open gate. An integrating build must
        # refuse what it cannot vouch for.
        return (0.0, 0.0, 1.0)
    if palm_facing is None or not palm_facing:
        # ⛔ Back of the hand, or no cue at all: nothing here is trustworthy, and an
        # integrating build must refuse what it cannot vouch for.
        return (0.0, 0.0, 0.0)
    nx, ny, nz = normal
    az = abs(nz)
    w_yaw = _fade(abs(math.degrees(math.atan2(nx, az))), yd, fd)
    w_pitch = _fade(abs(math.degrees(math.atan2(ny, az))), pd, fd)
    return (w_pitch, w_yaw, 1.0)


def step(cube_quat, q_now, q_prev, dt_ms, edge_on=None, edge_on_threshold=None,
         lo=None, hi=None, knee=None, shape=None, window=None):
    """One frame of PURE RATE CONTROL: return the object's new rotation.

    ⛔ THERE IS NO MASTER GAIN AND NO BLEND. The object's rotation is the integral
    of the hand's, scaled by the rate curve and nothing else -- the caller decides
    whether to call this at all (`MODE`), and if it does, this is the whole law.

    ⛔⛔ `DO3` -- THE HARD EDGE-ON GATE. When the caller reports the palm is
    edge-on, the increment is dropped ENTIRELY (not faded): the chirality sign is
    degenerate there, and a sign flip integrated in rate mode is permanent.
    """
    if cube_quat is None:
        return cube_quat
    if (edge_on is not None and edge_on_threshold is not None
            and edge_on < edge_on_threshold):
        return cube_quat
    d = delta_of(q_now, q_prev)
    v = _to_rotvec(d)
    if v == (0.0, 0.0, 0.0):
        return cube_quat
    k = rate_gain(speed_deg_s(d, dt_ms), lo, hi, knee, shape)
    # ⭐⭐ `DO3` -- THE PER-AXIS WINDOW, APPLIED IN ROTATION-VECTOR SPACE. The
    # three components of a SMALL rotation's log ARE its three axis contributions,
    # so weighting them independently is exact enough for a per-frame increment --
    # the same construction `lean_trim.trim` already uses to scale swing.
    # ⚠ Order is (x, y, z) = (pitch, yaw, roll): x is the knuckle axis, y the
    # vertical, z the optical axis.
    wp, wy, wr = window if window is not None else (1.0, 1.0, 1.0)
    # ⭐ The per-axis SIGN rides the same multiplication as the window weight --
    # one place decides how much of each axis reaches the object, and in which
    # direction. See `AXIS_SIGN` for why this cannot live in `camera_mount`.
    sp, sy, sr = AXIS_SIGN
    scaled = _from_rotvec((v[0] * k * wp * sp,
                           v[1] * k * wy * sy,
                           v[2] * k * wr * sr))
    return _qnorm(_qmul(scaled, cube_quat))
