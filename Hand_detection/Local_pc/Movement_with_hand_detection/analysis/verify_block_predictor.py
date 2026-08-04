"""Correctness check for `block_predictor.py` on SYNTHETIC data (queue B3'').

Not a test against the recordings -- this proves the implementation does what it
is described as doing, so the design can be reviewed meaningfully. Ground truth
is known by construction, which no recording provides.

Checks:
  1 a known quadratic trajectory -> p, v, a recovered exactly
  2 the prediction variance GROWS with horizon and with fit residual
  3 a known constant angular velocity -> omega recovered, alpha ~ 0
  4 known angular acceleration -> alpha recovered
  5 a clean injected outlier is rejected; smooth fast motion is not
  6 the coast band WIDENS with horizon (the self-limiting anti-cascade claim)

Run:  .venv/Scripts/python.exe analysis/verify_block_predictor.py
Exit: 0 all pass.
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from Resources import block_predictor as BP

ok = True


def check(label, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")


print("=" * 78)
print("block_predictor correctness on synthetic data (B3'')")
print("=" * 78)

# --- 1. derivative recovery ------------------------------------------------
print("\n--- 1. a known quadratic: are p, v, a recovered? ---")
P0, V0, A0 = 100.0, -3.0, 0.8
n = BP.WINDOW
vals = [P0 + V0 * t + 0.5 * A0 * t * t for t in [float(k - (n - 1)) for k in range(n)]]
st = BP.fit_channel(vals)
check("p recovered", st and abs(st.p - P0) < 1e-6, f"got {st.p:.6f} want {P0}")
check("v recovered", st and abs(st.v - V0) < 1e-6, f"got {st.v:.6f} want {V0}")
check("a recovered", st and abs(st.a - A0) < 1e-6, f"got {st.a:.6f} want {A0}")
check("noiseless fit has ~zero residual variance", st and st.s2 < 1e-12,
      f"s2={st.s2:.2e}")
pred1 = st.predict(1)
want1 = P0 + V0 * 1 + 0.5 * A0 * 1
check("prediction at h=1 matches the closed form", abs(pred1 - want1) < 1e-9)

# --- 2. variance behaviour -------------------------------------------------
print("\n--- 2. does the predictive variance behave like a distribution? ---")
noisy = [v + (0.5 if k % 2 else -0.5) for k, v in enumerate(vals)]   # jittered
stn = BP.fit_channel(noisy)
v1, v2, v3 = stn.variance(1), stn.variance(2), stn.variance(3)
check("variance grows with horizon", v1 < v2 < v3,
      f"h1={v1:.3f} h2={v2:.3f} h3={v3:.3f}")
check("noisy fit has larger variance than clean", stn.variance(1) > (st.variance(1) or 0),
      f"noisy={stn.variance(1):.3f} clean={st.variance(1):.3e}")

# --- 3/4. angular velocity and acceleration --------------------------------
print("\n--- 3. constant angular velocity: is omega recovered? ---")
AXIS = (0.0, 0.0, 1.0)
RATE = math.radians(6.0)          # 6 deg/frame about z
qs = [(1.0, 0.0, 0.0, 0.0)]
for _ in range(BP.WINDOW - 1):
    qs.append(BP._qmul(BP._qexp(tuple(a * RATE for a in AXIS)), qs[-1]))
qst = BP.fit_quat(qs)
got = math.degrees(qst.omega[2]) if qst else None
check("omega_z recovered", qst and abs(got - 6.0) < 0.05, f"got {got:.4f} deg/frame")
check("alpha ~ 0 for constant rate", qst and abs(math.degrees(qst.alpha[2])) < 0.05,
      f"alpha={math.degrees(qst.alpha[2]):.4f}")

print("\n--- 4. angular ACCELERATION: is alpha recovered? ---")
qs2 = [(1.0, 0.0, 0.0, 0.0)]
rate = math.radians(2.0)
step = math.radians(1.0)          # +1 deg/frame per frame
for k in range(BP.WINDOW - 1):
    qs2.append(BP._qmul(BP._qexp((0.0, 0.0, rate + step * k)), qs2[-1]))
qst2 = BP.fit_quat(qs2)
check("alpha_z recovered (~1 deg/frame^2)",
      qst2 and abs(math.degrees(qst2.alpha[2]) - 1.0) < 0.05,
      f"got {math.degrees(qst2.alpha[2]):.4f}")

# --- 5. does it reject an outlier but not smooth fast motion? --------------
print("\n--- 5. outlier rejected, smooth FAST motion accepted? ---")


def run(traj, floors=None):
    g = BP.BlockPredictor(floors=floors)
    out = []
    for x in traj:
        st = {"position": (x, 0.0), "scale": 60.0,
              "quaternion": (1.0, 0.0, 0.0, 0.0),
              "arcs": (0.9, 0.9, 0.9, 0.9)}
        out.append(g.update(st))
    return out


smooth_fast = [0.0 + 25.0 * k for k in range(14)]        # 25 px/frame, constant
res = run(smooth_fast)
flagged = sum(1 for r in res if "pos_x" in r["rejected"])
check("smooth fast motion NOT rejected", flagged == 0, f"{flagged} rejections")

with_jump = [0.0 + 5.0 * k for k in range(10)]
with_jump[8] += 200.0                                     # single teleport
res2 = run(with_jump)
caught = "pos_x" in res2[8]["rejected"]
others = sum(1 for k, r in enumerate(res2) if k != 8 and "pos_x" in r["rejected"])
check("injected 200 px teleport IS rejected", caught)
check("no other frame rejected", others == 0, f"{others} extra")

# --- 6. does the band widen while coasting? --------------------------------
print("\n--- 6. does sigma widen with the coast horizon? ---")
g = BP.BlockPredictor()
for k in range(10):
    g.update({"position": (5.0 * k, 0.0), "scale": 60.0,
              "quaternion": (1.0, 0.0, 0.0, 0.0), "arcs": (0.9,) * 4})
sig = []
for k in range(3):
    r = g.update({"position": (5.0 * (10 + k) + 300.0, 0.0), "scale": 60.0,
                  "quaternion": (1.0, 0.0, 0.0, 0.0), "arcs": (0.9,) * 4})
    d = r["debug"].get("pos_x")
    if d:
        sig.append((d["h"], d["sigma"]))
check("sigma increases as the coast horizon grows",
      len(sig) >= 2 and sig[1][1] > sig[0][1],
      "  ".join(f"h={h} sigma={s:.2f}" for h, s in sig))

print("\n" + "=" * 78)
print("ALL CHECKS PASSED" if ok else "FAILURES ABOVE")
print("=" * 78)
sys.exit(0 if ok else 1)
