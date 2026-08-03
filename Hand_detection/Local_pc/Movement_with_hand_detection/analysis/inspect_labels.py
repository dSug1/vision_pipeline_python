import glob, json, os, collections

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

for seq in ("known_right_palm", "known_right_back", "known_left_palm", "known_left_back"):
    for d in sorted(glob.glob(os.path.join(ROOT, f"*_{seq}"))):
        labels = collections.Counter()
        scores = []
        thumb_side = collections.Counter()
        for line in open(os.path.join(d, "raw_landmarks.jsonl"), encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            for h in (json.loads(line).get("hands") or []):
                labels[h["handedness"]] += 1
                scores.append(h["score"])
                lm = h["landmarks"]
                # thumb tip (4) vs pinky MCP (17) in IMAGE x. Tells us which side
                # of the hand the thumb appears on, in the recorded (mirrored) frame.
                thumb_side["thumb_left_of_pinky" if lm[4][0] < lm[17][0]
                            else "thumb_right_of_pinky"] += 1
        print(f"{seq:22s} labels={dict(labels)}  "
              f"mean_score={sum(scores)/len(scores):.3f}  {dict(thumb_side)}")
