# Tasks

## 1. Core maths

- [x] 1.1 Add `perspective_projector/core/blockout.py` with ray-plane hit, third click along a base normal (closest point on a line to a ray), axis snapping within 5 degrees, footprint rectangle from two corners on a horizontal or vertical base, reference corner from a ray and a distance, and ceiling extent; verify `tests/core/test_blockout.py` with synthetic cameras (hits reproject to their pixels within 0.1 px, snapping on/off at 4 and 6 degrees, grazing hits beyond the limit rejected, depth click on a vertical base reprojects within 0.1 px)

## 2. Clicks and surfaces in Blender

- [x] 2.1 Add photo-coordinate to world-ray conversion from camera A's frame and the surface hit (Blockout meshes first, then ground) in a new `blender/blockout.py`; verify a Blender test where rays through known pixels hit a ground point and the top of an existing box at their true positions
- [x] 2.2 Add a modal click base (crosshair, status text, Esc/right click cancel, navigation pass-through) shared by the tools, derived from `PP_OT_pick_point`; verify by a UI test that a tool started and cancelled leaves the scene unchanged
- [x] 2.3 Add the reference corner: scene properties (photo coordinate, assumed distance, selected axis), a pick operator, the reference planes as the last click target, and the "scale assumed" state; verify a Blender test with a synthetic camera looking up at a facade (no ground in view): a wall built with the X plane reprojects within 2 px, and doubling the distance doubles its size without changing its outline through camera A

## 3. Tools

- [x] 3.1 Floor tool (polygon from clicked corners, Enter or first-corner click to finish); verify a Blender test calling `execute` with points: corners reproject within 1 px through camera A
- [x] 3.2 Wall tool (two base points, top click, axis snapping); verify Blender tests for an axis wall and a 30-degree wall: edges reproject within 2 px, snapping as specified
- [x] 3.3 Box tool (two footprint corners on floor, on a box top or on a vertical base; third click is the height or the depth out of the facade); verify Blender tests for a bench on the floor, a box on a table top (base at the table height) and a balcony on a wall (back face in the wall, front edge reprojects within 2 px)
- [x] 3.7 Box from Edge (near bottom corner, top of that edge, opposite top corner; horizontal bases only) as its own operator and panel button; verify a Blender test with a bench against a wall whose far footprint corner is hidden: the three clicked points reproject within 2 px and the box spans floor to top
- [x] 3.4 Ceiling tool (height from a click on a vertical blockout surface, extent from the blockout); verify Blender tests for the wall case and the "not on a wall" refusal
- [x] 3.5 Blockout collection, naming and object conventions; verify a Blender test that Project and Remap on all blockout objects render through camera A like the photo (same tolerance as `test_remap.py`)
- [x] 3.6 Undo: verify `tests/blender/test_ui_undo_blockout.py` creates a box and one Ctrl+Z removes only it

## 4. Overlay and panel

- [x] 4.1 Draw handler for tool preview and the alignment overlay (outlined edges, only through camera A); verify a UI test that redraws the viewport with the overlay on, moves a box and sees the overlay's edge positions move, and gets no edges when not looking through camera A or with the overlay off
- [x] 4.2 Blockout sub-panel with the four tools, the overlay toggle and the reference corner (pick, distance, X/Y plane, "scale assumed" note), disabled with a hint before calibration; verify by a Blender test of the panel poll, the operators' poll and the note appearing only while a reference corner is set
- [x] 4.3 README: Blockout section (tool order: floor, walls, boxes, ceiling; then Project + Remap) and the scripting form (`execute` with points); verify the scripted example runs in background Blender

## 5. Integration

- [x] 5.1 Rebuild the field-test room (`room_projector.blend` photo) with the tools and compare with the hand-built scene (right wall y -0.211 vs -0.211, wall top 2.064 vs ceiling 2.077, bench by Box from Edge within 4 cm), and build the base column face of the skill's worm's-eye tower photo (`tower_photo.png`) with a reference corner (plane y 4.578 vs 4.578, x 3.861-4.372 vs 3.879-4.372, top 5.646 vs 5.653); positions were compared with the hand-built scenes (themselves checked by edge overlays), and the full test suite runs on Blender 5.3

## Workflow follow-up

- Archive the change after review; update the `photo-projection` skill to call the Blockout operators instead of its own raycasting.
