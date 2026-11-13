"""4.5: Calibrate is a single undo step (needs a window)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _helpers as H  # noqa: E402
import bpy  # noqa: E402


def test():
    H.reset_scene()
    path, _ = H.make_photo()
    with bpy.context.temp_override(**H.window_context()):
        bpy.context.scene.render.resolution_x = 1234
        bpy.ops.ed.undo_push(message="resolution")
        # 'EXEC_DEFAULT', True = push an undo step like a button click does
        bpy.ops.perspective_projector.load_photo("EXEC_DEFAULT", True, filepath=path)
        bpy.ops.perspective_projector.calibrate("EXEC_DEFAULT", True, open_editor=False)
    H.check(H.camera_a() is not None, "no camera after calibrate")
    H.check(bpy.context.scene.render.resolution_x == 4000, "resolution not set")
    H.undo()
    H.check(H.camera_a() is None, "camera A still there after one undo")
    print("RES", [s.render.resolution_x for s in bpy.data.scenes], bpy.context.scene.render.resolution_x)
    H.check(bpy.context.scene.render.resolution_x == 1234, "resolution not restored")
    H.check(bpy.context.scene.perspective_projector.image is not None, "undo went too far (photo gone)")


H.run_ui_test(test)
