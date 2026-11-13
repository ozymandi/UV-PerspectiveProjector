import bpy

from . import calibration


class PP_PT_main(bpy.types.Panel):
    bl_label = "Perspective Projector"
    bl_idname = "PP_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Projector"

    def draw(self, context):
        layout = self.layout
        props = context.scene.perspective_projector

        col = layout.column(align=True)
        col.operator("perspective_projector.load_photo", icon="FILE_IMAGE")
        if props.image is None:
            layout.label(text="Load a photo to start")
            return
        w, h = props.image.size
        col.label(text=f"{props.image.name}  ({w} x {h})")

        layout.operator("perspective_projector.calibrate", icon="CAMERA_DATA")
        if props.status:
            box = layout.box()
            box.label(text=props.status, icon="ERROR" if props.invalid_pair >= 0 else "INFO")
            if props.invalid_pair >= 0:
                box.label(text=f"Line pair {props.invalid_pair + 1} is invalid")


class PP_PT_camera(bpy.types.Panel):
    bl_label = "Camera"
    bl_parent_id = "PP_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Projector"

    @classmethod
    def poll(cls, context):
        return context.scene.perspective_projector.calibrated

    def draw(self, context):
        layout = self.layout
        props = context.scene.perspective_projector
        cam = calibration.camera_a(context.scene)

        layout.operator("perspective_projector.edit_lines", icon="GREASEPENCIL",
                        text="Finish Editing" if props.editing else "Edit Lines", depress=props.editing)
        row = layout.row(align=True)
        row.prop(props, "pair0_axis", text="Pair 1")
        row.prop(props, "pair1_axis", text="Pair 2")
        layout.operator("perspective_projector.swap_xy", icon="ARROW_LEFTRIGHT")

        col = layout.column(align=True)
        col.prop(props, "focal_mode")
        col.prop(props, "focal_35mm")
        if cam:
            col.label(text=f"Lens {cam.data.lens:.1f} mm  ({props.focal_source})")
        layout.label(text=f"Confidence {props.confidence:.0%}")


class PP_PT_position(bpy.types.Panel):
    bl_label = "Position and Scale"
    bl_parent_id = "PP_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Projector"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.perspective_projector.calibrated

    def draw(self, context):
        layout = self.layout
        props = context.scene.perspective_projector

        sub = layout.column()
        sub.enabled = not props.ref_enabled
        sub.prop(props, "camera_height")

        row = layout.row(align=True)
        row.operator("perspective_projector.pick_point", text="Pick Origin", icon="EMPTY_AXIS").target = "ORIGIN"
        if props.origin_set:
            row.operator("perspective_projector.clear_origin", text="", icon="X")

        layout.prop(props, "ref_enabled")
        col = layout.column(align=True)
        col.enabled = props.ref_enabled
        col.prop(props, "ref_axis")
        row = col.row(align=True)
        row.operator("perspective_projector.pick_point", text="Start").target = "REF0"
        row.operator("perspective_projector.pick_point", text="End").target = "REF1"
        col.prop(props, "ref_distance")
        if props.ref_enabled:
            col.label(text=f"Camera height {props.effective_height:.3f}")


class PP_PT_projection(bpy.types.Panel):
    bl_label = "Projection"
    bl_parent_id = "PP_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Projector"

    @classmethod
    def poll(cls, context):
        return context.scene.perspective_projector.image is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.perspective_projector
        if not props.calibrated:
            layout.label(text="Calibrate first", icon="INFO")
        layout.operator("perspective_projector.project", icon="MOD_UVPROJECT")
        layout.prop(props, "plane_distance")
        layout.separator()
        layout.operator("perspective_projector.remap", icon="TEXTURE")
        layout.prop(props, "remap_resolution")


_classes = (PP_PT_main, PP_PT_camera, PP_PT_position, PP_PT_projection)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
