"""Derive `block_predictor`'s absolute floors from the corpus (queue B3'').

The floors are the one part of the gate that cannot come from the fit itself.
When the hand is still, RSS -> 0, the OLS prediction variance collapses, and any
real motion becomes an enormous z-score -- a purely relative test would reject
the first frame of every deliberate movement. The floor is the noise level below
which a residual means nothing.

DERIVED, NOT GUESSED, and from the right population: per-channel one-step
prediction residuals on the `static_hold` takes, where the hand is deliberately
stationary so every residual IS sensor noise. The floor is set at the p99.5 of
that distribution -- above essentially all resting noise, and (checked below)
far below the residuals a real teleport produces, so the floor cannot mask one.

⚠ Floors are per-channel in the channel's own units: px for position and scale,
extension units for arcs, degrees for orientation.

    .venv/Scripts/python.exe analysis/calibrate_floors.py
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

CONTROL = "static_hold"


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def residuals(session_filter):
    """Raw one-step prediction residuals per channel, with NO gating -- the gate
    is what we are calibrating, so it must not be in the loop."""
    out = {c: [] for c in BP.CHANNELS}
    seen = {}
    for raw_name, frames in AJP.SESSIONS:
        seen[raw_name] = seen.get(raw_name, 0) + 1
        if session_filter not in raw_name:
            continue
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        hist, last_idx = {}, {}
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
                st = HB.block_state([tuple(p) for p in h["landmarks"]],
                                    [tuple(v) for v in h["world_landmarks"]])
                if st is None or st["position"] is None:
                    continue
                if lab in last_idx and last_idx[lab] != i - 1:
                    hist[lab] = []
                last_idx[lab] = i
                seq = hist.setdefault(lab, [])
                sc = BP.BlockPredictor._scalars(st)
                if len(seq) >= BP.MIN_HISTORY:
                    for ch in BP.SCALAR_CHANNELS:
                        vals = [s["_sc"][ch] for s in seq
                                if s["_sc"].get(ch) is not None]
                        if len(vals) < BP.MIN_HISTORY or sc.get(ch) is None:
                            continue
                        cs = BP.fit_channel(vals[-BP.WINDOW:])
                        if cs is None:
                            continue
                        out[ch].append(abs(sc[ch] - cs.predict(1)))
                    qs = [s["quaternion"] for s in seq if s.get("quaternion")]
                    if len(qs) >= BP.MIN_HISTORY and st.get("quaternion"):
                        qst = BP.fit_quat(qs[-BP.WINDOW:])
                        if qst is not None:
                            d = BP._qangle(qst.predict(1), st["quaternion"])
                            if d is not None:
                                out[BP.QUAT_CHANNEL].append(d)
                rec2 = dict(st)
                rec2["_sc"] = sc
                seq.append(rec2)
                while len(seq) > BP.WINDOW:
                    seq.pop(0)
    return out


def main():
    print("=" * 78)
    print("Calibrating block_predictor floors from the CONTROL takes")
    print("=" * 78)

    still = residuals(CONTROL)
    print(f"\npopulation: `{CONTROL}` -- hand deliberately stationary, so every")
    print("residual below IS sensor noise.\n")
    print(f"  {'channel':<10}{'n':>7}{'p50':>10}{'p95':>10}{'p99':>10}"
          f"{'p99.5':>10}{'max':>10}")
    floors = {}
    for ch in BP.CHANNELS:
        v = still[ch]
        if not v:
            continue
        floors[ch] = round(pct(v, 99.5), 4)
        print(f"  {ch:<10}{len(v):>7}{pct(v,50):>10.4f}{pct(v,95):>10.4f}"
              f"{pct(v,99):>10.4f}{pct(v,99.5):>10.4f}{max(v):>10.4f}")

    print("\n--- sanity: are the floors far BELOW real failure residuals? ---")
    print("  If a floor is comparable to what a teleport produces, it would mask")
    print("  one. Compared against the two_hand takes, which contain the")
    print("  identity mixups (spec 0.4).")
    bad = residuals("two_hand")
    print(f"  {'channel':<10}{'floor':>10}{'teleport-corpus p99':>22}{'ratio':>9}")
    for ch in BP.CHANNELS:
        if ch not in floors or not bad.get(ch):
            continue
        hi = pct(bad[ch], 99)
        r = hi / floors[ch] if floors[ch] > 0 else float("inf")
        flag = "" if r >= 3 else "   <-- TOO CLOSE"
        print(f"  {ch:<10}{floors[ch]:>10.4f}{hi:>22.4f}{r:>9.1f}{flag}")

    print("\n--- paste into block_predictor.FLOOR ---")
    print("FLOOR = {")
    for ch in BP.CHANNELS:
        if ch in floors:
            print(f'    "{ch}": {floors[ch]},')
    print("}")
    print("=" * 78)


if __name__ == "__main__":
    main()
