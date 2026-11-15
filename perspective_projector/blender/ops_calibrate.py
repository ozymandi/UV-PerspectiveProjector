"""Operators: load photo, calibrate, swap axes, pick origin / reference points."""

import os

import bpy
from bpy_extras.io_utils import ImportHelper

from ..core import solve
from . import calibration, editor, view

IMAGE_FILTER = "*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.exr;*.webp"


class PP_OT_load_photo(bpy.types.Operator, ImportHelper):
    """Load the photo to calibrate"""

    bl_idname = "perspective_projector.load_photo"
    bl_label = "Load Photo"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: bpy.props.StringProperty(default=IMAGE_FILTER, options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.perspective_projector
        path = self.filepath
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"File not found: {path}")
            return {"CANCELLED"}
        try:
            img = bpy.data.images.load(path, check_existing=True)
        except RuntimeError as exc:
            self.report({"ERROR"}, f"Cannot load image: {exc}")
            return {"CANCELLED"}
        if img.size[0] == 0 or img.size[1] == 0:
            if img.users == 0:
                bpy.data.images.remove(img)
            self.report({"ERROR"}, "Cannot read pixels from this file")
            return {"CANCELLED"}
        props.lock_updates = True
        try:
            props.image = img
            props.calibrated = False
            props.status = f"Loaded {img.size[0]} x {img.size[1]}"
            props.confidence = 0.0
            calibration.read_exif(props)
        finally:
            props.lock_updates = False
        return {"FINISHED"}


class PP_OT_calibrate(bpy.types.Operator):
    """Detect vanishing points and create or update the projection camera"""

    bl_idname = "perspective_projector.calibrate"
    bl_label = "Calibrate"
    bl_options = {"REGISTER", "UNDO"}

    open_editor: bpy.props.BoolProperty(default=True, options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene.perspective_projector.image is not None

    def execute(self, context):
        scene = context.scene
        props = scene.perspective_projector
        det, seeded = calibration.detect(props)
        props.confidence = det.confidence if det else 0.0
        confident = det is not None and seeded and det.confidence >= calibration.CONFIDENCE_THRESHOLD

        props.lock_updates = True
        try:
            props.calibrated = True
        finally:
            props.lock_updates = False
        ok = calibration.reapply(scene)

        if confident and ok:
            props.status = f"Calibrated automatically (confidence {props.confidence:.0%})"
            self.report({"INFO"}, props.status)
            return {"FINISHED"}

        props.status = ("Automatic detection was not confident "
                        f"({props.confidence:.0%}); adjust the lines")
        self.report({"WARNING"}, props.status)
        if self.open_editor:
            editor.start_editing(context)
        return {"FINISHED"}


class PP_OT_swap_xy(bpy.types.Operator):
    """Swap the horizontal X and Y axes (90 degree turn about Z); the view through camera A stays the same"""

    bl_idname = "perspective_projector.swap_xy"
    bl_label = "Swap X/Y"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.perspective_projector.calibrated

    def execute(self, context):
        props = context.scene.perspective_projector
        props.swap_xy = not props.swap_xy
        return {"FINISHED"}


class PP_OT_pick_point(bpy.types.Operator):
    """Click a point on the photo in camera A's view"""

    bl_idname = "perspective_projector.pick_point"
    bl_label = "Pick Point"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(items=[
        ("ORIGIN", "Origin", "World origin on the ground"),
        ("REF0", "Reference start", "First reference point"),
        ("REF1", "Reference end", "Second reference point"),
        ("SIZE_A0", "Size A start", "Start of known-size segment A on the ground"),
        ("SIZE_A1", "Size A end", "End of known-size segment A on the ground"),
        ("SIZE_B0", "Size B start", "Start of known-size segment B on the ground"),
        ("SIZE_B1", "Size B end", "End of known-size segment B on the ground"),
    ])

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == "VIEW_3D"
                and context.scene.perspective_projector.calibrated
                and calibration.camera_a(context.scene) is not None)

    def invoke(self, context, event):
        view.look_through(context, calibration.camera_a(context.scene))
        context.window.cursor_modal_set("CROSSHAIR")
        context.workspace.status_text_set("Click a point on the photo  |  Esc / right click: cancel")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._finish(context)
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            rect = view.camera_frame_region(context, calibration.camera_a(context.scene))
            if rect is None:
                return {"RUNNING_MODAL"}
            u, v = view.region_to_image(rect, event.mouse_region_x, event.mouse_region_y)
            if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
                return {"RUNNING_MODAL"}
            self.set_point(context.scene, (u, v))
            self._finish(context)
            return {"FINISHED"}
        return {"PASS_THROUGH"} if event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE"} else {"RUNNING_MODAL"}

    def set_point(self, scene, uv):
        props = scene.perspective_projector
        if self.target == "ORIGIN":
            previous = (props.origin_set, tuple(props.origin))
            props.lock_updates = True
            props.origin = uv
            props.origin_set = True
            props.lock_updates = False
            if not calibration.reapply(scene):
                props.lock_updates = True
                props.origin_set, props.origin = previous[0], previous[1]
                props.lock_updates = False
                calibration.reapply(scene)
                self.report({"ERROR"}, "The origin must be on the ground (below the horizon)")
        elif self.target == "REF0":
            props.ref_p0 = uv
        elif self.target == "REF1":
            props.ref_p1 = uv
        else:
            setattr(props, {"SIZE_A0": "size_a_p0", "SIZE_A1": "size_a_p1",
                            "SIZE_B0": "size_b_p0", "SIZE_B1": "size_b_p1"}[self.target], uv)


class PP_OT_clear_origin(bpy.types.Operator):
    """Use the default origin again"""

    bl_idname = "perspective_projector.clear_origin"
    bl_label = "Reset Origin"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.perspective_projector.origin_set = False
        return {"FINISHED"}


_classes = (PP_OT_load_photo, PP_OT_calibrate, PP_OT_swap_xy, PP_OT_pick_point, PP_OT_clear_origin)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
