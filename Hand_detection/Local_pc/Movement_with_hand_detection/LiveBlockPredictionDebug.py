"""Side-by-side A/B of the confirmation gate (B7), with the hand drawn as BLOCKS.

    LEFT   "RAW"    the normal pipeline -- exactly what debug_snap.bat shows
    RIGHT  "GATED"  the same frame, same detections, with B7's confirmation
                    gate (Resources/confirmation_gate.py) wired in

⛔ THE GATE THIS TOOL DEMONSTRATES IS PARKED (owner, 2026-08-04, spec 16.9.1):
   measured, cleared of its blockers, and then declined because the improvement
   is real but NOT VISIBLE and the pipeline stays leaner without the layer.
   ⭐ THE TOOL IS NOT PARKED. Keep it: it is the only place raw and gated cube
   behaviour can be compared side by side, it records takes for offline replay,
   and it is what caught the `scale` back-projection bug that no harness did.

Launch with `debug_prediction.bat`. Press 'q' in either window to stop.

⚠ ONE PROCESS, TWO WINDOWS -- AND THAT IS NOT A SHORTCUT, IT IS THE POINT
-------------------------------------------------------------------------
Two processes cannot both open the same webcam on Windows (DirectShow gives
exclusive access), so a two-process version would need two cameras -- and then
the two windows would be watching DIFFERENT hand motions, which makes the
comparison worthless. Here the camera is read ONCE, MediaPipe runs ONCE, DR-1
identity and DR-2 palm-facing run ONCE, and only then does the stream fork into
two independent `CubeState`s. **Every difference you see between the windows is
caused by the gate and by nothing else.**

The two windows are placed side by side automatically (`--gap`, `--scale`).


HOW THE GATE IS WIRED (16.2 rule 5 -- the consumers split)
----------------------------------------------------------
Per hand, per frame: `hand_blocks.block_state()` -> `ConfirmationGate.update()`
-> a corrected landmark set that the unchanged cube logic then consumes. The
gate's four channel groups are applied in the only places they can act:

  palm position    a pure TRANSLATION of all pixel landmarks
  palm rotation    the world landmarks are rotated by q_gated * conj(q_raw), so
                   `_hand_orientation_quaternion` -- untouched -- returns the
                   gated orientation, and its conditioning measure stays honest
  finger arcs      each finger's PIP/DIP/TIP slide along the MCP->TIP ray to
                   match the gated extension scalar. ⚠ Done in PIXEL space, not
                   world: the arcs reach the cube only through the fingertips in
                   `_weighted_position`'s translation anchor, and the palm frame
                   uses no finger bones at all (§0.18), so a world-space arc
                   correction would be invisible to the cube by construction
  palm scale       ⚠⚠ NOT BACK-PROJECTED AT ALL -- gated and displayed (as the
                   knuckle bar's length), never turned into landmark positions.
                   See `LANDMARK_CHANNELS` for the measured reason; the obvious
                   similarity transform divides by a palm width that COLLAPSES
                   edge-on and threw the hand 5235 px across the window

⚠ **S3, BINDING, and visible on screen**: while any palm channel is PENDING the
gate has not yet decided, so that hand may take NO NEW SNAP -- `update_hands`
receives it in `snap_blocked` and the HUD shows `S3 HOLD`. A cube already held
keeps being translated and rotated from the gated output; only the *decision* is
frozen. Prediction must never latch into a gesture.

⚠ **What you should NOT expect to see, and it is why the gate was parked.**
Back-of-hand and edge-on poses are nearly identical between the windows -- those
errors are SUSTAINED, so F..F+L agree coherently in the wrong place and the gate
accepts them -- and after DR-1 there are almost no identity teleports left to
catch. On a 450 s live take (§16.9) the held cube's worst step drops 21% and its
worst still-hand step 47%, which is real but **not visible to the eye**, against
~89 ms of hold at every flag and ~4% of grabs delayed. That trade is exactly what
this tool exists to let you judge, and the owner judged it not worth a layer.


THE BLOCK VIEW -- what replaced the landmark skeleton
------------------------------------------------------
The owner's model (§16) says a hand is six blocks and the landmark skeleton is
noise around them, so this tool draws the six blocks and NOT the 21 points. Each
drawn element is one channel of the state the gate actually judges:

  PALM (one block, 4 channels)
    * filled quad through the palm landmarks   -- the block itself
    * dot at its centroid                      -- `pos_x`, `pos_y`
    * bar across the knuckle row               -- `scale` (palm width, px)
    * 3-axis gizmo from the centroid           -- `quat` (R/G/B = e1/e2/e3)
  FINGERS (4 blocks, 1 channel each)
    * MCP and TIP vertices as dots, joined by a CIRCULAR ARC whose bow is
      computed from the arc-extension scalar alone -- straight at 1.0, bowing
      further as it curls. ⭐ The arc's SHAPE carries no landmark information:
      it is drawn from (MCP, TIP, extension), so what you see is exactly what
      the model keeps and nothing else. Only the SIDE it bows toward is taken
      from the real PIP, so the arc bends the way the finger does.
  THUMB (1 block, unmodelled)
    * raw polyline over its 4 landmarks, drawn dashed and labelled RAW -- the
      thumb is deliberately NOT an arc (saddle joint, §16 scope note), and
      drawing it differently is the honest way to show that.

A channel currently held PENDING by the gate is drawn in amber; a channel whose
frames were just DISCARDED flashes red. So the gate's state is legible on the
hand itself, not only in the HUD.

Not part of the production pipeline -- same "deliberately independent debug tool"
contract as LiveSnapDebug.py, which this file imports rather than copies.
"""

import argparse
import datetime
import json
import math
import os
import sys
import time
from typing import List, Tuple

import cv2
import numpy as np
import mediapipe as mp

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# ⚠ Imported, never copied -- the whole cube/snap/translate/rotate logic, the
# DR-1 tracker and the DR-2 trackers all come from the tool that already has
# them. Importing it opens no window (it is a single-OpenCV-window tool with no
# pygame at module scope), which is exactly why it is safe to reuse here.
import LiveSnapDebug as LSD                                    # noqa: E402
from Resources import hand_blocks as HB                        # noqa: E402
from Resources import confirmation_gate as CG                  # noqa: E402

sys.path.insert(0, os.path.join(
    BASE, "..", "Python_Server_MediaPipe_vision_pipeline", "Resources"))
import hand_identity                                           # noqa: E402

TRACKED_HANDS = LSD.TRACKED_HANDS

# --- block palette (BGR) ---
PALM_FILL = (150, 90, 40)
PALM_EDGE = (255, 190, 120)
ARC_COLOR = (90, 220, 90)
ARC_VERTEX = (255, 255, 255)
THUMB_COLOR = (200, 160, 255)
AXIS_COLORS = ((60, 60, 255), (60, 220, 60), (255, 180, 60))   # e1, e2, e3
PENDING_COLOR = (0, 190, 255)        # amber: the gate is withholding judgement
DISCARD_COLOR = (60, 60, 255)        # red: frames were just thrown away
PALM_ALPHA = 0.30

ARC_SEGMENTS = 18
DISCARD_FLASH_FRAMES = 6             # how long a discard stays visible on screen

# Recordings live on the external drive, never beside the code (owner rule).
CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_prediction_gate"


# ---------------------------------------------------------------- arc geometry
def _sagitta(chord: float, extension: float) -> float:
    """Bow height of the circular arc with this chord and this extension.

    `extension` is chord/contour (`hand_blocks.finger_extension`), so for a
    circular arc of half-angle t = theta/2 it is exactly sin(t)/t. Inverting
    that by bisection gives the arc that genuinely has the measured extension --
    rather than some eyeballed "curl factor", which would make the picture a
    drawing of a parameter instead of a drawing of the state.
    """
    if extension is None or extension >= 0.9995 or chord <= 1e-6:
        return 0.0
    ext = max(0.05, min(0.9995, extension))
    lo, hi = 1e-4, math.pi - 1e-4               # t in (0, pi): up to a full half-turn
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if math.sin(mid) / mid > ext:           # sinc is monotone decreasing on (0, pi)
            lo = mid
        else:
            hi = mid
    t = 0.5 * (lo + hi)
    # r = (chord/2)/sin(t); sagitta = r(1 - cos t)
    return (chord / 2.0) * (1.0 - math.cos(t)) / max(1e-6, math.sin(t))


def _arc_points(mcp, tip, pip, extension) -> List[Tuple[float, float]]:
    """Circular arc from MCP to TIP bowing by the extension scalar.

    ⭐ Shape from (mcp, tip, extension) ONLY. `pip` decides nothing but which
    SIDE the bow falls on, so the arc bends the way the real finger does; drop
    it and the picture is still correct, just possibly mirrored.
    """
    dx, dy = tip[0] - mcp[0], tip[1] - mcp[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-6:
        return [mcp, tip]
    ux, uy = dx / chord, dy / chord
    nx, ny = -uy, ux
    if pip is not None:                          # which side is the finger really on?
        side = (pip[0] - mcp[0]) * nx + (pip[1] - mcp[1]) * ny
        if side < 0:
            nx, ny = -nx, -ny
    s = _sagitta(chord, extension)
    if s < 0.5:
        return [mcp, tip]
    pts = []
    for i in range(ARC_SEGMENTS + 1):
        u = i / ARC_SEGMENTS
        # quadratic Bezier through a control point at 2x the sagitta reproduces
        # the circular arc's midpoint exactly, which is where the bow reads.
        b = 4.0 * u * (1.0 - u)
        pts.append((mcp[0] + dx * u + nx * s * b, mcp[1] + dy * u + ny * s * b))
    return pts


# ---------------------------------------------------------------- block drawing
def _poly(pts):
    return np.array([[int(round(x)), int(round(y))] for x, y in pts], dtype=np.int32)


def draw_blocks(frame, px, state, handedness, status=None):
    """Draw the six blocks for one hand. `status` maps channel -> 'pending' /
    'discarded' / None, so the gate's own state is legible on the hand."""
    status = status or {}

    def chan_color(channels, default):
        for c in channels:
            if status.get(c) == "discarded":
                return DISCARD_COLOR
            if status.get(c) == "pending":
                return PENDING_COLOR
        return default

    # --- palm block: the quad, alpha-blended so the video stays readable ---
    palm_pts = [px[i] for i in HB.PALM_LANDMARKS]
    hull = cv2.convexHull(_poly(palm_pts))
    overlay = frame.copy()
    cv2.fillConvexPoly(overlay, hull, PALM_FILL)
    cv2.addWeighted(overlay, PALM_ALPHA, frame, 1 - PALM_ALPHA, 0, frame)
    cv2.polylines(frame, [hull], True,
                  chan_color(("pos_x", "pos_y"), PALM_EDGE), 2, cv2.LINE_AA)

    centroid = state.get("position")
    scale = state.get("scale")
    if centroid is None:
        return
    cxi, cyi = int(round(centroid[0])), int(round(centroid[1]))

    # --- scale channel: a bar of exactly `scale` pixels, centred on the
    # centroid and aligned with the knuckle row.
    # ⚠ Drawn from the SCALAR, not between the two MCP landmarks: `scale` is
    # never back-projected onto landmark positions (see LANDMARK_CHANNELS), so
    # a bar drawn between landmarks would show the raw width in both windows and
    # the channel's gating would be invisible. Length here IS the channel value,
    # which is why the gated bar can differ from the raw one while the vertices
    # stay put.
    if scale:
        a, b = px[HB.INDEX_MCP], px[HB.PINKY_MCP]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n > 1e-6:
            ux, uy = dx / n, dy / n
            p0 = (centroid[0] - ux * scale / 2, centroid[1] - uy * scale / 2)
            p1 = (centroid[0] + ux * scale / 2, centroid[1] + uy * scale / 2)
            cv2.line(frame, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])),
                     chan_color(("scale",), (255, 255, 0)), 2, cv2.LINE_AA)

    # --- rotation channel: the palm frame's three axes, from the centroid.
    # The world frame is hand-relative metric with x right / y down, so dropping
    # z is a faithful orthographic projection for a gizmo -- an axis pointing at
    # the camera correctly shortens to a stub.
    q = state.get("quaternion")
    if q and scale:
        L = 0.55 * scale
        for axis, color in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), AXIS_COLORS):
            v = LSD._quat_rotate_vector(q, axis)
            tip = (centroid[0] + v[0] * L, centroid[1] + v[1] * L)
            if status.get("quat") in ("pending", "discarded"):
                color = chan_color(("quat",), color)
            cv2.arrowedLine(frame, (cxi, cyi),
                            (int(round(tip[0])), int(round(tip[1]))),
                            color, 2, cv2.LINE_AA, tipLength=0.25)
    cv2.circle(frame, (cxi, cyi), 5, chan_color(("pos_x", "pos_y"), (255, 255, 255)), -1)

    # --- the four finger arcs: one scalar each ---
    arcs = state.get("arcs") or (None,) * 4
    for i, (mcp_i, pip_i, dip_i, tip_i) in enumerate(HB.ARC_FINGERS.values()):
        ext = arcs[i] if i < len(arcs) else None
        color = chan_color((f"arc{i}",), ARC_COLOR)
        pts = _arc_points(px[mcp_i], px[tip_i], px[pip_i], ext)
        cv2.polylines(frame, [_poly(pts)], False, color, 2, cv2.LINE_AA)
        for v in (px[mcp_i], px[tip_i]):
            cv2.circle(frame, (int(round(v[0])), int(round(v[1]))), 4, ARC_VERTEX, -1)
            cv2.circle(frame, (int(round(v[0])), int(round(v[1]))), 4, color, 1, cv2.LINE_AA)
        if ext is not None:
            cv2.putText(frame, f"{ext:.2f}",
                        (int(px[tip_i][0]) + 6, int(px[tip_i][1]) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

    # --- thumb: RAW and unmodelled, drawn dashed so it cannot be mistaken
    # for an arc (§16 scope: its CMC is a saddle joint, "more or less bent"
    # does not describe opposition, and what to do with it is DEFERRED).
    thumb = [px[i] for i in HB.THUMB_LANDMARKS]
    for j in range(len(thumb) - 1):
        a, b = thumb[j], thumb[j + 1]
        for k in range(0, 6, 2):                  # dashed
            t0, t1 = k / 6.0, (k + 1) / 6.0
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            cv2.line(frame, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])),
                     THUMB_COLOR, 2, cv2.LINE_AA)
    cv2.putText(frame, "thumb: RAW", (int(thumb[-1][0]) + 6, int(thumb[-1][1])),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, THUMB_COLOR, 1, cv2.LINE_AA)
    cv2.putText(frame, handedness, (cxi - 14, cyi - int((scale or 60) * 0.7)),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


# ---------------------------------------------------------------- gate wiring
ALL_CHANNEL_GROUPS = ("position", "scale", "arcs", "quat")

# Which gated channels may be realised as LANDMARK POSITIONS.
#
# ⚠⚠ `scale` IS DELIBERATELY ABSENT, and this was a real bug before it was a
# design note -- spotted live by the owner ("in the gated window the arc and
# vertices literally jump all around the window"), then measured:
#
#   The obvious realisation of a gated palm width is a similarity transform,
#   f = gated_scale / raw_scale about the centroid. ITS DENOMINATOR COLLAPSES.
#   Edge-on, measured palm width falls to a couple of pixels while the gate
#   coasts its held value, so on a 450 s take f reached 35.4 and threw the
#   landmarks 5235 px across a 640 px window. Of the 118 frames with >100 px of
#   displacement, median palm width was 41.8 px against 91.6 px overall and
#   median edge_on 0.319 against 0.747 -- precisely the edge-on band.
#
#   ⭐ And it was wrong before it was unstable: EDGE-ON THE PALM IS
#   FORESHORTENED, NOT SHRUNK. "Palm width should be 86 px" has no valid
#   realisation as landmark positions at all; assuming the whole hand scaled is
#   the reciprocal of the trap §14.3.1/§16.5 documented, where feeding palm-width
#   collapse INTO cube position was the measured difference between arms B and C.
#
# So `scale` is still gated, and still DISPLAYED (as the length of the knuckle
# bar), but never back-projected. The three that remain each have a denominator
# that cannot collapse: position realises as a bounded TRANSLATION, quat as a
# bounded ROTATION of the world landmarks, arcs as a bounded slide along each
# finger's own MCP->TIP ray.
LANDMARK_CHANNELS = ("position", "quat", "arcs")
ARC_RATIO_CLAMP = 2.0        # a finger cannot plausibly double or halve in a frame


def apply_gate_to_landmarks(px, world, raw_state, out_state,
                            channels=LANDMARK_CHANNELS):
    """Realise the gated block state as a corrected landmark set.

    The cube logic is left completely untouched; it is fed corrected inputs.
    See LANDMARK_CHANNELS above for which channels may act here, and for the
    measured reason `scale` may not.
    """
    px = [tuple(p) for p in px]
    rp, gp = raw_state.get("position"), out_state.get("position")
    if "position" in channels and rp and gp and None not in gp:
        dx, dy = gp[0] - rp[0], gp[1] - rp[1]       # pure translation, bounded
        px = [(x + dx, y + dy) for x, y in px]

    if "arcs" in channels:
        r_arcs = raw_state.get("arcs") or ()
        g_arcs = out_state.get("arcs") or ()
        for i, (mcp_i, pip_i, dip_i, tip_i) in enumerate(HB.ARC_FINGERS.values()):
            if i >= len(r_arcs) or i >= len(g_arcs):
                continue
            ra, ga = r_arcs[i], g_arcs[i]
            if not ra or ga is None or abs(ga - ra) < 1e-9:
                continue
            # Bounded by construction -- extension is a chord/contour ratio and
            # cannot collapse the way a pixel width does -- and clamped anyway:
            # the scale bug is not a mistake worth making twice.
            k = max(1.0 / ARC_RATIO_CLAMP, min(ARC_RATIO_CLAMP, ga / ra))
            ax, ay = px[mcp_i]
            for j in (pip_i, dip_i, tip_i):
                px[j] = (ax + (px[j][0] - ax) * k, ay + (px[j][1] - ay) * k)

    if "quat" in channels:
        rq, gq = raw_state.get("quaternion"), out_state.get("quaternion")
        if rq and gq:
            dq = LSD._quat_multiply(gq, LSD._quat_conjugate(rq))
            world = [LSD._quat_rotate_vector(dq, w) for w in world]
    return px, world


def channel_status(res, flash):
    """channel -> 'discarded' | 'pending' | None, with discards held on screen
    for a few frames because a 1-frame flash at 24 fps is invisible."""
    st = {}
    for ch, left in list(flash.items()):
        if left > 0:
            st[ch] = "discarded"
            flash[ch] = left - 1
    for ch in res.get("pending", ()):
        st.setdefault(ch, "pending")
    for ch in res.get("discarded", ()):
        st[ch] = "discarded"
        flash[ch] = DISCARD_FLASH_FRAMES
    return st


# ---------------------------------------------------------------- HUD
def draw_hud(frame, title, subtitle, counters=None, holds=(), color=(255, 255, 255)):
    """Title/subtitle in a top strip, live counters in a BOTTOM strip.

    Separate strips on purpose: the title is long enough that right-aligning the
    counters on the same row collides with it at 640 px, which is exactly the
    width this runs at.
    """
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 50), (0, 0, 0), -1)
    cv2.putText(frame, title, (10, 22), cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 1, cv2.LINE_AA)
    cv2.putText(frame, subtitle, (10, 41), cv2.FONT_HERSHEY_SIMPLEX, 0.40,
                (185, 185, 185), 1, cv2.LINE_AA)
    if counters or holds:
        cv2.rectangle(frame, (0, h - 26), (w, h), (0, 0, 0), -1)
        if counters:
            cv2.putText(frame, counters, (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.44,
                        (200, 200, 200), 1, cv2.LINE_AA)
        if holds:
            txt = "S3 HOLD: " + ", ".join(sorted(holds))
            (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.46, 1)
            cv2.putText(frame, txt, (w - tw - 10, h - 8),
                        cv2.FONT_HERSHEY_DUPLEX, 0.46, PENDING_COLOR, 1, cv2.LINE_AA)


def cube_snapshot(state):
    return {n: {"pos": [round(c.position[0], 3), round(c.position[1], 3)],
                "quat": [round(v, 6) for v in c.orientation],
                "owner": c.owner}
            for n, c in state.cubes.items()}


def save_recording(records, args, width, height, counters):
    """⚠ LANDMARKS FIRST, then meta -- the same rule RecordPerceptionSequence
    enforces: the JSONL is the irreplaceable part and E: drops out (N4).

    ⚠ REAL wall-clock timestamps, never a synthesised 33 ms step. N17: takes
    that faked the step reported ~30.4 fps when the true rate was ~24, which
    made every real-time derivative wrong by ~25%. `tCapture` here is
    perf_counter at grab time.
    """
    if not records:
        print("[record] No frames captured, nothing saved.")
        return None
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session = os.path.join(args.record_root, f"{stamp}_{args.sequence}")
    os.makedirs(session, exist_ok=True)
    with open(os.path.join(session, "raw_landmarks.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    span = (records[-1]["tCapture"] - records[0]["tCapture"]) / 1000.0
    meta = {
        "sequence": args.sequence,
        "note": args.note,
        "frames": len(records),
        "actual_span_s": round(span, 3),
        "measured_fps": round(len(records) / span, 2) if span > 0 else None,
        "resolution": [width, height],
        "camera_index": args.camera_index,
        "mirrored_preview": True,
        "detection_on_mirrored_frame": True,
        "timestamps": "real perf_counter at capture (NOT synthesised -- see N17)",
        "tool": "LiveBlockPredictionDebug.py",
        "gate": {"lag": args.lag, "verdict_test": CG.VERDICT_TEST,
                 "reject_z_cli": args.reject_z,
                 "coast_mode": CG.COAST_MODE, "blend": CG.BLEND_FRAMES,
                 "fit_kwargs": CG.FIT_KWARGS, "reject_z": BPCFG["reject_z"],
                 "window": BPCFG["window"], "floors": "derived, block_predictor.FLOOR"},
        "counters": counters,
        "contains": ("per-frame raw pixel+world landmarks, the resolved DR-1 label, "
                     "the gate's per-channel decision, and BOTH cube states -- so the "
                     "A/B can be replayed offline under any gate configuration"),
    }
    with open(os.path.join(session, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[record] {len(records)} frames ({meta['measured_fps']} fps measured) -> {session}")
    return session


BPCFG = {"reject_z": None, "window": None}


def main():
    p = argparse.ArgumentParser(
        description="Side-by-side RAW vs GATED cube behaviour, hand drawn as blocks.")
    p.add_argument("--camera-index", type=int, default=0)
    # Recording is ON by default: a session you cannot re-measure offline is a
    # session you have to ask the operator to perform again.
    p.add_argument("--no-record", dest="record", action="store_false",
                   help="do NOT record (recording is on by default)")
    p.add_argument("--record", dest="record", action="store_true",
                   help=argparse.SUPPRESS)   # kept so old invocations still work
    p.set_defaults(record=True)
    p.add_argument("--record-root", default=CAPTURE_ROOT)
    p.add_argument("--sequence", default="gate_live_ab")
    p.add_argument("--note", default="")
    p.add_argument("--scale", type=float, default=1.0,
                   help="display scale for BOTH windows (use <1 if they do not fit)")
    p.add_argument("--gap", type=int, default=12, help="pixels between the windows")
    p.add_argument("--lag", type=int, default=CG.LAG,
                   help="B7's confirmation lag L, in frames (2 = ~83 ms at 24 fps)")
    # ⭐ The best single tune found by the live sweep (analysis/b7_live_ab.py):
    # 4.0 cuts flags 44% and the cube's max step a further 12% against the
    # default 3.0, at no latency cost and no measurable grab loss.
    p.add_argument("--reject-z", type=float, default=CG.BP.REJECT_Z,
                   help="flag threshold in sigmas (3.0 default, 4.0 measured better)")
    p.add_argument("--landmarks", action="store_true",
                   help="draw the raw 21-point skeleton instead of the six blocks")
    args = p.parse_args()

    gate_probe = CG.ConfirmationGate(lag=args.lag, reject_z=args.reject_z)
    BPCFG["reject_z"], BPCFG["window"] = gate_probe.reject_z, gate_probe.window
    if args.record:
        # Preflight the capture root BEFORE the operator does anything: fail
        # before their effort, never after it (N4 -- E: drops out).
        try:
            os.makedirs(args.record_root, exist_ok=True)
            probe = os.path.join(args.record_root, ".writable")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
        except OSError as e:
            raise SystemExit(f"[record] capture root not writable: {args.record_root}\n"
                             f"         {e}\n"
                             f"         Is E: connected? Pass --record-root to override.")

    detector = LSD.build_detector()
    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera_index}). "
                           "Is another program -- or a second copy of this tool -- using it?")
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("Could not read an initial frame from the webcam.")
    height, width = frame.shape[:2]

    state_raw = LSD.CubeState(window_size=(width, height))
    state_gated = LSD.CubeState(window_size=(width, height))
    gates = {h: CG.ConfirmationGate(lag=args.lag, reject_z=args.reject_z)
             for h in TRACKED_HANDS}
    flash = {h: {} for h in TRACKED_HANDS}
    seen_last = {h: False for h in TRACKED_HANDS}
    n_flag = n_disc = n_conf = 0

    win_raw = "RAW -- no gate (production behaviour)"
    win_gated = f"GATED -- B7 confirmation gate, L={args.lag}, z={args.reject_z}"
    disp_w = int(width * args.scale)
    disp_h = int(height * args.scale)
    for name, x in ((win_raw, 0), (win_gated, disp_w + args.gap)):
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(name, disp_w, disp_h)
        cv2.moveWindow(name, x, 0)

    fps_hint = 1000.0 / 24.0
    lat_ms = args.lag * fps_hint
    timestamp_ms = 0
    print(f"[BlockPredictionDebug] Running -- L={args.lag} (~{lat_ms:.0f} ms hold "
          f"per flag). Press 'q' in either window to stop.")

    records = []
    frame_idx = -1
    try:
        while True:
            ok, frame = cap.read()
            t_capture = time.perf_counter() * 1000.0    # REAL, never synthesised (N17)
            if not ok:
                break
            frame_idx += 1
            frame = cv2.flip(frame, 1)          # mirror, matching production's invert_x
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
            timestamp_ms += 33

            # --- ONE detection, ONE identity resolution, shared by both arms ---
            detections = []
            for i in range(len(result.hand_landmarks)):
                label = result.handedness[i][0].category_name
                if label not in TRACKED_HANDS:
                    continue
                detections.append({
                    "raw_handedness": label,
                    "score": float(result.handedness[i][0].score),
                    "pixel_landmarks": [(lm.x * width, lm.y * height)
                                        for lm in result.hand_landmarks[i]],
                    "world_landmarks": [(lm.x, lm.y, lm.z)
                                        for lm in result.hand_world_landmarks[i]],
                    "normalized": result.hand_landmarks[i],
                })
            obs = [(hand_identity.palm_centroid(d["pixel_landmarks"]),
                    d["raw_handedness"], d["score"],
                    hand_identity.palm_width(d["pixel_landmarks"])) for d in detections]
            if detections and all(o[0] is not None for o in obs):
                labels = LSD._hand_identity_tracker.update(
                    obs, now_ms=time.perf_counter() * 1000.0)
            else:
                labels = [d["raw_handedness"] for d in detections]

            data_raw = {h: None for h in TRACKED_HANDS}
            data_gated = {h: None for h in TRACKED_HANDS}
            draw_raw, draw_gated, normalized_by_label = {}, {}, {}
            holds = set()
            seen = {h: False for h in TRACKED_HANDS}
            rec_hands = []

            for d, label in zip(detections, labels):
                seen[label] = True
                # DR-2 runs ONCE and feeds both arms: it is upstream of the gate.
                outward, _valid = LSD._palm_facing_trackers[label].update(
                    d["pixel_landmarks"], label)
                px, world = d["pixel_landmarks"], d["world_landmarks"]
                data_raw[label] = {"pixel_landmarks": px, "world_landmarks": world,
                                   "thumb_outward": outward}
                # keyed by the RESOLVED label, never the raw one (DR-1): both
                # detections can carry the same raw handedness on the same frame.
                normalized_by_label[label] = d["normalized"]

                raw_state = HB.block_state(px, world)
                if raw_state is None or raw_state.get("position") is None:
                    data_gated[label] = dict(data_raw[label])
                    draw_raw[label] = (px, raw_state or {}, {})
                    draw_gated[label] = (px, raw_state or {}, {})
                    continue

                if not seen_last[label]:
                    gates[label].reset()        # never judge a new track against the old one
                res = gates[label].update(raw_state)
                n_flag += len(res["flagged"])
                n_disc += len(res["discarded"])
                n_conf += len(res["confirmed"])
                out_state = res["output"]
                gpx, gworld = apply_gate_to_landmarks(px, world, raw_state, out_state)
                data_gated[label] = {"pixel_landmarks": gpx, "world_landmarks": gworld,
                                     "thumb_outward": outward}

                # S3: while a PALM channel is unresolved the gate has not decided,
                # so no new snap may be taken with it. A held cube keeps moving.
                if any(not res["valid"][c] for c in ("pos_x", "pos_y", "scale", "quat")):
                    holds.add(label)

                st = channel_status(res, flash[label])
                draw_raw[label] = (px, raw_state, {})
                draw_gated[label] = (gpx, out_state, st)

                if args.record:
                    rec_hands.append({
                        "label": label,
                        "raw_handedness": d["raw_handedness"],
                        "score": round(d["score"], 4),
                        "thumb_outward": bool(outward),
                        # RAW landmarks: the gated ones are reproducible from
                        # these, the gate is not reproducible from the gated ones.
                        "landmarks": [[round(v, 3) for v in q] for q in px],
                        "world_landmarks": [[round(v, 6) for v in q] for q in world],
                        "gate": {
                            "flagged": list(res["flagged"]),
                            "pending": list(res["pending"]),
                            "discarded": list(res["discarded"]),
                            "confirmed": list(res["confirmed"]),
                            "forced": list(res["forced"]),
                            "invalid": [c for c, v in res["valid"].items() if not v],
                            "z": {c: round(dd["z"], 4)
                                  for c, dd in res["debug"].items() if "z" in dd},
                        },
                    })

            seen_last = seen

            LSD.update_hands(state_raw, data_raw)
            LSD.update_hands(state_gated, data_gated, snap_blocked=holds)

            if args.record:
                records.append({
                    "frame": frame_idx,
                    "tCapture": round(t_capture, 3),
                    "hands": rec_hands,
                    "s3_hold": sorted(holds),
                    "cubes_raw": cube_snapshot(state_raw),
                    "cubes_gated": cube_snapshot(state_gated),
                })

            frame_raw = frame.copy()
            frame_gated = frame.copy()
            for label, (px, st, status) in draw_raw.items():
                if args.landmarks and label in normalized_by_label:
                    LSD._draw_hand(frame_raw, normalized_by_label[label], label,
                                   data_raw[label]["thumb_outward"],
                                   state_raw.thumb_outward_snap_allowed[label],
                                   state_raw.last_hand_reliability_alpha[label],
                                   width, height)
                else:
                    draw_blocks(frame_raw, px, st, label)
            for label, (px, st, status) in draw_gated.items():
                draw_blocks(frame_gated, px, st, label, status)

            LSD._draw_cubes(frame_raw, state_raw)
            LSD._draw_cubes(frame_gated, state_gated)

            draw_hud(frame_raw, "RAW  (no gate)",
                     "what debug_snap.bat shows -- the production behaviour")
            draw_hud(frame_gated,
                     f"GATED  (B7, L={args.lag}, z={args.reject_z}, ~{lat_ms:.0f} ms hold)",
                     "amber = channel PENDING (deciding)   red = frames DISCARDED",
                     counters=f"flag {n_flag}  discard {n_disc}  keep {n_conf}",
                     holds=holds, color=PENDING_COLOR)

            cv2.imshow(win_raw, frame_raw)
            cv2.imshow(win_gated, frame_gated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if (cv2.getWindowProperty(win_raw, cv2.WND_PROP_VISIBLE) < 1
                    or cv2.getWindowProperty(win_gated, cv2.WND_PROP_VISIBLE) < 1):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"[BlockPredictionDebug] Stopped. flags {n_flag}, discarded {n_disc}, "
              f"confirmed {n_conf}.")
        if args.record:
            save_recording(records, args, width, height,
                           {"flagged": n_flag, "discarded": n_disc, "confirmed": n_conf})


if __name__ == "__main__":
    main()
