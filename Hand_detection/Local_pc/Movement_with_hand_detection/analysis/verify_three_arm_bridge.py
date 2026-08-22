"""The three-arm live comparison actually compares three things (queue D2/D3).

⚠⚠ WHY THIS EXISTS. A multi-arm debug tool fails in a way that LOOKS like a
result: if the arms share state, every panel shows the same thing and the owner
concludes "no difference". B4 paid for this lesson twice -- a leaked loop
variable made seven takes print IDENTICAL rows (`HANDOFF_ANCHOR_ROTATION.md` §5,
trap 2), and `--arms 6` once left a whole row computing all-None because a guard
was not widened with it. So before the owner is asked to look at three windows,
the three windows are proven to be three arms.

It drives `LiveSnapDebug.update_hands` directly with synthetic hand data -- no
camera, no detector -- and asserts:

  1. the arms are INDEPENDENT (separate cubes, trackers and counters);
  2. on a short dropout they DIVERGE the way the design says: OFF releases, ON
     and BLEND hold;
  3. ON and BLEND differ from each other only on the RESUME frame, where BLEND
     moves the cube a fraction of the distance ON moves it in one step;
  4. all three are driven by ONE `hand_data_by_hand`, so nothing but the Phase D
     configuration can differ between them.

    .venv/Scripts/python.exe analysis/verify_three_arm_bridge.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import LiveSnapDebug as L  # noqa: E402  (imports cv2/mediapipe; no camera opened)

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


W, H = 640, 480


def hand_at(cx, cy):
    """Synthetic right hand whose palm centre sits at (cx, cy). Only the geometry
    `update_hands` consumes matters; the world landmarks just need to be a
    non-degenerate palm so the rotation path does not bail."""
    px = [(cx + 6.0 * (i % 7) - 18.0, cy + 5.0 * (i // 7) - 10.0) for i in range(21)]
    wl = [(0.01 * (i % 7) - 0.03, 0.01 * (i // 7) - 0.01, 0.002 * (i % 5)) for i in range(21)]
    return {"pixel_landmarks": px, "world_landmarks": wl, "thumb_outward": False}


def frame(arms, hand, t_ms):
    L.update_hands_all(arms, {"Left": None, "Right": hand}, now_ms=t_ms,
                       rotation=L.PRODUCTION_ROTATION)


arms = [L._make_arm(m, W, H) for m in L.BRIDGE_MODES]
by = {a.arm_label: a for a in arms}

print("=" * 78)
print("THREE-ARM D2/D3 COMPARISON -- the panels are genuinely three arms")
print("=" * 78)

print("\n1. INDEPENDENCE -- no shared state between arms")
check("three arms", len(arms) == 3, ",".join(a.arm_label for a in arms))
check("separate cube dicts", len({id(a.cubes) for a in arms}) == 3)
check("separate tracking-state dicts", len({id(a.hand_state_trackers) for a in arms}) == 3)
check("separate blend counters", len({id(a.resync_blend_left) for a in arms}) == 3)
check("separate stat counters", len({id(a.stats) for a in arms}) == 3)
check("OFF really has a 0 ms window", by["off"].bridge_window_ms == 0.0)
check("ON and BLEND share the shipped window",
      by["on"].bridge_window_ms == by["blend"].bridge_window_ms == L.hand_state.BRIDGE_WINDOW_MS)
check("only BLEND blends",
      (by["off"].resync_blend_frames, by["on"].resync_blend_frames) == (0, 0)
      and by["blend"].resync_blend_frames > 0)

print("\n2. GRAB, then a SHORT dropout -- OFF drops it, ON and BLEND do not")
cx, cy = W / 2, H / 2                      # the cubes start centred
t = 0.0
for _ in range(6):                          # settle and snap
    frame(arms, hand_at(cx, cy), t)
    t += 42.0
held = {a.arm_label: a.cube_owned_by("Right") for a in arms}
check("all three arms grabbed the same cube", len(set(held.values())) == 1 and held["off"],
      str(held))
frame(arms, None, t)                        # ONE missed frame
t += 42.0
after = {a.arm_label: a.cube_owned_by("Right") for a in arms}
check("⭐ OFF released on the first missed frame", after["off"] is None)
check("⭐ ON held through it", after["on"] is not None)
check("⭐ BLEND held through it", after["blend"] is not None)
check("and the counters recorded it",
      by["off"].stats["releases"] == 1 and by["on"].stats["releases"] == 0
      and by["on"].stats["bridged_frames"] == 1)

print("\n3. THE RESUME -- ON teleports, BLEND walks back")
moved = (cx + 90.0, cy + 40.0)              # the hand reappears well away
before = {k: by[k].cube_center(after[k]) for k in ("on", "blend")}
frame(arms, hand_at(*moved), t)
t += 42.0
step = {k: math.dist(before[k], by[k].cube_center(after[k])) for k in ("on", "blend")}
check("ON moves the cube in one step", step["on"] > 1.0, f"{step['on']:.1f} px")
check("⭐ BLEND moves a fraction of that on the resume frame",
      step["blend"] < step["on"] * 0.6,
      f"blend {step['blend']:.1f} px vs on {step['on']:.1f} px")
check("  BLEND armed its blend, ON did not",
      by["blend"].resync_blend_left["Right"] > 0
      and by["on"].resync_blend_left["Right"] == 0)
for _ in range(by["blend"].resync_blend_frames + 1):
    frame(arms, hand_at(*moved), t)
    t += 42.0
end = {k: by[k].cube_center(after[k]) for k in ("on", "blend")}
check("⭐ and BLEND converges to exactly where ON is -- no residual offset",
      math.dist(end["on"], end["blend"]) < 0.01,
      f"{math.dist(end['on'], end['blend']):.4f} px")

print("\n4. A LONG dropout -- every arm gives up")
for _ in range(30):
    frame(arms, None, t)
    t += 42.0
check("all three released once the coast was exhausted",
      all(a.cube_owned_by("Right") is None for a in arms))


print("\n" + "=" * 78)
print(f"{len(FAILS)} failure(s)" + ("" if not FAILS else ": " + ", ".join(FAILS)))
print("=" * 78)
sys.exit(1 if FAILS else 0)
