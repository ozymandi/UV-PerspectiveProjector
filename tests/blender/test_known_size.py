"""Known size: focal length and scale from two ground segments in a one-point photo."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from bl_ext.user_default.perspective_projector.blender import calibration  # noqa: E402

W, HT = 4000, 3000
F_TRUE = 2200.0


def norm(p):
    return (float(p[0]) / W, float(p[1]) / HT)


H.reset_scene()
# one-point view: looking (almost) straight along +Y, parallel verticals, horizon above centre
path, synth = H.make_photo(name="onepoint.png", yaw_deg=-1.0, pitch_deg=0.0, focal_px=F_TRUE,
                           pp=(W / 2.0, HT * 0.42))
H.load(path)
props = H.props()
scene = bpy.context.scene

vals = []
for start in ((-2.0, 1.0, 0.0), (3.0, 1.0, 0.0)):          # Y (depth) lines on the floor
    p, q = synth.segment(start, (0, 1, 0), 4.0)
    vals += [*norm(p), *norm(q)]
for start in ((-2.0, 6.0, 0.0), (3.0, 6.0, 0.0)):          # Z lines (parallel in the photo)
    p, q = synth.segment(start, (0, 0, 1), 2.0)
    vals += [*norm(p), *norm(q)]
props.lock_updates = True
props.lines = vals
props.pair0_axis, props.pair1_axis = "Y", "Z"
props.focal_mode = "AUTO"
props.exif_focal_px = 1000.0  # EXIF present but wrong: known size must win
props.exif_label = "EXIF test"
props.origin = norm(synth.project((0.0, 0.0, 0.0)))
props.origin_set = True
# segment A: 1.2 m along depth, segment B: 0.6 m across
props.size_a_p0, props.size_a_p1 = norm(synth.project((0.5, 2.0, 0.0))), norm(synth.project((0.5, 3.2, 0.0)))
props.size_b_p0, props.size_b_p1 = norm(synth.project((-0.1, 2.0, 0.0))), norm(synth.project((0.5, 2.0, 0.0)))
props.size_a_length, props.size_b_length = 1.2, 0.6
props.size_enabled = True
props.calibrated = True
props.lock_updates = False

H.check(calibration.reapply(scene), f"known-size solve failed: {props.status}")
cam = H.camera_a()
true_lens = F_TRUE * 36.0 / W
print("lens", cam.data.lens, "true", true_lens, "height", props.effective_height, "source", props.focal_source)
H.check(abs(cam.data.lens - true_lens) / true_lens < 0.03, f"lens {cam.data.lens} vs {true_lens}")
H.check(props.focal_source == "known size", f"focal source {props.focal_source}")
H.check(abs(props.effective_height - synth.location[2]) / synth.location[2] < 0.03,
        f"height {props.effective_height} vs {synth.location[2]}")
H.check(abs(cam.data.shift_y) > 0.01, "parallel verticals with an off-centre horizon gave no shift")
H.check(props.shift_source == "vertical", f"shift source {props.shift_source!r}")
for p in [(0.5, 2.0, 0.0), (0.5, 3.2, 0.0), (-0.1, 2.0, 0.0), (1.0, 5.0, 1.0)]:
    got = H.to_frame(cam, p) * [W, HT]
    want = synth.project(p)
    H.check(np.abs(got - want).max() < 6.0, f"{p}: {got} vs {want}")

# without the known size the same photo falls back to EXIF
props.size_enabled = False
H.check(props.focal_source == "EXIF test", f"fallback source {props.focal_source}")
props.focal_mode = "MANUAL"
H.check(props.focal_source.startswith("manual"), f"manual source {props.focal_source}")
props.focal_mode = "AUTO"

# a segment above the horizon: flagged, camera keeps its last valid state
props.size_enabled = True
mat = np.array(cam.matrix_world)
props.size_a_p1 = (0.5, 0.05)
H.check(not calibration.reapply(scene), "segment above the horizon was accepted")
H.check("above the horizon" in props.status, props.status)
H.check(np.allclose(np.array(cam.matrix_world), mat, atol=1e-6), "camera changed on a failed known-size solve")

print("known size ok")
