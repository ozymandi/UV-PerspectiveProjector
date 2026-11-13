"""6.5: Project is a single undo step (needs a window)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _helpers as H  # noqa: E402
import bpy  # noqa: E402


def roles():
    return sorted(str(o.get("pp_role")) for o in bpy.context.scene.objects)


def test():
    H.reset_scene()
    path, _ = H.make_photo()
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.perspective_projector.load_photo("EXEC_DEFAULT", True, filepath=path)
        bpy.ops.perspective_projector.calibrate("EXEC_DEFAULT", True, open_editor=False)
        before = roles()
        n_mats = len(bpy.data.materials)
        bpy.ops.perspective_projector.project("EXEC_DEFAULT", True)
    H.check("PLANE" in roles() and "CAMERA_B" in roles(), f"project did nothing: {roles()}")
    H.undo()
    H.check(roles() == before, f"after undo {roles()} != {before}")
    H.check(len([m for m in bpy.data.materials if m.users]) <= n_mats, "projection material still used")
    H.check(H.camera_a() is not None, "undo went too far (camera A gone)")
    H.check(bpy.context.scene.camera == H.camera_a(), "active camera not restored to A")


H.run_ui_test(test)
