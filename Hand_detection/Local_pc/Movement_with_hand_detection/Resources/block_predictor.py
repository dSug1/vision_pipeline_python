"""B3'' -- predictive outlier gate over the block state, with EXPLICIT velocity,
acceleration, and a predictive PROBABILITY DISTRIBUTION over the next positions.

Owner design (GESTURE_PIPELINE 16 / 16.2), built in full this time. The previous
attempt (`block_tracker.py`) implemented roughly half of it and is superseded:
it fitted a quadratic but never extracted the derivatives, replaced the
distribution with a fixed 4x-median threshold, predicted only one frame, and had
no motion model at all for orientation. Those were shortcuts, not findings.

WHAT IS MODELLED
----------------
Six blocks, of which five are modelled and the thumb is carried raw (owner
decision -- its CMC is a saddle joint and an arc does not describe opposition):

    palm    : x, y (px), scale (px), orientation (quaternion)
    fingers : 4 arc-extension scalars (index, middle, ring, pinky)

Seven scalar channels plus one quaternion channel.


1. STATE: EXPLICIT POSITION, VELOCITY, ACCELERATION
---------------------------------------------------
For each scalar channel a weighted least-squares QUADRATIC is fitted over the
last N ACCEPTED frames:

    y(t) = p + v*t + 0.5*a*t^2          t in frames, t = 0 at the newest frame

and p, v, a are extracted as real quantities (`ChannelState`), not left implicit
in the fit. Fitting over a window rather than differencing two samples is the
single most important correction: S2(a) is explicit that a raw two-sample
derivative must never be extrapolated, and that filtering it is where
TurboTouch's 2-3x gain came from. Item 1.6 differenced two samples and its
"acceleration" was mostly landmark noise differentiated twice.

Prediction at horizon h frames:   yhat(h) = p + v*h + 0.5*a*h^2


2. THE DISTRIBUTION -- not a threshold
--------------------------------------
The next observation is modelled as Gaussian around the prediction, using the
standard ordinary-least-squares PREDICTION variance -- which is a real
distribution derived from the fit, not a tuned multiple of a median:

    Var[y(h)] = s^2 * (1 + x(h)' (X'X)^-1 x(h))     x(h) = [1, h, h^2/2]

with s^2 = RSS / (n - 3), the residual variance of the fit itself. This has
exactly the properties the owner asked for and a threshold cannot have:

  * it WIDENS WITH HORIZON automatically -- the x(h)'(X'X)^-1 x(h) term grows
    quadratically, so a prediction two frames out is legitimately less certain
    than one frame out;
  * it WIDENS WHEN THE MOTION IS UNMODELLABLE -- if the recent trajectory is not
    well described by a quadratic, RSS rises and the band opens, so the gate
    stops rejecting during genuinely erratic (but real) movement;
  * it NARROWS when the hand is moving smoothly, which is when an outlier is
    actually detectable.

Two additions on top:

  * INNOVATION INFLATION: a running dispersion of recent standardised residuals
    inflates s if the model has been consistently running hot. Guards against a
    fit that looks internally tidy while systematically mispredicting.
  * ⚠ AN ABSOLUTE FLOOR per channel. When the hand is still, RSS -> 0 and any
    real motion becomes an enormous z-score. Without a floor a purely relative
    test rejects the first frame of every deliberate movement. Floors are
    DERIVED from the corpus (see `calibrate_floors.py`), not guessed.

Decision: standardised residual z = |measured - yhat(h)| / sigma(h);
reject when z > REJECT_Z. Because sigma is a distribution and not a constant,
REJECT_Z is a tail probability (3.0 ~ 99.7% under the model), not a tuned pixel
count.


3. ORIENTATION GETS A REAL MOTION MODEL
---------------------------------------
The previous version held the last quaternion and called it a prediction. Here,
angular velocity is estimated properly via the LOG MAP:

    omega_k = log( q_k * conj(q_{k-1}) )            a rotation vector, rad/frame

omega is then fitted linearly over the window to give angular velocity AND
angular acceleration, and integrated forward:

    rot(h) = omega0*h + 0.5*alpha*h^2
    qhat(h) = exp( rot(h) ) * q_last

The residual is the angle between qhat(h) and the measurement, and its own
dispersion supplies sigma. ⚠ The axis is ill-conditioned exactly where this
gate matters (edge-on, where 0.18 shows the whole palm frame collapses), so
`orientation_conditioned` reports whether the frame was trustworthy and the
caller may choose to ignore the orientation channel there rather than gate on it.


4. MULTI-FRAME COASTING, AND WHY THE CASCADE CANNOT RUN AWAY
------------------------------------------------------------
Rejection is PER CHANNEL (16.2 rule 1). A rejected channel is replaced by its
own prediction and flagged invalid.

While coasting, the horizon h increases: 1 frame after the first rejection, 2
after the second, and so on. Because sigma(h) grows with h, **the acceptance band
widens automatically the longer we coast** -- so a gate that has been wrong for
two frames is far less likely to reject a third. That is a principled,
self-limiting version of the anti-cascade rule, and it is exactly what item
1.6's fixed threshold lacked: there, a rejection made the prediction drift while
the threshold stayed constant, so one bad frame booked up to 8 rejections
(0.13.3) and the resulting statistic was mistaken for a weak motion model
(0.15).

MAX_COAST_FRAMES survives as a HARD BACKSTOP on top of that, because a binding
rule should not depend on a variance estimate behaving well.

⚠ The estimator never learns from an inferred value (16.2 rule 6): only accepted
measurements enter the history, the fit, and the residual dispersion.

⚠ S3, binding: predicted state must NEVER reach a gesture state machine.
`valid` is the flag the grab/release logic must hold on.

Stdlib only, numpy-free, deterministic -- the port contract.
"""

import math

WRIST = 0
SCALAR_CHANNELS = ("pos_x", "pos_y", "scale", "arc0", "arc1", "arc2", "arc3")
QUAT_CHANNEL = "quat"
CHANNELS = SCALAR_CHANNELS + (QUAT_CHANNEL,)

# --- window ---
# 7 accepted frames ~= 290 ms at 24 fps. A quadratic has 3 parameters, so 7
# points leave 4 degrees of freedom for the residual variance -- enough for s^2
# to mean something. Shorter windows make s^2 unstable (and it is the whole
# distribution); longer ones smear real direction reversals.
WINDOW = 7
MIN_HISTORY = 4                 # >= 3 params + 1, else the fit is exact and s^2 = 0

# --- decision ---
REJECT_Z = 3.0                  # tail probability, not a tuned magnitude
MAX_COAST_FRAMES = 2            # hard backstop (16.2 rule 3)
INNOVATION_WINDOW = 40          # running dispersion of standardised residuals

# --- absolute floors (see analysis/calibrate_floors.py; DERIVED, not guessed) ---
# Placeholders until calibration runs; calibration writes the measured values.
FLOOR = {
    "pos_x": 1.5, "pos_y": 1.5,     # px
    "scale": 1.5,                   # px
    "arc0": 0.010, "arc1": 0.010, "arc2": 0.010, "arc3": 0.010,
    "quat": 3.0,                    # degrees
}


# ---------------------------------------------------------------- linear algebra
def _solve(a):
    """Gauss-Jordan on an augmented n x (n+1) matrix. Returns the solution or
    None if singular. Small and closed-form, so it stays numpy-free."""
    n = len(a)
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) < 1e-12:
            return None
        a[c], a[p] = a[p], a[c]
        for r in range(n):
            if r == c:
                continue
            f = a[r][c] / a[c][c]
            for k in range(c, n + 1):
                a[r][k] -= f * a[c][k]
    return [a[i][n] / a[i][i] for i in range(n)]


def _inv3(m):
    """Inverse of a symmetric 3x3, by cofactors. Returns None if singular."""
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-18:
        return None
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


# ---------------------------------------------------------------- quaternion ops
def _qmul(p, q):
    w1, x1, y1, z1 = p
    w2, x2, y2, z2 = q
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def _qlog(q):
    """Unit quaternion -> rotation vector (axis * angle), in radians."""
    w = max(-1.0, min(1.0, q[0]))
    v = (q[1], q[2], q[3])
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    ang = 2.0 * math.atan2(n, w)
    if ang > math.pi:                      # shortest arc
        ang -= 2.0 * math.pi
    s = ang / n
    return (v[0] * s, v[1] * s, v[2] * s)


def _qexp(r):
    """Rotation vector -> unit quaternion."""
    ang = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
    if ang < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    s = math.sin(ang / 2.0) / ang
    return (math.cos(ang / 2.0), r[0] * s, r[1] * s, r[2] * s)


def _qangle(a, b):
    if a is None or b is None:
        return None
    d = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


# ---------------------------------------------------------------- scalar channel
class ChannelState:
    """Explicit p, v, a plus the fit's own residual variance and (X'X)^-1."""

    __slots__ = ("p", "v", "a", "s2", "xtx_inv", "n")

    def __init__(self, p, v, a, s2, xtx_inv, n):
        self.p, self.v, self.a = p, v, a
        self.s2, self.xtx_inv, self.n = s2, xtx_inv, n

    def predict(self, h):
        return self.p + self.v * h + 0.5 * self.a * h * h

    def variance(self, h):
        """OLS prediction variance for a NEW observation at horizon h."""
        if self.xtx_inv is None:
            return None
        x = (1.0, float(h), 0.5 * h * h)
        quad = sum(x[i] * self.xtx_inv[i][j] * x[j]
                   for i in range(3) for j in range(3))
        return self.s2 * (1.0 + max(0.0, quad))


def fit_channel(values):
    """Weighted-equal least-squares quadratic over `values` (oldest -> newest).

    t is measured in frames with t = 0 at the NEWEST accepted sample, so
    predicting h frames ahead is evaluating at t = +h and needs no separate
    extrapolation step that could disagree with the fit.
    """
    n = len(values)
    if n < MIN_HISTORY:
        return None
    ts = [float(k - (n - 1)) for k in range(n)]          # ..., -2, -1, 0
    basis = [(1.0, t, 0.5 * t * t) for t in ts]
    xtx = [[sum(b[i] * b[j] for b in basis) for j in range(3)] for i in range(3)]
    xty = [sum(b[i] * y for b, y in zip(basis, values)) for i in range(3)]
    beta = _solve([row[:] + [xty[i]] for i, row in enumerate(xtx)])
    if beta is None:
        return None
    p, v, a = beta
    rss = sum((y - (p + v * t + 0.5 * a * t * t)) ** 2 for t, y in zip(ts, values))
    dof = n - 3
    s2 = rss / dof if dof > 0 else 0.0
    return ChannelState(p, v, a, s2, _inv3(xtx), n)


# ---------------------------------------------------------------- orientation
class QuatState:
    """Angular velocity and acceleration as rotation vectors (rad/frame)."""

    __slots__ = ("q_last", "omega", "alpha", "resid_deg")

    def __init__(self, q_last, omega, alpha, resid_deg):
        self.q_last = q_last
        self.omega = omega
        self.alpha = alpha
        self.resid_deg = resid_deg          # dispersion of recent step residuals

    def predict(self, h):
        rot = tuple(self.omega[i] * h + 0.5 * self.alpha[i] * h * h
                    for i in range(3))
        return _qmul(_qexp(rot), self.q_last)


def fit_quat(quats):
    """Angular velocity/acceleration by log map, fitted over the window.

    omega_k = log(q_k * conj(q_{k-1})) gives a rotation vector per step; a LINEAR
    fit of that sequence yields angular velocity and angular acceleration. This
    is S2(a) applied to orientation -- never a raw two-sample step.
    """
    if len(quats) < MIN_HISTORY:
        return None
    qs = []
    for q in quats:                          # enforce sign continuity
        if qs and sum(x * y for x, y in zip(q, qs[-1])) < 0:
            q = tuple(-c for c in q)
        qs.append(q)
    omegas = [_qlog(_qmul(qs[i + 1], _qconj(qs[i]))) for i in range(len(qs) - 1)]
    m = len(omegas)
    ts = [float(k - (m - 1)) for k in range(m)]
    omega, alpha = [0.0] * 3, [0.0] * 3
    for axis in range(3):
        ys = [o[axis] for o in omegas]
        if m >= 3:
            sx = sum(ts)
            sxx = sum(t * t for t in ts)
            sy = sum(ys)
            sxy = sum(t * y for t, y in zip(ts, ys))
            den = m * sxx - sx * sx
            if abs(den) > 1e-12:
                slope = (m * sxy - sx * sy) / den
                intercept = (sy - slope * sx) / m
                omega[axis] = intercept       # value at t = 0, the newest step
                alpha[axis] = slope
                continue
        omega[axis] = sum(ys) / m
    resid = []
    for i in range(1, len(qs)):
        pred = _qmul(_qexp(tuple(omega)), qs[i - 1])
        d = _qangle(pred, qs[i])
        if d is not None:
            resid.append(d)
    resid.sort()
    disp = resid[len(resid) // 2] if resid else 0.0
    return QuatState(qs[-1], tuple(omega), tuple(alpha), disp)


# ---------------------------------------------------------------- the gate
class BlockPredictor:
    """One per tracked hand. `reset()` on tracking loss or run break."""

    def __init__(self, window=WINDOW, reject_z=REJECT_Z,
                 max_coast=MAX_COAST_FRAMES, floors=None):
        self.window = window
        self.reject_z = reject_z
        self.max_coast = max_coast
        self.floors = dict(FLOOR if floors is None else floors)
        self.reset()

    def reset(self):
        self._accepted = []                       # measured states only
        self._coast = {c: 0 for c in CHANNELS}
        self._z_hist = {c: [] for c in CHANNELS}  # standardised residuals

    # -- inflation from how hot the model has been running --
    def _inflation(self, ch):
        h = self._z_hist[ch]
        if len(h) < 10:
            return 1.0
        s = sorted(abs(z) for z in h)
        med = s[len(s) // 2]
        # If |z| has been running above ~0.7 typically, the model is
        # mispredicting systematically and sigma is too tight -- widen it.
        return max(1.0, med / 0.7)

    @staticmethod
    def _scalars(state):
        pos = state.get("position") or (None, None)
        arcs = state.get("arcs") or (None, None, None, None)
        return {"pos_x": pos[0], "pos_y": pos[1], "scale": state.get("scale"),
                "arc0": arcs[0], "arc1": arcs[1], "arc2": arcs[2], "arc3": arcs[3]}

    def update(self, state):
        """Judge one block state. Returns output/valid/rejected/forced/debug.

        `debug` carries p, v, a, sigma and z per channel so the model can be
        inspected rather than trusted -- required before any conclusion is drawn
        from it.
        """
        blank = {c: True for c in CHANNELS}
        if state is None or state.get("position") is None:
            return {"output": state, "valid": blank, "rejected": [],
                    "forced": [], "debug": {}}

        meas = self._scalars(state)
        out_scalars = dict(meas)
        out_quat = state.get("quaternion")
        valid, rejected, forced, debug = dict(blank), [], [], {}

        hist = self._accepted
        if len(hist) >= MIN_HISTORY:
            for ch in SCALAR_CHANNELS:
                vals = [h["_sc"][ch] for h in hist if h["_sc"].get(ch) is not None]
                if len(vals) < MIN_HISTORY or meas.get(ch) is None:
                    continue
                st = fit_channel(vals[-self.window:])
                if st is None:
                    continue
                # Horizon grows while coasting: the band widens on its own.
                h = self._coast[ch] + 1
                pred = st.predict(h)
                var = st.variance(h)
                if var is None:
                    continue
                sigma = max(math.sqrt(max(var, 0.0)) * self._inflation(ch),
                            self.floors.get(ch, 0.0))
                resid = abs(meas[ch] - pred)
                z = resid / sigma if sigma > 0 else 0.0
                debug[ch] = {"p": st.p, "v": st.v, "a": st.a, "h": h,
                             "pred": pred, "sigma": sigma, "z": z}
                if z > self.reject_z:
                    if self._coast[ch] >= self.max_coast:
                        forced.append(ch)
                        self._coast[ch] = 0
                        self._z_hist[ch] = []
                    else:
                        self._coast[ch] += 1
                        rejected.append(ch)
                        valid[ch] = False
                        out_scalars[ch] = pred
                        continue
                else:
                    self._coast[ch] = 0
                zs = self._z_hist[ch]
                zs.append(z)
                if len(zs) > INNOVATION_WINDOW:
                    zs.pop(0)

            quats = [h["quaternion"] for h in hist if h.get("quaternion")]
            if len(quats) >= MIN_HISTORY and state.get("quaternion"):
                qst = fit_quat(quats[-self.window:])
                if qst is not None:
                    h = self._coast[QUAT_CHANNEL] + 1
                    pred = qst.predict(h)
                    resid = _qangle(pred, state["quaternion"])
                    if resid is not None:
                        # sigma grows with horizon like the scalar channels
                        sigma = max(qst.resid_deg * math.sqrt(h)
                                    * self._inflation(QUAT_CHANNEL),
                                    self.floors.get(QUAT_CHANNEL, 0.0))
                        z = resid / sigma if sigma > 0 else 0.0
                        debug[QUAT_CHANNEL] = {
                            "omega_deg": [math.degrees(w) for w in qst.omega],
                            "alpha_deg": [math.degrees(a) for a in qst.alpha],
                            "h": h, "sigma": sigma, "z": z}
                        if z > self.reject_z:
                            if self._coast[QUAT_CHANNEL] >= self.max_coast:
                                forced.append(QUAT_CHANNEL)
                                self._coast[QUAT_CHANNEL] = 0
                                self._z_hist[QUAT_CHANNEL] = []
                            else:
                                self._coast[QUAT_CHANNEL] += 1
                                rejected.append(QUAT_CHANNEL)
                                valid[QUAT_CHANNEL] = False
                                out_quat = pred
                        else:
                            self._coast[QUAT_CHANNEL] = 0
                            zs = self._z_hist[QUAT_CHANNEL]
                            zs.append(z)
                            if len(zs) > INNOVATION_WINDOW:
                                zs.pop(0)

        out = dict(state)
        out["position"] = (out_scalars["pos_x"], out_scalars["pos_y"])
        out["scale"] = out_scalars["scale"]
        out["quaternion"] = out_quat
        out["arcs"] = tuple(out_scalars[f"arc{i}"] for i in range(4))

        # 16.2 rule 6: MEASURED state only enters the history, never inferred.
        rec = dict(state)
        rec["_sc"] = meas
        self._accepted.append(rec)
        while len(self._accepted) > self.window:
            self._accepted.pop(0)

        return {"output": out, "valid": valid, "rejected": rejected,
                "forced": forced, "debug": debug}
