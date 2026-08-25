"""N11: is the Left/Right sign-cue asymmetry real, on CLEAN single-hand takes?

The four palm_back_s* takes used BOTH hands at once, which injects duplicate-label
frames and contaminates per-hand streams. These two takes use one hand each.

NOTE ON LABELS: the recorded handedness is the MIRRORED/apparent hand (spec §0.9),
so a physical RIGHT hand is labelled "Left". This script therefore does NOT filter
by label at all -- each take contains exactly one hand, so we take whatever is
there and trust meta["hands_used"] for which physical hand it was.
"""
import glob
import json
import os
import sys

sys.path.insert(0, r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
                   r"\Hand_detection\Local_pc\Movement_with_hand_detection")

# ⚠ AnalyzePerceptionSequences.py MOVED 2026-08-25 to tools/ -- it is not run by the debug tool
# or by production, so it no longer sits in the app root. Kept re-runnable:
# a harness that cannot be re-run is an assertion, not a finding.
_MOVED_2026_08_25 = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
sys.path.insert(0, _MOVED_2026_08_25)

from AnalyzePerceptionSequences import edge_on

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
IMPLAUSIBLE_ABOVE = 0.60

TAKES = ["2026-08-03_171314_palm_back_s2_slow",   # physical RIGHT
         "2026-08-03_171417_palm_back_s2_slow"]   # physical LEFT

print(f"{'physical hand':>14s} {'fps':>6s} {'ms/frame':>9s} {'s/cyc':>6s} "
      f"{'exp':>4s} {'got':>4s} {'delta':>6s} {'implaus':>8s} {'implaus%':>9s} {'dup':>4s}")
print("-" * 88)

for name in TAKES:
    d = os.path.join(ROOT, name)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    frames = [json.loads(l) for l in open(os.path.join(d, "raw_landmarks.jsonl"),
                                          encoding="utf-8") if l.strip()]

    hand = meta.get("hands_used", "?")
    expected = meta.get("expected_sign_changes")
    cycles = meta.get("counted_crossing_cycles")
    fps = meta["measured_fps"]
    span = meta["actual_span_s"]

    # single-hand take: take whatever hand is present, ignore the label entirely
    idxs, eos, signs = [], [], []
    dup = 0
    for i, rec in enumerate(frames):
        hands = rec.get("hands") or []
        if len(hands) > 1:
            dup += 1
            continue                      # ambiguous frame, skip rather than guess
        if not hands:
            continue
        s, eo = edge_on(hands[0]["landmarks"])
        idxs.append(i)
        eos.append(eo)
        signs.append(1 if s > 0 else -1)

    flips = []
    for k in range(1, len(signs)):
        if idxs[k] != idxs[k - 1] + 1:
            continue
        if signs[k] != signs[k - 1]:
            flips.append(min(eos[k], eos[k - 1]))

    implaus = [f for f in flips if f > IMPLAUSIBLE_ABOVE]
    pct = 100.0 * len(implaus) / len(flips) if flips else 0.0
    print(f"{hand:>14s} {fps:6.2f} {1000.0/fps:9.1f} {span/cycles:6.2f} "
          f"{expected:4} {len(flips):4} {len(flips)-expected:+6} "
          f"{len(implaus):8} {pct:8.0f}% {dup:4}")

print("-" * 88)
print(f"implausible = both straddling frames at edge-on > {IMPLAUSIBLE_ABOVE}")
print("dup = frames with >1 hand detected in a single-hand take (skipped)")
print()
print("Prior TWO-HAND result for the same sequence (spec §0.8, 2.14 s/cycle):")
print("    Left 7% implausible   |   Right 23% implausible")
