"""B7 -- the confirmation gate, measured on the full perception corpus.

Extends `b3_full_eval.py` (its stream builder and its non-causal reversal
labeller are imported, not re-written, so B7's numbers are comparable to B3'''s
line by line) and follows the test protocol in
`Claude/BUILD_PREDICTION_GATE.md` 3.

    0  ⚠ DIRECTION-REVERSAL SAFETY -- run FIRST, disqualifying
    1  jitter on a still hand
    2  edge-on band
    3  back-of-hand orientation
    4  teleport, CLASSIFIED not counted
    5  tracking cost on frames the raw deserves belief
    6  latency, in MILLISECONDS

⭐ THE ONE MEASUREMENT DESIGN DECISION THAT MATTERS HERE, stated up front so the
numbers cannot be read the flattering way:

    B7 does not reduce FLAGS. It cannot -- it flags on the same residual test
    B3'' used. What it changes is what a flag COSTS. So this harness reports two
    different rates at reversals and never conflates them:

      FLAG rate     the measurement is DEFERRED: output coasts on the prediction
                    for L frames, then the truth is restored. Cost = LATENCY.
                    Comparable to B3'''s 11.65% / 1.57% / 7.43x.
      DISCARD rate  the measurement is THROWN AWAY and never enters the fit.
                    Cost = a lost real movement. THIS is the quantity the
                    acceptance criterion (<= 1.5x) is about.

    Reporting only the discard ratio would be the same trick as item 1.6's
    "excursions removed" -- a metric that cannot tell removing the failure from
    removing the feature (0.18). Both are printed, always.

⚠⚠ TAUTOLOGY, FOUND IN THE FIRST RUN OF THIS HARNESS AND WORTH RECORDING.
The out-and-back classifier was applied to the discards of a gate whose own
verdict is `min |p_k - p_pre| / |p_F - p_pre|` over L frames. The classifier is
the SAME expression over 6 frames -- and a minimum over 6 frames is never larger
than a minimum over 2, so every RETURNED verdict at L<=6 is classified "teleport"
BY ALGEBRA. It duly printed "discards: 100.0% teleport, 0.0% real movement",
which reads like a triumph and means nothing at all.

    Any classifier that shares an expression with the thing it is judging is
    measuring itself. This is 0.18's lesson in a new costume.

So the load-bearing evidence here is the REVERSAL CROSS-TAB: reversal labels come
from raw velocity sign changes, share nothing with any verdict test, and are
reported per FLAG EPISODE -- "of the flags raised at a labelled direction change,
what fraction were thrown away?" against the same fraction elsewhere. The
out-and-back classification is still printed, marked TAUTOLOGICAL where it is.

    .venv/Scripts/python.exe analysis/b7_eval.py [--quick]
"""
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

import b3_full_eval as B3E
from Resources import block_predictor as BP
from Resources import confirmation_gate as CG

EDGE_ON_BAND = B3E.EDGE_ON_BAND
STILL_PALM_MOVE = B3E.STILL_PALM_MOVE
TRUST_Z = B3E.TRUST_Z
CLASSIFY_LOOKAHEAD = 6          # fixed, independent of L -- see the header
pct = B3E.pct


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------
def measured_fps():
    """Per-session measured fps (N10: never compare sessions without it)."""
    out = {}
    for d in sorted(glob.glob(os.path.join(B3E.AJP.ROOT, "*"))):
        p = os.path.join(d, "meta.json")
        if not os.path.exists(p):
            continue
        try:
            m = json.load(open(p, encoding="utf-8-sig"))
        except (ValueError, OSError):
            continue
        if m.get("measured_fps"):
            out[m.get("sequence", os.path.basename(d))] = m["measured_fps"]
    return out


def channel_series(seq, ch):
    if ch == BP.QUAT_CHANNEL:
        return [st.get("quaternion") for st in seq]
    return [BP.BlockPredictor._scalars(st).get(ch) for st in seq]


def classify(vals, f, ch):
    """NON-CAUSAL out-and-back verdict for an excursion starting at frame f.

    The project's ground-truth discriminant (m4_rejection_audit.py), at a FIXED
    6-frame lookahead regardless of the gate's L:

        out  = |v[f]   - v[f-1]|          how far it leapt
        back = min |v[k] - v[f-1]| over k in f+1 .. f+6
        <0.5 came back  -> TELEPORT (correctly discarded)
        >=0.9 kept going -> REAL MOVEMENT (wrongly discarded)
    """
    dist = ((lambda a, b: None if a is None or b is None else abs(a - b))
            if ch != BP.QUAT_CHANNEL else BP._qangle)
    if f < 1 or f >= len(vals):
        return None
    out = dist(vals[f], vals[f - 1])
    if out is None or out < 1e-9:
        return None
    backs = [dist(vals[k], vals[f - 1])
             for k in range(f + 1, min(len(vals), f + 1 + CLASSIFY_LOOKAHEAD))]
    backs = [b for b in backs if b is not None]
    if not backs:
        return None
    r = min(backs) / out
    return "teleport" if r < 0.5 else ("ambiguous" if r < 0.9 else "real")


# --------------------------------------------------------------------------
# one configuration over the whole corpus
# --------------------------------------------------------------------------
class Result:
    def __init__(self, label):
        self.label = label
        self.rev = [0, 0, 0]        # channel-frames at a reversal: n, flagged, discarded
        self.non = [0, 0, 0]        # ... elsewhere
        self.ep_rev = [0, 0]        # flag EPISODES at a reversal: n, discarded
        self.ep_non = [0, 0]        # ... elsewhere
        self.jit_raw, self.jit_out = [], []
        self.band_raw, self.band_out = [], []
        self.quat_raw, self.quat_out = {}, {}
        self.track = []
        self.episodes = 0           # flag episodes (each costs L frames of latency)
        self.deferred = 0           # channel-frames spent coasting
        self.forced = 0
        self.n_frames = 0
        self.cls_disc = {"teleport": 0, "ambiguous": 0, "real": 0}
        self.cls_conf = {"teleport": 0, "ambiguous": 0, "real": 0}
        self.tele_take = {}         # per-take teleport-corpus counts


def run_config(streams, label, factory, is_b7=True):
    r = Result(label)
    for name, seq in streams:
        if len(seq) < BP.MIN_HISTORY + 3:
            continue
        rev_idx = {ch: B3E.reversals(seq, ch) for ch in BP.SCALAR_CHANNELS}
        series = {ch: channel_series(seq, ch) for ch in BP.CHANNELS}
        g = factory()
        lag = getattr(g, "lag", 1)
        flagged_at = {ch: set() for ch in BP.CHANNELS}
        discarded_at = {ch: set() for ch in BP.CHANNELS}
        open_ep = {}                # ch -> the frame its current flag was raised
        prev_out = prev_raw = prev_palm = None
        prev_qr = prev_qo = None
        for k, st in enumerate(seq):
            res = g.update(st)
            r.n_frames += 1
            r.forced += len(res.get("forced", ()))
            if is_b7:
                for ch in res["flagged"]:
                    flagged_at[ch].add(k)
                    open_ep[ch] = k
                    r.episodes += 1
                r.deferred += len(res["pending"])
                for ch in res["discarded"]:
                    f = open_ep.pop(ch, max(0, k - lag))
                    # the thrown-away frames are F .. F+L-1
                    for j in range(f, k):
                        discarded_at[ch].add(j)
                    v = classify(series[ch], f, ch)
                    if v:
                        r.cls_disc[v] += 1
                    if ch in BP.SCALAR_CHANNELS:
                        b = r.ep_rev if f in rev_idx[ch] else r.ep_non
                        b[0] += 1
                        b[1] += 1
                for ch in res["confirmed"]:
                    f = open_ep.pop(ch, max(0, k - lag))
                    v = classify(series[ch], f, ch)
                    if v:
                        r.cls_conf[v] += 1
                    if ch in BP.SCALAR_CHANNELS:
                        (r.ep_rev if f in rev_idx[ch] else r.ep_non)[0] += 1
            else:                       # B3'': a rejection IS a discard
                for ch in res["rejected"]:
                    flagged_at[ch].add(k)
                    discarded_at[ch].add(k)
                    r.episodes += 1
                    r.deferred += 1
                    v = classify(series[ch], k, ch)
                    if v:
                        r.cls_disc[v] += 1
                    if ch in BP.SCALAR_CHANNELS:
                        b = r.ep_rev if k in rev_idx[ch] else r.ep_non
                        b[0] += 1
                        b[1] += 1       # B3'': every flag IS a discard

            out = res["output"]
            w = st["scale"] or 1.0
            if prev_raw is not None and prev_out is not None:
                if None not in out["position"]:
                    dr = math.dist(st["position"], prev_raw) / w
                    do = math.dist(out["position"], prev_out) / w
                    pm = math.dist(st["position"], prev_palm) if prev_palm else None
                    if pm is not None and pm < STILL_PALM_MOVE:
                        r.jit_raw.append(dr)
                        r.jit_out.append(do)
                    eo = st.get("_eo")
                    if eo is not None and eo < EDGE_ON_BAND:
                        r.band_raw.append(dr)
                        r.band_out.append(do)
                    z = (res["debug"].get("pos_x") or {}).get("z")
                    if z is not None and z < TRUST_Z:
                        r.track.append(math.dist(out["position"],
                                                 st["position"]) / w)
            if prev_raw is not None and st.get("quaternion") and prev_qr:
                dq = BP._qangle(st["quaternion"], prev_qr)
                dqo = BP._qangle(out.get("quaternion"), prev_qo)
                if dq is not None:
                    r.quat_raw.setdefault(name, []).append(dq)
                if dqo is not None:
                    r.quat_out.setdefault(name, []).append(dqo)
            prev_qr, prev_qo = st.get("quaternion"), out.get("quaternion")
            prev_raw = prev_palm = st["position"]
            prev_out = out["position"] if None not in out["position"] else prev_out

        # --- target 0, tallied after the run so discards are attributed to the
        #     frames they actually removed, not to the decision frame ---
        for ch in BP.SCALAR_CHANNELS:
            for k in range(len(seq)):
                bucket = r.rev if k in rev_idx[ch] else r.non
                bucket[0] += 1
                if k in flagged_at[ch]:
                    bucket[1] += 1
                if k in discarded_at[ch]:
                    bucket[2] += 1
        if "two_hand" in name or "jump" in name:
            d = r.tele_take.setdefault(name.split(" #")[0], [0, 0])
            d[0] += sum(len(v) for v in discarded_at.values())
            d[1] += len(seq)
    return r


def ratio(a, b):
    return (a / b) if b > 0 else float("inf") if a else float("nan")


def report(r, fps, lag, tautological=False):
    n_rev, f_rev, d_rev = r.rev
    n_non, f_non, d_non = r.non
    fr, fn = 100.0 * ratio(f_rev, n_rev), 100.0 * ratio(f_non, n_non)
    dr, dn = 100.0 * ratio(d_rev, n_rev), 100.0 * ratio(d_non, n_non)
    print(f"\n--- {r.label} " + "-" * max(0, 66 - len(r.label)))
    print(f"  channel-frames: {n_rev} at a reversal, {n_non} elsewhere; "
          f"force-accepts {r.forced}")
    print(f"  {'':<12}{'at reversal':>14}{'elsewhere':>14}{'ratio':>10}")
    print(f"  {'FLAGGED':<12}{fr:>13.2f}%{fn:>13.2f}%"
          f"{ratio(fr, fn):>9.2f}x   (cost = latency)")
    print(f"  {'DISCARDED':<12}{dr:>13.2f}%{dn:>13.2f}%"
          f"{ratio(dr, dn):>9.2f}x   <- criterion 1, must be <= 1.5x")
    print(f"  discarded channel-frames: {d_rev} at a reversal vs {d_non} "
          f"elsewhere  <- criterion 2, must be majority NOT-reversal")
    # ⭐ The verdict test judged on its own, with the flag rate divided out.
    er, en = r.ep_rev, r.ep_non
    print(f"  VERDICT TEST alone -- of flags raised, fraction thrown away:")
    print(f"    at a reversal {er[1]:>6}/{er[0]:<6} ({100.0*ratio(er[1],er[0]):.1f}%)"
          f"   elsewhere {en[1]:>6}/{en[0]:<6} ({100.0*ratio(en[1],en[0]):.1f}%)"
          f"   {ratio(ratio(er[1],er[0]), ratio(en[1],en[0])):.2f}x")
    lat_ms = 1000.0 * lag / fps
    pct_def = 100.0 * ratio(r.deferred, max(1, r.n_frames) * len(BP.CHANNELS))
    print(f"  latency {lat_ms:.0f} ms per flag ({lag} frames @ {fps:.1f} fps), "
          f"{r.episodes} episodes, {pct_def:.2f}% of channel-frames deferred")
    tot_d = sum(r.cls_disc.values())
    tot_c = sum(r.cls_conf.values())
    taut = "  ⚠ TAUTOLOGICAL, see header" if tautological else ""
    if tot_d:
        print("  out-and-back class, discards: " + ", ".join(
            f"{k} {v} ({100.0*v/tot_d:.1f}%)" for k, v in r.cls_disc.items()) + taut)
    else:
        print("  out-and-back class, discards: none")
    if tot_c:
        print("  out-and-back class, kept:     " + ", ".join(
            f"{k} {v} ({100.0*v/tot_c:.1f}%)" for k, v in r.cls_conf.items()))
    print(f"  jitter still  raw p50/p95/max "
          f"{pct(r.jit_raw,50):.4f} / {pct(r.jit_raw,95):.4f} / "
          f"{max(r.jit_raw or [0]):.4f}")
    print(f"                out p50/p95/max "
          f"{pct(r.jit_out,50):.4f} / {pct(r.jit_out,95):.4f} / "
          f"{max(r.jit_out or [0]):.4f}")
    print(f"  edge-on band  raw p50/p95/max "
          f"{pct(r.band_raw,50):.4f} / {pct(r.band_raw,95):.4f} / "
          f"{max(r.band_raw or [0]):.4f}")
    print(f"                out p50/p95/max "
          f"{pct(r.band_out,50):.4f} / {pct(r.band_out,95):.4f} / "
          f"{max(r.band_out or [0]):.4f}")
    if r.track:
        print(f"  tracking cost n={len(r.track)} mean={sum(r.track)/len(r.track):.5f}"
              f"  p99={pct(r.track,99):.5f}  max={max(r.track):.5f}")


def report_orientation(results):
    print("\n" + "=" * 78)
    print("3. BACK-OF-HAND orientation steps (deg/frame) -- per take, never pooled")
    print("=" * 78)
    takes = sorted(n for n in results[0].quat_raw if "back" in n)
    head = f"  {'take':<30}{'raw p95':>9}{'raw max':>9}"
    for r in results:
        head += f"{r.label[:11]:>12}"
    print(head + "   (gated p95 / max)")
    for n in takes:
        a = results[0].quat_raw.get(n) or []
        if not a:
            continue
        line = f"  {n[:29]:<30}{pct(a,95):>9.2f}{max(a):>9.2f}"
        for r in results:
            b = r.quat_out.get(n) or []
            line += f"{(pct(b,95) if b else 0):>6.2f}/{(max(b) if b else 0):>5.1f}"
        print(line)


def main():
    quick = "--quick" in sys.argv
    print("=" * 78)
    print("B7 -- CONFIRMATION GATE, full corpus evaluation")
    print("=" * 78)
    fps_map = measured_fps()
    fps_vals = sorted(fps_map.values())
    fps = fps_vals[len(fps_vals) // 2] if fps_vals else 24.0
    print(f"sessions with measured_fps: {len(fps_map)}, median {fps:.2f} fps "
          f"(range {min(fps_vals):.1f}-{max(fps_vals):.1f}) -- N10")

    streams = list(B3E.sessions())
    print(f"streams built via audit_jump_provenance (DR-1 replay, run-break "
          f"guarded): {len(streams)}")

    # B8's winner for the horizons a coast actually uses (h=1..2 on a MOVING
    # hand): order 1, exponential weights, half-life 2 frames. Passed in rather
    # than made the module default, so every pre-B8 number stays reproducible.
    B8 = {"order": 1, "weighting": "exp", "half_life": 2.0}

    configs = [("B3'' (baseline)", lambda: BP.BlockPredictor(), False)]
    lags = (2, 6) if quick else (2, 3, 4, 6)
    # verdict test: swept first, `pred` won decisively (0.38x vs p_pre's 1.13x)
    for test in ("p_pre", "pred", "self"):
        configs.append((f"B7 L=2 test={test}",
                        (lambda t=test:
                         CG.ConfirmationGate(lag=2, verdict_test=t)), True))
    # what the cube does while deferring -- B8 says the fit loses to "hold"
    for mode in ("hold", "damped", "extrapolate"):
        configs.append((f"B7 L=2 coast={mode}",
                        (lambda m=mode: CG.ConfirmationGate(lag=2,
                                                            coast_mode=m)), True))
    # the same, with B8's fit driving both the prediction and sigma
    for mode in ("hold", "extrapolate"):
        configs.append((f"B7 L=2 coast={mode} +B8",
                        (lambda m=mode: CG.ConfirmationGate(lag=2, coast_mode=m,
                                                            fit_kwargs=B8)), True))
    for L in lags:
        configs.append((f"B7 L={L} best +B8",
                        (lambda L=L: CG.ConfirmationGate(lag=L, fit_kwargs=B8)),
                        True))
    if not quick:
        for b in (1, 3):
            configs.append((f"B7 L=2 blend={b} +B8",
                            (lambda b=b: CG.ConfirmationGate(lag=2, blend=b,
                                                             fit_kwargs=B8)), True))
        configs.append(("B7 L=2 ambig=RETURNED",
                        lambda: CG.ConfirmationGate(lag=2, fit_kwargs=B8,
                                                    ambiguous_is_coherent=False),
                        True))

    print("\n" + "=" * 78)
    print("0. ⚠ DIRECTION-REVERSAL SAFETY -- the disqualifying test, run FIRST")
    print("=" * 78)
    results = []
    for label, factory, is_b7 in configs:
        r = run_config(streams, label, factory, is_b7)
        g = factory()
        lag = getattr(g, "lag", 1) if is_b7 else 1
        # the out-and-back classifier is a superset of the p_pre verdict itself
        taut = (not is_b7) or getattr(g, "verdict_test", "") == "p_pre"
        report(r, fps, lag, tautological=taut)
        results.append(r)

    report_orientation(results)

    print("\n" + "=" * 78)
    print("READING THIS TABLE")
    print("=" * 78)
    print("  * A FLAG ratio near B3'''s 7.43x is EXPECTED and is not a failure:")
    print("    B7 flags on the same test. It buys latency, not fewer flags.")
    print("  * The DISCARD ratio is the acceptance criterion. <= 1.5x ships.")
    print("  * ⚠ At L=6 the gate's coherence test and the classifier share the")
    print("    same 6-frame window, so that row's classification is near-circular")
    print("    and only the reversal ratios are independent evidence there.")
    print("=" * 78)


if __name__ == "__main__":
    main()
