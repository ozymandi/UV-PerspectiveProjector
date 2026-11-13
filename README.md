# Perspective Projector

A Blender add-on that matches a camera to a photo and projects the photo onto geometry, in three buttons:

1. **Calibrate**: finds the vanishing points in the photo and creates the projection camera (camera A) with the photo as its background.
2. **Project**: projects the photo from camera A onto a plane that fills the frame, or onto your own meshes, and adds a movable render camera (camera B).
3. **Remap**: bakes the projection into regular UVs and a texture, so the object keeps its look when it or camera B moves.

No fSpy, no external tools, no Python packages to install.

## Requirements

- Blender 4.2 or newer (tested on Blender 4.2.23 LTS and 5.2.1 LTS).
- Windows x64, macOS (Apple Silicon or Intel) or Linux x64.

## Install

1. Get the zip for your platform, e.g. `perspective_projector-0.1.0-windows_x64.zip`. To build it yourself, run these from the repository root. The OpenCV wheels are not stored in git; the first command downloads the four pinned wheels from PyPI.
   ```
   python tools/fetch_wheels.py
   blender --command extension build --source-dir perspective_projector --output-dir build --split-platforms
   ```
2. In Blender: **Edit → Preferences → Get Extensions → (drop-down, top right) → Install from Disk…** and pick the zip. Installing works offline because OpenCV is bundled.
3. Open the 3D Viewport sidebar (**N**) → **Projector** tab.

## Workflow

### 1. Calibrate

- **Load Photo**: JPEG, PNG, TIFF, EXR or WebP.
- **Calibrate**: detects straight edges and three orthogonal vanishing points, then sets:
  - camera A (`Proj_Cam_A`): focal length, rotation and position;
  - the photo as camera A's background;
  - the render resolution to the photo size.
- If detection is confident, you are done. If not (organic scenes, few straight edges), the line editor opens with the best guess already placed.
- **Edit Lines**: drag the eight round handles over the photo. There are two pairs of lines, and each pair runs along one scene axis (red X, green Y, blue Z). Camera A updates live while you drag. An invalid pair turns orange, and the camera keeps its last valid state.
- **Pair 1 / Pair 2**: which axis each pair follows.
- **Swap X/Y**: turns the scene 90° about Z without changing what camera A sees.
- **Focal length**:
  - *Auto* takes it from the vanishing points, or from EXIF when one vanishing point is at infinity.
  - *Manual* uses the 35 mm-equivalent value you enter. Use it for one-point perspective photos without EXIF.

**Position and Scale** (optional):

- **Camera height**: 1.6 m by default; changing it scales the scene, and the view stays the same.
- **Pick Origin**: click a ground point on the photo to make it the world origin.
- **Use reference distance**: pick two points along an axis and type their real distance. X/Y points lie on the ground; for Z, the start is on the ground and the end is straight above it.

### 2. Project

- With nothing selected, **Project** creates `Proj_Plane`, a card with the photo's aspect ratio that exactly fills camera A's frame. **Plane distance** moves it along the view and keeps it fitted.
- With meshes selected (your blockout), the projection goes onto them instead. Non-mesh objects are skipped.
- Each projected object gets:
  - a **Simple** subdivision, level chosen so edges stay under ~32 photo pixels in camera A, up to level 6, editable on the modifier;
  - a **UV Project** modifier from camera A with the photo's aspect;
  - an emission material that shows the photo unlit and is transparent outside camera A's frame.
- Camera B (`Render_Cam_B`) is created once as a copy of camera A and becomes the scene camera. Move or animate it for parallax. Camera A stays where it is as the projector.
- Project switches the scene's view transform to **Standard** so the photo keeps its original colours.

### 3. Remap

- Select projected objects and press **Remap**. Each one is baked with Cycles into a texture on a regular UV map:
  - an existing UV map is reused;
  - otherwise a Smart UV unwrap named `RemapUV` is created.
- The material switches to the baked texture, the UV Project modifier is removed, and the subdivision stays. The object no longer depends on camera A.
- **Remap resolution**: 0 (auto) picks a power of two between 1024 and 8192 from how many photo pixels the object covers. Set a number to override it.
- Textures are saved to `textures/<object>_remap.png` next to the .blend file. If the file has never been saved, they are packed into it.
- The render engine and bake settings are restored afterwards.

Calibrate, Project and Remap are each a single undo step.

## Known limitations

- **Lens distortion is not corrected.** Strong wide-angle distortion bends straight lines and lowers accuracy.
- **The principal point is assumed at the image centre.** Cropped photos calibrate as if uncropped.
- **No occlusion or stretch masks.** Projection and Remap also put the photo on faces camera A cannot see (for example the back of a box) and stretch it on faces seen edge-on. Clean these up by hand.
- **Areas revealed when camera B moves are not filled.** Paint them in Texture Paint or an image editor after Remap.
- **UV Project works per vertex.** On large surfaces that run close to camera A (a long floor), subdivision is capped at level 6, and faces nearest the camera can still bend slightly. Split such surfaces into smaller pieces before projecting.

## Development

```
python -m pytest tests/core          # maths and detection, plain Python (numpy, opencv-python, pillow)
python tests/run_blender.py          # build, install into build/blender_user, run tests/blender in Blender
```

Run `python tools/fetch_wheels.py` once before `tests/run_blender.py`, which builds the extension.

The real test photos are not in the repository (Pixabay's licence does not allow redistributing the files). `tests/data/sources.json` lists each one with its Pixabay id and page. Put them into `tests/data/media/` to run `tests/core/test_real_photos.py`, `tests/data/evaluate.py` and `tests/e2e/run_e2e.py`; without them the real-photo tests are skipped.

`tests/run_blender.py` uses an isolated Blender user folder, so it never touches your own preferences. Tests named `test_ui_*` open a Blender window for a few seconds (undo and viewport gizmos need one). Set `BLENDER` or pass `--blender` to use another Blender build, and `--user` to give it its own user folder, e.g.
`python tests/run_blender.py --blender path/to/blender-4.2/blender.exe --user build/blender_user_42`.
