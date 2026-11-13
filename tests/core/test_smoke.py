def test_core_imports_without_bpy():
    import perspective_projector.core  # noqa: F401
    import sys

    assert "bpy" not in sys.modules
