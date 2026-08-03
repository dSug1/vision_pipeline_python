"""DR-2 replay A/B (queue item 2.2), under the A10 kill-criterion.

Measures what the GESTURE LAYER sees: how many times `thumb_outward` changes
value, with and without DR-2's freeze, on identical recorded input.

The palm_back_s* takes carry operator ground truth (expected_sign_changes), so
"better" is not a matter of taste: DR-2 should move the observed count TOWARD
ground truth by absorbing chatter, without erasing genuine crossings.

The control sequences (static_hold, non_crossing, two_hand_near_miss) must show
DR-2 doing NOTHING -- it should be inert when the hand never goes edge-on.
"""
import glob
import json
import os
import sys

BASE = (r"c:\Users\sugit\Documents\_scripts_persos\_Persos\vision_pipeline_python"
        r"\Hand_detection\Local_pc\Movement_with_hand_detection")
sys.path.insert(0, BASE)

from Resources import palm_geometry

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# TRUE chirality controls: the palm never turns over, so DR-2 must never fire.
# NOTE: two_hand_near_miss is NOT one of these -- it is the IDENTITY control from
# §0.4 (near-miss vs overlap), and 9.7-12% of its frames sit below edge-on 0.15
# because hands naturally turn edge-on as they pass. Listing it here was an error
# in the first run of this A/B.
CONTROLS = ("static_hold", "non_crossing")

rows = []
for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
    p = os.path.join(d, "raw_landmarks.jsonl")
    if not os.path.exists(p):
        continue
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    seq = meta["sequence"]
    expected = meta.get("expected_sign_changes")

    frames = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

    for label in ("Left", "Right"):
        tracker = palm_geometry.PalmFacingTracker()
        raw_prev = dr2_prev = None
        raw_changes = dr2_changes = 0
        n = 0
        for rec in frames:
            hand = next((h for h in (rec.get("hands") or [])
                         if h["handedness"] == label), None)
            if hand is None:
                continue
            lm = hand["landmarks"]
            n += 1

            raw = palm_geometry.is_thumb_outward(lm, label)
            if raw_prev is not None and raw != raw_prev:
                raw_changes += 1
            raw_prev = raw

            dr2, _valid = tracker.update(lm, label)
            if dr2_prev is not None and dr2 != dr2_prev:
                dr2_changes += 1
            dr2_prev = dr2

        if n < 30:
            continue
        rows.append((os.path.basename(d), seq, label, n, expected,
                     raw_changes, dr2_changes, tracker.band_entries,
                     tracker.frames_frozen, tracker.chatter_suppressed))

print(f"{'sequence':28s} {'hand':>5s} {'n':>5s} {'exp':>5s} {'raw':>5s} {'DR2':>5s} "
      f"{'d|raw-e|':>9s} {'d|dr2-e|':>9s} {'bands':>6s} {'frozen':>7s} {'chatter':>8s}")
print("-" * 106)

improved = worsened = unchanged = 0
ctrl_touched = 0

for name, seq, label, n, exp, raw_c, dr2_c, bands, frozen, chatter in rows:
    if exp is not None:
        d_raw = abs(raw_c - exp)
        d_dr2 = abs(dr2_c - exp)
        if d_dr2 < d_raw:
            improved += 1
        elif d_dr2 > d_raw:
            worsened += 1
        else:
            unchanged += 1
        draw_s, ddr2_s = f"{d_raw}", f"{d_dr2}"
    else:
        draw_s = ddr2_s = "-"

    if any(c in seq for c in CONTROLS) and (bands or frozen):
        ctrl_touched += 1

    print(f"{seq:28s} {label:>5s} {n:5d} {str(exp):>5s} {raw_c:5d} {dr2_c:5d} "
          f"{draw_s:>9s} {ddr2_s:>9s} {bands:6d} {frozen:7d} {chatter:8d}")

print("-" * 106)
print(f"ground-truth takes: improved {improved} | worsened {worsened} | unchanged {unchanged}")
print(f"control sequences where DR-2 did ANYTHING (must be 0): {ctrl_touched}")
