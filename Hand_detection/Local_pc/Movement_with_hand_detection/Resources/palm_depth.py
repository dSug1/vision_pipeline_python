"""M9 / queue item 4.1 -- RELATIVE depth from palm foreshortening.

WHAT THIS PRODUCES, AND WHAT IT DELIBERATELY DOES NOT
-----------------------------------------------------
Produces a **ratio**, `d/d0`: how much nearer or further the hand is than it was
at the moment it grabbed. NOT metres, NOT absolute distance.

⭐ That is a deliberate design decision with a hard reason behind it, not a
shortcut. Absolute metric scale is **fundamentally unobservable** from one
uncalibrated camera looking at a hand of unknown size -- a large hand far away
and a small hand close by produce the same image (`PERCEPTION_LAYER_SPEC.md`
§2f). Literature agrees: recovering true camera-space hand position needs a
trained network with a baked-in anatomical prior and still lands at ~3.5 cm
(ScaleHP 2026, RootNet lineage). ⭐ **The ratio form cancels the unknown scale
exactly**, which is why it needs none of that.

THE ANCHOR: max of the FOUR RIGID PALM SPANS, each vs. its own grab baseline
----------------------------------------------------------------------------
Measured over the corpus (`analysis/m9_depth_anchors.py`, spec §14.3.1/§14.3.2),
CV during rotation-in-place -- LOWER is better, because a depth anchor must stay
CONSTANT while the hand merely rotates:

    rotation   width   length   max(w,l)   max4
    PITCH      0.094   0.301    0.088      0.085
    YAW        0.128   0.125    0.080      0.056

⚠ **Never palm width alone.** Foreshortening only ever SHRINKS an apparent span,
so the largest normalised span is the least corrupted, and taking the max
auto-selects whichever anchor the current pose left intact.

⚠ **Never a finger span.** Any MCP->TIP length changes with GRIP, so it would
conflate "the hand closed" with "the hand moved away" -- catastrophic for a grab
gesture, where the hand closes at exactly the moment depth must hold still. Only
the rigid palm quad is used: 5<->17, 0<->9, 0<->5, 0<->17.

S10 -- THE FREEZE IS A PREREQUISITE, NOT A NICETY
--------------------------------------------------
§14.3.1 predicted from geometry that width collapses under yaw while length
survives. §14.3.2 MEASURED it and **refuted** that: under yaw both degrade
equally (0.128 vs 0.125), because edge-on collapses all four palm-frame
landmarks together (§0.18). So there is no surviving anchor to fall back on
inside the band, and the ratio must FREEZE there or Z-control inherits the
pitch-crossing failure. Same pattern as `PalmFacingTracker`, deliberately: enter
on `edge_on_measure < threshold`, leave only after a sustained recovery run.

⚠ Even the best anchor still carries ~9% false depth during rotation, so the
freeze is necessary but not sufficient -- hence `RATE_LIMIT_PER_FRAME` too.
**Expect a usable RELATIVE signal, not a clean metric one.** That is all §14.3's
design ever claimed.

WHY NO CALIBRATION STEP
------------------------
Measured on the corpus's `depth_sweep` take (727 frames): pushing the hand toward
and away from the camera moves the max4 anchor over a **3.59x range** (ratio
0.53 .. 1.89 about the resting size), with observability holding at 0.85. That is
ample dynamic range, and because `d0` is captured AT GRAB, every grab
re-normalises itself -- a small hand, or a user sitting further back, still
starts at ratio 1.0. So no min/max calibration screen is required to make this
work. See `analysis/m9_depth_envelope.py`.

Stdlib only, numpy-free, clock-free, no side effects -- the port contract, same
as `palm_geometry.py` / `hand_state.py`. Golden vectors:
`analysis/verify_palm_depth.py`.
"""

import math

try:                                        # imported, never copied (N6)
    from . import palm_geometry as PG
except ImportError:
    import palm_geometry as PG

# The rigid palm quad: width, length, and the two diagonals. Adding the
# diagonals took the pitch CV 0.088 -> 0.085 and the yaw CV 0.080 -> 0.056.
PALM_SPANS = ((5, 17), (0, 9), (0, 5), (0, 17))

# Below this `edge_on_measure` the palm is collapsing in projection and NO span
# is trustworthy. Shared with DR-2 on purpose -- one band, one definition.
EDGE_ON_THRESHOLD = PG.EDGE_ON_THRESHOLD
EXIT_HYSTERESIS_FACTOR = 1.5
EXIT_DWELL_FRAMES = 3

# Max fractional change in the reported ratio per frame. At ~25 fps a genuine
# hand push spans the full 3.59x range over ~1 s, i.e. ~5%/frame; anything far
# above that is an estimator excursion, not an arm.
RATE_LIMIT_PER_FRAME = 0.12

# Ratios outside this are not reachable by arm movement (measured envelope is
# 0.53..1.89); clamping stops a bad frame throwing the cube to infinity.
MIN_RATIO = 0.40
MAX_RATIO = 2.50

# ⭐⭐ SECOND-ORDER FALLBACK (owner instruction 2026-08-22): "a depth measure
# cannot be frozen because the hand is on the edge and a second-order fallback
# shall be available to bridge".
#
# A span normalised below this fraction of its own grab baseline is treated as
# COLLAPSED and dropped from the max. If at least one span survives, depth is
# still MEASURED from it; only when ALL four have collapsed does the ratio hold.
#
# ⭐ MEASURED, not chosen. Over 206 genuinely edge-on frames (edge_on < 0.15)
# pooled across the 2026-08-22 recordings, the rigid spans do NOT all collapse
# together -- median retained, relative to the same span while measuring:
#     diagonal 0-5   1.01x      palm length 0-9  0.94x
#     diagonal 0-17  0.70x      palm width 5-17  0.63x
# So the old gate threw away two spans that still carried signal. 0.5 sits below
# the two survivors and above the collapsed width.
#
# ⚠ RIGID PALM SPANS ONLY. `wrist->fingertip` also survived edge-on (1.00x) and
# is deliberately NOT used: any MCP->TIP length changes with GRIP, so it would
# read "the hand closed" as "the hand moved away" at exactly the moment of a
# grab. That trade is not worth a bridge (spec 14.3.1 point 2).
#
# ⚠ This RELAXES S10, which the spec calls a prerequisite on the grounds that
# edge-on collapses all four palm landmarks together (0.18). Note that claim was
# made about WORLD landmarks; this is measured on PIXEL spans, so it is not a
# direct refutation -- but on pixels the premise does not hold, and holding a
# stale depth is itself a wrong answer.
MIN_SPAN_FRACTION = 0.50


def palm_spans(landmarks):
    """The four rigid palm-quad spans, in pixels. None if landmarks are unusable."""
    if not landmarks or len(landmarks) < 18:
        return None
    out = []
    for a, b in PALM_SPANS:
        pa, pb = landmarks[a], landmarks[b]
        if pa is None or pb is None:
            return None
        out.append(math.hypot(pa[0] - pb[0], pa[1] - pb[1]))
    return out


class DepthRatioTracker:
    """Per-hand relative-depth estimator. One instance per tracked hand.

    `freeze(landmarks)` captures the grab-time baseline; `update(landmarks)`
    returns `(ratio, valid)` every frame after that.

    `valid` is False while the ratio is being HELD rather than measured (inside
    the edge-on band, or before a baseline exists). ⚠ It is the caller's job to
    decide what to do with an invalid ratio -- this module never silently
    substitutes a fabricated value, it reports that it is holding. That mirrors
    `HandState.quality.orientationValid`'s contract.
    """

    def __init__(self, threshold=EDGE_ON_THRESHOLD,
                 rate_limit=RATE_LIMIT_PER_FRAME):
        self.threshold = threshold
        self.exit_threshold = threshold * EXIT_HYSTERESIS_FACTOR
        self.rate_limit = rate_limit
        self.baseline = None      # the four spans at grab time
        self.ratio = 1.0          # last reported ratio
        self.in_band = False
        self.exit_run = 0
        # diagnostics, same spirit as PalmFacingTracker's
        self.band_entries = 0
        self.frames_frozen = 0
        self.rate_limited = 0

    @property
    def depth_valid(self):
        """False while the ratio is held rather than measured. Maps to
        `HandState.quality.depthValid` when the v2 wire migration lands."""
        return self.baseline is not None and not self.in_band

    def freeze(self, landmarks):
        """Capture the grab-time baseline. Returns True if it took.

        ⚠ Refuses to baseline on an edge-on frame: a collapsed span would become
        the denominator for the whole hold, permanently inflating every later
        ratio. Better to report invalid until a good frame arrives.
        """
        spans = palm_spans(landmarks)
        if spans is None or min(spans) <= 1e-6:
            return False
        if PG.edge_on_measure(landmarks) < self.threshold:
            return False
        self.baseline = spans
        self.ratio = 1.0
        self.in_band = False
        self.exit_run = 0
        return True

    def update(self, landmarks):
        """Returns (ratio, valid). Ratio is d/d0 -- >1 nearer, <1 further."""
        if self.baseline is None:
            if not self.freeze(landmarks):
                return self.ratio, False
            return self.ratio, True

        spans = palm_spans(landmarks)
        if spans is None:
            self.frames_frozen += 1
            return self.ratio, False

        eo = PG.edge_on_measure(landmarks)

        # --- band bookkeeping, now DIAGNOSTIC rather than the gate itself.
        if eo < self.threshold:
            if not self.in_band:
                self.in_band = True
                self.band_entries += 1
            self.exit_run = 0
        elif self.in_band:
            if eo > self.exit_threshold:
                self.exit_run += 1
                if self.exit_run >= EXIT_DWELL_FRAMES:
                    self.in_band = False
                    self.exit_run = 0
            else:
                self.exit_run = 0

        # --- ⭐ THE GATE IS NOW PER-SPAN, NOT THE QUAD'S CONDITIONING.
        # Keep every span still above MIN_SPAN_FRACTION of its own baseline and
        # take the max of those. Being edge-on no longer freezes depth on its own
        # -- it only removes the spans edge-on actually destroyed. Measured: the
        # 0-5 diagonal and the palm length survive edge-on (1.01x / 0.94x) while
        # the width does not (0.63x), so a survivor is normally available.
        norm = [s / b for s, b in zip(spans, self.baseline) if b > 1e-6]
        usable = [r for r in norm if r >= MIN_SPAN_FRACTION]
        if not usable:
            # Every anchor collapsed at once -- there is genuinely nothing to
            # measure, so hold. This is S10's freeze, now the LAST resort rather
            # than the first response.
            self.frames_frozen += 1
            return self.ratio, False
        raw = max(usable)
        raw = max(MIN_RATIO, min(MAX_RATIO, raw))

        # --- rate limit: ~9% false depth survives even the best anchor.
        delta = raw - self.ratio
        cap = self.rate_limit * max(self.ratio, 1e-6)
        if delta > cap:
            raw = self.ratio + cap
            self.rate_limited += 1
        elif delta < -cap:
            raw = self.ratio - cap
            self.rate_limited += 1

        self.ratio = raw
        return self.ratio, True

    def reset(self):
        """Hand lost / track ended. Drops the baseline but keeps diagnostics.

        ⚠ The baseline MUST go: it belongs to a dead track, and §16.15's rule
        ("never fit against a dead track") applies here for the same reason.
        """
        self.baseline = None
        self.ratio = 1.0
        self.in_band = False
        self.exit_run = 0
