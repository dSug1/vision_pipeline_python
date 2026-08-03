"""Can the propagated filter track as tightly as the baseline AND keep the tail?

The baseline hits 1.404 deg tracking by effectively NOT filtering when
well-conditioned (alpha saturates at 1, so fused == raw). So the well-observed axis
needs a very SMALL sigma_long for the gain there to approach 1, while the degenerate
axes keep their large sigma_base. That corner (s_long < 0.2) was never swept.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from m6_ukf_ab import run

b = run("iso")
print(f"{'config':46s} {'>30':>5s} {'>60':>5s} {'p99':>7s} {'max':>7s} "
      f"{'trk_w':>7s} {'trk_f':>7s}")
print("-" * 90)
print(f"{'SHIPPED isotropic':46s} {b['j30']:5d} {b['j60']:5d} {b['p99']:7.2f} "
      f"{b['mx']:7.2f} {b['tw']:6.3f}° {b['tf']:6.3f}°   <- baseline")
print()

wins = []
for sl in (0.02, 0.05, 0.10, 0.15):
    for sb in (0.6, 1.0, 2.0):
        for q in (0.02, 0.08, 0.30):
            r = run("ukf", sigma_long=sl, sigma_base=sb, process_noise=q)
            tail_better = r['j60'] < b['j60'] and r['p99'] < b['p99'] and r['mx'] < b['mx']
            track_ok = r['tw'] <= b['tw'] * 1.25 and r['tf'] <= b['tf'] * 1.25
            v = ""
            if tail_better and track_ok:
                v = "  <== WINS BOTH"
                wins.append(((sl, sb, q), r))
            elif tail_better and r['tw'] <= b['tw'] * 2.0:
                v = "  close (tracking < 2x baseline)"
            tag = f"UKF s_long={sl} s_base={sb} Q={q}"
            print(f"{tag:46s} {r['j30']:5d} {r['j60']:5d} {r['p99']:7.2f} {r['mx']:7.2f} "
                  f"{r['tw']:6.3f}° {r['tf']:6.3f}°{v}")

print()
if wins:
    print(f"{len(wins)} config(s) WIN BOTH:")
    for (sl, sb, q), r in sorted(wins, key=lambda x: (x[1]['j60'], x[1]['mx'])):
        print(f"   s_long={sl} s_base={sb} Q={q}")
        print(f"      >60  {r['j60']:4d}  (baseline {b['j60']})")
        print(f"      max  {r['mx']:6.1f}  (baseline {b['mx']:.1f})")
        print(f"      p99  {r['p99']:6.1f}  (baseline {b['p99']:.1f})")
        print(f"      track {r['tw']:.3f}/{r['tf']:.3f}  (baseline {b['tw']:.3f}/{b['tf']:.3f})")
else:
    print("Still no config wins both.")
