# Design

## Context

See proposal.md for motivation. Current Remap (`blender/remap.py`):

- `bake_object` runs two Cycles EMIT bakes inside `_RenderState` (which switches the engine and bake settings and restores them): pass 1 bakes the photo colour (`_emission_only`), pass 2 bakes the projection's in-frame alpha as grey (`_alpha_as_emission`); numpy merges them into one RGBA image.
- `remap_material` builds UV Map -> Image -> Emission, Image alpha -> Mix(Transparent, Emission).
- The photo-projection skill (`C:\Projects\PhotoProjection\skill\photo-projection\scripts\pp_lib.py`) proved the method on three scenes: `bake_visibility` (point light at camera A, SHADOW bake) and `fill_hidden` (seen = visibility x alpha x grazing smoothstep, mixed with a fill texture). Its bake does not guard against the user's own lights or the projection card.

## Goals / Non-Goals

**Goals:**
- Occlusion and back faces masked by default, with no change through camera A.
- Mask stored with the object so it keeps working after camera A is deleted.
- A single obvious place (the Hidden input) for anything that fills hidden areas.

**Non-Goals:**
- Filling hidden areas with real content (inpainting, texture synthesis, Ripper); the add-on only provides the input.
- Masking the live projection before Remap.
- Sky / background keying by brightness on object edges (photo-specific; stays in the skill).
- Hidden-area handling outside camera A's frame (stays transparent).

## Decisions

### 1. Visibility from two direct-light bakes from a point light at camera A
Inside `_RenderState`, add a temporary point light (radius 0, so shadows are hard) at camera A's location, swap the object's surface for a white Diffuse BSDF for the pass, and run a Cycles DIFFUSE bake with only the direct contribution: once with the scene as it is, once with every other object hidden from render (the unoccluded reference). A texel is seen when it gets at least half of its unoccluded light. Back faces get no light in either pass and count as hidden.
Why two passes and a ratio: occluders still carry the projection material (a mix with Transparent), so shadow rays leak a little light through them; an absolute "any light" threshold called much of a box's shadow seen. The ratio also cancels the light's distance falloff and fixes the footprint under a box standing on the floor.
Findings during implementation: the SHADOW bake type returns about 1 for every texel in Blender 5.3 (no shadows at all), so it cannot be used; measured masks now match ray casting from camera A within 0.2 % of texels on a wall behind a box and on a floor with a box standing on it.
Alternative considered: ray casting each texel in Python with `mathutils.bvhtree`; rejected because it is seconds per object at 1024 px and minutes at 4096 px.

### 2. Isolation while baking
The bake must see only the helper light and only real occluders. While the shadow pass runs:
- every other light object gets `hide_render = True` (the world needs nothing: the SHADOW pass only uses lamps);
- the projection card (role `PLANE`) gets `hide_render = True`, because it fills camera A's frame and would shadow everything;
- cameras and empties never cast shadows, nothing to do.
All previous `hide_render` values are recorded and restored in `_RenderState.__exit__`, and the helper light and its data are deleted there, also on errors.

### 3. Grazing factor baked into the mask
The mask is final and self-contained: `mask = seen * facing`, where `facing` comes from a cheap EMIT pass that emits `smoothstep(sin(t), sin(1.5 t), dot(N, normalize(cam - P)))` for threshold angle `t` (camera A's position written into the temporary node tree as a constant). The pass always runs: with `t = 0` it is a hard front/back test, which costs little and backs up the light passes. Baking it (instead of computing it in the final material) is what keeps the result independent of camera A.
The setting is an angle in degrees (`remap_grazing_deg`, 0-45, default 0), easier to read than the skill's raw dot product (its 0.15 is about 8.6 degrees).

### 4. Mask image and material
- Mask: 8-bit greyscale image `<object>_vis`, same resolution as the texture, saved / packed by the same `save_image` path (`textures/<object>_vis.png`), colour space Non-Color.
- Material: the existing graph plus an Image node for the mask on the same UV, and an RGB node labelled **Hidden** feeding a Mix (Color) node: `colour = mix(Hidden, photo, mask)`. Alpha stays the texture's in-frame alpha, so outside the frame is still transparent. Users replace the RGB node by linking anything into the mix's Hidden input; the node keeps the label so scripts can find it.
- Default Hidden colour: median of the baked photo over texels with `mask > 0.5` and `alpha > 0.5`; if there are none (the object is fully hidden), mid grey.

### 5. One Remap, one undo step
The extra passes live inside the existing `remap()` call, so the operator still produces one undo step; the helper light is created and removed within it.

## Risks / Trade-offs

- [Shadow acne or light leaking at contact edges (a box standing on the floor)] -> threshold at 0.5 plus the bake margin; a Blender test with a box on a floor checks that the contact line does not leave a bright or dark seam wider than the margin.
- [A shadow pass with 4 samples is still noisy on large textures] -> the binary threshold removes noise; raise samples only if the test shows speckles.
- [Users who relied on the smeared photo on hidden faces] -> the Hidden input can be set to a texture; the README states the change, and through camera A nothing changes.
- [Remap time grows by roughly one bake] -> acceptable; the grazing pass only runs when the threshold is above 0.

## Migration Plan

Objects remapped with 1.1.0 keep their old material. Remapping again (after Undo, or projecting again) gives the new material with the mask. No file migration is needed.
