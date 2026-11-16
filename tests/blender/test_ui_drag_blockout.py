"""2.2: the blockout tools run as modal click tools: Esc cancels without changes, three clicks build a wall.
("drag" in the name: run_blender.py enables event simulation for it.)"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _helpers as H  # noqa: E402
import bpy  # noqa: E402

state = {}


def ctx():
    return H.window_context()


def blockout():
    from bl_ext.user_default.perspective_projector.blender import blockout as BL

    return BL.blockout_objects(bpy.context.scene)


def to_window(uv):
    from bl_ext.user_default.perspective_projector.blender import calibration, view

    c = ctx()
    with bpy.context.temp_override(**c):
        rect = view.camera_frame_region(bpy.context, calibration.camera_a(bpy.context.scene))
    x, y = view.image_to_region(rect, *uv)
    return int(c["region"].x + x), int(c["region"].y + y)


def setup():
    H.reset_scene()
    path, synth = H.make_photo(yaw_deg=-35, pitch_deg=-14, focal_px=3000)
    with bpy.context.temp_override(**ctx()):
        H.load(path)
        bpy.ops.perspective_projector.calibrate(open_editor=False)
    state["synth"], state["win"] = synth, ctx()["window"]


def uv_of(p):
    q = state["synth"].project(p)
    return (q[0] / 4000.0, q[1] / 3000.0)


def click(uv):
    x, y = to_window(uv)
    win = state["win"]
    return [lambda: win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y),
            lambda: win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y),
            lambda: win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)]


def start(op):
    def run():
        with bpy.context.temp_override(**ctx()):
            res = getattr(bpy.ops.perspective_projector, op)("INVOKE_DEFAULT")
        H.check(res == {"RUNNING_MODAL"}, f"{op} did not start: {res}")
        with bpy.context.temp_override(**ctx()):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    return run


def steps():
    win = state["win"]
    # Box tool: one click, then Esc -> nothing created
    yield start("blockout_box")
    for f in click(uv_of((-2.0, 4.0, 0.0))):
        yield f
    yield lambda: win.event_simulate(type="ESC", value="PRESS", x=10, y=10)
    yield lambda: win.event_simulate(type="ESC", value="RELEASE", x=10, y=10)
    yield lambda: state.update(after_cancel=len(blockout()))
    # Wall tool: two base clicks and a top click -> one wall
    yield start("blockout_wall")
    for p in [(1.8, 6.0, 0.0), (3.8, 6.0, 0.0), (3.8, 6.0, 2.5)]:
        for f in click(uv_of(p)):
            yield f


def check():
    import numpy as np

    H.check(state["after_cancel"] == 0, f"cancelled tool left {state['after_cancel']} objects")
    obs = blockout()
    H.check(len(obs) == 1 and obs[0].name.startswith("Wall"), f"wall not built by clicks: {[o.name for o in obs]}")
    vs = [np.array(obs[0].matrix_world @ v.co) for v in obs[0].data.vertices]
    zs = sorted(round(float(v[2]), 1) for v in vs)
    print("wall built by clicks:", [tuple(np.round(v, 2)) for v in vs])
    H.check(zs[0] < 0.2 and zs[-1] > 2.0, f"wall heights {zs}")
    H.check(bpy.context.workspace.status_text_set is not None, "status text api")


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
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            sys.stdout.flush()
            os._exit(1)

    bpy.app.timers.register(tick, first_interval=0.3)


bpy.app.timers.register(lambda: main() or None, first_interval=1.5)
