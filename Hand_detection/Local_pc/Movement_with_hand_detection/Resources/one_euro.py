"""⭐⭐ THE 1€ FILTER — adaptive low-pass for the fingertips (`F1`, queue step 1).

    Casiez, G., Roussel, N. and Vogel, D. (2012). "1€ Filter: A Simple
    Speed-based Low-pass Filter for Noisy Input in Interactive Systems." CHI '12.
    Reference implementation: https://github.com/casiez/OneEuroFilter

        Copyright 2023 Inria
        Licensed under the BSD-3-Clause licence.

    ⚠ The copyright line above is the upstream holder's, VERBATIM, and BSD-3
    clause 1 requires it to travel with this source. It lives at
    `python/LICENSE` upstream, NOT the repo root (which 404s). Verified
    2026-08-26. ⭐ Clears `N13`; the filter also ships as a third-party component
    in Qt WebEngine, i.e. it is used commercially at scale.

    ⛔⛔ A DOCSTRING IS NOT ENOUGH ON ITS OWN. Clause 2 attaches to BINARY
    redistribution, and a minifier or a packaged build erases this comment in the
    same pass that creates the obligation. The artifact that discharges it is
    `THIRD_PARTY_NOTICES.md` + `licenses/` at the project root -- queue `SEC6`.
    ⚠ Clause 3: NO ENDORSEMENT. Marketing copy must not say or imply that the
    authors or Inria endorse this game.

⛔ TRANSLITERATED, NOT IMPORTED, and deliberately so. `Resources/` is stdlib-only
and numpy-free by contract (`CONSTRAINTS` §2) so it can be moved to JS / Swift /
Kotlin for the port; the algorithm is a few dozen lines, so a dependency would buy
nothing and cost the port. The BSD-3 attribution above is the licence condition
and must travel with any copy.

────────────────────────────────────────────────────────────────────────────────
WHY THIS RATHER THAN THE THRESHOLD THE OWNER ASKED FOR

The specification asked for "a threshold with a slider" to kill fingertip jitter.
⛔ A fixed threshold is a DEADBAND, and its failure mode is STICTION: nothing moves
until the input crosses the threshold, then it moves by the whole accumulated
amount at once. That converts jitter into small POPS — precisely the artefact this
project has spent the most effort removing, and precisely in the small-amplitude
band `F1` exists to serve (assembly-style fine alignment).

⭐ The 1€ filter instead varies its CUTOFF with SPEED: low cutoff at rest, where a
lot of smoothing is free because nothing is moving; high cutoff in motion, where
lag would be felt. Two parameters, both with a direct physical meaning, which is
what makes them slider-able:

    min_cutoff (Hz)  lower  -> less jitter when the hand is still
    beta             higher -> less lag when the hand moves

⭐⭐ AND IT IS TIME-BASED, WHICH IS `L1`'s LESSON RESTATED. A fixed per-frame
smoothing factor was removed on 2026-08-24 because the frame rate here is
CAMERA-bound, not compute-bound: the same 0.35/frame felt like 111 ms in good
light and 149 ms in poor (`N10`). Every alpha below is computed from the MEASURED
dt, so the feel does not move with the room lighting — or with the device, which
matters for the port.

────────────────────────────────────────────────────────────────────────────────
⛔ THE OFF SWITCH IS BIT-EXACT, AND THAT IS A REQUIREMENT, NOT A COURTESY

`enabled=False` returns the input value ITSELF — the same object, no arithmetic
performed on it. `F1`'s acceptance gate is that the filter switched off is
byte-identical to today's behaviour, proved by replay (`T6d`'s method, 975/975
frames, which is what made that build revert-free when the owner rejected it). A
passthrough that recomputed `1.0 * x` could differ in the last bit and would make
that proof impossible.

⚠ `now_ms` is INJECTED, never read from a clock here — same rule as `hand_state`,
so this module stays deterministic and golden-vector testable
(`analysis/verify_one_euro.py`).
"""
import math

# Defaults. ⚠ PLACEHOLDERS UNTIL THE LIVE TAKE TUNES THEM -- `F1` step 1 lands the
# mechanism, and the owner sets the feel on a slider (the same discipline
# `GRAB_RADIUS_MULTIPLIER` and `ROTATION_SLERP_TAU_MS` were settled by).
#
# ⭐ THE STARTING POINT IS MEASURED, not guessed: `analysis/f1_tip_census.py` puts
# the fingertip noise floor at a 1.5 mm median / ~4.7 mm p95 per tip, on frames
# where the palm itself barely moved. MIN_CUTOFF_HZ is set low enough to bite on
# that at rest without being felt in motion.
# ⭐⭐ SETTLED LIVE BY THE OWNER, 2026-08-26: **tau = 70 ms**, i.e. this cutoff.
# Reached the way the project settles feel constants -- on the rig, by preference,
# after the owner found the 132.6 ms default's lag "unbearable".
# ⛔ 70 ms rather than the ZERO first asked for: zero is the filter's OFF state and
# `analysis/verify_f1_grip_offstate.py` REFUSES it -- unfiltered, the fingertip
# grip point steps 120.7 px in a single frame against the palm path's 76.0 px.
# ⚠ Stored as a CUTOFF because that is what the filter speaks; the slider spoke
# milliseconds because that is what a person can reason about. tau = 1/(2*pi*fc).
MIN_CUTOFF_HZ = 2.2736          # tau = 70 ms
BETA = 0.02
D_CUTOFF_HZ = 1.0          # the paper's own default for the derivative's own filter


def alpha(cutoff_hz, dt_s):
    """The paper's smoothing factor: 1 / (1 + tau/dt), with tau = 1/(2*pi*fc).

    ⚠ Expressed this way rather than as dt/(tau+dt) so it matches the reference
    implementation line for line -- a port that diverges here is very hard to spot,
    because both forms look right and differ only in rounding.
    """
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau / dt_s)


class _LowPass:
    """First-order low-pass holding its own last raw and filtered value."""

    __slots__ = ("_y", "_x", "initialised")

    def __init__(self):
        self._y = None          # last filtered
        self._x = None          # last raw
        self.initialised = False

    def filter(self, x, a):
        if not self.initialised:
            self._y = self._x = x
            self.initialised = True
            return x
        y = a * x + (1.0 - a) * self._y
        self._x, self._y = x, y
        return y

    @property
    def last(self):
        """Last FILTERED value."""
        return self._y

    @property
    def last_raw(self):
        """Last RAW input. ⛔ The speed term below is built from THIS, not from
        the filtered value -- the reference implementation reads
        `x->lastRawValue()`, and using the filtered value instead makes the
        derivative depend on the filter's own output. It still converges, and it
        still looks right, which is exactly what makes the divergence expensive to
        find in a port. Caught here by the golden vectors on 2026-08-26."""
        return self._x

    def reset(self):
        self._y = self._x = None
        self.initialised = False


class OneEuroFilter:
    """One scalar channel. Build one per axis; `Vec3Filter` below does that.

    `min_cutoff_hz` and `beta` are read on EVERY call rather than captured at
    construction, so a live slider takes effect on the next frame instead of at the
    next grab.
    """

    __slots__ = ("min_cutoff_hz", "beta", "d_cutoff_hz", "enabled",
                 "_x", "_dx", "_last_ms")

    def __init__(self, min_cutoff_hz=MIN_CUTOFF_HZ, beta=BETA,
                 d_cutoff_hz=D_CUTOFF_HZ, enabled=True):
        self.min_cutoff_hz = min_cutoff_hz
        self.beta = beta
        self.d_cutoff_hz = d_cutoff_hz
        self.enabled = enabled
        self._x = _LowPass()
        self._dx = _LowPass()
        self._last_ms = None

    def reset(self):
        """Forget everything. ⚠ Call this on a NEW TRACK, never on a relabel --
        the `4.1` postmortem's lesson: a returning hand is a new track and must
        inherit nothing, but the same hand under a new label must keep its state."""
        self._x.reset()
        self._dx.reset()
        self._last_ms = None

    def filter(self, x, now_ms):
        # ⛔ BIT-EXACT PASSTHROUGH -- see the module header. Return `x` itself.
        if not self.enabled:
            return x

        if self._last_ms is None:
            self._last_ms = now_ms
            self._x.filter(x, 1.0)
            return x

        dt_ms = now_ms - self._last_ms
        if dt_ms <= 0.0:
            # ⚠ HOLD, do not extrapolate and do not divide by zero. Two frames
            # stamped identically (or a clock that went backwards) carry no new
            # time, so the output cannot have moved. `B8` measured that holding the
            # last value beats every fit; this is the degenerate case of that.
            return self._x.last if self._x.initialised else x

        self._last_ms = now_ms
        dt_s = dt_ms / 1000.0

        # Speed, itself low-passed -- an unfiltered derivative of a noisy signal is
        # noisier than the signal, and it is what sets the cutoff below.
        dx = 0.0 if not self._x.initialised else (x - self._x.last_raw) / dt_s
        edx = self._dx.filter(dx, alpha(self.d_cutoff_hz, dt_s))

        cutoff = self.min_cutoff_hz + self.beta * abs(edx)
        return self._x.filter(x, alpha(cutoff, dt_s))


class Vec3Filter:
    """Three independent channels, so a point can be filtered as one call.

    ⚠ PER-AXIS, NOT ON THE MAGNITUDE. Filtering |v| would couple the axes and make
    the smoothing direction-dependent; the axes are independent measurements and
    stay that way.
    """

    __slots__ = ("_f", "enabled")

    def __init__(self, min_cutoff_hz=MIN_CUTOFF_HZ, beta=BETA,
                 d_cutoff_hz=D_CUTOFF_HZ, enabled=True):
        self._f = [OneEuroFilter(min_cutoff_hz, beta, d_cutoff_hz, enabled)
                   for _ in range(3)]
        self.enabled = enabled

    def configure(self, min_cutoff_hz=None, beta=None, enabled=None):
        """Live re-tuning from a slider, without dropping the filter's history."""
        for f in self._f:
            if min_cutoff_hz is not None:
                f.min_cutoff_hz = min_cutoff_hz
            if beta is not None:
                f.beta = beta
            if enabled is not None:
                f.enabled = enabled
        if enabled is not None:
            self.enabled = enabled

    def reset(self):
        for f in self._f:
            f.reset()

    def filter(self, v, now_ms):
        # ⛔ Bit-exact passthrough returns the INPUT SEQUENCE ITSELF, not a rebuilt
        # tuple: `F1`'s gate compares against today's behaviour exactly.
        if not self.enabled:
            return v
        return (self._f[0].filter(v[0], now_ms),
                self._f[1].filter(v[1], now_ms),
                self._f[2].filter(v[2], now_ms))
