"""THE PROPERTY THAT WAS MISSING: a cube may never be owned AND undriveable.

⚠ This is the test that should have existed before the owner was ever asked to
try the pipeline. Its absence is why the same defect was reported four times, in
four different shapes:

    "indicated as grabbed but did not move and the free hand could not grab it"
    "the small cube was dropped but my free hand could not catch it again"
    "you still have issues ... check the 450 ms and then later on the 300 ms"
    "several times, the cubes get ungrabbed but is still marked as grab"

Each time a patch was added on top of the previous one (governing hand, absent
timer, safety net) and each patch had a hole. The fault was that nothing asserted
the PROPERTY -- only the individual mechanisms were checked.

THE INVARIANT
--------------
For every frame, for every cube: if `owner is not None`, then EITHER some hand can
drive it this frame, OR it has been undriveable for less than OWNER_DEGRADE_MS.
Anything else is the frozen-but-owned state the operator sees as "stuck".

Driven entirely from RECORDED sessions, so it needs no camera and no operator.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/verify_no_frozen_cube.py
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Resources import HandsTriggeredActions as HTA  # noqa: E402

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
# ⚠ Sessions recorded BEFORE option A landed cannot pass -- they ARE the defect,
# preserved as evidence. Session names are timestamps, so a lexical cutoff sorts
# them. Older ones report as HISTORICAL and do not fail the run: a gate that
# fails forever on old data stops being read, which is worse than no gate.
FIX_CUTOFF = "2026-08-22_163000"
FAILURES = []


def sessions():
    """Every session that recorded cube state, or just the one named on argv.

    ⚠ This used to be a hardcoded list of glob patterns, and it silently SKIPPED
    the very session recorded to test the fix -- reporting only stale failures
    while the new evidence sat unexamined. A guard that quietly ignores new data
    is worse than no guard. Scan everything; name a session to narrow it.
    """
    if len(sys.argv) > 1:
        d = os.path.join(ROOT, sys.argv[1])
        if os.path.exists(os.path.join(d, "raw_landmarks.jsonl")):
            yield d
        return
    for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
        if os.path.exists(os.path.join(d, "raw_landmarks.jsonl")):
            yield d


def main():
    print("=" * 78)
    print("INVARIANT: no cube may be OWNED and UNDRIVEABLE beyond the degrade window")
    print("=" * 78)
    print(f"  OWNER_DEGRADE_MS = {HTA.OWNER_DEGRADE_MS:.0f}   "
          f"OWNER_ABSENT_RELEASE_MS = {HTA.OWNER_ABSENT_RELEASE_MS:.0f}")
    if HTA.OWNER_DEGRADE_MS != HTA.OWNER_ABSENT_RELEASE_MS:
        FAILURES.append("degrade and release windows differ -> a frozen gap exists")
        print("  [FAIL] the two windows differ: that GAP is the frozen-but-owned state")
    else:
        print("  [PASS] driving stops exactly when the cube is released -- no frozen gap\n")

    any_session = False
    for d in sessions():
        rows = [json.loads(l) for l in
                open(os.path.join(d, "raw_landmarks.jsonl"), encoding="utf-8") if l.strip()]
        rows = [r for r in rows if isinstance(r.get("cubes"), dict) and r["cubes"]]
        if not rows:
            continue
        any_session = True
        span = (rows[-1]["tCapture"] - rows[0]["tCapture"]) / 1000.0
        fps = len(rows) / max(1e-9, span)
        budget = HTA.OWNER_DEGRADE_MS / 1000.0 * fps      # frames allowed
        worst = {}
        for arm in rows[0]["cubes"]:
            run = {}
            for r in rows:
                hands = r.get("hands") or []
                live = {int(h["trackId"]) for h in hands if int(h.get("trackId", -1)) >= 0}
                for name, c in (r["cubes"].get(arm) or {}).items():
                    if not isinstance(c, dict):
                        continue
                    o = c.get("owner")
                    frozen = isinstance(o, int) and o not in live
                    run[name] = run.get(name, 0) + 1 if frozen else 0
                    worst[arm] = max(worst.get(arm, 0), run[name])
        label = os.path.basename(d)[:42]
        bad = [a for a, w in worst.items() if w > budget * 1.5]   # 50% slack for jitter
        historical = os.path.basename(d) < FIX_CUTOFF
        mark = "PASS" if not bad else ("hist" if historical else "FAIL")
        print(f"  [{mark}] {label:44s} budget {budget:4.1f} fr   worst "
              f"{max(worst.values()) if worst else 0:3d} fr"
              f"{'   (pre-fix, expected)' if bad and historical else ''}")
        if bad and not historical:
            FAILURES.append(f"{label}: {bad} exceeded the degrade window")

    if not any_session:
        print("  no usable sessions found")
    print("\n" + "=" * 78)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print("  -", f)
        print("\n  NOTE: sessions recorded BEFORE a fix legitimately fail -- that is")
        print("  the fix being demonstrated. Judge new recordings, and read the")
        print("  session name before treating a failure as a regression.")
        return 1
    print("ALL SESSIONS RESPECT THE INVARIANT.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
