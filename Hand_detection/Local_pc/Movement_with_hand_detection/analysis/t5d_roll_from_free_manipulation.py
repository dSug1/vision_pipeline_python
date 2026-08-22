"""T5d -- ROLL axis fidelity, harvested from the UNSCRIPTED free_manipulation takes.

The corpus has no scripted roll take: `RecordPerceptionSequence.py` prescribes
pitch (`pitch_sweep_*`, `palm_back_*`) and yaw (`yaw_sweep_constant_depth`) only.
Rather than assert from geometry what roll does -- §14.3.1 did exactly that about
yaw and §14.3.2 then REFUTED it -- this harvests real roll segments from the
unscripted takes, where the operator inevitably rolled at some point.

HOW A ROLL SEGMENT IS IDENTIFIED, WITHOUT USING THE ESTIMATOR
--------------------------------------------------------------
Roll is rotation about the DEPTH axis, i.e. purely in the image plane. Its
signature in 2D pixels alone is unambiguous and needs no z:

    both palm spans (width 5<->17, length 0<->9) stay CONSTANT   <- no foreshortening,
                                                                    so the axis points
                                                                    at the camera
    the knuckle row's in-image ANGLE sweeps                      <- and it is rotating

Any rotation with a component off the depth axis foreshortens at least one span,
so requiring both to hold excludes yaw and pitch contamination -- the same
z-free discipline as t5c, and the reason this is evidence rather than inference.

Segments are then replayed through production's estimator
(`palm_rotation.Horn(PALM_LANDMARKS,'ref')`) and the fitted axis compared to the
depth axis (world Z).

Stdlib only. Run from the parent directory:
    .venv/Scripts/python.exe analysis/t5d_roll_from_free_manipulation.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Resources"))
import palm_rotation as PR      # noqa: E402

CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_perception_layer\sessions"

WIN = 20            # frames per candidate segment
SPAN_TOL = 0.12     # both spans must stay within +/-12% of the segment median
MIN_SWEEP = 25.0    # the in-image knuckle angle must turn at least this much (deg)


def frames_of(session):
    out = []
    p = os.path.join(CAPTURE_ROOT, session, "raw_landmarks.jsonl")
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            hands = (json.loads(line).get("hands") or [])
            if len(hands) != 1:            # single hand only: keeps hands[0] unambiguous
                out.append(None)
                continue
            h = hands[0]
            px, wl = h.get("landmarks"), h.get("world_landmarks")
            if not px or not wl or len(px) != 21 or len(wl) != 21:
                out.append(None)
                continue
            out.append((px, wl))
    return out


def dist(px, a, b):
    return math.hypot(px[a][0] - px[b][0], px[a][1] - px[b][1])


def knuckle_angle(px):
    return math.degrees(math.atan2(px[17][1] - px[5][1], px[17][0] - px[5][0]))


def unwrap(seq):
    out, off = [seq[0]], 0.0
    for prev, cur in zip(seq, seq[1:]):
        d = cur - prev
        if d > 180:
            off -= 360
        elif d < -180:
            off += 360
        out.append(cur + off)
    return out


def axis_angle(q):
    w, x, y, z = q
    if w < 0.0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-9:
        return None, 0.0
    return (x / s, y / s, z / s), math.degrees(2.0 * math.acos(w))


def main():
    sessions = [s for s in sorted(os.listdir(CAPTURE_ROOT)) if s.endswith("free_manipulation")]
    print("=" * 78)
    print("T5d  ROLL AXIS FIDELITY -- harvested from unscripted free_manipulation")
    print("=" * 78)
    print(f"  segment = {WIN} frames, both palm spans stable within +/-{SPAN_TOL:.0%},")
    print(f"            in-image knuckle angle sweeping >= {MIN_SWEEP:.0f} deg")
    print("  -> a rotation about the DEPTH axis, identified WITHOUT the estimator\n")

    devs, kept, total = [], 0, 0
    for s in sessions:
        fr = frames_of(s)
        total += len(fr)
        i = 0
        while i + WIN <= len(fr):
            seg = fr[i:i + WIN]
            if any(f is None for f in seg):
                i += 1
                continue
            w = [dist(f[0], 5, 17) for f in seg]
            l = [dist(f[0], 0, 9) for f in seg]
            mw, ml = sorted(w)[len(w) // 2], sorted(l)[len(l) // 2]
            if mw <= 1e-6 or ml <= 1e-6:
                i += 1
                continue
            stable = (max(abs(v / mw - 1.0) for v in w) < SPAN_TOL and
                      max(abs(v / ml - 1.0) for v in l) < SPAN_TOL)
            if not stable:
                i += 1
                continue
            ang = unwrap([knuckle_angle(f[0]) for f in seg])
            sweep = abs(ang[-1] - ang[0])
            if sweep < MIN_SWEEP:
                i += 1
                continue

            horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
            st = horn.freeze(seg[0][0], seg[0][1])
            if st is None:
                i += 1
                continue
            q = horn.delta(st, seg[-1][0], seg[-1][1])
            if q is None:
                i += 1
                continue
            axis, rot = axis_angle(q)
            if axis is None or rot < 15.0:
                i += 1
                continue
            dev = math.degrees(math.acos(min(1.0, abs(axis[2]))))   # vs world Z (depth)
            devs.append(dev)
            kept += 1
            i += WIN          # non-overlapping
        # end while
    print(f"  scanned {len(sessions)} take(s), {total} frames -> {kept} clean roll segments\n")
    if not devs:
        print("  NO qualifying roll segments found. Roll cannot be settled from this data;")
        print("  a scripted roll take is required.")
        return
    devs.sort()
    print(f"  deviation of the fitted axis from the DEPTH axis (world Z):")
    print(f"      p50 {devs[len(devs)//2]:5.1f} deg     p95 {devs[int(len(devs)*0.95)]:5.1f} deg"
          f"     max {devs[-1]:5.1f} deg     n={len(devs)}")
    print()
    verdict = "OK" if devs[len(devs) // 2] < 15 else ("TILTED" if devs[len(devs) // 2] < 50 else "WRONG AXIS")
    print(f"  VERDICT: roll -> {verdict}")


if __name__ == "__main__":
    main()
