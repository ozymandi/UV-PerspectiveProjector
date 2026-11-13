"""Perspective Projector: calibrate a camera from a photo, project the photo, remap it to UVs.

Blender-specific modules are imported lazily inside register() so that the pure
maths in ``core`` can be imported and tested without Blender.
"""


def register():
    from .blender import register as _register

    _register()


def unregister():
    from .blender import unregister as _unregister

    _unregister()
