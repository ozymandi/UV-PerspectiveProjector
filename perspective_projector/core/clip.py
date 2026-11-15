"""Polygon clipping used to measure how much of the photo a face covers.

Plain Python on (x, y) / (x, y, z) tuples so it can be tested without Blender.
"""

from __future__ import annotations


def _clip(points, inside, intersect):
    """One Sutherland-Hodgman pass: keep the part of a closed polygon where ``inside`` holds."""
    out = []
    n = len(points)
    for i in range(n):
        cur, nxt = points[i], points[(i + 1) % n]
        cur_in, nxt_in = inside(cur), inside(nxt)
        if cur_in:
            out.append(cur)
        if cur_in != nxt_in:
            out.append(intersect(cur, nxt))
    return out


def _lerp(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(len(a)))


def clip_near(points, near):
    """Keep the part of a camera-space polygon in front of the camera (z <= -near; camera looks down -Z)."""
    z0 = -near

    def inside(p):
        return p[2] <= z0

    def intersect(a, b):
        return _lerp(a, b, (z0 - a[2]) / (b[2] - a[2]))

    return _clip(list(points), inside, intersect)


def clip_rect(points, x0, y0, x1, y1):
    """Clip a 2D polygon to the axis-aligned rectangle [x0, x1] x [y0, y1]."""
    pts = list(points)
    for axis, bound, keep_below in ((0, x0, False), (0, x1, True), (1, y0, False), (1, y1, True)):
        if not pts:
            break

        def inside(p, axis=axis, bound=bound, keep_below=keep_below):
            return p[axis] <= bound if keep_below else p[axis] >= bound

        def intersect(a, b, axis=axis, bound=bound):
            return _lerp(a, b, (bound - a[axis]) / (b[axis] - a[axis]))

        pts = _clip(pts, inside, intersect)
    return pts


def area(points):
    """Absolute area of a 2D polygon (shoelace)."""
    a = 0.0
    n = len(points)
    for i in range(n):
        x0, y0 = points[i][0], points[i][1]
        x1, y1 = points[(i + 1) % n][0], points[(i + 1) % n][1]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0
