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
⚠ THE GRANULARITY IS PER OBJECT, AND A HAND IS NOT REALLY ONE OBJECT

A gripping hand wraps a cube: some fingers are genuinely in front of it and some
behind. One depth per hand cannot express that, so a held cube either covers the
whole skeleton or none of it. ⭐ Per-landmark depth would fix it and MediaPipe's
per-landmark `z` is exactly the coordinate `T6` spent this project's time proving
untrustworthy — so it is deliberately NOT used here. This limit is honest and
recorded, not overlooked.

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
