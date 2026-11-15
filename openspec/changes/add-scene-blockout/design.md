# Design

## Context

See proposal.md for motivation. Existing pieces this builds on:

- `blender/view.py` maps viewport region pixels to normalised photo coordinates of camera A (`camera_frame_region`, `region_to_image`) and switches the view to camera A (`look_through`).
- `blender/ops_calibrate.py` `PP_OT_pick_point` is a working modal click-on-photo operator (crosshair, Esc/right click cancel, wheel/middle mouse pass-through).
- `core/solve.py` has the ground-hit and "point vertically above a ground point" maths (`ground_hit`, `measure_reference` Z case) for the calibration camera at the origin.
- The field test did the same job with a ray built from camera A's `view_frame()` and `matrix_world` and simple axis-plane intersections; that approach already includes any lens shift.

## Goals / Non-Goals

**Goals:**
- Floor, Wall, Box and Ceiling tools driven by clicks, plus the alignment overlay.
- Every tool usable from Python with explicit photo coordinates, so tests and scripted pipelines (the `photo-projection` skill drives Blender through MCP) do not need mouse events.

**Non-Goals:**
- Sloped planes (roofs, ramps), cylinders, freeform meshes.
- Editing blockout objects after creation beyond normal Blender editing.
- Keeping blockout objects in sync when the calibration later changes (they are plain objects in world space; re-run the tool if the camera changes).

## Decisions

### 1. Rays come from camera A itself; maths lives in core
The Blender layer turns a photo coordinate `(u, v)` into a world ray using camera A's `view_frame(scene)` corners and `matrix_world` (bilinear point on the frame, then normalise), exactly as in the field test. This respects lens, sensor fit and shift without re-deriving them. A new `core/blockout.py` takes rays as numpy arrays and does: ray-plane hit, closest point on a vertical line to a ray (height click), axis snapping of a direction, footprint rectangle from two corners, ceiling extent from boxes. Alternative considered: reuse `solve.Solution` rays; rejected because blockout must follow camera A as it is in the scene (the user may tweak it by hand), not the last solution.

### 2. Surface hits: blockout objects first, then the ground
For each click, cast the ray against the meshes of the `Blockout` collection with `Object.ray_cast` in object space (few objects, so a loop is cheap) and keep the nearest hit; otherwise intersect the plane z = 0. The hit records the surface normal, which the tools use: a horizontal hit is a base for Box/Floor, a vertical hit is a base for Ceiling. Alternative considered: `Scene.ray_cast`; rejected because it also hits projected photo planes, cameras' helpers and user geometry outside the blockout.

### 3. Height from a click
For Wall and Box tops, the third click is converted to the point on the vertical line through the base point that is closest to the click ray (the same construction as `measure_reference` for Z). This is independent of what lies behind the click, so tops can be picked against the sky or a window.

### 4. One operator per tool: modal for people, execute for scripts
Each tool is an operator with a hidden `points: FloatVectorProperty` collection of photo coordinates. `invoke` runs the modal click loop (based on `PP_OT_pick_point`) and fills `points`; `execute` builds the object from `points`. Calling `execute` directly with points is the scripting and test path. Both paths end in one `FINISHED` with `{"REGISTER", "UNDO"}`, giving one undo step.

### 5. Live preview and alignment overlay share one draw handler
A `POST_PIXEL` draw handler on `SpaceView3D` draws, only while the view looks through camera A: (a) the in-progress tool's clicked points and rubber-band lines, (b) when the overlay toggle is on, the edges of objects in the `Blockout` collection and of projected objects, projected with `world_to_camera_view` and mapped with `view.image_to_region`. Edges are drawn with a dark outline under a bright line so they read over any photo. Alternative considered: setting objects to wire display; rejected because it changes user display settings and still hides the photo behind solid faces of other objects.

### 6. Object conventions
Meshes are created with bmesh, flat faces with outward normals, object origin at the footprint centre on the base surface, names `Floor.001`, `Wall.001`, `Box.001`, `Ceiling.001`, all in a `Blockout` collection created on demand. No modifiers or materials, so Project adds its own as today.

## Risks / Trade-offs

- [Grazing-angle clicks (floor near the horizon) give huge or unstable hits] -> reject hits farther than a limit (e.g. 1000 x camera height) and say so in the status bar.
- [Snapping a nearly-axis wall can shift its far end visibly] -> snap only within 5 degrees and keep the first base point fixed; the overlay makes any error visible.
- [Overlay cost with many projected objects] -> draw only edges of the objects' evaluated meshes without subdivision (base mesh), batched once per redraw.
- [Lens shift from `complete-vanishing-point-cases`] -> no work needed here because rays come from camera A's frame; a test with a shifted camera A guards it once that change lands.
