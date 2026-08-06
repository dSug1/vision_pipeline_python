"""B7 on LIVE data: what the gate did to the CUBE, and which knob to turn.

Reads a take recorded by `debug_prediction.bat` (LiveBlockPredictionDebug.py
--record) and does two things the corpus harnesses cannot:

  PART 1  WHAT ACTUALLY HAPPENED, from the recorded decisions and both recorded
          cube tracks -- including real elapsed-time latency, because this
          recorder stores true perf_counter stamps (N17: never a synthesised
          33 ms step).

  PART 2  ⭐ REPLAY SWEEP OVER THE DEGREES OF FREEDOM. The take stores RAW
          landmarks, so the whole pipeline -- block state, gate, corrected
          landmarks, and the UNCHANGED cube logic from LiveSnapDebug -- is
          re-run offline under any configuration, deterministically. That gives
          the metric the offline corpus never had: what the CUBE does.

⭐ WHY THE CUBE-LEVEL METRIC IS THE POINT. §16.7 judged B7 on palm channels,
because the corpus has no cube in it. But the owner's complaint was never about
palm channels -- it is about the cube jumping. A gate can improve the palm and
still make the cube worse (the coast/rejoin transient does exactly that), and
only a take with cubes in it can show which way that goes.

⚠ Same binding rules as every harness here:
  * CLASSIFY what was discarded, never merely count it (§0.18).
  * Reversals labelled NON-CAUSALLY from raw velocity sign changes.
  * ⚠ Those labels are CONTAMINATED -- a teleport also produces two sign
    changes -- so every reversal ratio is an UPPER BOUND (§16.7).
  * Latency in MILLISECONDS, from the recorded timestamps, never in frames.

    .venv/Scripts/python.exe analysis/b7_live_ab.py [--session DIR] [--quick]
"""
import argparse
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import LiveBlockPredictionDebug as T
import LiveSnapDebug as LSD
from Resources import hand_blocks as HB
from Resources import block_predictor as BP
from Resources import confirmation_gate as CG

CAPTURE_ROOT = T.CAPTURE_ROOT
STILL_PALM_MOVE = 1.5          # px/frame -- "the hand is stationary"
CLASSIFY_LOOKAHEAD = 6


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def ratio(a, b):
    return (a / b) if b else (float("inf") if a else float("nan"))


# --------------------------------------------------------------------------
def load(session, trim=True):
    """Load a take, applying its DOCUMENTED trim.

    ⚠ The trim lives in meta.json (`analysis_trim`), never in the JSONL: the
    recording stays raw and intact, and every harness applies the identical
    window. An operator always spends the first seconds moving to grab the cube
    and the last seconds winding down; both are real hand motion that is not the
    condition under test, and leaving them in silently contaminates whichever
    metric happens to be sensitive to them.
    """
    with open(os.path.join(session, "meta.json"), encoding="utf-8-sig") as f:
        meta = json.load(f)
    recs = [json.loads(l) for l in
            open(os.path.join(session, "raw_landmarks.jsonl"), encoding="utf-8")
            if l.strip()]
    tr = meta.get("analysis_trim") or {}
    head, tail = float(tr.get("head_s", 0.0)), float(tr.get("tail_s", 0.0))
    if trim and recs and (head > 0 or tail > 0):
        t0, t1 = recs[0]["tCapture"], recs[-1]["tCapture"]
        lo, hi = t0 + head * 1000.0, t1 - tail * 1000.0
        kept = [r for r in recs if lo <= r["tCapture"] <= hi]
        if kept:
            meta = dict(meta)
            meta["_trimmed_from"] = len(recs)
            meta["frames"] = len(kept)
            meta["actual_span_s"] = round((kept[-1]["tCapture"] - kept[0]["tCapture"]) / 1000.0, 3)
            recs = kept
    return meta, recs


def hand_runs(recs):
    """Per-hand contiguous runs: [(label, [(frame_rec, hand_rec), ...]), ...].

    Run-break on a frame-index gap, exactly as `audit_jump_provenance.build_v2`
    does -- a re-acquisition must never be judged against the old track.
    """
    cur, last_idx, out = {}, {}, []
    for rec in recs:
        for h in rec.get("hands") or []:
            lab = h["label"]
            if lab in last_idx and last_idx[lab] != rec["frame"] - 1:
                if cur.get(lab):
                    out.append((lab, cur[lab]))
                cur[lab] = []
            last_idx[lab] = rec["frame"]
            cur.setdefault(lab, []).append((rec, h))
    for lab, seq in cur.items():
        if seq:
            out.append((lab, seq))
    return out


def reversals(vals, ch):
    """NON-CAUSAL: indices where this channel's raw velocity changes sign, with
    both velocities above the channel's derived noise floor."""
    floor = BP.FLOOR.get(ch, 0.0)
    idx = set()
    for k in range(2, len(vals)):
        a, b, c = vals[k - 2], vals[k - 1], vals[k]
        if a is None or b is None or c is None:
            continue
        v1, v2 = b - a, c - b
        if abs(v1) > floor and abs(v2) > floor and v1 * v2 < 0:
            idx.add(k)
    return idx


def classify(vals, f, ch):
    """Out-and-back verdict at a FIXED 6-frame lookahead, independent of L.
    ⚠ Circular for verdict_test='p_pre' (see b7_eval.py's header); honest for
    'pred' and 'self', which do not share this expression."""
    dist = ((lambda a, b: None if a is None or b is None else abs(a - b))
            if ch != BP.QUAT_CHANNEL else BP._qangle)
    if f < 1 or f >= len(vals):
        return None
    out = dist(vals[f], vals[f - 1])
    if out is None or out < 1e-9:
        return None
    backs = [d for d in (dist(vals[k], vals[f - 1])
                         for k in range(f + 1, min(len(vals), f + 1 + CLASSIFY_LOOKAHEAD)))
             if d is not None]
    if not backs:
        return None
    r = min(backs) / out
    return "teleport" if r < 0.5 else ("ambiguous" if r < 0.9 else "real")


# --------------------------------------------------------------------------
def part1(meta, recs):
    print("=" * 78)
    print("PART 1 -- WHAT HAPPENED LIVE")
    print("=" * 78)
    fps = meta.get("measured_fps") or 24.0
    n = len(recs)
    print(f"  take        : {meta.get('sequence')}  {meta.get('note') or ''}")
    print(f"  frames      : {n}  over {meta.get('actual_span_s')} s  "
          f"-> {fps} fps measured (N10)")
    print(f"  gate config : {json.dumps(meta.get('gate', {}))}")

    hand_frames = sum(len(r.get("hands") or []) for r in recs)
    flag = disc = conf = forced = 0
    hold_runs, cur_hold = [], 0
    for r in recs:
        for h in r.get("hands") or []:
            g = h["gate"]
            flag += len(g["flagged"]); disc += len(g["discarded"])
            conf += len(g["confirmed"]); forced += len(g["forced"])
        if r.get("s3_hold"):
            cur_hold += 1
        elif cur_hold:
            hold_runs.append(cur_hold); cur_hold = 0
    if cur_hold:
        hold_runs.append(cur_hold)

    print(f"\n  hand-frames {hand_frames};  flags {flag}, discarded {disc}, "
          f"confirmed {conf}, force-accepts {forced}")
    if hold_runs:
        ms = [h * 1000.0 / fps for h in hold_runs]
        print(f"  S3 HOLD episodes {len(hold_runs)}: median {pct(ms,50):.0f} ms, "
              f"p95 {pct(ms,95):.0f} ms, max {max(ms):.0f} ms "
              f"({100.0*sum(hold_runs)/max(1,n):.1f}% of frames)")
    else:
        print("  S3 HOLD episodes 0 -- the gate never withheld a grab decision")

    # --- the cube tracks, which is what the operator actually watched ---
    print("\n  ⭐ CUBE BEHAVIOUR, raw arm vs gated arm")
    print(f"  {'cube':<8}{'arm':<8}{'steps':>7}{'p50':>9}{'p95':>9}{'max':>9}"
          f"{'still p95':>11}{'still max':>11}")
    for name in (recs[0]["cubes_raw"].keys() if recs else ()):
        for arm in ("cubes_raw", "cubes_gated"):
            steps, still = [], []
            prev = None
            prev_palm = None
            for r in recs:
                c = r[arm][name]
                palm = None
                if r.get("hands"):
                    palm = HB.palm_position(r["hands"][0]["landmarks"])
                if prev is not None:
                    d = math.dist(c["pos"], prev)
                    steps.append(d)
                    if (prev_palm and palm
                            and math.dist(palm, prev_palm) < STILL_PALM_MOVE):
                        still.append(d)
                prev, prev_palm = c["pos"], palm
            print(f"  {name:<8}{arm[6:]:<8}{len(steps):>7}{pct(steps,50):>9.2f}"
                  f"{pct(steps,95):>9.2f}{max(steps or [0]):>9.2f}"
                  f"{pct(still,95):>11.2f}{max(still or [0]):>11.2f}")

    # --- did the two arms ever hold different cubes? ---
    diff_owner = sum(1 for r in recs
                     for k in r["cubes_raw"]
                     if r["cubes_raw"][k]["owner"] != r["cubes_gated"][k]["owner"])
    sep = []
    for r in recs:
        for k in r["cubes_raw"]:
            sep.append(math.dist(r["cubes_raw"][k]["pos"], r["cubes_gated"][k]["pos"]))
    print(f"\n  arms disagreed on ownership on {diff_owner} cube-frames "
          f"(S3 delaying or preventing a grab)")
    print(f"  raw-vs-gated cube separation: p50 {pct(sep,50):.2f}  "
          f"p95 {pct(sep,95):.2f}  max {max(sep or [0]):.2f} px")
    return fps


# --------------------------------------------------------------------------
def replay(recs, fps, gate_factory, use_gate=True,
           channels=T.LANDMARK_CHANNELS):
    """Re-run the FULL pipeline offline: block state -> gate -> corrected
    landmarks -> the unchanged cube logic. Deterministic, so a config sweep is
    an exact A/B rather than a second live session."""
    res_meta = recs[0]
    w, h = 640, 480
    state = LSD.CubeState(window_size=(w, h))
    gates = {}
    seen_last = {}
    out = {"flag": 0, "disc": 0, "conf": 0, "forced": 0, "hold_frames": 0,
           "cube_steps": [], "cube_still": [], "cls": {"teleport": 0, "ambiguous": 0,
                                                       "real": 0},
           "rev": [0, 0], "non": [0, 0], "ep_rev": [0, 0], "ep_non": [0, 0],
           "snaps": 0, "track": []}

    # Per-RUN channel series + non-causal reversal labels, computed up front.
    # ⚠ Keyed by run, not by label: a label with two runs would otherwise have
    # its first run's series silently overwritten by its second, and the frame
    # indices would then point into the wrong stream entirely.
    series, revs, run_of = {}, {}, {}
    for run_id, (lab, seq) in enumerate(hand_runs(recs)):
        for i, (r, _hh) in enumerate(seq):
            run_of[(lab, r["frame"])] = (run_id, i)
        for ch in BP.SCALAR_CHANNELS:
            vals = []
            for _r, hh in seq:
                st = HB.block_state(hh["landmarks"], hh["world_landmarks"])
                sc = BP.BlockPredictor._scalars(st) if st else {}
                vals.append(sc.get(ch))
            series.setdefault(run_id, {})[ch] = vals
            revs.setdefault(run_id, {})[ch] = reversals(vals, ch)
    run_len = {rid: len(next(iter(s.values()))) for rid, s in series.items()}
    # discarded frame indices per (run, channel), so criterion 1 is tallied over
    # the frames actually thrown away -- the SAME accounting as b7_eval.py, or
    # the live and corpus numbers are not comparable.
    discarded_at = {}

    pos_in_run = {}
    prev_owner = {}
    prev_cube, prev_palm = {}, None
    open_ep = {}
    last_frame = {}

    for r in recs:
        data = {hd: None for hd in LSD.TRACKED_HANDS}
        holds = set()
        for hh in r.get("hands") or []:
            lab = hh["label"]
            if lab in last_frame and last_frame[lab] != r["frame"] - 1:
                pos_in_run[lab] = 0
                if lab in gates:
                    gates[lab].reset()
            last_frame[lab] = r["frame"]
            k = pos_in_run.get(lab, 0)
            pos_in_run[lab] = k + 1
            rid = run_of.get((lab, r["frame"]), (None, k))[0]

            px, world = [tuple(p) for p in hh["landmarks"]], \
                        [tuple(v) for v in hh["world_landmarks"]]
            if not use_gate:
                data[lab] = {"pixel_landmarks": px, "world_landmarks": world,
                             "thumb_outward": hh["thumb_outward"]}
                continue
            st = HB.block_state(px, world)
            if st is None or st.get("position") is None:
                data[lab] = {"pixel_landmarks": px, "world_landmarks": world,
                             "thumb_outward": hh["thumb_outward"]}
                continue
            g = gates.setdefault(lab, gate_factory())
            res = g.update(st)
            out["flag"] += len(res["flagged"]); out["disc"] += len(res["discarded"])
            out["conf"] += len(res["confirmed"]); out["forced"] += len(res["forced"])
            for ch in res["flagged"]:
                open_ep[(lab, ch)] = k
            for ch in res["discarded"] + res["confirmed"]:
                f0 = open_ep.pop((lab, ch), max(0, k - g.lag))
                if ch in BP.SCALAR_CHANNELS and rid in revs:
                    b = (out["ep_rev"] if f0 in revs[rid][ch] else out["ep_non"])
                    b[0] += 1
                    if ch in res["discarded"]:
                        b[1] += 1
                if ch in res["discarded"]:
                    if rid in series:
                        v = classify(series[rid].get(ch, []), f0, ch)
                        if v:
                            out["cls"][v] += 1
                    # the frames actually thrown away are F .. F+L-1
                    discarded_at.setdefault((rid, ch), set()).update(range(f0, k))
            if any(not res["valid"][c] for c in ("pos_x", "pos_y", "scale", "quat")):
                holds.add(lab)
            gpx, gworld = T.apply_gate_to_landmarks(px, world, st, res["output"],
                                                    channels=channels)
            data[lab] = {"pixel_landmarks": gpx, "world_landmarks": gworld,
                         "thumb_outward": hh["thumb_outward"]}

        out["hold_frames"] += 1 if holds else 0
        LSD.update_hands(state, data, snap_blocked=holds)

        palm = (HB.palm_position(r["hands"][0]["landmarks"])
                if r.get("hands") else None)
        for name, c in state.cubes.items():
            if name in prev_cube:
                d = math.dist(c.position, prev_cube[name])
                out["cube_steps"].append(d)
                if palm and prev_palm and math.dist(palm, prev_palm) < STILL_PALM_MOVE:
                    out["cube_still"].append(d)
            if prev_owner.get(name) is None and c.owner is not None:
                out["snaps"] += 1
            prev_cube[name] = c.position
            prev_owner[name] = c.owner
        prev_palm = palm

    # Criterion 1, tallied over the frames that were actually discarded and
    # bucketed by the non-causal reversal labels -- b7_eval.py's accounting.
    if use_gate:
        for rid, chans in revs.items():
            for ch in BP.SCALAR_CHANNELS:
                dis = discarded_at.get((rid, ch), ())
                for k in range(run_len.get(rid, 0)):
                    bucket = out["rev"] if k in chans[ch] else out["non"]
                    bucket[0] += 1
                    if k in dis:
                        bucket[1] += 1
    return out


def report_replay(label, o, fps, lag):
    rev_n, rev_d = o["rev"]
    non_n, non_d = o["non"]
    rr, nr = 100.0 * ratio(rev_d, rev_n), 100.0 * ratio(non_d, non_n)
    er, en = o["ep_rev"], o["ep_non"]
    tot = sum(o["cls"].values())
    print(f"  {label:<26}{o['flag']:>6}{o['disc']:>7}"
          f"{rr:>8.2f}%{ratio(rr, nr):>8.2f}x"
          f"{100.0*ratio(er[1],er[0]):>8.1f}%{100.0*ratio(en[1],en[0]):>8.1f}%"
          f"{(100.0*o['cls']['teleport']/tot if tot else float('nan')):>8.1f}%"
          f"{pct(o['cube_steps'],95):>8.2f}{max(o['cube_steps'] or [0]):>8.2f}"
          f"{max(o['cube_still'] or [0]):>9.2f}"
          f"{1000.0*lag/fps:>8.0f}{o['snaps']:>6}")


def main():
    ap = argparse.ArgumentParser(description="B7 A/B on a live-recorded take.")
    ap.add_argument("--session", default=None,
                    help="recording dir (default: newest under the capture root)")
    ap.add_argument("--root", default=CAPTURE_ROOT)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    session = args.session
    if session is None:
        cands = sorted(glob.glob(os.path.join(args.root, "*")))
        cands = [c for c in cands if os.path.exists(os.path.join(c, "meta.json"))]
        if not cands:
            raise SystemExit(f"No recordings under {args.root}. "
                             "Run debug_prediction.bat first (it records by default).")
        session = cands[-1]
    print(f"session: {session}\n")
    meta, recs = load(session)
    if not recs:
        raise SystemExit("Recording has no frames.")

    fps = part1(meta, recs)

    print("\n" + "=" * 78)
    print("PART 2 -- REPLAY SWEEP: which degree of freedom actually moves anything")
    print("=" * 78)
    print("  Same take, same frames, full pipeline re-run per config.")
    print(f"  {'config':<26}{'flags':>6}{'disc':>7}{'revDisc':>9}{'ratio':>8}"
          f"{'ep@rev':>8}{'ep@else':>8}{'tele%':>8}{'cubP95':>8}{'cubMax':>8}"
          f"{'stillMx':>9}{'lat ms':>8}{'snap':>6}")

    base = replay(recs, fps, None, use_gate=False)
    print(f"  {'RAW (no gate)':<26}{0:>6}{0:>7}{'-':>9}{'-':>8}{'-':>8}{'-':>8}{'-':>8}"
          f"{pct(base['cube_steps'],95):>8.2f}{max(base['cube_steps'] or [0]):>8.2f}"
          f"{max(base['cube_still'] or [0]):>9.2f}{0:>8}{base['snaps']:>6}")

    B8 = CG.FIT_KWARGS
    configs = [
        ("B7 shipped default", dict()),
        ("L=3", dict(lag=3)),
        ("L=4", dict(lag=4)),
        ("L=6", dict(lag=6)),
        ("verdict=self", dict(verdict_test="self")),
        ("verdict=p_pre", dict(verdict_test="p_pre")),
        ("coast=extrapolate", dict(coast_mode="extrapolate")),
        ("coast=damped", dict(coast_mode="damped")),
        ("blend=1", dict(blend=1)),
        ("blend=5", dict(blend=5)),
        ("reject_z=2.5", dict(reject_z=2.5)),
        ("reject_z=4.0", dict(reject_z=4.0)),
        ("reject_z=5.0", dict(reject_z=5.0)),
        ("fit=B3'' order2", dict(fit_kwargs={})),
        ("fit=order1 hl=3", dict(fit_kwargs={"order": 1, "weighting": "exp",
                                             "half_life": 3.0})),
        ("window=5", dict(window=5)),
        ("window=11", dict(window=11)),
        ("accel_unc=0", dict(accel_uncertainty=0.0)),
        ("accel_unc=2", dict(accel_uncertainty=2.0)),
        ("ambig=RETURNED", dict(ambiguous_is_coherent=False)),
        # ⭐ THE CHANNEL->LANDMARK MASK -- not one of the gate's parameters at
        # all, but WHICH gated channels are realised as landmark positions.
        # ⚠ There is deliberately NO "+scale" row: that path was measured to
        # amplify by up to 35x (a collapsing denominator, see
        # LiveBlockPredictionDebug.LANDMARK_CHANNELS) and has been REMOVED from
        # the code rather than left switchable. Passing "scale" in this tuple now
        # does nothing, so a row claiming to reproduce the bug would be a lie --
        # the bug's numbers live in the LANDMARK_CHANNELS comment instead.
        ("mask: pos+quat", dict(), ("position", "quat")),
        ("mask: pos only", dict(), ("position",)),
        ("mask: quat only", dict(), ("quat",)),
        ("mask: pos+quat, L=4", dict(lag=4), ("position", "quat")),
        ("mask: pos+quat, z=4", dict(reject_z=4.0), ("position", "quat")),
    ]
    if args.quick:
        configs = configs[:6]
    for entry in configs:
        label, kw = entry[0], dict(entry[1])
        mask = entry[2] if len(entry) > 2 else T.LANDMARK_CHANNELS
        kw.setdefault("fit_kwargs", B8)
        o = replay(recs, fps, lambda kw=kw: CG.ConfirmationGate(**kw), channels=mask)
        report_replay(label, o, fps, kw.get("lag", CG.LAG))

    print("\n" + "=" * 78)
    print("READING IT")
    print("=" * 78)
    print("  revDisc/ratio  criterion 1 -- reversal channel-frames discarded, and")
    print("                 the ratio against elsewhere. Target <= 1.5x.")
    print("  ep@rev/ep@else the VERDICT TEST alone, flag rate divided out: of the")
    print("                 flags raised, what fraction was thrown away. Below 1.0")
    print("                 means deferral is protecting reversals.")
    print("  tele%          criterion 2, non-causal out-and-back. ⚠ circular for")
    print("                 verdict=p_pre only.")
    print("  cubMax/stillMx ⭐ criterion 3 measured ON THE CUBE, which the corpus")
    print("                 harness could not do. Compare against RAW, above.")
    print("  snap           grabs taken. Fewer than RAW means S3 blocked a grab.")
    print("=" * 78)


if __name__ == "__main__":
    main()
