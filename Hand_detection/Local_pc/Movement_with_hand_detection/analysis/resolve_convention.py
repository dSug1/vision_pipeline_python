"""Decide the handedness-label convention from data, not from reasoning.

In a MIRRORED (selfie) preview the operator's physical RIGHT hand necessarily
appears on the RIGHT of the image -- that is the mirror property, and it is not
open to interpretation. So for every frame containing exactly two hands with
distinct labels, ask: does MediaPipe's 'Right' label sit on the larger-x hand?

  'Right' on larger x  -> label == physical hand (in this mirrored convention)
  'Right' on smaller x -> label is the MIRROR of the physical hand
"""
import collections
import glob
import json
import os

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
PALM = (0, 5, 9, 13, 17)

totals = collections.Counter()

for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    name = os.path.basename(d)
    per = collections.Counter()
    path = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        continue
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        hands = json.loads(line).get("hands") or []
        if len(hands) != 2:
            continue
        if {h["handedness"] for h in hands} != {"Left", "Right"}:
            continue          # duplicate labels tell us nothing here
        cx = {h["handedness"]: sum(h["landmarks"][i][0] for i in PALM) / len(PALM)
              for h in hands}
        if cx["Right"] > cx["Left"]:
            per["Right_on_image_right"] += 1
        else:
            per["Right_on_image_left"] += 1
    if per:
        totals.update(per)
        rr = per["Right_on_image_right"]
        rl = per["Right_on_image_left"]
        n = rr + rl
        print(f"{name:44s} Right-on-image-right {rr:5d}/{n:5d}  ({100*rr/n:5.1f}%)")

print("-" * 78)
rr, rl = totals["Right_on_image_right"], totals["Right_on_image_left"]
n = rr + rl
print(f"TOTAL: 'Right' label on the image-RIGHT hand: {rr}/{n} ({100*rr/n:.1f}%)")
print()
if rr > rl:
    print("=> MediaPipe's label MATCHES the physical hand in this mirrored convention.")
    print("   So a clip of the physical RIGHT hand should carry the label 'Right'.")
else:
    print("=> MediaPipe's label is the MIRROR of the physical hand in this convention.")
    print("   So a clip of the physical RIGHT hand carries the label 'Left'.")
