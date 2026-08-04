"""M4 -- per-hand consistency gate (merged queue item 1.6).

Decides, per hand per frame, whether the measurement is plausible enough to be
accepted or should be rejected and coasted through. Pure stdlib, numpy-free, no
import side effects -- same contract as `palm_geometry.py`, `hand_identity.py`
and `hand_anatomy.py`, so production and the debug tool import it rather than
each keeping a copy.

WHAT THIS IS AND IS NOT FOR (spec A5, binding)
----------------------------------------------
This is an OCCLUSION / OUTLIER mechanism. It targets the whole-hand teleport
behind Object Jump Correction (T3, 14.1.4). It is **not** a pitch-crossing fix:
per-landmark weighting was measured to be statistically indistinguishable at the
degenerate frames, because the residual there is a correlated whole-knuckle-row
distortion. Do not read a null result on T1/T2 as an implementation failure here.

THE THREE BINDING RULES, LEARNED FROM 0.13.3's chi-2 FAILURE
------------------------------------------------------------
1. Compare against the **LAST ACCEPTED** measurement, never the last raw one.
2. **Cap consecutive rejections** (MAX_CONSECUTIVE_REJECTIONS). The chi-2 gate's
   cascade -- one rejection makes the prediction drift, so the next frame fails
   too, booking up to 8 rejections from one bad frame -- is what manufactured its
   own failure, and it is also what inflated the retracted "motion model is weak"
   statistic (0.15, VERDICT 2).
3. Evaluate **POSITION first.** The chi-2 null condemned orientation gating only.

⭐ WHAT THIS MODULE DOES **NOT** USE, AND WHY (ablation, 2026-08-04)
-------------------------------------------------------------------
Four cues were built and ablated against each other on the corpus
(`analysis/m4_gate_ab.py`). Two were REMOVED for failing to earn their keep --
recorded here so they are not re-added on the assumption that more cues is
better. Removing >1.0-palm-width excursions, against 71 in the raw stream:

    configuration              rejects   >1.0 left   removed   track cost
    position + width (SHIPPED)     ~190          33       54%      0.00013
    + bone deviation                507          35       51%      0.00021
    + M3a tightening                227          33       54%      0.00013
    bone deviation ALONE            323          72       -1%      0.00016
    without position innovation     429          61       14%      0.00021

* **Bone-length deviation: REMOVED.** Adding it changed the result by ONE
  excursion (35 vs 36) while causing 296 of 507 rejections -- 58% of all
  rejections for a 2-point effect -- and alone it is worse than doing nothing
  (-1%). World-landmark bone lengths are too noisy frame-to-frame to gate on
  (0.14 measured 6-22% IQR; here the all-frames p95 of frame-to-frame change is
  51%).
* **M3a tightening: REMOVED, and this one is counter-intuitive.** Item 1.5's
  validity bit is a strong signal about ORIENTATION jumps (92% coverage, 33.8x
  lift, spec 0.16) but using it to tighten this gate made the result slightly
  WORSE (35 vs 33 excursions) at more than double the rejections. The reason is
  measured and consistent: 80.8% of the largest position innovations occur on
  anatomically VALID frames, so M3a tightens thresholds on frames that are
  mostly not the teleports, buying rejections without buying coverage.
  **M3a and this gate address different failure classes and do not compose.**

The shipped gate is therefore just TWO cues: position innovation and palm-width
collapse. Both are cheap, scale-free, and measured to matter.

WHY M3a IS NOT USED AT ALL HERE (measured, 2026-08-04)
------------------------------------------------------
Item 1.5's validity bit is **blind to the failure this module exists to catch.**
Measured across the corpus:

    innovation > 0.5 palm widths : 44.9% of those frames are anatomically VALID
    innovation > 1.0            : 68.1% valid
    innovation > 2.0            : 80.8% valid

which is exactly what 14.1.4's root cause predicts -- a teleport moves every
landmark together COHERENTLY, so the hand stays anatomically perfect while
sitting in the wrong place. It is also a poor accuser in general: it flags 25% of
the corpus and only 7.5% of flagged frames jump, so rejecting on it would discard
a quarter of the stream to catch 2% of it and make rule 2 above unsatisfiable.

**Do not wire M3a into this gate.** It was tried as a threshold-tightener and
measured to make the result worse (see the ablation above). M3a's value, if it
has one, is on the ORIENTATION side; this module is position-first by the binding
rule.

THRESHOLD PROVENANCE
--------------------
Derived from measured corpus distributions (`analysis/m4_cue_distributions.py`),
not guessed. Both cues are scale-free -- divided by palm width -- so the same
gesture at half the distance does not read as twice the error. Thresholds sit
near the ALL-frames p99.5-p99.9 so ordinary motion is never rejected; rejections
must stay rare for the anti-cascade cap to be satisfiable at all.

    cue           all p50   all p99.5   all p99.9   >60deg-jump p95
    innovation      0.018       0.481       2.715             1.566
    width |log r|   0.009       0.283       0.769             0.481
"""

import math

INNOVATION_MAX = 1.0          # palm widths, vs a constant-velocity prediction
WIDTH_LOG_RATIO_MAX = 0.5     # |ln(w_k / w_accepted)|, ~65% apparent size change

# S5 / 0.13.3, binding. Two frames at 24 fps is ~83 ms of coasting -- inside the
# 30-50 ms usable prediction envelope's tolerance and far below the 8-frame
# coast that produced the cascade.
MAX_CONSECUTIVE_REJECTIONS = 2


class FrameGate:
    """One per tracked hand. `reset()` on tracking loss, exactly like
    PalmFacingTracker -- a new track must not be judged against the old one's
    position."""

    def __init__(self,
                 innovation_max=INNOVATION_MAX,
                 width_log_ratio_max=WIDTH_LOG_RATIO_MAX,
                 max_consecutive_rejections=MAX_CONSECUTIVE_REJECTIONS):
        self.innovation_max = innovation_max
        self.width_log_ratio_max = width_log_ratio_max
        self.max_consecutive_rejections = max_consecutive_rejections
        self.reset()

    def reset(self):
        self._accepted_pos = None       # last ACCEPTED palm centroid (px)
        self._accepted_vel = (0.0, 0.0)
        self._accepted_width = None
        self._consecutive_rejections = 0

    # -- the state a caller should use while coasting --
    @property
    def last_accepted_position(self):
        return self._accepted_pos

    def predicted_position(self):
        """Constant-velocity prediction from the last ACCEPTED frame."""
        if self._accepted_pos is None:
            return None
        return (self._accepted_pos[0] + self._accepted_vel[0],
                self._accepted_pos[1] + self._accepted_vel[1])

    def update(self, landmarks_px, world_landmarks=None):
        """Judge one frame.

        landmarks_px    : 21 (x, y) image-space landmarks
        world_landmarks : accepted and ignored. Kept in the signature because
                          callers have it to hand and an earlier design used it
                          (bone deviation, M3a tightening) -- both measured not
                          to earn their keep and removed. See the module
                          docstring's ablation before adding a world-landmark
                          cue back.

        Returns a dict: accepted, reasons, forced, cues.
        `forced` marks an accept that happened only because the anti-cascade cap
        was hit -- the caller should treat that frame as low-confidence rather
        than as evidence the hand is behaving.
        """
        cues = {"innovation": None, "width_log_ratio": None}
        reasons = []

        centroid = palm_geometry_centroid(landmarks_px)
        width = palm_geometry_width(landmarks_px)
        if centroid is None or not width or width <= 1e-6:
            # Unmeasurable, not implausible. Accept and do not poison the state.
            return {"accepted": True, "reasons": ["unmeasurable"],
                    "forced": False, "cues": cues}

        if self._accepted_pos is not None:
            pred = self.predicted_position()
            cues["innovation"] = math.dist(centroid, pred) / self._accepted_width
            if cues["innovation"] > self.innovation_max:
                reasons.append(f"position innovation {cues['innovation']:.2f} "
                               f"> {self.innovation_max:.2f} palm widths")

            ratio = width / self._accepted_width
            if ratio > 0:
                cues["width_log_ratio"] = abs(math.log(ratio))
                if cues["width_log_ratio"] > self.width_log_ratio_max:
                    reasons.append(f"palm width x{ratio:.2f}")

        accepted = not reasons
        forced = False
        if not accepted and self._consecutive_rejections >= self.max_consecutive_rejections:
            # ANTI-CASCADE. Whatever we believe, the world has moved on: a
            # sustained disagreement means our reference is stale, not that the
            # sensor is wrong for the third frame running.
            accepted = True
            forced = True
            reasons.append(f"FORCED accept after {self._consecutive_rejections} "
                           f"consecutive rejections (anti-cascade cap)")

        if accepted:
            if forced:
                # Re-seed rather than resume: the old velocity described a
                # trajectory we have just admitted we lost.
                self._accepted_vel = (0.0, 0.0)
            elif self._accepted_pos is not None:
                self._accepted_vel = (centroid[0] - self._accepted_pos[0],
                                      centroid[1] - self._accepted_pos[1])
            self._accepted_pos = centroid
            self._accepted_width = width
            self._consecutive_rejections = 0
        else:
            self._consecutive_rejections += 1

        return {"accepted": accepted, "reasons": reasons,
                "forced": forced, "cues": cues}


# `hand_identity` owns these two primitives, but it lives in the SERVER's
# Resources folder while this module lives in the CLIENT's, and it imports
# nothing else useful here. Reimplementing them would be the duplication that
# caused 13.6.1, so they are defined once here and verified against
# hand_identity's versions by analysis/m4_gate_ab.py.
def palm_geometry_centroid(landmarks_px):
    try:
        pts = [landmarks_px[i] for i in (0, 5, 9, 13, 17)]
    except (IndexError, TypeError):
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def palm_geometry_width(landmarks_px):
    try:
        return math.dist(landmarks_px[5][:2], landmarks_px[17][:2])
    except (IndexError, TypeError):
        return None
