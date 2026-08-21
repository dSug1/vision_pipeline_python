"""⭐ T3 -- can a relabelled hand be recognised, and at what threshold?

Queue T3 was re-opened on 2026-08-21 by `d2_bridge_ab.py`: of 205 spurious cube
releases, **113 are the owner's own hand reappearing under the OTHER handedness
label**, against 83 true dropouts. Ownership is keyed by the label, so any
relabel -- DR-1 erring, or DR-1 CORRECTING itself -- orphans a held cube.

The fix is to keep the cube with the TRACK rather than the label. On the wire the
client sees a relabel as: the owner's slot goes empty and the other slot fills,
with the same physical hand in it. So the client can recognise it by POSITION --
the same criterion DR-1 itself uses -- and hand the cube over instead of dropping
it. That needs no protocol change, which is the same scoping decision spec §2.2
made for D1.

THIS SCRIPT MEASURES THE TWO THINGS THAT DECISION NEEDS:

  1. **the threshold.** How far does the other-slot hand sit from where the owner
     hand just was? A true relabel is the same hand one frame later, so it should
     be very close; a genuinely different hand should not be.
  2. **the guard's cost.** The transfer must NOT fire when the other slot already
     held a tracked hand of its own -- that is two real hands, and handing the
     cube over would be theft, not repair. How many candidates does that remove?

⚠ The search window is D2's coast window, deliberately reused rather than a new
constant: the coast is already "we have not given up on this track yet", which is
exactly the period in which a transfer makes sense. Keeping the rule set small is
a standing owner preference.

    .venv/Scripts/python.exe analysis/t3_relabel_threshold.py [--root DIR]
"""
import argparse
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_blocks  # noqa: E402

DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"
OTHER = {"Left": "Right", "Right": "Left"}


def shipped(name, module, fallback):
    path = os.path.join(BASE, "Resources", module)
    try:
        for line in open(path, encoding="utf-8"):
            if line.startswith(name + " = "):
                return float(line.split("=", 1)[1].split("#")[0].strip())
    except OSError:
        pass
    return fallback


COAST_MS = shipped("BRIDGE_WINDOW_MS", "hand_state.py", 150.0)


def in_take(rows, meta):
    t0 = rows[0]["tCapture"]
    span = (rows[-1]["tCapture"] - t0) / 1000.0
    tr = meta.get("analysis_trim") or {}
    head, tail = tr.get("head_s", 10.0), tr.get("tail_s", 5.0)
    return [r for r in rows if head <= (r["tCapture"] - t0) / 1000.0 <= span - tail]


def owner_of(row):
    return ((row.get("cubes_raw") or {}).get("large", {}) or {}).get("owner")


def hand_by_label(row, label):
    for h in row.get("hands") or []:
        if h.get("label") == label:
            return h
    return None


def centre_scale(hand):
    lm = [tuple(p) for p in hand["landmarks"]]
    return hand_blocks.palm_position(lm), hand_blocks.palm_scale(lm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    a = ap.parse_args()

    # Every moment a held hand vanishes, and what the other slot was doing.
    cand, blocked, pure_dropout, no_geom = [], [], 0, 0
    for d in sorted(glob.glob(os.path.join(a.root, "*"))):
        f = os.path.join(d, "raw_landmarks.jsonl")
        if not os.path.isdir(d) or not os.path.exists(f):
            continue
        meta = json.load(open(os.path.join(d, "meta.json")))
        rows = [json.loads(l) for l in open(f)]
        if not rows:
            continue
        sub = in_take(rows, meta)
        if len(sub) < 30:
            continue
        for i in range(len(sub) - 1):
            owner = owner_of(sub[i])
            if owner is None or hand_by_label(sub[i], owner) is None:
                continue
            if hand_by_label(sub[i + 1], owner) is not None:
                continue                       # still tracked: nothing happened
            here, scale = centre_scale(hand_by_label(sub[i], owner))
            if here is None or not scale:
                no_geom += 1
                continue
            # ⚠ THE GUARD, evaluated at the last frame the owner was seen: was the
            # OTHER slot already carrying a hand of its own? If so this is two
            # real hands and the cube must NOT change hands.
            other_busy = hand_by_label(sub[i], OTHER[owner]) is not None
            # Look for the other slot filling, anywhere inside the coast window.
            found = None
            for j in range(i + 1, len(sub)):
                if sub[j]["tCapture"] - sub[i]["tCapture"] > COAST_MS:
                    break
                h = hand_by_label(sub[j], OTHER[owner])
                if h is not None:
                    p, _ = centre_scale(h)
                    if p is not None:
                        found = math.hypot(p[0] - here[0], p[1] - here[1]) / scale
                    break
            if found is None:
                pure_dropout += 1
            elif other_busy:
                blocked.append(found)
            else:
                cand.append(found)

    print("=" * 90)
    print("T3 -- RELABEL TRANSFER: is the moved hand recognisable, and how tight?")
    print("=" * 90)
    total = len(cand) + len(blocked) + pure_dropout
    print(f"  {total} moments where a HELD hand vanished (in-take, all takes)")
    print(f"    {pure_dropout:>4}  other slot stayed empty inside the {COAST_MS:.0f} ms coast")
    print(f"          -> a true dropout. D2's bridge already owns this case.")
    print(f"    {len(cand):>4}  other slot FILLED, and was empty when the owner vanished")
    print(f"          -> ⭐ transfer candidates: this is what T3 acts on")
    print(f"    {len(blocked):>4}  other slot filled but was ALREADY BUSY")
    print(f"          -> ⚠ two real hands. The guard blocks these, always.")
    if no_geom:
        print(f"    {no_geom:>4}  skipped, degenerate palm geometry")

    def dist(name, xs):
        if not xs:
            print(f"\n  {name}: none")
            return
        s = sorted(xs)
        print(f"\n  {name} -- displacement in palm widths ({len(s)} events)")
        print(f"    min {s[0]:.2f}   median {s[len(s)//2]:.2f}   "
              f"p90 {s[int(.9*len(s))]:.2f}   max {s[-1]:.2f}")
        for cut in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
            n = sum(1 for x in s if x <= cut)
            print(f"    <= {cut:>4} pw : {n:>4}/{len(s)}  ({100.0*n/len(s):>5.1f}%)")

    dist("TRANSFER CANDIDATES (other slot was free)", cand)
    dist("GUARD-BLOCKED (other slot already busy)", blocked)

    # ── What the SHIPPED rule does to the corpus ─────────────────────────────
    thr = shipped("TRANSFER_PALM_WIDTHS", "hand_ownership.py", 0.5)
    transferred = sum(1 for x in cand if x <= thr)
    missed = len(cand) - transferred
    print()
    print("  " + "=" * 84)
    print(f"  SHIPPED RULE APPLIED ({thr:.2f} palm widths + the busy-slot guard, "
          f"inside D2's {COAST_MS:.0f} ms coast)")
    print("  " + "=" * 84)
    print(f"    {transferred:>4}  cubes FOLLOW their hand instead of dropping  ⭐ T3's effect")
    print(f"    {missed:>4}  candidates fall outside the threshold -> still drop")
    print(f"    {len(blocked):>4}  blocked by the guard -> still drop, DELIBERATELY")
    print(f"    {pure_dropout:>4}  true dropouts -> D2's bridge, not this row")
    print()
    print(f"    of {total} vanish-while-held moments, T3 removes {transferred} "
          f"({100.0*transferred/max(1,total):.0f}%)")
    print("    ⚠ NOT a claim that the other cases are fixed. The guard-blocked 84")
    print("      are the two-hand case and stay open (spec §0.4's duplicate-label")
    print("      problem); the threshold misses are ambiguous and dropping is the")
    print("      safe default there.")
    print()
    print("  ⭐ HOW TO READ THIS. The candidates are a hand that vanished from one")
    print("     slot and appeared in the other within a few frames. If that is the")
    print("     SAME physical hand -- a relabel -- it cannot have moved far, so a")
    print("     tight distribution IS the evidence for the relabel reading, and the")
    print("     threshold should be set where that cluster ends, not wherever it")
    print("     catches the most events.")
    print("  ⚠ A threshold past the cluster does not 'save more cubes' -- it starts")
    print("     handing them to hands that are somewhere else.")
    print("=" * 90)


if __name__ == "__main__":
    main()
