"""Blockout tools driven with photo coordinates: hits, floor, walls, boxes, ceiling, reference corner, panel."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from bl_ext.user_default.perspective_projector.blender import blockout as BL  # noqa: E402
from bl_ext.user_default.perspective_projector.blender import ui  # noqa: E402

W, HT = 4000, 3000


def setup():
    """Calibrated scene whose world matches the synthetic camera's world."""
    H.reset_scene()
    path, synth = H.make_photo(name="blockout.png", yaw_deg=-35, pitch_deg=-14, focal_px=3000)
    H.check(not bpy.ops.perspective_projector.blockout_box.poll(), "Box tool enabled before calibration")
    H.load(path)
    bpy.ops.perspective_projector.calibrate(open_editor=False)
    props = H.props()
    p0 = synth.project((0.0, 0.0, 0.0))
    props.origin = (p0[0] / W, p0[1] / HT)
    props.origin_set = True
    props.camera_height = float(synth.location[2])
    # make camera A exactly the synthetic camera, so positions test the blockout and not the calibration
    cam = H.camera_a()
    m = Matrix([list(r) for r in synth.c2w]).to_4x4()
    m.translation = Vector(tuple(synth.location))
    cam.matrix_world = m
    cam.data.sensor_fit, cam.data.sensor_width = "HORIZONTAL", 36.0
    cam.data.lens = synth.f * 36.0 / W
    cam.data.shift_x = cam.data.shift_y = 0.0
    bpy.context.view_layer.update()
    return path, synth, cam


def uv(synth, p):
    q = synth.project(p)
    return (float(q[0]) / W, float(q[1]) / HT)


def pts(*uvs):
    return [{"name": str(i), "uv": u} for i, u in enumerate(uvs)]


def verts(ob):
    return [np.array(ob.matrix_world @ v.co) for v in ob.data.vertices]


def has_point(ob, p, tol=0.02):
    return min(np.linalg.norm(v - np.asarray(p)) for v in verts(ob)) < tol


def reproj_px(cam, ob, uvs):
    """Max distance in pixels from each clicked point to the nearest projected vertex."""
    vv = [H.to_frame(cam, v) * [W, HT] for v in verts(ob)]
    return max(min(np.linalg.norm(v - np.array(u) * [W, HT]) for v in vv) for u in uvs)


def last(prefix):
    obs = sorted(o.name for o in bpy.data.objects if o.name.startswith(prefix + "."))
    return bpy.data.objects[obs[-1]]


path, synth, cam = setup()
scene = bpy.context.scene

# ---- 3.1 floor
floor_pts = [(-3, 2, 0), (3, 2, 0), (3, 9, 0), (-3, 9, 0)]
H.check(bpy.ops.perspective_projector.blockout_floor(points=pts(*[uv(synth, p) for p in floor_pts])) == {"FINISHED"},
        "floor tool failed")
floor = last("Floor")
for p in floor_pts:
    H.check(has_point(floor, p), f"floor misses corner {p}")
px = reproj_px(cam, floor, [uv(synth, p) for p in floor_pts])
print("floor reprojection px", px)
H.check(px < 1.0, f"floor corners off by {px:.2f} px")
H.check(floor.users_collection[0].name == "Blockout" and floor.name == "Floor.001", f"naming {floor.name}")

# ---- 2.1 hits: ground, then the top of a box
g = BL.hit(scene, cam, *uv(synth, (1.0, 5.0, 0.0)), surfaces=False)
H.check(g is not None and np.allclose(g.point, (1.0, 5.0, 0.0), atol=1e-3), f"ground hit {g and g.point}")

# ---- 3.2 walls: along X, and oblique (30 degrees, not snapped)
# (placed so that no ray to a clicked point passes through another blockout object)
wall = [(1.8, 6.0, 0.0), (3.8, 6.0, 0.0), (3.8, 6.0, 2.5)]
bpy.ops.perspective_projector.blockout_wall(points=pts(*[uv(synth, p) for p in wall]))
w1 = last("Wall")
for p in [(1.8, 6, 0), (3.8, 6, 0), (3.8, 6, 2.5), (1.8, 6, 2.5)]:
    H.check(has_point(w1, p), f"wall misses {p}")
H.check(reproj_px(cam, w1, [uv(synth, p) for p in wall]) < 2.0, "wall reprojection")
near_x = [(-4.5, 7.0, 0.0), (-2.5, 7.07, 0.0), (-2.5, 7.07, 2.0)]  # 2 degrees off X: snaps
bpy.ops.perspective_projector.blockout_wall(points=pts(*[uv(synth, p) for p in near_x]))
ys = {round(v[1], 3) for v in verts(last("Wall"))}
H.check(ys == {7.0}, f"near-axis wall not snapped to X: y = {ys}")
c, s = np.cos(np.radians(30)), np.sin(np.radians(30))
obl = [(-4.5, 3.0, 0.0), (-4.5 + 2 * c, 3.0 + 2 * s, 0.0), (-4.5 + 2 * c, 3.0 + 2 * s, 1.5)]
bpy.ops.perspective_projector.blockout_wall(points=pts(*[uv(synth, p) for p in obl]))
w3 = last("Wall")
H.check(has_point(w3, obl[1]) and has_point(w3, obl[2]), "oblique wall was snapped or misplaced")

# ---- 3.3 balcony on the wall along X (back face in the wall, front 0.8 m towards the camera)
balcony = [(2.0, 6.0, 0.8), (3.2, 6.0, 1.5), (3.2, 5.2, 1.5)]
H.check(bpy.ops.perspective_projector.blockout_box(points=pts(*[uv(synth, p) for p in balcony])) == {"FINISHED"},
        "balcony failed")
bal = last("Box")
H.check(has_point(bal, (2.0, 6.0, 0.8)) and has_point(bal, (3.2, 5.2, 1.5)), "balcony misplaced")
H.check(reproj_px(cam, bal, [uv(synth, balcony[2])]) < 2.0, "balcony front reprojection")

# ---- 3.3 boxes (built after the walls, nearer to the camera): bench, a table and a box on the table
bench = [(-2.0, 4.0, 0.0), (-0.8, 4.5, 0.0), (-0.8, 4.5, 0.5)]
H.check(bpy.ops.perspective_projector.blockout_box(points=pts(*[uv(synth, p) for p in bench])) == {"FINISHED"},
        "bench failed")
b = last("Box")
for p in [(-2, 4, 0), (-0.8, 4.5, 0), (-2, 4.5, 0.5), (-0.8, 4, 0.5)]:
    H.check(has_point(b, p), f"bench misses {p}")
H.check(reproj_px(cam, b, [uv(synth, p) for p in bench]) < 2.0, "bench reprojection")
table = [(0.0, 3.0, 0.0), (1.2, 4.0, 0.0), (1.2, 4.0, 0.75)]
bpy.ops.perspective_projector.blockout_box(points=pts(*[uv(synth, p) for p in table]))
t = last("Box")
top = BL.hit(scene, cam, *uv(synth, (0.6, 3.5, 0.75)))
H.check(top is not None and top.kind == "surface" and abs(top.point[2] - 0.75) < 1e-3,
        f"hit on the table top {top and (top.kind, top.point)}")
on_table = [(0.2, 3.2, 0.75), (0.6, 3.6, 0.75), (0.6, 3.6, 1.0)]
bpy.ops.perspective_projector.blockout_box(points=pts(*[uv(synth, p) for p in on_table]))
bt = last("Box")
zs = sorted({round(v[2], 3) for v in verts(bt)})
H.check(zs == [0.75, 1.0], f"box on the table spans {zs}")

# ---- 3.7 box from its near edge: a bench against the wall along X (its far footprint corner is hidden)
edge = [(2.2, 5.5, 0.0), (2.2, 5.5, 0.5), (3.4, 6.0, 0.5)]
H.check(bpy.ops.perspective_projector.blockout_box_edge(points=pts(*[uv(synth, p) for p in edge])) == {"FINISHED"},
        "box from edge failed")
be = last("Box")
for p in [(2.2, 5.5, 0.0), (3.4, 6.0, 0.0), (2.2, 5.5, 0.5), (3.4, 6.0, 0.5)]:
    H.check(has_point(be, p), f"box from edge misses {p}")
px = reproj_px(cam, be, [uv(synth, p) for p in edge])
print("box from edge reprojection px", px)
H.check(px < 2.0, f"box from edge off by {px:.2f} px")
try:
    bpy.ops.perspective_projector.blockout_box_edge(
        points=pts(uv(synth, (3.0, 6.0, 1.8)), uv(synth, (3.0, 6.0, 2.2)), uv(synth, (3.5, 6.0, 2.2))))
    refused = False
except RuntimeError as exc:
    refused = "floor or a box top" in str(exc)
H.check(refused, "box from edge accepted a corner on a wall")

# ---- 3.4 ceiling from a click on the wall; refused on the floor
H.check(bpy.ops.perspective_projector.blockout_ceiling(points=pts(uv(synth, (3.6, 6.0, 2.2)))) == {"FINISHED"},
        "ceiling failed")
ceil = last("Ceiling")
ch = BL.hit(scene, cam, *uv(synth, (3.6, 6.0, 2.2)), ground=False, reference=False)
H.check({round(float(v[2]), 3) for v in verts(ceil)} == {2.2},
        f"ceiling height {sorted({round(float(v[2]), 3) for v in verts(ceil)})}, click hit {ch.obj.name} at {ch.point}")
all_xy = np.array([v[:2] for o in BL.blockout_objects(scene) if o != ceil for v in verts(o)])
cxy = np.array([v[:2] for v in verts(ceil)])
H.check(np.allclose(cxy.min(axis=0), all_xy.min(axis=0)) and np.allclose(cxy.max(axis=0), all_xy.max(axis=0)),
        "ceiling does not span the blockout")
n_before = len(BL.blockout_objects(scene))
try:  # an ERROR report becomes RuntimeError when an operator is called from Python
    res = bpy.ops.perspective_projector.blockout_ceiling(points=pts(uv(synth, (2.0, 8.0, 0.0))))
except RuntimeError as exc:
    res = {"CANCELLED"}
    H.check("meets a wall" in str(exc), f"unexpected refusal message: {exc}")
H.check(res == {"CANCELLED"} and len(BL.blockout_objects(scene)) == n_before, "ceiling accepted a floor click")

# ---- 3.5 conventions, then Project + Remap render through camera A like the photo
for o in BL.blockout_objects(scene):
    H.check(not o.modifiers and not o.data.materials, f"{o.name} has modifiers or materials")
    H.check(o.name.split(".")[0] in {"Floor", "Wall", "Box", "Ceiling"}, f"name {o.name}")
ceil.hide_render = True  # it would cover the photo from above
objs = [o for o in BL.blockout_objects(scene) if o != ceil]
for o in scene.objects:
    o.select_set(o in objs)
bpy.context.view_layer.objects.active = objs[0]
H.check(bpy.ops.perspective_projector.project() == {"FINISHED"}, "project failed")
H.props().remap_resolution = 512
for o in scene.objects:
    o.select_set(o in objs)
H.check(bpy.ops.perspective_projector.remap() == {"FINISHED"}, "remap failed")
H.set_eevee(scene)
img = H.render_camera(cam, "blockout_remap", transparent=True)
photo = H.photo_gray_resized(path, (img.shape[1], img.shape[0]))
mask = img[..., 3] > 0.99
diff = float(np.abs(img[..., :3].mean(axis=2)[mask] - photo[mask]).mean())
print("remapped blockout vs photo through camera A", diff, "covered", float(mask.mean()))
H.check(mask.mean() > 0.02, f"blockout covers only {mask.mean():.3f} of the frame")  # objects are 10-17 m away
H.check(diff < 0.03, f"render through camera A differs from the photo: {diff}")

# ---- 2.3 reference corner: camera looking up at a facade, no ground in view
path, synth, cam = setup()
scene = bpy.context.scene
props = H.props()
cam.matrix_world = cam.matrix_world @ Matrix.Rotation(np.radians(40), 4, "X")  # tilt up
bpy.context.view_layer.update()
H.check(BL.hit(scene, cam, 0.5, 0.95, surfaces=False, reference=False) is None, "ground still in view")
cuv = (0.55, 0.6)
H.check(bpy.ops.perspective_projector.blockout_reference(points=pts(cuv)) == {"FINISHED"}, "reference pick failed")
H.check(props.blockout_ref_set, "reference corner not set")


def facade_wall(distance):
    props.blockout_ref_distance = distance
    props.blockout_ref_axis = "X"
    o, d = BL.photo_ray(scene, cam, *cuv)
    corner = o + d * distance
    world = [corner + np.array(p) for p in [(-3.0 * distance / 10, 0, 0), (2.0 * distance / 10, 0, 0),
                                             (2.0 * distance / 10, 0, 4.0 * distance / 10)]]
    uvs = [tuple(H.to_frame(cam, p)) for p in world]
    H.check(bpy.ops.perspective_projector.blockout_wall(points=pts(*uvs)) == {"FINISHED"}, "facade wall failed")
    ob = last("Wall")
    return ob, uvs, world


w10, uvs10, world10 = facade_wall(10.0)
for p in world10:
    H.check(has_point(w10, p, tol=0.05), f"facade wall misses {p}")
H.check(abs(np.ptp([v[1] for v in verts(w10)])) < 1e-4, "facade wall is not in the X reference plane")
px = reproj_px(cam, w10, uvs10)
print("facade wall reprojection px", px)
H.check(px < 2.0, f"facade wall off by {px:.2f} px")
v10 = sorted(verts(w10), key=lambda v: tuple(np.round(v, 3)))
bpy.data.objects.remove(w10)  # otherwise the same clicks land on it (blockout surfaces come first)
w20, uvs20, _ = facade_wall(20.0)
o = np.array(cam.matrix_world.translation)
v20 = sorted(verts(w20), key=lambda v: tuple(np.round(v, 3)))
H.check(all(np.allclose(b - o, 2 * (a - o), atol=1e-3) for a, b in zip(v10, v20)), "doubling the distance did not double the wall")
H.check(reproj_px(cam, w20, uvs10) < 2.0, "the wall's outline through camera A changed with the distance")

# ---- 4.2 panel: tools enabled after calibration; "scale assumed" only with a reference corner


class FakeLayout:
    def __init__(self, texts):
        self.texts, self.enabled = texts, True

    def label(self, text="", **kw):
        self.texts.append(text)

    def operator(self, *a, **kw):
        return type("Op", (), {})()

    def prop(self, *a, **kw):
        pass

    def __getattr__(self, name):  # row, column, box, grid_flow, separator
        return lambda *a, **kw: self


def panel_texts():
    texts = []
    ui.PP_PT_blockout.draw(type("P", (), {"layout": FakeLayout(texts)})(), bpy.context)
    return texts


H.check(bpy.ops.perspective_projector.blockout_box.poll(), "Box tool disabled after calibration")
H.check(any("Scale assumed" in t for t in panel_texts()), "no 'scale assumed' note with a reference corner")
bpy.ops.perspective_projector.blockout_clear_reference()
H.check(not any("Scale assumed" in t for t in panel_texts()), "'scale assumed' shown without a reference corner")

print("blockout ok")
