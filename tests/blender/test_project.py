"""Group 6: Project."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

FRAME = [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)]


def role(r):
    return [o for o in bpy.context.scene.objects if o.get("pp_role") == r]


def deselect():
    for o in bpy.context.selected_objects:
        o.select_set(False)


def setup(name="scene.png", **cam):
    H.reset_scene()
    path, synth = H.make_photo(name=name, **cam)
    H.load(path)
    bpy.ops.perspective_projector.calibrate(open_editor=False)
    H.set_eevee(bpy.context.scene)
    return path, synth


def interp_error_px(obj, cam):
    """Max photo-pixel error between interpolated UVs and the true projection at face centres in the frame."""
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    uv = me.uv_layers["ProjUV"].data
    w, h = scene.render.resolution_x, scene.render.resolution_y
    errs = []
    for poly in me.polygons:
        loops = list(poly.loop_indices)
        uv_c = sum((Vector(uv[i].uv) for i in loops), Vector((0, 0))) / len(loops)
        t = H.to_frame(cam, obj.matrix_world @ poly.center)
        if not (0.02 < t[0] < 0.98 and 0.02 < t[1] < 0.98):
            continue
        errs.append(max(abs(uv_c.x - t[0]) * w, abs(uv_c.y - (1.0 - t[1])) * h))
    ev.to_mesh_clear()
    errs = np.array(errs)
    return float(errs.max()), float(np.median(errs)), float((errs > 2.0).mean())


# ---- 6.5 disabled without calibration
H.reset_scene()
path0, _ = H.make_photo(name="p0.png")
H.load(path0)
H.check(not bpy.ops.perspective_projector.project.poll(), "Project enabled before calibration")

# ---- 6.1 plane fills the frame (landscape)
path, synth = setup(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
deselect()
res = bpy.ops.perspective_projector.project()
H.check(res == {"FINISHED"}, f"project {res}")
cam_a = H.camera_a()
planes = role("PLANE")
H.check(len(planes) == 1, f"{len(planes)} planes")
plane = planes[0]
H.check(np.allclose(H.corners_in_view(cam_a, plane), FRAME, atol=1e-4), f"corners {H.corners_in_view(cam_a, plane)}")
dims = plane.dimensions
H.check(abs(dims.x / dims.y - 4 / 3) < 1e-3, f"plane ratio {dims.x / dims.y}")

props = H.props()
props.plane_distance = 25.0
H.check(np.allclose(H.corners_in_view(cam_a, plane), FRAME, atol=1e-4), "corners after distance change")
dist = (plane.matrix_world.translation - cam_a.matrix_world.translation).length
H.check(abs(dist - 25.0) < 1e-3, f"plane distance {dist}")

# the default card is perpendicular to camera A: no break even before subdivision
plane.modifiers["PP_Subdivision"].show_viewport = False
card_err = interp_error_px(plane, cam_a)
plane.modifiers["PP_Subdivision"].show_viewport = True
print("card interpolation error px", card_err)
H.check(card_err[0] < 0.5, f"card bends: {card_err}")

# ---- 6.4 camera B
cams_b = role("CAMERA_B")
H.check(len(cams_b) == 1, "camera B missing")
cam_b = cams_b[0]
H.check(bpy.context.scene.camera == cam_b, "camera B not active")
H.check(np.allclose(np.array(cam_b.matrix_world), np.array(cam_a.matrix_world), atol=1e-5), "camera B not at A")
H.check(abs(cam_b.data.lens - cam_a.data.lens) < 1e-6, "camera B lens")

# ---- 6.2 render through camera A matches the photo
mods = [m.type for m in plane.modifiers]
H.check(mods == ["SUBSURF", "UV_PROJECT"], f"modifier order {mods}")
H.check(plane.modifiers[0].subdivision_type == "SIMPLE", "subdivision is not simple")
render_a = H.render_camera(cam_a, "through_a")
gray = render_a[..., :3].mean(axis=2)
photo = H.photo_gray_resized(path, (gray.shape[1], gray.shape[0]))
err = float(np.abs(gray - photo).mean())
print("mean abs diff through A", err)
H.check(err < 0.02, f"render through A differs from the photo: {err}")

# ---- 6.3 a strong light does not change the photo
bpy.ops.object.light_add(type="POINT", location=plane.matrix_world.translation + Vector((0, 0, 3)))
bpy.context.object.data.energy = 100000
render_lit = H.render_camera(cam_a, "through_a_lit")
lit_err = float(np.abs(render_lit[..., :3] - render_a[..., :3]).mean())
H.check(lit_err < 0.002, f"light changed the projected photo: {lit_err}")
bpy.data.objects.remove(bpy.context.object)

# ---- outside camera A's frame renders transparent (camera B with a wider lens)
cam_b.data.lens = cam_a.data.lens / 2
wide = H.render_camera(cam_b, "wide_b", transparent=True)
h, w = wide.shape[:2]
border = np.concatenate([wide[: h // 8, :, 3].ravel(), wide[-h // 8:, :, 3].ravel(),
                         wide[:, : w // 8, 3].ravel(), wide[:, -w // 8:, 3].ravel()])
center = wide[3 * h // 8: 5 * h // 8, 3 * w // 8: 5 * w // 8, 3]
print("border alpha max", border.max(), "center alpha min", center.min())
H.check(border.max() < 0.01, "photo repeated outside the frame")
H.check(center.min() > 0.99, "photo missing inside the frame")
# Cycles treats alpha of alpha-less images differently: check it too
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 4
wide_c = H.render_camera(cam_b, "wide_b_cycles", percentage=10, transparent=True)
hc, wc = wide_c.shape[:2]
border_c = np.concatenate([wide_c[: hc // 8, :, 3].ravel(), wide_c[:, : wc // 8, 3].ravel()])
print("cycles border alpha max", border_c.max())
H.check(border_c.max() < 0.01, "Cycles: photo repeated outside the frame")
H.set_eevee(bpy.context.scene)
cam_b.data.lens = cam_a.data.lens

# ---- 6.2 no perspective break on a tilted surface (floor mesh)
deselect()
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 8, 0))
floor = bpy.context.object
floor.select_set(True)
bpy.ops.perspective_projector.project()
err_sub = interp_error_px(floor, cam_a)
floor.modifiers["PP_Subdivision"].show_viewport = False
err_raw = interp_error_px(floor, cam_a)
floor.modifiers["PP_Subdivision"].show_viewport = True
print("floor level", floor.modifiers["PP_Subdivision"].levels, "error px: subdivided", err_sub, "raw", err_raw)
# capped at level 6, a single 30 m quad reaching the camera still bends near the camera;
# the bulk of the floor must be within ~1 px
H.check(err_sub[1] < 1.0, f"median break on subdivided floor: {err_sub[1]:.2f} px")
H.check(err_sub[0] < err_raw[0] / 20, "subdivision does not reduce the break")

# ---- 6.4 selected meshes + light, camera B kept
deselect()
cam_b.location.x += 2.0
bpy.context.view_layer.update()
moved = np.array(cam_b.matrix_world)
boxes = []
for k in range(3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(k * 1.5 - 1.5, 6, 0.5))
    boxes.append(bpy.context.object)
bpy.ops.object.light_add(type="POINT", location=(0, 5, 3))
light = bpy.context.object
for o in boxes + [light]:
    o.select_set(True)
n_planes = len(role("PLANE"))
bpy.ops.perspective_projector.project()
H.check(all("PP_UVProject" in b.modifiers for b in boxes), "a box was not projected")
H.check(len(role("PLANE")) == n_planes, "a plane was created although meshes were selected")
H.check("skipped" in props.status and light.name in props.status, props.status)
H.check(len(role("CAMERA_B")) == 1, "second camera B created")
H.check(np.allclose(np.array(cam_b.matrix_world), moved, atol=1e-5), "camera B moved back")
dg = bpy.context.evaluated_depsgraph_get()
ev = boxes[0].evaluated_get(dg)
H.check(np.allclose(tuple(ev.dimensions), (1, 1, 1), atol=1e-5), f"box shape changed {tuple(ev.dimensions)}")

# ---- 6.1 portrait photo
path_p, _ = setup(name="portrait.png", yaw_deg=-50, pitch_deg=-8, focal_px=3600, width=3000, height=4000)
deselect()
bpy.ops.perspective_projector.project()
cam_a = H.camera_a()
plane = role("PLANE")[0]
H.check(np.allclose(H.corners_in_view(cam_a, plane), FRAME, atol=1e-4), "portrait corners")
r = H.render_camera(cam_a, "portrait_a")
g = r[..., :3].mean(axis=2)
photo = H.photo_gray_resized(path_p, (g.shape[1], g.shape[0]))
err_p = float(np.abs(g - photo).mean())
print("portrait mean abs diff", err_p)
H.check(err_p < 0.02, f"portrait render differs: {err_p}")

print("project ok")
