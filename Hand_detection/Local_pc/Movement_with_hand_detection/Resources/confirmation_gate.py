"""B7 -- the CONFIRMATION GATE: a selective fixed-lag smoother over the block state.

Owner design, 2026-08-04 (BUILD_PREDICTION_GATE.md 1.1):

    "F-7 frames provide the quadratic, the F frame flags if it is an outlier, F+1
     and F+2 confirm if F was an outlier or, if F, F+1 and F+2 are coherent, the
     genuine direction change is confirmed and F+2 resets the position... I would
     rather have F and F+1 at predicted position and then a F+2 slerped into
     correct position: this will create a short latency at direction change but
     no latency at all for all the rest of the cases."


WHY THIS IS NOT A THIRD ATTEMPT AT THE SAME THING
-------------------------------------------------
Two predictive outlier gates have been built and both failed, for ONE shared
reason: a direction reversal is UNPREDICTABLE FROM PAST DATA BY CONSTRUCTION.

  * item 1.6  (spec 0.17): two-sample velocity, fixed threshold
               -> ~4 real fast movements rejected per teleport caught,
                  at every threshold of both cues.
  * item B3'' (GESTURE_PIPELINE 16.6): seven channels, explicit p/v/a from a
               least-squares quadratic, a real OLS predictive distribution,
               angular velocity AND acceleration by log map, a horizon that
               grows while coasting
               -> reversal frames rejected 7.43x more often than other frames.

No forward extrapolation, however good, can tell "the hand turned around" from
"the landmark jumped" AT THE MOMENT IT HAPPENS. B7 therefore does not improve the
model -- it DEFERS THE DECISION until later frames disambiguate, which is the one
thing neither previous attempt did.

The discriminant it defers to is not new either: the out-and-back test
(`analysis/m4_rejection_audit.py`) is what this project already uses as GROUND
TRUTH, where it separates 7.9% teleport from 80.2% real movement. B7 is that
same test made causal-with-lag.


THE STATE MACHINE, per channel per hand
---------------------------------------
    NORMAL
        residual small -> ACCEPT. output = measurement. NO LATENCY, EVER.
        residual large -> FLAG, enter PENDING. output = the coast (see below).

    PENDING (holds L frames; the cube never freezes on a stale frame)
        buffer F..F+L and output the coast. ⚠ The owner's design says
        "predicted position" here and that is `coast_mode="extrapolate"`, but
        B8 measured the fitted quadratic to LOSE to "hold the last value" at
        every horizon on this sensor, so `COAST_MODE` defaults to "hold" --
        the choice is a measurement, not a reading of the brief.

    at F+L, DECIDE, from the buffered evidence:
        RETURNED   the stream came back to the pre-F trajectory
                   => F really was an outlier. Discard F..F+L-1, resume from the
                   measurement, and do NOT let the discarded frames enter the
                   fit. ⭐ The predictions already displayed were CORRECT, so
                   there is no visible artifact at all in this branch.
        COHERENT   the flagged frames form a consistent trajectory of their own
                   => a GENUINE direction change. Blend the output back onto the
                   measured trajectory over `blend` frames, and feed F..F+L into
                   the fit.
        AMBIGUOUS  treat as COHERENT. Accepting a real movement late is a smaller
                   sin than rejecting one (owner: "rapid movement is input, not
                   noise").


⚠ WHAT THIS COSTS, STATED UP FRONT
----------------------------------
1. LATENCY IS REAL. L frames of it, paid at every flag -- reversals included,
   because a reversal is flagged first and confirmed afterwards. At ~24 fps,
   L=2 is ~83 ms against a ~75 ms published perceptibility threshold. It is paid
   ONLY at flags, never in the common case, but it is not free. Report it in
   milliseconds (`latency_ms`), never in frames.
2. B7 WILL NOT FIX EDGE-ON OR BACK-OF-HAND. Those are SUSTAINED errors: the palm
   reconstruction collapses coherently and stays wrong for many frames, so
   F..F+L all agree IN THE WRONG PLACE, the test reads COHERENT, and the gate
   ACCEPTS them. B7 separates transient from sustained; it cannot separate
   sustained-correct from sustained-wrong (spec 0.18 -- that is a sensor floor).
3. TELEPORTS LONGER THAN L ARE ACCEPTED, for the same reason.
4. A GENUINE SHORT OUT-AND-BACK FLICK reads as RETURNED and is discarded. Its
   amplitude is bounded by the excursion that came back, and it lasts L frames.
   This is the irreducible cost of the discriminant.


PRESERVED FROM THE EXISTING DESIGN (binding -- each already cost real time)
--------------------------------------------------------------------------
  * PER-CHANNEL decisions, never per-frame (16.2 rule 1): a confused finger must
    not discard a good palm.
  * ⚠ THE ESTIMATOR NEVER LEARNS FROM AN INFERRED VALUE (16.2 rule 6). Only
    accepted measurements enter the fit. Note this is a REAL FIX, not an
    inherited property: `block_predictor.BlockPredictor.update()` appends every
    measurement to `_accepted` unconditionally, including rejected ones,
    contradicting its own docstring. Here the history is per channel and a
    discarded frame never reaches it.
  * HARD COAST CAP as a backstop (`hard_cap`). B7's lag bounds the decision, but
    a binding rule must not depend on the discriminant behaving well.
  * ⚠ S3, BINDING: predicted state must NEVER reach the grab/release state
    machine. While a channel is PENDING, `valid[ch]` is False and the gesture
    logic HOLDS -- no new snap, no release. Rendering uses `output`.
  * FULL RESET on tracking loss or run break (`reset()`).

⚠⚠ MEASURED VERDICT, 2026-08-04 -- THIS MODULE IS BUILT AND UNWIRED
------------------------------------------------------------------------------
`analysis/b7_eval.py`, 15 configurations over 235,319 channel-frames. Judged
against the four criteria fixed in advance (BUILD_PREDICTION_GATE 5):

  1 reversal-discard ratio <= 1.5x        9.44x best (B3'' 7.43x)   FAIL
  2 discards majority outlier, not real   89.5% / 3.4%              PASS
  3 jitter + edge-on better, max not worse  jitter max 0.0695 -> 0.4971  FAIL
                                            edge-on max 3.4555 -> 1.8617  ok
  4 latency stated in ms                  83 ms at L=2 @ 24.1 fps   owner's call

⭐ THE HALF THAT WORKS, and the reason this file is kept rather than deleted:
DEFERRING THE DECISION REALLY DOES SEPARATE. Of the flags raised, the `pred`
verdict discards 9.3% at a labelled reversal against 24.5% elsewhere -- 0.38x,
i.e. it PROTECTS reversals. Split the failure into its factors:

    reversal over-rejection = FLAG ratio x VERDICT ratio
    B3''                      7.43x        1.00x  (no deferral at all)
    B7 + B8                   3.84x        0.83x

⚠ The residue is the DETECTOR, not the decider: a reversal still trips the
residual test ~3.8x more often than an ordinary frame, and no amount of deferral
removes that. 16.6's generalisable result stands, narrowed.

⚠ Two things the ratio hides, both true: absolute harm at reversals FELL 2.8x
(11.65% -> 4.15% of reversal channel-frames discarded), and the reversal LABELS
are contaminated -- a teleport also produces velocity sign changes -- so every
such ratio, 16.6's included, is an upper bound.

Do not open a fourth variant of causal outlier gating without a fundamentally
new signal: a second camera, or item 3.2's RTS smoothing, which costs latency
for everyone rather than only at flags.

Stdlib only, numpy-free, deterministic, no side effects -- the port contract.
"""

import math

try:                                    # every other module here is standalone;
    from . import block_predictor as BP  # this one genuinely needs B3'''s fit,
except ImportError:                      # so it must import either way.
    import block_predictor as BP

SCALAR_CHANNELS = BP.SCALAR_CHANNELS
QUAT_CHANNEL = BP.QUAT_CHANNEL
CHANNELS = BP.CHANNELS

# --- the lag: the one parameter that matters (BUILD_PREDICTION_GATE 1.4) ---
# The documented Object Jump lasts "a few frames" and self-corrects (14.1.4). If
# a teleport persists through F+L it looks coherent and is ACCEPTED, so L must
# out-last it; but L frames of latency are paid at every flag, so it must not be
# larger than it needs to be. The ground-truth labeller uses 6.
LAG = 2

# --- the coherence test: WHICH QUESTION IS ASKED AT F+L ---
#
# ⚠⚠ THE INHERITED TEST DOES NOT TRANSFER TO THESE CHANNELS, and this was
# measured, not guessed (analysis/b7_eval.py, 2026-08-04):
#
#   "p_pre" -- m4_rejection_audit's shape, distance from the last accepted
#   VALUE. Of the flags it raised it discarded 31.8% at a labelled reversal and
#   28.3% elsewhere: 1.13x, i.e. IT DOES NOT DISCRIMINATE AT ALL. The mechanism
#   is structural -- m4 measured a 2D PALM CENTROID, where a hand rarely
#   retraces its own path exactly, but these channels are SIGNED SCALARS, and a
#   direction reversal comes back THROUGH the value it started from. "Returned
#   to where it was" and "turned around" are the same event on one axis. The
#   brief warned the THRESHOLDS were tuned for palm-centroid position; the SHAPE
#   does not transfer either.
#
# Two re-derivations, both asking a question that a reversal answers differently
# from a teleport:
#
#   "pred" -- distance from the PREDICTED TRAJECTORY, not from a frozen point.
#   A teleport leaves the prediction and comes back to it; a reversal leaves it
#   and keeps leaving. Uses the frozen pre-flag fit, so it is still causal.
#
#   "self" -- the owner's literal formulation: "if F, F+1 and F+2 are coherent,
#   the genuine direction change is confirmed". Fit the trajectory through
#   F+1..F+L, extrapolate BACK to F, and ask whether F sits on it. A teleport's
#   F is an outlier to its own successors; a reversal's F is not.
VERDICT_TEST = "pred"
RETURN_RATIO_RETURNED = 0.5     # below -> came back -> it was an outlier
RETURN_RATIO_COHERENT = 0.9     # above -> kept going -> genuine
# Measured (b7_eval.py): 3 frames gives the best still-hand max (0.497 palm
# widths vs 0.582 at 2 and 1.163 at 1) and the best edge-on max, at the cost of
# ~1.7x the tracking error. It costs NO decision latency -- the measurement is
# already accepted at F+L; only the rendered output is still easing in.
BLEND_FRAMES = 3
AMBIGUOUS_IS_COHERENT = True    # accept when unsure -- the owner's bar. Measured:
                                # flipping it to RETURNED raises the discard
                                # ratio 10.94x -> 9.36x but throws away 60% more
                                # frames (1229 -> 1915 at reversals). Keep True.

# B8's winner for the horizons a coast uses. ⚠ Passed to `fit_channel` rather
# than made ITS default, so every pre-B8 number stays reproducible. Measured to
# cut the reversal FLAG ratio 7.03x -> 3.84x and the still-hand output max
# 1.3244 -> 0.5816 -- B8 was NOT the independent lever the brief assumed.
FIT_KWARGS = {"order": 1, "weighting": "exp", "half_life": 2.0}

# --- WHAT THE OUTPUT DOES WHILE PENDING ---
# ⚠ This is not a free parameter, and "extrapolate" is not obviously right:
#
#   extrapolate  correct for a TELEPORT (the hand really did keep moving), wrong
#                for a REVERSAL -- the cube runs on past the turn and then comes
#                back. An OVERSHOOT-AND-RETURN, which reads worse than lag.
#   hold         correct for a reversal, and for a teleport it costs |v|*L px of
#                lag -- but it can never move in a direction the hand is not
#                going. Errs toward NOT moving.
#   damped       half velocity: bounded overshoot.
#
# Reversals are ~9% of channel-frames in this corpus and surviving teleports are
# nearly extinct (DR-1 removed them, 16.1: 3 in 29,164 frames), so the case
# "extrapolate" is right for barely occurs. Independently, B8 measured that the
# fitted quadratic LOSES to "hold the last value" at every horizon on this
# sensor -- so extrapolating is coasting on a model known to be worse than
# nothing. Swept by `b7_eval.py`; do not set this from taste.
COAST_MODE = "hold"

# Force-accept after this many consecutive frames without a clean NORMAL accept.
# Bounds a flag/discard/flag cycle, which the lag alone does not.
HARD_CAP_MULT = 2               # hard cap = HARD_CAP_MULT * L frames


def _lerp(a, b, f):
    return a + (b - a) * f


def _slerp(qa, qb, f):
    """Shortest-arc quaternion interpolation. Falls back to lerp when close."""
    d = sum(x * y for x, y in zip(qa, qb))
    if d < 0.0:
        qb = tuple(-c for c in qb)
        d = -d
    d = max(-1.0, min(1.0, d))
    if d > 0.9995:
        q = tuple(_lerp(a, b, f) for a, b in zip(qa, qb))
    else:
        th = math.acos(d)
        s = math.sin(th)
        wa, wb = math.sin((1.0 - f) * th) / s, math.sin(f * th) / s
        q = tuple(a * wa + b * wb for a, b in zip(qa, qb))
    n = math.sqrt(sum(c * c for c in q))
    return (1.0, 0.0, 0.0, 0.0) if n < 1e-12 else tuple(c / n for c in q)


class _Channel:
    """One channel's history, pending buffer and blend state."""

    __slots__ = ("hist", "pending", "buf", "p_pre", "sigma_flag", "last_out",
                 "blend_left", "blend_span", "z_hist", "since_clean")

    def __init__(self):
        self.hist = []          # ACCEPTED measurements only (16.2 rule 6)
        self.pending = False
        self.buf = []           # measurements F..F+L while PENDING
        self.p_pre = None       # last accepted value before the flag
        self.sigma_flag = None  # the fit's own sigma at the flag, frozen
        self.last_out = None    # last emitted output, for blending
        self.blend_left = 0
        self.blend_span = 0
        self.z_hist = []
        # Frames since the last NORMAL accept. A decision-frame accept does NOT
        # clear it, so a flag/discard/flag cycle still trips the hard cap -- the
        # lag alone bounds one episode, not a run of them.
        self.since_clean = 0


class ConfirmationGate:
    """One per tracked hand. `reset()` on tracking loss or run break.

    `update(block_state)` returns:
        output      block state for RENDERING (measured, predicted or blending)
        valid       per channel: may the GESTURE state machine act on it (S3)
        flagged     channels that entered PENDING on this frame
        pending     channels currently withholding a decision
        discarded   channels whose buffered frames were just thrown away
        confirmed   channels whose flagged frames were just confirmed genuine
        forced      channels force-accepted by the hard cap
        debug       per channel: z, sigma, prediction, verdict, return_ratio
    """

    def __init__(self, lag=LAG, window=BP.WINDOW, reject_z=BP.REJECT_Z,
                 blend=BLEND_FRAMES, verdict_test=VERDICT_TEST,
                 ratio_returned=RETURN_RATIO_RETURNED,
                 ratio_coherent=RETURN_RATIO_COHERENT,
                 ambiguous_is_coherent=AMBIGUOUS_IS_COHERENT,
                 coast_mode=COAST_MODE,
                 accel_uncertainty=BP.ACCEL_UNCERTAINTY, floors=None,
                 hard_cap=None, fit_kwargs=FIT_KWARGS):
        self.lag = max(1, int(lag))
        self.window = window
        self.reject_z = reject_z
        self.blend = max(1, int(blend))
        self.verdict_test = verdict_test
        self.coast_mode = coast_mode
        self.ratio_returned = ratio_returned
        self.ratio_coherent = ratio_coherent
        self.ambiguous_is_coherent = ambiguous_is_coherent
        self.accel_uncertainty = accel_uncertainty
        self.floors = dict(BP.FLOOR if floors is None else floors)
        self.hard_cap = (HARD_CAP_MULT * self.lag) if hard_cap is None else hard_cap
        # B8's knobs, passed straight through to the fit. Empty = B3'' behaviour.
        self.fit_kwargs = dict(fit_kwargs or {})
        self.reset()

    def reset(self):
        self._ch = {c: _Channel() for c in CHANNELS}

    # ------------------------------------------------------------- prediction
    def _inflation(self, c):
        if len(c.z_hist) < 10:
            return 1.0
        s = sorted(abs(z) for z in c.z_hist)
        return max(1.0, s[len(s) // 2] / 0.7)

    def _scalar_prediction(self, ch, c, h):
        """(prediction, sigma) for a scalar channel at horizon h, or None."""
        vals = [v for v in c.hist if v is not None]
        if len(vals) < BP.MIN_HISTORY:
            return None
        st = BP.fit_channel(vals[-self.window:], **self.fit_kwargs)
        if st is None:
            return None
        var = st.variance(h)
        if var is None:
            return None
        accel_term = self.accel_uncertainty * abs(0.5 * st.a * h * h)
        sigma = max(math.sqrt(max(var, 0.0)) * self._inflation(c) + accel_term,
                    self.floors.get(ch, 0.0))
        return st.predict(h), sigma, st

    def _quat_prediction(self, c, h):
        quats = [q for q in c.hist if q is not None]
        if len(quats) < BP.MIN_HISTORY:
            return None
        qst = BP.fit_quat(quats[-self.window:])
        if qst is None:
            return None
        sigma = max(qst.resid_deg * math.sqrt(h) * self._inflation(c),
                    self.floors.get(QUAT_CHANNEL, 0.0))
        return qst.predict(h), sigma, qst

    # -------------------------------------------------------------- the verdict
    @staticmethod
    def _dist(ch):
        if ch == QUAT_CHANNEL:
            return BP._qangle
        return lambda a, b: None if a is None or b is None else abs(a - b)

    def _band(self, r):
        """Map an out-and-back ratio onto the three verdicts."""
        if r is None:
            return "COHERENT", None
        if r < self.ratio_returned:
            return "RETURNED", r
        if r >= self.ratio_coherent:
            return "COHERENT", r
        return ("COHERENT" if self.ambiguous_is_coherent else "RETURNED"), r

    def _verdict(self, ch, c):
        """Decide whether the flagged frames were an outlier or a real change."""
        if not c.buf:
            return "COHERENT", None
        if self.verdict_test == "pred":
            return self._verdict_pred(ch, c)
        if self.verdict_test == "self":
            return self._verdict_self(ch, c)
        return self._verdict_ppre(ch, c)

    def _verdict_ppre(self, ch, c):
        """m4_rejection_audit's shape: distance from the last accepted VALUE.

        ⚠ Kept only so the failure stays reproducible -- measured ANTI-selective
        on these channels (see the VERDICT_TEST note). Do not ship it.
        """
        if c.p_pre is None:
            return "COHERENT", None
        dist = self._dist(ch)
        out = dist(c.buf[0], c.p_pre)
        backs = [b for b in (dist(v, c.p_pre) for v in c.buf[1:]) if b is not None]
        if out is None or out < 1e-9 or not backs:
            # A flag on a step of no size at all -- nothing to return from.
            # Treat as genuine; discarding here would eat a still hand.
            return "COHERENT", None
        return self._band(min(backs) / out)

    def _verdict_pred(self, ch, c):
        """Distance from the PREDICTED TRAJECTORY, over the buffered frames.

        The prediction is the pre-flag fit, frozen: the flagged frames never
        entered the history, so re-evaluating it at horizon h is the same curve
        the output has been coasting on.

            out  = |p_F     - pred(1)|            the residual that flagged
            back = min |p_F+k - pred(1+k)|        do the later frames come BACK?

        A teleport leaves the prediction and returns to it -> small ratio.
        A reversal leaves it and keeps leaving   -> large ratio.
        """
        dist = self._dist(ch)
        preds = [self._predict(ch, c, i + 1) for i in range(len(c.buf))]
        devs = [dist(v, p) for v, p in zip(c.buf, preds)]
        out = devs[0]
        backs = [d for d in devs[1:] if d is not None]
        if out is None or out < 1e-9 or not backs:
            return "COHERENT", None
        return self._band(min(backs) / out)

    def _verdict_self(self, ch, c):
        """The owner's literal test: are F, F+1 ... F+L coherent WITH EACH OTHER?

        Fit the trajectory through F+1..F+L, extrapolate BACK to F, and ask
        whether F sits on it, judged against the same sigma that flagged it.
        A teleport's F is an outlier to its own successors; a reversal's is not.
        """
        after = c.buf[1:]
        sigma = c.sigma_flag
        if len(after) < 2 or not sigma:
            return "COHERENT", None
        if ch == QUAT_CHANNEL:
            step = BP._qlog(BP._qmul(after[1], BP._qconj(after[0])))
            back = BP._qmul(BP._qexp(tuple(-s for s in step)), after[0])
            dev = BP._qangle(back, c.buf[0])
        else:
            n = len(after)
            ts = [float(i + 1) for i in range(n)]        # F is t = 0
            sx, sy = sum(ts), sum(after)
            sxx = sum(t * t for t in ts)
            sxy = sum(t * v for t, v in zip(ts, after))
            den = n * sxx - sx * sx
            if abs(den) < 1e-12:
                return "COHERENT", None
            slope = (n * sxy - sx * sy) / den
            dev = abs(c.buf[0] - (sy - slope * sx) / n)
        if dev is None:
            return "COHERENT", None
        z = dev / sigma
        return ("RETURNED" if z > self.reject_z else "COHERENT"), z

    # -------------------------------------------------------------------- main
    def update(self, state):
        blank = {c: True for c in CHANNELS}
        if state is None or state.get("position") is None:
            return {"output": state, "valid": blank, "flagged": [], "pending": [],
                    "discarded": [], "confirmed": [], "forced": [], "debug": {},
                    "latency_frames": {}}

        meas = dict(BP.BlockPredictor._scalars(state))
        meas[QUAT_CHANNEL] = state.get("quaternion")

        out_val, valid = {}, dict(blank)
        flagged, pending, discarded, confirmed, forced = [], [], [], [], []
        debug, latency = {}, {}

        for ch in CHANNELS:
            m = meas.get(ch)
            c = self._ch[ch]
            if m is None:
                out_val[ch] = c.last_out
                continue
            d = {}
            debug[ch] = d

            # ---------------- PENDING: buffer, coast, and decide at F+L -------
            if c.pending:
                c.buf.append(m)
                c.since_clean += 1
                if c.since_clean >= self.hard_cap:
                    # Backstop (16.2 rule 3): a sustained disagreement means our
                    # model is stale, not that the sensor is wrong this many
                    # frames running. Force-accept and re-seed the channel.
                    forced.append(ch)
                    d["verdict"] = "FORCED"
                    c.pending, c.buf, c.p_pre = False, [], None
                    c.hist, c.z_hist, c.since_clean = [], [], 0
                    c.blend_left = 0
                    self._accept(c, m)
                    out_val[ch] = c.last_out = m
                    continue
                if len(c.buf) > self.lag:           # F..F+L are all in hand
                    verdict, ratio = self._verdict(ch, c)
                    d["verdict"], d["return_ratio"] = verdict, ratio
                    latency[ch] = self.lag
                    if verdict == "RETURNED":
                        # F..F+L-1 were the outlier. They never enter the fit.
                        discarded.append(ch)
                        d["discarded"] = len(c.buf) - 1
                        self._accept(c, m)
                        out_val[ch] = m
                    else:
                        confirmed.append(ch)
                        for v in c.buf:             # the whole excursion is real
                            self._accept(c, v)
                        c.blend_left = c.blend_span = self.blend
                        out_val[ch] = self._blend_step(ch, c, m)
                    c.pending, c.buf, c.p_pre = False, [], None
                else:
                    pending.append(ch)
                    valid[ch] = False               # S3: gesture logic HOLDS
                    co = self._coast_output(ch, c, len(c.buf))
                    out_val[ch] = co if co is not None else c.last_out
                c.last_out = out_val[ch]
                continue

            # ---------------- NORMAL: judge the measurement -------------------
            got = (self._scalar_prediction(ch, c, 1) if ch != QUAT_CHANNEL
                   else self._quat_prediction(c, 1))
            if got is None:
                c.since_clean = 0
                self._accept(c, m)
                out_val[ch] = self._blend_step(ch, c, m) if c.blend_left else m
                c.last_out = out_val[ch]
                continue

            pred, sigma, _st = got
            resid = (abs(m - pred) if ch != QUAT_CHANNEL else BP._qangle(pred, m))
            z = (resid / sigma) if (sigma and resid is not None) else 0.0
            d.update({"pred": pred, "sigma": sigma, "z": z})

            if z > self.reject_z:
                # FLAG -- but do not decide. Coast, and let F+1..F+L settle it.
                flagged.append(ch)
                pending.append(ch)
                valid[ch] = False
                c.pending = True
                c.p_pre = c.hist[-1] if c.hist else None
                c.sigma_flag = sigma
                c.buf = [m]
                c.since_clean += 1
                c.blend_left = 0
                co = self._coast_output(ch, c, 1)
                out_val[ch] = co if co is not None else pred
            else:
                c.z_hist.append(z)
                if len(c.z_hist) > BP.INNOVATION_WINDOW:
                    c.z_hist.pop(0)
                c.since_clean = 0
                self._accept(c, m)
                out_val[ch] = self._blend_step(ch, c, m) if c.blend_left else m
            c.last_out = out_val[ch]

        out = dict(state)
        out["position"] = (out_val.get("pos_x"), out_val.get("pos_y"))
        out["scale"] = out_val.get("scale")
        out["quaternion"] = out_val.get(QUAT_CHANNEL)
        out["arcs"] = tuple(out_val.get(f"arc{i}") for i in range(4))
        return {"output": out, "valid": valid, "flagged": flagged,
                "pending": pending, "discarded": discarded,
                "confirmed": confirmed, "forced": forced, "debug": debug,
                "latency_frames": latency}

    # ------------------------------------------------------------------ helpers
    def _predict(self, ch, c, h):
        got = (self._scalar_prediction(ch, c, h) if ch != QUAT_CHANNEL
               else self._quat_prediction(c, h))
        return None if got is None else got[0]

    def _coast_output(self, ch, c, h):
        """What the CUBE does while the decision is deferred.

        Deliberately separate from `_predict`: the verdict test needs the honest
        model prediction, while the rendered output may be damped or held. Using
        one for both would tie a rendering choice to a decision rule.
        """
        hold = c.hist[-1] if c.hist else c.last_out
        if self.coast_mode == "hold":
            return hold
        pred = self._predict(ch, c, h)
        if pred is None or self.coast_mode == "extrapolate":
            return pred if pred is not None else hold
        if hold is None:
            return pred
        if ch == QUAT_CHANNEL:
            return _slerp(hold, pred, 0.5)
        return _lerp(hold, pred, 0.5)

    def _accept(self, c, value):
        c.hist.append(value)
        while len(c.hist) > self.window:
            c.hist.pop(0)

    def _blend_step(self, ch, c, m):
        """Ease the OUTPUT back onto the measurement over `blend_span` frames.

        Only the rendered output is blended; the fit already holds the raw
        measurement. Ends exactly on the measurement, so it cannot leave a
        standing offset.
        """
        if c.blend_left <= 0 or c.last_out is None:
            c.blend_left = 0
            return m
        f = (c.blend_span - c.blend_left + 1) / float(c.blend_span)
        c.blend_left -= 1
        if ch == QUAT_CHANNEL:
            return _slerp(c.last_out, m, f)
        return _lerp(c.last_out, m, f)
