"""⭐⭐ THE OWNER'S STRATEGY, BUILT WHOLE — regression fits + freeze-at-grab.

Owner, 2026-08-27: *"the open hand takes provide the regression fits, and we saw
that it improves vs Horn. On top of that, multiply by a matrix which is frozen at
the moment of grab which captures the fingers state at the grab."*

    HALF 1   sigma -> angle, FITTED from the six takes  (`palm_slant_table.py`)
    HALF 2   everything measured relative to a canonical FROZEN AT THE GRAB

⭐ Unlike `palm_slant_axis`, this is a WHOLE orientation estimator, not a
correction: Horn's answer is not used for the axis or the angle. All three degrees
of freedom come from PIXELS, with MediaPipe's world `z` never read:

    out-of-plane ANGLE   the fitted table, from sigma
    out-of-plane AXIS    `tilt`, the direction the palm did NOT foreshorten along
    ROLL                 the knuckle row 5->17, in-image (`t5j`'s depth-free method)

⛔⛔ THREE THINGS THE OFFLINE VALIDATION GOT FOR FREE AND A LIVE RUN DOES NOT.
They are the whole reason this file is longer than the formula:

1. **sigma_0 -- how turned the hand ALREADY was at the grab.** Offline that came
   from the take's declared angle. Live, nothing knows it. ⭐ Solved with a RUNNING
   FACE-ON REFERENCE: keep the frame with the largest `edge_on_measure` seen for
   this hand. Measured on the clean yaw take -- sigma against that frame is <= 0.98
   on 99.8% of frames, ~1.0 at the highest-`eo` frames and ~0.0 at the lowest. It
   self-calibrates within a session, so it is NOT a calibration step.
   ⚠ A hand never shown near face-on gives a poor reference, and the confidence
   below reports that rather than hiding it.

2. ⛔⛔ **THE COMPOSITION IS DIRECTION-BLIND AS WRITTEN.** `sigma` is an anisotropy
   RATIO, always <= 1, so `sigma_rel * sigma_0` can only ever get SMALLER -- i.e.
   the product can only ever say "turned further", never "turned back toward
   face-on". Every pair in the offline fit sat inside one branch and the metric
   compared |b - a0|, so the flaw could not surface there.
   ⭐ THE FIX KEEPS THE OWNER'S FORMULA AND TAKES THE MISSING SIGN FROM `tilt`:
   turning further compresses along the SAME direction as before, turning back
   EXPANDS along it, and those two produce major axes 90 deg apart. So

       same direction as the grab's tilt  ->  u = sigma_0 * sigma_rel
       perpendicular to it                ->  u = sigma_0 / sigma_rel

   which is the multiplicative composition the data kept (alpha = beta = 1), with
   the branch of it chosen by a measurement instead of assumed.

3. **The sign of the turn** -- left vs right about the tilt axis -- is the planar
   two-fold ambiguity and `sigma` cannot supply it. ⚠ Taken from Horn, which is a
   far weaker dependence than using Horn's magnitude or axis: only the SIGN is
   borrowed, and it is the one thing Horn gets right by construction.

⚠ EVERY NUMBER BEHIND THIS CAME FROM OPEN-HAND TAKES, AND THE GAME GRIPS. On the
owner's own grabbing session `sigma` moves 0.11 p95 per frame, and the fitted curve
is steepest exactly where sigma is highest. That is a live question this file exists
to answer, not one it answers.

Stdlib only, numpy-free, clock-free (`CONSTRAINTS` §2).
Golden vectors: `analysis/verify_palm_slant_pose.py`.
"""
import math

try:                                        # imported, never copied (N6)
    from . import palm_geometry as PG
    from . import palm_rotation as PR
    from . import palm_slant as PS
    from . import palm_slant_table as PT
except ImportError:                         # pragma: no cover - direct import
    import palm_geometry as PG
    import palm_rotation as PR
    import palm_slant as PS
    import palm_slant_table as PT

PALM = (0, 5, 9, 13, 17)
FINGERS = tuple(i for i in range(21) if i not in (1, 2, 3, 4))
FEATURE_SETS = {"palm": PALM, "fingers": FINGERS}

# ⛔⛔ A HARD SWITCH I BUILT, AND A DISCONTINUITY SOURCE IN ITS OWN RIGHT.
# Adopting a new face-on reference changes `sigma_abs`, `sigma_0` AND `tilt_abs` in a
# single frame, so the cube moves for a reason the hand did not supply. At 0.02 the
# margin was small enough that ordinary landmark noise kept re-adopting.
# ⚠ Raised so adoption is a real event, not a coin flip. It cannot be removed --
# without adoption the reference is whatever pose the grab happened at, which is the
# problem this mechanism exists to solve.
FACE_ON_MARGIN = 0.08

# ⛔ Below this the reference is not face-on enough for the table's zero to mean
# anything, and the estimator says so through `confidence` rather than guessing.
FACE_ON_MIN = 0.35

DEFAULT_BLEND = 0.0         # 0 = pure Horn. The rig's slider drives this.
BLEND = DEFAULT_BLEND       # live global, exactly the `palm_slant_axis.GAIN` idiom

# ⛔⛔ PARTIAL BLEND IS HARMFUL, AND THE MEASUREMENT IS BLUNT ABOUT IT: yaw lean
# reads 27.2 at blend 0, **53.9 at blend 0.5**, and 8.6 at blend 1.0. Slerping
# between two orientations that disagree lands on an axis WORSE THAN EITHER. So this
# is an all-or-nothing estimator, and the slider's middle is a trap rather than a
# tuning range. ⚠ Left reachable anyway: a control whose bad region is hidden
# teaches the wrong thing about where the limit is (the GRAB radius slider's rule).

# ⭐⭐ SMOOTHING, AND IT IS DELIBERATELY ON `u` AND NOT ON THE QUATERNION.
# `u` drives the OUT-OF-PLANE ANGLE only. Low-passing the finished orientation would
# lag ROLL as well -- and roll comes from the knuckle row, which is clean, needs no
# damping, and is the motion a hand feels most directly. Damping only the noisy
# channel is the whole point.
# ⚠ TIME-BASED, never per-frame (`L1`: a fixed per-frame factor's settling time
# moved with the ROOM LIGHTING, 111 ms at 48 ms/frame vs 149 ms at 64).
SMOOTH_TAU_MS = 0.0
SMOOTH_MAX_DT_MS = 200.0    # a long gap is a NEW pose, not a slow one


def _pts(px, ids):
    if not px or len(px) <= max(ids):
        return None
    out = []
    for i in ids:
        p = px[i]
        if p is None or len(p) < 2:
            return None
        out.append((float(p[0]), float(p[1])))
    return out


def knuckle_roll_deg(px):
    if not px or len(px) <= 17:
        return None
    return math.degrees(math.atan2(px[17][1] - px[5][1], px[17][0] - px[5][0]))


def lookup(table, axis, side, sigma):
    """Read the fitted curve. `side` is 'front' or 'back'; knots fall in sigma."""
    ks = table.get(axis, {}).get(side)
    if not ks or sigma is None or sigma != sigma:
        return None
    if sigma >= ks[0][0]:
        return ks[0][1]
    if sigma <= ks[-1][0]:
        return ks[-1][1]
    for (x1, y1), (x2, y2) in zip(ks, ks[1:]):
        if x2 <= sigma <= x1:
            t = 0.0 if abs(x1 - x2) < 1e-12 else (x1 - sigma) / (x1 - x2)
            return y1 + t * (y2 - y1)
    return ks[-1][1]


def angle_from(table, side, sigma, tilt_img):
    """Blend the yaw and pitch curves by which way the palm foreshortened.

    ⭐ `tilt_img` near 90 deg is a yaw-like compression, near 0/180 a pitch-like
    one -- measured on the takes (yaw holds read 75-102, pitch holds 151-177/7).
    `sin^2 + cos^2 = 1`, so the blend is smooth and the two pure cases are exact.
    ⛔ The two curves are NOT interchangeable: at a declared 90 the yaw hold reads
    sigma 0.238 and the pitch hold 0.341, because the hand is thicker one way than
    the other. Using one curve for both is the error this blend exists to avoid.
    """
    y = lookup(table, "yaw", side, sigma)
    p = lookup(table, "pitch", side, sigma)
    if y is None or p is None or tilt_img is None:
        return y if p is None else p
    s = math.sin(math.radians(tilt_img))
    return (s * s) * y + (1.0 - s * s) * p


def _quat_axis_angle(tilt_img_deg, ang_deg):
    a = math.radians(tilt_img_deg)
    h = math.radians(ang_deg) * 0.5
    s = math.sin(h)
    return PR._qnorm((math.cos(h), math.cos(a) * s, math.sin(a) * s, 0.0))


def _quat_roll(deg):
    h = math.radians(deg) * 0.5
    return (math.cos(h), 0.0, 0.0, math.sin(h))


class SlantPoseHorn:
    """The owner's strategy as a live estimator, blended against Horn by `BLEND`.

    ⛔ `BLEND = 0` returns Horn's quaternion as the SAME OBJECT -- bit-exact, the
    acceptance-gate pattern, so an A/B panel pinned at 0 is production itself.
    """

    def __init__(self, feature="palm", blend=DEFAULT_BLEND, table=None):
        self.feature = feature
        self.ids = FEATURE_SETS.get(feature, PALM)
        self.table = table if table is not None else PT.TABLES[feature]
        self.horn = PR.Horn(PR.PALM_LANDMARKS, "ref")
        self.blend = None if blend is None else float(blend)
        self._pinned = self.blend is not None
        self.last_sigma_abs = 1.0
        self.last_angle = 0.0
        self.last_confidence = 0.0

    @property
    def name(self):
        b = self.blend if self._pinned else BLEND
        return "slantpose_%s_b%.2f%s" % (self.feature, b, "" if self._pinned else "*")

    def freeze(self, px, world):
        st = self.horn.freeze(px, world)
        if st is None:
            return None
        pts = _pts(px, self.ids)
        if pts is None:
            return None
        eo = PG.edge_on_measure(px)
        st["pose"] = {
            # ⭐ THE RUNNING FACE-ON REFERENCE. Starts as the grab frame -- the best
            # guess available at that instant -- and is replaced whenever the hand is
            # seen more square to the camera. ⚠ It deliberately OUTLIVES nothing: it
            # is inside the per-grab state, so it dies with the hand (§16.15).
            "faceon": pts, "faceon_eo": eo,
            "grab": pts, "grab_roll": knuckle_roll_deg(px),
            # ⭐ The branch is defined BY THE GRAB, like every other per-grab
            # baseline here. `sign0` was referenced before it was ever set in the
            # first draft, which silently forced every frame onto the FRONT curve.
            "sign0": (PG.signed_palm_area(px) or 0.0) > 0.0,
            # ⚠ The smoother's memory belongs to THIS grab (§16.15).
            "u_s": None, "last_ms": None, "sign": 1.0, "sign_votes": 0,
        }
        return st

    def _absolute(self, pose, px):
        """(sigma_abs, tilt_abs) of this frame against the running face-on frame."""
        pts = _pts(px, self.ids)
        if pts is None:
            return None
        eo = PG.edge_on_measure(px)
        if eo > pose["faceon_eo"] + FACE_ON_MARGIN:
            # a better view of the same hand: adopt it, and re-express the grab
            pose["faceon"], pose["faceon_eo"] = pts, eo
        r = PS.affine_svd(pose["faceon"], pts)
        return r

    def delta(self, state, px, world, now_ms=None):
        q_horn = self.horn.delta(state, px, world)
        blend = BLEND if not self._pinned else self.blend
        self.last_confidence = 0.0
        if q_horn is None or state is None or blend <= 0.0:
            return q_horn
        pose = state.get("pose")
        if pose is None:
            return q_horn

        # ⚠ The reference must be face-on ENOUGH for the table's zero to mean zero.
        if pose["faceon_eo"] < FACE_ON_MIN:
            return q_horn

        cur = self._absolute(pose, px)
        grab = PS.affine_svd(pose["faceon"], pose["grab"])
        if cur is None or grab is None:
            return q_horn
        sigma_abs, tilt_abs = cur
        sigma0, tilt0 = grab
        self.last_sigma_abs = sigma_abs

        # HALF 2, with the missing direction supplied by tilt (see the header).
        rel = PS.affine_svd(pose["grab"], _pts(px, self.ids))
        if rel is not None and sigma0 > 1e-6:
            sigma_rel, tilt_rel = rel
            same = (tilt0 is None
                    or PS.tilt_delta(tilt_rel, tilt0) < 45.0)
            u = sigma0 * sigma_rel if same else min(1.0, sigma0 / max(sigma_rel, 1e-6))
        else:
            u = sigma_abs

        # ⭐ The low-pass, on the out-of-plane channel only.
        dt = None
        if now_ms is not None and pose.get("last_ms") is not None:
            dt = min(max(0.0, now_ms - pose["last_ms"]), SMOOTH_MAX_DT_MS)
        if now_ms is not None:
            pose["last_ms"] = now_ms
        if SMOOTH_TAU_MS > 0.0 and dt is not None and dt > 0.0 and pose["u_s"] is not None:
            a = 1.0 - math.exp(-dt / SMOOTH_TAU_MS)
            u = pose["u_s"] + a * (u - pose["u_s"])
        pose["u_s"] = u

        conf = PS.authority(u)
        self.last_confidence = conf
        if conf <= 0.0:
            return q_horn

        # front or back of the hand, from the cue that has always answered it
        sa = PG.signed_palm_area(px)
        side = "back" if (sa is not None and (sa > 0.0) != pose["sign0"]) else "front"

        ang = angle_from(self.table, side, u, tilt_abs)
        if ang is None:
            return q_horn
        self.last_angle = ang

        # ⚠ The SIGN of the turn is the two-fold ambiguity; only it is borrowed.
        # ⛔⛔ WITH HYSTERESIS, because a bare threshold here is the worst switch in
        # the file: flipping the sign REVERSES the rotation, so a single frame of
        # noise near the boundary sends the cube the other way and back. That is a
        # ~2x-angle jolt, not a small error, and it is a prime suspect for the p95
        # tail the owner felt as "discontinuities everywhere".
        # ⭐ A flip must clear 90 deg by a MARGIN and hold for two frames. Ambiguity
        # resolved by continuity is §1.3(b)'s remedy 1 and `DR-2` already ships the
        # same shape of guard.
        sign = pose.get("sign", 1.0)
        if q_horn is not None:
            n = math.hypot(q_horn[1], q_horn[2])
            if n > 1e-9:
                a = math.degrees(math.atan2(q_horn[2], q_horn[1]))
                d = abs(((tilt_abs - a + 180.0) % 360.0) - 180.0)
                want = -1.0 if d > 90.0 else 1.0
                if want != sign and (d > 105.0 or d < 75.0):
                    pose["sign_votes"] = pose.get("sign_votes", 0) + 1
                    if pose["sign_votes"] >= 2:
                        sign, pose["sign_votes"] = want, 0
                else:
                    pose["sign_votes"] = 0
        pose["sign"] = sign

        roll = knuckle_roll_deg(px)
        droll = 0.0
        if roll is not None and pose["grab_roll"] is not None:
            droll = ((roll - pose["grab_roll"] + 180.0) % 360.0) - 180.0

        q_abs = PR._qmul(_quat_roll(droll), _quat_axis_angle(tilt_abs, sign * ang))
        # ⚠ RECOMPUTED EVERY FRAME, NOT CACHED. The grab pose's own absolute
        # angle depends on the FACE-ON REFERENCE, and that reference IMPROVES during
        # a session -- so a `q_grab` frozen once goes stale the moment the operator
        # shows the camera a squarer palm, and the cube would jump at that instant.
        # ⛔ The first draft cached it, and also read a `pose["q_grab"]` key that
        # `freeze` never created: it raised KeyError on the first frame the
        # correction was actually reached, which is why nothing had exercised it.
        t0 = tilt0 if tilt0 is not None else tilt_abs
        ang0 = angle_from(self.table, side, sigma0, t0) or 0.0
        q_grab = _quat_axis_angle(t0, sign * ang0)

        # grab-relative, like every other orientation in this pipeline
        q_pose = PR._qnorm(PR._qmul(q_abs, PR._qconj(q_grab)))
        return _slerp(q_horn, q_pose, blend * conf)

    def step(self, state, px, world):
        return self.horn.step(state, px, world)


def _slerp(a, b, t):
    """Shortest-arc interpolation. ⚠ Local only because `palm_rotation` does not
    export one; the hemisphere flip is the part that must not be skipped."""
    d = sum(x * y for x, y in zip(a, b))
    if d < 0.0:
        b, d = tuple(-x for x in b), -d
    if d > 0.9995:
        return PR._qnorm(tuple(x + t * (y - x) for x, y in zip(a, b)))
    th = math.acos(max(-1.0, min(1.0, d)))
    s = math.sin(th)
    ka, kb = math.sin((1.0 - t) * th) / s, math.sin(t * th) / s
    return PR._qnorm(tuple(ka * x + kb * y for x, y in zip(a, b)))
