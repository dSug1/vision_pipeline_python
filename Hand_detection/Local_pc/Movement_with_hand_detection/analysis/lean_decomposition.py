# -*- coding: utf-8 -*-
"""⭐⭐ WHAT CONTAMINATES YAW, AND IS IT DEPTH-DEPENDENT? Measured, not argued.

    .venv/Scripts/python.exe analysis/lean_decomposition.py <session> [<session>...]

Owner, 2026-08-28: *"we know the yaw of the hand is not pure and is contaminated.
by what is it contaminated? roll? pitch? both? is the contamination dependent on
the z position of the hand?"*

`ORIENTATION_DIAGNOSIS.md` already proves the CAUSE (MediaPipe's world `z`) and
gives per-axis errors, but it never decomposes the lean itself. This does.

────────────────────────────────────────────────────────────────────────────────
THE METHOD, AND WHY IT NEEDS NO GROUND TRUTH

An ordinary recording does not know what the operator's hand was doing. It does not
have to. A rotation is an AXIS and an ANGLE, and the question is entirely about the
axis: when the hand turns like a page, the axis SHOULD be vertical. So take the
grab-referenced Horn rotation exactly as production computes it, keep the frames
where the axis is mostly vertical (a yaw-like turn) and enough angle to be real,
and ask which way the axis is tilted OFF vertical:

    n = (nx, ny, nz)  unit rotation axis, normalised so ny >= 0

    nx  -> tilt toward the PITCH axis   (horizontal, in the image plane)
    nz  -> tilt toward the ROLL axis    (the optical axis, into the screen)

⭐ A pure yaw gives `nx = nz = 0`. Whichever of the two is consistently non-zero IS
the contaminant, and its SIGN says which way it leans. That is the whole question,
and it is answerable from any take that contains turning.

⚠ THE SIGN IS REPORTED AS A MEAN, NOT AN ABSOLUTE. A contamination that flips sign
with the turn direction averages to ~0 while a genuine BIAS does not, so the mean
and the mean-absolute are printed side by side: |mean| ≈ mean_abs means a
one-directional bias (correctable by a constant), |mean| ≈ 0 with a large mean_abs
means it is symmetric in the turn and needs a term ODD in the yaw.

────────────────────────────────────────────────────────────────────────────────
⛔ ON THE DEPTH QUESTION, AND THE TRAP IT SITS NEXT TO

`CONSTRAINTS` §6 and `T6`'s CAVEAT ZERO: the six declared-angle takes had an
unreliable distance and a hand that moved, so **every depth-derived reading from
them was retracted**. This harness therefore does NOT use them for depth. It bins
by `hand_depth_m` as RECORDED, WITHIN a take, and reports the trend across bins.
That is a relationship between two measured quantities in one session -- not an
absolute depth claim, which is the thing that was invalidated.

⚠ Still read it as suggestive: `hand_depth_m` is the pipeline's own estimate and
carries a per-user scale bias (`palm_depth`'s absolute arm). A TREND across bins is
meaningful; the metres on the axis are not.

Stdlib only. Reads the corpus, writes nothing.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import palm_rotation as PR                     # noqa: E402

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

# A frame counts as "yaw-like" when the axis is mostly vertical and the turn is big
# enough that the axis direction is not noise. ⚠ Both thresholds are stated here
# rather than tuned: at small angles the axis of a near-identity rotation is
# undefined, which is the metric bug that made an earlier A/B report smoothing as
# making jitter WORSE (`REJECTED.md`).
MIN_ANGLE_DEG = 12.0
YAW_DOMINANCE = 0.60          # |ny| of the unit axis

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                          # pragma: no cover
    pass


def axis_angle(q):
    """Unit axis (ny >= 0) and angle in degrees, or None if degenerate."""
    w, x, y, z = q
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-9:
        return None
    ang = 2.0 * math.degrees(math.atan2(n, abs(w)))
    s = 1.0 if w >= 0.0 else -1.0
    ax, ay, az = s * x / n, s * y / n, s * z / n
    if ay < 0.0:                       # fold so a turn and its reverse compare
        ax, ay, az, ang = -ax, -ay, -az, -ang
    return (ax, ay, az), ang


def stats(v):
    if not v:
        return None
    v2 = sorted(v)
    n = len(v2)
    return {"n": n, "mean": sum(v2) / n, "abs": sum(abs(a) for a in v2) / n,
            "p50": v2[n // 2], "p95": v2[min(n - 1, int(n * 0.95))]}


def collect(session):
    path = os.path.join(CAPTURE, session, "raw_landmarks.jsonl")
    if not os.path.isfile(path):
        return []
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    states, rows = {}, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                frame = json.loads(line)
            except ValueError:
                continue
            for h in frame.get("hands") or []:
                w, px = h.get("world_landmarks"), h.get("landmarks")
                if not w or not px:
                    continue
                key = h.get("trackId", h.get("handedness"))
                if key not in states:
                    states[key] = horn.freeze(px, w)
                st = states[key]
                if st is None:
                    continue
                q = horn.delta(st, px, w)
                if q is None:
                    continue
                aa = axis_angle(q)
                if aa is None:
                    continue
                (ax, ay, az), ang = aa
                if abs(ang) < MIN_ANGLE_DEG or ay < YAW_DOMINANCE:
                    continue
                d = h.get("hand_depth_m") if h.get("depth_valid") else None
                rows.append((ax, az, ang, d))
    return rows


def report(label, rows):
    if not rows:
        print("  %-34s no yaw-like frames" % label)
        return
    sx, sz = stats([r[0] for r in rows]), stats([r[1] for r in rows])
    print("  %-34s n=%-6d" % (label, len(rows)))
    for name, s in (("nx  toward PITCH", sx), ("nz  toward ROLL ", sz)):
        print("      %s  mean %+.3f   mean|.| %.3f   p50 %+.3f   p95 %+.3f"
              % (name, s["mean"], s["abs"], s["p50"], s["p95"]))
    # which one dominates, and is it a bias or symmetric?
    dom = "PITCH (nx)" if sx["abs"] > sz["abs"] else "ROLL (nz)"
    ratio = max(sx["abs"], sz["abs"]) / max(1e-9, min(sx["abs"], sz["abs"]))
    print("      -> dominant contaminant: %-10s  %.1fx the other" % (dom, ratio))
    for name, s in (("nx", sx), ("nz", sz)):
        kind = ("ONE-DIRECTIONAL BIAS" if abs(s["mean"]) > 0.6 * s["abs"]
                else "SYMMETRIC in turn direction" if abs(s["mean"]) < 0.25 * s["abs"]
                else "mixed")
        print("      -> %s is %s  (|mean|/mean|.| = %.2f)"
              % (name, kind, abs(s["mean"]) / max(1e-9, s["abs"])))


def main():
    sessions = sys.argv[1:]
    if not sessions:
        print("usage: lean_decomposition.py <session> [<session> ...]")
        return 2
    print("=" * 78)
    print("YAW CONTAMINATION -- what tilts the axis, and does depth change it")
    print("=" * 78)
    print("axis kept when |ny| >= %.2f and |angle| >= %.0f deg\n"
          % (YAW_DOMINANCE, MIN_ANGLE_DEG))

    allrows, per_session = [], []
    for s in sessions:
        rows = collect(s)
        report(s, rows)
        per_session.append((s, rows))
        allrows += rows
        print("")

    if not allrows:
        print("no data")
        return 1
    print("-" * 78)
    report("ALL SESSIONS POOLED", allrows)

    # --- the depth question ------------------------------------------------
    # ⛔⛔ BINNED WITHIN EACH TAKE, NEVER ACROSS THEM. The first version of this
    # harness pooled every session and THEN binned by depth, which confounds depth
    # with take identity -- different sessions carry different hands, lighting and
    # framing, so a "depth trend" over a pooled set can be pure between-take
    # variation. It duly reported roll as DEPTH-DEPENDENT on numbers that were not
    # even monotone (0.350 0.419 0.246 0.295). ⭐ `B4` one level up: a metric must
    # not share a confound with the thing it is judging. A trend is believable only
    # if its SIGN agrees across independent takes.
    print("\n" + "-" * 78)
    print("DEPTH DEPENDENCE -- binned WITHIN each take, compared across takes")
    print("  near half vs far half of each take's own depth range\n")
    votes = {"nx": [], "nz": []}
    for label, rows in per_session:
        withd = [r for r in rows if r[3] is not None]
        if len(withd) < 120:
            print("  %-30s only %d frame(s) with depth -- skipped" % (label[:30], len(withd)))
            continue
        withd.sort(key=lambda r: r[3])
        h = len(withd) // 2
        near, far = withd[:h], withd[h:]
        out = []
        for jj, nm in ((0, "nx"), (1, "nz")):
            a = sum(abs(c[jj]) for c in near) / len(near)
            b = sum(abs(c[jj]) for c in far) / len(far)
            votes[nm].append(1 if b > a else -1)
            out.append("%s %.3f->%.3f %-4s" % (nm, a, b, "UP" if b > a else "DOWN"))
        print("  %-30s %.2f-%.2f m  %s" % (label[:30], withd[0][3], withd[-1][3],
                                           "  ".join(out)))
    print("")
    for nm in ("nx", "nz"):
        v = votes[nm]
        if len(v) < 2:
            print("  %s (%s): only %d take(s) -- cannot judge"
                  % (nm, "pitch" if nm == "nx" else "roll", len(v)))
        elif abs(sum(v)) == len(v):
            print("  %s (%s): ALL %d takes agree, contamination %s with depth"
                  " -> A REAL TREND" % (nm, "pitch" if nm == "nx" else "roll",
                                        len(v), "RISES" if sum(v) > 0 else "FALLS"))
        else:
            print("  %s (%s): takes DISAGREE (%s) -> NO consistent depth dependence"
                  % (nm, "pitch" if nm == "nx" else "roll",
                     "/".join("UP" if x > 0 else "DOWN" for x in v)))
    print("\n⚠ The metres are the pipeline's own estimate and carry a per-user scale")
    print("  bias. Only the DIRECTION of a trend is claimed here, never the metres.")
    return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
