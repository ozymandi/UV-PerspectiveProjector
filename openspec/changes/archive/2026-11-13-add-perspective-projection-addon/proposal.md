# Proposal

## Why

Today a photo-based camera projection shot takes a manual chain across two programs: fSpy (drag vanishing lines by hand) → export → import into Blender → duplicate the camera → move it. The projection itself (plane, subdivision, UV Project with the right aspect, emission material, bake to clean UVs) is set up by hand every time and is easy to get wrong (squashed aspect, diagonal perspective break on an unsubdivided plane). We want the whole chain inside Blender, driven by a few buttons, with no external tools.

## What Changes

- New Blender add-on (Extension format, Blender 4.2+) with a panel in the 3D Viewport sidebar.
- **Calibrate**: load a photo, detect vanishing points automatically, solve focal length and camera rotation, and create the projection camera (camera A) with the photo as its background and the render resolution set to the photo size.
- Manual fallback: when automatic detection is not confident (or the user wants to correct it), the user adjusts vanishing lines directly over the photo in the camera view; the lines start pre-placed from the best automatic guess.
- **Project**: create a plane with the photo's aspect ratio that exactly fills camera A's frame (or use the selected meshes), add a Simple subdivision and a UV Project modifier from camera A with the photo's aspect, assign an emission material with the photo, and create the movable render camera (camera B) as a copy of camera A.
- **Remap**: bake the projected texture into a new regular UV map and image, switch the material to it, and remove the UV Project modifier so the object keeps its texture wherever camera B or the object moves.
- Out of scope for this change: filling holes and stretched areas revealed by camera B (stays manual), lens distortion correction, depth-based geometry, multiple projection cameras.

Assumptions taken from the exploration (designer did not object to the proposed defaults):
- The default plane is a card perpendicular to camera A, sized to its frustum at a user-adjustable distance.
- Minimum Blender version is 4.2 (Extensions with bundled Python wheels).

## Capabilities

### New Capabilities
- `camera-calibration`: recover a Blender camera (focal length, rotation, position, scale) that matches a photo's perspective, automatically with a manual correction mode, and set the photo up as that camera's background.
- `camera-projection`: project the photo from the calibration camera onto a plane or selected meshes (subdivision, UV projection with correct aspect, emission material) and provide a separate movable render camera.
- `projection-remap`: freeze a camera projection into a regular UV map and baked image so the object no longer depends on the projection camera.

### Modified Capabilities
- None (no existing specs).

## Impact

- New code: a Blender add-on package in this repository (manifest, operators, UI panel, calibration math, viewport line editor).
- New dependency: OpenCV (headless) shipped as bundled wheels inside the extension for Windows, macOS and Linux; numpy comes with Blender.
- Uses Cycles for baking during Remap (temporarily switched, then restored).
- Writes baked images next to the .blend file (or packs them when the file is unsaved).
