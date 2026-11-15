# Proposal

## Why

After calibration the user still has to build the geometry the photo is projected onto, and the add-on only offers a single camera-facing plane. In the field test a room took twelve objects (floor, two ceilings, four walls, five furniture boxes), each placed by hand-written raycasts from camera A through measured photo pixels, and checked by drawing their edges over the photo in an external script. The add-on already knows everything needed to do this from clicks on the photo.

## What Changes

- New Blockout tools in the panel, used by clicking on the photo in camera A's view:
  - **Floor**: click the corners of a floor area; creates a ground polygon.
  - **Wall**: click two points where a wall meets the floor (or meets an existing blockout surface), then its top; creates a vertical wall. The base snaps to the X or Y axis when it is within a few degrees of it.
  - **Box**: click two opposite corners of a footprint on the floor or on another blockout surface, then its top; creates an axis-aligned box (bench, table, sofa).
  - **Ceiling**: click a point where the ceiling meets a wall; creates a horizontal plane at that height over the blockout's extent.
- Clicks land on existing blockout surfaces first, then on the ground, so objects can stand on tables or hang on walls.
- Created objects go into a `Blockout` collection with meaningful names and are ready for the existing Project and Remap.
- **Alignment overlay**: a toggle that draws the edges of blockout and projected objects over the photo in camera A's view, so misplacement is visible at a glance.
- Each tool is one undo step.

## Capabilities

### New Capabilities
- `scene-blockout`: building simple, photo-aligned geometry (floor, walls, boxes, ceilings) from clicks on the calibrated photo, and the alignment overlay that checks it.

### Modified Capabilities

## Impact

- New module(s) under `perspective_projector/blender/` for the click tools and the overlay draw handler; geometry maths (ray-plane hits, vertical height from a click, axis snapping) in `perspective_projector/core/` so it is testable without Blender.
- `ui.py`: a Blockout sub-panel. `view.py` click mapping is reused.
- Uses the camera A of `camera-calibration` as is, including lens shift once `complete-vanishing-point-cases` lands; no dependency in the other direction.
- No new dependencies; single-file offline install unchanged.
- Tests: core tests for the maths with synthetic cameras; Blender tests that drive the tools with synthetic clicks and check object positions; a UI test for the overlay.
