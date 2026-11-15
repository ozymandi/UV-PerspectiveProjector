# Tasks

## 1. Test fixtures

- [x] 1.1 Extend `tests/core/synth.py` `SynthCamera` with an optional principal point (lens shift) and verify the existing core tests still pass with `python -m pytest tests/core`

## 2. Principal point and lens shift

- [x] 2.1 Add the principal-point rule (parallel verticals -> horizon row; otherwise centre) in `core/solve.py` and verify new tests in `tests/core/test_solve.py`: a level synthetic camera with 15 % vertical shift solves to zero pitch and the true principal point; converging verticals keep the centre
- [x] 2.2 Pass the chosen principal point through `calibration.solve_state` and write it as `shift_x` / `shift_y` in `apply_solution`; verify a Blender test projects known world points through camera A to the synthetic camera's pixels within 1 px
- [x] 2.3 Verify Project and Remap with a shifted camera A (in `tests/blender/test_shift.py`): the render through camera A matches the photo as in the unshifted tests

## 3. Third line pair

- [x] 3.1 Add the orthocentre principal point for three finite VPs in `core/solve.py`, with degenerate-triangle and infinite-VP errors pointing at pair 3; verify core tests with a synthetic three-VP shifted camera (shift and focal within 2 %)
- [x] 3.2 Add `lines3` and `pair2_enabled` to `props.py` (the third pair's axis is computed as the one pairs 1 and 2 do not use, not stored) and use them in `solve_state`; verify `tests/blender/test_persist.py` still loads a two-pair state unchanged and a three-pair state survives save and reload
- [x] 3.3 Draw and drag the third pair in `editor.py` (4 more handles, its own colour and invalid state) and add the toggle to the Camera panel; verify `tests/blender/test_ui_editor.py` with a case that enables the pair and drags one endpoint

## 4. Focal length from a known size

- [x] 4.1 Add the known-size focal solve (bracket + bisection on the length ratio, then height) in `core/solve.py`; verify core tests on a synthetic one-point camera: focal within 3 %, both segments measure their lengths, and the above-horizon / same-axis cases raise `CalibrationError`
- [x] 4.2 Add the `size_*` properties, the pick operators for the four points (reusing `PP_OT_pick_point` targets) and the panel block, and make known size take priority over EXIF in `solve_state`; verify a Blender test that sets the points programmatically and checks lens and scale

## 5. Reporting and docs

- [x] 5.1 Show the focal source (vanishing points / known size / EXIF / manual) and "lens shift applied" in the Camera panel; verify by a Blender test reading `props.focal_source` and the shift flag for each case
- [x] 5.2 Update README (workflow section: one-point photos, renders with shift, third pair) and verify the described steps match the panel labels

## 6. Integration

- [x] 6.1 Run `python -m pytest tests/core` and `python tests/run_blender.py` on Blender 5.3 and verify all pass (4.2 LTS not installed on this machine; the user accepted 5.3 only)
- [x] 6.2 Calibrate the one-point interior photo from the field test (`room_projector.blend`) with the known-size tool on ground segments measured in that scene (floor/wall junction 0.68 m along depth, bench base 0.41 m across) and verify the result agrees with the hand-made camera there (about 18 mm equivalent); this is a consistency check, not ground truth

## Workflow follow-up

- Archive the change after review, then bump the add-on version.
