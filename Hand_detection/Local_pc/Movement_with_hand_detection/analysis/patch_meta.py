import json

p = (r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer"
     r"\sessions\2026-08-02_221948_palm_back\meta.json")

with open(p, encoding="utf-8") as f:
    m = json.load(f)

# OPERATOR'S UNIT: one "crossing" = palm -> back -> palm, i.e. a full CYCLE.
# That is TWO sign changes, so the metric the analyser counts (per-frame sign
# inversions) must be compared against 58, not 29. Recorded explicitly because
# this exact ambiguity produced a wrong reading once already (2026-08-02).
m["counted_crossing_cycles"] = 29
m["expected_sign_changes"] = 58
m["counted_crossings_definition"] = (
    "Operator counted CYCLES: one count = palm -> back -> palm. Each cycle is TWO "
    "sign changes, so expected_sign_changes = 29 * 2 = 58. The clip ends with the "
    "hand edge-on mid-turn; that trailing incomplete transition was NOT counted, so "
    "58 is a lower bound and the true figure may be 59."
)
m["counted_crossings_note"] = (
    "Several cycles were performed at HIGH SPEED (operator report). At the measured "
    "15.77 fps (63.4 ms/frame) a fast crossing can legitimately traverse the whole "
    "edge-on band between two consecutive frames, so high-edge-on flips are NOT "
    "automatically spurious in this take."
)
m["ground_truth_for"] = (
    "N3 / M0 chirality-flip-rate. Measured on this take: 52 flips (Left), 50 (Right) "
    "against 58 expected -- i.e. UNDER-detection of 6-8 per hand, not an excess. "
    "Totals alone cannot rule out a compensating mix of missed genuine crossings plus "
    "spurious flips; that needs per-flip matching against the rotation timeline."
)
m["frame_rate_caveat"] = (
    "Measured 15.77 fps vs 24.09-24.14 fps on the seven earlier sequences recorded the "
    "same day with the same recorder (19:13-20:51 vs 22:19). Suspected webcam "
    "auto-exposure lengthening frames in dimmer light. This take is therefore NOT "
    "frame-rate-comparable to those, and the wider 63.4 ms interval is precisely the "
    "confound for the high-edge-on question. See queue item N7/N10."
)

with open(p, "w", encoding="utf-8") as f:
    json.dump(m, f, indent=2)

print("patched:", p)
print("cycles =", m["counted_crossing_cycles"],
      "-> expected sign changes =", m["expected_sign_changes"])
print("measured_fps =", m["measured_fps"], "| frames =", m["frames"])
