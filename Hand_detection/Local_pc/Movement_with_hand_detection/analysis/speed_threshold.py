"""Speed-threshold table for the palm_back_s* sweep.

Compares DETECTED sign flips against the operator-counted ground truth in each
session's meta.json, and separately counts flips that are PHYSICALLY IMPLAUSIBLE
as genuine crossings.

The implausibility test: a flip is reported at min(edge_on[k], edge_on[k-1]) -- so
a flip "at 0.95" means BOTH straddling frames were strongly oriented. For the sign
to change, the hand must pass through edge-on (s=0). Both sides sitting at |s|>0.6
means it crossed and re-emerged within one frame interval (~41 ms here), which is
beyond plausible hand-rotation speed. Those are candidate SPURIOUS flips.
"""
import glob
import json
import math
import os
import sys

sys.path.insert(0, r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
                   r"\Hand_detection\Local_pc\Movement_with_hand_detection")

import numpy as np
from AnalyzePerceptionSequences import edge_on  # reuse the SAME edge-on definition

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
IMPLAUSIBLE_ABOVE = 0.60

SEQS = ["palm_back_s1_very_slow", "palm_back_s2_slow",
        "palm_back_s3_medium", "palm_back_s4_fast"]

print(f"{'sequence':24s} {'s/cycle':>8s} {'hand':>6s} {'exp':>5s} {'got':>5s} "
      f"{'delta':>6s} {'implaus':>8s} {'implaus%':>9s}")
print("-" * 82)

rows = []
for seq in SEQS:
    dirs = sorted(glob.glob(os.path.join(ROOT, f"*_{seq}")))
    if not dirs:
        continue
    d = dirs[-1]
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    expected = meta.get("expected_sign_changes")
    cycles = meta.get("counted_crossing_cycles")
    span = meta["actual_span_s"]
    s_per_cycle = span / cycles if cycles else float("nan")

    frames = []
    for line in open(os.path.join(d, "raw_landmarks.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line:
            frames.append(json.loads(line))

    # Duplicate labels are a real raw-MediaPipe failure (spec §0.4) and these takes
    # are pre-DR-1 raw capture, so count them -- they distort any per-hand stream.
    dup_frames = sum(
        1 for rec in frames
        if len({id(h) for h in (rec.get("hands") or [])}) > 1
        and len({h["handedness"] for h in (rec.get("hands") or [])}) == 1
        and len(rec.get("hands") or []) > 1
    )

    for hand in ("Left", "Right"):
        idxs, eos, signs = [], [], []
        for i, rec in enumerate(frames):
            for h in (rec.get("hands") or []):
                if h["handedness"] != hand:
                    continue
                s, eo = edge_on(h["landmarks"])
                idxs.append(i)
                eos.append(eo)
                signs.append(1 if s > 0 else -1)
                break   # ONE entry per frame, matching AnalyzePerceptionSequences'
                        # per_hand_stream(); without this, duplicate-label frames
                        # create same-index entries that the consecutive-frame
                        # check below silently drops, undercounting flips.
        if len(signs) < 2:
            continue

        flips = []
        for k in range(1, len(signs)):
            if idxs[k] != idxs[k - 1] + 1:
                continue
            if signs[k] != signs[k - 1]:
                flips.append(min(eos[k], eos[k - 1]))

        implaus = [f for f in flips if f > IMPLAUSIBLE_ABOVE]
        delta = len(flips) - expected
        pct = 100.0 * len(implaus) / len(flips) if flips else 0.0
        print(f"{seq:24s} {s_per_cycle:8.2f} {hand:>6s} {expected:5} {len(flips):5} "
              f"{delta:+6} {len(implaus):8} {pct:8.0f}%   dup_frames={dup_frames}")
        rows.append((seq, s_per_cycle, hand, expected, len(flips), len(implaus)))

print("-" * 82)
print(f"implausible = flip with BOTH straddling frames at edge-on > {IMPLAUSIBLE_ABOVE}")
print("            = the hand would have crossed and re-emerged within ~41 ms")
