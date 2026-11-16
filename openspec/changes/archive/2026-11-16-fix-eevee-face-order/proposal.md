# Proposal

## Why

In EEVEE, a projected or remapped object can show its own far faces through its near faces: a box seen from behind shows the photo of its front mixed into its back faces. Both materials use the BLENDED render method, which does not write depth, and EEVEE does not sort faces within one object. The tests for the visibility mask had to render back faces with Cycles for this reason. Fly-throughs with camera B in EEVEE are the add-on's main use, so every box in a scene is affected.

## What Changes

- The live projection material and the material created by Remap use the DITHERED render method instead of BLENDED. DITHERED writes depth, so EEVEE draws faces in the right order. Transparency outside camera A's frame keeps working: the opacity is 0 or 1, so dithering leaves no visible noise at the frame edge.
- Project no longer reuses a projection material made by an earlier version of the add-on; it builds a fresh one with the new render method.
- Objects remapped with an earlier version keep their old material; remapping again gives the new one (noted in the README).

## Capabilities

### New Capabilities

### Modified Capabilities
- `camera-projection`: new requirement that projected objects render with correct face order in EEVEE.
- `projection-remap`: new requirement that remapped objects render with correct face order in EEVEE.

## Impact

- Code: `perspective_projector/blender/projection.py` (`projection_material`: render method, material version mark) and `perspective_projector/blender/remap.py` (`remap_material`: render method).
- Tests: a new EEVEE case for the back faces of a projected and a remapped box; the existing transparency-outside-the-frame checks in `tests/blender/test_project.py` and `test_remap.py` must still pass in EEVEE and Cycles.
- No change in Cycles, which ignores the render method. No new dependencies.
