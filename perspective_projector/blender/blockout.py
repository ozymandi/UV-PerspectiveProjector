"""Blockout: build floor, walls, boxes and ceilings by clicking on the photo in camera A's view.

Every tool is an operator with a ``points`` collection of photo coordinates (u right, v down, 0..1).
``invoke`` collects them with mouse clicks; ``execute`` builds the object from them, so scripts and
tests call ``execute`` with the points directly.
"""

from __future__ import annotations

import bmesh
import bpy
import gpu
import numpy as np
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from ..core import blockout as B
from . import calibration, projection, view

COLLECTION = "Blockout"
LABELS = {"FLOOR": "Floor", "WALL": "Wall", "BOX": "Box", "CEILING": "Ceiling"}
FAR_FACTOR = 1000.0  # hits farther than this x camera height are rejected (grazing rays)
CLOSE_PX = 12.0  # Floor: a click this close to the first corner closes the polygon

EDGE_COLOR = (1.0, 0.85, 0.15, 1.0)
OUTLINE_COLOR = (0.0, 0.0, 0.0, 0.85)
PREVIEW_COLOR = (0.2, 0.9, 1.0, 1.0)

_preview = {"points": [], "cursor": None}  # world points of the tool in progress, cursor in region px


# ---------------------------------------------------------------- rays and hits


def photo_ray(scene, cam, u, v):
    """World ray (origin, unit direction) through photo coordinate (u, v) of ``cam``."""
    tr, br, bl, tl = cam.data.view_frame(scene=scene)
    p = tl.lerp(tr, u).lerp(bl.lerp(br, u), v)
    m = cam.matrix_world
    d = (m.to_3x3() @ p).normalized()
    return np.array(m.translation), np.array(d)


def max_distance(cam):
    return FAR_FACTOR * max(abs(cam.matrix_world.translation.z), 1.0)


def blockout_collection(scene, create=False):
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None and create:
        coll = bpy.data.collections.new(COLLECTION)
        scene.collection.children.link(coll)
    return coll


def blockout_objects(scene):
    coll = blockout_collection(scene)
    if coll is None:
        return []
    return [o for o in coll.all_objects if o.type == "MESH" and o.name in scene.objects]


class Hit:
    __slots__ = ("point", "normal", "kind", "obj")

    def __init__(self, point, normal, kind, obj=None):
        self.point, self.normal, self.kind, self.obj = np.asarray(point, float), np.asarray(normal, float), kind, obj


def _facing(normal, direction):
    n = np.asarray(normal, float)
    return -n if float(np.dot(n, direction)) > 0 else n


def reference_plane(scene, cam):
    """(point, normal) of the selected reference plane, or None when no reference corner is set."""
    props = scene.perspective_projector
    if not props.blockout_ref_set:
        return None
    o, d = photo_ray(scene, cam, *props.blockout_ref_uv)
    corner = B.reference_corner(o, d, props.blockout_ref_distance)
    return B.reference_plane(corner, props.blockout_ref_axis)


def hit(scene, cam, u, v, surfaces=True, ground=True, reference=True):
    """Where a click lands: blockout surfaces first, then the ground, then the reference plane."""
    o, d = photo_ray(scene, cam, u, v)
    far = max_distance(cam)
    if surfaces:
        best = None
        for ob in blockout_objects(scene):
            inv = ob.matrix_world.inverted()
            oo = inv @ Vector(o)
            dd = (inv.to_3x3() @ Vector(d)).normalized()
            ok, loc, nrm, _idx = ob.ray_cast(oo, dd, distance=far)
            if not ok:
                continue
            p = np.array(ob.matrix_world @ loc)
            dist = float(np.linalg.norm(p - o))
            if best is None or dist < best[0]:
                n = np.array((ob.matrix_world.inverted().transposed().to_3x3() @ nrm).normalized())
                best = (dist, Hit(p, _facing(n, d), "surface", ob))
        if best is not None:
            return best[1]
    if ground:
        p = B.ray_plane(o, d, (0, 0, 0), (0, 0, 1), far)
        if p is not None:
            return Hit(p, (0, 0, 1), "ground")
    if reference:
        plane = reference_plane(scene, cam)
        if plane is not None:
            p = B.ray_plane(o, d, plane[0], plane[1], far)
            if p is not None:
                return Hit(p, _facing(plane[1], d), "reference")
    return None


def _need_hit(h):
    if h is None:
        raise B.BlockoutError("the click did not hit the ground, a blockout surface or a reference plane")
    return h


def _nearest_on_lines(scene, cam, uv, bases, axis):
    """Third click: the point on one of the lines ``base + s * axis`` that the click ray passes closest to."""
    o, d = photo_ray(scene, cam, *uv)
    best = None
    for base in bases:
        p = B.closest_on_line(o, d, base, axis)
        w = p - o
        gap = float(np.linalg.norm(w - np.dot(w, d) * d))
        if best is None or gap < best[0]:
            best = (gap, p, np.asarray(base, float))
    return best[1], best[2]


# ---------------------------------------------------------------- building


def _next_name(label):
    n = 1
    while f"{label}.{n:03d}" in bpy.data.objects:
        n += 1
    return f"{label}.{n:03d}"


def make_object(scene, kind, verts, faces, cam=None, toward_camera=False):
    """Mesh object in the Blockout collection; origin at the centre of its first face."""
    verts = [np.asarray(v, float) for v in verts]
    centre = np.mean([verts[i] for i in faces[0]], axis=0)
    me = bpy.data.meshes.new(LABELS[kind])
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(v - centre)) for v in verts]
    for f in faces:
        bm.faces.new([bv[i] for i in f])
    if len(faces) > 1:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    elif toward_camera and cam is not None:
        bm.faces.ensure_lookup_table()
        f = bm.faces[0]
        f.normal_update()
        to_cam = Vector(cam.matrix_world.translation) - (Vector(tuple(centre)) + f.calc_center_median())
        if f.normal.dot(to_cam) < 0:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(_next_name(LABELS[kind]), me)
    ob.location = tuple(centre)
    blockout_collection(scene, create=True).objects.link(ob)
    return ob


def build_floor(scene, cam, uvs):
    if len(uvs) < 3:
        raise B.BlockoutError("a floor needs at least three corners")
    pts = []
    for uv in uvs:
        o, d = photo_ray(scene, cam, *uv)
        p = B.ray_plane(o, d, (0, 0, 0), (0, 0, 1), max_distance(cam))
        if p is None:
            raise B.BlockoutError("a floor corner is not on the ground")
        pts.append(p)
    return make_object(scene, "FLOOR", pts, [list(range(len(pts)))], cam, toward_camera=True)


def build_wall(scene, cam, uvs):
    if len(uvs) != 3:
        raise B.BlockoutError("a wall needs two base points and a top")
    a = _need_hit(hit(scene, cam, *uvs[0])).point
    b = _need_hit(hit(scene, cam, *uvs[1])).point
    top, _base = _nearest_on_lines(scene, cam, uvs[2], [a, b], B.UP)
    corners = B.wall_corners(a, b, top)
    return make_object(scene, "WALL", corners, [[0, 1, 2, 3]], cam, toward_camera=True)


def build_box(scene, cam, uvs):
    if len(uvs) != 3:
        raise B.BlockoutError("a box needs two footprint corners and a height (or depth) click")
    h0 = _need_hit(hit(scene, cam, *uvs[0]))
    if B.is_horizontal(h0.normal):
        normal = np.array([0.0, 0.0, 1.0]) if h0.normal[2] > 0 else np.array([0.0, 0.0, -1.0])
    else:
        normal = B.axis_normal(h0.normal)
    o1, d1 = photo_ray(scene, cam, *uvs[1])
    p1 = B.ray_plane(o1, d1, h0.point, normal, max_distance(cam))
    if p1 is None:
        raise B.BlockoutError("the second corner is not on the same surface as the first")
    rect = B.rect_from_corners(h0.point, p1, normal)
    far, base = _nearest_on_lines(scene, cam, uvs[2], rect, normal)
    extrude = normal * float(np.dot(far - base, normal))
    corners = B.box_corners(rect, extrude)
    return make_object(scene, "BOX", corners, BOX_FACES)


BOX_FACES = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def build_box_edge(scene, cam, uvs):
    """Box from its near edge: near bottom corner, top of that vertical edge, opposite top corner.
    For objects against a wall, whose far footprint corner is hidden behind them."""
    if len(uvs) != 3:
        raise B.BlockoutError("a box from its edge needs the near bottom corner, the top of that edge and the opposite top corner")
    h0 = _need_hit(hit(scene, cam, *uvs[0]))
    if not B.is_horizontal(h0.normal) or h0.normal[2] < 0:
        raise B.BlockoutError("click the near bottom corner on a floor or a box top")
    base = h0.point
    top, _ = _nearest_on_lines(scene, cam, uvs[1], [base], B.UP)
    height = float(top[2] - base[2])
    if height <= 1e-6:
        raise B.BlockoutError("the top of the edge must be above the bottom corner")
    o2, d2 = photo_ray(scene, cam, *uvs[2])
    far_top = B.ray_plane(o2, d2, top, B.UP, max_distance(cam))
    if far_top is None:
        raise B.BlockoutError("the opposite top corner is not on the box's top plane")
    far = far_top - B.UP * height
    rect = B.rect_from_corners(base, far, B.UP)
    return make_object(scene, "BOX", B.box_corners(rect, B.UP * height), BOX_FACES)


def build_ceiling(scene, cam, uvs):
    if len(uvs) != 1:
        raise B.BlockoutError("a ceiling needs one click on a wall")
    h = hit(scene, cam, *uvs[0], ground=False, reference=False)
    if h is None or B.is_horizontal(h.normal):
        raise B.BlockoutError("click where the ceiling meets a wall of the blockout")
    pts = [np.array(ob.matrix_world @ v.co) for ob in blockout_objects(scene) for v in ob.data.vertices]
    x0, y0, x1, y1 = B.ceiling_extent(pts)
    z = float(h.point[2])
    corners = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    return make_object(scene, "CEILING", corners, [[0, 1, 2, 3]], cam, toward_camera=True)


BUILDERS = {"FLOOR": build_floor, "WALL": build_wall, "BOX": build_box, "BOX_EDGE": build_box_edge,
            "CEILING": build_ceiling}
CLICKS = {"FLOOR": None, "WALL": 3, "BOX": 3, "BOX_EDGE": 3, "CEILING": 1}
PROMPTS = {
    "FLOOR": ["Click the floor corners; Enter or a click on the first corner finishes"],
    "WALL": ["Click a point where the wall meets the floor or a surface", "Click a second point along the wall's base",
             "Click the top edge of the wall"],
    "BOX": ["Click a corner of the footprint", "Click the opposite corner", "Click the top edge (or the front, on a facade)"],
    "BOX_EDGE": ["Click the near bottom corner (on the floor or a box top)", "Click the top of that vertical edge",
                 "Click the opposite top corner"],
    "CEILING": ["Click where the ceiling meets a wall"],
}


# ---------------------------------------------------------------- operators


class PP_BlockoutPoint(bpy.types.PropertyGroup):
    uv: bpy.props.FloatVectorProperty(size=2)


def _ready(context):
    scene = context.scene
    props = scene.perspective_projector
    return props.calibrated and props.image is not None and calibration.camera_a(scene) is not None


def _looking_through_a(context):
    cam = calibration.camera_a(context.scene)
    rv3d, space = context.region_data, context.space_data
    if cam is None or rv3d is None or space is None or rv3d.view_perspective != "CAMERA":
        return None
    view_cam = space.camera if (space.use_local_camera and space.camera) else context.scene.camera
    return cam if view_cam is cam else None


class _ClickTool:
    """Collect photo clicks in camera A's view, then build in ``execute``."""

    tool = ""
    bl_options = {"REGISTER", "UNDO"}

    points: bpy.props.CollectionProperty(type=PP_BlockoutPoint, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        if not _ready(context):
            cls.poll_message_set("Calibrate first")
            return False
        return True

    def uvs(self):
        return [tuple(p.uv) for p in self.points]

    def execute(self, context):
        scene = context.scene
        cam = calibration.camera_a(scene)
        try:
            ob = self.build(scene, cam, self.uvs())
        except B.BlockoutError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        for o in context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({"INFO"}, f"Created {ob.name}")
        return {"FINISHED"}

    def build(self, scene, cam, uvs):
        return BUILDERS[self.tool](scene, cam, uvs)

    # -- interactive

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "Run the tool from the 3D Viewport")
            return {"CANCELLED"}
        view.look_through(context, calibration.camera_a(context.scene))
        self.points.clear()
        _preview["points"], _preview["cursor"] = [], None
        context.window.cursor_modal_set("CROSSHAIR")
        self._status(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def _status(self, context, extra=""):
        prompts = PROMPTS[self.tool]
        text = prompts[min(len(self.points), len(prompts) - 1)]
        context.workspace.status_text_set(f"{text}{'  |  ' + extra if extra else ''}  |  Esc / right click: cancel")

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)
        _preview["points"], _preview["cursor"] = [], None
        context.area.tag_redraw()

    def _uv_at(self, context, event):
        rect = view.camera_frame_region(context, calibration.camera_a(context.scene))
        if rect is None:
            return None
        u, v = view.region_to_image(rect, event.mouse_region_x, event.mouse_region_y)
        return (u, v) if 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 else None

    def _accept(self, context, uv):
        """Check one click against what this step needs; returns an error text or None."""
        scene = context.scene
        cam = calibration.camera_a(scene)
        i = len(self.points)
        try:
            if self.tool == "FLOOR":
                o, d = photo_ray(scene, cam, *uv)
                if B.ray_plane(o, d, (0, 0, 0), (0, 0, 1), max_distance(cam)) is None:
                    return "that point is not on the ground"
            elif self.tool == "CEILING":
                h = hit(scene, cam, *uv, ground=False, reference=False)
                if h is None or B.is_horizontal(h.normal):
                    return "click where the ceiling meets a wall of the blockout"
            elif i < (1 if self.tool == "BOX_EDGE" else 2):  # Box from Edge: the 2nd click is the top of the edge
                if hit(scene, cam, *uv) is None:
                    return "the click did not hit the ground, a blockout surface or a reference plane"
        except B.BlockoutError as exc:
            return str(exc)
        return None

    def _preview_points(self, context):
        scene = context.scene
        cam = calibration.camera_a(scene)
        pts = []
        for uv in self.uvs():
            h = hit(scene, cam, *uv)
            if h is not None:
                pts.append(tuple(h.point))
        _preview["points"] = pts

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type == "MOUSEMOVE":
            _preview["cursor"] = (event.mouse_region_x, event.mouse_region_y)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type in {"RET", "NUMPAD_ENTER"} and event.value == "PRESS" and self.tool == "FLOOR":
            return self._finish(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            uv = self._uv_at(context, event)
            if uv is None:
                return {"RUNNING_MODAL"}
            if self.tool == "FLOOR" and len(self.points) >= 3 and self._near_first(context, event):
                return self._finish(context)
            err = self._accept(context, uv)
            if err:
                self._status(context, err)
                return {"RUNNING_MODAL"}
            self.points.add().uv = uv
            self._preview_points(context)
            need = CLICKS[self.tool]
            if need is not None and len(self.points) >= need:
                return self._finish(context)
            self._status(context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
            return {"PASS_THROUGH"}
        return {"RUNNING_MODAL"}

    def _near_first(self, context, event):
        rect = view.camera_frame_region(context, calibration.camera_a(context.scene))
        if rect is None:
            return False
        x, y = view.image_to_region(rect, *self.points[0].uv)
        return np.hypot(event.mouse_region_x - x, event.mouse_region_y - y) <= CLOSE_PX

    def _finish(self, context):
        self._end(context)
        return self.execute(context)


class PP_OT_blockout_floor(_ClickTool, bpy.types.Operator):
    """Click the corners of a floor area on the photo"""

    bl_idname = "perspective_projector.blockout_floor"
    bl_label = "Floor"
    tool = "FLOOR"


class PP_OT_blockout_wall(_ClickTool, bpy.types.Operator):
    """Click two points along the bottom of a wall, then its top"""

    bl_idname = "perspective_projector.blockout_wall"
    bl_label = "Wall"
    tool = "WALL"


class PP_OT_blockout_box(_ClickTool, bpy.types.Operator):
    """Click two opposite corners of a footprint (on the floor, a box or a facade), then the top or front"""

    bl_idname = "perspective_projector.blockout_box"
    bl_label = "Box"
    tool = "BOX"


class PP_OT_blockout_box_edge(_ClickTool, bpy.types.Operator):
    """Box against a wall: click its near bottom corner, the top of that edge, then the opposite top corner"""

    bl_idname = "perspective_projector.blockout_box_edge"
    bl_label = "Box from Edge"
    tool = "BOX_EDGE"


class PP_OT_blockout_ceiling(_ClickTool, bpy.types.Operator):
    """Click where the ceiling meets a wall of the blockout"""

    bl_idname = "perspective_projector.blockout_ceiling"
    bl_label = "Ceiling"
    tool = "CEILING"


class PP_OT_blockout_reference(_ClickTool, bpy.types.Operator):
    """Click a vertical corner edge of the building: walls and boxes can then be built without a visible floor"""

    bl_idname = "perspective_projector.blockout_reference"
    bl_label = "Pick Reference Corner"
    tool = "REFERENCE"

    def build(self, scene, cam, uvs):
        raise AssertionError("not used")

    def execute(self, context):
        uvs = self.uvs()
        if len(uvs) != 1:
            self.report({"ERROR"}, "pick one point on a vertical corner edge")
            return {"CANCELLED"}
        props = context.scene.perspective_projector
        props.blockout_ref_uv = uvs[0]
        props.blockout_ref_set = True
        self.report({"INFO"}, f"Reference corner set at an assumed {props.blockout_ref_distance:g} m")
        return {"FINISHED"}

    def _accept(self, context, uv):
        return None


CLICKS["REFERENCE"] = 1
PROMPTS["REFERENCE"] = ["Click a point on a vertical corner edge of the building"]


class PP_OT_blockout_clear_reference(bpy.types.Operator):
    """Stop using the reference corner"""

    bl_idname = "perspective_projector.blockout_clear_reference"
    bl_label = "Clear Reference Corner"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.perspective_projector.blockout_ref_set = False
        return {"FINISHED"}


# ---------------------------------------------------------------- overlay


def _region_point(context, p):
    return view3d_utils.location_3d_to_region_2d(context.region, context.region_data, Vector(p))


def overlay_objects(scene):
    out = list(blockout_objects(scene))
    for ob in scene.objects:
        if ob.type == "MESH" and ob not in out and (ob.get(projection.PROJECTED) or ob.get("pp_remapped")):
            out.append(ob)
    return out


def overlay_segments(context):
    """Region-space edge segments the overlay draws; empty unless the view looks through camera A."""
    if _looking_through_a(context) is None or not context.scene.perspective_projector.blockout_overlay:
        return []
    segs = []
    for ob in overlay_objects(context.scene):
        if not ob.visible_get():
            continue
        mw = ob.matrix_world
        pts = [_region_point(context, mw @ v.co) for v in ob.data.vertices]
        for e in ob.data.edges:
            a, b = pts[e.vertices[0]], pts[e.vertices[1]]
            if a is not None and b is not None:
                segs.append(((a.x, a.y), (b.x, b.y)))
    return segs


def _draw_lines(shader, segs, width, color):
    if not segs:
        return
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch_for_shader(shader, "LINES", {"pos": [p for s in segs for p in s]}).draw(shader)


def _draw():
    context = bpy.context
    if _looking_through_a(context) is None:
        return
    region = context.region
    shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    shader.uniform_float("viewportSize", (region.width, region.height))
    segs = overlay_segments(context)
    _draw_lines(shader, segs, 4.0, OUTLINE_COLOR)
    _draw_lines(shader, segs, 1.5, EDGE_COLOR)
    # tool in progress: clicked points joined, plus a rubber band to the cursor
    pts = [_region_point(context, p) for p in _preview["points"]]
    pts = [(p.x, p.y) for p in pts if p is not None]
    if _preview["cursor"] is not None and pts:
        pts.append(_preview["cursor"])
    if len(pts) >= 2:
        segs = list(zip(pts[:-1], pts[1:]))
        _draw_lines(shader, segs, 4.0, OUTLINE_COLOR)
        _draw_lines(shader, segs, 2.0, PREVIEW_COLOR)
    gpu.state.blend_set("NONE")


_classes = (PP_BlockoutPoint, PP_OT_blockout_floor, PP_OT_blockout_wall, PP_OT_blockout_box,
            PP_OT_blockout_box_edge, PP_OT_blockout_ceiling, PP_OT_blockout_reference, PP_OT_blockout_clear_reference)
_handle = None


def register():
    global _handle
    for cls in _classes:
        bpy.utils.register_class(cls)
    _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
