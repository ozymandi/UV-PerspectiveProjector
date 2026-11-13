"""Shared helpers for tests that run inside background Blender."""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_TESTS = os.path.join(os.path.dirname(HERE), "core")
for p in (HERE, CORE_TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

TMP = tempfile.mkdtemp(prefix="pp_test_")


def make_photo(name="scene.png", seed=1, **cam_params):
    """Render a synthetic photo of a known camera, save it as PNG, return (path, SynthCamera)."""
    import cv2
    from render import render_scene
    from synth import SynthCamera

    cam = SynthCamera(**cam_params)
    img = render_scene(cam, seed=seed)
    path = os.path.join(TMP, name)
    cv2.imwrite(path, img)
    return path, cam


def reset_scene():
    bpy.ops.wm.read_homefile(use_empty=True)


def props():
    return bpy.context.scene.perspective_projector


def load(path):
    return bpy.ops.perspective_projector.load_photo(filepath=path)


def camera_a():
    for obj in bpy.context.scene.objects:
        if obj.get("pp_role") == "CAMERA_A":
            return obj
    return None


def to_frame(cam_obj, point):
    """Normalised image coords (u right, v down) of a world point seen by ``cam_obj``."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    co = world_to_camera_view(bpy.context.scene, cam_obj, Vector(point))
    return np.array([co.x, 1.0 - co.y])


def rotation_np(cam_obj):
    return np.array(cam_obj.matrix_world.to_3x3())


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def run_ui_test(fn, delay=1.0):
    """Run ``fn()`` from a timer once the window exists, then exit Blender with 0 / 1."""
    import os
    import traceback

    def _tick():
        code = 0
        try:
            fn()
            print("UI TEST PASSED")
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            code = 1
        import sys

        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)

    bpy.app.timers.register(_tick, first_interval=delay)


def window_context():
    """Context override for operators that need a window and a 3D view."""
    win = bpy.context.window_manager.windows[0]
    area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    if area is None:
        area = win.screen.areas[0]
        area.type = "VIEW_3D"
    region = next(r for r in area.regions if r.type == "WINDOW")
    return dict(window=win, screen=win.screen, area=area, region=region,
                space_data=area.spaces.active, region_data=area.spaces.active.region_3d)


def undo():
    with bpy.context.temp_override(**window_context()):
        bpy.ops.ed.undo()


def set_eevee(scene):
    items = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in items else "BLENDER_EEVEE_NEXT"


def render_camera(cam_obj, name, percentage=25, transparent=False):
    """Render through ``cam_obj``; returns BGRA float array (0..1, top-down)."""
    import cv2

    scene = bpy.context.scene
    prev = (scene.camera, scene.render.resolution_percentage, scene.render.film_transparent)
    scene.camera = cam_obj
    scene.render.resolution_percentage = percentage
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    path = os.path.join(TMP, name + ".png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    scene.camera, scene.render.resolution_percentage, scene.render.film_transparent = prev
    return cv2.imread(path, cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0


def photo_gray_resized(path, size):
    import cv2

    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def corners_in_view(cam_obj, obj):
    mw = obj.matrix_world
    return sorted((round(float(c[0]), 4), round(float(c[1]), 4))
                  for c in (to_frame(cam_obj, mw @ v.co) for v in obj.data.vertices))
