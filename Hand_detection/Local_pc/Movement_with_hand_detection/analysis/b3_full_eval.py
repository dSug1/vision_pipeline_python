"""B3'' full evaluation across the whole corpus.

Owner's questions, in his priority order:

  0 ⚠ DOES IT REJECT GENUINE DIRECTION CHANGES?  The vigilance condition, and it
    is checked FIRST because a failure here disqualifies the gate regardless of
    everything else. A quadratic fitted over 7 PAST frames necessarily
    over-predicts continuation at a reversal -- velocity crosses zero, the
    residual spikes, and a naive gate rejects real motion. The rotation takes
    give a clean test: every pitch/yaw cycle contains exactly TWO reversals, and
    the operator-reported cycle counts are in the metadata.
  1 jitter                    does gating reduce still-hand noise?
  2 edge-on                   does it reduce excursions in the DR-2 band?
  3 back-of-hand precision    does it improve orientation on the known_*_back takes?
  4 teleport                  does it catch them -- and at what cost in real motion?

Plus the mandatory counter-metric:

  5 TRACKING COST             how far the gated output sits from the raw
                              measurement on frames the raw deserves to be
                              believed. A gate that rejects everything scores
                              perfectly on 1-4 and is worthless; this is what
                              catches that (the discipline from 0.12 and the
                              analysis README).

Reversals are detected NON-CAUSALLY from raw sign changes in each channel's own
velocity, independent of the gate, so the labels cannot be derived from the
thing under test.

    .venv/Scripts/python.exe analysis/b3_full_eval.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import hand_blocks as HB
from Resources import block_predictor as BP
from Resources import palm_geometry as PG

EDGE_ON_BAND = 0.15
STILL_PALM_MOVE = 1.5       # px/frame -- "the hand is stationary"
TRUST_Z = 1.0               # raw is trustworthy when its own z was small


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def sessions():
    """v2 streams of block states, per contiguous run, with edge-on attached."""
    seen = {}
    for raw_name, frames in AJP.SESSIONS:
        seen[raw_name] = seen.get(raw_name, 0) + 1
        name = raw_name if seen[raw_name] == 1 else f"{raw_name} #{seen[raw_name]}"
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        cur, last_idx, out = {}, {}, []
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs, keep = [], []
            for h in hands:
                pts = [tuple(p) for p in h["landmarks"]]
                cen = AJP.palm_centroid(pts)
                if cen is None:
                    continue
                obs.append((cen, h["handedness"], h.get("score", 1.0),
                            AJP.palm_width(pts)))
                keep.append(h)
            if not obs:
                trk.update([])
                continue
            for h, lab in zip(keep, trk.update(obs)):
                if not h.get("world_landmarks"):
                    continue
                pts = [tuple(p) for p in h["landmarks"]]
                st = HB.block_state(pts, [tuple(v) for v in h["world_landmarks"]])
                if st is None or st["position"] is None or not st["scale"]:
                    continue
                st["_eo"] = PG.edge_on_measure(pts)
                if lab in last_idx and last_idx[lab] != i - 1:
                    if cur.get(lab):
                        out.append((name, cur[lab]))
                    cur[lab] = []
                last_idx[lab] = i
                cur.setdefault(lab, []).append(st)
        for seq in cur.values():
            if seq:
                out.append((name, seq))
        for item in out:
            yield item


def reversals(seq, ch):
    """NON-CAUSAL: frame indices where this channel's raw velocity changes sign.

    Requires both velocities to exceed the channel's floor, so resting noise
    does not register as a direction change.
    """
    floor = BP.FLOOR.get(ch, 0.0)
    vals = []
    for st in seq:
        sc = BP.BlockPredictor._scalars(st)
        vals.append(sc.get(ch))
    idx = set()
    for k in range(2, len(vals)):
        a, b, c = vals[k - 2], vals[k - 1], vals[k]
        if a is None or b is None or c is None:
            continue
        v1, v2 = b - a, c - b
        if abs(v1) > floor and abs(v2) > floor and v1 * v2 < 0:
            idx.add(k)
    return idx


def main():
    print("=" * 78)
    print("B3'' -- full corpus evaluation")
    print("=" * 78)

    rev_tot = rev_rej = non_tot = non_rej = 0
    per_take_rev = {}
    jit_raw, jit_out = [], []
    band_raw, band_out = [], []
    quat_raw, quat_out = {}, {}
    track = []
    n_frames = n_any_rej = n_forced = 0
    ch_rej = {c: 0 for c in BP.CHANNELS}

    for name, seq in sessions():
        if len(seq) < BP.MIN_HISTORY + 3:
            continue
        rev_idx = {ch: reversals(seq, ch) for ch in BP.SCALAR_CHANNELS}
        g = BP.BlockPredictor()
        prev_out = prev_raw = None
        prev_palm = None
        prev_qr = prev_qo = None      # per-run, not module state
        for k, st in enumerate(seq):
            res = g.update(st)
            n_frames += 1
            if res["rejected"]:
                n_any_rej += 1
            if res["forced"]:
                n_forced += 1
            for c in res["rejected"]:
                ch_rej[c] += 1

            # --- 0. direction-reversal safety, per channel ---
            for ch in BP.SCALAR_CHANNELS:
                if k not in rev_idx[ch]:
                    non_tot += 1
                    non_rej += 1 if ch in res["rejected"] else 0
                else:
                    rev_tot += 1
                    hit = 1 if ch in res["rejected"] else 0
                    rev_rej += hit
                    d = per_take_rev.setdefault(name, [0, 0])
                    d[0] += 1
                    d[1] += hit

            out = res["output"]
            w = st["scale"] or 1.0
            # --- 1. jitter while still / 2. edge-on ---
            if prev_raw is not None and prev_out is not None:
                dr = math.dist(st["position"], prev_raw) / w
                do = math.dist(out["position"], prev_out) / w
                pm = math.dist(st["position"], prev_palm) if prev_palm else None
                if pm is not None and pm < STILL_PALM_MOVE:
                    jit_raw.append(dr)
                    jit_out.append(do)
                eo = st.get("_eo")
                if eo is not None and eo < EDGE_ON_BAND:
                    band_raw.append(dr)
                    band_out.append(do)
                # --- 5. tracking cost on trustworthy frames ---
                z = (res["debug"].get("pos_x") or {}).get("z")
                if z is not None and z < TRUST_Z:
                    track.append(math.dist(out["position"], st["position"]) / w)
            # --- 3. orientation, for the back-of-hand takes ---
            if prev_raw is not None and st.get("quaternion") and prev_qr:
                dq = BP._qangle(st["quaternion"], prev_qr)
                dqo = BP._qangle(out.get("quaternion"), prev_qo)
                if dq is not None:
                    quat_raw.setdefault(name, []).append(dq)
                if dqo is not None:
                    quat_out.setdefault(name, []).append(dqo)
            prev_qr = st.get("quaternion")
            prev_qo = out.get("quaternion")
            prev_raw = st["position"]
            prev_out = out["position"]
            prev_palm = st["position"]

    print(f"\nframes judged {n_frames}, frames with any rejection {n_any_rej} "
          f"({100.0*n_any_rej/max(1,n_frames):.2f}%), force-accepts {n_forced}")
    print("rejections by channel: " +
          ", ".join(f"{c}={ch_rej[c]}" for c in BP.CHANNELS if ch_rej[c]))

    print("\n" + "=" * 78)
    print("0. ⚠ DIRECTION-REVERSAL SAFETY -- the disqualifying test")
    print("=" * 78)
    rr = 100.0 * rev_rej / max(1, rev_tot)
    nr = 100.0 * non_rej / max(1, non_tot)
    print(f"  channel-frames AT a reversal   : {rev_tot:>7}  rejected {rev_rej:>5} "
          f"({rr:.2f}%)")
    print(f"  channel-frames elsewhere       : {non_tot:>7}  rejected {non_rej:>5} "
          f"({nr:.2f}%)")
    print(f"  ratio (reversal / elsewhere)   : "
          f"{(rr/nr if nr > 0 else float('inf')):.2f}x")
    print("  -> ~1.0x means reversals are treated like any other frame, which is")
    print("     the requirement. A large ratio means the quadratic is")
    print("     over-predicting continuation and the gate is eating real motion.")
    print("\n  worst takes by reversal-rejection rate:")
    rows = [(100.0 * d[1] / d[0], n, d) for n, d in per_take_rev.items() if d[0] > 30]
    for r, n, d in sorted(rows, reverse=True)[:8]:
        print(f"    {n[:44]:<46}{d[1]:>5}/{d[0]:<6} {r:>6.2f}%")

    print("\n" + "=" * 78)
    print("1-3. DOES IT FIX THE FOUR PROBLEMS?")
    print("=" * 78)
    print("\n1. JITTER while the hand is still (palm widths/frame)")
    print(f"  {'':<10}{'n':>7}{'p50':>10}{'p95':>10}{'max':>10}")
    print(f"  {'raw':<10}{len(jit_raw):>7}{pct(jit_raw,50):>10.4f}"
          f"{pct(jit_raw,95):>10.4f}{max(jit_raw) if jit_raw else 0:>10.4f}")
    print(f"  {'gated':<10}{len(jit_out):>7}{pct(jit_out,50):>10.4f}"
          f"{pct(jit_out,95):>10.4f}{max(jit_out) if jit_out else 0:>10.4f}")

    print("\n2. EDGE-ON band motion (palm widths/frame)")
    print(f"  {'raw':<10}{len(band_raw):>7}{pct(band_raw,50):>10.4f}"
          f"{pct(band_raw,95):>10.4f}{max(band_raw) if band_raw else 0:>10.4f}")
    print(f"  {'gated':<10}{len(band_out):>7}{pct(band_out,50):>10.4f}"
          f"{pct(band_out,95):>10.4f}{max(band_out) if band_out else 0:>10.4f}")

    print("\n3. BACK-OF-HAND orientation steps (deg/frame), known_*_back takes")
    print(f"  {'take':<34}{'raw p95':>10}{'gated p95':>11}{'raw max':>10}{'gated max':>11}")
    for n in sorted(quat_raw):
        if "back" not in n:
            continue
        a, b = quat_raw[n], quat_out.get(n, [])
        if not a or not b:
            continue
        print(f"  {n[:33]:<34}{pct(a,95):>10.2f}{pct(b,95):>11.2f}"
              f"{max(a):>10.2f}{max(b):>11.2f}")

    print("\n" + "=" * 78)
    print("5. TRACKING COST -- the counter-metric")
    print("=" * 78)
    if track:
        print(f"  n={len(track)}  mean={sum(track)/len(track):.5f}  "
              f"p99={pct(track,99):.5f}  max={max(track):.5f}  (palm widths)")
        print("  How far the gated output sits from a raw measurement the gate")
        print("  itself scored as trustworthy (z < 1). Near zero = invisible when")
        print("  the data deserves belief.")
    print("=" * 78)


if __name__ == "__main__":
    main()
