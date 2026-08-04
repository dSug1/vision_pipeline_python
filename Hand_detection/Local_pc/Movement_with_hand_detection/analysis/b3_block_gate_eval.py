"""B3' evaluation -- does the block gate beat item 1.6's 4:1 over-filtering?

THE BAR, set before running (0.18's binding rule): rejections must be
CLASSIFIED, not counted. A lower rejection count proves nothing -- it cannot
distinguish removing the failure from removing the feature. 1.6 initially
"passed" on exactly that mistake.

    1.6's result, on the same classification: 7.9% teleport / 80.2% real,
    i.e. ~4 real fast movements rejected per teleport caught, and no threshold
    of any cue improved the ratio.

CORPUS. Two sources, deliberately:

  * `Position_during_rotation/*.json` -- 7 takes recorded THROUGH the live
    snap/translate logic, so they contain real grabs, real cube positions, and
    the named Object Jump reproduction (`jump_test4`) plus three `edge_test`
    takes. This is the population the perception corpus lacks: build_v2 replays
    DR-1, and DR-1 is the FIX for Object Jump, so only 3 teleports survive there
    (16.1). These takes predate that correction in the recorded stream.
    ⚠ Read from a local copy: `Position_during_rotation` is not readable by
    Python in this environment (PermissionError; PowerShell reads it fine).
  * the perception corpus, for the real-fast-movement population.

LABELLING is the same independent, non-causal out-and-back test used in
`m4_rejection_audit.py` and `b2_block_separability.py`: did the hand RETURN to
its prior trajectory within 6 frames (teleport) or CONTINUE (real movement)?
It uses future frames, which a live gate cannot -- deliberately, so the labels
cannot be derived from the causal channels under test.

    .venv/Scripts/python.exe analysis/b3_block_gate_eval.py [pivot_dir]
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
from Resources import block_tracker as BT
from Resources import palm_geometry as PG

PIVOT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.environ.get("TEMP", "."), "claude",
    "c--Users-sugit-Documents--scripts-persos--Persos-vision-pipeline-python-Hand-detection",
    "fdbae111-1ad0-43ab-affa-7e653522be6e", "scratchpad", "pivot")

LOOKAHEAD = 6
DISPLACEMENT_GATE = 0.5
TELEPORT_MAX_RETURN = 0.5
REAL_MIN_RETURN = 0.9


def pivot_runs():
    """Yield (take, hand, [block_state, ...]) from the pivot recordings."""
    files = sorted(glob.glob(os.path.join(PIVOT_DIR, "*.json")))
    if not files:
        print(f"⚠ no pivot recordings under {PIVOT_DIR}")
        return
    for f in files:
        if f.endswith(".notes.json"):
            continue          # operator-annotation sidecar, not a recording
        with open(f, encoding="utf-8-sig") as fh:
            d = json.load(fh)
        take = d.get("label", os.path.basename(f))
        seqs = {}
        for rec in d.get("frames", []):
            for lab, h in (rec.get("hands") or {}).items():
                if not h or not h.get("detected"):
                    seqs.setdefault(lab, []).append(None)   # break marker
                    continue
                px = h.get("pixel_landmarks")
                wl = h.get("world_landmarks")
                st = HB.block_state([tuple(p) for p in px] if px else None,
                                    [tuple(v) for v in wl] if wl else None)
                if st is not None and px:
                    # DR-2's edge-on measure: inside the band the palm sign --
                    # and, per 0.18, the whole palm reconstruction -- is
                    # unobservable. The gate has no business judging there.
                    st["_eo"] = PG.edge_on_measure([tuple(p) for p in px])
                seqs.setdefault(lab, []).append(st)
        for lab, seq in seqs.items():
            run = []
            for st in seq + [None]:
                if st is None or st.get("position") is None or not st.get("scale"):
                    if len(run) > 10:
                        yield take, lab, run
                    run = []
                else:
                    run.append(st)


def label_of(seq, j):
    """Independent non-causal label for the transition into frame j."""
    a, b = seq[j - 1], seq[j]
    w = a["scale"]
    if not w or w < 1e-6:
        return None
    disp = math.dist(b["position"], a["position"]) / w
    if disp < DISPLACEMENT_GATE:
        return None
    out = math.dist(a["position"], b["position"])
    if out < 1e-9:
        return None
    back = min(math.dist(a["position"], seq[k]["position"])
               for k in range(j + 1, min(len(seq), j + 1 + LOOKAHEAD)))
    r = back / out
    if r < TELEPORT_MAX_RETURN:
        return "teleport"
    if r > REAL_MIN_RETURN:
        return "real"
    return None


def evaluate(sigma, order, window, suppress_edge_on=None):
    """`suppress_edge_on`: if set, the gate does not judge frames whose
    edge_on_measure is below it -- DR-2's existing contract, extended from the
    palm SIGN to the whole palm transform, which 0.18 showed collapses together
    in that band."""
    tele_caught = tele_total = real_flagged = real_total = 0
    frames = rejects = forced = 0
    per_take = {}
    for take, _lab, seq in pivot_runs():
        trk = BT.BlockTracker(window=window, order=order, reject_sigma=sigma)
        for j, st in enumerate(seq):
            res = trk.update(st)
            frames += 1
            pos_rejected = any(c in res["rejected"] for c in ("pos_x", "pos_y"))
            eo = st.get("_eo")
            if (suppress_edge_on is not None and eo is not None
                    and eo < suppress_edge_on):
                pos_rejected = False          # unobservable: do not judge
            rejects += 1 if res["rejected"] else 0
            forced += 1 if res["forced"] else 0
            if j == 0 or j >= len(seq) - LOOKAHEAD:
                continue
            lab = label_of(seq, j)
            if lab is None:
                continue
            d = per_take.setdefault(take, {"tc": 0, "tt": 0, "rf": 0, "rt": 0})
            if lab == "teleport":
                tele_total += 1
                d["tt"] += 1
                if pos_rejected:
                    tele_caught += 1
                    d["tc"] += 1
            else:
                real_total += 1
                d["rt"] += 1
                if pos_rejected:
                    real_flagged += 1
                    d["rf"] += 1
    return dict(tc=tele_caught, tt=tele_total, rf=real_flagged, rt=real_total,
                frames=frames, rejects=rejects, forced=forced, per_take=per_take)


def main():
    print("=" * 78)
    print("B3' -- block gate, evaluated by CLASSIFIED rejections")
    print("=" * 78)
    print(f"\npivot corpus: {PIVOT_DIR}")

    base = evaluate(BT.REJECT_SIGMA, BT.POLY_ORDER, BT.WINDOW)
    if not base["frames"]:
        raise SystemExit("no usable runs -- check the pivot directory")

    print(f"\nframes judged {base['frames']}, frames with a rejection "
          f"{base['rejects']} ({100.0*base['rejects']/base['frames']:.2f}%), "
          f"force-accepts {base['forced']}")
    print(f"labelled position transitions: {base['tt']} teleport, "
          f"{base['rt']} real movement")

    print("\n--- THE BAR: 1.6 caught teleports at ~4 real rejections each ---")
    print(f"  {'config':<26}{'tele caught':>12}{'real flagged':>14}{'ratio':>9}")

    def row(name, r):
        tc, tt = r["tc"], max(1, r["tt"])
        rf, rt = r["rf"], max(1, r["rt"])
        ratio = (rf / tc) if tc else float("inf")
        print(f"  {name:<26}{tc}/{r['tt']:<10}{rf}/{r['rt']:<12}"
              f"{'inf' if ratio == float('inf') else f'{ratio:.2f}':>8}")

    row(f"blocks (s={BT.REJECT_SIGMA}, o={BT.POLY_ORDER})", base)

    print("\n--- sensitivity ---")
    for sigma in (3.0, 4.0, 6.0, 8.0):
        row(f"sigma {sigma}", evaluate(sigma, BT.POLY_ORDER, BT.WINDOW))
    for order in (1, 2):
        row(f"order {order} (velocity{'+accel' if order == 2 else ''})",
            evaluate(BT.REJECT_SIGMA, order, BT.WINDOW))
    for window in (3, 5, 9):
        row(f"window {window} frames", evaluate(BT.REJECT_SIGMA, BT.POLY_ORDER, window))

    print("\n--- suppressing the gate inside the edge-on band (DR-2's contract) ---")
    print("  0.18: at edge-on the whole palm reconstruction collapses together,")
    print("  so the gate is judging an unobservable quantity there.")
    for thr in (0.15, 0.25, 0.35):
        row(f"suppress below {thr}",
            evaluate(BT.REJECT_SIGMA, BT.POLY_ORDER, BT.WINDOW,
                     suppress_edge_on=thr))

    print("\n--- per take ---")
    print(f"  {'take':<26}{'tele':>10}{'real':>12}")
    for take, d in sorted(base["per_take"].items()):
        print(f"  {take:<26}{d['tc']}/{d['tt']:<8}{d['rf']}/{d['rt']:<10}")

    print("\n" + "=" * 78)
    print("READING THIS: 'ratio' is REAL MOVEMENTS REJECTED PER TELEPORT CAUGHT.")
    print("1.6 scored ~4. Below ~1 would be a decisive improvement; near or above")
    print("4 means the extra channels and windowed derivatives did not help and")
    print("the gate should be parked like 1.6 was.")
    print("=" * 78)


if __name__ == "__main__":
    main()
