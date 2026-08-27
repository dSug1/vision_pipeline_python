# -*- coding: utf-8 -*-
"""⭐⭐ GLOBAL (whole-hand) COHERENCE vs the per-landmark vote — which separates better?

Owner, 2026-08-27: *"What about detecting the coherence on the whole set of
landmarks? are there matrix operations which can be done at frame N, N+1 and N+2 to
check that there is an overall direction of all the landmarks at N+2 which is not
random noise at each landmark?"*

⭐ There are, and the per-landmark version shipped OFF for a reason this measures:
it counts each landmark as ONE BINARY VOTE, so a landmark that barely moved
contributes a coin flip with the same weight as one that swung 5 px. The global
forms below weight by magnitude, which is exactly what that throws away.

────────────────────────────────────────────────────────────────────────────────
THE FOUR CANDIDATES, and where each comes from

  A. SIGN VOTE (shipped, off)   fraction of landmarks whose step agrees in
     direction with their previous step. The baseline being beaten.

  B. FROBENIUS CORRELATION      stack the displacements into D1 = P(N+1)-P(N) and
     D2 = P(N+2)-P(N+1), then  <D1,D2>_F / (||D1||_F ||D2||_F).
     \u2b50 One matrix inner product -- no SVD, no numpy, trivially portable. It is the
     multi-landmark generalisation of the per-landmark dot product, and it weights
     by magnitude instead of voting.
     Lineage: the temporal-coherence assumption behind Lucas-Kanade optical flow
     (Lucas & Kanade 1981) and its confidence measure in Shi & Tomasi 1994.

  C. RANK / SUBSPACE ENERGY     under orthography the measurement matrix of points
     tracked across frames is RANK-LIMITED (Tomasi & Kanade, IJCV 1992 -- already
     cited in this project by `T6`). Coherent motion lives in that low-rank
     subspace; independent per-landmark noise does not. Measured here as the share
     of the displacement field's energy captured by its single dominant direction.
     Related: Irani, "Multi-frame correspondence estimation using subspace
     constraints" (IJCV 2002), which uses exactly this to denoise tracks.

  D. RIGID RESIDUAL             fit the best RIGID transform P(N) -> P(N+2)
     (Kabsch 1976 / Horn 1987 -- both already shipped here) and take the residual
     as a share of the motion. A real hand moves near-rigidly; noise cannot be
     explained by any transform.

\u26a0 SCORED THE ONLY WAY THAT MATTERS: separation between a hand that is STILL and a
hand in a SLOW deliberate turn. Fast turns are easy and every measure gets them.

    .venv/Scripts/python.exe analysis/global_coherence.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import hand_state as HS                        # noqa: E402
from Resources import palm_rotation as PR                     # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
TAKES = ("2026-08-27_232000_steadytrans", "2026-08-27_230601_coherence",
         "2026-08-27_230012_coherence", "2026-08-27_224751_freeze")
DT = 66.0
N = 21


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else float("nan")


# ---------------------------------------------------------------- the measures
def frobenius_corr(d1, d2):
    """B. <D1,D2>_F / (||D1|| ||D2||). Magnitude-weighted, one pass, no SVD."""
    num = ss1 = ss2 = 0.0
    for (ax, ay), (bx, by) in zip(d1, d2):
        num += ax * bx + ay * by
        ss1 += ax * ax + ay * ay
        ss2 += bx * bx + by * by
    den = math.sqrt(ss1) * math.sqrt(ss2)
    return num / den if den > 1e-12 else 0.0


def dominant_energy(d):
    """C. Share of the displacement field's energy in its leading direction.

    ⭐ The 2x2 scatter matrix's top eigenvalue over its trace -- a closed form, so
    no SVD routine is needed. 0.5 = isotropic (noise), 1.0 = every landmark moving
    along one line (a pure translation).
    """
    sxx = sxy = syy = 0.0
    for dx, dy in d:
        sxx += dx * dx
        sxy += dx * dy
        syy += dy * dy
    tr = sxx + syy
    if tr < 1e-12:
        return 0.5
    t = 0.5 * (sxx - syy)
    lam = 0.5 * tr + math.sqrt(t * t + sxy * sxy)
    return lam / tr


def rigid_residual(p0, p2):
    """D. Residual of the best rigid fit P(N)->P(N+2), as a share of the motion."""
    n = len(p0)
    cx0 = sum(p[0] for p in p0) / n
    cy0 = sum(p[1] for p in p0) / n
    cx2 = sum(p[0] for p in p2) / n
    cy2 = sum(p[1] for p in p2) / n
    sxx = sxy = 0.0
    for a, b in zip(p0, p2):
        ax, ay = a[0] - cx0, a[1] - cy0
        bx, by = b[0] - cx2, b[1] - cy2
        sxx += ax * bx + ay * by
        sxy += ax * by - ay * bx
    th = math.atan2(sxy, sxx)
    c, s = math.cos(th), math.sin(th)
    res = mot = 0.0
    for a, b in zip(p0, p2):
        ax, ay = a[0] - cx0, a[1] - cy0
        bx, by = b[0] - cx2, b[1] - cy2
        res += (c * ax - s * ay - bx) ** 2 + (s * ax + c * ay - by) ** 2
        mot += (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    if mot < 1e-12:
        return 1.0
    return math.sqrt(res / mot)


# ---------------------------------------------------------------------- data
def load(session):
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.exists(path):
        return []
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    st = None
    hist = []          # last three frames of landmarks
    prev_q = None
    prev_deltas = None
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            h = r.get("hands") or []
            held = any(c.get("owner") for a in (r.get("cubes") or {}).values()
                       for c in a.values())
            if not held or len(h) != 1:
                st = None
                hist = []
                prev_q = prev_deltas = None
                continue
            px, wl = h[0].get("landmarks"), h[0].get("world_landmarks")
            if not px or not wl or len(px) < N:
                continue
            if st is None:
                st = horn.freeze(px, wl)
            q = horn.delta(st, px, wl)
            hist.append([(p[0], p[1]) for p in px[:N]])
            if len(hist) > 3:
                hist.pop(0)
            if len(hist) == 3 and q is not None and prev_q is not None:
                p0, p1, p2 = hist
                d1 = [(p1[i][0] - p0[i][0], p1[i][1] - p0[i][1]) for i in range(N)]
                d2 = [(p2[i][0] - p1[i][0], p2[i][1] - p1[i][1]) for i in range(N)]
                sign, _ = HS.landmark_coherence(p2, p1, d1)
                out.append((PR.quat_angle_deg(prev_q, q) * 1000.0 / DT,
                            sign if sign is not None else 0.0,
                            frobenius_corr(d1, d2),
                            dominant_energy(d2),
                            rigid_residual(p0, p2)))
            prev_q = q
    return out


def main():
    rows = []
    for t in TAKES:
        rows.extend(load(t))
    if not rows:
        print("no takes found")
        return 1

    still = [r for r in rows if r[0] < 40.0]
    slow = [r for r in rows if 40.0 <= r[0] < 120.0]
    fast = [r for r in rows if r[0] > 150.0]

    w = 84
    print("=" * w)
    print("  GLOBAL COHERENCE -- whole-hand matrix measures vs the per-landmark vote")
    print("=" * w)
    print("  n: still %d   slow turn %d   fast %d" % (len(still), len(slow), len(fast)))
    print()
    print("  %-34s %9s %9s %9s   %s" % ("measure", "STILL", "SLOW", "FAST", "separation"))
    print("  " + "-" * (w - 4))

    MEAS = (("A. per-landmark SIGN VOTE (shipped)", 1, False),
            ("B. Frobenius corr of D1,D2", 2, False),
            ("C. dominant-direction energy", 3, False),
            ("D. rigid residual (lower=coherent)", 4, True))
    best = None
    for name, idx, invert in MEAS:
        a, b, c = med([r[idx] for r in still]), med([r[idx] for r in slow]), med([r[idx] for r in fast])
        # separation: how far apart still and slow sit, in units of their own spread
        sa = [r[idx] for r in still]
        sb = [r[idx] for r in slow]
        spread = 0.5 * ((pct(sa, .75) - pct(sa, .25)) + (pct(sb, .75) - pct(sb, .25)))
        sep = abs(b - a) / spread if spread > 1e-9 else 0.0
        print("  %-34s %9.3f %9.3f %9.3f   %.2f" % (name, a, b, c, sep))
        if best is None or sep > best[0]:
            best = (sep, name, a, b)

    print("  " + "-" * (w - 4))
    print()
    print("=" * w)
    print("  \u2b50 BEST SEPARATION (still vs SLOW turn): %s" % best[1])
    print("     still %.3f  vs  slow %.3f   -- %.2f interquartile ranges apart"
          % (best[2], best[3], best[0]))
    print("  \u26a0 Separation is measured against STILL vs SLOW only. Every measure")
    print("     separates a FAST turn; that case was never the problem.")
    print("=" * w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
