"""Palm chirality geometry -- SHARED by production and the debug tool.

Merged queue item 1.2 (M5a `edgeOnMeasure`). See PERCEPTION_LAYER_SPEC.md §0.9 for
the chirality convention this rests on, and A2 for why only the *magnitude* is new.

--------------------------------------------------------------------------------
WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
Two things, and the second is the reason it is a MODULE rather than a function
added twice:

1. **The magnitude was being thrown away.** `_is_thumb_outward` already computed
   the signed area `s` of (index_MCP - wrist) x (pinky_MCP - wrist) and used only
   `sign(s)`. `|s|`, normalised, is the **edge-on measure**: how close the palm is
   to edge-on, 0 = perfectly edge-on, 1 = square to the camera. It costs one
   division and is the observability signal DR-2 (item 2.2), M4 and M6 need.

2. **The sign convention was duplicated.** `HandsTriggeredActions.py` and
   `LiveSnapDebug.py` each carried their own copy, "kept in sync" by hand. That is
   exactly how the convention drifted into the production-only inversion of
   2026-08-01 (§13.6.1). Duplication was already fixed once this way for the hand
   identity tracker (`hand_identity.py`, queue N6) on the owner's instruction --
   *"I do not want to have a debug tool which is not in tune with the
   production."* Same treatment here.

Deliberately dependency-free (pure stdlib, no numpy/cv2/pygame) so both callers
can import it without side effects -- `HandsTriggeredActions` opens a real pygame
window at import, so anything shared must not live there.

--------------------------------------------------------------------------------
THE NORMALISATION MUST NOT DRIFT FROM THE ANALYSER
--------------------------------------------------------------------------------
`AnalyzePerceptionSequences.edge_on()` computes `|s| / (|v1| * |v2|)`, and every
recorded threshold -- notably `EDGE_ON_THRESHOLD = 0.15`, settled by measurement
in spec §0.3 -- is expressed in THAT scale. Using a different normalisation here
would silently invalidate the threshold. `verify_matches_analyser()` below exists
to keep the two honest; `VerifyChiralityFixture.py` runs it.

Geometrically the quantity is |sin(theta)| between the two palm vectors, so it
falls to zero as the knuckle row turns edge-on to the camera -- which is precisely
the degenerate configuration behind the pitch-plane crossing (T2).
"""

import math

WRIST = 0
INDEX_MCP = 5
PINKY_MCP = 17

# Below this, the palm is close enough to edge-on that the SIGN is untrustworthy.
# Settled by measurement, NOT guessed (spec §0.3): the `non_crossing` sequence gave
# 0 sign flips in 723 frames with edge-on never dropping below 0.353, so 0.15 is
# never reached in normal motion -- but 4.6-8.0% of normal frames fall below 0.60,
# so raising it toward 0.60 would suppress valid gestures for no benefit. Keep 0.15.
EDGE_ON_THRESHOLD = 0.15


def palm_vectors(landmarks):
    """(index_MCP - wrist, pinky_MCP - wrist) in 2D pixel space."""
    wx, wy = landmarks[WRIST][0], landmarks[WRIST][1]
    v1 = (landmarks[INDEX_MCP][0] - wx, landmarks[INDEX_MCP][1] - wy)
    v2 = (landmarks[PINKY_MCP][0] - wx, landmarks[PINKY_MCP][1] - wy)
    return v1, v2


def signed_palm_area(landmarks):
    """2D cross product of the two palm vectors. Its SIGN is the palm/back cue."""
    v1, v2 = palm_vectors(landmarks)
    return v1[0] * v2[1] - v1[1] * v2[0]


def edge_on_measure(landmarks):
    """0..1. How far the palm is from edge-on: 0 = edge-on (sign meaningless),
    1 = knuckle row square to the camera. Equals |sin(theta)| between the palm
    vectors. Same normalisation as AnalyzePerceptionSequences.edge_on()."""
    v1, v2 = palm_vectors(landmarks)
    s = v1[0] * v2[1] - v1[1] * v2[0]
    den = math.hypot(*v1) * math.hypot(*v2)
    return abs(s) / den if den > 1e-9 else 0.0


# --------------------------------------------------------------------------
# U7 -- CHIRALITY FROM GEOMETRY, not from MediaPipe's handedness label
# --------------------------------------------------------------------------
# THE DEFECT (`Claude/HANDEDNESS_LABEL_DEFECT.md`): the handedness label is wrong
# **10.8%** of the time, measured against the operator's declaration, and
# `is_thumb_outward` below applies a handedness-dependent chirality correction --
# so its answer INVERTS under a wrong label. A back-of-hand hand computes as
# "palm" and passes rule 3's gate. MediaPipe scored one such wrong label 0.94, so
# score-gating does not catch it.
#
# ⛔ THE OBVIOUS FIX DOES NOT WORK, and the reason is worth keeping. The write-up
# first proposed taking the cue from "the 3D palm normal" instead of the 2D cross
# product. But `signed_palm_area` above ALREADY IS that normal's z-component, and
# that normal points out of the BACK for one chirality and out of the PALM for the
# other -- in 2D and in 3D alike. A left hand showing its palm and a right hand
# showing its back are MIRROR IMAGES; no function of the palm quad alone separates
# them. Going to 3D adds precision, not chirality.
#
# ⭐ WHAT DOES WORK IS THE THUMB, because it leaves the palm plane. The signed
# volume of the tetrahedron (wrist, index_MCP, pinky_MCP, thumb_CMC) is invariant
# under rotation and translation and changes sign ONLY under reflection. So its
# sign is chirality computed from geometry, with no label anywhere in it.
#
# MEASURED (`analysis/u7_geometric_chirality.py`, scored against the operator's
# DECLARATION -- never against `is_thumb_outward(px, label)`, which is the
# circularity that hid this defect through seven patches):
#
#   * corpus 99.8% vs the label's 98.8% (2555 frames, 7 declared sessions)
#   * on the ONE take that exercises the defect: 98.3% vs 89.4% -- 31 errors to 5
#   * the two signals are INDEPENDENT: they disagree on 30 frames and geometry is
#     right on 28. (Checked deliberately -- had MediaPipe chirality-normalised its
#     world landmarks by its own label, sign(V) would merely restate the label.)
#   * at the 5 recorded snaps, rule 3's input changes on exactly ONE: frame 122,
#     the documented failing snap. The four sound snaps are untouched.
#
# ⚠ REQUIRES `world_landmarks`. With none available this degrades to the label,
# which is exactly today's behaviour -- never worse.

THUMB_CMC = 1

# One bit, fitted by majority over the whole declared corpus and stated openly:
# a NEGATIVE signed volume means the apparent (mirrored) hand is `Left`. Under
# this project's mirrored convention that is a physical RIGHT hand.
CHIRALITY_V_NEGATIVE_IS_LEFT = True

# Consecutive agreeing observations required to CHANGE the held chirality.
#
# ⭐ CHOSEN BY MEASUREMENT, and the mechanism is explicable rather than fitted to
# noise: the residual geometric errors on the discriminating take form runs of
# [2, 1, 1, 1], so the longest spurious excursion is 2 frames and requiring 3
# clears all four runs -- 5 errors to 0, with 0 errors introduced across the six
# clean takes. Swept in `analysis/u7_geometric_chirality.py` (STEP 8).
#
# ⭐ WHY THE LATENCY COST IS NEAR ZERO, unlike DR-2's dwell: a hand cannot change
# chirality. Within one track the value is CONSTANT, so this debounce never delays
# a real transition -- it only delays adopting a DIFFERENT physical hand that has
# taken over the slot, where a few frames of lag is invisible. That is why a
# 3-frame requirement is affordable here and a 4-frame one was not in DR-2 (N7).
CHIRALITY_DEBOUNCE_FRAMES = 3

# U8 -- frames of geometric observation before a track's chirality may drive a
# RULE. Below this the value is PROVISIONAL: still produced and still used for
# display, but `ChiralityResolver.confirmed` is False and rule 3 refuses to snap.
#
# ⭐⭐ THIS IS A TRANSIT TIME, NOT A TUNING CONSTANT. The owner's argument, and it
# is the correct physical account of the failure: chirality is the THUMB's offset
# from the palm plane, so when the back of a right hand enters from the right, the
# thumb is the LAST part to appear. Until it does, the quantity is undefined --
# and MediaPipe supplies a hallucinated thumb, so the wrong answer arrives stable
# and well-conditioned rather than noisy.
#
# DERIVED FROM MEASUREMENT (`analysis/u8_entry_settling.py`), three ways that agree:
#   1. PHYSICAL: palm width 69 px (median) / entry speed 11 px/frame (median, for
#      the 75 corpus tracks that start at a vertical frame edge) = 4.8 frames to
#      travel one palm width. p75 is 10.1 frames.
#   2. EMPIRICAL: the leading run of wrong chirality per track -- 89.5% of tracks
#      are correct at frame 0, 93.4% by age 5, and it then PLATEAUS (93.9% at age
#      15). Waiting longer than ~5 buys almost nothing.
#   3. THE RECORDED FAILURE: `2026-08-22_190955_t3_remap_production_test`, track
#      t4 -- chirality wrong through age 4, correct at age 5, and the forbidden
#      grab landed at age 5. So the window must be at least 6 to cover it.
#
# COST, priced before shipping: a 6-frame window delays 17 of 78 corpus snaps
# (21.8%) by ~380 ms at the measured 15-17 fps. DELAYED, not refused -- the hand
# is still there when the gate opens. 8 frames would cost 33% of snaps for +0.5%
# of coverage, which is why this is 6 and not more.
#
# ⭐⭐ EXPRESSED IN MILLISECONDS (owner instruction, 2026-08-22), because it is a
# TRANSIT TIME and a frame count is only correct at the rate it was measured at.
# N7/N10 already burned this project once: the SAME camera and machine measured
# 24.1 fps in daylight and 15.1 fps in dim light, so DR-1's 500 ms `SWITCH_MS`
# silently became ~761 ms. A frame constant here would drift the same way.
#
# 400 ms, DERIVED rather than converted from a guessed rate:
#   * the measured transit -- palm width / entry speed, expressed in time
#     (`u8_entry_settling.py` step 3b) -- is median **230 ms**, p75 **453 ms**.
#     400 sits inside that range and covers the slower entries, which are the
#     dangerous ones: a slow entry hides the thumb for LONGER.
#   * the recorded failure session ran at a measured **18.14 fps**, and its
#     forbidden grab sat **317 ms** after that track's first observation, so the
#     window must exceed 317 ms.
#
# ⭐⭐ LOWERED 400 -> 200 ON 2026-08-22 after the live U9 take. Owner: *"400 ms is
# too long. Half of it would be good I think."* ⚠ It was NOT lowered on the
# request alone -- 200 ms is BELOW the recorded failure's 317 ms, so on the
# original reasoning it should leak. It does not, and the measurement says why:
#
#   window   f664 refused?   by what
#   400 ms   yes             time (317 < 400)
#   300 ms   yes             DISPUTE (raw observation disagrees with held)
#   250 ms   yes             DISPUTE
#   200 ms   yes             DISPUTE
#   150 ms   yes             DISPUTE
#   100 ms   yes             DISPUTE
#
# ⭐ THE DISPUTE CONDITION IS THE PRIMARY GUARD, not this window. That inverts the
# original design story: the window was thought to be the protection and the
# dispute check a refinement added when 6 frames landed exactly on the grab
# frame. Measured, the dispute check catches the recorded failure on its own at
# every window tried, and the window is a BACKSTOP for a hand whose bad chirality
# never disagrees with itself. Keeping some window is still right -- a stable
# wrong value is exactly the failure mode the corpus shows (5 consecutive frames)
# -- but it does not need to cover 317 ms to do its job.
#
# COST at 200 ms: **8.3%** of palm-reading frames suppress snapping, down from
# 14.1% at 400 ms. ⚠ Suppression is FRAMES, not grabs: the gate reopens, so a
# grab is delayed rather than refused.
#
# ⚠ U9's edge margin also now covers part of what this protected: a half-visible
# hand cannot grab at all, whatever its chirality says.
#
# ⭐⭐ GATED ON ELAPSED TIME, NOT ON A FRAME COUNT DERIVED FROM MEASURED FPS.
# That was considered and is strictly worse here: `FrameRateEstimator.fps` SORTS
# a ring buffer on every access (DR-1 pays that four times a frame), whereas
# elapsed time costs one subtraction and one comparison, needs no estimator, and
# has neither rounding nor the estimator's lag after a lighting change. Both call
# sites already hold `now_ms`, so nothing new is sampled.
CHIRALITY_CONFIRM_MS = 200.0

# ⚠ THE ONE THING THE FRAME COUNT DID BETTER, kept as a floor: chirality cannot
# be confirmed from frames that were never delivered. If detection is sparse --
# a hand seen in 2 of 10 frames -- elapsed time alone would confirm on almost no
# evidence. So confirmation ALSO requires a minimum number of observations.
# Mirrors the floors already in `hand_identity.frames_for()` (2, 2, 2, 3), which
# exist for exactly this reason.
CHIRALITY_CONFIRM_MIN_FRAMES = 3

# Used only by a caller that supplies no timestamp (older harnesses, unit tests).
# The rig's measured rate; a caller that passes `now_ms` never touches this.
CHIRALITY_FALLBACK_FPS = 18.0
CHIRALITY_CONFIRM_FRAMES = max(
    CHIRALITY_CONFIRM_MIN_FRAMES,
    int(CHIRALITY_CONFIRM_MS * CHIRALITY_FALLBACK_FPS / 1000.0 + 0.5))

# A/B switch. `False` restores the pre-U7 behaviour exactly (the raw MediaPipe
# label drives the chirality correction), so the two can be compared live rather
# than argued about -- the post-mortem's rule 6.
GEOMETRIC_CHIRALITY = True


def signed_palm_volume(world_landmarks, thumb_idx=THUMB_CMC):
    """det[index_MCP - wrist, pinky_MCP - wrist, thumb - wrist] over WORLD
    landmarks. Rotation- and translation-invariant; flips sign only under
    reflection, which is what makes it a chirality measure."""
    w = world_landmarks[WRIST]
    ax = world_landmarks[INDEX_MCP][0] - w[0]
    ay = world_landmarks[INDEX_MCP][1] - w[1]
    az = world_landmarks[INDEX_MCP][2] - w[2]
    bx = world_landmarks[PINKY_MCP][0] - w[0]
    by = world_landmarks[PINKY_MCP][1] - w[1]
    bz = world_landmarks[PINKY_MCP][2] - w[2]
    cx = world_landmarks[thumb_idx][0] - w[0]
    cy = world_landmarks[thumb_idx][1] - w[1]
    cz = world_landmarks[thumb_idx][2] - w[2]
    return (ax * (by * cz - bz * cy)
            - ay * (bx * cz - bz * cx)
            + az * (bx * cy - by * cx))


def palm_plane_thickness(world_landmarks, thumb_idx=THUMB_CMC):
    """The thumb's perpendicular distance from the palm plane, in metres --
    |V| normalised by the palm quad's area. This is the CONDITIONING of the
    chirality sign, the exact analogue of `edge_on_measure` for the 2D sign.

    ⚠⚠ DIAGNOSTIC ONLY -- it is deliberately NOT a gate, and that is a MEASURED
    decision, not an oversight. Sweeping a threshold from 0 to 7 mm changed the
    error count not at all between 0 and 5 mm, and between 3 and 5 mm it made
    things WORSE (0 residual errors -> 3), because suppressing observations stalls
    the debounce counter and lets a bad value persist. Under A10 a filter that
    shows no measured benefit is not shipped hopefully. Kept exposed because it is
    the honest conditioning signal and costs one division -- and because if a
    future failure IS conditioning-driven, this is the quantity to plot.

    Observed range over the declared corpus: min 0.9 mm, p10 7.9 mm, median 8.8 mm."""
    w = world_landmarks[WRIST]
    ax = world_landmarks[INDEX_MCP][0] - w[0]
    ay = world_landmarks[INDEX_MCP][1] - w[1]
    az = world_landmarks[INDEX_MCP][2] - w[2]
    bx = world_landmarks[PINKY_MCP][0] - w[0]
    by = world_landmarks[PINKY_MCP][1] - w[1]
    bz = world_landmarks[PINKY_MCP][2] - w[2]
    nx, ny, nz = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
    nn = math.sqrt(nx * nx + ny * ny + nz * nz)
    if nn < 1e-12:
        return 0.0
    return abs(signed_palm_volume(world_landmarks, thumb_idx)) / nn


def geometric_chirality(world_landmarks, thumb_idx=THUMB_CMC):
    """'Left' / 'Right' -- the APPARENT (mirrored) chirality, from geometry alone.

    Returns None only when the volume is exactly zero (perfectly degenerate),
    which lets the caller hold rather than guess. The returned value is in the
    same convention `is_thumb_outward` expects, so it is a drop-in for the label."""
    v = signed_palm_volume(world_landmarks, thumb_idx)
    if v == 0.0:
        return None
    return "Left" if ((v < 0) == CHIRALITY_V_NEGATIVE_IS_LEFT) else "Right"


class ChiralityResolver:
    """Holds a debounced geometric chirality for ONE hand.

    Falls back to the supplied MediaPipe label until it has a confident geometric
    value, so the worst case is exactly today's behaviour. Reset when the track
    dies -- a returning hand is a NEW hand and inherits nothing (the 4.1
    post-mortem's rule 2, which is what turned a state seam into frozen cubes)."""

    def __init__(self, debounce=CHIRALITY_DEBOUNCE_FRAMES):
        self.debounce = debounce
        self.held = None
        self._pending = None
        self._run = 0
        # U8: geometric observations seen for the CURRENT track. Until this
        # reaches CHIRALITY_CONFIRM_FRAMES the chirality is PROVISIONAL and
        # chirality-sensitive RULES must not act on it (see `confirmed`).
        self.frames_seen = 0
        # Timestamp of this track's FIRST geometric observation. `None` until one
        # arrives, and stays None for a caller that supplies no `now_ms` -- which
        # then falls back to the frame count. One subtraction per frame; no frame
        # rate is estimated and nothing is sampled.
        self._first_ms = None
        self._last_ms = None
        # True while the raw observation disagrees with the held value -- the
        # chirality is IN DISPUTE and no chirality-sensitive rule may act.
        self._disputed = False
        # diagnostics -- how often geometry overrode the label, and how often a
        # spurious excursion was absorbed. Both are what an A/B wants to read.
        self.overrides = 0
        self.debounce_absorbed = 0

    @property
    def confirmed(self):
        """False while this track's chirality is still PROVISIONAL.

        ⭐ WHY A RULE MUST NOT ACT ON A PROVISIONAL VALUE -- the owner's physical
        argument, which is the whole justification for this gate: chirality IS the
        thumb's offset from the palm plane, so when a hand enters the frame side-on
        the quantity is not merely noisy, it is UNDEFINED until the thumb clears
        the edge. MediaPipe fills the gap with a plausible hallucinated thumb, so
        the wrong value arrives STABLE and well-conditioned -- which is why no
        amount of debouncing, voting or conditioning-gating caught it (all three
        were measured and all three failed).

        `confirmed` is False only while GEOMETRIC_CHIRALITY is driving the answer.
        With no world landmarks the label is in charge and there is nothing to
        confirm, so this stays True and behaviour is exactly as before.

        ⭐⭐ TWO CONDITIONS, and the second was learned the hard way. The frame
        count alone is NOT enough: on the recorded production failure the count
        was satisfied on the very frame of the forbidden grab, while the HELD
        value was still the wrong one -- the debounce had not yet switched it.
        A count says "we have looked long enough"; it does not say "the answer is
        settled". So a rule may act only when BOTH hold:

          1. enough observations for the thumb to have entered view
             (`CHIRALITY_CONFIRM_FRAMES` -- a transit time, see the constant), and
          2. the latest observation AGREES with the held value.

        (2) is DR-2's philosophy applied to chirality: while the raw cue and the
        held value disagree, the chirality is IN DISPUTE, and a disputed chirality
        inverts `is_thumb_outward`. Freeze the rule rather than guess which side
        is right -- measured, guessing is near chance (46-64%)."""
        if not GEOMETRIC_CHIRALITY:
            return True
        if self.held is None:
            # No geometric value has ever been adopted, so the LABEL is driving
            # the answer and there is nothing for this gate to confirm.
            # ⚠ THIS BRANCH IS LOAD-BEARING, and omitting it was a real bug: with
            # no `world_landmarks` `frames_seen` never increments, so the gate
            # stayed shut forever and every caller that supplies only pixel
            # landmarks (harnesses, `verify_three_arm_bridge`) could never snap.
            # The gate must make an un-migrated caller unchanged, never blocked.
            return True
        # The observation floor always applies -- see CHIRALITY_CONFIRM_MIN_FRAMES.
        if self.frames_seen < CHIRALITY_CONFIRM_MIN_FRAMES:
            return False
        if self._first_ms is None:
            # No timestamps supplied: fall back to the frame count at the rig's
            # rate, which is exactly the pre-2026-08-22 behaviour.
            return self.frames_seen >= CHIRALITY_CONFIRM_FRAMES and not self._disputed
        if (self._last_ms - self._first_ms) < CHIRALITY_CONFIRM_MS:
            return False
        return not self._disputed

    def update(self, world_landmarks, handedness, now_ms=None):
        """-> the chirality label the chirality-sensitive rules should use.

        `now_ms` is OPTIONAL and additive: supplied, the confirmation window is a
        real duration (`CHIRALITY_CONFIRM_MS`) and is therefore correct at any
        capture rate; omitted, it falls back to a frame count at the rig's rate,
        which is what shipped before. Callers already hold this timestamp, so
        passing it samples nothing new."""
        if not GEOMETRIC_CHIRALITY or not world_landmarks:
            return handedness
        self.frames_seen += 1
        if now_ms is not None:
            if self._first_ms is None:
                self._first_ms = now_ms
            self._last_ms = now_ms
        obs = geometric_chirality(world_landmarks)
        if obs is None:
            # Degenerate this frame: hold, and treat the chirality as disputed --
            # we have no evidence either way, which is not the same as agreement.
            self._disputed = True
            return self.held if self.held is not None else handedness
        self._disputed = (self.held is not None and obs != self.held)
        if self.held is None:
            self.held = obs           # first sighting: adopt at once
        elif obs == self.held:
            self._pending, self._run = None, 0
        else:
            if obs == self._pending:
                self._run += 1
            else:
                self._pending, self._run = obs, 1
            if self._run >= self.debounce:
                self.held = obs
                self._pending, self._run = None, 0
            else:
                self.debounce_absorbed += 1
        if self.held != handedness:
            self.overrides += 1
        return self.held

    def reset(self):
        self.held = None
        self._pending = None
        self._run = 0
        # A new hand starts PROVISIONAL again. This is the point of the reset:
        # the confirmation belonged to the previous track, not to this one.
        self.frames_seen = 0
        self._first_ms = None
        self._last_ms = None
        self._disputed = False


# --------------------------------------------------------------------------
# U9 -- THE PLAY AREA: the object may never reach the display edge
# --------------------------------------------------------------------------
# OWNER, 2026-08-22: *"add a margin (half a hand width when hand is at 40 cm from
# camera) by which the cube is dropped when the center of the hand goes beyond
# that margin (before hand full exit of the frame): this helps when grabbing back
# the cube upon hand re-entrance: it gives time to detect the full hand to grab
# the cube (otherwise, currently, the cube is grabbed when the hand is already
# fully entered and the cube ends up grabbed at the edge of the hand)."*
#
# ⭐ THE MECHANISM. Today a held cube is released only once tracking is lost --
# i.e. once the hand is essentially GONE -- so the cube is abandoned right at the
# frame edge. On re-entry the hand is within grab radius while still only half
# visible, so it snaps immediately, and the grab is referenced to a hand pose
# built from landmarks that are half missing. The cube ends up hanging off the
# EDGE of the hand rather than sitting in it. Releasing earlier leaves the cube
# further inside the frame, so the hand must come properly into view before it is
# close enough to grab -- by which time there is a whole hand to grab with.
#
# ⚠ THE MARGIN MUST GATE SNAPPING TOO, not just release. Gating only the release
# would drop the cube and let the same half-visible hand re-snap it on the very
# next frame, which is a flap, not a fix.
#
# ⭐⭐ THE MARGIN -- 60 px, the owner's "half a hand width at 40 cm". It is now the
# INSET of the play area (see `clamp_to_play_area`).
# Derived two independent ways, which agree:
#   * OPTICAL (pinhole, hand breadth 85 mm): half a hand width at 40 cm is
#     49-65 px across plausible webcam FOVs -- 59 px at a typical 60 deg.
#   * EMPIRICAL: the corpus's p99 palm width is 127 px, which at 60 deg implies
#     0.37 m -- so 40 cm IS the closest the operator actually works, and half of
#     that width is 63 px.
#
# ⛔⛔ AN ADAPTIVE MARGIN (0.5 x the CURRENT palm width) WAS BUILT FIRST AND IS
# WRONG. It is more elegant, it is literally "half a hand width" at any distance,
# and it FAILED LIVE the first time it was tried -- owner, 2026-08-22: *"the
# margin seems inconsistent: when I grab the cube close to the margin and go
# beyond the margin again, the cube follows beyond the margin."*
#
# The measurement, from `2026-08-22_214607_u9_edge_margin_debug_test` f594-f595:
#
#     f594  width 50.9 px  margin 25.4  edge-dist 22.5  -> beyond, DROP
#     f595  width 28.2 px  margin 20.0  edge-dist 30.8  -> NOT beyond, re-grabs
#
# The measured palm width collapsed 45% in ONE frame, so the margin collapsed
# with it and the hand was no longer outside its own margin -- it re-grabbed and
# carried the cube out of frame, which is exactly the reported symptom.
# ⚠ And this is NOT a systematic edge effect that could be corrected for: bucketed
# by distance-to-edge, the median width is flat (84 px at 0-25 px from the edge,
# 87 px at 200 px). It is per-frame JITTER -- and an adaptive threshold inherits
# the jitter of its own input precisely where the decision matters most.
#
# ⭐ THE LESSON, worth more than the constant: a threshold must not be computed
# from a quantity that is noisy in the regime the threshold governs. Half a hand
# width is the right SIZE; the current frame's hand is the wrong way to measure it.
EDGE_MARGIN_PX = 60.0

# ⚠ NO HYSTERESIS, deliberately. DR-2 needs it (EXIT_HYSTERESIS_FACTOR) because
# its input dithers; this input is a hand CENTRE position, which is smooth. The
# chatter that was observed came entirely from the adaptive width above, and it
# goes away with the fixed margin. Add hysteresis only if boundary flapping is
# actually seen, and measure it first.


def clamp_to_play_area(x, y, size, frame_size, margin_px=EDGE_MARGIN_PX):
    """Clamp a cube's TOP-LEFT so the WHOLE cube stays inside the play area.

    ⭐⭐ THE PLAY AREA IS THE POINT, and it is a different rule from the hand
    margin above -- owner, 2026-08-23: *"I can still push step by step the cube to
    the edge of the display window, which I would like to avoid: I want the cube
    to be constrained in a smaller window within a display window (hence the
    margin); currently this is not robustly implemented."*

    ⚠ WHY THE HAND RULE ALONE COULD NEVER DO THIS, which is the lesson: translation
    is GRAB-RELATIVE (§14.1), so the cube keeps whatever offset it had from the
    hand at the moment of the grab. The cube can therefore sit much closer to the
    edge than the hand centre does, and every grab-push-drop cycle re-establishes
    a new offset and walks it further out. `beyond_edge_margin` decides WHEN TO
    LET GO; only a positional clamp decides WHERE THE CUBE MAY BE. One is a
    trigger, the other an invariant, and the trigger cannot enforce the invariant.

    ⭐ Stateless and absolute: no history, nothing to drift, nothing to "fluctuate".

    ⚠⚠ THIS IS A 2D RULE AND IT MUST BE REVISITED WHEN 4.2 (Z-AXIS) LANDS.
    The display is the camera's FIELD OF VIEW -- a frustum, not a box -- so an
    object's PROJECTED extent shrinks as it moves away and grows as it comes
    near. `size` here is a constant today only because nothing drives Z yet.
    Once it does:
      * `size` must become the object's extent AS PROJECTED at its current depth,
        not its nominal size. Otherwise a distant object is held needlessly far
        from the edge, and -- the dangerous direction -- a NEAR object's real
        footprint exceeds the margin and can still overflow the play area.
      * ✅ AND THE SHAPE IS DECIDED (owner, 2026-08-23): **a WORLD-SPACE VOLUME,
        accounting for the camera frustum** -- not a screen-space rectangle. So
        the clamp moves into world coordinates: at the object's depth, take the
        frustum's lateral extent, inset it by the world margin, clamp the
        object's world position inside that, then project. ⭐ The on-screen
        boundary will MOVE with depth (inward as the object recedes). That is the
        intended consequence, not a regression.
      * ⭐⭐ THE MARGIN IS ALREADY A WORLD QUANTITY, so this is a change of UNITS,
        not of the number: it was derived as HALF A HAND BREADTH AT 40 cm =
        **42.5 mm**, and EDGE_MARGIN_PX is just its projection there (554 px
        focal length * 0.0425 m / 0.40 m = 58.9 px). At other depths the same
        42.5 mm is 78 px at 0.30 m, 34 px at 0.70 m, 24 px at 1.00 m.
        **Carry 42.5 mm forward, not 60 px.**
    ⚠ Do this in the same pass as U2's bounding-radius change: both replace the
    `size` term, and doing them separately means touching this twice.
    Recorded in queue rows 4.2, U9 and U2.

    ⚠ DEGENERATE CASE: if the play area is narrower than the cube (a tiny window,
    or a margin larger than half of it) the clamp would invert and pin the cube to
    a nonsense corner. Centre it instead -- the least surprising thing, and it
    keeps the cube on screen."""
    if not frame_size:
        return (x, y)
    w, h = frame_size[0], frame_size[1]
    if w <= 0 or h <= 0:
        return (x, y)

    def _axis(v, extent):
        lo = margin_px
        hi = extent - margin_px - size
        if hi < lo:
            return (extent - size) / 2.0
        return max(lo, min(v, hi))

    return (_axis(x, w), _axis(y, h))


# --------------------------------------------------------------------------
# 4.2 -- THE CAMERA MODEL, AND THE PLAY AREA AS A WORLD-SPACE VOLUME
# --------------------------------------------------------------------------
# ✅ OWNER DECISION, 2026-08-23: *"the play area is a WORLD-SPACE VOLUME,
# accounting for the camera frustum"* -- not a screen-space rectangle. U9's
# `clamp_to_play_area` above is the depth-free special case that shipped while
# nothing drove Z; this is the general rule 4.2 needs.
#
# ⭐⭐ THIS IS A CHANGE OF UNITS, NOT OF THE NUMBER. The margin was always a world
# quantity -- HALF A HAND BREADTH AT 40 cm = 42.5 mm -- and `EDGE_MARGIN_PX = 60`
# is simply its projection at that one depth. Carried forward as metres it now
# projects correctly at EVERY depth:
#
#     depth   0.30 m   0.40 m   0.70 m   1.00 m
#     margin  78 px    59 px    34 px    24 px
#
# ⭐ SO THE ON-SCREEN BOUNDARY MOVES WITH DEPTH -- inward as the object recedes,
# outward as it approaches. That is the intended consequence of the decision, not
# a regression. Do not "fix" it.
#
# ⭐ AND IT FIXES A LATENT RESOLUTION BUG ON THE WAY. `EDGE_MARGIN_PX` is a fixed
# pixel count, so on a 1280-wide webcam it was half the intended world size. The
# focal length below scales with the frame, so the world margin does not.
#
# ⚠ THE ONE ASSUMPTION, STATED PLAINLY: the horizontal field of view. Nothing in
# this project ever calibrated the camera, and U9's own derivation already leaned
# on "a typical 60 deg" webcam -- so this constant is not a new assumption, it is
# the SAME assumption U9 made, now written down in one place instead of being
# baked into a pixel count. ⚠ It only ever sets the SCALE between metres and
# pixels; every quantity that matters for feel (the margin, the grab radius) was
# tuned in pixels at the reference depth and is reproduced there exactly.
CAMERA_HFOV_DEG = 60.0

# ⭐⭐ WHERE AN OBJECT LIVES, AND THE DEPTH AT WHICH ITS `size` IS ITS TRUE
# PROJECTION. **MEASURED, NOT CHOSEN** (`analysis/m9_working_distance.py`, 86 109
# trusted hand-frames across 65 corpus sessions, using the shipped estimator):
#
#     p1     p5     p25    MEDIAN   p75    p95    p99
#     0.309  0.372  0.443  0.497    0.558  0.668  0.837
#
# ⚠⚠ AND THE OBVIOUS VALUE WAS WRONG. 0.40 m was the first choice, because U9
# derived its margin there and its row says "40 cm IS the closest the operator
# actually works". ⭐ THAT SENTENCE IS ABOUT THE **CLOSEST APPROACH** -- it reads
# the corpus's **p99** palm width. The TYPICAL distance is 10 cm further, and it
# is the typical distance an object must sit at to be reachable. Measured against
# 4.2's own axial gate (+/-0.15 m):
#
#     object at 0.40 m -> 70.9% of trusted hand-frames could pass
#     object at 0.497 m -> 91.1%
#
# ⛔ A quarter of all frames unable to pick anything up would have looked like a
# BROKEN BUILD, not a mis-sized constant -- exactly the failure this project
# keeps paying for when a plausible number is shipped instead of a measured one.
# Re-run the harness if the camera, the FOV assumption or the operator's setup
# changes; the constant is a property of the setup, not of the code.
REFERENCE_DEPTH_M = 0.50

# The depth U9's `EDGE_MARGIN_PX = 60` was derived at, kept ONLY so the golden
# vectors can assert that the world margin and the pixel margin it replaces still
# meet there. ⚠ Not a reference for anything else -- the margin is 42.5 mm at
# every depth, which is the whole point of the world form.
U9_DERIVATION_DEPTH_M = 0.40

# Half a hand breadth (85 mm anthropometric median). U9's 60 px, in metres.
PLAY_AREA_MARGIN_M = 0.0425

# ⚠⚠ THE VOLUME IS BOUNDED IN Z TOO, and the bound decides something less obvious
# than "the object shrinks to a dot": **an object may only be pushed to a depth
# the hand can come back to.** Release freezes an object in place in all three
# axes, and re-grabbing needs the hand within `GRAB_Z_TOLERANCE_M` of it -- so a
# wall placed beyond the operator's reach would let an object be parked somewhere
# it can never be picked up again. It is the WALLS that bound re-grabbability,
# not the tolerance.
#
# ⭐ SO THE WALLS ARE THE MEASURED RANGE OF DEPTHS THE HAND ACTUALLY VISITS,
# p1..p99 = 0.309..0.837 m over 86 109 trusted frames
# (`analysis/m9_working_distance.py`), rounded to 0.30..0.85. Every reachable
# depth stays reachable, and nothing outside the operator's own demonstrated
# range is offered. ⚠ Cross-checked against the independent reach measurement:
# `analysis/m9_depth_envelope.py` puts a deliberate push/pull at ratio 0.53..1.89
# (3.59x), i.e. 0.26..0.94 m from a 0.50 m rest -- so both walls sit INSIDE the
# arm's envelope with margin, which is what makes them reachable rather than
# merely permitted.
#
# Geometry check at the walls, 640x480: at 0.30 m the large object projects to
# 133 px and its margin to 79 px, leaving a 483x323 play area -- still usable; at
# 0.85 m the small object is 24 px, still visible and still hittable laterally.
PLAY_DEPTH_MIN_M = 0.30
PLAY_DEPTH_MAX_M = 0.85


def focal_px(frame_size):
    """Pinhole focal length in pixels, from the frame width and CAMERA_HFOV_DEG.

    640 px wide at 60 deg -> 554.3 px, which is the number U9's margin
    derivation quoted (554 * 0.0425 / 0.40 = 58.9 px ~ EDGE_MARGIN_PX). ⭐ That
    agreement is asserted as a golden vector in `analysis/verify_play_area.py`:
    the world rule and the pixel rule it replaces must meet at
    `U9_DERIVATION_DEPTH_M`, or one of them is wrong.
    """
    if not frame_size or not frame_size[0] or frame_size[0] <= 0:
        return None
    return (frame_size[0] / 2.0) / math.tan(math.radians(CAMERA_HFOV_DEG) / 2.0)


def clamp_depth(depth_m):
    """Confine a depth to the play volume's Z extent."""
    return max(PLAY_DEPTH_MIN_M, min(float(depth_m), PLAY_DEPTH_MAX_M))


def projected_size_px(nominal_size_px, depth_m, reference_depth_m=REFERENCE_DEPTH_M):
    """An object's on-screen extent at `depth_m`, given its extent at the
    reference depth.

    ⭐ THE FOCAL LENGTH CANCELS. The object's real size is
    `nominal_size_px * reference_depth / f`, and projecting that back at
    `depth_m` multiplies by `f / depth_m` -- so this is frame-size independent
    and carries none of `CAMERA_HFOV_DEG`'s uncertainty.

    ⚠ THIS IS NOT THE DROPPED DEPTH-PROXY SCALE EFFECT (§14.3 decision 4). The
    object's REAL size never changes; only its projection does, which is what
    "real size stays fixed per-object" means under a perspective camera. Without
    it Z-translation would be literally invisible on screen.
    """
    if depth_m is None:
        return float(nominal_size_px)
    return float(nominal_size_px) * reference_depth_m / clamp_depth(depth_m)


def world_from_px(x_px, y_px, depth_m, frame_size):
    """Image point -> world offset from the optical axis, in metres, at `depth_m`.

    The optical axis is taken at the frame CENTRE (no principal-point
    calibration exists, and none is needed: the play volume is symmetric about
    the same centre, so any offset would cancel out of the clamp anyway).
    """
    f = focal_px(frame_size)
    if f is None or depth_m is None:
        return None
    return ((x_px - frame_size[0] / 2.0) * depth_m / f,
            (y_px - frame_size[1] / 2.0) * depth_m / f)


def px_from_world(x_m, y_m, depth_m, frame_size):
    """The inverse of `world_from_px`."""
    f = focal_px(frame_size)
    if f is None or depth_m is None:
        return None
    return (x_m * f / depth_m + frame_size[0] / 2.0,
            y_m * f / depth_m + frame_size[1] / 2.0)


def clamp_to_play_volume(cx_px, cy_px, depth_m, nominal_size_px, frame_size,
                         margin_m=PLAY_AREA_MARGIN_M,
                         reference_depth_m=REFERENCE_DEPTH_M):
    """Clamp an object's CENTRE into the play volume. Takes and returns PIXELS.

    Written the way the decision states it, deliberately, rather than as the
    algebraically-equal one-liner: at the object's depth take the frustum's
    lateral extent, inset it by the world margin AND by the object's own world
    half-extent, clamp the object's WORLD position inside that, then project.
    A reader looking for the owner's rule should find the owner's rule.

    ⚠ Takes the object's NOMINAL size (its extent at the reference depth) and
    projects it here, so no caller can pass a stale projected size.

    ⚠ FALLS BACK TO THE 2D RULE when there is no usable depth or frame size --
    `clamp_to_play_area` above, unchanged. An object whose depth was never
    driven must still be confined; degrading to the depth-free rule is the
    honest answer, and it is exactly the behaviour that shipped in U9.

    ⚠ DEGENERATE CASE, same policy as the 2D rule: if the play area at this
    depth is narrower than the object, centre it rather than invert the clamp.
    """
    f = focal_px(frame_size)
    if f is None or depth_m is None or not frame_size or frame_size[1] <= 0:
        size = projected_size_px(nominal_size_px, depth_m, reference_depth_m)
        tl = clamp_to_play_area(cx_px - size / 2.0, cy_px - size / 2.0,
                                size, frame_size)
        return (tl[0] + size / 2.0, tl[1] + size / 2.0)

    z = clamp_depth(depth_m)
    # The object's real half-extent, recovered from its size at the reference
    # depth. Constant with depth -- that is the whole point of a world volume.
    half_extent_m = (nominal_size_px / 2.0) * reference_depth_m / f

    world = world_from_px(cx_px, cy_px, z, frame_size)
    out = []
    for v, extent_px in ((world[0], frame_size[0]), (world[1], frame_size[1])):
        frustum_half_m = (extent_px / 2.0) * z / f      # the FOV at this depth
        limit = frustum_half_m - margin_m - half_extent_m
        if limit < 0.0:
            out.append(0.0)                              # degenerate -> centred
        else:
            out.append(max(-limit, min(v, limit)))
    return px_from_world(out[0], out[1], z, frame_size)


def palm_width_px(landmarks):
    """Hand breadth across the knuckles, in pixels: index_MCP to pinky_MCP.

    ⚠ Kept, but NOT used by the edge margin -- see EDGE_MARGIN_PX. It jitters by
    tens of percent frame to frame, which is why the margin is fixed."""
    return math.hypot(landmarks[INDEX_MCP][0] - landmarks[PINKY_MCP][0],
                      landmarks[INDEX_MCP][1] - landmarks[PINKY_MCP][1])


def is_thumb_outward(landmarks, handedness):
    """True when the hand shows its BACK to the camera (thumb outward) --
    GESTURE_PIPELINE_SPEC.md §13.6, GAME_RULES.md rule 3.

    `handedness` is the MIRRORED/apparent hand, which is what both pipeline paths
    deliver (spec §0.9) -- production via `_mirror_handedness()` after detecting on
    an un-mirrored frame, the debug tool directly from detecting on a mirrored one.
    Passing the raw un-mirrored label here inverts the result: that was the
    production-only bug of 2026-08-01.

    Calibrated live 2026-08-01 and re-verified 2026-08-03 against four
    known-hand/known-facing clips (788/788 frames, spec §0.9).
    """
    cross = signed_palm_area(landmarks)
    if handedness == "Left":
        cross = -cross
    return cross > 0


def is_edge_on(landmarks, threshold=EDGE_ON_THRESHOLD):
    """True when the palm is too close to edge-on for the sign to be trusted.
    DR-2's gate (item 2.2) -- consumers should suppress palm-facing-dependent
    decisions rather than act on a coin-flip sign."""
    return edge_on_measure(landmarks) < threshold


# --------------------------------------------------------------------------
# DR-2 -- edge-on exclusion (merged queue item 2.2, spec M5e)
# --------------------------------------------------------------------------
# Exit hysteresis: once inside the band, require edge-on to climb clearly ABOVE
# the entry threshold, and stay there, before per-frame updates resume. Without
# the gap, a value dithering around 0.15 would flap in and out of the band.
EXIT_HYSTERESIS_FACTOR = 1.6          # spec M5e: exit above THRESHOLD * 1.6 = 0.24
EXIT_DWELL_MS = 100.0                 # spec M5e says "3 consecutive frames"; that was
                                      # written assuming 30 fps, so the INTENT is 100 ms
                                      # (finding N1: frame-count parameters were ~38%
                                      # longer in wall-clock than intended).
# ⭐ N7 EXAMINED HERE AND DELIBERATELY NOT APPLIED (2026-08-04). Measured.
#
# N7 made `hand_identity`'s dwells frame-rate-driven, and the obvious next step
# was to do the same here. It was built, measured, and REVERTED:
#
#   * This dwell is a DEBOUNCE -- "resume only after N consecutive confirmations"
#     -- not a physical duration. Consecutive-confirmation counts belong in
#     frames. N1's "re-express frame parameters in ms" applies to dwells that
#     represent real elapsed time, which DR-1's voting windows are and this
#     is not.
#   * The shipped count exits on the SECOND consecutive above-threshold frame,
#     i.e. after ONE frame interval (~42 ms at 24 fps) -- not the ~83 ms a naive
#     reading of "2 frames" suggests. A time-based 100 ms dwell therefore needs
#     FOUR frames at 24 fps, and measured across the corpus it froze DR-2 for
#     **+47.4% more frames** (595 -> 877), lengthening exactly the staleness
#     window `GAME_RULES.md` rule 3 warns about.
#   * That is a felt behaviour change to a rule-affecting mechanism, bought for
#     no correctness gain. `analysis/n7_dr2_dwell_ab.py` reproduces it.
#
# So the frame count STAYS, and `_ASSUMED_FPS` here is not the same defect as
# the one N7 fixed in `hand_identity`: nothing about a 2-frame debounce depends
# on knowing the frame rate. The name is kept only because the arithmetic below
# is a frames-per-ms convenience, not a rate assumption anything acts on.
_ASSUMED_FPS = 24.0
EXIT_DWELL_FRAMES = max(1, round(EXIT_DWELL_MS * _ASSUMED_FPS / 1000.0))


class PalmFacingTracker:
    """DR-2: freeze the palm/back sign while the palm is too close to edge-on.

    WHY (measured, not assumed -- spec §0.2/§0.3): the sign is rock-stable when
    well-conditioned (ZERO flips in 3130 frames above edge-on 0.60) and chatters
    violently near edge-on (765 flips per 1k frames below 0.05 -- physically
    impossible as real rotation at that rate). The band below 0.15 is never
    entered during normal motion (`non_crossing` never dropped below 0.353), so
    this fires ONLY during a deliberate palm<->back crossing. That is what makes
    it cheap and safe.

    WHAT IT PROTECTS, concretely: rule 3 disarms its snap exception on a single
    thumb-inward reading (`if not thumb_outward: allowed = False`). One spurious
    flip mid-crossing therefore silently revokes the exception. Freezing the value
    through the band removes that failure mode.

    ⚠ PARTIAL vs. the spec. M5e also wants the sign CARRIED THROUGH the band by
    integrating angular velocity from M6 (the kinetic-depth effect), so a genuine
    crossing registers instantly on exit. **M6 is item 2.3 and is not built**, so
    that half is absent. Consequence: a real crossing is still detected correctly,
    but only once the hand leaves the band and the exit dwell elapses -- i.e.
    slightly LATE, never wrong. Revisit when 2.3 lands.
    """

    def __init__(self, threshold=EDGE_ON_THRESHOLD):
        self.threshold = threshold
        self.exit_threshold = threshold * EXIT_HYSTERESIS_FACTOR
        self.frozen = None        # last confident thumb-outward value
        self.in_band = False
        self.exit_run = 0         # consecutive frames above the exit threshold
        # U7: chirality resolved from geometry rather than from MediaPipe's label.
        # ⭐ IT LIVES HERE ON PURPOSE. `update()` is the ONE place the handedness
        # label enters the palm/back cue in either tool, so fixing it here fixes
        # production and the debug tool in a single edit -- N6, "shared, never
        # copied". Putting it in the two call sites instead is precisely how
        # §13.6.1's production-only inversion happened.
        self.chirality = ChiralityResolver()
        # ⭐ Which TRACK this tracker's held state belongs to. Slot-keyed state
        # inherited across a relabel is post-mortem §3.4, and it was still live
        # after the T3 ownership remap: measured 2026-08-22 in
        # `2026-08-22_185958_t3_remap_debug_test` at f1050, where track t9 moved
        # from slot Right to slot Left, inherited t5's chirality, and its
        # back-of-hand read as PALM for two frames -- long enough to grab a cube
        # that rule 3 should have refused.
        self._track_id = None
        # diagnostics
        self.band_entries = 0
        self.frames_frozen = 0
        self.chatter_suppressed = 0
        self.track_changes = 0

    @property
    def chirality_confirmed(self):
        """False while this hand's chirality is still PROVISIONAL (U8).

        ⭐ Rule 3 must consult this, not just `thumb_outward`. `thumb_outward` is
        computed FROM the chirality, so a provisional chirality yields a
        confidently-wrong palm/back answer -- measured: a back-of-hand hand read
        as PALM and grabbed a cube rule 3 forbids
        (`2026-08-22_190955_t3_remap_production_test`, f664)."""
        return self.chirality.confirmed

    @property
    def orientation_valid(self):
        """False while the sign is being held rather than measured. Maps to
        `HandState.quality.orientationValid` when that contract lands."""
        return not self.in_band

    def update(self, landmarks, handedness, world_landmarks=None, track_id=None,
               now_ms=None):
        """Returns (thumb_outward, orientation_valid).

        `thumb_outward` is the value the gesture layer should act on: measured
        when well-conditioned, frozen while inside the band.

        ⭐ U7: `world_landmarks` is OPTIONAL and additive. Supplied, the chirality
        correction is driven by geometry (`ChiralityResolver`) instead of by
        MediaPipe's 10.8%-wrong label; omitted -- or with `GEOMETRIC_CHIRALITY`
        off -- behaviour is bit-identical to before. So a caller that has not been
        migrated is not silently broken, it is merely not yet fixed.

        ⚠ `now_ms` IS NOT FOR DR-2's DWELL, and the distinction matters. DR-2's
        exit dwell stays a frame COUNT: it is a consecutive-confirmation debounce,
        and a time-based version was built and measured to freeze DR-2 47% longer
        for no correctness gain (N7). `now_ms` feeds only U8's confirmation
        window, which IS a physical transit time and must therefore be a duration.
        Two dwells in one class, deliberately in different units, each in the unit
        that matches what it represents.
        """
        # ⛔ A DIFFERENT HAND IN THIS SLOT INHERITS NOTHING (post-mortem rule 2).
        # Chirality and palm/back are properties of a PHYSICAL hand, so held state
        # is meaningless once the track changes -- and worse than meaningless: it
        # INVERTS the answer, because `is_thumb_outward` is chirality-dependent.
        # ⚠ Only a real id (>= 0) may trigger this. -1 is DR-1's "no identity this
        # frame"; treating it as a change would reset constantly and throw away
        # good state, and treating two -1s as the same hand would be worse still.
        if (track_id is not None and track_id >= 0
                and self._track_id is not None and track_id != self._track_id):
            self.reset()
            self.track_changes += 1
        if track_id is not None and track_id >= 0:
            self._track_id = track_id

        eo = edge_on_measure(landmarks)
        chirality = self.chirality.update(world_landmarks, handedness, now_ms)
        measured = is_thumb_outward(landmarks, chirality)

        if self.frozen is None:
            # First sighting. Trust it even if edge-on: there is nothing to freeze
            # to, and refusing to produce a value would block snapping outright.
            self.frozen = measured

        if not self.in_band:
            if eo < self.threshold:
                self.in_band = True
                self.exit_run = 0
                self.exit_started_ms = None
                self.band_entries += 1
            else:
                self.frozen = measured
                return measured, True
        else:
            # Inside the band: only a clear, sustained recovery resumes updates.
            if eo > self.exit_threshold:
                self.exit_run += 1
                if self.exit_run >= EXIT_DWELL_FRAMES:
                    self.in_band = False
                    self.exit_run = 0
                    self.frozen = measured
                    return measured, True
            else:
                self.exit_run = 0

        self.frames_frozen += 1
        if measured != self.frozen:
            # The raw cue disagreed with the held value while untrustworthy --
            # precisely the chatter this exists to absorb.
            self.chatter_suppressed += 1
        return self.frozen, False

    def reset(self):
        """Drop held state (hand lost / track ended) without clearing counters.

        ⭐ U7: the resolved chirality is dropped too. A returning hand is a NEW
        hand and must inherit nothing -- the 4.1 post-mortem's rule 2, whose
        violation (seeding new tracks from slot state) is what froze every cube."""
        self.frozen = None
        self.in_band = False
        self.exit_run = 0
        self.chirality.reset()
        self._track_id = None


# --------------------------------------------------------------------------
# Palm observability (M6b's metric, queue item 2.3) -- NO numpy, by design
# --------------------------------------------------------------------------
# Deliberately closed-form arithmetic. The perception layer is meant to be
# REIMPLEMENTED against the HandState contract for the web/mobile port, and numpy
# has no direct equivalent in JS/Swift/Kotlin -- a numpy dependency here turns a
# transliteration into a rewrite. Everything below is +-*/ and trig, so it ports
# line by line. (Owner decision 2026-08-03: "do what is best, considering the
# future transport to web.")
#
# WHY THIS METRIC AND NOT THE SHIPPED ONE (measured, spec §0.12):
#     observability     range 0.046 - 0.908 across the corpus
#     conditioning_norm range 0.058 - 0.092   <- barely discriminates
# observability collapses to 0.05-0.15 at exactly the pitch crossings and sits at
# 0.75-0.91 on every control sequence. They correlate only 0.27-0.81, so they are
# NOT the same signal. A6 forbids shipping both; this is the one to keep.
#
# NOTE: M6b's SVD *frame* was measured and REJECTED (2.1x more >30 deg jumps than
# the shipped Gram-Schmidt frame). Only the METRIC is adopted -- this function
# deliberately computes singular values WITHOUT constructing a frame.

PALM_3D_LANDMARKS = (0, 5, 9, 13, 17)   # wrist + 4 MCPs; landmark 1 (thumb CMC) moves


def _symmetric_3x3_eigenvalues(a00, a01, a02, a11, a12, a22):
    """Eigenvalues of a real symmetric 3x3 matrix, descending. Closed form
    (Smith's trigonometric method) -- no iteration, no library.

    Returns (l1, l2, l3) with l1 >= l2 >= l3 >= 0 for a positive-semidefinite
    input such as a scatter matrix.
    """
    p1 = a01 * a01 + a02 * a02 + a12 * a12
    if p1 <= 1e-24:
        # Already diagonal.
        ls = sorted((a00, a11, a22), reverse=True)
        return ls[0], ls[1], ls[2]

    q = (a00 + a11 + a22) / 3.0
    d0, d1, d2 = a00 - q, a11 - q, a22 - q
    p2 = d0 * d0 + d1 * d1 + d2 * d2 + 2.0 * p1
    p = math.sqrt(p2 / 6.0)
    if p <= 1e-18:
        return q, q, q

    # B = (A - qI)/p ; r = det(B)/2
    b00, b11, b22 = d0 / p, d1 / p, d2 / p
    b01, b02, b12 = a01 / p, a02 / p, a12 / p
    det_b = (b00 * (b11 * b22 - b12 * b12)
             - b01 * (b01 * b22 - b12 * b02)
             + b02 * (b01 * b12 - b11 * b02))
    r = max(-1.0, min(1.0, det_b / 2.0))

    phi = math.acos(r) / 3.0
    l1 = q + 2.0 * p * math.cos(phi)
    l3 = q + 2.0 * p * math.cos(phi + 2.0 * math.pi / 3.0)
    l2 = 3.0 * q - l1 - l3        # trace is preserved
    return l1, l2, l3


def palm_observability(world_landmarks):
    """M6b's `observability` = 1 - S3/S2 of the centred palm point set.

    0 = the palm points are collinear-in-projection, so the palm normal is
    unobservable (the pitch-crossing degeneracy). 1 = well-conditioned.

    Computed from the 3x3 scatter matrix's eigenvalues rather than an SVD:
    singular values of the centred matrix P are sqrt of the eigenvalues of P^T P,
    so S3/S2 == sqrt(l3/l2). Same number, no numpy.

    Returns 0.0 when the fit is degenerate or landmarks are missing.
    """
    pts = []
    for i in PALM_3D_LANDMARKS:
        if i >= len(world_landmarks):
            return 0.0
        p = world_landmarks[i]
        if p is None or len(p) < 3:
            return 0.0
        pts.append((float(p[0]), float(p[1]), float(p[2])))

    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    cz = sum(p[2] for p in pts) / n

    a00 = a01 = a02 = a11 = a12 = a22 = 0.0
    for x, y, z in pts:
        dx, dy, dz = x - cx, y - cy, z - cz
        a00 += dx * dx
        a01 += dx * dy
        a02 += dx * dz
        a11 += dy * dy
        a12 += dy * dz
        a22 += dz * dz

    l1, l2, l3 = _symmetric_3x3_eigenvalues(a00, a01, a02, a11, a12, a22)
    if l2 <= 1e-24:
        return 0.0
    ratio = max(0.0, l3) / l2          # clamp: tiny negatives are round-off
    return 1.0 - math.sqrt(min(1.0, ratio))


def verify_matches_analyser(landmarks_list, analyser_edge_on, tol=1e-9):
    """Assert this module agrees with AnalyzePerceptionSequences.edge_on().

    Kept here rather than in the test so the invariant sits next to the code it
    constrains. Returns (max_abs_diff, n_compared); raises on disagreement.
    """
    worst = 0.0
    n = 0
    for lm in landmarks_list:
        _s, expected = analyser_edge_on(lm)
        got = edge_on_measure(lm)
        worst = max(worst, abs(got - expected))
        n += 1
    if worst > tol:
        raise AssertionError(
            f"edge_on_measure has DRIFTED from AnalyzePerceptionSequences.edge_on(): "
            f"max abs diff {worst:g} over {n} frames. Every recorded threshold "
            f"(EDGE_ON_THRESHOLD=0.15) is expressed in the analyser's scale, so this "
            f"must stay exact."
        )
    return worst, n
