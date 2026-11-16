# Design

## Context

See proposal.md for motivation. Both materials are Emission mixed with Transparent BSDF by an opacity that is 1 inside camera A's frame and 0 outside it (projection: UV range test times image alpha; Remap: baked alpha). They set `surface_render_method = "BLENDED"` (EEVEE Next, Blender 4.2+), with `blend_method = "BLEND"` as a fallback for older builds. The original design gives no reason for BLENDED beyond needing transparency. `projection_material` reuses an existing `PP_Projection_<image>` material when its `pp_version` mark is 2.

## Goals / Non-Goals

**Goals:**
- Correct face order in EEVEE for projected and remapped objects.
- Unchanged transparency outside camera A's frame in EEVEE and Cycles.

**Non-Goals:**
- Converting materials of objects remapped by earlier versions (remapping again fixes them; documented).
- Soft, partially transparent edges (the opacity is binary by design).

## Decisions

### 1. DITHERED render method
Set `surface_render_method = "DITHERED"` on both materials. DITHERED writes depth and resolves transparency stochastically; with a binary opacity the result is exact (opacity 1 renders opaque, 0 renders fully transparent), so there is no dither noise at the frame edge. Fallback for builds without `surface_render_method`: `blend_method = "HASHED"`, the older equivalent.
Alternatives considered: keep BLENDED and enable `use_transparency_overlap` / show backfaces off - backface culling would hide the inside of open meshes and the overlap option still does not sort faces of one object; an "opaque inside, clip outside" alpha-clip material - EEVEE Next has no separate alpha-clip mode, DITHERED is its replacement.

### 2. Material version mark
Raise `pp_version` of the projection material from 2 to 3, so a material made by 1.2.0 or earlier is not reused and a fresh one (with DITHERED) is built. The remap material is created new for every Remap, so it needs no mark.

### 3. Tests
A new Blender test renders a projected box and a remapped box from behind in EEVEE and in Cycles and compares them; it also re-runs Project in a file that contains an old (`pp_version` 2, BLENDED) projection material and checks the new material is DITHERED. The existing frame-transparency checks in `test_project.py` and `test_remap.py` stay as they are and must pass.

## Risks / Trade-offs

- [EEVEE's dithered transparency needs a few samples to converge at anti-aliased edges] -> the opacity is binary, and the render tests compare EEVEE with Cycles at the default sample count.
- [Users' existing remapped objects keep BLENDED] -> README note; remapping again (or setting the render method by hand) fixes them.
