"""M4 frame-gate A/B under A10 (queue item 1.6).

Every module must show a measured improvement on identical recorded input or be
reverted. This measures BOTH families, because each alone is gameable -- the
lesson 0.12/analysis README record from the orientation work:

  * EXCURSIONS: large position innovations surviving into the output stream.
    A gate that rejects everything scores perfectly here.
  * TRACKING COST: how far the gated output sits from the raw measurement on
    frames where the raw is TRUSTWORTHY (anatomically valid AND small
    innovation). A gate that does nothing scores perfectly here.

A gate is only worth shipping if it improves the first without meaningfully
damaging the second. Attempt 1 of the orientation filter looked like a triumph
on excursions (>60: 589 -> 0) while sitting 37 deg from the truth.

Streams are built as build_v2() builds them (binding rule, spec 0.15).

    .venv/Scripts/python.exe analysis/m4_gate_ab.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import frame_gate as FG
from Resources import hand_anatomy

EXCURSION_LEVELS = (0.5, 1.0, 2.0)
TRUSTWORTHY_INNOVATION = 0.2      # raw is believable here, so the gate has no
                                  # excuse to disagree with it


def verify_primitives():
    """frame_gate defines centroid/width locally (see its docstring). Prove they
    agree with hand_identity's, or the gate is judging a different quantity from
    the one DR-1 associates on."""
    n = agree_c = agree_w = 0
    for _name, frames in AJP.SESSIONS:
        for rec in frames:
            for h in (rec.get("hands") or []):
                pts = [tuple(p) for p in h["landmarks"]]
                a, b = AJP.palm_centroid(pts), FG.palm_geometry_centroid(pts)
                wa, wb = AJP.palm_width(pts), FG.palm_geometry_width(pts)
                if a is None or b is None:
                    continue
                n += 1
                agree_c += math.dist(a, b) < 1e-9
                agree_w += abs((wa or 0) - (wb or 0)) < 1e-9
    ok = n and agree_c == n and agree_w == n
    print(f"  [{'PASS' if ok else 'FAIL'}] centroid/width match hand_identity: "
          f"{agree_c}/{n} centroid, {agree_w}/{n} width")
    return bool(ok)


def run(gate_kwargs=None):
    raw_exc = {t: 0 for t in EXCURSION_LEVELS}
    gated_exc = {t: 0 for t in EXCURSION_LEVELS}
    n_frames = n_rejected = n_forced = 0
    track_err = []
    reasons = {}

    for _name, frames in AJP.SESSIONS:
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        gates, last_idx = {}, {}
        raw_prev, raw_prev2 = {}, {}
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
            assigned = trk.update(obs_list)
            for h, lab in zip(keep, assigned):
                pts = [tuple(p) for p in h["landmarks"]]
                world = [tuple(v) for v in h["world_landmarks"]] if h.get("world_landmarks") else None
                cen = AJP.palm_centroid(pts)
                wid = AJP.palm_width(pts)
                if cen is None or not wid or wid <= 1e-6:
                    continue

                broke = lab in last_idx and last_idx[lab] != i - 1
                if lab not in gates or broke:
                    gates[lab] = FG.FrameGate(**(gate_kwargs or {}))
                    raw_prev.pop(lab, None)
                    raw_prev2.pop(lab, None)
                last_idx[lab] = i
                gate = gates[lab]

                # --- RAW baseline excursion (no gate at all) ---
                p1, p2 = raw_prev.get(lab), raw_prev2.get(lab)
                if p1 is not None and p2 is not None:
                    pv = (p1[0] - p2[0], p1[1] - p2[1])
                    pred = (p1[0] + pv[0], p1[1] + pv[1])
                    innov_raw = math.dist(cen, pred) / wid
                    for t in EXCURSION_LEVELS:
                        if innov_raw > t:
                            raw_exc[t] += 1
                else:
                    innov_raw = None

                # --- GATED ---
                pred_before = gate.predicted_position()
                res = gate.update(pts, world)
                n_frames += 1
                if res["accepted"]:
                    out = cen
                else:
                    out = pred_before if pred_before is not None else cen
                    n_rejected += 1
                if res["forced"]:
                    n_forced += 1
                for r in res["reasons"]:
                    key = r.split(" ")[0] + (" " + r.split(" ")[1]
                                             if r.startswith("palm") else "")
                    reasons[key] = reasons.get(key, 0) + 1

                # gated excursion: how far the OUTPUT moved vs its own prediction
                if pred_before is not None:
                    innov_out = math.dist(out, pred_before) / wid
                    for t in EXCURSION_LEVELS:
                        if innov_out > t:
                            gated_exc[t] += 1

                # tracking cost, on frames where raw is trustworthy
                if (innov_raw is not None and innov_raw < TRUSTWORTHY_INNOVATION
                        and (world is None or hand_anatomy.evaluate(world)["valid"])):
                    track_err.append(math.dist(out, cen) / wid)

                raw_prev2[lab] = raw_prev.get(lab)
                raw_prev[lab] = cen

    return raw_exc, gated_exc, n_frames, n_rejected, n_forced, track_err, reasons


def main():
    print("=" * 78)
    print("M4 frame gate -- A/B under A10 (queue item 1.6)")
    print("=" * 78)
    print("\n--- primitive parity check ---")
    if not verify_primitives():
        raise SystemExit("frame_gate's centroid/width disagree with hand_identity's")

    raw_exc, gated_exc, n, rej, forced, track, reasons = run()

    print(f"\nhand-frames judged {n}")
    print(f"rejected           {rej}  ({100.0*rej/n:.2f}%)")
    print(f"  of which FORCED accepts (anti-cascade cap hit)  {forced}")

    print("\n--- METRIC 1: position excursions surviving into the output ---")
    print(f"  {'threshold':>12}{'raw':>10}{'gated':>10}{'removed':>12}")
    for t in EXCURSION_LEVELS:
        r, g = raw_exc[t], gated_exc[t]
        rem = f"{100.0*(r-g)/r:.0f}%" if r else "n/a"
        print(f"  >{t:>10.1f}{r:>10}{g:>10}{rem:>12}")

    print("\n--- METRIC 2: tracking cost on TRUSTWORTHY frames ---")
    print(f"  (raw innovation < {TRUSTWORTHY_INNOVATION} AND anatomically valid)")
    if track:
        s = sorted(track)
        mean = sum(track) / len(track)
        print(f"  n={len(track)}  mean={mean:.5f}  p99={s[int(0.99*(len(s)-1))]:.5f}  "
              f"max={max(track):.5f}   (palm widths from raw)")
        print(f"  -> the gate disagrees with a trustworthy measurement by "
              f"{mean*100:.3f}% of a palm width on average")
    else:
        print("  (no trustworthy frames?)")

    print("\n--- which cue fired ---")
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<26}{v:>8}")

    # ---- ABLATION: does every cue earn its keep? ----
    # Standing project rule: no heuristic pile-up; a filter earns its place only
    # with measured, non-marginal impact. INF disables a cue without changing
    # any other code path.
    INF = float("inf")
    print("\n--- ABLATION: each cue disabled in turn (>1.0 excursions) ---")
    print(f"  {'configuration':<28}{'rejects':>9}{'>1.0':>8}{'removed':>10}{'trk_mean':>11}")
    base_removed = 100.0 * (raw_exc[1.0] - gated_exc[1.0]) / raw_exc[1.0]
    print(f"  {'ALL CUES':<28}{rej:>9}{gated_exc[1.0]:>8}"
          f"{base_removed:>9.0f}%{(sum(track)/len(track)):>11.5f}")
    # Bone deviation and M3a tightening were ablated here on 2026-08-04, both
    # failed to earn their keep, and are now GONE from frame_gate.py -- so they
    # can no longer appear as rows. The measured table is preserved in that
    # module's docstring so the null result is not retried blindly (A10).
    for label, kw in (
        ("no position innovation", {"innovation_max": INF}),
        ("no palm-width collapse", {"width_log_ratio_max": INF}),
        ("looser cap (4 frames)", {"max_consecutive_rejections": 4}),
        ("tighter cap (1 frame)", {"max_consecutive_rejections": 1}),
    ):
        _r, g, _n, rj, _f, tr, _rs = run(kw)
        rem = 100.0 * (raw_exc[1.0] - g[1.0]) / raw_exc[1.0]
        print(f"  {label:<28}{rj:>9}{g[1.0]:>8}{rem:>9.0f}%"
              f"{(sum(tr)/len(tr) if tr else 0):>11.5f}")

    print("\n" + "=" * 78)
    print("A10 VERDICT needs BOTH: excursions materially down AND tracking cost")
    print("near zero. A gate that improves one at the other's expense is the")
    print("over-damping trap 0.12 recorded -- report both or the result is void.")
    print("=" * 78)


if __name__ == "__main__":
    main()
