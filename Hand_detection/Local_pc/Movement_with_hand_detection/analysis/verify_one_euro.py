"""Golden vectors for `Resources/one_euro.py` — the 1€ filter (`F1` step 1).

⛔ THE REFERENCE BELOW IS WRITTEN INDEPENDENTLY, ON PURPOSE. `_reference_filter`
implements the paper's algorithm in a different style — functional, and using the
`dt/(tau+dt)` form of alpha rather than the module's `1/(1+tau/dt)` — so agreement
between the two is a real cross-check rather than a restatement.

⚠ This project has been burnt by exactly that distinction: four harnesses reported
CLEAN on takes the owner had just watched fail, and every one of them was a
RECOMPUTATION of the thing it was supposed to be checking (`_record_flush`'s header
exists for this reason). A golden-vector suite that generates its expectations
from the implementation pins regressions and nothing else.

⭐ These vectors exist BEFORE the port does, which is rule 6 of the house rules
(`CONSTRAINTS` §3). The very first such fixture in this project caught a real
banker's-rounding bug.

    .venv/Scripts/python.exe analysis/verify_one_euro.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import one_euro                                # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

_fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<62} {detail}")
    if not ok:
        _fails.append(name)


def close(a, b, tol=1e-12):
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# An INDEPENDENT implementation of the published algorithm. Different shape,
# different alpha expression. Do not refactor it to share code with the module.
# ---------------------------------------------------------------------------
def _reference_filter(samples, min_cutoff, beta, d_cutoff=1.0):
    """`samples` = [(x, t_ms), ...] -> [y, ...]"""
    out = []
    x_prev = y_prev = None
    dx_prev = None                # None => the derivative filter is uninitialised
    t_prev = None
    for x, t in samples:
        if t_prev is None:
            out.append(x)
            x_prev, y_prev, t_prev = x, x, t
            continue
        dt = (t - t_prev) / 1000.0
        t_prev = t

        def a(fc):
            tau = 1.0 / (2.0 * math.pi * fc)
            return dt / (tau + dt)                    # the OTHER algebraic form

        dx = (x - x_prev) / dt        # RAW previous value, per the paper
        edx = dx if dx_prev is None else (
            a(d_cutoff) * dx + (1.0 - a(d_cutoff)) * dx_prev)
        dx_prev = edx
        cutoff = min_cutoff + beta * abs(edx)
        y = a(cutoff) * x + (1.0 - a(cutoff)) * y_prev
        out.append(y)
        x_prev, y_prev = x, y
    return out


def section_alpha():
    print("\n§1  ALPHA — against the other algebraic form")
    for fc in (0.5, 1.0, 1.2, 30.0):
        for dt in (1 / 15.0, 1 / 30.0, 0.25):
            tau = 1.0 / (2.0 * math.pi * fc)
            check(f"alpha(fc={fc}, dt={dt:.4f})",
                  close(one_euro.alpha(fc, dt), dt / (tau + dt), 1e-12),
                  f"{one_euro.alpha(fc, dt):.12f}")
    check("alpha is in (0,1)", 0.0 < one_euro.alpha(1.0, 1 / 15.0) < 1.0)
    check("a faster sample smooths MORE (smaller alpha)",
          one_euro.alpha(1.0, 1 / 30.0) < one_euro.alpha(1.0, 1 / 15.0))


def section_offswitch():
    print("\n§2  ⛔ OFF IS BIT-EXACT — F1's acceptance gate depends on this")
    f = one_euro.OneEuroFilter(enabled=False)
    vals = [0.1, 1e-17, 12345.6789, -0.0, float("inf")]
    allsame = True
    for i, v in enumerate(vals):
        got = f.filter(v, i * 66.0)
        if not (got is v or (got != got and v != v)):
            allsame = False
    check("scalar passthrough returns the INPUT OBJECT", allsame)

    v3 = one_euro.Vec3Filter(enabled=False)
    src = (1.0, 2.0, 3.0)
    out = v3.filter(src, 0.0)
    check("Vec3 passthrough returns the input SEQUENCE itself", out is src)

    # ⭐ The real gate, stated as a test: a whole stream through a disabled filter
    # must be reproducible bit for bit.
    stream = [(math.sin(i) * 37.0, i * 66.0) for i in range(200)]
    g = one_euro.OneEuroFilter(enabled=False)
    check("200-sample stream is bit-identical with the filter off",
          all(g.filter(x, t) is x for x, t in stream))


def section_golden():
    print("\n§3  GOLDEN — module vs the independent reference")
    # A deterministic noisy ramp: no clock, no RNG module, reproducible anywhere.
    samples = []
    for i in range(120):
        t = i * 66.0                                   # ~15 fps, this rig's rate
        noise = ((i * 7919) % 101 - 50) / 50.0         # deterministic, +/-1
        samples.append((i * 0.5 + noise, t))

    for mc, beta in ((1.2, 0.02), (0.5, 0.0), (5.0, 0.5)):
        f = one_euro.OneEuroFilter(min_cutoff_hz=mc, beta=beta)
        got = [f.filter(x, t) for x, t in samples]
        want = _reference_filter(samples, mc, beta)
        worst = max(abs(a - b) for a, b in zip(got, want))
        check(f"min_cutoff={mc}, beta={beta} matches the reference",
              worst <= 1e-9, f"worst |diff| = {worst:.3e}")

    f = one_euro.OneEuroFilter()
    check("the first sample is passed through unchanged",
          f.filter(4.25, 0.0) == 4.25)


def section_time_basis():
    print("\n§4  ⭐⭐ TIME-BASED, NOT FRAME-BASED — L1's lesson, as a test")
    print("      The same physical motion sampled at two frame rates must reach")
    print("      the same place at the same WALL-CLOCK time. A per-frame factor")
    print("      would not: 0.35/frame felt 111 ms in good light, 149 ms in poor.")

    def settle(fps, target=1.0, ms=500.0):
        f = one_euro.OneEuroFilter(min_cutoff_hz=1.0, beta=0.0)
        step = 1000.0 / fps
        t, y = 0.0, None
        f.filter(0.0, 0.0)
        while t < ms:
            t += step
            y = f.filter(target, t)
        return y

    a15, a30, a60 = settle(15.0), settle(30.0), settle(60.0)
    spread = max(a15, a30, a60) - min(a15, a30, a60)
    check("15 / 30 / 60 fps settle to the same value after 500 ms",
          spread < 0.02, f"15={a15:.4f} 30={a30:.4f} 60={a60:.4f} spread={spread:.4f}")

    # And the contrast that motivates it: a fixed per-frame factor does NOT.
    def settle_perframe(fps, factor=0.35, target=1.0, ms=150.0):
        y, t, step = 0.0, 0.0, 1000.0 / fps
        while t < ms:
            t += step
            y += factor * (target - y)
        return y

    p15, p60 = settle_perframe(15.0), settle_perframe(60.0)
    check("...whereas a per-frame factor does NOT (the rejected design)",
          abs(p60 - p15) > 0.25,
          f"after 150 ms: 15fps={p15:.4f} 60fps={p60:.4f} -- the SAME constant, "
          f"two different feels")


def section_behaviour():
    print("\n§5  BEHAVIOUR — it must actually reduce jitter, and not add lag")
    # Jitter: a still signal with noise at the MEASURED fingertip floor (1.5 mm
    # median / 4.7 mm p95, `analysis/f1_tip_census.py`).
    noisy = []
    for i in range(300):
        noisy.append((((i * 7919) % 101 - 50) / 50.0 * 1.5, i * 66.0))
    f = one_euro.OneEuroFilter(min_cutoff_hz=1.2, beta=0.02)
    out = [f.filter(x, t) for x, t in noisy][50:]
    raw = [x for x, _ in noisy][50:]

    def rms(v):
        return math.sqrt(sum(a * a for a in v) / len(v))

    check("a still, noisy signal is attenuated",
          rms(out) < 0.5 * rms(raw),
          f"rms {rms(raw):.4f} -> {rms(out):.4f} ({rms(out)/rms(raw)*100:.0f}%)")

    # Lag: a fast ramp must be tracked, i.e. beta must be doing its job.
    ramp = [(i * 10.0, i * 66.0) for i in range(60)]
    slow = one_euro.OneEuroFilter(min_cutoff_hz=1.2, beta=0.0)
    fast = one_euro.OneEuroFilter(min_cutoff_hz=1.2, beta=0.05)
    es = abs(ramp[-1][0] - [slow.filter(x, t) for x, t in ramp][-1])
    ef = abs(ramp[-1][0] - [fast.filter(x, t) for x, t in ramp][-1])
    check("a higher beta tracks a fast ramp more closely (less lag)",
          ef < es, f"error beta=0 -> {es:.2f}, beta=0.05 -> {ef:.2f}")

    # ⭐ THE PROPERTY THAT MAKES A DEADBAND WRONG: no stiction. A slow drift far
    # below any sensible threshold must still MOVE the output, not accumulate.
    drift = [(i * 0.05, i * 66.0) for i in range(80)]
    d = one_euro.OneEuroFilter(min_cutoff_hz=1.2, beta=0.02)
    dout = [d.filter(x, t) for x, t in drift]
    monotonic = all(b >= a - 1e-12 for a, b in zip(dout, dout[1:]))
    check("a sub-threshold drift moves the output every frame (no stiction)",
          monotonic and dout[-1] > 0.5 * drift[-1][0],
          f"final {dout[-1]:.3f} vs input {drift[-1][0]:.3f}")


def section_edges():
    print("\n§6  EDGES — clocks, resets, axes")
    f = one_euro.OneEuroFilter()
    f.filter(1.0, 0.0)
    y1 = f.filter(2.0, 66.0)
    check("a repeated timestamp HOLDS, it does not divide by zero",
          f.filter(9.0, 66.0) == y1, f"held {y1:.6f}")
    check("a backwards clock also holds", f.filter(9.0, 10.0) == y1)

    f.reset()
    check("reset -> the next sample is passed through again",
          f.filter(123.0, 200.0) == 123.0)

    v = one_euro.Vec3Filter(min_cutoff_hz=1.0, beta=0.0)
    v.filter((0.0, 0.0, 0.0), 0.0)
    out = v.filter((10.0, 0.0, -10.0), 66.0)
    check("axes are filtered independently and symmetrically",
          close(out[0], -out[2], 1e-12) and out[1] == 0.0, str(out))

    v.configure(min_cutoff_hz=3.0, beta=0.1)
    check("configure() retunes every axis without a reset",
          all(x.min_cutoff_hz == 3.0 and x.beta == 0.1 for x in v._f))
    v.configure(enabled=False)
    src = (7.0, 8.0, 9.0)
    check("configure(enabled=False) restores the bit-exact passthrough",
          v.filter(src, 999.0) is src)


def main():
    print("=" * 82)
    print("ONE EURO FILTER — golden vectors (F1 step 1)")
    print("=" * 82)
    section_alpha()
    section_offswitch()
    section_golden()
    section_time_basis()
    section_behaviour()
    section_edges()
    print("=" * 82)
    if _fails:
        print(f"{len(_fails)} CHECK(S) FAILED")
        for n in _fails:
            print(f"   - {n}")
        return 1
    print("ALL CHECKS PASSED — matches an independent implementation of the paper,")
    print("is time-based not frame-based, and is bit-exact when switched off.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
