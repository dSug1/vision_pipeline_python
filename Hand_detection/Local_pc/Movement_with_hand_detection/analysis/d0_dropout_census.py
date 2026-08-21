"""⭐ THE DROPOUT CENSUS — does MediaPipe actually drop out, when, and what does it cost?

Written 2026-08-21 to test the premise of an owner-supplied document,
`DROPOUT_MITIGATION.md`, BEFORE building against it.

⚠ THAT DOCUMENT IS NOT IN THIS REPOSITORY AND IS NOT MEANT TO BE (owner decision,
2026-08-21: distil it, do not file it). Its content lives in the places that own
each part -- its schema in `PERCEPTION_LAYER_SPEC.md` §2.1, its build tiers in
`PART_ONE.md` §3.1's Phase D rows, and its PREMISE right here, quoted below so
this script remains readable without it. Naming it is provenance, not a pointer.

It asserts:

    "MediaPipe's hand tracking is weak at detecting the hand when it crosses the
     horizontal plane during pitch rotation ... the palm detector itself can fail
     to find a box at all ... produces zero landmarks for that frame."

and orders the whole build on that basis ("build this first, before the Z-axis").
It is a specific, falsifiable claim about *this* corpus, and this project owns
purpose-built pitch-crossing and back-of-hand takes. So it can simply be checked.

────────────────────────────────────────────────────────────────────────────────
WHAT THIS MEASURES

  1. Dropout rate per take (frames where `hands` is empty), IN-TAKE only — each
     take's own `meta.analysis_trim` head/tail is removed, because the operator
     reaching in at the start and withdrawing at the end are not dropouts and
     they dominate the raw count (they are the 24-43 frame gaps).
  2. Gap-length distribution, in frames AND in ms at the take's measured fps.
     ⚠ This pipeline runs at 14-24 fps, NOT the 30-60 fps the document's
     constants implicitly assume: 150 ms is ~2-3 frames here, not 5-9.
  3. ⭐ The number that actually matters: **dropouts that began while a cube was
     HELD**. `HandsTriggeredActions._is_detected` is False on a single
     placeholder frame and `update_hands` releases immediately, so every one of
     those is a spurious cube drop the player sees.

────────────────────────────────────────────────────────────────────────────────
RESULT ON THE 2026-08-04 → 2026-08-17 CORPUS (54k in-take frames)

  ⛔ **THE DOCUMENT'S PREMISE IS NOT SUPPORTED HERE.** Pitch-crossing and
     back-of-hand takes — seven of them, three sessions, two frame rates,
     11,524 in-take frames, the operator deliberately pitching through
     horizontal 10-12x per take — contain **ZERO dropped frames. 0.000%.**

  ⭐ **BUT THE REMEDY IS STILL JUSTIFIED, FOR A DIFFERENT AND MEASURED REASON.**
     Dropouts are real at **1.36%** overall and cluster in FREE PLAY (hand
     leaving frame, fast motion), not in controlled rotation. They cause
     **98 spurious cube releases** across 40,307 held frames — about one every
     24 s of holding. Median gap **89 ms**; bridging to 150 ms saves 66% of
     them, to 300 ms saves 82%.

  ⚠ **And the real pitch-crossing failure is the OPPOSITE kind.** §16.17
     measured ~60° orientation jumps that BOTH rotation estimators reproduce to
     within 1°. Those are bad landmarks, not missing ones. The document says the
     problem is "not a landmark-*accuracy* problem you can threshold your way
     around — it's an upstream detection failure"; on this corpus it is exactly
     and only a landmark-accuracy problem, and there is no detection failure at
     all. Bridging cannot help it (there is nothing to bridge), and it belongs to
     the landmark layer — queue T1/T2, items 1.5/1.6/1.7, 5.4.

    .venv/Scripts/python.exe analysis/d0_dropout_census.py [--root DIR]
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"
# Takes whose NAME says they contain the condition the document is about.
# ⚠ The take name is ground truth -- never infer the axis from the data
# (`HANDOFF_ANCHOR_ROTATION.md` §5 trap 3).
PREMISE_TAKES = ("pitch", "back_of_hand")


def in_take(rows, meta):
    """Frames with each take's own head/tail trim removed."""
    t0 = rows[0]["tCapture"]
    span = (rows[-1]["tCapture"] - t0) / 1000.0
    tr = meta.get("analysis_trim") or {}
    head, tail = tr.get("head_s", 10.0), tr.get("tail_s", 5.0)
    return [r for r in rows if head <= (r["tCapture"] - t0) / 1000.0 <= span - tail]


def gaps_of(rows, held_only=False):
    """Runs of consecutive empty-`hands` frames. `held_only` keeps just those
    that BEGAN while a cube was held -- i.e. those that cost the player a drop."""
    out, run, began_held, prev_held = [], 0, False, False
    for r in rows:
        empty = not (r.get("hands") or [])
        if empty:
            if run == 0:
                began_held = prev_held
            run += 1
        else:
            if run and (began_held or not held_only):
                out.append(run)
            run = 0
            prev_held = bool((r.get("cubes_raw") or {}).get("large", {}).get("owner"))
    if run and (began_held or not held_only):
        out.append(run)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    a = ap.parse_args()

    print("=" * 92)
    print("DROPOUT CENSUS — in-take only (each take's own head/tail trim removed)")
    print("=" * 92)
    print(f"  {'take':<30}{'frames':>8}{'zero':>7}{'pct':>8}{'fps':>7}  gaps (frames)")
    print("-" * 92)

    tot = zero = held_frames = 0
    prem_tot = prem_zero = 0
    all_gaps, drop_ms = [], []

    for d in sorted(glob.glob(os.path.join(a.root, "*"))):
        f = os.path.join(d, "raw_landmarks.jsonl")
        if not os.path.isdir(d) or not os.path.exists(f):
            continue
        meta = json.load(open(os.path.join(d, "meta.json")))
        rows = [json.loads(l) for l in open(f)]
        if not rows:
            continue
        sub = in_take(rows, meta)
        if len(sub) < 30:
            continue                       # too short to say anything about
        fps = meta.get("measured_fps") or 17.0
        g = gaps_of(sub)
        z = sum(g)
        name = meta.get("sequence", os.path.basename(d))
        tot += len(sub)
        zero += z
        held_frames += sum(
            1 for r in sub if (r.get("cubes_raw") or {}).get("large", {}).get("owner"))
        all_gaps += g
        drop_ms += [n / fps * 1000.0 for n in gaps_of(sub, held_only=True)]
        if any(k in name for k in PREMISE_TAKES):
            prem_tot += len(sub)
            prem_zero += z
        print(f"  {name[:30]:<30}{len(sub):>8}{z:>7}{100*z/len(sub):>7.2f}%{fps:>7.1f}  "
              f"{sorted(Counter(g).items()) if g else '-'}")

    print("-" * 92)
    print(f"  ALL in-take: {tot} frames, {zero} dropped ({100*zero/max(1,tot):.2f}%)")
    print()
    print("  ⛔ THE DOCUMENT'S PREMISE — pitch-crossing / back-of-hand takes only:")
    print(f"     {prem_tot} frames, {prem_zero} dropped "
          f"({100*prem_zero/max(1,prem_tot):.3f}%)")
    if prem_zero == 0:
        print("     ⇒ ZERO. MediaPipe does not drop out during pitch crossing on this")
        print("       corpus. The premise of DROPOUT_MITIGATION.md is NOT supported.")
    print()
    print(f"  ⭐ WHAT IT ACTUALLY COSTS: {len(drop_ms)} dropouts began while a cube was")
    print(f"     HELD, over {held_frames} held frames — every one releases the cube today")
    print(f"     (`_is_detected` is False on one placeholder frame).")
    if drop_ms:
        s = sorted(drop_ms)
        print(f"     gap ms: min {s[0]:.0f}  median {s[len(s)//2]:.0f}  "
              f"p90 {s[int(.9*len(s))]:.0f}  max {s[-1]:.0f}")
        for cut in (80, 150, 300, 500, 1000):
            n = sum(1 for m in s if m <= cut)
            print(f"     bridging to {cut:>4} ms would save {n:>3} of {len(s)} "
                  f"({100*n/len(s):.0f}%)")
    print("=" * 92)


if __name__ == "__main__":
    main()
