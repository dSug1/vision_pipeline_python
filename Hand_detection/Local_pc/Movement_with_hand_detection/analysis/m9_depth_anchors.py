"""Which scale anchor survives rotation? (groundwork for items 4.1 / 4.2)

Owner observation, 2026-08-04: palm width works as a depth anchor "except when
the hand rotates around the yaw axis and shows the hand edge to the camera",
and other markers may be needed depending on what the hand presents.

A depth anchor must be CONSTANT while the hand rotates in place, and must move
only when the hand actually changes distance. So:

  * rotation takes at roughly constant distance (palm_back_*, pitch_sweep_*)
    -> a good anchor has LOW variation here. Variation is false depth signal.
  * depth_sweep -> a good anchor has HIGH variation here. That is real signal.

Anchors compared (all rigid: the palm quad wrist/index-MCP/middle-MCP/pinky-MCP
does not flex, unlike any MCP->TIP span, which changes with grip):

  width   |index_MCP - pinky_MCP|    the current M9 / 14.3 proposal
  length  |wrist - middle_MCP|       ORTHOGONAL to width in the palm plane
  maxwl   max(width/w0, length/l0)   take whichever is less foreshortened
  diag    max over the four palm-quad spans, same idea with more candidates

THE GEOMETRIC CLAIM BEING TESTED: width and length foreshorten under
ORTHOGONAL rotations -- yaw collapses the MCP row while leaving palm length in
the image plane, pitch does the reverse -- so the larger of the two should
survive a single-axis rotation that kills either one alone.

    .venv/Scripts/python.exe analysis/m9_depth_anchors.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP

WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 5, 9, 17


def anchors(px):
    w = math.dist(px[INDEX_MCP][:2], px[PINKY_MCP][:2])
    l = math.dist(px[WRIST][:2], px[MIDDLE_MCP][:2])
    d1 = math.dist(px[WRIST][:2], px[INDEX_MCP][:2])
    d2 = math.dist(px[WRIST][:2], px[PINKY_MCP][:2])
    return w, l, d1, d2


def cv(vals):
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    if m < 1e-9:
        return None
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    return math.sqrt(var) / m


def main():
    print("=" * 78)
    print("M9 depth-anchor stability under rotation (groundwork for 4.1 / 4.2)")
    print("=" * 78)
    print("\nLOW cv = stable = good on rotation takes (variation there is FALSE")
    print("depth). HIGH cv is what we WANT on depth_sweep (real signal).\n")
    print(f"  {'session':<34}{'width':>9}{'length':>9}{'max(w,l)':>10}{'max4':>9}")

    seen = {}
    rows = []
    for raw_name, frames in AJP.SESSIONS:
        seen[raw_name] = seen.get(raw_name, 0) + 1
        name = raw_name if seen[raw_name] == 1 else f"{raw_name} #{seen[raw_name]}"
        ws, ls, mx, m4 = [], [], [], []
        base = None
        for rec in frames:
            hands = rec.get("hands") or []
            if len(hands) != 1:
                continue                     # single-hand only: clean scale
            px = [tuple(p) for p in hands[0]["landmarks"]]
            w, l, d1, d2 = anchors(px)
            if w < 1e-6 or l < 1e-6:
                continue
            if base is None:
                base = (w, l, d1, d2)
            ws.append(w)
            ls.append(l)
            mx.append(max(w / base[0], l / base[1]))
            m4.append(max(w / base[0], l / base[1],
                          d1 / base[2] if base[2] > 1e-6 else 0,
                          d2 / base[3] if base[3] > 1e-6 else 0))
        if len(ws) < 50:
            continue
        rows.append((name, cv(ws), cv(ls), cv(mx), cv(m4)))

    def fmt(x):
        return f"{x:.3f}" if x is not None else "  --  "

    rot = [r for r in rows if r[0].startswith(("palm_back", "pitch_sweep"))]
    other = [r for r in rows if r not in rot]

    print("  --- ROTATION IN PLACE (want LOW: any variation is false depth) ---")
    for n, a, b, c, d in sorted(rot):
        print(f"  {n[:33]:<34}{fmt(a):>9}{fmt(b):>9}{fmt(c):>10}{fmt(d):>9}")
    for label, vals in (("width", 0), ("length", 1), ("max(w,l)", 2), ("max4", 3)):
        got = [r[vals + 1] for r in rot if r[vals + 1] is not None]
        if got:
            print(f"  {'MEAN ' + label:<34}{sum(got)/len(got):>9.3f}")

    print("\n  --- EVERYTHING ELSE (depth_sweep wants HIGH) ---")
    for n, a, b, c, d in sorted(other):
        print(f"  {n[:33]:<34}{fmt(a):>9}{fmt(b):>9}{fmt(c):>10}{fmt(d):>9}")

    print("\n" + "=" * 78)
    print("If max(w,l) is materially more stable than width alone on the rotation")
    print("takes while staying responsive on depth_sweep, the owner's multi-anchor")
    print("proposal is right and S10's freeze-only answer is insufficient.")
    print("=" * 78)


if __name__ == "__main__":
    main()
