"""Screenshots and the featured image for the extensions.blender.org listing.

Needs the test photos in tests/data/media and the extension installed (tests/run_blender.py does that):

    BLENDER_USER_RESOURCES=build/blender_user blender --python release/make_screenshots.py

Writes build/release_assets/*.png (kept out of git: they contain the stock photos) and quits.
"""

import math
import os
import sys
import traceback

import bpy
from mathutils import Euler, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "blender"))
import _helpers as H  # noqa: E402

MEDIA = os.path.join(ROOT, "tests", "data", "media")
OUT = os.path.join(ROOT, "build", "release_assets")


def ctx():
    return H.window_context()


def view3d():
    c = ctx()
    return c["area"], c["space_data"], c["region_data"]


def setup_window():
    area, space, rv3d = view3d()
    # region visibility triggers a window-level update: set it with a window in context
    with bpy.context.temp_override(**ctx()):
        space.show_region_ui = True
        space.show_region_toolbar = False
    space.overlay.show_floor = True


def sidebar_region():
    area, space, rv3d = view3d()
    return next(r for r in area.regions if r.type == "UI")


def fresh_scene():
    """Empty the scene without reloading the file (a reload would reset the sidebar tab)."""
    scene = bpy.context.scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj)
    for coll in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights, bpy.data.materials, bpy.data.images):
        for block in list(coll):
            if block.users == 0 or block.name.startswith(("PP_", "Proj_", "Render_Cam_B")):
                coll.remove(block)
    scene.property_unset("perspective_projector")
    scene.camera = None
    area, space, rv3d = view3d()
    space.use_local_camera = False
    space.shading.type = "SOLID"


def shot(name, ui=True):
    """Generator step: apply sidebar visibility, let it redraw, then capture the 3D View area.

    A full-window screenshot cropped to the area (screenshot_area from a timer gives 1x1 px).
    """
    import cv2

    area, space, rv3d = view3d()
    with bpy.context.temp_override(**ctx()):
        space.show_region_ui = ui
    yield 1.0
    area, space, rv3d = view3d()
    win = ctx()["window"]
    path = os.path.join(OUT, name)
    with bpy.context.temp_override(**ctx()):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        bpy.ops.screen.screenshot(filepath=path)
    img = cv2.imread(path)
    h_img, w_img = img.shape[:2]
    sx, sy = w_img / win.width, h_img / win.height
    x0, x1 = int(area.x * sx), int((area.x + area.width) * sx)
    y0 = int((win.height - area.y - area.height) * sy)
    y1 = int((win.height - area.y) * sy)
    cv2.imwrite(path, img[y0:y1, x0:x1])


def load_and_calibrate(photo):
    fresh_scene()
    with bpy.context.temp_override(**ctx()):
        bpy.ops.perspective_projector.load_photo(filepath=os.path.join(MEDIA, photo))
        bpy.ops.perspective_projector.calibrate()
    return H.props()


def add_subject(cam_a, dist):
    """A shaded object in front of the card, so camera B shows parallax."""
    fwd = cam_a.matrix_world.to_3x3() @ Vector((0, 0, -1))
    up = Vector((0, 0, 1))
    with bpy.context.temp_override(**ctx()):
        bpy.ops.mesh.primitive_monkey_add(size=dist * 0.14,
                                          location=cam_a.matrix_world.translation + fwd * dist * 0.4 - up * dist * 0.02)
    obj = bpy.context.view_layer.objects.active
    with bpy.context.temp_override(**ctx(), object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.shade_smooth()
    obj.modifiers.new("Smooth", "SUBSURF").levels = 2
    mat = bpy.data.materials.new("Subject")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.42, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.35
    obj.data.materials.append(mat)
    obj.rotation_euler = Euler((math.radians(90), 0, cam_a.matrix_world.to_euler().z + math.pi))
    obj.select_set(False)
    return obj


def run():
    """Generator: yields seconds to wait so the window can redraw and compile shaders."""
    os.makedirs(OUT, exist_ok=True)

    # 1. automatic calibration on a three-point photo, with the lines shown
    props = load_and_calibrate("towers_three_point.jpg")
    with bpy.context.temp_override(**ctx()):
        bpy.ops.perspective_projector.edit_lines()
    yield from settle()
    yield from shot("01_calibrate_three_point.png")

    # 2. one-point photo: the editor opens, the user enters a focal length
    props = load_and_calibrate("church_nave.jpg")
    props.focal_35mm = 20.0
    props.focal_mode = "MANUAL"
    from bl_ext.user_default.perspective_projector.blender import editor
    with bpy.context.temp_override(**ctx()):
        editor.start_editing(bpy.context)
    yield from settle()
    yield from shot("02_editor_one_point.png")

    # 3. projection overview and 4. view through the moved camera B
    props = load_and_calibrate("warehouse.jpg")
    cam_a = H.camera_a()
    with bpy.context.temp_override(**ctx()):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.ops.perspective_projector.project()
    cam_b = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "CAMERA_B")
    dist = props.plane_distance
    subject = add_subject(cam_a, dist)
    right = cam_a.matrix_world.to_3x3() @ Vector((1, 0, 0))
    cam_b.location = cam_a.matrix_world.translation + right * dist * 0.14
    cam_b.rotation_euler = (cam_a.matrix_world.to_3x3() @ Euler((0, math.radians(-5), 0)).to_matrix()).to_euler()
    bpy.context.view_layer.update()

    area, space, rv3d = view3d()
    space.shading.type = "MATERIAL"
    space.use_local_camera = False
    # overview from above and to the side of the two cameras
    plane = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "PLANE")
    centre = (cam_a.matrix_world.translation + plane.matrix_world.translation) / 2
    yaw = cam_a.matrix_world.to_euler().z
    rv3d.view_perspective = "PERSP"
    rv3d.view_location = centre
    rv3d.view_rotation = Euler((math.radians(62), 0, yaw - math.radians(55))).to_quaternion()
    rv3d.view_distance = dist * 1.55
    space.lens = 40
    yield from settle(min_wait=3.0)
    yield from shot("03_projection_overview.png")
    yield from settle()
    yield from shot("featured_source.png", ui=False)

    bpy.context.scene.camera = cam_b
    rv3d.view_perspective = "CAMERA"
    yield from settle()
    yield from shot("04_camera_b_parallax.png")

    # 5. remap and show the baked texture moving with the card
    with bpy.context.temp_override(**ctx()):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        plane.select_set(True)
        bpy.context.view_layer.objects.active = plane
        props.remap_resolution = 2048
        bpy.ops.perspective_projector.remap()
    subject.hide_set(True)
    plane.rotation_euler.rotate_axis("Y", math.radians(-18))
    bpy.context.view_layer.update()
    rv3d.view_perspective = "PERSP"
    rv3d.view_location = plane.matrix_world.translation
    rv3d.view_rotation = Euler((math.radians(75), 0, yaw + math.radians(20))).to_quaternion()
    rv3d.view_distance = dist * 0.95
    yield from settle()
    yield from shot("05_remapped_card.png")


def settle(min_wait=1.0):
    """Let the window redraw and EEVEE finish compiling shaders before a screenshot."""
    yield min_wait
    for _ in range(120):
        if not bpy.app.is_job_running("SHADER_COMPILATION"):
            break
        yield 0.5
    yield 0.5


def hide_other_sidebar_tabs():
    """Throwaway session only: unregister the other 3D View sidebar panels, so Projector is the only tab.

    The active sidebar tab cannot be set from Python (read-only), and this session is never saved.
    """
    def walk(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from walk(sub)

    for cls in list(walk(bpy.types.Panel)):
        if (getattr(cls, "bl_space_type", "") == "VIEW_3D" and getattr(cls, "bl_region_type", "") == "UI"
                and getattr(cls, "bl_category", "") != "Projector" and cls.is_registered):
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError:
                pass


def main():
    def finish(code):
        sys.stdout.flush()
        os._exit(code)

    try:
        H.reset_scene()
        setup_window()
        hide_other_sidebar_tabs()
        steps = run()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        finish(1)

    def tick():
        try:
            return next(steps)
        except StopIteration:
            print("SCREENSHOTS DONE")
            finish(0)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            finish(1)

    bpy.app.timers.register(tick, first_interval=1.0)


bpy.app.timers.register(lambda: main() or None, first_interval=1.5)
