"""5.1: a real mouse drag on a handle (simulated events) moves the endpoint and camera A."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import _helpers as H  # noqa: E402
import bpy  # noqa: E402

state = {}


def setup():
    from bl_ext.user_default.perspective_projector.blender import calibration, editor, view

    H.reset_scene()
    path, _ = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
    ctx = H.window_context()
    with bpy.context.temp_override(**ctx):
        H.load(path)
        bpy.ops.perspective_projector.calibrate()
        bpy.ops.perspective_projector.edit_lines()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    ctx = H.window_context()
    with bpy.context.temp_override(**ctx):
        rect = view.camera_frame_region(bpy.context, calibration.camera_a(bpy.context.scene))
    u, v = editor.get_point(bpy.context.scene, 1)
    x, y = view.image_to_region(rect, u, v)
    region = ctx["region"]
    state.update(win=ctx["window"], rect=rect, start=(u, v),
                 wx=int(region.x + x), wy=int(region.y + y), rot0=H.rotation_np(H.camera_a()).copy())


def steps():
    win = state["win"]
    wx, wy = state["wx"], state["wy"]
    yield lambda: win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=wx, y=wy)
    yield lambda: win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=wx, y=wy)
    yield lambda: win.event_simulate(type="LEFTMOUSE", value="PRESS", x=wx, y=wy)
    for k in range(1, 9):
        yield (lambda k=k: win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=wx, y=wy - 5 * k))
    yield lambda: win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=wx, y=wy - 40)


def check():
    from bl_ext.user_default.perspective_projector.blender import editor, view

    u, v = editor.get_point(bpy.context.scene, 1)
    expect_u, expect_v = view.region_to_image(state["rect"], state["wx"] - H.window_context()["region"].x,
                                              state["wy"] - 40 - H.window_context()["region"].y)
    print("moved", state["start"], "->", (u, v), "expected", (expect_u, expect_v))
    H.check(abs(u - expect_u) < 0.003 and abs(v - expect_v) < 0.003, "endpoint did not follow the cursor")
    H.check(not np.allclose(H.rotation_np(H.camera_a()), state["rot0"], atol=1e-4), "camera did not change")


def main():
    import traceback

    try:
        setup()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        os._exit(1)
    it = steps()

    def tick():
        try:
            next(it)()
            return 0.05
        except StopIteration:
            try:
                check()
                print("UI TEST PASSED")
                code = 0
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                code = 1
            sys.stdout.flush()
            os._exit(code)

    bpy.app.timers.register(tick, first_interval=0.3)


bpy.app.timers.register(lambda: main() or None, first_interval=1.5)
