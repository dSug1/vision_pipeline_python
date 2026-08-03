"""ATTEMPT 5: gated KF -- passthrough above an observability threshold, anisotropic
KF only inside the degenerate band.

Hypothesis: attempts 1-4 lost because a KF damps on EVERY frame. Above the gate,
this one is byte-identical to a passthrough (zero lag). Inside the band it does
something the shipped filter cannot: the shipped alpha->0 freezes ALL axes onto
pure prediction, while the anisotropic update keeps tracking the well-observed axis
and coasts only on the degenerate ones.

Same two-sided rule as before -- must beat the shipped filter on the tail WITHOUT
losing tracking fidelity.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from m6_ukf_ab import run

b = run("iso")
print(f"{'config':52s} {'>30':>5s} {'>60':>5s} {'p99':>7s} {'max':>7s} "
      f"{'trk_w':>7s} {'trk_f':>7s}")
print("-" * 96)
print(f"{'SHIPPED isotropic':52s} {b['j30']:5d} {b['j60']:5d} {b['p99']:7.2f} "
      f"{b['mx']:7.2f} {b['tw']:6.3f}° {b['tf']:6.3f}°   <- baseline")
print()

wins = []
for gate in (0.75, 0.60, 0.45, 0.30):
    for sb in (0.6, 1.0, 2.0):
        for q in (0.02, 0.08):
            r = run("ukf", sigma_long=0.05, sigma_base=sb,
                    process_noise=q, passthrough_obs=gate)
            tail_better = r['j60'] < b['j60'] and r['p99'] < b['p99'] and r['mx'] < b['mx']
            track_ok = r['tw'] <= b['tw'] * 1.25 and r['tf'] <= b['tf'] * 1.25
            v = ""
            if tail_better and track_ok:
                v = "  <== WINS BOTH"
                wins.append(((gate, sb, q), r))
            elif tail_better:
                v = "  tail better, tracking worse"
            elif track_ok:
                v = "  tracks fine, tail no better"
            tag = f"GATED gate={gate} s_base={sb} Q={q}"
            print(f"{tag:52s} {r['j30']:5d} {r['j60']:5d} {r['p99']:7.2f} {r['mx']:7.2f} "
                  f"{r['tw']:6.3f}° {r['tf']:6.3f}°{v}")

print()
if wins:
    print(f"*** {len(wins)} config(s) BEAT THE SHIPPED FILTER ON BOTH ***")
    for (g, sb, q), r in sorted(wins, key=lambda x: (x[1]['j60'], x[1]['mx'])):
        print(f"   gate={g} s_base={sb} Q={q}")
        print(f"      >60   {r['j60']:5d}   (baseline {b['j60']})")
        print(f"      p99   {r['p99']:7.2f} (baseline {b['p99']:.2f})")
        print(f"      max   {r['mx']:7.2f} (baseline {b['mx']:.2f})")
        print(f"      track {r['tw']:.3f}/{r['tf']:.3f} (baseline {b['tw']:.3f}/{b['tf']:.3f})")
else:
    print("Attempt 5 also fails. Five attempts -- stop and record.")
