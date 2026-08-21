"""⭐ D2 -- WHAT BRIDGING ACTUALLY DOES, CLASSIFIED. Not "drops removed".

⚠⚠ THIS SCRIPT EXISTS BECAUSE THE OBVIOUS METRIC IS THE ONE THAT ALREADY FAILED.
Item 1.6 passed its A/B on "54% of large excursions removed" and had to be
REVERSED once `m4_rejection_audit.py` classified the rejections: 80.2% of them
were the owner's real fast movements. The binding rule that came out of it --
**any module that rejects or suppresses data must CLASSIFY what it removed, not
merely count it** -- applies symmetrically to a module that ADDS data. "98 drops
-> N" cannot see a bridge that held a cube while the hand went somewhere else.

So every held-cube dropout is placed in one of four classes, per candidate window:

  SAVED         the owner hand returns inside the window AND close to where it
                vanished -> the player's drop is genuinely gone, and the cube
                barely moves on resume. This is the only class that is a win.
  POP           the owner hand returns inside the window but FAR away. The cube
                stayed held and then teleports to the new hand position. ⚠ NOT a
                save -- a drop was traded for a jump. This is the false-hold
                class, and it is invisible to a count.
  LATE_RELEASE  the hand does not come back in time. The cube is released anyway,
                just later. Cost is the added hang time before the drop, which is
                bounded by the window and reported.
  UNRESOLVED    the gap runs past the end of the take; nothing can be concluded.

⚠ "Far" is measured in PALM WIDTHS, not pixels -- scale-free, and the same unit
item 1.6 stated its excursions in (>1.0 / >2.0 palm widths), so the thresholds
are borrowed rather than invented.

⚠ TWO APPROXIMATIONS, both stated rather than hidden:
  1. Cube displacement is approximated by the OWNER HAND's palm-centre
     displacement across the gap. Under §14.1 the held cube tracks a frozen
     weighted combination of that hand's landmarks, so the two move together;
     the exact weights are frozen at grab time and are not recoverable from a
     recording that did not grab under this code.
  2. A dropout is the OWNER HAND being absent, which is what production's
     per-hand `_is_detected` actually tests. `d0_dropout_census.py` counted
     frames where NO hand was present at all. Both are reported below so the
     difference is visible rather than surprising.

    .venv/Scripts/python.exe analysis/d2_bridge_ab.py [--root DIR]
"""
import argparse
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from Resources import hand_blocks  # noqa: E402

DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"

# Candidate coast windows. 0 is today's behaviour and must reproduce the
# pre-D2 outcome exactly (every dropout releases immediately) -- it is the
# control, not a candidate.
WINDOWS_MS = (0.0, 80.0, 150.0, 200.0, 300.0, 500.0, 1000.0)

# Item 1.6's excursion scale, reused deliberately. A resume that moves the cube
# less than this is not something the player can distinguish from the jitter the
# pipeline already has.
POP_PALM_WIDTHS = 1.0


def _shipped(name, module, fallback):
    """Read a shipped constant out of `Resources/<module>` by text.

    ⚠ Deliberately not an import: `HandsTriggeredActions` builds a pygame window
    at import time, and a measurement script must not depend on a display. But a
    harness that quietly analyses a DIFFERENT value than the one production runs
    is worse than useless, so the value is read rather than restated."""
    path = os.path.join(BASE, "Resources", module)
    try:
        for line in open(path, encoding="utf-8"):
            if line.startswith(name + " = "):
                return float(line.split("=", 1)[1].split("#")[0].strip())
    except OSError:
        pass
    print(f"  ⚠ could not read {name} from {module}; using {fallback}")
    return fallback


RESYNC_BLEND_FRAMES = int(_shipped("RESYNC_BLEND_FRAMES", "HandsTriggeredActions.py", 3))


def in_take(rows, meta):
    """Each take's own head/tail trim removed -- identical to the D0 census, so
    the two scripts are counting over the same frames."""
    t0 = rows[0]["tCapture"]
    span = (rows[-1]["tCapture"] - t0) / 1000.0
    tr = meta.get("analysis_trim") or {}
    head, tail = tr.get("head_s", 10.0), tr.get("tail_s", 5.0)
    return [r for r in rows if head <= (r["tCapture"] - t0) / 1000.0 <= span - tail]


def owner_of(row):
    return ((row.get("cubes_raw") or {}).get("large", {}) or {}).get("owner")


def hand_by_label(row, label):
    for h in row.get("hands") or []:
        if h.get("label") == label:
            return h
    return None


def palm_centre_and_scale(hand):
    """Palm centre in px and palm width in px, from the shared block view --
    the same functions production's anchor and scale reasoning use."""
    lm = [tuple(p) for p in hand["landmarks"]]
    return hand_blocks.palm_position(lm), hand_blocks.palm_scale(lm)


# A hand within this many palm widths of where the owner hand just was is the
# same physical hand, not a second one. DR-1 resolves identity by position at the
# same scale; the value is loose on purpose, because the question here is "same
# hand or a different one", not "how far did it move".
RELABEL_PALM_WIDTHS = 2.0


def _relabel_or_other(before, span, owner):
    """RELABEL = the owner's own hand came back under the other label (T3).
    OTHER = a genuinely different hand is in frame and the owner's is gone."""
    b, bs = palm_centre_and_scale(hand_by_label(before, owner))
    if b is None or not bs:
        return "OTHER"
    for r in span:
        for h in r.get("hands") or []:
            if h.get("label") == owner:
                continue
            p, _ = palm_centre_and_scale(h)
            if p is None:
                continue
            if math.hypot(p[0] - b[0], p[1] - b[1]) / bs <= RELABEL_PALM_WIDTHS:
                return "RELABEL"
    return "OTHER"


def gaps_for(rows):
    """Every run of frames in which the hand that HELD the cube is absent, with
    the frames either side. Yields dicts; `after` is None if the take ends
    inside the gap."""
    out = []
    i = 0
    while i < len(rows):
        owner = owner_of(rows[i])
        if owner is None or hand_by_label(rows[i], owner) is None:
            i += 1
            continue
        # rows[i] holds the cube and the owner hand is visible: a gap can start
        # at i+1.
        j = i + 1
        while j < len(rows) and hand_by_label(rows[j], owner) is None:
            j += 1
        if j > i + 1:
            # ⭐ WHY THE OWNER HAND IS MISSING IS NOT ONE QUESTION. Production's
            # `_is_detected` is PER HAND, so it fires both when MediaPipe found
            # nothing (a real dropout -- D2's business) and when it found a hand
            # but under the OTHER label (an identity flip -- T3's business, which
            # DR-1 already attacks from the other end). Bridging is the right
            # answer to the first and at best an accident on the second, so they
            # must never be pooled into one headline.
            span = rows[i + 1:j]
            other = sum(1 for r in span if r.get("hands"))
            cause = "DROPOUT" if other == 0 else ("IDENTITY" if other == len(span) else "MIXED")
            if cause != "DROPOUT":
                # ⚠ "a hand is present under another label" is still two different
                # things, and they have opposite fixes. If that hand is sitting
                # roughly where the owner hand just was, it IS the owner hand
                # wearing the wrong label -- T3, and bridging would only paper
                # over it. If it is somewhere else, it is a genuinely different
                # hand and the owner's really did leave. Same position test DR-1
                # itself uses, at the same palm-width scale.
                cause += "/" + _relabel_or_other(rows[i], span, owner)
            out.append({
                "owner": owner,
                "cause": cause,
                "before": rows[i],
                "after": rows[j] if j < len(rows) else None,
                # The frames the resync blend actually runs over, so D3 can be
                # replayed against the hand's real post-gap trajectory instead of
                # assumed to divide the step by the blend length.
                "after_rows": rows[j:j + 8],
                "frames": j - i - 1,
                "ms": ((rows[j]["tCapture"] if j < len(rows) else rows[-1]["tCapture"])
                       - rows[i]["tCapture"]),
                # ms from the last measurement to each missed frame, which is what
                # `hand_state` thresholds.
                "miss_ms": [rows[k]["tCapture"] - rows[i]["tCapture"] for k in range(i + 1, j)],
            })
        i = j
    return out


def classify(gap, window_ms):
    """Where this gap lands for a given coast window. Mirrors
    `hand_state.HandStateTracker`: a missed frame bridges while its staleness is
    <= the window, and a zero window never bridges at all."""
    if window_ms <= 0.0:
        return "LATE_RELEASE", 0.0, None      # today: released on the first miss
    if gap["after"] is None:
        return "UNRESOLVED", None, None
    survived = [m for m in gap["miss_ms"] if m <= window_ms]
    if len(survived) < gap["frames"]:
        # Released mid-gap. The added hang time is the last bridged frame's
        # staleness -- the extra time the player watched the cube stay put.
        return "LATE_RELEASE", (survived[-1] if survived else 0.0), None
    b, bs = palm_centre_and_scale(hand_by_label(gap["before"], gap["owner"]))
    a, _ = palm_centre_and_scale(hand_by_label(gap["after"], gap["owner"]))
    if b is None or a is None or not bs:
        return "UNRESOLVED", None, None
    moved = math.hypot(a[0] - b[0], a[1] - b[1]) / bs
    return ("POP" if moved > POP_PALM_WIDTHS else "SAVED"), 0.0, moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    a = ap.parse_args()

    gaps, no_hand_at_all, held_frames, take_count = [], 0, 0, 0
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
            continue
        take_count += 1
        name = meta.get("sequence", os.path.basename(d))
        for g in gaps_for(sub):
            g["take"] = name
            gaps.append(g)
        held_frames += sum(1 for r in sub if owner_of(r))
        prev_held = False
        for r in sub:
            if not (r.get("hands") or []) and prev_held:
                no_hand_at_all += 1
            prev_held = bool(owner_of(r))

    print("=" * 96)
    print("D2 -- BRIDGING, CLASSIFIED (never a count of drops removed)")
    print("=" * 96)
    by_cause = {}
    for g in gaps:
        by_cause.setdefault(g["cause"], []).append(g)
    print(f"  {take_count} takes, {held_frames} held frames, "
          f"{len(gaps)} releases of the OWNER hand while a cube was held")
    for cause in sorted(by_cause):
        sub = by_cause[cause]
        m = sorted(g["ms"] for g in sub)
        print(f"    {cause:<9} {len(sub):>4}   gap ms: median {m[len(m)//2]:>5.0f}"
              f"   p90 {m[int(.9*len(m))]:>6.0f}   max {m[-1]:>6.0f}")
    if not gaps:
        print("  nothing to classify")
        return
    print()
    print("  ⚠ ONLY THE `DROPOUT` ROW IS D2's. `IDENTITY` is MediaPipe finding the")
    print("    hand under the other label -- queue T3, which DR-1 already attacks")
    print("    at source. Bridging would paper over it, so it is reported apart and")
    print("    the window is NOT chosen on it.")

    for cause in [c for c in sorted(by_cause) if by_cause[c]]:
        sub = by_cause[cause]
        print()
        print(f"  ── {cause} ({len(sub)} releases) " + "─" * (66 - len(cause)))
        print(f"  {'window':>8}{'SAVED':>8}{'POP':>7}{'LATE':>7}{'UNRES':>7}"
              f"{'  saved%':>9}{'  pop/save':>11}   added hang (ms, median/max)")
        for w in WINDOWS_MS:
            counts = {"SAVED": 0, "POP": 0, "LATE_RELEASE": 0, "UNRESOLVED": 0}
            hangs = []
            for g in sub:
                k, hang, _moved = classify(g, w)
                counts[k] += 1
                if k == "LATE_RELEASE" and hang:
                    hangs.append(hang)
            n = counts["SAVED"] + counts["POP"] + counts["LATE_RELEASE"]
            hs = sorted(hangs)
            hang_s = (f"{hs[len(hs)//2]:.0f} / {hs[-1]:.0f}" if hs else "-")
            ratio = (counts["POP"] / counts["SAVED"]) if counts["SAVED"] else float("inf")
            print(f"  {w:>7.0f}{counts['SAVED']:>8}{counts['POP']:>7}"
                  f"{counts['LATE_RELEASE']:>7}{counts['UNRESOLVED']:>7}"
                  f"{100.0*counts['SAVED']/max(1, n):>8.0f}%{ratio:>11.2f}   {hang_s}")

    print()
    print("  ⭐ READ THE `pop/save` COLUMN, NOT `saved%`. Item 1.6's reversal was")
    print("     exactly a high headline rate hiding a bad ratio of harm to help.")
    print()
    gaps = by_cause.get("DROPOUT", [])

    # The resume displacement distribution, which is what D3's blend has to
    # absorb -- and the evidence for whether D3 must precede shipping D2.
    w = _shipped("BRIDGE_WINDOW_MS", "hand_state.py", 150.0)
    moves = sorted(m for m in (classify(g, w)[2] for g in gaps) if m is not None)
    if moves:
        print(f"  RESUME DISPLACEMENT, DROPOUT gaps only, at the SHIPPED "
              f"{w:.0f} ms window (palm widths, {len(moves)} resumes)")
        print(f"    median {moves[len(moves)//2]:.2f}   p90 {moves[int(.9*len(moves))]:.2f}"
              f"   max {moves[-1]:.2f}")
        for cut in (0.25, 0.5, 1.0, 2.0):
            print(f"    <= {cut:>4} palm widths: "
                  f"{sum(1 for m in moves if m <= cut):>3}/{len(moves)}")
        print("    ⚠ This is what the cube does on the resume frame with NO blend.")
        print("      It is the size of the problem queue D3 exists to absorb.")

    # ── D3, replayed rather than modelled ────────────────────────────────────
    # The tempting shortcut is "a 3-frame blend divides the step by 3". It does
    # not: the hand keeps moving during the blend, so the real question is what
    # the WORST SINGLE-FRAME cube step becomes over the whole resume, and that
    # can only be answered against the trajectory the hand actually took.
    # Working in hand-position space is exact here -- under §14.1 the held cube
    # is that position plus an offset frozen at grab, so the two step together.
    print()
    print(f"  ── D3 RESYNC BLEND, replayed over the real post-gap frames "
          f"({RESYNC_BLEND_FRAMES}-frame lerp) ──")
    raw_steps, blend_steps = [], []
    for g in gaps:
        if classify(g, w)[0] not in ("SAVED", "POP"):
            continue
        b, bs = palm_centre_and_scale(hand_by_label(g["before"], g["owner"]))
        if b is None or not bs:
            continue
        path = []
        for r in g["after_rows"]:
            h = hand_by_label(r, g["owner"])
            if h is None:
                break
            p, _ = palm_centre_and_scale(h)
            if p is None:
                break
            path.append(p)
        if len(path) < RESYNC_BLEND_FRAMES + 1:
            continue
        # No blend: the cube is set to the measurement every frame.
        prev, worst = b, 0.0
        for p in path:
            worst = max(worst, math.hypot(p[0] - prev[0], p[1] - prev[1]) / bs)
            prev = p
        raw_steps.append(worst)
        # With the blend, exactly as production runs it: t = 1 / frames_left, so
        # the final step lands on the measurement with no residual offset.
        c, left, worst = b, RESYNC_BLEND_FRAMES, 0.0
        for p in path:
            t = 1.0 / left if left > 0 else 1.0
            nc = (c[0] + (p[0] - c[0]) * t, c[1] + (p[1] - c[1]) * t)
            worst = max(worst, math.hypot(nc[0] - c[0], nc[1] - c[1]) / bs)
            c, left = nc, max(0, left - 1)
        blend_steps.append(worst)
    if raw_steps:
        rs, bl = sorted(raw_steps), sorted(blend_steps)
        print(f"    worst single-frame cube step over the resume, palm widths "
              f"({len(rs)} resumes)")
        print(f"      no blend : median {rs[len(rs)//2]:.2f}   "
              f"p90 {rs[int(.9*len(rs))]:.2f}   max {rs[-1]:.2f}")
        print(f"      D3 blend : median {bl[len(bl)//2]:.2f}   "
              f"p90 {bl[int(.9*len(bl))]:.2f}   max {bl[-1]:.2f}")
        worse = sum(1 for a, c in zip(raw_steps, blend_steps) if c > a + 1e-9)
        print(f"      resumes made WORSE by blending: {worse}/{len(rs)}")
        print("      ⚠ `worse` is the number that matters. A smoother that helps")
        print("        on average and hurts on some cases is how 1.6 passed.")
    print()
    print(f"  ⓘ cross-check against D0: {no_hand_at_all} gaps by D0's "
          f"no-hand-at-all definition, {len(gaps)} DROPOUT gaps here")
    print("=" * 96)


if __name__ == "__main__":
    main()
