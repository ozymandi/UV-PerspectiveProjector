"""Group 7: Remap."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def role(r):
    return [o for o in bpy.context.scene.objects if o.get("pp_role") == r]


def deselect():
    for o in bpy.context.selected_objects:
        o.select_set(False)


def select_only(*objs):
    deselect()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


H.reset_scene()
path, synth = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
H.load(path)
bpy.ops.perspective_projector.calibrate(open_editor=False)
scene = bpy.context.scene
H.set_eevee(scene)
deselect()
bpy.ops.perspective_projector.project()
plane = role("PLANE")[0]
cam_a = H.camera_a()
cam_b = role("CAMERA_B")[0]
props = H.props()

# ---- auto resolution for the frame-filling plane: ~4000 px of photo -> 4096
from bl_ext.user_default.perspective_projector.blender import remap as remap_mod  # noqa: E402

uv_name, _ = "ProjUV", None

# ---- photo coverage counts faces that reach behind camera A
covered = remap_mod.projected_pixels(scene, cam_a, plane)
H.check(abs(covered - 4000 * 3000) / (4000 * 3000) < 0.01, f"frame-filling plane covers {covered} px")
ground = cam_a.matrix_world.translation.copy()
ground.z = 0.0
fwd = cam_a.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
fwd.z = 0.0
fwd.normalize()
side = Vector((fwd.y, -fwd.x, 0.0))
corners = [ground - fwd * 2 - side * 20, ground - fwd * 2 + side * 20,
           ground + fwd * 60 + side * 20, ground + fwd * 60 - side * 20]
me = bpy.data.meshes.new("behind_floor")
me.from_pydata([tuple(c) for c in corners], [], [(0, 1, 2, 3)])
behind = bpy.data.objects.new("behind_floor", me)
scene.collection.objects.link(behind)
bpy.context.view_layer.update()
behind_px = remap_mod.projected_pixels(scene, cam_a, behind)
print("floor reaching behind camera A covers", behind_px)
H.check(behind_px > 0.2 * 4000 * 3000, f"floor reaching behind camera A covers only {behind_px} px")
bpy.data.objects.remove(behind)

before_a = H.render_camera(cam_a, "remap_before_a")

# ---- 7.1 / 7.2 / 7.3 remap the plane (unsaved file -> packed)
props.remap_resolution = 1024
select_only(plane)
res = bpy.ops.perspective_projector.remap()
H.check(res == {"FINISHED"}, f"remap {res}")
H.check("RemapUV" in plane.data.uv_layers, "no RemapUV created for the plane")
H.check("ProjUV" not in plane.data.uv_layers, "projection UV map left behind")
H.check("PP_UVProject" not in plane.modifiers, "UV Project modifier not removed")
H.check("PP_Subdivision" in plane.modifiers, "subdivision removed")
mat = plane.data.materials[0]
img = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
H.check(tuple(img.size) == (1024, 1024), f"image size {tuple(img.size)}")
H.check(img.packed_file is not None, "image not packed in an unsaved file")
H.check(scene.render.engine.startswith("BLENDER_EEVEE"), f"engine changed to {scene.render.engine}")
uvs = [n for n in mat.node_tree.nodes if n.type == "UVMAP"]
H.check(uvs and uvs[0].uv_map == "RemapUV", "material does not use RemapUV")

after_a = H.render_camera(cam_a, "remap_after_a")
diff = float(np.abs(after_a[..., :3] - before_a[..., :3]).mean())
print("through A before/after remap", diff)
H.check(diff < 0.02, f"remapped render differs: {diff}")

# auto resolution check on the remapped plane's UVs
auto = remap_mod.auto_resolution(scene, cam_a, plane, "RemapUV")
print("auto resolution for the plane", auto)
H.check(auto == 4096, f"auto resolution {auto}")

# ---- texture moves with the object: move plane and camera B together -> same picture
before_b = H.render_camera(cam_b, "remap_b0")
offset = Vector((3.0, -1.0, 0.5))
plane.location += offset
cam_b.location += offset
bpy.context.view_layer.update()
moved_b = H.render_camera(cam_b, "remap_b1")
d_move = float(np.abs(moved_b[..., :3] - before_b[..., :3]).mean())
print("move together diff", d_move)
H.check(d_move < 0.005, f"texture slid on the plane: {d_move}")
plane.location -= offset
cam_b.location -= offset
bpy.context.view_layer.update()

# ---- camera A deleted: render through B unchanged
cam_b.location.x += 1.0
bpy.context.view_layer.update()
b_with_a = H.render_camera(cam_b, "remap_b_with_a")
bpy.data.objects.remove(cam_a)
b_without_a = H.render_camera(cam_b, "remap_b_without_a")
d_del = float(np.abs(b_without_a[..., :3] - b_with_a[..., :3]).mean())
H.check(d_del < 0.002, f"deleting camera A changed the remapped object: {d_del}")

# ---- new scene: object with its own UVs, saved file, skip, alpha
H.reset_scene()
path, synth = H.make_photo(name="scene2.png", yaw_deg=-35, pitch_deg=-14, focal_px=3000)
H.load(path)
bpy.ops.perspective_projector.calibrate(open_editor=False)
scene = bpy.context.scene
H.set_eevee(scene)
blend = os.path.join(H.TMP, "remap_saved.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
props = H.props()
props.remap_resolution = 1024

bpy.ops.mesh.primitive_cube_add(size=1.5, location=(1.0, 6.0, 0.75))
cube = bpy.context.object
H.check("UVMap" in cube.data.uv_layers, "primitive cube has no UVs")
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 8, 0))
floor = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(location=(-3, 5, 1))
sphere = bpy.context.object  # never projected
select_only(cube, floor)
bpy.ops.perspective_projector.project()
select_only(cube, floor, sphere)
bpy.ops.perspective_projector.remap()
H.check("RemapUV" not in cube.data.uv_layers and "UVMap" in cube.data.uv_layers, "cube got a new unwrap")
H.check(cube.data.materials[0].name.startswith("PP_Remap"), "cube not remapped")
H.check("skipped" in props.status and sphere.name in props.status, props.status)
H.check(not sphere.modifiers and not sphere.data.materials, "sphere was changed")

tex_dir = os.path.join(H.TMP, "textures")
for o in (cube, floor):
    png = os.path.join(tex_dir, f"{o.name}_remap.png")
    H.check(os.path.isfile(png), f"missing {png}")
    img = next(n.image for n in o.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    H.check(img.filepath.startswith("//"), f"image path not relative: {img.filepath}")
    H.check(img.packed_file is None, "image packed although the file is saved")

# floor is partly outside camera A's frame: its baked alpha has both transparent and opaque texels
fimg = next(n.image for n in floor.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
px = np.empty(fimg.size[0] * fimg.size[1] * 4, dtype=np.float32)
fimg.pixels.foreach_get(px)
alpha = px[3::4]
print("floor alpha: transparent", float((alpha < 0.05).mean()), "opaque", float((alpha > 0.95).mean()))
H.check((alpha < 0.05).mean() > 0.05 and (alpha > 0.95).mean() > 0.05, "alpha not kept")

print("remap ok")
