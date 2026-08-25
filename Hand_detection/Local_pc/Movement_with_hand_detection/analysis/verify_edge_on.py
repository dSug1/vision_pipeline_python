"""Item 1.2 verification: the new production edge_on_measure must agree EXACTLY
with AnalyzePerceptionSequences.edge_on() on real recorded data.

This matters because EDGE_ON_THRESHOLD = 0.15 was settled by measurement in the
analyser's scale (spec §0.3). A different normalisation in production would
silently invalidate it.
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

# ⚠ AnalyzePerceptionSequences.py MOVED 2026-08-25 to tools/ -- it is not run by the debug tool
# or by production, so it no longer sits in the app root. Kept re-runnable:
# a harness that cannot be re-run is an assertion, not a finding.
_MOVED_2026_08_25 = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
sys.path.insert(0, _MOVED_2026_08_25)

from AnalyzePerceptionSequences import edge_on as analyser_edge_on
from Resources import palm_geometry

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

all_lms = []
sessions = 0
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    sessions += 1
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        for h in (json.loads(line).get("hands") or []):
            all_lms.append(h["landmarks"])

print(f"sessions: {sessions}   hand-frames: {len(all_lms)}")

worst, n = palm_geometry.verify_matches_analyser(all_lms, analyser_edge_on)
print(f"[PASS] edge_on_measure matches the analyser on {n} frames "
      f"(max abs diff {worst:g})")

# Distribution sanity: how much of the real corpus sits below the DR-2 gate?
below = sum(1 for lm in all_lms if palm_geometry.is_edge_on(lm))
print(f"frames below EDGE_ON_THRESHOLD={palm_geometry.EDGE_ON_THRESHOLD}: "
      f"{below}/{len(all_lms)} ({100.0*below/len(all_lms):.2f}%)")
print("  (spec §0.3 predicted this band is never entered in NORMAL motion and only")
print("   during deliberate crossings -- a small non-zero % across a corpus that is")
print("   mostly deliberate pitch sweeps is the expected shape.)")
