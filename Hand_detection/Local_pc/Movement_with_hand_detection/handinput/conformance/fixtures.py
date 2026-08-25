"""Deterministic synthetic hands -- the INPUT half of every conformance vector.

⭐⭐ SYNTHETIC ON PURPOSE, AND THIS IS A DECISION, NOT A SHORTCUT. Vectors cut from
the corpus would be better evidence of realism and WORSE evidence of correctness:
the corpus lives on an external drive that is not always awake (`wake_e_drive.py`
exists for exactly that), and a suite that cannot run is a suite nobody runs. These
fixtures are a closed form -- any language reproduces the inputs from the numbers
below, with no data file to ship and nothing to go stale.

⚠ THEY ARE NOT A CLAIM ABOUT REAL HANDS. They exercise the ARITHMETIC: sign
conventions, chirality, degenerate/edge-on conditioning, the rounding boundaries.
Realism is what the recorded corpus and the live takes are for, and the project
already has 24 suites plus `parity_replay` pointed at those.

Landmark indices are MediaPipe's 21-point model: 0 wrist; 1-4 thumb; 5-8 index;
9-12 middle; 13-16 ring; 17-20 pinky. ⚠ Image convention: y is DOWN.
"""
import math

# Canonical hand in a right-handed, y-UP unit frame, wrist at the origin, fingers
# along +y, knuckles along +x. One entry per landmark, in index order.
_CANONICAL = (
    (0.00, 0.00),                                            # 0  wrist
    (-0.34, 0.16), (-0.52, 0.38), (-0.60, 0.60), (-0.64, 0.80),   # 1-4  thumb
    (-0.33, 1.02), (-0.36, 1.42), (-0.38, 1.66), (-0.39, 1.86),   # 5-8  index
    (-0.11, 1.08), (-0.12, 1.54), (-0.13, 1.82), (-0.14, 2.04),   # 9-12 middle
    (0.11, 1.06), (0.13, 1.48), (0.14, 1.74), (0.15, 1.94),       # 13-16 ring
    (0.31, 0.98), (0.36, 1.32), (0.39, 1.52), (0.41, 1.68),       # 17-20 pinky
)


def pixel_hand(cx=320.0, cy=300.0, scale=90.0, roll_deg=0.0, mirror=False,
               width_squeeze=1.0):
    """21 pixel landmarks.

    `mirror` flips x about the wrist -- the difference between the two chirality
    cases. `width_squeeze` compresses the knuckle axis, which is what a YAW turn
    does in projection and what drives `edge_on_measure` toward 0.
    """
    a = math.radians(roll_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in _CANONICAL:
        x = -x if mirror else x
        x *= width_squeeze
        rx, ry = x * ca - y * sa, x * sa + y * ca
        out.append([round(cx + rx * scale, 6), round(cy - ry * scale, 6)])
    return out


def world_hand(scale=0.095, mirror=False, thumb_z=0.030, tilt_deg=0.0):
    """21 metric landmarks, palm roughly in the z=0 plane.

    ⭐ `thumb_z` IS THE CHIRALITY KNOB and is why the thumb is modelled at all:
    U7's `signed_palm_volume` is the determinant of [index_MCP-wrist,
    pinky_MCP-wrist, thumb_CMC-wrist], so the SIGN of the thumb's offset from the
    palm plane is the whole cue. Flip `thumb_z` and the hand is the other way up.
    """
    t = math.radians(tilt_deg)
    ct, st = math.cos(t), math.sin(t)
    out = []
    for i, (x, y) in enumerate(_CANONICAL):
        x = -x if mirror else x
        z = thumb_z / scale if i in (1, 2, 3, 4) else 0.0
        # rotate about the knuckle (x) axis: pitch the palm toward the camera
        yy, zz = y * ct - z * st, y * st + z * ct
        out.append([round(x * scale, 9), round(yy * scale, 9), round(zz * scale, 9)])
    return out


# The named cases every vector file iterates over. ⚠ Names are part of the
# contract: a port's failure report must be able to say WHICH case broke.
PIXEL_CASES = (
    ("upright", dict()),
    ("rolled_30", dict(roll_deg=30.0)),
    ("rolled_-75", dict(roll_deg=-75.0)),
    ("mirrored", dict(mirror=True)),
    ("near_edge_on", dict(width_squeeze=0.08)),          # yaw almost to edge-on
    ("small_far", dict(scale=38.0, cx=120.0, cy=90.0)),
    ("large_near", dict(scale=170.0, cx=520.0, cy=400.0)),
)

WORLD_CASES = (
    ("palm_to_camera", dict()),
    ("back_to_camera", dict(thumb_z=-0.030)),
    ("mirrored_palm", dict(mirror=True)),
    ("mirrored_back", dict(mirror=True, thumb_z=-0.030)),
    ("pitched_40", dict(tilt_deg=40.0)),
    ("thin_thumb", dict(thumb_z=0.002)),                 # near-degenerate chirality
)

FRAME_SIZE = (640, 480)
