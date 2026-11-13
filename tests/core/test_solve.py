import numpy as np
import pytest

from perspective_projector.core import solve
from synth import SynthCamera, angle_deg

CAMERAS = [
    dict(),
    dict(yaw_deg=-20, pitch_deg=-25, roll_deg=3, focal_px=2200),
    dict(yaw_deg=-60, pitch_deg=5, roll_deg=-2, focal_px=4500, width=3000, height=4000),
    dict(yaw_deg=-45, pitch_deg=-40, focal_px=1800, width=1920, height=1080),
]


@pytest.mark.parametrize("params", CAMERAS)
def test_two_vps_recover_focal_and_rotation(params):
    cam = SynthCamera(**params)
    sol = solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "Y"), cam.width, cam.height)
    assert sol.focal_px == pytest.approx(cam.f, rel=0.005)
    assert angle_deg(sol.rotation, cam.M) < 0.2
    assert sol.focal_source == "vanishing points"


@pytest.mark.parametrize("axes", [("X", "Z"), ("Y", "Z"), ("Z", "X"), ("Y", "X")])
def test_other_axis_pairs(axes):
    cam = SynthCamera(yaw_deg=-30, pitch_deg=-20, focal_px=2500)
    idx = {"X": 0, "Y": 1, "Z": 2}
    sol = solve.solve_from_vps(cam.vp(idx[axes[0]]), cam.vp(idx[axes[1]]), axes, cam.width, cam.height)
    assert sol.focal_px == pytest.approx(cam.f, rel=0.005)
    # Z is up and the frame is right-handed whatever the pair
    assert sol.rotation[1, 2] > 0
    assert np.linalg.det(sol.rotation) == pytest.approx(1.0)
    # every axis is parallel to the true one
    for i in range(3):
        assert abs(np.dot(sol.rotation[:, i], cam.M[:, i])) == pytest.approx(1.0, abs=1e-5)


def test_z_is_up_when_looking_down():
    cam = SynthCamera(pitch_deg=-50, focal_px=2000)
    sol = solve.solve_from_vps(cam.vp(0), cam.vp(2), ("X", "Z"), cam.width, cam.height)
    assert sol.camera_rotation[2, 1] > 0  # camera's up vector has positive world Z


def test_swap_xy_keeps_view():
    cam = SynthCamera()
    sol = solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "Y"), cam.width, cam.height)
    m2 = solve.swap_xy(sol.rotation)
    assert np.allclose(m2[:, 0], sol.rotation[:, 1])
    assert np.allclose(m2[:, 1], -sol.rotation[:, 0])
    assert np.allclose(m2[:, 2], sol.rotation[:, 2])
    assert np.linalg.det(m2) == pytest.approx(1.0)
    # same camera view direction relative to the ground plane: pitch unchanged
    assert m2[2, 2] == pytest.approx(sol.rotation[2, 2])


def test_lens_mm_uses_longer_side():
    cam = SynthCamera(width=4000, height=3000, focal_px=4000)
    sol = solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "Y"), cam.width, cam.height)
    assert sol.lens_mm() == pytest.approx(36.0, rel=0.005)


def _lines(cam, axis_dir, starts):
    return [cam.segment(p, axis_dir, 2.0) for p in starts]


def test_solve_from_lines():
    cam = SynthCamera(yaw_deg=-40, pitch_deg=-10, focal_px=2800)
    x_lines = _lines(cam, (1, 0, 0), [(-1, 4, 0), (-1, 5, 2.5)])
    y_lines = _lines(cam, (0, 1, 0), [(2, 3, 0), (3, 3, 2.0)])
    sol = solve.solve_from_lines([x_lines, y_lines], ("X", "Y"), cam.width, cam.height)
    assert sol.focal_px == pytest.approx(cam.f, rel=0.005)
    assert angle_deg(sol.rotation, cam.M) < 0.2


# ---------------------------------------------------------------- single VP / given focal


def test_one_point_perspective_needs_focal():
    # camera looking straight along +Y, level: X lines are parallel in the image
    cam = SynthCamera(yaw_deg=0, pitch_deg=0, focal_px=3000)
    x_lines = _lines(cam, (1, 0, 0), [(-1, 6, 0), (-1, 6, 2.0)])
    y_lines = _lines(cam, (0, 1, 0), [(1, 3, 0), (-1, 3, 2.0)])
    with pytest.raises(solve.CalibrationError) as err:
        solve.solve_from_lines([x_lines, y_lines], ("X", "Y"), cam.width, cam.height)
    assert err.value.pair == 0
    sol = solve.solve_from_lines([x_lines, y_lines], ("X", "Y"), cam.width, cam.height, focal_px=3000)
    assert sol.focal_source == "given"
    assert angle_deg(sol.rotation, cam.M) < 0.2


def test_two_point_perspective_vertical_at_infinity():
    # level camera: vertical lines parallel, both horizontal VPs finite -> focal still solvable
    cam = SynthCamera(yaw_deg=-40, pitch_deg=0, focal_px=2600)
    sol = solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "Y"), cam.width, cam.height)
    assert sol.focal_px == pytest.approx(cam.f, rel=0.005)
    assert angle_deg(sol.rotation, cam.M) < 0.2


def test_given_focal_with_finite_vps():
    cam = SynthCamera(focal_px=3100)
    sol = solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "Y"), cam.width, cam.height, focal_px=3100)
    assert angle_deg(sol.rotation, cam.M) < 0.2


def test_focal_from_35mm():
    # 36x24 frame, 50 mm -> 50 * 6000 / 36 px along a 6000x4000 image
    f = solve.focal_from_35mm(50, 6000, 4000)
    assert f == pytest.approx(50 * 6000 / 36, rel=0.002)


# ---------------------------------------------------------------- degenerate input


def test_parallel_pair_without_focal_is_flagged():
    lines_parallel = [((0, 0), (100, 0)), ((0, 50), (100, 50))]
    lines_ok = [((0, 0), (100, 10)), ((0, 100), (100, 80))]
    with pytest.raises(solve.CalibrationError) as err:
        solve.solve_from_lines([lines_ok, lines_parallel], ("X", "Y"), 1000, 800)
    assert err.value.pair == 1


def test_zero_length_line_is_flagged():
    with pytest.raises(solve.CalibrationError) as err:
        solve.solve_from_lines([[((5, 5), (5, 5)), ((0, 0), (10, 3))], [((0, 0), (1, 9)), ((5, 0), (4, 9))]],
                               ("X", "Y"), 1000, 800)
    assert err.value.pair == 0


def test_vps_on_same_side_are_flagged():
    # both VPs to the right of the centre on the horizon: not orthogonal for any focal
    with pytest.raises(solve.CalibrationError):
        solve.solve_from_vps((3000, 500, 1), (5000, 500, 1), ("X", "Y"), 2000, 1000)


def test_same_axis_twice_is_rejected():
    cam = SynthCamera()
    with pytest.raises(solve.CalibrationError):
        solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "X"), cam.width, cam.height)


# ---------------------------------------------------------------- position and scale


def _solution(cam):
    return solve.solve_from_vps(cam.vp(0), cam.vp(1), ("X", "Y"), cam.width, cam.height)


def test_default_origin_projects_to_its_pixel():
    cam = SynthCamera(pitch_deg=-20)
    sol = _solution(cam)
    loc = solve.camera_location(sol, 1.6)
    assert loc[2] == pytest.approx(1.6)
    px = solve.project_point(sol, loc, (0, 0, 0))
    assert np.allclose(px, (cam.width / 2, cam.height / 2), atol=1e-6)


def test_default_origin_when_camera_looks_up():
    cam = SynthCamera(pitch_deg=10, focal_px=2000)
    sol = _solution(cam)
    loc = solve.camera_location(sol, 1.6)
    px = solve.project_point(sol, loc, (0, 0, 0))
    assert px[1] == pytest.approx(cam.height * 0.95)


def test_picked_origin():
    cam = SynthCamera()
    sol = _solution(cam)
    corner = cam.project((2.0, 3.0, 0.0))
    loc = solve.camera_location(sol, 1.6, origin_px=corner)
    assert np.allclose(solve.project_point(sol, loc, (0, 0, 0)), corner, atol=1e-6)


def test_origin_above_horizon_is_rejected():
    cam = SynthCamera(pitch_deg=0)
    sol = _solution(cam)
    with pytest.raises(solve.CalibrationError):
        solve.camera_location(sol, 1.6, origin_px=(cam.width / 2, 10))


def test_height_change_only_scales_position():
    cam = SynthCamera()
    sol = _solution(cam)
    corner = cam.project((2.0, 3.0, 0.0))
    a = solve.camera_location(sol, 1.6, corner)
    b = solve.camera_location(sol, 10.0, corner)
    assert np.allclose(b, a * (10.0 / 1.6))
    # the world origin projects to the same pixel at both heights
    assert np.allclose(solve.project_point(sol, a, (0, 0, 0)), solve.project_point(sol, b, (0, 0, 0)))


@pytest.mark.parametrize("axis,p0,p1,dist", [
    ("X", (0.5, 4.0, 0.0), (3.5, 4.0, 0.0), 3.0),
    ("Y", (1.0, 2.0, 0.0), (1.0, 6.5, 0.0), 4.5),
    ("Z", (1.0, 3.0, 0.0), (1.0, 3.0, 2.5), 2.5),
])
def test_reference_distance_recovers_height(axis, p0, p1, dist):
    cam = SynthCamera(location=(0.0, -8.0, 1.75))
    sol = _solution(cam)
    origin_px = cam.project((0.0, 0.0, 0.0))
    h = solve.height_from_reference(sol, cam.project(p0), cam.project(p1), axis, dist, origin_px)
    assert h == pytest.approx(1.75, rel=1e-4)
    loc = solve.camera_location(sol, h, origin_px)
    assert np.allclose(loc, cam.location, atol=1e-3)
