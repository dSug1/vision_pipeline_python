"""U7 STEP 0 -- is chirality recoverable from the LANDMARKS, without the label?

THIS IS A MEASUREMENT, NOT A BUILD. It decides whether U7's remedy (1) is viable
before a line of production code is touched.
See `Claude/HANDEDNESS_LABEL_DEFECT.md` and PART_ONE.md 3.1 row U7.

--------------------------------------------------------------------------------
THE CORRECTION THIS HARNESS RESTS ON
--------------------------------------------------------------------------------
`HANDEDNESS_LABEL_DEFECT.md` 5 proposes deriving the palm/back cue "from the 3D
palm normal in `world_landmarks` rather than from a 2D cross product that needs
chirality". WARNING: moving to 3D does not, on its own, remove the chirality
dependence. The shipped 2D signed area is already the z-component of
`cross(wrist->index_MCP, wrist->pinky_MCP)`; that normal points out of the BACK
for one chirality and out of the PALM for the other, in 2D and in 3D alike. A
left hand showing its palm and a right hand showing its back are mirror images,
and no function of the palm quad alone can separate them.

What DOES break the dependency is the THUMB, because it leaves the palm plane.
The signed volume

    V = det[ index_MCP - wrist , pinky_MCP - wrist , thumb_* - wrist ]

is invariant under rotation and translation and changes sign ONLY under
reflection. So `sign(V)` is a chirality measure computed from geometry, with no
MediaPipe label anywhere in it.

--------------------------------------------------------------------------------
GROUND TRUTH -- and the B4 rule
--------------------------------------------------------------------------------
Ground truth is the OPERATOR'S DECLARATION (`meta.json.known_hand`, or the
`known_<hand>_<facing>` sequence name), never `is_thumb_outward(px, label)`.
That circularity -- an anchor metric sharing an expression with the anchor -- is
exactly why the defect survived seven patches. Facing ground truth likewise comes
from the sequence name (`_palm` / `_back`), not from any computed cue.

ONE BIT IS FITTED: which sign of V means which chirality. It is fitted by
majority over the whole corpus and reported, so the reader can discount it. With
~3000 frames and 8 sessions, one bit is negligible -- but it is stated, not
hidden.

--------------------------------------------------------------------------------
THE MIRROR CONVENTION
--------------------------------------------------------------------------------
Detection runs on an ALREADY-MIRRORED frame in every session here, so the
apparent hand is the mirror of the physical one: a physical RIGHT hand must be
labelled `Left` (confirmed 751/751 by `VerifyChiralityFixture.py`). World
landmarks come from that same mirrored frame, so `sign(V)` and the label are
answering the same question and are directly comparable.
"""

import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Resources import palm_geometry as PG  # noqa: E402

SESSIONS_DIR = (r"E:\Python\Recordings for vision_pipeline"
                r"\Recordings_perception_layer\sessions")

WRIST = 0
INDEX_MCP = 5
PINKY_MCP = 17
# Candidate off-plane reference points, in increasing distance from the palm plane.
THUMB_CANDIDATES = {"thumb_CMC(1)": 1, "thumb_MCP(2)": 2,
                    "thumb_IP(3)": 3, "thumb_TIP(4)": 4}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def signed_palm_volume(world, thumb_idx):
    """det[v_index, v_pinky, v_thumb]. Rotation-invariant; flips under reflection."""
    w = world[WRIST]
    a = _sub(world[INDEX_MCP], w)
    b = _sub(world[PINKY_MCP], w)
    c = _sub(world[thumb_idx], w)
    return (a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0]))


def palm_thickness(world, thumb_idx):
    """|V| normalised by the palm quad's area -- the thumb's perpendicular
    distance from the palm plane, in metres. This is the CONDITIONING of the
    chirality sign, the exact analogue of `edge_on_measure` for the 2D sign.
    When it collapses, sign(V) is a coin flip."""
    w = world[WRIST]
    a = _sub(world[INDEX_MCP], w)
    b = _sub(world[PINKY_MCP], w)
    n = (a[1] * b[2] - a[2] * b[1],
         a[2] * b[0] - a[0] * b[2],
         a[0] * b[1] - a[1] * b[0])
    nn = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if nn < 1e-12:
        return 0.0
    return abs(signed_palm_volume(world, thumb_idx)) / nn


def load(session):
    """-> (meta, hands, multi, empty) for frames with exactly ONE hand.

    Multi-hand frames are dropped: the declaration names one physical hand, so a
    second hand in frame would break the ground truth. The count is reported."""
    path = os.path.join(SESSIONS_DIR, session)
    with open(os.path.join(path, "meta.json")) as f:
        meta = json.load(f)
    hands, multi, empty = [], 0, 0
    with open(os.path.join(path, "raw_landmarks.jsonl")) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            hh = d.get("hands") or []
            if not hh:
                empty += 1
                continue
            if len(hh) > 1:
                multi += 1
                continue
            h = hh[0]
            if not h.get("world_landmarks"):
                continue
            hands.append(h)
    return meta, hands, multi, empty


def declared(session, meta):
    """(physical hand, expected APPARENT label, declared facing or None)."""
    name = meta.get("sequence") or session
    kh = meta.get("known_hand")
    if kh:
        phys = kh.lower()
    elif "known_right" in name:
        phys = "right"
    elif "known_left" in name:
        phys = "left"
    else:
        return None, None, None
    # Mirrored capture: a physical right hand presents as apparent `Left`.
    apparent = "Left" if phys == "right" else "Right"
    facing = None
    if name.endswith("_palm"):
        facing = "palm"
    elif name.endswith("_back"):
        facing = "back"
    return phys, apparent, facing


def _corpus_acc(data, tidx, convention):
    n = ok = 0
    for d in data:
        for h in d["hands"]:
            v = signed_palm_volume(h["world_landmarks"], tidx)
            n += 1
            if ("Left" if ((v > 0) == convention) else "Right") == d["apparent"]:
                ok += 1
    return ok / n if n else 0.0


def main():
    sessions = sorted(s for s in os.listdir(SESSIONS_DIR) if "known_" in s)
    data = []
    for s in sessions:
        meta, hands, multi, empty = load(s)
        phys, apparent, facing = declared(s, meta)
        if apparent is None:
            continue
        data.append(dict(session=s, meta=meta, hands=hands, multi=multi,
                         empty=empty, phys=phys, apparent=apparent, facing=facing))

    # COVERAGE FIRST, per the post-mortem's rule 4: a green number from an empty
    # session is worse than a red one. Sessions with no usable frame are EXCLUDED
    # and named, never silently averaged into a corpus figure.
    excluded = [d for d in data if not d["hands"]]
    data = [d for d in data if d["hands"]]
    for d in excluded:
        print("EXCLUDED %s -- 0 single-hand frames (%d multi-hand frames dropped: "
              "the declaration names ONE physical hand, so a second detected hand "
              "makes the ground truth ambiguous)." % (d["session"], d["multi"]))
    if excluded:
        print()

    print("=" * 78)
    print("U7 STEP 0 -- geometric chirality vs the MediaPipe label, scored against")
    print("            the OPERATOR'S DECLARATION (never a computed cue).")
    print("=" * 78)
    total = sum(len(d["hands"]) for d in data)
    print()
    print("%d declared sessions, %d single-hand frames." % (len(data), total))
    print()

    # ---- fit the one bit: which sign of V means apparent-Left --------------
    print("-" * 78)
    print("STEP 1 -- fit the sign convention (ONE bit, by majority over ALL frames)")
    print("-" * 78)
    conv = {}
    for tname, tidx in THUMB_CANDIDATES.items():
        agree = n = 0
        for d in data:
            want_left = (d["apparent"] == "Left")
            for h in d["hands"]:
                v = signed_palm_volume(h["world_landmarks"], tidx)
                if v == 0.0:
                    continue
                n += 1
                if (v > 0) == want_left:
                    agree += 1
        conv[tname] = (agree * 2 >= n)
        frac = agree / n if n else 0.0
        chosen = frac if conv[tname] else 1.0 - frac
        print("  %-14s V>0 == apparent-Left on %6.1f%% of frames -> '%s', accuracy %6.2f%%"
              % (tname, 100 * frac,
                 "V>0=Left" if conv[tname] else "V<0=Left", 100 * chosen))

    # ---- per-session accuracy ---------------------------------------------
    best_thumb = max(THUMB_CANDIDATES,
                     key=lambda t: _corpus_acc(data, THUMB_CANDIDATES[t], conv[t]))
    bt = THUMB_CANDIDATES[best_thumb]
    bconv = conv[best_thumb]
    print()
    print("-" * 78)
    print("STEP 2 -- CHIRALITY accuracy per session (the number to beat is MediaPipe's)")
    print("-" * 78)
    print("  (best candidate: %s, convention '%s')"
          % (best_thumb, "V>0=Left" if bconv else "V<0=Left"))
    print()
    print("  %-40s %5s %10s %10s" % ("session", "n", "MediaPipe", "geometric"))
    print("  " + "-" * 68)
    mp_ok = geo_ok = nn = 0
    for d in data:
        m = g = 0
        for h in d["hands"]:
            if h["handedness"] == d["apparent"]:
                m += 1
            v = signed_palm_volume(h["world_landmarks"], bt)
            if ("Left" if ((v > 0) == bconv) else "Right") == d["apparent"]:
                g += 1
        n = len(d["hands"])
        mp_ok += m
        geo_ok += g
        nn += n
        print("  %-40s %5d %9.1f%% %9.1f%%" % (d["session"], n, 100 * m / n, 100 * g / n))
    print("  " + "-" * 68)
    print("  %-40s %5d %9.1f%% %9.1f%%" % ("CORPUS", nn, 100 * mp_ok / nn, 100 * geo_ok / nn))

    # ---- stratify by the DR-2 edge-on band ---------------------------------
    print()
    print("-" * 78)
    print("STEP 3 -- accuracy INSIDE vs OUTSIDE the DR-2 edge-on band")
    print("           (edge_on < %s = the 2D sign is untrustworthy)" % PG.EDGE_ON_THRESHOLD)
    print("-" * 78)
    buckets = defaultdict(lambda: [0, 0, 0])   # n, mp_ok, geo_ok
    for d in data:
        for h in d["hands"]:
            eo = PG.edge_on_measure(h["landmarks"])
            b = buckets["inside band" if eo < PG.EDGE_ON_THRESHOLD else "outside band"]
            b[0] += 1
            if h["handedness"] == d["apparent"]:
                b[1] += 1
            v = signed_palm_volume(h["world_landmarks"], bt)
            if ("Left" if ((v > 0) == bconv) else "Right") == d["apparent"]:
                b[2] += 1
    for key in ("inside band", "outside band"):
        n, m, g = buckets[key]
        if n:
            print("  %-14s n=%5d   MediaPipe %6.1f%%   geometric %6.1f%%"
                  % (key, n, 100 * m / n, 100 * g / n))

    # ---- conditioning of the new sign --------------------------------------
    print()
    print("-" * 78)
    print("STEP 4 -- CONDITIONING of the geometric sign (thumb distance from the")
    print("           palm plane, metres). Its analogue of `edge_on_measure`.")
    print("-" * 78)
    for tname, tidx in THUMB_CANDIDATES.items():
        vals = sorted(palm_thickness(h["world_landmarks"], tidx)
                      for d in data for h in d["hands"])
        if not vals:
            continue

        def p(q, vals=vals):
            return vals[min(len(vals) - 1, int(q * len(vals)))]

        cut = p(0.10)
        n = ok = 0
        for d in data:
            for h in d["hands"]:
                if palm_thickness(h["world_landmarks"], tidx) <= cut:
                    n += 1
                    v = signed_palm_volume(h["world_landmarks"], tidx)
                    if ("Left" if ((v > 0) == conv[tname]) else "Right") == d["apparent"]:
                        ok += 1
        print("  %-14s min %.4f  p10 %.4f  median %.4f  max %.4f   acc worst decile %6.1f%%"
              % (tname, p(0.0), p(0.10), p(0.5), p(1.0), 100 * (ok / n if n else 0)))

    # ---- the payload: does it fix FACING? ----------------------------------
    print()
    print("-" * 78)
    print("STEP 5 -- THE PAYLOAD: does a label-independent chirality fix rule 3?")
    print("           `thumb_outward` vs the DECLARED facing (`_palm` / `_back`).")
    print("-" * 78)
    print("  %-40s %5s %9s %9s" % ("session", "n", "shipped", "geo-chir"))
    print("  " + "-" * 66)
    tot = [0, 0, 0]
    for d in data:
        if d["facing"] is None:
            continue
        want = (d["facing"] == "back")   # back of hand to camera == thumb_outward
        n = s_ok = g_ok = 0
        for h in d["hands"]:
            n += 1
            if PG.is_thumb_outward(h["landmarks"], h["handedness"]) == want:
                s_ok += 1
            v = signed_palm_volume(h["world_landmarks"], bt)
            geo_label = "Left" if ((v > 0) == bconv) else "Right"
            if PG.is_thumb_outward(h["landmarks"], geo_label) == want:
                g_ok += 1
        tot[0] += n
        tot[1] += s_ok
        tot[2] += g_ok
        print("  %-40s %5d %8.1f%% %8.1f%%" % (d["session"], n, 100 * s_ok / n, 100 * g_ok / n))
    print("  " + "-" * 66)
    if tot[0]:
        print("  %-40s %5d %8.1f%% %8.1f%%"
              % ("CORPUS (declared-facing sessions)", tot[0],
                 100 * tot[1] / tot[0], 100 * tot[2] / tot[0]))

    # ---- STEP 6: the only session that DISCRIMINATES -----------------------
    # Six of the seven takes are "held steady" clips on which MediaPipe is 100%,
    # so the corpus average is dominated by frames that were never in doubt. The
    # re-entry take is the only one that exercises the defect, and it is
    # therefore the only one that carries information.
    print()
    print("-" * 78)
    print("STEP 6 -- THE DISCRIMINATING SESSION, frame by frame")
    print("-" * 78)
    hard = [d for d in data if "reentry" in d["session"]]
    for d in hard:
        errs_mp, errs_geo, both = [], [], []
        for i, h in enumerate(d["hands"]):
            mp_bad = (h["handedness"] != d["apparent"])
            v = signed_palm_volume(h["world_landmarks"], bt)
            geo = "Left" if ((v > 0) == bconv) else "Right"
            geo_bad = (geo != d["apparent"])
            if mp_bad:
                errs_mp.append(i)
            if geo_bad:
                errs_geo.append(i)
            if mp_bad and geo_bad:
                both.append(i)
        n = len(d["hands"])
        print("  %s  (n=%d)" % (d["session"], n))
        print("    MediaPipe wrong on %d frames (%.1f%%)" % (len(errs_mp), 100 * len(errs_mp) / n))
        print("    geometric wrong on %d frames (%.1f%%)  -> %.0f%% fewer errors"
              % (len(errs_geo), 100 * len(errs_geo) / n,
                 100 * (1 - len(errs_geo) / len(errs_mp)) if errs_mp else 0))
        print("    BOTH wrong on %d frames (are the failures correlated?)" % len(both))

        # Independence check: if MediaPipe's world landmarks were internally
        # chirality-normalised BY the label, sign(V) would merely restate the
        # label and prove nothing. Disagreements show they are separate signals.
        dis = agree_geo_right = 0
        for dd in data:
            for h in dd["hands"]:
                v = signed_palm_volume(h["world_landmarks"], bt)
                geo = "Left" if ((v > 0) == bconv) else "Right"
                if geo != h["handedness"]:
                    dis += 1
                    if geo == dd["apparent"]:
                        agree_geo_right += 1
        print("    corpus-wide the two signals DISAGREE on %d frames; on %d of those"
              % (dis, agree_geo_right))
        print("    the geometric answer was the CORRECT one. (So sign(V) is not a")
        print("    restatement of the label -- it is an independent signal.)")

        # Are the residual geometric errors isolated frames a debounce would
        # kill, or sustained runs it would not?
        runs, cur = [], None
        for i in errs_geo:
            if cur is not None and i == cur[1] + 1:
                cur[1] = i
            else:
                cur = [i, i]
                runs.append(cur)
        if runs:
            lens = [r[1] - r[0] + 1 for r in runs]
            print("    residual geometric errors form %d run(s), lengths %s"
                  % (len(runs), lens))
            print("    -> %d of %d are ISOLATED single frames (a 2-frame debounce,"
                  % (sum(1 for x in lens if x == 1), len(runs)))
            print("       which DR-1 already applies elsewhere, would remove those).")
        # conditioning at the residual failures
        if errs_geo:
            th = [palm_thickness(d["hands"][i]["world_landmarks"], bt) for i in errs_geo]
            eo = [PG.edge_on_measure(d["hands"][i]["landmarks"]) for i in errs_geo]
            print("    at those frames: palm thickness %.4f-%.4f m (corpus median %.4f),"
                  % (min(th), max(th),
                     sorted(palm_thickness(h["world_landmarks"], bt)
                            for dd in data for h in dd["hands"])[
                                sum(len(dd["hands"]) for dd in data) // 2]))
            print("                     edge_on %.3f-%.3f" % (min(eo), max(eo)))

    # ---- STEP 7: the snaps themselves --------------------------------------
    # Frame-rate accuracy is not the deliverable -- rule 3's answer AT A SNAP is.
    # This walks the recorded `cubes` field, finds every snap, and reports what
    # rule 3 was fed versus what it would have been fed. Both halves matter: the
    # defective snap must flip, and the CORRECT ones must not.
    print()
    print("-" * 78)
    print("STEP 7 -- rule 3's input AT EVERY RECORDED SNAP (the actual deliverable)")
    print("-" * 78)
    for d in data:
        path = os.path.join(SESSIONS_DIR, d["session"], "raw_landmarks.jsonl")
        with open(path) as f:
            frames = [json.loads(x) for x in f if x.strip()]
        if not any(fr.get("cubes") for fr in frames):
            continue

        def owners(fr):
            out = {}
            for arm, cubes in (fr.get("cubes") or {}).items():
                for name, c in cubes.items():
                    out[(arm, name)] = c.get("owner")
            return out

        prev, snaps = {}, []
        for i, fr in enumerate(frames):
            o = owners(fr)
            for k, v in o.items():
                if v and not prev.get(k):
                    snaps.append((i, k, v))
            prev = o
        if not snaps:
            continue
        print("  %s -- %d snap event(s)" % (d["session"], len(snaps)))
        print("    %-6s %-7s %-6s %-6s %8s %10s %10s"
              % ("frame", "cube", "label", "geo", "edge_on", "rule3 now", "rule3 geo"))
        changed = 0
        for i, k, v in snaps:
            hh = frames[i].get("hands") or []
            if len(hh) != 1:
                print("    %-6d %-7s (%d hands -- skipped)" % (i, k[1], len(hh)))
                continue
            h = hh[0]
            lab = h["handedness"]
            vol = signed_palm_volume(h["world_landmarks"], bt)
            geo = "Left" if ((vol > 0) == bconv) else "Right"
            ship = PG.is_thumb_outward(h["landmarks"], lab)
            gto = PG.is_thumb_outward(h["landmarks"], geo)
            if ship != gto:
                changed += 1
            note = "" if lab == d["apparent"] else "   <-- LABEL WRONG"
            print("    %-6d %-7s %-6s %-6s %8.3f %10s %10s%s"
                  % (i, k[1], lab, geo, PG.edge_on_measure(h["landmarks"]),
                     ship, gto, note))
        print("    -> rule 3's input changes on %d of %d snaps." % (changed, len(snaps)))
        print("       (A fix must flip the DEFECTIVE snap and leave the sound ones alone.)")

    # ---- STEP 8: pick the parameters BY MEASUREMENT ------------------------
    print()
    print("-" * 78)
    print("STEP 8 -- parameter sweep. Errors under the SHIPPED resolver's rule:")
    print("           thickness gate T, and the debounce that guards a CHANGE.")
    print("-" * 78)

    def simulate(hands, T, debounce):
        held, pending, run, out = None, None, 0, []
        for h in hands:
            w = h["world_landmarks"]
            obs = PG.geometric_chirality(w)
            if obs is not None and palm_thickness(w, bt) >= T:
                if held is None:
                    held, pending, run = obs, None, 0
                elif obs == held:
                    pending, run = None, 0
                else:
                    run = run + 1 if obs == pending else 1
                    pending = obs
                    if run >= debounce:
                        held, pending, run = obs, None, 0
            out.append(held if held is not None else h["handedness"])
        return out

    print("  %-8s %-9s %-24s %-24s" % ("T (mm)", "debounce",
                                       "re-entry errors (n=293)", "clean takes (n=2262)"))
    print("  " + "-" * 68)
    for t_mm in (0.0, 3.0, 5.0, 7.0):
        for deb in (1, 2, 3):
            hard = hard_n = clean = clean_n = 0
            for d in data:
                res = simulate(d["hands"], t_mm / 1000.0, deb)
                err = sum(1 for r in res if r != d["apparent"])
                if "reentry" in d["session"]:
                    hard, hard_n = hard + err, hard_n + len(d["hands"])
                else:
                    clean, clean_n = clean + err, clean_n + len(d["hands"])
            print("  %-8.1f %-9d %-24s %-24s"
                  % (t_mm, deb,
                     "%d  (%.1f%%)" % (hard, 100 * hard / hard_n),
                     "%d  (%.2f%%)" % (clean, 100 * clean / clean_n)))
    print()
    print("  READ THIS, because it decided the design:")
    print("   * The THICKNESS GATE EARNS NOTHING -- 0 mm and 5 mm are identical --")
    print("     and between 3 and 5 mm it is WORSE, because suppressing observations")
    print("     stalls the debounce and lets a bad value persist. Under A10 it is")
    print("     therefore NOT SHIPPED as a gate; `palm_plane_thickness` stays exposed")
    print("     as a diagnostic only. A null result is recorded, not shipped hopefully.")
    print("   * The DEBOUNCE does all the work: 3 clears every residual error, and the")
    print("     mechanism is explicable rather than fitted -- the longest spurious run")
    print("     measured is 2 frames. It costs nothing, because a hand cannot change")
    print("     chirality: within a track the value is constant.")
    print("   ** ONE HONEST CAVEAT: debounce=3 is chosen against 5 residual errors in")
    print("      ONE session. That is a small sample. Re-validate on the live")
    print("      known-hand take before treating 3 as settled.")

    # ---- STEP 9: the SHIPPED code, at the snaps ----------------------------
    print()
    print("-" * 78)
    print("STEP 9 -- A/B THROUGH THE REAL `PalmFacingTracker` (not a reimplementation)")
    print("           Flag OFF = pre-U7 behaviour; flag ON = what will ship.")
    print("-" * 78)
    for d in data:
        path = os.path.join(SESSIONS_DIR, d["session"], "raw_landmarks.jsonl")
        with open(path) as f:
            frames = [json.loads(x) for x in f if x.strip()]
        if not any(fr.get("cubes") for fr in frames):
            continue

        def run_arm(flag):
            saved = PG.GEOMETRIC_CHIRALITY
            PG.GEOMETRIC_CHIRALITY = flag
            try:
                trackers = {"Left": PG.PalmFacingTracker(),
                            "Right": PG.PalmFacingTracker()}
                out = {}
                for i, fr in enumerate(frames):
                    for h in (fr.get("hands") or []):
                        lab = h["handedness"]
                        to, _v = trackers[lab].update(
                            h["landmarks"], lab, h.get("world_landmarks"))
                        out[i] = to
                return out, trackers
            finally:
                PG.GEOMETRIC_CHIRALITY = saved

        off, _ = run_arm(False)
        on, trk = run_arm(True)

        prev, snaps = {}, []
        for i, fr in enumerate(frames):
            o = {}
            for arm, cubes in (fr.get("cubes") or {}).items():
                for name, c in cubes.items():
                    o[(arm, name)] = c.get("owner")
            for k, v in o.items():
                if v and not prev.get(k):
                    snaps.append((i, k))
            prev = o
        print("  %s" % d["session"])
        print("    %-6s %-7s %-12s %-12s %s"
              % ("frame", "cube", "rule3 OFF", "rule3 ON", ""))
        changed = 0
        for i, k in snaps:
            a, b = off.get(i), on.get(i)
            if a != b:
                changed += 1
            print("    %-6d %-7s %-12s %-12s %s"
                  % (i, k[1], a, b, "<-- CHANGED" if a != b else ""))
        print("    -> %d of %d snaps changed." % (changed, len(snaps)))
        print("    overrides: Left %d, Right %d   debounce absorbed: Left %d, Right %d"
              % (trk["Left"].chirality.overrides, trk["Right"].chirality.overrides,
                 trk["Left"].chirality.debounce_absorbed,
                 trk["Right"].chirality.debounce_absorbed))

    print()
    print("=" * 78)
    print("Coverage (a green number from an empty session is worse than a red one):")
    for d in data:
        print("  %-40s single-hand %5d  multi dropped %4d  no-hand %4d"
              % (d["session"], len(d["hands"]), d["multi"], d["empty"]))
    print("=" * 78)


if __name__ == "__main__":
    main()
