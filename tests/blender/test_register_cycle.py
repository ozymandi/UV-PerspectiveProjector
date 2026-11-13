"""Disable and re-enable the extension several times: no errors, no leftovers, still works."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _helpers as H  # noqa: E402
import addon_utils  # noqa: E402
import bpy  # noqa: E402

MOD = next(m for m in bpy.context.preferences.addons.keys() if m.endswith("perspective_projector"))
handlers_before = None
for _ in range(3):
    addon_utils.disable(MOD, default_set=True, handle_error=None)
    H.check(not hasattr(bpy.types, "PP_PT_main"), "panel left registered after disable")
    H.check(not hasattr(bpy.types.Scene, "perspective_projector"), "scene property left after disable")
    try:
        bpy.ops.perspective_projector.calibrate.get_rna_type()
        operator_left = True
    except KeyError:
        operator_left = False
    H.check(not operator_left, "operator left after disable")
    addon_utils.enable(MOD, default_set=True, handle_error=None)
    H.check(hasattr(bpy.types, "PP_PT_main"), "panel missing after enable")

# still works after the cycles
H.reset_scene()
path, _ = H.make_photo()
H.load(path)
res = bpy.ops.perspective_projector.calibrate(open_editor=False)
H.check(res == {"FINISHED"} and H.camera_a() is not None, "calibrate broken after re-enable")
print("register cycle ok")
