"""5.3: lines and camera A survive save / close / reopen."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402

H.reset_scene()
path, _ = H.make_photo(yaw_deg=-30, pitch_deg=-12, focal_px=2800)
H.load(path)
bpy.ops.perspective_projector.calibrate(open_editor=False)
props = H.props()
vals = list(props.lines)
vals[1] += 0.01  # a manual tweak
props.lines = vals
props.camera_height = 2.5
props.swap_xy = True
cam = H.camera_a()
mat = np.array(cam.matrix_world)
lens = cam.data.lens
lines = list(props.lines)

blend = os.path.join(H.TMP, "persist.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
bpy.ops.wm.read_homefile(use_empty=True)
H.check(H.camera_a() is None, "scene not cleared")
bpy.ops.wm.open_mainfile(filepath=blend)

props = H.props()
cam = H.camera_a()
H.check(cam is not None, "camera A missing after reopen")
H.check(np.allclose(list(props.lines), lines, atol=1e-6), "lines changed after reopen")
H.check(np.allclose(np.array(cam.matrix_world), mat, atol=1e-6), "camera moved after reopen")
H.check(abs(cam.data.lens - lens) < 1e-6, "lens changed after reopen")
H.check(props.swap_xy and abs(props.camera_height - 2.5) < 1e-6 and props.calibrated, "settings lost")
H.check(props.image is not None and props.image.size[0] == 4000, "photo lost")
# re-solving from the stored state reproduces the same camera
props.lines = list(props.lines)
H.check(np.allclose(np.array(cam.matrix_world), mat, atol=1e-5), "re-solve after reopen differs")
print("persist ok")
