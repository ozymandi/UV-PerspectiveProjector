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
# a two-pair state (as written by 1.0.0) has the new inputs off
H.check(not props.pair2_enabled, "third pair on by default")
H.check(abs(cam.data.shift_x) < 1e-9 and abs(cam.data.shift_y) < 1e-9, "two-pair camera got a shift")

# ---- a three-pair state survives save and reload
H.reset_scene()
path3, synth3 = H.make_photo(name="three.png", yaw_deg=-40, pitch_deg=-25, focal_px=2400,
                             pp=(2000 + 240, 1500 - 300))
H.load(path3)
props = H.props()


def seg_norm(start, direction):
    p, q = synth3.segment(start, direction, 2.0)
    return [p[0] / 4000, p[1] / 3000, q[0] / 4000, q[1] / 3000]


props.lock_updates = True
props.lines = (seg_norm((-2.0, 2.0, 0.0), (1, 0, 0)) + seg_norm((-2.0, 4.0, 2.5), (1, 0, 0))
               + seg_norm((2.0, -2.0, 0.0), (0, 1, 0)) + seg_norm((4.0, -2.0, 2.5), (0, 1, 0)))
props.pair0_axis, props.pair1_axis = "X", "Y"
props.lines3 = seg_norm((-1.5, 3.0, 0.0), (0, 0, 1)) + seg_norm((2.5, 3.0, 0.0), (0, 0, 1))
props.pair2_enabled = True
props.calibrated = True
props.lock_updates = False
from bl_ext.user_default.perspective_projector.blender import calibration  # noqa: E402

H.check(calibration.reapply(bpy.context.scene), f"three-pair solve failed: {props.status}")
cam = H.camera_a()
mat3, shift3, lines3 = np.array(cam.matrix_world), (cam.data.shift_x, cam.data.shift_y), list(props.lines3)
H.check(abs(shift3[0]) > 0.01 and abs(shift3[1]) > 0.01, f"three VPs gave no shift: {shift3}")
H.check(props.shift_source == "three vanishing points", f"shift source {props.shift_source!r}")
H.check(abs(shift3[0] - (2000 - 2240) / 4000) < 0.005 and abs(shift3[1] - (1200 - 1500) / 4000) < 0.005,
        f"three-VP shift {shift3} differs from the true lens shift")
blend3 = os.path.join(H.TMP, "persist3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend3)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=blend3)
props, cam = H.props(), H.camera_a()
H.check(props.pair2_enabled and np.allclose(list(props.lines3), lines3, atol=1e-6), "third pair lost")
H.check(np.allclose(np.array(cam.matrix_world), mat3, atol=1e-6), "three-pair camera moved after reopen")
H.check(np.allclose((cam.data.shift_x, cam.data.shift_y), shift3, atol=1e-7), "shift lost after reopen")
print("persist ok")
