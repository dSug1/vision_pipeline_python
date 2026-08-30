"""⭐ THE PER-FRAME ASSEMBLY STEP — the one function both tools call.

`mate_connector.py` is pure geometry and knows nothing about cubes, pixels or
depth. This module is the seam: it converts an object's stored state (a top-left
in PIXELS plus a metric `depth_m`) into world metres, runs the mate logic, and
converts the answer back. Queue rows `AS3`/`AS4`; design of record
`Claude/30_OBJECTS_3D/SPEC_ASSEMBLY_MATE_CONNECTORS.md`.

⛔ **Stdlib-only and numpy-free**, like everything it imports (`mate_connector`,
`palm_geometry`), so the port contract still holds and `N6` is satisfied: both
tools import THIS, neither carries a copy.

────────────────────────────────────────────────────────────────────────────────
⛔⛔ THE ORDER IS THE DESIGN, AND IT IS NOT INTERCHANGEABLE

    1. DESIRE    each object's pose from its OWN driver -- its hand, or its parent
    2. RESIDUAL  measured between the two DESIRED connector poses
    3. BREAK ?   over the release threshold for the dwell -> drop the mate
    4. ENFORCE   otherwise place the follower exactly on the mate

`resolve()` therefore takes each object's **UNCLAMPED, HAND-DRIVEN DESIRE**, not
the state the tool has already stored. Measuring on the enforced pose returns zero
forever and the mate becomes unbreakable -- see `mate_connector.residual`.

⚠ **The play-volume clamp is EXEMPT** (owner, 2026-08-28): it is a second driver,
and an object at a wall would otherwise break its mate for a reason no player can
see. So the caller passes the pre-clamp desire, and clamps afterwards.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ RE-ROOTING, WHICH IS WHAT MAKES "BOTH REMAIN GRABBABLE" TRUE

The structural PARENT (the bigger object) only says who stores the relative
transform. The DRIVER is whoever the hand has hold of, and the assembly is walked
outward from there -- so grabbing the small cube moves the big one. Without this,
grabbing a child moves nothing at all, because a child is by definition placed by
its parent.

⚠ **When BOTH are held, the structural parent wins** and the child follows. That
is Guiard's asymmetry, and it is also the only choice that cannot oscillate: two
independent drivers on one constraint have no fixed point. The pair is not stuck --
that is exactly the case where the residual grows and the mate BREAKS.
"""

from . import mate_connector as MC
from . import palm_geometry


# ⭐⭐ AS6 -- RELEASE AT MATE, AND RE-ARM ON EXIT.
#
# > **Owner, live 2026-08-28:** *"the smaller object must ungrab at snap otherwise
# > the snap breaks immediately."*
#
# ⛔ WHY IT BROKE. With a cube in each hand, BOTH are driven, so the residual is
# real -- and the hand that just placed the child keeps moving, because a person
# does not stop dead at the instant of contact. Within a few frames the residual
# passes the break threshold and the mate lets go. Releasing the child's grab at
# the mate removes one of the two drivers, and `AS3`'s rule then makes the mate
# unbreakable by the remaining one.
#
# ⭐ It is the STRONGER of the two fixes the spec had on the table. The other was
# to re-seat the grab baseline (spec §7) -- but that leaves TWO authorities on one
# transform and merely agrees them for an instant. Releasing removes one.
#
# ⛔⛔ AND IT CREATES A SECOND PROBLEM, WHICH IS THE MIDAS TOUCH. The hand is still
# exactly where the object is, so the next frame's proximity snap takes it back,
# it is driven again, and the mate breaks -- mate, release, re-grab, break, repeat.
# **Buxton's three-state model (1990) names the constraint exactly: you cannot go
# from State 2 (dragging) to State 2. The transition has to pass through State 1
# (tracking).** So there must be a state in which the hand is over the object and
# NOT holding it, and the system has to be able to get there.
#
# ⭐ THE MECHANISM IS POSITIONAL, NOT A TIMER AND NOT A GESTURE. After an automatic
# release the hand must LEAVE the object -- past a threshold wider than the one
# that grabs it -- before it may take it again. That is:
#   * the "leave the zone before it can re-trigger" answer the Midas-touch
#     literature settles on, and the asymmetric-threshold hysteresis the VR grasp
#     literature uses (grab at >= 0.75, release at <= 0.25, precisely so the state
#     cannot bounce);
#   * ⭐⭐ the shape THIS project already paid for twice: `U9`'s two hand-side
#     TRIGGERS were built and reverted before a POSITIONAL rule shipped, and
#     `METHOD` records the lesson as *"a trigger cannot enforce an invariant"*;
#   * self-clearing, so a player who simply stands still keeps their assembly --
#     which a cooldown timer would silently undo.
#
# ⚠ It needs NO new gesture, which matters: `4.4`'s hand-open release is still
# unbuilt and the owner has deliberately not built it.

# ⛔ FLOOR: strictly > 1.0, or the grab and re-arm thresholds coincide and the
# latch does nothing. At 1.5 the hand must get half again the grab radius away --
# about 30 px from the small cube at the reference depth, roughly three quarters
# of its own width, and far outside `F1`'s 1.5 mm fingertip noise floor.
# ⚠ Same 1.5 as `MATE_BREAK_FACTOR`, and deliberately a SEPARATE constant: they
# answer different questions and there is no reason they must move together.
REGRAB_RELEASE_FACTOR = 1.5

# The hand must stay outside for this long. ⭐ Two independent supports for 100 ms:
# `L1`'s MEASURED inter-frame gap is 48-64 ms, so this cannot be tripped by a
# single frame; and the VR grasp literature reports a pinch state bouncing until
# it was required to hold for **100 ms**, which "resulted in a much smoother user
# experience". A duration, not a frame count (`U8`).
REGRAB_DWELL_MS = MC.MATE_DWELL_MS


class RegrabLatch(object):
    """Which (object, hand) pairs may not re-grab yet, after an automatic release.

    ⭐ Per (object, OWNER), not per object: the OTHER hand may take it immediately,
    which is what makes a two-handed detach work the moment the mate exists. Only
    the hand that just let go has to step away first.
    """

    __slots__ = ("_blocked",)

    def __init__(self):
        self._blocked = {}          # (object, owner) -> ms the hand went outside

    def arm(self, object_name, owner_key):
        if owner_key is not None:
            self._blocked[(object_name, owner_key)] = None

    def blocked(self, object_name, owner_key):
        return (object_name, owner_key) in self._blocked

    def observe(self, object_name, owner_key, outside, now_ms,
                dwell_ms=REGRAB_DWELL_MS):
        """Feed this pair's 'the hand is clear of it' verdict. Returns True while
        the grab is still refused.

        ⚠ Coming back inside RESETS the dwell rather than banking it -- a hand
        that hovers in and out has not left, and treating it as though it had is
        how a latch becomes decorative.
        """
        key = (object_name, owner_key)
        if key not in self._blocked:
            return False
        if not outside:
            self._blocked[key] = None
            return True
        since = self._blocked[key]
        if since is None:
            self._blocked[key] = now_ms
            return True
        if now_ms - since >= dwell_ms:
            del self._blocked[key]
            return False
        return True

    def forget(self, object_name):
        for key in [k for k in self._blocked if k[0] == object_name]:
            del self._blocked[key]

    def clear(self):
        self._blocked.clear()


# ⭐⭐ AS7 -- THE MATE PREVIEW: a GHOST and a DROP LINE.
#
# > **Owner, after the second live run:** *"it is very difficult to judge the
# > relative positions of the objects on z axis and therefore to align them for
# > snap … draw the small object projected to the mate in translucent highlighted.
# > that will also help select which mate to choose."*
#
# ⛔ WHY DEPTH IS UNREADABLE HERE, AND IT IS NOT A DRAWING BUG. The play volume is
# 0.30-0.85 m, i.e. **personal space**, where Cutting & Vishton rank **occlusion**
# the strongest depth cue by a wide margin -- and `R1` already ships it. ⛔ But
# occlusion is SILENT until the two shapes overlap on screen, which during a
# face-to-face approach is not until they are nearly touching. **The strongest cue
# available is absent for exactly the phase that needs it**, leaving only relative
# size, which is confounded here because the two cubes are genuinely different
# sizes. There is no stereo. So the depth information has to be DRAWN.
#
# ⭐⭐ THE CANONICAL ANSWER IS A SHADOW/DROP LINE, and it comes from a MANIPULATION
# paper for exactly this reason: **Herndon et al., "Interactive Shadows" (UIST
# 1992)** introduced shadow widgets so that a user could position objects in 3D
# *with a 2D input device* -- which is this situation precisely, a hand whose z is
# estimated driving an object in a 3D scene. The gap between an object and its
# projection reads as depth where the object alone does not.
#
# ⭐ AND THE GHOST IS THE OTHER HALF, from a different tradition: the translucent
# **placement preview** that every building game and CAD placement tool draws. The
# two answer DIFFERENT questions and that is why both are built:
#
#     the GHOST      -> "where would it land, and turned which way?"
#     the DROP LINE  -> "how far is there still to go?"   <- the half z hides
#
# ⚠⚠ THE PREVIEW MUST APPEAR BEFORE THE MATE IS POSSIBLE, or it cannot guide you
# to it -- a preview that only shows once you have already succeeded is a report,
# not an aid. Hence its own, wider gates below.

# ⛔ FLOOR: strictly > 1.0, or the preview appears only once the mate is already
# available and guides nothing. At 3x the capture reach that is ~54 mm of approach
# for the two cubes, about one and a half small-cube widths.
# ⚠ Settle live with the capture radius; they are the same kind of number.
# ⭐ 3.0 -> 2.0 (owner, 2026-08-28: the preview radius is *"twice the radius for
# snap"*). The preview now reaches 2 x 72.2 = 144.4 mm.
PREVIEW_RADIUS_FACTOR = 2.0

# ⛔ CEILING: strictly < 90 deg. At 90 deg two outward normals are perpendicular
# and past it they point the same way -- the objects are back to back, not facing,
# and a ghost there would be noise. 75 deg leaves a wide approach cone while
# staying unambiguous.
PREVIEW_ANGLE_DEG = 75.0


class MatePreview(object):
    """Everything a renderer needs to draw one candidate mate. Display only.

    ⚠ Computed from the SAME poses and thresholds the predicate uses, never
    recomputed alongside them: a preview that disagrees with the rule it previews
    would be worse than no preview at all.
    """

    __slots__ = ("parent", "parent_connector", "child_connector",
                 "center_px", "depth_m", "orientation",
                 "from_px", "to_px", "gap_m", "deviation_deg", "score", "reachable")

    def __init__(self, parent, parent_connector, child_connector,
                 center_px, depth_m, orientation, from_px, to_px,
                 gap_m, deviation_deg, score, reachable):
        self.parent = parent
        self.parent_connector = parent_connector
        self.child_connector = child_connector
        # Where the child would be if it mated now -- the GHOST's pose.
        self.center_px = center_px
        self.depth_m = depth_m
        self.orientation = orientation
        # The DROP LINE: the child's connector, and the parent's it would meet.
        self.from_px = from_px
        self.to_px = to_px
        self.gap_m = gap_m
        self.deviation_deg = deviation_deg
        self.score = score
        # ⭐ True when the pair would mate at this instant, i.e. only the DWELL is
        # left. This is what separates "keep coming" from "hold still".
        self.reachable = reachable


class ObjectDesire(object):
    """One object's UNCLAMPED, hand-driven wish for this frame, in tool units.

    `center_px` is the object's centre on screen, `depth_m` how far away it wants
    to be, `nominal_size_px` its extent at the reference depth (never its projected
    extent -- `CONSTRAINTS` §7).
    """

    __slots__ = ("name", "nominal_size_px", "center_px", "depth_m", "orientation",
                 "connectors", "driven", "actual_center_px", "actual_depth_m")

    def __init__(self, name, nominal_size_px, center_px, depth_m, orientation,
                 connectors, driven=False,
                 actual_center_px=None, actual_depth_m=None):
        self.name = name
        self.nominal_size_px = float(nominal_size_px)
        self.center_px = center_px
        self.depth_m = depth_m
        self.orientation = orientation
        self.connectors = tuple(connectors or ())
        self.driven = bool(driven)
        # ⭐⭐ THE DESIRE AND THE ACTUAL POSE ARE BOTH NEEDED, AND THEY ARE USED FOR
        # DIFFERENT THINGS. `center_px`/`depth_m` above are the UNCLAMPED wish;
        # these two are where the object really ended up after the play-volume
        # clamp.
        #
        #   ENGAGE  reads the ACTUAL pose  -- a player aims at what is on screen
        #   BREAK   reads the DESIRE       -- so a wall cannot break a joint (§4.2)
        #   ENFORCE reads the ACTUAL pose  -- or a parent stopped at a wall would
        #                                     visibly shed its child
        #
        # ⚠ That asymmetry was found by the golden vectors, not by reasoning: an
        # earlier draft enforced from the desire and the child sailed on through
        # the wall while the parent stopped dead.
        self.actual_center_px = actual_center_px if actual_center_px is not None else center_px
        self.actual_depth_m = actual_depth_m if actual_depth_m is not None else depth_m


def half_extent_m(nominal_size_px, frame_size):
    """The object's REAL half-size in metres.

    ⭐ Depth-independent by construction: `nominal_size_px` is the extent at
    `REFERENCE_DEPTH_M`, so the real size is that projected back at the reference
    depth -- which is why an assembled pair keeps its proportions as it moves in Z.
    """
    f = palm_geometry.focal_px(frame_size)
    if not f:
        return None
    return (float(nominal_size_px) * palm_geometry.REFERENCE_DEPTH_M / f) / 2.0


def to_world(desire, frame_size, actual=False):
    """(x, y, z) in metres for an object's centre. Screen x right, y down, z away.

    `actual=True` returns where the object really is (post-clamp) rather than where
    its hand wanted it. See `ObjectDesire`'s note on which reader needs which.
    """
    center = desire.actual_center_px if actual else desire.center_px
    depth = desire.actual_depth_m if actual else desire.depth_m
    if center is None or depth is None:
        return None
    xy = palm_geometry.world_from_px(center[0], center[1], depth, frame_size)
    if xy is None:
        return None
    return (xy[0], xy[1], float(depth))


def to_screen(center_m, frame_size):
    """The inverse of `to_world` — (center_px, depth_m)."""
    depth = palm_geometry.clamp_depth(center_m[2])
    px = palm_geometry.px_from_world(center_m[0], center_m[1], center_m[2], frame_size)
    if px is None:
        return None
    return (px, depth)


def _poses_for(desire, frame_size, actual=False):
    """Every connector on one object, resolved into world metres."""
    half = half_extent_m(desire.nominal_size_px, frame_size)
    center = to_world(desire, frame_size, actual=actual)
    if half is None or center is None:
        return []
    return [MC.world_pose(c, center, desire.orientation, half)
            for c in desire.connectors]


def resolve(desires, assembly, frame_size, now_ms,
            angle_tol_deg=MC.MATE_ANGLE_TOL_DEG,
            break_factor=MC.MATE_BREAK_FACTOR,
            dwell_ms=MC.MATE_DWELL_MS):
    """Run one frame of assembly. Returns `(placements, events)`.

    `placements` maps an object name to `(center_px, depth_m, orientation)` for
    every object the mate MOVED. Objects not in it are untouched -- the caller
    keeps whatever its own hand logic decided.

    `events` is a list of `('mated'|'broke', parent, child)` for the caller to
    report; nothing here draws or logs.
    """
    by_name = {d.name: d for d in desires}
    # ⛔ TWO SETS OF POSES, AND SWAPPING THEM IS THE DEFECT THIS DESIGN IS ABOUT.
    wanted = {d.name: _poses_for(d, frame_size) for d in desires}           # break
    actual = {d.name: _poses_for(d, frame_size, actual=True) for d in desires}  # engage + enforce
    events = []
    candidates = set()
    previews = {}                                   # child name -> MatePreview

    # ── 2 + 3. RESIDUAL, then BREAK. Measured on the DESIRES, before anything is
    # enforced -- the whole reason this function takes desires at all.
    for child_name in list(assembly.links.keys()):
        link = assembly.links[child_name]
        pp = wanted.get(link.parent) or []
        cp = wanted.get(child_name) or []
        if link.parent_connector >= len(pp) or link.child_connector >= len(cp):
            continue
        # ⭐⭐ A RESIDUAL EXISTS ONLY WHEN BOTH OBJECTS HAVE THEIR OWN DRIVER, and
        # this line is what makes "one hand can never break a mate" STRUCTURAL
        # rather than merely likely. An undriven object's driver IS the mate, so it
        # cannot disagree with it; asking what it "wanted" independently is a
        # question with no answer, and answering it with its stored pose is how the
        # golden vectors caught a mate breaking against a play-volume WALL.
        both_driven = (by_name.get(link.parent) is not None
                       and by_name.get(child_name) is not None
                       and by_name[link.parent].driven and by_name[child_name].driven)
        over = both_driven and MC.should_break(
            pp[link.parent_connector], cp[link.child_connector],
            angle_tol_deg=angle_tol_deg, break_factor=break_factor)
        if assembly.offer_break(child_name, over, now_ms, dwell_ms=dwell_ms):
            events.append(("broke", link.parent, child_name))

    # ── 1 + the candidate search. Every connector pair on every pair of objects.
    # ⚠ O((objects x connectors)^2). Two objects with one connector each is four
    # tests a frame; a spatial index only earns its weight past ~50 objects, and
    # adding one now would be an optimisation with nothing to show for it.
    names = [d.name for d in desires]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = by_name[names[i]], by_name[names[j]]
            parent_name, child_name = MC.order_by_size(a.name, a.nominal_size_px,
                                                       b.name, b.nominal_size_px)
            pp, cp = actual.get(parent_name) or [], actual.get(child_name) or []
            for pi, p_pose in enumerate(pp):
                for ci, c_pose in enumerate(cp):
                    ok = MC.can_mate(p_pose, c_pose, angle_tol_deg=angle_tol_deg)
                    # ⛔⛔ AFTER A BREAK THIS PAIR MUST ACTUALLY PART BEFORE IT MAY
                    # RE-MATE. Without it an un-snap survives exactly one frame:
                    # breaking measures the two DESIRES diverging, never the
                    # objects separating, so they are still touching when the mate
                    # drops and `ok` is true again immediately. The object returns
                    # to being a FOLLOWER, whose depth its parent owns — which is
                    # why z looked dead after an un-snap (four live reports).
                    # ⚠ "Apart" uses the BREAK distance, not the capture distance:
                    # a pair that has only just left capture has not parted.
                    _apart = MC.separation_m(p_pose, c_pose) > \
                        (p_pose.radius + c_pose.radius) * break_factor
                    if assembly.cooling(parent_name, child_name, pi, ci,
                                        _apart, now_ms, dwell_ms=dwell_ms):
                        ok = False
                    if ok and child_name not in assembly.links:
                        candidates.add(parent_name)
                        candidates.add(child_name)
                    # ⭐⭐ AS7 -- the PREVIEW, on WIDER gates than the mate itself,
                    # because a preview that only appears once the mate is already
                    # possible guides nothing.
                    if child_name not in assembly.links \
                            and assembly.can_link(parent_name, child_name, pi, ci):
                        preview = _preview_for(
                            by_name[parent_name], by_name[child_name], pi, ci,
                            p_pose, c_pose, frame_size, angle_tol_deg, ok)
                        if preview is not None:
                            best = previews.get(child_name)
                            # ⭐ BUBBLE CURSOR: exactly one target is live, and it
                            # is the best-scoring one. Everything else is dimmed
                            # rather than drawn, so the choice is never ambiguous.
                            if best is None or preview.score < best.score:
                                previews[child_name] = preview
                    if assembly.offer(parent_name, child_name, pi, ci, ok, now_ms,
                                      dwell_ms=dwell_ms):
                        events.append(("mated", parent_name, child_name))

    # ── 4. ENFORCE, walking outward from the DRIVER (re-rooting).
    placements = {}
    for group in _groups(assembly, names):
        if len(group) < 2:
            continue
        driver = _driver_for(group, by_name, assembly)
        resolved = {driver: (to_world(by_name[driver], frame_size, actual=True),
                             by_name[driver].orientation)}
        for parent_name, child_name, link in _edges_from(driver, group, assembly):
            src, dst = (parent_name, child_name) if parent_name in resolved \
                else (child_name, parent_name)
            if dst in resolved or src not in resolved:
                continue
            src_center, src_quat = resolved[src]
            if src_center is None:
                continue
            src_conn_i = link.parent_connector if src == link.parent else link.child_connector
            dst_conn_i = link.child_connector if src == link.parent else link.parent_connector
            src_obj, dst_obj = by_name[src], by_name[dst]
            if src_conn_i >= len(src_obj.connectors) or dst_conn_i >= len(dst_obj.connectors):
                continue
            src_half = half_extent_m(src_obj.nominal_size_px, frame_size)
            dst_half = half_extent_m(dst_obj.nominal_size_px, frame_size)
            if src_half is None or dst_half is None:
                continue
            src_pose = MC.world_pose(src_obj.connectors[src_conn_i], src_center,
                                     src_quat, src_half)
            quat, center = MC.snap_pose(src_pose, dst_obj.connectors[dst_conn_i],
                                        dst_obj.orientation, dst_half)
            if center is None:
                continue
            resolved[dst] = (center, quat)
            screen = to_screen(center, frame_size)
            if screen is not None:
                placements[dst] = (screen[0], screen[1], quat)
    return (placements, events, candidates, previews)


def _preview_for(parent, child, parent_conn_i, child_conn_i,
                 parent_pose, child_pose, frame_size, angle_tol_deg, reachable):
    """One candidate's ghost pose and drop line, or None if it is not worth drawing.

    ⚠ The two gates are WIDER than the mate's own, on purpose (see this module's
    AS7 note): `PREVIEW_RADIUS_FACTOR` x the capture reach, and
    `PREVIEW_ANGLE_DEG` — which must stay under 90°, where two outward normals
    stop facing each other at all.
    """
    reach = parent_pose.radius + child_pose.radius
    gap = MC.separation_m(parent_pose, child_pose)
    dev = MC.facing_deviation_deg(parent_pose, child_pose)
    if reach <= 0.0 or gap > reach * PREVIEW_RADIUS_FACTOR or dev > PREVIEW_ANGLE_DEG:
        return None
    if not MC.is_outward(parent_pose, child_pose):
        return None

    child_half = half_extent_m(child.nominal_size_px, frame_size)
    if child_half is None:
        return None
    # ⭐ THE GHOST IS THE REAL SNAP POSE, from the very function that would place
    # it — not a lookalike. If the ghost and the landing ever disagreed, the aid
    # would be teaching the player something false.
    quat, center = MC.snap_pose(parent_pose, child.connectors[child_conn_i],
                                child.orientation, child_half)
    if center is None:
        return None
    screen = to_screen(center, frame_size)
    if screen is None:
        return None

    from_px = palm_geometry.px_from_world(child_pose.position[0], child_pose.position[1],
                                          child_pose.position[2], frame_size)
    to_px = palm_geometry.px_from_world(parent_pose.position[0], parent_pose.position[1],
                                        parent_pose.position[2], frame_size)
    return MatePreview(
        parent=parent.name, parent_connector=parent_conn_i,
        child_connector=child_conn_i,
        center_px=screen[0], depth_m=screen[1], orientation=quat,
        from_px=from_px, to_px=to_px, gap_m=gap, deviation_deg=dev,
        score=MC.mate_score(parent_pose, child_pose, angle_tol_deg=angle_tol_deg),
        reachable=bool(reachable))


def _groups(assembly, names):
    """Connected components, as lists of names."""
    seen, out = set(), []
    for name in names:
        if name in seen:
            continue
        group = [n for n in assembly.connected(name) if n in names]
        if not group:
            group = [name]
        seen.update(group)
        out.append(group)
    return out


def _driver_for(group, by_name, assembly):
    """⭐⭐ RE-ROOTING: whoever is HELD drives; ties go to the structural parent.

    ⚠ With two hands on one assembly there is no fixed point, so a tie must be
    broken deterministically or the pair would oscillate. Giving it to the parent
    is Guiard's asymmetry -- and that case is precisely the one where the residual
    grows until the mate BREAKS, which is the intended outcome, not a deadlock.
    """
    held = [n for n in group if by_name.get(n) and by_name[n].driven]
    if not held:
        return assembly.root_for(group[0])
    if len(held) == 1:
        return held[0]
    ranked = sorted(held, key=lambda n: len(assembly.ancestors(n)))
    return ranked[0]


def _edges_from(driver, group, assembly):
    """Every link in the group, ordered so each edge touches an already-placed node."""
    placed, edges, pending = {driver}, [], []
    for child_name in group:
        link = assembly.links.get(child_name)
        if link and link.parent in group:
            pending.append((link.parent, child_name, link))
    progress = True
    while pending and progress:
        progress = False
        for edge in list(pending):
            if edge[0] in placed or edge[1] in placed:
                edges.append(edge)
                placed.add(edge[0])
                placed.add(edge[1])
                pending.remove(edge)
                progress = True
    return edges


# ⭐⭐ WHERE OBJECTS START, AND IT IS NOT THE CENTRE OF THE WINDOW.
#
# ⛔⛔ BOTH CUBES USED TO START AT THE SAME POINT — interpenetrating, at the same
# depth. That was invisible while each carried a single `+X` connector, because two
# unrotated cubes could not mate at all. The moment `AS1` went to six faces it
# became: grab a cube, move it a little, and it snaps to the other one and is taken
# out of your hand by `AS6`. Measured from the real startup pose, an ordinary 72 px
# drag mated on frame 12. The owner reported it as **"I can't get the cube to move
# on the z axis"** — which is what it looks like from the outside, because the cube
# stops moving in EVERY axis and z is what they were testing.
#
# ⭐ THE SEPARATION IS DERIVED, NOT CHOSEN. Two objects must start further apart
# than the PREVIEW radius, or the scene opens already showing a ghost and the aid
# means nothing.
#
# ⚠⚠ RE-DERIVED 2026-08-28 when the owner made the two cubes THE SAME SIZE. The
# old value was computed against a 2:1 pair and **would have failed silently**:
# equal 72.2 mm cubes have equal 18.0 mm connector radii, so the capture reach goes
# 27.1 -> 36.1 mm and the preview reach 81.2 -> 108.3 mm, while the home gap
# SHRANK, because the smaller cube grew. At the old 160 mm the gap is 87.8 mm
# against a 108.3 mm preview -- **the scene would have opened showing a ghost.**
#
#     gap(D) = D - 36.1 - 36.1 mm      must exceed      3 x 36.1 = 108.3 mm
#     =>  D > 180.5 mm
#
# 220 mm leaves margin. ⚠ It still fits: at 640 px wide the two centres land 244 px
# apart at 198 and 442, and the play-area clamp allows 87..553.
# ⚠ In METRES, not pixels, so it means the same thing on any camera resolution --
# the same reason `U9`'s margin moved to metres.
# ⛔ IF THE OBJECT SIZES CHANGE AGAIN, RE-DERIVE THIS. `verify_home_cube.py`
# asserts the relationship against the tools' REAL sizes so it cannot rot quietly.
# ⚠⚠ RE-DERIVED AGAIN 2026-08-28, when the snap radius doubled. Capture reach went
# 36.1 -> 72.2 mm and the preview 108.3 -> 144.4 mm, so:
#     gap(D) = D - 36.1 - 36.1 mm   must exceed   144.4 mm   =>   D > 216.6 mm
# ⛔ The previous 220 mm cleared that by 3.4 mm -- true but far too close to call
# a margin. 260 mm gives 187.8 mm against 144.4 mm.
# ⚠ Still fits: at 640 px the centres land 288 px apart, at 176 and 464, and the
# play-area clamp allows 87..553.
# ⚠⚠ RE-DERIVED A THIRD TIME, 2026-08-28, when the snap radius went to 150 %.
# Capture reach 72.2 -> 108.3 mm and the preview 144.3 -> 216.5 mm, so:
#     gap(D) = D - 36.1 - 36.1 mm   must exceed   216.5 mm   =>   D > 288.7 mm
# ⛔ The previous 260 mm NO LONGER CLEARED IT -- the scene would have opened with a
# ghost already showing. 340 mm gives 267.8 mm against 216.5 mm.
# ⚠ It still fits, but the margin is now thin: at 640 px the centres land at 132
# and 508 px, against a play area of 87..553. A wider snap radius than this would
# start pushing the objects off the usable area at low camera resolutions.
HOME_SEPARATION_M = 0.340


def home_center_px(index, total, frame_size, separation_m=HOME_SEPARATION_M,
                   depth_m=None):
    """Where object `index` of `total` starts: laid out in a row about the centre.

    ⚠ Falls back to the plain centre for a single object, and if the frame size
    cannot give a focal length — an object with no home is worse than one that
    starts in the middle.
    """
    cx = frame_size[0] / 2.0
    cy = frame_size[1] / 2.0
    if total <= 1:
        return (cx, cy)
    f = palm_geometry.focal_px(frame_size)
    if not f:
        return (cx, cy)
    depth = palm_geometry.REFERENCE_DEPTH_M if depth_m is None else depth_m
    step_px = separation_m * f / depth
    span = step_px * (total - 1)
    return (cx - span / 2.0 + index * step_px, cy)


def project_vertices_px(cube, frame_size):
    """⭐⭐⭐ PROJECT AN OBJECT'S MESH THROUGH **THE SCENE CAMERA** — one projection
    for the whole scene, the same one the mate is solved in.

    Returns `[((px, py), world_z), ...]`, one entry per mesh vertex.

    ⛔⛔ WHAT THIS REPLACES, AND WHY IT WAS A DEFECT. Each object used to be drawn
    through its OWN virtual camera at `cam = 3 x its projected size`, centred on
    itself — while its CENTRE was placed by the linear pinhole `px_from_world`.
    **Two inconsistent projections for one scene.** Each object's faces were pulled
    inward by `s = cam/(cam+rz) = 6/7`, but the centre-to-centre distance stayed
    linear, so two objects whose faces COINCIDE in world space were drawn with a gap
    of `2 x half x (1 - s)`:

        predicted 11.4 px in x, measured 13.9 px including y, worst 18.4 px
        on an 80 px cube -- 23% of its width, and present even at 0 deg rotation

    The owner reported it as *"an offset and misalignment between the cubes' faces,
    as if the snap was not done properly on the centers of the faces"*, and it was
    not the snap: the mate is exact to **0.0000 mm** in world space every time.

    ⭐ The local camera also EXAGGERATED foreshortening: it applied a near/far ratio
    of **1.400** where the real camera at 0.50 m gives **1.156**. So the true
    projection is both consistent AND more physical -- objects still foreshorten,
    by the amount they actually should.

    ⚠ `CUBE_PERSPECTIVE_DISTANCE_RATIO`'s original purpose survives: it existed to
    avoid a 2026-08-01 morphing bug where a naive per-vertex scale could send the
    denominator negative. A real pinhole at the object's own depth cannot do that
    while the object is inside the play volume, because `depth - half_extent` is
    0.464 m at the near wall -- nowhere near zero.
    """
    pose = pose_of(cube, frame_size)
    if pose is None:
        return []
    return project_locals_px(pose, cube.mesh.vertices, frame_size)


def project_vertices_px_at(pose, cube, frame_size):
    """An object's mesh at a GIVEN pose — the ghost's case."""
    return project_locals_px(pose, cube.mesh.vertices, frame_size)


def pose_of(cube, frame_size, center_px=None, depth_m=None, orientation=None):
    """`(centre_m, orientation, half_extent_m)` for an object — or for a HYPOTHETICAL
    pose of it, which is what the ghost needs."""
    half = half_extent_m(cube.size, frame_size)
    if half is None:
        return None
    center = to_world(ObjectDesire("_", cube.size,
                                   center_px if center_px is not None else center_px_of(cube),
                                   cube.depth_m if depth_m is None else depth_m,
                                   cube.orientation, ()), frame_size, actual=True)
    if center is None:
        return None
    return (center, cube.orientation if orientation is None else orientation, half)


def project_locals_px(pose, locals_xyz, frame_size):
    """Project unit-mesh local points through the SCENE camera. `[((px,py), wz), ...]"""
    center, orientation, half = pose
    out = []
    for v in locals_xyz:
        off = MC.quat_rotate(orientation, MC._scale(v, half))
        wx, wy, wz = center[0] + off[0], center[1] + off[1], center[2] + off[2]
        px = palm_geometry.px_from_world(wx, wy, wz, frame_size)
        if px is None:
            return []
        out.append((px, wz))
    return out


def center_px_of(cube):
    """An object's centre on screen, from its stored top-left.

    ⛔ Uses `projected_size_px`, never `cube.size` — `CONSTRAINTS` §7. The stored
    `position` is a corner of the PROJECTED extent, so converting with the nominal
    size would put the centre in the wrong place as the object moves in depth.
    """
    size = palm_geometry.projected_size_px(cube.size, cube.depth_m)
    return (cube.position[0] + size / 2.0, cube.position[1] + size / 2.0)


def place_center(cube, center_px, frame_size, clamp=True):
    """Write a centre back onto an object, optionally clamped into the play volume.

    ⭐ The one copy of this conversion. Both tools had their own `set_target_center`
    and both may keep it; assembly writes through here so the two cannot disagree
    about where a mated object ended up (`N6`).

    ⛔⛔ `clamp=False` FOR A MATE-PLACED FOLLOWER, and it is not a loosening.
    A follower's position is DETERMINED by the mate; clamping it afterwards is a
    second authority silently overriding the constraint, and the faces then visibly
    fail to meet. Measured 2026-08-28: with the solved pose outside the play area
    the clamp displaced the follower by **87 px** while the mate itself was exact to
    0.0000 mm — the owner saw it as *"an offset and misalignment between the cubes'
    faces, as if the snap was not done properly"*.
    ⭐ It is the same rule §4.2 already states for the residual: the clamp is a
    SECOND DRIVER and must not be mistaken for the mate's intent.
    ⚠ The assembly stays reachable because the DRIVER is still clamped by its own
    hand logic, so a follower can only ever sit one object-extent beyond the line —
    and it is re-clamped the moment the mate breaks and it becomes its own object.
    """
    if clamp:
        cx, cy = palm_geometry.clamp_to_play_volume(
            center_px[0], center_px[1], cube.depth_m, cube.size, frame_size)
    else:
        cx, cy = center_px
    size = palm_geometry.projected_size_px(cube.size, cube.depth_m)
    cube.position = (cx - size / 2.0, cy - size / 2.0)


def step(cubes, assembly, frame_size, now_ms, desires=None,
         release=None, latch=None, **kw):
    """⭐ ONE FRAME OF ASSEMBLY, for a dict of duck-typed cubes. Mutates in place.

    This is the single entry point both tools call (`N6`), so production and the
    debug tool cannot drift on the most defect-prone logic in the feature.

    `desires` optionally maps a cube name to `{"center_px":…, "depth_m":…}` — the
    UNCLAMPED, hand-driven wish for this frame. ⛔ Pass it. Without it the residual
    is measured on the clamped state and the play-volume wall becomes a second
    driver that can break mates invisibly (spec §4.2).

    `release` is the tool's own `release_cube(name)`, and `latch` its
    `RegrabLatch`. ⭐ **AS6: on the frame a mate engages, the CHILD's grab is
    dropped and its hand is latched out** — otherwise two drivers keep fighting
    over one transform and the mate breaks within a few frames (owner, live
    2026-08-28). Pass both, or the mate will not survive a two-handed assembly.

    Returns the event list, for the caller to report if it wants to.
    """
    views = []
    for name, cube in cubes.items():
        want = (desires or {}).get(name) or {}
        views.append(ObjectDesire(
            name=name,
            nominal_size_px=cube.size,
            center_px=want.get("center_px") or center_px_of(cube),
            depth_m=want.get("depth_m", cube.depth_m),
            # Where it REALLY is, after the tool's own clamp ran.
            actual_center_px=center_px_of(cube),
            actual_depth_m=cube.depth_m,
            orientation=cube.orientation,
            connectors=getattr(cube, "connectors", ()),
            # "Driven" means a hand is moving it this frame. It is what re-rooting
            # keys on, and it is why grabbing the small cube moves the big one.
            driven=cube.owner is not None,
        ))

    placements, events, candidates, previews = resolve(views, assembly, frame_size,
                                                       now_ms, **kw)

    for name, (center_px, depth_m, orientation) in placements.items():
        cube = cubes[name]
        cube.depth_m = depth_m
        cube.orientation = orientation
        # ⛔ NOT CLAMPED -- see `place_center`. A follower is placed BY the mate;
        # clamping it here is a second authority overriding the constraint, and it
        # was measured displacing a perfectly solved mate by 87 px.
        place_center(cube, center_px, frame_size, clamp=False)

    # ⭐⭐ AS6 -- RELEASE AT MATE. The child is now driven by the mate, so the hand
    # must let go of it: two authorities on one transform is what broke the snap
    # live. ⛔ Read `cube.owner` BEFORE releasing -- the latch has to know which
    # hand to hold off, and `release_cube` clears it.
    for kind, parent_name, child_name in events:
        child = cubes.get(child_name)
        if kind == "mated" and child is not None:
            parent = cubes.get(parent_name)
            # ⭐⭐ SCOPED TO THE CASE THAT NEEDS IT (owner, 2026-08-28), and the
            # first version was universal. `AS3` already makes **one hand unable
            # to break a mate** -- a residual needs TWO independent drivers -- so
            # a one-handed mate has nothing to protect: the hand simply keeps the
            # object and drives the assembly with it. Releasing there was pure
            # cost, and the cost was severe:
            #
            #   re-arm distance  144 px / 130 mm      cube width        72 mm
            #   grab radius       96 px /  87 mm      centres when mated 72 mm
            #
            # ⛔ i.e. stepping off the child meant leaving the WHOLE assembly and
            # coming back -- and on return the NEAREST cube wins while the child
            # is still latched and the parent never was, so the hand re-took the
            # PARENT. Owner: *"when a cube is snapped, it is very difficult to
            # re-grab it."*
            #
            # ⚠ The two-handed case is untouched, and it is the one the release
            # was built for: both objects driven, the placing hand carries on
            # moving, and without the release the residual breaks the mate within
            # a few frames.
            both_driven = (child.owner is not None
                           and parent is not None and parent.owner is not None)
            if both_driven:
                owner = child.owner
                if release is not None:
                    release(child_name)
                if latch is not None:
                    latch.arm(child_name, owner)
        elif kind == "broke":
            # ⭐⭐ FLAG THE RE-SEAT HERE, ON THE BREAK ITSELF -- not from the role
            # change below. ⛔ `step` runs AFTER the hand loop, so a flag set from
            # the role recomputation arrives ONE FRAME LATE: the hand has already
            # driven the object from its stale anchor and the 18 cm jump has
            # already happened. Setting it on the event means the flag is true at
            # the START of the next frame, which is when the hand loop reads it.
            # ⛔⛔ ONLY THE FOLLOWER. Re-seating the DRIVER is not merely
            # unnecessary, it RATCHETS: the driver's depth was always its own, so
            # re-anchoring bakes the current offset in as a new zero and resets the
            # ratio to 1.0 — and doing that on every break ACCUMULATES.
            # ⚠ Measured live 2026-08-28 across three mate/break cycles: the parent
            # climbed **0.589 → 0.774 m** toward the far wall while its anchor sat
            # at 0.670, never released. The owner reported it as *"still a problem
            # to control the parent on z axis translation after un-snap"* — and it
            # was caused by the fix for the CHILD's jump, applied one object too
            # wide.
            # ⭐ `mate_role` still holds LAST frame's value here (the roles are
            # recomputed below), which is exactly what is needed: the follower is
            # the object whose depth the mate was owning.
            # ⛔⛔ NO WALL GATE HERE, AND THAT WAS TRIED AND REVERTED THE SAME DAY.
            # Skipping the re-seat when the object sits at a play-volume wall looks
            # protective and is the exact opposite: the re-seat is what walks the
            # object BACK TO ITS HAND (`A1`), so refusing it at a wall is refusing
            # the one thing that recovers from the wall.
            _obj = cubes.get(child_name)
            if _obj is not None and _obj.owner is not None \
                    and getattr(_obj, "mate_role", "") == "follower":
                _obj.rebaseline_depth = True
            _par = cubes.get(parent_name)
            if _par is not None and _par.owner is not None \
                    and getattr(_par, "mate_role", "") == "follower":
                # Re-rooting can make the structural PARENT the follower, so this
                # is not dead code — it is the same rule, applied by ROLE.
                _par.rebaseline_depth = True
            if latch is not None:
                # ⚠ Nothing to hold off once the mate is gone: the pair are two
                # free objects again, and a stale latch would refuse an ordinary
                # grab.
                latch.forget(child_name)

    # Display only (AS5). ⚠ Recomputed every frame from the live state rather than
    # toggled on events, so it cannot get stuck showing a mate that has gone.
    for name, cube in cubes.items():
        if name in assembly.links or assembly.children_of(name):
            cube.mate_state = "mated"
        elif name in candidates:
            cube.mate_state = "candidate"
        else:
            cube.mate_state = ""
        # ⭐ AS7: the ghost and drop line for this object, or None. Display only,
        # and rebuilt every frame from live state so it cannot get stuck showing a
        # candidate that has gone.
        cube.mate_preview = None if cube.mate_state == "mated" else previews.get(name)
        # ⭐ Display only: which end of a mate this object is this frame. `driver`
        # keeps its own pose; `follower` is placed BY the mate, so its depth and
        # position are not its own. Recomputed every frame from live state.
        _was_follower = getattr(cube, "mate_role", "") == "follower"
        cube.mate_role = ("follower" if name in placements
                          else ("driver" if (name in assembly.links
                                             or assembly.children_of(name))
                                else ""))
        # ⭐⭐ HANDING AN OBJECT BACK TO ITS HAND MUST BE CONTINUOUS IN Z.
        # ⛔ While an object is a FOLLOWER the mate owns its depth, and its grab
        # baseline goes stale -- it was captured before the mate ever moved it. The
        # moment the mate lets go, the hand's ratio drive resumes from that stale
        # anchor and the object TELEPORTS. Measured 2026-08-28: a child carried to
        # 0.680 m by its parent snapped back to **0.500 m the instant the mate
        # broke -- an 18 cm jump** (owner: *"the z position ... does not match with
        # the z position of the hand that grabbed it when it was a child"*).
        # ⭐ So flag it, and let the hand loop re-seat the baseline where the
        # capture code already lives. Same no-pop principle as the grab frame,
        # `D3`'s resync blend and `A1`'s walk: a transition never teleports.
        if _was_follower and cube.mate_role != "follower" and cube.owner is not None:
            cube.rebaseline_depth = True
    return events


ALL_SIX_FACES = ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
                 (0.0, 1.0, 0.0), (0.0, -1.0, 0.0),
                 (0.0, 0.0, 1.0), (0.0, 0.0, -1.0))


def cube_face_connectors(vertices, faces, face_normals=None,
                         which=ALL_SIX_FACES, roll_order=4):
    """Connectors at the centres of the named faces of a mesh.

    ⭐ `which` is a list of LOCAL outward normals to place a connector on.

    ⛔⛔ THE DEFAULT WAS `+X` ALONE AND THAT WAS UNREACHABLE — found live,
    2026-08-28, by the owner seeing no preview at all. Both cubes start unrotated,
    so two `+X` connectors point the SAME way: facing deviation **180°**, the worst
    value there is. Nothing could mate, and nothing could even be PREVIEWED, until
    one cube was turned a full half-turn — which is the hardest thing to ask of a
    hand carrying a 27° yaw lean and 25° of jitter.
    ⭐ **One connector per object also made the owner's own requirement
    untestable**: *"that will also help select which mate to choose if the small
    object can be mated to more than 1 mates"* — with one connector each there is
    exactly ONE possible pair, so there is never a choice to make.

    ⭐⭐ So the default is now ALL SIX FACES, and it pays three ways: any face mates
    any face, so an approach from any direction works; several candidates exist, so
    the bubble-cursor choice is real; and **six outward normals drawn on a cube ARE
    an orientation gizmo** — which is the first thing the owner asked for.

    ⚠ Cost is nil at this scale: 6 × 6 = 36 pair tests a frame for two objects.

    ⚠ Matching is by normal rather than by face index so it does not silently move
    if the mesh's face order ever changes.
    """
    out = []
    for target in which:
        for idx, face in enumerate(faces):
            n = face_normals[idx] if face_normals else face.normal
            if all(abs(n[k] - target[k]) < 1e-9 for k in range(3)):
                conn = MC.face_center_connector(
                    vertices, face.vertex_indices if hasattr(face, "vertex_indices") else face,
                    n, roll_order=roll_order,
                    name="%+.0f%+.0f%+.0f" % (n[0], n[1], n[2]))
                if conn is not None:
                    out.append(conn)
                break
    return tuple(out)
