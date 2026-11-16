"""Blender layer: properties, operators, panel, viewport editor."""

from . import blockout, editor, ops_calibrate, ops_project, props, ui

_modules = (props, ops_calibrate, editor, ops_project, blockout, ui)


def register():
    for module in _modules:
        module.register()


def unregister():
    for module in reversed(_modules):
        module.unregister()
