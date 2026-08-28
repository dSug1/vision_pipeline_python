"""⭐⭐ WHERE THE CAMERA IS RELATIVE TO THE USER'S EYES -- one setting, three modes.

Owner, 2026-08-28: *"I need to be able to port my game to vision glasses, and in
such case the camera view is aligned with the user view. Therefore I need to be
able to toggle the flip: camera worn by user = current setup, camera facing user
= this new setup"*.

⭐ SO THIS IS NOT A "FLIP" SWITCH. It is a statement about the HARDWARE, and every
sign in the pipeline that depends on the camera's placement is derived from it
here, in one place, rather than being spread across the tools (`L1`'s rule: a
tuning constant lives in exactly one module).

────────────────────────────────────────────────────────────────────────────────
⭐⭐⭐ THE FINDING THAT PRODUCED THIS MODULE: THE SHIPPED BUILD IS A HYBRID OF THE
TWO MOUNTINGS, AND THAT IS THE DEFECT.

A desktop webcam and the user look at the hands from OPPOSITE sides of the z
axis. The frame is mirrored before detection (`cv2.flip`, spec §14.3.4.3), so
after that flip:

    x  is in the USER's frame   -- your right hand appears on the screen's right
    z  is still in the CAMERA's frame

That mixed frame is a REFLECTION (determinant -1), which is not any physical
viewpoint at all. It is why the owner reported yaw and pitch reading backwards
while roll read correctly:

    conjugating a rotation by D = diag(1, 1, -1) maps
        R(n, theta)  ->  R((nx, ny, -nz), -theta)

    yaw   (n = (0,1,0))  -> REVERSED
    pitch (n = (1,0,0))  -> REVERSED
    roll  (n = (0,0,1))  -> UNCHANGED

⭐ That is exactly the symptom that was reported -- yaw and pitch named, roll not
-- which is what makes the diagnosis a prediction rather than a story.

Completing the mirror with a z negation makes the frame diag(-1, 1, -1), which is
a PROPER rotation (determinant +1): a 180 deg turn about the vertical, i.e.
literally the user's own viewpoint.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ THE THREE MODES, AND WHAT EACH ONE ACTUALLY CHANGES

    mount          mirror frame   orientation      depth from ratio   chirality
    ------------   ------------   --------------   ----------------   ---------
    facing_user    yes            (w,-x,-y,z)      grab * ratio       as today
    head_worn      NO             unchanged        grab / ratio       INVERTED
    legacy         yes            unchanged        grab / ratio       as today

`legacy` is the build as shipped on 2026-08-27. ⛔ It is NOT a supported
deployment -- it is the mirror of `facing_user` with the depth handling of
`head_worn`, which is the hybrid described above. It exists so `A10` and
`parity_replay` can reproduce the pre-change baseline EXACTLY, and so the owner
can A/B live instead of arguing. It is the DEFAULT until that live look happens.

⭐ Note what the table says about `head_worn`: on glasses the camera IS the user's
viewpoint, so nothing needs correcting -- the mirror comes OFF and the depth
mapping is already right. Today's depth handling was never wrong for a worn
camera; it was only ever wrong for a facing one.

────────────────────────────────────────────────────────────────────────────────
⭐ WHY THE ORIENTATION IS FIXED BY CONJUGATING A QUATERNION RATHER THAN BY
NEGATING EVERY LANDMARK z

The owner's first proposal was to negate `z` on every landmark. That is
PROVABLY EQUIVALENT for everything on screen, and this is the proof: Horn/Kabsch
minimises ||R a - b||, and with a' = Da, b' = Db (D orthogonal, D*D = I)

    ||R' D a - D b||  =  ||D (D R' D) a - D b||  =  ||(D R' D) a - b||

so the optimum obeys  R'_opt = D R_opt D  EXACTLY, and det(D R D) = det(R) = +1,
so it is still a rotation. Every frame builder in the pipeline conjugates the
same way (a frame F built from cross products satisfies F' = D F D), and the
cube's rotation is grab-relative, which conjugates too:

    R'_rel = (D R_now D)(D R_grab D)^T = D (R_now R_grab^T) D = D R_rel D

⛔ BUT NEGATING THE LANDMARKS ALSO INVERTS THREE THINGS THAT MUST NOT INVERT, and
each one is a scar this project already carries:

  * `signed_palm_volume` -- `U7`'s geometric chirality is a DETERMINANT over
    world z, so it changes sign. That is `U7`'s error class, which
    `HANDEDNESS_LABEL_DEFECT.md` records as having survived seven patches and
    `R1` records as having been committed again on 2026-08-27.
  * `depth_order.landmark_depths` and `fingertips.grip_depth_m` -- `R1`'s
    occlusion. These are METRES FROM THE CAMERA and must stay that way: the hand
    pixels being composited come from the camera, so a hand the camera sees in
    front must be drawn in front, whatever the user's viewpoint is.
  * every one of the 26 golden-vector suites and all 415 recordings, which are
    written in the camera's convention.

⭐ Conjugating the quaternion at the ONE point both tools finalise it reaches
every consumer of the orientation -- Horn, the raw fallback, and `handinput`'s
published pose -- and reaches nothing else. Same picture, none of the collateral.

⚠ WHAT THIS DELIBERATELY DOES NOT DO: it does not publish user-referenced
LANDMARKS. A future consumer that wants per-landmark z in the user's frame must
apply `user_view_world` itself. Doing it at ingest instead is a bounded follow-up
and needs exactly the three compensations listed above -- it is not free, which
is why it is not done here by default.

────────────────────────────────────────────────────────────────────────────────
Stdlib only, numpy-free, clock-free (`CONSTRAINTS` §2), so the port transliterates
it. Golden vectors: `analysis/verify_camera_mount.py`.
"""

import os

FACING_USER = "facing_user"
HEAD_WORN = "head_worn"
LEGACY = "legacy"

MOUNTS = (FACING_USER, HEAD_WORN, LEGACY)

# ⛔ THE DEFAULT IS `legacy` -- the build exactly as it shipped 2026-08-27 -- and it
# stays there until the owner has looked at `facing_user` live in BOTH tools.
# `METHOD.md`: automated green is necessary, not sufficient; a live look is what
# closes a change. Flip this line, or set CAMERA_MOUNT in the environment.
#
# ⚠ A port replaces this env read with its own config read. It is the only
# non-pure line in the module and it runs exactly once, at import.
_ENV = os.environ.get("CAMERA_MOUNT", "").strip().lower()
MOUNT = _ENV if _ENV in MOUNTS else LEGACY


def _m(mount):
    """Resolve `None` to the module setting. Every entry point takes an explicit
    `mount` so the golden vectors can exercise all three WITHOUT mutating global
    state -- `F1`'s void take came from a switch verified where it was SET rather
    than where it took EFFECT."""
    return MOUNT if mount is None else mount


def mirror_frame(mount=None):
    """Does the frame get `cv2.flip`-ed before detection?

    ⛔ The frame, never the coordinates. `REJECTED.md`: post-hoc `invert_x` was
    FALSIFIED -- MediaPipe is not mirror-equivariant, and the two routes disagree
    by 7.7-10 mm of world landmark and 12-20 deg of fitted rotation."""
    return _m(mount) != HEAD_WORN


# ⭐⭐ THE THREE VIEWPOINT CONJUGATIONS, AND WHY THERE ARE EXACTLY THREE.
#
# A change of viewpoint is a CONJUGATION `R -> Q R Q^T`. For a diagonal `Q` it maps
# the quaternion's vector part by the signs `-Q_diag`, and it reverses anything at
# all only when `det(Q) = -1`. There are exactly three such diagonal `Q`, and each
# reverses EXACTLY TWO of the three axes:
#
#     Q = diag( 1, 1,-1)   q -> (w,-x,-y, z)   reverses PITCH + YAW
#     Q = diag(-1, 1, 1)   q -> (w, x,-y,-z)   reverses YAW   + ROLL
#     Q = diag( 1,-1, 1)   q -> (w,-x, y,-z)   reverses PITCH + ROLL
#
# ⛔⛔ REVERSING ONE AXIS ALONE IS GEOMETRICALLY IMPOSSIBLE -- it would require
# `det(Q)` to be `+1` and `-1` at once. So "yaw is backwards" can never be fixed on
# its own; whichever option is right, a second axis moves with it. That is the fact
# that turns this from a guess into a three-way choice.
#
# ⚠ ALL THREE PRESERVE THE ROTATION ANGLE EXACTLY (they are conjugations by
# orthogonal matrices), so none of them can make the hand appear to turn further or
# less far. Only the DIRECTIONS differ.
VIEW_AXES = {
    "pitch_yaw": (-1.0, -1.0, 1.0),
    "yaw_roll": (1.0, -1.0, -1.0),
    "pitch_roll": (-1.0, 1.0, -1.0),
    "none": (1.0, 1.0, 1.0),
}

# ✅✅ SETTLED LIVE BY THE OWNER, 2026-08-28: `pitch_yaw`.
# *"the setup I closed with is the correct one"*, after cycling all four options
# with the 'm' key on one camera, one pose, no restarts.
#
# ⭐ SO THE MODULE HEADER'S DIAGNOSIS STANDS: the correction IS conjugation by
# `D = diag(1,1,-1)` -- the completion of the mirror with a `z` negation -- and it
# reverses PITCH and YAW while leaving ROLL alone.
#
# ⛔⛔ A STORY WRITTEN HERE EARLIER IS RETRACTED. When `yaw_roll` was briefly the
# default it was argued to be "the one with the cleanest physical meaning" -- the
# inverse of the `cv2.flip` mirror, since a bathroom mirror preserves nodding and
# reverses turning and tilting. That reasoning is sound about MIRRORS and WRONG
# about this pipeline, and it was reached by working backwards from a live report
# rather than forwards from the geometry. Kept because a tidy physical story is
# exactly the kind of thing that gets believed twice.
#
# ⚠⚠ HOW THIS WAS NEARLY DECIDED WRONGLY -- THE REUSABLE PART. Three options were
# tried one-per-restart and the three reports came out MUTUALLY INCONSISTENT:
#
#     run 1  pitch_yaw  (P,Y,R)=(1,1,0)  wrong: yaw          => yaw should be 0
#     run 2  pitch_roll (1,0,1)          wrong: yaw, roll    => yaw 1, roll 0
#     run 3  yaw_roll   (0,1,1)          wrong: roll, pitch  => pitch 1, roll 0
#
# Runs 2 and 3 agreed (pitch reverse, roll keep -> yaw FORCED to reverse, because a
# conjugation reverses exactly two axes). Run 1 dissented, and run 1 was right about
# nothing -- it was the FIRST look, and the open YAW-LEAN defect makes the cube ROLL
# WHILE IT YAWS by up to ~27 deg, so yaw and roll cannot be judged independently by
# eye on a single pose.
#
# ⭐⭐⭐ THE METHOD RULE: WHEN ONE OPTION PER RESTART PRODUCES INCONSISTENT REPORTS,
# THE PROBLEM IS THE INSTRUMENT, NOT THE OBSERVER. A/B ON ONE POSE INSTEAD.
# The 'm' key was built for exactly that and settled in ONE session what three had
# failed to. ⚠ And it matters here specifically because a KNOWN defect couples two
# of the three axes being judged -- when the axes are not separable, asking for a
# per-axis verdict asks for something the eye cannot give.
_AXES_ENV = os.environ.get("CAMERA_VIEW_AXES", "").strip().lower()
VIEW_AXIS_MODE = _AXES_ENV if _AXES_ENV in VIEW_AXES else "pitch_yaw"

# ⚠⚠ THE THREE LIVE REPORTS CONTRADICT EACH OTHER ON YAW, AND THE START POINT
# ABOVE IS AN INFERENCE, NOT A VERDICT. One option was run per restart; each report
# named the axes that looked wrong:
#
#     run 1  pitch_yaw  (P,Y,R)=(1,1,0)  wrong: yaw          => yaw should be 0
#     run 2  pitch_roll (1,0,1)          wrong: yaw, roll    => yaw 1, roll 0
#     run 3  yaw_roll   (0,1,1)          wrong: roll, pitch  => pitch 1, roll 0
#
#   pitch -> reverse      (consistent)
#   roll  -> do NOT       (consistent, twice)
#   yaw   -> runs 1 and 2 DIRECTLY CONTRADICT
#
# ⭐ A conjugation must reverse EXACTLY TWO axes, so pitch-reversed + roll-kept
# FORCES yaw-reversed: `pitch_yaw`. Runs 2 and 3 agree on it; only run 1 dissents.
#
# ⚠ AND THERE IS A KNOWN REASON RUN 1's YAW CALL IS THE SUSPECT ONE: the open
# yaw-lean defect makes the cube ROLL WHILE IT YAWS (up to ~27 deg), so yaw and roll
# cannot be judged independently by eye on one pose. Run 1 was the first look.
#
# ⛔ That is an argument for which option to TRY FIRST -- nothing more. Dismissing
# a contradicting observation is exactly the error made earlier in this same row
# (see `chirality_v_negative_is_left`). The debug tool's 'm' key now cycles the
# options LIVE so the owner can settle yaw by direct A/B in one session instead of
# one-guess-per-restart, which is what produced the contradiction.


def user_view_quat(q, mount=None, axes=None):
    """The same rotation, expressed from the USER's side of the hand.

    Applies one of the three conjugations above -- see `VIEW_AXES`. Identity for
    every mount whose camera already shares the user's viewpoint.

    ⚠ Involution: applying it twice returns the original quaternion."""
    if q is None or _m(mount) != FACING_USER:
        return q
    sx, sy, sz = VIEW_AXES[axes or VIEW_AXIS_MODE]
    return (q[0], sx * q[1], sy * q[2], sz * q[3])


def user_view_world(world_landmarks, mount=None):
    """Per-landmark world coordinates in the USER's frame -- `z` negated.

    ⚠⚠ NOT WIRED INTO EITHER TOOL, and that is deliberate: see the header. It is
    provided so a future consumer (a game layer, a port, a new gesture) can ask
    for user-referenced landmarks explicitly rather than re-deriving the sign.
    ⛔ Do NOT feed its output to `depth_order`, `fingertips.grip_depth_m` or
    `palm_geometry.signed_palm_volume` -- those three are camera-referenced by
    design and inverting them is what this module exists to prevent.

    ⚠ Involution, like `user_view_quat`."""
    if world_landmarks is None or _m(mount) != FACING_USER:
        return world_landmarks
    out = []
    for w in world_landmarks:
        if w is None or len(w) < 3:
            out.append(w)
        else:
            out.append((w[0], w[1], -w[2]))
    return out


def depth_from_ratio(grab_depth_m, ratio, mount=None):
    """4.2's Z-translation mapping: where the held object's depth goes, given the
    apparent-palm-span ratio against its own grab-time baseline.

    ⭐ `ratio > 1` means the palm looks BIGGER, which always means NEARER THE
    CAMERA. What changes with the mount is what that means for the USER:

      * camera facing the user -- nearer the camera is FURTHER FROM THE USER, so
        the object must recede:            depth = grab * ratio
      * camera worn by the user -- nearer the camera is nearer the user, so the
        object must approach:              depth = grab / ratio

    ⚠ Multiplicative either way, and that is forced rather than chosen: the hand's
    own depth is known only up to an unknown scale, so a ratio is the only
    quantity the sensor supplies. Both forms are 1.0 at the grab frame by
    construction, which is what keeps §14.1's no-pop guarantee.

    ⛔ The RESULT stays METRES FROM THE CAMERA in every mode -- it must, because
    `projected_size_px` and `depth_order` both consume it. Only the DIRECTION the
    hand drives it changes."""
    if grab_depth_m is None or ratio is None or ratio <= 0.0:
        return grab_depth_m
    if _m(mount) == FACING_USER:
        return grab_depth_m * ratio
    return grab_depth_m / ratio


def chirality_v_negative_is_left(mount=None):
    """`palm_geometry.CHIRALITY_V_NEGATIVE_IS_LEFT` -- MOUNT-INDEPENDENT. Always True.

    ⛔⛔ RETRACTED 2026-08-28, THE SAME DAY IT WAS WRITTEN. This first returned
    `mirror_frame(mount)`, on the reasoning that `signed_palm_volume` is a
    DETERMINANT and so flips sign when the frame is unmirrored. That half is true.
    The error was forgetting that **the target flips too**, so the two cancel:

      `geometric_chirality` REPLACES MediaPipe's handedness label, so it must say
      what MediaPipe would say about THE FRAME IT WAS FED. On a mirrored frame a
      physical RIGHT hand looks left-handed and MediaPipe calls it 'Left'; on an
      unmirrored one it calls it 'Right'. The volume's sign flips with the mirror
      and the wanted answer flips with the mirror. Net: no correction at all.

    ⭐⭐ HOW IT WAS CAUGHT, AND THE LESSON. `verify_geometric_chirality` FAILED
    under `head_worn` and said `V<0 -> 'Left'` had become `'Right'` -- it was
    reporting this defect exactly. It was misread as the fixture being bound to
    the mirrored convention, and SILENCED with a mount guard. The owner then found
    it by eye in one live run: *"the mentions left and right hands are inversed in
    the user worn"*.

    ⛔ That is `METHOD.md`'s rule inverted and it is worth keeping: the standing
    warning is that a harness can report CLEAN on a broken build -- this is the
    other direction, a harness reporting a REAL defect and being explained away.
    **Suspecting the instrument is not the same as dismissing it.** A guard may
    only be added once the fixture's claim has been re-derived independently and
    shown to be about a convention rather than a defect.

    ⭐ What IS genuinely mount-dependent is `hand_identity.anatomical_name` -- the
    DISPLAY swap, which exists to undo the mirror and must not run when there is
    no mirror. That is the real half of what the owner saw."""
    return True
