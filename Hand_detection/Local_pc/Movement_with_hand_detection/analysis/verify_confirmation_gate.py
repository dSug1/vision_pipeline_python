"""Synthetic correctness for B7 (`Resources/confirmation_gate.py`).

The corpus cannot tell you whether the state machine is CORRECT -- only whether
it is useful. This does the first half, on signals whose ground truth is known by
construction, and it is where the two cases that matter are separated:

    a TELEPORT       out-and-back -> RETURNED, the excursion is DISCARDED and
                     never reaches the fit
    a REVERSAL       genuine turn  -> COHERENT, the frames are ACCEPTED (late,
                     by exactly L frames) and DO reach the fit

B3'' passed its own synthetic test (`verify_block_predictor.py`) and then failed
on the corpus, so passing here proves nothing about usefulness. It proves the
mechanism does what the design says, which is the precondition for the corpus
numbers meaning anything at all.

    .venv/Scripts/python.exe analysis/verify_confirmation_gate.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:                                    # the console here is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import confirmation_gate as CG

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def state(x, y=100.0, scale=80.0, arcs=(0.9, 0.9, 0.9, 0.9), q=(1.0, 0.0, 0.0, 0.0)):
    return {"position": (x, y), "scale": scale, "quaternion": q,
            "arcs": arcs, "conditioning": 1.0}


def run(xs, **kw):
    g = CG.ConfirmationGate(**kw)
    rows = []
    for x in xs:
        rows.append(g.update(state(x)))
    return g, rows


print("=" * 78)
print("B7 confirmation gate -- synthetic correctness")
print("=" * 78)

# ---------------------------------------------------------------- 1. no-op case
print("\n1. SMOOTH MOTION -- the common case must be untouched, with NO latency")
xs = [100.0 + 8.0 * k for k in range(20)]
g, rows = run(xs, lag=2)
flags = sum(1 for r in rows if r["flagged"])
maxdev = max(abs(r["output"]["position"][0] - x) for r, x in zip(rows, xs))
check("constant velocity: never flags", flags == 0, f"flags={flags}")
check("constant velocity: output IS the measurement", maxdev < 1e-9,
      f"max|out-meas|={maxdev:.2e}")

xs = [100.0 + 4.0 * k + 0.5 * 1.5 * k * k for k in range(20)]
g, rows = run(xs, lag=2)
check("constant acceleration: never flags",
      sum(1 for r in rows if r["flagged"]) == 0)

# ---------------------------------------------------------------- 2. teleport
print("\n2. TELEPORT (out-and-back over 2 frames) -> RETURNED, discarded")
base = [100.0 + 5.0 * k for k in range(10)]
tele = base + [base[-1] + 5.0 + 250.0, base[-1] + 10.0 + 240.0] + \
       [base[-1] + 5.0 * k for k in range(3, 9)]
g, rows = run(tele, lag=2)
flag_at = [i for i, r in enumerate(rows) if r["flagged"]]
disc_at = [i for i, r in enumerate(rows) if r["discarded"]]
check("teleport is flagged", flag_at and flag_at[0] == 10, f"flagged at {flag_at}")
check("verdict is RETURNED (discarded, not confirmed)", bool(disc_at),
      f"discarded at {disc_at}")
check("decision comes exactly L frames after the flag",
      bool(disc_at) and disc_at[0] - flag_at[0] == 2,
      f"lag measured {disc_at[0]-flag_at[0] if disc_at else '-'}")
# ⭐ the point of the whole design: during the excursion the output never goes
# ANYWHERE NEAR the 250 px outlier, so the visible artifact is at worst a short
# lag rather than a jump. ⚠ Under the default coast_mode="hold" the output
# freezes instead of tracking the true trajectory, so it lags by |v|*L -- an
# honest cost, measured below and swept by b7_eval.py.
true_x = [base[-1] + 5.0 * (i - 9) for i in (10, 11)]
err = [abs(rows[i]["output"]["position"][0] - t) for i, t in zip((10, 11), true_x)]
check("output during the excursion never follows the outlier",
      max(err) < 30.0, f"lag={[round(e,2) for e in err]} px (outlier was 250)")
g_x, rows_x = run(tele, lag=2, coast_mode="extrapolate")
err_x = [abs(rows_x[i]["output"]["position"][0] - t)
         for i, t in zip((10, 11), true_x)]
check("coast_mode='extrapolate' tracks the true trajectory exactly",
      max(err_x) < 1e-9, f"err={[round(e,4) for e in err_x]} px")
check("the excursion never entered the fit (16.2 rule 6)",
      max(g._ch["pos_x"].hist) < 300.0,
      f"hist max={max(g._ch['pos_x'].hist):.1f} (excursion was ~400)")

print("\n2b. TELEPORT LONGER THAN L is accepted -- the documented limit")
long_tele = base + [base[-1] + 300.0 + 5.0 * k for k in range(1, 6)]
g, rows = run(long_tele, lag=2)
check("a 5-frame teleport reads COHERENT (honest failure mode)",
      any(r["confirmed"] for r in rows[10:]),
      "confirmed=" + str([i for i, r in enumerate(rows) if r["confirmed"]]))

# ---------------------------------------------------------------- 3. reversal
print("\n3. DIRECTION REVERSAL -> COHERENT, accepted late, NOT discarded")
rev = [100.0 + 12.0 * k for k in range(10)]
rev += [rev[-1] - 12.0 * k for k in range(1, 9)]        # hard turn, same speed
g, rows = run(rev, lag=2)
disc = [i for i, r in enumerate(rows) if r["discarded"]]
conf = [i for i, r in enumerate(rows) if r["confirmed"]]
check("a reversal is NEVER discarded", not disc, f"discarded at {disc}")
check("if flagged, it is confirmed instead",
      (not any(r["flagged"] for r in rows)) or bool(conf), f"confirmed at {conf}")
# and the output must arrive back on the truth
tail = [abs(rows[i]["output"]["position"][0] - rev[i]) for i in range(14, 18)]
check("output rejoins the measurement after the blend", max(tail) < 1e-6,
      f"max tail err={max(tail):.2e}")

print("\n3b. SMOOTH REVERSAL (decelerate, turn, accelerate) -- the game's case")
rev2 = []
v = 14.0
x = 100.0
for k in range(22):
    rev2.append(x)
    x += v
    v -= 2.6
g, rows = run(rev2, lag=2)
check("smooth reversal is never discarded",
      not any(r["discarded"] for r in rows),
      "flags=" + str(sum(1 for r in rows if r["flagged"])))

# ---------------------------------------------------------------- 4. S3 / rules
print("\n4. BINDING RULES")
g, rows = run(tele, lag=2)
pend = [i for i, r in enumerate(rows) if not all(r["valid"].values())]
check("S3: valid=False while PENDING (gesture logic holds)", bool(pend),
      f"invalid frames {pend}")
check("S3: valid is True again once the decision is taken",
      all(all(rows[i]["valid"].values()) for i in range(13, len(rows))))

g2 = CG.ConfirmationGate(lag=2)
for x in tele[:11]:
    g2.update(state(x))
g2.reset()
check("reset() clears all channel history",
      all(not c.hist and not c.pending for c in g2._ch.values()))

print("\n4b. PER-CHANNEL: a confused finger must not discard a good palm")
g3 = CG.ConfirmationGate(lag=2)
res = None
for k in range(14):
    arcs = (0.90, 0.90, 0.90, 0.90)
    if k == 10:
        arcs = (0.30, 0.90, 0.90, 0.90)          # index arc alone goes wrong
    res = g3.update(state(100.0 + 5.0 * k, arcs=arcs))
    if k == 10:
        check("only the offending channel is flagged",
              res["flagged"] == ["arc0"], f"flagged={res['flagged']}")
        check("the palm output is still the measurement",
              abs(res["output"]["position"][0] - 150.0) < 1e-9)

print("\n4c. HARD CAP -- the backstop the LAG alone does not provide")
# ⚠ Note what does NOT trip it, because it is the more interesting half: a
# permanent level shift is CONFIRMED (F..F+L are coherent with each other), so
# the gate accepts it after L frames and no backstop is needed. The cap exists
# for the case the lag cannot bound -- a repeating flag/discard cycle, where each
# episode ends legitimately but the channel never gets a clean accept.
step = [100.0 + 3.0 * k for k in range(10)] + [500.0 + 3.0 * k for k in range(10)]
g, rows = run(step, lag=2)
check("a permanent level shift is CONFIRMED, not coasted",
      any(r["confirmed"] for r in rows) and not any(r["forced"] for r in rows))

# Tested directly, with a cap tighter than the lag, because the DEFAULT cap (2L)
# is deliberately hard to reach -- a flag/discard cycle self-terminates, since the
# accepted frame widens the fit's own residual variance and the next frame passes.
# How often the cap actually fires on real data is reported by `b7_eval.py`; if
# that number is ever large, the gate is cascading and the run is void.
g, rows = run(tele, lag=6, hard_cap=2)
forced_at = [i for i, r in enumerate(rows) if r["forced"]]
check("the cap bounds the coast independently of L",
      forced_at and forced_at[0] == 11, f"forced at {forced_at}")
check("a forced channel re-seeds (output returns to the measurement)",
      bool(forced_at) and abs(rows[11]["output"]["position"][0] - tele[11]) < 1e-9)

# ---------------------------------------------------------------- 5. latency
print("\n4d. COAST MODE -- what the cube does while the decision is deferred")
# The reversal is the case that separates them: extrapolating runs the cube PAST
# the turn and brings it back (an overshoot), holding merely lags.
over = {}
for mode in ("hold", "damped", "extrapolate"):
    g, rows = run(rev, lag=2, coast_mode=mode)
    # rev turns at index 9; the true direction after the turn is negative
    over[mode] = max(rows[i]["output"]["position"][0] - rev[i] for i in (10, 11))
    print(f"    {mode:<12} overshoot past the turn: {over[mode]:>7.2f} px")
check("holding never overshoots the reversal", over["hold"] <= over["damped"] + 1e-9)
check("damped overshoots less than extrapolating",
      over["damped"] <= over["extrapolate"] + 1e-9)

print("\n5. LATENCY, in the unit that matters")
for lag in (2, 3, 4, 6):
    for fps in (24.0, 30.0):
        ms = 1000.0 * lag / fps
        print(f"    L={lag}  @{fps:.0f} fps -> {ms:6.1f} ms"
              + ("   ⚠ above the ~75 ms perceptibility threshold" if ms > 75 else ""))

# ---------------------------------------------------------------- 6. quaternion
print("\n6. QUATERNION CHANNEL")


def qz(deg):
    a = math.radians(deg) / 2.0
    return (math.cos(a), 0.0, 0.0, math.sin(a))


g = CG.ConfirmationGate(lag=2)
rows = []
for k in range(10):
    rows.append(g.update(state(100.0, q=qz(6.0 * k))))
rows.append(g.update(state(100.0, q=qz(6.0 * 9 + 70.0))))      # orientation jump
for k in range(1, 8):
    rows.append(g.update(state(100.0, q=qz(6.0 * (9 + k)))))    # and back
check("orientation teleport flagged", any("quat" in r["flagged"] for r in rows),
      "flag=" + str([i for i, r in enumerate(rows) if "quat" in r["flagged"]]))
check("orientation teleport DISCARDED (came back)",
      any("quat" in r["discarded"] for r in rows),
      "disc=" + str([i for i, r in enumerate(rows) if "quat" in r["discarded"]]))
rows = []
g = CG.ConfirmationGate(lag=2)
for k in range(10):
    rows.append(g.update(state(100.0, q=qz(8.0 * k))))
for k in range(1, 9):
    rows.append(g.update(state(100.0, q=qz(8.0 * (9 - k)))))     # genuine reversal
check("orientation reversal NOT discarded",
      not any("quat" in r["discarded"] for r in rows),
      "disc=" + str([i for i, r in enumerate(rows) if "quat" in r["discarded"]]))

print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
