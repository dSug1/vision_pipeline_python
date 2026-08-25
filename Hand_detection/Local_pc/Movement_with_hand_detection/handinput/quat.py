"""Quaternion helpers -- RE-EXPORTED from `palm_rotation`, never re-derived.

⚠⚠ THIS FILE DELIBERATELY CONTAINS NO MATHS. Hamilton products and conjugates
already exist three times in this codebase (`palm_rotation`, and a private copy in
each of the two tools) and the project's own rule N6 says a shared module is
IMPORTED, never copied. A fourth copy here would be the one that drifts -- and a
sign error in a conjugate is invisible until a cube rotates the wrong way.

⭐ `palm_rotation`'s helpers are underscore-private only because nothing outside
that module had needed them yet. Re-exporting under public names here is the
smallest possible change: one definition, two names.
"""
try:                                         # in-repo layout
    from Resources import palm_rotation as _PR
except ImportError:                          # standalone export, or Resources on sys.path
    import palm_rotation as _PR

IDENTITY = _PR._IDENTITY
multiply = _PR._qmul          # Hamilton product p*q
conjugate = _PR._qconj        # inverse of a unit quaternion
normalize = _PR._qnorm
angle_deg = _PR.quat_angle_deg


def delta(now, reference):
    """The world-frame rotation that takes `reference` to `now`.

    Exactly the expression both tools use for a grab-referenced cube
    (`hand_now * inverse(grab_hand_orientation)`), named once so a consumer of
    the input system does not have to know quaternion order conventions to use
    `rotation_delta`.
    """
    return multiply(now, conjugate(reference))
