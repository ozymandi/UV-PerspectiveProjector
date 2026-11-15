"""Calibration that cannot be solved on the first try still creates camera A (placeholder)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from bl_ext.user_default.perspective_projector.blender import calibration  # noqa: E402
from bl_ext.user_default.perspective_projector.core import solve  # noqa: E402

H.reset_scene()
path, synth = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
H.load(path)
props = H.props()
scene = bpy.context.scene

# pair 2 parallel in the image with Focal length: Auto and no EXIF -> cannot be solved
lines = list(props.lines)
lines[8:16] = [0.30, 0.20, 0.30, 0.80, 0.70, 0.20, 0.70, 0.80]
props.lock_updates = True
props.lines = lines
props.pair0_axis, props.pair1_axis = "X", "Z"
props.focal_mode = "AUTO"
props.calibrated = True
props.lock_updates = False
H.check(H.camera_a() is None, "camera A exists before the first solve")

ok = calibration.reapply(scene)
H.check(not ok, "unsolvable lines reported as solved")
H.check(props.invalid_pair == 1, f"invalid pair {props.invalid_pair}")
cam = H.camera_a()
H.check(cam is not None, "no camera A after a failed first calibration")
H.check(cam.data.background_images[0].image == props.image, "photo is not camera A's background")
r = scene.render
H.check((r.resolution_x, r.resolution_y) == (4000, 3000), "render resolution not the photo size")
expected = solve.focal_from_35mm(props.focal_35mm, 4000, 3000) * 36.0 / 4000
H.check(abs(cam.data.lens - expected) < 1e-3, f"placeholder lens {cam.data.lens} vs {expected}")
H.check(abs(cam.matrix_world.translation.z - props.camera_height) < 1e-6, "placeholder height")
fwd = np.array(cam.matrix_world.to_3x3()) @ np.array([0.0, 0.0, -1.0])
H.check(np.allclose(fwd, [0, 1, 0], atol=1e-6), f"placeholder not looking along +Y: {fwd}")

# a later failure keeps the last camera (here: still the placeholder, one camera A only)
before = cam.matrix_world.copy()
H.check(not calibration.reapply(scene), "still unsolvable")
H.check(cam.matrix_world == before, "camera A changed on a failed solve")
cams = [o for o in scene.objects if o.get("pp_role") == "CAMERA_A"]
H.check(len(cams) == 1, f"{len(cams)} camera A objects")

# fixing the lines replaces the placeholder with the solved camera
props.focal_mode = "MANUAL"
H.check(props.invalid_pair == -1, f"manual focal still invalid: {props.status}")
H.check(H.camera_a() == cam and cam.matrix_world != before, "camera A not updated after a valid solve")

print("calibrate placeholder ok")
