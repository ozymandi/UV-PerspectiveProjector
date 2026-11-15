# Tasks

## 1. Core maths

- [ ] 1.1 Add `perspective_projector/core/blockout.py` with ray-plane hit, height from a click (closest point on a vertical line), axis snapping within 5 degrees, footprint rectangle from two corners and ceiling extent; verify `tests/core/test_blockout.py` with synthetic cameras (hits reproject to their pixels within 0.1 px, snapping on/off at 4 and 6 degrees, grazing hits beyond the limit rejected)

## 2. Clicks and surfaces in Blender

- [ ] 2.1 Add photo-coordinate to world-ray conversion from camera A's frame and the surface hit (Blockout meshes first, then ground) in a new `blender/blockout.py`; verify a Blender test where rays through known pixels hit a ground point and the top of an existing box at their true positions
- [ ] 2.2 Add a modal click base (crosshair, status text, Esc/right click cancel, navigation pass-through) shared by the tools, derived from `PP_OT_pick_point`; verify by a UI test that a tool started and cancelled leaves the scene unchanged

## 3. Tools

- [ ] 3.1 Floor tool (polygon from clicked corners, Enter or first-corner click to finish); verify a Blender test calling `execute` with points: corners reproject within 1 px through camera A
- [ ] 3.2 Wall tool (two base points, top click, axis snapping); verify Blender tests for an axis wall and a 30-degree wall: edges reproject within 2 px, snapping as specified
- [ ] 3.3 Box tool (two footprint corners on floor or on a box top, height click); verify Blender tests for a bench on the floor and a box on a table top (base at the table height)
- [ ] 3.4 Ceiling tool (height from a click on a vertical blockout surface, extent from the blockout); verify Blender tests for the wall case and the "not on a wall" refusal
- [ ] 3.5 Blockout collection, naming and object conventions; verify a Blender test that Project and Remap on all blockout objects render through camera A like the photo (same tolerance as `test_remap.py`)
- [ ] 3.6 Undo: verify `tests/blender/test_ui_undo_blockout.py` creates a box and one Ctrl+Z removes only it

## 4. Overlay and panel

- [ ] 4.1 Draw handler for tool preview and the alignment overlay (outlined edges, only through camera A); verify a UI test that renders the viewport with the overlay on, moves a box and sees the drawn edges move, and sees nothing when not looking through camera A
- [ ] 4.2 Blockout sub-panel with the four tools and the overlay toggle, disabled with a hint before calibration; verify by a Blender test of the panel poll and the operators' poll
- [ ] 4.3 README: Blockout section (tool order: floor, walls, boxes, ceiling; then Project + Remap) and the scripting form (`execute` with points); verify the scripted example runs in background Blender

## 5. Integration

- [ ] 5.1 Rebuild the field-test room (`room_projector.blend` photo) with the tools only and compare object positions with the hand-built scene; verify the overlay shows edges on the photo's edges and run the full test suite on Blender 4.2 LTS and 5.x

## Workflow follow-up

- Archive the change after review; update the `photo-projection` skill to call the Blockout operators instead of its own raycasting.
