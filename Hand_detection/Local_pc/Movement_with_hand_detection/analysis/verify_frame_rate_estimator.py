"""GOLDEN VECTORS for `hand_identity.FrameRateEstimator` (queue N7 / U3 port).

⭐ THIS FILE IS THE EXECUTABLE SPECIFICATION FOR THE WEB/MOBILE PORT.

The cross-platform target means the frame-rate estimator will be reimplemented
outside Python. A reimplementation is correct when it reproduces the table
below, and is not to be trusted until it does. **Do not edit the expected values
to match a port -- fix the port.** Precedent: `verify_observability.py`, which
pinned the numpy-free closed form to 1.6e-11 against numpy for exactly this
reason.

It also guards the Python side against silent drift: the window length, the
outlier bounds and the minimum sample count are all behavioural, and changing
any of them changes DR-1's dwells in production.

Run:  .venv/Scripts/python.exe analysis/verify_frame_rate_estimator.py
Exit: 0 all vectors reproduce, 1 otherwise.

--- PORT NOTES (read before reimplementing) ---
  * timestamps are MILLISECONDS, monotonic. Browser: `performance.now()`.
    NOT `Date.now()` -- wall-clock, jumps on NTP correction.
  * no dependencies: list ops, comparison, division. Nothing else.
  * intervals outside [1, 500] ms are DISCARDED, not clamped -- they are dropped
    frames and stalls, not measurements.
  * fewer than 5 intervals -> report the fallback rate, not a guess.
  * the estimate is the MEDIAN of the window (lower-middle element for an even
    count, i.e. index len//2 after sorting), never the mean.
"""
import importlib.util
import os
import sys

_HI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Python_Server_MediaPipe_vision_pipeline", "Resources", "hand_identity.py")
_spec = importlib.util.spec_from_file_location("hand_identity", _HI_PATH)
HI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(HI)


def steady(fps, n, start=1000.0):
    """n timestamps at a constant rate."""
    step = 1000.0 / fps
    return [start + i * step for i in range(n)]


def feed(timestamps):
    est = HI.FrameRateEstimator()
    for t in timestamps:
        est.observe(t)
    return est


# (name, timestamps, expected_fps_rounded_1dp, expected_switch_dwell, expected_measured)
VECTORS = []

# --- 1. fallback until enough samples ---
VECTORS.append(("no samples", [], 24.0, 12, False))
VECTORS.append(("1 timestamp", steady(24.0, 1), 24.0, 12, False))
VECTORS.append(("4 intervals (below the 5 minimum)", steady(24.0, 5), 24.0, 12, False))

# --- 2. steady rates ---
VECTORS.append(("steady 24 fps", steady(24.0, 60), 24.0, 12, True))
VECTORS.append(("steady 15.77 fps (dim light, N10)", steady(15.77, 60), 15.8, 8, True))
VECTORS.append(("steady 30 fps", steady(30.0, 60), 30.0, 15, True))
VECTORS.append(("steady 19.33 fps (free_manipulation #3)", steady(19.33, 60), 19.3, 10, True))

# --- 3. robustness: a dropped frame must NOT drag the estimate ---
_drop = steady(24.0, 60)
del _drop[30]                       # one missing frame -> one double interval
VECTORS.append(("24 fps with a dropped frame", _drop, 24.0, 12, True))

# --- 4. robustness: a stall is discarded, not absorbed ---
_stall = steady(24.0, 30) + [steady(24.0, 30)[-1] + 3000.0]
_stall += [_stall[-1] + i * (1000.0 / 24.0) for i in range(1, 30)]
VECTORS.append(("24 fps with a 3 s stall", _stall, 24.0, 12, True))

# --- 5. duplicate timestamps are discarded (interval below the 1 ms floor) ---
_dupes = []
for t in steady(24.0, 60):
    _dupes.extend([t, t])           # every frame delivered twice
VECTORS.append(("duplicated timestamps", _dupes, 24.0, 12, True))

# --- 6. a sustained rate CHANGE is followed once it fills the window ---
_change = steady(24.0, 60)
_change += [_change[-1] + i * (1000.0 / 15.0) for i in range(1, 61)]
# 500 ms x 15 fps = 7.5 frames exactly -- a half-way case, so this vector also
# pins the rounding convention. Float accumulation puts the measured rate a hair
# under 15.0, which is why the dwell is 7 rather than 8; that is correct and is
# the honest behaviour of a measured (not assumed) rate.
VECTORS.append(("24 -> 15 fps, sustained", _change, 15.0, 7, True))


def main():
    print("=" * 78)
    print("FrameRateEstimator golden vectors (N7 / web-port contract)")
    print("=" * 78)
    print(f"\n  window={HI._FPS_WINDOW} frames, min_samples={HI._MIN_FPS_SAMPLES}, "
          f"interval bounds=[{HI._MIN_INTERVAL_MS}, {HI._MAX_INTERVAL_MS}] ms, "
          f"fallback={HI.FALLBACK_FPS} fps\n")
    print(f"  {'vector':<42}{'fps':>8}{'want':>8}{'dwell':>7}{'want':>6}{'':>4}")

    ok = True
    for name, ts, want_fps, want_dwell, want_measured in VECTORS:
        est = feed(ts)
        got_fps = round(est.fps, 1)
        got_dwell = HI.frames_for("switch", est.fps)
        good = (got_fps == want_fps and got_dwell == want_dwell
                and est.measured == want_measured)
        ok &= good
        print(f"  {name[:41]:<42}{got_fps:>8.1f}{want_fps:>8.1f}"
              f"{got_dwell:>7}{want_dwell:>6}{'  ok' if good else ' FAIL':>4}")
        if not good and est.measured != want_measured:
            print(f"      measured={est.measured}, expected {want_measured}")

    print("\n--- dwell table at representative rates (the port must match) ---")
    print(f"  {'fps':>7}{'track_end':>11}{'lock_vote':>11}{'pos_window':>12}{'switch':>8}")
    for fps in (12.0, 15.0, 15.77, 19.33, 21.0, 24.0, 25.0, 30.0):
        print(f"  {fps:>7.2f}{HI.frames_for('track_end', fps):>11}"
              f"{HI.frames_for('lock_vote', fps):>11}"
              f"{HI.frames_for('position_window', fps):>12}"
              f"{HI.frames_for('switch', fps):>8}")

    print("\n--- half-way rounding must match JS `Math.round`, not Python's ---")
    # Python's round() is banker's (half-to-even); JS Math.round is half-up. The
    # dwells hit exactly .5 at odd frame rates, so this is a real divergence.
    for fps in (13.0, 17.0, 19.0):
        exact = HI._SWITCH_MS * fps / 1000.0
        got = HI.frames_for("switch", fps)
        want = int(exact + 0.5)
        good = got == want
        ok &= good
        print(f"  {fps:>5.1f} fps -> {exact:>4.1f} frames -> {got:>3} "
              f"(JS Math.round would give {want}) {'ok' if good else 'FAIL'}"
              f"{'   [python round() would give %d]' % round(exact) if round(exact) != want else ''}")

    print("\n--- dependency check (the port must have nothing to install) ---")
    # Read the file directly: the module is loaded via importlib without a
    # sys.modules entry, so inspect.getsource() cannot locate it.
    with open(_HI_PATH, encoding="utf-8") as f:
        text = f.read()
    start = text.index("class FrameRateEstimator")
    # End at the next TOP-LEVEL definition, not the next class: `palm_centroid`
    # and `palm_width` sit in between and legitimately use `math`, which made an
    # over-wide slice report a dependency the class does not have.
    ends = [text.index(m, start + 1) for m in ("\nclass ", "\ndef ")
            if m in text[start + 1:]]
    src = text[start:min(ends)] if ends else text[start:]
    # Strip the class docstring before scanning: it DESCRIBES the port contract
    # and legitimately names numpy/math/time in prose. Scanning it produced a
    # false failure on the first run.
    q = src.find('"""')
    if q != -1:
        q2 = src.find('"""', q + 3)
        if q2 != -1:
            src = src[:q] + src[q2 + 3:]
    banned = [w for w in ("import ", "numpy", "math.", "time.", "random.")
              if w in src]
    if banned:
        ok = False
        print(f"  [FAIL] FrameRateEstimator references {banned} -- it must stay "
              f"dependency-free for the port")
    else:
        print("  [PASS] no imports, no math/time/random, no numpy "
              f"({len(src.splitlines())} lines to transcribe)")

    print("\n" + "=" * 78)
    print("ALL VECTORS REPRODUCE" if ok else "FAILURES ABOVE -- fix the code, "
          "not the expectations")
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
