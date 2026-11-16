"""Calibration state stored on the scene (saved with the .blend)."""

import bpy

AXIS_ITEMS = [("X", "X", "World X axis"), ("Y", "Y", "World Y axis"), ("Z", "Z", "World Z axis (up)")]

# 8 endpoints = 2 pairs x 2 lines x 2 points, normalised image coords (0..1, origin top-left)
DEFAULT_LINES = (
    0.10, 0.62, 0.45, 0.55,  0.10, 0.85, 0.45, 0.70,   # pair 0
    0.55, 0.55, 0.90, 0.62,  0.55, 0.70, 0.90, 0.85,   # pair 1
)
# optional third pair (stored separately so 1.0.0 files keep their 16 values)
DEFAULT_LINES3 = (0.30, 0.15, 0.30, 0.45,  0.70, 0.15, 0.70, 0.45)


def _plane_distance(self, context):
    from . import projection

    projection.update_plane_distance(context.scene)


def _reapply(self, context):
    from . import calibration

    calibration.reapply_if_calibrated(context.scene)


class PP_Calibration(bpy.types.PropertyGroup):
    image: bpy.props.PointerProperty(type=bpy.types.Image, name="Photo")

    # vanishing lines
    lines: bpy.props.FloatVectorProperty(size=16, default=DEFAULT_LINES, update=_reapply)
    pair0_axis: bpy.props.EnumProperty(items=AXIS_ITEMS, default="X", name="Pair 1 axis", update=_reapply)
    pair1_axis: bpy.props.EnumProperty(items=AXIS_ITEMS, default="Y", name="Pair 2 axis", update=_reapply)
    lines3: bpy.props.FloatVectorProperty(size=8, default=DEFAULT_LINES3, update=_reapply)
    pair2_enabled: bpy.props.BoolProperty(
        name="Third pair", default=False, update=_reapply,
        description="A third pair of lines on the remaining axis; with three converging pairs "
                    "the lens shift is solved from them")
    calibrated: bpy.props.BoolProperty(default=False)
    swap_xy: bpy.props.BoolProperty(default=False, name="Swap X/Y", update=_reapply)

    # focal length
    focal_mode: bpy.props.EnumProperty(
        name="Focal length",
        items=[("AUTO", "Auto", "From vanishing points; EXIF or the manual value when the photo does not constrain it"),
               ("MANUAL", "Manual", "Always use the manual 35 mm-equivalent value")],
        default="AUTO", update=_reapply)
    focal_35mm: bpy.props.FloatProperty(name="Focal (35 mm equiv.)", default=35.0, min=1.0, max=2000.0,
                                        unit="CAMERA", update=_reapply)
    exif_focal_px: bpy.props.FloatProperty(default=0.0)
    exif_label: bpy.props.StringProperty(default="")
    focal_source: bpy.props.StringProperty(default="")
    shift_source: bpy.props.StringProperty(default="")  # "", "vertical" or "three vanishing points"

    # position and scale
    camera_height: bpy.props.FloatProperty(name="Camera height", default=1.6, min=0.001, unit="LENGTH",
                                           update=_reapply)
    origin_set: bpy.props.BoolProperty(default=False, update=_reapply)
    origin: bpy.props.FloatVectorProperty(size=2, default=(0.5, 0.5), update=_reapply)
    ref_enabled: bpy.props.BoolProperty(name="Use reference distance", default=False, update=_reapply)
    ref_axis: bpy.props.EnumProperty(items=AXIS_ITEMS, default="X", name="Reference axis", update=_reapply)
    ref_p0: bpy.props.FloatVectorProperty(size=2, default=(0.4, 0.8), update=_reapply)
    ref_p1: bpy.props.FloatVectorProperty(size=2, default=(0.6, 0.8), update=_reapply)
    ref_distance: bpy.props.FloatProperty(name="Distance", default=1.0, min=0.0001, unit="LENGTH", update=_reapply)
    effective_height: bpy.props.FloatProperty(default=0.0)

    # known size: two ground segments, one along each horizontal axis
    size_enabled: bpy.props.BoolProperty(
        name="Use known size", default=False, update=_reapply,
        description="Solve the focal length (when the lines cannot) and the scale from two ground "
                    "segments of known length, one along each horizontal axis")
    size_a_p0: bpy.props.FloatVectorProperty(size=2, default=(0.40, 0.80), update=_reapply)
    size_a_p1: bpy.props.FloatVectorProperty(size=2, default=(0.45, 0.65), update=_reapply)
    size_a_length: bpy.props.FloatProperty(name="Length A", default=1.0, min=0.0001, unit="LENGTH",
                                           update=_reapply)
    size_b_p0: bpy.props.FloatVectorProperty(size=2, default=(0.35, 0.85), update=_reapply)
    size_b_p1: bpy.props.FloatVectorProperty(size=2, default=(0.60, 0.85), update=_reapply)
    size_b_length: bpy.props.FloatProperty(name="Length B", default=1.0, min=0.0001, unit="LENGTH",
                                           update=_reapply)

    # reporting
    confidence: bpy.props.FloatProperty(default=0.0)
    status: bpy.props.StringProperty(default="")
    invalid_pair: bpy.props.IntProperty(default=-1)
    lock_updates: bpy.props.BoolProperty(default=False)
    editing: bpy.props.BoolProperty(default=False, name="Editing lines")

    # projection
    plane_distance: bpy.props.FloatProperty(name="Plane distance", default=10.0, min=0.01, unit="LENGTH",
                                            update=_plane_distance)
    remap_resolution: bpy.props.IntProperty(name="Remap resolution", default=0, min=0, max=16384,
                                            description="Size of the baked texture; 0 = automatic")
    remap_grazing_deg: bpy.props.FloatProperty(
        name="Grazing threshold", default=0.0, min=0.0, max=45.0, precision=1,
        description="Surfaces seen from camera A at less than this angle (degrees) also count as hidden "
                    "and show the Hidden colour; 0 keeps them, so the view through camera A is unchanged")


_classes = (PP_Calibration,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.perspective_projector = bpy.props.PointerProperty(type=PP_Calibration)


def unregister():
    del bpy.types.Scene.perspective_projector
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
