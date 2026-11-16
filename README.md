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

1. Get the zip for your platform, e.g. `perspective_projector-1.2.1-windows_x64.zip`. To build it yourself, run these from the repository root. The OpenCV wheels are not stored in git; the first command downloads the four pinned wheels from PyPI.
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
- **Third pair**: adds four more handles for the remaining axis. When all three pairs converge (three finite vanishing points), the lens shift (principal point) is solved from them instead of being assumed at the centre.
- **Swap X/Y**: turns the scene 90° about Z without changing what camera A sees.
- **Focal length**:
  - *Auto* takes it from the vanishing points. When the lines do not fix it (one-point perspective), it uses the known size if set (see below), then EXIF.
  - *Manual* always uses the 35 mm-equivalent value you enter.
- **Lens shift**: when the vertical lines are parallel in the photo (a Z pair that does not converge), camera A stays level and the horizon's offset from the centre becomes vertical lens shift instead of a tilt. This is how architectural renders are usually made. The panel shows the shift and where it came from.

Which layout is which:

| What you see in the photo | What to set |
|---|---|
| Two horizontal directions converge, verticals converge | Nothing extra |
| Two horizontal directions converge, verticals parallel | A Z pair with parallel lines: lens shift is applied |
| Only one horizontal direction converges (corridor, street) | **Use known size** (or EXIF / Manual focal) |
| All three directions converge, photo was shifted or cropped | **Third pair** |

**Position and Scale** (optional):

- **Camera height**: 1.6 m by default; changing it scales the scene, and the view stays the same.
- **Pick Origin**: click a ground point on the photo to make it the world origin.
- **Use known size**: pick **A Start / A End** on the ground along one horizontal axis and **B Start / B End** along the other, and type their real lengths (for example the length and the depth of a bench, or a tile's two sides). In a one-point photo this solves the focal length; in every case it sets the scale. It replaces the camera height and the reference distance while it is on.
- **Use reference distance**: pick two points along an axis and type their real distance. X/Y points lie on the ground; for Z, the start is on the ground and the end is straight above it.

### 2. Blockout (optional)

Build simple geometry that lines up with the photo by clicking on it in camera A's view (the tools switch the view to camera A). Objects go into a `Blockout` collection as `Floor.001`, `Wall.001`, `Box.001`, `Ceiling.001`, ready for Project and Remap.

- **Floor**: click the corners of a floor area; Enter or a click on the first corner finishes.
- **Wall**: click two points where the wall meets the floor (or another blockout surface), then a point on its top edge. The base snaps to X or Y when it is within 5° of it.
- **Box**: click two opposite corners of a footprint, then its top edge. The box stands on whatever you clicked: the floor, the top of another box, or a wall. On a wall the third click sets how far the box sticks out (balconies, pylons).
- **Box from Edge**: for furniture against a wall, whose far footprint corner is hidden behind it: click the near bottom corner (on the floor or a box top), the top of that vertical edge, then the opposite top corner.
- **Ceiling**: click where the ceiling meets a wall of the blockout; the ceiling spans the whole blockout (build the floor or two walls first).
- Clicks land on blockout objects first, then on the floor. Esc or right click cancels a tool; each tool is one undo step.
- **Alignment overlay**: draws the edges of blockout and projected objects over the photo through camera A, so a misplaced object shows at once.
- **No floor in the photo** (looking up at a building): **Pick Reference Corner** and click a vertical corner edge of the building, set the **Assumed distance** to that corner, and choose the reference plane **Along X** or **Along Y**. Clicks that hit neither a blockout object nor the floor land on that vertical plane, so walls and boxes can be built on the facades. The scale is a guess: the panel says so, and doubling the distance doubles everything without changing what camera A sees. Switch the plane before clicking the other facade.

A good order is floor, walls, boxes, ceiling; then select the `Blockout` collection and press **Project**, then **Remap**.

From Python, every tool takes the clicks as photo coordinates (`u` right, `v` down, 0 to 1), so scripts do not need a mouse:

```python
import bpy

def clicks(*uvs):
    return [{"name": str(i), "uv": uv} for i, uv in enumerate(uvs)]

ops = bpy.ops.perspective_projector
ops.blockout_floor(points=clicks((0.2, 0.9), (0.8, 0.9), (0.7, 0.6), (0.3, 0.6)))
ops.blockout_box(points=clicks((0.40, 0.80), (0.55, 0.75), (0.55, 0.65)))
```

### 3. Project

- With nothing selected, **Project** creates `Proj_Plane`, a card with the photo's aspect ratio that exactly fills camera A's frame. **Plane distance** moves it along the view and keeps it fitted.
- With meshes selected (your blockout), the projection goes onto them instead. Non-mesh objects are skipped.
- Each projected object gets:
  - a **Simple** subdivision, level chosen so edges stay under ~32 photo pixels in camera A, up to level 6, editable on the modifier;
  - a **UV Project** modifier from camera A with the photo's aspect;
  - an emission material that shows the photo unlit and is transparent outside camera A's frame.
- Camera B (`Render_Cam_B`) is created once as a copy of camera A and becomes the scene camera. Move or animate it for parallax. Camera A stays where it is as the projector.
- Project switches the scene's view transform to **Standard** so the photo keeps its original colours.

### 4. Remap

- Select projected objects and press **Remap**. Each one is baked with Cycles into a texture on a regular UV map:
  - an existing UV map is reused;
  - otherwise a Smart UV unwrap named `RemapUV` is created.
- The material switches to the baked texture, the UV Project modifier is removed, and the subdivision stays. The object no longer depends on camera A.
- **Remap resolution**: 0 (auto) picks a power of two between 1024 and 8192 from how many photo pixels the object covers. Set a number to override it.
- **Visibility mask**: Remap also works out which parts of each object camera A really sees. Faces turned away from camera A and faces hidden behind other objects do not get the photo. They show the material's **Hidden** colour instead: a flat colour taken from the visible part. Replace the `Hidden` node with any colour or texture (link it into the mix's A input). The view through camera A does not change.
- **Grazing threshold**: 0 by default. Raise it (in degrees) to also treat surfaces seen almost edge-on from camera A as hidden, which removes stretched photo on long floors and walls when camera B flies over them. Those surfaces then show the Hidden colour through camera A too.
- Textures are saved to `textures/<object>_remap.png` and the masks to `textures/<object>_vis.png` next to the .blend file. If the file has never been saved, they are packed into it.
- The render engine, bake settings and lights are restored afterwards; your own lights do not affect the mask.
- Projected and remapped objects render with their faces in depth order in EEVEE as well as Cycles. Objects remapped with version 1.2.0 or earlier keep their old material, where EEVEE can show the far faces through the near ones; remap them again (or set the material's Render Method to Dithered) to fix that.

Calibrate, Project and Remap are each a single undo step.

## Known limitations

- **Lens distortion is not corrected.** Strong wide-angle distortion bends straight lines and lowers accuracy.
- **The principal point is at the image centre unless the photo says otherwise.** Parallel verticals give vertical shift, and a third converging pair gives both shifts. A cropped photo with converging verticals and only two pairs still calibrates as if uncropped.
- **The live projection is not masked.** Before Remap, the photo still lands on faces camera A cannot see; Remap fixes that with the visibility mask.
- **Hidden areas are not filled with real content.** After Remap they show the flat Hidden colour; paint them or plug a texture into the `Hidden` node.
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
