# Proposal

## Why

Calibration is reliable only in one of the four vanishing-point layouts users meet: two finite horizontal vanishing points with converging verticals. In a one-point view (corridor, street along the axis) the focal length falls back to 35 mm unless EXIF exists, so depths come out wrong (a 1.3 m bench measured 3.3 m in a real test). Architectural renders with parallel verticals and an off-centre horizon are solved as a tilted camera, so verticals no longer stay vertical. A third visible direction cannot be used at all. The add-on should calibrate correctly in any photo where a vanishing point can be found.

## What Changes

- Focal length from a known size: when the photo does not constrain the focal length (one finite horizontal vanishing point), the user marks one ground segment along each horizontal axis and enters their real lengths; the add-on solves the focal length and the scale from them.
- Lens shift for parallel verticals: when the vertical lines are parallel in the photo, camera A stays level and the horizon's offset from the image centre becomes a vertical lens shift instead of a camera tilt.
- Optional third line pair: the editor can show a third pair for the remaining axis; with three finite vanishing points the principal point is solved from them and applied as horizontal and vertical lens shift.
- The panel states which case was solved (two vanishing points, one vanishing point with a known size, EXIF, manual, shift) so the user can see where the focal length and shift came from.
- Calibration inputs saved in the .blend file include the new inputs; files saved with the current version keep loading unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities
- `camera-calibration`: focal length recovery gains the known-size and three-vanishing-point paths; the principal point is no longer always the image centre (lens shift); the manual editor gains an optional third pair; stored inputs and the reference-distance requirement grow accordingly.

## Impact

- Code: `perspective_projector/core/solve.py` (principal point and focal solving), `perspective_projector/blender/calibration.py` (solve state, applying shift to camera A), `props.py` (new stored inputs), `editor.py` (third pair handles and lines), `ui.py` (panel), `ops_calibrate.py` (picking the size segments).
- Camera A gets non-zero `shift_x` / `shift_y`; projection and remap already follow camera A's projection matrix, so they need checks, not changes.
- No new dependencies; the single-file offline install is unchanged.
- Tests: new cases in `tests/core/test_solve.py` (synthetic cameras with shift, one VP, three VPs) and `tests/blender/test_calibrate.py`.
