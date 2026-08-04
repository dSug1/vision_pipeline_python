"""Why does M3a fire on the CONTROL take? Distributions, not verdicts.

The first m3a_violations.py run reported a 93.7% violation rate on static_hold.
That is a broken constraint, not a broken hand, so this dumps the underlying
quantities rather than adjusting any threshold.

Leading hypothesis to test: the "all bends of a finger agree in rotation sense"
rule is anatomically WRONG at the MCP. A resting hand can hyperextend the MCP
while flexing the PIP/DIP, which reverses the MCP axis relative to the IP axes
legitimately. If so, the sense rule belongs to the PIP<->DIP pair ONLY.

    .venv/Scripts/python.exe analysis/m3a_diagnose.py [sequence]
"""
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from Resources import hand_anatomy as A

ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"
TARGET = sys.argv[1] if len(sys.argv) > 1 else "static_hold"


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(p / 100.0 * len(s))))]


def show(label, vals, unit=""):
    if not vals:
        print(f"  {label:<28} (no samples)")
        return
    print(f"  {label:<28} n={len(vals):<6} "
          f"p05={pct(vals,5):7.2f} p50={pct(vals,50):7.2f} "
          f"p95={pct(vals,95):7.2f} min={min(vals):7.2f} max={max(vals):7.2f}{unit}")


def main():
    dirs = [d for d in sorted(glob.glob(os.path.join(ROOT, "*")))
            if TARGET in os.path.basename(d)]
    if not dirs:
        raise SystemExit(f"no session matching {TARGET!r}")

    mcp_b, pip_b, dip_b = [], [], []
    dot_mcp_pip, dot_pip_dip = [], []
    hinge_old, hinge_new = [], []

    for d in dirs:
        p = os.path.join(d, "raw_landmarks.jsonl")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            frames = [json.loads(l) for l in f if l.strip()]
        for rec in frames:
            for h in (rec.get("hands") or []):
                wl = h.get("world_landmarks")
                if not wl:
                    continue
                w = [tuple(v) for v in wl]
                for finger in A.FINGERS.values():
                    mcp, pip, dip, tip = finger
                    bones = (A._sub(w[mcp], w[A.WRIST]), A._sub(w[pip], w[mcp]),
                             A._sub(w[dip], w[pip]), A._sub(w[tip], w[dip]))
                    angs = [A._angle_between(bones[i], bones[i + 1]) for i in range(3)]
                    if angs[0] is not None:
                        mcp_b.append(angs[0])
                    if angs[1] is not None:
                        pip_b.append(angs[1])
                    if angs[2] is not None:
                        dip_b.append(angs[2])

                    axes = []
                    for i in range(3):
                        if angs[i] is None or angs[i] < A.MIN_BEND_DEG:
                            axes.append(None)
                        else:
                            axes.append(A._unit(A._cross(bones[i], bones[i + 1])))
                    if axes[0] and axes[1]:
                        dot_mcp_pip.append(A._dot(axes[0], axes[1]))
                    if axes[1] and axes[2]:
                        dot_pip_dip.append(A._dot(axes[1], axes[2]))

                    # current hinge definition: plane from metacarpal x proximal
                    hv = A.hinge_violation(w, finger)
                    if hv is not None:
                        hinge_old.append(hv)
                    # proposed: plane from proximal x middle, test the distal bone
                    if angs[1] is not None and angs[1] >= A.MIN_BEND_DEG:
                        n2 = A._unit(A._cross(bones[1], bones[2]))
                        u = A._unit(bones[3])
                        if n2 and u:
                            import math
                            out = abs(90.0 - math.degrees(math.acos(
                                max(-1.0, min(1.0, A._dot(u, n2))))))
                            hinge_new.append(out)

    print("=" * 78)
    print(f"M3a DIAGNOSTIC on {TARGET!r}  ({len(dirs)} session(s))")
    print("=" * 78)
    print("\nBEND ANGLES (deg, 0 = straight):")
    show("MCP bend", mcp_b)
    show("PIP bend", pip_b)
    show("DIP bend", dip_b)

    print("\nROTATION-SENSE AGREEMENT (dot of successive joint axes, want >= 0):")
    show("dot(MCP axis, PIP axis)", dot_mcp_pip)
    show("dot(PIP axis, DIP axis)", dot_pip_dip)
    for label, vals in (("MCP-PIP", dot_mcp_pip), ("PIP-DIP", dot_pip_dip)):
        if vals:
            neg = sum(1 for v in vals if v < 0)
            print(f"    {label}: {neg}/{len(vals)} = {100.0*neg/len(vals):.1f}% NEGATIVE")

    print("\nHINGE OUT-OF-PLANE (deg):")
    show("current (metacarpal x prox)", hinge_old)
    show("proposed (prox x middle)", hinge_new)


if __name__ == "__main__":
    main()
