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

# ⛔⛔ AND IT IS THE WRONG UNIT, WHICH IS WHY THE OWNER STILL SAW Z JUMPS.
#
# Owner, 2026-08-26: *"there was still a big jump in the z direction of the cube
# during one of the grabs"*. ⭐ MEASURED on that very take: none of the 48 depth
# steps over 2 cm land on a grab -- `A1`'s walk fixed that -- they are all DURING
# a hold, and their size is set by this limiter:
#
#     per-frame relative depth step, held frames: p50 0.009  p90 0.052
#                                                 p95 0.083  p99 0.116  max 0.137
#
# ⚠ The cap is 0.12 and the comment above says genuine hand motion is ~5%/frame.
# So the limiter sits at 2.4x real motion and passes exactly the excursions it was
# added to stop -- p90 is already under the genuine rate, and the visible jumps are
# the 5-10% tail above it.
#
# ⛔ WORSE, IT IS PER FRAME. That is the defect `L1` already paid for once: a
# per-frame fraction changes its real-world meaning with the camera's frame rate,
# so the same constant is 240%/s in a bright room and 360%/s in a dark one. The
# fix there was to express the constant in TIME, and it is the fix here.
#
# ⭐ 1.20 per SECOND reproduces ~6%/frame at this pipeline's measured ~20 fps --
# just above the module's own 5%/frame figure for a genuine push, and tight enough
# that the 8-11% of frames carrying the tail are limited instead of shown.
# ⭐⭐ AND THE CAP IS PER SECOND WHEN THE CALLER SUPPLIES AN INTERVAL.
#
# ⛔ A FIRST ATTEMPT PASSED `now_ms` AND WAS REVERTED WHOLE, correctly: this module
# is CLOCK-FREE BY CONTRACT (`CONSTRAINTS` §2 -- the estimator layer is
# transliterated, not rewritten, and a wall-clock read is the first thing that does
# not port). `verify_palm_depth` caught it within the hour.
#
# ⭐ The shape that satisfies both: the CALLER owns the frame loop, computes the
# interval with `hand_state.frame_dt_ms` (clamped, shared, reusable) and passes it
# down as a PLAIN NUMBER. Nothing here asks what time it is, so the module stays
# deterministic under replay and ports unchanged.
#
# ⭐⭐ 2.00 per second -- SETTLED LIVE BY THE OWNER on the rig slider, 2026-08-27
# ("z rate 200% is good"), the way this project settles every feel constant.
#
# The unit fix and the tightening were deliberately separated. 2.40/s reproduced
# the old 12%/frame at ~20 fps exactly, so the switch to time changed nothing; the
# owner then swept the slider and stopped at 2.00/s = 10%/frame at 20 fps.
#
# ⚠ WHAT IT IS TRADING, measured on the owner's own take: per-frame relative depth
# steps while holding ran p50 0.9%, p90 5.2%, p95 8.3%, max 13.7%. The module's
# own figure for a GENUINE hand push is ~5%/frame. So 10%/frame still sits above
# real motion and clips only the top of the excursion tail -- the owner traded
# JUMP against LAG and stopped where the cube still follows a real push.
# ⛔ It is NOT at the 5%/frame genuine rate, and that is a choice, not an
# oversight: going there was audibly laggy on a deliberate push.
RATE_LIMIT_PER_S = 2.00

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
# So the old gate threw away two spans that still carried signal.
#
# ⚠ CORRECTION to an earlier version of this comment, which claimed 0.5 sits
# "above the collapsed width". It does NOT -- the width retained 0.63, which is
# ABOVE 0.5, so the floor does not exclude it. That turns out not to matter,
# because `max()` selects the largest survivor and the width is never the largest
# when a 0.94/1.01 span is present. The floor's real and only job is deciding
# when to HOLD, i.e. when EVERY span has collapsed.
#
# ⚠⚠ AND THE FLOOR IS SETUP-DEPENDENT IN A WAY THE RATIO ITSELF IS NOT. Under a
# pinhole camera the ratio is Z0/Z: focal length, field of view and hand size all
# CANCEL. This floor does not cancel -- it is an absolute size threshold, so it
# conflates "far away" with "collapsed", both of which shrink every span. For a
# +/-30 cm reach the retreat ratio stays >= 0.57 for sitting distances of 40-120
# cm, so the floor is not reached by distance alone there; but a user who leans
# well back can cross it and have genuine distance read as collapse.
#
# ⭐ THE SCALE-INVARIANT FIX, if this ever needs to generalise: distance shrinks
# every span PROPORTIONALLY while foreshortening shrinks them ANISOTROPICALLY, so
# the RATIO BETWEEN spans separates the two and is scale-free. Gate the hold on
# shape (that ratio, or `edge_on_measure`) rather than on absolute size.
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

    def update(self, landmarks, dt_ms=None):
        """Returns (ratio, valid). Ratio is d/d0 -- >1 nearer, <1 further.

        `dt_ms` is the frame interval from `hand_state.frame_dt_ms`, already
        clamped. ⭐ It is a PLAIN NUMBER, never a clock: see `RATE_LIMIT_PER_S`.
        ⚠ `None` means the caller has no interval yet, and the per-FRAME cap is
        used -- which is exactly today's behaviour, so every existing call site is
        unchanged until it is updated.
        """
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
        # ⭐ Per SECOND when an interval is supplied, per FRAME otherwise.
        per_frame = (self.rate_limit if dt_ms is None
                     else RATE_LIMIT_PER_S * (dt_ms / 1000.0))
        cap = per_frame * max(self.ratio, 1e-6)
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


# ==========================================================================
# 4.2 -- ABSOLUTE HAND DEPTH, FOR THE 3D SNAP GATE ONLY
# ==========================================================================
# ⭐⭐ WHY A SECOND ESTIMATOR EXISTS, AND WHY IT IS NOT A DUPLICATE.
#
# `DepthRatioTracker` above answers "how much nearer than at the grab?" and its
# baseline is captured AT THE GRAB. That is exactly right for driving a held
# object, and the unknown hand size cancels EXACTLY in the ratio.
#
# ⚠ But 4.2's snap gate asks a question the ratio form cannot answer: *before*
# any grab, is this hand at the same depth as that object? There is no grab
# baseline yet, and a free hand's ratio is measured against wherever it happened
# to enter -- a number with no relation to the object's depth.
#
# ⭐ SO THIS ONE SUBSTITUTES NOMINAL ANATOMY FOR THE MISSING BASELINE: under a
# pinhole camera `Z = f * S / span_px`, so assuming the rigid palm spans have
# their anthropometric median lengths gives an absolute depth in metres.
#
# ⚠⚠ AND IT IS ONLY EVER TRUE UP TO THE USER'S OWN HAND SIZE. Absolute metric
# scale is unobservable from one uncalibrated camera (see this module's header);
# nothing here refutes that. A hand 20% smaller than nominal reads ~20% FURTHER
# than it is, permanently. **That error is a constant per user, not noise** --
# which is what makes it usable for a TOLERANCE decision and useless for
# anything else. Hence, and this is binding:
#
#   * this value gates SNAPPING and nothing else;
#   * `GRAB_Z_TOLERANCE_M` in the gesture layer is sized to swallow that bias
#     (+/-20% of nominal hand breadth is +/-0.08 m at 0.40 m), so the gate stays
#     REACHABLE for a user whose hands are not median;
#   * the held object's depth is driven by the RATIO form above, where the same
#     unknown cancels and no such bias exists.
#
# ⛔ DO NOT feed this into the Z-translation mapping "because it is in metres".
# That would re-import the scale error the ratio design exists to eliminate.
#
# Anthropometric medians for the four rigid palm spans, in metres. Hand breadth
# across the metacarpals is the 85 mm U9's own margin derivation already used --
# this is the SAME assumption, not a new one. The other three are the
# corresponding adult wrist-to-MCP medians.
# ⚠ NOT derived from `world_landmarks`: the M2 audit established that those do
# not encode a pose-consistent skeleton (0/21 bones inside target), so measuring
# a nominal length from them would be measuring the estimator, not a hand.
# ⭐ DECISION 1, OWNER 2026-08-23: **NO SNAPPING WHILE DEPTH IS FROZEN.** With the
# grab check now three-dimensional, a snap decided from a HELD depth would be
# deciding proximity from a number the sensor is not currently supplying. Same
# philosophy as DR-2's sign freeze and U8's provisional chirality: SUPPRESS,
# DO NOT GUESS. Spec §14.3.2 left this open; it is closed.
#
# ⚠ FLAGGED TUNABLE FOR GAME FEEL (the owner's own framing). If refusing feels
# too strict in play, the fallback to try is degrading to the flat 2D radius
# while frozen -- set this False -- rather than refusing outright. ⛔ Do not
# change it on impression: measure how often the freeze actually coincides with
# a grab attempt first. Both the freeze and the refusal are RECORDED
# (`depth_valid`, `snap_allowed`, recorder schema 3) precisely so that is a query
# against an existing take and not a new session.
#
# ⚠ Lives HERE, not in either tool, for the reason N6 exists: production and the
# debug tool must apply the same policy, and "kept in sync by hand" is how the
# chirality convention drifted into a production-only inversion (§13.6.1).
SNAP_REQUIRES_VALID_DEPTH = True

# The AXIAL half-tolerance of the 3D grab check, in metres. The lateral half
# stays the projected grab radius, so X/Y feel is untouched and Z is a new
# AND-condition.
#
# ⚠⚠ WHY IT IS NOT "the same radius made spherical", which was §14.3.2's other
# candidate. A sphere would give the small object a 43 mm axial tolerance, while
# the hand depth feeding the check is scaled by NOMINAL anatomy (see
# `NOMINAL_SPAN_M` below): a user whose hands are 20% off the median reads ~80 mm
# away from where they are, CONSTANTLY. A 43 mm sphere would be unreachable for
# them -- the object simply could never be picked up, and the failure would look
# like a broken build rather than a mis-sized constant. 0.15 m swallows that bias
# with room to spare while still being a real constraint (the play volume is
# 0.65 m deep).
# ⚠ A first value with a stated derivation, not a measured optimum -- same
# live-tuning discipline as GRAB_RADIUS_MULTIPLIER and ROTATION_SLERP_FACTOR.
GRAB_Z_TOLERANCE_M = 0.15

NOMINAL_SPAN_M = {
    (5, 17): 0.085,     # hand breadth across the knuckles
    (0, 9): 0.100,      # wrist -> middle MCP (palm length)
    (0, 5): 0.100,      # wrist -> index MCP
    (0, 17): 0.092,     # wrist -> pinky MCP
}


class HandDepthTracker:
    """Absolute hand depth in metres, plus S10 validity, with NO grab baseline.

    `update(landmarks, frame_size) -> (depth_m, valid)`.

    `valid` is False while the value is being HELD rather than measured -- the
    S10 edge-on band, with the same enter/exit hysteresis as
    `DepthRatioTracker`. ⭐ Under queue 4.2's DECISION 1 (owner, 2026-08-23) the
    gesture layer REFUSES a snap when this is False rather than guessing: a
    frozen depth is a held value, not a measurement, and deciding proximity from
    a number the sensor is not currently supplying is the confidently-wrong
    answer this project has paid for repeatedly.

    ⚠ Unlike the ratio tracker, the S10 band IS the gate here, not a diagnostic.
    The ratio tracker could relax it because it has a per-span baseline to test
    each span against; with no baseline there is nothing to compare a span to,
    so the band is the only signal available that the palm has collapsed.
    """

    def __init__(self, threshold=EDGE_ON_THRESHOLD):
        self.threshold = threshold
        self.exit_threshold = threshold * EXIT_HYSTERESIS_FACTOR
        self.depth_m = None
        self.in_band = False
        self.exit_run = 0
        self.frames_frozen = 0

    def measure(self, landmarks, focal):
        """Raw depth from the least-foreshortened span. None if unusable.

        Foreshortening only ever SHRINKS an apparent span, and a shrunken span
        makes `f * S / span` too LARGE -- so the smallest per-span depth is the
        one computed from the span the current pose left most intact. Same
        selection rule as the ratio form's `max()`, seen from the other side.
        """
        spans = palm_spans(landmarks)
        if spans is None or focal is None:
            return None
        best = None
        for (pair, px) in zip(PALM_SPANS, spans):
            if px <= 1e-6:
                continue
            z = focal * NOMINAL_SPAN_M[pair] / px
            if best is None or z < best:
                best = z
        return best

    def update(self, landmarks, frame_size):
        try:                                    # imported, never copied (N6)
            focal = PG.focal_px(frame_size)
        except AttributeError:                  # pragma: no cover - old module
            focal = None
        raw = self.measure(landmarks, focal)
        if raw is None:
            self.frames_frozen += 1
            return self.depth_m, False

        eo = PG.edge_on_measure(landmarks)
        if eo < self.threshold:
            self.in_band = True
            self.exit_run = 0
        elif self.in_band:
            if eo > self.exit_threshold:
                self.exit_run += 1
                if self.exit_run >= EXIT_DWELL_FRAMES:
                    self.in_band = False
                    self.exit_run = 0
            else:
                self.exit_run = 0

        if self.in_band:
            # HOLD. Never publish a depth measured through a collapsed palm.
            self.frames_frozen += 1
            return self.depth_m, False

        self.depth_m = PG.clamp_depth(raw)
        return self.depth_m, True

    def reset(self):
        """Hand lost / track ended -- the held value belonged to that hand."""
        self.depth_m = None
        self.in_band = False
        self.exit_run = 0
