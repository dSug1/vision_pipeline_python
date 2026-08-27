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

# ⚠ Below this the palm/back sign is meaningless, so the branch cannot be trusted
# and neither can the correction. Reuses `edge_on_measure`, the codebase's ONE
# definition of edge-on -- a second threshold here would be a second definition.
EDGE_ON_FLOOR = 0.15


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
        self.gain = float(gain)
        self.name = "slantaxis_%s_g%.2f" % (self.horn.name, self.gain)
        # observability, for the panel and for the A/B -- never used in the maths
        self.last_sigma = 1.0
        self.last_authority = 0.0
        self.last_applied = 0.0
        self.frames_back_branch = 0
        self.frames_edge_on = 0

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
        return st

    def delta(self, state, px, world):
        q = self.horn.delta(state, px, world)
        self.last_applied = 0.0
        if q is None or state is None or self.gain <= 0.0:
            return q

        tr = state.get("slant")
        if tr is None:
            return q
        sigma, tilt, auth = tr.update(px)
        self.last_sigma, self.last_authority = sigma, auth
        if auth <= 0.0 or tilt is None:
            return q

        # ⛔ The fold. Off the grab's branch, the tilt INVERTS (46.6 vs Horn's 11.3),
        # so hand the frame back to Horn untouched rather than correct it backwards.
        sa = PG.signed_palm_area(px)
        if state.get("sign0") is not None and sa is not None:
            if (sa > 0.0) != state["sign0"]:
                self.frames_back_branch += 1
                return q
        # ⚠ ...and near edge-on the sign that selects the branch is itself
        # meaningless, so the guard above cannot be trusted either.
        if PG.edge_on_measure(px) < EDGE_ON_FLOOR:
            self.frames_edge_on += 1
            return q

        roll = knuckle_roll_deg(px)
        if roll is None or state.get("roll0") is None:
            return q
        # the two frames, reconciled -- see the module header
        target = (tilt + (roll - state["roll0"])) % 180.0

        amount = self.gain * auth
        self.last_applied = amount
        return steer_axis(q, target, amount)

    def step(self, state, px, world):
        return self.horn.step(state, px, world)
