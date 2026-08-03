"""Append an operator observation to a recorded session's meta.json.

Usage: python patch_note.py <session_name_fragment> "<observation>"
"""
import glob
import json
import os
import sys

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

frag, obs = sys.argv[1], sys.argv[2]
matches = sorted(glob.glob(os.path.join(ROOT, f"*{frag}*")))
if len(matches) != 1:
    raise SystemExit(f"need exactly one match for {frag!r}, got {[os.path.basename(m) for m in matches]}")

p = os.path.join(matches[0], "meta.json")
with open(p, encoding="utf-8") as f:
    m = json.load(f)

existing = m.get("operator_observations", [])
existing.append(obs)
m["operator_observations"] = existing

with open(p, "w", encoding="utf-8") as f:
    json.dump(m, f, indent=2)

print(f"{os.path.basename(matches[0])}: +observation -> {obs}")
