"""Is each M4 rejection a real teleport, or legitimate fast movement?

The owner's acceptance bar (2026-08-04): the rapid movements in this corpus are
LEGITIMATE game input, so rejecting them is a worse failure than letting a
teleport through.

DISCRIMINATOR. A teleport is an OUT-AND-BACK excursion -- MediaPipe briefly
reports a different hand's position, then self-corrects "a few frames later"
(14.1.4). Genuine fast movement CONTINUES. So for each rejected frame j, look
ahead up to LOOKAHEAD frames and ask whether the hand came back to where it was
heading before the rejection:

    out    = dist(p[j-1], p[j])                  how far it leapt
    back   = min over k in j+1..j+L of dist(p[j-1], p[k])
    return_ratio = back / out

    ~0   came straight back      -> TELEPORT, correctly rejected
    >=1  kept going              -> REAL MOVEMENT, wrongly rejected

⚠ Two bugs in the first version of this measurement, both fixed here and both
worth knowing because they each produced a confident wrong answer:
  (a) run-break handling overwrote the per-label history instead of starting a
      new run, so only 12 of 118 rejections were ever classified;
  (b) a single-frame lookahead classifies a MULTI-frame teleport as "continued
      movement" -- which is exactly backwards, and the documented teleport lasts
      several frames.

    .venv/Scripts/python.exe analysis/m4_rejection_audit.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import frame_gate as FG

LOOKAHEAD = 6


def runs(innovation_max=None, width_max=None):
    """Yield (session_name, [(centroid, width, rejected), ...]) per CONTIGUOUS run."""
    kw = {}
    if innovation_max is not None:
        kw["innovation_max"] = innovation_max
    if width_max is not None:
        kw["width_log_ratio_max"] = width_max
    seen = {}
    for raw_name, frames in AJP.SESSIONS:
        seen[raw_name] = seen.get(raw_name, 0) + 1
        name = raw_name if seen[raw_name] == 1 else f"{raw_name} #{seen[raw_name]}"
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        gates, last_idx, cur = {}, {}, {}
        out = []
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs_list, keep = [], []
            for h in hands:
                pts = [tuple(p) for p in h["landmarks"]]
                cen = AJP.palm_centroid(pts)
                if cen is None:
                    continue
                obs_list.append((cen, h["handedness"], h.get("score", 1.0),
                                 AJP.palm_width(pts)))
                keep.append(h)
            if not obs_list:
                trk.update([])
                continue
            for h, lab in zip(keep, trk.update(obs_list)):
                pts = [tuple(p) for p in h["landmarks"]]
                cen = AJP.palm_centroid(pts)
                wid = AJP.palm_width(pts)
                if cen is None or not wid or wid <= 1e-6:
                    continue
                broke = lab in last_idx and last_idx[lab] != i - 1
                if lab not in gates or broke:
                    if cur.get(lab):
                        out.append(cur[lab])      # CLOSE the run, do not drop it
                    gates[lab] = FG.FrameGate(**kw)
                    cur[lab] = []
                last_idx[lab] = i
                rejected = not gates[lab].update(pts, None)["accepted"]
                cur.setdefault(lab, []).append((cen, wid, rejected))
        for seq in cur.values():
            if seq:
                out.append(seq)
        for seq in out:
            yield name, seq


def main():
    print("=" * 78)
    print("M4 rejections: teleport, or legitimate fast movement?")
    print("=" * 78)

    buckets = {"teleport (<0.5)": 0, "partial (0.5-0.9)": 0,
               "continued (>=0.9)": 0}
    per_session = {}
    ratios = []
    total_rej = 0

    for name, seq in runs():
        for j in range(1, len(seq) - 1):
            if not seq[j][2]:
                continue
            total_rej += 1
            a, b = seq[j - 1][0], seq[j][0]
            out = math.dist(a, b)
            if out < 1e-9:
                continue
            back = min(math.dist(a, seq[k][0])
                       for k in range(j + 1, min(len(seq), j + 1 + LOOKAHEAD)))
            r = back / out
            ratios.append(r)
            key = ("teleport (<0.5)" if r < 0.5
                   else "partial (0.5-0.9)" if r < 0.9 else "continued (>=0.9)")
            buckets[key] += 1
            d = per_session.setdefault(name, {"tele": 0, "real": 0})
            d["tele" if r < 0.9 else "real"] += 1

    n = sum(buckets.values())
    print(f"\nrejections classified: {n} (of {total_rej} total; the rest are at a "
          f"run edge with no lookahead)\n")
    for k, v in buckets.items():
        print(f"  {k:<22}{v:>6}  ({100.0*v/n:.1f}%)" if n else k)

    if ratios:
        s = sorted(ratios)
        print(f"\n  return_ratio  p10={s[len(s)//10]:.2f}  median={s[len(s)//2]:.2f}  "
              f"p90={s[9*len(s)//10]:.2f}")

    print("\n--- by session (tele = came back, real = kept going) ---")
    print(f"  {'session':<42}{'tele':>7}{'real':>7}")
    for k in sorted(per_session, key=lambda k: -per_session[k]["real"]):
        d = per_session[k]
        if d["tele"] or d["real"]:
            print(f"  {k[:41]:<42}{d['tele']:>7}{d['real']:>7}")

    # ---- THRESHOLD SWEEP: where does real movement stop being taxed? ----
    # The owner's bar: rapid movement in this corpus is legitimate input, so
    # "real" rejections are the cost and teleports caught are the benefit.
    INF = float("inf")
    print("\n--- threshold sweep (innov = position innovation, w = palm width) ---")
    print(f"  {'config':<22}{'rejects':>9}{'teleport':>10}{'REAL':>7}"
          f"{'>1.0 exc':>10}{'>2.0 exc':>10}")
    configs = [(f"innov {t}, w 0.5", t, None) for t in (1.0, 1.5, 2.0, 3.0)]
    configs += [(f"innov {t}, NO width", t, INF) for t in (1.0, 1.5, 2.0, 3.0)]
    configs += [("NO innov, w 0.5", INF, None),
                ("innov 1.0, w 1.0", 1.0, 1.0)]
    for label, thr, wmax in configs:
        tele = real = rej = 0
        exc10 = exc20 = 0
        for _name, seq in runs(innovation_max=thr, width_max=wmax):
            for j in range(1, len(seq) - 1):
                # excursions surviving: raw step vs the previous accepted frame,
                # counted only where the gate let the frame through
                if not seq[j][2]:
                    step = math.dist(seq[j][0], seq[j - 1][0]) / seq[j][1]
                    if step > 1.0:
                        exc10 += 1
                    if step > 2.0:
                        exc20 += 1
                    continue
                rej += 1
                a, b = seq[j - 1][0], seq[j][0]
                out = math.dist(a, b)
                if out < 1e-9:
                    continue
                back = min(math.dist(a, seq[k][0])
                           for k in range(j + 1, min(len(seq), j + 1 + LOOKAHEAD)))
                if back / out < 0.9:
                    tele += 1
                else:
                    real += 1
        print(f"  {label:<22}{rej:>9}{tele:>10}{real:>7}{exc10:>10}{exc20:>10}")

    print("\n" + "=" * 78)
    print("A high 'REAL' count means the gate is taxing legitimate movement and")
    print("the threshold must rise. Pick the threshold where REAL collapses but")
    print("teleports are still caught.")
    print("=" * 78)


if __name__ == "__main__":
    main()
