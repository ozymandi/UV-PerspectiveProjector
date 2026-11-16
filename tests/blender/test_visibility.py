"""Remap visibility mask: occlusion, back faces, light isolation, grazing threshold, Hidden input."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

RES = 512


def deselect():
    for o in bpy.context.selected_objects:
        o.select_set(False)


def select_only(*objs):
    deselect()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def setup(name):
    H.reset_scene()
    path, synth = H.make_photo(name=name, yaw_deg=-35, pitch_deg=-14, focal_px=3000)
    H.load(path)
    bpy.ops.perspective_projector.calibrate(open_editor=False)
    scene = bpy.context.scene
    H.set_eevee(scene)
    H.props().remap_resolution = RES
    cam = H.camera_a()
    f = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    f.z = 0
    f.normalize()
    r = Vector((f.y, -f.x, 0))
    base = cam.matrix_world.translation.copy()
    base.z = 0
    return scene, cam, f, r, base


def quad(name, pts):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], [], [(0, 1, 2, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, centre, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=tuple(centre))
    ob = bpy.context.object
    ob.name = name
    ob.scale = tuple(size)
    bpy.ops.object.transform_apply(scale=True)
    me = ob.data
    while me.uv_layers:  # no own UVs: Remap makes its own unwrap
        me.uv_layers.remove(me.uv_layers[0])
    return ob


def wall(f, r, base, dist=10.0, half=4.0, height=4.0):
    c = base + f * dist
    return quad("Wall", [c - r * half, c + r * half, c + r * half + Vector((0, 0, height)),
                         c - r * half + Vector((0, 0, height))])


def project(*objs):
    select_only(*objs)
    H.check(bpy.ops.perspective_projector.project() == {"FINISHED"}, "project failed")


def remap(*objs):
    select_only(*objs)
    H.check(bpy.ops.perspective_projector.remap() == {"FINISHED"}, "remap failed")


def project_remap(*objs):
    project(*objs)
    remap(*objs)


def arrays(obj):
    mat = obj.data.materials[0]
    tex = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.name != "PP_VisMask")
    vis = mat.node_tree.nodes["PP_VisMask"].image
    n = tex.size[0] * tex.size[1]
    rgba = np.empty(n * 4, dtype=np.float32)
    tex.pixels.foreach_get(rgba)
    m = np.empty(vis.size[0] * vis.size[1] * 4, dtype=np.float32)
    vis.pixels.foreach_get(m)
    return rgba.reshape(-1, 4), m[0::4]


def black_fraction(obj):
    rgba, mask = arrays(obj)
    inside = rgba[:, 3] > 0.5
    return float((mask[inside] < 0.5).mean()), float(inside.mean())


def expected_hidden(scene, cam, pts_fn, target, n=60):
    """Fraction of in-frame points on ``target`` that camera A cannot see (ray hits another object first)."""
    o = cam.matrix_world.translation
    dg = bpy.context.evaluated_depsgraph_get()
    total = hidden = 0
    for i in range(n):
        for j in range(n):
            p = pts_fn((i + 0.5) / n, (j + 0.5) / n)
            uv = H.to_frame(cam, p)
            if not (0 < uv[0] < 1 and 0 < uv[1] < 1):
                continue
            total += 1
            d = (p - o)
            dist = d.length
            hit, loc, _nrm, _idx, ob, _m = scene.ray_cast(dg, o, d.normalized(), distance=dist - 1e-3)
            if hit and ob != target:
                hidden += 1
    return hidden / max(total, 1)


# ---- 1.1 a box in front of a wall: the wall's shadow from camera A is hidden
scene, cam, f, r, base = setup("vis1.png")
w = wall(f, r, base)
b = box("Box", base + f * 6.0 + Vector((0, 0, 0.75)), (1.5, 1.5, 1.5))
c = base + f * 10.0
expect = expected_hidden(scene, cam, lambda s, t: c + r * (8 * s - 4) + Vector((0, 0, 4 * t)), w)
project(w, b)
before_a = H.render_camera(cam, "vis_before_a")  # live projection, as test_remap does
remap(w, b)
got, _ = black_fraction(w)
print("wall hidden fraction", got, "expected", expect)
H.check(expect > 0.05, f"test geometry does not occlude the wall: {expect}")
H.check(abs(got - expect) < 0.02, f"wall mask hides {got:.3f}, ray casting says {expect:.3f}")

# back faces of the box are hidden, faces towards camera A are seen
box_black, _ = black_fraction(b)
print("box hidden fraction", box_black)
H.check(0.4 < box_black < 0.6, f"box mask: {box_black:.3f} hidden, expected about half (3 of 6 faces)")

# ---- 3.1 mask saved / packed; 1.2 helper light gone, nothing else changed
vis = b.data.materials[0].node_tree.nodes["PP_VisMask"].image
H.check(vis.packed_file is not None, "mask not packed in an unsaved file")
H.check(vis.colorspace_settings.name == "Non-Color", "mask colour space")
H.check(not [o for o in scene.objects if o.type == "LIGHT"], "a helper light was left in the scene")

# ---- 3.2 render through camera A unchanged
after_a = H.render_camera(cam, "vis_after_a")
d = float(np.abs(after_a[..., :3] - before_a[..., :3]).mean())
print("through A before/after", d)
H.check(d < 0.02, f"render through camera A changed: {d}")

# Hidden colour = median of visible texels; back faces render flat in that colour
rgba, mask = arrays(b)
seen = (mask > 0.5) & (rgba[:, 3] > 0.5)
median = np.median(rgba[seen, :3], axis=0)
hidden_node = b.data.materials[0].node_tree.nodes["Hidden"]
H.check(np.allclose(hidden_node.outputs[0].default_value[:3], median, atol=1e-3), "Hidden is not the median")
back = bpy.data.objects.new("BackCam", bpy.data.cameras.new("BackCam"))
scene.collection.objects.link(back)
back.location = b.location + f * 6.0  # at the box's mid height: sees only faces camera A cannot see
back.rotation_euler = (b.location - back.location).to_track_quat("-Z", "Y").to_euler()
for o in (w,):
    o.hide_render = True
# Cycles for the back views: EEVEE's blended surfaces do not sort faces within one object,
# so the box's front faces would show through its back faces there
engine = scene.render.engine
scene.render.engine = "CYCLES"
scene.cycles.samples = 8
img = H.render_camera(back, "vis_back", transparent=True)
opaque = img[..., 3] > 0.9
col = img[opaque][:, [2, 1, 0]].mean(axis=0)  # BGRA -> RGB
# the render is in display space (Standard view transform): compare after the same transfer
srgb = np.where(median <= 0.0031308, median * 12.92, 1.055 * np.power(median, 1 / 2.4) - 0.055)
print("back faces", col, "hidden", srgb, "opaque px", int(opaque.sum()))
H.check(opaque.sum() > 500, "back camera does not see the box")
H.check(np.abs(col - srgb).max() < 0.1, f"back faces {col} are not the flat Hidden colour {srgb}")

# custom Hidden texture: link a red image into the Hidden input
mat = b.data.materials[0]
red = bpy.data.images.new("red", 8, 8)
red.pixels.foreach_set(np.tile([1.0, 0.0, 0.0, 1.0], 64).astype(np.float32))
tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
tn.image = red
mix = next(n for n in mat.node_tree.nodes if n.type == "MIX" and n.data_type == "RGBA")
mat.node_tree.links.new(tn.outputs["Color"], mix.inputs["A"])
img = H.render_camera(back, "vis_back_red", transparent=True)
col = img[img[..., 3] > 0.9][:, [2, 1, 0]].mean(axis=0)
print("back faces with red Hidden", col)
H.check(col[0] > 0.8 and col[1] < 0.2 and col[2] < 0.2, f"Hidden texture not shown on hidden areas: {col}")
scene.render.engine = engine
w.hide_render = False
after_red = H.render_camera(cam, "vis_after_red_a")
H.check(float(np.abs(after_red[..., :3] - before_a[..., :3]).mean()) < 0.02,
        "custom Hidden texture changed the view through camera A")

# ---- 1.2 isolation: a strong sun does not change the mask; the card does not shadow
masks = []
for with_sun in (False, True):
    scene, cam, f, r, base = setup("vis2.png")
    w = wall(f, r, base)
    b = box("Box", base + f * 6.0 + Vector((0, 0, 0.75)) + r * 1.5, (1.5, 1.5, 1.5))
    deselect()
    bpy.ops.perspective_projector.project()  # frame-filling card in front of everything
    card = next(o for o in scene.objects if o.get("pp_role") == "PLANE")
    sun = None
    if with_sun:
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
        sun.data.energy = 20.0
        sun.rotation_euler = (0.9, 0.0, 2.2)
        scene.collection.objects.link(sun)
    project_remap(w, b)
    masks.append(arrays(w)[1])
    H.check(not card.hide_render, "projection card left hidden from render")
    if sun is not None:
        H.check(not sun.hide_render, "user light left hidden from render")
        H.check([o.name for o in scene.objects if o.type == "LIGHT"] == ["Sun"], "helper light left behind")
diff = float((np.abs(masks[0] - masks[1]) > 0.5).mean())
print("mask difference with / without sun", diff)
H.check(diff < 0.005, f"user light changed the mask in {diff:.3%} of texels")
H.check(float((masks[0] < 0.5).mean()) < 0.9, "the projection card shadowed the wall")

# ---- 2.1 grazing threshold on a shallow floor
fracs = {}
for deg in (0.0, 5.0):  # camera at 1.6 m: the floor drops below 5 degrees beyond about 18 m
    scene, cam, f, r, base = setup("vis3.png")
    floor = quad("Floor", [base + f * 2 - r * 6, base + f * 2 + r * 6, base + f * 40 + r * 6, base + f * 40 - r * 6])
    H.props().remap_grazing_deg = deg
    project_remap(floor)
    fracs[deg] = black_fraction(floor)[0]
print("floor hidden fraction by threshold", fracs)
H.check(fracs[0.0] < 0.01, f"default threshold hid {fracs[0.0]:.3f} of a fully visible floor")
H.check(0.05 < fracs[5.0] < 0.95, f"5 degrees should hide the far part only: {fracs[5.0]:.3f}")

# ---- 3.3 contact seam: a box standing on a floor
res = {}
for with_floor in (False, True):
    scene, cam, f, r, base = setup("vis4.png")
    b = box("Box", base + f * 7.0 + Vector((0, 0, 0.75)), (1.5, 1.5, 1.5))
    objs = [b]
    if with_floor:
        floor = quad("Floor", [base + f * 3 - r * 4, base + f * 3 + r * 4, base + f * 12 + r * 4,
                               base + f * 12 - r * 4])
        objs.append(floor)
        a0, a1 = base + f * 3 - r * 4, f * 9
        expect = expected_hidden(scene, cam, lambda s, t: a0 + r * (8 * s) + a1 * t, floor)
    project_remap(*objs)
    res[with_floor] = black_fraction(b)[0]
    if with_floor:
        fl = black_fraction(floor)[0]
        print("floor hidden", fl, "expected", expect)
        H.check(abs(fl - expect) < 0.02, f"floor mask hides {fl:.3f}, ray casting says {expect:.3f}")
print("box hidden without / with floor", res)
H.check(abs(res[True] - res[False]) < 0.02, f"standing on the floor changed the box mask: {res}")

# ---- 3.1 saved .blend: the mask is written next to the texture and referenced by the material
scene, cam, f, r, base = setup("vis5.png")
w = wall(f, r, base)
blend = os.path.join(H.TMP, "vis_saved.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
project_remap(w)
png = os.path.join(H.TMP, "textures", "Wall_vis.png")
H.check(os.path.isfile(png), f"missing {png}")
vis = w.data.materials[0].node_tree.nodes["PP_VisMask"].image
H.check(vis.packed_file is None and vis.filepath.startswith("//"), f"mask not saved as a relative file: {vis.filepath}")
H.check(os.path.isfile(os.path.join(H.TMP, "textures", "Wall_remap.png")), "texture missing next to the mask")

print("visibility ok")
