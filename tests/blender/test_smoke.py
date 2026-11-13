"""Runs inside background Blender via tests/run_blender.py."""

import bpy

assert any("perspective_projector" in name for name in bpy.context.preferences.addons.keys()), "extension not enabled"
assert hasattr(bpy.types, "PP_PT_main"), "panel not registered"
print("smoke ok")
