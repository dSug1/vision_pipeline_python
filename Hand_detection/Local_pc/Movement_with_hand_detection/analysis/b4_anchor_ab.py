"""B4 -- the translation-anchor A/B. Which point should a held cube follow?

THE A7 GATE. `GESTURE_PIPELINE_SPEC.md` 14.1 must not be modified until this
runs. Three anchors, replayed over the takes that were recorded THROUGH the live
snap/translate logic, so the grabs and cube positions in them are real events:

  A  14.1 (incumbent)  distance-weighted 5 fingertips + 4 MCPs, inverse-distance
                       weights frozen at grab, plus a residual offset so the cube
                       does not pop.
  B  palm SIMILARITY   a single offset frozen in the palm's 2D frame -- origin at
                       the palm centroid, x along the MCP row, scale = palm width.
  C  palm RIGID        same, but WITHOUT the scale term.

⭐ WHY C EXISTS, and it tests a real risk rather than padding the table: palm
width is the scale reference, and 14.3.1 measured that it COLLAPSES when the hand
yaws edge-on. Arm B therefore feeds that collapse straight into cube position;
arm C is immune to it but cannot follow genuine depth change. Comparing them
isolates whether including scale helps or hurts.

⚠ EVERYTHING IS COMPUTED IN 2D PIXEL SPACE, deliberately. A7 records that the
original reason for rejecting a palm-anchored design was a 2D/3D coordinate
mismatch. Building the palm frame from pixel landmarks (centroid, MCP-row
direction, palm width) dissolves that objection without needing M6 or M9, neither
of which is going to land.

⚠ THERE IS NO INDEPENDENT GROUND TRUTH for where the cube should be -- the
recorded `center` is 14.1's OWN output, so scoring error against it would just
crown the incumbent. Judged on PROPERTIES instead, the same way 14.1's original
verification was:

  1 no-pop at grab      sanity check: all arms freeze an offset, so all must be ~0
  2 jitter when still   frame-to-frame anchor motion while the palm is stationary
  3 yaw-sink (T4)       does the anchor drift toward the palm as it turns edge-on
  4 cross-plane (N12)   anchor motion inside the edge-on band vs outside
  5 teleport (T3)       anchor motion through the jump_test4 Object Jump

    .venv/Scripts/python.exe analysis/b4_anchor_ab.py [pivot_dir]
"""
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Resources import hand_blocks as HB
from Resources import palm_geometry as PG

PIVOT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.environ.get("TEMP", "."), "claude",
    "c--Users-sugit-Documents--scripts-persos--Persos-vision-pipeline-python-Hand-detection",
    "fdbae111-1ad0-43ab-affa-7e653522be6e", "scratchpad", "pivot")

F141 = (4, 8, 12, 16, 20, 5, 9, 13, 17)     # 5 fingertips + 4 MCPs (14.1)
STILL_PALM_MOVE = 1.5                        # px/frame: "the hand is stationary"
EDGE_ON_BAND = 0.15


# --------------------------------------------------------------------------
# the three anchors
# --------------------------------------------------------------------------
def palm_frame_2d(px):
    """Origin, unit x along the MCP row, unit y perpendicular, and scale."""
    o = HB.palm_position(px)
    s = HB.palm_scale(px)
    if o is None or not s or s < 1e-6:
        return None
    dx = px[17][0] - px[5][0]
    dy = px[17][1] - px[5][1]
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return None
    ex = (dx / n, dy / n)
    ey = (-ex[1], ex[0])
    return o, ex, ey, s


def w141(px, target):
    """14.1's frozen inverse-distance weights, computed at grab."""
    ws = []
    for i in F141:
        d = math.dist(px[i], target)
        ws.append(1.0 / max(d, 1e-3))
    tot = sum(ws)
    return [w / tot for w in ws] if tot > 0 else None


def anchor141(px, weights):
    return (sum(w * px[i][0] for w, i in zip(weights, F141)),
            sum(w * px[i][1] for w, i in zip(weights, F141)))


def to_local(frame, target, use_scale):
    o, ex, ey, s = frame
    vx, vy = target[0] - o[0], target[1] - o[1]
    lx = vx * ex[0] + vy * ex[1]
    ly = vx * ey[0] + vy * ey[1]
    return (lx / s, ly / s) if use_scale else (lx, ly)


def from_local(frame, local, use_scale):
    o, ex, ey, s = frame
    lx, ly = local
    if use_scale:
        lx, ly = lx * s, ly * s
    return (o[0] + lx * ex[0] + ly * ey[0],
            o[1] + lx * ex[1] + ly * ey[1])


# --------------------------------------------------------------------------
def load_takes():
    for f in sorted(glob.glob(os.path.join(PIVOT_DIR, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        yield d.get("label", os.path.basename(f)), d.get("frames", [])


def grab_intervals(frames):
    """(cube, hand, [frame indices]) for each contiguous ownership run."""
    runs = []
    cur = {}
    for i, rec in enumerate(frames):
        cubes = rec.get("cubes") or {}
        seen = set()
        for name, c in cubes.items():
            owner = c.get("owner")
            if owner:
                seen.add((name, owner))
                cur.setdefault((name, owner), []).append(i)
        for key in list(cur):
            if key not in seen:
                if len(cur[key]) > 5:
                    runs.append((key[0], key[1], cur[key]))
                del cur[key]
    for key, idxs in cur.items():
        if len(idxs) > 5:
            runs.append((key[0], key[1], idxs))
    return runs


def px_of(rec, hand):
    h = (rec.get("hands") or {}).get(hand)
    if not h or not h.get("detected") or not h.get("pixel_landmarks"):
        return None
    return [tuple(p) for p in h["pixel_landmarks"]]


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def corr(xs, ys):
    n = len(xs)
    if n < 8:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def main():
    print("=" * 78)
    print("B4 -- translation-anchor A/B (the A7 gate on 14.1)")
    print("=" * 78)
    print(f"\npivot corpus: {PIVOT_DIR}\n")

    arms = ("A 14.1 (9 pts)", "B palm+scale", "C palm rigid")
    pop = {a: [] for a in arms}            # no-pop at grab (px)
    jit = {a: [] for a in arms}            # jitter while still (px/frame)
    band = {a: ([], []) for a in arms}     # (edge-on, open) motion px/frame
    sink = {a: ([], []) for a in arms}     # (|anchor-palm|/scale, edge_on)
    tele = {a: [] for a in arms}           # motion during jump_test4
    n_int = 0

    for take, frames in load_takes():
        for cube, hand, idxs in grab_intervals(frames):
            g = idxs[0]
            px0 = px_of(frames[g], hand)
            if px0 is None:
                continue
            f0 = palm_frame_2d(px0)
            if f0 is None:
                continue
            target = tuple((frames[g].get("cubes") or {})[cube]["center"])
            w = w141(px0, target)
            if w is None:
                continue
            n_int += 1

            ref = {
                arms[0]: (w, (target[0] - anchor141(px0, w)[0],
                              target[1] - anchor141(px0, w)[1])),
                arms[1]: to_local(f0, target, True),
                arms[2]: to_local(f0, target, False),
            }
            prev = {a: None for a in arms}
            prev_palm = None
            for i in idxs:
                px = px_of(frames[i], hand)
                if px is None:
                    continue
                fr = palm_frame_2d(px)
                if fr is None:
                    continue
                eo = PG.edge_on_measure(px)
                pos = {
                    arms[0]: (anchor141(px, ref[arms[0]][0])[0] + ref[arms[0]][1][0],
                              anchor141(px, ref[arms[0]][0])[1] + ref[arms[0]][1][1]),
                    arms[1]: from_local(fr, ref[arms[1]], True),
                    arms[2]: from_local(fr, ref[arms[2]], False),
                }
                if i == g:
                    for a in arms:
                        pop[a].append(math.dist(pos[a], target))
                palm_move = (math.dist(fr[0], prev_palm) if prev_palm else None)
                for a in arms:
                    if prev[a] is not None:
                        d = math.dist(pos[a], prev[a])
                        if palm_move is not None and palm_move < STILL_PALM_MOVE:
                            jit[a].append(d)
                        if eo is not None:
                            band[a][0 if eo < EDGE_ON_BAND else 1].append(d)
                        if take == "jump_test4":
                            tele[a].append(d)
                    if eo is not None:
                        sink[a][0].append(math.dist(pos[a], fr[0]) / fr[3])
                        sink[a][1].append(eo)
                    prev[a] = pos[a]
                prev_palm = fr[0]

    print(f"grab intervals replayed: {n_int}\n")
    if not n_int:
        raise SystemExit("no grab intervals found -- check the corpus")

    print("--- 1. no-pop at grab (px; all arms freeze an offset, so all ~0) ---")
    for a in arms:
        print(f"  {a:<18}max {max(pop[a]) if pop[a] else float('nan'):.6f}")

    print("\n--- 2. jitter while the palm is stationary (px/frame) ---")
    print(f"  {'arm':<18}{'n':>7}{'p50':>9}{'p95':>9}{'max':>9}")
    for a in arms:
        v = jit[a]
        print(f"  {a:<18}{len(v):>7}{pct(v,50):>9.3f}{pct(v,95):>9.3f}"
              f"{max(v) if v else float('nan'):>9.3f}")

    print("\n--- 3. yaw-sink (T4): coupling of the anchor to palm facing ---")
    print("  correlation of |anchor - palm centroid| / scale with edge_on_measure.")
    print("  ⚠ Read the MAGNITUDE, not the sign. 14.1's documented yaw-sink is")
    print("  r = -0.25 (14.1.1), so the defect appears NEGATIVE in this project's")
    print("  convention; the exact quantity it was correlated against is not")
    print("  recorded, so only |r| is compared here. LOWER |r| = less coupled.")
    for a in arms:
        r = corr(sink[a][0], sink[a][1])
        print(f"  {a:<18}r = {r:+.3f}   |r| = {abs(r):.3f}")

    print("\n--- 4. cross-plane (N12): anchor motion inside vs outside the band ---")
    print(f"  {'arm':<18}{'edge-on p95':>13}{'open p95':>11}{'ratio':>8}")
    for a in arms:
        e, o = band[a]
        pe, po = pct(e, 95), pct(o, 95)
        print(f"  {a:<18}{pe:>13.3f}{po:>11.3f}"
              f"{(pe/po if po else float('nan')):>8.2f}")

    print("\n--- 5. teleport response (jump_test4, px/frame) ---")
    print(f"  {'arm':<18}{'p95':>9}{'max':>9}")
    for a in arms:
        v = tele[a]
        print(f"  {a:<18}{pct(v,95):>9.2f}{max(v) if v else float('nan'):>9.2f}")

    print("\n" + "=" * 78)
    print("A7 VERDICT needs no-pop preserved AND a material win on 2-5. If 14.1")
    print("wins, the palm-anchoring proposal is closed and N12 needs another fix.")
    print("=" * 78)


if __name__ == "__main__":
    main()
