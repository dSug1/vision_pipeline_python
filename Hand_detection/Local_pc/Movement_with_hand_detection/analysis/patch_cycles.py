"""Patch the ACTUAL cycle count into a recorded session's meta.json.

The recorder writes the PRESCRIBED count; the operator may perform a different
number. Actual always wins. Usage:

    python patch_cycles.py <session_name_fragment> <cycles> [hands]
"""
import glob
import json
import os
import sys

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

frag = sys.argv[1]
# Half-cycles are real: a take can end mid-turn (e.g. "15 and a half"), and a half
# cycle is still ONE genuine sign change, so the count must not be rounded to int.
cycles = float(sys.argv[2])
cycles = int(cycles) if cycles.is_integer() else cycles
hands = sys.argv[3] if len(sys.argv) > 3 else "both"

matches = sorted(glob.glob(os.path.join(ROOT, f"*{frag}*")))
if len(matches) != 1:
    raise SystemExit(f"need exactly one match for {frag!r}, got {matches}")

p = os.path.join(matches[0], "meta.json")
with open(p, encoding="utf-8") as f:
    m = json.load(f)

prescribed = m.get("counted_crossing_cycles")
expected = 2 * cycles
expected = int(expected) if float(expected).is_integer() else expected
m["counted_crossing_cycles"] = cycles
m["expected_sign_changes"] = expected
m["cycles_source"] = "operator-reported ACTUAL count (overrides the prescribed default)"
m["prescribed_cycles"] = prescribed
m["hands_used"] = hands
if hands == "both":
    m["expected_sign_changes_note"] = (
        "BOTH hands performed the motion simultaneously, so expected_sign_changes "
        "applies PER HAND -- compare the analyser's per-hand flip count against it, "
        "not the sum across hands."
    )

with open(p, "w", encoding="utf-8") as f:
    json.dump(m, f, indent=2)

print(f"{os.path.basename(matches[0])}: prescribed={prescribed} -> actual={cycles} "
      f"({2 * cycles} expected sign changes per hand, hands={hands})")
