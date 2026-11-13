"""Camera calibration from vanishing points (fSpy-style maths).

Conventions
-----------
* Image pixels: origin at the top-left corner, u to the right, v down.
* Camera space (Blender): +X right, +Y up, looking down -Z.
* World: Z up, ground is the XY plane (z = 0).
* A vanishing point (VP) is homogeneous ``(u, v, w)`` in pixels; ``w == 0`` means
  the VP is at infinity in image direction ``(u, v)``.
* ``M`` is the 3x3 matrix whose columns are the world X, Y, Z axes expressed in
  camera space (world -> camera rotation). The camera's rotation in the world
  (what Blender stores on the camera object) is ``M.T``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AXES = ("X", "Y", "Z")

# A VP farther than this many image diagonals from the centre is treated as infinite.
INFINITE_VP_DIAGONALS = 100.0

# 35 mm film diagonal, used to convert a 35 mm-equivalent focal length to pixels.
FILM_DIAGONAL_MM = 43.2666


class CalibrationError(ValueError):
    """Raised when inputs cannot produce a camera. ``pair`` names the offending line pair (0/1) if any."""

    def __init__(self, message: str, pair: int | None = None):
        super().__init__(message)
        self.pair = pair


@dataclass
class Solution:
    focal_px: float
    rotation: np.ndarray  # M: columns = world axes in camera space
    principal_point: np.ndarray  # (cx, cy) pixels
    width: int
    height: int
    focal_source: str = "vanishing points"  # or "given"

    @property
    def camera_rotation(self) -> np.ndarray:
        """Camera-to-world rotation (Blender camera object rotation)."""
        return self.rotation.T

    def lens_mm(self, sensor_mm: float = 36.0) -> float:
        """Focal length in mm for a sensor of ``sensor_mm`` along the image's longer side."""
        return self.focal_px * sensor_mm / max(self.width, self.height)


# ---------------------------------------------------------------- basic helpers


def _normalize(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n < 1e-12:
        raise CalibrationError("zero-length vector")
    return v / n


def line_through(p, q):
    """Homogeneous image line through pixel points p and q."""
    p = np.array([p[0], p[1], 1.0])
    q = np.array([q[0], q[1], 1.0])
    if np.linalg.norm(p - q) < 1e-9:
        raise CalibrationError("line has zero length")
    return np.cross(p, q)


def vp_from_lines(line_a, line_b, diagonal: float, pair: int | None = None):
    """Homogeneous VP (u, v, w) from two segments ``((x0, y0), (x1, y1))``.

    Returns w == 0 when the segments are parallel or the VP is so far away that it
    is numerically infinite.
    """
    try:
        la = line_through(*line_a)
        lb = line_through(*line_b)
    except CalibrationError as exc:
        raise CalibrationError(str(exc), pair) from None
    vp = np.cross(la, lb)
    if np.linalg.norm(vp) < 1e-12:
        raise CalibrationError("the two lines are identical", pair)
    return normalize_vp(vp, diagonal)


def normalize_vp(vp, diagonal: float):
    """Scale a homogeneous VP to w = 1 (finite) or w = 0 with unit direction (infinite)."""
    u, v, w = (float(x) for x in vp)
    if abs(w) > 1e-12 and np.hypot(u / w, v / w) < INFINITE_VP_DIAGONALS * diagonal:
        return np.array([u / w, v / w, 1.0])
    d = _normalize([u, v])
    return np.array([d[0], d[1], 0.0])


def _centered(vp, pp):
    """VP in centred, y-up image coordinates (x, y, w)."""
    u, v, w = vp
    return np.array([u - pp[0] * w, -(v - pp[1] * w), w])


def focal_from_vps(vp1, vp2, pp, pair: int | None = None) -> float:
    """Focal length (pixels) from two orthogonal finite VPs."""
    a = _centered(vp1, pp)
    b = _centered(vp2, pp)
    if a[2] == 0 or b[2] == 0:
        raise CalibrationError("a vanishing point is at infinity; enter the focal length", pair)
    f2 = -(a[0] * b[0] + a[1] * b[1])
    if f2 <= 0:
        raise CalibrationError("vanishing points are on the same side of the image centre", pair)
    return float(np.sqrt(f2))


def direction_from_vp(vp, pp, f) -> np.ndarray:
    """Camera-space unit direction pointing towards the VP."""
    x, y, w = _centered(vp, pp)
    return _normalize([x, y, -f * w])


def focal_from_35mm(f35: float, width: int, height: int) -> float:
    """Pixels focal length from a 35 mm-equivalent focal (diagonal-based, CIPA)."""
    return f35 * float(np.hypot(width, height)) / FILM_DIAGONAL_MM


# ---------------------------------------------------------------- rotation


def _third_axis(axes, dirs):
    """Return dict axis -> direction with the missing axis filled for a right-handed frame."""
    d = dict(zip(axes, dirs))
    missing = [a for a in AXES if a not in d][0]
    if missing == "Z":
        d["Z"] = np.cross(d["X"], d["Y"])
    elif missing == "Y":
        d["Y"] = np.cross(d["Z"], d["X"])
    else:
        d["X"] = np.cross(d["Y"], d["Z"])
    return d


def rotation_from_directions(axes, dirs) -> np.ndarray:
    """World->camera rotation from two camera-space axis directions.

    The first given horizontal axis keeps pointing towards its VP; Z is forced to
    point up in the image (positive camera Y). The result is right-handed.
    """
    if len(axes) != 2 or axes[0] == axes[1] or any(a not in AXES for a in axes):
        raise CalibrationError("need two different axes")
    d1 = _normalize(dirs[0])
    d2 = np.asarray(dirs[1], dtype=float)
    d2 = _normalize(d2 - d1 * np.dot(d1, d2))  # Gram-Schmidt
    d = _third_axis(axes, [d1, d2])
    d = {k: _normalize(v) for k, v in d.items()}

    if d["Z"][1] < 0:  # world up must look up in the image
        d["Z"] = -d["Z"]
        # flip one horizontal axis to stay right-handed; keep the first given
        # horizontal axis (if any) pointing towards its VP
        horizontal_given = [a for a in axes if a != "Z"]
        keep = horizontal_given[0] if horizontal_given else "X"
        flip = "Y" if keep == "X" else "X"
        d[flip] = -d[flip]

    m = np.column_stack([d["X"], d["Y"], d["Z"]])
    u, _, vt = np.linalg.svd(m)  # re-orthonormalise
    m = u @ vt
    return m


def swap_xy(rotation: np.ndarray) -> np.ndarray:
    """Rotate the world 90 degrees about Z: new X = old Y, new Y = -old X."""
    m = rotation
    return np.column_stack([m[:, 1], -m[:, 0], m[:, 2]])


def solve_from_vps(vp1, vp2, axes, width, height, focal_px=None, pp=None) -> Solution:
    """Full rotation + focal from two VPs assigned to ``axes`` (e.g. ("X", "Y"))."""
    pp = np.array([width / 2.0, height / 2.0]) if pp is None else np.asarray(pp, dtype=float)
    diag = float(np.hypot(width, height))
    vp1 = normalize_vp(vp1, diag)
    vp2 = normalize_vp(vp2, diag)
    if focal_px is None:
        f = focal_from_vps(vp1, vp2, pp)
        source = "vanishing points"
    else:
        f = float(focal_px)
        if f <= 0:
            raise CalibrationError("focal length must be positive")
        source = "given"
        if vp1[2] == 0 and vp2[2] == 0:
            raise CalibrationError("both vanishing points are at infinity")
    m = rotation_from_directions(axes, [direction_from_vp(vp1, pp, f), direction_from_vp(vp2, pp, f)])
    return Solution(f, m, pp, int(width), int(height), source)


def solve_from_lines(pairs, axes, width, height, focal_px=None) -> Solution:
    """Solve from two pairs of line segments (manual editor input).

    ``pairs`` = [ [lineA, lineB], [lineC, lineD] ], each line ((x0, y0), (x1, y1)) in pixels.
    Raises CalibrationError with ``pair`` set to the index of the offending pair.
    """
    diag = float(np.hypot(width, height))
    vps = [vp_from_lines(p[0], p[1], diag, pair=i) for i, p in enumerate(pairs)]
    if focal_px is None:
        for i, vp in enumerate(vps):
            if vp[2] == 0:
                raise CalibrationError("lines of this pair are parallel; enter the focal length", i)
    try:
        return solve_from_vps(vps[0], vps[1], axes, width, height, focal_px)
    except CalibrationError as exc:
        if exc.pair is None:
            exc.pair = 1
        raise


# ---------------------------------------------------------------- position / scale


def pixel_ray(sol: Solution, uv) -> np.ndarray:
    """World-space unit ray direction through pixel ``uv`` (camera rotation only)."""
    x = uv[0] - sol.principal_point[0]
    y = -(uv[1] - sol.principal_point[1])
    d_cam = _normalize([x, y, -sol.focal_px])
    return sol.camera_rotation @ d_cam


def ground_hit(sol: Solution, uv, camera_height: float):
    """Ground (z = 0) point hit by the pixel ray from a camera at (0, 0, h), or None."""
    d = pixel_ray(sol, uv)
    if d[2] >= -1e-9:
        return None
    t = camera_height / -d[2]
    p = np.array([0.0, 0.0, camera_height]) + t * d
    p[2] = 0.0
    return p


def default_origin_pixel(sol: Solution, camera_height: float = 1.0):
    """Image point used as world origin when the user has not picked one."""
    w, h = sol.width, sol.height
    for uv in ((w / 2.0, h / 2.0), (w / 2.0, h * 0.95)):
        if ground_hit(sol, uv, camera_height) is not None:
            return uv
    return None


def camera_location(sol: Solution, camera_height: float, origin_px=None) -> np.ndarray:
    """Camera location so that the ground point under ``origin_px`` is the world origin.

    With ``origin_px`` None the default origin pixel is used; if no pixel ray hits the
    ground, the origin is the point directly below the camera.
    """
    if camera_height <= 0:
        raise CalibrationError("camera height must be positive")
    if origin_px is None:
        origin_px = default_origin_pixel(sol)
    cam = np.array([0.0, 0.0, camera_height])
    if origin_px is None:
        return cam
    hit = ground_hit(sol, origin_px, camera_height)
    if hit is None:
        raise CalibrationError("the origin point is above the horizon")
    return cam - hit


def measure_reference(sol: Solution, camera_height: float, p0, p1, axis: str, origin_px=None) -> float:
    """Distance in scene units between two marked image points.

    X / Y: both points lie on the ground. Z: p0 is on the ground, p1 vertically above it.
    """
    cam = camera_location(sol, camera_height, origin_px)
    a = ground_hit(sol, p0, camera_height)
    if a is None:
        raise CalibrationError("reference start point is above the horizon")
    shift = cam - np.array([0.0, 0.0, camera_height])
    a = a + np.array([shift[0], shift[1], 0.0])
    if axis in ("X", "Y"):
        b = ground_hit(sol, p1, camera_height)
        if b is None:
            raise CalibrationError("reference end point is above the horizon")
        b = b + np.array([shift[0], shift[1], 0.0])
        idx = 0 if axis == "X" else 1
        return float(abs(b[idx] - a[idx]))
    if axis == "Z":
        # closest point between the pixel ray of p1 and the vertical line through a
        d = pixel_ray(sol, p1)
        o = cam
        # line 1: o + t d ; line 2: a + s z
        z = np.array([0.0, 0.0, 1.0])
        w0 = o - a
        b_ = np.dot(d, z)
        denom = 1.0 - b_ * b_
        if denom < 1e-9:
            raise CalibrationError("reference ray is parallel to the vertical axis")
        s = (np.dot(z, w0) - b_ * np.dot(d, w0)) / denom
        return float(abs(s))
    raise CalibrationError(f"unknown axis {axis}")


def height_from_reference(sol: Solution, p0, p1, axis: str, distance: float, origin_px=None) -> float:
    """Camera height that makes the marked reference ``distance`` long."""
    if distance <= 0:
        raise CalibrationError("reference distance must be positive")
    measured = measure_reference(sol, 1.0, p0, p1, axis, origin_px)
    if measured < 1e-9:
        raise CalibrationError("reference points coincide")
    return distance / measured


def project_point(sol: Solution, cam_location, point) -> np.ndarray:
    """Project a world point to pixels (for checks and drawing)."""
    p_cam = sol.rotation @ (np.asarray(point, dtype=float) - np.asarray(cam_location, dtype=float))
    if p_cam[2] >= 0:
        raise CalibrationError("point is behind the camera")
    x = sol.focal_px * p_cam[0] / -p_cam[2]
    y = sol.focal_px * p_cam[1] / -p_cam[2]
    return np.array([sol.principal_point[0] + x, sol.principal_point[1] - y])
