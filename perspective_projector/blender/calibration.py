"""Turn the stored calibration state into camera A (and back from automatic detection)."""

from __future__ import annotations

import bpy
import numpy as np
from mathutils import Matrix

from ..core import exif, lines as core_lines, solve, vp_detect

ROLE = "pp_role"
ROLE_CAMERA_A = "CAMERA_A"
CAMERA_A_NAME = "Proj_Cam_A"
SENSOR_MM = 36.0
CONFIDENCE_THRESHOLD = 0.5  # tuned in tests/data/README.md


# ---------------------------------------------------------------- lookup helpers


def find_role(scene, role):
    for obj in scene.objects:
        if obj.get(ROLE) == role:
            return obj
    return None


def camera_a(scene):
    return find_role(scene, ROLE_CAMERA_A)


def image_size(img):
    w, h = img.size
    return int(w), int(h)


def _px(norm, w, h):
    return (norm[0] * w, norm[1] * h)


def line_pairs_px(props, w, h):
    v = list(props.lines)
    pts = [(v[i] * w, v[i + 1] * h) for i in range(0, 16, 2)]
    return [[(pts[0], pts[1]), (pts[2], pts[3])], [(pts[4], pts[5]), (pts[6], pts[7])]]


# ---------------------------------------------------------------- solving


def manual_focal_px(props, w, h):
    return solve.focal_from_35mm(props.focal_35mm, w, h)


def solve_state(props):
    """Solution, camera location and focal source for the stored state. Raises CalibrationError."""
    img = props.image
    if img is None:
        raise solve.CalibrationError("load a photo first")
    w, h = image_size(img)
    pairs = line_pairs_px(props, w, h)
    axes = (props.pair0_axis, props.pair1_axis)
    if props.focal_mode == "MANUAL":
        sol = solve.solve_from_lines(pairs, axes, w, h, focal_px=manual_focal_px(props, w, h))
        source = f"manual {props.focal_35mm:g} mm"
    else:
        try:
            sol = solve.solve_from_lines(pairs, axes, w, h)
            source = "vanishing points"
        except solve.CalibrationError as exc:
            if "focal" not in str(exc):
                raise
            if props.exif_focal_px <= 0:
                # no focal in the photo: the user has to enter one (Focal length: Manual)
                raise solve.CalibrationError(
                    "a vanishing point is at infinity and the photo has no EXIF focal length; "
                    "set Focal length to Manual", exc.pair)
            f, source = props.exif_focal_px, props.exif_label or "EXIF"
            sol = solve.solve_from_lines(pairs, axes, w, h, focal_px=f)
    if props.swap_xy:
        sol.rotation = solve.swap_xy(sol.rotation)

    origin_px = _px(props.origin, w, h) if props.origin_set else None
    height = props.camera_height
    if props.ref_enabled:
        height = solve.height_from_reference(sol, _px(props.ref_p0, w, h), _px(props.ref_p1, w, h),
                                             props.ref_axis, props.ref_distance, origin_px)
    loc = solve.camera_location(sol, height, origin_px)
    return sol, loc, source, height


# ---------------------------------------------------------------- applying to Blender


def ensure_camera_a(scene):
    cam = camera_a(scene)
    if cam is None:
        data = bpy.data.cameras.new(CAMERA_A_NAME)
        cam = bpy.data.objects.new(CAMERA_A_NAME, data)
        scene.collection.objects.link(cam)
        cam[ROLE] = ROLE_CAMERA_A
    return cam


def apply_solution(scene, sol, loc, img):
    cam = ensure_camera_a(scene)
    data = cam.data
    data.type = "PERSP"
    data.sensor_width = SENSOR_MM
    data.sensor_height = SENSOR_MM
    data.sensor_fit = "HORIZONTAL" if sol.width >= sol.height else "VERTICAL"
    data.lens = sol.lens_mm(SENSOR_MM)
    data.shift_x = data.shift_y = 0.0

    rot = Matrix([list(r) for r in sol.camera_rotation])
    cam.matrix_world = Matrix.Translation(tuple(loc)) @ rot.to_4x4()

    data.show_background_images = True
    bg = data.background_images[0] if len(data.background_images) else data.background_images.new()
    bg.image = img
    bg.alpha = 1.0
    bg.display_depth = "BACK"
    bg.frame_method = "STRETCH"
    bg.show_background_image = True

    render = scene.render
    render.resolution_x, render.resolution_y = sol.width, sol.height
    render.resolution_percentage = 100
    render.pixel_aspect_x = render.pixel_aspect_y = 1.0

    from . import projection  # camera B and plane follow camera A when they exist

    if projection.camera_b(scene) is None:
        scene.camera = cam
    projection.on_camera_a_changed(scene)
    return cam


def reapply(scene):
    """Solve from the stored state and update camera A. Returns True on success."""
    props = scene.perspective_projector
    try:
        sol, loc, source, height = solve_state(props)
    except solve.CalibrationError as exc:
        props.status = str(exc)
        props.invalid_pair = exc.pair if exc.pair is not None else -1
        return False
    props.invalid_pair = -1
    props.focal_source = source
    props.effective_height = float(height)
    apply_solution(scene, sol, loc, props.image)
    return True


def reapply_if_calibrated(scene):
    props = scene.perspective_projector
    if props.calibrated and not props.lock_updates:
        reapply(scene)


# ---------------------------------------------------------------- automatic detection


def image_gray(img):
    w, h = image_size(img)
    channels = img.channels
    buf = np.empty(w * h * channels, dtype=np.float32)
    img.pixels.foreach_get(buf)
    return core_lines.to_gray_u8(buf.reshape(h, w, channels), w, h, bottom_up=True)


def read_exif(props):
    img = props.image
    props.exif_focal_px, props.exif_label = 0.0, ""
    path = bpy.path.abspath(img.filepath) if img.filepath else ""
    if not path:
        return
    w, h = image_size(img)
    found = exif.focal_px_from_exif(path, w, h)
    if found:
        props.exif_focal_px, props.exif_label = float(found[0]), found[1]


def _snap_segment(seg, vp):
    """Rotate a segment about its midpoint so it points exactly at ``vp`` (homogeneous)."""
    p, q = np.array(seg[:2]), np.array(seg[2:])
    mid = (p + q) / 2.0
    half = np.linalg.norm(q - p) / 2.0
    if vp[2] != 0:
        d = vp[:2] / vp[2] - mid
    else:
        d = np.array(vp[:2], dtype=float)
    d = d / (np.linalg.norm(d) + 1e-12)
    if np.dot(d, q - p) < 0:
        d = -d
    return np.concatenate([mid - d * half, mid + d * half])


def _pick_two(seg, idx):
    """Two long, well separated inlier segments."""
    idx = list(idx)
    lengths = np.hypot(seg[idx, 2] - seg[idx, 0], seg[idx, 3] - seg[idx, 1])
    order = [idx[i] for i in np.argsort(-lengths)]
    first = order[0]
    mid0 = (seg[first, :2] + seg[first, 2:]) / 2.0
    best, best_score = order[1], -1.0
    for j in order[1:12]:
        mid = (seg[j, :2] + seg[j, 2:]) / 2.0
        score = np.linalg.norm(mid - mid0) * np.hypot(*(seg[j, 2:] - seg[j, :2]))
        if score > best_score:
            best, best_score = j, score
    return first, best


def lines_from_detection(det):
    """Seed the 16 line values and the pair axes from a detection."""
    axes, _ = det.axis_pair()
    out = []
    for axis in axes:
        k = solve.AXES.index(axis)
        idx = det.inliers[k]
        if len(idx) >= 2:
            a, b = _pick_two(det.segments, idx)
            segs = [_snap_segment(det.segments[s], det.vps[k]) for s in (a, b)]
        else:
            segs = _guide_segments(det.vps[k], det.width, det.height)
            if segs is None:
                return None
        for snapped in segs:
            out += [snapped[0] / det.width, snapped[1] / det.height,
                    snapped[2] / det.width, snapped[3] / det.height]
    return out, axes


def _guide_segments(vp, w, h):
    """Two lines from the lower corners towards a finite VP that has too few detected edges
    (typically the depth point of a one-point photo); the user drags them onto real edges."""
    if vp[2] == 0:
        return None
    target = np.array(vp[:2]) / vp[2]
    segs = []
    for start in ((0.2 * w, 0.92 * h), (0.8 * w, 0.92 * h)):
        start = np.array(start)
        end = start + (target - start) * 0.6
        segs.append(np.concatenate([start, end]))
    return segs


def detect(props):
    """Run automatic detection. Returns (detection or None, seeded: bool)."""
    img = props.image
    w, h = image_size(img)
    gray = image_gray(img)
    seg = core_lines.detect_segments(gray)
    hint = props.exif_focal_px or None
    det = vp_detect.detect(seg, w, h, focal_hint_px=hint)
    if det is None:
        return None, False
    seeded = lines_from_detection(det)
    if seeded is None:
        return det, False
    values, axes = seeded
    props.lock_updates = True
    try:
        props.lines = values
        props.pair0_axis, props.pair1_axis = axes
    finally:
        props.lock_updates = False
    return det, True
