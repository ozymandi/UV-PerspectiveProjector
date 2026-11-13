"""End-to-end on real photos: Calibrate -> Project -> move camera B -> Remap, with screenshots.

Run inside a windowed Blender with the extension installed (tests/run_blender.py installs it):

    BLENDER_USER_RESOURCES=build/blender_user blender --python tests/e2e/run_e2e.py

Writes tests/e2e/<blender version>/<photo>_{viewport,through_a,through_b}.png and summary.json, then quits.
Exit code 0 when every photo passes its checks.
"""

import json
import os
import sys
import traceback

import bpy
import numpy as np
from mathutils import Euler, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests", "blender"))
import _helpers as H  # noqa: E402

MEDIA = os.path.join(ROOT, "tests", "data", "media")
OUT = os.path.join(ROOT, "tests", "e2e", f"blender_{bpy.app.version[0]}.{bpy.app.version[1]}")

# photo, manual focal (35 mm eq.) to use when automatic calibration is not confident
PHOTOS = [("warehouse.jpg", None), ("towers_three_point.jpg", None), ("church_nave.jpg", 20.0)]


def screenshot(name):
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name))


def run_photo(photo, manual_focal):
    import cv2

    H.reset_scene()
    ctx = H.window_context()
    path = os.path.join(MEDIA, photo)
    stem = os.path.splitext(photo)[0]
    info = {"photo": photo}
    with bpy.context.temp_override(**ctx):
        bpy.ops.perspective_projector.load_photo("EXEC_DEFAULT", True, filepath=path)
        bpy.ops.perspective_projector.calibrate("EXEC_DEFAULT", True)
    props = H.props()
    info["auto_confidence"] = round(props.confidence, 3)
    info["editor_opened"] = bool(props.editing)
    if props.editing:
        H.check(manual_focal is not None, f"{photo}: editor opened unexpectedly")
        # the user's move in the editor: enter the focal length (one-point photo, no EXIF)
        props.focal_35mm = manual_focal
        props.focal_mode = "MANUAL"
        H.check(props.invalid_pair == -1, f"{photo}: still invalid after manual focal: {props.status}")
        with bpy.context.temp_override(**H.window_context()):
            bpy.ops.perspective_projector.edit_lines()  # finish editing
    cam_a = H.camera_a()
    info["lens_mm"] = round(cam_a.data.lens, 2)
    info["focal_source"] = props.focal_source
    screenshot(f"{stem}_calibrated.png")

    H.set_eevee(bpy.context.scene)
    with bpy.context.temp_override(**H.window_context()):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.ops.perspective_projector.project("EXEC_DEFAULT", True)
    plane = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "PLANE")
    cam_b = next(o for o in bpy.context.scene.objects if o.get("pp_role") == "CAMERA_B")

    # a 3D object in front of the card, so moving camera B shows parallax
    dist = props.plane_distance
    fwd = cam_a.matrix_world.to_3x3() @ Vector((0, 0, -1))
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.mesh.primitive_monkey_add(size=dist * 0.12,
                                          location=cam_a.matrix_world.translation + fwd * dist * 0.45)
    monkey = bpy.context.view_layer.objects.active
    monkey.select_set(False)

    # remap the plane
    with bpy.context.temp_override(**H.window_context()):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        plane.select_set(True)
        bpy.context.view_layer.objects.active = plane
        props.remap_resolution = 2048
        bpy.ops.perspective_projector.remap("EXEC_DEFAULT", True)
    H.check("PP_UVProject" not in plane.modifiers, f"{photo}: remap did not run")

    # through camera A the remapped card still matches the photo
    through_a = H.render_camera(cam_a, f"{stem}_a", percentage=50)
    photo_img = cv2.imread(path)
    photo_small = cv2.resize(photo_img, (through_a.shape[1], through_a.shape[0]), interpolation=cv2.INTER_AREA)
    mask = np.ones(through_a.shape[:2], bool)
    # ignore the monkey: compare only where it is not
    diff = np.abs(through_a[..., :3] - photo_small.astype(np.float32) / 255.0).mean(axis=2)
    info["through_a_mean_diff"] = round(float(np.median(diff[mask])), 4)
    cv2.imwrite(os.path.join(OUT, f"{stem}_through_a.png"), (through_a[..., :3] * 255).astype(np.uint8))

    # move camera B sideways and turn it a little: the card stays put, the monkey shifts
    right = cam_a.matrix_world.to_3x3() @ Vector((1, 0, 0))
    cam_b.location = cam_a.matrix_world.translation + right * dist * 0.12
    cam_b.rotation_euler = (cam_a.matrix_world.to_euler().to_matrix() @
                            Euler((0, np.radians(-4), 0)).to_matrix()).to_euler()
    bpy.context.view_layer.update()
    through_b = H.render_camera(cam_b, f"{stem}_b", percentage=50)
    cv2.imwrite(os.path.join(OUT, f"{stem}_through_b.png"), (through_b[..., :3] * 255).astype(np.uint8))
    info["through_b_differs"] = round(float(np.abs(through_b[..., :3] - through_a[..., :3]).mean()), 4)

    with bpy.context.temp_override(**H.window_context()):
        bpy.context.scene.camera = cam_b
        ctx = H.window_context()
        ctx["region_data"].view_perspective = "CAMERA"
        ctx["space_data"].use_local_camera = False
    screenshot(f"{stem}_viewport_b.png")

    H.check(info["through_a_mean_diff"] < 0.05, f"{photo}: through A differs from the photo")
    H.check(info["through_b_differs"] > 0.005, f"{photo}: camera B view did not change")
    return info


def main():
    os.makedirs(OUT, exist_ok=True)
    results, failed = [], []
    for photo, focal in PHOTOS:
        try:
            info = run_photo(photo, focal)
            info["ok"] = True
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            info = {"photo": photo, "ok": False, "error": str(exc)}
            failed.append(photo)
        results.append(info)
        print("E2E", json.dumps(info))
    summary = {"blender": bpy.app.version_string, "results": results}
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    sys.stdout.flush()
    os._exit(1 if failed else 0)


bpy.app.timers.register(lambda: main() or None, first_interval=1.5)
