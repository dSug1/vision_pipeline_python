"""Does the M4 gate over-filter RAPID hand movement? (queue item 1.6, owner question)

Owner statement, 2026-08-04, which sets the acceptance bar: *"what I captured in
the recordings are rapid movements but still acceptable expected inputs for my
game."* So fast motion in this corpus is LEGITIMATE INPUT, and a gate that
rejects it is broken -- rejecting a real fast gesture is a worse failure than
letting a teleport through, because it degrades the input the game is built on.

The gate thresholds UNPREDICTED movement, not speed as such: smooth fast motion
is predictable, so the constant-velocity model absorbs it. The genuine risk is
ACCELERATION and DIRECTION REVERSAL at speed, where the prediction is badly wrong
while nothing is actually broken. This measures exactly that.

Reported:
  1. rejection rate vs hand SPEED decile (palm widths per frame, scale-free)
  2. rejection rate vs |acceleration|
  3. per-session rates, with the palm_back_s1..s4 speed ladder called out --
     that series is a controlled speed experiment (prescribed cycle times from
     4.4 s/cycle down to ~1 s/cycle) and is the cleanest evidence available
  4. the speed profile WITHIN each 2026-08-04 session, to locate any take where
     the operator ramped the speed up over time

    .venv/Scripts/python.exe analysis/m4_speed_tradeoff.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import frame_gate as FG

SPEED_BUCKETS = [(0.0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.20),
                 (0.20, 0.35), (0.35, 0.50), (0.50, 0.75), (0.75, 1.0),
                 (1.0, 1.5), (1.5, 99.0)]
ACCEL_BUCKETS = [(0.0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.25),
                 (0.25, 0.50), (0.50, 1.0), (1.0, 99.0)]


def bucket_of(v, buckets):
    for b in buckets:
        if b[0] <= v < b[1]:
            return b
    return buckets[-1]


def run():
    speed_tot = {b: 0 for b in SPEED_BUCKETS}
    speed_rej = {b: 0 for b in SPEED_BUCKETS}
    acc_tot = {b: 0 for b in ACCEL_BUCKETS}
    acc_rej = {b: 0 for b in ACCEL_BUCKETS}
    per_session = {}
    profiles = {}

    # AJP.SESSIONS keys on meta["sequence"], and the corpus has three
    # free_manipulation takes and three palm_back_s2_slow takes -- keying a dict
    # on that name silently keeps only the last of each. Disambiguate.
    seen = {}
    for _si, (raw_name, frames) in enumerate(AJP.SESSIONS):
        seen[raw_name] = seen.get(raw_name, 0) + 1
        name = raw_name if seen[raw_name] == 1 else f"{raw_name} #{seen[raw_name]}"
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        gates, last_idx, prev, prev2 = {}, {}, {}, {}
        tot = rej = 0
        prof = []
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
                    gates[lab] = FG.FrameGate()
                    prev.pop(lab, None)
                    prev2.pop(lab, None)
                last_idx[lab] = i

                p1, p2 = prev.get(lab), prev2.get(lab)
                speed = math.dist(cen, p1) / wid if p1 is not None else None
                accel = None
                if p1 is not None and p2 is not None:
                    v_now = (cen[0] - p1[0], cen[1] - p1[1])
                    v_prev = (p1[0] - p2[0], p1[1] - p2[1])
                    accel = math.dist(v_now, v_prev) / wid

                res = gates[lab].update(pts, None)
                rejected = not res["accepted"]
                tot += 1
                rej += rejected
                if speed is not None:
                    b = bucket_of(speed, SPEED_BUCKETS)
                    speed_tot[b] += 1
                    speed_rej[b] += rejected
                    prof.append((i, speed, rejected))
                if accel is not None:
                    b = bucket_of(accel, ACCEL_BUCKETS)
                    acc_tot[b] += 1
                    acc_rej[b] += rejected

                prev2[lab] = prev.get(lab)
                prev[lab] = cen
        if tot:
            per_session[name] = (tot, rej, prof)
            profiles[name] = prof
    return speed_tot, speed_rej, acc_tot, acc_rej, per_session


def main():
    st, sr, at, ar, per = run()

    print("=" * 78)
    print("M4 gate vs RAPID MOTION -- are we over-filtering legitimate input?")
    print("=" * 78)

    print("\n--- rejection rate by hand SPEED (palm widths / frame) ---")
    print(f"  {'speed':>14}{'frames':>10}{'rejected':>10}{'rate':>9}")
    for b in SPEED_BUCKETS:
        if not st[b]:
            continue
        print(f"  {b[0]:>6.2f}-{b[1]:<7.2f}{st[b]:>10}{sr[b]:>10}"
              f"{100.0*sr[b]/st[b]:>8.2f}%")

    print("\n--- rejection rate by |ACCELERATION| (change in velocity) ---")
    print(f"  {'accel':>14}{'frames':>10}{'rejected':>10}{'rate':>9}")
    for b in ACCEL_BUCKETS:
        if not at[b]:
            continue
        print(f"  {b[0]:>6.2f}-{b[1]:<7.2f}{at[b]:>10}{ar[b]:>10}"
              f"{100.0*ar[b]/at[b]:>8.2f}%")

    print("\n--- the palm_back speed LADDER (controlled experiment) ---")
    print(f"  {'session':<44}{'frames':>8}{'rej':>7}{'rate':>8}{'p95 speed':>11}")
    ladder = sorted(k for k in per if "palm_back_s" in k)
    for k in ladder:
        tot, rej, prof = per[k]
        sp = sorted(s for _i, s, _r in prof)
        p95 = sp[int(0.95 * (len(sp) - 1))] if sp else 0
        print(f"  {k[:43]:<44}{tot:>8}{rej:>7}{100.0*rej/tot:>7.2f}%{p95:>11.3f}")

    print("\n--- fastest sessions in the corpus, by p95 speed ---")
    rows = []
    for k, (tot, rej, prof) in per.items():
        sp = sorted(s for _i, s, _r in prof)
        if not sp:
            continue
        rows.append((sp[int(0.95 * (len(sp) - 1))], k, tot, rej))
    print(f"  {'session':<44}{'frames':>8}{'rej':>7}{'rate':>8}{'p95 speed':>11}")
    for p95, k, tot, rej in sorted(rows, reverse=True)[:10]:
        print(f"  {k[:43]:<44}{tot:>8}{rej:>7}{100.0*rej/tot:>7.2f}%{p95:>11.3f}")

    print("\n--- speed profile over time, per session (did the speed ramp up?) ---")
    for k in sorted(per):
        tot, rej, prof = per[k]
        if len(prof) < 50:
            continue
        n = len(prof)
        parts = []
        for q in range(5):
            seg = prof[q * n // 5:(q + 1) * n // 5]
            sp = sorted(s for _i, s, _r in seg)
            rj = sum(1 for _i, _s, r in seg if r)
            parts.append(f"{sp[int(0.95*(len(sp)-1))]:.3f}/{rj}")
        print(f"  {k[:40]:<42}" + "  ".join(parts))
    print("      (per fifth of the take: p95 speed / rejections)")

    # ---- Are the high-speed rejections REAL motion or teleports? ----
    # A teleport is an out-and-back excursion: the frame after it returns to the
    # trajectory the hand was already on. Genuine fast motion CONTINUES past.
    # ratio = dist(p[i-1], p[i+1]) / dist(p[i-1], p[i])
    #   ~0  -> came straight back  = teleport (correctly rejected)
    #   >=1 -> kept going          = real movement (WRONGLY rejected)
    print("\n--- rejected frames: teleport (out-and-back) or real movement? ---")
    tele = real = ambig = 0
    for _name, frames in AJP.SESSIONS:
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        gates, last_idx, hist = {}, {}, {}
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
                    gates[lab] = FG.FrameGate()
                    hist[lab] = []
                last_idx[lab] = i
                rejected = not gates[lab].update(pts, None)["accepted"]
                hist.setdefault(lab, []).append((cen, wid, rejected))
        for seq in hist.values():
            for j in range(1, len(seq) - 1):
                if not seq[j][2]:
                    continue
                a, b, c = seq[j - 1][0], seq[j][0], seq[j + 1][0]
                out = math.dist(a, b)
                if out < 1e-9:
                    continue
                ratio = math.dist(a, c) / out
                if ratio < 0.5:
                    tele += 1
                elif ratio > 0.9:
                    real += 1
                else:
                    ambig += 1
    tot_cls = tele + real + ambig
    if tot_cls:
        print(f"  out-and-back (teleport, correctly rejected) {tele:>5} "
              f"({100.0*tele/tot_cls:.1f}%)")
        print(f"  continued    (real movement, WRONGLY rejected){real:>5} "
              f"({100.0*real/tot_cls:.1f}%)")
        print(f"  ambiguous                                    {ambig:>5} "
              f"({100.0*ambig/tot_cls:.1f}%)")

    print("\n" + "=" * 78)
    print("READING THIS: if the rejection rate climbs steeply with speed, the")
    print("gate is taxing legitimate fast input and the threshold must rise.")
    print("Rejection driven by ACCELERATION rather than speed is the expected")
    print("and acceptable shape -- a teleport is infinite acceleration.")
    print("=" * 78)


if __name__ == "__main__":
    main()
