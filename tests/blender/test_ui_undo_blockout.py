"""3.6 + 4.1: one Ctrl+Z removes a box and nothing else; the alignment overlay follows objects and
draws only through camera A (needs a window)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _helpers as H  # noqa: E402
import bpy  # noqa: E402


def names():
    return sorted(o.name for o in bpy.context.scene.objects)


def test():
    from bl_ext.user_default.perspective_projector.blender import blockout as BL
    from bl_ext.user_default.perspective_projector.blender import calibration, view

    H.reset_scene()
    path, synth = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)

    def uv(p):
        q = synth.project(p)
        return {"name": "p", "uv": (q[0] / 4000.0, q[1] / 3000.0)}

    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.perspective_projector.load_photo("EXEC_DEFAULT", True, filepath=path)
        bpy.ops.perspective_projector.calibrate("EXEC_DEFAULT", True, open_editor=False)
        bpy.ops.perspective_projector.blockout_box(
            "EXEC_DEFAULT", True, points=[uv((-2, 4, 0)), uv((-0.8, 4.5, 0)), uv((-0.8, 4.5, 0.5))])
        before = names()
        bpy.ops.perspective_projector.blockout_box(
            "EXEC_DEFAULT", True, points=[uv((0, 3, 0)), uv((1.2, 4, 0)), uv((1.2, 4, 0.75))])
    H.check(len(names()) == len(before) + 1, "second box not created")

    # ---- 3.6 one undo step removes only the last box
    H.undo()
    H.check(names() == before, f"after undo {names()} != {before}")
    H.check(H.camera_a() is not None, "undo went too far")

    # ---- 4.1 overlay: through camera A, follows the box, nothing otherwise
    box = BL.blockout_objects(bpy.context.scene)[0]
    props = H.props()
    props.blockout_overlay = True
    c = H.window_context()
    with bpy.context.temp_override(**c):
        view.look_through(bpy.context, calibration.camera_a(bpy.context.scene))
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    c = H.window_context()
    with bpy.context.temp_override(**c):
        segs0 = BL.overlay_segments(bpy.context)
    H.check(len(segs0) >= 12, f"overlay draws {len(segs0)} edges for a box")
    box.location.x += 0.1
    bpy.context.view_layer.update()
    with bpy.context.temp_override(**H.window_context()):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    c = H.window_context()
    with bpy.context.temp_override(**c):
        segs1 = BL.overlay_segments(bpy.context)
    H.check(len(segs1) == len(segs0), f"overlay edges {len(segs0)} -> {len(segs1)} after moving the box")
    moved = max(abs(a[0][0] - b[0][0]) + abs(a[0][1] - b[0][1]) for a, b in zip(segs0, segs1))
    print("overlay edges moved by up to", moved, "px for 10 cm")
    H.check(moved > 0.5, "overlay did not follow the moved box")
    c["region_data"].view_perspective = "PERSP"
    with bpy.context.temp_override(**c):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        H.check(BL.overlay_segments(bpy.context) == [], "overlay draws outside camera A")
    props.blockout_overlay = False
    c["region_data"].view_perspective = "CAMERA"
    with bpy.context.temp_override(**c):
        H.check(BL.overlay_segments(bpy.context) == [], "overlay draws while switched off")


H.run_ui_test(test)
