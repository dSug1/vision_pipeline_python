"""Six-arm live A/B, with the hand drawn as BLOCKS. 3 rows x 2 columns.

    1  §14.1 anchor, OLD rotation          2  + B7 gate    <- the BASELINE
    3  ARM B anchor, OLD rotation          4  + B7 gate    <- change ONE thing
    5  ARM B + HORN rotation               6  + B7 gate    <- change ONE more
       (with --horn-on-141, row 3 is §14.1 + HORN = PRODUCTION since 2026-08-17)

  ⚠⚠ ROW 1 IS NO LONGER PRODUCTION. On 2026-08-17 production moved to §14.1
  anchor + Horn palm-only rotation, no gate (`HandsTriggeredActions.py`). Row 1
  keeps the OLD Gram-Schmidt frame DELIBERATELY, because every row below is
  measured against it and changing it would make each row compare against a
  moving reference. To see production, run `--horn-on-141` and read WINDOW 5.

  ⚠ The three headline results below are REPLAY numbers and TWO OF THEM DID NOT
  SURVIVE LIVE (2026-08-17, `Claude/HANDOFF_ANCHOR_ROTATION.md` + the B4 queue
  row). Arm B was REJECTED: its still-hand step is worse on all four takes, and
  its "sink 0.000" is an algebraic identity, not a measurement -- see
  `analysis/b4_orbit_and_sink_audit.py`. Horn's 3.82/9.64 did not reproduce
  either: live, both estimators emit the SAME ~60 deg jumps to within 1 deg,
  because those jumps are in the landmarks and no rotation estimator can remove
  them. Horn palm-only shipped on design grounds (no worse, cannot degenerate),
  NOT on measured benefit -- the balanced blind A/B scored 4-2, p = 0.34.

  ⭐ EACH ROW IS A ONE-VARIABLE CHANGE ON THE ROW ABOVE, and this is verified,
  not assumed -- replayed on a pitch take:

                            cube POSITION p95/max   cube ORIENTATION p95/max
      1  §14.1                   5.09 / 13.57              6.22 / 37.57
      3  arm B                   8.11 / 25.07              6.22 / 37.57   <- same
      5  arm B + Horn            8.11 / 25.07              3.82 /  9.64   <- same

  The anchor moves ONLY position; the rotation estimator moves ONLY orientation.
  Nothing leaks between rows, so a difference you see has exactly one cause.

  READ DOWN A COLUMN for what each change does, ACROSS A ROW for the gate's cost.
  `--arms 4` drops row 3, `--arms 2` drops rows 2 and 3.

⭐ WHAT TO WATCH FOR IN THE BOTTOM ROW -- the defect it exists to remove is a
  SYSTEMATIC DRIFT, not noise. Pitch the hand through the horizontal, or yaw it
  edge-on, while holding a cube: in the TOP row the cube slides away from the
  palm as the hand turns (sink |r| = -0.807 on pitch, -0.656 on yaw); in the
  BOTTOM row it should stay put relative to the hand (-0.000 / 0.000, §16.14).
  ⚠ The bottom row is ~30-70% jitterier in p95. That is the trade, and it is the
  owner's call -- §16.5: "a systematic drift is the defect the operator actually
  reported; jitter is not."

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
FOUR independent `CubeState`s. **Every difference you see between the windows is
caused by the anchor or the gate and by nothing else.**

The windows are placed in a 2x2 grid automatically (`--gap`, `--vgap`,
`--scale`; use `--scale 0.7` if four windows do not fit).


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
import random
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
from Resources import palm_anchor as PAnc                      # noqa: E402
from Resources import palm_rotation as PRot                    # noqa: E402

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
ANCHOR_COLOR = (140, 255, 140)       # green: the B4 palm-anchor row
HORN_COLOR = (255, 200, 120)         # blue: the Horn-rotation row

ARC_SEGMENTS = 18
DISCARD_FLASH_FRAMES = 6             # how long a discard stays visible on screen

# Recordings live on the external drive, never beside the code (owner rule).
# ⚠ Moved off `Recordings_prediction_gate` on 2026-08-07: that DIRECTORY ENTRY
# went corrupt on the exFAT volume ("the file or directory is corrupted and
# unreadable" on any write, and one take vanished from its listing) while the
# rest of E: stayed perfectly writable. The files inside remained READABLE, so
# every take was copied out intact. If a capture root ever starts refusing
# writes, test the parent directories before blaming the drive -- it was one
# bad directory, not the volume.
CAPTURE_ROOT = r"E:\Python\Recordings for vision_pipeline\Recordings_anchor_study"


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
def draw_countdown(frame, remaining):
    """Big centred countdown. Nothing is recorded until it reaches zero, so the
    trackers (DR-1, DR-2, the fit windows) are warm before capture starts and
    the operator has time to get into position."""
    h, w = frame.shape[:2]
    n = int(math.ceil(remaining))
    txt = str(max(1, n))
    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 6.0, 12)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
    cv2.putText(frame, txt, ((w - tw) // 2, (h + th) // 2),
                cv2.FONT_HERSHEY_DUPLEX, 6.0, (80, 255, 255), 12, cv2.LINE_AA)
    msg = "get into position -- recording starts at 0"
    (mw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1)
    cv2.putText(frame, msg, ((w - mw) // 2, (h + th) // 2 + 44),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


def draw_hud(frame, title, subtitle, counters=None, holds=(), color=(255, 255, 255),
             timer=None):
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
    if timer is not None:
        txt = f"REC {timer:5.1f}s"
        (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.62, 2)
        cv2.circle(frame, (w - tw - 26, 22), 7, (60, 60, 255), -1)
        cv2.putText(frame, txt, (w - tw - 12, 28), cv2.FONT_HERSHEY_DUPLEX, 0.62,
                    (60, 60, 255), 2, cv2.LINE_AA)
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


# Local staging. ⚠⚠ THE OPERATOR'S EFFORT IS WRITTEN HERE FIRST, ALWAYS.
# N4: E: drops out several times per session. A preflight cannot prevent it --
# the drive can pass the check at launch and be gone 90 seconds later, which is
# exactly what happened on 2026-08-07 and cost a completed take. Staging locally
# and migrating afterwards makes a mid-session dropout survivable: the worst
# case becomes "the take is on C: and needs moving", never "the take is gone".
STAGING_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                            "vision_pipeline_staging")


def save_recording(records, args, width, height, counters):
    """Write the take LOCALLY first, then migrate to the capture root.

    ⚠ LANDMARKS FIRST, then meta -- the same rule RecordPerceptionSequence
    enforces: the JSONL is the irreplaceable part.

    ⚠ REAL wall-clock timestamps, never a synthesised 33 ms step. N17: takes
    that faked the step reported ~30.4 fps when the true rate was ~24, which
    made every real-time derivative wrong by ~25%. `tCapture` is perf_counter
    at grab time.

    ⚠ Files are COPIED to E:, never written in place. An in-place write to a
    drive that disappears mid-write TRUNCATES the destination -- that is how a
    meta.json was destroyed on 2026-08-06.
    """
    if not records:
        print("[record] No frames captured, nothing saved.")
        return None
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    name = f"{stamp}_{args.sequence}"
    span = (records[-1]["tCapture"] - records[0]["tCapture"]) / 1000.0
    meta = {
        "sequence": args.sequence,
        "note": args.note,
        "prompt": args.prompt,
        "countdown_s": args.countdown,
        "warmup_excluded": True,
        "analysis_trim": {"head_s": args.trim_head, "tail_s": args.trim_tail,
                          "why": "grab approach at the start, wind-down at the end -- "
                                 "real hand motion, but not the condition under test"},
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
        "arms": args.arms,
        "rotation_row3": args.rotation,
        "horn_on_141": bool(args.horn_on_141),
        # ⚠ THE BLIND KEY. Written here and NOWHERE else -- never printed to the
        # console -- so the operator can be asked which window they preferred
        # before anyone looks up which arm it was.
        "blind": (None if not getattr(args, "blind_map", None) else
                  {"A": args.blind_map["A"][0], "B": args.blind_map["B"][0],
                   "A_key": args.blind_map["A"][1],
                   "B_key": args.blind_map["B"][1]}),
        "rows": {"1": "14.1", "2": "14.1 + B7", "3": "armB", "4": "armB + B7",
                 "5": f"{'14.1' if args.horn_on_141 else 'armB'} + {args.rotation}",
                 "6": f"{'14.1' if args.horn_on_141 else 'armB'} + {args.rotation} + B7"},
        "bottom_row_anchor": ("arm_C" if args.arm_c else
                              ("palm_3d_native" if args.anchor_3d else "arm_B")),
        "palm_anchor": {"arm_B": "2D palm frame (origin=centroid, x=knuckle row), "
                                 "offset frozen in palm widths, scale=palm width px",
                        "scale_alpha": args.scale_alpha},
        "counters": counters,
        "contains": ("per-frame raw pixel+world landmarks, the resolved DR-1 label, "
                     "the gate's per-channel decision, and BOTH cube states -- so the "
                     "A/B can be replayed offline under any gate configuration"),
    }

    # --- 1. LOCAL, and this must not fail ---
    stage = os.path.join(STAGING_ROOT, name)
    os.makedirs(stage, exist_ok=True)
    with open(os.path.join(stage, "raw_landmarks.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + chr(10))
    with open(os.path.join(stage, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[record] {len(records)} frames ({meta['measured_fps']} fps) staged -> {stage}")

    # --- 2. migrate to the capture root, with retries ---
    import shutil
    dest = os.path.join(args.record_root, name)
    for attempt in range(6):
        try:
            os.makedirs(dest, exist_ok=True)
            for fn in ("raw_landmarks.jsonl", "meta.json"):
                shutil.copyfile(os.path.join(stage, fn), os.path.join(dest, fn))
            ok = all(os.path.getsize(os.path.join(dest, fn))
                     == os.path.getsize(os.path.join(stage, fn))
                     for fn in ("raw_landmarks.jsonl", "meta.json"))
            if ok:
                shutil.rmtree(stage, ignore_errors=True)
                print(f"[record] migrated -> {dest}")
                return dest
        except OSError as e:
            last = e
        time.sleep(2.0)
    print(f"[record] ⚠ COULD NOT REACH {args.record_root}")
    print(f"[record]   the take is SAFE at: {stage}")
    print("[record]   move it when the drive is back; nothing was lost.")
    return stage


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
    p.add_argument("--prompt", default="",
                   help="operator instruction drawn on screen for the whole take")
    p.add_argument("--countdown", type=float, default=3.0,
                   help="seconds of un-recorded warm-up before capture starts")
    # The operator always spends the opening seconds moving to grab the cube and
    # the closing seconds winding down. Recorded, but excluded from analysis by
    # every harness via meta.json -- the take stays raw, the window is documented.
    p.add_argument("--trim-head", type=float, default=10.0,
                   help="seconds to EXCLUDE FROM ANALYSIS at the start (grab approach)")
    p.add_argument("--trim-tail", type=float, default=5.0,
                   help="seconds to EXCLUDE FROM ANALYSIS at the end (wind-down)")
    p.add_argument("--scale", type=float, default=None,
                   help="display scale (default fits the row count on a 1080p screen)")
    p.add_argument("--gap", type=int, default=12, help="pixels between the windows")
    p.add_argument("--vgap", type=int, default=46,
                   help="vertical pitch allowance for the OS title bar")
    p.add_argument("--scale-alpha", type=float, default=PAnc.SCALE_ALPHA,
                   help="EMA on the 3D-native anchor's scale (only with --anchor-3d)")
    p.add_argument("--arm-c", action="store_true",
                   help="bottom row uses arm C (no scale term) -- measurably worse")
    # ⭐ §16.15: the rotation estimator, applied to ALL FOUR windows (it is
    # orthogonal to the anchor). "horn" cuts the held cube's worst orientation
    # step 39.94 -> 9.64 deg on pitch and 58.86 -> 8.40 at back-of-hand.
    # ⭐ §16.15. Rows 1-2 ALWAYS use the shipped Gram-Schmidt rotation; this
    # selects which least-squares variant ROW 3 uses, so the third row is a
    # clean one-variable change against row 2.
    p.add_argument("--rotation", choices=("horn", "horn-palm", "horn-ff"),
                   default="horn",
                   help="which rotation estimator row 3 uses "
                        "(horn = palm+tips grab-referenced, drift-free)")
    # ⭐⭐ 2026-08-17. BLIND A/B. Both of the owner's picks in the six-window
    # session (window 2, then window 6) were made KNOWING the layout, which is
    # exactly the confound B7's original park could not rule out either. This
    # shows TWO unlabelled windows, "A" and "B", in an order drawn from
    # `random.SystemRandom` per run. Both arms carry §14.1's anchor AND the B7
    # gate, so the ONLY difference is the rotation estimator.
    #
    # ⚠ The assignment is written to the take's meta.json and is DELIBERATELY
    # NOT PRINTED -- so the operator can be asked which they preferred before
    # anyone, including the analyst, looks it up. Run it several times: each run
    # re-randomises, and a preference is only worth believing across rounds.
    #
    # ⚠⚠ THE 2026-08-17 SERIES WAS CONFOUNDED AND THE FAULT WAS HERE, not in the
    # operator. A free per-run `SystemRandom` draw put one arm on "A" in 4 of 6
    # rounds; the operator answered A,B,A,B,A,B (the textbook guessing pattern),
    # and that alone reproduces the 5-1 result. **A BALANCED ASSIGNMENT MAKES
    # THAT IMPOSSIBLE**: with exactly half the rounds on each side, a perfectly
    # alternating answer scores exactly 50%. `--blind-series` therefore draws ONE
    # balanced permutation for the whole series and consumes it one round per
    # run, storing it in the capture root. Never go back to a free draw.
    p.add_argument("--blind", nargs="?", const="rotation", default=None,
                   choices=("rotation", "rotation-nogate", "gate"),
                   help="two unlabelled windows A/B. 'rotation' = §14.1+B7 vs "
                        "§14.1+<rotation>+B7 (isolates the estimator, gate in "
                        "BOTH arms); 'rotation-nogate' = §14.1 vs "
                        "§14.1+<rotation>, no gate anywhere -- ⭐ the pair that "
                        "matches what would actually ship now B7 is parked; "
                        "'gate' = §14.1+<rotation> vs §14.1+<rotation>+B7 "
                        "(isolates B7). Implies --arms 6 --horn-on-141")
    p.add_argument("--blind-series", default=None,
                   help="name of a balanced series; the permutation is drawn "
                        "once and consumed one round per run")
    p.add_argument("--blind-rounds", type=int, default=8,
                   help="rounds in the series, split exactly half/half")
    # ⭐ 2026-08-17. Arm B was rejected (owner's eye on the six-window session,
    # plus a still-hand regression on all four takes and a SINK metric it cannot
    # lose by construction -- analysis/b4_orbit_and_sink_audit.py). That left the
    # rotation candidate stranded on an anchor nobody will ship. This puts row 3
    # back on §14.1's anchor so row 1 -> row 3 is a one-variable ROTATION change
    # on the anchor that is actually staying.
    p.add_argument("--horn-on-141", action="store_true",
                   help="row 3 uses §14.1's anchor instead of arm B, so rows 1 "
                        "and 3 differ ONLY in the rotation estimator")
    p.add_argument("--anchor-3d", action="store_true",
                   help="bottom row uses the 3D-native PalmAnchor instead of arm B "
                        "(kept for reproducing the null result; arm B is better)")
    p.add_argument("--arms", type=int, default=6, choices=(2, 4, 6),
                   help="2 = §14.1 pair; 4 = + the arm B row; 6 = + the Horn row")
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
    if args.blind:
        # All six arms are still COMPUTED (the take stays fully analysable and
        # the two shown arms are ordinary members of it); only the DISPLAY is
        # reduced to two anonymous windows.
        args.arms, args.horn_on_141 = 6, True
    if args.scale is None:
        # 3 rows of 480 px plus title bars will not fit 1080p at 1.0.
        args.scale = 1.0 if args.blind else {2: 1.0, 4: 0.7, 6: 0.52}[args.arms]

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
    # Bottom row: the SAME two arms again, but with the cube riding the PALM
    # BLOCK instead of §14.1's 9 landmarks (B4). Separate CubeStates and
    # separate gates -- they must not share a frame of state with the top row.
    state_anch = LSD.CubeState(window_size=(width, height))
    state_anch_gated = LSD.CubeState(window_size=(width, height))
    # Row 3: identical inputs to row 2, different rotation estimator only.
    state_horn = LSD.CubeState(window_size=(width, height))
    state_horn_gated = LSD.CubeState(window_size=(width, height))
    # ⭐ ARM B -- §16.5's 2D formulation, the MEASURED WINNER (§16.14): it kills
    # the sink on every axis (yaw 0.000, pitch -0.000, depth -0.001, back 0.000)
    # against §14.1's -0.656 / -0.807 / -0.589 / -0.083. The 3D-native
    # `PalmAnchor` is NOT used here -- it scored pitch p95 27.80 / max 72.22
    # against arm B's 8.11 / 25.07, because it rides the 3D palm frame, which
    # degenerates exactly at edge-on.
    palm_anchor = (PAnc.Arm2D(use_scale=not args.arm_c) if not args.anchor_3d
                   else PAnc.PalmAnchor(scale_alpha=args.scale_alpha))
    # Row 3 only. Rows 1-2 keep the shipped Gram-Schmidt path untouched, so
    # row 3 vs row 2 is a ONE-VARIABLE change: the rotation estimator.
    horn = {"horn": PRot.Horn(PRot.PALM_AND_TIPS, "ref"),
            "horn-palm": PRot.Horn(PRot.PALM_LANDMARKS, "ref"),
            "horn-ff": PRot.Horn(PRot.PALM_AND_TIPS, "ff")}[args.rotation]
    gates = {h: CG.ConfirmationGate(lag=args.lag, reject_z=args.reject_z)
             for h in TRACKED_HANDS}
    gates_anch = {h: CG.ConfirmationGate(lag=args.lag, reject_z=args.reject_z)
                  for h in TRACKED_HANDS}
    flash = {h: {} for h in TRACKED_HANDS}
    flash_a = {h: {} for h in TRACKED_HANDS}
    seen_last = {h: False for h in TRACKED_HANDS}
    n_flag = n_disc = n_conf = 0

    _abn = "ARM C" if args.arm_c else ("PALM 3D" if args.anchor_3d else "ARM B")
    # ⚠ NOT "production" any more. Production moved to horn-palm on 2026-08-17;
    # row 1 keeps the OLD Gram-Schmidt rotation ON PURPOSE, because every row
    # below is measured against it. With --horn-on-141 it is window 5 that
    # matches production today.
    win_raw = "1 14.1 anchor + OLD Gram-Schmidt rotation, no gate (the baseline)"
    win_gated = f"2 14.1 + B7 gate (L={args.lag}, z={args.reject_z})"
    win_anch = f"3 {_abn} -- cube rides the palm's 2D frame, no gate"
    win_anch_gated = f"4 {_abn} + B7 gate"
    _hbn = "14.1" if args.horn_on_141 else _abn
    win_horn = f"5 {_hbn} + {args.rotation.upper()} rotation, no gate"
    win_horn_gated = f"6 {_hbn} + {args.rotation.upper()} + B7 gate"
    disp_w = int(width * args.scale)
    disp_h = int(height * args.scale)
    # ROWS = the change under test, COLUMNS = the gate. Reading down a column
    # shows what each change does; reading across a row shows the gate's cost.
    #   row 1  §14.1                      (production today)
    #   row 2  + ARM B anchor             (one variable vs row 1)
    #   row 3  + HORN rotation            (one variable vs row 2)
    # ⭐⭐ BLIND: draw the A/B assignment, then say NOTHING about it. Both arms
    # are §14.1 + B7; only the rotation estimator differs. The hand blocks come
    # from the SAME gated stream in both windows, so the hand itself cannot leak
    # which is which -- only the cube can.
    blind_map = None
    if args.blind:
        if args.blind == "rotation":
            _pair = [("shipped_gramschmidt", "cubes_gated"),
                     (args.rotation, "cubes_horn_gated")]
        elif args.blind == "rotation-nogate":
            # ⭐ Production today vs production with the estimator swapped, with
            # B7 in NEITHER arm -- the honest test now that B7 is parked.
            _pair = [("shipped_gramschmidt_nogate", "cubes_raw"),
                     (f"{args.rotation}_nogate", "cubes_horn")]
        else:                                     # 'gate': B7 on top of horn
            _pair = [(f"{args.rotation}_nogate", "cubes_horn"),
                     (f"{args.rotation}_plus_B7", "cubes_horn_gated")]
        # ⭐ Balanced series: draw the whole permutation once, consume one round
        # per run. `swap` says whether this round shows _pair reversed.
        if args.blind_series:
            _sf = os.path.join(args.record_root,
                               f"_blind_{args.blind_series}.json")
            try:
                _ser = json.load(open(_sf))
            except (OSError, ValueError):
                _n = max(2, args.blind_rounds)
                _order = [False] * (_n // 2) + [True] * (_n - _n // 2)
                random.SystemRandom().shuffle(_order)
                _ser = {"order": _order, "next": 0, "pair": args.blind}
            _i = _ser.get("next", 0)
            _swap = _ser["order"][_i % len(_ser["order"])]
            _ser["next"] = _i + 1
            try:
                os.makedirs(args.record_root, exist_ok=True)
                json.dump(_ser, open(_sf, "w"), indent=1)
            except OSError:
                pass                              # series file is a convenience
        else:
            _swap = random.SystemRandom().random() < 0.5
        if _swap:
            _pair.reverse()
        blind_map = {"A": _pair[0], "B": _pair[1]}
        args.blind_map = blind_map        # save_recording writes it to meta.json
        win_raw, win_gated = "A", "B"

    layout = [(win_raw, 0, 0), (win_gated, disp_w + args.gap, 0)]
    if args.arms >= 4 and not args.blind:
        y2 = disp_h + args.vgap
        layout += [(win_anch, 0, y2), (win_anch_gated, disp_w + args.gap, y2)]
    if args.arms >= 6 and not args.blind:
        y3 = 2 * (disp_h + args.vgap)
        layout += [(win_horn, 0, y3), (win_horn_gated, disp_w + args.gap, y3)]
    for name, x, y in layout:
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(name, disp_w, disp_h)
        cv2.moveWindow(name, x, y)
    windows = [n for n, _x, _y in layout]

    fps_hint = 1000.0 / 24.0
    lat_ms = args.lag * fps_hint
    timestamp_ms = 0
    print(f"[BlockPredictionDebug] Running -- L={args.lag} (~{lat_ms:.0f} ms hold "
          f"per flag). Press 'q' in either window to stop.")

    records = []
    frame_idx = -1
    t_first = None          # perf_counter ms of the first frame
    rec_start = None        # perf_counter ms when the countdown ended
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
            holds_a = set()
            data_anch = {h: None for h in TRACKED_HANDS}
            data_anch_gated = {h: None for h in TRACKED_HANDS}
            draw_anch, draw_anch_gated = {}, {}
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

                # --- the palm-anchor arms (B4) -------------------------------
                # Arm 3 consumes the SAME raw landmarks as arm 1; only the
                # anchor differs. Arm 4 consumes the SAME gated landmarks as
                # arm 2. So column = gate, row = anchor, and no arm shares
                # state with another.
                # ⚠ `>= 4`, NOT `== 4`: rows 2 AND 3 are fed from here. The
                # Horn row (2c44634) added `arms 6` without widening this
                # guard, so at the DEFAULT --arms 6 `data_anch` stayed all-None
                # and all four lower windows never acquired a cube -- owner
                # null on 4257 recorded frames, position frozen at spawn.
                # Caught by eye on 2026-08-17, not by any metric.
                if args.arms >= 4:
                    data_anch[label] = data_raw[label]
                    res_a = gates_anch[label].update(raw_state)
                    gpx_a, gw_a = apply_gate_to_landmarks(px, world, raw_state,
                                                          res_a["output"])
                    data_anch_gated[label] = {
                        "pixel_landmarks": gpx_a, "world_landmarks": gw_a,
                        "thumb_outward": outward}
                    if any(not res_a["valid"][c]
                           for c in ("pos_x", "pos_y", "scale", "quat")):
                        holds_a.add(label)
                    draw_anch[label] = (px, raw_state, {})
                    draw_anch_gated[label] = (gpx_a, res_a["output"],
                                              channel_status(res_a, flash_a[label]))

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
            if args.arms >= 4:
                LSD.update_hands(state_anch, data_anch, anchor=palm_anchor)
                LSD.update_hands(state_anch_gated, data_anch_gated,
                                 snap_blocked=holds_a, anchor=palm_anchor)
            if args.arms >= 6:
                if args.horn_on_141:
                    # ⭐ Row 3 becomes a one-variable change on ROW 1, not row 2:
                    # §14.1's anchor, §14.1's gate stream, ONLY the rotation
                    # estimator differs. Added 2026-08-17 because arm B was
                    # rejected (owner's eye + a still-hand regression on all
                    # four takes), which left Horn stranded on an anchor nobody
                    # will ship -- the orbit made it unjudgeable BY EYE even
                    # though the orientation metrics stayed clean.
                    LSD.update_hands(state_horn, data_raw, rotation=horn)
                    LSD.update_hands(state_horn_gated, data_gated,
                                     snap_blocked=holds, rotation=horn)
                else:
                    # ⭐ Identical inputs to row 2 -- same landmarks, same gate
                    # decisions, same anchor. ONLY the rotation estimator differs,
                    # so any visible difference is Horn and nothing else.
                    LSD.update_hands(state_horn, data_anch, anchor=palm_anchor,
                                     rotation=horn)
                    LSD.update_hands(state_horn_gated, data_anch_gated,
                                     snap_blocked=holds_a, anchor=palm_anchor,
                                     rotation=horn)

            if t_first is None:
                t_first = t_capture
            counting = (rec_start is None
                        and (t_capture - t_first) / 1000.0 < args.countdown)
            if rec_start is None and not counting:
                rec_start = t_capture
                print(f"[record] countdown finished -- capturing '{args.sequence}'")
            elapsed = None if rec_start is None else (t_capture - rec_start) / 1000.0

            if args.record and rec_start is not None:
                records.append({
                    "frame": frame_idx,
                    "tCapture": round(t_capture, 3),
                    "hands": rec_hands,
                    "s3_hold": sorted(holds),
                    "cubes_raw": cube_snapshot(state_raw),
                    "cubes_gated": cube_snapshot(state_gated),
                })
                if args.arms >= 4:
                    records[-1]["cubes_anchor"] = cube_snapshot(state_anch)
                    records[-1]["cubes_anchor_gated"] = cube_snapshot(state_anch_gated)
                    records[-1]["s3_hold_anchor"] = sorted(holds_a)
                if args.arms >= 6:
                    records[-1]["cubes_horn"] = cube_snapshot(state_horn)
                    records[-1]["cubes_horn_gated"] = cube_snapshot(state_horn_gated)

            frame_raw = frame.copy()
            frame_gated = frame.copy()
            if args.blind:
                # ⭐ Identical hand rendering in both windows, from the RAW
                # stream and with NO channel status: only the cube may differ.
                # ⚠⚠ The status colouring must NOT be drawn here. Amber/red mean
                # "B7 is withholding / just discarded", so on a gate-vs-no-gate
                # pair they would announce which window is the gated one and the
                # blind test would measure nothing but that tell.
                _by_key = {"cubes_raw": state_raw,
                           "cubes_gated": state_gated,
                           "cubes_horn": state_horn,
                           "cubes_horn_gated": state_horn_gated}
                for _fr, _letter in ((frame_raw, "A"), (frame_gated, "B")):
                    for label, (px, st, _status) in draw_raw.items():
                        draw_blocks(_fr, px, st, label)
                    LSD._draw_cubes(_fr, _by_key[blind_map[_letter][1]])
                    draw_hud(_fr, _letter, args.prompt or "", timer=elapsed)
            else:
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

                draw_hud(frame_raw, "1  BASELINE  (14.1 anchor, OLD rotation, no gate)",
                         args.prompt or "the reference every row below is measured against "
                                        "-- NOT production since 2026-08-17",
                         timer=elapsed)
            if args.prompt and not args.blind:
                h0, w0 = frame_raw.shape[:2]
                (tw, _), _ = cv2.getTextSize(args.prompt, cv2.FONT_HERSHEY_DUPLEX, 0.62, 2)
                cv2.rectangle(frame_raw, (0, h0 - 62), (w0, h0 - 26), (0, 0, 0), -1)
                cv2.putText(frame_raw, args.prompt, (max(8, (w0 - tw) // 2), h0 - 38),
                            cv2.FONT_HERSHEY_DUPLEX, 0.62, (80, 255, 255), 2, cv2.LINE_AA)
            if not args.blind:
                draw_hud(frame_gated,
                         f"2  GATED  (14.1 anchor + B7, L={args.lag}, z={args.reject_z}, ~{lat_ms:.0f} ms)",
                         "amber = channel PENDING (deciding)   red = frames DISCARDED",
                         counters=f"flag {n_flag}  discard {n_disc}  keep {n_conf}",
                         holds=holds, color=PENDING_COLOR)

            if counting:
                remaining = args.countdown - (t_capture - t_first) / 1000.0
                draw_countdown(frame_raw, remaining)
                draw_countdown(frame_gated, remaining)
            cv2.imshow(win_raw, frame_raw)
            cv2.imshow(win_gated, frame_gated)

            if args.arms >= 4 and not args.blind:
                frame_anch = frame.copy()
                frame_anch_gated = frame.copy()
                for label, (pxa, sta, _st) in draw_anch.items():
                    draw_blocks(frame_anch, pxa, sta, label)
                for label, (pxa, sta, status) in draw_anch_gated.items():
                    draw_blocks(frame_anch_gated, pxa, sta, label, status)
                LSD._draw_cubes(frame_anch, state_anch)
                LSD._draw_cubes(frame_anch_gated, state_anch_gated)
                draw_hud(frame_anch, f"3  {_abn}  (no gate)",
                         "sink killed on every axis; no fingertip can move the cube",
                         color=ANCHOR_COLOR)
                draw_hud(frame_anch_gated,
                         f"4  {_abn} + B7  (L={args.lag}, z={args.reject_z})",
                         "both changes at once",
                         holds=holds_a, color=ANCHOR_COLOR)
                if counting:
                    draw_countdown(frame_anch, args.countdown - (t_capture - t_first) / 1000.0)
                    draw_countdown(frame_anch_gated, args.countdown - (t_capture - t_first) / 1000.0)
                cv2.imshow(win_anch, frame_anch)
                cv2.imshow(win_anch_gated, frame_anch_gated)

            if args.arms >= 6 and not args.blind:
                frame_horn = frame.copy()
                frame_horn_gated = frame.copy()
                # The blocks come from whichever stream row 3 is riding, so the
                # hand drawn under the cube always matches the cube's anchor.
                _src, _src_g = ((draw_raw, draw_gated) if args.horn_on_141
                                else (draw_anch, draw_anch_gated))
                for label, (pxa, sta, _st) in _src.items():
                    draw_blocks(frame_horn, pxa, sta, label)
                for label, (pxa, sta, status) in _src_g.items():
                    draw_blocks(frame_horn_gated, pxa, sta, label, status)
                LSD._draw_cubes(frame_horn, state_horn)
                LSD._draw_cubes(frame_horn_gated, state_horn_gated)
                _rn = args.rotation.upper()
                _base = "§14.1" if args.horn_on_141 else _abn
                _note = ("SAME anchor as row 1 -- ONLY the rotation differs"
                         if args.horn_on_141
                         else "least-squares orientation: pitch 39.9->9.6 deg, back 58.9->8.4")
                draw_hud(frame_horn, f"5  {_base} + {_rn} rotation  (no gate)",
                         _note, color=HORN_COLOR)
                draw_hud(frame_horn_gated, f"6  {_base} + {_rn} + B7",
                         "rotation + gate",
                         holds=(holds if args.horn_on_141 else holds_a),
                         color=HORN_COLOR)
                if counting:
                    _rem = args.countdown - (t_capture - t_first) / 1000.0
                    draw_countdown(frame_horn, _rem)
                    draw_countdown(frame_horn_gated, _rem)
                cv2.imshow(win_horn, frame_horn)
                cv2.imshow(win_horn_gated, frame_horn_gated)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if any(cv2.getWindowProperty(w, cv2.WND_PROP_VISIBLE) < 1
                   for w in windows):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"[BlockPredictionDebug] Stopped. flags {n_flag}, discarded {n_disc}, "
              f"confirmed {n_conf}.")
        # ⚠ An arm that never acquires a cube produces a take that LOOKS
        # recorded and scores as all-NaN downstream. The `arms == 4` guard
        # above did exactly that to four arms across four takes before anyone
        # noticed. A take is only comparable if EVERY arm held the cube, so
        # say so here, at the moment it can still be re-recorded.
        if records:
            _arm_keys = [("1 raw", "cubes_raw"), ("2 gated", "cubes_gated")]
            if args.arms >= 4:
                _arm_keys += [("3 anchor", "cubes_anchor"),
                              ("4 anchor+gate", "cubes_anchor_gated")]
            if args.arms >= 6:
                _arm_keys += [("5 horn", "cubes_horn"),
                              ("6 horn+gate", "cubes_horn_gated")]
            _dead = []
            for _name, _key in _arm_keys:
                _held = sum(1 for r in records
                            if (r.get(_key) or {}).get("large", {}).get("owner"))
                print(f"[arms] {_name:<14} held the cube on {_held:5d} / "
                      f"{len(records)} frames")
                if _held == 0:
                    _dead.append(_name)
            if _dead:
                print(f"[arms] ⚠⚠ NEVER ACQUIRED: {', '.join(_dead)} -- this take "
                      f"CANNOT compare those arms. Re-record after fixing.")
        if args.record:
            save_recording(records, args, width, height,
                           {"flagged": n_flag, "discarded": n_disc, "confirmed": n_conf})


if __name__ == "__main__":
    main()
