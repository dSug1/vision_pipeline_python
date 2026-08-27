"""⭐⭐ ONE RULE FOR EVERY DRAWABLE IN THE GAME: sort by depth, paint far to near.

Owner, 2026-08-27: *"every object introduced in the game should be subject to
depth-ordered occlusion and should generate depth-ordered occlusion"*.

⭐ That is a statement about the RENDERER, not about cubes and hands, so it lives
in one shared module rather than being re-derived per object type. Anything that
can say how far away it is takes part; nothing needs to know what else exists.

    order([(depth_m, payload), ...])  ->  payloads, FARTHEST FIRST

Painter's algorithm, at the object level. Each object already sorts its own faces
internally (`_draw_object_3d`); this is the layer above that.

────────────────────────────────────────────────────────────────────────────────
⛔ WHAT AN UNKNOWN DEPTH DOES, AND WHY THAT DIRECTION

`None` sorts **FARTHEST** — drawn first, occluded by everything that knows where it
is. The opposite default would let an object of unknown position hide objects whose
position is known, which is the worse failure: a hand whose depth estimate has
dropped out would start covering the cube it is behind. ⭐ Unknown means "cannot
claim to be in front", never "assume in front".

⚠ Depths are METRES FROM THE CAMERA, so SMALLER IS NEARER. Every producer in this
pipeline already uses that convention (`cube.depth_m`, `palm_depth`), and getting
it backwards inverts the whole scene silently.

────────────────────────────────────────────────────────────────────────────────
⭐⭐ PER-LANDMARK DEPTH (owner, 2026-08-27), AND PER-SEGMENT BONES

The object-level rule above cannot express a gripping hand: some fingers are
genuinely in front of the cube and some behind. So the second half of this module
works at the LANDMARK and the BONE-SEGMENT level — `point_visible` and
`segment_runs` — and a bone that passes behind a cube is drawn as the pieces of it
that are still in front.

⚠ IT USES MEDIAPIPE'S PER-LANDMARK `z`, WHICH `T6` MEASURED AS UNRELIABLE. That
finding was about ORIENTATION: fitting a rotation to that coordinate reads a face-on
palm as 24.9 deg tilted. Depth ORDERING is a far coarser question — it asks only
"nearer or farther", against a cube typically 10-30 cm away — so the same error can
be tolerable here while being fatal there. ⛔ But it is the same coordinate, so if
the skeleton flickers in and out of a cube, THAT is the cause and not the
compositing.

⭐ The absolute depth of a landmark is built, never guessed:

    landmark_depth_m = hand_depth_m + world_z

`hand_depth_m` is the pipeline's own estimate (`palm_depth`) and `world_z` is
MediaPipe's offset from the hand's own origin, in metres, negative toward the
camera — the same "smaller is nearer" convention as everything else here.

Stdlib only, numpy-free, clock-free (`CONSTRAINTS` §2).
Golden vectors: `analysis/verify_depth_order.py`.
"""

# ⚠ Sorts after every real depth. Chosen rather than `float('inf')` so the value
# survives JSON round-trips in a recording without becoming `Infinity`.
UNKNOWN_DEPTH = 1.0e9


def depth_key(depth_m):
    """Sort key for one depth. `None`/NaN -> farthest."""
    if depth_m is None or depth_m != depth_m:
        return UNKNOWN_DEPTH
    return float(depth_m)


def order(items):
    """`[(depth_m, payload), ...]` -> payloads FARTHEST FIRST (largest depth first).

    ⭐ Stable, so objects at equal depth keep the order the caller supplied. Two
    cubes at exactly the reference depth must not swap places frame to frame — that
    would flicker, and it is the kind of thing that only shows up on screen.
    """
    return [p for _d, p in
            sorted(((depth_key(d), p) for d, p in items),
                   key=lambda dp: dp[0], reverse=True)]


def occludes(front_depth_m, back_depth_m):
    """True when `front` is NEARER than `back` and so may cover it.

    ⛔ An unknown depth occludes NOTHING — it cannot claim to be in front. That is
    the same rule as `order`'s, stated once more where a caller reaches for it
    directly instead of sorting a list.
    """
    return depth_key(front_depth_m) < depth_key(back_depth_m)


# ---------------------------------------------------------------------------
# ⭐⭐ PER-LANDMARK / PER-SEGMENT OCCLUSION
#
# An OCCLUDER is `(polygon, depth_m)`: a CONVEX screen polygon and how far away it
# is. A cube contributes its projected silhouette, which is convex because the cube
# is. ⚠ Convex is required -- `point_in_convex` is a same-side test and would
# silently accept the wrong region for a concave shape.
# ---------------------------------------------------------------------------

# How many pieces a bone is cut into when testing it against the occluders.
# ⚠ MEASURED AGAINST THE JOB, not chosen for elegance: a bone spans at most ~90 px
# on a 640x480 frame, so 16 pieces put the seam within ~6 px -- below what reads as a
# ragged edge at this scale. Raising it costs a linear amount of point-in-polygon
# work every frame, on every bone, in the live loop.
SEGMENT_STEPS = 16


def convex_hull(points):
    """Monotone-chain hull. Returns the hull in order; needs no numpy."""
    pts = sorted(set((float(x), float(y)) for x, y in points))
    if len(pts) <= 2:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) > 0:
                    break
                out.pop()
            out.append(p)
        return out

    return half(pts)[:-1] + half(reversed(pts))[:-1]


def point_in_convex(poly, x, y):
    """True if (x, y) is inside `poly`. Orientation-agnostic same-side test."""
    n = len(poly)
    if n < 3:
        return False
    pos = neg = False
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if cross > 1e-9:
            pos = True
        elif cross < -1e-9:
            neg = True
        if pos and neg:
            return False
    return True


def point_visible(x, y, depth_m, occluders):
    """False when some NEARER occluder covers this pixel.

    ⛔ An unknown landmark depth is hidden by every occluder that covers it --
    `occludes` decides, so the "unknown cannot claim to be in front" rule is stated
    once and reused rather than re-implemented here.
    """
    for poly, odepth in occluders:
        if occludes(odepth, depth_m) and point_in_convex(poly, x, y):
            return False
    return True


def segment_runs(p0, d0, p1, d1, occluders, steps=SEGMENT_STEPS):
    """The visible pieces of one bone, as `[(start_xy, end_xy), ...]`.

    ⭐ Depth is interpolated ALONG the bone, which is the whole point: a finger
    reaching past a cube has one end in front and the other behind, and the crossing
    happens somewhere in the middle. Returning runs rather than a boolean is what
    lets the caller draw that.

    ⚠ Adjacent visible pieces are MERGED before returning. Drawing 16 stubs where
    one line would do is both slower and visibly different -- round caps and
    anti-aliasing pile up at every seam.
    """
    if not occluders:
        return [(p0, p1)]
    x0, y0 = p0
    x1, y1 = p1
    runs = []
    start = None
    for i in range(steps):
        t0 = i / float(steps)
        t1 = (i + 1) / float(steps)
        tm = 0.5 * (t0 + t1)
        mx = x0 + (x1 - x0) * tm
        my = y0 + (y1 - y0) * tm
        md = None
        if d0 is not None and d1 is not None:
            md = d0 + (d1 - d0) * tm
        vis = point_visible(mx, my, md, occluders)
        if vis and start is None:
            start = t0
        elif not vis and start is not None:
            runs.append((start, t0))
            start = None
    if start is not None:
        runs.append((start, 1.0))
    return [((x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
             (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)) for a, b in runs]


def landmark_depths(world_landmarks, hand_depth_m):
    """`hand_depth_m + world_z` per landmark, or None when either input is missing.

    ⚠ Returns a LIST OF None rather than None when the hand depth is unknown, so a
    caller still gets one entry per landmark and the "unknown sorts farthest" rule
    applies per point instead of the hand vanishing.
    """
    n = len(world_landmarks) if world_landmarks else 0
    if not n:
        return []
    if hand_depth_m is None:
        return [None] * n
    out = []
    for w in world_landmarks:
        if w is None or len(w) < 3 or w[2] != w[2]:
            out.append(hand_depth_m)
        else:
            out.append(hand_depth_m + float(w[2]))
    return out
