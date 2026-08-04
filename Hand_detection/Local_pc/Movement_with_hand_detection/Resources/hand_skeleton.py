"""M2b -- impose a fixed-bone-length skeleton instead of measuring one (item 1.7).

⚠⚠ PARKED 2026-08-04. THE FIT WORKS; IT CANNOT HELP T1/T2, BY CONSTRUCTION.

Measured (`analysis/m2b_skeleton_ab.py`, 29,164 hand-frames):

    configuration              >30 deg    >60 deg    distortion
    raw (no fit)                  1413        586          --
    fingers only (palm pinned)    1413        586       0.23 palm widths
    whole hand (palm fitted)      1367        582       0.73 palm widths

**Fingers-only changes orientation by exactly 0.0%, and that is not a bug.** The
orientation frame is built from wrist(0), index-MCP(5), middle-MCP(9) and
pinky-MCP(17) -- four PALM landmarks, not one finger bone. A fit that pins the
palm therefore cannot move the frame, and a fit that does NOT pin the palm
overwrites the most reliable data on the hand (0.2: palm rigidity 2.76 mm,
already at target) with a population-average prior, for a change indistinguishable
from noise at 3x the distortion.

So there is no version of "impose a skeleton" that improves orientation
stability. The verdict is structural, not a tuning failure -- do not retry with
better proportions or more iterations.

⭐ **THIS IS THE THIRD INDEPENDENT MEASUREMENT SAYING THE SAME THING**, and
together they are why T1/T2 are now treated as a sensor floor:
  * 0.13.2 -- large jumps occur in WELL-OBSERVED frames: bad landmarks, not bad
    filtering.
  * A5 / 13.7 -- per-landmark weighting is statistically indistinguishable at the
    degenerate frames, because the distortion is CORRELATED across the whole
    knuckle row.
  * here -- constraining bone lengths cannot help, because the orientation frame
    does not use those bones.
When MediaPipe's palm reconstruction collapses (Google issue #5156, back of
hand), all four frame landmarks are wrong TOGETHER. Nothing in Phase 1 touches
that, which matches the literature: HandFlow (VMV 2022) shows the edge-on
configuration is genuinely ill-posed for a single RGB view, and Meta uses
multi-camera rigs for exactly this.

✅ **ONE DELIVERABLE SURVIVES AND IS WORTH KEEPING**: `palm_width_world()` is the
per-session scale reference item 4.1 (M9) needs -- the thing dead item 1.4 was
supposed to supply. It needs no skeleton fit at all, just the observed palm
width, which 10.1 records as the documented anchor of choice because it is near
pose-invariant. That unblocks 4.1 -> 4.2 (Z-axis translation).

--- original design notes follow ---


Pure stdlib, numpy-free, no import side effects -- the same contract as
`palm_geometry.py`, `hand_identity.py` and `hand_anatomy.py`.

WHY THIS EXISTS
---------------
Item 1.4 (M2) tried to MEASURE a personal skeleton from `worldLandmarks` and
died: not one bone converges (0/21 inside the 2% gate, 6-22% IQR), a verdict
audited and upheld against the correct quantity in 0.15. The literature's answer
(S7) is not to average harder -- it is to FIT A FIXED-BONE-LENGTH MODEL each
frame, so lengths are consistent BY CONSTRUCTION rather than by convergence.

⭐ WHY THIS IS NOT SUBJECT TO WHAT KILLED 1.6
---------------------------------------------
1.6 was parked because a REJECTION gate cannot tell a teleport from a fast real
movement, so it taxed legitimate input ~4:1. **This module never rejects
anything.** It takes every frame and nudges the landmarks onto a
length-consistent skeleton. There is no accept/reject decision, so fast movement
cannot be filtered out -- the failure mode does not exist here.

The cost it CAN incur is different and must be measured instead: DISTORTION.
A fit that drags landmarks far from what was observed damages good frames. So
the A/B (`analysis/m2b_skeleton_ab.py`) reports both directions -- orientation
stability gained, and displacement imposed on well-observed frames.

THE MODEL, AND WHY IT IS LICENCE-CLEAN
--------------------------------------
⚠ **NOT MANO.** The spec calls this "MANO-lite", but MANO is licensed for
non-commercial research only and this project ships commercially (queue N13).
Nothing here derives from MANO or from any research dataset.

The skeleton is 20 bones with fixed PROPORTIONS, scaled per frame by the
observed palm width. Proportions are population-average hand anthropometry --
anatomical facts, unlicensed -- expressed relative to palm width (the
index-MCP-to-pinky-MCP span), which 0.2 measured as the most rigid quantity on
the hand (2.76 mm, already at target) and which 10.1 records as the documented
anchor of choice because it is near pose-invariant.

Per 2f's own note, population-average proportions suffice to start; per-user
refinement is optional and deliberately NOT attempted, because that is what 1.4
proved this sensor cannot support.

THE FIT
-------
Constrained relaxation (Jakobsen-style), not a matrix solve -- so it stays
numpy-free and cheap enough for the web/mobile port:

    repeat ITERATIONS times:
        pull each joint toward its observed position   (data term)
        walk each finger chain, resetting every bone to its model length
                                                       (constraint term)

The wrist is the anchor. Alternating a soft data term with a hard length
projection converges in a handful of passes and needs no derivatives. It is
warm-startable (pass the previous frame's fit as `initial`), which both speeds
convergence and adds temporal continuity for free.
"""

import math

WRIST = 0
# (mcp, pip, dip, tip) -- MediaPipe hand-landmark topology
FINGERS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
INDEX_MCP, PINKY_MCP = 5, 17

# Bone lengths as a fraction of PALM WIDTH (index-MCP to pinky-MCP span).
# Population-average proportions. Each finger lists the four bones in order:
#   wrist->MCP (metacarpal), MCP->PIP (proximal), PIP->DIP (middle), DIP->TIP
# The thumb's first entry is wrist->CMC and its chain is genuinely different --
# it has no middle phalanx, so its third entry is the (short) IP segment.
BONE_PROPORTIONS = {
    "thumb":  (0.42, 0.38, 0.31, 0.28),
    "index":  (1.06, 0.55, 0.32, 0.24),
    "middle": (1.02, 0.60, 0.37, 0.25),
    "ring":   (0.96, 0.55, 0.35, 0.25),
    "pinky":  (0.91, 0.44, 0.25, 0.22),
}

ITERATIONS = 6          # measured to converge well before this; see the A/B
DATA_WEIGHT = 0.5       # how hard a joint is pulled toward its observation each
                        # pass. 1.0 would ignore the constraint between passes
                        # and oscillate; 0.5 converges smoothly.


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(v, s):
    return (v[0] * s, v[1] * s, v[2] * s)


def _norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def palm_width_world(world_landmarks):
    """The scale reference: index-MCP to pinky-MCP span, in world units.

    This is also the per-session scale reference item 4.1 (M9) needs -- 1.4 was
    supposed to supply it and cannot.
    """
    w = world_landmarks
    return _norm(_sub(w[PINKY_MCP], w[INDEX_MCP]))


def model_bone_lengths(palm_width):
    """Absolute bone lengths for this hand, from proportions x observed scale."""
    return {name: tuple(p * palm_width for p in props)
            for name, props in BONE_PROPORTIONS.items()}


def fit(world_landmarks, initial=None, iterations=ITERATIONS, fingers_only=True):
    """See `_fit_impl`. `fingers_only=True` (default) holds the wrist and the
    five MCPs at their observed positions and constrains only the phalanges.

    WHY THAT IS THE DEFAULT, and why the alternative is circular:
      * The palm is the RELIABLE part of this sensor -- 0.2 measured palm
        rigidity at 2.76 mm, already at target -- while the distal bones carry
        13-32% CV. Fitting the palm means distorting the best data with the
        worst prior.
      * Scaling bone lengths by the observed palm width and then MOVING the
        landmarks that define palm width (5 and 17) is circular, and measured
        to be unstable: mean distortion 0.73 palm widths, max 101.
    """
    return _fit_impl(world_landmarks, initial, iterations, fingers_only)


def _fit_impl(world_landmarks, initial=None, iterations=ITERATIONS,
              fingers_only=True):
    """Return a length-consistent 21-point skeleton close to the observation.

    world_landmarks : 21 (x, y, z) observed points
    initial         : optional previous frame's fit, for warm start + temporal
                      continuity
    Returns a new list of 21 points. Never raises; returns the input unchanged
    if the hand is too degenerate to scale.
    """
    if world_landmarks is None or len(world_landmarks) < 21:
        return world_landmarks

    obs = [tuple(p) for p in world_landmarks]
    palm = palm_width_world(obs)
    if palm < 1e-9:
        return obs                      # collapsed: nothing to scale by
    lengths = model_bone_lengths(palm)

    pts = [tuple(p) for p in (initial if initial and len(initial) == 21 else obs)]
    pts[WRIST] = obs[WRIST]             # anchor

    # Landmarks held at their observed positions: the wrist always, and in
    # fingers_only mode the five MCPs too (the rigid, reliable palm).
    pinned = {WRIST}
    if fingers_only:
        pinned |= {chain[0] for chain in FINGERS.values()}
    for i in pinned:
        pts[i] = obs[i]

    for _ in range(iterations):
        # --- data term: pull toward what was actually observed ---
        for i in range(21):
            if i in pinned:
                continue
            pts[i] = _lerp(pts[i], obs[i], DATA_WEIGHT)

        # --- constraint term: hard-set every bone to its model length ---
        for name, chain in FINGERS.items():
            L = lengths[name]
            # In fingers_only mode the metacarpal is observed, not imposed, so
            # the chain starts at the MCP and skips its first model length.
            prev = chain[0] if fingers_only else WRIST
            todo = list(enumerate(chain))[1:] if fingers_only else list(enumerate(chain))
            for k, joint in todo:
                d = _sub(pts[joint], pts[prev])
                n = _norm(d)
                if n < 1e-12:
                    # Degenerate: push off along the observed direction instead
                    # of picking an arbitrary axis, so the fit stays near the
                    # data rather than inventing a pose.
                    d = _sub(obs[joint], obs[prev])
                    n = _norm(d)
                    if n < 1e-12:
                        d, n = (0.0, 1.0, 0.0), 1.0
                pts[joint] = _add(pts[prev], _scale(d, L[k] / n))
                prev = joint

    return pts


def residual(world_landmarks, fitted):
    """Mean distance between observation and fit, in palm widths (scale-free).

    This is the DISTORTION cost -- the quantity that decides whether the fit is
    helping or just moving landmarks around. Report it alongside any stability
    gain, never on its own.
    """
    if not fitted or len(fitted) != 21:
        return None
    palm = palm_width_world(world_landmarks)
    if palm < 1e-9:
        return None
    tot = sum(_norm(_sub(a, b)) for a, b in zip(world_landmarks, fitted))
    return tot / (21.0 * palm)
