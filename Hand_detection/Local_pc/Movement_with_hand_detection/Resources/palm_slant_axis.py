"""⭐⭐ KEEP HORN'S ANGLE. TAKE THE AXIS FROM THE SLANT.

`T6`'s correction, and it is aimed at the half of the defect that `t5f` actually
measured:

    "ANGLE is broadly satisfied -- the cube turns about as far as the hand.
     AXIS is not: the residual tilt is what shows up as x/y mixing on screen."

⛔ So every design that inverts `sigma` into an ANGLE was aimed at the wrong half
-- and it is the half that needs the per-user hand-thickness table (`U12`), which
is what was blocking the row. **This needs no table at all.**

────────────────────────────────────────────────────────────────────────────────
⭐ WHY THE PROJECTED LONG AXIS *IS* THE ROTATION AXIS

Under orthography a plane foreshortens ALONG the turn, so whatever survives
uncompressed lies ALONG the axis it turned about:

    yaw   about vertical    -> width collapses  -> long axis vertical
    pitch about horizontal  -> length collapses -> long axis horizontal

`palm_slant.affine_svd` returns exactly that direction, from PIXELS, with no `z`.

⭐⭐ MEASURED, `analysis/t6_tilt_is_the_axis.py`, on `t5f`'s CLEAN yaw take, truth
= vertical from the recording instruction (never from an estimator, `B4`):

    turned      HORN axis err     TILT axis err
    20- 40         20.4                17.6
    40- 60         24.5                13.2
    60- 80         25.1                 6.7
    >=40, palm-facing   22.8           10.4     <- the show-stopper's own band

────────────────────────────────────────────────────────────────────────────────
⛔⛔ IT IS BRANCH-LIMITED, AND THE FALLBACK IS NOT OPTIONAL

Past the fold the feature INVERTS: back-facing frames score TILT 46.6 against
HORN 11.3. That is the planar two-fold ambiguity (Faugeras & Lustman 1988), and
an independent witness confirms the diagnosis -- `signed_palm_area`, read from
pixels and sharing no expression with either competitor, flips at exactly the
rotation where the tilt collapses (median 149 deg).

⭐ So the palm/back sign SELECTS, and on the back branch this module returns
Horn untouched. ⚠ The fold has now cost this row four separate wrong conclusions;
it is handled explicitly here rather than hoped away.

────────────────────────────────────────────────────────────────────────────────
⚠ TWO FRAMES, AND MIXING THEM IS THE BUG THAT NEARLY KILLED THE IDEA

`tilt` is a right-singular direction: an axis in the CANONICAL PALM's frame,
which is precisely what makes it roll-invariant. The cube's axis lives in the
IMAGE frame. The first run of the harness compared them directly, measured the
hand's ROLL, and reported the claim refuted. The palm's own in-image roll (the
knuckle row 5->17, `t5j`'s depth-free method) maps one to the other.

⛔⛔ REJECTED ONCE ALREADY, AND THE FIX IS IN THIS FILE. The first live take was
rejected on feel -- *"no consistency in the rotation axis, discontinuities
everywhere"* -- and the cause was two HARD GATES here, not the signal: 114 toggles
in one take, jolt p95 29.7 deg, per-frame axis jump 1.90x worse than Horn at p95
while the MEDIAN improved. They are now one continuous fade (`confidence()`).

⭐ GAIN 0 IS BIT-EXACT HORN -- the input quaternion is returned unchanged, not an
approximation of it. That is the `tip_trim` acceptance-gate pattern, and it is
what lets an A/B arm be honest.

Stdlib only, numpy-free, clock-free (`CONSTRAINTS` §2).
Golden vectors: `analysis/verify_palm_slant_axis.py`.
"""
import math

try:                                        # imported, never copied (N6)
    from . import palm_geometry as PG
    from . import palm_rotation as PR
    from . import palm_slant as PS
except ImportError:                         # pragma: no cover - direct import
    import palm_geometry as PG
    import palm_rotation as PR
    import palm_slant as PS

# ⛔ SHIPS AT 0 = OFF, matching production bit-for-bit. `F1`'s trim taught this the
# hard way: a module that defaults ON in the debug tool and OFF in production makes
# the two tools differ in ordinary use, which is the exact divergence `U6` keeps
# `parity_replay` around to catch. The rig turns it on; the module does not.
DEFAULT_GAIN = 0.0

# ⭐ The LIVE global the debug sliders drive, and ONLY they. An estimator built
# with `gain=None` follows this; one built with a number pins itself and ignores it.
# ⚠ Exactly the `trim_gain=None` idiom the `F1` rig already uses, for the same
# reason: a rig needs one panel pinned OFF and one panel swept, on one camera.
# ⛔ Production never constructs this class at all, so this global cannot reach it.
GAIN = DEFAULT_GAIN

# ⛔⛔ THESE REPLACED A HARD GATE, AND THE HARD GATE IS WHY THE FIRST LIVE TAKE
# WAS REJECTED. Owner, 2026-08-27: *"the feel is very bad. there is no consistency
# in the rotation axis, discontinuities everywhere"*. Measured on that take
# (`analysis/t6_discontinuity_census.py`): **114 gate toggles**, each switching the
# correction on or off WHOLE, jolt p95 **29.7 deg**, max 61.8 -- and the per-frame
# axis jump p95 went 21.4 -> 40.6, i.e. **1.90x worse** than shipped Horn.
#
# ⚠ The median IMPROVED (2.39 -> 2.03) while the p95 doubled. That is the profile
# that averages well and feels broken, and it is exactly what the sweep-based
# `wander` metric could not see: a smooth instructed sweep never makes a gate chatter.
#
# ⭐⭐ AND THE STRATEGY SPEC HAD ALREADY SAID SO: §1.3(a)'s rule is *"fade, do not
# gate"*. It was applied to `authority` and then ignored for these two, which is the
# whole defect.
#
# ⭐ ONE FADE NOW COVERS BOTH, and it is geometrically necessary rather than tuned:
# a hand can only cross from palm-facing to back-facing BY PASSING THROUGH EDGE-ON.
# So fading on `edge_on_measure` fades the branch transition too -- it is §1.3(b)'s
# remedy 1 ("the solution pair can only exchange through the degenerate zone") and
# §1.3(c)'s edge-on band, expressed as one continuous quantity instead of two
# switches. ⛔ No time constant is involved, so this costs NO lag (`L1`).
EDGE_FADE_ZERO = 0.15       # was the hard threshold; now where authority reaches 0
EDGE_FADE_FULL = 0.45       # ...and where it reaches 1

# ⚠ Kept as the name of the geometric floor, unchanged in value, because other
# code and the golden vectors refer to "the" edge-on threshold.
EDGE_ON_FLOOR = EDGE_FADE_ZERO

# ⛔⛔ THE FADE ABOVE WAS NOT ENOUGH, AND THE MEASUREMENT SAID SO PLAINLY.
# Replacing the two hard gates cut the toggle JOLT (p95 29.7 -> 15.2 deg, max 61.8
# -> 22.0) but barely moved the thing the owner actually feels: per-frame axis jump
# p95 40.6 -> 39.2, still **1.84x** shipped Horn. ⭐ So the gates were NOT the
# dominant cause; the TARGET ITSELF is noisy on a gripping hand -- tilt moves 7.8
# deg p95 frame to frame, sigma 0.11.
#
# ⭐⭐ WHAT IS SMOOTHED, AND WHY IT IS NOT `L1` ALL OVER AGAIN. The low-pass is on
# the CORRECTION -- a small angular offset applied to Horn's axis -- and NOT on the
# rotation. Horn still answers at full speed every frame, so the cube tracks the
# hand with no added lag; only the corrective nudge is damped. Lagging a nudge and
# lagging the motion are different costs, and only the second is what the owner
# called unbearable.
#
# ⚠ TIME-BASED, NOT PER-FRAME. `L1` measured a fixed per-frame factor's settling
# time moving with the ROOM LIGHTING (111 ms at 48 ms/frame, 149 ms at 64). A time
# constant does not care what the camera is doing.
SMOOTH_TAU_MS = 0.0         # 0 = off. Set by the debug slider; swept offline first.

# ⚠ A long gap is a NEW pose, not a slow one. Without this a 2-second dropout
# would apply a single enormous smoothing step and snap the correction on.
SMOOTH_MAX_DT_MS = 200.0


def knuckle_roll_deg(px):
    """The palm's IN-IMAGE roll from the knuckle row 5->17. Depth-free (`t5j`)."""
    if not px or len(px) <= 17:
        return None
    return math.degrees(math.atan2(px[17][1] - px[5][1], px[17][0] - px[5][0]))


def _axis_angle(q):
    w, x, y, z = q
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-9:
        return None
    w = -1.0 if w < -1.0 else (1.0 if w > 1.0 else w)
    return (x / n, y / n, z / n), 2.0 * math.acos(w)


def _quat(axis, ang):
    s = math.sin(ang * 0.5)
    return PR._qnorm((math.cos(ang * 0.5), axis[0] * s, axis[1] * s, axis[2] * s))


def rotate_axis_by(q, delta_deg):
    """Rotate `q`'s axis IN THE IMAGE PLANE by `delta_deg`. Angle untouched.

    ⭐ The primitive the smoother needs: `steer_axis` takes a FRACTION of the way to
    a target, which cannot express "apply the correction I damped last frame".
    """
    if q is None or delta_deg is None or delta_deg == 0.0:
        return q
    aa = _axis_angle(q)
    if aa is None:
        return q
    (nx, ny, nz), ang = aa
    r = math.hypot(nx, ny)
    if r < 1e-6:
        return q
    new = math.atan2(ny, nx) + math.radians(delta_deg)
    return _quat((r * math.cos(new), r * math.sin(new), nz), ang)


def steer_offset_deg(q, target_deg):
    """Signed degrees from `q`'s in-image axis to `target_deg`, in [-90, 90].

    ⛔ THE SIGN TRAP lives here now. `target_deg` is an AXIS (mod 180) with no
    direction; picking the far representative would flip the rotation axis and turn
    the cube BACKWARDS -- worse than the lean being corrected.
    """
    if q is None or target_deg is None:
        return None
    aa = _axis_angle(q)
    if aa is None:
        return None
    (nx, ny, _nz), _ang = aa
    if math.hypot(nx, ny) < 1e-6:
        return None
    cur = math.degrees(math.atan2(ny, nx))
    d = ((target_deg - cur + 180.0) % 360.0) - 180.0
    if d > 90.0:
        d -= 180.0
    elif d < -90.0:
        d += 180.0
    return d


def steer_axis(q, target_deg, amount):
    """Rotate `q`'s axis, IN THE IMAGE PLANE ONLY, toward `target_deg`. Angle kept.

    ⛔ THE SIGN TRAP. A rotation axis carries a direction, but `target_deg` is an
    AXIS (mod 180) and has none. Steering toward the wrong representative flips
    `n`, which with the angle unchanged turns the cube the WRONG WAY -- a far worse
    artefact than the lean being corrected. So the nearer representative is chosen
    explicitly, never assumed.

    ⚠ `z` is deliberately left alone. It is the component MediaPipe fabricates, and
    the measured claim covers the in-image direction only; damping `z` here would be
    an unmeasured second change riding along with a measured one.
    """
    if q is None or target_deg is None or amount <= 0.0:
        return q
    aa = _axis_angle(q)
    if aa is None:
        return q
    (nx, ny, nz), ang = aa
    r = math.hypot(nx, ny)
    if r < 1e-6:                    # axis points straight at the camera: no in-image
        return q                    # direction to steer, and no lean to fix
    cur = math.degrees(math.atan2(ny, nx))
    d = ((target_deg - cur + 180.0) % 360.0) - 180.0
    if d > 90.0:                    # pick the representative on the same side
        d -= 180.0
    elif d < -90.0:
        d += 180.0
    new = math.radians(cur + amount * d)
    return _quat((r * math.cos(new), r * math.sin(new), nz), ang)


class SlantAxisHorn:
    """Horn, with its axis steered by the slant. Same interface as `PR.Horn`.

    Drop-in for `LiveSnapDebug`'s per-arm estimator slot, so an A/B is one camera,
    one detection, one variable.
    """

    def __init__(self, indices=None, mode="ref", gain=DEFAULT_GAIN):
        self.horn = PR.Horn(PR.PALM_LANDMARKS if indices is None else indices, mode)
        # ⚠ None = follow the live module global; a number PINS this arm.
        self.gain = None if gain is None else float(gain)
        self._pinned = self.gain is not None
        # observability, for the panel and for the A/B -- never used in the maths
        self.last_sigma = 1.0
        self.last_authority = 0.0
        self.last_applied = 0.0
        self.last_confidence = 0.0
        self.frames_back_branch = 0
        self.frames_edge_on = 0

    @property
    def name(self):
        """⭐ Reports the EFFECTIVE gain, not the constructed one, so the debug
        panel's label tracks the slider instead of saying "live" forever. A panel
        whose label contradicts what it is doing is the complaint the `T6d` and
        ownership rigs each had to fix."""
        g = self.gain if self._pinned else GAIN
        return "slantaxis_%s_g%.2f%s" % (self.horn.name, g, "" if self._pinned else "*")

    def confidence(self, px, state):
        """0..1 — how far the correction may be trusted THIS frame, continuously.

        ⛔ Replaces two hard switches. Off-branch it is 0, but the hand cannot GET
        off-branch without passing through edge-on, where the fade has already
        brought it to 0 — so the transition is smooth rather than a 30 deg step.
        """
        if state is None:
            return 0.0
        sa = PG.signed_palm_area(px)
        if state.get("sign0") is not None and sa is not None:
            if (sa > 0.0) != state["sign0"]:
                self.frames_back_branch += 1
                return 0.0
        eo = PG.edge_on_measure(px)
        c = PS.smoothstep(eo, EDGE_FADE_ZERO, EDGE_FADE_FULL)
        if c < 1.0:
            self.frames_edge_on += 1
        return c

    def freeze(self, px, world):
        st = self.horn.freeze(px, world)
        if st is None:
            return None
        tr = PS.SlantTracker()
        if not tr.freeze(px):
            return None
        st["slant"] = tr
        st["roll0"] = knuckle_roll_deg(px)
        # ⭐ The branch is defined BY THE GRAB, like every other per-grab baseline in
        # this pipeline (`DepthRatioTracker`, `Horn(ref)`, `tip_trim`). A reference
        # outliving its hand is §16.15's rule.
        sa = PG.signed_palm_area(px)
        st["sign0"] = (sa > 0.0) if sa is not None else None
        # ⚠ The smoother's memory belongs to THIS grab, like every other per-grab
        # baseline here (§16.15). A correction carried over from a dead hand would
        # be applied to a pose that never produced it.
        st["applied_deg"] = 0.0
        st["last_ms"] = None
        return st

    def delta(self, state, px, world, now_ms=None):
        """⚠ `now_ms` is INJECTED, never read here -- the same contract `hand_state`
        states for itself. The module stays clock-free and a replay is deterministic,
        because recordings carry `tCapture`."""
        q = self.horn.delta(state, px, world)
        self.last_applied = 0.0
        self.last_confidence = 0.0
        gain = GAIN if self.gain is None else self.gain
        if q is None or state is None or gain <= 0.0:
            return q

        tr = state.get("slant")
        if tr is None:
            return q
        sigma, tilt, auth = tr.update(px)
        self.last_sigma, self.last_authority = sigma, auth
        if auth <= 0.0 or tilt is None:
            return q

        # ⛔ The fold, and the edge-on band, as ONE continuous fade rather than two
        # switches. Off the grab's branch the tilt INVERTS (46.6 vs Horn's 11.3), so
        # the correction must vanish there -- but it must vanish SMOOTHLY, which the
        # first version did not, and that is what the owner felt.
        conf = self.confidence(px, state)
        self.last_confidence = conf
        if conf <= 0.0:
            return q

        roll = knuckle_roll_deg(px)
        if roll is None or state.get("roll0") is None:
            return q
        # the two frames, reconciled -- see the module header
        target = (tilt + (roll - state["roll0"])) % 180.0

        want = steer_offset_deg(q, target)
        if want is None:
            return q
        want *= gain * auth * conf

        # ⭐ The low-pass, on the CORRECTION only. Horn's own answer is untouched.
        dt = None
        if now_ms is not None and state.get("last_ms") is not None:
            dt = min(max(0.0, now_ms - state["last_ms"]), SMOOTH_MAX_DT_MS)
        if now_ms is not None:
            state["last_ms"] = now_ms
        if SMOOTH_TAU_MS > 0.0 and dt is not None and dt > 0.0:
            a = 1.0 - math.exp(-dt / SMOOTH_TAU_MS)
            applied = state.get("applied_deg", 0.0)
            applied += a * (want - applied)
        else:
            # ⚠ No timestamp, or smoothing off: apply it straight. Harnesses that
            # predate `now_ms` therefore reproduce the ORIGINAL behaviour exactly,
            # rather than silently getting a different one.
            applied = want
        state["applied_deg"] = applied

        self.last_applied = applied
        return rotate_axis_by(q, applied)

    def step(self, state, px, world):
        return self.horn.step(state, px, world)
