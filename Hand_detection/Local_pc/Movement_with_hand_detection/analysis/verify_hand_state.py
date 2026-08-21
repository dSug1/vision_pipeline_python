"""Golden vectors for `Resources/hand_state.py` (queue D1, spec §2.1/§2.2).

⚠ HISTORY, BECAUSE THE HEADLINE TEST CHANGED ON PURPOSE. D1 shipped this file
asserting `BRIDGE_WINDOW_MS == 0.0` -- that was D1's whole claim, that landing the
contract changed no behaviour. **D2 raised the window to 150 ms deliberately**,
against the classified measurement in `analysis/d2_bridge_ab.py`, so §2 now
asserts the shipped value AND that a 0-window tracker still reproduces the pre-D2
rule exactly. The second half is the live A/B's control arm, not ceremony.

⭐ §4 IS THE ONE TO READ. The same coast window at two different frame rates must
give the SAME verdict in ms and DIFFERENT frame counts. This pipeline runs 14-24
fps depending on the machine (spec §0.7), so a window expressed in frames means
different things on different hardware -- N1's rule, and the reason
`ms_since_measurement` and not `frames_since_measurement` is what D2 thresholds.

⚠ Do not edit the expectations to match a port. The port is wrong, not this.

    .venv/Scripts/python.exe analysis/verify_hand_state.py
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_state as HS

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


print("=" * 78)
print("GOLDEN VECTORS -- Resources/hand_state.py (D1)")
print("=" * 78)

print("\n1. INITIAL STATE -- a hand never seen is LOST, not tracked")
t = HS.HandStateTracker()
check("fresh tracker is SUSTAINED_LOST", t.tracking_state == HS.SUSTAINED_LOST, t.tracking_state)
check("fresh tracker does not hold a track", t.holds_track is False)
check("frames_since_measurement starts at 0", t.frames_since_measurement == 0)
check("ms_since_measurement is None (never measured)", t.ms_since_measurement is None)
check("orientation_valid starts False", t.orientation_valid is False)
# A miss BEFORE any measurement must not bridge -- there is no pose to hold.
t2 = HS.HandStateTracker(bridge_window_ms=1000.0)
check("miss with no prior measurement -> SUSTAINED_LOST even with a 1 s window",
      t2.update(False, 0.0) == HS.SUSTAINED_LOST)

print("\n2. ⭐ THE ZERO-WINDOW CONTROL -- pre-D2 behaviour must stay reproducible")
# ⚠ D1 shipped this as `BRIDGE_WINDOW_MS == 0.0`, asserting that D1 changed no
# behaviour. D2 raised it to 150 ms DELIBERATELY, with the measurement in
# `analysis/d2_bridge_ab.py` -- so the assertion moved from "the default is 0"
# to "the default is the value D2 measured, and a 0 window still reproduces the
# pre-D2 rule exactly". That second half is not ceremony: it is the control arm
# of the live A/B, and if it ever stopped working the A/B would have no baseline.
check("shipped default is D2's measured 150.0 ms", HS.BRIDGE_WINDOW_MS == 150.0,
      repr(HS.BRIDGE_WINDOW_MS))
check("⚠ and is not in D4/M10.7 grace-period territory (<= 300 ms)",
      HS.BRIDGE_WINDOW_MS <= 300.0)
t = HS.HandStateTracker(bridge_window_ms=0.0)
t.update(True, 1000.0)
states = set()
now = 1000.0
for i in range(200):                       # 200 frames of assorted gaps
    now += 41.7 if i % 3 else 8.0          # incl. gaps far below any window
    states.add(t.update(False, now))
check("no sequence of misses ever reaches BRIDGING at a 0 window",
      states == {HS.SUSTAINED_LOST}, str(sorted(states)))
# The zero-gap edge: two packets sharing a timestamp must still not bridge,
# or `<=` on a 0.0 window would quietly open one.
t = HS.HandStateTracker(bridge_window_ms=0.0)
t.update(True, 500.0)
check("a miss at the SAME timestamp still does not bridge",
      t.update(False, 500.0) == HS.SUSTAINED_LOST)

print("\n3. THE STATE MACHINE at the SHIPPED window (D2's behaviour)")
t = HS.HandStateTracker()          # the shipped 150 ms
check("the shipped tracker bridges rather than dropping on frame one",
      t.update(True, 0.0) == HS.TRACKING and t.update(False, 42.0) == HS.BRIDGING)
t = HS.HandStateTracker(bridge_window_ms=150.0)
check("first detection -> TRACKING", t.update(True, 0.0) == HS.TRACKING)
check("  frames_since_measurement == 0", t.frames_since_measurement == 0)
check("  ms_since_measurement == 0.0", t.ms_since_measurement == 0.0)
check("  reacquired_after_ms == 0.0 on a first-ever detection",
      t.reacquired_after_ms == 0.0)
check("miss at 60 ms -> BRIDGING", t.update(False, 60.0) == HS.BRIDGING)
check("  frames_since_measurement == 1", t.frames_since_measurement == 1)
check("  ms_since_measurement == 60.0", t.ms_since_measurement == 60.0)
check("miss at 150 ms -> BRIDGING (boundary is inclusive)",
      t.update(False, 150.0) == HS.BRIDGING)
check("  frames_since_measurement == 2", t.frames_since_measurement == 2)
check("miss at 151 ms -> SUSTAINED_LOST", t.update(False, 151.0) == HS.SUSTAINED_LOST)
check("  holds_track is False once LOST", t.holds_track is False)
check("a LOST track does not resurrect on a later miss inside the window",
      t.update(False, 152.0) == HS.SUSTAINED_LOST)

print("\n4. ⭐ MILLISECONDS, NOT FRAMES -- same window, two real frame rates")
for fps, expect_frames in ((24.0, 3), (14.0, 2)):
    dt = 1000.0 / fps
    t = HS.HandStateTracker(bridge_window_ms=150.0)
    t.update(True, 0.0)
    now, bridged = 0.0, 0
    while True:
        now += dt
        if t.update(False, now) != HS.BRIDGING:
            break
        bridged += 1
    check(f"{fps:.0f} fps: bridged {bridged} frames over the same 150 ms",
          bridged == expect_frames, f"{bridged} frames x {dt:.1f} ms")
check("  -> the frame COUNT differs by frame rate; the ms verdict does not", True)

print("\n5. REACQUISITION -- the gap D3's resync blend needs")
t = HS.HandStateTracker(bridge_window_ms=150.0)
t.update(True, 0.0)
t.update(False, 40.0)
t.update(False, 80.0)
check("reacquired_after_ms is 0.0 WHILE coasting", t.reacquired_after_ms == 0.0)
t.update(True, 120.0)
check("on reacquisition it reports the whole gap", t.reacquired_after_ms == 120.0,
      f"{t.reacquired_after_ms} ms")
check("  and the counters reset", t.frames_since_measurement == 0 and t.ms_since_measurement == 0.0)
t.update(True, 160.0)
check("next continuously-tracked frame reports 0.0 again",
      t.reacquired_after_ms == 0.0)

print("\n6. orientation_valid -- DR-2's bit, and it must never coast")
t = HS.HandStateTracker(bridge_window_ms=150.0)
t.update(True, 0.0)
t.set_orientation_valid(True)
check("set while TRACKING is kept", t.orientation_valid is True)
t.update(False, 40.0)
check("a dropout clears it -- a stale True must not survive", t.orientation_valid is False)
t.set_orientation_valid(True)
check("and it cannot be set while BRIDGING (no measurement to validate)",
      t.orientation_valid is False)

print("\n7. reset() and a backwards clock")
t = HS.HandStateTracker(bridge_window_ms=150.0)
t.update(True, 1000.0)
t.set_orientation_valid(True)
t.reset()
check("reset() restores the construction state",
      (t.tracking_state == HS.SUSTAINED_LOST and t.frames_since_measurement == 0
       and t.ms_since_measurement is None and t.orientation_valid is False
       and t.reacquired_after_ms == 0.0))
t = HS.HandStateTracker(bridge_window_ms=150.0)
t.update(True, 1000.0)
check("a clock that steps BACKWARDS clamps to 0, never negative",
      t.update(False, 900.0) is not None and t.ms_since_measurement == 0.0,
      f"{t.ms_since_measurement}")

print("\n8. PORT CONTRACT -- stdlib only, no side effects")
# Strip EVERY string literal and comment before scanning, not just the leading
# docstring: the prose legitimately discusses `time.perf_counter()` and numpy
# (it says the module must not use them). `verify_hand_ownership.py` shipped the
# slice-off-the-docstring version first and it false-positived on a class
# docstring; tokenize is the version that does not.
import io  # noqa: E402
import tokenize  # noqa: E402

with open(os.path.join(BASE, "Resources", "hand_state.py"), encoding="utf-8") as _fh:
    _toks = list(tokenize.generate_tokens(_fh.readline))
code = " ".join(t.string for t in _toks
                if t.type not in (tokenize.STRING, tokenize.COMMENT))
check("imports nothing (no numpy, no clock read)", "import " not in code)
for banned in ("time.", "perf_counter", "random", "numpy"):
    check(f"no `{banned}` anywhere in the module", banned not in code)

print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
