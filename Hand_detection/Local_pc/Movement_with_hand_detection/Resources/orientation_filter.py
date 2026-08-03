"""Error-state orientation filter with PROPAGATED covariance (M6c/6d).

================================================================================
 STATUS: PARKED -- NOT WIRED TO PRODUCTION. Nothing imports this yet.
================================================================================
Queue item 2.3. Four attempts to beat the shipped `HandOrientationFilter` have all
failed (spec §0.13 / §0.13.1). Retained by owner decision as the substrate for the
GATED variant below, not because it earned a place: ungated, it loses.

**Do not wire this in unless a config beats the shipped filter on BOTH families:**
    jumps (>30/>60, p99, max)   -- gameable by over-damping
    tracking angle(fused, raw) where observability > 0.6 -- gameable by not filtering
That two-sided rule is what caught attempts 1-4; one metric alone always looked
like a win.
================================================================================

Shared-by-design; pure stdlib, no numpy, so the web/mobile port transliterates it
directly.

--------------------------------------------------------------------------------
WHY THIS EXISTS -- AND WHY THE PREVIOUS ATTEMPT FAILED
--------------------------------------------------------------------------------
Spec §0.13 records three null results from a FIXED-GAIN approximation of M6c. The
missing mechanism was covariance propagation, and it is the whole point:

    P grows by Q every frame, and shrinks ONLY when an update is actually trusted.

So while the hand is edge-on and the measurement is worthless, the filter coasts on
its motion model and its uncertainty INFLATES. When the view clears, that inflated
P makes the Kalman gain large, and the filter snaps back to the truth instead of
crawling. Growing-while-lost and snapping-back-when-found are the same mechanism.

A fixed P cannot do this: it damps during the bad patch and then stays damped, which
is why every fixed-gain configuration traded glitch-suppression for tracking lag.

--------------------------------------------------------------------------------
CONTRACT WITH M7 (item 3.1) -- DO NOT BREAK THIS
--------------------------------------------------------------------------------
M7 does FORWARD prediction (where the hand will be when the frame renders). It is a
CONSUMER of this filter, not a competitor: this filter answers "where is the hand
now", M7 extrapolates that forward by the measured latency.

Spec M7 (line ~2076): "Never compute velocity by finite-differencing the smoothed
position... Velocity is a filter state in M6, obtained from the motion model."

Therefore, deliberately public:
  * `omega`        -- angular velocity as an explicit STATE (rotation vector per
                      frame, body frame). M7 extrapolates with this. If it were
                      private, M7 would be forced into the finite-differencing the
                      spec forbids.
  * `quality()`    -- 0..1 confidence derived from P. M7 scales its prediction
                      horizon by this (`L_effective = L_total * quality`), so the
                      growing-P behaviour feeds M7's horizon directly.

NOT touched here: `ROTATION_SLERP_FACTOR`. That is the project's existing
single-cutoff compromise and the spec assigns its retirement to M7's FORM channel.
Entangling it with this filter would create exactly the collision M7 must avoid.

--------------------------------------------------------------------------------
FORMULATION
--------------------------------------------------------------------------------
Error-state (multiplicative) Kalman filter on SO(3):

    predict   q_pred = q (x) exp(omega)          constant angular velocity (6d)
              omega  = omega * OMEGA_DECAY       decay term (6d)
              P      = P + Q                     uncertainty grows while coasting

    update    dz = log(q_pred^-1 (x) q_meas)     innovation, BODY frame
              R   = anisotropic from observability (6c)
              K_i = P_i / (P_i + R_i)            per-axis gain
              q   = q_pred (x) exp(K . dz)
              P_i = (1 - K_i) * P_i

P is kept DIAGONAL in the body frame. Q and R are diagonal there too, and the
frame-rotation cross-term is second order for the per-frame rotations seen here
(~1 deg typical). Recorded as an approximation, not an oversight -- a full 3x3 P
is the next refinement if measurement ever justifies it.
"""

import math

# --- 6c: anisotropic measurement noise -------------------------------------
# Axis 0 is the well-observed one; axes 1,2 are the pair that determine the palm
# normal and blow up at the crossing. The spec's ordering, which was TESTED against
# the alternative (rotation-about-the-long-axis) and came out marginally better
# (spec §0.13) -- so the spec stands and the hypothesis that it was inverted does not.
SIGMA_LONG = 0.30          # measurement noise, well-observed axis
SIGMA_BASE = 0.60          # measurement noise, degenerate axes (scaled by 1/observability)
OBS_FLOOR = 1e-3           # never divide by zero observability

# --- 6d: motion model -------------------------------------------------------
# Human wrist angular velocity rarely exceeds ~15 rad/s (spec 6d). At ~24 fps that
# is ~0.63 rad/frame; anything beyond MAX_OMEGA_PER_FRAME is not a hand movement and
# is clamped rather than propagated into the prediction.
MAX_OMEGA_PER_FRAME = 0.65
OMEGA_DECAY = 0.85         # constant-velocity WITH decay -- unforced motion dies out
PROCESS_NOISE = 0.02       # Q: how fast uncertainty grows while coasting
INITIAL_P = 1.0

# --- ATTEMPT 5: the GATE ----------------------------------------------------
# Attempts 1-4 lost because a Kalman filter damps on EVERY frame, paying lag
# continuously to buy protection that is only needed occasionally. The shipped
# heuristic wins precisely because it is BIMODAL: a pure passthrough (fused == raw,
# zero lag) when well-conditioned, hard damping when degenerate -- matched to a
# failure mode that is rare and severe rather than gradual (spec §0.13.1).
#
# So: keep the bimodality, and use the covariance machinery ONLY inside the bad
# band. Above the gate this filter is a passthrough and costs nothing. Below it,
# the anisotropic KF does something the shipped filter cannot -- the shipped
# `alpha -> 0` freezes ALL axes onto pure prediction, whereas the anisotropic
# update keeps tracking the well-observed axis while coasting only on the
# degenerate ones.
#
# PASSTHROUGH_OBS = None disables the gate (attempts 1-4 behaviour).
PASSTHROUGH_OBS = 0.60
# While passing through, uncertainty must not stay stale: decay it toward the
# well-conditioned floor so that entering the band starts from a sane P.
PASSTHROUGH_P = 0.05

IDENTITY = (1.0, 0.0, 0.0, 0.0)


def _qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def _qnorm(q):
    n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    if n < 1e-12:
        return IDENTITY
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def _continuous(q, ref):
    """Resolve the quaternion double cover before any arithmetic."""
    d = q[0] * ref[0] + q[1] * ref[1] + q[2] * ref[2] + q[3] * ref[3]
    return (-q[0], -q[1], -q[2], -q[3]) if d < 0 else q


def _qlog(q):
    """Unit quaternion -> rotation vector."""
    w = max(-1.0, min(1.0, q[0]))
    x, y, z = q[1], q[2], q[3]
    sn = math.sqrt(x * x + y * y + z * z)
    if sn < 1e-9:
        return (2.0 * x, 2.0 * y, 2.0 * z)
    k = (2.0 * math.atan2(sn, w)) / sn
    return (x * k, y * k, z * k)


def _qexp(v):
    """Rotation vector -> unit quaternion."""
    a = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if a < 1e-9:
        return _qnorm((1.0, 0.5 * v[0], 0.5 * v[1], 0.5 * v[2]))
    h = 0.5 * a
    s = math.sin(h) / a
    return (math.cos(h), v[0] * s, v[1] * s, v[2] * s)


class OrientationFilter:
    """One hand's orientation estimate. See module docstring for the contract."""

    def __init__(self, sigma_long=SIGMA_LONG, sigma_base=SIGMA_BASE,
                 process_noise=PROCESS_NOISE, omega_decay=OMEGA_DECAY,
                 passthrough_obs=PASSTHROUGH_OBS):
        self.q = None                      # nominal orientation
        self.omega = (0.0, 0.0, 0.0)       # PUBLIC state -- M7 reads this (rot vec/frame)
        self.P = [INITIAL_P] * 3           # diagonal error covariance, body frame
        self.sigma_long = sigma_long
        self.sigma_base = sigma_base
        self.q_noise = process_noise
        self.omega_decay = omega_decay
        self.passthrough_obs = passthrough_obs
        self.frames_gated = 0              # diagnostics: frames spent inside the band
        self.frames_passthrough = 0

    def reset(self):
        self.__init__(self.sigma_long, self.sigma_base, self.q_noise,
                      self.omega_decay, self.passthrough_obs)

    def quality(self):
        """0..1 confidence from the propagated covariance. PUBLIC -- M7 scales its
        prediction horizon by this. Falls while coasting through a degenerate patch,
        recovers once measurements are trusted again."""
        worst = max(self.P)
        return 1.0 / (1.0 + worst)

    def predict_forward(self, frames_ahead):
        """Extrapolate the CURRENT estimate forward. Provided for M7 (item 3.1);
        not used by this filter's own update. Returns a quaternion."""
        if self.q is None:
            return IDENTITY
        w = self.omega
        return _qnorm(_qmul(self.q, _qexp((w[0] * frames_ahead,
                                           w[1] * frames_ahead,
                                           w[2] * frames_ahead))))

    def update(self, q_meas, observability):
        """One frame. `q_meas` is the raw frame-derived orientation; `observability`
        is palm_geometry.palm_observability(). Returns the fused quaternion."""
        q_meas = _qnorm(q_meas)

        if self.q is None:                       # first sighting: adopt it
            self.q = q_meas
            self.P = [INITIAL_P] * 3
            self.omega = (0.0, 0.0, 0.0)
            return self.q

        q_meas = _continuous(q_meas, self.q)

        # --- ATTEMPT 5: gate ---------------------------------------------------
        # Well-conditioned -> PASSTHROUGH. Costs exactly zero lag, matching the
        # shipped filter's saturated-alpha behaviour, which is why it wins.
        # The KF machinery below only earns its keep inside the degenerate band.
        if self.passthrough_obs is not None and observability > self.passthrough_obs:
            step = _qlog(_qmul(_qconj(self.q), q_meas))
            self.omega = (step[0] * self.omega_decay,
                          step[1] * self.omega_decay,
                          step[2] * self.omega_decay)
            # Do not let P go stale while passing through: relax it toward the
            # well-conditioned floor so entering the band starts from a sane value.
            self.P = [min(p, PASSTHROUGH_P) for p in self.P]
            self.q = q_meas
            self.frames_passthrough += 1
            return self.q

        self.frames_gated += 1

        # --- predict (6d) -----------------------------------------------------
        w = self.omega
        mag = math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])
        if mag > MAX_OMEGA_PER_FRAME:            # not a hand movement; do not propagate it
            s = MAX_OMEGA_PER_FRAME / mag
            w = (w[0] * s, w[1] * s, w[2] * s)
        q_pred = _continuous(_qnorm(_qmul(self.q, _qexp(w))), self.q)

        # Uncertainty GROWS every frame. This is the mechanism the fixed-gain
        # attempt lacked: coasting through a bad patch inflates P, so the first
        # trustworthy measurement afterwards gets a large gain and snaps back.
        P = [self.P[i] + self.q_noise for i in range(3)]

        # --- update (6c) ------------------------------------------------------
        dz = _qlog(_qmul(_qconj(q_pred), q_meas))

        obs = max(observability, OBS_FLOOR)
        s_long2 = self.sigma_long * self.sigma_long
        s_base2 = self.sigma_base * self.sigma_base
        R = (s_long2, s_base2 / obs, s_base2 / obs)

        k = [P[i] / (P[i] + R[i]) for i in range(3)]
        correction = (dz[0] * k[0], dz[1] * k[1], dz[2] * k[2])

        q_new = _continuous(_qnorm(_qmul(q_pred, _qexp(correction))), self.q)

        # angular velocity as a STATE, from the motion model -- never finite
        # differenced from smoothed output (spec M7). Decay = 6d's decay term.
        step = _qlog(_qmul(_qconj(self.q), q_new))
        self.omega = (step[0] * self.omega_decay,
                      step[1] * self.omega_decay,
                      step[2] * self.omega_decay)

        self.P = [(1.0 - k[i]) * P[i] for i in range(3)]
        self.q = q_new
        return self.q
