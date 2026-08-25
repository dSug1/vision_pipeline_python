"""⭐⭐ F1 STEP 0 — THE FINGERTIP CENSUS. Four questions, answered before a constant is chosen.

`F1` drives the object's whole transform from the fingertips. Google's own Model
Card says the fingertips are the landmarks their model estimates WORST ("per-joint
MNAE is the smallest at the base of each finger, and gets larger toward the
fingertip"), and lists a hand HOLDING AN OBJECT as out of scope. So four numbers
have to exist before the design's constants are picked, and all four can be taken
from the corpus that already exists -- no camera, no new takes, nothing shipped.

Spec: `Claude/10_HAND_TRACKING/spec/F1_FINGERTIP_TRANSFORM_SPEC.md` §9.

────────────────────────────────────────────────────────────────────────────────
WHAT IT MEASURES, AND WHAT EACH NUMBER DECIDES

  M1  TIP INSTABILITY, held vs not held. Per-tip frame-to-frame motion measured
      IN THE PALM FRAME, so the hand's own motion is removed and what is left is
      articulation plus noise.
      ⇒ decides how tightly the trim must be clamped. If the tips are wild
        exactly while a cube is held, the "object follows the fingers" end of the
        design is dead on arrival.

      ⛔ WHY NOT MEDIAPIPE'S OWN CONFIDENCE: the recorder stores `landmarks` and
      `world_landmarks` and nothing else -- per-point `visibility`/`presence` are
      not written, and are not reliably populated for hands anyway. Measuring what
      the tips DID beats asking the model what it thought, and it keeps the rule
      `_record_flush` exists for: record what ran, never re-derive it.

  M2  THE TIP RESIDUAL. Within each held segment, the angle of the Horn fit of the
      tips at time t against the tips at the START of that hold -- both expressed
      in the palm frame, so this is PURE ARTICULATION, never wrist motion.
      ⇒ sets the clamp from real handling. If assembly-style finger motion is
        +/-10 deg, a 45 deg clamp is decoration.

  M3  BARYCENTRE DRIFT. How far the fingertip barycentre moves in the palm frame
      during a hold -- i.e. how much the object would TRANSLATE from re-gripping
      alone, with the hand perfectly still.
      ⇒ decides whether `g_pos = 1` (the owner's plain barycentre) ships as the
        default or wants a clamp.

  M4  CONDITIONING. Eigenvalues of the centred tip cloud:
        spread = sqrt(l2/l1)  -- COLLINEARITY. -> 0 means the tips lie on a line
                                 and rotation about that line is unobservable.
        scale  = sqrt(l1)/palm_span -- absolute size. -> 0 means a fist.
      ⇒ sets §6.2's floors from measurement instead of taste.

      ⭐ Note it is `spread` that gates, NOT planarity. A planar tip set is
      perfectly well-conditioned; a collinear one is not. That correction is the
      whole of the spec's §6 answer.

────────────────────────────────────────────────────────────────────────────────
METHOD NOTES -- read before trusting a number

  * The palm frame comes from `palm_rotation.Horn(PALM_LANDMARKS, "ref")`, the
    SHIPPED estimator, seeded per presence-run. Not a second derivation of it.
  * Eigenvalues come from `palm_geometry._symmetric_3x3_eigenvalues`, also shared.
  * `world_landmarks` are metres; every length here is reported in MILLIMETRES.
  * A frame counts as HELD for a hand only when a cube's `owner` matches THAT
    hand (its handedness, or its trackId on takes recorded while `TRACK_OWNERSHIP`
    was on). A cube held by the other hand must not colour this hand's numbers.
  * Frame-to-frame quantities are skipped across any gap in presence, so a
    dropout is never read as motion.

  ⚠ This is a CENSUS, not an A/B. It measures the corpus as recorded; it does not
  compare arms and it cannot accept or reject anything on its own.

    .venv/Scripts/python.exe analysis/f1_tip_census.py [--root DIR] [--limit N]
"""
import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_geometry, palm_rotation          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

DEFAULT_ROOT = r"E:\Python\Recordings for vision_pipeline"

PALM = palm_rotation.PALM_LANDMARKS                 # (0, 5, 9, 13, 17)
TIPS = (4, 8, 12, 16, 20)
TIP_NAMES = ("thumb", "index", "middle", "ring", "pinky")

# A frame is "QUIET" when the palm itself barely moved between it and the
# previous one, so tip motion there is noise + fine articulation rather than the
# operator swinging their hand. Deliberately strict: this is a noise floor.
QUIET_ROT_DEG = 1.0
QUIET_TRANS_MM = 2.0

# ~0.5 s at this pipeline's measured 14-24 fps (N10: the frame rate is
# camera-bound and environment-dependent, so this is frames, stated as such).
SHORT_HORIZON_FRAMES = 8


# --------------------------------------------------------------------------
# small vector / quaternion helpers (analysis-local; the estimator layer owns
# the shipped versions and is deliberately not extended for a census)
# --------------------------------------------------------------------------
def _rotate_by_conj(q, v):
    """q^-1 . v -- express a world vector in the frame `q` describes."""
    w, x, y, z = q
    # conjugate rotation: v' = q* v q
    tx, ty, tz = 2.0 * (y * v[2] - z * v[1]), 2.0 * (z * v[0] - x * v[2]), 2.0 * (x * v[1] - y * v[0])
    return (v[0] - w * tx + (y * tz - z * ty),
            v[1] - w * ty + (z * tx - x * tz),
            v[2] - w * tz + (x * ty - y * tx))


def _pct(vals, p):
    if not vals:
        return float("nan")
    s = sorted(vals)
    return s[min(len(s) - 1, int(p * len(s)))]


def _eig_of(points):
    """(l1 >= l2 >= l3) of the centred point set's scatter matrix."""
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    cz = sum(p[2] for p in points) / n
    a00 = a01 = a02 = a11 = a12 = a22 = 0.0
    for x, y, z in points:
        dx, dy, dz = x - cx, y - cy, z - cz
        a00 += dx * dx
        a01 += dx * dy
        a02 += dx * dz
        a11 += dy * dy
        a12 += dy * dz
        a22 += dz * dz
    return palm_geometry._symmetric_3x3_eigenvalues(a00, a01, a02, a11, a12, a22)


# --------------------------------------------------------------------------
def _owned_keys(row):
    """Every ownership key held this frame, across both recorder shapes.

    Production writes `cubes: {"production": {name: {...}}}`; the debug tool
    writes per-arm blocks (`cubes_raw`, `cubes_gated`) and older takes wrote a
    single flat block. All three reduce to "which keys own something".
    """
    out = set()
    blocks = []
    c = row.get("cubes")
    if isinstance(c, dict):
        vals = list(c.values())
        if vals and all(isinstance(v, dict) and v and
                        all(isinstance(x, dict) for x in v.values()) for v in vals):
            blocks.extend(vals)                     # per-arm
        else:
            blocks.append(c)                        # flat
    for k in ("cubes_raw", "cubes_gated"):
        if isinstance(row.get(k), dict):
            blocks.append(row[k])
    for b in blocks:
        for cube in b.values():
            if isinstance(cube, dict) and cube.get("owner") is not None:
                out.add(str(cube["owner"]))
    return out


def _hand_frames(rows):
    """{slot: [(index, world_landmarks, held_bool), ...]} -- one entry per frame
    the hand is actually present with world landmarks."""
    per = {}
    for i, r in enumerate(rows):
        owners = _owned_keys(r)
        for h in (r.get("hands") or []):
            w = h.get("world_landmarks")
            if not w or len(w) < 21:
                continue
            slot = h.get("handedness")
            keys = {str(slot), str(h.get("trackId", -1))}
            per.setdefault(slot, []).append((i, w, bool(owners & keys)))
    return per


def analyse_run(run, acc):
    """One presence-run of (frame_index, world, held). Accumulates into `acc`."""
    horn = palm_rotation.Horn(PALM, "ref")
    state = None
    prev = None                 # (frame_index, tips_in_palm_frame, held, q, palm_centre)
    hold_ref = None             # tips_in_palm_frame at the start of the current hold
    hist = []                   # (frame_index, tips) inside the current hold

    for idx, world, held in run:
        if state is None:
            state = horn.freeze(None, world)
            if state is None:
                continue
        q = horn.delta(state, None, world)
        if q is None:
            continue

        pc = [sum(world[i][k] for i in PALM) / len(PALM) for k in range(3)]
        tips = [_rotate_by_conj(q, tuple(world[t][k] - pc[k] for k in range(3)))
                for t in TIPS]

        # --- M4 conditioning (every frame, held or not) -------------------
        l1, l2, l3 = _eig_of(tips)
        span = math.dist(world[PALM[1]], world[PALM[4]]) or 1e-9   # index_MCP..pinky_MCP
        if l1 > 1e-18:
            acc["spread"].append(math.sqrt(max(0.0, l2) / l1))
            acc["scale"].append(math.sqrt(l1) / span)

        # --- M1 instability, per tip, only across CONSECUTIVE frames ------
        #
        # ⚠⚠ THE TRAP THIS SPLIT EXISTS TO AVOID: raw frame-to-frame tip motion
        # conflates SENSOR NOISE with the operator genuinely moving their fingers,
        # and the two want opposite conclusions. A "QUIET" frame is one where the
        # palm itself barely moved -- so whatever the tips did is noise plus fine
        # articulation, which is exactly the band the trim has to survive.
        if prev is not None and idx == prev[0] + 1:
            palm_step_deg = palm_rotation.quat_angle_deg(prev[3], q)
            palm_step_mm = math.dist(pc, prev[4]) * 1000.0
            quiet = palm_step_deg < QUIET_ROT_DEG and palm_step_mm < QUIET_TRANS_MM
            bucket = "held" if held else "free"
            for j, (a, b) in enumerate(zip(tips, prev[1])):
                d = math.dist(a, b) * 1000.0
                acc[f"step_{bucket}"][j].append(d)
                if quiet:
                    acc[f"quiet_{bucket}"][j].append(d)
        prev = (idx, tips, held, q, pc)

        # --- M2 / M3, within a hold ---------------------------------------
        if held:
            if hold_ref is None:
                hold_ref = tips
                hist = [(idx, tips)]
                continue
            hist.append((idx, tips))
            # vs the START of the hold -- the reference the spec's trim actually
            # uses, since R_trim is grab-referenced.
            qr = palm_rotation.horn_rotation(hold_ref, tips)
            if qr is not None:
                acc["residual_deg"].append(
                    palm_rotation.quat_angle_deg(palm_rotation._IDENTITY, qr))
            u_now = [sum(t[k] for t in tips) / 5.0 for k in range(3)]
            u_ref = [sum(t[k] for t in hold_ref) / 5.0 for k in range(3)]
            acc["bary_mm"].append(math.dist(u_now, u_ref) * 1000.0)

            # ⭐ AND vs ~SHORT_HORIZON_FRAMES ago. A hold lasting ten seconds lets
            # the operator completely re-grip, which is real but is NOT what a
            # jitter budget is about. The short horizon separates "the fingers
            # drifted over seconds" from "the fingers are unsteady right now".
            if len(hist) > SHORT_HORIZON_FRAMES:
                _, ref = hist[-1 - SHORT_HORIZON_FRAMES]
                qs = palm_rotation.horn_rotation(ref, tips)
                if qs is not None:
                    acc["residual_short_deg"].append(
                        palm_rotation.quat_angle_deg(palm_rotation._IDENTITY, qs))
                u_s = [sum(t[k] for t in ref) / 5.0 for k in range(3)]
                acc["bary_short_mm"].append(math.dist(u_now, u_s) * 1000.0)
        else:
            hold_ref = None
            hist = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--limit", type=int, default=0, help="max takes (0 = all)")
    a = ap.parse_args()

    acc = {"step_held": [[] for _ in TIPS], "step_free": [[] for _ in TIPS],
           "quiet_held": [[] for _ in TIPS], "quiet_free": [[] for _ in TIPS],
           "residual_deg": [], "bary_mm": [], "spread": [], "scale": [],
           "residual_short_deg": [], "bary_short_mm": []}
    takes = held_takes = 0

    paths = sorted(set(glob.glob(os.path.join(a.root, "*", "sessions", "*")) +
                       glob.glob(os.path.join(a.root, "*", "*"))))
    for d in paths:
        f = os.path.join(d, "raw_landmarks.jsonl")
        if not os.path.isfile(f):
            continue
        try:
            rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        except (OSError, ValueError):
            continue
        if len(rows) < 30:
            continue
        takes += 1
        before = len(acc["residual_deg"])
        for _slot, frames in _hand_frames(rows).items():
            run = []
            for fr in frames:
                if run and fr[0] != run[-1][0] + 1:
                    if len(run) >= 3:
                        analyse_run(run, acc)
                    run = []
                run.append(fr)
            if len(run) >= 3:
                analyse_run(run, acc)
        if len(acc["residual_deg"]) > before:
            held_takes += 1
        if a.limit and takes >= a.limit:
            break

    w = 96
    print("=" * w)
    print("F1 STEP 0 — FINGERTIP CENSUS   (tips expressed in the palm frame; "
          "lengths in mm)")
    print("=" * w)
    print(f"  takes read: {takes}    takes contributing held frames: {held_takes}")
    print(f"  held samples: {len(acc['residual_deg'])}    "
          f"conditioning samples: {len(acc['spread'])}")
    print()

    print("-" * w)
    print("  M1  TIP INSTABILITY — frame-to-frame motion in the palm frame (mm)")
    print("-" * w)
    print(f"      {'tip':<8}{'HELD median':>14}{'HELD p95':>12}"
          f"{'FREE median':>14}{'FREE p95':>12}{'ratio med':>12}")
    for j, nm in enumerate(TIP_NAMES):
        h, fr = acc["step_held"][j], acc["step_free"][j]
        hm, fm = _pct(h, .5), _pct(fr, .5)
        ratio = (hm / fm) if (fm and fm == fm and fm > 1e-9) else float("nan")
        print(f"      {nm:<8}{hm:>14.2f}{_pct(h, .95):>12.2f}"
              f"{fm:>14.2f}{_pct(fr, .95):>12.2f}{ratio:>12.2f}")
    nh = sum(len(x) for x in acc["step_held"])
    nf = sum(len(x) for x in acc["step_free"])
    print(f"      n = {nh} held / {nf} free tip-steps")
    print("      ⭐ ratio > 1 means the tips are NOISIER while a cube is held —")
    print("        which is the Model Card's occlusion prediction, measured here.")
    print()
    print(f"      ⭐⭐ QUIET FRAMES ONLY (palm moved < {QUIET_ROT_DEG:.0f}° and "
          f"< {QUIET_TRANS_MM:.0f} mm) — this is the NOISE FLOOR,")
    print("         with the operator's own hand motion excluded:")
    print(f"      {'tip':<8}{'HELD median':>14}{'HELD p95':>12}"
          f"{'FREE median':>14}{'FREE p95':>12}{'ratio med':>12}")
    for j, nm in enumerate(TIP_NAMES):
        h, fr = acc["quiet_held"][j], acc["quiet_free"][j]
        hm, fm = _pct(h, .5), _pct(fr, .5)
        ratio = (hm / fm) if (fm and fm == fm and fm > 1e-9) else float("nan")
        print(f"      {nm:<8}{hm:>14.2f}{_pct(h, .95):>12.2f}"
              f"{fm:>14.2f}{_pct(fr, .95):>12.2f}{ratio:>12.2f}")
    qh = sum(len(x) for x in acc["quiet_held"])
    qf = sum(len(x) for x in acc["quiet_free"])
    print(f"      n = {qh} held / {qf} free tip-steps on quiet frames")
    print()

    print("-" * w)
    print("  M2  TIP RESIDUAL — articulation only, vs the start of each hold (deg)")
    print("-" * w)
    r, rs = acc["residual_deg"], acc["residual_short_deg"]
    print(f"      {'':<6}{'vs HOLD START':>16}{'vs ~' + str(SHORT_HORIZON_FRAMES) + ' frames ago':>24}")
    for p in (.5, .9, .95, .99):
        print(f"      p{int(p*100):<5}{_pct(r, p):>16.2f}{_pct(rs, p):>24.2f}")
    print(f"      {'max':<6}{(max(r) if r else float('nan')):>16.2f}"
          f"{(max(rs) if rs else float('nan')):>24.2f}")
    print("      ⭐ The two columns answer different questions. VS HOLD START is what")
    print("        the spec's grab-referenced trim actually sees; the SHORT horizon")
    print("        is the jitter budget. A large gap between them means the fingers")
    print("        DRIFT over a hold rather than shake — a very different problem.")
    print()

    print("-" * w)
    print("  M3  BARYCENTRE DRIFT during a hold — translation from re-gripping alone (mm)")
    print("-" * w)
    b, bs = acc["bary_mm"], acc["bary_short_mm"]
    print(f"      {'':<6}{'vs HOLD START':>16}{'vs ~' + str(SHORT_HORIZON_FRAMES) + ' frames ago':>24}")
    for p in (.5, .9, .95, .99):
        print(f"      p{int(p*100):<5}{_pct(b, p):>16.2f}{_pct(bs, p):>24.2f}")
    print(f"      {'max':<6}{(max(b) if b else float('nan')):>16.2f}"
          f"{(max(bs) if bs else float('nan')):>24.2f}")
    print("      ⇒ this is how far the object would move when only the FINGERS move,")
    print("        at g_pos = 1 (the plain barycentre, as specified).")
    print()

    print("-" * w)
    print("  M4  CONDITIONING of the tip cloud")
    print("-" * w)
    sp, sc = acc["spread"], acc["scale"]
    print(f"      spread = sqrt(l2/l1)   p1 {_pct(sp,.01):.3f}   p5 {_pct(sp,.05):.3f}"
          f"   median {_pct(sp,.5):.3f}   p95 {_pct(sp,.95):.3f}")
    print(f"      scale  = sqrt(l1)/span p1 {_pct(sc,.01):.3f}   p5 {_pct(sc,.05):.3f}"
          f"   median {_pct(sc,.5):.3f}   p95 {_pct(sc,.95):.3f}")
    for cut in (0.10, 0.15, 0.20, 0.30):
        n = sum(1 for v in sp if v < cut)
        print(f"      spread < {cut:.2f}: {n:>7} frames ({100.0*n/max(1,len(sp)):5.2f}%)"
              f"  — the trim would be frozen here")
    print("=" * w)


if __name__ == "__main__":
    main()
