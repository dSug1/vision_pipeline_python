"""Does M3a's validity bit actually PREDICT the large orientation jumps?

THE GATE ON ITEM 1.6. Item 1.5 established that the anatomical constraints are
clean (0.00% on the control) and that they fire more often in poses where
MediaPipe is documented to fail. That is NOT the same claim as "they fire on the
frames that actually go wrong", and only the second one makes them useful:

  * if violations coincide with the >60 deg jumps, the bit is a real predictor
    and 1.6 has something to gate on;
  * if they are disjoint -- violations on frames the pipeline already handles,
    jumps on frames that look anatomically fine -- then gating on it cannot help
    T1/T2, and under A10 item 1.5 should be REVERTED rather than carried forward
    on the strength of a good false-positive rate.

METHOD. Streams are built the way `audit_jump_provenance.build_v2()` builds them
-- DR-1 identity replay, duplicate-label frames dropped, runs broken at frame
index gaps -- because per-frame DELTAS are exactly what identity contamination
corrupts (spec 0.15, binding rule). The primitives are IMPORTED from that module
rather than reimplemented, and the resulting jump census is CHECKED against
build_v2()'s own, so a silent divergence in stream construction cannot pass.

Run from the parent directory:
    .venv/Scripts/python.exe analysis/m3a_predicts_jumps.py
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importing this loads the whole corpus at module level (its SESSIONS global).
import audit_jump_provenance as AJP
from Resources import hand_anatomy

JUMP_LEVELS = (30.0, 60.0)


def build_v2_with_anatomy():
    """build_v2()'s stream construction, carrying the M3a verdict per entry.

    Mirrors AJP.build_v2 exactly; `verify_matches_build_v2` below proves it.
    Entries are (rec_idx, quat, obs, anat_valid) or None for a run break.
    """
    out = []
    for name, frames in AJP.SESSIONS:
        trk = AJP.HandIdentityTracker(log=lambda *a, **k: None)
        streams = {}
        last_idx = {}
        for i, rec in enumerate(frames):
            hands = rec.get("hands") or []
            obs_list = []
            keep = []
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
                q, obs = AJP.quat_of(h)
                if q is None:
                    continue
                anat = hand_anatomy.evaluate(h["world_landmarks"])
                st = streams.setdefault(lab, [])
                if lab in last_idx and last_idx[lab] != i - 1:
                    st.append(None)
                st.append((i, q, obs, anat["valid"]))
                last_idx[lab] = i
        out.append((name, streams))
    return out


def census(streams_per_session, level):
    n = 0
    for _name, streams in streams_per_session:
        for entries in streams.values():
            prev = None
            for e in entries:
                if e is None:
                    prev = None
                    continue
                q = e[1]
                if prev is not None:
                    if AJP.angle_between(q, AJP.cont(prev, q)) > level:
                        n += 1
                prev = q
    return n


def verify_matches_build_v2(mine):
    """A stream built differently measures a different pipeline. Prove it isn't."""
    theirs = AJP.build_v2()
    ok = True
    for level in JUMP_LEVELS:
        mine_n = census(mine, level)
        theirs_n = census(theirs, level)
        if mine_n != theirs_n:
            print(f"  [FAIL] >{level:.0f} deg: mine={mine_n} build_v2={theirs_n}")
            ok = False
        else:
            print(f"  [PASS] >{level:.0f} deg census matches build_v2: {mine_n}")
    return ok


def contingency(streams_per_session, level):
    """Cross the M3a verdict against 'this transition is a big jump'.

    A jump is a property of a TRANSITION (k-1 -> k), while validity is a
    property of a FRAME, so both endpoints are reported: the bad landmark that
    produced the jump may sit at either end.
    """
    stats = {
        "transitions": 0, "jumps": 0,
        "viol_cur": 0, "jump_and_viol_cur": 0,
        "viol_either": 0, "jump_and_viol_either": 0,
    }
    for _name, streams in streams_per_session:
        for entries in streams.values():
            prev = None
            for e in entries:
                if e is None:
                    prev = None
                    continue
                _idx, q, _obs, valid = e
                if prev is not None:
                    pq, pvalid = prev
                    d = AJP.angle_between(q, AJP.cont(pq, q))
                    is_jump = d > level
                    v_cur = not valid
                    v_either = (not valid) or (not pvalid)
                    stats["transitions"] += 1
                    stats["jumps"] += is_jump
                    stats["viol_cur"] += v_cur
                    stats["viol_either"] += v_either
                    stats["jump_and_viol_cur"] += (is_jump and v_cur)
                    stats["jump_and_viol_either"] += (is_jump and v_either)
                prev = (q, valid)
    return stats


def report(stats, level):
    t = stats["transitions"]
    j = stats["jumps"]
    print(f"\n--- jumps > {level:.0f} deg ---")
    if not t or not j:
        print("  (no data)")
        return
    print(f"  transitions {t}, jumps {j}  (base rate {100.0*j/t:.2f}%)")
    for tag, vkey, jkey in (("violation on the CURRENT frame", "viol_cur", "jump_and_viol_cur"),
                            ("violation on EITHER endpoint", "viol_either", "jump_and_viol_either")):
        v = stats[vkey]
        jv = stats[jkey]
        if not v or v == t:
            print(f"  {tag}: degenerate (v={v}/{t})")
            continue
        p_jump_given_viol = jv / v
        p_jump_given_ok = (j - jv) / (t - v)
        lift = (p_jump_given_viol / p_jump_given_ok) if p_jump_given_ok else float("inf")
        coverage = jv / j
        print(f"  {tag}:")
        print(f"    flagged frames             {v}/{t} = {100.0*v/t:.1f}%")
        print(f"    P(jump | violation)        {100.0*p_jump_given_viol:.2f}%")
        print(f"    P(jump | anatomically ok)  {100.0*p_jump_given_ok:.2f}%")
        print(f"    LIFT                       {lift:.2f}x")
        print(f"    COVERAGE (jumps flagged)   {jv}/{j} = {100.0*coverage:.1f}%")


def main():
    print("=" * 78)
    print("Does M3a's validity bit predict the large orientation jumps?")
    print("The gate on item 1.6 -- see this file's docstring.")
    print("=" * 78)

    print("\n--- stream-construction check (must match build_v2) ---")
    mine = build_v2_with_anatomy()
    if not verify_matches_build_v2(mine):
        raise SystemExit("stream construction diverged from build_v2 -- "
                         "the numbers below would describe a different pipeline")

    for level in JUMP_LEVELS:
        report(contingency(mine, level), level)

    print("\n" + "=" * 78)
    print("READING THIS: lift ~1.0 means the bit carries NO information about")
    print("jumps -- under A10 that is grounds to revert 1.5, not to build 1.6 on")
    print("it. High lift with low coverage means it is precise but partial: a")
    print("useful gate, but not a fix for T1/T2 on its own.")
    print("=" * 78)


if __name__ == "__main__":
    main()
