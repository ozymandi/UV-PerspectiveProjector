"""EEVEE draws the faces of projected and remapped objects in depth order (no faces through faces)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from bl_ext.user_default.perspective_projector.blender import projection  # noqa: E402


def select_only(*objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def render_both(cam, name):
    """(EEVEE, Cycles) renders through ``cam`` with transparent film."""
    scene = bpy.context.scene
    H.set_eevee(scene)
    ee = H.render_camera(cam, name + "_eevee", transparent=True)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    cy = H.render_camera(cam, name + "_cycles", transparent=True)
    H.set_eevee(scene)
    return ee, cy


def box_diff(ee, cy):
    """Mean colour difference on the pixels Cycles says are the box, and the box pixel count."""
    m = cy[..., 3] > 0.9
    return float(np.abs(ee[m][:, :3] - cy[m][:, :3]).mean()), int(m.sum())


H.reset_scene()
path, synth = H.make_photo(name="order.png", yaw_deg=-35, pitch_deg=-14, focal_px=3000)
H.load(path)
bpy.ops.perspective_projector.calibrate(open_editor=False)
scene = bpy.context.scene
H.props().remap_resolution = 512
cam = H.camera_a()
f = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
f.z = 0
f.normalize()
base = cam.matrix_world.translation.copy()
base.z = 0

bpy.ops.mesh.primitive_cube_add(size=1.5, location=tuple(base + f * 6 + Vector((0, 0, 0.75))))
box = bpy.context.object
while box.data.uv_layers:
    box.data.uv_layers.remove(box.data.uv_layers[0])
back = bpy.data.objects.new("Back", bpy.data.cameras.new("Back"))
scene.collection.objects.link(back)
back.location = box.location + f * 6.0
back.rotation_euler = (box.location - back.location).to_track_quat("-Z", "Y").to_euler()

# ---- 1.1 projection material is DITHERED; an old (version 2, BLENDED) material is not reused
select_only(box)
bpy.ops.perspective_projector.project()
mat = box.data.materials[0]
H.check(mat.surface_render_method == "DITHERED", f"projection material uses {mat.surface_render_method}")
H.check(mat.get("pp_version") == projection.MATERIAL_VERSION, "projection material version mark")

ee, cy = render_both(back, "live")
d_live, n_live = box_diff(ee, cy)
print("live projection, EEVEE vs Cycles from behind:", d_live, "box px", n_live)
H.check(n_live > 500, "back camera does not see the box")
H.check(d_live < 0.03, f"live projection: EEVEE differs from Cycles by {d_live:.3f}")

# ---- 1.2 / 2.1 remapped box: DITHERED, back faces are the flat Hidden colour in EEVEE
select_only(box)
bpy.ops.perspective_projector.remap()
rmat = box.data.materials[0]
H.check(rmat.surface_render_method == "DITHERED", f"remap material uses {rmat.surface_render_method}")
ee, cy = render_both(back, "remap")
d_remap, n_remap = box_diff(ee, cy)
hidden = np.array(rmat.node_tree.nodes["Hidden"].outputs[0].default_value[:3])
srgb = np.where(hidden <= 0.0031308, hidden * 12.92, 1.055 * np.power(hidden, 1 / 2.4) - 0.055)
m = cy[..., 3] > 0.9
col = ee[m][:, [2, 1, 0]].mean(axis=0)
print("remapped, EEVEE vs Cycles from behind:", d_remap, "EEVEE back colour", col, "Hidden", srgb)
H.check(d_remap < 0.03, f"remapped box: EEVEE differs from Cycles by {d_remap:.3f}")
H.check(np.abs(col - srgb).max() < 0.03, f"EEVEE back faces {col} are not the Hidden colour {srgb}")

# the test notices the old setting: BLENDED shows the front faces through the back faces
rmat.surface_render_method = "BLENDED"
ee_old, _ = render_both(back, "remap_blended")
d_old, _ = box_diff(ee_old, cy)
print("with the old BLENDED setting:", d_old)
H.check(d_old > 0.03, f"test does not detect the BLENDED face-order problem ({d_old:.3f})")
rmat.surface_render_method = "DITHERED"

# ---- 1.1 a file with an old projection material gets a new one on Project
old = projection.projection_material(H.props().image)
old["pp_version"] = 2
old.surface_render_method = "BLENDED"
bpy.ops.mesh.primitive_cube_add(size=1.0, location=tuple(base + f * 9 + Vector((2, 0, 0.5))))
box2 = bpy.context.object
select_only(box2)
bpy.ops.perspective_projector.project()
new = box2.data.materials[0]
H.check(new != old, "old projection material was reused")
H.check(new.surface_render_method == "DITHERED" and new.get("pp_version") == projection.MATERIAL_VERSION,
        f"new projection material: {new.surface_render_method}, version {new.get('pp_version')}")

print("face order ok")
