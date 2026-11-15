"""Principal point (lens shift) from parallel verticals and from three vanishing points."""

import numpy as np
import pytest

from perspective_projector.core import solve
from synth import SynthCamera, angle_deg

W, H = 4000, 3000


def pair(cam, direction, starts):
    return [cam.segment(s, direction, 2.0) for s in starts]


X_LINES = [(-2.0, 2.0, 0.0), (-2.0, 4.0, 2.5)]
Y_LINES = [(2.0, -2.0, 0.0), (4.0, -2.0, 2.5)]
Z_LINES = [(-1.5, 3.0, 0.0), (2.5, 3.0, 0.0)]


def lines(cam, axes):
    src = {"X": ((1, 0, 0), X_LINES), "Y": ((0, 1, 0), Y_LINES), "Z": ((0, 0, 1), Z_LINES)}
    return [pair(cam, *src[a]) for a in axes]


def shifted_level_camera(shift_frac=0.15, **kw):
    pp = (W / 2.0, H / 2.0 - shift_frac * H)  # horizon 15 % of the height above the centre
    return SynthCamera(width=W, height=H, pitch_deg=0.0, pp=pp, **kw)


def test_parallel_verticals_two_horizontal_vps_give_vertical_shift():
    cam = shifted_level_camera(focal_px=2800, yaw_deg=-35)
    pairs = lines(cam, ("X", "Y", "Z"))
    pp, kind = solve.principal_point_for(pairs, ("X", "Y", "Z"), W, H)
    assert kind == "vertical"
    assert pp == pytest.approx(cam.pp, abs=0.5)
    sol = solve.solve_from_lines(pairs[:2], ("X", "Y"), W, H, pp=pp)
    assert sol.focal_px == pytest.approx(cam.f, rel=0.005)
    assert angle_deg(sol.rotation, cam.M) < 0.1
    # level: the camera's view direction is horizontal
    view = sol.camera_rotation @ np.array([0.0, 0.0, -1.0])
    assert abs(view[2]) < 1e-6


def test_one_point_with_parallel_verticals_and_given_focal():
    cam = shifted_level_camera(focal_px=2200, yaw_deg=-3)
    pairs = lines(cam, ("X", "Z"))
    pp, kind = solve.principal_point_for(pairs, ("X", "Z"), W, H)
    assert kind == "vertical"
    assert pp == pytest.approx(cam.pp, abs=0.5)
    sol = solve.solve_from_lines(pairs, ("X", "Z"), W, H, focal_px=cam.f, pp=pp)
    assert angle_deg(sol.rotation, cam.M) < 0.1
    for p in [(1.0, 5.0, 0.0), (-2.0, 9.0, 2.0)]:
        loc = cam.location
        assert solve.project_point(sol, loc, p) == pytest.approx(cam.project(p), abs=0.5)


def test_parallel_verticals_with_roll():
    cam = SynthCamera(width=W, height=H, pitch_deg=0.0, roll_deg=4.0, pp=(W / 2.0, H * 0.4), focal_px=2600)
    pairs = lines(cam, ("X", "Y", "Z"))
    pp, kind = solve.principal_point_for(pairs, ("X", "Y", "Z"), W, H)
    assert pp == pytest.approx(cam.pp, abs=0.5)  # shift is along the sensor's y axis, not the rolled verticals
    sol = solve.solve_from_lines(pairs[:2], ("X", "Y"), W, H, pp=pp)
    assert angle_deg(sol.rotation, cam.M) < 0.1
    for p in [(1.0, 5.0, 0.0), (-2.0, 9.0, 2.0)]:
        assert solve.project_point(sol, cam.location, p) == pytest.approx(cam.project(p), abs=1.5)


def test_converging_verticals_keep_the_centre():
    cam = SynthCamera(width=W, height=H, pitch_deg=-14.0)
    pairs = lines(cam, ("X", "Z"))
    pp, kind = solve.principal_point_for(pairs, ("X", "Z"), W, H)
    assert kind == ""
    assert pp == pytest.approx([W / 2.0, H / 2.0])


def test_three_vanishing_points_give_the_principal_point():
    true_pp = (W / 2.0 + 0.06 * W, H / 2.0 - 0.1 * H)
    cam = SynthCamera(width=W, height=H, pitch_deg=-25.0, yaw_deg=-40.0, focal_px=2400, pp=true_pp)
    pairs = lines(cam, ("X", "Y", "Z"))
    pp, kind = solve.principal_point_for(pairs, ("X", "Y", "Z"), W, H)
    assert kind == "three vanishing points"
    assert np.linalg.norm(pp - cam.pp) < 0.02 * max(W, H)
    sol = solve.solve_from_lines(pairs[:2], ("X", "Y"), W, H, pp=pp)
    assert sol.focal_px == pytest.approx(cam.f, rel=0.02)
    assert angle_deg(sol.rotation, cam.M) < 0.5


def test_third_pair_parallel_is_invalid():
    cam = SynthCamera(width=W, height=H, pitch_deg=-25.0)
    pairs = lines(cam, ("X", "Z"))
    third = [((100.0, 100.0), (200.0, 100.0)), ((100.0, 300.0), (200.0, 300.0))]  # parallel in the image
    with pytest.raises(solve.CalibrationError) as exc:
        solve.principal_point_for(pairs + [third], ("X", "Z", "Y"), W, H)
    assert exc.value.pair == 2


def test_three_collinear_vps_are_invalid():
    with pytest.raises(solve.CalibrationError) as exc:
        solve.orthocentre((0.0, 0.0), (1.0, 1.0), (2.0, 2.0))
    assert exc.value.pair == 2
