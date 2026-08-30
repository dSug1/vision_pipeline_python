"""⭐ THE OBJECT'S ON-SCREEN FOOTPRINT — what the grab test is allowed to measure.

> **Owner, 2026-08-26:** *"the barycenter must be away less than half of the min
> dimension of the two natural axis of the cube's projection into the camera
> screen"*.

Until now the grab radius was `projected_size_of(cube) * GRAB_RADIUS_MULTIPLIER`,
and `projected_size_of` is the object's NOMINAL edge scaled by depth -- it does not
know the object's orientation. ⛔ So the radius said the same thing whether the
cube was square to the camera or standing on a corner, which is not what a person
sees and not what they aim at.

────────────────────────────────────────────────────────────────────────────────
⭐ WHAT "THE TWO NATURAL AXES OF THE PROJECTION" MEANS HERE

The object's vertices are projected exactly as the renderers project them, and the
footprint is the **axis-aligned bounding box of that projection**: a WIDTH along
screen-x and a HEIGHT along screen-y. `min(width, height)` is the narrower of the
two, and half of it is the radius.

⭐ Taking the MIN, not the max or the mean, is the strict reading and the right
one: it is the largest circle that fits inside the footprint's narrow direction,
so "close enough to grab" can never mean "outside the shape you can see".

⚠ A rotated cube's bounding box is LARGER than its edge, never smaller (a tilted
square needs more room, not less), so this is not automatically a tightening at
every pose -- it is orientation-CORRECT, which is a different thing. The
tightening comes from the multiplier, which the owner moved 1.5 -> 0.5.

────────────────────────────────────────────────────────────────────────────────
⛔ WHY THIS IS ITS OWN MODULE, AND STDLIB-ONLY

The two renderers are kept deliberately separate (`U6`): `CubeWindow` owns
production's, and `LiveSnapDebug` carries its own copy precisely so importing it
does not open a pygame window. Neither can host geometry the other needs.

⭐ So the maths lives here -- **stdlib only, numpy-free, no side effects**, the
same port contract as the estimator layer (`CONSTRAINTS` §2), and both renderers
pass their own mesh in. That is `N6` applied to the one thing the two tools must
agree on exactly: where an object can be picked up.

Golden vectors: `analysis/verify_object_extent.py`.
"""


def _quat_rotate_vector(q, v):
    """Rotate `v` by unit quaternion `q = (w, x, y, z)`.

    ⚠ Deliberately a local copy of the same six lines both renderers already
    carry, rather than an import of either: this module must not depend on a
    pygame-importing one, and the operation is a closed-form identity that cannot
    drift. The golden vectors pin it against both renderers' versions.
    """
    w, x, y, z = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def projected_extents(size_px, orientation, vertices, perspective_ratio):
    """(width_px, height_px) of the object's projected footprint.

    `size_px` is the object's on-screen extent at its current depth -- i.e. what
    `projected_size_of` already returns. `vertices` are the mesh's unit-cube
    vertices, in the same +/-1 convention both renderers use.

    ⚠ Returns `(size_px, size_px)` when the inputs cannot describe a shape, so a
    caller never gets a zero radius out of a malformed object and silently loses
    the ability to grab anything.
    """
    if not vertices or size_px is None or size_px <= 0.0:
        return (float(size_px or 0.0), float(size_px or 0.0))
    if orientation is None or len(orientation) != 4:
        return (float(size_px), float(size_px))

    half = size_px / 2.0
    camera_distance = size_px * perspective_ratio
    xs, ys = [], []
    for v in vertices:
        local = (v[0] * half, v[1] * half, v[2] * half)
        rx, ry, rz = _quat_rotate_vector(orientation, local)
        denom = camera_distance + rz
        # ⛔ A vertex at or behind the virtual camera has no meaningful projection.
        # Skip it rather than divide -- the remaining vertices still bound the
        # shape, and a sign flip here would silently mirror the footprint.
        if denom <= 1e-6:
            continue
        scale = camera_distance / denom
        xs.append(rx * scale)
        ys.append(ry * scale)
    if not xs:
        return (float(size_px), float(size_px))
    return (max(xs) - min(xs), max(ys) - min(ys))


def grab_extent(size_px, orientation, vertices, perspective_ratio):
    """The NARROWER of the projected footprint's two axes -- the grab dimension.

    ⭐ The owner's rule is half of this. Kept as its own function so the choice of
    `min` is named and testable rather than buried in a call site.
    """
    w, h = projected_extents(size_px, orientation, vertices, perspective_ratio)
    return min(w, h)
