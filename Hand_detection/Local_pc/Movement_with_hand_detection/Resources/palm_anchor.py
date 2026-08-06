"""B4 -- the PALM ANCHOR: a held object rides the palm block, not the fingers.

3D-NATIVE BY CONSTRUCTION, rendered in 2D until real depth exists (owner
decision, 2026-08-04). See "THE Z RETROFIT" at the bottom: when depth arrives,
one function changes and the frozen state does not.


THE DEFECT THIS REPLACES (§16.10, measured on a 450 s live take)
----------------------------------------------------------------
Today's anchor (§14.1) is a fixed linear combination of NINE landmark pixel
positions -- 5 FINGERTIPS + 4 MCPs -- with the weights frozen at grab by inverse
distance from the cube. Consequence, measured:

    with the 5 palm landmarks moving < 0.5 px  (i.e. the palm is STILL),
    the 9-landmark anchor still moves  p50 0.570 px, p95 1.701, MAX 17.51 px
    -- an amplification of 1.66x.

Because the frozen weights include fingertips, ANY finger flex moves the cube.
Even grabbing at the palm centroid -- the most MCP-favourable case there is --
the fingertips carry a median 27% of the total weight (p95 42%), and they are
the 13-32% CV landmarks (§0.2) against the palm's 2.76 mm rigidity.

⚠ This is not palm noise leaking through. The anchor DELIBERATELY INCLUDES the
noisiest points on the hand, by a §14.1 design chosen to fix a different problem
(the translation pivot). It is the same defect §16.5 measured as |r| = 0.822
yaw-sink and 0.323 pitch-sink.

⭐ This module REMOVES a layer rather than adding one: the palm position and the
palm frame are already computed every frame for other purposes.


THE FORMULATION
---------------
    at grab:   R3  = Rot_G^-1 . ( X_G - o_G )       metres, in the PALM's frame
    every t:   P_t = o_t(px) + k_t . proj_xy( Rot_t . R3 )

  R3     the frozen offset. ⭐ A METRIC 3-VECTOR IN THE PALM'S OWN FRAME -- the
         single most important choice here, and the one that makes the Z
         retrofit free. Pixel offsets and 2D palm-frame units do NOT survive it.
  Rot_t  the palm's 3D orientation, columns (e1, e2, e3) from `hand_blocks.
         palm_frame` -- ALREADY COMPUTED EVERY FRAME for cube rotation.
  o_t    the palm centroid in pixels (the 5 palm landmarks).
  k_t    metres -> pixels, by weak-perspective fit (see below).

⭐ ROTATING IN 3D AND PROJECTING AFTERWARDS gives correct ANISOTROPIC
foreshortening for free: as the palm tilts, the part of the offset that rotates
out of the image plane is dropped by `proj_xy`, so the projected offset shortens
along the axis actually being tilted. A scalar 2D scale term cannot do that --
it shrinks everything isotropically, which is very likely why §16.5 measured
arm B as 2.5x noisier under yaw (jitter p95 5.486 vs §14.1's 2.235).

NO-POP IS EXACT, not approximate: at t = G, Rot_G . R3 = X_G - o_G identically,
so P_G = X_G to floating-point. §14.1's `grab_residual_offset` existed only
because inverse-distance weighting does not interpolate through the query point;
it is not needed here and has no counterpart.


⚠⚠ WHY k IS NOT PALM WIDTH -- MEASURED, NOT ASSUMED
----------------------------------------------------
The obvious metres->pixels scale is the apparent palm width. It COLLAPSES:

                          p50      CV     r(edge_on)   edge-on -> open
    palm width, PIXELS   91.5 px  25.8%     +0.601        0.320   <- 3x collapse
    palm width, WORLD    0.064 m  18.5%     +0.002        0.993
    weak-perspective k   1403     28.9%     +0.091        0.809

⭐ THE PALM NEVER ACTUALLY COLLAPSES -- ONLY ITS PROJECTION DOES. In metric
space it is the same hand at every pose (r = +0.002). So a scale built from the
projection alone inherits the projection's degeneracy, while one that FITS the
known 3D shape to the observed 2D points does not: it knows the palm is rotated.

`weak_perspective_scale` is the least-squares scale mapping world-xy offsets onto
pixel offsets over the 5 palm landmarks. MediaPipe's world landmarks are
hand-relative but CAMERA-ALIGNED, so they foreshorten exactly as the pixels do
and the ratio stays stable. Residual noise (CV ~29%) is comparable to palm
width's but is POSE-INDEPENDENT -- and noise can be smoothed (`scale_alpha`),
whereas a collapse cannot be recovered from.

⚠ 0.809 is not 1.000: about a fifth of the collapse survives. This is an
improvement, not a cure, and it must be reported per-band rather than pooled.


⚠ THE HONEST COST, NAMED BEFORE THE FIRST MEASUREMENT
------------------------------------------------------
§14.1's anchor is PURELY POSITIONAL -- it does not depend on orientation at all.
This one makes cube POSITION depend on the palm quaternion, which is built from
the 4-landmark frame that §0.18 identifies as the LEAST reliable signal on the
hand (back-of-hand collapse, Google issue #5156). Translation is thereby coupled
to the worst-behaved channel. Arm B already did this implicitly and still removed
the sink, so this is a reason to MEASURE before porting -- specifically in the
back-of-hand and edge-on bands -- not a reason to avoid it.


THE Z RETROFIT (deferred, and this is what makes it cheap)
-----------------------------------------------------------
⛔ What is missing for true 3D is NOT this formula: it is ABSOLUTE DEPTH.
MediaPipe's world landmarks are hand-RELATIVE -- metric shape, origin at the
hand, no world position -- so `o_t`'s z-component does not exist anywhere in the
data. That is the Z-translation item's problem and it is identical for every
anchor design, including §14.1's.

When depth arrives:
    R3       unchanged -- already a metric 3-vector
    Rot_t    unchanged -- already the 3D palm frame
    o_t      gains a real z
    proj_xy + k_t  -> replaced by a real perspective projection. ONE FUNCTION.
The frozen state stored on the Cube does not change at all.

`analysis/verify_palm_anchor.py` locks this: it asserts that with the offset
confined to the image plane this module reproduces the 2D similarity form
EXACTLY, so the generalisation is provable rather than hopeful (the U3 golden-
vector discipline that caught a real banker's-vs-half-up rounding divergence).

Stdlib only, numpy-free, deterministic, no side effects -- the port contract.
"""

import math

try:                                        # imported, never copied (N6): the
    from . import hand_blocks as HB         # palm frame MUST stay identical to
except ImportError:                         # the one the rest of the pipeline
    import hand_blocks as HB                # uses, or the two silently diverge.

PALM_LANDMARKS = HB.PALM_LANDMARKS          # (0, 5, 9, 13, 17)

# EMA on k. 1.0 = off (raw fit). k's noise is pose-INDEPENDENT, so unlike palm
# width it is legitimate to smooth -- but it is off by default so the A/B
# measures the anchor, not the smoother.
SCALE_ALPHA = 1.0

# Below this the weak-perspective fit is not trustworthy (a degenerate palm
# projection). The caller is told, rather than being handed a wild number.
MIN_SCALE = 1e-6


def _sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def palm_origin_px(pixel_landmarks):
    """The palm centroid, in pixels -- `o_t`. Same 5 points as `hand_blocks`."""
    return HB.palm_position(pixel_landmarks)


def weak_perspective_scale(pixel_landmarks, world_landmarks, indices=None):
    """Least-squares metres -> pixels scale `k`, from the palm's own geometry.

    Fits the single scale that best maps world-xy offsets onto pixel offsets:

        k = SUM (w_i - w_bar).(p_i - p_bar)  /  SUM |w_i - w_bar|^2

    over the palm landmarks. ⚠ NOT palm width -- see the module docstring for
    the measurement that rules palm width out (it collapses 3x edge-on; this
    collapses 0.809x).
    """
    idx = PALM_LANDMARKS if indices is None else indices
    try:
        n = float(len(idx))
        pbx = sum(pixel_landmarks[i][0] for i in idx) / n
        pby = sum(pixel_landmarks[i][1] for i in idx) / n
        wbx = sum(world_landmarks[i][0] for i in idx) / n
        wby = sum(world_landmarks[i][1] for i in idx) / n
    except (IndexError, TypeError, ZeroDivisionError):
        return None
    num = den = 0.0
    for i in idx:
        dwx = world_landmarks[i][0] - wbx
        dwy = world_landmarks[i][1] - wby
        num += dwx * (pixel_landmarks[i][0] - pbx) + dwy * (pixel_landmarks[i][1] - pby)
        den += dwx * dwx + dwy * dwy
    if den < 1e-18:
        return None
    k = num / den
    return k if k > MIN_SCALE else None


class AnchorState:
    """What is frozen at grab. ⭐ `offset` is METRES IN THE PALM'S OWN FRAME --
    the representation that survives the Z retrofit untouched."""

    __slots__ = ("offset", "k_smoothed")

    def __init__(self, offset):
        self.offset = offset            # (a, b, c) metres, palm frame
        self.k_smoothed = None          # EMA state, only if scale_alpha < 1


class PalmAnchor:
    """Stateless apart from optional k smoothing. One instance may serve many
    cubes: all per-grab state lives in the `AnchorState` the caller stores."""

    def __init__(self, scale_alpha=SCALE_ALPHA, use_scale=True):
        self.scale_alpha = scale_alpha
        # use_scale=False pins k to its grab value -- the "arm C" of §16.5,
        # kept selectable because that A/B is the reason this module exists.
        self.use_scale = use_scale

    # ------------------------------------------------------------------ frame
    @staticmethod
    def basis(world_landmarks):
        """(e1, e2, e3) -- the palm's 3D orientation. None if degenerate."""
        f = HB.palm_frame(world_landmarks)
        return None if f is None else (f[0], f[1], f[2])

    def _scale(self, state, pixel_landmarks, world_landmarks):
        k = weak_perspective_scale(pixel_landmarks, world_landmarks)
        if k is None:
            return state.k_smoothed if state is not None else None
        if state is not None and self.scale_alpha < 1.0:
            prev = state.k_smoothed
            k = k if prev is None else (self.scale_alpha * k
                                        + (1.0 - self.scale_alpha) * prev)
            state.k_smoothed = k
        return k

    # ------------------------------------------------------------------- grab
    def freeze(self, object_pos_px, pixel_landmarks, world_landmarks):
        """Capture the offset at grab. Returns AnchorState, or None if the palm
        geometry is degenerate this frame (the caller must then not grab)."""
        o = palm_origin_px(pixel_landmarks)
        e = self.basis(world_landmarks)
        k = weak_perspective_scale(pixel_landmarks, world_landmarks)
        if o is None or e is None or not k:
            return None
        # The cube's pixel offset, taken to metres. z = 0: with no depth in the
        # data the cube is coplanar with the palm, which is exactly the
        # assumption the Z retrofit will lift -- and the only one it needs to.
        d = ((object_pos_px[0] - o[0]) / k, (object_pos_px[1] - o[1]) / k, 0.0)
        # Express it in the PALM's frame: Rot^-1 . d = (d.e1, d.e2, d.e3),
        # since (e1, e2, e3) is orthonormal.
        st = AnchorState((_dot3(d, e[0]), _dot3(d, e[1]), _dot3(d, e[2])))
        st.k_smoothed = k
        return st

    # ------------------------------------------------------------------ track
    def apply(self, state, pixel_landmarks, world_landmarks):
        """Where the object should be this frame, in pixels. None if degenerate
        (the caller should hold the previous position rather than jump)."""
        if state is None:
            return None
        o = palm_origin_px(pixel_landmarks)
        e = self.basis(world_landmarks)
        if o is None or e is None:
            return None
        k = self._scale(state, pixel_landmarks, world_landmarks)
        if not k:
            return None
        if not self.use_scale:
            k = state.k_smoothed or k
        a, b, c = state.offset
        # Rot_t . R3, then drop z -- the orthographic projection that makes the
        # foreshortening anisotropic and correct.
        vx = a * e[0][0] + b * e[1][0] + c * e[2][0]
        vy = a * e[0][1] + b * e[1][1] + c * e[2][1]
        return (o[0] + k * vx, o[1] + k * vy)
