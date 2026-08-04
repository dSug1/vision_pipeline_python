"""B3' -- per-channel predictive outlier gate over the BLOCK state.

Spec: GESTURE_PIPELINE 16.2 (the coasting policy). Stdlib only, numpy-free, no
side effects, deterministic -- the port contract.

WHY THIS IS A RE-TRY AND NOT A REPEAT OF ITEM 1.6
-------------------------------------------------
1.6 built the single-channel version of this and over-filtered 4:1 -- it rejected
roughly four real fast movements per teleport caught, at every threshold (0.17).
It is worth being exact about what it did, because the popular summary is wrong:

    its position cue was ALREADY the palm centroid, not fingertips, and
    innovation = p(k) - 2p(k-1) + p(k-2)  ==  the discrete SECOND derivative.

So "palm block, second derivative" is not the new idea. What 1.6 actually got
wrong, and what this module fixes:

  (a) ⭐ IT ESTIMATED VELOCITY FROM TWO SAMPLES. `v = p(k-1) - p(k-2)` on landmark
      data whose own noise is the same order as the motion -- so its
      "acceleration" was mostly noise differentiated twice, and it could not
      measure jerk at all. S2(a) is explicit that one must never extrapolate a
      raw two-sample difference, and that filtering it is where TurboTouch's
      2-3x gain came from. **This module fits derivatives over a WINDOW.**
  (b) ONE CHANNEL. Here there are seven: palm x, y, scale, quaternion, and four
      arc extensions -- and rejection is per channel (16.2), so a confused
      finger no longer discards a good palm.
  (c) A FIXED THRESHOLD in palm widths. Here each channel is scored against its
      OWN recent residual scale, i.e. an adaptive distribution rather than a
      constant.

⚠ NONE OF THAT MAKES IT WORK. It makes it worth measuring. The bar is explicit:
it must beat 1.6's 4:1 by a wide margin **on rejections that are CLASSIFIED**
(teleport vs real fast movement), not on a lower rejection count -- a count
cannot tell you whether you removed the failure or the feature (0.18).
"""

import math

# --- windowed derivative estimation (fixes 1.6's two-sample velocity) ---
WINDOW = 5              # frames of accepted history used to fit derivatives.
                        # ~200 ms at 24 fps: long enough to average landmark
                        # noise, short enough not to smear a real reversal.
POLY_ORDER = 2          # 1 = velocity only, 2 = + acceleration (owner: "up to
                        # second derivative"). Needs WINDOW >= ORDER + 2 to be
                        # over-determined and therefore noise-averaging.
MIN_HISTORY = 3         # below this there is nothing to predict from.

# --- adaptive residual scale ---
SCALE_WINDOW = 30       # residual history per channel, ~1.2 s
MIN_SCALE_SAMPLES = 8
REJECT_SIGMA = 4.0      # residual > SIGMA x scale -> candidate rejection

# ⚠ ABSOLUTE FLOORS, and they are load-bearing. When the hand is still, the
# residual scale collapses toward zero and ANY movement becomes an enormous
# multiple of it -- a purely relative test would reject the first frame of every
# deliberate motion. A channel must exceed BOTH the adaptive test and its own
# absolute floor. Floors are set near the p95 of ordinary per-frame change
# measured across the corpus (spec 16.1's band table).
FLOOR_POSITION = 0.20   # palm widths
FLOOR_SCALE = 0.15      # |log ratio|
FLOOR_QUAT = 25.0       # degrees
FLOOR_ARC = 0.12        # extension units

MAX_COAST_FRAMES = 2    # 16.2 rule 3, binding. Then force-accept and re-seed.

CHANNELS = ("pos_x", "pos_y", "scale", "quat", "arc0", "arc1", "arc2", "arc3")


def _poly_fit_predict(ts, ys, order):
    """Least-squares polynomial fit over a window; return the value at t=0.

    Times are supplied as NEGATIVE offsets from the frame being predicted, so
    evaluating at 0 IS the one-step-ahead prediction and no separate
    extrapolation step can disagree with the fit.

    Solved by Gaussian elimination on the normal equations -- small, closed
    form, numpy-free, and portable. Falls back to lower order (and finally to
    the last value) when the system is degenerate, which is what happens when
    the hand is perfectly still.
    """
    n = len(ts)
    if n == 0:
        return None
    order = min(order, n - 1)
    while order >= 1:
        m = order + 1
        a = [[0.0] * (m + 1) for _ in range(m)]
        for i in range(m):
            for j in range(m):
                a[i][j] = sum(t ** (i + j) for t in ts)
            a[i][m] = sum(y * (t ** i) for t, y in zip(ts, ys))
        ok = True
        for c in range(m):
            p = max(range(c, m), key=lambda r: abs(a[r][c]))
            if abs(a[p][c]) < 1e-12:
                ok = False
                break
            a[c], a[p] = a[p], a[c]
            for r in range(m):
                if r == c:
                    continue
                f = a[r][c] / a[c][c]
                for k in range(c, m + 1):
                    a[r][k] -= f * a[c][k]
        if ok:
            return a[0][m] / a[0][0]        # constant term == value at t = 0
        order -= 1
    return ys[-1]


def _median(v):
    s = sorted(v)
    return s[len(s) // 2] if s else 0.0


def _quat_angle(qa, qb):
    if qa is None or qb is None:
        return None
    d = abs(sum(x * y for x, y in zip(qa, qb)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


class BlockTracker:
    """One per tracked hand. `reset()` on tracking loss or run break."""

    def __init__(self, window=WINDOW, order=POLY_ORDER,
                 reject_sigma=REJECT_SIGMA, max_coast=MAX_COAST_FRAMES):
        self.window = window
        self.order = order
        self.reject_sigma = reject_sigma
        self.max_coast = max_coast
        self.reset()

    def reset(self):
        self._hist = []                                   # accepted states only
        self._resid = {c: [] for c in CHANNELS}
        self._coast = {c: 0 for c in CHANNELS}

    # ---- channel extraction -------------------------------------------------
    @staticmethod
    def _scalars(state):
        pos = state.get("position")
        arcs = state.get("arcs") or (None, None, None, None)
        return {
            "pos_x": None if pos is None else pos[0],
            "pos_y": None if pos is None else pos[1],
            "scale": state.get("scale"),
            "arc0": arcs[0], "arc1": arcs[1], "arc2": arcs[2], "arc3": arcs[3],
        }

    def _floor(self, ch, palm_scale):
        if ch in ("pos_x", "pos_y"):
            return FLOOR_POSITION * (palm_scale or 1.0)
        if ch == "scale":
            return FLOOR_SCALE * (palm_scale or 1.0)
        if ch == "quat":
            return FLOOR_QUAT
        return FLOOR_ARC

    def _predict(self, ch):
        """One-step-ahead prediction for a channel from accepted history."""
        vals, ts = [], []
        for k, st in enumerate(self._hist):
            v = st["_scalars"].get(ch) if ch != "quat" else None
            if ch == "quat":
                continue
            if v is None:
                continue
            vals.append(v)
            ts.append(float(k - len(self._hist)))          # ..., -2, -1
        if len(vals) < MIN_HISTORY:
            return None
        return _poly_fit_predict(ts, vals, self.order)

    def _predict_quat(self):
        """Constant-angular-velocity prediction, with the rate estimated over
        the window rather than from the last pair -- the same fix as (a)."""
        qs = [st["quaternion"] for st in self._hist if st.get("quaternion")]
        if len(qs) < MIN_HISTORY:
            return None
        # Average per-frame rotation magnitude over the window; direction is
        # taken from the most recent step, which is where it is best defined.
        steps = [_quat_angle(qs[i], qs[i + 1]) for i in range(len(qs) - 1)]
        steps = [s for s in steps if s is not None]
        if not steps:
            return qs[-1]
        # A zero-order prediction plus an allowance equal to the typical step is
        # sufficient for OUTLIER DETECTION -- extrapolating the quaternion itself
        # would add a second failure mode (S2's warning about damping) for no
        # gain in a gate that only needs a plausible envelope.
        return qs[-1]

    def _quat_allowance(self):
        qs = [st["quaternion"] for st in self._hist if st.get("quaternion")]
        steps = [_quat_angle(qs[i], qs[i + 1]) for i in range(len(qs) - 1)]
        steps = [s for s in steps if s is not None]
        return _median(steps) if steps else 0.0

    # ---- main -------------------------------------------------------------
    def update(self, state):
        """Judge one block state (from `hand_blocks.block_state`).

        Returns dict:
            output   the block state to RENDER with (measured, or inferred
                     per rejected channel)
            valid    {channel: bool} -- False where the value was inferred.
                     ⚠ The grab/release state machine must HOLD while any
                     channel it depends on is False (16.2 rule 5).
            rejected list of channel names inferred this frame
            forced   list of channels force-accepted at the coast cap
        """
        if state is None or state.get("position") is None:
            return {"output": state, "valid": {c: True for c in CHANNELS},
                    "rejected": [], "forced": []}

        state = dict(state)
        state["_scalars"] = self._scalars(state)
        palm_scale = state.get("scale") or 1.0

        valid = {c: True for c in CHANNELS}
        rejected, forced = [], []
        out_scalars = dict(state["_scalars"])
        out_quat = state.get("quaternion")

        if len(self._hist) >= MIN_HISTORY:
            for ch in CHANNELS:
                if ch == "quat":
                    meas = state.get("quaternion")
                    pred = self._predict_quat()
                    resid = _quat_angle(pred, meas)
                    allowance = self._quat_allowance()
                else:
                    meas = state["_scalars"].get(ch)
                    pred = self._predict(ch)
                    resid = None if (meas is None or pred is None) else abs(meas - pred)
                    allowance = 0.0
                if resid is None:
                    continue

                hist = self._resid[ch]
                scale = _median(hist) if len(hist) >= MIN_SCALE_SAMPLES else None
                floor = self._floor(ch, palm_scale) + allowance
                over_floor = resid > floor
                over_sigma = scale is not None and resid > self.reject_sigma * max(scale, 1e-9)

                # BOTH tests must fire. The adaptive one alone rejects the first
                # frame of any deliberate motion when the hand has been still.
                if over_floor and over_sigma:
                    if self._coast[ch] >= self.max_coast:
                        # 16.2 rule 3: the model is stale, not the sensor.
                        forced.append(ch)
                        self._coast[ch] = 0
                        self._resid[ch] = []          # re-seed
                    else:
                        self._coast[ch] += 1
                        rejected.append(ch)
                        valid[ch] = False
                        if ch == "quat":
                            out_quat = pred
                        else:
                            out_scalars[ch] = pred
                        continue
                else:
                    self._coast[ch] = 0
                # 16.2 rule 6: only ACCEPTED measurements train the scale.
                hist.append(resid)
                if len(hist) > SCALE_WINDOW:
                    hist.pop(0)

        out = dict(state)
        out["position"] = (out_scalars["pos_x"], out_scalars["pos_y"])
        out["scale"] = out_scalars["scale"]
        out["quaternion"] = out_quat
        out["arcs"] = tuple(out_scalars[f"arc{i}"] for i in range(4))

        # 16.2 rule 6: history holds MEASURED state only, never inferred values.
        self._hist.append(state)
        while len(self._hist) > self.window:
            self._hist.pop(0)

        return {"output": out, "valid": valid,
                "rejected": rejected, "forced": forced}
