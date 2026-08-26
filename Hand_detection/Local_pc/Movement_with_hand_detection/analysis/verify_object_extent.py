"""GOLDEN VECTORS for `Resources/object_extent.py` — the grab footprint.

`CONSTRAINTS` §3: new shared geometry lands with its fixture in the same change,
not after. The properties below are the ones the grab rule actually leans on, and
two of them are things a plausible-looking implementation gets wrong.

⭐ The decisive check is the LAST one: this module's projection must agree with
what the renderers actually draw, to floating-point. If it ever disagrees, the
grab region stops matching the shape on screen and the operator is aiming at
something the code cannot see.

    .venv/Scripts/python.exe analysis/verify_object_extent.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Resources import object_extent as OE                      # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # pragma: no cover
    pass

V = ((-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
     (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0))
RATIO = 3.0
IDENT = (1.0, 0.0, 0.0, 0.0)

_fails = []


def check(name, ok, detail=""):
    print("  [%s] %-58s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        _fails.append(name)


def q_axis(ax, deg):
    a = math.radians(deg) / 2.0
    s = math.sin(a)
    n = math.sqrt(sum(c * c for c in ax)) or 1.0
    return (math.cos(a), ax[0] / n * s, ax[1] / n * s, ax[2] / n * s)


print("=" * 82)
print("object_extent — the grab footprint")
print("=" * 82)

w, h = OE.projected_extents(133.0, IDENT, V, RATIO)
check("a face-on cube projects SQUARE", abs(w - h) < 1e-9, "%.4f x %.4f" % (w, h))

# ⛔ The near face is closer to the virtual camera, so it projects LARGER than the
# nominal edge. A "footprint == size" assumption would under-size the grab region
# by 20% at every pose.
check("...and LARGER than the nominal edge (perspective, not orthographic)",
      w > 133.0 * 1.15, "%.1f px from a nominal 133" % w)

check("a 90 deg yaw returns the SAME footprint (symmetry of a cube)",
      abs(OE.grab_extent(133.0, q_axis((0, 1, 0), 90), V, RATIO)
          - OE.grab_extent(133.0, IDENT, V, RATIO)) < 1e-6)

# ⚠ A rotated cube needs MORE room, never less -- the intuition that turning an
# object "makes it smaller on screen" is foreshortening of a FACE, not of the
# silhouette, and confusing the two would shrink the grab region at exactly the
# poses where the object is largest.
worst = min(OE.grab_extent(133.0, q_axis(ax, d), V, RATIO)
            for ax in ((0, 1, 0), (1, 0, 0), (0, 0, 1), (1, 1, 0), (1, 1, 1))
            for d in range(0, 181, 15))
check("no orientation makes the footprint SMALLER than face-on",
      worst >= OE.grab_extent(133.0, IDENT, V, RATIO) - 1e-6,
      "worst %.1f vs face-on %.1f" % (worst, OE.grab_extent(133.0, IDENT, V, RATIO)))

check("grab_extent is the MIN of the two axes, not the max or the mean",
      abs(OE.grab_extent(133.0, q_axis((0, 1, 0), 45), V, RATIO)
          - min(OE.projected_extents(133.0, q_axis((0, 1, 0), 45), V, RATIO))) < 1e-12)

check("scales linearly with the object's projected size",
      abs(OE.grab_extent(266.0, q_axis((1, 1, 0), 33), V, RATIO)
          - 2.0 * OE.grab_extent(133.0, q_axis((1, 1, 0), 33), V, RATIO)) < 1e-9)

# degenerate inputs must never yield a zero radius -- that would silently make
# every object un-grabbable rather than fail loudly
check("a missing orientation falls back to the nominal size, not to zero",
      OE.grab_extent(133.0, None, V, RATIO) == 133.0)
check("an empty mesh falls back to the nominal size, not to zero",
      OE.grab_extent(133.0, IDENT, (), RATIO) == 133.0)

# ⭐⭐ THE ONE THAT MATTERS: agree with what the renderer DRAWS.
half = 133.0 / 2.0
cam = 133.0 * RATIO
q = q_axis((1, 1, 0), 37.0)


def renderer_project(v):
    """The exact five lines both renderers use, inlined here as the reference."""
    local = (v[0] * half, v[1] * half, v[2] * half)
    rx, ry, rz = OE._quat_rotate_vector(q, local)
    scale = cam / (cam + rz)
    return (rx * scale, ry * scale)


pts = [renderer_project(v) for v in V]
ew = max(p[0] for p in pts) - min(p[0] for p in pts)
eh = max(p[1] for p in pts) - min(p[1] for p in pts)
gw, gh = OE.projected_extents(133.0, q, V, RATIO)
check("matches the renderers' own projection, to floating point",
      abs(gw - ew) < 1e-12 and abs(gh - eh) < 1e-12,
      "%.9f / %.9f" % (abs(gw - ew), abs(gh - eh)))

print("=" * 82)
if _fails:
    print("%d CHECK(S) FAILED: %s" % (len(_fails), ", ".join(_fails)))
    sys.exit(1)
print("ALL CHECKS PASSED — the grab footprint is what the screen shows.")
