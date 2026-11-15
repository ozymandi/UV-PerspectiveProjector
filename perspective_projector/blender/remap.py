"""Remap: bake a live camera projection into a regular UV map and image."""

from __future__ import annotations

import math
import os

import bpy
import numpy as np

from ..core import clip
from . import projection

REMAP_UV = "RemapUV"
MIN_RES, MAX_RES = 1024, 8192
BAKE_MARGIN = 16


def is_projected(obj):
    return (obj.type == "MESH" and obj.get(projection.PROJECTED)
            and projection.MOD_UVPROJECT in obj.modifiers)


# ---------------------------------------------------------------- UVs


def ensure_bake_uv(obj):
    """Return the name of the regular UV map to bake into, creating a non-overlapping unwrap if needed."""
    mesh = obj.data
    for layer in mesh.uv_layers:
        if layer.name != projection.UV_PROJ:
            return layer.name, False
    layer = mesh.uv_layers.new(name=REMAP_UV)
    mesh.uv_layers.active = layer
    layer.active_render = True
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = [o for o in bpy.context.selected_objects]
    for o in prev_sel:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    try:
        with bpy.context.temp_override(active_object=obj, object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.01,
                                     correct_aspect=True, scale_to_bounds=True)
            bpy.ops.object.mode_set(mode="OBJECT")
    finally:
        obj.select_set(False)
        for o in prev_sel:
            o.select_set(True)
        view_layer.objects.active = prev_active
    return REMAP_UV, True


def uv_coverage(obj, uv_name):
    """Fraction of the 0..1 UV square covered by the object's islands."""
    mesh = obj.data
    uv = mesh.uv_layers[uv_name].data
    total = 0.0
    for poly in mesh.polygons:
        pts = [uv[i].uv for i in poly.loop_indices]
        a = 0.0
        for k in range(len(pts)):
            x0, y0 = pts[k]
            x1, y1 = pts[(k + 1) % len(pts)]
            a += x0 * y1 - x1 * y0
        total += abs(a) / 2.0
    return min(max(total, 1e-6), 1.0)


# ---------------------------------------------------------------- resolution


def projected_pixels(scene, cam, obj):
    """Photo pixels covered by the object in camera A: face areas clipped to the part in front of
    the camera and to the frame, so faces that reach behind camera A still count."""
    w, h = scene.render.resolution_x, scene.render.resolution_y
    tr, _br, bl, _tl = cam.data.view_frame(scene=scene)  # camera-space frame corners at depth -tr.z
    depth = -tr.z
    fx0, fx1 = bl.x / depth, tr.x / depth
    fy0, fy1 = bl.y / depth, tr.y / depth
    near = max(cam.data.clip_start, 1e-6)
    to_cam = cam.matrix_world.inverted() @ obj.matrix_world
    pts = [tuple(to_cam @ v.co) for v in obj.data.vertices]
    total = 0.0
    for poly in obj.data.polygons:
        front = clip.clip_near([pts[i] for i in poly.vertices], near)
        if len(front) < 3:
            continue
        xy = [((x / -z - fx0) / (fx1 - fx0) * w, (y / -z - fy0) / (fy1 - fy0) * h) for x, y, z in front]
        total += clip.area(clip.clip_rect(xy, 0.0, 0.0, w, h))
    return total


def auto_resolution(scene, cam, obj, uv_name):
    pixels = projected_pixels(scene, cam, obj)
    side = math.sqrt(max(pixels, 1.0) / uv_coverage(obj, uv_name))
    res = 2 ** math.ceil(math.log2(max(side, 1.0)))
    return int(min(max(res, MIN_RES), MAX_RES))


# ---------------------------------------------------------------- bake


class _RenderState:
    """Capture and restore the scene settings that baking touches."""

    def __init__(self, scene):
        self.scene = scene

    def __enter__(self):
        s = self.scene
        bake = s.render.bake
        self.engine = s.render.engine
        self.samples = s.cycles.samples if hasattr(s, "cycles") else None
        self.bake = {k: getattr(bake, k) for k in ("margin", "use_clear", "target", "use_selected_to_active")}
        self.bake_type = s.cycles.bake_type if hasattr(s, "cycles") else None
        s.render.engine = "CYCLES"
        s.cycles.samples = 1
        s.cycles.bake_type = "EMIT"
        bake.margin = BAKE_MARGIN
        bake.use_clear = True
        bake.target = "IMAGE_TEXTURES"
        bake.use_selected_to_active = False
        return self

    def __exit__(self, *exc):
        s = self.scene
        s.render.engine = "CYCLES"
        if self.samples is not None:
            s.cycles.samples = self.samples
        if self.bake_type is not None:
            s.cycles.bake_type = self.bake_type
        for k, v in self.bake.items():
            setattr(s.render.bake, k, v)
        s.render.engine = self.engine
        return False


def _bake(obj, img, mat, node_tree_edit=None):
    """Bake Emit for ``obj`` into ``img`` through an active image node in ``mat``."""
    nt = mat.node_tree
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    node.location = (-150, -300)
    prev_active = nt.nodes.active
    nt.nodes.active = node
    restore = node_tree_edit(nt) if node_tree_edit else None
    view_layer = bpy.context.view_layer
    prev_sel = list(bpy.context.selected_objects)
    prev_obj = view_layer.objects.active
    try:
        for o in prev_sel:
            o.select_set(False)
        obj.select_set(True)
        view_layer.objects.active = obj
        bpy.ops.object.bake(type="EMIT")
    finally:
        if restore:
            restore()
        nt.nodes.remove(node)
        nt.nodes.active = prev_active
        obj.select_set(False)
        for o in prev_sel:
            o.select_set(True)
        view_layer.objects.active = prev_obj


def _emission_only(nt):
    """Bake pass 1: full emission colour, ignoring alpha."""
    mix = next(n for n in nt.nodes if n.type == "MIX_SHADER")
    fac = mix.inputs["Fac"]
    link = fac.links[0] if fac.is_linked else None
    src = link.from_socket if link else None
    if link:
        nt.links.remove(link)
    old = fac.default_value
    fac.default_value = 1.0

    def restore():
        fac.default_value = old
        if src is not None:
            nt.links.new(src, fac)
    return restore


def _alpha_as_emission(nt):
    """Bake pass 2: emit the material's opacity (whatever drives the mix factor) as grey."""
    mix = next(n for n in nt.nodes if n.type == "MIX_SHADER")
    fac = mix.inputs["Fac"]
    alpha_src = fac.links[0].from_socket if fac.is_linked else None
    alpha_value = fac.default_value
    restore_mix = _emission_only(nt)
    emission = next(n for n in nt.nodes if n.type == "EMISSION")
    col = emission.inputs["Color"]
    old_link = col.links[0].from_socket if col.is_linked else None
    old_value = tuple(col.default_value)
    if col.is_linked:
        nt.links.remove(col.links[0])
    if alpha_src is not None:
        nt.links.new(alpha_src, col)
    else:
        col.default_value = (alpha_value, alpha_value, alpha_value, 1.0)

    def restore():
        if col.is_linked:
            nt.links.remove(col.links[0])
        col.default_value = old_value
        if old_link is not None:
            nt.links.new(old_link, col)
        restore_mix()
    return restore


def bake_object(scene, obj, resolution):
    """Bake the projection of ``obj`` into a new RGBA image. Returns the image."""
    mat = obj.data.materials[0]
    name = f"{obj.name}_remap"
    img = bpy.data.images.new(name, resolution, resolution, alpha=True, float_buffer=False)
    img["pp_bake"] = True
    alpha_img = bpy.data.images.new(name + "_alpha_tmp", resolution, resolution, alpha=False, float_buffer=True)
    alpha_img["pp_bake"] = True
    try:
        with _RenderState(scene):
            _bake(obj, img, mat, _emission_only)
            _bake(obj, alpha_img, mat, _alpha_as_emission)
        n = resolution * resolution
        rgba = np.empty(n * 4, dtype=np.float32)
        img.pixels.foreach_get(rgba)
        a = np.empty(n * 4, dtype=np.float32)
        alpha_img.pixels.foreach_get(a)
        rgba[3::4] = np.clip(a[0::4], 0.0, 1.0)
        img.pixels.foreach_set(rgba)
        img.update()
    finally:
        bpy.data.images.remove(alpha_img)
    del img["pp_bake"]
    return img


def save_image(img, obj_name):
    if bpy.data.is_saved:
        folder = bpy.path.abspath("//textures")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{bpy.path.clean_name(obj_name)}_remap.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        img.filepath = bpy.path.relpath(path)
        img.source = "FILE"
        img.reload()
    else:
        img.pack()


def remap_material(obj, img, uv_name):
    mat = bpy.data.materials.new(f"PP_Remap_{obj.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (400, 0)
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (200, 120)
    emission = nt.nodes.new("ShaderNodeEmission")
    emission.location = (200, -60)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-150, 0)
    tex.image = img
    tex.interpolation = "Linear"
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.location = (-350, 0)
    uv.uv_map = uv_name
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], emission.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emission.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    return mat


def remap(scene, obj, resolution=0):
    """Freeze the projection on ``obj``. Returns (image, uv_name, created_uv)."""
    from .calibration import camera_a

    cam = camera_a(scene)
    uv_name, created = ensure_bake_uv(obj)
    mesh = obj.data
    mesh.uv_layers.active = mesh.uv_layers[uv_name]
    res = resolution or auto_resolution(scene, cam, obj, uv_name)
    img = bake_object(scene, obj, res)
    save_image(img, obj.name)
    mat = remap_material(obj, img, uv_name)
    mesh.materials.clear()
    mesh.materials.append(mat)
    obj.modifiers.remove(obj.modifiers[projection.MOD_UVPROJECT])
    if projection.UV_PROJ in mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[projection.UV_PROJ])
    mesh.uv_layers.active = mesh.uv_layers[uv_name]
    mesh.uv_layers[uv_name].active_render = True
    obj[projection.PROJECTED] = False
    obj["pp_remapped"] = True
    return img, uv_name, created
