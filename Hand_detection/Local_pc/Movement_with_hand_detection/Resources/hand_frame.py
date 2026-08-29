# -*- coding: utf-8 -*-
"""⭐⭐ `RB1` — THE FRAME. One viewpoint, applied to the landmarks, as a rotation.

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`.
Branch `1.7.42-`. ⚠ This REPLACES `camera_mount` for new work; that module stays
readable as the archive of what the 2026-08-28 build did, and is not imported here.

────────────────────────────────────────────────────────────────────────────────
⭐⭐⭐ THE PHYSICS, WHICH IS THE OWNER'S ARGUMENT (2026-08-29)

    *"if the hand is rotating around the vertical axis, any observer which watches
     the hand will see the hand rotating in the same direction ... Roll and pitch
     will be reversed if the camera and the user are watching in opposite
     directions."*

Two observers facing each other are related by a 180 deg rotation about the
VERTICAL -- NOT by a mirror:

    Ry180 = diag(-1, 1, -1)        det = +1, a PROPER ROTATION

    yaw   (0,1,0)   UNCHANGED     <- the vertical is SHARED
    pitch (1,0,0)   reversed
    roll  (0,0,1)   reversed

⛔⛔ THE INVARIANT, AND IT IS A TEST (`verify_frame_signs.py` §1): **ANY VIEWPOINT
THAT CHANGES THE SIGN OF YAW IS WRONG BY CONSTRUCTION.** The 2026-08-28 build
shipped `pitch_yaw`, which reverses yaw. One assertion would have killed it on day
one and there was no such assertion anywhere.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ WHY THE LANDMARKS AND NOT THE QUATERNION

`V1` applied the viewpoint as a QUATERNION CONJUGATION, to the orientation only.
Chirality, depth, occlusion and rendering all kept reading the raw frame -- so the
hybrid `V1` existed to remove was not removed, it MOVED ONE LAYER DOWN. That is the
stack whose composite came out a REFLECTION (det -1), which no rigid hand-to-object
correspondence can be.

⛔ `V1` rejected "negate the landmark z" for CORRECT reasons: it inverts `U7`'s
chirality determinant and `R1`'s camera-referenced occlusion.
⭐⭐ **But negate-z was never the right operation.** It is a reflection. `Ry180`
negates x AND z, is a rotation, and therefore CANNOT change handedness:

    operation        det   chirality      occlusion
    negate z alone   -1    INVERTED       broken
    Ry180            +1    PRESERVED      consistent (z flips coherently)

⭐ Measured on all three 2026-08-29 gripping takes: the palm determinant is
identical under both mounts (+5.883e-05 either way), and negate-z alone flips it.
`verify_frame_signs.py` §3 and §4 keep both facts.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE IMAGE MIRROR IS NOT HERE, AND MUST NOT COME BACK

A mirror is det -1. Composing it with a rotation is EXACTLY the determinant
mismatch that IS the hybrid. **Mirroring is a DISPLAY choice** -- see
`DISPLAY_MIRROR` at the bottom -- and belongs at draw time, nowhere else.

⚠ CONSEQUENCE, AND IT IS A REAL COST: MediaPipe's handedness label and
`palm_geometry.is_thumb_outward` are calibrated against the MIRRORED/APPARENT hand
(788/788 frames, 2026-08-01). Detecting un-mirrored changes what *apparent* means,
so both must be re-derived rather than carried over. `RB2` owns that.

PORT CONTRACT (`CONSTRAINTS` §2): stdlib only, no numpy, CLOCK-FREE. The only
non-pure line is the env read, once, at import.
"""
import math
import os

FACING_USER = "facing_user"
HEAD_WORN = "head_worn"
MOUNTS = (FACING_USER, HEAD_WORN)

# ⭐ `facing_user` is the hardware this game runs on: a desktop webcam looking at
# the player. `head_worn` is the glasses case, where the camera sees what the user
# sees and there is nothing to correct. ⛔ There is no `legacy`: the 2026-08-28
# behaviour is reachable by checking out the archive commit, not by a flag, because
# it was a hybrid rather than a viewpoint.
_ENV = os.environ.get("HAND_MOUNT", "").strip().lower()
MOUNT = _ENV if _ENV in MOUNTS else FACING_USER

WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 0, 5, 9, 13, 17
PALM = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)


def _m(mount):
    return MOUNT if mount is None else mount


def to_user_frame(world_landmarks, mount=None):
    """Landmarks in the USER's frame. The ONLY viewpoint transform in the pipeline.

    ⛔ `facing_user` applies `Ry180` -- negate x AND z. Negating z alone is a
    reflection and would invert chirality; negating x alone is the image mirror,
    which is a display concern. Only the pair is a rotation.
    ⚠ Returns a NEW list; the caller's landmarks are never mutated, because two
    consumers reading the same list with one of them transformed in place is the
    shape of the hybrid this module exists to end.
    """
    if world_landmarks is None:
        return None
    if _m(mount) == HEAD_WORN:
        # The camera sees what the user sees. Nothing to correct -- and this branch
        # is why the transform is a function and not a constant.
        return [tuple(p) for p in world_landmarks]
    return [(-p[0], p[1], -p[2]) for p in world_landmarks]


def yaw_is_invariant(mount=None):
    """⭐ Stated as code so it can be asserted, not just believed.

    Every mount in `MOUNTS` is a rotation about the VERTICAL, so none of them can
    change the sign of a yaw. A future mount that is not a vertical rotation must
    return False here and explain itself."""
    return _m(mount) in MOUNTS


def signed_palm_volume(world_landmarks):
    """⭐ CHIRALITY, as the determinant of the palm's own frame.

    ⛔ It is INVARIANT under every mount in this module, because every mount is a
    proper rotation -- and that invariance is the entire reason `Ry180` was chosen
    over negating z. Do not "fix" a chirality by flipping a viewpoint: if the two
    disagree, one of them is wrong and it is not the determinant.
    ⚠ Sign convention is anatomical and fixed by `RB2` against declared hands, NOT
    by MediaPipe's label -- which is measured 10.8% wrong (`U7`).
    """
    if world_landmarks is None:
        return None
    w = world_landmarks[WRIST]
    a = [world_landmarks[INDEX_MCP][k] - w[k] for k in range(3)]
    b = [world_landmarks[PINKY_MCP][k] - w[k] for k in range(3)]
    c = [world_landmarks[MIDDLE_MCP][k] - w[k] for k in range(3)]
    cx = (a[1] * b[2] - a[2] * b[1],
          a[2] * b[0] - a[0] * b[2],
          a[0] * b[1] - a[1] * b[0])
    return cx[0] * c[0] + cx[1] * c[1] + cx[2] * c[2]


# ⭐⭐ DISPLAY ONLY, AND THE NAME SAYS SO. The player should see themselves as in a
# mirror; that is a drawing decision and it must never reach the geometry. ⛔ It is
# deliberately NOT a function of `MOUNT`: coupling them is how the 2026-08-28 build
# came to take its mirror from one mounting and its depth from the other.
# ⚠ A renderer flips the IMAGE and the projected x of whatever it draws, together,
# at the last step. Nothing upstream may consult this.
DISPLAY_MIRROR = True


def rotvec_deg(q):
    """Quaternion -> (pitch, yaw, roll) in degrees, about x, y, z. SHORTEST ARC.

    ⛔⛔ THE `w < 0` CANONICALISATION IS LOAD-BEARING. `q` and `-q` are the SAME
    rotation and a least-squares fit returns whichever sign its eigenvector carries.
    On 2026-08-29 this exact omission made a 15 deg turn read as -345 deg and drove
    a correction to full strength on gestures that must receive none."""
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    ang = math.degrees(2.0 * math.atan2(n, w))
    return (x / n * ang, y / n * ang, z / n * ang)
