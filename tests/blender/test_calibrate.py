"""Group 4: load photo, Calibrate, swap, height, origin, reference distance."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy

H.reset_scene()
path, synth = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
props = H.props()

# ---- 4.1 load photo
res = H.load(path)
H.check(res == {"FINISHED"}, f"load failed {res}")
H.check(tuple(props.image.size) == (4000, 3000), f"size {tuple(props.image.size)}")

bad = os.path.join(H.TMP, "bad.jpg")
with open(bad, "w") as fh:
    fh.write("not an image")
try:
    res = H.load(bad)
except RuntimeError:
    res = {"CANCELLED"}
H.check(res == {"CANCELLED"}, f"bad file accepted: {res}")
H.check(props.image is not None and tuple(props.image.size) == (4000, 3000), "previous photo lost")

# ---- 4.2 calibrate (twice) -> one camera A
for _ in range(2):
    res = bpy.ops.perspective_projector.calibrate(open_editor=False)
    H.check(res == {"FINISHED"}, f"calibrate {res}")
cams = [o for o in bpy.context.scene.objects if o.get("pp_role") == "CAMERA_A"]
H.check(len(cams) == 1, f"{len(cams)} camera A objects")
cam = cams[0]
r = bpy.context.scene.render
H.check((r.resolution_x, r.resolution_y, r.resolution_percentage) == (4000, 3000, 100), "resolution")
H.check(cam.data.background_images[0].image == props.image, "background image")
H.check(props.confidence >= 0.5, f"confidence {props.confidence}")
true_lens = synth.f * 36.0 / 4000
H.check(abs(cam.data.lens - true_lens) / true_lens < 0.03, f"lens {cam.data.lens} vs {true_lens}")
rot = H.rotation_np(cam)
for i in range(3):
    H.check(abs(np.dot(rot[i], synth.c2w[i])) > np.cos(np.radians(1.0)), f"axis {i} off")

# vertical edges map to Z: a vertical world segment projects onto a line through the Z VP;
# simpler check: the camera's up vector has positive world Z and roll is ~0 like the synth camera
H.check(rot[2, 1] > 0, "camera up vector points down")

# ---- 4.3 height keeps the view
props.camera_height = 1.6
origin_px_before = H.to_frame(cam, (0, 0, 0))
p_before = H.to_frame(cam, (1.0, 2.0, 0.0))
props.camera_height = 10.0
H.check(abs(cam.matrix_world.translation.z - 10.0) < 1e-4, "height not applied")
H.check(np.allclose(H.to_frame(cam, (0, 0, 0)), origin_px_before, atol=1e-4), "origin moved in view")
H.check(np.allclose(H.to_frame(cam, (1.0 * 10 / 1.6, 2.0 * 10 / 1.6, 0.0)), p_before, atol=1e-4),
        "scaled point moved in view")
props.camera_height = 1.6

# ---- swap X/Y keeps the view
pt = H.to_frame(cam, (1.0, 2.0, 0.0))
bpy.ops.perspective_projector.swap_xy()
H.check(np.allclose(H.to_frame(cam, (2.0, -1.0, 0.0)), pt, atol=1e-4), "swap changed the view")
bpy.ops.perspective_projector.swap_xy()
H.check(np.allclose(H.to_frame(cam, (1.0, 2.0, 0.0)), pt, atol=1e-4), "double swap not identity")

# ---- origin picked on the photo
corner_px = synth.project((2.0, 3.0, 0.0))
props.origin = (corner_px[0] / 4000, corner_px[1] / 3000)
props.origin_set = True
H.check(np.allclose(H.to_frame(cam, (0, 0, 0)), props.origin, atol=2e-3), "origin not at picked pixel")

# ---- reference distance: 3 m along the world X axis on the ground, from the picked corner
p0 = synth.project((2.0, 3.0, 0.0))
p1 = synth.project((5.0, 3.0, 0.0))
props.ref_p0 = (p0[0] / 4000, p0[1] / 3000)
props.ref_p1 = (p1[0] / 4000, p1[1] / 3000)
props.ref_axis = "X"
props.ref_distance = 3.0
props.ref_enabled = True
H.check(abs(props.effective_height - 1.6) / 1.6 < 0.03, f"reference height {props.effective_height}")
# the two marked points are 3 m apart in the scene: (0,0,0) and (3,0,0) project to them
H.check(np.allclose(H.to_frame(cam, (3.0, 0, 0)), props.ref_p1, atol=3e-3), "reference end not 3 m along X")

print("calibrate ok")
