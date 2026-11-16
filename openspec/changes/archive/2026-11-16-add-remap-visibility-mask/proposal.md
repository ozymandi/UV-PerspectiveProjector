# Proposal

## Why

After Remap, every texel gets a piece of the photo, including texels camera A never saw: back faces, and faces hidden behind other objects receive the photo of whatever was in front of them, stretched across the surface. This is invisible through camera A but breaks every fly-through with camera B, and it is the first item under "Known limitations" in the README. The photo-projection skill already solved it in its own scripts (visibility bake from camera A, then a fill texture) on three real scenes; the general part belongs in the add-on so every user gets it and the skill stops patching the add-on's material from outside.

## What Changes

- Remap also bakes a **visibility mask** for each object: white where camera A sees the surface, black where it is hidden by other objects or faces away from camera A. The mask is saved next to the baked texture (or packed, like the texture).
- The remapped material shows the photo only where the mask is white. Elsewhere it shows a **Hidden** input: by default a flat neutral colour taken from the visible texels; the user (or the skill) can plug any colour or texture into it.
- New Remap setting **Grazing threshold** (default 0, off): when raised, surfaces seen at a very shallow angle from camera A also count as hidden, which helps fly-throughs at the cost of changing the view through camera A on those surfaces.
- While baking the mask, lights already in the scene and the frame-filling projection card are excluded, so the user's lighting and the card cannot spoil the mask; everything is restored afterwards.
- Areas outside camera A's frame stay transparent, as today.
- **Behaviour change:** remapped objects now show the Hidden colour instead of smeared photo on hidden areas. The render through camera A is unchanged (with the default threshold 0).

## Capabilities

### New Capabilities

### Modified Capabilities
- `projection-remap`: the baked result gains a visibility mask and a Hidden input; the saved-image and restored-settings requirements cover the mask and the temporary lighting changes; a new grazing-threshold setting.

## Impact

- Code: `perspective_projector/blender/remap.py` (third bake pass, mask image, material with Hidden input), `props.py` (grazing threshold), `ui.py` (Projection panel). The bake-pass helpers follow the existing `_RenderState` / `_bake` pattern.
- Remap takes longer: one more Cycles bake per object (shadow pass, a few samples).
- Files: one more PNG per remapped object, `<object>_vis.png`, in the same textures folder.
- No new dependencies; single-file offline install unchanged.
- The photo-projection skill can drop its own visibility bake and plug its Ripper texture into the Hidden input (follow-up in that project).
