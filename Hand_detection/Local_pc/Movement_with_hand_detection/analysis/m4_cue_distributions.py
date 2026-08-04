"""What do M4's consistency cues actually look like? (queue item 1.6, step 1)

Thresholds get DERIVED here, not guessed and then tuned until the corpus goes
quiet -- that is the trap 0.14 records against M2, and the approach that worked
for 1.5 (0.16: the control take exposed a wrong constraint in one run).

Cues measured, all SCALE-FREE (divided by palm width), because the same gesture
at half the distance must not read as twice the error:

  innovation  |pos(k) - (pos(k-1) + v(k-1))| / palm_width
              The position residual against a constant-velocity prediction from
              the LAST ACCEPTED frame. This is M4's core quantity and the one
              0.13.3's binding rule is about. A whole-hand teleport (the Object
              Jump Correction symptom, T3) should be enormous here while genuine
              fast motion stays small, because genuine motion is predictable.

  step        |pos(k) - pos(k-1)| / palm_width
              Raw displacement, no velocity model. Kept for comparison: if step
              separates as well as innovation, the velocity model is not
              earning its keep and the simpler cue should win.

  width_ratio palm_width(k) / palm_width(k-1)
              Palm-pixel-width collapse (S5). A hand cannot change apparent size
              abruptly; a collapse means the landmark fit has failed.

  bone_dev    max relative frame-to-frame change over the 5 palm bones (world)
              GROSS outlier flag only, at the ~6-10% precision this sensor
              actually supports -- NOT M2's dead 2% (0.14/0.15).

Each is reported overall and CONDITIONED on the frame being a >60 deg
orientation jump, because separation between those two columns is the whole
question: a cue that looks the same on both carries no information.

Streams are built as build_v2() builds them (binding rule, spec 0.15).

    .venv/Scripts/python.exe analysis/m4_cue_distributions.py
"""
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_jump_provenance as AJP
from Resources import hand_anatomy

PALM_BONES = ((0, 5), (5, 9), (9, 13), (13, 17), (0, 17))


def _d3(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def palm_bone_lengths(world):
    return [_d3(world[i], world[j]) for i, j in PALM_BONES]


def pct(vals, p):
    if not vals:
        return float("nan")
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))]


def build():
    """v2 streams carrying everything the cues need, per entry."""
    out = []
    for name, frames in AJP.SESSIONS:
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        streams = {}
        last_idx = {}
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs_list, keep = [], []
            for h in hands:
                pts = [tuple(p) for p in h["landmarks"]]
                cen = AJP.palm_centroid(pts)
                if cen is None:
                    continue
                obs_list.append((cen, h["handedness"], h.get("score", 1.0),
                                 AJP.palm_width(pts)))
                keep.append(h)
            if not obs_list:
                trk.update([])
                continue
            assigned = trk.update(obs_list)
            for h, lab in zip(keep, assigned):
                q, _obs = AJP.quat_of(h)
                if q is None:
                    continue
                pts = [tuple(p) for p in h["landmarks"]]
                cen = AJP.palm_centroid(pts)
                wid = AJP.palm_width(pts)
                if cen is None or not wid or wid <= 1e-6:
                    continue
                world = [tuple(v) for v in h["world_landmarks"]]
                st = streams.setdefault(lab, [])
                if lab in last_idx and last_idx[lab] != i - 1:
                    st.append(None)
                st.append({
                    "q": q, "cen": cen, "width": wid,
                    "bones": palm_bone_lengths(world),
                    "anat_ok": hand_anatomy.evaluate(world)["valid"],
                })
                last_idx[lab] = i
        out.append((name, streams))
    return out


def main():
    print("=" * 78)
    print("M4 consistency-cue distributions (queue item 1.6, step 1)")
    print("=" * 78)

    cues = {k: {"all": [], "jump": []} for k in
            ("innovation", "step", "width_ratio", "bone_dev")}
    n_trans = n_jump = 0
    anat_flagged_jump = 0

    global STREAMS
    STREAMS = build()
    for _name, streams in STREAMS:
        for entries in streams.values():
            prev = prev2 = None
            for e in entries:
                if e is None:
                    prev = prev2 = None
                    continue
                if prev is not None:
                    w = prev["width"]
                    step = math.dist(e["cen"], prev["cen"]) / w
                    if prev2 is not None:
                        vx = prev["cen"][0] - prev2["cen"][0]
                        vy = prev["cen"][1] - prev2["cen"][1]
                        pred = (prev["cen"][0] + vx, prev["cen"][1] + vy)
                        innov = math.dist(e["cen"], pred) / w
                    else:
                        innov = None
                    wr = e["width"] / w
                    bd = max(abs(a - b) / b for a, b in zip(e["bones"], prev["bones"])
                             if b > 1e-9)

                    is_jump = AJP.angle_between(e["q"], AJP.cont(prev["q"], e["q"])) > 60.0
                    n_trans += 1
                    n_jump += is_jump
                    if is_jump and not (e["anat_ok"] and prev["anat_ok"]):
                        anat_flagged_jump += 1

                    for key, val in (("innovation", innov), ("step", step),
                                     ("width_ratio", abs(math.log(wr)) if wr > 0 else None),
                                     ("bone_dev", bd)):
                        if val is None:
                            continue
                        cues[key]["all"].append(val)
                        if is_jump:
                            cues[key]["jump"].append(val)
                prev2 = prev
                prev = e

    print(f"\ntransitions {n_trans}, >60deg jumps {n_jump} "
          f"({100.0*n_jump/n_trans:.2f}%)")
    print(f"M3a flags {anat_flagged_jump}/{n_jump} of them "
          f"({100.0*anat_flagged_jump/n_jump:.1f}%) -- the 0.16 coverage figure\n")

    print(f"{'cue':<14}{'set':>7}{'p50':>10}{'p95':>10}{'p99':>10}"
          f"{'p99.5':>10}{'p99.9':>10}{'max':>10}")
    for key in ("innovation", "step", "width_ratio", "bone_dev"):
        for setname in ("all", "jump"):
            v = cues[key][setname]
            if not v:
                continue
            print(f"{key if setname=='all' else '':<14}{setname:>7}"
                  f"{pct(v,50):>10.3f}{pct(v,95):>10.3f}{pct(v,99):>10.3f}"
                  f"{pct(v,99.5):>10.3f}{pct(v,99.9):>10.3f}{max(v):>10.3f}")
        print()

    # ---- Does M3a cover the POSITION failures too, or only orientation? ----
    # The 0.16 exculpator statistic is about ORIENTATION jumps. The documented
    # Object Jump mechanism (14.1.4 / T3) is a whole-hand teleport in which all
    # landmarks move together COHERENTLY -- so the teleported hand may be
    # anatomically perfect. If that is true, "M3a valid -> accept" would wave
    # teleports straight through, and the position check must run on EVERY frame
    # rather than only on M3a-flagged ones.
    print("\n--- is a large POSITION innovation visible to M3a? ---")
    for thr in (0.5, 1.0, 2.0):
        big = big_and_anat_ok = 0
        for _name, streams in STREAMS:
            for entries in streams.values():
                prev = prev2 = None
                for e in entries:
                    if e is None:
                        prev = prev2 = None
                        continue
                    if prev is not None and prev2 is not None:
                        vx = prev["cen"][0] - prev2["cen"][0]
                        vy = prev["cen"][1] - prev2["cen"][1]
                        pred = (prev["cen"][0] + vx, prev["cen"][1] + vy)
                        innov = math.dist(e["cen"], pred) / prev["width"]
                        if innov > thr:
                            big += 1
                            if e["anat_ok"] and prev["anat_ok"]:
                                big_and_anat_ok += 1
                    prev2 = prev
                    prev = e
        if big:
            print(f"  innovation > {thr:>4}: {big:>5} frames, of which "
                  f"{big_and_anat_ok:>5} are anatomically VALID "
                  f"({100.0*big_and_anat_ok/big:.1f}%) -> M3a would MISS these")

    print()
    print("READING THIS: a usable gate needs the 'jump' row to sit far above the")
    print("'all' row. Set the threshold near 'all' p99.5+ so ordinary motion is")
    print("not rejected -- rejections must stay rare for S5's 1-2 frame")
    print("anti-cascade cap to be satisfiable at all.")
    print("=" * 78)


if __name__ == "__main__":
    main()
