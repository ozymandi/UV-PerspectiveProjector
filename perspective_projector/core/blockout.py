"""Geometry for building blockout objects from clicks on the photo.

Rays and points are numpy arrays in world space (Z up). Nothing here knows about Blender, so the
maths can be tested on its own; the Blender layer turns photo coordinates into rays and builds meshes.
"""

from __future__ import annotations

import numpy as np

SNAP_DEG = 5.0
UP = np.array([0.0, 0.0, 1.0])


class BlockoutError(ValueError):
    """A click or a set of clicks cannot produce the requested geometry."""


def _unit(v):
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise BlockoutError("zero-length direction")
    return v / n


def ray_plane(origin, direction, point, normal, max_distance=None):
    """Point where the ray hits the plane, or None when parallel, behind the origin or too far."""
    o, d = np.asarray(origin, float), _unit(direction)
    n = _unit(normal)
    den = float(np.dot(d, n))
    if abs(den) < 1e-9:
        return None
    t = float(np.dot(np.asarray(point, float) - o, n)) / den
    if t <= 1e-9 or (max_distance is not None and t > max_distance):
        return None
    return o + t * d


def closest_on_line(origin, direction, base, axis):
    """Point on the line ``base + s * axis`` closest to the ray ``origin + t * direction``.

    Used for the third click of Wall and Box: the height above a floor point (axis = Z) or the
    depth out of a facade (axis = its normal).
    """
    d, a = _unit(direction), _unit(axis)
    o, b = np.asarray(origin, float), np.asarray(base, float)
    w0 = b - o
    ad = float(np.dot(a, d))
    den = 1.0 - ad * ad
    if den < 1e-9:
        raise BlockoutError("the click ray runs along the line it should pick a point on")
    s = (ad * float(np.dot(d, w0)) - float(np.dot(a, w0))) / den
    return b + s * a


def snap_horizontal(direction, snap_deg=SNAP_DEG):
    """Horizontal unit direction; snapped to the nearest world X or Y axis when within ``snap_deg``."""
    d = np.asarray(direction, float).copy()
    d[2] = 0.0
    d = _unit(d)
    for axis in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])):
        c = float(np.dot(d, axis))
        if abs(c) >= np.cos(np.radians(snap_deg)):
            return axis * np.sign(c)
    return d


def axis_normal(normal):
    """The world axis (with sign) closest to a surface normal."""
    n = _unit(normal)
    i = int(np.argmax(np.abs(n)))
    out = np.zeros(3)
    out[i] = np.sign(n[i])
    return out


def is_horizontal(normal):
    return abs(float(_unit(normal)[2])) > 0.7


def base_frame(normal):
    """Two in-surface unit axes for an axis-aligned rectangle on a surface with this normal."""
    n = axis_normal(normal)
    if abs(n[2]) > 0.5:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    return _unit(np.cross(UP, n)), UP.copy()


def rect_from_corners(a, b, normal):
    """Four corners (loop order) of the axis-aligned rectangle with opposite corners a and b on a base."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u, v = base_frame(normal)
    du, dv = float(np.dot(b - a, u)), float(np.dot(b - a, v))
    if abs(du) < 1e-6 or abs(dv) < 1e-6:
        raise BlockoutError("the two corners must differ along both sides of the footprint")
    return [a, a + du * u, a + du * u + dv * v, a + dv * v]


def box_corners(rect, extrude):
    """Eight corners of a box from a base rectangle and an extrusion vector (bottom four, then top four)."""
    e = np.asarray(extrude, float)
    if float(np.linalg.norm(e)) < 1e-6:
        raise BlockoutError("the box has no height or depth")
    return [np.asarray(p, float) for p in rect] + [np.asarray(p, float) + e for p in rect]


def wall_corners(a, b, top, snap_deg=SNAP_DEG):
    """Vertical wall rectangle from two base points and a top point (already lifted onto the wall's
    vertical line). The base direction snaps to X / Y; the first base point stays fixed."""
    a, b, top = (np.asarray(p, float) for p in (a, b, top))
    d = snap_horizontal(b - a, snap_deg)
    length = float(np.dot(b - a, d))
    if abs(length) < 1e-6:
        raise BlockoutError("the wall's two base points are the same")
    z0 = min(a[2], b[2])
    z1 = float(top[2])
    if abs(z1 - z0) < 1e-6:
        raise BlockoutError("the wall has no height")
    p0 = np.array([a[0], a[1], z0])
    p1 = p0 + length * d
    return [p0, p1, np.array([p1[0], p1[1], z1]), np.array([p0[0], p0[1], z1])]


def reference_corner(origin, direction, distance):
    """Point at ``distance`` along the click ray: the vertical corner line passes through it."""
    if distance <= 0:
        raise BlockoutError("the assumed distance must be positive")
    return np.asarray(origin, float) + _unit(direction) * float(distance)


def reference_plane(corner, axis):
    """(point, normal) of the vertical reference plane through ``corner`` that runs along ``axis`` ('X' or 'Y')."""
    if axis == "X":
        return np.asarray(corner, float), np.array([0.0, 1.0, 0.0])
    if axis == "Y":
        return np.asarray(corner, float), np.array([1.0, 0.0, 0.0])
    raise BlockoutError(f"unknown reference axis {axis}")


def ceiling_extent(points):
    """(min x, min y, max x, max y) over world points of the existing blockout."""
    pts = np.asarray(points, float)
    if pts.size == 0:
        raise BlockoutError("there is no blockout to span: build a floor or walls first")
    lo, hi = pts[:, :2].min(axis=0), pts[:, :2].max(axis=0)
    if float(np.min(hi - lo)) < 1e-6:
        raise BlockoutError("the blockout covers no floor area yet: build a floor or a second wall first")
    return float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])
