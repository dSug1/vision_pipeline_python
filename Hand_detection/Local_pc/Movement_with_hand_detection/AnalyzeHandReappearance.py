"""REAPPEARANCE detector -- targets the exact jump_test4 pattern.

The SWAP detector in AnalyzeHandIdentity.py requires BOTH labels present in BOTH
consecutive frames. But the recorded Object Jump Correction event (§14.1.4) went
THROUGH a period where one hand was undetected: 'Left' was absent for frames
100-107, then reappeared exactly where 'Right' had been. The swap detector is
structurally blind to precisely that case.

This detector: when a label disappears and later reappears, compare where it
reappears against (a) where it was last seen, (b) where the OTHER hand was last
seen. Reappearing much closer to the other hand is the mixup signature.
"""
import glob, json, os, time
import numpy as np

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
PALM = [0, 5, 9, 13, 17]

def _retry(fn, n=5, d=1.5):
    last = None
    for i in range(n):
        try: return fn()
        except OSError as e:
            last = e
            if i < n-1: time.sleep(d)
    raise last

def cen(h): return np.asarray([h["landmarks"][i] for i in PALM], float).mean(axis=0)

for dpath in sorted(glob.glob(os.path.join(ROOT, "*"))):
    if not _retry(lambda p=dpath: os.path.isfile(os.path.join(p, "meta.json"))): continue
    meta = _retry(lambda p=dpath: json.load(open(os.path.join(p,"meta.json"), encoding="utf-8")))
    frames = _retry(lambda p=dpath: [json.loads(l) for l in open(os.path.join(p,"raw_landmarks.jsonl"), encoding="utf-8")])
    pos = [{h["handedness"]: cen(h) for h in fr["hands"]} for fr in frames]

    last_seen = {}          # label -> (frame, centroid)
    events = []
    for k, p in enumerate(pos):
        for lab in ("Left", "Right"):
            other = "Right" if lab == "Left" else "Left"
            if lab in p:
                prev = last_seen.get(lab)
                if prev and k - prev[0] > 1:            # reappeared after a gap
                    gap = k - prev[0]
                    d_own = float(np.linalg.norm(p[lab] - prev[1]))
                    o = last_seen.get(other)
                    d_other = float(np.linalg.norm(p[lab] - o[1])) if o else None
                    events.append((k, lab, gap, d_own, d_other))
                last_seen[lab] = (k, p[lab])

    susp = [e for e in events if e[4] is not None and e[4] < e[3] * 0.5 and e[3] > 60]
    print(f"{meta['sequence']:<22} reappearances={len(events):>3}   suspicious={len(susp):>2}")
    for k, lab, gap, d_own, d_other in susp[:8]:
        print(f"{'':24} frame {k:>4} {lab:<5} gap={gap:>3}f  "
              f"from-own-last={d_own:6.1f}px  from-OTHER-last={d_other:6.1f}px  <-- MIXUP")
    if events and not susp:
        worst = max(events, key=lambda e: e[3])
        print(f"{'':24} (largest clean reappearance: frame {worst[0]}, {worst[1]}, "
              f"gap={worst[2]}f, moved {worst[3]:.1f}px)")
