"""Detect MediaPipe hand-identity mixups (Object Jump Correction, §14.1.4).

The recorded failure: for a few frames, ALL landmarks of a labelled hand move
together to a different on-screen location -- MediaPipe assigning a handedness
label to the wrong physical hand -- at high confidence, self-correcting later.

Two independent detectors:
  TELEPORT -- a single label's palm centroid moves more than JUMP_PX in one
              frame. Coherent whole-hand motion, not landmark noise.
  SWAP     -- the direct identity test: "Left" lands closer to where "Right"
              was than to where "Left" was (and/or vice versa). This is the
              signature that cannot be explained by fast motion.

Run over the two_hand_* sequences to test the occlusion hypothesis:
  overlap   -> hands genuinely occlude
  near_miss -> hands approach but never overlap  (CONTROL)
If mixups appear in BOTH, occlusion is not the mechanism and the cause is
proximity/association alone -- a materially different fix.
"""
import glob, json, os, time
import numpy as np

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
PALM = [0, 5, 9, 13, 17]
JUMP_PX = 100.0


def _retry(fn, n=5, d=1.5):
    last = None
    for i in range(n):
        try:
            return fn()
        except OSError as e:
            last = e
            if i < n - 1:
                time.sleep(d)
    raise last


def load(d):
    def _r():
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        frames = [json.loads(l) for l in open(os.path.join(d, "raw_landmarks.jsonl"), encoding="utf-8")]
        return meta, frames
    return _retry(_r)


def centroid(h):
    return np.asarray([h["landmarks"][i] for i in PALM], float).mean(axis=0)


def analyse(d):
    meta, frames = load(d)
    seq = meta["sequence"]
    dur_min = meta["actual_span_s"] / 60.0

    pos = []  # per frame: {label: centroid}
    for fr in frames:
        pos.append({h["handedness"]: centroid(h) for h in fr["hands"]})

    teleports, swaps, both_frames = [], [], 0
    for k in range(1, len(pos)):
        a, b = pos[k - 1], pos[k]
        if len(b) == 2:
            both_frames += 1
        for lab in ("Left", "Right"):
            if lab in a and lab in b:
                dist = float(np.linalg.norm(b[lab] - a[lab]))
                if dist > JUMP_PX:
                    teleports.append((k, lab, dist))
        # SWAP: both labels present in both frames, and each landed nearer the
        # OTHER label's previous position than its own
        if len(a) == 2 and len(b) == 2:
            dLL = np.linalg.norm(b["Left"] - a["Left"])
            dLR = np.linalg.norm(b["Left"] - a["Right"])
            dRR = np.linalg.norm(b["Right"] - a["Right"])
            dRL = np.linalg.norm(b["Right"] - a["Left"])
            if dLR < dLL and dRL < dRR:
                swaps.append((k, float(dLL), float(dLR)))

    one_hand = sum(1 for p in pos if len(p) == 1)
    print(f"{seq:<22} frames={len(frames):>4}  {meta['actual_span_s']:>5.1f}s   "
          f"both-hands={both_frames:>4}  one-hand={one_hand:>4}")
    print(f"{'':22} TELEPORTS >100px : {len(teleports):>3}  ({len(teleports)/dur_min:5.1f}/min)")
    for k, lab, dist in teleports[:6]:
        print(f"{'':26} frame {k:>4} {lab:<5} {dist:7.1f}px")
    print(f"{'':22} IDENTITY SWAPS   : {len(swaps):>3}  ({len(swaps)/dur_min:5.1f}/min)")
    for k, dll, dlr in swaps[:6]:
        print(f"{'':26} frame {k:>4}  own={dll:6.1f}px  other={dlr:6.1f}px")
    print()
    return seq, len(teleports), len(swaps), dur_min, one_hand, len(frames)


rows = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    if _retry(lambda d=d: os.path.isfile(os.path.join(d, "meta.json"))):
        rows.append(analyse(d))

print("=" * 78)
print("OCCLUSION HYPOTHESIS — overlap vs. near-miss control")
print("=" * 78)
print(f"{'sequence':<22} {'teleports/min':>14} {'swaps/min':>10} {'one-hand frames':>17}")
for seq, t, s, dm, oh, nf in rows:
    if seq.startswith("two_hand"):
        print(f"{seq:<22} {t/dm:>14.1f} {s/dm:>10.1f} {oh:>10} / {nf}")
