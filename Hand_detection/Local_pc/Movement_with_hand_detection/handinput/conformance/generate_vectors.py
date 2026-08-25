"""Generate `vectors/*.json` -- the golden vectors, as DATA rather than as asserts.

    .venv/Scripts/python.exe handinput/conformance/generate_vectors.py

⭐⭐ WHY THIS EXISTS WHEN 24 `verify_*.py` SUITES ALREADY DO. Those suites assert
in Python, so they can only ever test the Python. A port cannot run them. The same
inputs and outputs written to JSON can be run by ANY language, which turns
"is the TypeScript faithful?" from an argument into a test. That is rule 6
("golden vectors BEFORE a port exists") taken one step further: golden vectors in
a form a port can actually consume.

⛔ THE EXPECTATIONS ARE PRODUCED BY THE SHIPPED CODE, WHICH MAKES THEM A LOCK, NOT
A PROOF. They pin TODAY's behaviour so a port -- or a refactor -- cannot change it
silently. A number in here being *right* is what the 24 suites, the corpus
harnesses and the live takes are for. ⚠ So: regenerating after an intentional
change is correct; regenerating to make a red suite green is how the lock is lost.
Any regeneration must appear in a commit that says which behaviour changed.

⚠ FLOATS ARE WRITTEN FULL-PRECISION AND COMPARED WITH A TOLERANCE (1e-9), never
for equality. Cross-language float formatting differs in the last digit, and the
first port bug this project ever caught was a rounding-mode difference
(Python's banker's `round` vs JavaScript's half-up) -- so rounding is exactly what
must not be baked into the comparison.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from handinput.conformance import fixtures as F        # noqa: E402

try:
    from Resources import palm_geometry as PG          # noqa: E402
    from Resources import palm_depth as PD             # noqa: E402
    from Resources import palm_rotation as PR          # noqa: E402
    from Resources import hand_state as HS             # noqa: E402
    from Resources import hand_tracks as HT            # noqa: E402
    from Resources import owner_remap as OR            # noqa: E402
except ImportError:                                    # standalone export
    import palm_geometry as PG, palm_depth as PD, palm_rotation as PR   # noqa: E401,E402
    import hand_state as HS, hand_tracks as HT, owner_remap as OR       # noqa: E401,E402

VECTORS = os.path.join(_HERE, "vectors")
TOL = 1e-9


def _w(name, payload):
    os.makedirs(VECTORS, exist_ok=True)
    payload["_tolerance"] = TOL
    path = os.path.join(VECTORS, name + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=False)
    n = len(payload.get("cases", []))
    print("  %-26s %3d cases" % (name + ".json", n))
    return path


# --------------------------------------------------------------------------
def gen_palm_geometry():
    cases = []
    for label, kw in F.PIXEL_CASES:
        lm = F.pixel_hand(**kw)
        cases.append({
            "case": label,
            "input": {"landmarks": lm, "frameSize": list(F.FRAME_SIZE)},
            "expect": {
                "signed_palm_area": PG.signed_palm_area(lm),
                "edge_on_measure": PG.edge_on_measure(lm),
                "palm_center_px": list(PG.palm_center_px(lm)),
                "palm_width_px": PG.palm_width_px(lm),
                "is_edge_on": PG.is_edge_on(lm),
                # ⚠ BOTH labels, because `is_thumb_outward` NEGATES for "Left":
                # a port that drops that branch passes every right-hand case.
                "is_thumb_outward_Left": PG.is_thumb_outward(lm, "Left"),
                "is_thumb_outward_Right": PG.is_thumb_outward(lm, "Right"),
            },
        })
    for label, kw in F.WORLD_CASES:
        wl = F.world_hand(**kw)
        cases.append({
            "case": "world_" + label,
            "input": {"worldLandmarks": wl},
            "expect": {
                "signed_palm_volume": PG.signed_palm_volume(wl),
                "palm_plane_thickness": PG.palm_plane_thickness(wl),
                "geometric_chirality": PG.geometric_chirality(wl),
                "palm_observability": PG.palm_observability(wl),
            },
        })
    return _w("palm_geometry", {
        "module": "palm_geometry",
        "note": "signs and conditioning. `geometric_chirality` is U7's replacement "
                "for the 10.8%-wrong handedness label; its SIGN convention is the "
                "load-bearing part (CHIRALITY_V_NEGATIVE_IS_LEFT).",
        "cases": cases,
    })


def gen_projection():
    cases = []
    for depth in (0.30, 0.40, 0.497, 0.50, 0.85, 1.20):
        for size in (40.0, 80.0):
            cases.append({
                "case": "d%.3f_s%.0f" % (depth, size),
                "input": {"depth_m": depth, "nominal_size_px": size,
                          "frameSize": list(F.FRAME_SIZE)},
                "expect": {
                    "focal_px": PG.focal_px(F.FRAME_SIZE),
                    "clamp_depth": PG.clamp_depth(depth),
                    "projected_size_px": PG.projected_size_px(size, depth),
                    # round-trip: px -> world -> px must return the input
                    "world_from_px": list(PG.world_from_px(200.0, 150.0, depth, F.FRAME_SIZE)),
                    "px_roundtrip": list(PG.px_from_world(
                        *PG.world_from_px(200.0, 150.0, depth, F.FRAME_SIZE),
                        depth_m=depth, frame_size=F.FRAME_SIZE)),
                    "clamp_to_play_volume": list(PG.clamp_to_play_volume(
                        5.0, 5.0, depth, size, F.FRAME_SIZE)),
                },
            })
    return _w("projection", {
        "module": "palm_geometry (4.2 projection + play volume)",
        "note": "⚠ `clamp_to_play_volume` is fed a point OUTSIDE the boundary "
                "(5,5) on purpose -- the clamp is the behaviour, not the pass-through. "
                "`px_roundtrip` must equal (200,150) to tolerance at every depth.",
        "cases": cases,
    })


def gen_palm_depth():
    cases = []
    for label, kw in F.PIXEL_CASES:
        lm = F.pixel_hand(**kw)
        t = PD.HandDepthTracker()
        d1 = t.update(lm, F.FRAME_SIZE)
        d2 = t.update(lm, F.FRAME_SIZE)               # a second identical frame
        cases.append({
            "case": label,
            "input": {"landmarks": lm, "frameSize": list(F.FRAME_SIZE)},
            "expect": {
                "palm_spans": list(PD.palm_spans(lm)),
                "measure": PD.HandDepthTracker().measure(lm, PG.focal_px(F.FRAME_SIZE)),
                "update_1": [d1[0], bool(d1[1])],
                "update_2": [d2[0], bool(d2[1])],
            },
        })
    # ⭐ A SEQUENCE, because the ratio tracker is STATEFUL and its rate limit,
    # freeze and hold behaviour are the parts a port gets wrong. Zoom in, then
    # collapse the palm to edge-on so the tracker must HOLD rather than measure.
    seq, r = [], PD.DepthRatioTracker()
    base = F.pixel_hand()
    r.freeze(base)
    for i, squeeze in enumerate((1.0, 1.0, 0.9, 0.75, 0.5, 0.2, 0.05, 0.05, 0.6, 1.0)):
        lm = F.pixel_hand(scale=90.0 * (1.0 + 0.04 * i), width_squeeze=squeeze)
        ratio, valid = r.update(lm)
        seq.append({"frame": i, "width_squeeze": squeeze,
                    "ratio": ratio, "valid": bool(valid)})
    return _w("palm_depth", {
        "module": "palm_depth",
        "note": "⚠ `ratio_sequence` is ORDER-DEPENDENT: RATE_LIMIT_PER_FRAME, "
                "MIN/MAX_RATIO and the edge-on HOLD only appear across frames. "
                "A port that vectors single frames only will pass and still be wrong.",
        "cases": cases,
        "ratio_sequence": {"frozen_on": "pixel_hand()", "frames": seq},
    })


def gen_palm_rotation():
    """Horn's fit, as a sequence: freeze once, then rotate the hand."""
    horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
    px0, w0 = F.pixel_hand(), F.world_hand()
    state = horn.freeze(px0, w0)
    frames = []
    for tilt in (0.0, 5.0, 15.0, 35.0, 60.0, 90.0, 35.0, 0.0):
        w = F.world_hand(tilt_deg=tilt)
        q = horn.delta(state, F.pixel_hand(), w)
        frames.append({
            "tilt_deg": tilt,
            "quat": None if q is None else list(q),
            "angle_deg": None if q is None else PR.quat_angle_deg(PR._IDENTITY, q),
        })
    return _w("palm_rotation", {
        "module": "palm_rotation (Horn, shipped)",
        "note": "⛔ THE SIGN OF THE QUATERNION IS NOT FREE: q and -q are the same "
                "rotation, so a port comparing componentwise must resolve the "
                "double cover first (compare |dot| or the angle). "
                "⚠ Horn is exact on synthetic input -- these are a LOCK on the "
                "convention (axis order, frame handedness), not a measure of quality.",
        "cases": frames,
    })


def gen_hand_state():
    """D1/D2: the coast. ⚠ A pure function of (detected, now_ms) -- so it is
    fully specified by a sequence and is the easiest thing in the package for a
    port to get subtly wrong (the bridge boundary is `<=`, not `<`)."""
    t = HS.HandStateTracker()
    seq, now = [], 0.0
    script = [(True, 40.0)] * 3 + [(False, 40.0)] * 2 + [(True, 40.0)] * 2 + \
             [(False, 60.0)] * 4 + [(True, 40.0)] * 2
    for detected, dt in script:
        now += dt
        state = t.update(detected, now)
        seq.append({"t_ms": now, "detected": detected, "state": state,
                    "holds_track": t.holds_track,
                    "frames_since_measurement": t.frames_since_measurement,
                    "reacquired_after_ms": t.reacquired_after_ms})
    return _w("hand_state", {
        "module": "hand_state (D1/D2/D3)",
        "note": "BRIDGE_WINDOW_MS = %.1f. The 60 ms steps walk the gap PAST it, so "
                "the sequence contains both a bridged recovery and a genuine "
                "SUSTAINED_LOST." % HS.BRIDGE_WINDOW_MS,
        "cases": seq,
    })


def gen_owner_remap():
    """T3: ownership follows the TRACK across a relabel."""
    cases = []
    for label, owner, holder, ids in (
        ("no_holder", "Left", None, {"Left": 3, "Right": 4}),
        ("still_in_slot", "Left", 3, {"Left": 3, "Right": 4}),
        ("slots_swapped", "Left", 3, {"Left": 4, "Right": 3}),
        ("track_absent", "Left", 3, {"Left": -1, "Right": 4}),
        ("both_absent", "Right", 9, {"Left": -1, "Right": -1}),
        ("int_owner_untouched", 3, 3, {"Left": 4, "Right": 3}),
    ):
        cases.append({"case": label,
                      "input": {"owner": owner, "holder_track": holder, "track_ids": ids},
                      "expect": {"owner": OR.remap_owner(owner, holder, ids),
                                 "slot_of_track": OR.slot_of_track(ids, holder)}})
    return _w("owner_remap", {
        "module": "owner_remap (T3)",
        "note": "⭐ `track_absent` is the case that matters: an absent track must "
                "be a NO-OP here, because releasing it belongs to the strand timer. "
                "Getting this wrong strands a cube -- the owner hit that live.",
        "cases": cases,
    })


def gen_hand_tracks():
    reg = HT.TrackRegistry(dict)
    seq, now = [], 0.0
    for ids in ({"Left": 1, "Right": 2}, {"Left": 2, "Right": 1},
                {"Left": -1, "Right": 1}, {"Left": -1, "Right": -1},
                {"Left": 1, "Right": 3}):
        now += 100.0
        resolved = reg.resolve(dict(ids), now)
        seq.append({"t_ms": now, "slot_ids": ids, "resolved": resolved,
                    "live_ids": sorted(reg.live_ids())})
    return _w("hand_tracks", {
        "module": "hand_tracks",
        "note": "SLOT_MEMORY_MS = %.1f, TRACK_TTL_MS = %.1f." % (
            HT.SLOT_MEMORY_MS, HT.TRACK_TTL_MS),
        "cases": seq,
    })


def main():
    print("handinput conformance -- generating vectors")
    for gen in (gen_palm_geometry, gen_projection, gen_palm_depth,
                gen_palm_rotation, gen_hand_state, gen_owner_remap, gen_hand_tracks):
        gen()
    print("done -> %s" % VECTORS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
