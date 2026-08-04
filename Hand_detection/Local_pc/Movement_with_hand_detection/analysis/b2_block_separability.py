"""B2 -- do the BLOCK channels separate teleports from fast real movement?

â­ THE MEASUREMENT THAT DECIDES PHASE B. Item 1.6 already built the
single-channel version of the owner's outlier idea and it FAILED: it rejected
~4 real fast movements per teleport caught, at every threshold of every cue,
because at this input envelope a teleport and a fast real movement produce the
SAME position innovation (spec 0.17).

When two populations overlap in the measured quantity, no threshold separates
them -- and neither does a probability distribution over that quantity. So the
thing that could rescue the idea is NOT a better estimator, it is MORE CHANNELS:

    palm displacement   (what 1.6 had, and it is not enough on its own)
    palm quaternion delta
    palm scale ratio
    ARC DISCONTINUITY   <- the new channel, and the hypothesis

THE HYPOTHESIS (spec 16 / queue B6): the recorded Object Jump is MediaPipe
reporting a DIFFERENT PHYSICAL HAND under the same label (14.1.4). A different
hand is in a different POSE, so a teleport should show a large palm displacement
TOGETHER WITH a discontinuous jump in the arc vector, whereas genuine fast
motion shows large displacement with CONTINUOUS arcs.

âš  LABELLING IS INDEPENDENT AND NON-CAUSAL, ON PURPOSE. Frames are labelled by
the out-and-back test from `m4_rejection_audit.py` -- did the hand RETURN to its
prior trajectory within 6 frames (teleport) or CONTINUE (real movement)? That
uses future frames, which a live gate cannot, precisely so the labels are not
derived from the causal channels being tested. Testing a channel against labels
made from that same channel would be circular and would prove nothing.

Streams are built as build_v2() builds them (binding rule, spec 0.15).

    .venv/Scripts/python.exe analysis/b2_block_separability.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import hand_blocks as HB
from Resources import palm_geometry as _PG


def _edge_on(pixel_landmarks):
    try:
        return _PG.edge_on_measure(pixel_landmarks)
    except Exception:
        return None

LOOKAHEAD = 6
DISPLACEMENT_GATE = 0.5      # palm widths: only judge frames big enough to matter
TELEPORT_MAX_RETURN = 0.5    # came back  -> teleport
REAL_MIN_RETURN = 0.9        # kept going -> real movement


def verify_primitives():
    """hand_blocks defines palm centroid/width locally (it lives across the
    socket from hand_identity). Prove they agree, or the block view is measuring
    a different hand from the one DR-1 associates."""
    n = ok_c = ok_w = 0
    for _name, frames in AJP.SESSIONS:
        for rec in frames:
            for h in (rec.get("hands") or []):
                pts = [tuple(p) for p in h["landmarks"]]
                a, b = AJP.palm_centroid(pts), HB.palm_position(pts)
                wa, wb = AJP.palm_width(pts), HB.palm_scale(pts)
                if a is None or b is None:
                    continue
                n += 1
                ok_c += math.dist(a, b) < 1e-9
                ok_w += abs((wa or 0) - (wb or 0)) < 1e-9
    good = n and ok_c == n and ok_w == n
    print(f"  [{'PASS' if good else 'FAIL'}] palm centroid/scale match "
          f"hand_identity: {ok_c}/{n}, {ok_w}/{n}")
    return bool(good)


def runs():
    """v2 streams of per-frame block states, per contiguous run."""
    for name, frames in AJP.SESSIONS:
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
                st = HB.block_state([tuple(p) for p in h["landmarks"]],
                                    [tuple(v) for v in h["world_landmarks"]])
                if st is None or st["position"] is None or not st["scale"]:
                    continue
                # edge-on measure, for the N12 band split below
                st["_eo"] = _edge_on([tuple(p) for p in h["landmarks"]])
                if lab in last_idx and last_idx[lab] != i - 1:
                    if cur.get(lab):
                        out.append(cur[lab])
                    cur[lab] = []
                last_idx[lab] = i
                cur.setdefault(lab, []).append(st)
        for seq in cur.values():
            if seq:
                out.append(seq)
        for seq in out:
            yield name, seq


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def overlap_rate(tele, real):
    """Fraction of REAL frames that exceed the teleports' 10th percentile.

    A channel only helps if most teleports sit above most real movements. This
    reports the false-positive cost of a threshold set low enough to catch 90%
    of teleports -- the honest way round, given 1.6 failed by catching teleports
    at enormous cost in real movements.
    """
    if len(tele) < 5 or not real:
        return None, None
    thr = pct(tele, 10)
    fp = sum(1 for v in real if v >= thr) / len(real)
    return thr, fp


def main():
    print("=" * 78)
    print("B2 -- do the BLOCK channels separate teleports from fast real motion?")
    print("=" * 78)
    print("\n--- primitive parity ---")
    if not verify_primitives():
        raise SystemExit("hand_blocks disagrees with hand_identity")

    chans = {"palm displacement": ([], []), "quaternion delta": ([], []),
             "scale log-ratio": ([], []), "ARC discontinuity": ([], [])}
    n_tele = n_real = 0

    for _name, seq in runs():
        for j in range(1, len(seq) - 1):
            a, b = seq[j - 1], seq[j]
            w = a["scale"]
            if not w or w < 1e-6:
                continue
            disp = math.dist(b["position"], a["position"]) / w
            if disp < DISPLACEMENT_GATE:
                continue                      # too small to be either population
            # --- independent, non-causal label ---
            back = min(math.dist(a["position"], seq[k]["position"])
                       for k in range(j + 1, min(len(seq), j + 1 + LOOKAHEAD)))
            out = math.dist(a["position"], b["position"])
            if out < 1e-9:
                continue
            ratio = back / out
            if ratio < TELEPORT_MAX_RETURN:
                idx = 0
                n_tele += 1
            elif ratio > REAL_MIN_RETURN:
                idx = 1
                n_real += 1
            else:
                continue                      # ambiguous, excluded

            chans["palm displacement"][idx].append(disp)
            qd = HB.quat_angle_between(a["quaternion"], b["quaternion"])
            if qd is not None:
                chans["quaternion delta"][idx].append(qd)
            if b["scale"] and a["scale"]:
                chans["scale log-ratio"][idx].append(
                    abs(math.log(b["scale"] / a["scale"])))
            ad = HB.arc_distance(a["arcs"], b["arcs"])
            if ad is not None:
                chans["ARC discontinuity"][idx].append(ad)

    print(f"\nlabelled transitions above {DISPLACEMENT_GATE} palm widths: "
          f"{n_tele} teleport, {n_real} real movement")
    if n_tele < 5:
        print("âš  too few teleports to conclude anything -- report and stop.")

    print(f"\n  {'channel':<22}{'set':>6}{'n':>6}{'p10':>9}{'p50':>9}"
          f"{'p90':>9}")
    for name, (tele, real) in chans.items():
        for label, v in (("tele", tele), ("real", real)):
            if v:
                print(f"  {name if label=='tele' else '':<22}{label:>6}{len(v):>6}"
                      f"{pct(v,10):>9.3f}{pct(v,50):>9.3f}{pct(v,90):>9.3f}")

    print("\n--- SEPARATION: threshold catching 90% of teleports, and its cost ---")
    print(f"  {'channel':<22}{'threshold':>11}{'real flagged':>14}")
    for name, (tele, real) in chans.items():
        thr, fp = overlap_rate(tele, real)
        if thr is None:
            print(f"  {name:<22}{'--':>11}{'--':>14}")
            continue
        print(f"  {name:<22}{thr:>11.3f}{100.0*fp:>13.1f}%")

    # ----------------------------------------------------------------------
    # N12 -- the owner's actual target, and a DIFFERENT population entirely.
    # ----------------------------------------------------------------------
    # "when the hand crosses the horizontal plane, the cube jumps slightly
    #  because the landmarks of the fingers become confused" (operator, 0.11).
    # That is a FINGER event: it barely moves the palm, so the palm-displacement
    # labelling above cannot see it at all. The question that matters for the
    # block model is therefore not "can we detect it" but "does it even reach
    # the cube" -- if position comes from the palm, confused fingers cannot move
    # anything.
    print("\n--- N12: what moves during a pitch crossing (edge-on band)? ---")
    print("  Per-frame change, split by whether the palm is edge-on.")
    from Resources import palm_geometry as PG
    bands = {"edge-on (<0.15)": ([], []), "near (0.15-0.35)": ([], []),
             "open (>0.35)": ([], [])}
    for _name, seq in runs():
        for j in range(1, len(seq)):
            a, b = seq[j - 1], seq[j]
            w = a["scale"]
            if not w or w < 1e-6:
                continue
            eo = a.get("_eo")
            if eo is None:
                continue
            key = ("edge-on (<0.15)" if eo < 0.15
                   else "near (0.15-0.35)" if eo < 0.35 else "open (>0.35)")
            disp = math.dist(b["position"], a["position"]) / w
            ad = HB.arc_distance(a["arcs"], b["arcs"])
            bands[key][0].append(disp)
            if ad is not None:
                bands[key][1].append(ad)
    print(f"  {'band':<20}{'n':>7}{'palm p50':>10}{'palm p95':>10}"
          f"{'arc p50':>10}{'arc p95':>10}")
    for k, (dis, arcs) in bands.items():
        if dis:
            print(f"  {k:<20}{len(dis):>7}{pct(dis,50):>10.3f}{pct(dis,95):>10.3f}"
                  f"{pct(arcs,50):>10.3f}{pct(arcs,95):>10.3f}")
    print("  -> Both channels degrade edge-on by a similar factor, so ARCS give")
    print("     no distinctive signature there. That is NOT the question N12 asks.")

    # ----------------------------------------------------------------------
    # THE QUESTION N12 ACTUALLY ASKS: which ANCHOR is noisier?
    # ----------------------------------------------------------------------
    # 14.1 anchors the held cube to 5 fingertips + 4 MCPs; the block model would
    # anchor it to the palm. So the decisive comparison is not "palm noise vs arc
    # noise" but the frame-to-frame stability of the two CANDIDATE ANCHOR POINTS,
    # which is what actually reaches the cube. Equal weights are used here as a
    # proxy for 14.1's inverse-distance weights -- fair for a NOISE comparison,
    # since the weights are frozen at grab and do not change frame to frame.
    print("\n--- N12 decisive: anchor stability, 14.1's 9 points vs the palm ---")
    F141 = (4, 8, 12, 16, 20, 5, 9, 13, 17)     # 5 fingertips + 4 MCPs
    bands2 = {"edge-on (<0.15)": ([], []), "near (0.15-0.35)": ([], []),
              "open (>0.35)": ([], [])}
    # recompute from raw landmark streams (the anchor needs all 21 points)
    for _name, frames in AJP.SESSIONS:
        prev = {}
        for rec in frames:
            for h in (rec.get("hands") or []):
                lab = h["handedness"]
                pts = [tuple(p) for p in h["landmarks"]]
                w = HB.palm_scale(pts)
                eo = _edge_on(pts)
                if not w or w < 1e-6 or eo is None:
                    continue
                a141 = (sum(pts[i][0] for i in F141) / len(F141),
                        sum(pts[i][1] for i in F141) / len(F141))
                apalm = HB.palm_position(pts)
                p = prev.get(lab)
                prev[lab] = (a141, apalm, w)
                if p is None:
                    continue
                key = ("edge-on (<0.15)" if eo < 0.15
                       else "near (0.15-0.35)" if eo < 0.35 else "open (>0.35)")
                bands2[key][0].append(math.dist(a141, p[0]) / w)
                bands2[key][1].append(math.dist(apalm, p[1]) / w)
    print(f"  {'band':<20}{'n':>7}{'14.1 p50':>10}{'14.1 p95':>10}"
          f"{'palm p50':>10}{'palm p95':>10}")
    for k, (f9, pl) in bands2.items():
        if f9:
            print(f"  {k:<20}{len(f9):>7}{pct(f9,50):>10.3f}{pct(f9,95):>10.3f}"
                  f"{pct(pl,50):>10.3f}{pct(pl,95):>10.3f}")
    print("  -> If the 9-point anchor moves materially MORE than the palm, N12 is")
    print("     a consequence of WHERE the cube is anchored, and B4's palm anchor")
    print("     removes it at source -- no gate, no prediction, no coasting.")

    print("\n" + "=" * 78)
    print("READING THIS: 1.6's palm-displacement-only gate flagged ~4 real")
    print("movements per teleport. A channel is worth building on only if its")
    print("'real flagged' cost is MUCH lower at the same teleport recall. If ARC")
    print("discontinuity is no better than palm displacement, the two-channel")
    print("hypothesis is dead and Phase B redirects to the structural fix (B4).")
    print("=" * 78)


if __name__ == "__main__":
    main()
