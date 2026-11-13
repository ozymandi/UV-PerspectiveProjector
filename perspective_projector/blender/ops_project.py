"""Project operator."""

import bpy

from . import calibration, projection, remap


class PP_OT_project(bpy.types.Operator):
    """Project the photo from camera A onto the selected meshes, or onto a plane that fills camera A's frame"""

    bl_idname = "perspective_projector.project"
    bl_label = "Project"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = context.scene.perspective_projector
        if not (props.calibrated and props.image is not None and calibration.camera_a(context.scene)):
            cls.poll_message_set("Calibrate first")
            return False
        return True

    def execute(self, context):
        scene = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        selected = list(context.selected_objects)
        targets, skipped, created_b = projection.project(scene, selected)
        msg = f"Projected onto {', '.join(o.name for o in targets)}"
        if skipped:
            msg += f"; skipped (not a mesh): {', '.join(o.name for o in skipped)}"
            self.report({"WARNING"}, msg)
        else:
            self.report({"INFO"}, msg)
        scene.perspective_projector.status = msg
        return {"FINISHED"}


class PP_OT_remap(bpy.types.Operator):
    """Bake the projection of the selected objects into a regular UV map and texture"""

    bl_idname = "perspective_projector.remap"
    bl_label = "Remap"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not any(remap.is_projected(o) for o in context.selected_objects):
            cls.poll_message_set("Select an object with a live projection")
            return False
        return True

    def execute(self, context):
        scene = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        props = scene.perspective_projector
        selected = list(context.selected_objects)
        done, skipped = [], []
        for obj in selected:
            if not remap.is_projected(obj):
                skipped.append(obj.name)
                continue
            img, _, _ = remap.remap(scene, obj, props.remap_resolution)
            done.append(f"{obj.name} ({img.size[0]} px)")
        for obj in selected:
            obj.select_set(True)
        msg = f"Remapped {', '.join(done)}" if done else "Nothing remapped"
        if skipped:
            msg += f"; skipped (no projection): {', '.join(skipped)}"
        props.status = msg
        self.report({"WARNING"} if skipped else {"INFO"}, msg)
        return {"FINISHED"}


_classes = (PP_OT_project, PP_OT_remap)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
