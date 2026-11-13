"""7.4: Remap is a single undo step that restores the live projection (needs a window)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _helpers as H  # noqa: E402
import bpy  # noqa: E402


def test():
    H.reset_scene()
    path, _ = H.make_photo()
    ctx = H.window_context()
    with bpy.context.temp_override(**ctx):
        bpy.ops.perspective_projector.load_photo("EXEC_DEFAULT", True, filepath=path)
        bpy.ops.perspective_projector.calibrate("EXEC_DEFAULT", True, open_editor=False)
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.ops.perspective_projector.project("EXEC_DEFAULT", True)
        plane = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "PLANE")
        plane.select_set(True)
        bpy.context.view_layer.objects.active = plane
        bpy.context.scene.perspective_projector.remap_resolution = 256
        bpy.ops.ed.undo_push(message="selected")
        bpy.ops.perspective_projector.remap("EXEC_DEFAULT", True)
    plane = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "PLANE")
    H.check("PP_UVProject" not in plane.modifiers, "remap did not run")
    H.undo()
    plane = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "PLANE")
    H.check("PP_UVProject" in plane.modifiers, "projection modifier not restored")
    H.check(plane.data.materials[0].name.startswith("PP_Projection"), "projection material not restored")
    H.check("ProjUV" in plane.data.uv_layers, "projection UV map not restored")


H.run_ui_test(test)
