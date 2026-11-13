"""Mapping between 3D viewport region pixels and normalised photo coordinates of camera A."""

from __future__ import annotations

from bpy_extras import view3d_utils


def camera_frame_region(context, cam):
    """Region-space rectangle (left, bottom, right, top) of ``cam``'s frame, or None."""
    region, rv3d, scene = context.region, context.region_data, context.scene
    if region is None or rv3d is None:
        return None
    frame = cam.data.view_frame(scene=scene)  # TR, BR, BL, TL in camera space
    pts = [view3d_utils.location_3d_to_region_2d(region, rv3d, cam.matrix_world @ v) for v in frame]
    if any(p is None for p in pts):
        return None
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def region_to_image(rect, x, y):
    """Region pixel -> normalised image coords (u right, v down, 0..1 inside the frame)."""
    left, bottom, right, top = rect
    return (x - left) / (right - left), (top - y) / (top - bottom)


def image_to_region(rect, u, v):
    left, bottom, right, top = rect
    return left + u * (right - left), top - v * (top - bottom)


def look_through(context, cam):
    """Make the active 3D view look through ``cam`` without changing the scene camera."""
    space = context.space_data
    if space is None or space.type != "VIEW_3D":
        return False
    if context.scene.camera is not cam:
        space.use_local_camera = True
        space.camera = cam
    context.region_data.view_perspective = "CAMERA"
    return True
