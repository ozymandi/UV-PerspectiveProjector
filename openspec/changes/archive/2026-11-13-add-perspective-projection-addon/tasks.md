# Tasks

## 1. Extension scaffolding

- [x] 1.1 Create the `perspective_projector/` package with `blender_manifest.toml` (Blender 4.2+, extension id, version) and `__init__.py` that registers an empty N-panel; verify it installs from a zip in Blender 5.2 and the panel appears in the 3D Viewport sidebar
- [x] 1.2 Add `opencv-python-headless` wheels for Windows, macOS (x86_64, arm64) and Linux to the manifest and build with `blender --command extension build --split-platforms`; verify `import cv2` works inside Blender after an offline install of the Windows build
- [x] 1.3 Set up `tests/core` (pytest, plain Python with numpy + opencv) and `tests/blender` (run via `blender --background --python`); verify both runners execute a trivial passing test

## 2. Calibration maths (core, no bpy)

- [x] 2.1 Implement `core/solve.py`: two VPs → focal and rotation (fSpy formulas), third axis by cross product, re-orthonormalisation, Swap X/Y; verify with pytest that VPs projected from a known synthetic camera solve back to its focal (±0.5%) and rotation (±0.2°)
- [x] 2.2 Add single-VP mode with a given focal (EXIF or user) and degenerate-input detection (parallel lines, non-orthogonal VPs); verify pytest cases for 2-point perspective and for each degenerate case returning an error instead of a camera
- [x] 2.3 Add position solving: camera height, origin from an image point on the ground plane, reference-distance scaling; verify pytest that changing height or reference distance changes only the camera position and that the picked image point maps to world origin
- [x] 2.4 Implement `core/exif.py` reading the 35 mm equivalent focal length from JPEG/TIFF EXIF; verify against two sample photos with known EXIF and one without EXIF (returns None)

## 3. Vanishing point detection (core, no bpy)

- [x] 3.1 Implement `core/lines.py`: downscale, LSD via OpenCV, length filter, coordinates normalised back to full resolution; verify on a synthetic rendered box image that detected segments lie on the box edges
- [x] 3.2 Implement `core/vp_detect.py`: 2-line exhaustive Manhattan search, length-weighted inlier scoring, axis assignment (vertical → Z, rightmost → X), confidence value; verify on synthetic images from known cameras that focal is within ±3% and axes are assigned correctly
- [x] 3.3 Collect 8–10 real test photos (interiors, street, two-point architecture, one organic scene) under `tests/data/`, pick the confidence threshold so architectural photos pass and the organic one fails; record the threshold and results in `tests/data/README.md`

## 4. Calibrate in Blender

- [x] 4.1 Implement `blender/props.py` (scene PropertyGroup with image, lines, axes, height, origin, reference, confidence) and the image picker in the panel; verify a picked image shows its resolution in the panel and an invalid file reports an error
- [x] 4.2 Implement `blender/camera.py` + Calibrate operator: run detection, create or update camera A (tag `pp_role`), set focal/sensor fit, background image, render resolution at 100%; verify in a `tests/blender` script on a test photo that one camera A exists after running Calibrate twice and the resolution equals the photo size
- [x] 4.3 Add Swap X/Y, camera height, origin pick and reference distance controls to the panel; verify in Blender that each changes the scene axes or scale while the view through camera A stays identical (compare two viewport renders through camera A)
- [x] 4.4 Route low-confidence results to the manual editor and show confidence and focal source (auto / EXIF / user) in the panel; verify with the organic test photo that the editor opens with seeded lines
- [x] 4.5 Make Calibrate a single undo step; verify Ctrl+Z after Calibrate restores the previous camera and resolution

## 5. Manual line editor

- [x] 5.1 Implement `blender/editor.py`: GizmoGroup with eight endpoint handles in camera A's view, line and VP drawing via a `gpu` draw handler, axis assignment per pair; verify handles can be dragged in Blender 5.2 and lines follow the cursor
- [x] 5.2 Re-solve on every drag and update camera A live, keeping the last valid camera and flagging the invalid pair on degenerate input; verify dragging an X endpoint rotates camera A live and making a pair parallel shows the warning without breaking the camera
- [x] 5.3 Persist lines in the PropertyGroup and seed them from automatic detection; verify that after save/close/reopen the editor shows the same lines and camera A is unchanged
- [x] 5.4 Check the editor on Blender 4.2 LTS as well; verify the same drag and save/reopen checks pass there

## 6. Project

- [x] 6.1 Implement the frustum-fitted plane in `blender/projection.py` (photo aspect, distance D, tag `pp_role`) and the distance control that rebuilds it; verify through camera A that the plane edges coincide with the frame for a landscape and a portrait photo
- [x] 6.2 Add Simple subdivision with automatic level (≤ 32 px projected edge, cap 6) followed by the UV Project modifier (camera A, `ProjUV`, photo aspect); verify a render through camera A matches the photo and a render through a camera at 30° shows straight photo lines on the plane
- [x] 6.3 Build the shared projection material (Image Texture Clip → Emission, alpha → Transparent); verify adding a strong light does not change the photo through camera A and parts outside the frame render transparent
- [x] 6.4 Apply Project to selected meshes (skip and report non-meshes), create camera B once as a copy of A and make it the active camera; verify with three selected boxes and a light that only the boxes are projected, and that a second Project keeps a moved camera B in place
- [x] 6.5 Disable Project without calibration and make Project a single undo step; verify the disabled hint in an empty scene and that Ctrl+Z removes plane, modifiers, material and camera B

## 7. Remap

- [x] 7.1 Implement UV selection in `blender/remap.py`: reuse an existing non-projection UV map or create a Smart UV unwrap; verify the default plane gets a new UV map and a pre-unwrapped mesh keeps its own
- [x] 7.2 Implement the Cycles Emit bake with resolution from projected pixel coverage (power of two, 1024–8192, overridable) and a separate alpha pass, restoring engine and bake settings in `finally`; verify renders through camera A before and after Remap match, alpha is kept outside the frame, and an EEVEE scene is still EEVEE afterwards
- [x] 7.3 Save the image to `//textures/<object>_remap.png` or pack it when the .blend is unsaved, switch to the remap material, remove UV Project, keep Subdivision; verify the PNG exists next to a saved .blend, the plane texture moves with the plane, and deleting camera A leaves the render through camera B unchanged
- [x] 7.4 Skip and report objects without a live projection and make Remap a single undo step; verify on a mixed selection and that Ctrl+Z restores the projection modifier and material

## 8. End-to-end check and docs

- [x] 8.1 Run the full chain Calibrate → Project → move camera B → Remap on three real test photos in Blender 5.2 and 4.2; verify each step against the spec scenarios and record screenshots in `tests/e2e/`
- [x] 8.2 Write `README.md` with install, the three-button workflow, and known limitations (no distortion, centred principal point, no occlusion masks); verify a fresh install following only the README reaches a remapped plane
