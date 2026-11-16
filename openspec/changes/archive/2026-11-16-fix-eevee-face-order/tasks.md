# Tasks

## 1. Materials

- [x] 1.1 Switch `projection_material` in `blender/projection.py` to DITHERED (fallback `blend_method = "HASHED"`) and raise its `pp_version` mark to 3; verify a Blender test that a file with an old `pp_version` 2 BLENDED material gets a new DITHERED material on Project
- [x] 1.2 Switch `remap_material` in `blender/remap.py` to DITHERED (same fallback); verify the material of a remapped object reports DITHERED

## 2. Face order

- [x] 2.1 Add `tests/blender/test_face_order.py`: a projected box and a remapped box rendered from behind in EEVEE match the Cycles render of the same view (mean difference under 0.03 on the box pixels), and the remapped box's back faces show the Hidden colour within 0.03; verify it fails with the old BLENDED setting and passes with DITHERED
- [x] 2.2 Remove the Cycles workaround for back faces from `tests/blender/test_visibility.py` (render them in EEVEE) and verify the test still passes

## 3. Docs and integration

- [x] 3.1 README: note in the Remap section that objects remapped with 1.2.0 or earlier keep their old material and show faces through faces in EEVEE until remapped again; in `release/listing.md` (which had no EEVEE limitation) note the same for old objects; verify the text matches the behaviour
- [x] 3.2 Run `python -m pytest tests/core` and `python tests/run_blender.py` on Blender 5.3 and verify all pass, including the frame-transparency checks in `test_project.py` and `test_remap.py`

## Workflow follow-up

- Archive the change after review and bump the add-on version (1.2.1).
