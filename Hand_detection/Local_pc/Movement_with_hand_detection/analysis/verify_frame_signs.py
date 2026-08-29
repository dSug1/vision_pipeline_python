# -*- coding: utf-8 -*-
"""⭐⭐⭐ `RB0` — THE SIGN HARNESS. The first thing built on `1.7.42-`.

    .venv/Scripts/python.exe analysis/verify_frame_signs.py

Design of record: `Claude/10_HAND_TRACKING/spec/SPEC_FRAME_AND_REBUILD.md`.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ WHY THIS EXISTS, AND WHY IT IS FIRST

Every defect of 2026-08-29 was a **SIGN** error:

    * the edge-on gate was SYMMETRIC, so it re-opened past edge-on;
    * the palm normal is CHIRALITY-ODD, so the whole left hand was gated to zero;
    * `is_thumb_outward` is TRUE for the BACK of the hand, so the polarity was
      inverted and BOTH hands died;
    * and the composite mount+sign mapping came out a REFLECTION (det -1), which
      no rigid hand-to-object correspondence can be.

**Not one of them was caught by a suite.** All four were found by the owner, live,
one at a time, across a whole day. They share a shape: a quantity whose MAGNITUDE
was right and whose SIGN was wrong, in code that runs identically either way.

⭐ So this file tests SIGNS, against DECLARED truth, before anything is built on
top. It is deliberately independent of everything `1.7.42` rebuilds: it reads
landmarks and does its own arithmetic.

────────────────────────────────────────────────────────────────────────────────
⭐⭐⭐ THE INVARIANT, WHICH IS THE OWNER'S OWN ARGUMENT (2026-08-29)

    *"if the hand is rotating around the vertical axis, any observer which watches
     the hand will see the hand rotating in the same direction ... Roll and pitch
     will be reversed if the camera and the user are watching in opposite
     directions."*

Two observers facing each other are related by a 180 deg rotation about the
VERTICAL -- `Ry180 = diag(-1, 1, -1)`, determinant **+1**, a proper rotation:

    yaw   (0,1,0)   UNCHANGED   <- the vertical is SHARED
    pitch (1,0,0)   reversed
    roll  (0,0,1)   reversed

⛔ **ANY VIEWPOINT SETTING THAT CHANGES THE SIGN OF YAW IS WRONG BY CONSTRUCTION.**
The shipped `pitch_yaw` reverses yaw. This one assertion would have killed it on
day one, and there was no such assertion anywhere.

────────────────────────────────────────────────────────────────────────────────
⚠ WHAT IT USES AS TRUTH, AND THE LIMIT OF THAT

The three stepped GRIPPING takes of 2026-08-29, whose holds are **declared** by the
recorder rather than inferred from a threshold. The operator moved PROGRESSIVELY IN
ONE DIRECTION through each take, so the DIRECTION of motion is known even though the
ANGLES are ballpark (owner: *"the 10 degrees increment were ballpark"*, and yaw
reached ~80 not 90).

⭐ **Direction is all a sign test needs.** It deliberately asserts nothing about
magnitude -- the compression between declared and measured angles is a separate
question (`SPEC_DELTA_ORBIT` §8bis) and mixing the two is how earlier work talked
itself into wrong conclusions.

Stdlib + the landmark corpus. Reads only; writes nothing.
"""
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):                           # pragma: no cover
    pass

CAPTURE = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 0, 5, 9, 13, 17
# ⚠ The five palm points, which is what the orientation fit uses. Named here rather
# than imported: this file must not depend on the modules it is checking.
PALM = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)

FAILURES = []


def ok(name, cond, detail=""):
    print(("  [PASS] " if cond else "  [FAIL] ") + name.ljust(56) + " " + detail)
    if not cond:
        FAILURES.append(name)


# ── the two viewpoints, as LANDMARK transforms ──────────────────────────────
# ⭐⭐ BOTH ARE PROPER ROTATIONS. `Ry180` negates x AND z; negating z alone would be
# a REFLECTION (det -1) and would invert chirality -- which is exactly why the
# 2026-08-28 build's "negate the z" idea was rejected, correctly, for the wrong
# operation. See the spec §3.
def head_worn(p):
    """The camera sees what the user sees: nothing to correct."""
    return p


def facing_user(p):
    """Ry180: the camera and the user look at each other."""
    return (-p[0], p[1], -p[2])


MOUNTS = (("head_worn", head_worn), ("facing_user", facing_user))


# ── minimal geometry, written here on purpose ───────────────────────────────
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def signed_palm_volume(wl):
    """⭐ CHIRALITY as a determinant: the handedness of the palm's own frame.

    ⛔ It must be INVARIANT under a viewpoint that is a proper rotation, and that
    invariance is the whole reason §3 chose `Ry180` over negating z. This function
    is what proves it rather than asserts it."""
    a = _sub(wl[INDEX_MCP], wl[WRIST])
    b = _sub(wl[PINKY_MCP], wl[WRIST])
    c = _sub(wl[MIDDLE_MCP], wl[WRIST])
    return _dot(_cross(a, b), c)


def horn(src, dst):
    """Least-squares rotation src -> dst as a quaternion (Horn 1987 / Davenport).

    ⚠ Written here rather than imported, deliberately: `RB0` must be able to fail
    on the module it is checking. ⛔ Canonicalised to `w >= 0` -- `q` and `-q` are
    one rotation, and reading an angle off the wrong sign is the defect that cost
    2026-08-29 a whole row."""
    n = len(src)
    cs = [sum(p[k] for p in src) / n for k in range(3)]
    cd = [sum(p[k] for p in dst) / n for k in range(3)]
    S = [[0.0] * 3 for _ in range(3)]
    for p, q in zip(src, dst):
        a = [p[k] - cs[k] for k in range(3)]
        b = [q[k] - cd[k] for k in range(3)]
        for i in range(3):
            for j in range(3):
                S[i][j] += a[i] * b[j]
    K = [
        [S[0][0] + S[1][1] + S[2][2], S[1][2] - S[2][1], S[2][0] - S[0][2], S[0][1] - S[1][0]],
        [S[1][2] - S[2][1], S[0][0] - S[1][1] - S[2][2], S[0][1] + S[1][0], S[2][0] + S[0][2]],
        [S[2][0] - S[0][2], S[0][1] + S[1][0], -S[0][0] + S[1][1] - S[2][2], S[1][2] + S[2][1]],
        [S[0][1] - S[1][0], S[2][0] + S[0][2], S[1][2] + S[2][1], -S[0][0] - S[1][1] + S[2][2]],
    ]
    # power iteration on (K + shift I) -- enough for a 4x4 with a dominant root
    v = [1.0, 0.0, 0.0, 0.0]
    shift = max(abs(K[i][j]) for i in range(4) for j in range(4)) * 4.0 + 1.0
    for _ in range(200):
        w = [sum(K[i][j] * v[j] for j in range(4)) + shift * v[i] for i in range(4)]
        m = math.sqrt(sum(c * c for c in w)) or 1.0
        v = [c / m for c in w]
    if v[0] < 0.0:
        v = [-c for c in v]
    return tuple(v)


def rotvec_deg(q):
    """Rotation vector (axis*angle) in degrees: (pitch, yaw, roll) about x, y, z."""
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    ang = math.degrees(2.0 * math.atan2(n, w))
    return (x / n * ang, y / n * ang, z / n * ang)


# ── the takes ───────────────────────────────────────────────────────────────
TAKES = (("2026-08-29_122958_window_yaw_grip", "YAW", 1),
         ("2026-08-29_123058_window_pitch_grip", "PITCH", 0),
         ("2026-08-29_123725_window_roll_grip", "ROLL", 2))


def load(key):
    m = [d for d in sorted(os.listdir(CAPTURE)) if key in d]
    if not m:
        return None, []
    path = os.path.join(CAPTURE, m[-1], "raw_landmarks.jsonl")
    if not os.path.isfile(path):
        return m[-1], []
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            hs = r.get("hands") or []
            if len(hs) != 1:
                continue
            h = hs[0]
            wl = h.get("world_landmarks")
            if wl and len(wl) >= 21:
                out.append((wl, h.get("handedness", "?"), r.get("step")))
    return m[-1], out


def sweep(frames, xf):
    """The rotation from the FIRST declared hold to each later one, per axis."""
    ref = None
    per_step = {}
    for wl, _hd, step in frames:
        if not step or not step.startswith("hold"):
            continue
        pts = [xf(wl[i]) for i in PALM]
        if ref is None:
            ref = pts
        per_step.setdefault(step, []).append(pts)
    out = []
    for step in sorted(per_step, key=lambda s: int(s.split("_")[1])):
        block = per_step[step]
        mid = block[len(block) // 2]
        out.append((int(step.split("_")[1]), rotvec_deg(horn(ref, mid))))
    return out


def main():
    print("=" * 78)
    print("RB0 — FRAME SIGN HARNESS (1.7.42)")
    print("=" * 78)
    print("  Truth: the operator moved PROGRESSIVELY ONE WAY through each take.")
    print("  Only DIRECTION is asserted. Magnitudes are ballpark and not tested.")

    data = {}
    for key, axis, idx in TAKES:
        session, frames = load(key)
        if not frames:
            print("\n  -- %s: not found, SKIPPED" % key)
            continue
        data[axis] = (session, frames, idx)

    # ── 1. the owner's invariant ────────────────────────────────────────────
    print("\n1. ⛔⛔ YAW MUST HAVE THE SAME SIGN IN BOTH MOUNTS")
    print("     (two observers share the vertical — the owner's argument, 2026-08-29)")
    if "YAW" in data:
        _s, frames, idx = data["YAW"]
        res = {}
        for name, xf in MOUNTS:
            sw = sweep(frames, xf)
            res[name] = sw[-1][1][idx] if sw else 0.0
            print("     %-12s final yaw %+8.2f°" % (name, res[name]))
        same = (res["head_worn"] * res["facing_user"]) > 0.0
        ok("yaw keeps its sign across the viewpoint", same,
           "%+.2f vs %+.2f" % (res["head_worn"], res["facing_user"]))
        ok("⛔ and it is NOT near zero (the test would be vacuous)",
           abs(res["head_worn"]) > 5.0, "%.1f°" % abs(res["head_worn"]))

    # ── 2. pitch and roll must FLIP ────────────────────────────────────────
    print("\n2. ⭐ PITCH AND ROLL MUST REVERSE BETWEEN THE MOUNTS")
    for axis in ("PITCH", "ROLL"):
        if axis not in data:
            continue
        _s, frames, idx = data[axis]
        vals = {}
        for name, xf in MOUNTS:
            sw = sweep(frames, xf)
            vals[name] = sw[-1][1][idx] if sw else 0.0
        flipped = (vals["head_worn"] * vals["facing_user"]) < 0.0
        ok("%s reverses across the viewpoint" % axis, flipped,
           "%+.2f vs %+.2f" % (vals["head_worn"], vals["facing_user"]))

    # ── 3. chirality is a rotation invariant ───────────────────────────────
    print("\n3. ⭐⭐ CHIRALITY IS UNCHANGED BY THE VIEWPOINT")
    print("     (this is what negating z alone would have broken — spec §3)")
    for axis, (session, frames, _i) in data.items():
        wl = frames[len(frames) // 2][0]
        a = signed_palm_volume([head_worn(p) for p in wl])
        b = signed_palm_volume([facing_user(p) for p in wl])
        ok("%-5s determinant keeps its sign" % axis, (a * b) > 0.0,
           "%+.3e vs %+.3e" % (a, b))

    # ── 4. and negating z ALONE would break it — the counter-example ───────
    print("\n4. ⛔ THE COUNTER-EXAMPLE: negating z ALONE inverts chirality")
    print("     — which is why `Ry180` (negate x AND z) is the correct operation")
    for axis, (session, frames, _i) in list(data.items())[:1]:
        wl = frames[len(frames) // 2][0]
        a = signed_palm_volume(wl)
        z_only = signed_palm_volume([(p[0], p[1], -p[2]) for p in wl])
        ok("negate-z INVERTS the determinant (so it is a reflection)",
           (a * z_only) < 0.0, "%+.3e vs %+.3e" % (a, z_only))

    # ── 5. the per-axis picture, printed for the eye ───────────────────────
    print("\n5. ⭐ THE SWEEPS, per declared hold (facing_user)")
    for axis, (session, frames, idx) in data.items():
        sw = sweep(frames, facing_user)
        line = "  ".join("%d°:%+6.1f" % (d, v[idx]) for d, v in sw)
        print("     %-5s %s" % (axis, line))
        mono = all(sw[i][1][idx] * sw[-1][1][idx] >= -1e-9 for i in range(1, len(sw)))
        ok("%-5s never reverses mid-sweep" % axis, mono,
           "one direction throughout")

    print("\n" + "=" * 78)
    if FAILURES:
        print("FAILED %d check(s):" % len(FAILURES))
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
