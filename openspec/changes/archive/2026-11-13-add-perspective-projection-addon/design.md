# Design

## Context

The repository is empty apart from OpenSpec scaffolding; this is a greenfield Blender add-on. Blender 5.1 and 5.2 are installed on the development machine. Motivation and scope are in proposal.md; behaviour is in `specs/camera-calibration`, `specs/camera-projection` and `specs/projection-remap`.

Constraints that shape the approach:
- Blender ships numpy but not OpenCV; users must not run pip (spec: "Works out of the box").
- The designer's existing workflow uses the UV Project modifier with a Simple subdivision; the add-on automates that chain rather than replacing it.
- fSpy is the reference for calibration maths and manual line UX.

## Goals / Non-Goals

**Goals:**
- Calibration maths and vanishing-point detection as pure Python/numpy modules, testable outside Blender.
- Thin Blender layer (operators, panel, viewport editor) that only maps solved parameters onto Blender data.
- All state needed to re-open a calibration lives in the .blend.

**Non-Goals:**
- Lens distortion, off-centre principal point (cropped photos are calibrated as if uncropped).
- Visibility/occlusion masks, stretch masks, hole filling or inpainting.
- Depth estimation or automatic geometry beyond the frustum-fitted plane.
- Several projection cameras blending onto one object.

## Decisions

### D1. Package as a Blender Extension (4.2+) with bundled OpenCV wheels
`blender_manifest.toml` lists `opencv-python-headless==4.11.0.86` wheels for win_amd64, macosx (x86_64, arm64) and manylinux x86_64 (pinned: 4.12+ require numpy 2, while Blender 4.2 ships numpy 1.26; 4.11 runs on both numpy 1.26 and 2.x); Blender installs them offline with the extension. Platform-specific builds are produced with `blender --command extension build --split-platforms`.
- Alternative: pip-install on first enable. Rejected: needs internet and admin rights in some setups, the exact friction we are removing.
- Alternative: own line detector in numpy (Canny + Hough). Rejected for v1: slower and noisier than LSD; kept as a possible fallback if wheel size becomes a problem.

### D2. Module layout
```
perspective_projector/
  blender_manifest.toml
  __init__.py            register/unregister
  core/                  pure numpy, no bpy imports
    lines.py             LSD wrapper, segment filtering
    vp_detect.py         Manhattan vanishing point search + confidence
    solve.py             VPs -> focal, rotation; origin/height/reference scale
    exif.py              minimal JPEG/TIFF EXIF reader for focal length
  blender/
    props.py             PropertyGroup stored on the scene (calibration state)
    camera.py            apply solution to camera A, background, resolution
    projection.py        plane, subdivision, UV Project, material, camera B
    remap.py             unwrap, bake, save/pack, material switch
    editor.py            manual line editor (gizmos + gpu drawing)
    ui.py                N-panel
tests/
  core/                  pytest, plain Python
  blender/               scripts run with `blender --background --python`
```
`core/` never imports `bpy`, so the hard maths is unit-tested with synthetic data (lines generated from a known camera, solved back).

### D3. Vanishing point detection: LSD + Manhattan 2-line exhaustive search
Downscale the photo only above 4096 px on the long side (measured on synthetic scenes: LSD at 1500 px biases slanted segments, 0.29° rotation error vs 0.05° at full resolution, and full-resolution LSD takes ~0.4 s at 4000 px), run `cv2.createLineSegmentDetector`, drop segments shorter than ~2% of the diagonal. Generate hypotheses with the 2-line method (Lu et al., 2017): two segments give VP1; for sampled focal lengths, orthogonality fixes a great circle for VP2 and a third segment pins it; VP3 = cross product. Score each hypothesis by length-weighted inlier segments (angular error below ~1.5 degrees); keep the best. Candidates are all pairs of the 60 longest segments plus random pairs, and three independent runs are made, keeping the one that explains the most edge length (on real photos a single run swung between optima: towers 0.43-0.85 confidence). Then rotation only is refined over the inliers of all supported axes with Levenberg-Marquardt (refining the focal too was biased towards short focals on real photos). The focal is the median of the pairwise estimates of well-supported finite VPs, accepted only in 8-400 mm (35 mm eq.).
- Confidence = share of edge length explained, scaled by the second-strongest direction (full at 15%: one direction alone, like forest trunks, is not a camera), x0.85 with only two axes, x0.5 when the focal is unobservable without EXIF, and lowered when pairwise focal estimates disagree by more than 1.25x (cropped photos). Threshold 0.5, tuned on the real photos in tests/data (README there). Below threshold → open the manual editor seeded with the best hypothesis (spec: "Confidence and manual fallback").
- Editor seeding without a known focal (one-point views): the pair is the VP nearest the image centre plus the best-supported other axis, even when the central VP has few edges (the two other axes already fix the rotation); with fewer than two edges for it, two guide lines from the lower corners point at it. Two VPs far towards infinity would give no camera even after the user enters a focal.
- Axis assignment: the VP whose inlier segments are closest to image-vertical becomes Z; of the other two, the one more to the right in the image becomes X. Swap X/Y rotates the solution 90 degrees about Z.
- EXIF: only FocalLengthIn35mmFilm is used; FocalLength + FocalPlaneXResolution is unreliable (a Fujifilm X100T photo gave 13.9 mm instead of 35 mm).
- Alternative: J-Linkage clustering then orthogonalisation. Rejected: slower, and it does not use the orthogonality constraint during the search.
- Alternative: learned calibration (Perspective Fields, GeoCalib). Rejected: requires torch, the heavy dependency we ruled out.

### D4. Calibration maths as in fSpy
With principal point P at the image centre: `f = sqrt(-(V1-P)·(V2-P))`; axis directions `d_i = normalize(V_i - P, -f)`, third axis by cross product, then re-orthonormalised. Rotation goes into camera A as a world matrix; focal goes into Blender with sensor fit set to the photo's longer side and a 36 mm sensor width. If one of the two VPs used is at infinity (e.g. one-point perspective), focal comes from EXIF (35 mm equivalent); without EXIF the pair is reported invalid until the user switches Focal length to Manual, so a parallel pair in the editor is flagged (spec: "Degenerate lines") rather than silently solved with a default focal (spec: "Focal length recovery").
- Position: camera at (0, 0, height) relative to the ground point under it, then shifted so the world origin is the ground point at the image centre ray (default) or the user-picked origin. Reference distance rescales the camera position only, which keeps the view through camera A unchanged.

### D5. Manual editor with gizmos, drawing with `gpu`
Endpoints are `GizmoGroup` handles in the camera view, so dragging, snapping and undo behave like native Blender tools; lines and the resulting vanishing points are drawn with a `SpaceView3D` draw handler. Endpoints are stored in normalised image coordinates (0..1) in the scene `PropertyGroup`; every update re-runs `core/solve.py` and rewrites camera A. Invalid configurations keep the last valid camera (spec: "Degenerate lines").
- Alternative: a modal operator handling mouse events directly. Rejected: re-implements hit testing and loses gizmo highlighting; harder to keep undo clean.

### D6. Projection uses the UV Project modifier (designer's workflow)
Modifier stack per object: `Subdivision (Simple)` → `UV Project (projector = camera A, uv_layer = "ProjUV", aspect_x/aspect_y = W/H of photo normalised to the shorter side)`. Subdivision level: project the object's bounding-box corners into camera A, estimate the longest edge in photo pixels, pick the smallest level with edges ≤ 32 px, cap at 6.
- Alternative: shader-side projection with the camera matrix (per-pixel correct, no subdivision). Rejected for v1 because the designer works with the modifier, and Remap must bake from a UV map anyway.

Material: Image Texture (extension Clip, sRGB) → Emission strength 1, mixed with Transparent BSDF by opacity = texture alpha × [0 ≤ u ≤ 1] × [0 ≤ v ≤ 1] computed from the projection UVs. The UV test is required: Cycles reports alpha 1 outside a clipped image that has no alpha channel (JPEG, grey PNG), so texture alpha alone repeats the photo outside the frame in Cycles and in the Remap bake. Project also sets the scene view transform to Standard so the emitted photo keeps its original colours. One shared material per photo, reused across projected objects.

Plane: built in camera A's local space at distance D, size `2·D·tan(fov/2)` along the sensor-fit axis, the other side by aspect, parented to nothing (world space) and tagged with a custom property so "Changing the plane distance" can rebuild it. Camera B: `camera_A.copy()` plus a copy of its data, named `Render_Cam_B`, set as `scene.camera`; found again by tag, not by name.

### D7. Remap bakes Emit with Cycles
For each projected object: pick or create the regular UV map (Smart UV Project with island margin when none exists), create an 8-bit RGBA image at the computed resolution, add a temporary Image Texture node pointing at it as the active node, switch the scene to Cycles with 1 sample, `bpy.ops.object.bake(type='EMIT')`, then bake alpha via a second Emit pass of the texture alpha into the same image's alpha channel (Emit drops alpha). Save as PNG to `//textures/<object>_remap.png` or pack if the file is unsaved. Then build a new material (Image Texture on the regular UV map → Emission, alpha → Transparent), remove the UV Project modifier, keep Subdivision. Render engine and bake settings are captured before and restored after in a `try/finally` (spec: "Remap leaves render settings unchanged").
- Alternative: write UVs by reprojecting vertices and resampling the image in numpy. Rejected: re-implements Blender's rasteriser and breaks on subdivided meshes.

### D8. State and identification
All calibration inputs live in `scene.perspective_projector` (PropertyGroup): image reference, line endpoints, axis assignment, height, origin, reference points and distance, last confidence. Camera A, camera B, the projection plane and projected objects are identified by a custom property `pp_role`, so renaming objects does not break the add-on.

## Risks / Trade-offs

- [Auto detection fails on organic or cluttered scenes] → confidence check routes to the manual editor pre-seeded with the best guess; the editor is the main fallback, not an afterthought.
- [Cropped photos or lens distortion give wrong focal] → documented limitation; the manual editor lets the user enter focal by hand.
- [OpenCV wheels make the extension large (~40-60 MB per platform)] → split-platform builds keep each download to one wheel; numpy-only detector stays as a fallback option.
- [UV Project is per-vertex, so low subdivision shows bending] → automatic level from projected edge length; level is user-editable.
- [Bake drops alpha in Emit mode] → separate alpha pass written into the alpha channel.
- [Baking replaces texture on faces not visible from camera A (e.g. back of a box)] → accepted: out of scope (no occlusion masks); the designer cleans these by hand.
- [Gizmo API changes between 4.2 and 5.x] → test the editor on 4.2 LTS and the installed 5.2.

## Open Questions

- Default distance D for the frustum-fitted plane (starting value: 10 m); can be tuned during implementation without changing specs.
- Exact confidence threshold; to be set from a small set of test photos during implementation.
