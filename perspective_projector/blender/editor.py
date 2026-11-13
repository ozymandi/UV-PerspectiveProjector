"""Manual vanishing-line editor: draggable endpoints (gizmos) over the photo in camera A's view."""

from __future__ import annotations

import bpy
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader

from ..core import solve
from . import calibration, view

AXIS_COLORS = {"X": (0.95, 0.25, 0.25, 1.0), "Y": (0.35, 0.85, 0.3, 1.0), "Z": (0.3, 0.55, 1.0, 1.0)}
INVALID_COLOR = (1.0, 0.6, 0.0, 1.0)
HANDLE_RADIUS_PX = 7.0


def _active(context):
    scene = context.scene
    props = scene.perspective_projector
    if not (props.editing and props.calibrated and props.image is not None):
        return None
    rv3d = context.region_data
    cam = calibration.camera_a(scene)
    if cam is None or rv3d is None or rv3d.view_perspective != "CAMERA":
        return None
    space = context.space_data
    view_cam = space.camera if (space and space.use_local_camera and space.camera) else scene.camera
    if view_cam is not cam:
        return None
    return cam


def set_point(scene, index, u, v):
    """Move endpoint ``index`` (0..7) to normalised image coords and re-solve camera A."""
    props = scene.perspective_projector
    values = list(props.lines)
    values[2 * index], values[2 * index + 1] = float(u), float(v)
    props.lines = values  # update callback re-solves; failures keep the last valid camera


def get_point(scene, index):
    v = scene.perspective_projector.lines
    return v[2 * index], v[2 * index + 1]


# ---------------------------------------------------------------- gizmos


def _circle(center, radius, segments=20):
    cx, cy = center
    pts = []
    for k in range(segments):
        a0 = 2 * np.pi * k / segments
        a1 = 2 * np.pi * (k + 1) / segments
        pts += [(cx, cy), (cx + radius * np.cos(a0), cy + radius * np.sin(a0)),
                (cx + radius * np.cos(a1), cy + radius * np.sin(a1))]
    return pts


class PP_GT_handle(bpy.types.Gizmo):
    """A round 2D handle for one line endpoint, dragged in region pixels."""

    bl_idname = "PP_GT_handle"
    __slots__ = ("index", "pos", "rect", "start_uv")

    def setup(self):
        self.index = 0
        self.pos = (0.0, 0.0)
        self.rect = None
        self.start_uv = None

    def draw(self, context):
        if self.rect is None:
            return
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        radius = HANDLE_RADIUS_PX * (1.35 if self.is_highlight else 1.0)
        shader.uniform_float("color", (0.0, 0.0, 0.0, 0.6))
        batch_for_shader(shader, "TRIS", {"pos": _circle(self.pos, radius + 1.5)}).draw(shader)
        color = self.color_highlight if self.is_highlight else self.color
        shader.uniform_float("color", (*color, 1.0))
        batch_for_shader(shader, "TRIS", {"pos": _circle(self.pos, radius)}).draw(shader)
        gpu.state.blend_set("NONE")

    def test_select(self, context, location):
        if self.rect is None:
            return -1
        d = np.hypot(location[0] - self.pos[0], location[1] - self.pos[1])
        return 0 if d <= HANDLE_RADIUS_PX + 4 else -1

    def invoke(self, context, event):
        self.start_uv = get_point(context.scene, self.index)
        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        if self.rect is None:
            return {"RUNNING_MODAL"}
        u, v = view.region_to_image(self.rect, event.mouse_region_x, event.mouse_region_y)
        set_point(context.scene, self.index, u, v)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        if cancel and self.start_uv is not None:
            set_point(context.scene, self.index, *self.start_uv)
        context.area.tag_redraw()


class PP_GGT_lines(bpy.types.GizmoGroup):
    bl_idname = "PP_GGT_lines"
    bl_label = "Perspective Projector Lines"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"PERSISTENT", "SHOW_MODAL_ALL"}

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def setup(self, context):
        self.handles = []
        for i in range(8):
            gz = self.gizmos.new(PP_GT_handle.bl_idname)
            gz.index = i
            gz.color_highlight = (1.0, 0.9, 0.2)
            self.handles.append(gz)

    def draw_prepare(self, context):
        cam = _active(context)
        rect = view.camera_frame_region(context, cam) if cam else None
        props = context.scene.perspective_projector
        axes = (props.pair0_axis, props.pair1_axis)
        for i, gz in enumerate(self.handles):
            gz.rect = rect
            if rect is not None:
                u, v = get_point(context.scene, i)
                gz.pos = view.image_to_region(rect, u, v)
            pair = i // 4
            color = INVALID_COLOR if props.invalid_pair == pair else AXIS_COLORS[axes[pair]]
            gz.color = color[:3]


# ---------------------------------------------------------------- line drawing


def _vp_of_pair(pts, diag):
    try:
        return solve.vp_from_lines((pts[0], pts[1]), (pts[2], pts[3]), diag)
    except solve.CalibrationError:
        return None


def _draw_lines():
    context = bpy.context
    cam = _active(context)
    if cam is None:
        return
    rect = view.camera_frame_region(context, cam)
    if rect is None:
        return
    props = context.scene.perspective_projector
    values = list(props.lines)
    region = context.region
    shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    shader.uniform_float("viewportSize", (region.width, region.height))

    for pair in range(2):
        axis = props.pair0_axis if pair == 0 else props.pair1_axis
        color = INVALID_COLOR if props.invalid_pair == pair else AXIS_COLORS[axis]
        pts = []
        for k in range(4):
            idx = pair * 4 + k
            pts.append(view.image_to_region(rect, values[2 * idx], values[2 * idx + 1]))
        # the two editable segments
        shader.uniform_float("lineWidth", 2.0)
        shader.uniform_float("color", color)
        batch_for_shader(shader, "LINES", {"pos": pts}).draw(shader)
        # thin extensions towards the vanishing point
        vp = _vp_of_pair(pts, float(np.hypot(region.width, region.height)))
        if vp is None:
            continue
        ext = []
        reach = 4.0 * max(region.width, region.height)
        for a, b in ((pts[0], pts[1]), (pts[2], pts[3])):
            a, b = np.array(a), np.array(b)
            if vp[2] != 0:
                target = vp[:2] / vp[2]
                da, db = np.linalg.norm(target - a), np.linalg.norm(target - b)
                start = b if db < da else a
                d = target - start
                n = np.linalg.norm(d)
                end = target if n < reach else start + d / n * reach
            else:
                d = b - a
                d = d / (np.linalg.norm(d) + 1e-12)
                start, end = b, b + d * reach
            ext += [tuple(start), tuple(end)]
        shader.uniform_float("lineWidth", 1.0)
        shader.uniform_float("color", (color[0], color[1], color[2], 0.45))
        batch_for_shader(shader, "LINES", {"pos": ext}).draw(shader)
    gpu.state.blend_set("NONE")


# ---------------------------------------------------------------- operator


def start_editing(context):
    scene = context.scene
    props = scene.perspective_projector
    props.editing = True
    cam = calibration.camera_a(scene)
    if cam is not None and context.area is not None and context.area.type == "VIEW_3D":
        view.look_through(context, cam)
        context.area.tag_redraw()


class PP_OT_edit_lines(bpy.types.Operator):
    """Show the vanishing lines over the photo and drag their endpoints to refine camera A"""

    bl_idname = "perspective_projector.edit_lines"
    bl_label = "Edit Lines"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = context.scene.perspective_projector
        return props.calibrated and calibration.camera_a(context.scene) is not None

    def execute(self, context):
        props = context.scene.perspective_projector
        if props.editing:
            props.editing = False
        else:
            start_editing(context)
        for area in context.screen.areas if context.screen else ():
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


_classes = (PP_GT_handle, PP_GGT_lines, PP_OT_edit_lines)
_handle = None


def register():
    global _handle
    for cls in _classes:
        bpy.utils.register_class(cls)
    _handle = bpy.types.SpaceView3D.draw_handler_add(_draw_lines, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
