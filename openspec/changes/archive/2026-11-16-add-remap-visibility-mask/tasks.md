# Tasks

## 1. Visibility bake

- [x] 1.1 Add the visibility passes to `bake_object` (two direct-light DIFFUSE bakes, see design decision 1; the SHADOW bake type does not work in Blender 5.3) in `blender/remap.py`: temporary point light at camera A, other lights and the projection card hidden from render, seen where the texel gets at least half of its unoccluded direct light, everything restored in `_RenderState.__exit__` (also on errors); verify a Blender test where a projected wall with a box in front gets a black shadow region and white elsewhere, and a box's back faces are black
- [x] 1.2 Verify isolation: in `tests/blender/test_visibility.py` the same wall remapped with and without a strong sun gives masks that differ in under 0.5 % of texels, and after Remap the sun, the projection card and the absence of a helper light are as before

## 2. Grazing threshold

- [x] 2.1 Add `remap_grazing_deg` (0-45, default 0) to `props.py`, the EMIT facing pass (a hard front/back test at 0) multiplied into the mask, and the field in the Projection panel; verify a Blender test on a shallow floor: default mask all white inside the frame, 5 degrees hides part of the floor but not all of it (between 5 % and 95 %)

## 3. Mask image and material

- [x] 3.1 Save the mask as `<object>_vis` (Non-Color) through `save_image` next to the texture, or pack it in unsaved files; verify the saved-file and unsaved-file cases in `test_visibility.py`
- [x] 3.2 Extend `remap_material` with the mask Image node, the Hidden RGB node (label `Hidden`, default = median of visible texels, mid grey when nothing is visible) and the colour Mix; verify: render through camera A matches the pre-Remap render (same tolerance as now), a render from camera B on the box's back faces shows a flat colour within 10 % of the visible median, and linking an image into the Hidden input shows it on hidden areas only
- [x] 3.3 Verify a box standing on a floor leaves no seam wider than the bake margin along the contact line in either object's mask

## 4. Docs and integration

- [x] 4.1 README: Remap section (mask, Hidden input, grazing threshold) and remove the occlusion item from Known limitations; verify the panel labels match the text
- [x] 4.2 Run `python -m pytest tests/core` and `python tests/run_blender.py` on Blender 5.3 and verify all pass; check the undo test still restores the live projection in one step

## Workflow follow-up

- Archive the change after review and bump the add-on version.
- In the photo-projection skill, replace `bake_visibility` / the mask part of `fill_hidden` with the add-on's mask and plug the Ripper texture into the Hidden input.
