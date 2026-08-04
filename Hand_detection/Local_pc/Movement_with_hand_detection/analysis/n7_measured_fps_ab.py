"""N7 A/B: does driving DR-1's dwells from MEASURED frame timing change anything?

N7 was promoted from tidiness to CORRECTNESS because the pipeline's frame rate is
environment-dependent (N10): 24.09-24.14 fps in daylight versus 15.1-15.77 in dim
light on the same camera. Every DR-1 dwell scales with it, so at 15.77 fps
SWITCH_MS silently became ~761 ms against an intended 500.

The two things this must show, and they pull in opposite directions:

  1. REGRESSION SAFETY -- on sessions recorded at ~24 fps, identity assignments
     must be IDENTICAL to the hard-coded behaviour. The fix is supposed to be a
     no-op exactly where the old assumption happened to be true.
  2. THE ACTUAL FIX -- on sessions recorded away from 24 fps, the dwells must
     change, and the assignments may. That divergence IS the bug being fixed, so
     it must be reported per session rather than buried in a total.

Uses each recording's own `tCapture`, which is a real monotonic timestamp taken
at frame read -- not a synthesised cadence.

    .venv/Scripts/python.exe analysis/n7_measured_fps_ab.py
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP

HI = AJP.hand_identity


def replay(frames, use_timestamps):
    """Return per-frame assigned labels, plus the dwell ACTUALLY IN USE each frame.

    The dwell is sampled per frame rather than read once at the end: the
    estimate tracks a changing rate by design, so a single end-of-session value
    misrepresents what the tracker actually ran with -- reporting it that way
    would be the same "one number that isn't the quantity" error 0.15 records.
    """
    trk = HI.HandIdentityTracker(log=lambda *a, **k: None)
    out = []
    dwells = []
    for rec in frames:
        dwells.append(trk.switch_frames)
        hands = rec.get("hands") or []
        obs, keep = [], []
        for h in hands:
            pts = [tuple(p) for p in h["landmarks"]]
            cen = HI.palm_centroid(pts)
            if cen is None:
                continue
            obs.append((cen, h["handedness"], h.get("score", 1.0),
                        HI.palm_width(pts)))
            keep.append(h)
        now = rec.get("tCapture") if use_timestamps else None
        if not obs:
            trk.update([], now_ms=now)
            out.append(())
            continue
        out.append(tuple(trk.update(obs, now_ms=now)))
    dwells.sort()
    median_dwell = dwells[len(dwells) // 2] if dwells else None
    return out, trk.fps, median_dwell


def main():
    print("=" * 78)
    print("N7 -- measured frame rate vs the hard-coded 24 fps assumption")
    print("=" * 78)
    print(f"\n  {'session':<40}{'meta fps':>9}{'measured':>10}"
          f"{'dwell sw':>10}{'differs':>9}")

    seen = {}
    identical_near24 = diverged_near24 = 0
    total_diff = 0
    rows = []
    for raw_name, frames in AJP.SESSIONS:
        seen[raw_name] = seen.get(raw_name, 0) + 1
        name = raw_name if seen[raw_name] == 1 else f"{raw_name} #{seen[raw_name]}"
        if not frames or "tCapture" not in frames[0]:
            continue
        old, _, _ = replay(frames, use_timestamps=False)
        new, fps, med_dwell = replay(frames, use_timestamps=True)
        diff = sum(1 for a, b in zip(old, new) if a != b)
        total_diff += diff
        span = (frames[-1]["tCapture"] - frames[0]["tCapture"]) / 1000.0
        meta_fps = len(frames) / span if span > 0 else 0.0
        sw = med_dwell
        rows.append((name, meta_fps, fps, sw, diff))
        if abs(meta_fps - 24.0) < 1.0:
            if diff:
                diverged_near24 += 1
            else:
                identical_near24 += 1

    for name, meta_fps, fps, sw, diff in sorted(rows, key=lambda r: r[1]):
        flag = "" if diff == 0 else f"{diff}"
        print(f"  {name[:39]:<40}{meta_fps:>9.2f}{fps:>10.2f}{sw:>10}{flag:>9}")

    print(f"\n  baseline dwell at the hard-coded 24 fps: switch="
          f"{HI.frames_for('switch', HI.FALLBACK_FPS)} frames "
          f"(~{HI._SWITCH_MS:.0f} ms)")

    print("\n--- 1. REGRESSION SAFETY (sessions within 1 fps of 24) ---")
    print(f"  identical assignments : {identical_near24}")
    print(f"  diverged              : {diverged_near24}")
    print("  -> a no-op here is the PASS condition: where the old assumption was")
    print("     true, nothing should change.")

    print("\n--- 2. THE FIX (sessions away from 24 fps) ---")
    off = [r for r in rows if abs(r[1] - 24.0) >= 1.0]
    if off:
        for name, meta_fps, fps, sw, diff in sorted(off, key=lambda r: r[1]):
            err = 100.0 * (HI._SWITCH_MS * (24.0 / meta_fps) - HI._SWITCH_MS) / HI._SWITCH_MS
            print(f"  {name[:39]:<40}{meta_fps:>7.2f} fps  switch was "
                  f"{HI.frames_for('switch', HI.FALLBACK_FPS)}f "
                  f"(~{1000.0*HI.frames_for('switch', HI.FALLBACK_FPS)/meta_fps:.0f} ms, "
                  f"{err:+.0f}% off) -> now {sw}f")
    else:
        print("  (no sessions materially away from 24 fps in this corpus)")

    print(f"\n  total frames with changed assignments across the corpus: {total_diff}")
    print("=" * 78)


if __name__ == "__main__":
    main()
