"""B4 -- the PALM ANCHOR: a held object rides the palm block, not the fingers.

⭐⭐ READ THIS FIRST -- THE MEASURED WINNER IS `Arm2D` (arm B), AT THE BOTTOM
    OF THIS FILE, AND IT IS THE 2D FORMULATION, NOT THE 3D-NATIVE ONE ABOVE IT.

    Both are implemented. On the 2026-08-06/07 purpose-built takes, pitch axis:

                                    p95     max   stillMax    SINK
        §14.1 incumbent            5.09   13.57      4.81    -0.807
        Arm2D  (arm B, 2D)         8.11   25.07      4.64    -0.000   <- WINNER
        PalmAnchor (3D-native)    27.80   72.22     36.43    -0.420

    ⭐ The 3D-native design below was built on the argument that using the palm
    quaternion is "free, because it is computed every frame anyway". IT IS NOT
    FREE: it costs the DEGENERACY of that 3D frame, which collapses at edge-on --
    exactly where the anchor is needed, and exactly where pitch drives the hand.
    Arm B never touches the 3D reconstruction at all.

    **For the ANCHOR, staying in 2D pixel space is not a limitation but a
    shield.** The 3D-native class is kept because its Z-retrofit reduction is
    proven (`verify_palm_anchor.py` §5) and because the null result is worth
    preserving -- not because it is the recommendation.

The rest of this docstring describes the 3D-native `PalmAnchor` class.


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


# ==========================================================================
# ⭐⭐ ARM B -- §16.5's original 2D formulation, and the MEASURED WINNER.
# ==========================================================================
class Arm2D:
    """A held object rides the palm's own 2D frame, in PIXELS.

        at grab:   o, ex, ey, s  from the palm landmarks (all pixel-space)
                   d = X_G - o
                   R = ( d.ex / s , d.ey / s )        <- frozen, scale-free
        every t:   P = o_t + s_t * ( R.x * ex_t + R.y * ey_t )

      o   palm centroid (landmarks 0, 5, 9, 13, 17)
      ex  unit vector along the knuckle row, index-MCP -> pinky-MCP
      ey  perpendicular to ex, in the image plane
      s   palm width in pixels          (`use_scale=False` freezes it = arm C)

    ⭐⭐ WHY THIS BEATS THE 3D-NATIVE VERSION, and it is the opposite of what
    was predicted (§16.11 argued 3D-native was "free" because the palm
    quaternion is computed every frame anyway). Measured on the purpose-built
    takes, pitch axis:

                                    p95     max   stillMax    SINK
        §14.1 incumbent            5.09   13.57      4.81    -0.807
        ARM B                      8.11   25.07      4.64    -0.000
        3D-native (palm + Horn)   27.80   72.22     36.43    -0.420

    Arm B NEVER TOUCHES THE 3D RECONSTRUCTION. Its axis is a pixel direction and
    its scale is a pixel width, so both foreshorten with the projection for free
    -- while the 3D palm frame DEGENERATES at edge-on, which is exactly where the
    anchor is needed and exactly where pitch drives the hand. **For the anchor,
    staying in 2D is not a limitation, it is a shield.**

    ⭐ AND IT KILLS THE SINK ON EVERY AXIS -- yaw 0.000, pitch -0.000, depth
    -0.001, back-of-hand 0.000, against §14.1's -0.656 / -0.807 / -0.589 /
    -0.083. That reproduces §16.5's arm-B result (0.005 / 0.001) on takes that
    actually contain the conditions, which §16.4's takes did not.

    ⚠ THE COST, stated plainly: jitter p95 rises ~30-70% on yaw, pitch and
    back-of-hand (unchanged on depth) and max rises similarly. The worst
    STILL-HAND step does NOT degrade (pitch 4.81 -> 4.64, back 3.56 -> 3.44).
    A systematic drift is the defect the operator reported; jitter is not (§16.5).

    ⚠ `use_scale=False` (arm C) is kept because the A/B is the reason this exists
    -- and it is measurably WRONG: it fixes neither axis (yaw -0.745, depth
    -0.873). The scale term is what decouples the sink.

    ⚠⚠ WHAT THIS WILL COST WHEN THE Z-AXIS ARRIVES — read before extending it.
    (Full version: `Claude/HANDOFF_ANCHOR_ROTATION.md` §3.)

    `R` is a 2-VECTOR in palm-frame units, so a cube CANNOT be held in front of
    or behind the palm. When Z-axis translation lands:

        R      (a, b)          ->  (a, b, c)      c = out-of-plane offset
        frame  ex, ey (pixels) ->  needs ez = ex x ey, i.e. a 3D palm frame
        scale  palm width px   ->  a real projection

    ⭐ THE ONE DECISION THAT MAKES THIS CHEAP IS ALREADY TAKEN: `R` IS
    SCALE-FREE — stored in palm widths, not pixels. That is what survives the
    transition; a pixel offset would not. Adding a third component is additive.

    ⚠ BUT THE THIRD AXIS REINTRODUCES EXACTLY WHAT THIS CLASS AVOIDS. `ez` can
    only come from the palm's 3D reconstruction — the channel that degenerates
    at edge-on, which is why the 3D-native `PalmAnchor` above loses (pitch
    still-max 36.43 vs this class's 4.64). So the retrofit is NOT "add a
    component"; it is "add a component whose axis is unreliable in precisely
    the band this class was built to survive". Plan for `c` to need its own
    reliability treatment — a DR-2-style freeze in the edge-on band — not just
    a slot in a tuple.

    ⛔ And the real blocker is not the formula: it is ABSOLUTE DEPTH. MediaPipe's
    world landmarks are hand-RELATIVE (metric shape, origin at the hand, no world
    position), so the cube's depth does not exist anywhere in the data. That is
    identical for every anchor design, §14.1's included.

    ⭐ WEB/MOBILE PORT: this class is already port-clean (stdlib, numpy-free,
    deterministic, no side effects). `analysis/verify_palm_anchor.py` §8 is its
    executable specification — a reimplementation is correct when it reproduces
    those vectors and UNTRUSTED until it does (queue U3). ⚠ Do not edit the
    expectations to match a port. Neither this class nor `palm_rotation` rounds
    today; if a port adds rounding, use `hand_identity._round_half_up`'s
    convention — JS `Math.round` is half-up, Python's `round()` is banker's.
    """

    def __init__(self, use_scale=True):
        self.use_scale = use_scale
        self.name = "arm_B" if use_scale else "arm_C"

    @staticmethod
    def frame(pixel_landmarks):
        """(origin, ex, ey, palm width) in pixels, or None if degenerate."""
        o = HB.palm_position(pixel_landmarks)
        s = HB.palm_scale(pixel_landmarks)
        if o is None or not s or s < 1e-6:
            return None
        try:
            dx = pixel_landmarks[HB.PINKY_MCP][0] - pixel_landmarks[HB.INDEX_MCP][0]
            dy = pixel_landmarks[HB.PINKY_MCP][1] - pixel_landmarks[HB.INDEX_MCP][1]
        except (IndexError, TypeError):
            return None
        n = math.hypot(dx, dy)
        if n < 1e-6:
            return None
        ex = (dx / n, dy / n)
        return o, ex, (-ex[1], ex[0]), s

    def freeze(self, object_pos_px, pixel_landmarks, world_landmarks=None):
        f = self.frame(pixel_landmarks)
        if f is None:
            return None
        o, ex, ey, s = f
        d = (object_pos_px[0] - o[0], object_pos_px[1] - o[1])
        return {"a": (d[0] * ex[0] + d[1] * ex[1]) / s,
                "b": (d[0] * ey[0] + d[1] * ey[1]) / s,
                "s0": s}

    def apply(self, state, pixel_landmarks, world_landmarks=None):
        if state is None:
            return None
        f = self.frame(pixel_landmarks)
        if f is None:
            return None
        o, ex, ey, s = f
        k = s if self.use_scale else state["s0"]
        a, b = state["a"], state["b"]
        return (o[0] + k * (a * ex[0] + b * ey[0]),
                o[1] + k * (a * ex[1] + b * ey[1]))
