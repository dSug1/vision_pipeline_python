"""ARCHIVE -- the predictive / reliability-weighted hand-orientation filter.

⛔⛔ NOT IMPORTED BY ANYTHING. REMOVED FROM BOTH TOOLS ON 2026-08-24 (owner:
*"remove the predictive orientation filter (keep it for archive we can refer to
later on if ever we need in the future)"*). Kept whole, with its rationale and the
measurement that retired it, because a filter that was once justified is worth
being able to reconstruct exactly rather than half-remember.

WHAT IT WAS
-----------
A constant-angular-velocity predictor fused with the raw per-frame orientation,
weighted by how well-conditioned the palm's vector pair was that frame:

    predicted = omega * last_fused                  (constant angular velocity)
    alpha     = _reliability_alpha(conditioning_norm)
    fused     = slerp(predicted, raw, alpha)        (alpha 1 = trust the raw frame)
    omega     = fused * conj(last_fused)            (re-estimate the velocity)

`alpha` fell toward 0 as the palm's two vectors became parallel -- i.e. it leaned
on the prediction exactly where the instantaneous estimate was least trustworthy.
Reset to a fresh instance whenever the hand was not detected, so reacquiring after
a gap never predicted from a stale reference. Design and live-test write-up:
GESTURE_PIPELINE_SPEC.md §13.7.

⭐ IT WAS A REAL FIX FOR THE ESTIMATOR IT WAS BUILT AGAINST. The rotation source at
the time was the Gram-Schmidt frame over three vectors, whose orthogonalisation
denominator collapses exactly where the palm foreshortens: p50 1.59, p95 21.91,
**max 144.19 deg of single-frame excursion**. Against that signal, prediction-plus-
conditioning-weight measurably cut the large jumps (>30 deg frames down ~4-5x,
>60 deg ~2-3x across matched recordings).

WHY IT WAS REMOVED -- IT HAD BECOME DEAD CODE, AND THAT IS MEASURED
-------------------------------------------------------------------
⭐⭐ Horn least-squares over the five palm landmarks shipped on 2026-08-17 and
REPLACES this filter's output whenever it succeeds:

    hand_quat_now = _predictive_filter_step(...)     # ran, then was overwritten
    if rotation is not None:
        _d = rotation.delta(...)
        if _d is not None:
            hand_quat_now = _d                       # <-- always taken

The filter's value therefore survived only on frames where Horn FAILED. Measured
over **9091 hand-frames across four recordings** (`t6d_ab_ghost`, `t6d_psi_sweep`,
`yaw_card_axis_check_b`, `roll_card_axis_check_b`):

    Horn returned None on 0 of 9091 frames  --  0.0000%

**So the filter contributed nothing to the cube's orientation on any recorded
frame.** It cost a quaternion slerp, a multiply and per-hand state per frame, and
it made the rotation path read as though two filters were stacked when only one
was: the `ROTATION_SLERP_FACTOR` blend on the cube.

⚠ WHAT WAS KEPT. `_reliability_alpha(conditioning_norm)` STAYS in both tools --
it is a conditioning measure, not part of this filter, and it still drives the
on-screen `reliability` readout that tells the operator when the palm is
degenerate. Only the prediction/fusion above was removed.

⚠ IF THIS IS EVER REVIVED, CHECK THE PREMISE FIRST. It presumes the per-frame
orientation is noisy enough to be worth predicting through. That was true of
Gram-Schmidt (p95 21.91 deg) and is much less true of Horn (p95 11.71 deg over the
palm, 2.91 with the fingertips). Re-measure the estimator's own jitter before
re-adding a predictor for it -- and note that B8 measured every velocity fit in
this project LOSING to simply holding the last value.

⚠ NOT THE SAME THING as `Resources/orientation_filter.py` (the UKF explored under
queue item 2.3, five attempts, all null). That module is still used by the
`analysis/` harnesses and is untouched by this removal.

The code below is the production copy as it stood at removal. `Quat`, `_quat_*`
and `_make_continuous` are the callers' own helpers and are not reproduced here.
"""

IDENTITY_QUATERNION = (1.0, 0.0, 0.0, 0.0)


class HandOrientationFilter:
    """Per-hand predictive/reliability-weighted orientation filter state.

    `last_fused` is the filter's own running orientation estimate (this frame's
    output, next frame's prediction base); `omega` is the most recently observed
    per-frame rotation delta among accepted/fused frames (constant-angular-velocity
    model). Reset to a fresh instance whenever the hand isn't detected, so
    reacquiring tracking after a gap never predicts from a stale reference."""

    def __init__(self):
        self.last_fused = None
        self.omega = IDENTITY_QUATERNION


def predictive_filter_step(filt, raw_quat, conditioning_norm,
                           reliability_alpha, quat_multiply, quat_conjugate,
                           quat_slerp, make_continuous):
    """Advances `filt` by one frame and returns the fused orientation.

    ⚠ Helpers are passed in rather than imported: this module is an ARCHIVE and
    must not create an import edge into the live tools. To revive it, inline the
    body back into the caller and drop the parameters.
    """
    if filt.last_fused is None:
        filt.last_fused = raw_quat
        return raw_quat
    raw_quat = make_continuous(raw_quat, filt.last_fused)
    predicted = make_continuous(quat_multiply(filt.omega, filt.last_fused),
                                filt.last_fused)
    alpha = reliability_alpha(conditioning_norm)
    fused = quat_slerp(predicted, raw_quat, alpha)
    filt.omega = quat_multiply(fused, quat_conjugate(filt.last_fused))
    filt.last_fused = fused
    return fused
