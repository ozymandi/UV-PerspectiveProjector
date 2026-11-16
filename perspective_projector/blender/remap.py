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
SHADOW_SAMPLES = 4
HIDDEN_NODE = "Hidden"  # name and label of the colour node feeding hidden areas
MASK_NODE = "PP_VisMask"
HELPER_LIGHT = "PP_CamA_Light"


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
        self.bake = {k: getattr(bake, k) for k in ("margin", "use_clear", "target", "use_selected_to_active",
                                                   "use_pass_direct", "use_pass_indirect", "use_pass_color")}
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


class _CameraLight:
    """While active: a hard point light at camera A is the only light that renders, and the
    frame-filling projection card does not cast shadows. Everything is restored on exit."""

    def __init__(self, scene, cam, target, alone=False):
        self.scene, self.cam = scene, cam
        self.target = target  # the object being baked: never hidden
        self.alone = alone  # True: every other object is hidden too (unoccluded reference pass)
        self.hidden = []
        self.light = None

    def _hide(self, o):
        if o == self.target:
            return False
        if o.type == "LIGHT" or o.get(projection.ROLE) == projection.ROLE_PLANE:
            return True
        return self.alone and o.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}

    def __enter__(self):
        for o in self.scene.objects:
            if self._hide(o) and not o.hide_render:
                o.hide_render = True
                self.hidden.append(o.name)
        data = bpy.data.lights.new(HELPER_LIGHT, "POINT")
        data.energy = 1.0e6  # only "lit or not" matters; keep far surfaces well above zero
        data.shadow_soft_size = 0.0
        self.light = bpy.data.objects.new(HELPER_LIGHT, data)
        self.scene.collection.objects.link(self.light)
        self.light.location = self.cam.matrix_world.translation
        bpy.context.view_layer.update()
        return self

    def __exit__(self, *exc):
        if self.light is not None:
            data = self.light.data
            bpy.data.objects.remove(self.light, do_unlink=True)
            bpy.data.lights.remove(data)
            self.light = None
        for name in self.hidden:
            o = self.scene.objects.get(name)
            if o is not None:
                o.hide_render = False
        self.hidden = []
        return False


def _bake(obj, img, mat, node_tree_edit=None, bake_type="EMIT"):
    """Bake ``bake_type`` for ``obj`` into ``img`` through an active image node in ``mat``."""
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
        bpy.ops.object.bake(type=bake_type)
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


def _white_diffuse(nt):
    """Bake pass 3 surface: plain white diffuse, so the direct-light bake measures only light
    from camera A's position (zero where another object blocks it or the face looks away)."""
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    surf = out.inputs["Surface"]
    old = surf.links[0].from_socket if surf.is_linked else None
    diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(diffuse.outputs[0], surf)

    def restore():
        nt.nodes.remove(diffuse)
        if old is not None:
            nt.links.new(old, surf)
    return restore


def _facing_as_emission(cam_pos, grazing_deg):
    """Bake pass 4: emit how squarely the surface faces camera A.

    0 for faces turned away, 1 for faces seen at more than ``grazing_deg`` (smooth step
    between ``grazing_deg`` and 1.5 x that angle); with 0 degrees it is a hard front/back test.
    """

    def edit(nt):
        restore_mix = _emission_only(nt)
        emission = next(n for n in nt.nodes if n.type == "EMISSION")
        col = emission.inputs["Color"]
        old_link = col.links[0].from_socket if col.is_linked else None
        if col.is_linked:
            nt.links.remove(col.links[0])
        added = []

        def new(kind, **kw):
            n = nt.nodes.new(kind)
            for k, v in kw.items():
                setattr(n, k, v)
            added.append(n)
            return n

        geo = new("ShaderNodeNewGeometry")
        cam = new("ShaderNodeCombineXYZ")
        for i in range(3):
            cam.inputs[i].default_value = float(cam_pos[i])
        to_cam = new("ShaderNodeVectorMath", operation="SUBTRACT")
        nt.links.new(cam.outputs[0], to_cam.inputs[0])
        nt.links.new(geo.outputs["Position"], to_cam.inputs[1])
        norm = new("ShaderNodeVectorMath", operation="NORMALIZE")
        nt.links.new(to_cam.outputs[0], norm.inputs[0])
        dot = new("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        nt.links.new(norm.outputs[0], dot.inputs[0])
        nt.links.new(geo.outputs["True Normal"], dot.inputs[1])
        lo = math.sin(math.radians(grazing_deg))
        hi = max(math.sin(math.radians(min(grazing_deg * 1.5, 89.0))), lo + 1e-3)
        step = new("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        step.inputs["From Min"].default_value = lo
        step.inputs["From Max"].default_value = hi
        nt.links.new(dot.outputs["Value"], step.inputs["Value"])
        nt.links.new(step.outputs["Result"], col)

        def restore():
            for n in added:
                nt.nodes.remove(n)
            if old_link is not None:
                nt.links.new(old_link, col)
            restore_mix()
        return restore
    return edit


def _grey(img, n):
    px = np.empty(n * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    return px[0::4].copy()


def hidden_colour(rgba, mask):
    """Median colour of the visible, in-frame texels (mid grey when there are none)."""
    rgb = rgba.reshape(-1, 4)
    seen = (mask > 0.5) & (rgb[:, 3] > 0.5)
    if not seen.any():
        return (0.5, 0.5, 0.5)
    return tuple(float(c) for c in np.median(rgb[seen, :3], axis=0))


def bake_object(scene, obj, resolution, cam=None, grazing_deg=0.0):
    """Bake the projection of ``obj``. Returns (RGBA image, visibility mask image or None, hidden colour).

    Passes: photo colour, in-frame alpha, then (with camera A) a shadow pass from a light at
    camera A and a facing pass; the mask is their product.
    """
    mat = obj.data.materials[0]
    name = f"{obj.name}_remap"
    img = bpy.data.images.new(name, resolution, resolution, alpha=True, float_buffer=False)
    img["pp_bake"] = True
    tmp = [bpy.data.images.new(name + suffix, resolution, resolution, alpha=False, float_buffer=True)
           for suffix in ("_alpha_tmp", "_shadow_tmp", "_free_tmp", "_facing_tmp")]
    alpha_img, shadow_img, free_img, facing_img = tmp
    for t in tmp:
        t["pp_bake"] = True
    mask_img = None
    n = resolution * resolution
    try:
        with _RenderState(scene):
            _bake(obj, img, mat, _emission_only)
            _bake(obj, alpha_img, mat, _alpha_as_emission)
            if cam is not None:
                # direct light from a point light at camera A, once with the scene and once with the
                # object alone; seen where it gets at least half of its unoccluded light. The ratio
                # ignores light leaking through semi-transparent occluders and the light's falloff.
                # (The SHADOW bake type returns a constant in recent Blender versions.)
                scene.cycles.samples = SHADOW_SAMPLES
                bake = scene.render.bake
                bake.use_pass_direct, bake.use_pass_indirect, bake.use_pass_color = True, False, False
                with _CameraLight(scene, cam, obj):
                    _bake(obj, shadow_img, mat, _white_diffuse, bake_type="DIFFUSE")
                with _CameraLight(scene, cam, obj, alone=True):
                    _bake(obj, free_img, mat, _white_diffuse, bake_type="DIFFUSE")
                scene.cycles.samples = 1
                _bake(obj, facing_img, mat, _facing_as_emission(cam.matrix_world.translation, grazing_deg))
        rgba = np.empty(n * 4, dtype=np.float32)
        img.pixels.foreach_get(rgba)
        rgba[3::4] = np.clip(_grey(alpha_img, n), 0.0, 1.0)
        img.pixels.foreach_set(rgba)
        img.update()
        if cam is not None:
            lit, free = _grey(shadow_img, n), _grey(free_img, n)
            seen = (free > max(float(free.max()) * 1e-6, 1e-12)) & (lit > 0.5 * free)
            mask = seen.astype(np.float32) * np.clip(_grey(facing_img, n), 0.0, 1.0)
            mask_img = bpy.data.images.new(f"{obj.name}_vis", resolution, resolution, alpha=False)
            mask_img.colorspace_settings.name = "Non-Color"
            grey = np.empty(n * 4, dtype=np.float32)
            grey[0::4] = grey[1::4] = grey[2::4] = mask
            grey[3::4] = 1.0
            mask_img.pixels.foreach_set(grey)
            mask_img.update()
            colour = hidden_colour(rgba, mask)
        else:
            colour = hidden_colour(rgba, np.ones(n, dtype=np.float32))
    finally:
        for t in tmp:
            bpy.data.images.remove(t)
    del img["pp_bake"]
    return img, mask_img, colour


def save_image(img, obj_name, suffix="_remap"):
    if bpy.data.is_saved:
        folder = bpy.path.abspath("//textures")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{bpy.path.clean_name(obj_name)}{suffix}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        img.filepath = bpy.path.relpath(path)
        img.source = "FILE"
        img.reload()
    else:
        img.pack()


def remap_material(obj, img, uv_name, mask_img=None, hidden=(0.5, 0.5, 0.5)):
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
    if mask_img is None:
        nt.links.new(tex.outputs["Color"], emission.inputs["Color"])
    else:
        # colour = mix(Hidden, photo, mask): the photo where camera A saw the surface
        vis = nt.nodes.new("ShaderNodeTexImage")
        vis.name = vis.label = MASK_NODE
        vis.location = (-150, -280)
        vis.image = mask_img
        vis.interpolation = "Linear"
        nt.links.new(uv.outputs["UV"], vis.inputs["Vector"])
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.name = rgb.label = HIDDEN_NODE
        rgb.location = (-150, 220)
        rgb.outputs[0].default_value = (*hidden, 1.0)
        mix_col = nt.nodes.new("ShaderNodeMix")
        mix_col.data_type = "RGBA"
        mix_col.label = "Photo / Hidden"
        mix_col.location = (60, -60)
        nt.links.new(vis.outputs["Color"], mix_col.inputs["Factor"])
        nt.links.new(rgb.outputs["Color"], mix_col.inputs["A"])
        nt.links.new(tex.outputs["Color"], mix_col.inputs["B"])
        nt.links.new(mix_col.outputs["Result"], emission.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emission.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    projection.set_render_method(mat)
    return mat


def remap(scene, obj, resolution=0):
    """Freeze the projection on ``obj``. Returns (image, uv_name, created_uv)."""
    from .calibration import camera_a

    cam = camera_a(scene)
    uv_name, created = ensure_bake_uv(obj)
    mesh = obj.data
    mesh.uv_layers.active = mesh.uv_layers[uv_name]
    res = resolution or auto_resolution(scene, cam, obj, uv_name)
    grazing = float(scene.perspective_projector.remap_grazing_deg)
    img, mask_img, hidden = bake_object(scene, obj, res, cam=cam, grazing_deg=grazing)
    save_image(img, obj.name)
    if mask_img is not None:
        save_image(mask_img, obj.name, "_vis")
        mask_img.colorspace_settings.name = "Non-Color"
        obj["pp_vis"] = mask_img.name
    mat = remap_material(obj, img, uv_name, mask_img, hidden)
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
