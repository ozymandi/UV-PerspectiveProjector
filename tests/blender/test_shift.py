"""Lens shift: parallel verticals with an off-centre horizon give a level camera A with shift,
and Project / Remap through the shifted camera A still match the photo."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from bl_ext.user_default.perspective_projector.blender import calibration  # noqa: E402
from bl_ext.user_default.perspective_projector.core import solve  # noqa: E402

W, HT = 4000, 3000
PP = (W / 2.0, HT / 2.0 - 0.15 * HT)  # horizon 15 % of the height above the centre


def norm(p):
    return (float(p[0]) / W, float(p[1]) / HT)


def set_lines(props, synth, axes):
    src = {"X": ((1, 0, 0), [(-2.0, 2.0, 0.0), (-2.0, 4.0, 2.5)]),
           "Y": ((0, 1, 0), [(2.0, 2.0, 0.0), (4.0, 2.0, 2.5)]),
           "Z": ((0, 0, 1), [(-1.5, 6.0, 0.0), (2.5, 6.0, 0.0)])}
    values = []
    for a in axes:
        d, starts = src[a]
        for s in starts:
            p, q = synth.segment(s, d, 2.0)
            values += [*norm(p), *norm(q)]
    props.lock_updates = True
    props.lines = values
    props.pair0_axis, props.pair1_axis = axes
    props.lock_updates = False


def calibrate_synth(synth, path, axes, manual=True):
    H.load(path)
    props = H.props()
    set_lines(props, synth, axes)
    props.lock_updates = True
    if manual:
        props.focal_mode = "MANUAL"
        props.focal_35mm = synth.f * solve.FILM_DIAGONAL_MM / float(np.hypot(W, HT))
    props.camera_height = float(synth.location[2])
    props.origin = norm(synth.project((0.0, 0.0, 0.0)))
    props.origin_set = True
    props.calibrated = True
    props.lock_updates = False
    ok = calibration.reapply(bpy.context.scene)
    H.check(ok, f"calibration failed: {props.status}")
    return props, H.camera_a()


def check_matches(cam, synth, label):
    for p in [(0.0, 0.0, 0.0), (1.0, 5.0, 0.0), (-2.0, 9.0, 2.0), (3.0, 4.0, 1.0)]:
        got = H.to_frame(cam, p) * [W, HT]
        want = synth.project(p)
        H.check(np.abs(got - want).max() < 1.0, f"{label}: {p} -> {got} vs {want}")


# ---- one-point layout with parallel verticals (X + Z pairs, manual focal)
H.reset_scene()
path, synth = H.make_photo(name="shift1.png", yaw_deg=-3, pitch_deg=0.0, focal_px=2200, pp=PP)
props, cam = calibrate_synth(synth, path, ("X", "Z"))
H.check(abs(cam.data.shift_x) < 1e-4, f"shift_x {cam.data.shift_x}")
H.check(abs(cam.data.shift_y - (PP[1] - HT / 2.0) / W) < 1e-4, f"shift_y {cam.data.shift_y}")
view = np.array(cam.matrix_world.to_3x3()) @ np.array([0.0, 0.0, -1.0])
H.check(abs(view[2]) < 1e-5, f"camera A is not level: {view}")
check_matches(cam, synth, "one-point shifted")
H.check(props.shift_source == "vertical", f"shift source {props.shift_source!r}")
H.check(props.focal_source.startswith("manual"), f"focal source {props.focal_source!r}")

# ---- two horizontal VPs, focal from the VPs; verticals parallel is detected from the Z pair only,
# so with X + Y pairs the centre is kept (no Z information) - converging case keeps zero shift
H.reset_scene()
path, synth = H.make_photo(name="tilt.png", yaw_deg=-35, pitch_deg=-14, focal_px=3000)
props, cam = calibrate_synth(synth, path, ("X", "Z"), manual=False)
H.check(cam.data.shift_x == 0.0 and cam.data.shift_y == 0.0, "converging verticals got a shift")
H.check(props.shift_source == "" and props.focal_source == "vanishing points",
        f"converging case reported {props.focal_source!r} / {props.shift_source!r}")
check_matches(cam, synth, "converging")

# ---- Project and Remap through a shifted camera A
H.reset_scene()
path, synth = H.make_photo(name="shift2.png", yaw_deg=-30, pitch_deg=0.0, focal_px=2400, pp=PP)
props, cam = calibrate_synth(synth, path, ("X", "Z"))
scene = bpy.context.scene
H.set_eevee(scene)
for o in bpy.context.selected_objects:
    o.select_set(False)
bpy.ops.perspective_projector.project()
plane = next(o for o in scene.objects if o.get("pp_role") == "PLANE")
corners = H.corners_in_view(cam, plane)
H.check(np.allclose([c for xy in corners for c in xy], [0, 0, 0, 1, 1, 0, 1, 1], atol=2e-3),
        f"plane does not fill the shifted frame: {corners}")

photo = H.photo_gray_resized(path, (W // 4, HT // 4))
render = H.render_camera(cam, "shift_project")
gray = render[..., :3].mean(axis=2)
diff = float(np.abs(gray - photo).mean())
print("shifted project vs photo", diff)
H.check(diff < 0.03, f"render through shifted camera A differs from the photo: {diff}")

plane.select_set(True)
bpy.context.view_layer.objects.active = plane
props.remap_resolution = 1024
H.check(bpy.ops.perspective_projector.remap() == {"FINISHED"}, "remap failed")
after = H.render_camera(cam, "shift_remap")[..., :3].mean(axis=2)
d2 = float(np.abs(after - photo).mean())
print("shifted remap vs photo", d2)
H.check(d2 < 0.035, f"remapped render through shifted camera A differs: {d2}")

print("shift ok")
