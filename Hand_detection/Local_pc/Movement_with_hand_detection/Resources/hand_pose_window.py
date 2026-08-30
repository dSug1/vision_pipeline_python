# -*- coding: utf-8 -*-
"""⭐⭐ `RB5` — WHERE IS THE HAND, AND DOES IT GET TO DRIVE? The pose window.

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md` §8sexies.
Branch `1.7.42-`.

The owner, 2026-08-30, specified the ranges in which the hand provides input, with
`0` on every axis meaning **the hand VERTICAL, PALM FACING THE CAMERA**:

    pitch  +15 -> +50 deg      (+ = fingertips toward the camera, palm tilting UP)
    yaw      0 -> +60 deg
    roll   -45 -> +45 deg

and outside them *"the delta increment shall not fire (smoothly and rapidly decaying
to zero gain)"*.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THOSE ARE **REAL** HAND ANGLES, AND NOTHING IN THIS FILE READS REAL ANGLES.

The owner chose real angles deliberately (2026-08-30). But a pose reading built from
the world landmarks is COMPRESSED against the real angle, by a factor that is neither
1 nor constant: the owner's ~80 deg of real yaw measured **~60 deg** on this reading,
and at the declared zero it read **-12 deg** (yaw) / **-14 deg** (pitch) rather than
0. So the owner's numbers may NOT be pasted into `WINDOW_*` below.

⭐ `analysis/rb5_window_calibration.py` measures the map -- declared real angle ->
this module's reading, per axis -- on a stepped, declared-angle take, and prints the
constants to paste here. ⛔ **`CALIBRATED` stays False until it has been run on an
UN-MIRRORED take**, and the placeholder values below are the pre-rebuild build's,
kept only so the module is runnable.

⛔ AND THIS IS A GATE, NOT A MEASUREMENT -- IT IS NOT `T6`. The empirical map feeds a
soft window EDGE; it never feeds the object's rotation. `SPEC_DELTA_ORBIT` §8bis drew
the line: *"good enough for a soft gate with a ~15 deg fade; not good enough for a
measurement."*

────────────────────────────────────────────────────────────────────────────────
⛔⛔⛔ THE TWO DEFECTS A REVIEW FOUND IN THE FIRST VERSION OF THIS FILE (2026-08-30),
AND BOTH WERE RE-INTRODUCTIONS OF DEFECTS THE PROJECT HAD ALREADY FIXED ONCE

**1. THE PALM NORMAL WAS CHIRALITY-ODD.** `cross(index_MCP -> pinky_MCP,
wrist -> middle_MCP)` uses the KNUCKLE ROW, which points the opposite anatomical way
on the two hands -- so the normal, and with it the pitch and yaw readings, came out
**negated on the left hand**. Measured: the same +20 deg physical yaw read `-20` on
the right and `+20` on the left. ⛔ With the owner's **asymmetric** windows
(pitch `+15..+50`, yaw `0..+60`) that gates the OPPOSITE motion on the left hand.
A chirality-odd palm normal was one of the four sign defects of 2026-08-29; this file
brought it back, and the golden suite missed it because §3 tested chirality on ROLL
only -- the one axis that never had the problem.

⭐ THE FIX: multiply the normal by the sign of `signed_palm_volume`, which flips with
exactly the same handedness. ⭐⭐ AND IT BUYS MIRROR-INVARIANCE FOR FREE, MEASURED:
a mirror flips the determinant AND the normal, so their product is unchanged --
`nz_corrected > 0` means *palm toward the camera* on a mirrored and an un-mirrored
capture alike.

**2. `abs(nz)` FOLDED THE READING PAST EDGE-ON.** With the back of the hand to the
camera, yaw +180 deg read **-0.0 deg with weights (1, 1, 1)** -- full gain, in the
most degenerate region there is, permanently integrated. ⛔⛔ This is exactly the
defect `SPEC_DELTA_ORBIT` §8bis records against `edge_on_measure`: *"~1.0 palm-on,
~0.15 at edge-on, and ~1.0 again with the BACK of the hand toward the camera ... the
SIGN is what v1 lacked."* Dropping `sign(nz)` re-opened it.

⭐ THE FIX: `palm_faces_camera()` is a **HARD gate on every axis**, never a fade.
Past edge-on the chirality sign flips, and in rate mode a flip is a permanent ~180
deg increment rather than a glitch that recovers next frame.

⭐⭐ MEASURED, ON DECLARED GROUND TRUTH, so the convention is not a guess:

    2026-08-29_202939_rb2_facing_right_palm   un-mirrored, declared RIGHT, PALM
        -> raw nz < 0 on 201/201 frames (median -0.929), is_right_hand 100%
    2026-08-29_122958_window_yaw_grip          MIRRORED, same physical pose
        -> raw nz > 0 on 839/839, determinant flipped too

so **corrected `nz > 0` == palm toward the camera** in both captures.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ THE ROLL READING, AND WHY IT NEEDED BUILDING AT ALL

`yaw` and `pitch` come from the palm normal's swing. ⛔⛔ **A ROLL CANNOT MOVE THE
PALM NORMAL, BECAUSE THE NORMAL *IS* THE ROLL AXIS** -- measured: on the roll take
the normal's yaw reading wandered **27 deg** while the hand only rolled. So the
owner's `-45..+45` roll window had no instrument.

⭐ Roll is read from the palm's LONG AXIS -- wrist -> middle MCP -- projected on the
IMAGE plane, i.e. from `x, y` ALONE. It never touches world `z`, which is why `ROLL`
is this project's precision axis. ⛔ It is **chirality-EVEN** as built: wrist ->
middle MCP runs wrist-to-knuckles on both hands. The knuckle row does not, and
`verify_hand_pose_window` keeps that as a counter-example it must FAIL on.

⚠ Its honest limit: a projected direction is foreshortened by yaw and pitch, so this
reading is contaminated by them. Tolerable for a gate, not for a measurement.

PORT CONTRACT (`CONSTRAINTS` §2): stdlib only, no numpy, CLOCK-FREE.
"""
import math

from . import hand_frame

WRIST = hand_frame.WRIST
INDEX_MCP = hand_frame.INDEX_MCP
MIDDLE_MCP = hand_frame.MIDDLE_MCP
PINKY_MCP = hand_frame.PINKY_MCP

# ⭐⭐ THE OWNER'S SPECIFICATION, IN THE OWNER'S UNITS. Kept as data so the
# calibration harness can quote it and a reader can see what the measured constants
# below are supposed to be an image OF. ⛔ Never gate on these directly.
OWNER_WINDOW_REAL_DEG = {
    "pitch": (15.0, 50.0),
    "yaw": (0.0, 60.0),
    "roll": (-45.0, 45.0),
}
OWNER_CUBE_SPAN_DEG = 180.0     # -90 .. +90 on every axis

# ⛔⛔ PLACEHOLDERS -- the pre-rebuild `delta_orbit` numbers in THIS module's units,
# not the owner's window. They keep the module runnable until the calibration take
# exists; `CALIBRATED` is the guard.
WINDOW_PITCH_DEG = (-45.0, 45.0)
WINDOW_YAW_DEG = (-60.0, 60.0)
WINDOW_ROLL_DEG = (-45.0, 45.0)
WINDOW_FADE_DEG = 15.0

# ⚠ Below this the palm's triple product is the sign of ~zero and the chirality
# correction above is a coin flip. Measured floor from `RB4`/`hand_identity`:
# palm-side p5 is 3.19e-05 and degenerate p95 is 2.57e-07, a two-order gap.
# ⛔ ABSOLUTE, in metres cubed -- a port that changes landmark scale must re-derive it.
CONFIDENT_DET = 3.0e-06

CALIBRATED = False
CALIBRATION_SOURCE = None

_ZERO_W = (0.0, 0.0, 0.0)


def palm_normal(world_landmarks, mount=None):
    """Unit palm normal in the USER's frame, ⭐ CHIRALITY-CORRECTED. `None` if degenerate.

    ⛔ The correction is the whole point -- see the header. The raw cross product is
    chirality-ODD and using it gates the two hands on opposite motions."""
    pts = hand_frame.to_user_frame(world_landmarks, mount=mount)
    if pts is None or len(pts) < 21:
        return None
    w, i, m, p = pts[WRIST], pts[INDEX_MCP], pts[MIDDLE_MCP], pts[PINKY_MCP]
    a = (p[0] - i[0], p[1] - i[1], p[2] - i[2])
    b = (m[0] - w[0], m[1] - w[1], m[2] - w[2])
    n = (a[1] * b[2] - a[2] * b[1],
         a[2] * b[0] - a[0] * b[2],
         a[0] * b[1] - a[1] * b[0])
    mag = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
    if mag < 1e-9:
        return None
    det = hand_frame.signed_palm_volume(world_landmarks)
    if det is None or abs(det) < CONFIDENT_DET:
        # ⛔ Not "assume right-handed and carry on". The determinant IS the sign this
        # correction needs, and where it collapses there is no correction to make.
        return None
    s = (1.0 if det > 0.0 else -1.0) / mag
    return (n[0] * s, n[1] * s, n[2] * s)


def palm_faces_camera(world_landmarks, mount=None):
    """Is the PALM toward the camera (rather than the back of the hand)? `None` if unknown.

    ⛔⛔ A HARD GATE, NEVER A FADE. Past edge-on the palm/back chirality sign flips;
    in absolute mode that is a glitch that recovers next frame, and in rate mode it
    is a ~180 deg increment integrated permanently. A fade would admit a fraction of
    it. `DR-2` already owns this bit."""
    n = palm_normal(world_landmarks, mount=mount)
    if n is None:
        return None
    return n[2] > 0.0


def roll_deg(world_landmarks, mount=None):
    """Roll reading: the palm's long axis, in the IMAGE plane. `None` if degenerate.

    ⭐ `x, y` only -- never world `z`. 0 deg is fingers UP. ⛔ Chirality-EVEN, unlike
    the knuckle row (see the header).
    ⚠ `+y is DOWN` in MediaPipe's world landmarks -- the wrist's y is GREATER than
    the middle MCP's on a fingers-up hand -- which is why the `-vy` appears. Pinned
    by a golden vector rather than left to a reader's memory."""
    pts = hand_frame.to_user_frame(world_landmarks, mount=mount)
    if pts is None or len(pts) < 21:
        return None
    w, m = pts[WRIST], pts[MIDDLE_MCP]
    vx, vy = m[0] - w[0], m[1] - w[1]
    if (vx * vx + vy * vy) < 1e-12:
        return None
    return math.degrees(math.atan2(vx, -vy))


def read(world_landmarks, mount=None, fade_deg=None):
    """⭐ ONE pass: `(angles, weights, facing)`. The single entry point for a frame.

    `angles` is `(pitch, yaw, roll)` or `None`; `weights` is per-axis in `[0, 1]`;
    `facing` is `palm_faces_camera`'s verdict.
    ⚠ It exists because the caller needs all three and each one costs a
    `to_user_frame` pass over 21 points -- the first version computed the set twice
    per frame, for every hand, forever."""
    n = palm_normal(world_landmarks, mount=mount)
    if n is None:
        return (None, _ZERO_W, None)
    r = roll_deg(world_landmarks, mount=mount)
    if r is None:
        return (None, _ZERO_W, None)

    facing = n[2] > 0.0
    nz = abs(n[2])
    angles = (math.degrees(math.atan2(n[1], nz)),
              math.degrees(math.atan2(n[0], nz)),
              r)
    if not facing:
        # ⛔ Past edge-on: the reading exists but nothing may be driven by it.
        return (angles, _ZERO_W, False)

    fade = WINDOW_FADE_DEG if fade_deg is None else fade_deg
    weights = (_smoothstep_out(angles[0], WINDOW_PITCH_DEG[0], WINDOW_PITCH_DEG[1], fade),
               _smoothstep_out(angles[1], WINDOW_YAW_DEG[0], WINDOW_YAW_DEG[1], fade),
               _smoothstep_out(angles[2], WINDOW_ROLL_DEG[0], WINDOW_ROLL_DEG[1], fade))
    return (angles, weights, True)


def pose_angles(world_landmarks, mount=None):
    """`(pitch, yaw, roll)` readings in degrees, or `None` on any degeneracy.

    ⛔ ALL-OR-NOTHING BY DESIGN. A partial answer would let a caller gate two axes on
    a reading and the third on a guess; an integrating build must refuse what it
    cannot vouch for."""
    return read(world_landmarks, mount=mount)[0]


def _smoothstep_out(value, lo, hi, fade):
    """1 inside `[lo, hi]`, 0 beyond it by `fade`, smooth between. Zero SLOPE at both

    ends -- `F1`'s trim died (§10.1) on being non-monotone in the declared angle, and
    a kink mid-gesture is felt.
    ⛔⛔ THE FADE IS **OUTSIDE** THE WINDOW, NOT INSIDE IT. The owner's sentence is
    directional: inside the range there is input, outside it decays. Fading inward
    from the edge would attenuate yaw right around FACE-ON -- the most reliable pose
    the estimator has -- which is the opposite of what the window is for."""
    if lo <= value <= hi:
        return 1.0
    over = (lo - value) if value < lo else (value - hi)
    if fade <= 0.0:
        return 0.0
    t = over / fade
    if t >= 1.0:
        return 0.0
    return 1.0 - (t * t * (3.0 - 2.0 * t))


def weights(world_landmarks, mount=None, fade_deg=None):
    """Per-axis gate weights `(w_pitch, w_yaw, w_roll)`, each in `[0, 1]`.

    ⛔ A degenerate or absent reading is a CLOSED gate -- `(0, 0, 0)` -- never an
    open one. In an absolute build a bad frame is a bad frame; here every frame is
    added to the object permanently.
    ⭐ PER-AXIS, by the owner's decision of 2026-08-30: one axis leaving its window
    must not silence the other two, because the pitch window excludes the neutral
    pose and a joint gate would make a resting grip drive nothing at all."""
    return read(world_landmarks, mount=mount, fade_deg=fade_deg)[1]
