"""Projection setup: frustum plane, simple subdivision, UV Project from camera A, material, camera B."""

from __future__ import annotations

import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ROLE = "pp_role"
ROLE_CAMERA_B = "CAMERA_B"
ROLE_PLANE = "PLANE"
PROJECTED = "pp_projected"  # custom property on objects with a live projection

PLANE_NAME = "Proj_Plane"
CAMERA_B_NAME = "Render_Cam_B"
UV_PROJ = "ProjUV"
MOD_SUBDIV = "PP_Subdivision"
MOD_UVPROJECT = "PP_UVProject"
MAX_EDGE_PX = 32.0
MAX_LEVEL = 6


def _find(scene, role):
    for obj in scene.objects:
        if obj.get(ROLE) == role:
            return obj
    return None


def camera_b(scene):
    return _find(scene, ROLE_CAMERA_B)


def projection_plane(scene):
    return _find(scene, ROLE_PLANE)


def on_camera_a_changed(scene):
    """Camera A moved or changed lens. Projections follow automatically through the modifier."""


# ---------------------------------------------------------------- plane


def _frame_corners(scene, cam, distance):
    """Camera-local corners of camera A's frame at ``distance`` in front of it (TR, BR, BL, TL)."""
    corners = cam.data.view_frame(scene=scene)
    return [c * (distance / -c.z) for c in corners]


def build_plane(scene, cam, distance, plane=None):
    """Create or rebuild the frustum-fitted plane at ``distance`` from camera A."""
    corners = _frame_corners(scene, cam, distance)
    verts = [(c.x, c.y, 0.0) for c in (corners[2], corners[1], corners[0], corners[3])]  # BL, BR, TR, TL
    if plane is None:
        mesh = bpy.data.meshes.new(PLANE_NAME)
        plane = bpy.data.objects.new(PLANE_NAME, mesh)
        scene.collection.objects.link(plane)
        plane[ROLE] = ROLE_PLANE
    mesh = plane.data
    # rebuild geometry in place (keeps UV layers and materials)
    if len(mesh.vertices) == 4 and len(mesh.polygons) == 1:
        for v, co in zip(mesh.vertices, verts):
            v.co = co
    else:
        mesh.clear_geometry()
        mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    plane.matrix_world = cam.matrix_world @ Matrix.Translation((0.0, 0.0, -distance))
    plane["pp_distance"] = distance
    return plane


def update_plane_distance(scene):
    plane = projection_plane(scene)
    from .calibration import camera_a

    cam = camera_a(scene)
    if plane is None or cam is None or plane.get("pp_remapped"):
        return
    build_plane(scene, cam, scene.perspective_projector.plane_distance, plane)


# ---------------------------------------------------------------- subdivision level


def auto_subdiv_level(scene, cam, obj):
    """Smallest simple-subdivision level so that no edge spans more than ~32 photo pixels in camera A."""
    w, h = scene.render.resolution_x, scene.render.resolution_y
    diag = math.hypot(w, h)
    mw = obj.matrix_world
    mesh = obj.data
    pts = []
    for v in mesh.vertices:
        co = world_to_camera_view(scene, cam, mw @ v.co)
        pts.append(co)
    longest = 0.0
    for e in mesh.edges:
        a, b = pts[e.vertices[0]], pts[e.vertices[1]]
        if a.z <= 0 and b.z <= 0:
            continue  # entirely behind camera A
        if a.z <= 0 or b.z <= 0:
            length = diag  # crosses the camera plane: treat as large
        else:
            length = min(math.hypot((a.x - b.x) * w, (a.y - b.y) * h), diag)
        longest = max(longest, length)
    if longest <= MAX_EDGE_PX:
        return 0
    return min(MAX_LEVEL, math.ceil(math.log2(longest / MAX_EDGE_PX)))


# ---------------------------------------------------------------- material


def projection_material(img):
    name = f"PP_Projection_{img.name}"
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("pp_image") == img.name and mat.get("pp_version") == 2:
        return mat
    mat = bpy.data.materials.new(name)
    mat["pp_image"] = img.name
    mat["pp_version"] = 2
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
    emission.inputs["Strength"].default_value = 1.0
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-150, 0)
    tex.image = img
    tex.extension = "CLIP"
    tex.interpolation = "Linear"
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.location = (-350, 0)
    uv.uv_map = UV_PROJ
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], emission.inputs["Color"])
    # Opacity = image alpha x "inside camera A's frame". The frame test is done on the UVs because
    # Cycles reports alpha 1 outside a clipped image that has no alpha channel (JPEG etc.).
    alpha = _inside_frame_mask(nt, uv.outputs["UV"], tex.outputs["Alpha"])
    nt.links.new(alpha, mix.inputs["Fac"])
    nt.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emission.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    return mat


def _inside_frame_mask(nt, uv_socket, alpha_socket):
    """Node chain returning alpha_socket * [0 <= u <= 1] * [0 <= v <= 1]."""
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-150, -260)
    nt.links.new(uv_socket, sep.inputs[0])
    result = alpha_socket
    x = 50
    for comp in ("X", "Y"):
        for op, bound in (("GREATER_THAN", -1e-6), ("LESS_THAN", 1.0 + 1e-6)):
            cmp_node = nt.nodes.new("ShaderNodeMath")
            cmp_node.operation = op
            cmp_node.location = (x, -260)
            nt.links.new(sep.outputs[comp], cmp_node.inputs[0])
            cmp_node.inputs[1].default_value = bound
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.location = (x, -420)
            nt.links.new(result, mul.inputs[0])
            nt.links.new(cmp_node.outputs[0], mul.inputs[1])
            result = mul.outputs[0]
            x += 60
    return result


# ---------------------------------------------------------------- per-object setup


def _aspect(w, h):
    return (w / h, 1.0) if w >= h else (1.0, h / w)


def setup_projection(scene, cam, img, obj):
    mesh = obj.data
    if UV_PROJ not in mesh.uv_layers:
        had_uv = len(mesh.uv_layers) > 0
        layer = mesh.uv_layers.new(name=UV_PROJ, do_init=False)
        if had_uv:
            # keep the user's own map active for editing / render
            for other in mesh.uv_layers:
                if other.name != UV_PROJ:
                    mesh.uv_layers.active = other
                    other.active_render = True
                    break
        elif layer is not None:
            layer.active_render = True

    level = auto_subdiv_level(scene, cam, obj)
    sub = obj.modifiers.get(MOD_SUBDIV)
    if sub is None:
        sub = obj.modifiers.new(MOD_SUBDIV, "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = level
    sub.render_levels = level
    sub.show_only_control_edges = True

    uvp = obj.modifiers.get(MOD_UVPROJECT)
    if uvp is None:
        uvp = obj.modifiers.new(MOD_UVPROJECT, "UV_PROJECT")
    uvp.uv_layer = UV_PROJ
    uvp.projector_count = 1
    uvp.projectors[0].object = cam
    w, h = img.size
    uvp.aspect_x, uvp.aspect_y = _aspect(w, h)
    uvp.scale_x = uvp.scale_y = 1.0

    # modifier order: subdivision before projection
    names = [m.name for m in obj.modifiers]
    if names.index(MOD_SUBDIV) > names.index(MOD_UVPROJECT):
        with bpy.context.temp_override(object=obj):
            bpy.ops.object.modifier_move_to_index(modifier=MOD_SUBDIV, index=names.index(MOD_UVPROJECT))

    mat = projection_material(img)
    mesh.materials.clear()
    mesh.materials.append(mat)
    obj[PROJECTED] = True
    return level


def ensure_camera_b(scene, cam_a):
    cam_b = camera_b(scene)
    if cam_b is None:
        data = cam_a.data.copy()
        data.name = CAMERA_B_NAME
        data.show_background_images = False
        cam_b = bpy.data.objects.new(CAMERA_B_NAME, data)
        scene.collection.objects.link(cam_b)
        cam_b[ROLE] = ROLE_CAMERA_B
        cam_b.matrix_world = cam_a.matrix_world.copy()
    scene.camera = cam_b
    return cam_b


def project(scene, selected):
    """Set up projection on selected meshes (or the default plane). Returns (targets, skipped, created_b)."""
    from .calibration import camera_a

    props = scene.perspective_projector
    cam = camera_a(scene)
    img = props.image
    meshes = [o for o in selected if o.type == "MESH" and o.get(ROLE) is None]
    skipped = [o for o in selected if o not in meshes and o.get(ROLE) not in ("CAMERA_A", ROLE_CAMERA_B)]
    if not meshes:
        plane = build_plane(scene, cam, props.plane_distance, projection_plane(scene))
        meshes = [plane]
    for obj in meshes:
        setup_projection(scene, cam, img, obj)
    created_b = camera_b(scene) is None
    ensure_camera_b(scene, cam)
    # emission shows the photo unchanged only with the Standard view transform
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    return meshes, skipped, created_b
