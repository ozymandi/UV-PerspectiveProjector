"""Group 5 + 4.4: manual line editor (needs a window for gizmos and drawing)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402

SHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "build", "editor_shot.png")


def redraw():
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


def test():
    from bl_ext.user_default.perspective_projector.blender import editor

    scene_ctx = H.window_context()
    # ---- 4.4: a photo without straight edges opens the editor with lines placed
    import cv2

    rng = np.random.default_rng(3)
    noise = cv2.GaussianBlur((rng.random((1200, 1600)) * 255).astype(np.uint8), (0, 0), 6)
    noise_path = os.path.join(H.TMP, "noise.png")
    cv2.imwrite(noise_path, noise)
    H.reset_scene()
    scene_ctx = H.window_context()
    with bpy.context.temp_override(**scene_ctx):
        H.load(noise_path)
        bpy.ops.perspective_projector.calibrate()
    props = H.props()
    H.check(props.editing, "editor did not open for a low-confidence photo")
    H.check(props.confidence < 0.5, f"confidence {props.confidence}")
    H.check("not confident" in props.status, props.status)

    # ---- editor on a good photo
    H.reset_scene()
    scene_ctx = H.window_context()
    path, synth = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
    with bpy.context.temp_override(**scene_ctx):
        H.load(path)
        bpy.ops.perspective_projector.calibrate()
        props = H.props()
        H.check(not props.editing, "editor opened for a confident photo")
        bpy.ops.perspective_projector.edit_lines()
    H.check(props.editing, "edit_lines did not start editing")
    cam = H.camera_a()
    rv3d = scene_ctx["region_data"]
    H.check(rv3d.view_perspective == "CAMERA", "view is not through camera A")

    # lines reproduce the current camera (seeded from detection)
    rot0 = H.rotation_np(cam).copy()
    lens0 = cam.data.lens
    lines_before = list(props.lines)
    props.lines = lines_before
    H.check(np.allclose(H.rotation_np(cam), rot0, atol=1e-6), "re-solving from lines changed the camera")

    redraw()
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.screen.screenshot(filepath=SHOT)

    # ---- dragging an endpoint (same path as the gizmo setter) rotates camera A live
    u, v = editor.get_point(bpy.context.scene, 0)
    editor.set_point(bpy.context.scene, 0, u, v + 0.03)
    H.check(not np.allclose(H.rotation_np(cam), rot0, atol=1e-4), "camera did not follow the drag")
    H.check(props.invalid_pair == -1, "valid drag flagged invalid")
    editor.set_point(bpy.context.scene, 0, u, v)
    H.check(np.allclose(H.rotation_np(cam), rot0, atol=1e-5), "camera did not return")

    # ---- degenerate: make pair 2 lines parallel -> flagged, camera keeps last valid state
    vals = list(props.lines)
    # pair 1 = points 4..7; make line B = line A shifted down
    a0, a1 = (vals[8], vals[9]), (vals[10], vals[11])
    vals[12], vals[13] = a0[0], a0[1] + 0.1
    vals[14], vals[15] = a1[0], a1[1] + 0.1
    props.lines = vals
    H.check(props.invalid_pair == 1, f"invalid pair {props.invalid_pair}")
    H.check(np.allclose(H.rotation_np(cam), rot0, atol=1e-5), "invalid lines changed the camera")
    H.check(abs(cam.data.lens - lens0) < 1e-6, "invalid lines changed the lens")
    # with a manual focal length the same parallel pair is a valid one-point setup
    props.focal_35mm = 30.0
    props.focal_mode = "MANUAL"
    H.check(props.invalid_pair == -1, "parallel pair rejected despite manual focal")
    props.focal_mode = "AUTO"
    props.lines = lines_before
    H.check(props.invalid_pair == -1, "flag not cleared")
    H.check(np.allclose(H.rotation_np(cam), rot0, atol=1e-5), "camera not restored")

    # toggle off
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.perspective_projector.edit_lines()
    H.check(not props.editing, "edit_lines did not stop editing")


H.run_ui_test(test, delay=1.5)
