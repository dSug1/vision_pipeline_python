"""M3a anatomical-constraint violation rates across the corpus (queue item 1.5).

Answers the only two questions that decide whether M3a is worth shipping under
A10:

  1. FALSE POSITIVE RATE. On `static_hold` -- a deliberately still, ordinary,
     anatomically valid pose -- the violation rate must be ~0. Every violation
     there is by definition a false positive, and a validity bit that fires on
     good frames is worse than no validity bit, because 1.6 would gate away
     frames it should trust.

  2. DETECTION RATE where MediaPipe is known to fail. If the constraints fire no
     more often on the back-of-hand and finger-occlusion takes than on the
     control, M3a has no signal and, per A10, is not shipped.

A note on the binding stream rule (spec 0.15): replay harnesses must build
streams via `audit_jump_provenance.build_v2()` because per-frame DELTAS are
corrupted by identity contamination. This measurement is PER-FRAME and
identity-free -- each detected hand is judged on its own 21 landmarks with no
reference to any other frame -- so duplicate labels and association swaps cannot
affect it. Streams are therefore not built here, deliberately, and the raw
handedness label is used only to break results down for display, never to
compare across frames.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/m3a_violations.py
"""
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from Resources import hand_anatomy

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# The control first, then the takes recorded specifically to contain failures.
CONTROL = "static_hold"


def load_sessions():
    out = []
    for d in sorted(glob.glob(os.path.join(ROOT, "*"))):
        p = os.path.join(d, "raw_landmarks.jsonl")
        m = os.path.join(d, "meta.json")
        if not (os.path.exists(p) and os.path.exists(m)):
            continue
        with open(m, encoding="utf-8") as f:
            meta = json.load(f)
        with open(p, encoding="utf-8") as f:
            frames = [json.loads(line) for line in f if line.strip()]
        out.append((os.path.basename(d), meta, frames))
    return out


def analyse(frames):
    """Per-hand-frame violation stats for one session.

    Also broken down BY HANDEDNESS LABEL. That is not cosmetic: two 2026-08-04
    takes requested as single-hand turned out to contain a second, motionless
    hand in view, and without this split its violations would be silently
    attributed to the hand the take was actually about. The label is used only
    to group within a session -- never to compare across frames (spec 0.15).
    """
    total = 0
    bad = 0
    rule_counts = {}
    senses = []
    per_label = {}
    for rec in frames:
        for h in (rec.get("hands") or []):
            wl = h.get("world_landmarks")
            if not wl:
                continue
            total += 1
            lab = h.get("handedness", "?")
            slot = per_label.setdefault(lab, [0, 0])
            slot[0] += 1
            res = hand_anatomy.evaluate(wl)
            if res["worst_sense"] is not None:
                senses.append(res["worst_sense"])
            if not res["valid"]:
                bad += 1
                slot[1] += 1
                for v in res["violations"]:
                    # bucket by rule type, not by finger, so counts are readable
                    if "bends against" in v:
                        key = "DIP vs PIP reversal (bas-relief)"
                    elif "out of plane" in v:
                        key = "IP out of plane (hinge)"
                    elif "abduction" in v:
                        key = "MCP abduction over limit"
                    else:
                        key = "joint flexion over limit"
                    rule_counts[key] = rule_counts.get(key, 0) + 1
    return total, bad, rule_counts, senses, per_label


def main():
    sessions = load_sessions()
    if not sessions:
        raise SystemExit(f"No sessions found under {ROOT} -- is E: connected?")

    rows = []
    for name, meta, frames in sessions:
        total, bad, rules, senses, per_label = analyse(frames)
        if not total:
            continue
        rows.append({
            "name": name,
            "sequence": meta.get("sequence", name),
            "fps": meta.get("measured_fps"),
            "hand_frames": total,
            "violating": bad,
            "pct": 100.0 * bad / total,
            "rules": rules,
            "per_label": per_label,
            "p01_sense": (sorted(senses)[max(0, int(0.01 * len(senses)) - 1)]
                          if senses else None),
        })

    # ---- the control, and therefore the false-positive rate ----
    controls = [r for r in rows if r["sequence"] == CONTROL]
    print("=" * 78)
    print("M3a ANATOMICAL CONSTRAINTS -- violation rates (queue item 1.5)")
    print("=" * 78)
    print()
    print("CONTROL (valid poses -- any violation here is a FALSE POSITIVE):")
    for r in controls:
        print(f"  {r['sequence']:<32} {r['violating']:>6}/{r['hand_frames']:<6} "
              f"= {r['pct']:6.2f}%   ({r['fps']} fps)")
    if controls:
        fp = sum(r["violating"] for r in controls) / sum(r["hand_frames"] for r in controls)
        print(f"  -> pooled false-positive rate: {100 * fp:.2f}%")
    print()

    print("ALL SESSIONS, worst first:")
    print(f"  {'sequence':<34}{'fps':>7}{'frames':>9}{'viol':>8}{'pct':>9}")
    for r in sorted(rows, key=lambda r: -r["pct"]):
        print(f"  {r['sequence']:<34}{str(r['fps']):>7}{r['hand_frames']:>9}"
              f"{r['violating']:>8}{r['pct']:>8.2f}%")
    print()

    agg = {}
    for r in rows:
        for k, v in r["rules"].items():
            agg[k] = agg.get(k, 0) + v
    print("WHICH RULE FIRES (all sessions pooled):")
    if agg:
        for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<34}{v:>8}")
    else:
        print("  (none fired anywhere)")
    print()

    print("PER-HAND BREAKDOWN (sessions with more than one label present):")
    multi = [r for r in rows if len(r["per_label"]) > 1]
    if multi:
        print(f"  {'session':<40}{'label':>8}{'frames':>9}{'viol':>8}{'pct':>9}")
        for r in sorted(multi, key=lambda r: r["name"]):
            for lab, (n, b) in sorted(r["per_label"].items()):
                print(f"  {r['name'][:39]:<40}{lab:>8}{n:>9}{b:>8}"
                      f"{100.0 * b / n:>8.2f}%")
    else:
        print("  (none)")
    print()

    total_frames = sum(r["hand_frames"] for r in rows)
    total_bad = sum(r["violating"] for r in rows)
    print(f"CORPUS TOTAL: {total_bad}/{total_frames} hand-frames violate "
          f"= {100.0 * total_bad / total_frames:.2f}%")


if __name__ == "__main__":
    main()
