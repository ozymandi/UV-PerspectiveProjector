# Design

## Context

See proposal.md for motivation. Current state of the solver and storage:

- `core/solve.py`: `solve_from_vps` already takes a principal point `pp`, but every caller passes the image centre. `Solution` carries `principal_point`, and `pixel_ray` / `project_point` already use it.
- `blender/calibration.py`: `apply_solution` always sets `shift_x = shift_y = 0`, so a non-centred principal point would be lost when building camera A.
- `props.py`: lines are one `FloatVectorProperty(size=16)` (2 pairs x 2 lines x 2 points); axes are `pair0_axis` / `pair1_axis`. The reference distance (`ref_*`) only scales the scene (camera height).
- `editor.py`: the gizmo group creates 8 handles and `_draw_lines` loops over two pairs.
- Tests: `tests/core/synth.py` builds cameras with the principal point fixed at the centre.

## Goals / Non-Goals

**Goals:**
- Correct camera A in all four layouts: 2 finite horizontal VPs; 1 finite VP + parallel verticals; parallel verticals with an off-centre horizon; 3 finite VPs.
- Old files load and behave exactly as before.

**Non-Goals:**
- Lens distortion.
- Automatic detection of a third pair or of known-size segments (the editor places a third pair at a default position; the user adjusts it).
- Calibration without any vanishing point.

## Decisions

### 1. Principal point is decided before the focal length
One function picks the principal point from the line state, then the existing solving runs with it:

```
verticals parallel (Z VP at infinity)?
   yes -> pp = (cx, horizon_y)      horizon_y = row of the finite horizontal VP(s)
   no  -> third pair on and 3 finite VPs?
            yes -> pp = orthocentre of the VP triangle
            no  -> pp = (cx, cy)    (today's behaviour)
```
`horizon_y`: with one finite horizontal VP it is that VP's row; with two it is the row where the line through them crosses the image centre column (roll stays possible). Alternative considered: fit pitch and shift jointly by least squares; rejected because parallel verticals already pin the camera to zero pitch, so the closed form is exact and needs no tuning.

### 2. Shift is written to camera A from the principal point
`apply_solution` converts `pp` to Blender shift: `shift_x = (cx - pp_x) / max(w, h)` with sign so the frame moves the right way, `shift_y = (pp_y - cy) / max(w, h)` (Blender shift is in units of the larger frame side). A unit test round-trips: synthetic shifted camera -> solve -> camera A -> project known points with `world_to_camera_view` -> pixels match.

### 3. Focal length from a known size: 1-D solve
Two ground segments, one per horizontal axis, with real lengths `La` and `Lb`. For a candidate focal `f`, build the solution (rotation from the lines with the fixed `pp`), measure both segments with the existing `measure_reference` at camera height 1, and take the ratio. The lateral length barely depends on `f` while the depth length scales with it, so `ratio(f)` is monotonic; solve `ratio(f) = La / Lb` by bracketing plus bisection over a focal range equivalent to 8-300 mm. The camera height then follows from `La / measured_a(f)`, reusing `height_from_reference`. Alternative considered: closed-form formula for the level one-point case; rejected because it breaks as soon as the camera has roll or the horizontal VP is not on the axis, while the 1-D solve uses the same code path as every other case.

Storage: new properties `size_enabled`, `size_a_p0/p1`, `size_a_length`, `size_b_p0/p1`, `size_b_length`. The existing single-axis reference distance stays as is (it only scales); when the known size is enabled it also sets the scale and the reference-distance block is disabled in the UI.

### 4. Third pair stored separately
New `lines3: FloatVectorProperty(size=8)` and `pair2_enabled: Bool`; the third pair's axis is computed as the axis not used by pairs 1 and 2 (shown read-only), so it can never disagree with them. Keeping the 16-float `lines` untouched means a 1.0.0 file loads with `pair2_enabled = False` and identical results. Alternative considered: grow `lines` to 24 floats; rejected because Blender resets a property whose size changed, losing users' lines.

With three finite VPs the focal length is solved from pairs 1 and 2 with the orthocentre `pp`; the third VP is used for `pp` only, and its residual is reported in the panel as a consistency check.

### 5. Reporting
`focal_source` already holds a label; extend it with "known size" and add a `shift_applied` flag, shown in the Camera panel.

## Risks / Trade-offs

- [Orthocentre is unstable when one VP is far away] -> treat a VP beyond `INFINITE_VP_DIAGONALS` as infinite (existing rule) and fall back to the parallel-verticals or centre rule; report the third pair as invalid.
- [Shift changes what Project/Remap see] -> projection uses camera A's projection matrix through the UV Project modifier, which includes shift in Blender; add an explicit Project + Remap test with a shifted camera A.
- [Known-size bisection finds no bracket (segments badly placed)] -> report "known size cannot be solved" and keep the last camera, as the spec requires.
- [Users with converging verticals but a shifted lens] -> not distinguishable from tilt with two pairs; the third pair is the answer, documented in the panel tooltip.

## Migration Plan

New properties have defaults that reproduce 1.0.0 behaviour (`pair2_enabled = False`, `size_enabled = False`, centre principal point unless verticals are parallel). The one behaviour change for old files: a file calibrated with parallel verticals and an off-centre horizon gets level camera + shift on the next re-solve (any edit), instead of the old tilt. That is the bug being fixed; it is noted in the release notes.
